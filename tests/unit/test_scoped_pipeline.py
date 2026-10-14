"""Frozen orchestration, reference isolation, and per-gap benchmark populations."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_physical_collision import _numerics
from test_reviewed_collision import _bound_provider
from test_scoped_projection import _inputs_for
from test_scoped_projection import approved as scaled_approved

import amidst.finalization.scoped_pipeline as pipeline
from amidst.domain.metric_config import MetricConfig
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.finalization.reviewed_collision import collision_bundle_from_provider
from amidst.finalization.reviewed_pipeline import (
    digest,
    read_json,
    require_inference_freeze,
    write_json,
)
from amidst.finalization.scoped_inference import ScopedBudgetLineage, ScopedInferenceConfig
from amidst.finalization.scoped_projection import ScopedSourceContext
from amidst.obstacle_volume_authority import content_sha256


def _replace_json(path: Path, value: Any) -> None:
    """Intentional mutation of test inputs, unlike the exclusive production writer."""
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def test_table_keeps_k_specific_metrics_distinct_from_scalar_counts_and_runtime() -> None:
    result = {
        "status": "SCOPED_EVALUATED",
        "result_type": "SCOPED_LOCAL_SYNTHETIC",
        "ade_m": 0.9,
        "fde_m": 1.1,
        "candidate_count": 2,
        "timing_hypothesis_count": 7,
        "feasible_candidate_recall": None,
        "feasible_candidate_recall_status": "N/A_INCOMPLETE_INVENTORY",
        "feasible_candidate_recall_numerator": None,
        "feasible_candidate_recall_denominator": None,
        "runtime_s": 0.0,
        "case_inference_runtime_s": 2.5,
        "transition_count": 0,
        "impossible_transition_rate": None,
        "impossible_transition_status": "N/A_NO_CAMERA_HANDOFFS",
        "termination_reason": "MAX_BRANCH_FACTOR",
        "metrics_at_k": {
            "1": {"min_ade_at_k_m": 0.7, "min_fde_at_k_m": 0.8, "coverage_at_k": False},
            "2": {"min_ade_at_k_m": 0.2, "min_fde_at_k_m": 0.3, "coverage_at_k": True},
        },
    }
    before = copy.deepcopy(result)
    rows = pipeline._scoped_table_rows("case3", "gap00", "spatiotemporal", result)
    assert [row["k"] for row in rows] == [1, 2, 3]
    assert [row["min_ade_at_k_m"] for row in rows] == [0.7, 0.2, None]
    assert [row["coverage_at_k"] for row in rows] == [False, True, None]
    for row in rows:
        assert (row["ade_m"], row["fde_m"]) == (0.9, 1.1)
        assert (row["candidate_count"], row["timing_hypothesis_count"]) == (2, 7)
        assert row["candidate_recall_denominator"] is None
        assert row["candidate_recall_status"] == "N/A_INCOMPLETE_INVENTORY"
        assert row["gap_inference_runtime_s"] == 0.0
        assert row["case_inference_runtime_s"] == 2.5
        assert row["runtime_repeated_for_k_only_do_not_sum"] is True
        assert row["impossible_transition_rate"] is None
        assert row["transition_count"] == 0
        assert row["termination_reason"] == "MAX_BRANCH_FACTOR"
    other_gap = pipeline._scoped_table_rows("case3", "gap01", "spatiotemporal", result)
    assert len(rows + other_gap) == 6
    assert {(row["gap_id"], row["k"]) for row in rows + other_gap} == {
        (gap, k) for gap in ("gap00", "gap01") for k in (1, 2, 3)
    }
    assert result == before


def test_unavailable_rows_keep_reason_and_missing_populations_without_zero_padding() -> None:
    rows = pipeline._scoped_table_rows(
        "case2", "gap00", "remove_collision", {"status": "N/A", "reason": "NO_CONSUMER"}
    )
    assert [row["k"] for row in rows] == [1, 2, 3]
    for row in rows:
        assert row["status"] == row["result_type"] == "N/A"
        assert row["blockers"] == "NO_CONSUMER"
        assert all(row[field] is None for field in (
            "ade_m", "min_ade_at_k_m", "coverage_at_k", "candidate_count",
            "timing_hypothesis_count", "candidate_recall_numerator",
            "candidate_recall_denominator", "gap_inference_runtime_s",
            "case_inference_runtime_s", "transition_count",
        ))


@pytest.fixture(scope="module")
def synthetic_authority() -> Any:
    """Construct in-memory synthetic geometry; never hydrate the school evidence."""
    provider = scaled_approved.__wrapped__()
    consumer = _bound_provider(
        SimpleNamespace(source_sha256=provider.source_sha256, provider=provider)
    )
    collisions = collision_bundle_from_provider(
        consumer, provider.contract, _numerics(), floor_ids=("1F",), manifest_sha256="a" * 64,
        local_certificate_content_sha256=provider.certificate_content_sha256,
        semantic_receipt_content_sha256=provider.semantic_review_content_sha256,
    )
    return provider, collisions


@pytest.fixture
def isolated_dataset(tmp_path: Path, synthetic_authority: Any) -> dict[str, Any]:
    provider, collisions = synthetic_authority
    root, dataset = tmp_path / "root", tmp_path / "dataset"
    raw, context_raw = _inputs_for(provider)
    evidence = json.loads(raw)
    for frame in evidence["frames"]:
        frame["timestamp"] *= 50.0  # 0, 10, 20 s; ample physical movement budget.
    observations_path = dataset / "inference/case3/observations.json"
    write_json(observations_path, evidence)
    context = json.loads(context_raw)
    context["observations_sha256"] = digest(observations_path)
    context_path = dataset / "inference/case3/context.json"
    write_json(context_path, context)
    write_json(dataset / "inference/case2/observations.json", evidence)
    write_json(dataset / "inference/case2/context.json", context)
    policy = GraphSearchPolicy(
        max_candidate_paths=3, max_search_nodes=1000, max_path_length_m=30.0,
        max_search_time_s=10.0, max_branch_factor=32, max_detour_ratio=2.0,
    )
    typed_context = ScopedSourceContext.model_validate_json(json.dumps(context))
    config = ScopedInferenceConfig(
        authority=typed_context.authority,
        fresh_export_config_sha256=context["config_file_sha256"],
        source_camera_plane_ids={
            item.camera.camera_id: typed_context.plane_id
            for item in provider.proposal.camera_landmark_bindings
        },
        metres_per_blender_unit=typed_context.metres_per_blender_unit,
        movement=MovementConstraints(max_speed_m_s=2.0), search_policy=policy,
        budget_lineage=ScopedBudgetLineage(
            parent_inference_lock_content_sha256="e" * 64, parent_search_policy=policy
        ),
    )
    protocol_path = root / "configs/benchmarks/protocol_v1.json"
    write_json(protocol_path, {"test_only": "SYNTHETIC_FROZEN_PROTOCOL"})
    addendum_path = root / "configs/finalization/case2_interior_branch_addendum_v1.json"
    addendum = {
        "parent_protocol_file_sha256": digest(protocol_path),
        "all_other_protocol_gates_preserved": True,
        "physical_scope_expanded": False,
        "formal_case_readiness_granted": False,
        "proposal_content_sha256": config.authority.proposal_content_sha256,
        "union_certificate_content_sha256": config.authority.certificate_content_sha256,
        "scope_id": provider.scope_id,
    }
    write_json(addendum_path, addendum)
    decision_path = root / "data/finalization/case23_scope_audit_20261014/human_approval.json"
    write_json(decision_path, {
        "decision": "APPROVE", "addendum_content_sha256": content_sha256(addendum),
        "source_sha256": provider.source_sha256, "scope_id": provider.scope_id,
        "parent_protocol_file_sha256": digest(protocol_path),
        "test_only": "SYNTHETIC_APPROVAL_DOES_NOT_APPROVE_SCHOOL_RESEARCH",
    })
    producer_path = root / "src/synthetic_producer.py"
    producer_path.parent.mkdir(parents=True)
    producer_path.write_text("# Synthetic producer freeze fixture\n", encoding="utf-8")
    protected = [protocol_path, addendum_path, decision_path]
    master = {
        "schema_version": "phase1-scoped-case23-experiment-v1",
        "source_case_ids": ["case2", "case3"],
        "class_definition": "FIXED_ENDPOINT_INTEGER_WINDING_CANONICAL_SHORTEST",
        "protected_input_hashes": {str(path.relative_to(root)): digest(path) for path in protected},
        "producer_hashes": {str(producer_path.relative_to(root)): digest(producer_path)},
        "inference_config": config.model_dump(mode="json"),
        "metric_config": MetricConfig(
            k_values=(1, 2, 3), coverage_epsilon_m=0.5, collision_tolerance_m=0.001
        ).model_dump(mode="json"),
        "class_generation_budget": {
            "max_processed_labels": 1000, "max_pending_labels": 1000, "max_elapsed_s": 10.0,
        },
        "inventory_budget": {
            "max_expanded_states": 1000, "max_pending_states": 1000, "max_elapsed_s": 10.0,
        },
    }
    master_path = root / "configs/finalization/scoped_master.json"
    write_json(master_path, master)
    write_json(root / "configs/finalization/reviewed_case_inference_with_collision_v3.json", {
        "known_collision": {
            "context_path": "data/public/synthetic_collision_context.json",
            "physical_manifest_file_sha256": "a" * 64, "scope_ids": list(collisions.scope_ids),
        }
    })
    # These are poison sentinels, not reference trajectories or simulation recipes.
    for relative in ("evaluation/case3/ground_truth.json", "simulation/case3/recipe.json"):
        write_json(dataset / relative, {"MUST_NEVER_OPEN_DURING_INFERENCE": True})
    manifest = {
        "schema_version": "phase1-scoped-source-dataset-v1",
        "dataset_version": "SYNTHETIC_ISOLATED_PIPELINE_TEST",
        "source_sha256": provider.source_sha256,
        "config_file_sha256": config.fresh_export_config_sha256,
        "export_lock_file_sha256": context["export_lock_file_sha256"],
        "full_experiment_config_file_sha256": digest(master_path),
        "cases": [{"case_id": "case2"}, {"case_id": "case3"}],
        "artifacts": {
            str(path.relative_to(dataset)): digest(path) for path in dataset.rglob("*.json")
        },
    }
    write_json(dataset / "manifest.json", manifest)
    return {
        "root": root, "dataset": dataset, "master_path": master_path, "master": master,
        "manifest": manifest, "context_path": context_path, "producer_path": producer_path,
        "provider": provider, "collisions": collisions, "config": config,
    }


def _infer_with_isolation(
    inputs: dict[str, Any], monkeypatch: pytest.MonkeyPatch, output: Path
) -> dict[str, Any]:
    opened: list[str] = []
    original_open = Path.open

    def guarded_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path.is_relative_to(inputs["dataset"]):
            relative = path.relative_to(inputs["dataset"])
            opened.append(str(relative))
            assert relative.parts[0] not in {"evaluation", "simulation"}, relative
        return original_open(path, *args, **kwargs)

    def forbidden_reference(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("reference/evaluation loader ran during inference")

    authority_calls: list[Path] = []

    def authority(root: Path) -> Any:
        authority_calls.append(root)
        return inputs["provider"]

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(pipeline, "load_export_authority", authority)
    monkeypatch.setattr(
        pipeline, "load_reviewed_collision_bundle", lambda *a, **k: inputs["collisions"]
    )
    monkeypatch.setattr(pipeline, "evaluate_scoped_run", forbidden_reference)
    monkeypatch.setattr(pipeline, "load_reference_movement_approval", forbidden_reference)
    # Exercise genuine inference and a known-collision ablation without repeating
    # all baseline variants; their core contracts already have independent tests.
    monkeypatch.setattr(pipeline, "METHODS", ("geometry", "spatiotemporal"))
    monkeypatch.setattr(pipeline, "ABLATIONS", ("remove_collision",))
    result = pipeline.infer_scoped_dataset(
        inputs["dataset"], inputs["master_path"], output, root=inputs["root"]
    )
    assert authority_calls == [inputs["root"]]
    assert "inference/case3/context.json" in opened
    assert "inference/case3/observations.json" in opened
    return result


def test_isolated_inference_freezes_actual_source_and_master_before_reference_access(
    isolated_dataset: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    inputs = isolated_dataset
    output = tmp_path / "inference"
    summary = _infer_with_isolation(inputs, monkeypatch, output)
    assert summary["ground_truth_read"] is False
    assert {case["case_id"] for case in summary["cases"]} == {"case2", "case3"}
    assert all(case["gap_count"] == 1 for case in summary["cases"])
    freeze = require_inference_freeze(output)
    assert freeze["ground_truth_read"] is False
    assert freeze["status"] == "FROZEN_BEFORE_EVALUATION"
    assert freeze["dataset_manifest_sha256"] == digest(inputs["dataset"] / "manifest.json")
    assert freeze["config_sha256"] == digest(inputs["master_path"])
    assert {
        "config.json", "experiment.json", "summary.json", "case3/scoped_context.json",
        "case3/projection.json", "case3/frames.json", "case3/aggregation.json",
        "case3/gap00/navigation.json", "case3/gap00/raw_visibility_graph.json",
    } <= set(freeze["artifacts"])
    assert not any(path.endswith("runtime.json") for path in freeze["artifacts"])
    projection = read_json(output / "case3/projection.json")
    source_context = read_json(output / "case3/scoped_context.json")
    assert projection["observations_file_sha256"] == source_context["observations_sha256"]
    assert projection["config_file_sha256"] == inputs["manifest"]["config_file_sha256"]
    assert projection["export_lock_file_sha256"] == inputs["manifest"]["export_lock_file_sha256"]
    frames = read_json(output / "case3/frames.json")
    assert len(frames["samples"]) == 6
    assert {sample["timestamp"] for sample in frames["samples"]} == {0.0, 10.0, 20.0}
    variant = output / "case3/gap00/spatiotemporal"
    run = read_json(variant / "run.json")
    assert run["camera_handoffs"] == 0
    assert run["ground_truth_read"] is False
    assert run["budget_lineage"] == inputs["config"].budget_lineage.model_dump(mode="json")
    assert run["class_selection_truncated"] == (
        len(run["production_class_search"]["classes"]) > run["requested_k"]
    )
    runtime = read_json(variant / "runtime.json")
    assert runtime["inference_runtime_s"] >= 0
    assert runtime["independent_inventory_or_evaluation_included"] is False
    case_runtime = read_json(output / "case3/runtime.json")
    shared = case_runtime["shared_projection_aggregation_binding_runtime_s"] + case_runtime[
        "shared_source_navigation_runtime_s"
    ]
    assert case_runtime["case_inference_runtime_s_by_variant"]["spatiotemporal"] == pytest.approx(
        shared + runtime["inference_runtime_s"]
    )
    assert case_runtime["independent_inventory_evaluation_reporting_included"] is False
    assert case_runtime[
        "shared_work_attributed_once_to_each_independently_comparable_variant"
    ] is True


@pytest.mark.parametrize("change", [
    "observations", "producer", "master_binding", "export_config", "protected_protocol",
    "dataset_producer", "missing_master_binding", "missing_export_config",
])
def test_tampered_inputs_fail_before_creating_output_or_loading_authority(
    isolated_dataset: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path, change: str
) -> None:
    inputs = isolated_dataset
    if change == "observations":
        path = inputs["dataset"] / "inference/case3/observations.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif change == "producer":
        inputs["producer_path"].write_text("# mutated producer\n", encoding="utf-8")
    elif change == "protected_protocol":
        _replace_json(inputs["root"] / "configs/benchmarks/protocol_v1.json", {"changed": True})
    else:
        manifest = dict(inputs["manifest"])
        if change == "dataset_producer":
            manifest["producer_hashes"] = {"src/synthetic_producer.py": "f" * 64}
        else:
            field = "full_experiment_config_file_sha256" if "master_binding" in change else (
                "config_file_sha256"
            )
            if change.startswith("missing_"):
                manifest.pop(field)
            else:
                manifest[field] = "f" * 64
        _replace_json(inputs["dataset"] / "manifest.json", manifest)
    monkeypatch.setattr(
        pipeline, "load_export_authority",
        lambda *args: pytest.fail("loaded authority after tamper"),
    )
    output = tmp_path / "rejected"
    with pytest.raises(ValueError):
        pipeline.infer_scoped_dataset(
            inputs["dataset"], inputs["master_path"], output, root=inputs["root"]
        )
    assert not output.exists()


@pytest.mark.parametrize("cases", [[], [{"case_id": "case2"}], [
    {"case_id": "case2"}, {"case_id": "case2"}, {"case_id": "case3"},
]])
def test_dataset_cannot_drop_or_duplicate_frozen_case_population(
    isolated_dataset: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path, cases: list[dict[str, str]],
) -> None:
    inputs = isolated_dataset
    manifest = dict(inputs["manifest"], cases=cases)
    _replace_json(inputs["dataset"] / "manifest.json", manifest)
    monkeypatch.setattr(
        pipeline, "load_export_authority",
        lambda *args: pytest.fail("loaded authority before verifying case population"),
    )
    output = tmp_path / "wrong_population"
    with pytest.raises(ValueError, match="case|population"):
        pipeline.infer_scoped_dataset(
            inputs["dataset"], inputs["master_path"], output, root=inputs["root"]
        )
    assert not output.exists()


@pytest.mark.parametrize("field", ["config_file_sha256", "export_lock_file_sha256"])
def test_rehashed_source_context_cannot_substitute_another_export_freeze(
    isolated_dataset: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str
) -> None:
    inputs = isolated_dataset
    context = read_json(inputs["context_path"])
    context[field] = "f" * 64
    _replace_json(inputs["context_path"], context)
    manifest = copy.deepcopy(inputs["manifest"])
    manifest["artifacts"]["inference/case3/context.json"] = digest(inputs["context_path"])
    _replace_json(inputs["dataset"] / "manifest.json", manifest)
    output = tmp_path / "bad_context"
    with pytest.raises(ValueError, match="config|export|context|freeze"):
        _infer_with_isolation(inputs, monkeypatch, output)
    assert not (output / "inference_freeze.json").exists()


def test_evaluation_without_freeze_cannot_open_any_reference_loader(
    isolated_dataset: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("reference loader opened before validating the inference freeze")

    monkeypatch.setattr(pipeline, "load_export_authority", forbidden)
    monkeypatch.setattr(pipeline, "load_reference_movement_approval", forbidden)
    monkeypatch.setattr(pipeline, "evaluate_scoped_run", forbidden)
    with pytest.raises(FileNotFoundError, match="inference_freeze"):
        pipeline.evaluate_scoped_dataset(
            isolated_dataset["dataset"], tmp_path / "absent", tmp_path / "evaluation",
            root=isolated_dataset["root"],
        )
    assert not (tmp_path / "evaluation").exists()


def test_changed_frozen_prediction_stops_evaluation_before_reference_loaders(
    isolated_dataset: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    inputs = isolated_dataset
    output = tmp_path / "inference"
    _infer_with_isolation(inputs, monkeypatch, output)
    run_path = output / "case3/gap00/spatiotemporal/run.json"
    before = hashlib.sha256(run_path.read_bytes()).hexdigest()
    run_path.write_bytes(run_path.read_bytes() + b" ")
    assert hashlib.sha256(run_path.read_bytes()).hexdigest() != before
    monkeypatch.setattr(
        pipeline, "load_export_authority", lambda *args: pytest.fail("loaded before tamper check")
    )
    with pytest.raises(ValueError, match="changed after freeze"):
        pipeline.evaluate_scoped_dataset(
            inputs["dataset"], output, tmp_path / "evaluation", root=inputs["root"]
        )
    assert not (tmp_path / "evaluation").exists()
