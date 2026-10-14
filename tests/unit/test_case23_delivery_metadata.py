from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from amidst.finalization import reviewed_pipeline, scoped_reproduction

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "case23_metadata_test", ROOT / "scripts/compare_case23_delivery_metadata.py"
)
assert SPEC is not None and SPEC.loader is not None
metadata = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metadata)
MODULES = SimpleNamespace(p=reviewed_pipeline, repro=scoped_reproduction)


def _reader(count: int) -> dict[str, Any]:
    return {
        "recording_count": 1,
        "store_count": count,
        "chunk_count": count,
        "required_source_layers_verified": True,
        "primary_gt_entities_absent": True,
        "rrd_reader_verified": True,
    }


def _presentation(case: str, count: int) -> dict[str, Any]:
    return {
        "case_id": case,
        "reader": _reader(count),
        "source_sha256": "a" * 64,
        "gaps": [{"event": {"candidate_order": ["FIRST", "SECOND"]}}],
    }


def _summary(root: Path, count: int) -> dict[str, Any]:
    rows = []
    for case in ("case2", "case3"):
        presentation = _presentation(case, count)
        reviewed_pipeline.write_json(root / f"demos/{case}/presentation.json", presentation)
        rows.append(
            {
                "case_id": case,
                "reader": presentation["reader"],
                "presentation": str(root / f"demos/{case}/presentation.json"),
                "recording": str(root / f"demos/{case}/scoped.rrd"),
                "preview": str(root / f"demos/{case}/preview.png"),
            }
        )
    return {"demos": rows, "metric": {"ade_m": 0.5}, "population_count": 11}


@pytest.mark.parametrize("relative", ["demos/case3/presentation.json", "summary.json"])
def test_only_verified_reader_batch_counts_and_exact_output_path_are_normalized(
    tmp_path: Path, relative: str
) -> None:
    roots = [tmp_path / "primary", tmp_path / "clean"]
    resolved = []
    for root, count in zip(roots, (1960, 1957), strict=True):
        summary = _summary(root, count)
        value = summary if relative == "summary.json" else _presentation("case3", count)
        resolved.append(
            metadata._resolved_json(
                value,
                relative=relative,
                evaluation=root,
                modules=MODULES,
                counts={
                    case: {"recording_count": 1, "store_count": count, "chunk_count": count}
                    for case in ("case2", "case3")
                },
            )
        )
        assert value["reader"]["store_count"] == count if "reader" in value else True
    assert resolved[0] == resolved[1]


@pytest.mark.parametrize(
    "tamper",
    [
        "foreign_path",
        "foreign_case",
        "reordered_cases",
        "forged_reader_count",
        "forged_summary_reader",
    ],
)
def test_output_paths_and_reader_counts_cannot_substitute_foreign_artifacts(
    tmp_path: Path, tamper: str
) -> None:
    summary = _summary(tmp_path, 10)
    row = summary["demos"][0]
    if tamper == "foreign_path":
        row["presentation"] = str(tmp_path / "demos/case3/presentation.json")
    elif tamper == "foreign_case":
        row["case_id"] = "case3"
    elif tamper == "reordered_cases":
        summary["demos"].reverse()
    elif tamper == "forged_reader_count":
        row["reader"]["chunk_count"] += 1
        (tmp_path / "demos/case2/presentation.json").write_text(
            json.dumps(_presentation("case2", 11))
        )
    else:
        row["reader"]["rrd_reader_verified"] = False
    with pytest.raises(ValueError):
        metadata._resolved_json(
            summary,
            relative="summary.json",
            evaluation=tmp_path,
            modules=MODULES,
            counts={
                case: {"recording_count": 1, "store_count": 10, "chunk_count": 10}
                for case in ("case2", "case3")
            },
        )


@pytest.mark.parametrize(
    "tamper", ["source", "order", "reader_boolean", "extra_reader_field", "reader_count_type"]
)
def test_non_bookkeeping_values_remain_strict(tmp_path: Path, tamper: str) -> None:
    first = _presentation("case3", 10)
    second = _presentation("case3", 10)
    if tamper == "source":
        second["source_sha256"] = "b" * 64
    elif tamper == "order":
        second["gaps"][0]["event"]["candidate_order"].reverse()
    elif tamper == "reader_boolean":
        second["reader"]["primary_gt_entities_absent"] = False
    elif tamper == "reader_count_type":
        second["reader"]["recording_count"] = True
    else:
        second["reader"]["row_count"] = 10
    counts = {"case3": {"recording_count": 1, "store_count": 10, "chunk_count": 10}}
    first_normalized = metadata._resolved_json(
        first,
        relative="demos/case3/presentation.json",
        evaluation=tmp_path,
        modules=MODULES,
        counts=counts,
    )
    if tamper in {"reader_boolean", "extra_reader_field", "reader_count_type"}:
        with pytest.raises(ValueError):
            metadata._resolved_json(
                second,
                relative="demos/case3/presentation.json",
                evaluation=tmp_path,
                modules=MODULES,
                counts=counts,
            )
    else:
        assert first_normalized != metadata._resolved_json(
            second,
            relative="demos/case3/presentation.json",
            evaluation=tmp_path,
            modules=MODULES,
            counts=counts,
        )


