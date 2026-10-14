"""Synthetic closeout contracts; fixtures are not formal benchmark evidence."""

import argparse
import hashlib
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from amidst.finalization import reviewed_pipeline
from amidst.obstacle_volume_authority import content_sha256

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "case23_acceptance_test_module", ROOT / "scripts/finalize_case23_acceptance.py"
)
assert SPEC and SPEC.loader
closeout = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = closeout
SPEC.loader.exec_module(closeout)
MODULES = SimpleNamespace(p=reviewed_pipeline, content_sha256=content_sha256)
STATE = {"sha256": "a" * 64, "size_bytes": 1, "mtime_ns": 123}


def _validation_fixture(root: Path) -> tuple[Path, dict[str, Any]]:
    nodes = [f"tests/synthetic_test.py::test_receipt_{index}" for index in range(2182)]
    xml = ET.Element("testsuites")
    suite = ET.SubElement(xml, "testsuite", tests="2182", failures="0", errors="0", skipped="0")
    for index in range(2182):
        ET.SubElement(
            suite, "testcase", classname="tests.synthetic_test", name=f"test_receipt_{index}"
        )
    root.mkdir()
    ET.ElementTree(xml).write(root / "junit.xml")
    (root / "pytest.log").write_text("SYNTHETIC_FIXTURE_ONLY_2182_PASSED")
    checks = {}
    for name in ("ruff", "mypy", "diff"):
        (root / (name + ".log")).write_text("SYNTHETIC_FIXTURE_ONLY")
        checks[name] = {
            "status": "PASS",
            "exit_code": 0,
            "log_path": name + ".log",
            "log_file_sha256": reviewed_pipeline.digest(root / (name + ".log")),
        }
    receipt = {
        "schema_version": "phase1-full-repository-validation-v1",
        "status": "PASS",
        "pytest_exit_code": 0,
        "master_file_sha256": "b" * 64,
        "code_commit_sha": "c" * 40,
        "master_unchanged": True,
        "producer_files_unchanged": True,
        "source_unchanged": True,
        "source_before": STATE,
        "source_after": STATE,
        "expected_population_count": 2182,
        "expected_original_test_count": 1978,
        "expected_new_test_count": 204,
        "full_counts": {
            "tests": 2182,
            "passed": 2182,
            "failures": 0,
            "errors": 0,
            "skipped": 0,
        },
        "all_node_ids": nodes,
        "all_node_ids_content_sha256": content_sha256(nodes),
        "failed_node_ids": [],
        "skipped_node_ids": [],
        "junit_path": "junit.xml",
        "junit_file_sha256": reviewed_pipeline.digest(root / "junit.xml"),
        "pytest_log_path": "pytest.log",
        "pytest_log_file_sha256": reviewed_pipeline.digest(root / "pytest.log"),
        "pytest_command": ["python", "-m", "pytest", "--require-physical-evidence"],
        "checks": checks,
        "fixture": "SYNTHETIC_UNIT_TEST_NOT_AN_ACTUAL_EXECUTION",
    }
    path = root / "validation.json"
    reviewed_pipeline.write_json(path, receipt)
    return path, receipt


@pytest.mark.parametrize(
    "tamper",
    [
        None,
        "junit_skip_reissued_sha",
        "junit_foreign_node_reissued_sha",
        "duplicate_nodes",
        "check_log",
        "wrong_master",
        "wrong_source",
    ],
)
def test_full_validation_checks_actual_junit_population_and_bound_bytes(
    tmp_path: Path,
    tamper: str | None,
) -> None:
    path, receipt = _validation_fixture(tmp_path / "validation")
    if tamper in {"junit_skip_reissued_sha", "junit_foreign_node_reissued_sha"}:
        tree = ET.parse(path.parent / "junit.xml")
        case = next(tree.getroot().iter("testcase"))
        if tamper == "junit_skip_reissued_sha":
            ET.SubElement(case, "skipped")
        else:
            case.attrib["name"] = "foreign_case"
        tree.write(path.parent / "junit.xml")
        receipt["junit_file_sha256"] = reviewed_pipeline.digest(path.parent / "junit.xml")
    elif tamper == "duplicate_nodes":
        receipt["all_node_ids"][1] = receipt["all_node_ids"][0]
        receipt["all_node_ids_content_sha256"] = content_sha256(receipt["all_node_ids"])
    elif tamper == "check_log":
        (path.parent / "mypy.log").write_text("CHANGED_WITHOUT_REVALIDATION")
    elif tamper == "wrong_master":
        receipt["master_file_sha256"] = "f" * 64
    elif tamper == "wrong_source":
        receipt["source_after"] = {**STATE, "mtime_ns": 999}
    path.write_text(json.dumps(receipt))
    arguments = dict(
        root=tmp_path, master_sha="b" * 64, code_commit="c" * 40, source_state=STATE, count=2182
    )
    if tamper:
        with pytest.raises(ValueError):
            closeout._validation(path, MODULES, **arguments)
    else:
        assert closeout._validation(path, MODULES, **arguments)["passed_test_count"] == 2182


