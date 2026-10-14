"""Schedule frozen public reproduction APIs; never replace a model or gate.

This controller is independently hashed and lives outside the frozen producer
closure. It requires a completed primary joint release before any GT access.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

MODE = "PARALLEL_FROZEN_PUBLIC_APIS_NOT_ORIGINAL_SEQUENTIAL_RUNNER"
WORKERS = ("repeat-order", "fresh", "poison", "clean", "office")


def _modules(root: Path) -> SimpleNamespace:
    sys.path.insert(0, str(root / "src"))
    from amidst.finalization import (
        reviewed_pipeline,
        scoped_export,
        scoped_pipeline,
        scoped_protocol,
        scoped_reproduction,
    )

    return SimpleNamespace(
        p=reviewed_pipeline,
        export=scoped_export,
        pipeline=scoped_pipeline,
        protocol=scoped_protocol,
        repro=scoped_reproduction,
    )


def _controller_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _ready(args: argparse.Namespace, modules: SimpleNamespace) -> dict[str, Any]:
    p, protocol = modules.p, modules.protocol
    master = p.read_json(args.master)
    protocol.validate_master_bindings(master, args.root)
    protocol.require_joint_inference_boundary(
        args.release / "joint_inference_freeze.json",
        args.master,
        args.release / "office/inference_primary",
    )
    receipt = p.read_json(args.release / "primary_run_receipt.json")
    joint_freeze_sha = p.digest(args.release / "joint_inference_freeze.json")
    if receipt.get("source_unchanged") is not True or (
        receipt.get("master_file_sha256") != p.digest(args.master)
        or receipt.get("joint_inference_freeze_file_sha256") != joint_freeze_sha
    ):
        raise ValueError("completed source-preserving primary evaluation receipt required")
    evaluation_bindings = {}
    definitions = (
        (
            "office",
            "verification.json",
            "phase1-reviewed-evaluation-report-v1",
            "dataset_manifest_sha256",
            "primary_inference_freeze_sha256",
        ),
        (
            "scoped",
            "summary.json",
            "phase1-scoped-evaluation-summary-v1",
            "dataset_manifest_file_sha256",
            "inference_freeze_file_sha256",
        ),
    )
    for case_scope, filename, schema, manifest_field, freeze_field in definitions:
        child = args.release / case_scope
        path = child / "evaluation" / filename
        if not path.is_file():
            raise ValueError("both actual primary evaluations must finish before reproduction")
        evaluation = p.read_json(path)
        manifest = p.read_json(child / "dataset/manifest.json")
        manifest_sha = p.digest(child / "dataset/manifest.json")
        frozen = p.require_inference_freeze(child / "inference_primary")
        freeze_sha = p.digest(child / "inference_primary/inference_freeze.json")
        if frozen.get("schema_version") != "phase1-reviewed-inference-freeze-v1" or (
            frozen.get("ground_truth_read") is not False
            or frozen.get("dataset_manifest_sha256") != manifest_sha
            or evaluation.get("schema_version") != schema
            or evaluation.get(manifest_field) != manifest_sha
            or evaluation.get(freeze_field) != freeze_sha
            or sorted(row["case_id"] for row in evaluation.get("cases", []))
            != sorted(row["case_id"] for row in manifest["cases"])
        ):
            raise ValueError("primary evaluation differs from its actual child dataset/freeze")
        if (
            case_scope == "office"
            and evaluation.get("evaluation_inference_freeze_verified") is not True
        ):
            raise ValueError("office evaluation lacks the original verified freeze boundary")
        if case_scope == "scoped" and (
            evaluation.get("source_sha256") != master["source_sha256"]
            or evaluation.get("original_protocol_preserved") is not True
        ):
            raise ValueError("scoped evaluation source/protocol binding differs from frozen master")
        evaluation_bindings[case_scope] = {
            "receipt_path": str(path),
            "receipt_file_sha256": p.digest(path),
            "dataset_manifest_file_sha256": manifest_sha,
            "inference_freeze_file_sha256": freeze_sha,
            "schema_version": schema,
        }
    spec = modules.repro.CleanCheckoutSpec.model_validate_json(
        args.clean_checkout_spec.read_bytes()
    )
    if spec.joint_release is not True:
        raise ValueError("parallel reproduction requires full joint clean-checkout delivery")
    source = (p.digest(spec.source), spec.source.stat().st_size, spec.source.stat().st_mtime_ns)
    if source[0] != master["source_sha256"] or tuple(receipt["source_after"]) != source:
        raise ValueError("source hash/size/mtime differs from completed primary receipt")
    return {
        "master_file_sha256": p.digest(args.master),
        "joint_inference_freeze_file_sha256": p.digest(
            args.release / "joint_inference_freeze.json"
        ),
        "scoped_inference_freeze_file_sha256": p.digest(
            args.release / "scoped/inference_primary/inference_freeze.json"
        ),
        "office_inference_freeze_file_sha256": p.digest(
            args.release / "office/inference_primary/inference_freeze.json"
        ),
        "source_hash_size_mtime": source,
        "producer_hashes": master["producer_hashes"],
        "producer_closure_file_count": len(master["producer_hashes"]),
        "protected_input_hashes": master["protected_input_hashes"],
        "primary_evaluations_completed": True,
        "primary_evaluation_bindings": evaluation_bindings,
        "joint_freeze_verified_before_reference_access": True,
    }


def _run_worker(args: argparse.Namespace, modules: SimpleNamespace) -> None:
    _ready(args, modules)
    p, repro = modules.p, modules.repro
    scope = args.release / "scoped"
    print(f"{args.worker}: FROZEN_PUBLIC_OPERATION_STARTED", flush=True)
    if args.worker == "repeat-order":
        provider = modules.export.load_export_authority(args.root)
        records = []
        for name, reordered in (("repeat", False), ("reordered", True)):
            print(f"{name}: SAME_WORKER_INTACT_PROVIDER_PUBLIC_INFERENCE_STARTED", flush=True)
            started = time.monotonic()
            modules.pipeline.infer_scoped_dataset(
                scope / "dataset",
                args.master,
                args.output / name,
                root=args.root,
                reordered=reordered,
                provider=provider,
            )
            records.append({"operation": name, "elapsed_s": time.monotonic() - started})
        result = {"status": "EXECUTED", "same_process_repeat_order": True, "operations": records}
    elif args.worker in {"fresh", "poison"}:
        name = "fresh_process" if args.worker == "fresh" else "gt_poison"
        dataset = scope / "dataset" if args.worker == "fresh" else args.output / "poison_dataset"
        command = repro.fresh_process_inference(
            dataset,
            args.master,
            args.output / name,
            root=args.root,
            python_executable=args.python,
        )
        result = {"status": "EXECUTED", "fresh_interpreter": True, "command": command}
    elif args.worker == "clean":
        spec = repro.CleanCheckoutSpec.model_validate_json(args.clean_checkout_spec.read_bytes())
        result = repro.clean_checkout_delivery(
            spec,
            local_dataset=scope / "dataset",
            local_inference=scope / "inference_primary",
            local_evaluation=scope / "evaluation",
        )
    elif args.worker == "office":
        result = modules.protocol.reproduce_office_child(
            args.root,
            args.release / "office",
            master_path=args.master,
            joint_freeze_path=args.release / "joint_inference_freeze.json",
        )
    else:
        raise ValueError("unknown controller worker")
    _ready(args, modules)
    p.write_json(args.output / "jobs" / (args.worker + ".json"), result)
    print(f"{args.worker}: FROZEN_PUBLIC_OPERATION_FINISHED", flush=True)


def _command(args: argparse.Namespace, worker: str) -> list[str]:
    return [
        str(args.python),
        str(Path(__file__).resolve()),
        "--root",
        str(args.root),
        "--master",
        str(args.master),
        "--release",
        str(args.release),
        "--clean-checkout-spec",
        str(args.clean_checkout_spec),
        "--output",
        str(args.output),
        "--python",
        str(args.python),
        "--expected-controller-sha256",
        args.expected_controller_sha256,
        "--worker",
        worker,
    ]


def _subprocess_job(args: argparse.Namespace, worker: str) -> dict[str, Any]:
    argv = _command(args, worker)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(args.root / "src")
    log = args.output / "logs" / (worker + ".log")
    started = time.monotonic()
    with log.open("x", encoding="utf-8") as stream:
        process = subprocess.run(
            argv,
            cwd=args.root,
            env=environment,
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return {
        "worker": worker,
        "arguments": argv,
        "returncode": process.returncode,
        "elapsed_s": time.monotonic() - started,
        "log": str(log),
        "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
    }


def _schedule(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    # Office waits for a slot after the four scoped/native jobs. Each active
    # numerical authority is owned by a new interpreter; no fork/pickle/cache.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        pending = {executor.submit(_subprocess_job, args, worker): worker for worker in WORKERS}
        results = {}
        for future in concurrent.futures.as_completed(pending):
            worker = pending[future]
            try:
                results[worker] = future.result()
            except Exception as error:
                results[worker] = {
                    "worker": worker,
                    "returncode": -1,
                    "error": f"{type(error).__name__}: {error}",
                }
            print(json.dumps({"worker_finished": worker, **results[worker]}), flush=True)
    return results


def _office_gates(args: argparse.Namespace, modules: SimpleNamespace) -> dict[str, Any]:
    path = args.release / "office/reproduction/verification.json"
    if not path.is_file():
        return {"status": "FAIL", "reason": "ORIGINAL_OFFICE_REPRODUCTION_RECEIPT_MISSING"}
    receipt = modules.p.read_json(path)
    comparisons = receipt.get("comparisons", {})
    metric_changes = receipt.get("gt_poison_evaluation_changed", [])
    passed = (
        receipt.get("status") == "PASS"
        and set(comparisons) == {"repeat", "fresh_process", "reordered", "gt_poison"}
        and all(item.get("status") == "PASS" for item in comparisons.values())
        and all(
            receipt.get(name) == "PASS"
            for name in (
                "repeat_status",
                "fresh_process_status",
                "ordering_status",
                "gt_poison_status",
                "termination_status",
            )
        )
        and receipt.get("annotation_poison_inference_unchanged") is True
        and isinstance(receipt.get("poisoned_reference_annotation_files"), int)
        and not isinstance(receipt.get("poisoned_reference_annotation_files"), bool)
        and receipt["poisoned_reference_annotation_files"] > 0
        and bool(metric_changes)
        and all(item is True for item in metric_changes)
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "receipt_path": str(path),
        "receipt_file_sha256": modules.p.digest(path),
        "all_declared_original_office_reproduction_fields_verified": passed,
        "original_receipt": receipt,
    }


def _finalize(
    args: argparse.Namespace,
    modules: SimpleNamespace,
    before: dict[str, Any],
    poison_receipt: dict[str, Any],
    jobs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    p, repro = modules.p, modules.repro
    primary = args.release / "scoped/inference_primary"
    dataset = args.release / "scoped/dataset"
    manifest = repro.verify_scoped_dataset(dataset)
    comparisons = {}
    for name in ("repeat", "fresh_process", "reordered", "gt_poison"):
        try:
            comparisons[name] = p.compare_frozen_runs(primary, args.output / name)
        except Exception as error:
            comparisons[name] = {"status": "FAIL", "error": f"{type(error).__name__}: {error}"}
    sensitivity = repro._gt_metric_probe(dataset, args.output / "poison_dataset", primary)
    cases = {case["case_id"] for case in manifest["cases"]}
    measured = [item for item in sensitivity if item["status"] != "N/A_NO_TIMED_CANDIDATES"]
    sensitive_cases = {item["case_id"] for item in sensitivity if item["status"] == "PASS"}
    poison_pass = bool(
        all(poison_receipt["changed_partitions"].values())
        and poison_receipt["inference_artifacts_byte_identical"]
        and measured
        and all(item["status"] == "PASS" for item in measured)
        and sensitive_cases <= cases
        and comparisons["gt_poison"]["status"] == "PASS"
    )
    p.write_json(
        args.output / "poison_sensitivity.json", {"records": sensitivity, **poison_receipt}
    )
    termination: list[dict[str, Any]] = []
    for name in comparisons:
        summary_path = args.output / name / "summary.json"
        if summary_path.is_file():
            summary = p.read_json(summary_path)
            termination.extend(
                variant
                for case in summary["cases"]
                for gap in case["gaps"]
                for variant in gap["variants"]
                if variant["status"] == "EXECUTED"
            )
    termination_pass = bool(termination) and all(
        item.get("termination_reason") in {"COMPLETE", "NO_FEASIBLE_PATH", "MAX_PATHS_REACHED"}
        and item.get("generation_complete") is True
        and item.get("inventory_complete") is True
        for item in termination
    )
    clean_path, office_path = args.output / "jobs/clean.json", args.output / "jobs/office.json"
    clean = (
        p.read_json(clean_path)
        if clean_path.is_file()
        else {"status": "FAIL", "reason": "WORKER_FAILED"}
    )
    office = p.read_json(office_path) if office_path.is_file() else {"reproduction_status": "FAIL"}
    office_gates = _office_gates(args, modules)
    after = _ready(args, modules)
    unchanged = before == after
    scoped_pass = (
        set(jobs) == set(WORKERS)
        and set(comparisons) == {"repeat", "fresh_process", "reordered", "gt_poison"}
        and all(row["status"] == "PASS" for row in comparisons.values())
        and poison_pass
        and termination_pass
        and clean["status"] == "PASS"
        and all(job["returncode"] == 0 for job in jobs.values())
        and unchanged
    )
    scoped = {
        "schema_version": "phase1-scoped-reproduction-v1",
        "status": "PASS" if scoped_pass else "INCOMPLETE",
        "scope_case_ids": sorted(cases),
        "dataset_manifest_sha256": p.digest(dataset / "manifest.json"),
        "config_sha256": p.digest(args.master),
        "comparisons": comparisons,
        "fresh_process_command": p.read_json(args.output / "jobs/fresh.json").get("command")
        if (args.output / "jobs/fresh.json").is_file()
        else None,
        "gt_sensitive_case_ids": sorted(sensitive_cases),
        "gt_metric_sensitivity_unavailable": [
            item for item in sensitivity if item["status"] == "N/A_NO_TIMED_CANDIDATES"
        ],
        "gt_recipe_reference_annotation_poison_status": "PASS" if poison_pass else "FAIL",
        "termination_status": "PASS" if termination_pass else "FAIL",
        "termination_ledger": termination,
        "clean_checkout": clean,
        "original_phase1_full_exit_or_freeze_granted": False,
        "execution_method": MODE,
        "original_sequential_runner_executed": False,
    }
    p.write_json(args.output / "verification.json", scoped)
    result = {
        "schema_version": "phase1-joint-parallel-reproduction-receipt-v1",
        "status": "PASS"
        if scoped_pass and office["reproduction_status"] == office_gates["status"] == "PASS"
        else "FAIL",
        "execution_method": MODE,
        "original_sequential_runner_executed": False,
        "controller_file_sha256": _controller_sha256(),
        "max_active_workers": 4,
        "interpreter_start_method": "SUBPROCESS_FRESH_INTERPRETERS_NO_FORK",
        "same_worker_repeat_order_provider_reuse_only": True,
        "wallclock_budgets_and_frozen_public_checks_preserved": True,
        "frozen_primary_and_source_unchanged": unchanged,
        "frozen_lineage_before": before,
        "frozen_lineage_after": after,
        "office": office,
        "original_office_field_gates": office_gates,
        "scoped": scoped,
        "jobs": jobs,
        "master_file_sha256": p.digest(args.master),
        "formal_freeze_granted": False,
    }
    p.write_json(args.output / "joint_reproduction_receipt.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "master", "release", "clean-checkout-spec", "output", "python"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-controller-sha256", required=True)
    parser.add_argument("--worker", choices=WORKERS)
    args = parser.parse_args()
    if args.expected_controller_sha256 != _controller_sha256():
        raise ValueError("controller bytes differ from separately reviewed SHA-256")
    modules = _modules(args.root)
    if args.worker:
        _run_worker(args, modules)
        return
    before = _ready(args, modules)
    if args.output.exists():
        raise FileExistsError("parallel reproduction output must be fresh")
    spec = modules.repro.CleanCheckoutSpec.model_validate_json(
        args.clean_checkout_spec.read_bytes()
    )
    if spec.output.exists():
        raise FileExistsError("full clean-checkout joint delivery output must be fresh")
    args.output.mkdir(parents=True)
    (args.output / "logs").mkdir()
    modules.p.write_json(
        args.output / "execution_plan.json",
        {
            "execution_method": MODE,
            "controller_file_sha256": _controller_sha256(),
            "max_active_workers": 4,
            "jobs_in_submission_order": WORKERS,
            "frozen_lineage": before,
            "original_sequential_runner_executed": False,
        },
    )
    # _ready has required both child freezes and completed primary evaluations;
    # this is the first controller operation allowed to open reference inputs.
    poison = modules.repro.create_scoped_poison_dataset(
        args.release / "scoped/dataset",
        args.output / "poison_dataset",
        primary=args.release / "scoped/inference_primary",
    )
    jobs = _schedule(args)
    result = _finalize(args, modules, before, poison, jobs)
    print(json.dumps(result, sort_keys=True, indent=2), flush=True)
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