def test_reader_count_field_outside_declared_locations_is_not_excluded(tmp_path: Path) -> None:
    counts = {"case3": {"recording_count": 1, "store_count": 10, "chunk_count": 10}}
    one = metadata._resolved_json(
        {"reader": _reader(10)},
        relative="metrics/case3/gap00/spatiotemporal.json",
        evaluation=tmp_path,
        modules=MODULES,
        counts=counts,
    )
    two = metadata._resolved_json(
        {"reader": _reader(11)},
        relative="metrics/case3/gap00/spatiotemporal.json",
        evaluation=tmp_path,
        modules=MODULES,
        counts=counts,
    )
    assert one != two


@pytest.mark.parametrize(
    "tamper",
    [
        None,
        "component_changed",
        "incomplete_coverage",
        "missing_case",
        "blueprint_claim",
        "helper_bytes",
    ],
)
def test_semantic_gate_recomputes_full_receipt_and_binds_reviewed_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tamper: str | None
) -> None:
    script = tmp_path / metadata.SEMANTIC_SCRIPT
    script.parent.mkdir()
    script.write_text("SYNTHETIC_SEMANTIC_COMPARATOR_FIXTURE")
    script_sha = reviewed_pipeline.digest(script)
    actual = {
        "schema_version": "phase1-full-data-recording-semantic-comparison-v1",
        "status": "PASS",
        "full_recording_component_timeline_coverage": True,
        "all_case_ids": ["case1", "case2", "case3"],
        "blueprint_semantics_claimed": False,
        "component_update_sha256": "a" * 64,
    }
    issued = dict(actual)
    if tamper == "component_changed":
        actual["component_update_sha256"] = "b" * 64
    elif tamper == "incomplete_coverage":
        issued["full_recording_component_timeline_coverage"] = False
        actual = dict(issued)
    elif tamper == "missing_case":
        issued["all_case_ids"] = ["case2", "case3"]
        actual = dict(issued)
    elif tamper == "blueprint_claim":
        issued["blueprint_semantics_claimed"] = True
        actual = dict(issued)
    elif tamper == "helper_bytes":
        script.write_text("UNREVIEWED_SYNTHETIC_COMPARATOR_FIXTURE")
    receipt = tmp_path / "semantic.json"
    reviewed_pipeline.write_json(receipt, issued)
    calls = []

    def compare(*args: Any) -> dict[str, Any]:
        calls.append(args)
        return actual

    monkeypatch.setattr(
        metadata, "_load", lambda *a: SimpleNamespace(verify_joint_rrd_semantics=compare)
    )
    arguments = (
        tmp_path,
        tmp_path / "primary",
        tmp_path / "clean",
        tmp_path / "master.json",
        receipt,
        script_sha,
        MODULES,
    )
    if tamper:
        with pytest.raises(ValueError):
            metadata._semantic_evidence(*arguments)
    else:
        assert metadata._semantic_evidence(*arguments) == issued
        assert calls == [(tmp_path / "primary", tmp_path / "clean", tmp_path / "master.json")]


