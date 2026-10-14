"""Close workflow gates from immutable receipts, without inference or GT evaluation.

Research targets are classified separately. A valid negative benchmark result
can complete workflow gates; it cannot become an overall metric PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Callable
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote

MODE = "PARALLEL_FROZEN_PUBLIC_APIS_NOT_ORIGINAL_SEQUENTIAL_RUNNER"
RUNS = {"repeat", "fresh_process", "reordered", "gt_poison"}
WORKERS = {"repeat-order", "fresh", "poison", "clean", "office"}
CONTROLLER = "scripts/reproduce_case23_parallel.py"
CONTROLLER_TEST = "tests/unit/test_case23_parallel_controller.py"
CLOSEOUT_TEST = "tests/unit/test_case23_acceptance_closeout.py"
METADATA_SCRIPT = "scripts/compare_case23_delivery_metadata.py"
METADATA_TEST = "tests/unit/test_case23_delivery_metadata.py"
SEMANTIC_SCRIPT = "scripts/verify_rrd_semantics.py"
SEMANTIC_TEST = "tests/unit/test_rrd_semantics.py"
SCOPE = "SOURCE_BOUND_OFFICE_AND_EXACT_SIX_CELL_UNION_ONLY"


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed audit helper unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
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


def _require(condition: Any, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _json_types(value: Any) -> Any:
    """Compare issued JSON with live helper values using the same JSON types."""
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


def _junit_identity(node: str) -> tuple[str, str]:
    path, *parts = node.split("::")
    _require(path.endswith(".py") and bool(parts), "invalid declared test node ID")
    module = path[:-3].replace("/", ".")
    return (".".join([module, *parts[:-1]]), parts[-1])


def _validation(
    path: Path,
    modules: SimpleNamespace,
    *,
    root: Path,
    master_sha: str,
    code_commit: str,
    source_state: dict[str, Any],
    count: int,
    population: str | None = None,
    script: str | None = None,
    test: str | None = None,
) -> dict[str, Any]:
    p = modules.p
    receipt = p.read_json(path)
    expected_schema = (
        "phase1-full-repository-validation-v1"
        if population is None
        else "phase1-supplemental-validation-v1"
    )
    _require(receipt.get("schema_version") == expected_schema, "validation receipt schema differs")
    _require(
        receipt.get("status") == "PASS" and receipt.get("pytest_exit_code") == 0,
        "actual validation did not pass",
    )
    _require(
        receipt.get("expected_population_count") == count
        and receipt.get("full_counts")
        == {
            "tests": count,
            "passed": count,
            "failures": 0,
            "errors": 0,
            "skipped": 0,
        },
        "validation population/failure/skip counts differ",
    )
    _require(
        receipt.get("master_file_sha256") == master_sha
        and receipt.get("code_commit_sha") == code_commit
        and receipt.get("master_unchanged") is True
        and receipt.get("producer_files_unchanged") is True,
        "validation master/code/producer lineage differs",
    )
    _require(
        receipt.get("source_unchanged") is True
        and receipt.get("source_before") == receipt.get("source_after") == source_state,
        "validation immutable source lineage differs",
    )
    nodes = receipt.get("all_node_ids", [])
    _require(
        isinstance(nodes, list)
        and len(nodes) == len(set(nodes)) == count
        and receipt.get("all_node_ids_content_sha256") == modules.content_sha256(nodes),
        "validation node ID population/hash differs",
    )
    _require(
        receipt.get("failed_node_ids") == [] and receipt.get("skipped_node_ids") == [],
        "validation retains failed or skipped tests",
    )
    for path_key, sha_key in (
        ("junit_path", "junit_file_sha256"),
        ("pytest_log_path", "pytest_log_file_sha256"),
    ):
        actual = p.safe_artifact(path.parent, receipt[path_key])
        _require(p.digest(actual) == receipt.get(sha_key), "validation artifact hash differs")
    xml = ET.parse(p.safe_artifact(path.parent, receipt["junit_path"])).getroot()
    cases = list(xml.iter("testcase"))
    identities = [(case.attrib.get("classname"), case.attrib.get("name")) for case in cases]
    _require(
        len(cases) == count
        and set(identities) == {_junit_identity(node) for node in nodes}
        and all(
            case.find(tag) is None for case in cases for tag in ("failure", "error", "skipped")
        ),
        "actual JUnit results differ from declared passed nodes",
    )
    expected_checks = {"ruff", "mypy", "diff"} if population is None else {"ruff", "mypy"}
    _require(
        set(receipt.get("checks", {})) == expected_checks, "required validation checks missing"
    )
    for check in receipt["checks"].values():
        _require(
            check.get("status") == "PASS"
            and check.get("exit_code") == 0
            and p.digest(p.safe_artifact(path.parent, check["log_path"]))
            == check.get("log_file_sha256"),
            "validation check/log failed or changed",
        )
    if population is None:
        _require(
            "--require-physical-evidence" in receipt.get("pytest_command", [])
            and receipt.get("expected_original_test_count") == 1978
            and receipt.get("expected_new_test_count") == 204,
            "full repository physical-evidence population differs",
        )
    else:
        _require(
            receipt.get("validation_population") == population
            and receipt.get("validated_files_unchanged") is True,
            "supplemental validation population/bytes differ",
        )
        expected_files = {script: p.digest(root / str(script)), test: p.digest(root / str(test))}
        _require(
            receipt.get("validated_file_hashes") == expected_files
            and all(node.startswith(str(test) + "::") for node in nodes),
            "supplemental script/tests are not the actual validated bytes",
        )
        command = receipt.get("pytest_command", [])
        pytest_args = command[command.index("pytest") + 1 :] if "pytest" in command else []
        _require(
            str(test) in pytest_args
            and not any(flag in pytest_args for flag in ("-k", "-m", "--ignore")),
            "supplemental test selection was narrowed",
        )
    return {
        "status": "PASS",
        "receipt_file_sha256": p.digest(path),
        "passed_test_count": count,
        "code_commit_sha": code_commit,
        "all_node_ids_content_sha256": receipt["all_node_ids_content_sha256"],
    }


def _commit_producers(root: Path, master: dict[str, Any], code_commit: str) -> dict[str, Any]:
    _require(re.fullmatch(r"[0-9a-f]{40}", code_commit), "full code commit required")
    for relative, expected in master["producer_hashes"].items():
        process = subprocess.run(
            ["git", "show", code_commit + ":" + relative],
            cwd=root,
            capture_output=True,
            check=False,
        )
        _require(
            process.returncode == 0 and hashlib.sha256(process.stdout).hexdigest() == expected,
            "validated code commit differs from frozen producer: " + relative,
        )
    return {
        "status": "PASS",
        "code_commit_sha": code_commit,
        "producer_file_count": len(master["producer_hashes"]),
    }


def _formal_cases(release: Path, master_sha: str, modules: SimpleNamespace) -> dict[str, Any]:
    p = modules.p
    receipt = p.read_json(release / "verification.json")
    _require(
        receipt.get("schema_version") == "phase1-joint-formal-verification-v1"
        and receipt.get("formal_case_execution_complete") is True
        and receipt.get("blockers") == [],
        "joint formal execution gates remain incomplete",
    )
    _require(
        receipt.get("master_file_sha256") == master_sha
        and receipt.get("joint_inference_freeze_file_sha256")
        == p.digest(release / "joint_inference_freeze.json"),
        "joint execution lineage differs",
    )
    cases = receipt.get("cases", [])
    _require(
        len(cases) == 3
        and {c["case_id"] for c in cases} == {"case1", "case2", "case3"}
        and all(c.get("status") == "PASS" and c.get("blockers") == [] for c in cases),
        "Case 1/2/3 execution population is incomplete or blocked",
    )
    _require(
        receipt.get("formal_scope") == SCOPE
        and receipt.get("case4_status") == "DEFERRED"
        and receipt.get("school_surface_authority") == "NOT_CERTIFIED"
        and receipt.get("phase2_modified") is False
        and receipt.get("historical_child_statuses_rewritten") is False
        and receipt.get("cross_case_overall_coverage") is None
        and receipt.get("cross_case_weighting_status")
        == "UNAPPROVED_NO_OVERALL_TARGET_PASS_CLAIMED"
        and receipt.get("same_camera_scoped_transition_rate_status")
        == "N/A_ZERO_DECLARED_TRANSITIONS_WITH_INDEPENDENT_HOLD_VALIDATION",
        "required scope/negative/N/A boundaries changed",
    )
    scoped = p.read_json(release / "scoped/evaluation/summary.json")
    _require(
        all(
            c.get("status") == "PASS"
            and c.get("blockers") == []
            and c.get("actual_handoff_count") == 0
            and c.get("impossible_transition_rate") is None
            and c.get("transition_status") == "N/A_NO_DECLARED_CAMERA_OR_FLOOR_TRANSITIONS"
            for c in scoped["cases"]
        ),
        "scoped stress execution or zero-handoff population differs",
    )
    office = p.read_json(release / "office/evaluation/verification.json")
    _require(
        office.get("overall_physical_authority") == "PARTIAL_APPROVED",
        "global physical authority was upgraded",
    )
    return {
        "status": "PASS",
        "receipt_file_sha256": p.digest(release / "verification.json"),
        "formal_scope": SCOPE,
        "cases": cases,
        "case4_status": "DEFERRED",
    }


def _source_readiness(
    args: argparse.Namespace, modules: SimpleNamespace, master: dict[str, Any]
) -> dict[str, Any]:
    p = modules.p
    path = args.release / "source_readiness_audit.json"
    receipt = p.read_json(path)
    _require(
        receipt.get("schema_version") == "phase1-independent-gt-free-source-readiness-audit-v1"
        and receipt.get("status") == "PRE_GT_CASE2_CASE3_SOURCE_READINESS_PASS"
        and receipt.get("master_file_sha256") == p.digest(args.master)
        and receipt.get("authority") == master["inference_config"]["authority"]
        and receipt.get("ground_truth_read") is False
        and receipt.get("evaluation_partition_read") is False
        and receipt.get("simulation_partition_read") is False
        and receipt.get("source_recipes_deserialized") is False
        and receipt.get("oracle_routes_used_as_predictions") is False
        and receipt.get("producer_master_config_or_source_modified") is False
        and receipt.get("raw_graph_termination_population_is_separate_from_declared_class_grammar")
        is True,
        "independent source readiness/production separation receipt differs",
    )
    for field, relative in (
        ("joint_inference_freeze_file_sha256", "joint_inference_freeze.json"),
        ("scoped_dataset_manifest_file_sha256", "scoped/dataset/manifest.json"),
        ("scoped_inference_freeze_file_sha256", "scoped/inference_primary/inference_freeze.json"),
        ("scoped_inference_summary_file_sha256", "scoped/inference_primary/summary.json"),
    ):
        _require(
            receipt.get(field) == p.digest(args.release / relative),
            "source readiness frozen artifact differs",
        )
    summary = p.read_json(args.release / "scoped/inference_primary/summary.json")
    expected = {
        (case["case_id"], gap["gap_directory"]) for case in summary["cases"] for gap in case["gaps"]
    }
    records = receipt.get("C_gap_records", [])
    _require(
        len(records) == receipt.get("full_C_gap_count") == len(expected)
        and {(r["case_id"], r["gap_directory"]) for r in records} == expected
        and all(
            r.get("pre_gt_source_readiness_status") == "PASS"
            and r.get("class_generation_complete") is True
            and r.get("inventory_complete") is True
            and r.get("source_denominator_complete") is True
            for r in records
        ),
        "independent source/class denominator population is incomplete",
    )
    return {
        "status": "PASS",
        "receipt_file_sha256": p.digest(path),
        "full_C_gap_count": len(records),
        "raw_full_visibility_graph_termination_counts": receipt[
            "raw_full_visibility_graph_termination_counts"
        ],
        "raw_graph_failure_receipts_preserved_separately": True,
    }


def _poison_coverage(
    args: argparse.Namespace,
    modules: SimpleNamespace,
    poison: dict[str, Any],
    scoped: dict[str, Any],
) -> dict[str, Any]:
    p = modules.p
    manifest = p.read_json(args.release / "scoped/dataset/manifest.json")
    cases = {row["case_id"] for row in manifest["cases"]}
    suffixes = {
        "ground_truth": ("evaluation", "ground_truth.json"),
        "recipe": ("simulation", "recipe.json"),
        "reference_annotation": ("evaluation", "reference_movement_annotations.json"),
    }
    changed = poison.get("changed_partitions", {})
    _require(
        set(changed) == set(suffixes), "poison receipt does not cover all three exact partitions"
    )
    for key, (partition, filename) in suffixes.items():
        expected = {f"{partition}/{case}/{filename}" for case in cases}
        actual = changed[key]
        _require(
            expected <= set(manifest["artifacts"])
            and isinstance(actual, list)
            and len(actual) == len(set(actual)) == len(expected)
            and set(actual) == expected,
            "poison artifact population differs: " + key,
        )
    primary = args.release / "scoped/inference_primary"
    summary = p.read_json(primary / "summary.json")
    expected_queries = {
        (case["case_id"], gap["gap_directory"]) for case in summary["cases"] for gap in case["gaps"]
    }
    paths = sorted(primary.glob("case*/gap*/spatiotemporal/run.json"))
    queries = [
        (
            path.relative_to(primary).parts[0],
            path.parent.parent.name,
            bool(p.read_json(path)["event"]["trajectories"]),
        )
        for path in paths
    ]
    _require(
        len(queries) == len(expected_queries)
        and {(case, gap) for case, gap, _ in queries} == expected_queries,
        "primary C query census differs from frozen summary",
    )
    records = poison.get("records", [])
    _require(
        len(records) == len(queries), "poison sensitivity omits or duplicates frozen C queries"
    )
    sensitive_cases, unavailable = set(), []
    for (case, gap, timed), row in zip(queries, records, strict=True):
        _require(row.get("case_id") == case, "poison sensitivity belongs to a foreign case/query")
        if timed:
            _require(
                row.get("gap_directory") == gap
                and row.get("status") == "PASS"
                and row.get("evaluation_changed") is True
                and row.get("normal") != row.get("poisoned"),
                "timed C query poison sensitivity is missing, duplicated, or unchanged",
            )
            sensitive_cases.add(case)
        else:
            _require(
                row.get("status") == "N/A_NO_TIMED_CANDIDATES"
                and row.get("gap_directory") in {None, gap},
                "poison N/A is not justified by the same frozen zero-timed query",
            )
            unavailable.append(row)
    _require(
        bool(sensitive_cases)
        and sorted(sensitive_cases) == scoped.get("gt_sensitive_case_ids")
        and unavailable == scoped.get("gt_metric_sensitivity_unavailable")
        and poison.get("inference_artifacts_byte_identical") is True
        and poison.get("manifest_preserved") is True,
        "poison completeness/identity summary differs from actual query census",
    )
    return {
        "status": "PASS",
        "frozen_primary_C_query_count": len(queries),
        "measured_query_count": len(records) - len(unavailable),
        "exact_three_partition_case_population_verified": True,
    }


def _termination_coverage(
    args: argparse.Namespace, modules: SimpleNamespace, declared: list[dict[str, Any]]
) -> dict[str, Any]:
    expected: list[dict[str, Any]] = []
    for name in ("repeat", "fresh_process", "reordered", "gt_poison"):
        summary = modules.p.read_json(args.reproduction / name / "summary.json")
        expected.extend(
            variant
            for case in summary["cases"]
            for gap in case["gaps"]
            for variant in gap["variants"]
            if variant["status"] == "EXECUTED"
        )
    _require(
        bool(expected) and _json_types(expected) == declared,
        "termination ledger omits, duplicates, or changes actual executed variant populations",
    )
    _require(
        all(
            item.get("termination_reason") in {"COMPLETE", "NO_FEASIBLE_PATH", "MAX_PATHS_REACHED"}
            and item.get("generation_complete") is True
            and item.get("inventory_complete") is True
            for item in expected
        ),
        "actual search/oracle generation is incomplete",
    )
    return {
        "status": "PASS",
        "executed_variant_run_count": len(expected),
        "four_runs_verified": True,
    }


def _job_bodies(
    args: argparse.Namespace, modules: SimpleNamespace, receipt: dict[str, Any]
) -> dict[str, Any]:
    p = modules.p
    bodies = {name: p.read_json(args.reproduction / "jobs" / (name + ".json")) for name in WORKERS}
    repeat = bodies["repeat-order"]
    _require(
        repeat.get("status") == "EXECUTED"
        and repeat.get("same_process_repeat_order") is True
        and [row.get("operation") for row in repeat.get("operations", [])]
        == ["repeat", "reordered"],
        "same-worker repeated/order execution receipt differs",
    )
    for worker, name in (("fresh", "fresh_process"), ("poison", "gt_poison")):
        body = bodies[worker]
        dataset = (
            args.release / "scoped/dataset"
            if worker == "fresh"
            else args.reproduction / "poison_dataset"
        )
        expected = [
            str(args.root / "scripts/run_phase1_scoped_case23.py"),
            "infer",
            "--dataset",
            str(dataset),
            "--config",
            str(args.master),
            "--output",
            str(args.reproduction / name),
        ]
        _require(
            body.get("status") == "EXECUTED"
            and body.get("fresh_interpreter") is True
            and body.get("command", {}).get("returncode") == 0
            and body["command"].get("arguments", [])[1:] == expected,
            "fresh-interpreter command/input/output binding differs: " + worker,
        )
    _require(
        bodies["clean"] == receipt["scoped"]["clean_checkout"]
        and bodies["office"] == receipt["office"],
        "actual clean/office job completion body differs",
    )
    return {"status": "PASS", "all_five_actual_job_bodies_verified": True}


def _reproduction(
    args: argparse.Namespace,
    modules: SimpleNamespace,
    controller: Any,
    lineage: dict[str, Any],
    delivery_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    p = modules.p
    receipt = p.read_json(args.reproduction / "joint_reproduction_receipt.json")
    resolved_metadata_failure = (
        delivery_resolution is not None
        and delivery_resolution.get("status") == "PASS"
        and delivery_resolution["comparison"].get("original_controller_status") == "FAIL"
        and delivery_resolution["comparison"].get("original_scoped_status") == "INCOMPLETE"
        and delivery_resolution["comparison"].get("schema_version")
        == "phase1-case23-delivery-metadata-resolution-v1"
        and delivery_resolution["comparison"]
        .get("original_receipt_file_sha256", {})
        .get("controller")
        == p.digest(args.reproduction / "joint_reproduction_receipt.json")
        and delivery_resolution["comparison"].get("original_receipt_file_sha256", {}).get("scoped")
        == p.digest(args.reproduction / "verification.json")
        and delivery_resolution["comparison"].get(
            "original_failed_receipts_overwritten_or_relabelled"
        )
        is False
        and receipt.get("status") == "FAIL"
    )
    _require(
        receipt.get("schema_version") == "phase1-joint-parallel-reproduction-receipt-v1"
        and (receipt.get("status") == "PASS" or resolved_metadata_failure)
        and receipt.get("execution_method") == MODE
        and receipt.get("original_sequential_runner_executed") is False
        and receipt.get("controller_file_sha256") == args.expected_controller_sha256
        and receipt.get("master_file_sha256") == p.digest(args.master),
        "actual reviewed parallel reproduction did not pass",
    )
    _require(
        receipt.get("max_active_workers") == 4
        and receipt.get("interpreter_start_method") == "SUBPROCESS_FRESH_INTERPRETERS_NO_FORK"
        and receipt.get("same_worker_repeat_order_provider_reuse_only") is True
        and receipt.get("wallclock_budgets_and_frozen_public_checks_preserved") is True
        and receipt.get("frozen_primary_and_source_unchanged") is True
        and receipt.get("frozen_lineage_before")
        == receipt.get("frozen_lineage_after")
        == _json_types(lineage),
        "reproduction concurrency/budget/frozen lineage differs",
    )
    jobs = receipt.get("jobs", {})
    _require(
        set(jobs) == WORKERS and all(j.get("returncode") == 0 for j in jobs.values()),
        "a required actual reproduction worker is absent or failed",
    )
    for name, job in jobs.items():
        _require(
            job.get("worker") == name and p.digest(Path(job["log"])) == job.get("log_sha256"),
            "actual worker log changed or identity differs",
        )
        _require(
            Path(job["log"]).resolve() == (args.reproduction / "logs" / (name + ".log")).resolve(),
            "worker log is not the actual isolated job output",
        )
        _require(
            (args.reproduction / "jobs" / (name + ".json")).is_file(),
            "actual worker completion receipt missing",
        )
    scoped = receipt["scoped"]
    bodies = _job_bodies(args, modules, receipt)
    _require(
        p.read_json(args.reproduction / "verification.json") == scoped
        and (
            scoped.get("status") == "PASS"
            or (resolved_metadata_failure and scoped.get("status") == "INCOMPLETE")
        )
        and set(scoped.get("comparisons", {})) == RUNS
        and scoped.get("gt_recipe_reference_annotation_poison_status") == "PASS"
        and scoped.get("termination_status") == "PASS",
        "scoped repeat/order/poison/termination failed",
    )
    for name in RUNS:
        comparison = p.compare_frozen_runs(
            args.release / "scoped/inference_primary", args.reproduction / name
        )
        _require(
            _json_types(comparison) == scoped["comparisons"][name]
            and comparison.get("status") == "PASS",
            "actual frozen reproduced inference differs: " + name,
        )
    termination = _termination_coverage(args, modules, scoped.get("termination_ledger", []))
    poison = p.read_json(args.reproduction / "poison_sensitivity.json")
    poison_population = _poison_coverage(args, modules, poison, scoped)
    office_gates = controller._office_gates(args, modules)
    _require(
        office_gates.get("status") == "PASS"
        and _json_types(office_gates) == receipt.get("original_office_field_gates")
        and receipt["office"].get("reproduction_status") == "PASS"
        and p.read_json(args.reproduction / "jobs/office.json") == receipt["office"],
        "original office extra reproduction fields did not pass",
    )
    return {
        "status": "PASS",
        "receipt_file_sha256": p.digest(args.reproduction / "joint_reproduction_receipt.json"),
        "execution_method": MODE,
        "original_office_extra_fields_verified": True,
        "complete_termination_population": termination,
        "complete_poison_population": poison_population,
        "actual_job_bodies": bodies,
        "original_controller_status": receipt["status"],
        "original_scoped_status": scoped["status"],
        "original_failed_receipts_overwritten_or_relabelled": False,
        "verified_metadata_resolution_applied": resolved_metadata_failure,
    }


def _metadata_resolution(args: argparse.Namespace, modules: SimpleNamespace) -> dict[str, Any]:
    p = modules.p
    _require(
        p.digest(args.root / METADATA_SCRIPT) == args.expected_metadata_adapter_sha256
        and p.digest(args.root / SEMANTIC_SCRIPT) == args.expected_semantic_script_sha256,
        "reviewed delivery metadata/semantic helper bytes differ",
    )
    adapter = _load(args.root / METADATA_SCRIPT, "case23_acceptance_metadata_resolution")
    actual = adapter.compare_metadata_delivery(
        root=args.root,
        release=args.release,
        reproduction=args.reproduction,
        master_path=args.master,
        semantic_receipt_path=args.rrd_semantic_comparison,
        expected_semantic_script_sha256=args.expected_semantic_script_sha256,
        expected_adapter_sha256=args.expected_metadata_adapter_sha256,
    )
    issued = p.read_json(args.delivery_metadata_comparison)
    _require(
        _json_types(actual) == issued
        and issued.get("status") == "PASS"
        and issued.get("original_failed_receipts_overwritten_or_relabelled") is False,
        "actual metadata resolution differs from independently reviewed issued proof",
    )
    return {
        "status": "PASS",
        "receipt_file_sha256": p.digest(args.delivery_metadata_comparison),
        "comparison": actual,
    }


def _clean_delivery(
    args: argparse.Namespace,
    modules: SimpleNamespace,
    delivery_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    p = modules.p
    spec = modules.repro.CleanCheckoutSpec.model_validate_json(
        args.clean_checkout_spec.read_bytes()
    )
    declared = p.read_json(args.reproduction / "jobs/clean.json")
    resolved_metadata_failure = (
        delivery_resolution is not None
        and delivery_resolution.get("status") == "PASS"
        and delivery_resolution["comparison"].get("original_clean_delivery_status") == "FAIL"
        and delivery_resolution["comparison"].get("schema_version")
        == "phase1-case23-delivery-metadata-resolution-v1"
        and delivery_resolution["comparison"]
        .get("original_receipt_file_sha256", {})
        .get("clean_job")
        == p.digest(args.reproduction / "jobs/clean.json")
        and delivery_resolution["comparison"]
        .get("original_receipt_file_sha256", {})
        .get("clean_delivery")
        == p.digest(spec.output / "delivery_comparison.json")
        and delivery_resolution["comparison"].get(
            "original_failed_receipts_overwritten_or_relabelled"
        )
        is False
        and declared.get("status") == "FAIL"
    )
    _require(
        declared == p.read_json(spec.output / "delivery_comparison.json")
        and (declared.get("status") == "PASS" or resolved_metadata_failure)
        and declared.get("joint_release") is True
        and declared.get("clean_checkout_head") == spec.expected_commit == args.expected_code_commit
        and declared.get("initial_checkout_clean") is True
        and declared.get("all_stages_actually_executed") is True
        and declared.get("both_child_freezes_verified_before_reference_access") is True,
        "complete same-code clean joint delivery was not actually verified",
    )
    master = p.read_json(args.master)
    modules.protocol.validate_master_bindings(master, spec.root)
    _require(
        p.digest(spec.root / spec.master_relative_path) == p.digest(args.master),
        "clean checkout master bytes differ",
    )
    for release in (args.release, spec.output):
        modules.protocol.require_joint_inference_boundary(
            release / "joint_inference_freeze.json",
            args.master,
            release / "office/inference_primary",
        )
        source = p.read_json(release / "primary_run_receipt.json")
        _require(
            source.get("source_unchanged") is True
            and source["source_before"] == source["source_after"]
            and source.get("master_file_sha256") == p.digest(args.master),
            "primary/clean immutable source preservation differs",
        )
    for child, compare in (
        ("scoped", modules.repro.compare_scoped_deliveries),
        ("office", modules.office_compare),
    ):
        current = compare(
            local_dataset=args.release / child / "dataset",
            fresh_dataset=spec.output / child / "dataset",
            local_inference=args.release / child / "inference_primary",
            fresh_inference=spec.output / child / "inference_primary",
            local_evaluation=args.release / child / "evaluation",
            fresh_evaluation=spec.output / child / "evaluation",
        )
        _require(
            _json_types(current)
            == declared["scoped_comparison" if child == "scoped" else "original_office_comparison"]
            and (
                current["status"] == "PASS"
                or (child == "scoped" and resolved_metadata_failure and current["status"] == "FAIL")
            ),
            "current complete delivery differs: " + child,
        )
    for name in ("verification.json", "case3_growth.json", "benchmark_table.json"):
        _require(
            modules.repro._normalize(p.read_json(args.release / name), args.release)
            == modules.repro._normalize(p.read_json(spec.output / name), spec.output),
            "current joint population differs: " + name,
        )
    _require(
        not declared.get("joint_population_differences")
        and not modules.repro._table_consistency(args.release)
        and not modules.repro._table_consistency(spec.output),
        "joint table population consistency failed",
    )
    return {
        "status": "PASS",
        "receipt_file_sha256": p.digest(spec.output / "delivery_comparison.json"),
        "clean_checkout_commit": spec.expected_commit,
        "full_delivery_compared_again_without_recalculation": True,
        "original_clean_delivery_status": declared["status"],
        "original_scoped_comparison_status": declared["scoped_comparison"]["status"],
        "original_failed_receipts_overwritten_or_relabelled": False,
        "verified_metadata_resolution_applied": resolved_metadata_failure,
    }


def _reader(
    path: Path, required: tuple[str, ...], expected_prediction_entities: tuple[str, ...] = ()
) -> dict[str, Any]:
    from rerun.chunk import RrdReader

    reader = RrdReader(path)
    paths, chunks = set(), 0
    for chunk in reader.stream():
        paths.add(chunk.entity_path.lstrip("/").replace("\\", ""))
        chunks += 1
    _require(
        len(reader.recordings()) == 1
        and len(reader.store()) > 0
        and chunks > 0
        and all(any(value.startswith(prefix) for value in paths) for prefix in required)
        and set(expected_prediction_entities) <= paths
        and not any("ground_truth" in value.lower() for value in paths),
        "actual demo reader rejected missing source layers or primary GT",
    )
    return {
        "recording_count": 1,
        "store_count": len(reader.store()),
        "chunk_count": chunks,
        "required_source_layers_verified": True,
        "primary_gt_entities_absent": True,
        "rrd_reader_verified": True,
    }


def _prediction_entities(events: list[dict[str, Any]]) -> tuple[str, ...]:
    paths: list[str] = []
    for event in events:
        prefix = "world/events/" + quote(event["event_id"], safe="")
        paths.extend(
            prefix + "/candidates/" + quote(candidate["candidate_id"], safe="")
            for candidate in event["candidates"]
        )
        for hypothesis in event["trajectories"]:
            base = prefix + "/hypotheses/" + quote(hypothesis["hypothesis_id"], safe="")
            paths.extend((base + "/path", base + "/marker"))
    _require(bool(paths), "formal demo has no frozen prediction entities")
    return tuple(paths)


def _scoped_demo_events(
    args: argparse.Namespace, modules: SimpleNamespace, presentation: dict[str, Any], case_id: str
) -> list[dict[str, Any]]:
    p = modules.p
    primary = args.release / "scoped/inference_primary"
    summary = p.read_json(primary / "summary.json")
    cases = [case for case in summary["cases"] if case["case_id"] == case_id]
    _require(len(cases) == 1, "scoped demo has no unique same-case frozen inference population")
    expected = {gap["gap_id"]: gap for gap in cases[0]["gaps"]}
    records = presentation.get("gaps", [])
    _require(
        len(records) == len(expected) and {row["gap_id"] for row in records} == set(expected),
        "scoped demo substitutes, duplicates, or omits same-case frozen gaps",
    )
    events = []
    for record in records:
        directory = primary / case_id / expected[record["gap_id"]]["gap_directory"]
        run = p.read_json(directory / "spatiotemporal/run.json")
        production = p.read_json(directory / "spatiotemporal/production.json")
        aggregation = p.read_json(primary / case_id / "aggregation.json")
        context = p.read_json(primary / case_id / "scoped_context.json")
        _require(
            record.get("run") == run
            and record.get("event") == run["event"]
            and record.get("production") == production
            and record.get("run_content_sha256") == modules.content_sha256(run)
            and record.get("production_content_sha256") == modules.content_sha256(production)
            and record.get("aggregation_content_sha256") == modules.content_sha256(aggregation)
            and record.get("context_content_sha256") == modules.content_sha256(context)
            and record.get("navigation_content_sha256") == run["navigation_content_sha256"],
            "scoped demo event/run/production/source context differs from frozen same-case query",
        )
        events.append(run["event"])
    return events


def _demo(
    args: argparse.Namespace, modules: SimpleNamespace, case_id: str, master: dict[str, Any]
) -> dict[str, Any]:
    p = modules.p
    office = case_id == "case1"
    child, filename = ("office", "reviewed.rrd") if office else ("scoped", "scoped.rrd")
    folder = args.release / child / "evaluation/demos" / case_id
    presentation = p.read_json(folder / "presentation.json")
    _require(
        presentation.get("rrd_reader_verified") is True
        and presentation.get("ground_truth_logged_to_primary_recording") is False
        and presentation.get("gt_debug_default_visible") is False
        and presentation.get("coordinate_units") == "METRES",
        "demo provenance/reader receipt differs",
    )
    required = (
        (
            "debug/reviewed_authority",
            "world/reviewed_certificate/footpoint_domain",
            "world/reviewed_certificate/body_guard",
            "world/source_observation_cameras/",
            "world/projected/",
            "cameras/",
            "world/events/",
        )
        if office
        else (
            "debug/scoped_authority",
            "world/scoped_authority/union/",
            "world/scoped_authority/body_guards/",
            "world/source_observation_cameras/",
            "world/source_projected/",
            "cameras/",
            "world/events/",
        )
    )
    hashes = {
        name: p.digest(folder / name) for name in (filename, "preview.png", "presentation.json")
    }
    _require(all((folder / name).stat().st_size > 0 for name in hashes), "demo artifact is empty")
    if office:
        run = p.read_json(args.release / "office/inference_primary/case1/spatiotemporal.json")
        _require(
            presentation["event"] == run["event"]
            and presentation["authority"]["source_sha256"] == master["source_sha256"]
            and presentation["authority"].get("whole_component_approved") is False,
            "Case1 demo differs from its frozen event/source authority",
        )
        events = [run["event"]]
    else:
        _require(
            presentation.get("schema_version") == "phase1-scoped-source-presentation-v1"
            and presentation.get("case_id") == case_id
            and presentation.get("source_sha256") == master["source_sha256"]
            and presentation.get("authority") == master["inference_config"]["authority"]
            and presentation.get("ground_truth_read") is False
            and presentation.get("requested_k_is_not_padded") is True
            and presentation.get("full_raw_samples_and_recoveries_retained") is True
            and presentation["geometry"].get("outer_rectangle_used_as_domain") is False
            and presentation["geometry"].get("hole_count", 0) > 0,
            "scoped demo source/hole/K/recovery lineage differs",
        )
        for key, name in (("recording", filename), ("preview", "preview.png")):
            _require(
                presentation["artifacts"][key] == {"filename": name, "sha256": hashes[name]},
                "scoped demo recorded artifact SHA differs",
            )
        events = _scoped_demo_events(args, modules, presentation, case_id)
    reader = _reader(folder / filename, required, _prediction_entities(events))
    if not office:
        _require(
            presentation["reader"] == _json_types(reader),
            "actual scoped reader result differs from issued receipt",
        )
    _require(
        bool(presentation.get("source_observation_cameras")), "demo has no actual source cameras"
    )
    return {
        "status": "PASS",
        "case_id": case_id,
        "artifact_sha256": hashes,
        "actual_reader": reader,
        "reader_scope": "FORMAT_SOURCE_LAYERS_GT_ABSENCE_AND_EXACT_ARTIFACT_HASHES",
    }


def _targets(args: argparse.Namespace, modules: SimpleNamespace) -> dict[str, Any]:
    p = modules.p
    protocol = p.read_json(args.root / "configs/benchmarks/protocol_v1.json")
    _require(
        protocol["acceptance"]["overall_pass_fail"] is False,
        "protocol overall metric classification changed",
    )
    summary = p.read_json(args.release / "scoped/inference_primary/summary.json")
    cases = [case for case in summary["cases"] if case["case_id"] == "case3"]
    _require(
        len(cases) == 1 and bool(cases[0]["gaps"]),
        "Case3 target report has no declared actual gaps",
    )
    rows = []
    target_records = []
    office = p.read_json(args.release / "office/evaluation/verification.json")["measurements"][
        "case1"
    ]["spatiotemporal"]
    for field in ("ade_m", "fde_m"):
        value = office.get(field)
        _require(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0,
            "Case1 initial target lacks actual measurement",
        )
        target_records.append(
            {
                "case_id": "case1",
                "metric": field,
                "value": value,
                "comparison": "<=",
                "target_value": 0.5,
                "status": "TARGET_MET" if value <= 0.5 else "TARGET_MISSED",
            }
        )
    for gap in cases[0]["gaps"]:
        base = args.release / "scoped/evaluation/metrics/case3" / gap["gap_directory"]
        a, c = p.read_json(base / "shortest_path.json"), p.read_json(base / "spatiotemporal.json")
        first, proposed = a.get("ade_m"), c.get("ade_m")
        measured = all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0
            for v in (first, proposed)
        )
        row = {
            "case_id": "case3",
            "gap_id": gap["gap_id"],
            "time_range": gap["time_range"],
            "target": "PRD_SECTION_20_CASE3_PRIMARY_ADE_AT_LEAST_30_PERCENT_GAIN",
            "baseline": "A_SHORTEST_PATH",
            "proposed": "C_SPATIOTEMPORAL",
            "target_gain_fraction": 0.30,
            "baseline_ade_m": first,
            "proposed_ade_m": proposed,
            "baseline_metric_file_sha256": p.digest(base / "shortest_path.json"),
            "proposed_metric_file_sha256": p.digest(base / "spatiotemporal.json"),
        }
        if measured:
            row.update(
                {
                    "status": (
                        "N/A_ZERO_BASELINE_ADE"
                        if first == 0
                        else ("TARGET_MET" if proposed <= 0.7 * first else "TARGET_MISSED")
                    ),
                    "formula_comparison_status": "SATISFIED"
                    if proposed <= 0.7 * first
                    else "MISSED",
                    "ade_gain_fraction": (first - proposed) / first if first > 0 else None,
                    "relative_gain_status": "MEASURED" if first > 0 else "N/A_ZERO_BASELINE_ADE",
                }
            )
        else:
            for name, result in (("shortest_path", a), ("spatiotemporal", c)):
                if result.get("ade_m") is None:
                    frozen = p.read_json(
                        args.release
                        / "scoped/inference_primary/case3"
                        / gap["gap_directory"]
                        / name
                        / "run.json"
                    )
                    _require(
                        not frozen["event"]["trajectories"]
                        and result.get("timed_candidate_count") == 0,
                        "Case3 required timed A/C ADE measurement is missing",
                    )
                else:
                    _require(
                        isinstance(result["ade_m"], (int, float))
                        and not isinstance(result["ade_m"], bool)
                        and math.isfinite(result["ade_m"])
                        and result["ade_m"] >= 0,
                        "Case3 required A/C ADE measurement is nonfinite or invalid",
                    )
            row.update(
                {
                    "status": "N/A_NO_TIMED_BASELINE_OR_PROPOSED",
                    "ade_gain_fraction": None,
                    "reason": "FROZEN_A_OR_C_RESULT_HAS_NO_MEASURED_FINITE_ADE",
                    "baseline_status": a.get("status"),
                    "proposed_status": c.get("status"),
                }
            )
        rows.append(row)
        fde = c.get("fde_m")
        _require(
            isinstance(fde, (int, float))
            and not isinstance(fde, bool)
            and math.isfinite(fde)
            and fde >= 0,
            "Case3 initial FDE target lacks actual measurement",
        )
        target_records.append(
            {
                "case_id": "case3",
                "gap_id": gap["gap_id"],
                "metric": "fde_m",
                "value": fde,
                "comparison": "<=",
                "target_value": 1.0,
                "status": "TARGET_MET" if fde <= 1.0 else "TARGET_MISSED",
            }
        )
    for identity in ("case2", "case3"):
        for path in sorted(
            (args.release / "scoped/evaluation/metrics" / identity).glob("gap*/spatiotemporal.json")
        ):
            result = p.read_json(path)
            collision = result.get("collision_rate")
            _require(
                isinstance(collision, (int, float))
                and not isinstance(collision, bool)
                and math.isfinite(collision),
                "formal collision target lacks actual measurement",
            )
            target_records.append(
                {
                    "case_id": identity,
                    "gap_directory": path.parent.name,
                    "metric": "collision_rate",
                    "value": collision,
                    "target_value": 0,
                    "status": "TARGET_MET" if collision == 0 else "TARGET_MISSED",
                }
            )
            _require(
                result.get("impossible_transition_rate") is None,
                "zero-handoff population was given a synthetic transition rate",
            )
            target_records.append(
                {
                    "case_id": identity,
                    "gap_directory": path.parent.name,
                    "metric": "impossible_transition_rate",
                    "value": None,
                    "denominator": 0,
                    "status": "N/A_ZERO_DECLARED_TRANSITIONS",
                }
            )
    for field in ("collision_rate", "impossible_transition_rate"):
        value = office.get(field)
        _require(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value),
            "Case1 formal validity target lacks actual measurement",
        )
        target_records.append(
            {
                "case_id": "case1",
                "metric": field,
                "value": value,
                "target_value": 0,
                "status": "TARGET_MET" if value == 0 else "TARGET_MISSED",
            }
        )
    target_records.append(
        {
            "scope": "OVERALL_COVERAGE_AT_3",
            "target_value": 0.9,
            "value": None,
            "status": "N/A_UNAPPROVED_OVERALL_WEIGHTING",
        }
    )
    return {
        "status": "FULLY_REPORTED",
        "rows": rows,
        "protocol_initial_target_records": target_records,
        "target_source": "docs/PRD.md:434",
        "target_source_file_sha256": p.digest(args.root / "docs/PRD.md"),
        "protocol_file_sha256": p.digest(args.root / "configs/benchmarks/protocol_v1.json"),
        "overall_metric_pass": None,
        "overall_pass_fail_enabled": False,
        "all_research_targets_met": False,
        "initial_target_misses_are_valid_negative_benchmark_results": True,
        "target_misses_waived_or_thresholds_retuned": False,
        "cross_case_coverage_target": "N/A_UNAPPROVED_OVERALL_WEIGHTING",
        "zero_handoff_transition_target": "N/A_ZERO_DECLARED_TRANSITIONS",
    }


def audit_acceptance(args: argparse.Namespace) -> dict[str, Any]:
    modules = _modules(args.root)
    p = modules.p
    blockers: list[dict[str, str]] = []
    gates: dict[str, Any] = {}

    def check(name: str, callback: Callable[[], Any]) -> Any:
        try:
            value = callback()
            gates[name] = {"status": "PASS", "evidence": value}
            return value
        except Exception as error:
            reason = str(error) or type(error).__name__
            blockers.append({"gate": name, "reason": reason})
            gates[name] = {"status": "FAIL", "reason": reason}
            return None

    master = p.read_json(args.master)
    master_sha = p.digest(args.master)
    self_sha = p.digest(Path(__file__))

    def load_reviewed_controller() -> Any:
        _require(
            p.digest(args.root / CONTROLLER) == args.expected_controller_sha256
            and self_sha == args.expected_closeout_sha256,
            "reviewed controller/closeout bytes differ",
        )
        return _load(args.root / CONTROLLER, "case23_acceptance_reviewed_controller")

    controller = check("reviewed_audit_bytes", load_reviewed_controller)
    # Do not serialize the imported Python module into the final receipt.
    if controller is not None:
        gates["reviewed_audit_bytes"]["evidence"] = {
            "controller_file_sha256": args.expected_controller_sha256,
            "closeout_file_sha256": self_sha,
        }
    args.clean_checkout_spec = args.release / "clean_checkout_spec.json"
    lineage = check(
        "frozen_source_config_approval_and_evaluations",
        lambda: (
            controller._ready(args, modules)
            if controller is not None
            else _require(False, "reviewed controller unavailable")
        ),
    )
    state = {
        "sha256": p.digest(args.source),
        "size_bytes": args.source.stat().st_size,
        "mtime_ns": args.source.stat().st_mtime_ns,
    }
    check(
        "validated_code_producer_closure",
        lambda: _commit_producers(args.root, master, args.expected_code_commit),
    )
    check("formal_case_execution", lambda: _formal_cases(args.release, master_sha, modules))
    check("independent_source_class_readiness", partial(_source_readiness, args, modules, master))
    delivery_resolution = check(
        "independent_full_rrd_semantics_and_metadata_resolution",
        lambda: _metadata_resolution(args, modules),
    )
    if lineage is not None:
        check(
            "actual_reproduction_all_fields",
            lambda: _reproduction(args, modules, controller, lineage, delivery_resolution),
        )
    else:
        blockers.append(
            {
                "gate": "actual_reproduction_all_fields",
                "reason": "frozen primary lineage is unavailable",
            }
        )
    check(
        "full_clean_checkout_delivery", lambda: _clean_delivery(args, modules, delivery_resolution)
    )
    for name, path, count, population, script, test in (
        (
            "full_repository_validation",
            args.release / "repository_validation.json",
            2182,
            None,
            None,
            None,
        ),
        (
            "controller_supplemental_validation",
            args.controller_validation,
            16,
            "CONTROLLER_OUTSIDE_FROZEN_PRODUCER_CLOSURE",
            CONTROLLER,
            CONTROLLER_TEST,
        ),
        (
            "closeout_supplemental_validation",
            args.closeout_validation,
            args.expected_closeout_tests,
            "CLOSEOUT_OUTSIDE_FROZEN_PRODUCER_CLOSURE",
            "scripts/finalize_case23_acceptance.py",
            CLOSEOUT_TEST,
        ),
        (
            "rrd_semantic_comparator_supplemental_validation",
            args.semantic_validation,
            args.expected_semantic_tests,
            "RRD_SEMANTIC_COMPARATOR_OUTSIDE_FROZEN_PRODUCER_CLOSURE",
            SEMANTIC_SCRIPT,
            SEMANTIC_TEST,
        ),
        (
            "delivery_metadata_adapter_supplemental_validation",
            args.metadata_validation,
            args.expected_metadata_tests,
            "DELIVERY_METADATA_ADAPTER_OUTSIDE_FROZEN_PRODUCER_CLOSURE",
            METADATA_SCRIPT,
            METADATA_TEST,
        ),
    ):
        check(
            name,
            partial(
                _validation,
                path,
                modules,
                root=args.root,
                master_sha=master_sha,
                code_commit=args.expected_code_commit,
                source_state=state,
                count=count,
                population=population,
                script=script,
                test=test,
            ),
        )
    for case in ("case1", "case2", "case3"):
        check(
            case + "_actual_demo_reader_integrity",
            partial(_demo, args, modules, case, master),
        )
    targets = check("research_targets_fully_reported", lambda: _targets(args, modules))
    if lineage is not None:
        check(
            "final_immutable_source_and_primary_check",
            lambda: _require(
                _json_types(controller._ready(args, modules)) == _json_types(lineage)
                and p.digest(args.master) == master_sha
                and {
                    "sha256": p.digest(args.source),
                    "size_bytes": args.source.stat().st_size,
                    "mtime_ns": args.source.stat().st_mtime_ns,
                }
                == state,
                "source/master/primary evaluation changed during closeout audit",
            ),
        )
    return {
        "schema_version": "phase1-case123-workflow-acceptance-v1",
        "status": "PHASE1_EXIT_GATES_PASSED" if not blockers else "PHASE1_FINALIZATION_BLOCKED",
        "freeze_allowed": not blockers,
        "blockers": blockers,
        "gates": gates,
        "acceptance_scope": "COMPLETE_CASE1_3_WORKFLOW_WITH_VALID_NEGATIVE_RESEARCH_RESULTS",
        "formal_scope": SCOPE,
        "master_file_sha256": master_sha,
        "controller_file_sha256": p.digest(args.root / CONTROLLER),
        "delivery_metadata_adapter_file_sha256": p.digest(args.root / METADATA_SCRIPT),
        "rrd_semantic_helper_file_sha256": p.digest(args.root / SEMANTIC_SCRIPT),
        "closeout_file_sha256": self_sha,
        "validated_producer_code_commit_sha": args.expected_code_commit,
        "producer_file_count": len(master["producer_hashes"]),
        "source": state,
        "research_target_report": targets,
        "all_research_targets_met": False,
        "overall_metric_pass": None,
        "overall_pass_fail_enabled": False,
        "cross_case_weighting_status": "UNAPPROVED_NO_OVERALL_TARGET_PASS_CLAIMED",
        "same_camera_scoped_transition_rate_status": (
            "N/A_ZERO_DECLARED_TRANSITIONS_WITH_INDEPENDENT_HOLD_VALIDATION"
        ),
        "overall_physical_authority": "PARTIAL_APPROVED",
        "school_surface_authority": "NOT_CERTIFIED",
        "case4_status": "DEFERRED",
        "phase2_modified": False,
        "primary_verification_overwritten": False,
        "inference_or_reference_metrics_recalculated": False,
        "tag_or_publication_granted": False,
        "original_controller_status": gates.get("actual_reproduction_all_fields", {})
        .get("evidence", {})
        .get("original_controller_status"),
        "original_clean_delivery_status": gates.get("full_clean_checkout_delivery", {})
        .get("evidence", {})
        .get("original_clean_delivery_status"),
        "original_controller_failure_preserved": gates.get("actual_reproduction_all_fields", {})
        .get("evidence", {})
        .get("original_controller_status")
        == "FAIL",
        "original_clean_delivery_failure_preserved": gates.get("full_clean_checkout_delivery", {})
        .get("evidence", {})
        .get("original_clean_delivery_status")
        == "FAIL",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "root",
        "release",
        "master",
        "reproduction",
        "source",
        "controller-validation",
        "closeout-validation",
        "semantic-validation",
        "metadata-validation",
        "rrd-semantic-comparison",
        "delivery-metadata-comparison",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in (
        "expected-controller-sha256",
        "expected-closeout-sha256",
        "expected-code-commit",
        "expected-metadata-adapter-sha256",
        "expected-semantic-script-sha256",
    ):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--expected-closeout-tests", type=int, required=True)
    parser.add_argument("--expected-semantic-tests", type=int, required=True)
    parser.add_argument("--expected-metadata-tests", type=int, required=True)
    args = parser.parse_args()
    _require(
        args.output.name == "acceptance_verification.json" and not args.output.exists(),
        "fresh acceptance_verification.json output required",
    )
    result = audit_acceptance(args)
    _modules(args.root).p.write_json(args.output, result)
    print(result["status"])
    if not result["freeze_allowed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
