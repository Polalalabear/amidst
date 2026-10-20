"""Explicit r003 RGB-playback scope. Never upgrades geometry or runtime authority."""

from fractions import Fraction
from pathlib import Path

from amidst.engineering.registry import content_hash
from amidst.workbench.controlled_scene_data import (
    D55_RGB_INDEX_METADATA,
    RunRegistration,
    SafeRun,
    adapt_rgb_index,
    checked_hash,
    pinned_json,
    read_regular,
)
from amidst.workbench.scene_errors import DataIntegrityError

SCENE_ID = "controlled-l-corridor"
SOURCE_SHA256 = "6e7de38dc069d330e0ffbb6c0051cdab304566fdbb7e3e8dfb429af863ae6d8e"
RUN_PINS = {
    "ctrl-lcorr-s1-a-5fps-v1-r001":
        "26465eb77cc5f4f3b6a13f9dec661fd06987655974dda781b58eb9c749c44976",
    "ctrl-lcorr-s1-b1-5fps-v1-r001":
        "8645f531994b7dd73e4abd6be6bd9056e89a39ad429c0ab1105991ac58395e08",
}


def registrations(repo: Path) -> tuple[RunRegistration, ...]:
    """Fixed server-owned locator and pins; no discovery, browser paths or re-pinning."""
    return tuple(RunRegistration(
        repo / "data/pilot/controlled_scene_v1/runs" / run, pin, SCENE_ID, run, SOURCE_SHA256
    ) for run, pin in RUN_PINS.items())