def _formal_fixture(root: Path) -> None:
    reviewed_pipeline.write_json(
        root / "joint_inference_freeze.json", {"fixture": "SYNTHETIC_ONLY"}
    )
    reviewed_pipeline.write_json(
        root / "verification.json",
        {
            "schema_version": "phase1-joint-formal-verification-v1",
            "formal_case_execution_complete": True,
            "blockers": [],
            "master_file_sha256": "b" * 64,
            "joint_inference_freeze_file_sha256": reviewed_pipeline.digest(
                root / "joint_inference_freeze.json"
            ),
            "cases": [
                {"case_id": case, "status": "PASS", "blockers": []}
                for case in ("case1", "case2", "case3")
            ],
            "formal_scope": closeout.SCOPE,
            "case4_status": "DEFERRED",
            "school_surface_authority": "NOT_CERTIFIED",
            "phase2_modified": False,
            "historical_child_statuses_rewritten": False,
            "cross_case_overall_coverage": None,
            "cross_case_weighting_status": "UNAPPROVED_NO_OVERALL_TARGET_PASS_CLAIMED",
            "same_camera_scoped_transition_rate_status": (
                "N/A_ZERO_DECLARED_TRANSITIONS_WITH_INDEPENDENT_HOLD_VALIDATION"
            ),
        },
    )
    reviewed_pipeline.write_json(
        root / "scoped/evaluation/summary.json",
        {
            "cases": [
                {
                    "case_id": case,
                    "status": "PASS",
                    "blockers": [],
                    "actual_handoff_count": 0,
                    "impossible_transition_rate": None,
                    "transition_status": "N/A_NO_DECLARED_CAMERA_OR_FLOOR_TRANSITIONS",
                }
                for case in ("case2", "case3", "case3_short_control", "case3_long_stress")
            ]
        },
    )
    reviewed_pipeline.write_json(
        root / "office/evaluation/verification.json",
        {
            "overall_physical_authority": "PARTIAL_APPROVED",
        },
    )


@pytest.mark.parametrize(
    "tamper", [None, "pretend_complete", "invented_overall_coverage", "invented_transition_zero"]
)
def test_formal_completion_retains_partial_authority_and_legal_na(
    tmp_path: Path,
    tamper: str | None,
) -> None:
    _formal_fixture(tmp_path)
    path = tmp_path / "verification.json"
    value = reviewed_pipeline.read_json(path)
    if tamper == "pretend_complete":
        value["cases"][1]["status"] = "BLOCKED"
    elif tamper == "invented_overall_coverage":
        value["cross_case_overall_coverage"] = 0.98
    elif tamper == "invented_transition_zero":
        scoped = tmp_path / "scoped/evaluation/summary.json"
        other = reviewed_pipeline.read_json(scoped)
        other["cases"][0]["impossible_transition_rate"] = 0.0
        scoped.write_text(json.dumps(other))
    path.write_text(json.dumps(value))
    if tamper:
        with pytest.raises(ValueError):
            closeout._formal_cases(tmp_path, "b" * 64, MODULES)
    else:
        assert closeout._formal_cases(tmp_path, "b" * 64, MODULES)["status"] == "PASS"


@pytest.mark.parametrize("gt", [False, True])
def test_actual_rrd_reader_rejects_gt_despite_self_reported_reader_pass(
    tmp_path: Path,
    gt: bool,
) -> None:
    import rerun as rr

    path = tmp_path / "recording.rrd"
    recording = rr.RecordingStream("SYNTHETIC_TEST_ONLY")
    recording.save(path)
    recording.log("debug/reviewed_authority", rr.TextDocument("SYNTHETIC_TEST_ONLY"), static=True)
    recording.log(
        "world/source_observation_cameras/CAM_TEST/pose", rr.Points3D([[0, 0, 0]]), static=True
    )
    if gt:
        recording.log("world/debug_ground_truth/test", rr.Points3D([[0, 0, 0]]), static=True)
    recording.flush()
    recording.disconnect()
    required = ("debug/reviewed_authority", "world/source_observation_cameras/")
    if gt:
        with pytest.raises(ValueError, match="primary GT"):
            closeout._reader(path, required)
    else:
        assert closeout._reader(path, required)["primary_gt_entities_absent"] is True


def test_actual_rrd_reader_requires_prediction_entities_not_only_source_layers(
    tmp_path: Path,
) -> None:
    import rerun as rr

    path = tmp_path / "recording.rrd"
    recording = rr.RecordingStream("SYNTHETIC_SOURCE_ONLY_MISSING_PREDICTIONS")
    recording.save(path)
    recording.log("debug/reviewed_authority", rr.TextDocument("SYNTHETIC_UNIT_TEST"), static=True)
    recording.log(
        "world/source_observation_cameras/CAM_TEST/pose", rr.Points3D([[0, 0, 0]]), static=True
    )
    recording.flush()
    recording.disconnect()
    with pytest.raises(ValueError, match="missing source layers"):
        closeout._reader(
            path, ("debug/reviewed_authority", "world/source_observation_cameras/", "world/events/")
        )


