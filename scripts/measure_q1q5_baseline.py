"""SYNTHETIC once-search / RULE_ONLY pursuit telemetry; no model or GT reads."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from amidst.q1q5.baseline_telemetry import MeasurementFailure, measure_call, verify_replay
from amidst.q1q5.store import canonical_hash

CASES = {
    "supported_candidate": None,
    "empty_candidates": {"A": {0: "STRONG", 1: "STRONG"}},
    "temporary_loss_recovery": {
        "A": {0: "STRONG", 1: "STRONG", **dict.fromkeys(range(4, 10), "STRONG")}
    },
    "incomplete_candidate_frames": {
        "A": {0: "STRONG", 1: "STRONG"},
        "B": dict.fromkeys(range(10), "MISSING"),
    },
    "no_seed": {},
}
WORKFLOWS = ("ONCE_SEARCH", "CONTINUOUS_PURSUIT")
MIN_DISK_BYTES = 8 * 1024**3


def save(path, value):
    raw = (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)


def disk(root, tag):
    if shutil.which("df"):
        raw = subprocess.check_output(["df", "-k", str(root)], text=True)
        (root / ("df-" + tag + ".txt")).write_text(raw)
    free = shutil.disk_usage(root).free
    if free < MIN_DISK_BYTES:
        raise RuntimeError("DISK_SPACE_BELOW_8_GIB")
    return free


def prepare(case):
    """Import existing SYNTHETIC fixtures only; fixture build is not model loading."""
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "tests/q1q5"))
    from test_q1_search import aliases
    from test_q5_controller import fixture, repin, request, seal_parameters, seed_id

    from amidst.q1q5.q1_search import search_cameras
    from amidst.q1q5.q4_evidence import candidate_evidence
    from amidst.q1q5.q5_controller import RuleController
    from amidst.q1q5.store import DetectionSnapshot

    b = fixture(CASES[case], cameras=("A", "B", "E"))
    # The legacy controller helper marks missing rows without clearing its mock
    # RGB hash. This new producer must emit honest MISSING records, not alter the kit.
    records = deepcopy(list(b.index.records))
    for row in records:
        if row["frame_state"] == "MISSING":
            row["rgb_file_sha256"] = None
    index = repin(DetectionSnapshot(deepcopy(b.index.manifest), tuple(records)))
    parameters = deepcopy(b.parameter_set)
    parameters["applies_to"]["detection_index_ids"] = [index.manifest["index_id"]]
    b = replace(
        b, index=index, index_sha256=index.manifest["content_sha256"], parameter_set=parameters
    )
    b.parameter_set["parameters"].append(
        {
            "name": "segment_merge_gap_us",
            "value": 0,
            "unit": "us",
            "status": "APPROVED",
            "proposed_by": "SYNTHETIC",
            "proposal_ref": "synthetic://test",
        }
    )
    seal_parameters(b.parameter_set)
    # RuntimeBindings is frozen; reconstruct it with the new fixture-only pin.
    b = replace(b, parameter_sha256=b.parameter_set["content_sha256"])
    a = aliases(b.index)
    q2 = request(b)
    q1 = {
        "schema_version": "q-demo.q1-request.v1",
        "session_ref": "SYNTHETIC",
        "scene_id": q2["scene_id"],
        "run_ids": q2["run_ids"],
        "time": q2["time"],
        "condition": {
            "class_label": "person",
            "min_count_per_frame": 1,
            "color": {"label": "red", "min_verdict": "STRONG"},
            "query_min_score": 0.5,
        },
        "camera_ids": None,
        "region_ids": None,
        "page_size": 20,
        "cursor": None,
        "origin": "MANUAL",
    }
    selected = seed_id(b) if case != "no_seed" else None

    def once_search():
        return search_cameras(
            q1,
            index=b.index,
            expected_index_sha256=b.index_sha256,
            aliases=a,
            expected_aliases_sha256=a["content_sha256"],
            clock_mapping=b.clock,
            parameter_set=b.parameter_set,
            expected_parameter_sha256=b.parameter_sha256,
            camera_catalog_ids=[r["camera_id"] for r in b.index.manifest["sampling"]["per_camera"]],
            media_token_for_frame=lambda ref: "SYNTHETIC-" + canonical_hash(ref),
            graphs=b.graphs,
        )

    def pursuit():
        return RuleController(
            q2,
            bindings=b,
            selected_observation_id=selected,
            evidence_provider=lambda i, s, r, c: candidate_evidence(i, s, r, **c),
        ).run()

    return b, q1, q2, selected, once_search, pursuit


def worker(args):
    from amidst.q1q5.event_modes import event_flags
    from amidst.q1q5.q5_controller import jsonl

    prepared, setup = measure_call(lambda: prepare(args.case))
    b, q1, q2, selected, once_search, pursuit = prepared
    operation = once_search if args.workflow == "ONCE_SEARCH" else pursuit
    rows = []
    first = None
    report = {
        "case_id": args.case,
        "workflow": args.workflow,
        "source_kind": "SYNTHETIC",
        "switch_mode": "RULE_ONLY",
        "counts_for_acceptance": False,
        "setup": setup,
        "cold_definition": "FIRST_KERNEL_CALL_IN_FRESH_WORKER_AFTER_FIXTURE_SETUP",
        "warm_definition": "REPEAT_KERNEL_CALL_SAME_PROCESS_SAME_PINNED_INPUT",
        "fixture_rebuild_in_timing": False,
        "model_connection": False,
        "http_in_timing": False,
        "ui_in_timing": False,
        "model_inference_fps": None,
        "display_fps": None,
        "accuracy": None,
        "unmeasured_reason": "NO_MODEL_RGB_PLAYBACK_OR_HUMAN_LABELS_IN_THIS_RUN",
        "selected_seed": selected,
        "samples": rows,
    }
    for n in range(args.warm_repeats + 1):
        phase = "FIRST_CALL" if n == 0 else "WARM_REPEAT"
        try:
            result, sample = measure_call(operation)
            replay = verify_replay(result if first is None else first, result)
            if first is None:
                first = result
            response = result if args.workflow == "ONCE_SEARCH" else result.response
            if response["agent_attempted"] or response["agent_used"]:
                raise ValueError("RULE_ONLY measurement unexpectedly attempted Agent")
            sample.update(
                iteration=n,
                phase=phase,
                domain_status=response["status"],
                output_sha256=response["output_sha256"],
                replay=replay,
                provider_calls=0,
                model_connection=False,
            )
            if args.workflow == "CONTINUOUS_PURSUIT":
                sample["flags"] = event_flags(response, lost_after_us=args.lost_after_us)
                sample["evidence_queries"] = len(result.evidence)
                sample["decisions"] = [
                    {
                        k: d.get(k)
                        for k in (
                            "source_time_us",
                            "decision_time_us",
                            "executed_action",
                            "candidate_ref",
                            "entry_observation_id",
                            "rejection_code",
                        )
                    }
                    for d in (json.loads(line) for line in result.decisions_bytes.splitlines())
                ]
                sample["fallback_used"] = response["fallback_used"]
            else:
                sample["matched_cameras"] = [r["camera_id"] for r in response["results"]]
                sample["not_evaluated_cameras"] = response["not_evaluated_cameras"]
            rows.append(sample)
        except MeasurementFailure as exc:
            rows.append(exc.sample | {"iteration": n, "phase": phase})
            report["status"] = "ERROR"
            break
    else:
        report["status"] = "COMPLETE"
    if first is not None:
        recorded = args.output / "recorded"
        recorded.mkdir(mode=0o700)
        response = first if args.workflow == "ONCE_SEARCH" else first.response
        docs = {
            "request.json": q1 if args.workflow == "ONCE_SEARCH" else q2,
            "response.json": response,
            "detection_index.json": b.index.manifest,
            "parameter_set.json": b.parameter_set,
            "clock_mapping.json": dict(b.clock.document),
            "region_graph.json": b.graphs.region,
            "camera_graph.json": b.graphs.camera,
        }
        for name, doc in docs.items():
            save(recorded / name, doc)
        (recorded / b.index.manifest["records_ref"]).write_bytes(jsonl(b.index.records))
        if args.workflow == "CONTINUOUS_PURSUIT":
            (recorded / first.response["decisions_ref"]).write_bytes(first.decisions_bytes)
            (recorded / first.response["links_ref"]).write_bytes(first.links_bytes)
            for i, snapshot in enumerate(first.snapshots):
                save(recorded / f"{i}.snapshot.json", snapshot)
            for i, evidence in enumerate(first.evidence):
                save(recorded / f"{i}.evidence.json", evidence)
    report["content_sha256"] = canonical_hash(report)
    save(args.output / "telemetry.json", report)
    if report["status"] != "COMPLETE":
        raise RuntimeError("WORKER_MEASUREMENT_FAILED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.add_argument("--lost-after-us", type=int, required=True)
    parser.add_argument("--warm-repeats", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--case", choices=CASES, help=argparse.SUPPRESS)
    parser.add_argument("--workflow", choices=WORKFLOWS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.lost_after_us <= 0 or not 1 <= args.warm_repeats <= 20:
        parser.error("Explicit positive LOST threshold; warm repeats between 1 and 20")
    if args.worker:
        if args.case is None or args.workflow is None:
            parser.error("Worker requires case and workflow")
        return worker(args)
    out = args.output
    if not out.is_absolute() or out.resolve() != out or out.exists() or not out.parent.is_dir():
        parser.error("New absolute canonical output with existing parent required")
    if shutil.disk_usage(out.parent).free < MIN_DISK_BYTES:
        parser.error("DISK_SPACE_BELOW_8_GIB")
    out.mkdir(mode=0o700)
    before = disk(out, "before")
    reports = []
    errors = []
    try:
        for case in CASES:
            for workflow in WORKFLOWS:
                disk(out, "latest")
                child = out / case / workflow
                child.mkdir(parents=True, mode=0o700)
                command = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--synthetic",
                    "--worker",
                    "--case",
                    case,
                    "--workflow",
                    workflow,
                    "--lost-after-us",
                    str(args.lost_after_us),
                    "--warm-repeats",
                    str(args.warm_repeats),
                    "--output",
                    str(child),
                ]
                try:
                    completed = subprocess.run(
                        command, capture_output=True, timeout=45, check=False
                    )
                    (child / "worker.stderr.txt").write_bytes(completed.stderr)
                    if completed.returncode:
                        errors.append(
                            {
                                "case_id": case,
                                "workflow": workflow,
                                "error": "WORKER_EXIT",
                                "exit_code": completed.returncode,
                            }
                        )
                except subprocess.TimeoutExpired:
                    errors.append(
                        {"case_id": case, "workflow": workflow, "error": "WORKER_TIMEOUT"}
                    )
                if (child / "telemetry.json").is_file():
                    reports.append(json.loads((child / "telemetry.json").read_text()))
    except Exception as exc:
        errors.append({"error": type(exc).__name__})
        raise
    finally:
        after = disk(out, "after")
        if len(reports) != len(CASES) * len(WORKFLOWS):
            errors.append({"error": "INCOMPLETE_REPORTS", "completed": len(reports)})
        report = {
            "schema_version": "q-demo.baseline-telemetry.v1",
            "source_kind": "SYNTHETIC",
            "counts_for_acceptance": False,
            "status": "ERROR" if errors else "COMPLETE",
            "worker_isolation": "ONE_PROCESS_PER_CASE_AND_WORKFLOW",
            "warm_repeats": args.warm_repeats,
            "lost_after_us": args.lost_after_us,
            "threshold_status": "EXPERIMENT_ONLY_NOT_APPROVED",
            "model_inference_fps": None,
            "display_fps": None,
            "accuracy": None,
            "platform": platform.system(),
            "machine": platform.machine(),
            "os_release": platform.release(),
            "logical_cpu_count": os.cpu_count(),
            "system_load_controlled": False,
            "python_version": platform.python_version(),
            "df_available_bytes_before": before,
            "df_available_bytes_after": after,
            "disk_delta_is_not_artifact_allocation": True,
            "reports": reports,
            "errors": errors,
        }
        report["content_sha256"] = canonical_hash(report)
        save(out / "REPORT.json", report)
        files = {
            p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(out.rglob("*"))
            if p.is_file()
        }
        save(out / "MANIFEST.json", files)
    if errors:
        raise SystemExit("MEASUREMENT_FAILED: see REPORT.json")
    print(
        json.dumps(
            {
                "status": report["status"],
                "workflows": len(reports),
                "samples": sum(len(r["samples"]) for r in reports),
                "report_sha256": report["content_sha256"],
            }
        )
    )


if __name__ == "__main__":
    main()
