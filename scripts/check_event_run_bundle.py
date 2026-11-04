#!/usr/bin/env python3
"""Read-only CX-7 bundle checks: explicit TEST-ONLY contract or D119 profile.

D119 checks mechanical consistency only, never human approval or product authority.
No profile and no TEST-ONLY options remains CONTRACT_UNSELECTED.
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
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from amidst.q1q5.clock_mapping import ClockMapping, ClockMappingError

MAX_FILE = 16_777_216
CHECKER_VERSION = "cx7t-synthetic-v1"
R004_IMAGE_SIZE = (960, 540)
R004_BINDINGS = {
    "freeze_sha256": "ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb",
    "g4_head": "0502225bb16f117014fd875fc7a9281220ede484",
    "g4_decisions_sha256": "9d99f87ea007e1988797e50fa28e70f67e6973578bc15ef3f440ba4f4d8bc76c",
    "source_sha256": "466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b",
    "catalog_sha256": "3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f",
    "freeze_ref": "https://github.com/Polalalabear/amidst/issues/93#issuecomment-6556609083",
    "render_ref": "https://github.com/Polalalabear/amidst/issues/93#issuecomment-6579052576",
    "projection_ref": "https://github.com/Polalalabear/amidst/issues/93#issuecomment-6593904034",
}
R004_RUNS = (
    dict(label="A4-1", run_id="ctrl-lcorr-s1-a4-5fps-v1-r004",
         camera_ids=["CAM_ENTRY", "CAM_EXT_CAR", "CAM_EXT_CLEAR", "CAM_W1"],
         source_duration_us=50_000_000, frame_count=250, clock_ref="clocks/r004_a4_v1.json",
         clock_sha256="a6d6df46110b5b8bc7874792c9bc0b469dd099eb7fc24f2806b7933d7e08079a",
         run_declaration_sha256="2f9c77fac097098787a1b23602cc59868677d655a1c4f92c0831c21f9dd0a0b9",
         producer_script_sha256="d304d0fcc17932e11dd54120fc06f88c96e28dbb07713c75e388e7664a4824a9",
         source_inventory_sha256="907615d4645507182590fbbc9c6d3e9213deef60c28fb07c9b5514773b60b939"),
    dict(label="B4-1", run_id="ctrl-lcorr-s1-b4-5fps-v1-r004",
         camera_ids=["CAM_BRANCH", "CAM_R101_IN", "CAM_W1", "CAM_W2", "CAM_WIDE"],
         source_duration_us=42_000_000, frame_count=210, clock_ref="clocks/r004_b4_v1.json",
         clock_sha256="3a39443753120c102acaf23ed7c166048157f4ae805d92ff12f36e45a31c35d4",
         run_declaration_sha256="bec1b2829ef2eabcdac74ea9123725ee7e9b486364c27c360b45e70eb707b598",
         producer_script_sha256="c1e7dcd1461f646c532fdd85d6f59c81ae9155cc14bcaf3c3b0a5ba2865c8345",
         source_inventory_sha256="2b797d69ac6c400f58bffac74496066f455c9b47173350e29498530d9bfb4173"),
)
PRIVATE_PREFIXES = ("trajectory", "trajectories", "visibility", "visibilities",
                    "depth", "actor", "script", "groundtruth")
SHA = re.compile(r"[0-9a-f]{64}")
D84_RECEIPT_SHA256 = "3ade8183442781066b062d62f22e7af2335923fe73ead76b0fa5df5f9e0a81f5"
D84_RECEIPT = ROOT / "docs/history/R004_CAMERA_CATALOG_FREEZE_D84_20261027.json"


def private_token(value):
    # D105 B-12 / #394 P1: retain naming boundaries before case folding.
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", value)
    separated = re.sub(r"(?<=[A-Za-z])(?=[0-9])|(?<=[0-9])(?=[A-Za-z])", " ", separated)
    tokens = re.split(r"[^a-z0-9]+", separated.casefold())
    # Prefixes catch depthmap/scripts; embedded substrings in description/factory
    # remain benign. A benign token never exempts a later private token.
    return (any(token == "gt" or token.startswith(PRIVATE_PREFIXES) for token in tokens)
            or any(left == "ground" and right.startswith("truth")
                   for left, right in zip(tokens, tokens[1:])))


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
        require(not private_token(name) and "private" not in name.lower(), "SAFE_PATH_REJECTED")
    result = root / name
    require(result.resolve() == result and result.is_relative_to(root), "SYMLINK_REJECTED")
    return result


def private_keys(value, safe_root):
    if isinstance(value, dict):
        for key, child in value.items():
            require(not private_token(key), "PRIVATE_CONTENT_IN_SAFE")
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
        require(not private_token(name) and "private" not in name.lower(), "PRIVATE_CONTENT_IN_SAFE")
        if path.is_file() and name != "manifest.json":
            actual.add(name)
    for name in files:
        require(not private_token(name) and "private" not in name.lower(), "PRIVATE_CONTENT_IN_SAFE")
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


def exact_keys(doc, keys, code):
    require(isinstance(doc, dict) and set(doc) == set(keys), code)


def inspect_png(raw):
    """Bounded RGB8 PNG decoding; ancillary text/EXIF and unknown chunks fail."""
    require(raw[:8] == b"\x89PNG\r\n\x1a\n", "PNG_INVALID")
    offset, kinds, compressed = 8, [], []
    allowed = {b"IHDR", b"IDAT", b"IEND", b"cHRM", b"gAMA", b"oFFs", b"pHYs", b"sRGB"}
    while offset < len(raw):
        require(offset + 12 <= len(raw), "PNG_INVALID")
        size = struct.unpack(">I", raw[offset:offset + 4])[0]
        kind = raw[offset + 4:offset + 8]
        end = offset + size + 12
        require(end <= len(raw) and kind in allowed, "PNG_CHUNK_REJECTED")
        data = raw[offset + 8:end - 4]
        require(zlib.crc32(kind + data) == struct.unpack(">I", raw[end - 4:end])[0], "PNG_CRC_INVALID")
        if kind == b"IHDR":
            require(not kinds and size == 13, "PNG_INVALID")
            width, height, bits, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", data)
            require((width, height) == R004_IMAGE_SIZE
                    and (bits, color, compression, filtering, interlace) == (8, 2, 0, 0, 0), "PNG_FORMAT_MISMATCH")
        elif kind == b"IDAT":
            require(kinds and kinds[-1] in {b"IHDR", b"IDAT", b"cHRM", b"gAMA", b"oFFs", b"pHYs", b"sRGB"}
                    and (b"IDAT" not in kinds or kinds[-1] == b"IDAT"), "PNG_INVALID")
            compressed.append(data)
        elif kind == b"IEND":
            require(size == 0 and compressed and end == len(raw), "PNG_INVALID")
        kinds.append(kind)
        offset = end
    require(kinds and kinds[0] == b"IHDR" and kinds[-1] == b"IEND", "PNG_INVALID")
    stride = R004_IMAGE_SIZE[0] * 3 + 1
    expected = stride * R004_IMAGE_SIZE[1]
    try:
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(b"".join(compressed), expected + 1)
    except zlib.error as exc:
        raise BundleError("PNG_INVALID") from exc
    require(len(pixels) == expected and decoder.eof and not decoder.unused_data
            and not decoder.unconsumed_tail and all(pixels[i] <= 4 for i in range(0, expected, stride)), "PNG_INVALID")


def _inspect_r004(bundle, receipt_path):
    # The original freeze keeps its historical flags. Its hash is a binding,
    # never an approval decoder. No renderer source, GT or G4 file is opened.
    pinned(ROOT / "docs/engineering/R004_A4B4_SCRIPT_FREEZE_20261029.json",
           R004_BINDINGS["freeze_sha256"], code="FREEZE_PIN_MISMATCH")
    receipt_path = Path(receipt_path).absolute()
    receipt_raw = read(receipt_path)
    receipt = parse(receipt_raw)
    require(isinstance(receipt, dict) and receipt.get("profile") == "r004-a4b4"
            and receipt.get("classification") == "ENGINEERING" and receipt.get("projection") == "D119"
            and receipt.get("human_approval_verified") is False
            and receipt.get("allowed_purposes") == [], "D119_RECEIPT_INVALID")
    require(receipt.get("bindings") == R004_BINDINGS, "D119_BINDING_MISMATCH")
    disk = {key: df_available(receipt.get(key)) for key in ("before_df_k", "after_df_k")}
    require(min(disk.values()) >= 8 * 1024**3, "DISK_BELOW_8_GIB")
    evidence = receipt.get("runs")
    require(isinstance(evidence, list) and len(evidence) == 2
            and all(isinstance(run, dict) for run in evidence), "D119_RUN_RECEIPT_INVALID")
    by_id = {run.get("run_id"): run for run in evidence}
    require(set(by_id) == {scope["run_id"] for scope in R004_RUNS}, "RUN_SET_MISMATCH")
    source_frames = {}
    for scope in R004_RUNS:
        record = by_id[scope["run_id"]]
        require(all(record.get(key) == scope[key] for key in (
            "clock_sha256", "run_declaration_sha256", "producer_script_sha256", "source_inventory_sha256"))
            and record.get("render_before_source_sha256") == R004_BINDINGS["source_sha256"]
            and record.get("render_after_source_sha256") == R004_BINDINGS["source_sha256"], "D119_RUN_PIN_MISMATCH")
        available = record.get("disk_min_available_bytes")
        require(type(available) is int and available >= 8 * 1024**3, "DISK_BELOW_8_GIB")
        inventory = pinned(relative(receipt_path.parent, record.get("source_inventory_ref")),
                           scope["source_inventory_sha256"], code="SOURCE_INVENTORY_PIN_MISMATCH")
        require(isinstance(inventory, list)
                and len(inventory) == len(scope["camera_ids"]) * scope["frame_count"], "SOURCE_INVENTORY_INVALID")
        indexed = {}
        for item in inventory:
            exact_keys(item, {"camera_id", "frame_index", "filename", "file_sha256", "source_time_us"},
                       "SOURCE_INVENTORY_INVALID")
            camera, index = item["camera_id"], item["frame_index"]
            require(camera in scope["camera_ids"] and type(index) is int and 0 <= index < scope["frame_count"]
                    and (camera, index) not in indexed
                    and item["filename"] == f"media/{camera}/{index:06d}.png"
                    and type(item["source_time_us"]) is int and item["source_time_us"] == index * 200_000
                    and isinstance(item["file_sha256"], str) and SHA.fullmatch(item["file_sha256"]),
                    "SOURCE_INVENTORY_INVALID")
            indexed[camera, index] = item["file_sha256"]
        source_frames[scope["run_id"]] = indexed

    bundle = Path(bundle).absolute()
    require(bundle.resolve() == bundle, "SYMLINK_REJECTED")
    safe = relative(bundle, "safe_bundle")
    require(safe.is_dir(), "FILE_MISSING")
    current = os.statvfs(safe)
    available_now = current.f_bavail * current.f_frsize
    require(available_now >= 8 * 1024**3, "DISK_BELOW_8_GIB")
    manifest = pinned(safe / "manifest.json", receipt.get("safe_manifest_sha256"))
    exact_keys(manifest, {"files", "runs"}, "SAFE_MANIFEST_KEYS_REJECTED")
    run_refs = [f"runs/{scope['label']}.json" for scope in R004_RUNS]
    require(isinstance(manifest["runs"], list) and len(manifest["runs"]) == 2
            and set(manifest["runs"]) == set(run_refs), "RUN_SET_MISMATCH")
    expected_files = {"provenance/camera_catalog.json", *run_refs,
                      *(scope["clock_ref"] for scope in R004_RUNS)}
    for scope in R004_RUNS:
        expected_files.update(f"rgb/{scope['run_id']}/{camera}/frame_{i:06d}.png"
                              for camera in scope["camera_ids"] for i in range(scope["frame_count"]))
    files = manifest["files"]
    require(isinstance(files, dict) and set(files) == expected_files, "SAFE_FILE_SET_MISMATCH")
    expected_dirs = {parent.as_posix() for name in expected_files
                     for parent in PurePosixPath(name).parents if parent != PurePosixPath(".")}
    actual_files, actual_dirs = set(), set()
    for directory, directories, filenames in os.walk(safe, followlinks=False):
        for name in directories + filenames:
            path = Path(directory) / name
            require(not path.is_symlink(), "SYMLINK_REJECTED")
            info = path.lstat()
            ref = path.relative_to(safe).as_posix()
            if stat.S_ISDIR(info.st_mode):
                actual_dirs.add(ref)
            else:
                require(stat.S_ISREG(info.st_mode), "FILE_SIZE_OR_TYPE")
                actual_files.add(ref)
    require(actual_dirs == expected_dirs and actual_files == expected_files | {"manifest.json"},
            "SAFE_FILE_SET_MISMATCH")
    documents = {}
    for name in sorted(expected_files):
        raw = read(relative(safe, name, safe=True))
        require(isinstance(files[name], str) and SHA.fullmatch(files[name])
                and digest(raw) == files[name], "FILE_SHA256_MISMATCH")
        if name.endswith(".png"):
            inspect_png(raw)
        else:
            documents[name] = parse(raw)
    require(files["provenance/camera_catalog.json"] == R004_BINDINGS["catalog_sha256"], "CATALOG_FREEZE_MISMATCH")
    summaries = []
    for scope in R004_RUNS:
        run = documents[f"runs/{scope['label']}.json"]
        exact_keys(run, {"run_id", "label", "camera_ids", "catalog_sha256", "clock_ref", "sampling", "frames"},
                   "RUN_KEYS_REJECTED")
        exact_keys(run["sampling"], {"fps"}, "SAMPLING_KEYS_REJECTED")
        require(run["run_id"] == scope["run_id"] and run["label"] == scope["label"]
                and isinstance(run["camera_ids"], list) and run["camera_ids"] == scope["camera_ids"]
                and type(run["sampling"]["fps"]) is int and run["sampling"]["fps"] == 5,
                "FROZEN_RUN_SCOPE_MISMATCH")
        require(run["catalog_sha256"] == R004_BINDINGS["catalog_sha256"], "CATALOG_FREEZE_MISMATCH")
        require(run["clock_ref"] == scope["clock_ref"]
                and files[scope["clock_ref"]] == scope["clock_sha256"], "CLOCK_PIN_MISMATCH")
        try:
            clock = ClockMapping.from_document(documents[scope["clock_ref"]], expected_run_id=scope["run_id"])
        except ClockMappingError as exc:
            raise BundleError("CLOCK_INVALID") from exc
        require(clock.duration_us == scope["source_duration_us"], "FROZEN_RUN_SCOPE_MISMATCH")
        frames = run["frames"]
        require(isinstance(frames, list) and len(frames) == len(scope["camera_ids"]) * scope["frame_count"],
                "FRAME_GRID_INCOMPLETE")
        seen = set()
        for frame in frames:
            exact_keys(frame, {"camera_id", "frame_index", "filename", "file_sha256"}, "FRAME_KEYS_REJECTED")
            camera, index = frame["camera_id"], frame["frame_index"]
            require(camera in scope["camera_ids"] and type(index) is int and 0 <= index < scope["frame_count"]
                    and (camera, index) not in seen, "FRAME_GRID_INCOMPLETE")
            seen.add((camera, index))
            name = f"rgb/{scope['run_id']}/{camera}/frame_{index:06d}.png"
            require(frame["filename"] == name and frame["file_sha256"] == files[name]
                    and files[name] == source_frames[scope["run_id"]][camera, index], "FRAME_PIN_MISMATCH")
        summaries.append({"run_id": scope["run_id"], "label": scope["label"], "frame_count": len(frames),
                          "clock_sha256": scope["clock_sha256"],
                          "render_min_available_bytes": by_id[scope["run_id"]]["disk_min_available_bytes"]})
    return {"status": "PASS", "profile": "r004-a4b4", "run_count": 2, "frame_count": 2050,
            "runs": summaries, "disk_available_bytes": disk, "current_disk_available_bytes": available_now,
            "safe_manifest_sha256": receipt["safe_manifest_sha256"], "receipt_file_sha256": digest(receipt_raw),
            "bindings": R004_BINDINGS}


def inspect_bundle(bundle, receipt, *, profile=None, contract_path=None, contract_sha256=None):
    production = profile == "r004-a4b4" and contract_path is None and contract_sha256 is None
    try:
        if production:
            result = _inspect_r004(bundle, receipt)
        else:
            require(profile is not None, "CONTRACT_UNSELECTED")
            result = _inspect(bundle, receipt, profile, contract_path, contract_sha256)
    except BundleError as exc:
        result = {"status": "FAIL", "profile": profile, "code": str(exc)}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        result = {"status": "FAIL", "profile": profile, "code": "INPUT_INVALID"}
    return {**result, "checker_version": "cx7-d119-v1" if production else CHECKER_VERSION,
            "authority_verified": False, "render_authorized": False,
            "formal_run_allowed": False, "production_contract": "UNSELECTED",
            "human_approval_verified": False, "allowed_purposes": [],
            **({"classification": "ENGINEERING", "projection": "D119"} if production else {})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["r004-a4b4", "l2"])
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--contract-options", type=Path, help="Explicit TEST-ONLY external projection")
    parser.add_argument("--contract-sha256", help="SHA-256 of the explicit contract file bytes")
    args = parser.parse_args()
    result = inspect_bundle(args.bundle, args.receipt, profile=args.profile,
                            contract_path=args.contract_options, contract_sha256=args.contract_sha256)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in {"SYNTHETIC_VALID", "PASS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