def _delivery_fixture(root: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    release, clean_root = root / "release", root / "clean"
    clean = clean_root / "delivery"
    master_path = root / "master.json"
    reviewed_pipeline.write_json(master_path, {"fixture": "SYNTHETIC_UNIT_ONLY"})
    reviewed_pipeline.write_json(clean_root / "master.json", {"fixture": "SYNTHETIC_UNIT_ONLY"})
    semantic_script = root / metadata.SEMANTIC_SCRIPT
    semantic_script.parent.mkdir()
    semantic_script.write_text("SYNTHETIC_SEMANTIC_COMPARATOR_FIXTURE")
    reviewed_pipeline.write_json(
        release / "clean_checkout_spec.json",
        {
            "root": str(clean_root),
            "expected_commit": "c" * 40,
            "master_relative_path": "master.json",
            "source_config_relative_path": "source.json",
            "source": str(root / "SYNTHETIC_SOURCE_ONLY.blend"),
            "python_executable": str(root / "python"),
            "blender_executable": str(root / "blender"),
            "output": str(clean),
            "joint_release": True,
        },
    )
    for parent, count in ((release, 10), (clean, 11)):
        evaluation = parent / "scoped/evaluation"
        reviewed_pipeline.write_json(evaluation / "summary.json", _summary(evaluation, count))
        for name in ("verification.json", "case3_growth.json", "benchmark_table.json"):
            reviewed_pipeline.write_json(
                parent / name, {"fixture": "SYNTHETIC_EQUAL_JOINT_POPULATION"}
            )
    comparison = {
        "status": "FAIL",
        "differences": list(metadata.RAW_DIFFERENCES),
        "missing_required_reports": [],
        "dataset_manifest_and_all_artifacts_equal": True,
        "inference": {"status": "PASS"},
    }
    office = {"status": "PASS", "fixture": "SYNTHETIC_OFFICE_COMPARISON"}
    clean_job = {
        "status": "FAIL",
        "all_stages_actually_executed": True,
        "both_child_freezes_verified_before_reference_access": True,
        "initial_checkout_clean": True,
        "clean_checkout_head": "c" * 40,
        "joint_population_differences": [],
        "scoped_comparison": comparison,
        "original_office_comparison": office,
    }
    reproduction = release / "reproduction"

    def save_raw() -> None:
        scoped = {"status": "INCOMPLETE", "clean_checkout": clean_job}
        controller = {
            "status": "FAIL",
            "scoped": scoped,
            "frozen_primary_and_source_unchanged": True,
        }
        for path, value in (
            (reproduction / "joint_reproduction_receipt.json", controller),
            (reproduction / "verification.json", scoped),
            (reproduction / "jobs/clean.json", clean_job),
            (clean / "delivery_comparison.json", clean_job),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))

    save_raw()
    repro = SimpleNamespace(
        CleanCheckoutSpec=scoped_reproduction.CleanCheckoutSpec,
        _normalize=scoped_reproduction._normalize,
        _table_consistency=lambda *a: [],
        compare_scoped_deliveries=lambda **k: comparison,
    )
    modules = SimpleNamespace(
        p=reviewed_pipeline,
        repro=repro,
        protocol=SimpleNamespace(validate_master_bindings=lambda *a: None),
        office_compare=lambda **k: office,
        content_sha256=lambda value: (
            __import__("hashlib").sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        ),
    )
    monkeypatch.setattr(metadata, "_modules", lambda *a: modules)
    monkeypatch.setattr(
        metadata, "_semantic_evidence", lambda *a: {"status": "PASS", "fixture": "SYNTHETIC_ONLY"}
    )
    monkeypatch.setattr(
        metadata,
        "_actual_reader_counts",
        lambda path: {
            key: value
            for key, value in reviewed_pipeline.read_json(path.parent / "presentation.json")[
                "reader"
            ].items()
            if key in {"recording_count", "store_count", "chunk_count"}
        },
    )
    semantic_receipt = root / "semantic.json"
    reviewed_pipeline.write_json(semantic_receipt, {"fixture": "SYNTHETIC_ONLY"})
    return {
        "arguments": {
            "root": root,
            "release": release,
            "reproduction": reproduction,
            "master_path": master_path,
            "semantic_receipt_path": semantic_receipt,
            "expected_semantic_script_sha256": reviewed_pipeline.digest(semantic_script),
            "expected_adapter_sha256": reviewed_pipeline.digest(Path(metadata.__file__)),
        },
        "comparison": comparison,
        "clean_job": clean_job,
        "save_raw": save_raw,
        "repro": repro,
        "clean": clean,
    }


@pytest.mark.parametrize(
    "tamper",
    [
        None,
        "extra_raw_difference",
        "missing_report",
        "failed_inference",
        "incomplete_actual_rerun",
        "changed_metric",
        "changed_raw_receipt_during_comparison",
    ],
)
def test_delivery_resolution_preserves_original_failure_and_rejects_other_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tamper: str | None
) -> None:
    fixture = _delivery_fixture(tmp_path, monkeypatch)
    comparison = fixture["comparison"]
    if tamper == "extra_raw_difference":
        comparison["differences"].append(
            "metrics/case3/gap00/spatiotemporal.json: canonical JSON differs"
        )
    elif tamper == "missing_report":
        comparison["missing_required_reports"] = ["charts/projection_error_m.png"]
    elif tamper == "failed_inference":
        comparison["inference"]["status"] = "FAIL"
    elif tamper == "incomplete_actual_rerun":
        fixture["clean_job"]["all_stages_actually_executed"] = False
    elif tamper == "changed_metric":
        path = fixture["clean"] / "scoped/evaluation/summary.json"
        value = reviewed_pipeline.read_json(path)
        value["metric"]["ade_m"] = 0.6
        path.write_text(json.dumps(value))
    elif tamper == "changed_raw_receipt_during_comparison":

        def mutate(**kwargs: Any) -> dict[str, Any]:
            path = fixture["arguments"]["reproduction"] / "joint_reproduction_receipt.json"
            path.write_text(path.read_text() + "\n")
            return comparison

        fixture["repro"].compare_scoped_deliveries = mutate
    fixture["save_raw"]()
    if tamper:
        with pytest.raises(ValueError):
            metadata.compare_metadata_delivery(**fixture["arguments"])
    else:
        result = metadata.compare_metadata_delivery(**fixture["arguments"])
        assert result["status"] == "PASS"
        assert (
            result["original_controller_status"]
            == result["original_clean_delivery_status"]
            == "FAIL"
        )
        assert result["original_scoped_status"] == "INCOMPLETE"
        assert result["original_failed_receipts_overwritten_or_relabelled"] is False
        assert result["original_failed_receipts_unchanged_during_comparison"] is True