def _target_fixture(root: Path, baseline: float, proposed: float) -> argparse.Namespace:
    reviewed_pipeline.write_json(
        root / "configs/benchmarks/protocol_v1.json",
        {
            "acceptance": {"overall_pass_fail": False},
        },
    )
    (root / "docs").mkdir()
    (root / "docs/PRD.md").write_text("SYNTHETIC_FIXTURE: Case3 ADE improvement initial target 30%")
    release = root / "release"
    reviewed_pipeline.write_json(
        release / "scoped/inference_primary/summary.json",
        {
            "cases": [
                {
                    "case_id": "case3",
                    "gaps": [
                        {"gap_id": "SYNTHETIC_GAP", "gap_directory": "gap00", "time_range": [0, 10]}
                    ],
                },
            ]
        },
    )
    reviewed_pipeline.write_json(
        release / "office/evaluation/verification.json",
        {
            "measurements": {
                "case1": {
                    "spatiotemporal": {
                        "ade_m": 0.1,
                        "fde_m": 0.1,
                        "collision_rate": 0,
                        "impossible_transition_rate": 0,
                    }
                }
            },
        },
    )
    for case in ("case2", "case3"):
        folder = release / "scoped/evaluation/metrics" / case / "gap00"
        reviewed_pipeline.write_json(
            folder / "shortest_path.json", {"status": "EVALUATED", "ade_m": baseline}
        )
        reviewed_pipeline.write_json(
            folder / "spatiotemporal.json",
            {
                "status": "EVALUATED",
                "ade_m": proposed,
                "fde_m": 0.02,
                "collision_rate": 0,
                "impossible_transition_rate": None,
            },
        )
    return argparse.Namespace(root=root, release=release)


@pytest.mark.parametrize(
    "baseline,proposed,expected",
    [(1.0, 1.0, "TARGET_MISSED"), (1.0, 0.6, "TARGET_MET"), (0.0, 0.0, "N/A_ZERO_BASELINE_ADE")],
)
def test_research_gain_is_reported_without_retuning_or_global_metric_pass(
    tmp_path: Path,
    baseline: float,
    proposed: float,
    expected: str,
) -> None:
    args = _target_fixture(tmp_path, baseline, proposed)
    result = closeout._targets(args, MODULES)
    assert result["rows"][0]["status"] == expected
    assert result["rows"][0]["target_gain_fraction"] == 0.30
    assert result["overall_metric_pass"] is None and result["all_research_targets_met"] is False
    assert result["target_misses_waived_or_thresholds_retuned"] is False
    if baseline == proposed == 1.0:
        assert result["rows"][0]["ade_gain_fraction"] == 0.0
    if baseline == 0:
        assert result["rows"][0]["relative_gain_status"] == "N/A_ZERO_BASELINE_ADE"


@pytest.mark.parametrize("tamper", [False, True])
def test_supplemental_validation_accepts_interpreter_m_flag_but_binds_exact_new_bytes(
    tmp_path: Path,
    tamper: bool,
) -> None:
    path, receipt = _validation_fixture(tmp_path / "validation")
    script, test = "scripts/audit.py", "tests/unit/test_audit.py"
    for relative in (script, test):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("SYNTHETIC_SOURCE_FIXTURE")
    xml = ET.Element("testsuites")
    suite = ET.SubElement(xml, "testsuite")
    ET.SubElement(suite, "testcase", classname="tests.unit.test_audit", name="test_audit")
    ET.ElementTree(xml).write(path.parent / "junit.xml")
    receipt.update(
        {
            "schema_version": "phase1-supplemental-validation-v1",
            "validation_population": "UNIT_TEST_POPULATION",
            "expected_population_count": 1,
            "full_counts": {"tests": 1, "passed": 1, "failures": 0, "errors": 0, "skipped": 0},
            "all_node_ids": [test + "::test_audit"],
            "junit_file_sha256": reviewed_pipeline.digest(path.parent / "junit.xml"),
            "pytest_command": ["python", "-m", "pytest", "-q", test],
            "validated_files_unchanged": True,
            "validated_file_hashes": {
                relative: reviewed_pipeline.digest(tmp_path / relative)
                for relative in (script, test)
            },
            "checks": {key: value for key, value in receipt["checks"].items() if key != "diff"},
        }
    )
    receipt["all_node_ids_content_sha256"] = content_sha256(receipt["all_node_ids"])
    path.write_text(json.dumps(receipt))
    if tamper:
        (tmp_path / script).write_text("CHANGED_AFTER_VALIDATION")
        with pytest.raises(ValueError, match="validated bytes"):
            closeout._validation(
                path,
                MODULES,
                root=tmp_path,
                master_sha="b" * 64,
                code_commit="c" * 40,
                source_state=STATE,
                count=1,
                population="UNIT_TEST_POPULATION",
                script=script,
                test=test,
            )
    else:
        assert (
            closeout._validation(
                path,
                MODULES,
                root=tmp_path,
                master_sha="b" * 64,
                code_commit="c" * 40,
                source_state=STATE,
                count=1,
                population="UNIT_TEST_POPULATION",
                script=script,
                test=test,
            )["status"]
            == "PASS"
        )


