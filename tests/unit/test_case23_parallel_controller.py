"""Synthetic orchestration checks; these are not native research receipts."""

import argparse
import importlib.util
import json
import shutil
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REPO = Path(__file__).resolve().parents[2]
HERE = REPO / "scripts/reproduce_case23_parallel.py"
controller = _load(HERE, "phase1_parallel_controller_test_module")
fixtures = _load(REPO / "tests/unit/test_scoped_reproduction.py", "scoped_repro_fixture_module")


def test_active_numerical_workers_are_bounded_at_four(monkeypatch: pytest.MonkeyPatch) -> None:
    counts = {"active": 0, "peak": 0, "completed": 0}
    lock = threading.Lock()

    def job(args: Any, worker: str) -> dict[str, Any]:
        with lock:
            counts["active"] += 1
            counts["peak"] = max(counts["peak"], counts["active"])
        time.sleep(0.04)
        with lock:
            counts["active"] -= 1
            counts["completed"] += 1
        return {"worker": worker, "returncode": 0}

    monkeypatch.setattr(controller, "_subprocess_job", job)
    jobs = controller._schedule(SimpleNamespace())
    assert counts == {"active": 0, "peak": 4, "completed": 5}
    assert set(jobs) == set(controller.WORKERS)


def test_failed_joint_gate_stops_before_any_reference_receipt_read() -> None:
    calls = []

    def read_json(path: Path) -> dict[str, Any]:
        calls.append(path.name)
        return {}

    def joint(*args: Any) -> None:
        calls.append("joint_gate")
        raise ValueError("primary is not jointly frozen")

    modules = SimpleNamespace(
        p=SimpleNamespace(read_json=read_json),
        protocol=SimpleNamespace(
            validate_master_bindings=lambda *a: None, require_joint_inference_boundary=joint
        ),
    )
    args = SimpleNamespace(master=Path("master.json"), root=REPO, release=Path("release"))
    with pytest.raises(ValueError, match="jointly frozen"):
        controller._ready(args, modules)
    assert calls == ["master.json", "joint_gate"]


