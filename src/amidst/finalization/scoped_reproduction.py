"""Actual scoped reruns and full-delivery comparison, without granting Phase 1 Exit."""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from pydantic import Field

from amidst.domain.common import DomainModel
from amidst.finalization.reviewed_pipeline import (
    compare_frozen_runs,
    digest,
    read_json,
    require_inference_freeze,
    safe_artifact,
    write_json,
)
from amidst.finalization.reviewed_reproduction import COUNT_FIELDS
from amidst.finalization.scoped_authority import ScopedUnionPhysicalProvider

RUNTIME_FIELDS = frozenset({
    "runtime_s", "inference_runtime_s", "runtime_seconds", "case_inference_runtime_s",
    "gap_inference_runtime_s", "case_inference_runtime_s_by_variant",
})
PATH_FIELDS = frozenset({"recording", "preview", "path", "output", "directory"})


class CleanCheckoutSpec(DomainModel):
    root: Path
    expected_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    master_relative_path: str
    source_config_relative_path: str
    source: Path
    python_executable: Path
    blender_executable: Path
    output: Path
    joint_release: bool = False


def verify_scoped_dataset(dataset: Path, *, inference_only: bool = False) -> dict[str, Any]:
    manifest = read_json(dataset / "manifest.json")
    if manifest.get("schema_version") != "phase1-scoped-source-dataset-v1":
        raise ValueError("scoped source dataset manifest required")
    for relative, expected in manifest["artifacts"].items():
        if inference_only and Path(relative).parts[0] != "inference":
            continue
        if digest(safe_artifact(dataset, relative)) != expected:
            raise ValueError("scoped dataset artifact differs from frozen manifest: " + relative)
    return manifest