@pytest.mark.parametrize("lineage_changes", [False, True])
def test_workflow_can_freeze_valid_target_miss_but_not_changed_primary_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lineage_changes: bool,
) -> None:
    args = _target_fixture(tmp_path, 1.0, 1.0)
    source = tmp_path / "source.blend"
    source.write_bytes(b"SYNTHETIC_TEST_ONLY")
    master = tmp_path / "master.json"
    reviewed_pipeline.write_json(master, {"producer_hashes": {"synthetic.py": "a" * 64}})
    controller_path = tmp_path / closeout.CONTROLLER
    controller_path.parent.mkdir()
    controller_path.write_text("SYNTHETIC_CONTROLLER_FIXTURE")
    for relative in (closeout.METADATA_SCRIPT, closeout.SEMANTIC_SCRIPT):
        (tmp_path / relative).write_text("SYNTHETIC_REVIEWED_COMPARATOR_FIXTURE")
    args.master, args.source, args.reproduction = master, source, tmp_path / "repro"
    args.controller_validation, args.closeout_validation = (
        tmp_path / "ctrl.json",
        tmp_path / "audit.json",
    )
    args.expected_closeout_tests, args.expected_code_commit = 21, "c" * 40
    args.semantic_validation, args.metadata_validation = (
        tmp_path / "sem.json",
        tmp_path / "meta.json",
    )
    args.expected_semantic_tests, args.expected_metadata_tests = 1, 1
    args.expected_controller_sha256 = reviewed_pipeline.digest(controller_path)
    args.expected_closeout_sha256 = reviewed_pipeline.digest(Path(closeout.__file__))
    calls = []

    def ready(*values: Any) -> dict[str, Any]:
        calls.append(values)
        return {"sha": "changed" if lineage_changes and len(calls) == 2 else "same"}

    controller = SimpleNamespace(_ready=ready)
    monkeypatch.setattr(closeout, "_modules", lambda *a: MODULES)
    monkeypatch.setattr(closeout, "_load", lambda *a: controller)
    for name in (
        "_commit_producers",
        "_formal_cases",
        "_source_readiness",
        "_metadata_resolution",
        "_reproduction",
        "_clean_delivery",
        "_validation",
        "_demo",
    ):
        monkeypatch.setattr(
            closeout, name, lambda *a, **k: {"status": "PASS", "fixture": "SYNTHETIC_ONLY"}
        )
    result = closeout.audit_acceptance(args)
    assert result["freeze_allowed"] is (not lineage_changes)
    assert result["research_target_report"]["rows"][0]["status"] == "TARGET_MISSED"
    assert result["all_research_targets_met"] is False and result["overall_metric_pass"] is None
    assert result["primary_verification_overwritten"] is False
    assert result["inference_or_reference_metrics_recalculated"] is False
    if lineage_changes:
        assert result["blockers"] == [
            {
                "gate": "final_immutable_source_and_primary_check",
                "reason": "source/master/primary evaluation changed during closeout audit",
            }
        ]


def test_claimed_same_commit_is_not_enough_when_frozen_producer_bytes_differ(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        closeout.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0,
            stdout=b"CHANGED_CORE_PRODUCER_BYTES",
        ),
    )
    master = {
        "producer_hashes": {"src/amidst/core.py": hashlib.sha256(b"FROZEN_BYTES").hexdigest()}
    }
    with pytest.raises(ValueError, match="differs from frozen producer"):
        closeout._commit_producers(tmp_path, master, "c" * 40)


