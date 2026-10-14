"""Resolve only verified RRD batch bookkeeping and exact demo output paths.

Original failed receipts are inputs and remain unchanged. This adapter does not
export, infer, evaluate, rewrite artifacts, or relax any metric/source equality.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

RAW_DIFFERENCES = [
    "demos/case3/presentation.json: canonical JSON differs",
    "summary.json: canonical JSON differs",
]
COUNT_KEYS = frozenset({"store_count", "chunk_count"})
READER_KEYS = frozenset(
    {
        "recording_count",
        "store_count",
        "chunk_count",
        "required_source_layers_verified",
        "primary_gt_entities_absent",
        "rrd_reader_verified",
    }
)
SEMANTIC_SCRIPT = "scripts/verify_rrd_semantics.py"


def _require(condition: Any, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _load(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("case23_reviewed_rrd_semantics", path)
    _require(spec is not None and spec.loader is not None, "semantic helper unavailable")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _modules(root: Path) -> SimpleNamespace:
    sys.path.insert(0, str(root / "src"))
    from amidst.finalization import reviewed_pipeline, scoped_protocol, scoped_reproduction
    from amidst.finalization.reviewed_reproduction import compare_reviewed_deliveries
    from amidst.obstacle_volume_authority import content_sha256

    return SimpleNamespace(
        p=reviewed_pipeline,
        protocol=scoped_protocol,
        repro=scoped_reproduction,
        office_compare=compare_reviewed_deliveries,
        content_sha256=content_sha256,
    )


def _actual_reader_counts(path: Path) -> dict[str, int]:
    from rerun.chunk import RrdReader

    reader = RrdReader(path)
    counts = {
        "recording_count": len(reader.recordings()),
        "store_count": len(reader.store()),
        "chunk_count": sum(1 for _ in reader.stream()),
    }
    _require(
        counts["recording_count"] == 1 and counts["store_count"] > 0 and counts["chunk_count"] > 0,
        "recording has no actual readable RRD population",
    )
    return counts


def _normalized_reader(value: Any, actual: dict[str, int]) -> dict[str, Any]:
    _require(
        isinstance(value, dict)
        and set(value) == READER_KEYS
        and all(type(value.get(key)) is int for key in actual)
        and all(value.get(key) == count for key, count in actual.items())
        and all(
            value.get(key) is True
            for key in (
                "required_source_layers_verified",
                "primary_gt_entities_absent",
                "rrd_reader_verified",
            )
        ),
        "issued reader metadata differs from the actual same-case recording",
    )
    return {
        key: "<VERIFIED_RRD_BATCH_BOOKKEEPING>" if key in COUNT_KEYS else item
        for key, item in value.items()
    }


def _resolved_json(
    value: dict[str, Any],
    *,
    relative: str,
    evaluation: Path,
    modules: SimpleNamespace,
    counts: dict[str, dict[str, int]],
) -> dict[str, Any]:
    """Apply new exclusions only at exact declared JSON locations."""
    normalized: dict[str, Any] = modules.repro._normalize(value, evaluation)
    if relative in {"demos/case2/presentation.json", "demos/case3/presentation.json"}:
        case = Path(relative).parts[1]
        _require(value.get("case_id") == case, "presentation case identity differs")
        normalized["reader"] = _normalized_reader(value.get("reader"), counts[case])
    elif relative == "summary.json":
        demos = value.get("demos", [])
        _require(
            len(demos) == 2 and [row.get("case_id") for row in demos] == ["case2", "case3"],
            "summary demo population/order differs",
        )
        for index, row in enumerate(demos):
            case = row["case_id"]
            expected_relative = f"demos/{case}/presentation.json"
            _require(
                row.get("presentation") == str(evaluation / expected_relative)
                and (evaluation / expected_relative).is_file(),
                "presentation output path does not bind its exact same-case artifact",
            )
            presentation = modules.p.read_json(evaluation / expected_relative)
            _require(
                row.get("reader") == presentation.get("reader"),
                "summary reader differs from its actual same-case presentation",
            )
            normalized["demos"][index]["presentation"] = "<EVALUATION>/" + expected_relative
            normalized["demos"][index]["reader"] = _normalized_reader(
                row.get("reader"), counts[case]
            )
    return normalized


def compare_metadata_delivery(
    *,
    root: Path,
    release: Path,
    reproduction: Path,
    master_path: Path,
    semantic_receipt_path: Path,
    expected_semantic_script_sha256: str,
    expected_adapter_sha256: str,
) -> dict[str, Any]:
    modules = _modules(root)
    p = modules.p
    _require(
        p.digest(Path(__file__)) == expected_adapter_sha256
        and p.digest(root / SEMANTIC_SCRIPT) == expected_semantic_script_sha256,
        "reviewed metadata/semantic helper bytes differ",
    )
    master = p.read_json(master_path)
    modules.protocol.validate_master_bindings(master, root)
    spec_path = release / "clean_checkout_spec.json"
    spec = modules.repro.CleanCheckoutSpec.model_validate_json(spec_path.read_bytes())
    _require(spec.joint_release is True, "actual full joint clean checkout required")
    modules.protocol.validate_master_bindings(master, spec.root)
    _require(
        p.digest(spec.root / spec.master_relative_path) == p.digest(master_path),
        "clean frozen master bytes differ",
    )
    raw_paths = {
        "controller": reproduction / "joint_reproduction_receipt.json",
        "scoped": reproduction / "verification.json",
        "clean_job": reproduction / "jobs/clean.json",
        "clean_delivery": spec.output / "delivery_comparison.json",
    }
    original_receipt_hashes = {key: p.digest(path) for key, path in raw_paths.items()}
    raw = {key: p.read_json(path) for key, path in raw_paths.items()}
    _require(
        raw["controller"].get("status") == "FAIL"
        and raw["scoped"].get("status") == "INCOMPLETE"
        and raw["controller"].get("scoped") == raw["scoped"]
        and raw["scoped"].get("clean_checkout") == raw["clean_job"]
        and raw["clean_job"] == raw["clean_delivery"]
        and raw["clean_job"].get("status") == "FAIL"
        and raw["controller"].get("frozen_primary_and_source_unchanged") is True,
        "original observed failure/unchanged-source receipt lineage differs",
    )
    _require(
        raw["clean_job"].get("all_stages_actually_executed") is True
        and raw["clean_job"].get("both_child_freezes_verified_before_reference_access") is True
        and raw["clean_job"].get("initial_checkout_clean") is True
        and raw["clean_job"].get("clean_checkout_head") == spec.expected_commit
        and raw["clean_job"].get("joint_population_differences") == [],
        "actual clean full rerun is incomplete or joint population differs",
    )
    current = modules.repro.compare_scoped_deliveries(
        local_dataset=release / "scoped/dataset",
        fresh_dataset=spec.output / "scoped/dataset",
        local_inference=release / "scoped/inference_primary",
        fresh_inference=spec.output / "scoped/inference_primary",
        local_evaluation=release / "scoped/evaluation",
        fresh_evaluation=spec.output / "scoped/evaluation",
    )
    _require(
        current == raw["clean_job"].get("scoped_comparison")
        and current.get("status") == "FAIL"
        and current.get("differences") == RAW_DIFFERENCES
        and current.get("missing_required_reports") == []
        and current.get("dataset_manifest_and_all_artifacts_equal") is True
        and current.get("inference", {}).get("status") == "PASS",
        "raw comparator has changes beyond the exact observed metadata differences",
    )
    office = modules.office_compare(
        local_dataset=release / "office/dataset",
        fresh_dataset=spec.output / "office/dataset",
        local_inference=release / "office/inference_primary",
        fresh_inference=spec.output / "office/inference_primary",
        local_evaluation=release / "office/evaluation",
        fresh_evaluation=spec.output / "office/evaluation",
    )
    _require(
        office.get("status") == "PASS"
        and office == raw["clean_job"].get("original_office_comparison"),
        "original office delivery equality failed or changed",
    )
    # The separately reviewed semantic helper supplies the complete decoded
    # component/timeline proof. Its adapter contract is bound below.
    semantic = _semantic_evidence(
        root,
        release,
        spec.output,
        master_path,
        semantic_receipt_path,
        expected_semantic_script_sha256,
        modules,
    )
    roots = (release / "scoped/evaluation", spec.output / "scoped/evaluation")
    actual_counts = [
        {
            case: _actual_reader_counts(evaluation / f"demos/{case}/scoped.rrd")
            for case in ("case2", "case3")
        }
        for evaluation in roots
    ]
    compared_json = []
    for relative in (
        "demos/case2/presentation.json",
        "demos/case3/presentation.json",
        "summary.json",
    ):
        values = [p.read_json(evaluation / relative) for evaluation in roots]
        normalized = [
            _resolved_json(
                value, relative=relative, evaluation=evaluation, modules=modules, counts=counts
            )
            for value, evaluation, counts in zip(values, roots, actual_counts, strict=True)
        ]
        _require(
            normalized[0] == normalized[1], "non-bookkeeping canonical JSON differs: " + relative
        )
        compared_json.append(
            {
                "relative_path": relative,
                "primary_file_sha256": p.digest(roots[0] / relative),
                "clean_file_sha256": p.digest(roots[1] / relative),
                "resolved_canonical_content_sha256": modules.content_sha256(normalized[0]),
            }
        )
    for name in ("verification.json", "case3_growth.json", "benchmark_table.json"):
        _require(
            modules.repro._normalize(p.read_json(release / name), release)
            == modules.repro._normalize(p.read_json(spec.output / name), spec.output),
            "joint canonical population differs: " + name,
        )
    _require(
        not modules.repro._table_consistency(release)
        and not modules.repro._table_consistency(spec.output),
        "joint table population differs from its JSON",
    )
    _require(
        original_receipt_hashes == {key: p.digest(path) for key, path in raw_paths.items()},
        "original failed receipts changed during the read-only comparison",
    )
    return {
        "schema_version": "phase1-case23-delivery-metadata-resolution-v1",
        "status": "PASS",
        "resolution_scope": "EXACT_OUTPUT_PATH_AND_VERIFIED_RRD_BATCH_BOOKKEEPING_ONLY",
        "adapter_file_sha256": expected_adapter_sha256,
        "semantic_helper_file_sha256": expected_semantic_script_sha256,
        "semantic_receipt_file_sha256": p.digest(semantic_receipt_path),
        "semantic_comparison": semantic,
        "master_file_sha256": p.digest(master_path),
        "clean_checkout_spec_file_sha256": p.digest(spec_path),
        "original_receipt_file_sha256": original_receipt_hashes,
        "original_failed_receipts_unchanged_during_comparison": True,
        "original_controller_status": "FAIL",
        "original_scoped_status": "INCOMPLETE",
        "original_clean_delivery_status": "FAIL",
        "original_scoped_comparison_status": "FAIL",
        "original_failure_differences": RAW_DIFFERENCES,
        "original_failed_receipts_overwritten_or_relabelled": False,
        "resolved_json": compared_json,
        "actual_reader_batch_counts": {"primary": actual_counts[0], "clean": actual_counts[1]},
        "new_nondeterministic_exclusions": [
            "demos/case{2,3}/presentation.json: reader.store_count/chunk_count only",
            "summary.json: demos[case2/case3].reader.store_count/chunk_count only",
            "summary.json: demos[case2/case3].presentation exact verified output path only",
        ],
        "all_other_frozen_comparator_rules_preserved": True,
        "source_metrics_thresholds_or_candidate_order_changed": False,
        "native_export_inference_or_evaluation_rerun": False,
        "formal_acceptance_or_freeze_granted": False,
    }


def _semantic_evidence(
    root: Path,
    release: Path,
    clean: Path,
    master_path: Path,
    receipt_path: Path,
    expected_script_sha256: str,
    modules: SimpleNamespace,
) -> dict[str, Any]:
    _require(
        modules.p.digest(root / SEMANTIC_SCRIPT) == expected_script_sha256,
        "reviewed full RRD semantic helper bytes differ",
    )
    issued = modules.p.read_json(receipt_path)
    helper = _load(root / SEMANTIC_SCRIPT)
    actual = helper.verify_joint_rrd_semantics(release, clean, master_path)
    actual = json.loads(json.dumps(actual, sort_keys=True, allow_nan=False))
    _require(isinstance(actual, dict), "full semantic proof is not a structured receipt")
    _require(
        issued == actual
        and actual.get("schema_version") == "phase1-full-data-recording-semantic-comparison-v1"
        and actual.get("status") == "PASS"
        and actual.get("full_recording_component_timeline_coverage") is True
        and actual.get("all_case_ids") == ["case1", "case2", "case3"]
        and actual.get("blueprint_semantics_claimed") is False,
        "full decoded recording semantic proof failed, changed, or omits the case population",
    )
    result: dict[str, Any] = actual
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "release", "reproduction", "master", "semantic-receipt", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-semantic-script-sha256", required=True)
    parser.add_argument("--expected-adapter-sha256", required=True)
    args = parser.parse_args()
    _require(not args.output.exists(), "fresh metadata resolution receipt required")
    result = compare_metadata_delivery(
        root=args.root,
        release=args.release,
        reproduction=args.reproduction,
        master_path=args.master,
        semantic_receipt_path=args.semantic_receipt,
        expected_semantic_script_sha256=args.expected_semantic_script_sha256,
        expected_adapter_sha256=args.expected_adapter_sha256,
    )
    _modules(args.root).p.write_json(args.output, result)
    print(result["status"])


if __name__ == "__main__":
    main()