def test_repeat_and_order_share_one_worker_loaded_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from amidst.finalization import reviewed_pipeline

    sentinel = object()
    loads, calls = [], []

    def load(root: Path) -> object:
        loads.append(root)
        return sentinel

    def infer(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    modules = SimpleNamespace(
        p=reviewed_pipeline,
        repro=SimpleNamespace(),
        export=SimpleNamespace(load_export_authority=load),
        pipeline=SimpleNamespace(infer_scoped_dataset=infer),
    )
    monkeypatch.setattr(controller, "_ready", lambda *a: {})
    args = argparse.Namespace(
        root=REPO,
        release=tmp_path / "release",
        master=tmp_path / "master",
        output=tmp_path / "output",
        worker="repeat-order",
    )
    controller._run_worker(args, modules)
    assert loads == [REPO] and len(calls) == 2
    assert all(call[1]["provider"] is sentinel for call in calls)
    assert [call[1]["reordered"] for call in calls] == [False, True]
    assert (args.output / "jobs/repeat-order.json").is_file()


@pytest.mark.parametrize(
    "failure",
    [None, "office", "worker", "termination", "lineage", "office_annotation", "missing_worker"],
)
def test_parallel_receipt_preserves_all_canonical_and_failure_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
) -> None:
    from amidst.finalization import reviewed_pipeline, scoped_reproduction

    packages = fixtures._packages(tmp_path)
    release = tmp_path / "release"
    scope = release / "scoped"
    scope.mkdir(parents=True)
    for kind, source in (
        ("dataset", packages["local_dataset"]),
        ("inference_primary", packages["local_inference"]),
    ):
        shutil.copytree(source, scope / kind)
    output = tmp_path / "parallel"
    output.mkdir()
    poison = scoped_reproduction.create_scoped_poison_dataset(
        scope / "dataset",
        output / "poison_dataset",
        primary=scope / "inference_primary",
    )
    for name in ("repeat", "fresh_process", "reordered", "gt_poison"):
        shutil.copytree(scope / "inference_primary", output / name)
    if failure == "termination":
        path = output / "repeat/summary.json"
        summary = reviewed_pipeline.read_json(path)
        summary["cases"][0]["gaps"][0]["variants"][0]["generation_complete"] = False
        path.write_text(__import__("json").dumps(summary))
        # Canonical comparison also fails because the primary semantics changed;
        # the termination receipt must independently preserve its FAIL.
    reviewed_pipeline.write_json(output / "jobs/clean.json", {"status": "PASS"})
    reviewed_pipeline.write_json(output / "jobs/fresh.json", {"command": {"returncode": 0}})
    reviewed_pipeline.write_json(
        output / "jobs/office.json",
        {"reproduction_status": "FAIL" if failure == "office" else "PASS"},
    )
    reviewed_pipeline.write_json(
        release / "office/reproduction/verification.json",
        {
            "status": "PASS",
            "comparisons": {
                name: {"status": "PASS"}
                for name in (
                    "repeat",
                    "fresh_process",
                    "reordered",
                    "gt_poison",
                )
            },
            "repeat_status": "PASS",
            "fresh_process_status": "PASS",
            "ordering_status": "PASS",
            "gt_poison_status": "PASS",
            "termination_status": "PASS",
            "annotation_poison_inference_unchanged": failure != "office_annotation",
            "poisoned_reference_annotation_files": 2,
            "gt_poison_evaluation_changed": [True, True],
        },
    )
    lineage = {"master_file_sha256": "a" * 64}
    monkeypatch.setattr(
        controller,
        "_ready",
        lambda *a: {"master_file_sha256": "b" * 64} if failure == "lineage" else lineage,
    )
    monkeypatch.setattr(
        scoped_reproduction,
        "_gt_metric_probe",
        lambda *a: [
            {"case_id": case, "status": "PASS", "evaluation_changed": True}
            for case in fixtures.CASES
        ],
    )
    modules = SimpleNamespace(p=reviewed_pipeline, repro=scoped_reproduction)
    jobs = {
        worker: {"returncode": -1 if failure == "worker" and worker == "fresh" else 0}
        for worker in controller.WORKERS
    }
    if failure == "missing_worker":
        jobs.pop("fresh")
    args = argparse.Namespace(release=release, master=packages["master"], output=output)
    result = controller._finalize(args, modules, lineage, poison, jobs)
    assert result["status"] == ("PASS" if failure is None else "FAIL")
    assert result["execution_method"] == controller.MODE
    assert result["original_sequential_runner_executed"] is False
    assert result["formal_freeze_granted"] is False
    assert result["controller_file_sha256"] == controller._controller_sha256()
    assert set(result["scoped"]["comparisons"]) == {
        "repeat",
        "fresh_process",
        "reordered",
        "gt_poison",
    }
    assert result["scoped"]["gt_recipe_reference_annotation_poison_status"] == "PASS"
    if failure == "termination":
        assert result["scoped"]["termination_status"] == "FAIL"
    if failure == "lineage":
        assert result["frozen_primary_and_source_unchanged"] is False
    if failure == "office_annotation":
        assert result["original_office_field_gates"]["status"] == "FAIL"
    assert (output / "joint_reproduction_receipt.json").is_file()


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "office_summary_only",
        "office_foreign_manifest",
        "scoped_foreign_freeze",
        "office_unverified_freeze",
        "joint_receipt_foreign_freeze",
    ],
)
def test_ready_uses_actual_child_evaluation_paths_and_exact_hash_bindings(
    tmp_path: Path,
    failure: str | None,
) -> None:
    from amidst.finalization import reviewed_pipeline, scoped_reproduction

    source = tmp_path / "source.blend"
    source.write_bytes(b"SYNTHETIC_UNIT_TEST_SOURCE_ONLY")
    master = tmp_path / "master.json"
    reviewed_pipeline.write_json(
        master,
        {
            "source_sha256": reviewed_pipeline.digest(source),
            "producer_hashes": {"synthetic.py": "a" * 64},
            "protected_input_hashes": {},
        },
    )
    release = tmp_path / "release"
    evaluations = {}
    for name, cases in (("office", ("case1", "case2", "case3")), ("scoped", fixtures.CASES)):
        child = release / name
        reviewed_pipeline.write_json(
            child / "dataset/manifest.json",
            {
                "cases": [{"case_id": case} for case in cases],
            },
        )
        reviewed_pipeline.write_json(
            child / "inference_primary/summary.json",
            {
                "cases": [{"case_id": case} for case in cases],
                "source": "SYNTHETIC_TEST_ONLY",
            },
        )
        reviewed_pipeline.freeze_inference(
            child / "inference_primary",
            dataset_manifest_sha256=reviewed_pipeline.digest(child / "dataset/manifest.json"),
            config_sha256=reviewed_pipeline.digest(master),
        )
        if name == "office":
            path = child / "evaluation/verification.json"
            receipt = {
                "schema_version": "phase1-reviewed-evaluation-report-v1",
                "status": "PHASE1_FINALIZATION_BLOCKED",
                "dataset_manifest_sha256": reviewed_pipeline.digest(
                    child / "dataset/manifest.json"
                ),
                "primary_inference_freeze_sha256": reviewed_pipeline.digest(
                    child / "inference_primary/inference_freeze.json"
                ),
                "evaluation_inference_freeze_verified": True,
            }
        else:
            path = child / "evaluation/summary.json"
            receipt = {
                "schema_version": "phase1-scoped-evaluation-summary-v1",
                "status": "SCOPED_CASE23_VALIDATED",
                "dataset_manifest_file_sha256": reviewed_pipeline.digest(
                    child / "dataset/manifest.json"
                ),
                "inference_freeze_file_sha256": reviewed_pipeline.digest(
                    child / "inference_primary/inference_freeze.json"
                ),
                "source_sha256": reviewed_pipeline.digest(source),
                "original_protocol_preserved": True,
            }
        receipt["cases"] = [{"case_id": case} for case in cases]
        reviewed_pipeline.write_json(path, receipt)
        evaluations[name] = path
    reviewed_pipeline.write_json(
        release / "joint_inference_freeze.json",
        {
            "fixture": "SYNTHETIC_TEST_ONLY_NOT_A_REAL_JOINT_GATE",
        },
    )
    reviewed_pipeline.write_json(
        release / "primary_run_receipt.json",
        {
            "source_unchanged": True,
            "master_file_sha256": reviewed_pipeline.digest(master),
            "joint_inference_freeze_file_sha256": reviewed_pipeline.digest(
                release / "joint_inference_freeze.json"
            ),
            "source_after": [
                reviewed_pipeline.digest(source),
                source.stat().st_size,
                source.stat().st_mtime_ns,
            ],
        },
    )
    spec_path = tmp_path / "clean_checkout_spec.json"
    spec = scoped_reproduction.CleanCheckoutSpec(
        root=tmp_path,
        expected_commit="a" * 40,
        master_relative_path="master.json",
        source_config_relative_path="source.json",
        source=source,
        python_executable=Path(sys.executable),
        blender_executable=Path("/SYNTHETIC_TEST_BLENDER"),
        output=tmp_path / "fresh_joint",
        joint_release=True,
    )
    reviewed_pipeline.write_json(spec_path, spec.model_dump(mode="json"))
    args = argparse.Namespace(
        root=tmp_path,
        master=master,
        release=release,
        clean_checkout_spec=spec_path,
    )
    modules = SimpleNamespace(
        p=reviewed_pipeline,
        repro=scoped_reproduction,
        protocol=SimpleNamespace(
            validate_master_bindings=lambda *a: None,
            require_joint_inference_boundary=lambda *a: None,
        ),
    )
    if failure == "office_summary_only":
        evaluations["office"].rename(evaluations["office"].parent / "summary.json")
    elif failure in {"office_foreign_manifest", "office_unverified_freeze"}:
        receipt = reviewed_pipeline.read_json(evaluations["office"])
        if failure == "office_foreign_manifest":
            receipt["dataset_manifest_sha256"] = "f" * 64
        else:
            receipt["evaluation_inference_freeze_verified"] = False
        evaluations["office"].write_text(json.dumps(receipt))
    elif failure == "scoped_foreign_freeze":
        receipt = reviewed_pipeline.read_json(evaluations["scoped"])
        receipt["inference_freeze_file_sha256"] = "f" * 64
        evaluations["scoped"].write_text(json.dumps(receipt))
    elif failure == "joint_receipt_foreign_freeze":
        path = release / "primary_run_receipt.json"
        receipt = reviewed_pipeline.read_json(path)
        receipt["joint_inference_freeze_file_sha256"] = "f" * 64
        path.write_text(json.dumps(receipt))
    if failure:
        with pytest.raises(ValueError):
            controller._ready(args, modules)
    else:
        lineage = controller._ready(args, modules)
        assert lineage["primary_evaluations_completed"]
        for name, path in evaluations.items():
            assert lineage["primary_evaluation_bindings"][name]["receipt_file_sha256"] == (
                reviewed_pipeline.digest(path)
            )
        assert lineage["primary_evaluation_bindings"]["office"]["receipt_path"].endswith(
            "office/evaluation/verification.json"
        )
        assert not (release / "office/evaluation/summary.json").exists()