@pytest.mark.parametrize("changed_source", [False, True])
@pytest.mark.parametrize("raw_status", ["PASS", "FAIL", "RESOLVED_FAIL", "FORGED_RESOLUTION"])
def test_reproduction_lineage_json_roundtrip_preserves_tuple_source_state_and_all_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_source: bool,
    raw_status: str,
) -> None:
    root = tmp_path / "reproduction"
    root.mkdir()
    (root / "logs").mkdir()
    master = tmp_path / "master.json"
    reviewed_pipeline.write_json(master, {"fixture": "SYNTHETIC_UNIT_TEST"})
    lineage = {
        "source_hash_size_mtime": ("a" * 64, 1, 123),
        "producer_closure_file_count": 116,
        "master_file_sha256": reviewed_pipeline.digest(master),
    }
    office = {"reproduction_status": "PASS", "fixture": "SYNTHETIC_UNIT_TEST"}
    office_gates = {"status": "PASS", "fixture": "SYNTHETIC_UNIT_TEST"}
    jobs = {}
    for name in closeout.WORKERS:
        log = root / "logs" / (name + ".log")
        log.write_text("SYNTHETIC_UNIT_TEST_WORKER_LOG")
        jobs[name] = {
            "worker": name,
            "returncode": 0,
            "log": str(log),
            "log_sha256": reviewed_pipeline.digest(log),
        }
        reviewed_pipeline.write_json(
            root / "jobs" / (name + ".json"), office if name == "office" else {}
        )
    scoped = {
        "status": "PASS" if raw_status == "PASS" else "INCOMPLETE",
        "comparisons": {name: {"status": "PASS"} for name in closeout.RUNS},
        "gt_recipe_reference_annotation_poison_status": "PASS",
        "termination_status": "PASS",
        "termination_ledger": [
            {
                "termination_reason": "COMPLETE",
                "generation_complete": True,
                "inventory_complete": True,
            }
        ],
    }
    receipt = {
        "schema_version": "phase1-joint-parallel-reproduction-receipt-v1",
        "status": "PASS" if raw_status == "PASS" else "FAIL",
        "execution_method": closeout.MODE,
        "original_sequential_runner_executed": False,
        "controller_file_sha256": "d" * 64,
        "master_file_sha256": reviewed_pipeline.digest(master),
        "max_active_workers": 4,
        "interpreter_start_method": "SUBPROCESS_FRESH_INTERPRETERS_NO_FORK",
        "same_worker_repeat_order_provider_reuse_only": True,
        "wallclock_budgets_and_frozen_public_checks_preserved": True,
        "frozen_primary_and_source_unchanged": True,
        "frozen_lineage_before": lineage,
        "frozen_lineage_after": lineage,
        "jobs": jobs,
        "scoped": scoped,
        "office": office,
        "original_office_field_gates": office_gates,
    }
    reviewed_pipeline.write_json(root / "joint_reproduction_receipt.json", receipt)
    reviewed_pipeline.write_json(root / "verification.json", scoped)
    reviewed_pipeline.write_json(
        root / "poison_sensitivity.json",
        {
            "inference_artifacts_byte_identical": True,
            "manifest_preserved": True,
            "changed_partitions": {
                "ground_truth": ["test"],
                "recipe": ["test"],
                "reference_annotation": ["test"],
            },
            "records": [
                {
                    "status": "PASS",
                    "evaluation_changed": True,
                    "normal": {"ade_m": 1},
                    "poisoned": {"ade_m": 2},
                }
            ],
        },
    )
    live = dict(lineage)
    if changed_source:
        live["source_hash_size_mtime"] = ("a" * 64, 1, 124)
    p = SimpleNamespace(
        read_json=reviewed_pipeline.read_json,
        digest=reviewed_pipeline.digest,
        compare_frozen_runs=lambda *a: {"status": "PASS"},
    )
    modules = SimpleNamespace(p=p)
    for function in ("_job_bodies", "_termination_coverage", "_poison_coverage"):
        monkeypatch.setattr(closeout, function, lambda *a: {"status": "PASS"})
    controller = SimpleNamespace(_office_gates=lambda *a: office_gates)
    args = argparse.Namespace(
        master=master,
        release=tmp_path / "release",
        reproduction=root,
        expected_controller_sha256="d" * 64,
    )
    resolution = None
    if raw_status in {"RESOLVED_FAIL", "FORGED_RESOLUTION"}:
        resolution = {
            "status": "PASS",
            "comparison": {
                "schema_version": "phase1-case23-delivery-metadata-resolution-v1",
                "original_controller_status": "FAIL",
                "original_scoped_status": "INCOMPLETE",
                "original_failed_receipts_overwritten_or_relabelled": False,
                "original_receipt_file_sha256": {
                    "controller": reviewed_pipeline.digest(
                        root / "joint_reproduction_receipt.json"
                    ),
                    "scoped": reviewed_pipeline.digest(root / "verification.json"),
                },
            },
        }
        if raw_status == "FORGED_RESOLUTION":
            resolution["comparison"]["original_receipt_file_sha256"]["controller"] = "f" * 64
    if raw_status in {"FAIL", "FORGED_RESOLUTION"}:
        with pytest.raises(ValueError, match="actual reviewed parallel reproduction did not pass"):
            closeout._reproduction(args, modules, controller, live, resolution)
    elif changed_source:
        with pytest.raises(ValueError, match="frozen lineage differs"):
            closeout._reproduction(args, modules, controller, live, resolution)
    else:
        result = closeout._reproduction(args, modules, controller, live, resolution)
        assert result["status"] == "PASS"
        assert result["original_controller_status"] == ("PASS" if raw_status == "PASS" else "FAIL")
        assert result["verified_metadata_resolution_applied"] is (raw_status == "RESOLVED_FAIL")
        assert isinstance(live["source_hash_size_mtime"], tuple)
        assert isinstance(
            reviewed_pipeline.read_json(root / "joint_reproduction_receipt.json")[
                "frozen_lineage_before"
            ]["source_hash_size_mtime"],
            list,
        )


