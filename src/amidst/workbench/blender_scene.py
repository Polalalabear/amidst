"""Read-only Blender RGB imports and source-mesh context, without Agent decisions.

Materialization is an explicit local operation. It extracts only camera calibration,
RGB locators and source-bound floor/model evidence from existing exports; it never
renders, copies or saves a Blender scene. Runtime only opens the sanitized bundle.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
import struct
import zlib
from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from amidst.engineering.registry import content_hash, opaque_ref
from amidst.workbench.scenes import SceneAdapter
from amidst.workbench.source_presentation import METRES_PER_BU, SOURCE_SHA256, _clip_polygon

Json = dict[str, Any]
SITE_PINS = {
    "office": "2367ecc30c05740e64320130237878315034f61b6b91ec92979fd2deba8619c4",
    "classroom101": "f240deab853eef570ca8aeb43087a5930e310bf65fce755d9a3e10e033185091",
    "auditorium": "b298220834b8e7b239a59cd64628aedf555639a09cff801ec6f3849d122ca93f",
}
SITE_LABELS = {"office": "Office", "classroom101": "CLASS101", "auditorium": "Auditorium"}
_SUPPORT = "data/scene_audit/phase1_physical_policy_approval_20261006/floor_support_details.json.gz"
_GEOMETRY = "data/scene_audit/phase1_physical_policy_approval_20261006/source_evidence.json.gz"
_SCALE = "configs/architectural_scale_school_v3.json"
_PINS = {
    _SUPPORT: "6a37b041a368e3e576da4c3f3894708462c0504956f82ad599082acd816b23d0",
    _GEOMETRY: "6d30e591d6210707f2b6175bf96dc2fe2395fe0202b24bd0a6df7ee87a5d997c",
    _SCALE: "7e3615a3b0b4485585da9c0f7beefb96955517f7a321910fc008c041f99a3eaf",
}
_WALKABLE = {"office": "WALK_1F_OFFICE", "classroom101": "WALK_1F_CLASS101",
             "auditorium": "WALK_1F_AUDITORIUM"}
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_TEXT_CHUNKS = {b"tEXt", b"iTXt", b"zTXt"}
_SOURCE_TYPES = {"rgb": "ACTUAL_BLENDER_CAMERA_RENDER_SYNTHETIC",
                 "model": "SOURCE_EVALUATED_PARTIAL_DISPLAY_CONTEXT",
                 "perception": "PIXEL_BASELINE_ALGORITHM",
                 "projection": "SOURCE_CALIBRATION_AND_APPROVED_FLOOR_PLANE",
                 "behavior": "USER_SELECTED_INTENT_ONLY", "events": "NOT_GENERATED",
                 "agent": "NOT_USED"}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _fingerprint(path: Path) -> Json:
    stat = path.stat()
    return {"sha256": _file_sha(path), "byte_count": stat.st_size,
            "mtime_ns": stat.st_mtime_ns}


def strip_png_text(raw: bytes) -> bytes:
    """Remove PNG text metadata only; preserve every retained chunk byte-for-byte."""
    if not raw.startswith(_PNG_SIGNATURE):
        raise ValueError("INVALID_BLENDER_PNG")
    output = bytearray(_PNG_SIGNATURE)
    offset, chunks, ended = 8, 0, False
    while offset < len(raw):
        if offset + 12 > len(raw):
            raise ValueError("INVALID_BLENDER_PNG")
        size = int.from_bytes(raw[offset:offset + 4], "big")
        end = offset + size + 12
        if end > len(raw):
            raise ValueError("INVALID_BLENDER_PNG")
        kind, payload = raw[offset + 4:offset + 8], raw[offset + 8:end - 4]
        if zlib.crc32(kind + payload) != int.from_bytes(raw[end - 4:end], "big"):
            raise ValueError("INVALID_BLENDER_PNG")
        if chunks == 0 and (kind != b"IHDR" or size != 13):
            raise ValueError("INVALID_BLENDER_PNG")
        if kind not in _TEXT_CHUNKS:
            output.extend(raw[offset:end])
        chunks += 1
        offset = end
        if kind == b"IEND":
            if size or offset != len(raw):
                raise ValueError("INVALID_BLENDER_PNG")
            ended = True
            break
    if not ended:
        raise ValueError("INVALID_BLENDER_PNG")
    return bytes(output)


def _json_bytes(value: Json) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       indent=2) + "\n").encode()


def _pinned(repo: Path, relative: str) -> Json:
    path = repo / relative
    if path.is_symlink() or not path.resolve().is_relative_to(repo.resolve()):
        raise ValueError("BLENDER_SOURCE_EVIDENCE_UNAVAILABLE")
    raw = path.read_bytes()
    if _sha(raw) != _PINS[relative]:
        raise ValueError("BLENDER_SOURCE_EVIDENCE_UNAVAILABLE")
    value = json.loads(gzip.decompress(raw) if relative.endswith(".gz") else raw)
    if not isinstance(value, dict):
        raise ValueError("BLENDER_SOURCE_EVIDENCE_UNAVAILABLE")
    return value


def _finite_vector(value: Any) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3 or any(
        type(v) not in (int, float) or not math.isfinite(v) for v in value
    ):
        raise ValueError("INVALID_BLENDER_SOURCE_VECTOR")
    return [float(v) for v in value]


def _calibration(camera: Json) -> Json:
    fields = ("camera_id", "camera_to_world", "fx", "fy", "cx", "cy", "width", "height",
              "clip_start", "clip_end", "convention", "pixel_origin", "floor_id", "zone_id")
    result = {key: copy.deepcopy(camera[key]) for key in fields}
    matrix = result["camera_to_world"]
    if not isinstance(matrix, list) or len(matrix) != 4 or any(
        not isinstance(row, list) or len(row) != 4 or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in row
        ) for row in matrix
    ):
        raise ValueError("INVALID_BLENDER_CAMERA")
    for axis in range(3):
        matrix[axis][3] *= METRES_PER_BU
    for field in ("clip_start", "clip_end"):
        result[field] *= METRES_PER_BU
    result["meters_per_unit"] = 1.0
    return result


def _source_meshes(archive: Json, support: Json, site: str) -> Json:
    review = next(row for row in support["walkable_reviews"]
                  if row["walkable_id"] == _WALKABLE[site])
    if review["authority"] != "APPROVED" or not review["source_selection_complete"]:
        raise ValueError("SOURCE_MODEL_CONTEXT_UNAVAILABLE")
    supported = [s for s in support["support_surfaces"]
                 if s["surface_id"] in review["support_surface_ids"]]
    points = [_finite_vector(v) for surface in supported for v in surface["vertices"]]
    if not points:
        raise ValueError("SOURCE_MODEL_CONTEXT_UNAVAILABLE")
    # Select a display box from independently approved source support, never actor positions.
    padding = 0.5 / METRES_PER_BU
    floor = float(review["source_support_height_bu"])
    low = [min(p[a] for p in points) - padding for a in range(2)] + [floor - 0.02 / METRES_PER_BU]
    high = [max(p[a] for p in points) + padding for a in range(2)] + [floor + 2.8 / METRES_PER_BU]
    meshes: list[Json] = []
    selected = [r for r in archive["meshes"]
                if r["source_object_id"] in {"group_0", "group_0.002"}]
    if len(selected) != 2 or any(r["full_object_exported"] is not True for r in selected):
        raise ValueError("SOURCE_MODEL_CONTEXT_UNAVAILABLE")
    for row in selected:
        original = [_finite_vector(v) for v in row["vertices"]]
        vertices: list[list[float]] = []
        triangles: list[list[int]] = []
        identities: dict[tuple[float, ...], int] = {}
        source_indices, non_horizontal = [], 0
        for index, triangle in enumerate(row["triangles"]):
            if len(triangle) != 3 or any(type(v) is not int or not 0 <= v < len(original)
                                         for v in triangle):
                raise ValueError("SOURCE_MODEL_CONTEXT_UNAVAILABLE")
            polygon = [original[v] for v in triangle]
            for axis in range(3):
                polygon = _clip_polygon(polygon, axis, low[axis], True)
                if not polygon:
                    break
                polygon = _clip_polygon(polygon, axis, high[axis], False)
                if not polygon:
                    break
            for fan in range(1, len(polygon) - 1):
                corners = [polygon[0], polygon[fan], polygon[fan + 1]]
                u = [corners[1][a] - corners[0][a] for a in range(3)]
                v = [corners[2][a] - corners[0][a] for a in range(3)]
                normal = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
                          u[0] * v[1] - u[1] * v[0]]
                magnitude = math.hypot(*normal)
                if magnitude < 1e-8:
                    continue
                ids = []
                for corner in corners:
                    key = tuple(corner)
                    if key not in identities:
                        identities[key] = len(vertices)
                        vertices.append([c * METRES_PER_BU for c in corner])
                    ids.append(identities[key])
                triangles.append(ids)
                source_indices.append(index)
                non_horizontal += abs(normal[2]) / magnitude < 0.999999
        if not triangles:
            continue
        derivation = {"method": "SOURCE_TRIANGLE_SIX_PLANE_CLIP_NO_CAPS_V1",
                      "source_sha256": SOURCE_SHA256, "archive_sha256": _PINS[_GEOMETRY],
                      "source_geometry_sha256": row["geometry_sha256"],
                      "source_triangle_indices_sha256": content_hash(source_indices),
                      "source_triangle_count": len(set(source_indices)),
                      "crop_native_bu": [low, high], "metres_per_unit": METRES_PER_BU,
                      "new_caps_created": False, "physical_authority_changed": False}
        meshes.append({"mesh_ref": opaque_ref("mesh", site, content_hash(derivation)),
                       "vertices": vertices, "triangles": triangles, "derivation": derivation,
                       "geometry_sha256": content_hash({"vertices": vertices,
                                                        "triangles": triangles}),
                       "non_horizontal_triangle_count": non_horizontal,
                       "origin": "SOURCE_EVALUATED_GEOMETRY", "color": "#727b84",
                       "authority": "PARTIAL_DISPLAY_CONTEXT", "display_only": True,
                       "source_geometry_modified": False})
    if not meshes:
        raise ValueError("SOURCE_MODEL_CONTEXT_UNAVAILABLE")
    return {"meshes": meshes, "routes": [], "authority": "PARTIAL_DISPLAY_CONTEXT",
            "bounds_metres": [[v * METRES_PER_BU for v in low],
                              [v * METRES_PER_BU for v in high]],
            "evaluated_scene": {"name": "Scene", "frame": 220, "subframe": 0.0},
            "default_material": "DISPLAY_ONLY_SMOOTH_GRAY",
            "source_archive_sha256": _PINS[_GEOMETRY], "archive_is_whole_scene": False,
            "selected_object_count": len(selected), "selected_objects_complete": True,
            "display_triangle_count": sum(len(m["triangles"]) for m in meshes),
            "truncated": False, "whole_scene_occlusion_proof": False,
            "physical_authority_changed": False, "source_geometry_modified": False}


def _frame_path(site_root: Path, camera_id: str, index: int, relative: Any) -> Path:
    expected = f"frames/{camera_id}/frame_{index:03d}.png"
    if relative != expected or ".." in PurePosixPath(expected).parts:
        raise ValueError("BLENDER_MEDIA_SCOPE_DENIED")
    path = site_root / expected
    if path.is_symlink() or not path.resolve().is_relative_to(site_root.resolve()):
        raise ValueError("BLENDER_MEDIA_SCOPE_DENIED")
    return path.resolve()


def _exact_fields(value: Any, fields: str) -> None:
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        raise ValueError("INVALID_BLENDER_SAFE_INPUT")


def _safe_input_contract(inputs: Json) -> None:
    """Reject extensible metadata before any source-model data enters public DTOs."""
    _exact_fields(inputs, "schema_version source_binding cameras frames floor_plane presentation "
                  "source_types")
    _exact_fields(inputs["source_binding"], "source_sha256 dataset_sha256 site_id run_id clock_id "
                  "scale_sha256 model_revision native_units units metres_per_bu")
    _exact_fields(inputs["floor_plane"], "point normal floor_id source_sha256 authority "
                  "authority_scope evidence_sha256")
    _exact_fields(inputs["source_types"], "rgb model perception projection behavior events agent")
    if inputs["source_types"] != _SOURCE_TYPES:
        raise ValueError("INVALID_BLENDER_SAFE_INPUT")
    if inputs["source_binding"]["native_units"] != "NATIVE_BU" or (
        inputs["source_binding"]["units"] != "METRES"
        or inputs["source_binding"]["metres_per_bu"] != METRES_PER_BU
        or inputs["source_binding"]["model_revision"] != "SOURCE_SCENE_FRAME_220"
    ):
        raise ValueError("INVALID_BLENDER_SAFE_INPUT")
    for camera in inputs["cameras"]:
        _exact_fields(camera, "camera_id camera_ref calibration authority coverage_status")
        _exact_fields(camera["calibration"], "camera_id camera_to_world fx fy cx cy width height "
                      "clip_start clip_end convention pixel_origin floor_id zone_id "
                      "meters_per_unit")
    for frame in inputs["frames"]:
        _exact_fields(frame, "frame_ref camera_id timestamp width height sha256 byte_count "
                      "served_sha256 served_byte_count local_path origin data_kind")
    presentation = inputs["presentation"]
    _exact_fields(presentation, "meshes routes authority bounds_metres evaluated_scene "
                  "default_material source_archive_sha256 archive_is_whole_scene "
                  "selected_object_count selected_objects_complete display_triangle_count "
                  "truncated whole_scene_occlusion_proof physical_authority_changed "
                  "source_geometry_modified")
    if presentation["routes"] != [] or presentation["authority"] != "PARTIAL_DISPLAY_CONTEXT" or (
        presentation["default_material"] != "DISPLAY_ONLY_SMOOTH_GRAY"
        or presentation["source_archive_sha256"] != _PINS[_GEOMETRY]
        or presentation["evaluated_scene"] != {"name": "Scene", "frame": 220, "subframe": 0.0}
        or presentation["source_geometry_modified"] is not False
        or presentation["physical_authority_changed"] is not False
        or not 0 < presentation["display_triangle_count"] <= 25000
        or not 1 <= len(presentation["meshes"]) <= 2
    ):
        raise ValueError("INVALID_BLENDER_SAFE_INPUT")
    for mesh in presentation["meshes"]:
        _exact_fields(mesh, "mesh_ref vertices triangles derivation geometry_sha256 "
                      "non_horizontal_triangle_count origin color authority display_only "
                      "source_geometry_modified")
        derivation = mesh["derivation"]
        _exact_fields(derivation, "method source_sha256 archive_sha256 source_geometry_sha256 "
                      "source_triangle_indices_sha256 source_triangle_count crop_native_bu "
                      "metres_per_unit new_caps_created physical_authority_changed")
        if derivation["source_sha256"] != SOURCE_SHA256 or (
            derivation["archive_sha256"] != _PINS[_GEOMETRY]
            or derivation["new_caps_created"] is not False
            or derivation["physical_authority_changed"] is not False
            or mesh["geometry_sha256"] != content_hash(
                {"vertices": mesh["vertices"], "triangles": mesh["triangles"]})
        ):
            raise ValueError("INVALID_BLENDER_SAFE_INPUT")
        for point in mesh["vertices"]:
            _finite_vector(point)
        if any(len(triangle) != 3 or any(type(v) is not int or not 0 <= v < len(mesh["vertices"])
                                        for v in triangle) for triangle in mesh["triangles"]):
            raise ValueError("INVALID_BLENDER_SAFE_INPUT")


def materialize_blender_workbench(
    repo: Path, canonical_repo: Path, output: Path,
    sites: Sequence[str] = ("office", "classroom101", "auditorium"),
) -> Json:
    """Extract safe local inputs from pinned existing RGB; never copy source/media."""
    repo, canonical_repo, output = repo.resolve(), canonical_repo.resolve(), output.resolve()
    if len(set(sites)) != len(sites) or any(site not in SITE_PINS for site in sites):
        raise ValueError("BLENDER_SITE_DENIED")
    if output.exists():
        raise FileExistsError("BLENDER_OUTPUT_EXISTS")
    source = canonical_repo / "blender/school_v3.blend"
    if source.is_symlink():
        raise ValueError("BLENDER_SOURCE_UNAVAILABLE")
    before = _fingerprint(source)
    if before["sha256"] != SOURCE_SHA256:
        raise ValueError("BLENDER_SOURCE_UNAVAILABLE")
    scale, support, geometry = (_pinned(repo, ref) for ref in (_SCALE, _SUPPORT, _GEOMETRY))
    if scale["source_asset_sha256"] != SOURCE_SHA256 or (
        scale["authority"] != "APPROVED" or scale["metres_per_blender_unit"] != METRES_PER_BU
        or support["source_sha256"] != SOURCE_SHA256 or support["scale_m_per_bu"] != METRES_PER_BU
        or geometry["source_sha256"] != SOURCE_SHA256
        or geometry["evaluated_scene"] != {"name": "Scene", "frame": 220, "subframe": 0.0}
        or geometry["geometry_modified"] is not False or geometry["saved"] is not False
    ):
        raise ValueError("BLENDER_SOURCE_EVIDENCE_UNAVAILABLE")
    floor = next(row for row in support["floor_authorities"] if row["floor_id"] == "1F")
    bundles: list[tuple[str, Json, Json]] = []
    for site in sites:
        site_root = canonical_repo / "data/pilot/school_v3_multisite_20261005" / site
        dataset_path = site_root / "dataset.json"
        if dataset_path.is_symlink() or not dataset_path.resolve().is_relative_to(canonical_repo):
            raise ValueError("BLENDER_DATASET_UNAVAILABLE")
        dataset_raw = dataset_path.read_bytes()
        if _sha(dataset_raw) != SITE_PINS[site]:
            raise ValueError("BLENDER_DATASET_UNAVAILABLE")
        dataset = json.loads(dataset_raw)
        if dataset["data_kind"] != "SYNTHETIC" or dataset["site_id"] != site or (
            dataset["source_scene"]["sha256_before"] != SOURCE_SHA256
            or dataset["source_scene"]["sha256_after"] != SOURCE_SHA256
            or dataset["sampling_fps"] != 5 or len(dataset["timestamps"]) != 50
            or dataset["render_policy"]["source_scene_saved"] is not False
            or dataset["render_policy"]["geometry_frame"] != 220
            or dataset["render_policy"]["geometry_subframe"] != 0
            or dataset["render_policy"]["png_label_policy"] !=
                "SYNTHETIC_PROVENANCE_TEXT_CHUNKS_RENDERED_PIXELS_UNCHANGED"
        ):
            raise ValueError("BLENDER_DATASET_BINDING_MISMATCH")
        run_id = f"blender-pilot-{site}-baseline-v1"
        binding = {"source_sha256": SOURCE_SHA256, "dataset_sha256": SITE_PINS[site],
                   "site_id": site, "run_id": run_id,
                   "clock_id": "BLENDER_PILOT_CONFIGURED_SECONDS_5HZ",
                   "scale_sha256": _PINS[_SCALE], "model_revision": "SOURCE_SCENE_FRAME_220",
                   "native_units": "NATIVE_BU", "units": "METRES", "metres_per_bu": METRES_PER_BU}
        cameras = [{"camera_id": row["camera_id"],
                    "camera_ref": opaque_ref("camera", run_id, row["camera_id"]),
                    "calibration": _calibration(row),
                    "authority": "SOURCE_CAMERA_CALIBRATION", "coverage_status": "UNKNOWN"}
                   for row in dataset["cameras"]]
        camera_ids = {row["camera_id"] for row in cameras}
        if len(camera_ids) != 2:
            raise ValueError("INVALID_BLENDER_CAMERA")
        frames = []
        for index, timestamp in enumerate(dataset["timestamps"]):
            if timestamp["index"] != index or timestamp["timestamp"] != index / 5 or (
                {row["camera_id"] for row in timestamp["per_camera"]} != camera_ids
                or len(timestamp["per_camera"]) != 2
            ):
                raise ValueError("INVALID_BLENDER_FRAME_CLOCK")
            # Read no observation, visibility, simulated UV/depth, diagnostics or truth values.
            for row in timestamp["per_camera"]:
                camera_id, render = row["camera_id"], row["render"]
                path = _frame_path(site_root, camera_id, index, render["path"])
                raw = path.read_bytes()
                if _sha(raw) != render["sha256"] or struct.unpack(">IIBB", raw[16:26]) != (
                    960, 540, 8, 2
                ):
                    raise ValueError("BLENDER_MEDIA_HASH_MISMATCH")
                served = strip_png_text(raw)
                frames.append({"frame_ref": opaque_ref("frame", run_id, camera_id, str(index),
                                                       render["sha256"]),
                               "camera_id": camera_id, "timestamp": index / 5,
                               "width": 960, "height": 540, "sha256": render["sha256"],
                               "byte_count": len(raw), "served_sha256": _sha(served),
                               "served_byte_count": len(served), "local_path": str(path),
                               "origin": "BLENDER_CAMERA_RGB", "data_kind": "SYNTHETIC"})
        inputs = {"schema_version": "workbench.blender-safe-inputs.v1", "source_binding": binding,
                  "cameras": cameras, "frames": frames,
                  "floor_plane": {"point": [v * METRES_PER_BU for v in floor["point"]],
                                  "normal": floor["normal"], "floor_id": "1F",
                                  "source_sha256": SOURCE_SHA256, "authority": "APPROVED",
                                  "authority_scope": support["authority_scope"],
                                  "evidence_sha256": _PINS[_SUPPORT]},
                  "presentation": _source_meshes(geometry, support, site),
                  "source_types": copy.deepcopy(_SOURCE_TYPES)}
        manifest = {"schema_version": "workbench.blender-local-bundle.v1",
                    "inputs_sha256": _sha(_json_bytes(inputs)), "source_integrity": before,
                    "source_path": str(source), "dataset_path": str(dataset_path.resolve()),
                    "asset_root": str(site_root.resolve()), "dataset_sha256": SITE_PINS[site],
                    "source_geometry_sha256": _PINS[_GEOMETRY], "frame_count": len(frames),
                    "source_saved": False, "source_copied": False, "media_copied": False,
                    "rendered": False, "gt_values_used_for_inference": False}
        bundles.append((site, inputs, manifest))
    after = _fingerprint(source)
    if before != after:
        raise ValueError("IMMUTABLE_BLENDER_SOURCE_CHANGED")
    output.mkdir(parents=True)
    for site, inputs, manifest in bundles:
        folder = output / site
        folder.mkdir()
        (folder / "safe_inputs.json").write_bytes(_json_bytes(inputs))
        (folder / "manifest.json").write_bytes(_json_bytes(manifest))
    return {"schema_version": "workbench.blender-materialization.v1", "status": "MATERIALIZED",
            "sites": [{"site_id": site, "inputs_sha256": manifest["inputs_sha256"],
                       "dataset_sha256": manifest["dataset_sha256"],
                       "frames": len(inputs["frames"]), "cameras": len(inputs["cameras"]),
                       "model_triangles": inputs["presentation"]["display_triangle_count"]}
                      for site, inputs, manifest in bundles],
            "source_before": before, "source_after": after,
            "source_saved": False, "source_copied": False, "media_copied": False,
            "rendered": False, "gt_values_used_for_inference": False}


class BlenderSceneAdapter(SceneAdapter):
    """An immutable RGB/model view with deterministic, bounded frame retrieval."""

    def __init__(self, root: Path) -> None:
        from amidst.workbench.blender_association import BaselineAssociationIndex
        from amidst.workbench.blender_motion import BaselineMotionIndex
        from amidst.workbench.frame_baseline import BaselineFrameIndex

        self.root = root.resolve()
        self._manifest_raw = (self.root / "manifest.json").read_bytes()
        self._manifest = json.loads(self._manifest_raw)
        self._inputs_raw = (self.root / "safe_inputs.json").read_bytes()
        self._inputs = json.loads(self._inputs_raw)
        self._verify()
        binding = self._inputs["source_binding"]
        site = binding["site_id"]
        self.scene_id = "blender-" + site
        self.label = f"Blender 鏡頭・{SITE_LABELS[site]}"
        self.description = "原來源 camera RGB、平滑來源模型與基底 Top-K；本階段無 Agent 決策"
        self.source_hash = binding["source_sha256"]
        self.run_id = binding["run_id"]
        self.model_revision = binding["model_revision"]
        self.index = BaselineFrameIndex(self._inputs)
        self.motion = BaselineMotionIndex(self.index.snapshot())
        self.association = BaselineAssociationIndex(self.index.snapshot())
        self.physical: Any = None
        self._physical_source: Any = None
        self._physical_review_index: Any = None
        self._camera_rows = {c["camera_id"]: c for c in self._inputs["cameras"]}
        self._media = {f["frame_ref"]: f for f in self._inputs["frames"]}
        self._observation_rows: dict[str, list[Json]] = {}
        self._observation_times: dict[str, list[float]] = {}
        for camera_id in self._camera_rows:
            rows = sorted((r for r in self.index.observations if r["camera_id"] == camera_id),
                          key=lambda r: r["timestamp"])
            self._observation_rows[camera_id] = rows
            self._observation_times[camera_id] = [r["timestamp"] for r in rows]
        cameras, objects = [], []
        for row in self._inputs["cameras"]:
            calibration = row["calibration"]
            position = [calibration["camera_to_world"][a][3] for a in range(3)]
            properties = {key: copy.deepcopy(calibration[key]) for key in (
                "camera_to_world", "fx", "fy", "cx", "cy", "width", "height", "convention")}
            properties.update({"calibration_kind": "PINHOLE", "position": position})
            cameras.append({"camera_id": row["camera_id"], "camera_ref": row["camera_ref"],
                            "label": row["camera_id"], "position": position,
                            "coverage_status": "UNKNOWN", "region_ids": [],
                            "calibration": copy.deepcopy(calibration),
                            "authority": row["authority"], "properties": properties})
            objects.append({"object_id": "camera:" + row["camera_id"], "kind": "CAMERA",
                            "label": row["camera_id"], "semantic": "CAMERA",
                            "geometry": {"type": "point", "points": [position]},
                            "properties": properties, "editable_fields": [],
                            "authority": row["authority"]})
        presentation = self._inputs["presentation"]
        bounds = presentation["bounds_metres"]
        floor_z = self._inputs["floor_plane"]["point"][2]
        objects.append({"object_id": "source-context:" + site, "kind": "REGION",
                        "label": SITE_LABELS[site] + " 來源模型展示範圍", "semantic": "REGION",
                        "geometry": {"type": "polygon", "points": [
                            [bounds[0][0], bounds[0][1], floor_z],
                            [bounds[1][0], bounds[0][1], floor_z],
                            [bounds[1][0], bounds[1][1], floor_z],
                            [bounds[0][0], bounds[1][1], floor_z]]},
                        "properties": {"description":
                                       "僅來源面裁切展示，未證明鏡頭覆蓋或全場景遮擋。"},
                        "editable_fields": [], "authority": "SOURCE_DISPLAY_CROP_ONLY"})
        self._snapshot = {
            "scene_id": self.scene_id, "label": self.label, "description": self.description,
            "model_id": "school-v3:" + site, "model_revision": self.model_revision,
            "run_id": self.run_id, "source_hash": self.source_hash,
            "source_ref": opaque_ref("source", self.source_hash),
            "config_sha256": self._manifest["inputs_sha256"],
            "registry_sha256": content_hash(binding), "freeze_ref": self.index.source_features,
            "clock": {"clock_id": binding["clock_id"], "unit": "SECONDS", "sampling_hz": 5},
            "coordinates": {"native_units": "NATIVE_BU", "normalized_units": "METRES",
                            "metres_per_unit": METRES_PER_BU,
                            "coordinate_frame": "RIGHT_HANDED_XYZ_Z_UP"},
            "evidence_level": "BLENDER_CAMERA_RGB_PIXEL_BASELINE", "origin": "SYNTHETIC",
            "authority": "SOURCE_BOUND_ENGINEERING_ONLY", "formal_phase1_acceptance": False,
            "capabilities": {"images": True, "video": False, "local_3d": True,
                             "camera_pose": True, "events": False, "scene_review": False,
                             "result_review": False, "evaluation": False,
                             "inference_execution": False, "frame_query": True,
                             "navigation_guidance": False, "product": False,
                             "motion_reconstruction": True,
                             "cross_camera_reconstruction": True,
                             "physical_cross_camera_reconstruction": False},
            "bounds": [bounds[0][0], bounds[0][1], bounds[1][0], bounds[1][1]],
            "time_range": [0.0, 9.8], "cameras": cameras, "objects": objects,
            "presentation": copy.deepcopy(presentation), "source_binding": copy.deepcopy(binding),
            "source_types": copy.deepcopy(self._inputs["source_types"]),
            "counts": {"cameras": len(cameras), "frames": len(self._media),
                       "observations": len(self.index.observations), "events": 0},
            "baseline": self.index.snapshot(),
            "limitations": ["Blender renders are synthetic project media; no physical stream.",
                            "The orange body is a simulated substitute; RGB measurements are real "
                            "pixel algorithm outputs, not renderer annotations.",
                            "Model context is a source-triangle crop, not whole-scene coverage.",
                            "Behavior is user intent; events and physical reconstruction video "
                            "are not generated."]}

    def _verify(self) -> None:
        try:
            if (self.root / "manifest.json").is_symlink() or (
                self.root / "safe_inputs.json").is_symlink() or (
                (self.root / "manifest.json").read_bytes() != self._manifest_raw
                or _sha((self.root / "safe_inputs.json").read_bytes()) !=
                self._manifest["inputs_sha256"]
            ):
                raise ValueError("BLENDER_SCENE_STALE")
            binding = self._inputs["source_binding"]
            _safe_input_contract(self._inputs)
            site = binding["site_id"]
            source = Path(self._manifest["source_path"])
            dataset = Path(self._manifest["dataset_path"])
            asset_root = Path(self._manifest["asset_root"])
            if source.is_symlink() or dataset.is_symlink() or site not in SITE_PINS or (
                self._manifest["schema_version"] != "workbench.blender-local-bundle.v1"
                or self._inputs["schema_version"] != "workbench.blender-safe-inputs.v1"
                or binding["source_sha256"] != SOURCE_SHA256
                or binding["dataset_sha256"] != SITE_PINS[site]
                or self._manifest["dataset_sha256"] != SITE_PINS[site]
                or binding["scale_sha256"] != _PINS[_SCALE]
                or binding["run_id"] != f"blender-pilot-{site}-baseline-v1"
                or self._inputs["floor_plane"]["source_sha256"] != SOURCE_SHA256
                or asset_root.is_symlink() or asset_root.resolve() != asset_root
                or dataset.resolve().parent != asset_root
                or source.resolve() != source
                or _file_sha(dataset) != SITE_PINS[site]
                or source.stat().st_size != self._manifest["source_integrity"]["byte_count"]
                or source.stat().st_mtime_ns != self._manifest["source_integrity"]["mtime_ns"]
                or self._manifest["source_integrity"]["sha256"] != SOURCE_SHA256
            ):
                raise ValueError("BLENDER_SCENE_STALE")
        except (OSError, KeyError, TypeError, ValueError):
            raise ValueError("BLENDER_SCENE_STALE") from None

    def export_safe_inputs(self) -> Json:
        """Local probe inputs; includes private media locators, never return through HTTP."""
        self._verify()
        return copy.deepcopy(self._inputs)

    def live_scope(self) -> Json:
        self._verify()
        return {**copy.deepcopy(self._inputs["source_binding"]),
                "scene_id": self.scene_id, "source_hash": self.source_hash,
                "run_id": self.run_id, "model_revision": self.model_revision,
                "inputs_sha256": self._manifest["inputs_sha256"],
                "source_features": self.index.source_features, "stage": "BASELINE_RESULTS"}

    def summary(self) -> Json:
        self._verify()
        return super().summary()

    def snapshot(self) -> Json:
        self._verify()
        return super().snapshot()

    def query(self, camera_id: str, start: float, end: float) -> Json:
        self._verify()
        result = self.index.query([camera_id], start, end, (start + end) / 2, 5)
        times = self._observation_times[camera_id]
        observations = copy.deepcopy(self._observation_rows[camera_id][
            bisect_left(times, start):bisect_right(times, end)])
        retrieval = {**result["retrieval"],
                     "frame_records_read": result["retrieval"]["records_read"],
                     "observation_records_read": len(observations),
                     "records_read": result["retrieval"]["records_read"] + len(observations)}
        return {"events": [], "observations": observations, "retrieval": retrieval,
                "scope": self.live_scope()}

    def frame_query(self, camera_ids: Sequence[str], start: float, end: float,
                    target_timestamp: float, top_k: int = 3,
                    behavior_intent: str = "walking") -> Json:
        self._verify()
        result = self.index.query(camera_ids, start, end, target_timestamp, top_k, behavior_intent)
        return {**result, "scope": self.live_scope()}

    def frames(self, camera_ids: Sequence[str], timestamp: float) -> Json:
        self._verify()
        return self.index.frames(camera_ids, timestamp)

    def camera_frame_wall(self, camera_ids: Sequence[str], start: float, end: float,
                          slot_count: int) -> Json:
        """A bounded temporal mosaic of existing source frames, never extra cameras."""
        self._verify()
        self.index._validate_cameras(camera_ids)
        source_start, source_end = self._snapshot["time_range"]
        if (type(slot_count) is not int or slot_count not in (8, 12, 16)
                or any(type(t) not in (int, float) or not math.isfinite(t) for t in (start, end))
                or start < source_start or end > source_end or start > end):
            raise ValueError("FRAME_WALL_SCOPE_INVALID")
        samples = math.ceil(slot_count / len(camera_ids))
        rows: list[Json] = []
        seen: set[str] = set()
        for sample in range(samples):
            timestamp = start if samples == 1 else start + (end - start) * sample / (samples - 1)
            for row in self.index.frames(camera_ids, timestamp)["frames"]:
                if len(rows) == slot_count:
                    break
                frame_ref = row.get("frame_ref")
                rows.append({**row, "slot_index": len(rows), "sample_index": sample,
                             "repeated_source_frame": frame_ref in seen if frame_ref else False})
                if frame_ref:
                    seen.add(frame_ref)
        return {"schema_version": "workbench.camera-frame-wall.v1",
                "selection": {"camera_ids": list(camera_ids), "time_range": [start, end],
                              "slot_count": slot_count}, "frames": rows,
                "data_kind": "ACTUAL_SOURCE_RGB_TIME_SAMPLES", "temporal_mosaic": True,
                "source_camera_count": len(camera_ids), "unique_source_frames": len(seen),
                "missing_slots": [r["slot_index"] for r in rows if r["status"] == "MISSING"],
                "retrieval": {"indexed": True, "source_rgb_scan": False,
                              "frame_records_read": len(rows), "global_scan": False},
                "source_binding": copy.deepcopy(self._inputs["source_binding"]),
                "scope": self.live_scope(), "agent_used": False, "real_stream": False}

    def motion_reconstruction(self, camera_ids: Sequence[str], start: float, end: float) -> Json:
        self._verify()
        return {**self.motion.reconstruct(camera_ids, start, end), "scope": self.live_scope()}

    def cross_camera_reconstruction(self, camera_ids: Sequence[str], start: float, end: float,
                                    top_k: int = 3) -> Json:
        self._verify()
        return {**self.association.reconstruct(camera_ids, start, end, top_k),
                "scope": self.live_scope()}

    def bind_physical(self, source: Any) -> None:
        """Attach independently verified constraints without changing the RGB bundle."""
        from amidst.workbench.blender_physical import BlenderPhysicalIndex

        self._verify()
        source.verify()
        self.physical = BlenderPhysicalIndex(self.association, source)
        self._physical_source = source
        self._physical_review_index = None
        self._snapshot["capabilities"]["physical_cross_camera_reconstruction"] = True
        self._snapshot["capabilities"]["physical_review"] = True
        self._snapshot["capabilities"]["camera_frame_wall"] = True
        self._snapshot["physical_constraints"] = source.public_summary()

    def physical_review_index(self) -> Any:
        """Reference the unchanged cached baseline; preparing review never re-encodes media."""
        from amidst.workbench.blender_physical_review import BlenderPhysicalReviewIndex

        self._verify()
        if self.physical is None or self._physical_source is None:
            raise ValueError("PHYSICAL_REVIEW_UNAVAILABLE")
        self._physical_source.verify()
        if self._physical_review_index is None:
            start, end = self._snapshot["time_range"]
            baseline = self.physical.reconstruct(sorted(self._camera_rows), start, end, 3)
            self._physical_review_index = BlenderPhysicalReviewIndex(
                self._physical_source, baseline)
        return self._physical_review_index

    def physical_review(self, camera_ids: Sequence[str], start: float, end: float) -> Json:
        result: Json = self.physical_review_index().snapshot(camera_ids, start, end)
        return {**result, "scope": self.live_scope(), "baseline_results_unchanged": True,
                "baseline_checkpoint": "2de98213fa361b49699a9b896ead8c152cb9a6c1",
                "post_confirmation_rerun_performed": False}

    def export_physical_source(self) -> Json:
        """Local physical probe inputs; raw geometry is never returned through HTTP."""
        self._verify()
        if self._physical_source is None:
            raise ValueError("PHYSICAL_SOURCE_UNAVAILABLE")
        self._physical_source.verify()
        result: Json = self._physical_source.export_safe_inputs()
        return result

    def physical_cross_camera_reconstruction(self, camera_ids: Sequence[str], start: float,
                                           end: float, top_k: int = 3) -> Json:
        self._verify()
        if self.physical is None or self._physical_source is None:
            raise ValueError("PHYSICAL_SOURCE_UNAVAILABLE")
        self._physical_source.verify()
        return {**self.physical.reconstruct(camera_ids, start, end, top_k),
                "scope": self.live_scope()}

    def event(self, ref: str) -> Json:
        raise ValueError("BASELINE_EVENT_NOT_GENERATED")

    def media(self, ref: str) -> tuple[str, bytes]:
        self._verify()
        row = self._media.get(ref)
        if row is None:
            raise ValueError("MEDIA_SCOPE_DENIED")
        path, asset_root = Path(row["local_path"]), Path(self._manifest["asset_root"])
        if path.is_symlink() or not path.resolve().is_relative_to(asset_root.resolve()):
            raise ValueError("MEDIA_SCOPE_DENIED")
        raw = path.read_bytes()
        if _sha(raw) != row["sha256"] or len(raw) != row["byte_count"]:
            raise ValueError("BLENDER_MEDIA_HASH_MISMATCH")
        served = strip_png_text(raw)
        if _sha(served) != row["served_sha256"] or len(served) != row["served_byte_count"]:
            raise ValueError("BLENDER_MEDIA_HASH_MISMATCH")
        return "image/png", served

    def evaluation(self) -> Json:
        self._verify()
        return {"status": "UNAVAILABLE", "reason": "BASELINE_HAS_NO_FORMAL_EVALUATION"}


def load_blender_scene(root: Path) -> BlenderSceneAdapter:
    return BlenderSceneAdapter(root)
