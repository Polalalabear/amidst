#!/usr/bin/env python3
"""CX-7-T read-only mechanical checker; UNKNOWN production contracts fail closed.

Only the explicit SYNTHETIC_EVENT_BUNDLE_V1 TEST-ONLY projection is implemented.
It cannot authenticate human approval, authorize rendering, or unlock a real run.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from amidst.q1q5.clock_mapping import ClockMapping, ClockMappingError

MAX_FILE = 16_777_216
CHECKER_VERSION = "cx7t-synthetic-v1"
PRIVATE = re.compile(r"trajectory|visibility|depth|actor|script|ground.?truth|(?:^|[^a-z])gt(?:$|[^a-z])", re.I)
SHA = re.compile(r"[0-9a-f]{64}")
D84_RECEIPT_SHA256 = "3ade8183442781066b062d62f22e7af2335923fe73ead76b0fa5df5f9e0a81f5"
D84_RECEIPT = ROOT / "docs/history/R004_CAMERA_CATALOG_FREEZE_D84_20261027.json"


class BundleError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise BundleError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def invalid(_):
        raise BundleError("NONFINITE_JSON")

    doc = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    json.dumps(doc, allow_nan=False)
    return doc


def read(path, *, missing="FILE_MISSING"):
    path = Path(path)
    require(path.is_absolute() and path.resolve() == path, "SYMLINK_REJECTED")
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise BundleError(missing) from exc
    require(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_FILE, "FILE_SIZE_OR_TYPE")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        require(stat.S_ISREG(opened.st_mode) and opened.st_size <= MAX_FILE, "FILE_SIZE_OR_TYPE")
        raw = stream.read(MAX_FILE + 1)
    require(len(raw) == opened.st_size and opened.st_ino == info.st_ino
            and opened.st_dev == info.st_dev, "FILE_CHANGED_DURING_READ")
    return raw


def pinned(path, expected, *, code="FILE_SHA256_MISMATCH", missing="FILE_MISSING"):
    require(isinstance(expected, str) and SHA.fullmatch(expected), code)
    raw = read(path, missing=missing)
    require(digest(raw) == expected, code)
    return parse(raw)


def relative(root, name, *, safe=False):
    require(isinstance(name, str) and name and "\\" not in name, "SAFE_PATH_REJECTED")
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.as_posix() == name
            and ".." not in path.parts and "." not in path.parts, "SAFE_PATH_REJECTED")
    if safe:
        require(not PRIVATE.search(name) and "private" not in name.lower(), "SAFE_PATH_REJECTED")
    result = root / name
    require(result.resolve() == result and result.is_relative_to(root), "SYMLINK_REJECTED")
    return result


def private_keys(value, safe_root):
    if isinstance(value, dict):
        for key, child in value.items():
            require(not PRIVATE.search(key), "PRIVATE_CONTENT_IN_SAFE")
            if re.search(r"(?:^|_)(?:refs?|references?|paths?|filenames?)$", key, re.I):
                refs = child if isinstance(child, list) else [child]
                require(all(isinstance(ref, str) for ref in refs), "SAFE_PATH_REJECTED")
                for ref in refs:
                    relative(safe_root, ref, safe=True)
            private_keys(child, safe_root)
    elif isinstance(value, list):
        for child in value:
            private_keys(child, safe_root)


def external(contract, key, root, *, missing="FILE_MISSING"):
    ref = contract.get(key)
    require(isinstance(ref, dict) and set(ref) == {"filename", "file_sha256"},
            "EXTERNAL_REFERENCE_MISSING")
    doc = pinned(relative(root, ref["filename"]), ref["file_sha256"],
                 code="EXTERNAL_PIN_MISMATCH", missing=missing)
    require(isinstance(doc, dict) and doc.get("fixture_role") == "SYNTHETIC_ONLY",
            "SYNTHETIC_ROLE_REQUIRED")
    return doc, ref["file_sha256"]


def df_available(text):
    require(isinstance(text, str), "DF_K_INVALID")
    lines = [line.split() for line in text.splitlines() if line.strip()]
    require(len(lines) == 2 and len(lines[0]) >= 4
            and lines[0][:4] == ["Filesystem", "1024-blocks", "Used", "Available"]
            and len(lines[1]) >= 4 and lines[1][3].isdigit(), "DF_K_INVALID")
    return int(lines[1][3]) * 1024


def _inspect(bundle, receipt_path, profile, contract_path, contract_sha256):
    require(profile in {"r004-a4b4", "l2"}, "PROFILE_UNKNOWN")
    require(contract_path is not None and contract_sha256 is not None, "CONTRACT_UNSELECTED")
    # Accept repository-relative CLI paths without resolving away symlinks.
    contract_path = Path(contract_path).absolute()
    contract = pinned(contract_path, contract_sha256, code="CONTRACT_PIN_MISMATCH")
    require(isinstance(contract, dict)
            and contract.get("fixture_role") == "SYNTHETIC_ONLY"
            and contract.get("projection") == "SYNTHETIC_EVENT_BUNDLE_V1"
            and contract.get("profile") == profile, "CONTRACT_UNSELECTED")
    # This choice never represents U8 or a production G4/freeze decoder.
    plan, plan_sha = external(contract, "frozen_plan", contract_path.parent)
    require(plan.get("state") == "FROZEN_SYNTHETIC" and plan.get("profile") == profile,
            "FROZEN_PLAN_UNSELECTED")
    scopes = plan.get("runs")
    require(isinstance(scopes, list) and scopes and all(isinstance(s, dict) for s in scopes),
            "FROZEN_RUN_SCOPE_MISSING")
    scope_by_run = {s.get("run_id"): s for s in scopes}
    require(len(scope_by_run) == len(scopes) and all(isinstance(k, str) and k for k in scope_by_run),
            "FROZEN_RUN_SCOPE_MISSING")
    if profile == "r004-a4b4":
        require(len(scopes) == 2 and {s.get("label"): s.get("source_duration_us") for s in scopes}
                == {"A4-1": 50_000_000, "B4-1": 42_000_000}
                and all(type(s.get("fps")) is int and s["fps"] == 5 for s in scopes),
                "R004_D89_SCOPE_MISMATCH")
        freeze = pinned(D84_RECEIPT, D84_RECEIPT_SHA256, code="D84_RECEIPT_PIN_MISMATCH")
        catalog_sha = freeze["catalog_sha256"]  # Full D84 value, not a prefix.
    else:
        catalog_sha = None
    receipt = pinned(Path(receipt_path).absolute(), contract.get("receipt_file_sha256"),
                     code="RECEIPT_PIN_MISMATCH")
    require(isinstance(receipt, dict) and receipt.get("fixture_role") == "SYNTHETIC_ONLY"
            and receipt.get("profile") == profile, "SYNTHETIC_ROLE_REQUIRED")
    require(receipt.get("frozen_plan_sha256"), "FROZEN_PLAN_REFERENCE_MISSING")
    require(receipt["frozen_plan_sha256"] == plan_sha, "FROZEN_PLAN_REFERENCE_MISMATCH")
    require(receipt.get("authorization_ref"), "AUTHORIZATION_SOURCE_MISSING")
    authorization, _ = external(contract, "authorization", contract_path.parent)
    require(authorization.get("reference") == receipt["authorization_ref"]
            and authorization.get("frozen_plan_sha256") == plan_sha,
            "AUTHORIZATION_SCOPE_MISMATCH")
    graph_sha = plan.get("graph_sha256")
    require(isinstance(graph_sha, str) and SHA.fullmatch(graph_sha)
            and receipt.get("graph_sha256") == graph_sha, "GRAPH_PIN_MISMATCH")
    if profile == "r004-a4b4":
        require(contract.get("g4") and receipt.get("g4_receipt_sha256"), "G4_RECEIPT_MISSING")
        g4, g4_sha = external(contract, "g4", contract_path.parent, missing="G4_RECEIPT_MISSING")
        require(g4.get("decision") == "APPROVED" and g4.get("graph_sha256") == graph_sha
                and g4.get("frozen_plan_sha256") == plan_sha, "G4_SCOPE_MISMATCH")
        require(receipt["g4_receipt_sha256"] == g4_sha, "G4_RECEIPT_PIN_MISMATCH")
    disk = {key: df_available(receipt.get(key)) for key in ("before_df_k", "after_df_k")}
    require(min(disk.values()) >= 8 * 1024**3, "DISK_BELOW_8_GIB")
    bundle = Path(bundle).absolute()
    require(bundle.is_absolute() and bundle.resolve() == bundle, "SYMLINK_REJECTED")
    safe = relative(bundle, "safe_bundle")
    manifest = pinned(safe / "manifest.json", receipt.get("safe_manifest_sha256"))
    require(isinstance(manifest, dict) and manifest.get("fixture_role") == "SYNTHETIC_ONLY",
            "SYNTHETIC_ROLE_REQUIRED")
    private_keys(manifest, safe)
    files = manifest.get("files")
    require(isinstance(files, dict) and files, "SAFE_MANIFEST_INVALID")
    actual = set()
    require(safe.is_dir(), "FILE_MISSING")
    for path in safe.rglob("*"):
        require(not path.is_symlink(), "SYMLINK_REJECTED")
        name = path.relative_to(safe).as_posix()
        require(not PRIVATE.search(name) and "private" not in name.lower(), "PRIVATE_CONTENT_IN_SAFE")
        if path.is_file() and name != "manifest.json":
            actual.add(name)
    for name in files:
        require(not PRIVATE.search(name) and "private" not in name.lower(), "PRIVATE_CONTENT_IN_SAFE")
        relative(safe, name, safe=True)
    # Missing manifest entries get a direct FILE_MISSING diagnostic, not a skip.
    require(not actual - files.keys(), "SAFE_FILE_SET_MISMATCH")
    documents = {}
    for name, pin in files.items():
        path = relative(safe, name, safe=True)
        raw = read(path)
        require(isinstance(pin, str) and SHA.fullmatch(pin) and digest(raw) == pin,
                "FILE_SHA256_MISMATCH")
        if path.suffix == ".json":
            documents[name] = parse(raw)
            private_keys(documents[name], safe)
        else:
            require(path.suffix == ".png", "SAFE_FILE_TYPE_REJECTED")
    runs = manifest.get("runs")
    require(isinstance(runs, list) and len(runs) == len(set(runs)) == len(scopes), "RUN_SET_MISMATCH")
    seen_runs, clocks, used_frames = set(), set(), set()
    total = 0
    for run_ref in runs:
        relative(safe, run_ref, safe=True)
        run = documents.get(run_ref)
        require(isinstance(run, dict) and run.get("fixture_role") == "SYNTHETIC_ONLY", "RUN_INVALID")
        run_id = run.get("run_id")
        require(run_id in scope_by_run and run_id not in seen_runs, "RUN_SET_MISMATCH")
        seen_runs.add(run_id)
        scope = scope_by_run[run_id]
        camera_ids = run.get("camera_ids")
        require(isinstance(camera_ids, list) and camera_ids and all(isinstance(c, str) and c for c in camera_ids)
                and len(set(camera_ids)) == len(camera_ids) and camera_ids == scope.get("camera_ids")
                and run.get("label") == scope.get("label")
                and run.get("sampling", {}).get("fps") == scope.get("fps"), "FROZEN_RUN_SCOPE_MISMATCH")
        if catalog_sha is not None:
            require(run.get("catalog_sha256") == catalog_sha, "CATALOG_FREEZE_MISMATCH")
        clock_ref = run.get("clock_ref")
        relative(safe, clock_ref, safe=True)
        try:
            clock = ClockMapping.from_document(documents.get(clock_ref), expected_run_id=run_id)
        except ClockMappingError as exc:
            raise BundleError("CLOCK_INVALID") from exc
        require(clock.clock_id not in clocks, "CLOCK_REUSED")
        clocks.add(clock.clock_id)
        require(clock.duration_us == scope.get("source_duration_us"), "FROZEN_RUN_SCOPE_MISMATCH")
        fps = Fraction(str(run["sampling"]["fps"]))
        count = clock.duration_us * fps / 1_000_000
        require(fps > 0 and count.denominator == 1, "FRAME_COUNT_INVALID")
        frames = run.get("frames")
        require(isinstance(frames, list) and len(frames) == count * len(camera_ids), "FRAME_GRID_INCOMPLETE")
        seen = set()
        for frame in frames:
            require(isinstance(frame, dict), "FRAME_GRID_INCOMPLETE")
            camera, i = frame.get("camera_id"), frame.get("frame_index")
            require(isinstance(camera, str) and camera in camera_ids and type(i) is int
                    and 0 <= i < count and (camera, i) not in seen, "FRAME_GRID_INCOMPLETE")
            seen.add((camera, i))
            name = frame.get("filename")
            relative(safe, name, safe=True)
            require(name == f"rgb/{run_id}/{camera}/frame_{i:06d}.png"
                    and name not in used_frames and name in files
                    and frame.get("file_sha256") == files[name], "FRAME_PIN_MISMATCH")
            used_frames.add(name)
        total += len(frames)
    require(used_frames == {name for name in files if name.endswith(".png")}, "FRAME_FILE_SET_MISMATCH")
    return {"status": "SYNTHETIC_VALID", "profile": profile, "run_count": len(runs),
            "frame_count": total, "disk_available_bytes": disk,
            "contract_file_sha256": contract_sha256,
            "receipt_file_sha256": contract["receipt_file_sha256"]}


def inspect_bundle(bundle, receipt, *, profile, contract_path=None, contract_sha256=None):
    try:
        result = _inspect(bundle, receipt, profile, contract_path, contract_sha256)
    except BundleError as exc:
        result = {"status": "FAIL", "profile": profile, "code": str(exc)}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        result = {"status": "FAIL", "profile": profile, "code": "INPUT_INVALID"}
    return {**result, "checker_version": CHECKER_VERSION,
            "authority_verified": False, "render_authorized": False,
            "formal_run_allowed": False, "production_contract": "UNSELECTED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["r004-a4b4", "l2"], required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--contract-options", type=Path, help="Explicit TEST-ONLY external projection")
    parser.add_argument("--contract-sha256", help="SHA-256 of the explicit contract file bytes")
    args = parser.parse_args()
    result = inspect_bundle(args.bundle, args.receipt, profile=args.profile,
                            contract_path=args.contract_options, contract_sha256=args.contract_sha256)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "SYNTHETIC_VALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