@pytest.mark.parametrize("tamper", [None, "recording", "preview"])
def test_scoped_demo_reader_pass_does_not_override_artifact_sha_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str | None,
) -> None:
    folder = tmp_path / "release/scoped/evaluation/demos/case2"
    folder.mkdir(parents=True)
    (folder / "scoped.rrd").write_bytes(b"SYNTHETIC_TEST_CONTAINER_NOT_NATIVE")
    (folder / "preview.png").write_bytes(b"SYNTHETIC_TEST_PREVIEW")
    reader = {
        "recording_count": 1,
        "store_count": 8,
        "chunk_count": 8,
        "required_source_layers_verified": True,
        "primary_gt_entities_absent": True,
        "rrd_reader_verified": True,
    }
    authority = {"fixture": "SYNTHETIC_TEST_ONLY"}
    presentation = {
        "schema_version": "phase1-scoped-source-presentation-v1",
        "case_id": "case2",
        "rrd_reader_verified": True,
        "reader": reader,
        "ground_truth_logged_to_primary_recording": False,
        "gt_debug_default_visible": False,
        "ground_truth_read": False,
        "coordinate_units": "METRES",
        "source_sha256": "a" * 64,
        "authority": authority,
        "requested_k_is_not_padded": True,
        "full_raw_samples_and_recoveries_retained": True,
        "geometry": {"outer_rectangle_used_as_domain": False, "hole_count": 1},
        "source_observation_cameras": [{"camera_id": "SYNTHETIC_CAMERA"}],
        "artifacts": {
            "recording": {
                "filename": "scoped.rrd",
                "sha256": reviewed_pipeline.digest(folder / "scoped.rrd"),
            },
            "preview": {
                "filename": "preview.png",
                "sha256": reviewed_pipeline.digest(folder / "preview.png"),
            },
        },
    }
    reviewed_pipeline.write_json(folder / "presentation.json", presentation)
    if tamper:
        (folder / ("scoped.rrd" if tamper == "recording" else "preview.png")).write_bytes(
            b"CHANGED_AFTER_READER_RECEIPT"
        )
    monkeypatch.setattr(closeout, "_reader", lambda *a: reader)
    monkeypatch.setattr(
        closeout,
        "_scoped_demo_events",
        lambda *a: [
            {
                "event_id": "SYNTHETIC_EVENT",
                "candidates": [{"candidate_id": "SYNTHETIC_CANDIDATE"}],
                "trajectories": [{"hypothesis_id": "SYNTHETIC_HYPOTHESIS"}],
            }
        ],
    )
    args = argparse.Namespace(release=tmp_path / "release")
    master = {"source_sha256": "a" * 64, "inference_config": {"authority": authority}}
    if tamper:
        with pytest.raises(ValueError, match="artifact SHA differs"):
            closeout._demo(args, MODULES, "case2", master)
    else:
        assert closeout._demo(args, MODULES, "case2", master)["status"] == "PASS"


@pytest.mark.parametrize(
    "tamper",
    [
        None,
        "truncated_denominator",
        "oracle_prediction",
        "evaluation_partition_read",
        "simulation_partition_read",
        "source_recipes_deserialized",
        "missing_reference_isolation_flag",
    ],
)
def test_independent_source_readiness_cannot_hide_truncated_population_or_oracle_predictions(
    tmp_path: Path,
    tamper: str | None,
) -> None:
    master_path = tmp_path / "master.json"
    authority = {"fixture": "SYNTHETIC_AUTHORITY_ONLY"}
    master = {"inference_config": {"authority": authority}}
    reviewed_pipeline.write_json(master_path, master)
    release = tmp_path / "release"
    for relative in (
        "joint_inference_freeze.json",
        "scoped/dataset/manifest.json",
        "scoped/inference_primary/inference_freeze.json",
    ):
        reviewed_pipeline.write_json(release / relative, {"fixture": "SYNTHETIC_UNIT_TEST"})
    reviewed_pipeline.write_json(
        release / "scoped/inference_primary/summary.json",
        {
            "cases": [{"case_id": "case3", "gaps": [{"gap_directory": "gap00"}]}],
        },
    )
    receipt = {
        "schema_version": "phase1-independent-gt-free-source-readiness-audit-v1",
        "status": "PRE_GT_CASE2_CASE3_SOURCE_READINESS_PASS",
        "master_file_sha256": reviewed_pipeline.digest(master_path),
        "authority": authority,
        "ground_truth_read": False,
        "evaluation_partition_read": tamper == "evaluation_partition_read",
        "simulation_partition_read": tamper == "simulation_partition_read",
        "source_recipes_deserialized": tamper == "source_recipes_deserialized",
        "oracle_routes_used_as_predictions": tamper == "oracle_prediction",
        "producer_master_config_or_source_modified": False,
        "raw_graph_termination_population_is_separate_from_declared_class_grammar": True,
        "full_C_gap_count": 1,
        "raw_full_visibility_graph_termination_counts": {"MAX_BRANCH_FACTOR": 1},
        "C_gap_records": [
            {
                "case_id": "case3",
                "gap_directory": "gap00",
                "pre_gt_source_readiness_status": "PASS",
                "class_generation_complete": True,
                "inventory_complete": True,
                "source_denominator_complete": tamper != "truncated_denominator",
            }
        ],
    }
    if tamper == "missing_reference_isolation_flag":
        receipt.pop("source_recipes_deserialized")
    for field, relative in (
        ("joint_inference_freeze_file_sha256", "joint_inference_freeze.json"),
        ("scoped_dataset_manifest_file_sha256", "scoped/dataset/manifest.json"),
        ("scoped_inference_freeze_file_sha256", "scoped/inference_primary/inference_freeze.json"),
        ("scoped_inference_summary_file_sha256", "scoped/inference_primary/summary.json"),
    ):
        receipt[field] = reviewed_pipeline.digest(release / relative)
    reviewed_pipeline.write_json(release / "source_readiness_audit.json", receipt)
    args = argparse.Namespace(release=release, master=master_path)
    if tamper:
        with pytest.raises(ValueError):
            closeout._source_readiness(args, MODULES, master)
    else:
        result = closeout._source_readiness(args, MODULES, master)
        assert result["status"] == "PASS"
        assert result["raw_full_visibility_graph_termination_counts"] == {"MAX_BRANCH_FACTOR": 1}


