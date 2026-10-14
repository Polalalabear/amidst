"""Two-child pre-reference freezes and a bounded, lossless joint release."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

import amidst.finalization.scoped_joint_release as release_module
import amidst.finalization.scoped_protocol as protocol
import amidst.finalization.scoped_reproduction as reproduction
from amidst.finalization.reviewed_pipeline import digest, freeze_inference, read_json, write_json
from amidst.obstacle_volume_authority import content_sha256

METHODS = ("shortest_path", "geometry", "spatiotemporal")
ABLATIONS = (
    "remove_travel_time", "remove_collision", "remove_topology",
    "shortest_path_only", "full_deterministic_graph",
)
SOURCE_CASES = ("case2", "case3", "case3_short_control", "case3_long_stress")


def _replace_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def children(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Only original master/authority hydration is mocked; all child hashes are real."""
    root, release = tmp_path / "root", tmp_path / "release"
    write_json(root / protocol.OFFICE_EXPORT_CONFIG, {"test_only": "original-office-export"})
    write_json(root / protocol.OFFICE_INFERENCE_CONFIG, {"test_only": "original-office-inference"})
    write_json(root / protocol.OFFICE_APPLICATION / "manifest.json", {
        "test_only": "original office authority manifest"
    })
    write_json(root / "source_export_config.json", {"test_only": "frozen source settings"})
    master = {
        "source_sha256": "a" * 64, "export_seed": 20261005, "inference_seed": 42,
        "sampling_fps": 5, "source_case_ids": list(SOURCE_CASES),
        "source_config_file_sha256": digest(root / "source_export_config.json"),
        "original_human_decisions_content_sha256": "e" * 64,
        "inference_config": {"test_only": "frozen scoped inference settings"},
        "inference_config_content_sha256": content_sha256({
            "test_only": "frozen scoped inference settings"
        }),
        "joint_release_selection": {
            "case1": "FRESH_ORIGINAL_REVIEWED_OFFICE_CHILD_CASE1",
            "case2": "FRESH_APPROVED_CORRIDOR_UNION_CHILD_CASE2",
            "case3": "FRESH_APPROVED_CORRIDOR_UNION_CHILD_CASE3",
            "other_child_case_rows_preserved": True,
            "stress_controls_are_formal_cases": False, "cross_case_aggregation": "NONE",
        },
        "office_child": {
            "application_path": protocol.OFFICE_APPLICATION,
            "export_config_path": protocol.OFFICE_EXPORT_CONFIG,
            "inference_config_path": protocol.OFFICE_INFERENCE_CONFIG,
            "selected_case_ids": ["case1"],
        },
        "protected_input_hashes": {
            protocol.OFFICE_EXPORT_CONFIG: digest(root / protocol.OFFICE_EXPORT_CONFIG),
            protocol.OFFICE_INFERENCE_CONFIG: digest(root / protocol.OFFICE_INFERENCE_CONFIG),
            protocol.OFFICE_APPLICATION + "/manifest.json": digest(
                root / protocol.OFFICE_APPLICATION / "manifest.json"
            ),
        },
    }
    master_path = root / "master.json"
    write_json(master_path, master)
    for role in ("office", "scoped"):
        dataset = release / role / "dataset"
        manifest = {
            "schema_version": "phase1-reviewed-dataset-v1" if role == "office" else (
                "phase1-scoped-source-dataset-v1"
            ),
            "dataset_version": "SYNTHETIC_FRESH_" + role.upper(),
            "source_sha256": master["source_sha256"], "export_seed": master["export_seed"],
            "inference_seed": master["inference_seed"], "sampling_fps": 5,
            "config_sha256": digest(root / protocol.OFFICE_EXPORT_CONFIG),
            "config_file_sha256": master["source_config_file_sha256"],
            "application_manifest_sha256": master["protected_input_hashes"][
                protocol.OFFICE_APPLICATION + "/manifest.json"
            ],
            "human_decisions_sha256": master["original_human_decisions_content_sha256"],
            "full_experiment_config_file_sha256": digest(master_path),
            "cases": [{"case_id": name} for name in (
                ("case1", "case2", "case3") if role == "office" else SOURCE_CASES
            )],
            "artifacts": {},
        }
        write_json(dataset / "manifest.json", manifest)
        inference = release / role / "inference_primary"
        write_json(inference / "prediction.json", {
            "test_only": "frozen synthetic prediction", "role": role,
            "provenance": "INFERRED_GAP", "source_sha256": master["source_sha256"],
        })
        if role == "scoped":
            write_json(inference / "config.json", master["inference_config"])
            write_json(inference / "experiment.json", master)
            cases = []
            gap_counts = (1, 3, 1, 3)
            for identity, count in zip(SOURCE_CASES, gap_counts, strict=True):
                gaps = []
                for index in range(count):
                    directory = f"gap{index:02d}"
                    if identity == "case3_short_control":
                        endpoints = [[2.25, 2.25, 0.0], [7.75, 2.25, 0.0]]
                    elif identity == "case3" and index == 1:
                        endpoints = [[7.75, 5.0, 0.0], [7.75, 7.75, 0.0]]
                    elif index == 2:
                        endpoints = [[7.75, 7.75, 0.0], [2.25, 7.75, 0.0]]
                    else:
                        endpoints = [[2.25, 5.0, 0.0], [7.75, 5.0, 0.0]]
                    duration = 5 if identity == "case3_short_control" else (
                        40 if identity == "case3_long_stress" else 20
                    )
                    gaps.append({
                        "gap_id": identity + ":" + directory, "gap_directory": directory,
                        "time_range": [float(index * 50), float(index * 50 + duration)],
                    })
                    write_json(inference / identity / directory / "navigation.json", {
                        "endpoint_positions_bu": endpoints
                    })
                cases.append({"case_id": identity, "gaps": gaps})
            write_json(inference / "summary.json", {"cases": cases, "ground_truth_read": False})
        else:
            write_json(inference / "collision_inference_lock.json", read_json(
                root / protocol.OFFICE_INFERENCE_CONFIG
            ))
        freeze_inference(
            inference, dataset_manifest_sha256=digest(dataset / "manifest.json"),
            config_sha256=digest(root / protocol.OFFICE_INFERENCE_CONFIG) if role == "office"
            else digest(master_path),
        )
    monkeypatch.setattr(release_module, "validate_master_bindings", lambda *_: None)
    monkeypatch.setattr(protocol, "validate_master_bindings", lambda *_: None)
    return {"root": root, "release": release, "master_path": master_path, "master": master}