def load_rgb_playback(reg: RunRegistration) -> SafeRun:
    """Read four manifest-listed JSONs; do not open geometry or production/evaluation files.

    NOT_EVALUATED geometry and float32 optics remain unchanged. They are not
    projection-approved by this adapter; calibrations is deliberately empty.
    """
    m = pinned_json(reg.run_root, "safe_bundle/manifest.json", reg.manifest_sha256)
    if (set(m) != {"schema_version", "scene_id", "scene_version", "run_id", "clock_id",
                   "source_sha256", "sampling", "allowlist", "geometry_files", "data_origin",
                   "runtime_readiness"}
            or m["schema_version"] != "controlled-scene.manifest.v1"
            or m["scene_id"] != reg.scene_id or m["run_id"] != reg.run_id
            or m["source_sha256"] != checked_hash(reg.source_sha256)
            or m["clock_id"] != "clock:" + reg.run_id or m["data_origin"] != "ACTUAL_BLENDER"
            or m["scene_version"] != 1 or m["runtime_readiness"] != "NOT_READY"):
        raise DataIntegrityError("RGB_PLAYBACK_MANIFEST_MISMATCH")
    sampling = m["sampling"]
    if set(sampling) != {"fps", "image_size_px", "format", "sampling_version", "duration_s",
                         "sample_count_per_camera", "last_timestamp_s"}:
        raise DataIntegrityError("INVALID_SAMPLING")
    fps, duration = Fraction(str(sampling["fps"])), Fraction(str(sampling["duration_s"]))
    count = fps * duration
    if (fps <= 0 or duration <= 0 or count.denominator != 1
            or type(sampling["sample_count_per_camera"]) is not int
            or sampling["sample_count_per_camera"] != int(count)
            or Fraction(str(sampling["last_timestamp_s"])) != (count - 1) / fps
            or sampling["image_size_px"] != [960, 540] or sampling["format"] != "PNG_RGB8"):
        raise DataIntegrityError("INVALID_SAMPLING")
    if not isinstance(m["allowlist"], list) or len(m["allowlist"]) != 4:
        raise DataIntegrityError("SAFE_ALLOWLIST_REJECTED")
    entries = {}
    for entry in m["allowlist"]:
        if (set(entry) != {"role", "filename", "file_sha256"}
                or entry["role"] not in {"scene_static", "cameras", "rgb_index", "runtime_profile"}
                or entry["role"] in entries or entry["filename"] != entry["role"] + ".json"):
            raise DataIntegrityError("SAFE_ALLOWLIST_REJECTED")
        entries[entry["role"]] = entry
    files = {role: pinned_json(reg.run_root, "safe_bundle/" + entry["filename"],
                               entry["file_sha256"])
             for role, entry in entries.items() if role != "rgb_index"}
    adapted = adapt_rgb_index(read_regular(reg.run_root, "safe_bundle/rgb_index.json"),
                              expected_file_sha256=entries["rgb_index"]["file_sha256"])
    files["rgb_index"] = index = adapted.document
    for value in (index, files["runtime_profile"]):
        if any(value[k] != m[k] for k in ("scene_id", "scene_version", "run_id", "clock_id",
                                          "source_sha256", "sampling", "data_origin")):
            raise DataIntegrityError("RGB_PLAYBACK_BINDING_MISMATCH")
    static = files["scene_static"]
    if (static["schema_version"] != "controlled-scene.static.v1"
            or static["scene_id"] != reg.scene_id or static["scene_version"] != m["scene_version"]
            or static["source_static_sha256"] != reg.source_sha256):
        raise DataIntegrityError("STATIC_SOURCE_MISMATCH")
    camera_file = files["cameras"]
    if (set(camera_file) != {"schema_version", "cameras", "run_bindings"}
            or camera_file["schema_version"] != "controlled-scene.cameras.v1"):
        raise DataIntegrityError("CAMERA_BINDING_MISMATCH")
    cameras = {c["camera_id"]: c for c in camera_file["cameras"]}
    bindings = {b["camera_id"]: b for b in camera_file["run_bindings"]}
    if (not bindings or len(cameras) != len(camera_file["cameras"])
            or len(bindings) != len(camera_file["run_bindings"])
            or not set(bindings).issubset(cameras)):
        raise DataIntegrityError("CAMERA_BINDING_MISMATCH")
    for key, b in bindings.items():
        c = cameras[key]
        if (content_hash({k: v for k, v in c.items() if k != "calibration_sha256"})
                != checked_hash(c["calibration_sha256"])
                or content_hash({k: v for k, v in b.items() if k != "binding_sha256"})
                != checked_hash(b["binding_sha256"])
                or b["run_id"] != reg.run_id or b["clock_id"] != m["clock_id"]
                or b["valid_time_range_s"] != [0, float(duration)]
                or [c["width"], c["height"]] != sampling["image_size_px"]):
            raise DataIntegrityError("CALIBRATION_BINDING_MISMATCH")
    profile = files["runtime_profile"]
    if (profile["schema_version"] != "controlled-scene.runtime-profile.v1"
            or set(profile["camera_ids"]) != set(bindings)
            or profile["rgb_index_schema_version"] != index["schema_version"]
            or profile["runtime_readiness"] != "NOT_READY"
            or profile["complete_runtime_bundle"] is not False
            or profile["missing_inputs_policy"] != "FAIL_CLOSED"):
        raise DataIntegrityError("RUNTIME_PROFILE_MISMATCH")
    grid = index["expected_grid"]
    if (set(index) != {"schema_version", "run_id", "clock_id", "records", "missing"}
            | D55_RGB_INDEX_METADATA or index["rgb_ref_base"] != "RUN_ROOT"
            or set(grid) != {"camera_ids", "frame_index_start", "frame_index_end_exclusive",
                             "timestamp_rule"}
            or set(grid["camera_ids"]) != set(bindings)
            or len(grid["camera_ids"]) != len(bindings)
            or grid["frame_index_start"] != 0 or grid["frame_index_end_exclusive"] != int(count)
            or grid["timestamp_rule"] != "frame_index / fps"):
        raise DataIntegrityError("RGB_INDEX_BINDING_MISMATCH")
    seen = set()
    for collection in ("records", "missing"):
        if not isinstance(index[collection], list):
            raise DataIntegrityError("RGB_INDEX_SCHEMA_MISMATCH")
        for record in index[collection]:
            camera, i = record["camera_id"], record["frame_index"]
            if (camera not in bindings or type(i) is not int or not 0 <= i < count
                    or (camera, i) in seen
                    or Fraction(str(record["timestamp_s"])) != Fraction(i, 1) / fps):
                raise DataIntegrityError("RGB_INDEX_GRID_MISMATCH")
            seen.add((camera, i))
            if collection == "records":
                if (set(record) != {"camera_id", "frame_index", "timestamp_s", "rgb_ref",
                                   "file_sha256"}
                        or record["rgb_ref"] != f"rgb/{camera}/frame_{i:06d}.png"):
                    raise DataIntegrityError("RGB_PATH_REJECTED")
                checked_hash(record["file_sha256"])
            elif (set(record) != {"camera_id", "frame_index", "timestamp_s", "reason"}
                  or record["reason"] != "RGB_RECORD_ABSENT"):
                raise DataIntegrityError("RGB_MISSING_REASON_MISMATCH")
    if len(seen) != int(count) * len(bindings):
        raise DataIntegrityError("RGB_INDEX_INCOMPLETE")
    return SafeRun(reg, m, files, {}, (adapted.receipt,), frozenset(bindings))
