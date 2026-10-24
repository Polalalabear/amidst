"""Read-only baseline/production metadata checks; never approval or production."""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path, PurePosixPath


class PreflightError(ValueError):
    pass


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_pinned(path, expected_sha256, *, maximum=2_097_152):
    """Only explicit, bounded regular JSON metadata; reject parents/leaf symlinks."""
    path = Path(path)
    if (
        not path.is_absolute()
        or path.resolve() != path
        or path.suffix not in {".json", ".jsonl"}
        or not isinstance(expected_sha256, str)
        or not re.fullmatch("[0-9a-f]{64}", expected_sha256)
    ):
        raise PreflightError("CANONICAL_JSON_AND_FILE_PIN_REQUIRED")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise PreflightError("METADATA_SIZE_OR_TYPE")
        raw = stream.read(maximum + 1)
    if len(raw) != info.st_size or sha(raw) != expected_sha256:
        raise PreflightError("METADATA_PIN_MISMATCH")
    return raw


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise PreflightError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def invalid(_):
        raise PreflightError("NONFINITE_JSON")

    data = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    json.dumps(data, allow_nan=False)  # Includes exponent overflow, e.g. 1e999.
    return data


def metadata_ref(root, relative):
    """Resolve a declared metadata ref, without scanning or following private refs."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise PreflightError("RELATIVE_METADATA_REF_REQUIRED")
    parts = PurePosixPath(relative)
    forbidden = {"gt", "ground_truth", "private_evaluation", "human_review", "review_only"}
    if (
        parts.is_absolute()
        or parts.as_posix() != relative
        or ".." in parts.parts
        or forbidden.intersection(p.lower() for p in parts.parts)
        or parts.name == "persons.sim.json"
        or parts.name.startswith("event_")
    ):
        raise PreflightError("FORBIDDEN_METADATA_REF")
    path = Path(root) / relative
    if path.resolve() != path or not path.is_relative_to(root):
        raise PreflightError("METADATA_REF_OUTSIDE_ROOT")
    return path


def inspect_protocol(path, pin, *, repo=None, data_root=None, free_bytes=None):
    """Report facts/missing inputs. A receipt hash never grants human approval."""
    raw = read_pinned(path, pin)
    doc = strict_json(raw)
    if not isinstance(doc, dict) or doc.get("schema_version") != "q-demo.baseline-protocol.v1":
        raise PreflightError("PROTOCOL_VERSION")
    checks = []

    def add(item, status, reason):
        checks.append({"item": item, "status": status, "reason": reason})

    add("protocol_bytes", "VERIFIED", pin)
    add("protocol_status", "UNRESOLVED", str(doc.get("status")))
    gates = doc.get("formal_run", {}).get("required_gates", {})
    if not isinstance(gates, dict) or not gates:
        raise PreflightError("REQUIRED_GATES_MISSING")
    for name, row in gates.items():
        # Even a declaration APPROVED remains evidence for independent review.
        add("gate:" + name, "UNRESOLVED", "HUMAN_APPROVAL_SCOPE_NOT_VERIFIED")
        if data_root and row.get("receipt_ref") and row.get("receipt_sha256"):
            receipt = read_pinned(
                metadata_ref(Path(data_root), row["receipt_ref"]), row["receipt_sha256"]
            )
            add("receipt_bytes:" + name, "VERIFIED", sha(receipt))
    bindings = doc.get("input_bindings", {})
    camera_ids, interval = (
        bindings.get("authorized_camera_ids"),
        bindings.get("authorized_source_range_us"),
    )
    scoped = (
        isinstance(bindings.get("run_id"), str)
        and bool(bindings["run_id"])
        and isinstance(camera_ids, list)
        and bool(camera_ids)
        and all(isinstance(x, str) and x for x in camera_ids)
        and len(set(camera_ids)) == len(camera_ids)
        and isinstance(interval, list)
        and len(interval) == 2
        and all(type(x) is int for x in interval)
        and 0 <= interval[0] < interval[1]
    )
    add(
        "run_camera_time_scope",
        "VERIFIED" if scoped else "UNRESOLVED",
        "DECLARED_SCOPE_ONLY_NOT_AUTHORIZATION" if scoped else "NO_FROZEN_RUN_CAMERA_TIME",
    )
    for name, row in bindings.get("hashes", {}).items():
        if data_root and row.get("ref") and row.get("file_sha256"):
            raw = read_pinned(
                metadata_ref(Path(data_root), row["ref"]), row["file_sha256"], maximum=16_777_216
            )
            add("binding:" + name, "VERIFIED", sha(raw))
        else:
            add("binding:" + name, "UNRESOLVED", "MISSING_EXPLICIT_METADATA_REF_OR_PIN")
    if repo:
        for name, row in doc.get("source_references", {}).items():
            commit, relative = row.get("commit"), row.get("path")
            if (
                not isinstance(commit, str)
                or not re.fullmatch("[0-9a-f]{40}", commit)
                or not isinstance(relative, str)
                or relative.startswith("-")
                or ".." in PurePosixPath(relative).parts
            ):
                raise PreflightError("INVALID_GIT_SOURCE_REF")
            result = subprocess.run(
                ["git", "show", commit + ":" + relative], cwd=repo, capture_output=True
            )
            if result.returncode:
                add("source:" + name, "UNRESOLVED", "GIT_OBJECT_NOT_AVAILABLE")
            elif sha(result.stdout) != row.get("file_sha256"):
                raise PreflightError("SOURCE_FILE_PIN_MISMATCH")
            else:
                add("source:" + name, "VERIFIED", row["file_sha256"])
    available = shutil.disk_usage(Path(path).parent).free if free_bytes is None else free_bytes
    if type(available) is not int or available < 0:
        raise PreflightError("INVALID_DISK_MEASUREMENT")
    low_disk = available < 8 * 1024**3
    add(
        "disk_capacity",
        "FAIL" if low_disk else "VERIFIED",
        "BELOW_8_GIB" if low_disk else "AT_LEAST_8_GIB",
    )
    return {
        "schema_version": "q-demo.production-preflight.v1",
        "status": "BLOCKED",
        "protocol_file_sha256": pin,
        "checks": checks,
        "free_disk_bytes": available,
        "production_performed": False,
        "human_approval_verified": False,
        "formal_run_allowed": False,
        "reason": "DISK_SPACE_BELOW_8_GIB"
        if low_disk
        else "INDEPENDENT_APPROVAL_AND_FREEZE_REQUIRED",
    }


def inspect_review_metadata(path, pin):
    """Read five locked safe metadata files; never editable returns or image data."""
    path = Path(path)
    manifest = strict_json(read_pinned(path, pin))
    allowed = (
        "provenance/build_sources.json",
        "provenance/camera_catalog.json",
        "provenance/region_graph.json",
        "provenance/camera_graph.json",
        "provenance/hsv_config.json",
    )
    verified, docs = {}, {}
    for relative in allowed:
        expected = manifest["files"][relative]
        raw = read_pinned(metadata_ref(path.parent, relative), expected)
        verified[relative] = sha(raw)
        docs[relative] = strict_json(raw)
    build = docs[allowed[0]]
    if build.get("gt_read") is not False:
        raise PreflightError("REVIEW_METADATA_GT_BOUNDARY")
    cameras = docs[allowed[1]]["cameras"]
    return {
        "manifest_file_sha256": pin,
        "locked_metadata_file_hashes": verified,
        "static_source_sha256": build["static_source_sha256"],
        "source_asset_verified_now": False,
        "camera_calibration_sha256": {
            row["camera_id"]: row["calibration_sha256"] for row in cameras
        },
        "camera_ids": sorted(row["camera_id"] for row in cameras),
        "formal_run_bindings": "UNRESOLVED",
        "human_approval_verified": False,
        "editable_returns_read": False,
        "proposed_production_design": {
            "status": "REPORTED_EXISTING_D70_DESIGN_NOT_FROZEN_RUN_SCOPE",
            "source_ref": "https://github.com/Polalalabear/amidst/issues/115#issuecomment-6334859555",
            "runs": [
                {"label": "A4", "camera_count": 4, "camera_ids": None, "run_id": None},
                {"label": "B4", "camera_count": 5, "camera_ids": None, "run_id": None},
            ],
            "duration_us": 30_000_000,
            "source_fps": 5,
            "image_size_px": [960, 540],
            "clock_mapping_sha256": None,
            "rgb_manifest_sha256": None,
            "detection_index_sha256": None,
        },
    }
