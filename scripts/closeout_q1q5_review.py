"""Bounded offline review closeout tools; outputs never grant runtime authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import socket
import statistics
import sys
from collections import Counter
from pathlib import Path


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def pinned(path: str | Path, expected: str) -> bytes:
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise ValueError("REGULAR_FILE_REQUIRED")
    raw = p.read_bytes()
    if sha(raw) != expected:
        raise ValueError("FILE_HASH_MISMATCH")
    return raw


def relative(name: str) -> Path:
    p = Path(name)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError("RELATIVE_PATH_REQUIRED")
    return p


def fresh(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError("OUTPUT_ALREADY_EXISTS")
    if shutil.disk_usage(path.parent).free < 8 * 1024**3:
        raise ValueError("DISK_BELOW_8_GIB")
    path.mkdir(mode=0o700)


def save(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def context(config: dict, output: Path) -> dict:
    """Add independently sourced vocabularies to new copies of Q1 recordings."""
    sources = {}
    for pack, ref in config["alias_sources"].items():
        sources[pack] = json.loads(pinned(ref["path"], ref["sha256"]))
        for source in ref.get("source_files", []):
            pinned(source["path"], source["sha256"])
    for case in config["cases"]:
        for name, digest in case["files"].items():
            pinned(Path(case["recorded"]) / relative(name), digest)
    fresh(output)
    cases, added = [], []
    for original in config["cases"]:
        case = dict(original)
        request = json.loads((Path(case["recorded"]) / "case.request.json").read_text())
        if request.get("schema_version") != "q-demo.q1-request.v1":
            cases.append(case)
            continue
        aliases = sources[case["pack"]]
        index = json.loads((Path(case["recorded"]) / "detection_index.json").read_text())
        if aliases["class_map_sha256"] != index["detector"]["class_map"]["content_sha256"]:
            raise ValueError("CLASS_MAP_BINDING_MISMATCH")
        response = json.loads((Path(case["recorded"]) / "case.response.json").read_text())
        if response.get("supported_classes_ref") not in (
            None,
            "supported-classes:" + aliases["content_sha256"],
        ):
            raise ValueError("SUPPORTED_CLASSES_REF_MISMATCH")
        dest = output / relative(case["id"])
        dest.mkdir(mode=0o700)
        for name in case["files"]:
            shutil.copyfile(Path(case["recorded"]) / name, dest / name)
        support = {
            "schema_version": "q1q5-conformance.supported-classes.v1",
            "class_labels": aliases["class_labels"],
            "aliases": aliases["aliases"],
            "color_labels": aliases["color_vocabulary"]["labels"],
        }
        save(dest / "supported_classes.json", support)
        case["recorded"] = str(dest)
        case["files"] = {
            **case["files"],
            "supported_classes.json": sha((dest / "supported_classes.json").read_bytes()),
        }
        cases.append(case)
        added.append(case["id"])
    new_input = {**config, "cases": cases}
    save(output / "INPUTS.json", new_input)
    result = {
        "schema_version": "q-demo.closeout-context.v1",
        "supplemented_q1_recordings": len(added),
        "cases": added,
        "new_input_sha256": sha((output / "INPUTS.json").read_bytes()),
        "original_recordings_modified": False,
        "schema_status": "KIT_INPUT_NOT_FORMAL_CONTRACT",
        "formal_run_allowed": False,
    }
    save(output / "RESULT.json", result)
    return result


def conformance(config: dict, output: Path) -> dict:
    """Invoke all checks from the unchanged pinned kit against original recordings."""
    kit = Path(config["kit_root"])
    for name, digest in config["kit_files"].items():
        pinned(kit / relative(name), digest)
    for case in config["cases"]:
        for name, digest in case["files"].items():
            pinned(Path(case["recorded"]) / relative(name), digest)
    fresh(output)
    sys.path.insert(0, str(kit / "src"))
    from amidst.evaluation.q1q5_conformance import (
        Doc,
        build_report,
        exit_code,
        file_sha256,
        load_directory,
    )

    attempts = []

    def deny(*args, **kwargs):
        attempts.append(True)
        raise RuntimeError("NETWORK_FORBIDDEN")

    previous = socket.socket.connect, socket.create_connection
    socket.socket.connect = deny
    socket.create_connection = deny
    reports, totals, failures = [], {}, []
    try:
        for case in config["cases"]:
            path = Path(case["recorded"])
            docs = load_directory(path)
            params = path / "parameter_set.json"
            parameter_file = None
            if params.is_file():
                parameter_file = (params.name, file_sha256(params))
                docs = [d for d in docs if d.kind != "parameter_set"]
                docs.append(
                    Doc(
                        params.name,
                        "parameter_set",
                        json.loads(params.read_text()),
                        parameter_file[1],
                        params.stem,
                        "",
                    )
                )
            report = build_report(docs, "recorded", params_file=parameter_file, only=None)
            name = str(relative(case["id"])) + ".json"
            save(output / name, report)
            counts = report["summary"]["by_status"]
            totals.setdefault(case["pack"], Counter()).update(counts)
            reports.append(
                {
                    "id": case["id"],
                    "pack": case["pack"],
                    "exit_code": exit_code(report, False),
                    "counts": counts,
                    "report_sha256": sha((output / name).read_bytes()),
                }
            )
            for result in report["checks"]:
                if result["status"] == "FAIL":
                    failures.append(
                        {
                            "case": case["id"],
                            "check_id": result["check_id"],
                            "findings": result.get("findings", []),
                        }
                    )
    finally:
        socket.socket.connect, socket.create_connection = previous
    result = {
        "schema_version": "q-demo.closeout-conformance.v1",
        "kit_commit": config["kit_commit"],
        "cases": len(reports),
        "totals": totals,
        "runs": reports,
        "failures": failures,
        "network_attempts": len(attempts),
        "kit_modified": False,
        "original_recordings_modified": False,
        "formal_run_allowed": False,
    }
    save(output / "RESULT.json", result)
    return result


def timeouts(config: dict, output: Path) -> dict:
    calls, resources, files = [], [], []

    def find_records(value, stage, row, location=""):
        if isinstance(value, dict):
            if {"timeout_ms", "validation", "stats", "timed_out"} <= set(value):
                wire = value.get("wire_request", {})
                calls.append(
                    {
                        "number": len(calls) + 1,
                        "round": row["round"],
                        "stage": stage,
                        "recorded_at": row["recorded_at"],
                        "recording_sha256": row["sha256"],
                        "record_location": location,
                        "timeout_ms": value["timeout_ms"],
                        "latency_ms": value["stats"].get("latency_ms"),
                        "validation": value["validation"],
                        "timed_out": value["timed_out"],
                        "has_raw_output": value.get("raw_output") is not None,
                        "model": value.get("model"),
                        "prompt_characters": len(value.get("prompt", "")),
                        "num_predict": wire.get("options", {}).get("num_predict"),
                        "load_duration_ms": None,
                        "queue_duration_ms": None,
                        "generation_duration_ms": None,
                    }
                )
                return
            for key, child in value.items():
                find_records(child, stage, row, location + "/" + key)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                find_records(child, stage, row, location + "/" + str(i))

    for row in config["files"]:
        raw = pinned(row["path"], row["sha256"])
        files.append(row["sha256"])
        doc = json.loads(raw)
        if row["role"] == "api_recording":
            row = {**row, "recorded_at": doc["recorded_at"]}
            find_records(doc.get("q3_provider_audit", []), "q3", row)
            find_records(doc.get("agent_trace", {}), "q5", row)
        elif row["role"] == "resources":
            resources.append(
                {
                    "round": row["round"],
                    "runner_samples": len(doc.get("runners", {}).get("samples", [])),
                    "runner_missing_reason": doc.get("runners", {}).get("missing_reason"),
                    "sampled_rss_peak_bytes": doc.get("processes", {}).get(
                        "sampled_rss_peak_bytes"
                    ),
                }
            )
    if len(calls) != config["expected_calls"]:
        raise ValueError("CALL_COUNT_MISMATCH")
    summary = {}
    for stage in ("q3", "q5"):
        selected = [c for c in calls if c["stage"] == stage]
        values = sorted(c["latency_ms"] for c in selected if c["latency_ms"] is not None)
        summary[stage] = {
            "calls": len(selected),
            "timeouts": sum(c["timed_out"] for c in selected),
            "budgets_ms": sorted({c["timeout_ms"] for c in selected}),
            "latency_min_ms": min(values) if values else None,
            "latency_median_ms": statistics.median(values) if values else None,
            "latency_p95_nearest_rank_ms": values[math.ceil(0.95 * len(values)) - 1]
            if values
            else None,
            "latency_max_ms": max(values) if values else None,
        }
    fresh(output)
    result = {
        "schema_version": "q-demo.closeout-timeouts.v1",
        "calls": calls,
        "summary": summary,
        "resources": resources,
        "new_generation_calls": 0,
        "budgets_changed": False,
        "llm_used": 0,
        "cause": "DEADLINE_REACHED_WITHOUT_COMPLETE_PROVIDER_RESPONSE",
        "load_queue_generation_breakdown": "UNKNOWN_NOT_RECORDED",
        "runner_absence_proves_model_not_running": False,
        "formal_run_allowed": False,
        "source_file_hashes": files,
    }
    save(output / "RESULT.json", result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["conformance", "context", "timeouts"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    config = json.loads(pinned(args.input, args.input_sha256))
    result = {"conformance": conformance, "context": context, "timeouts": timeouts}[args.command](
        config, args.output
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"runs", "failures", "calls", "source_file_hashes"}
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
