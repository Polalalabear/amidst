#!/usr/bin/env python3
"""QT-25-T checks; SYNTHETIC envelope is a test seam, not a receipt wire contract.

Without an explicitly selected decoder this exits INCOMPLETE. A checks PASS never
approves a parameter set, a source run, inference, or formal index acceptance.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import importlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys

KIT_COMMIT = "e1415f32a778f497bdd048d992440718bf0a9310"
KIT_PINS = {
    "src/amidst/evaluation/q1q5_conformance.py": "df0e5c62e97ce23950514eda0ddcabd2962bb8450e70edd3d4416c31aac39459",
    "src/amidst/evaluation/response_versions.py": "6c14b4a66b696c53aefe1d0fbcb5d19084a6a416342506d40114057e27384904",
    "src/amidst/contracts/q_demo/__init__.py": "082d2af0dcae52a30d02a5c9b8cb93b9f034aae744730da5df4a2bfbec770bc8",
    "src/amidst/contracts/q_demo/mini_schema.py": "07b2fa8fe958e3a9beee02b3933ab9ed4c59d662664d67f52c888a74b4f338a4",
    "src/amidst/contracts/q_demo/schemas/common.schema.json": "6cde5005412a4b55f7725a65713b468ca31380b80e296a2cdbcb2701637185fc",
    "src/amidst/contracts/q_demo/schemas/detection-index.v1.schema.json": "7b57ba14d5b62eb20593aa431acf5724eda3654fb6d5fe1a26f9938d5c7823e5",
    "src/amidst/contracts/q_demo/schemas/detection-record.schema.json": "23e69782f3c38e2a441c32f5fe2671626cce5615ebc9cfe66c4cede8c55e9a75",
}
KIT_CHECKS = {
    "DOCUMENT_LOADABLE", "SCHEMA_VALID", "NO_FORBIDDEN_CONTENT",
    "CONTENT_HASH_RECOMPUTE", "ID_DERIVED_FROM_HASH", "COMMON_GT_READ_FALSE",
    "INDEX_MANIFEST_RULES", "INDEX_RECORDS_FILE_HASH", "RECORDS_FRAME_STATE",
    "RECORDS_OBSERVATION_IDS", "RECORDS_INDEX_GRID", "RECORDS_COLOR_RULES",
    "RECORDS_MATCH_MANIFEST", "RECORDS_SCORE_FLOOR",
}
STAGES = {"import", "read", "hash", "forward", "hsv", "write"}
ROLES = {"index", "records", "detector_config", "hsv_config", "parameter_set", "run_manifest"}
FORBIDDEN = {
    "gt", "ground_truth", "groundtruth", "actor_id", "material_id", "trajectory",
    "trajectories", "renderer_trajectory", "visibility", "renderer_visibility",
    "depth", "script", "event_script", "persons.sim.json", "private_evaluation",
}


class CheckError(ValueError):
    pass


class Incomplete(CheckError):
    pass


def require(condition, message):
    if not condition:
        raise CheckError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value, exclude=()):
    body = {k: v for k, v in value.items() if k not in exclude}
    return sha(json.dumps(body, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode())


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def loads(raw):
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(CheckError("nonfinite JSON")))
    # Also reject exponent overflow.
    json.dumps(value, allow_nan=False)
    return value


def safe_content(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key).lower().replace("-", "_")
            require(lowered not in FORBIDDEN
                    and not {"trajectory", "trajectories", "visibility", "depth", "script"}.intersection(lowered.split("_")),
                    "forbidden content key: " + key)
            if lowered == "gt_read":
                require(key == "gt_read" and child is False and path[-1:] == ("provenance",),
                        "only provenance.gt_read=false is allowed")
            safe_content(child, path + (key,))
    elif isinstance(value, list):
        for child in value:
            safe_content(child, path)
    elif isinstance(value, str):
        require(not re.search(r"(?:^|[/\\])(?:gt|ground_truth|private_evaluation)(?:[/\\]|$)", value, re.I),
                "forbidden content source")
        require(not value.startswith(("/", "~/", "file://"))
                and not re.match(r"^[A-Za-z]:[\\/]", value), "private absolute path")


def read_relative(root, relative, *, suffixes=(".json", ".jsonl")):
    require(isinstance(relative, str) and relative, "relative metadata path required")
    path = PurePosixPath(relative)
    require(not path.is_absolute() and path.as_posix() == relative and ".." not in path.parts
            and "\\" not in relative and path.suffix in suffixes, "unsafe metadata path")
    target = root
    for part in path.parts:
        target = target / part
        require(not target.is_symlink(), "symlink rejected")
    require(target.is_file() and target.resolve().is_relative_to(root), "metadata missing/outside root")
    return target.read_bytes()


def load_pins(receipt, root):
    pins = receipt["pins"]
    require(set(pins) == ROLES, "complete exact byte-pin roles required")
    require(len({p["path"] for p in pins.values()}) == len(ROLES), "one file per role required")
    values, raw = {}, {}
    for role, pin in pins.items():
        require(set(pin) == {"path", "file_sha256"}, "unknown pin field")
        raw[role] = read_relative(root, pin["path"])
        require(sha(raw[role]) == pin["file_sha256"], role + " byte-pin mismatch")
        if role != "records":
            values[role] = loads(raw[role])
            safe_content(values[role])
    return values, raw


def checked_kit(kit_root):
    root = Path(kit_root).absolute()
    require(root.resolve() == root, "canonical kit root required")
    for path, digest in KIT_PINS.items():
        require(sha(read_relative(root, path, suffixes=(".py", ".json"))) == digest,
                "pinned #127 kit source mismatch: " + path)
    # Import only these two pinned checker modules. evaluation/__init__.py imports
    # unrelated trajectory metrics; none are needed to validate an index.
    def pinned_module(name, relative):
        if name in sys.modules:
            module = sys.modules[name]
            require(Path(module.__file__).resolve() == root / relative,
                    "kit module imported from different root")
            return module
        spec = importlib.util.spec_from_file_location(name, root / relative)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    pinned_module("amidst.evaluation.response_versions", "src/amidst/evaluation/response_versions.py")
    module = pinned_module("_amidst_index_receipt_pinned_kit", "src/amidst/evaluation/q1q5_conformance.py")
    for name, relative in (
        ("amidst.evaluation.response_versions", "src/amidst/evaluation/response_versions.py"),
        ("amidst.contracts.q_demo", "src/amidst/contracts/q_demo/__init__.py"),
        ("amidst.contracts.q_demo.mini_schema", "src/amidst/contracts/q_demo/mini_schema.py"),
    ):
        require(Path(importlib.import_module(name).__file__).resolve() == root / relative,
                "kit dependency imported from different root")
    return module


def validate_timings(timings):
    require(set(timings) == STAGES, "six timing categories required")
    for name, timing in timings.items():
        require(set(timing) == {"seconds", "source", "reason"}, "unknown timing field")
        value = timing["seconds"]
        if value is None:
            require(timing["source"] == "NOT_MEASURED" and isinstance(timing["reason"], str)
                    and timing["reason"].strip(), name + " null timing needs a reason")
        else:
            require(type(value) in (int, float) and math.isfinite(value) and value >= 0
                    and timing["source"] == "MEASURED" and timing["reason"] is None,
                    name + " timing must be measured, finite and nonnegative")


def validate_bindings(receipt, values, raw):
    index, run, params = (values[k] for k in ("index", "run_manifest", "parameter_set"))
    for key in ("run_id", "scene_id", "clock_id"):
        require(receipt[key] == run[key] == index[key], "single-run binding mismatch: " + key)
    require(run["fixture_role"] == "SYNTHETIC", "synthetic run required")
    require(params["fixture_role"] == "SYNTHETIC" and params["approval"]["status"] == "PROPOSED",
            "test-only parameters cannot claim approval")
    require(params["content_sha256"] == canonical(params, ("content_sha256", "parameter_set_id")),
            "parameter_set canonical hash mismatch")
    entries = params["parameters"]
    require(len({p["name"] for p in entries}) == len(entries), "duplicate parameter")
    require(all(p["status"] == "PROPOSED" for p in entries), "synthetic parameter status")
    parameters = {p["name"]: p["value"] for p in entries}
    require(set(parameters) == {"index_score_floor", "stride_samples", "index_grid_origin_frame", "hsv_config"},
            "explicit index/HSV parameters required")
    from amidst.q1q5.hsv_color import HSVConfig
    hsv = HSVConfig(**values["hsv_config"])
    require(parameters["hsv_config"] == values["hsv_config"], "HSV parameter bytes/value mismatch")
    require(index["color_method"]["content_sha256"] == hsv.content_sha256
            and index["color_method"]["version"] == hsv.version, "HSV method hash/version mismatch")
    vocabulary = index["color_method"]["color_vocabulary"]
    require(vocabulary == {"version": hsv.version, "labels": list(hsv.bands),
                           "content_sha256": canonical({"version": hsv.version, "labels": list(hsv.bands)})},
            "HSV vocabulary mismatch")
    detector = index["detector"]
    require(detector["config_sha256"] == canonical({
        "model_config_sha256": sha(raw["detector_config"]),
        "index_score_floor": parameters["index_score_floor"], "nms": detector["nms"]}),
        "detector config wrapper hash mismatch")
    require(detector["index_score_floor"] == parameters["index_score_floor"], "score-floor binding mismatch")
    require(index["rgb_index_sha256"] == run["rgb_index_sha256"], "RGB index source binding mismatch")
    require(index["sampling"]["stride_samples"] == parameters["stride_samples"], "stride mismatch")
    require(all(c["index_grid_origin_frame"] == parameters["index_grid_origin_frame"]
                for c in index["sampling"]["per_camera"]), "grid origin mismatch")


def coverage(receipt, run, index, records):
    sampling = run["sampling"]
    count = sampling["sample_count_per_camera"]
    require(type(count) is int and count > 0, "positive source frame count required")
    interval = Fraction(1_000_000) / Fraction(str(sampling["fps"]))
    duration = Fraction(str(sampling["duration_s"])) * 1_000_000
    require(interval.denominator == duration.denominator == 1 and count * interval == duration,
            "run source grid inconsistent")
    interval, duration = int(interval), int(duration)
    cameras = run["camera_ids"]
    require(cameras and len(cameras) == len(set(cameras)), "unique run cameras required")
    declarations = receipt["coverage"]
    require(set(declarations) == set(cameras), "coverage camera set mismatch")
    grid = {c["camera_id"]: c for c in index["sampling"]["per_camera"]}
    require(len(grid) == len(cameras) and set(grid) == set(cameras), "index camera set mismatch")
    rows = {(r["camera_id"], r["frame_index"]): r for r in records}
    require(len(rows) == len(records), "duplicate frame")
    require(all(c in grid and type(f) is int and 0 <= f < count for c, f in rows), "out-of-run frame")
    summary = {}
    for camera in cameras:
        cam = grid[camera]
        require(cam["source_frame_interval_us"] == interval, "source interval mismatch")
        declaration = declarations[camera]
        require(set(declaration) == {"expected_frames", "not_evaluated"}
                and declaration["expected_frames"] == count, "coverage frame count mismatch")
        gaps = set()
        for gap in declaration["not_evaluated"]:
            require(set(gap) == {"state", "frame_range", "reason"}
                    and gap["state"] == "NOT_EVALUATED" and isinstance(gap["reason"], str)
                    and gap["reason"].strip(), "NOT_EVALUATED reason required")
            a, b = gap["frame_range"]
            require(type(a) is int and type(b) is int and 0 <= a < b <= count, "gap outside run")
            cells = set(range(a, b))
            require(not cells & gaps, "overlapping gap declarations")
            gaps |= cells
        actual_gaps, present, inferred = set(), 0, 0
        for frame in range(count):
            row = rows.get((camera, frame))
            on_grid = frame >= cam["index_grid_origin_frame"] and (
                frame - cam["index_grid_origin_frame"]) % cam["stride_samples"] == 0
            if row is None:
                actual_gaps.add(frame)
            else:
                present += 1
                require(row["timestamp_us"] == frame * interval, "record timestamp off source grid")
                if row["frame_state"] in {"MISSING", "NOT_INFERRED"}:
                    actual_gaps.add(frame)
                if row["frame_state"] == "INFERRED":
                    inferred += 1
            inside = any(a <= frame * interval < b for a, b in cam["inferred_ranges_us"])
            if on_grid:
                require(inside == (row is not None and row["frame_state"] == "INFERRED"),
                        "coarse inferred range overclaims run coverage")
        for name in ("sampled_ranges_us", "inferred_ranges_us"):
            require(all(0 <= a < b <= duration and a % interval == b % interval == 0
                        for a, b in cam[name]), "index range outside source grid")
        require(gaps == actual_gaps, "missing or spurious NOT_EVALUATED declaration")
        summary[camera] = {"expected_frames": count, "recorded_frames": present,
                           "inferred_frames": inferred, "not_evaluated_frames": len(gaps)}
    return summary


def check_receipt(receipt_path, index_root, *, decoder=None, kit_root=None):
    if decoder is None:
        raise Incomplete("formal receipt decoder UNKNOWN; select SYNTHETIC_TEST_ONLY_V1 only for fixtures")
    if decoder != "SYNTHETIC_TEST_ONLY_V1":
        raise Incomplete("unknown/unadopted receipt decoder")
    root = Path(index_root).absolute()
    require(root.resolve() == root and root.is_dir(), "canonical metadata root required")
    receipt_path = Path(receipt_path).absolute()
    require(not receipt_path.is_symlink() and receipt_path.resolve() == receipt_path
            and receipt_path.is_file(), "regular canonical receipt file required")
    receipt = loads(receipt_path.read_bytes())
    require(set(receipt) == {"format", "fixture_role", "run_id", "scene_id", "clock_id", "pins", "coverage", "timings"},
            "unknown/missing synthetic envelope field")
    require(receipt["format"] == decoder and receipt["fixture_role"] == "SYNTHETIC", "not a synthetic envelope")
    safe_content(receipt)
    values, raw = load_pins(receipt, root)
    validate_timings(receipt["timings"])
    validate_bindings(receipt, values, raw)
    from amidst.q1q5.store import DocumentPin, JsonRunStore
    pins = receipt["pins"]
    store = JsonRunStore(root, {
        "index": DocumentPin(pins["index"]["path"], pins["index"]["file_sha256"], "q-demo.detection-index.v1"),
        "records": DocumentPin(pins["records"]["path"], pins["records"]["file_sha256"], "q-demo.detection-record.v1"),
    })
    snapshot = store.load_detection_index("index")
    records = list(snapshot.records)
    safe_content(records)
    summary = coverage(receipt, values["run_manifest"], snapshot.manifest, records)
    kit = checked_kit(kit_root or Path(__file__).resolve().parents[1])
    results = []
    # The pinned kit samples at most 2000 records per Doc. Run every chunk so
    # schema/color/grid/floor checks cover every record; reader checks global order.
    for offset in range(0, len(records), 2000):
        docs = [kit.Doc(pins["index"]["path"], "detection_index", snapshot.manifest, sha(raw["index"])),
                kit.Doc(pins["records"]["path"], "detection_records", records[offset:offset+2000], sha(raw["records"]))]
        batch = kit.run_checks(docs, only=KIT_CHECKS)
        require({r["check_id"] for r in batch} == KIT_CHECKS, "missing pinned-kit check/context")
        require(all(r["status"] == "PASS" for r in batch), "#127 kit rejected: " + json.dumps(
            [r for r in batch if r["status"] != "PASS"], sort_keys=True))
        results.extend(batch)
    require(results, "no #127 checks executed")
    return {"status": "PASS_SYNTHETIC_ONLY", "authority_verified": False,
            "formal_acceptance": "NOT_EVALUATED", "reader": "store.JsonRunStore.load_detection_index",
            "kit_commit": KIT_COMMIT, "kit_checks_passed": len(results), "coverage": summary}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--index-root", type=Path, required=True)
    parser.add_argument("--decoder", help="Explicit test decoder; no formal default exists")
    parser.add_argument("--kit-root", type=Path, help="Root containing the exact pinned #127 sources")
    args = parser.parse_args(argv)
    try:
        result = check_receipt(args.receipt, args.index_root, decoder=args.decoder, kit_root=args.kit_root)
        code = 0
    except Incomplete as exc:
        result, code = {"status": "INCOMPLETE", "authority_verified": False, "reason": str(exc)}, 2
    except (ValueError, TypeError, KeyError, IndexError, OSError, ImportError, ZeroDivisionError) as exc:
        result, code = {"status": "FAIL", "authority_verified": False, "reason": str(exc)}, 1
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
