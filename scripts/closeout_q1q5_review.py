"""Bounded offline review closeout tools; outputs never grant runtime authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import socket
import statistics
import sys
import xml.etree.ElementTree as ET
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


def fixed_files(root: Path, manifest: dict, allowed_missing=()) -> list[str]:
    missing = []
    for name, digest in manifest["files"].items():
        path = root / relative(name)
        if not path.exists() and name in allowed_missing:
            missing.append(name)
        else:
            pinned(path, digest)
    return missing


def supplement(config: dict, output: Path) -> dict:
    original, returned = Path(config["original"]), Path(config["returned"])
    raw = pinned(original / "MANIFEST.json", config["manifest_sha256"])
    pinned(returned / "MANIFEST.json", config["manifest_sha256"])
    manifest = json.loads(raw)
    fixed_files(original, manifest)
    missing = fixed_files(returned, manifest, ("templates/審查表.csv",))
    csv_name = relative(config["returned_csv"])
    csv_raw = pinned(returned / csv_name, config["returned_csv_sha256"])
    owners = pinned(returned / "RETURN/OWNER_DECISIONS.csv", config["owner_decisions_sha256"])
    sys.path.insert(0, str(original / "tools"))
    from r004_prereview_pack import import_pack, verify_pack

    before = import_pack(original, config["manifest_sha256"], returned / csv_name)
    if before["status"] != "VALID":
        raise ValueError("RETURN_CSV_NOT_VALID")
    fresh(output)
    package = output / "package"
    package.mkdir(mode=0o700)
    for name in manifest["files"]:
        dest = package / relative(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original / name, dest)
    (package / "MANIFEST.json").write_bytes(raw)
    (package / "RETURN").mkdir(exist_ok=True)
    (package / csv_name).write_bytes(csv_raw)
    (package / "RETURN/OWNER_DECISIONS.csv").write_bytes(owners)
    verify_pack(package, config["manifest_sha256"])
    after = import_pack(package, config["manifest_sha256"], package / csv_name)
    if after["status"] != "VALID" or after["counts"] != before["counts"]:
        raise ValueError("SUPPLEMENT_IMPORT_MISMATCH")
    save(output / "IMPORT_RECEIPT.json", after)
    (output / "ISSUES.md").write_text(config["issue_summary"], encoding="utf-8")
    result = {
        "schema_version": "q-demo.closeout-review-supplement.v1",
        "version": "r004-review-return-supplement-v1",
        "original_missing": missing,
        "restored_files": missing,
        "fixed_files_verified": len(manifest["files"]),
        "csv_sha256": sha(csv_raw),
        "csv_counts": after["counts"],
        "package_manifest_sha256": config["manifest_sha256"],
        "original_modified": False,
        "returned_modified": False,
        "approval_granted": False,
        "formal_run_allowed": False,
    }
    save(output / "RESULT.json", result)
    delivery = {
        str(p.relative_to(output)): sha(p.read_bytes()) for p in output.rglob("*") if p.is_file()
    }
    save(output / "DELIVERY_MANIFEST.json", {"files": delivery})
    return result


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


def svg_bindings(svg_path: Path, camera: dict) -> list[dict]:
    zones = [("E", z["entry_zone_id"], z["roi_polygon_px"]) for z in camera["entry_zones"]]
    zones += [("X", z["exit_zone_id"], z["roi_polygon_px"]) for z in camera["exit_zones"]]
    result, current = [], None
    for element in ET.parse(svg_path).getroot():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "polygon":
            current = [
                [float(v) for v in pair.split(",")] for pair in element.attrib["points"].split()
            ]
        elif tag == "text":
            label = "".join(element.itertext()).strip()
            if not re.fullmatch(r"[EX]\d+", label):
                continue
            matches = [
                (zone_id, polygon)
                for role, zone_id, polygon in zones
                if role == label[0]
                and current is not None
                and len(polygon) == len(current)
                and all(
                    abs(a - b) <= 0.00051
                    for left, right in zip(polygon, current, strict=True)
                    for a, b in zip(left, right, strict=True)
                )
            ]
            if len(matches) != 1:
                raise ValueError("SVG_ROI_BINDING_AMBIGUOUS_OR_MISMATCH")
            result.append(
                {
                    "camera_id": camera["camera_id"],
                    "display_label": label,
                    "roi_id": matches[0][0],
                    "role": "ENTRY" if label[0] == "E" else "EXIT",
                    "roi_polygon_px": matches[0][1],
                }
            )
    if len(result) != len(zones) or len({r["roi_id"] for r in result}) != len(zones):
        raise ValueError("SVG_ROI_COVERAGE_MISMATCH")
    return result


def roi_map(config: dict, output: Path) -> dict:
    packet = Path(config["packet"])
    manifest = json.loads(pinned(packet / "MANIFEST.json", config["manifest_sha256"]))
    fixed_files(packet, manifest)
    graph = json.loads((packet / "provenance/camera_graph.json").read_text())
    bindings = []
    for camera in graph["cameras"]:
        name = "images/zones/" + camera["camera_id"] + ".svg"
        for row in svg_bindings(packet / name, camera):
            row["image_ref"] = name
            row["image_sha256"] = manifest["files"][name]
            bindings.append(row)
    by_id = {r["roi_id"]: r for r in bindings}
    transitions = []
    for transition in graph["transitions"]:
        ids = transition["via_exit_zone_ids"] + transition["to_entry_zone_ids"]
        if any(zone_id not in by_id for zone_id in ids):
            raise ValueError("TRANSITION_ROI_REFERENCE_MISSING")
        transitions.append(
            {
                "transition_id": transition["transition_id"],
                "from_camera_id": transition["from_camera_id"],
                "to_camera_id": transition["to_camera_id"],
                "via_exit_zone_ids": transition["via_exit_zone_ids"],
                "to_entry_zone_ids": transition["to_entry_zone_ids"],
                "display_refs": [
                    by_id[z]["camera_id"] + ":" + by_id[z]["display_label"] for z in ids
                ],
                "relation": transition["relation"],
                "status": "PROPOSED_NOT_APPROVED",
            }
        )
    for row in bindings:
        row["dependent_transition_ids"] = [
            t["transition_id"]
            for t in transitions
            if row["roi_id"] in t["via_exit_zone_ids"] + t["to_entry_zone_ids"]
        ]
    fresh(output)
    result = {
        "schema_version": "q-demo.closeout-roi-map.v1",
        "source_manifest_sha256": config["manifest_sha256"],
        "camera_graph_sha256": manifest["files"]["provenance/camera_graph.json"],
        "cameras": len(graph["cameras"]),
        "bindings": bindings,
        "transitions": transitions,
        "roi_count": len(bindings),
        "transition_count": len(transitions),
        "polygon_tolerance_px": 0.00051,
        "coordinates_changed": False,
        "approval_granted": False,
        "formal_run_allowed": False,
    }
    save(output / "RESULT.json", result)
    rows = [
        "# ROI display-to-ID map\n\n"
        "All coordinates are original PROPOSED pixels; this is not approval.\n",
        "| Camera | Label | Stable ROI ID | Dependent transitions |",
        "| --- | --- | --- | --- |",
    ]
    rows += [
        f"| {r['camera_id']} | {r['display_label']} | {r['roi_id']} | "
        f"{', '.join(r['dependent_transition_ids']) or 'NONE'} |"
        for r in bindings
    ]
    (output / "ROI_MAP.md").write_text("\n".join(rows) + "\n")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["conformance", "context", "timeouts", "supplement", "roi-map"]
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    config = json.loads(pinned(args.input, args.input_sha256))
    result = {
        "conformance": conformance,
        "context": context,
        "timeouts": timeouts,
        "supplement": supplement,
        "roi-map": roi_map,
    }[args.command](config, args.output)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                not in {
                    "runs",
                    "failures",
                    "calls",
                    "source_file_hashes",
                    "bindings",
                    "transitions",
                }
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
