"""Build fresh joint Case 1–3 primary evidence in an isolated release directory."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from amidst.finalization.reviewed_pipeline import digest, write_json
from amidst.finalization.scoped_export import freeze_export, load_export_authority
from amidst.finalization.scoped_joint_release import assemble_joint_release, freeze_joint_inference
from amidst.finalization.scoped_pipeline import evaluate_scoped_dataset, infer_scoped_dataset
from amidst.finalization.scoped_protocol import (
    build_scoped_experiment,
    evaluate_office_child,
    export_office_child,
    infer_office_child,
    reproduce_office_child,
    require_joint_inference_boundary,
    validate_master_bindings,
)


def run_primary(
    root: Path,
    source: Path,
    blender: Path,
    source_config: Path,
    master_path: Path,
    output: Path,
    *,
    reuse_frozen_master: bool = False,
) -> dict[str, Any]:
    if output.exists() or (master_path.exists() and not reuse_frozen_master):
        raise FileExistsError("fresh joint release and experiment definition paths required")
    source_before = digest(source), source.stat().st_size, source.stat().st_mtime_ns
    started = time.monotonic()
    print("SOURCE_AUTHORITY_NUMERICAL_REGENERATION_STARTED", flush=True)
    provider = load_export_authority(root)
    print("SOURCE_AUTHORITY_REGENERATED_BUILDING_FROZEN_MASTER", flush=True)
    if reuse_frozen_master:
        from amidst.finalization.reviewed_pipeline import read_json

        validate_master_bindings(read_json(master_path), root)
    else:
        build_scoped_experiment(root, source_config, master_path, provider=provider)
    output.mkdir(parents=True)
    lock = output / "source_export_lock.json"
    freeze_export(
        source_config, source, lock, root=root, experiment_path=master_path, provider=provider
    )
    scope_output = output / "scoped"
    scope_output.mkdir()
    print("NATIVE_SCOPED_SOURCE_EXPORT_STARTED_NO_SAVE_NO_RENDER", flush=True)
    argv = [
        str(blender),
        "--background",
        "--disable-autoexec",
        "--threads",
        "1",
        str(source),
        "--python",
        str(root / "scripts/export_phase1_scoped_inputs.py"),
        "--",
        "--lock",
        str(lock),
        "--expected-lock-sha256",
        digest(lock),
        "--output",
        str(scope_output / "dataset"),
    ]
    process = subprocess.run(argv, cwd=root, capture_output=True, text=True, check=False)
    (output / "scoped_export.log").write_text(process.stdout + "\n" + process.stderr)
    if process.returncode:
        raise RuntimeError("scoped native source export failed; inspect scoped_export.log")
    print("NATIVE_OFFICE_SOURCE_EXPORT_STARTED_ORIGINAL_PRODUCER", flush=True)

    def export_logged(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        exported = subprocess.run(*args, **kwargs)
        (output / "office_export.log").write_text(exported.stdout + "\n" + exported.stderr)
        return exported

    export_office_child(
        root,
        source,
        blender,
        output / "office",
        master_path=master_path,
        export_runner=export_logged,
    )
    print("OFFICE_PRIMARY_INFERENCE_STARTED_REFERENCE_PARTITIONS_UNOPENED", flush=True)
    infer_office_child(root, output / "office", master_path=master_path)
    print("SCOPED_PRIMARY_INFERENCE_STARTED_REFERENCE_PARTITIONS_UNOPENED", flush=True)
    infer_scoped_dataset(
        scope_output / "dataset",
        master_path,
        scope_output / "inference_primary",
        root=root,
        provider=provider,
    )
    freeze_joint_inference(output, master_path, root=root)
    print("BOTH_PRIMARY_CHILDREN_FROZEN_STARTING_INDEPENDENT_EVALUATION", flush=True)
    evaluate_office_child(
        root,
        output / "office",
        master_path=master_path,
        joint_freeze_path=output / "joint_inference_freeze.json",
        demos=True,
    )
    evaluate_scoped_dataset(
        scope_output / "dataset",
        scope_output / "inference_primary",
        scope_output / "evaluation",
        root=root,
        provider=provider,
    )
    result = assemble_joint_release(output, master_path, root=root)
    source_after = digest(source), source.stat().st_size, source.stat().st_mtime_ns
    if source_before != source_after:
        raise RuntimeError("immutable Blender source changed during joint experiment")
    write_json(
        output / "primary_run_receipt.json",
        {
            "schema_version": "phase1-joint-primary-run-receipt-v1",
            "source_before": source_before,
            "source_after": source_after,
            "source_unchanged": True,
            "master_file_sha256": digest(master_path),
            "joint_inference_freeze_file_sha256": digest(output / "joint_inference_freeze.json"),
            "total_primary_workflow_runtime_s": time.monotonic() - started,
            "runtime_population": "WHOLE_WORKFLOW_DIAGNOSTIC_NOT_CASE_INFERENCE_RUNTIME",
            "phase2_modified": False,
            "formal_freeze_granted": False,
        },
    )
    return result


def run_reproduction(
    root: Path, master_path: Path, release: Path, spec_path: Path
) -> dict[str, Any]:
    from amidst.finalization.scoped_reproduction import (
        CleanCheckoutSpec,
        verify_scoped_reproduction,
    )

    require_joint_inference_boundary(
        release / "joint_inference_freeze.json", master_path, release / "office/inference_primary"
    )
    spec = CleanCheckoutSpec.model_validate_json(spec_path.read_bytes())
    if spec.joint_release is not True:
        raise ValueError("joint reproduction requires full office/scoped clean checkout delivery")
    print("REPRODUCTION_SOURCE_AUTHORITY_REGENERATION_STARTED", flush=True)
    provider = load_export_authority(root)
    print("ORIGINAL_OFFICE_REPEAT_FRESH_ORDER_POISON_STARTED", flush=True)
    office = reproduce_office_child(
        root,
        release / "office",
        master_path=master_path,
        joint_freeze_path=release / "joint_inference_freeze.json",
    )
    print("SCOPED_REPEAT_FRESH_ORDER_POISON_AND_CLEAN_JOINT_DELIVERY_STARTED", flush=True)
    scoped = verify_scoped_reproduction(
        release / "scoped/dataset",
        release / "scoped/inference_primary",
        master_path,
        release / "reproduction",
        root=root,
        provider=provider,
        primary_evaluation=release / "scoped/evaluation",
        fresh_checkout=spec,
        python_executable=Path(sys.executable),
    )
    result = {
        "schema_version": "phase1-joint-reproduction-receipt-v1",
        "status": "PASS" if office["reproduction_status"] == scoped["status"] == "PASS" else "FAIL",
        "office": office,
        "scoped": scoped,
        "master_file_sha256": digest(master_path),
        "formal_freeze_granted": False,
    }
    write_json(release / "reproduction_receipt.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("primary", "rerun", "reproduce"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--clean-checkout-spec", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.stage == "reproduce":
        if args.clean_checkout_spec is None:
            parser.error("reproduce requires --clean-checkout-spec")
        result = run_reproduction(root, args.config, args.output, args.clean_checkout_spec)
    else:
        result = run_primary(
            root,
            args.source,
            args.blender,
            args.source_config,
            args.config,
            args.output,
            reuse_frozen_master=args.stage == "rerun",
        )
    print(json.dumps(result, sort_keys=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