def create_scoped_poison_dataset(dataset: Path, output: Path, *, primary: Path) -> dict[str, Any]:
    freeze = require_inference_freeze(primary)
    manifest = verify_scoped_dataset(dataset)
    if freeze["dataset_manifest_sha256"] != digest(dataset / "manifest.json"):
        raise ValueError("poison test dataset differs from frozen primary inference")
    if output.exists():
        raise FileExistsError("poison dataset must be fresh")
    output.mkdir(parents=True)
    # Copy only allowlisted manifest artifacts; never traverse unlisted symlinks/raw files.
    shutil.copyfile(dataset / "manifest.json", output / "manifest.json")
    for relative in manifest["artifacts"]:
        target = safe_artifact(output, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(safe_artifact(dataset, relative), target)
    changed: dict[str, list[str]] = {"ground_truth": [], "recipe": [], "reference_annotation": []}
    for path in sorted((output / "evaluation").rglob("ground_truth.json")):
        value = read_json(path)
        for row in value["samples"]:
            row["position"] = [position + 100000 * (axis + 1)
                               for axis, position in enumerate(row["position"])]
        path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
        changed["ground_truth"].append(str(path.relative_to(output)))
    for path in sorted((output / "simulation").rglob("recipe.json")):
        value = read_json(path)
        for row in value.get("waypoints", []):
            row["position"] = [position - 100000 * (axis + 1)
                               for axis, position in enumerate(row["position"])]
        value["poisoned_for_gt_isolation_test"] = True
        path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
        changed["recipe"].append(str(path.relative_to(output)))
    for path in sorted((output / "evaluation").rglob("reference_movement_annotations.json")):
        path.write_text('{"poisoned_reference_annotations": true, "segments": "INVALID"}\n')
        changed["reference_annotation"].append(str(path.relative_to(output)))
    inference_equal = all(digest(safe_artifact(dataset, relative)) == digest(
        safe_artifact(output, relative),
    ) for relative in manifest["artifacts"] if Path(relative).parts[0] == "inference")
    return {"changed_partitions": changed, "inference_artifacts_byte_identical": inference_equal,
            "manifest_preserved": digest(dataset / "manifest.json") == (
                digest(output / "manifest.json")
            )}


def _normalize(value: Any, root: Path, *, runtime: bool = False, field: str = "") -> Any:
    if isinstance(value, dict):
        result = {key: _normalize(item, root, runtime=(
            key in RUNTIME_FIELDS or runtime and key not in COUNT_FIELDS
        ), field=key) for key, item in value.items()}
        if str(value.get("filename", "")).endswith(".rrd") and "sha256" in value:
            result["sha256"] = "<RRD_CONTAINER_SHA256>"
        filename = Path(str(value.get("file", "")))
        if filename.stem in RUNTIME_FIELDS and filename.suffix in {".png", ".pdf"}:
            result["sha256"] = "<MEASURED_RUNTIME_PLOT_SHA256>"
        return result
    if isinstance(value, list):
        return [_normalize(item, root, runtime=runtime, field=field) for item in value]
    if runtime and isinstance(value, (int, float)) and not isinstance(value, bool):
        return "<MEASURED_RUNTIME>"
    if isinstance(value, str) and field in PATH_FIELDS:
        prefix = str(root.resolve()) + "/"
        if value.startswith(prefix):
            return "<EVALUATION>/" + value[len(prefix):]
    return value


def _runtime_artifact_integrity(value: Any, root: Path) -> list[str]:
    failures: list[str] = []
    if isinstance(value, dict):
        filename = Path(str(value.get("file", "")))
        if filename.stem in RUNTIME_FIELDS and filename.suffix in {".png", ".pdf"}:
            path = safe_artifact(root, "charts/" + filename.name)
            if not path.is_file() or value.get("sha256") != digest(path):
                failures.append(str(filename) + ": runtime plot receipt differs from actual bytes")
        for item in value.values():
            failures.extend(_runtime_artifact_integrity(item, root))
    elif isinstance(value, list):
        for item in value:
            failures.extend(_runtime_artifact_integrity(item, root))
    return failures


def _table_consistency(root: Path) -> list[str]:
    rows = read_json(root / "benchmark_table.json")["rows"]
    failures = []
    with (root / "benchmark_table.csv").open(newline="") as stream:
        actual = list(csv.DictReader(stream))
    expected = [{key: "" if value is None else str(value) for key, value in row.items()}
                for row in rows]
    if actual != expected:
        failures.append("benchmark_table.csv: differs from its JSON population")
    lines = [line for line in (root / "benchmark_table.md").read_text().splitlines()
             if line.startswith("|")]
    if len(lines) < 2:
        return failures + ["benchmark_table.md: absent population table"]
    columns = [cell.strip() for cell in lines[0].split("|")[1:-1]]
    actual_md = [[cell.strip() for cell in line.split("|")[1:-1]] for line in lines[2:]]
    expected_md = [["N/A" if row[key] is None else str(row[key]) for key in columns]
                   for row in rows]
    if actual_md != expected_md:
        failures.append("benchmark_table.md: differs from its JSON population")
    return failures


def compare_scoped_deliveries(
    *, local_dataset: Path, fresh_dataset: Path, local_inference: Path, fresh_inference: Path,
    local_evaluation: Path, fresh_evaluation: Path,
) -> dict[str, Any]:
    first_manifest = verify_scoped_dataset(local_dataset)
    second_manifest = verify_scoped_dataset(fresh_dataset)
    inference = compare_frozen_runs(local_inference, fresh_inference)
    files = [{str(path.relative_to(root)): path for path in root.rglob("*") if path.is_file()}
             for root in (local_evaluation, fresh_evaluation)]
    differences, exclusions = [], []
    required = {"summary.json", "benchmark_table.json", "benchmark_table.csv", "benchmark_table.md"}
    demo_cases = [case for case in first_manifest["cases"] if case["case_id"] in {"case2", "case3"}]
    required.update(f"demos/{case['case_id']}/{name}" for case in demo_cases
                    for name in ("scoped.rrd", "preview.png", "presentation.json"))
    required.update({"charts/projection_error_m.png", "charts/projection_error_m.pdf"})
    missing = sorted(required - set(files[0]) | required - set(files[1]))
    for index, root in enumerate((local_evaluation, fresh_evaluation)):
        table_names = {"benchmark_table.json", "benchmark_table.csv", "benchmark_table.md"}
        if not (table_names - set(files[index])):
            differences.extend(_table_consistency(root))
    counts: dict[str, int] = {}
    for relative in sorted(set(files[0]) | set(files[1])):
        if relative not in files[0] or relative not in files[1]:
            differences.append(relative + ": missing artifact")
            continue
        first, second = files[0][relative], files[1][relative]
        suffix = first.suffix
        counts[suffix] = counts.get(suffix, 0) + 1
        if suffix == ".rrd":
            for path in (first, second):
                presentation = read_json(path.parent / "presentation.json")
                if path.stat().st_size == 0 or presentation.get("rrd_reader_verified") is not True:
                    differences.append(relative + ": missing actual verified recording")
                recording = presentation.get("artifacts", {}).get("recording", {})
                if recording.get("filename") != path.name or (
                    recording.get("sha256") != digest(path)
                ):
                    differences.append(relative + ": recording receipt differs from actual bytes")
            exclusions.append(relative + ": container metadata bytes and their recorded SHA only")
        elif suffix in {".png", ".pdf"} and first.stem in RUNTIME_FIELDS:
            if not first.stat().st_size or not second.stat().st_size:
                differences.append(relative + ": empty measured-runtime plot")
            exclusions.append(relative + ": measured-runtime plot values only")
        elif suffix == ".json":
            first_value, second_value = read_json(first), read_json(second)
            differences.extend(_runtime_artifact_integrity(first_value, local_evaluation))
            differences.extend(_runtime_artifact_integrity(second_value, fresh_evaluation))
            if _normalize(first_value, local_evaluation) != (
                _normalize(second_value, fresh_evaluation)
            ):
                differences.append(relative + ": canonical JSON differs")
        elif relative in {"benchmark_table.csv", "benchmark_table.md"}:
            # Each table must exactly match its own full JSON population; JSON
            # equality preserves non-runtime values, N/A, counts and ordering.
            exclusions.append(relative + ": measured runtime values in declared columns only")
        elif digest(first) != digest(second):
            differences.append(relative + ": byte SHA-256 differs")
    passed = first_manifest == second_manifest and inference["status"] == "PASS" and not (
        differences or missing
    )
    return {"schema_version": "phase1-scoped-fresh-delivery-comparison-v1",
            "status": "PASS" if passed else "FAIL", "dataset_manifest_and_all_artifacts_equal": (
                first_manifest == second_manifest), "inference": inference,
            "report_and_demo_comparison_counts": counts, "differences": differences,
            "missing_required_reports": missing, "explicit_nondeterministic_exclusions": exclusions,
            "case_failure_na_and_candidate_order_preserved": True,
            "original_phase1_full_exit_or_freeze_granted": False}


def _command(arguments: list[str], *, root: Path) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root / "src")
    result = subprocess.run(arguments, cwd=root, env=environment, capture_output=True,
                            text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return {"arguments": arguments, "returncode": result.returncode}


def fresh_process_inference(dataset: Path, master: Path, output: Path, *, root: Path,
                            python_executable: Path) -> dict[str, Any]:
    return _command([str(python_executable), str(root / "scripts/run_phase1_scoped_case23.py"),
                     "infer", "--dataset", str(dataset), "--config", str(master),
                     "--output", str(output)], root=root)


def _gt_metric_probe(dataset: Path, poisoned: Path, primary: Path) -> list[dict[str, Any]]:
    from amidst.domain.evaluation import ConstraintConfig
    from amidst.domain.metric_config import MetricConfig
    from amidst.domain.trajectory import Event
    from amidst.evaluation.configured import evaluate_configured_trajectories
    from amidst.finalization.reviewed_pipeline import evaluation_reference
    from amidst.finalization.scoped_evaluation import ScopedGroundTruth, _reference_adapter

    require_inference_freeze(primary)
    master = read_json(primary / "experiment.json")
    metrics = MetricConfig.model_validate(master["metric_config"])
    config = read_json(primary / "config.json")
    constraints = ConstraintConfig(max_speed_m_s=config["movement"]["max_speed_m_s"])
    records: list[dict[str, Any]] = []
    for path in sorted(primary.glob("case*/gap*/spatiotemporal/run.json")):
        event = Event.model_validate(read_json(path)["event"])
        case_id = path.relative_to(primary).parts[0]
        if not event.trajectories:
            records.append({"case_id": case_id, "status": "N/A_NO_TIMED_CANDIDATES"})
            continue
        outputs = []
        for root in (dataset, poisoned):
            truth = ScopedGroundTruth.model_validate_json(
                (root / "evaluation" / case_id / "ground_truth.json").read_bytes(),
            )
            reference = evaluation_reference(
                _reference_adapter(truth, config["metres_per_blender_unit"]), event, seed=42,
            )
            outputs.append(evaluate_configured_trajectories(
                event.trajectories, reference, metrics, constraints=constraints,
            ).model_dump(mode="json"))
        records.append({"case_id": case_id, "gap_directory": path.parent.parent.name,
                        "status": "PASS" if outputs[0] != outputs[1] else "FAIL",
                        "evaluation_changed": outputs[0] != outputs[1],
                        "normal": outputs[0], "poisoned": outputs[1]})
    require_inference_freeze(primary)
    return records


def clean_checkout_delivery(
    spec: CleanCheckoutSpec, *, local_dataset: Path, local_inference: Path, local_evaluation: Path,
) -> dict[str, Any]:
    spec = CleanCheckoutSpec.model_validate(spec.model_dump(mode="python"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=spec.root, capture_output=True,
                          text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=normal"],
                           cwd=spec.root, capture_output=True, text=True, check=True).stdout.strip()
    if head != spec.expected_commit or dirty:
        raise ValueError("independent full rerun requires the exact clean checkout commit")
    if spec.output.exists():
        raise FileExistsError("fresh clean-checkout run output required")
    master = safe_artifact(spec.root, spec.master_relative_path)
    config = safe_artifact(spec.root, spec.source_config_relative_path)
    if spec.joint_release:
        from amidst.finalization.reviewed_reproduction import compare_reviewed_deliveries
        from amidst.finalization.scoped_protocol import require_joint_inference_boundary

        if local_dataset.parent != local_inference.parent or (
            local_dataset.parent != local_evaluation.parent
            or local_dataset.parent.name != "scoped"
        ):
            raise ValueError("joint comparison requires the actual scoped child package layout")
        local_joint = local_dataset.parent.parent
        command = _command([
            str(spec.python_executable), str(spec.root / "scripts/run_phase1_joint_case23.py"),
            "rerun", "--source", str(spec.source), "--blender", str(spec.blender_executable),
            "--source-config", str(config), "--config", str(master), "--output", str(spec.output),
        ], root=spec.root)
        for release in (local_joint, spec.output):
            require_joint_inference_boundary(
                release / "joint_inference_freeze.json", master,
                release / "office/inference_primary",
            )
            receipt = read_json(release / "primary_run_receipt.json")
            if receipt.get("source_unchanged") is not True or (
                receipt.get("master_file_sha256") != digest(master)
            ):
                raise ValueError("joint rerun source/master integrity receipt is incomplete")
        scoped = compare_scoped_deliveries(
            local_dataset=local_dataset, fresh_dataset=spec.output / "scoped/dataset",
            local_inference=local_inference,
            fresh_inference=spec.output / "scoped/inference_primary",
            local_evaluation=local_evaluation, fresh_evaluation=spec.output / "scoped/evaluation",
        )
        office = compare_reviewed_deliveries(
            local_dataset=local_joint / "office/dataset",
            fresh_dataset=spec.output / "office/dataset",
            local_inference=local_joint / "office/inference_primary",
            fresh_inference=spec.output / "office/inference_primary",
            local_evaluation=local_joint / "office/evaluation",
            fresh_evaluation=spec.output / "office/evaluation",
        )
        joint_differences = []
        for filename in ("verification.json", "case3_growth.json", "benchmark_table.json"):
            if _normalize(read_json(local_joint / filename), local_joint) != (
                _normalize(read_json(spec.output / filename), spec.output)
            ):
                joint_differences.append(filename + ": canonical joint population differs")
        for release in (local_joint, spec.output):
            joint_differences.extend(_table_consistency(release))
        passed = scoped["status"] == office["status"] == "PASS" and not joint_differences
        result = {
            "status": "PASS" if passed else "FAIL", "joint_release": True,
            "clean_checkout_head": head, "initial_checkout_clean": True,
            "all_stages_actually_executed": True, "commands": [command],
            "scoped_comparison": scoped, "original_office_comparison": office,
            "joint_population_differences": joint_differences,
            "both_child_freezes_verified_before_reference_access": True,
            "original_phase1_full_exit_or_freeze_granted": False,
        }
        write_json(spec.output / "delivery_comparison.json", result)
        return result
    spec.output.mkdir(parents=True)
    script = spec.root / "scripts/run_phase1_scoped_case23.py"
    lock, dataset = spec.output / "export_lock.json", spec.output / "dataset"
    inference, evaluation = spec.output / "inference", spec.output / "evaluation"
    commands = [_command([str(spec.python_executable), str(script), "freeze-export", "--config",
                          str(config), "--source", str(spec.source), "--output", str(lock),
                          "--experiment", str(master)], root=spec.root)]
    commands.append(_command([
        str(spec.blender_executable), "--background", "--disable-autoexec", str(spec.source),
        "--python", str(spec.root / "scripts/export_phase1_scoped_inputs.py"), "--", "--lock",
        str(lock), "--expected-lock-sha256", digest(lock), "--output", str(dataset),
    ], root=spec.root))
    commands.append(fresh_process_inference(dataset, master, inference, root=spec.root,
                                            python_executable=spec.python_executable))
    commands.append(_command([str(spec.python_executable), str(script), "evaluate", "--dataset",
                              str(dataset), "--inference", str(inference), "--output",
                              str(evaluation)], root=spec.root))
    comparison = compare_scoped_deliveries(
        local_dataset=local_dataset, fresh_dataset=dataset, local_inference=local_inference,
        fresh_inference=inference, local_evaluation=local_evaluation, fresh_evaluation=evaluation,
    )
    result = {"status": comparison["status"], "clean_checkout_head": head,
              "initial_checkout_clean": True, "all_stages_actually_executed": True,
              "commands": commands, "comparison": comparison}
    write_json(spec.output / "delivery_comparison.json", result)
    return result


def verify_scoped_reproduction(
    dataset: Path, primary: Path, master_path: Path, output: Path, *, root: Path,
    primary_evaluation: Path | None = None, fresh_checkout: CleanCheckoutSpec | None = None,
    provider: ScopedUnionPhysicalProvider | None = None,
    python_executable: Path = Path(sys.executable),
) -> dict[str, Any]:
    from amidst.finalization.scoped_export import load_export_authority
    from amidst.finalization.scoped_pipeline import evaluate_scoped_dataset, infer_scoped_dataset

    require_inference_freeze(primary)
    manifest = verify_scoped_dataset(dataset)
    master = read_json(master_path)
    if require_inference_freeze(primary)["config_sha256"] != digest(master_path) or (
        sorted(case["case_id"] for case in manifest["cases"]) != sorted(master["source_case_ids"])
    ):
        raise ValueError("reproduction scope/config differs from frozen source population")
    if output.exists():
        raise FileExistsError("reproduction output must be fresh")
    output.mkdir(parents=True)
    provider = provider or load_export_authority(root)
    infer_scoped_dataset(dataset, master_path, output / "repeat", root=root, provider=provider)
    fresh_command = fresh_process_inference(dataset, master_path, output / "fresh_process",
                                             root=root, python_executable=python_executable)
    infer_scoped_dataset(dataset, master_path, output / "reordered", root=root, reordered=True,
                         provider=provider)
    poison = output / "poison_dataset"
    poison_receipt = create_scoped_poison_dataset(dataset, poison, primary=primary)
    infer_scoped_dataset(poison, master_path, output / "gt_poison", root=root, provider=provider)
    comparisons = {name: compare_frozen_runs(primary, output / name)
                   for name in ("repeat", "fresh_process", "reordered", "gt_poison")}
    sensitivity = _gt_metric_probe(dataset, poison, primary)
    cases = {case["case_id"] for case in manifest["cases"]}
    measured_sensitivity = [item for item in sensitivity if item["status"] != (
        "N/A_NO_TIMED_CANDIDATES"
    )]
    sensitive_cases = {item["case_id"] for item in sensitivity if item["status"] == "PASS"}
    poison_pass = all(poison_receipt["changed_partitions"].values()) and (
        poison_receipt["inference_artifacts_byte_identical"] and measured_sensitivity
        and all(item["status"] == "PASS" for item in measured_sensitivity)
        and sensitive_cases <= cases
        and comparisons["gt_poison"]["status"] == "PASS"
    )
    write_json(output / "poison_sensitivity.json", {"records": sensitivity, **poison_receipt})
    summaries = [read_json(output / name / "summary.json") for name in comparisons]
    termination = [variant for summary in summaries for case in summary["cases"]
                   for gap in case["gaps"] for variant in gap["variants"]
                   if variant["status"] == "EXECUTED"]
    termination_pass = bool(termination) and all(
        item.get("termination_reason") in {"COMPLETE", "NO_FEASIBLE_PATH", "MAX_PATHS_REACHED"}
        and item.get("generation_complete") is True and item.get("inventory_complete") is True
        for item in termination
    )
    evaluation = primary_evaluation
    if evaluation is None:
        evaluation = output / "evaluation"
        evaluate_scoped_dataset(dataset, primary, evaluation, root=root, provider=provider)
    clean = clean_checkout_delivery(fresh_checkout, local_dataset=dataset, local_inference=primary,
                                   local_evaluation=evaluation) if fresh_checkout else {
        "status": "NOT_RUN", "reason": "CLEAN_CHECKOUT_FULL_DELIVERY_NOT_SUPPLIED",
    }
    passed = all(row["status"] == "PASS" for row in comparisons.values()) and poison_pass and (
        termination_pass and clean["status"] == "PASS"
    )
    result = {"schema_version": "phase1-scoped-reproduction-v1",
              "status": "PASS" if passed else "INCOMPLETE",
              "scope_case_ids": sorted(cases),
              "dataset_manifest_sha256": digest(dataset / "manifest.json"),
              "config_sha256": digest(master_path), "comparisons": comparisons,
              "fresh_process_command": fresh_command,
              "gt_sensitive_case_ids": sorted(sensitive_cases),
              "gt_metric_sensitivity_unavailable": [
                  item for item in sensitivity if item["status"] == "N/A_NO_TIMED_CANDIDATES"
              ],
              "gt_recipe_reference_annotation_poison_status": (
                  "PASS" if poison_pass else "FAIL"),
              "termination_status": "PASS" if termination_pass else "FAIL",
              "termination_ledger": termination, "clean_checkout": clean,
              "original_phase1_full_exit_or_freeze_granted": False}
    require_inference_freeze(primary)
    write_json(output / "verification.json", result)
    return result
