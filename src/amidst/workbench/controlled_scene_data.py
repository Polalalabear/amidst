"""Pinned safe-only controlled-run inputs. No production/evaluation import or discovery."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import ValidationError

from amidst.domain.camera import Camera
from amidst.engineering.registry import content_hash
from amidst.workbench.scene_errors import DataIntegrityError

SHA = re.compile(r"[a-f0-9]{64}\Z")
PRIVATE_KEYS = frozenset({
    "persons", "persons.sim", "person_sim_id", "actor_id", "actor_ids", "trajectory",
    "route", "route_waypoints_m", "designed_blind_intervals", "observation_windows",
    "separation_requirements", "random_seed", "generator_script", "production_manifest",
    "gt", "ground_truth", "mask", "depth", "renderer_visibility", "private_locator", "local_path",
    "event_script", "designed_visibility", "persons.sim.json", "seed",
})
REQUIRED_FILES = frozenset({"scene_static", "cameras", "event_query", "rgb_index",
                            "runtime_profile"})
SAFE_FILENAMES = {
    "scene_static": {"scene_static.json"}, "cameras": {"cameras.json"},
    "event_query": {"event_A.query.json", "event_B1.query.json", "event_query.json"},
    "rgb_index": {"rgb_index.json"}, "runtime_profile": {"runtime_profile.json"},
}
RGB_INDEX_ADAPTER_NAME = "controlled-scene.rgb-index-adapter"
RGB_INDEX_ADAPTER_VERSION = "d57-v1"
# Server-owned, exact D55 byte hashes. Neither requests nor manifests can add pins.
D55_RGB_INDEX_PINS = {
    "9e43237e9c9ac9ea4f2bc97f65e49103a0ec3946b1b555b9d7fbf59850e97d47":
        "ctrl-lcorr-s1-a-5fps-v1-r001",
    "a5392a6fc5b51257adb82827df376f42290690cbdb52160888eb241f256ecc39":
        "ctrl-lcorr-s1-b1-5fps-v1-r001",
}
D55_RGB_INDEX_METADATA = frozenset({
    "scene_id", "scene_version", "source_sha256", "data_origin", "sampling",
    "rgb_ref_base", "expected_grid",
})


class RequiredInputUnavailable(RuntimeError):
    """Missing technical inputs cannot yield READY; this is not missing RGB."""


def checked_hash(value: object) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise DataIntegrityError("INVALID_HASH_PIN")
    return value


def safe_relative(value: str) -> tuple[str, ...]:
    if (not isinstance(value, str) or not value or "\\" in value or "%" in value
            or "\x00" in value or value.startswith("/")
            or any(p in {"", ".", ".."} for p in value.split("/"))):
        raise DataIntegrityError("PATH_REJECTED")
    return PurePosixPath(value).parts


def read_regular(root: Path, relative: str, *, max_bytes: int = 16 * 1024 * 1024) -> bytes:
    """Open relative components without following symlinks (including the trusted root)."""
    parts = safe_relative(relative)
    root = root.absolute()
    descriptors = []
    try:
        fd = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY)
        descriptors.append(fd)
        for component in (*root.parts[1:], *parts[:-1]):
            fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            descriptors.append(fd)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        descriptors.append(fd)
        import stat

        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > max_bytes:
            raise DataIntegrityError("PATH_REJECTED")
        chunks, count = [], 0
        while chunk := os.read(fd, min(65536, max_bytes + 1 - count)):
            chunks.append(chunk)
            count += len(chunk)
            if count > max_bytes:
                raise DataIntegrityError("PATH_REJECTED")
        return b"".join(chunks)
    except FileNotFoundError:
        raise
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise DataIntegrityError("PATH_REJECTED") from error
        raise
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def parse_json(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise DataIntegrityError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def reject(_: str) -> None:
        raise DataIntegrityError("NONFINITE_JSON")

    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=reject)
        if not isinstance(value, dict):
            raise DataIntegrityError("INVALID_JSON_OBJECT")
        # Also reject numeric overflow such as 1e999.
        content_hash(value)
        return value
    except (UnicodeError, ValueError) as error:
        if isinstance(error, DataIntegrityError):
            raise
        raise DataIntegrityError("INVALID_JSON") from error


def no_private(value: Any) -> None:
    if isinstance(value, dict):
        if PRIVATE_KEYS.intersection(value):
            raise DataIntegrityError("PRIVATE_FIELD_IN_SAFE_INPUT")
        for item in value.values():
            no_private(item)
    elif isinstance(value, list):
        for item in value:
            no_private(item)


def pinned_json(root: Path, path: str, digest: str) -> dict[str, Any]:
    raw = read_regular(root, path)
    if hashlib.sha256(raw).hexdigest() != checked_hash(digest):
        raise DataIntegrityError("SAFE_FILE_HASH_MISMATCH")
    value = parse_json(raw)
    no_private(value)
    return value


@dataclass(frozen=True)
class RGBIndexAdaptation:
    document: dict[str, Any]
    receipt: dict[str, Any]


def adapt_rgb_index(raw: bytes, *, expected_file_sha256: str) -> RGBIndexAdaptation:
    """D57: normalize only approved D55 bytes in memory; never guess between keys.

    Native records[] needs its normal manifest pin, not a legacy D55 pin. A
    frames[] input additionally needs the exact v1 schema and server-owned D55
    byte hash/run binding. Returned provenance always refers to original bytes.
    This pure entry point is also reusable by offline validators/receipts.
    """
    source_hash = hashlib.sha256(raw).hexdigest()
    if source_hash != checked_hash(expected_file_sha256):
        raise DataIntegrityError("SAFE_FILE_HASH_MISMATCH")
    value = parse_json(raw)
    no_private(value)
    if value.get("schema_version") != "controlled-scene.rgb-index.v1":
        raise DataIntegrityError("RGB_INDEX_SCHEMA_VERSION_UNSUPPORTED")
    has_frames, has_records = "frames" in value, "records" in value
    if has_frames == has_records:
        raise DataIntegrityError("RGB_INDEX_COLLECTION_KEY_MISMATCH")
    source_collection = "frames" if has_frames else "records"
    if not isinstance(value[source_collection], list):
        raise DataIntegrityError("RGB_INDEX_SCHEMA_MISMATCH")
    if has_frames:
        if (source_hash not in D55_RGB_INDEX_PINS
                or value.get("run_id") != D55_RGB_INDEX_PINS[source_hash]):
            raise DataIntegrityError("LEGACY_RGB_INDEX_PIN_NOT_APPROVED")
        value["records"] = value.pop("frames")
    return RGBIndexAdaptation(value, {
        "adapter_name": RGB_INDEX_ADAPTER_NAME,
        "adapter_version": RGB_INDEX_ADAPTER_VERSION,
        "source_file_sha256": source_hash,
        "source_schema_version": value["schema_version"],
        "source_collection": source_collection,
        "target_collection": "records",
        "adapted": has_frames,
        "normalized_content_sha256": content_hash(value),
    })


@dataclass(frozen=True)
class RunRegistration:
    """Server-owned; never accepted in an API request."""

    run_root: Path
    manifest_sha256: str
    scene_id: str
    run_id: str
    source_sha256: str


@dataclass(frozen=True)
class CalibrationAdapter:
    optics: Camera
    optical_metadata: dict[str, Any]
    run_binding: dict[str, Any]


def adapt_calibration(optics: dict[str, Any], binding: dict[str, Any], *,
                      run_id: str, clock_id: str, duration_s: float) -> CalibrationAdapter:
    """Preserve the optical hash across clocks; no Office constants or transposes."""
    optical_fields = {
        "schema_version", "camera_id", "camera_to_world", "convention", "fx", "fy", "cx", "cy",
        "width", "height", "pixel_origin", "pixel_aspect_xy", "render_resolution_percentage",
        "shift_x", "shift_y", "sensor_fit", "sensor_width_mm", "sensor_height_mm",
        "focal_length_mm", "clip_start", "clip_end", "distortion", "camera_model", "floor_id",
        "zone_id", "meters_per_unit", "static_validity", "calibration_sha256",
    }
    if set(optics) != optical_fields or set(binding) != {
        "run_id", "camera_id", "clock_id", "valid_time_range_s", "visibility_index_ref",
        "binding_sha256",
    }:
        raise DataIntegrityError("CALIBRATION_SCHEMA_MISMATCH")
    if content_hash({k: v for k, v in optics.items() if k != "calibration_sha256"}) != (
        checked_hash(optics["calibration_sha256"])
    ):
        raise DataIntegrityError("CALIBRATION_HASH_MISMATCH")
    if content_hash({k: v for k, v in binding.items() if k != "binding_sha256"}) != (
        checked_hash(binding["binding_sha256"])
    ):
        raise DataIntegrityError("CALIBRATION_BINDING_HASH_MISMATCH")
    if (binding["run_id"] != run_id or binding["clock_id"] != clock_id
            or binding["camera_id"] != optics["camera_id"]
            or binding["valid_time_range_s"] != [0, duration_s]):
        raise DataIntegrityError("CALIBRATION_BINDING_MISMATCH")
    if (optics["convention"] != "BLENDER_NEG_Z_UP_Y"
            or optics["pixel_origin"] != "TOP_LEFT_CONTINUOUS"
            or optics["meters_per_unit"] != 1 or optics["camera_model"] != "PINHOLE"
            or optics["distortion"] is not None):
        raise DataIntegrityError("CALIBRATION_CONVENTION_MISMATCH")
    if (optics["sensor_fit"] not in {"AUTO", "HORIZONTAL", "VERTICAL"}
            or any(type(optics[k]) not in {int, float} or optics[k] <= 0
                   for k in ("sensor_width_mm", "sensor_height_mm", "focal_length_mm"))
            or not isinstance(optics["pixel_aspect_xy"], list)
            or len(optics["pixel_aspect_xy"]) != 2
            or any(type(v) not in {int, float} or v <= 0 for v in optics["pixel_aspect_xy"])
            or optics["render_resolution_percentage"] != 100
            or not optics["static_validity"]):
        raise DataIntegrityError("CALIBRATION_METADATA_INVALID")
    keys = set(Camera.model_fields)
    try:
        camera = Camera.model_validate({k: v for k, v in optics.items() if k in keys})
    except ValidationError as error:
        raise DataIntegrityError("INVALID_CALIBRATION") from error
    matrix = camera.camera_to_world
    columns = [[matrix[i][j] for i in range(3)] for j in range(3)]
    def dot(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))
    determinant = sum(matrix[0][i] * (
        matrix[1][(i + 1) % 3] * matrix[2][(i + 2) % 3]
        - matrix[1][(i + 2) % 3] * matrix[2][(i + 1) % 3]
    ) for i in range(3))
    if (list(matrix[3]) != [0, 0, 0, 1] or abs(determinant - 1) > 1e-8
            or any(abs(dot(a, b) - int(i == j)) > 1e-8
                   for i, a in enumerate(columns) for j, b in enumerate(columns))):
        raise DataIntegrityError("NONRIGID_CAMERA_TRANSFORM")
    return CalibrationAdapter(camera, optics, binding)


@dataclass
class SafeRun:
    registration: RunRegistration
    manifest: dict[str, Any]
    files: dict[str, dict[str, Any]]
    calibrations: dict[str, CalibrationAdapter]
    input_adapter_receipts: tuple[dict[str, Any], ...] = ()
    rgb_camera_ids: frozenset[str] | None = None

    @property
    def camera_ids(self) -> frozenset[str]:
        return (self.rgb_camera_ids if self.rgb_camera_ids is not None
                else frozenset(self.calibrations))

    def rgb_record(self, camera_id: str, index: int) -> dict[str, Any] | None:
        return next((r for r in self.files["rgb_index"]["records"]
                     if r["camera_id"] == camera_id and r["frame_index"] == index), None)

    def read_rgb(self, camera_id: str, index: int) -> bytes | None:
        if (camera_id not in self.camera_ids or type(index) is not int
                or not 0 <= index < self.manifest["sampling"]["sample_count_per_camera"]):
            raise ValueError("RGB_SCOPE_DENIED")
        record = self.rgb_record(camera_id, index)
        if record is None:
            return None
        try:
            raw = read_regular(self.registration.run_root, record["rgb_ref"])
        except FileNotFoundError as error:
            raise DataIntegrityError("PINNED_RGB_RECORD_MISSING") from error
        if hashlib.sha256(raw).hexdigest() != record["file_sha256"]:
            raise DataIntegrityError("RGB_RECORD_HASH_MISMATCH")
        return raw


def load_safe_run(registration: RunRegistration, *, purpose: str = "FULL_RUNTIME") -> SafeRun:
    """Read only explicitly pinned safe files. Missing technical index is fatal to readiness."""
    try:
        if purpose == "RGB_PLAYBACK":
            from amidst.workbench.controlled_scene_rgb_data import load_rgb_playback

            return load_rgb_playback(registration)
        if purpose != "FULL_RUNTIME":
            raise ValueError("UNSUPPORTED_SAFE_LOAD_PURPOSE")
        return _load_safe_run(registration)
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        if isinstance(error, DataIntegrityError):
            raise
        raise DataIntegrityError("SAFE_SCHEMA_MISMATCH") from error
    except FileNotFoundError as error:
        raise RequiredInputUnavailable("REQUIRED_SAFE_INPUT_UNAVAILABLE") from error


def _load_safe_run(reg: RunRegistration) -> SafeRun:
    m = pinned_json(reg.run_root, "safe_bundle/manifest.json", reg.manifest_sha256)
    allowed = {"schema_version", "scene_id", "scene_version", "run_id", "clock_id",
               "source_sha256", "sampling", "allowlist", "config_pins", "data_origin"}
    if set(m) != allowed or m["schema_version"] != "controlled-scene.manifest.v1":
        raise DataIntegrityError("MANIFEST_SCHEMA_MISMATCH")
    if (m["scene_id"] != reg.scene_id or m["run_id"] != reg.run_id
            or m["source_sha256"] != checked_hash(reg.source_sha256)
            or m["clock_id"] != "clock:" + reg.run_id):
        raise DataIntegrityError("SOURCE_RUN_PIN_MISMATCH")
    if m["data_origin"] != "ACTUAL_BLENDER":
        raise DataIntegrityError("REAL_RUN_ORIGIN_MISMATCH")
    sampling = m["sampling"]
    if set(sampling) != {"fps", "image_size_px", "format", "sampling_version", "duration_s",
                         "sample_count_per_camera", "last_timestamp_s"}:
        raise DataIntegrityError("INVALID_SAMPLING")
    fps, duration = Fraction(str(sampling["fps"])), Fraction(str(sampling["duration_s"]))
    count = fps * duration
    if (fps <= 0 or duration <= 0 or count.denominator != 1
            or sampling["sample_count_per_camera"] != int(count)
            or Fraction(str(sampling["last_timestamp_s"])) != (count - 1) / fps
            or sampling["format"] != "PNG_RGB8" or sampling["image_size_px"] != [960, 540]):
        raise DataIntegrityError("INVALID_SAMPLING")
    entries = m["allowlist"]
    if not REQUIRED_FILES.issubset(entries):
        raise RequiredInputUnavailable("REQUIRED_SAFE_INDEX_UNAVAILABLE")
    paths, files = set(), {}
    adapter_receipts: tuple[dict[str, Any], ...] = ()
    for kind, entry in entries.items():
        if kind not in REQUIRED_FILES and not kind.startswith("geometry:"):
            raise DataIntegrityError("SAFE_ALLOWLIST_REJECTED")
        if set(entry) != {"path", "file_sha256"}:
            raise DataIntegrityError("SAFE_ALLOWLIST_REJECTED")
        path = entry["path"]
        parts = safe_relative(path)
        if (parts[0] != "safe_bundle" or len(parts) != 2 or path in paths
                or not path.endswith(".json")):
            raise DataIntegrityError("SAFE_ALLOWLIST_REJECTED")
        names = SAFE_FILENAMES.get(kind, {kind.removeprefix("geometry:") + ".geometry.json",
                                          "geometry.json"})
        if parts[-1] not in names:
            raise DataIntegrityError("SAFE_ALLOWLIST_REJECTED")
        paths.add(path)
        if kind == "rgb_index":
            adapted = adapt_rgb_index(read_regular(reg.run_root, path),
                                      expected_file_sha256=entry["file_sha256"])
            files[kind] = adapted.document
            adapter_receipts = (adapted.receipt,)
        else:
            files[kind] = pinned_json(reg.run_root, path, entry["file_sha256"])
    pins = m["config_pins"]
    if set(pins) != {"body_prior_sha256", "detector_config_sha256"}:
        raise DataIntegrityError("CONFIG_PIN_MISSING")
    for pin in pins.values():
        checked_hash(pin)
    static = files["scene_static"]
    if (static["schema_version"] != "controlled-scene.static.v1"
            or static["scene_id"] != reg.scene_id or static["scene_version"] != m["scene_version"]
            or static["length_unit"] != "m" or static["time_unit"] != "s"
            or static["world_axes"] != "BLENDER_Z_UP_RIGHT_HANDED"):
        raise DataIntegrityError("STATIC_SOURCE_MISMATCH")
    checked_hash(static["source_static_sha256"])
    floors = {f["floor_id"]: f for f in static["floors"]}
    if not floors or len(floors) != len(static["floors"]):
        raise DataIntegrityError("FLOOR_BINDING_MISMATCH")
    for floor in floors.values():
        if (floor["source_static_sha256"] != static["source_static_sha256"]
                or not floor["support_surface_ids"] or not floor["approved_scope_ref"]):
            raise DataIntegrityError("FLOOR_BINDING_MISMATCH")
        plane = floor["support_plane"]
        if (len(plane["point_m"]) != 3 or len(plane["normal"]) != 3
                or abs(sum(float(x) ** 2 for x in plane["normal"]) - 1) > 1e-8):
            raise DataIntegrityError("INVALID_SUPPORT_PLANE")
    ids = set()
    for obj in static["objects"]:
        if obj["id"] in ids:
            raise DataIntegrityError("DUPLICATE_STATIC_ID")
        ids.add(obj["id"])
        required_object = {
            "id", "class", "source_mesh", "source_object_id", "geometry_ref", "geometry_sha256",
            "geometry_version", "geometry_encoding_version", "transform_applied", "bounds_m",
            "source_method", "allowed_purposes", "approval_status", "scope_ref", "approval_ref",
            "approval_sha256", "display_only",
        }
        if not required_object.issubset(obj):
            raise DataIntegrityError("STATIC_SCHEMA_INCOMPLETE")
        purposes = set(obj["allowed_purposes"])
        if (not purposes or not purposes.issubset({"WALKABILITY", "OCCLUSION", "COLLISION",
                                                  "VISIBILITY_INDEX", "DISPLAY"})
                or (obj["display_only"] and purposes != {"DISPLAY"})
                or obj["approval_status"] != "APPROVED"
                or obj["transform_applied"] != "WORLD_METRES"
                or not obj["scope_ref"] or not obj["approval_ref"] or not obj["source_object_id"]):
            raise DataIntegrityError("STATIC_PURPOSE_NOT_APPROVED")
        checked_hash(obj["approval_sha256"])
        geometry_key = "geometry:" + obj["id"]
        if (geometry_key not in files or obj["geometry_ref"] != entries[geometry_key]["path"]
                or obj["geometry_sha256"] != entries[geometry_key]["file_sha256"]
                or not files[geometry_key].get("vertices_m")
                or not files[geometry_key].get("faces")):
            raise DataIntegrityError("STATIC_GEOMETRY_UNAVAILABLE")
        geometry = files[geometry_key]
        vertices, faces = geometry["vertices_m"], geometry["faces"]
        if (any(not isinstance(v, list) or len(v) != 3
                or any(type(n) not in {int, float} for n in v) for v in vertices)
                or any(not isinstance(f, list) or len(f) < 3
                       or any(type(i) is not int or not 0 <= i < len(vertices) for i in f)
                       for f in faces)):
            raise DataIntegrityError("INVALID_MESH_GEOMETRY")
    if any(not set(f["support_surface_ids"]).issubset(ids) for f in floors.values()):
        raise DataIntegrityError("FLOOR_SUPPORT_GEOMETRY_UNAVAILABLE")
    camera_file = files["cameras"]
    cams = {c["camera_id"]: c for c in camera_file["cameras"]}
    bindings = {b["camera_id"]: b for b in camera_file["run_bindings"]}
    if (not cams or len(cams) != len(camera_file["cameras"])
            or len(bindings) != len(camera_file["run_bindings"]) or set(cams) != set(bindings)):
        raise DataIntegrityError("CAMERA_BINDING_MISMATCH")
    calibrated = {key: adapt_calibration(c, bindings[key], run_id=reg.run_id,
                                       clock_id=m["clock_id"], duration_s=float(duration))
                  for key, c in cams.items()}
    if any(c.optics.floor_id not in floors for c in calibrated.values()):
        raise DataIntegrityError("CAMERA_FLOOR_MISMATCH")
    if any([c.optics.width, c.optics.height] != sampling["image_size_px"]
           for c in calibrated.values()):
        raise DataIntegrityError("CALIBRATION_IMAGE_SIZE_MISMATCH")
    query = files["event_query"]
    if (set(query) != {"schema_version", "event_id", "run_id", "duration_s", "camera_ids",
                       "sampling_version", "suggested_queries"}
            or query["schema_version"] != "controlled-scene.event-query.v1"
            or query["run_id"] != reg.run_id or set(query["camera_ids"]) != set(cams)
            or query["duration_s"] != float(duration)
            or query["sampling_version"] != sampling["sampling_version"]):
        raise DataIntegrityError("QUERY_SCOPE_MISMATCH")
    profile = files["runtime_profile"]
    if (set(profile) != {"schema_version", "run_id", "clock_id", "sampling_version",
                         "camera_ids", "required_inputs", "api_available"}
            or profile["schema_version"] != "controlled-scene.runtime-profile.v1"
            or profile["run_id"] != reg.run_id or profile["clock_id"] != m["clock_id"]
            or profile["sampling_version"] != sampling["sampling_version"]
            or set(profile["camera_ids"]) != set(cams)
            or set(profile["required_inputs"]) != REQUIRED_FILES):
        raise DataIntegrityError("RUNTIME_PROFILE_MISMATCH")
    index = files["rgb_index"]
    index_keys = {"schema_version", "run_id", "clock_id", "records", "missing"}
    if adapter_receipts[0]["adapted"]:
        index_keys.update(D55_RGB_INDEX_METADATA)
        grid = index["expected_grid"]
        if (index["scene_id"] != reg.scene_id or index["scene_version"] != m["scene_version"]
                or index["source_sha256"] != reg.source_sha256
                or index["data_origin"] != m["data_origin"] or index["sampling"] != sampling
                or index["rgb_ref_base"] != "RUN_ROOT"
                or set(grid) != {"camera_ids", "frame_index_start", "frame_index_end_exclusive",
                                 "timestamp_rule"}
                or set(grid["camera_ids"]) != set(cams) or grid["frame_index_start"] != 0
                or grid["frame_index_end_exclusive"] != int(count)
                or grid["timestamp_rule"] != "frame_index / fps"):
            raise DataIntegrityError("RGB_INDEX_BINDING_MISMATCH")
    if (set(index) != index_keys
            or index["schema_version"] != "controlled-scene.rgb-index.v1"
            or index["run_id"] != reg.run_id or index["clock_id"] != m["clock_id"]):
        raise DataIntegrityError("RGB_INDEX_BINDING_MISMATCH")
    seen = set()
    for record in index["records"] + index["missing"]:
        key = record["camera_id"], record["frame_index"]
        if (key in seen or key[0] not in cams or type(key[1]) is not int
                or not 0 <= key[1] < count
                or Fraction(str(record["timestamp_s"])) != Fraction(key[1], 1) / fps):
            raise DataIntegrityError("RGB_INDEX_GRID_MISMATCH")
        seen.add(key)
        if "rgb_ref" in record:
            if set(record) != {"camera_id", "frame_index", "timestamp_s", "rgb_ref", "file_sha256"}:
                raise DataIntegrityError("RGB_INDEX_SCHEMA_MISMATCH")
            expected = f"rgb/{key[0]}/frame_{key[1]:06d}.png"
            if record["rgb_ref"] != expected:
                raise DataIntegrityError("RGB_PATH_REJECTED")
            checked_hash(record["file_sha256"])
        elif (set(record) != {"camera_id", "frame_index", "timestamp_s", "reason"}
              or record.get("reason") != "RGB_RECORD_ABSENT"):
            raise DataIntegrityError("RGB_MISSING_REASON_MISMATCH")
    if len(seen) != int(count) * len(cams):
        raise DataIntegrityError("RGB_INDEX_INCOMPLETE")
    return SafeRun(reg, m, files, calibrated, adapter_receipts)