def _poison_fixture(root: Path) -> tuple[argparse.Namespace, dict[str, Any], dict[str, Any]]:
    cases = ("case2", "case3", "case3_short_control", "case3_long_stress")
    artifacts = {
        f"{partition}/{case}/{filename}": "a" * 64
        for case in cases
        for partition, filename in (
            ("evaluation", "ground_truth.json"),
            ("simulation", "recipe.json"),
            ("evaluation", "reference_movement_annotations.json"),
        )
    }
    release = root / "release"
    reviewed_pipeline.write_json(
        release / "scoped/dataset/manifest.json",
        {
            "cases": [{"case_id": case} for case in cases],
            "artifacts": artifacts,
        },
    )
    summary, records = [], []
    for case in sorted(cases):
        gaps = []
        for index in range(2 if case == "case3_short_control" else 3):
            gap = f"gap{index:02d}"
            gaps.append({"gap_directory": gap})
            reviewed_pipeline.write_json(
                release / "scoped/inference_primary" / case / gap / "spatiotemporal/run.json",
                {"event": {"trajectories": [{"fixture": "SYNTHETIC_TIMING"}]}},
            )
            records.append(
                {
                    "case_id": case,
                    "gap_directory": gap,
                    "status": "PASS",
                    "evaluation_changed": True,
                    "normal": {"ade": 1},
                    "poisoned": {"ade": 2},
                }
            )
        summary.append({"case_id": case, "gaps": gaps})
    reviewed_pipeline.write_json(
        release / "scoped/inference_primary/summary.json", {"cases": summary}
    )
    poison = {
        "inference_artifacts_byte_identical": True,
        "manifest_preserved": True,
        "changed_partitions": {
            "ground_truth": sorted(p for p in artifacts if p.endswith("ground_truth.json")),
            "recipe": sorted(p for p in artifacts if p.endswith("recipe.json")),
            "reference_annotation": sorted(
                p for p in artifacts if p.endswith("reference_movement_annotations.json")
            ),
        },
        "records": records,
    }
    scoped = {"gt_sensitive_case_ids": sorted(cases), "gt_metric_sensitivity_unavailable": []}
    return argparse.Namespace(release=release), poison, scoped


@pytest.mark.parametrize(
    "tamper",
    [
        None,
        "empty_partitions",
        "one_partition",
        "one_case_only",
        "one_sensitivity_row",
        "duplicate_query",
        "foreign_query",
        "fake_na",
    ],
)
def test_poison_requires_all_three_partitions_and_every_frozen_11_query(
    tmp_path: Path,
    tamper: str | None,
) -> None:
    args, poison, scoped = _poison_fixture(tmp_path)
    if tamper == "empty_partitions":
        poison["changed_partitions"] = {}
    elif tamper == "one_partition":
        poison["changed_partitions"].pop("recipe")
    elif tamper == "one_case_only":
        poison["changed_partitions"]["ground_truth"] = poison["changed_partitions"]["ground_truth"][
            :1
        ]
    elif tamper == "one_sensitivity_row":
        poison["records"] = poison["records"][:1]
    elif tamper == "duplicate_query":
        poison["records"][1] = dict(poison["records"][0])
    elif tamper == "foreign_query":
        poison["records"][0]["gap_directory"] = "gap99"
    elif tamper == "fake_na":
        poison["records"][0]["status"] = "N/A_NO_TIMED_CANDIDATES"
    if tamper:
        with pytest.raises(ValueError):
            closeout._poison_coverage(args, MODULES, poison, scoped)
    else:
        assert (
            closeout._poison_coverage(args, MODULES, poison, scoped)["measured_query_count"] == 11
        )


@pytest.mark.parametrize("tamper", [None, "one_row", "duplicate_row", "false_complete"])
def test_termination_requires_full_four_run_308_variant_population(
    tmp_path: Path,
    tamper: str | None,
) -> None:
    ledger = []
    for run in ("repeat", "fresh_process", "reordered", "gt_poison"):
        gaps = []
        for _gap in range(11):
            variants = [
                {
                    "variant": f"SYNTHETIC_VARIANT_{variant}",
                    "status": "EXECUTED",
                    "termination_reason": "MAX_PATHS_REACHED" if variant == 0 else "COMPLETE",
                    "generation_complete": True,
                    "inventory_complete": True,
                }
                for variant in range(7)
            ]
            gaps.append({"variants": variants})
            ledger.extend(variants)
        reviewed_pipeline.write_json(tmp_path / run / "summary.json", {"cases": [{"gaps": gaps}]})
    declared = json.loads(json.dumps(ledger))
    if tamper == "one_row":
        declared = declared[:1]
    elif tamper == "duplicate_row":
        declared[1] = dict(declared[0])
    elif tamper == "false_complete":
        declared[0]["generation_complete"] = False
    args = argparse.Namespace(reproduction=tmp_path)
    if tamper:
        with pytest.raises(ValueError):
            closeout._termination_coverage(args, MODULES, declared)
    else:
        assert (
            closeout._termination_coverage(args, MODULES, declared)["executed_variant_run_count"]
            == 308
        )