def _freeze(inputs: dict[str, Any]) -> dict[str, Any]:
    return release_module.freeze_joint_inference(
        inputs["release"], inputs["master_path"], root=inputs["root"]
    )


def _require(inputs: dict[str, Any]) -> dict[str, Any]:
    return protocol.require_joint_inference_boundary(
        inputs["release"] / "joint_inference_freeze.json", inputs["master_path"],
        inputs["release"] / "office/inference_primary",
    )


def _reissue_child_freeze(inputs: dict[str, Any], role: str) -> None:
    directory = inputs["release"] / role / "inference_primary"
    old = read_json(directory / "inference_freeze.json")
    (directory / "inference_freeze.json").unlink()
    freeze_inference(
        directory,
        dataset_manifest_sha256=digest(inputs["release"] / role / "dataset/manifest.json"),
        config_sha256=old["config_sha256"],
    )


def test_joint_freeze_checks_both_real_children_before_any_reference_access(
    children: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original_open = Path.open
    opened: list[Path] = []

    def guarded_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        opened.append(path)
        assert not {"evaluation", "simulation"}.intersection(path.parts)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    joint = _freeze(children)
    assert joint["ground_truth_read"] is False
    assert joint["status"] == "ALL_PRIMARY_CHILDREN_FROZEN_BEFORE_ANY_REFERENCE_EVALUATION"
    assert set(joint["children"]) == set(joint["datasets"]) == {"office", "scoped"}
    assert joint["master_file_sha256"] == digest(children["master_path"])
    for role in ("office", "scoped"):
        manifest = children["release"] / role / "dataset/manifest.json"
        receipt = children["release"] / role / "inference_primary/inference_freeze.json"
        assert manifest in opened and receipt in opened
        assert joint["datasets"][role]["manifest_file_sha256"] == digest(manifest)
        assert joint["children"][role]["freeze_file_sha256"] == digest(receipt)
    assert _require(children) == joint
    with pytest.raises(FileExistsError, match="new complete joint"):
        _freeze(children)


@pytest.mark.parametrize("role", ["office", "scoped"])
@pytest.mark.parametrize("field", ["source_sha256", "export_seed", "inference_seed"])
def test_even_a_valid_reissued_child_cannot_change_source_or_seeds(
    children: dict[str, Any], role: str, field: str
) -> None:
    manifest_path = children["release"] / role / "dataset/manifest.json"
    manifest = read_json(manifest_path)
    manifest[field] = "f" * 64 if field == "source_sha256" else manifest[field] + 1
    _replace_json(manifest_path, manifest)
    _reissue_child_freeze(children, role)
    with pytest.raises(ValueError, match="source|seed|child"):
        _freeze(children)
    assert not (children["release"] / "joint_inference_freeze.json").exists()


@pytest.mark.parametrize("change", ["missing_freeze", "changed_prediction", "changed_manifest"])
def test_scoped_child_must_be_frozen_and_manifest_exact_before_joint_creation(
    children: dict[str, Any], change: str
) -> None:
    directory = children["release"] / "scoped"
    if change == "missing_freeze":
        (directory / "inference_primary/inference_freeze.json").unlink()
    elif change == "changed_prediction":
        _replace_json(directory / "inference_primary/prediction.json", {"changed": True})
    else:
        manifest = read_json(directory / "dataset/manifest.json")
        manifest["dataset_version"] += "_CHANGED"
        _replace_json(directory / "dataset/manifest.json", manifest)
    with pytest.raises((ValueError, FileNotFoundError)):
        _freeze(children)
    assert not (children["release"] / "joint_inference_freeze.json").exists()


@pytest.mark.parametrize("field", [
    "source_sha256", "export_seed", "inference_seed", "dataset_version",
])
def test_postfreeze_scoped_manifest_change_stops_office_gt_before_loader(
    children: dict[str, Any], monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    _freeze(children)
    manifest_path = children["release"] / "scoped/dataset/manifest.json"
    manifest = read_json(manifest_path)
    manifest[field] = manifest[field] + 1 if isinstance(manifest[field], int) else "changed"
    _replace_json(manifest_path, manifest)
    calls: list[str] = []
    monkeypatch.setattr(protocol, "evaluate_dataset", lambda *a, **k: calls.append("GT"))
    with pytest.raises(ValueError, match="manifest|dataset|source|seed"):
        protocol.evaluate_office_child(
            children["root"], children["release"] / "office",
            master_path=children["master_path"],
            joint_freeze_path=children["release"] / "joint_inference_freeze.json",
        )
    assert calls == []


def test_reissued_other_source_scoped_child_cannot_be_attached_to_existing_joint(
    children: dict[str, Any]
) -> None:
    _freeze(children)
    manifest_path = children["release"] / "scoped/dataset/manifest.json"
    manifest = read_json(manifest_path)
    manifest["source_sha256"] = "f" * 64
    _replace_json(manifest_path, manifest)
    _reissue_child_freeze(children, "scoped")
    path = children["release"] / "joint_inference_freeze.json"
    joint = read_json(path)
    joint["children"]["scoped"]["freeze_file_sha256"] = digest(
        children["release"] / "scoped/inference_primary/inference_freeze.json"
    )
    joint["datasets"]["scoped"]["manifest_file_sha256"] = digest(manifest_path)
    _replace_json(path, joint)
    with pytest.raises(ValueError, match="source|dataset|child"):
        _require(children)


@pytest.mark.parametrize("field,value", [
    ("ground_truth_read", True), ("status", "POST_EVALUATION"),
    ("source_sha256", "f" * 64), ("case_selection", {}),
])
def test_forged_joint_boundary_claims_are_refused(
    children: dict[str, Any], field: str, value: Any
) -> None:
    _freeze(children)
    path = children["release"] / "joint_inference_freeze.json"
    joint = read_json(path)
    joint[field] = value
    _replace_json(path, joint)
    with pytest.raises(ValueError):
        _require(children)


def test_one_office_freeze_cannot_alias_both_independent_children(children: dict[str, Any]) -> None:
    _freeze(children)
    path = children["release"] / "joint_inference_freeze.json"
    joint = read_json(path)
    joint["children"]["scoped"] = dict(joint["children"]["office"])
    _replace_json(path, joint)
    with pytest.raises(ValueError, match="child|scoped|directory"):
        _require(children)


@pytest.mark.parametrize("role", ["office", "scoped"])
def test_valid_child_receipt_must_pin_its_exact_original_config(
    children: dict[str, Any], role: str
) -> None:
    path = children["release"] / role / "inference_primary/inference_freeze.json"
    frozen = read_json(path)
    frozen["config_sha256"] = "f" * 64
    _replace_json(path, frozen)
    with pytest.raises(ValueError, match="config|master|child"):
        _freeze(children)


def test_reissued_scoped_config_cannot_differ_from_frozen_master_settings(
    children: dict[str, Any]
) -> None:
    _replace_json(
        children["release"] / "scoped/inference_primary/config.json",
        {"test_only": "undeclared replacement inference settings"},
    )
    _reissue_child_freeze(children, "scoped")
    with pytest.raises(ValueError, match="config|master|settings"):
        _freeze(children)


@pytest.mark.parametrize("role", ["office", "scoped"])
def test_child_freeze_must_explicitly_certify_ground_truth_unread(
    children: dict[str, Any], role: str
) -> None:
    path = children["release"] / role / "inference_primary/inference_freeze.json"
    frozen = read_json(path)
    frozen["ground_truth_read"] = None
    _replace_json(path, frozen)
    with pytest.raises(ValueError, match="freeze|GT|truth|child"):
        _freeze(children)


def _rows(case_id: str, variants: tuple[str, ...]) -> list[dict[str, Any]]:
    return [{
        "case_id": case_id, "gap_id": "gap00", "method_id": variant, "k": k,
        "status": "N/A" if variant == "remove_topology" else "FORMAL_LOCAL_SCOPE",
        "candidate_count": None if variant == "remove_topology" else (
            1 if case_id == "case1" else 2
        ),
        "timing_hypothesis_count": None if variant == "remove_topology" else 6,
        "impossible_transition_rate": None,
        "blockers": "UNAVAILABLE_FACTOR" if variant == "remove_topology" else "",
        "runtime_repeated_for_k_only_do_not_sum": True,
    } for variant in variants for k in (1, 2, 3)]


@pytest.fixture
def evaluated(children: dict[str, Any]) -> dict[str, Any]:
    _freeze(children)
    release = children["release"]
    case1_metrics = {
        "ade_m": 0.25, "fde_m": 0.2, "projection_error_m": 0.1,
        "feasible_candidate_recall": 1.0, "collision_rate": 0.0,
        "constraint_violation_rate": 0.0, "impossible_transition_rate": 0.0,
        "path_length_error_m": 0.2, "travel_time_error_s": 0.0, "candidate_count": 1,
        "inference_runtime_s": 0.0, "expanded_states": 2, "termination_reason": "COMPLETE",
        "metrics_at_k": {str(k): {
            "min_ade_at_k_m": 0.25, "min_fde_at_k_m": 0.2, "coverage_at_k": True,
        } for k in (1, 2, 3)},
    }
    office = {
        "status": "PHASE1_FINALIZATION_BLOCKED", "freeze_allowed": False,
        "dataset_manifest_sha256": digest(release / "office/dataset/manifest.json"),
        "primary_inference_freeze_sha256": digest(
            release / "office/inference_primary/inference_freeze.json"
        ),
        "evaluation_inference_freeze_verified": True,
        "measurements": {
            "case1": {method: dict(case1_metrics) for method in METHODS},
            "case2": {}, "case3": {"spatiotemporal": {"result_type": "OLD_OFFICE_TEMPORAL"}},
        },
        "cases": [{"case_id": "case2", "status": "BLOCKED", "reason": "ORIGINAL_OFFICE_SCOPE"}],
    }
    write_json(release / "office/evaluation/verification.json", office)
    old_blocked = {
        "case_id": "case2", "method_id": "spatiotemporal", "k": 1,
        "status": "N/A", "blockers": "ORIGINAL_OFFICE_SCOPE", "ade_m": None,
    }
    write_json(release / "office/evaluation/benchmark_table.json", {
        "rows": _rows("case1", METHODS) + [old_blocked] + _rows("case3", METHODS)
    })
    write_json(release / "office/evaluation/ablations/benchmark_table.json", {
        "rows": _rows("case1", ABLATIONS) + [dict(old_blocked, method_id="remove_collision")]
    })
    counts = {"case2": [2], "case3": [2, 1, 1], "case3_short_control": [1],
              "case3_long_stress": [2, 2, 1]}
    scoped = {
        "status": "SCOPED_CASE23_VALIDATED", "source_sha256": children["master"]["source_sha256"],
        "dataset_version": read_json(release / "scoped/dataset/manifest.json")["dataset_version"],
        "dataset_manifest_file_sha256": digest(release / "scoped/dataset/manifest.json"),
        "inference_freeze_file_sha256": digest(
            release / "scoped/inference_primary/inference_freeze.json"
        ),
        "cases": [{
            "case_id": identity, "status": "PASS", "blockers": [],
            "candidate_counts": counts[identity], "gap_count": len(counts[identity]),
            "gap_durations_s": [5.0] if identity == "case3_short_control" else (
                [40.0 if identity == "case3_long_stress" else 20.0] * len(counts[identity])
            ),
            "actual_handoff_count": 0, "impossible_transition_rate": None,
        } for identity in SOURCE_CASES],
    }
    write_json(release / "scoped/evaluation/summary.json", scoped)
    write_json(release / "scoped/evaluation/benchmark_table.json", {
        "rows": [row for case in SOURCE_CASES for row in _rows(case, METHODS + ABLATIONS)]
    })
    return dict(children, office=office, scoped=scoped)


def _assemble(inputs: dict[str, Any]) -> dict[str, Any]:
    return release_module.assemble_joint_release(
        inputs["release"], inputs["master_path"], root=inputs["root"]
    )


def test_joint_rows_preserve_child_status_na_stress_and_original_office_bytes(
    evaluated: dict[str, Any]
) -> None:
    release = evaluated["release"]
    before = {path: digest(path) for role in ("office", "scoped")
              for path in (release / role / "evaluation").rglob("*.json")}
    result = _assemble(evaluated)
    rows = read_json(release / "benchmark_table.json")["rows"]
    assert len(rows) == 120  # 24 selected office + 4 * 24 independently retained scoped rows.
    office_rows = [row for row in rows if row["child_dataset"] == "office"]
    scoped_rows = [row for row in rows if row["child_dataset"] == "scoped"]
    assert {row["case_id"] for row in office_rows} == {"case1"}
    assert {row["case_id"] for row in scoped_rows} == set(SOURCE_CASES)
    assert all(row["child_original_status"] == row["status"] for row in rows)
    unavailable = [row for row in rows if row["status"] == "N/A"]
    assert len(unavailable) == 15
    assert all(row["candidate_count"] is None and row["blockers"] == "UNAVAILABLE_FACTOR"
               for row in unavailable)
    assert all(row["timing_hypothesis_count"] == 6 for row in rows if row["status"] != "N/A")
    assert all(row["candidate_count"] == 1 for row in office_rows if row["status"] != "N/A")
    assert all(row["candidate_count"] == 2 for row in scoped_rows if row["status"] != "N/A")
    assert {case["case_id"] for case in result["cases"]} == {"case1", "case2", "case3"}
    assert result["selected_case1_original_child_status"] == "PHASE1_FINALIZATION_BLOCKED"
    assert result["historical_child_statuses_rewritten"] is False
    assert {path: digest(path) for path in before} == before
    assert read_json(release / "office/evaluation/verification.json")["cases"][0]["status"] == (
        "BLOCKED"
    )


def test_case_growth_preserves_separate_actual_gap_populations_and_pending_release_gates(
    evaluated: dict[str, Any]
) -> None:
    result = _assemble(evaluated)
    growth = read_json(evaluated["release"] / "case3_growth.json")
    assert max(growth["main"]["candidate_counts"]) > max(
        growth["short_control"]["candidate_counts"]
    )
    assert growth["main"]["gap_count"] != growth["short_control"]["gap_count"]
    assert growth["different_schedules_do_not_imply_matched_gap_endpoints"] is True
    assert growth["population_comparison"] == (
        "SOURCE_RECIPE_FAMILY_WITH_SEPARATE_ACTUAL_GAP_ANCHORS"
    )
    assert growth["plateau_allowed_at_FIXED_PATH_LENGTH_DETOUR_LIMIT"] is True
    queries = growth["frozen_actual_gap_queries"]
    assert queries["case3"][0]["endpoint_positions_bu"] != queries[
        "case3_short_control"
    ][0]["endpoint_positions_bu"]
    assert queries["case3"][0]["time_range"] != queries["case3_short_control"][0]["time_range"]
    assert result["formal_case_execution_complete"] is True
    assert result["status"] == "PHASE1_FINALIZATION_BLOCKED"
    assert result["freeze_allowed"] is False
    assert result["reproduction_status"] == result["repository_validation_status"] == "PENDING"
    assert result["cross_case_overall_coverage"] is None
    assert result["school_surface_authority"] == "NOT_CERTIFIED"
    assert result["case4_status"] == "DEFERRED"


@pytest.mark.parametrize("missing", [
    "inference_runtime_s", "expanded_states", "termination_reason", "min_ade_k3", "coverage_k2",
])
def test_missing_case1_required_measurement_remains_unevaluated_and_blocks_joint(
    evaluated: dict[str, Any], missing: str
) -> None:
    path = evaluated["release"] / "office/evaluation/verification.json"
    office = read_json(path)
    primary = office["measurements"]["case1"]["spatiotemporal"]
    if missing == "min_ade_k3":
        primary["metrics_at_k"]["3"].pop("min_ade_at_k_m")
    elif missing == "coverage_k2":
        primary["metrics_at_k"]["2"].pop("coverage_at_k")
    else:
        primary.pop(missing)
    _replace_json(path, office)
    result = _assemble(evaluated)
    assert result["formal_case_execution_complete"] is False
    assert result["freeze_allowed"] is False
    assert next(case for case in result["cases"] if case["case_id"] == "case1")["status"] == (
        "BLOCKED"
    )
    assert any(blocker.startswith("CASE1_") for blocker in result["blockers"])
    assert read_json(path) == office


@pytest.mark.parametrize("role,field", [
    ("office", "primary_inference_freeze_sha256"), ("office", "dataset_manifest_sha256"),
    ("office", "evaluation_inference_freeze_verified"),
    ("scoped", "inference_freeze_file_sha256"), ("scoped", "source_sha256"),
    ("scoped", "dataset_version"), ("scoped", "dataset_manifest_file_sha256"),
])
def test_stale_child_evaluation_cannot_be_assembled_with_a_fresh_joint_freeze(
    evaluated: dict[str, Any], role: str, field: str
) -> None:
    filename = "verification.json" if role == "office" else "summary.json"
    path = evaluated["release"] / role / "evaluation" / filename
    document = read_json(path)
    document[field] = False if field == "evaluation_inference_freeze_verified" else "f" * 64
    _replace_json(path, document)
    with pytest.raises(ValueError, match="evaluation|freeze|source|manifest|version|child"):
        _assemble(evaluated)
    assert not (evaluated["release"] / "verification.json").exists()


def test_blocked_scoped_case_cannot_be_completed_even_without_detail_blockers(
    evaluated: dict[str, Any]
) -> None:
    path = evaluated["release"] / "scoped/evaluation/summary.json"
    scoped = read_json(path)
    scoped["cases"][0]["status"] = "BLOCKED"
    _replace_json(path, scoped)
    result = _assemble(evaluated)
    assert result["formal_case_execution_complete"] is False
    assert result["blockers"]
    assert next(case for case in result["cases"] if case["case_id"] == "case2")["status"] == (
        "BLOCKED"
    )


@pytest.mark.parametrize("change", ["duplicate_primary", "missing_primary", "missing_stress"])
def test_scoped_evaluation_population_must_match_every_frozen_source_case(
    evaluated: dict[str, Any], change: str
) -> None:
    path = evaluated["release"] / "scoped/evaluation/summary.json"
    scoped = read_json(path)
    if change == "duplicate_primary":
        scoped["cases"].append(copy.deepcopy(scoped["cases"][0]))
    else:
        removed = "case2" if change == "missing_primary" else "case3_short_control"
        scoped["cases"] = [case for case in scoped["cases"] if case["case_id"] != removed]
    _replace_json(path, scoped)
    with pytest.raises(ValueError, match="case|population|scoped evaluation"):
        _assemble(evaluated)


def test_equal_main_and_short_class_counts_remain_blocked_without_fabricated_growth(
    evaluated: dict[str, Any]
) -> None:
    path = evaluated["release"] / "scoped/evaluation/summary.json"
    scoped = read_json(path)
    for case in scoped["cases"]:
        if case["case_id"] == "case3_short_control":
            case["candidate_counts"] = [2]
    _replace_json(path, scoped)
    result = _assemble(evaluated)
    assert result["formal_case_execution_complete"] is False
    assert "CASE3_NO_CANDIDATE_GROWTH_DEMONSTRATED" in result["blockers"]
    assert result["freeze_allowed"] is False


@pytest.mark.parametrize("freeze_succeeds", [False, True])
def test_primary_entry_finishes_both_inferences_before_any_reference_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, freeze_succeeds: bool
) -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/run_phase1_joint_case23.py"
    spec = importlib.util.spec_from_file_location("scoped_joint_entry_test", script)
    assert spec is not None and spec.loader is not None
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    source, config = tmp_path / "synthetic_source.blend", tmp_path / "source_config.json"
    source.write_bytes(b"SYNTHETIC_IMMUTABLE_BYTES_NOT_A_BLENDER_SCENE")
    write_json(config, {"test_only": "source export settings"})
    master_path, output = tmp_path / "master.json", tmp_path / "release"
    events: list[str] = []
    monkeypatch.setattr(entry, "load_export_authority", lambda *_: events.append("authority"))

    def definition(*args: Any, **kwargs: Any) -> None:
        events.append("definition")
        write_json(master_path, {"test_only": "frozen master"})

    def export_lock(*args: Any, **kwargs: Any) -> None:
        events.append("export_lock")
        write_json(output / "source_export_lock.json", {"test_only": "source freeze"})

    def scoped_export(*args: Any, **kwargs: Any) -> Any:
        events.append("scoped_export")
        from subprocess import CompletedProcess

        return CompletedProcess(args[0], 0, stdout="synthetic", stderr="")

    def joint_boundary(*args: Any, **kwargs: Any) -> None:
        events.append("joint_freeze")
        assert "office_infer" in events and "scoped_infer" in events
        assert "office_GT" not in events and "scoped_GT" not in events
        if not freeze_succeeds:
            raise ValueError("synthetic joint freeze blocked")
        write_json(output / "joint_inference_freeze.json", {"test_only": "both frozen"})

    def assemble(*args: Any, **kwargs: Any) -> dict[str, Any]:
        events.append("assemble")
        return {"status": "PHASE1_FINALIZATION_BLOCKED", "freeze_allowed": False}

    monkeypatch.setattr(entry, "build_scoped_experiment", definition)
    monkeypatch.setattr(entry, "freeze_export", export_lock)
    monkeypatch.setattr(entry.subprocess, "run", scoped_export)
    for function, event in (
        ("export_office_child", "office_export"), ("infer_office_child", "office_infer"),
        ("infer_scoped_dataset", "scoped_infer"), ("evaluate_office_child", "office_GT"),
        ("evaluate_scoped_dataset", "scoped_GT"),
    ):
        monkeypatch.setattr(entry, function, lambda *a, _event=event, **k: events.append(_event))
    monkeypatch.setattr(entry, "freeze_joint_inference", joint_boundary)
    monkeypatch.setattr(entry, "assemble_joint_release", assemble)
    if not freeze_succeeds:
        with pytest.raises(ValueError, match="joint freeze blocked"):
            entry.run_primary(
                tmp_path, source, Path("synthetic_blender"), config, master_path, output
            )
        assert "office_GT" not in events and "scoped_GT" not in events and "assemble" not in events
        assert not (output / "primary_run_receipt.json").exists()
    else:
        result = entry.run_primary(
            tmp_path, source, Path("synthetic_blender"), config, master_path, output
        )
        assert events.index("office_infer") < events.index("joint_freeze")
        assert events.index("scoped_infer") < events.index("joint_freeze")
        assert events.index("joint_freeze") < events.index("office_GT")
        assert events.index("joint_freeze") < events.index("scoped_GT")
        assert events.index("office_GT") < events.index("assemble")
        assert events.index("scoped_GT") < events.index("assemble")
        assert result["freeze_allowed"] is False
        receipt = read_json(output / "primary_run_receipt.json")
        assert receipt["source_before"] == receipt["source_after"]
        assert receipt["formal_freeze_granted"] is False


def _reproduction_spec(inputs: dict[str, Any], *, joint_release: bool = True) -> Path:
    path = inputs["root"] / "clean_checkout_spec.json"
    write_json(path, {
        "root": str(inputs["root"]), "expected_commit": "b" * 40,
        "master_relative_path": "master.json",
        "source_config_relative_path": "source_export_config.json",
        "source": str(inputs["root"] / "synthetic_source.blend"),
        "python_executable": sys.executable,
        "blender_executable": str(inputs["root"] / "synthetic_blender"),
        "output": str(inputs["release"].parent / "new_clean_delivery"),
        "joint_release": joint_release,
    })
    return path


def _joint_entry() -> Any:
    script = Path(__file__).resolve().parents[2] / "scripts/run_phase1_joint_case23.py"
    spec = importlib.util.spec_from_file_location("scoped_joint_reproduction_entry_test", script)
    assert spec is not None and spec.loader is not None
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    return entry


@pytest.mark.parametrize("office_status,scoped_status", [
    ("PASS", "PASS"), ("FAIL", "PASS"), ("PASS", "INCOMPLETE"), ("FAIL", "INCOMPLETE"),
])
def test_reproduction_receipt_requires_both_child_status_fields_and_never_grants_exit(
    children: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
    office_status: str, scoped_status: str,
) -> None:
    _freeze(children)
    entry = _joint_entry()
    spec_path = _reproduction_spec(children)
    verification = children["release"] / "verification.json"
    write_json(verification, {
        "status": "PHASE1_FINALIZATION_BLOCKED", "freeze_allowed": False,
        "reproduction_status": "PENDING", "repository_validation_status": "PENDING",
    })
    before = digest(verification)
    office = {"reproduction_status": office_status, "status": "PASS"}
    scoped = {"status": scoped_status, "reproduction_status": "PASS"}
    events: list[str] = []
    provider = object()

    def authority(*args: Any, **kwargs: Any) -> Any:
        events.append("authority")
        return provider

    def office_reproduction(*args: Any, **kwargs: Any) -> dict[str, Any]:
        events.append("office")
        assert kwargs["joint_freeze_path"] == children["release"] / "joint_inference_freeze.json"
        return office

    def scoped_reproduction(*args: Any, **kwargs: Any) -> dict[str, Any]:
        events.append("scoped")
        assert kwargs["provider"] is provider
        assert kwargs["fresh_checkout"].joint_release is True
        assert kwargs["primary_evaluation"] == children["release"] / "scoped/evaluation"
        assert args[:2] == (
            children["release"] / "scoped/dataset",
            children["release"] / "scoped/inference_primary",
        )
        return scoped

    monkeypatch.setattr(entry, "load_export_authority", authority)
    monkeypatch.setattr(entry, "reproduce_office_child", office_reproduction)
    monkeypatch.setattr(reproduction, "verify_scoped_reproduction", scoped_reproduction)
    result = entry.run_reproduction(
        children["root"], children["master_path"], children["release"], spec_path
    )
    assert events == ["authority", "office", "scoped"]
    expected = "PASS" if office_status == scoped_status == "PASS" else "FAIL"
    assert result["status"] == expected
    assert result["office"] == office and result["scoped"] == scoped
    assert result["formal_freeze_granted"] is False
    assert result["master_file_sha256"] == digest(children["master_path"])
    assert read_json(children["release"] / "reproduction_receipt.json") == result
    assert digest(verification) == before


def test_joint_reproduction_rejects_scoped_only_clean_checkout_before_heavy_stages(
    children: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze(children)
    entry = _joint_entry()
    spec_path = _reproduction_spec(children, joint_release=False)
    calls: list[str] = []
    monkeypatch.setattr(entry, "load_export_authority", lambda *_: calls.append("authority"))
    monkeypatch.setattr(
        entry, "reproduce_office_child",
        lambda *a, **k: calls.append("office") or {"reproduction_status": "PASS"},
    )
    monkeypatch.setattr(
        reproduction, "verify_scoped_reproduction",
        lambda *a, **k: calls.append("scoped") or {"status": "PASS"},
    )
    with pytest.raises(ValueError, match="joint|clean"):
        entry.run_reproduction(
            children["root"], children["master_path"], children["release"], spec_path
        )
    assert calls == []
    assert not (children["release"] / "reproduction_receipt.json").exists()