def test_foreign_rrd_prediction_ids_cannot_satisfy_required_event_prefix(tmp_path: Path) -> None:
    import rerun as rr

    recording = rr.RecordingStream("SYNTHETIC_FOREIGN_EVENT_FIXTURE")
    path = tmp_path / "foreign.rrd"
    recording.save(path)
    recording.log(
        "world/events/FOREIGN_EVENT/candidates/FOREIGN_CANDIDATE",
        rr.LineStrips3D([[[0, 0, 0], [1, 0, 0]]]),
        static=True,
    )
    recording.flush()
    recording.disconnect()
    expected = closeout._prediction_entities(
        [
            {
                "event_id": "EXPECTED_EVENT",
                "candidates": [{"candidate_id": "EXPECTED_CANDIDATE"}],
                "trajectories": [],
            }
        ]
    )
    with pytest.raises(ValueError):
        closeout._reader(path, ("world/events/",), expected)


@pytest.mark.parametrize(
    "tamper", [None, "foreign_event", "reissued_foreign_run", "wrong_production_hash", "wrong_gap"]
)
def test_scoped_presentation_is_bound_to_same_case_frozen_event_and_run(
    tmp_path: Path,
    tamper: str | None,
) -> None:
    primary = tmp_path / "release/scoped/inference_primary"
    reviewed_pipeline.write_json(
        primary / "summary.json",
        {
            "cases": [
                {
                    "case_id": "case2",
                    "gaps": [{"gap_id": "SYNTHETIC_GAP", "gap_directory": "gap00"}],
                }
            ]
        },
    )
    event = {
        "event_id": "SYNTHETIC_EVENT",
        "candidates": [{"candidate_id": "SYNTHETIC_CANDIDATE"}],
        "trajectories": [],
    }
    run = {"event": event, "navigation_content_sha256": "a" * 64, "fixture": "SYNTHETIC_FROZEN_RUN"}
    production, aggregation, context = (
        {"fixture": "PRODUCTION"},
        {"fixture": "AGGREGATION"},
        {"fixture": "CONTEXT"},
    )
    for relative, value in (
        ("case2/gap00/spatiotemporal/run.json", run),
        ("case2/gap00/spatiotemporal/production.json", production),
        ("case2/aggregation.json", aggregation),
        ("case2/scoped_context.json", context),
    ):
        reviewed_pipeline.write_json(primary / relative, value)
    record = {
        "gap_id": "SYNTHETIC_GAP",
        "event": event,
        "run": run,
        "production": production,
        "run_content_sha256": content_sha256(run),
        "production_content_sha256": content_sha256(production),
        "aggregation_content_sha256": content_sha256(aggregation),
        "context_content_sha256": content_sha256(context),
        "navigation_content_sha256": "a" * 64,
    }
    record = json.loads(json.dumps(record))
    if tamper == "foreign_event":
        record["event"]["event_id"] = "FOREIGN_EVENT"
    elif tamper == "reissued_foreign_run":
        record["run"]["event"]["event_id"] = "FOREIGN_EVENT"
        record["event"] = record["run"]["event"]
        record["run_content_sha256"] = content_sha256(record["run"])
    elif tamper == "wrong_production_hash":
        record["production_content_sha256"] = "f" * 64
    elif tamper == "wrong_gap":
        record["gap_id"] = "FOREIGN_GAP"
    args = argparse.Namespace(release=tmp_path / "release")
    if tamper:
        with pytest.raises(ValueError):
            closeout._scoped_demo_events(args, MODULES, {"gaps": [record]}, "case2")
    else:
        assert closeout._scoped_demo_events(args, MODULES, {"gaps": [record]}, "case2") == [event]


def test_missing_measured_ade_in_timed_baseline_blocks_target_report(tmp_path: Path) -> None:
    args = _target_fixture(tmp_path, 1.0, 1.0)
    path = args.release / "scoped/evaluation/metrics/case3/gap00/shortest_path.json"
    value = reviewed_pipeline.read_json(path)
    value["ade_m"] = None
    value["timed_candidate_count"] = 1
    path.write_text(json.dumps(value))
    reviewed_pipeline.write_json(
        args.release / "scoped/inference_primary/case3/gap00/shortest_path/run.json",
        {
            "event": {"trajectories": [{"fixture": "SYNTHETIC_TIMED_CANDIDATE"}]},
        },
    )
    with pytest.raises(ValueError, match="required timed A/C ADE measurement is missing"):
        closeout._targets(args, MODULES)
