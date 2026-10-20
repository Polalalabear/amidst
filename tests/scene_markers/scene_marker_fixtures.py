"""SYNTHETIC controlled-scene safe bundle built from the CS-B design values (D50).

Nothing here is read from a real run: every document is generated in memory from literal design
numbers.  Hashes are sha256 of short labels, not of real geometry or images.  Do not treat any
value as measured; physical and calibration error is UNKNOWN (design §0).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from amidst.scene_markers import load_template

RUN_A = "ctrl-lcorr-s1-a-5fps-v1-r001"
RUN_B1 = "ctrl-lcorr-s1-b1-5fps-v1-r001"
FLOOR = "FLOOR_GROUND"


def sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _round(points: list[tuple[float, float]]) -> list[list[float]]:
    return [[round(x, 6), round(y, 6)] for x, y in points]


def _ccw_box_ring(lo: list[float], hi: list[float]) -> list[list[float]]:
    return [[lo[0], lo[1]], [hi[0], lo[1]], [hi[0], hi[1]], [lo[0], hi[1]]]


def synthetic_matrix(
    position: list[float], yaw_deg: float, pitch_down_deg: float, roll_deg: float = 0.0
) -> list[list[float]]:
    """4×4 row-major camera_to_world; columns are right, up, -forward, position (Blender)."""
    y, p = math.radians(yaw_deg), math.radians(pitch_down_deg)
    forward = (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), -math.sin(p))
    right = (math.sin(y), -math.cos(y), 0.0)
    up = (math.sin(p) * math.cos(y), math.sin(p) * math.sin(y), math.cos(p))
    r = math.radians(roll_deg)  # rotate right/up about the viewing axis
    right, up = (
        tuple(a * math.cos(r) + b * math.sin(r) for a, b in zip(right, up, strict=True)),
        tuple(-a * math.sin(r) + b * math.cos(r) for a, b in zip(right, up, strict=True)),
    )
    cols = [right, up, tuple(-v for v in forward), tuple(position)]
    return [[cols[j][i] for j in range(4)] for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]]


def _objects(design: dict[str, Any], walk_geoms: dict[str, Polygon]) -> list[dict[str, Any]]:
    solids = {s["id"]: s["bounds_m"] for s in design["solids_aabb_m"]["items"]}
    extents = {
        "CORR_VEST_W": [[-3.2, -2, 0], [5, 2.4, 0]],
        "CORR_W": [[0, 0, 0], [17.4, 2.4, 0]],
        "CORR_N": [[15, 2.4, 0], [17.4, 12, 0]],
        "ROOM_R101": [[5, -5, 0], [11, 0, 0]],
        "ROOM_R102": [[17.4, 7, 0], [22.4, 11, 0]],
        "AREA_R101_FRONT": [[6.5, 0, 0], [9.5, 2.4, 0]],
        "AREA_OBS_BAY_N": [[12.5, 7, 0], [15, 14.2, 0]],
        "PORTAL_R101": [[7.4, -0.12, 0], [8.6, 0, 2.4]],
        "PORTAL_R102": [[17.4, 8.4, 0], [17.52, 9.6, 2.4]],
    }
    out: list[dict[str, Any]] = []
    for spec in design["expected_objects"]:
        id_ = spec["id"]
        if id_ in solids:
            bounds = solids[id_]
        elif id_ in walk_geoms:
            minx, miny, maxx, maxy = walk_geoms[id_].bounds
            bounds = [[minx, miny, -0.12], [maxx, maxy, 0]]
        else:
            bounds = extents[id_]
        record: dict[str, Any] = {
            "id": id_,
            "class": spec["class"],
            "source_mesh": f"Mesh_{id_}",
            "source_object_id": f"SRC_{id_}",
            "geometry_ref": f"geometry/{id_}.json",
            "geometry_sha256": sha(f"geometry:{id_}"),
            "geometry_version": 1,
            "geometry_encoding_version": "geometry-encoding.synthetic.v1",
            "transform_applied": "WORLD_METRES",
            "bounds_m": bounds,
            "source_method": "ANNOTATED_AT_CREATION",
            "allowed_purposes": list(spec["allowed_purposes_candidates"]),
            "approval_status": "NOT_EVALUATED",
            "scope_ref": None,
            "approval_ref": None,
            "approval_sha256": None,
            "display_only": spec["display_only"],
        }
        if id_ in solids:
            lo, hi = bounds
            record.update(
                {
                    "floor_id": FLOOR,
                    "footprint_m": _ccw_box_ring(lo, hi),
                    "base_z_m": lo[2],
                    "height_m": hi[2] - lo[2],
                    "role": "PHYSICAL",
                    "collision_scope": "FOOTPRINT_EXTRUDED",
                    "body_policy_ref": "body-policy-d42.synthetic.v1",
                    "body_policy_sha256": sha("body-policy"),
                }
            )
        out.append(record)
    return out


def _walkables(design: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Polygon]]:
    pre = {k: Polygon(v) for k, v in design["walkable_precut_polygons_m"]["polygons"].items()}
    cuts: dict[str, list[Any]] = {}
    for item in design["cutouts"]["items"]:
        x0, x1, y0, y1 = item["xy_box_m"]
        cuts.setdefault(item["owner"], []).append(box(x0, y0, x1, y1))
    edges = design["walkable_connections"]["edges"]
    walks: list[dict[str, Any]] = []
    geoms: dict[str, Polygon] = {}
    for wid, poly in pre.items():
        cut = poly.difference(unary_union(cuts[wid])) if wid in cuts else poly
        assert isinstance(cut, Polygon), wid
        cut = orient(cut, 1.0)  # exterior CCW, interiors CW
        geoms[wid] = cut
        conns = [
            {"to_walk_id": e["b"], "via_portal_id": e["via_portal_id"]}
            for e in edges
            if e["a"] == wid
        ]
        conns += [
            {"to_walk_id": e["a"], "via_portal_id": e["via_portal_id"]}
            for e in edges
            if e["b"] == wid
        ]
        walks.append(
            {
                "id": wid,
                "floor_id": FLOOR,
                "support_surface_id": FLOOR,
                "polygon_m": _round(list(cut.exterior.coords)[:-1]),
                "holes_m": [_round(list(r.coords)[:-1]) for r in cut.interiors],
                "geometry_ref": f"geometry/{wid}.json",
                "geometry_sha256": sha(f"walk:{wid}"),
                "status": "WALKABLE",
                "connections": conns,
                "approval": {
                    "status": "NOT_EVALUATED",
                    "verified_by": [],
                    "verification_sha256": None,
                },
            }
        )
    return walks, geoms


def _camera_docs(design: dict[str, Any]) -> list[dict[str, Any]]:
    common = design["cameras"]["common"]
    out = []
    for item in design["cameras"]["items"]:
        fx = (common["width"] / 2) / math.tan(math.radians(item["hfov_deg"]) / 2)
        out.append(
            {
                "schema_version": "controlled-scene.camera.v1",
                "camera_id": item["camera_id"],
                "camera_to_world": synthetic_matrix(
                    item["position_m"], item["yaw_deg"], item["pitch_down_deg"]
                ),
                "convention": "BLENDER_NEG_Z_UP_Y",
                "fx": fx,
                "fy": fx,
                "cx": common["cx"],
                "cy": common["cy"],
                "pixel_origin": "TOP_LEFT_CONTINUOUS",
                "width": common["width"],
                "height": common["height"],
                "pixel_aspect_xy": 1,
                "render_resolution_percentage": 100,
                "shift_x": 0,
                "shift_y": 0,
                "sensor_fit": "HORIZONTAL",
                "sensor_width_mm": common["sensor_width_mm"],
                "sensor_height_mm": common["sensor_height_mm"],
                "focal_length_mm": common["sensor_width_mm"] * fx / common["width"],
                "clip_start": common["clip_start"],
                "clip_end": common["clip_end"],
                "distortion": None,
                "camera_model": "PINHOLE",
                "floor_id": FLOOR,
                "zone_id": "ZONE_SYNTHETIC",
                "meters_per_unit": 1.0,
                "static_validity": {"synthetic": True},
                "calibration_sha256": sha(f"calibration:{item['camera_id']}"),
            }
        )
    return out


def build_bundle(event: str = "a") -> dict[str, Any]:
    """A conforming synthetic bundle for event ``a`` (3 cameras × 50) or ``b1`` (4 × 100)."""
    template = load_template()
    design = template["design_reference"]
    spec = design["events"]["items"][event]
    run_id = RUN_A if event == "a" else RUN_B1
    walks, geoms = _walkables(design)
    portals = [
        {
            "id": p["id"],
            "floor_id": FLOOR,
            "opening_m": {
                "a": p["a"],
                "b": p["b"],
                "width_m": p["width_m"],
                "sill_z_m": p["sill_z_m"],
                "height_m": p["height_m"],
            },
            "geometry_ref": f"geometry/{p['id']}.json",
            "geometry_sha256": sha(f"portal:{p['id']}"),
            "geometry_version": 1,
            "connects": list(p["connects"]),
            "state": "OPEN",
            "allowed_purposes": ["WALKABILITY", "DISPLAY"],
        }
        for p in design["portals"]["items"]
    ]
    static = {
        "schema_version": "controlled-scene.static.v1",
        "scene_id": "controlled-l-corridor",
        "scene_version": 1,
        "frame_id": "WORLD_SYNTHETIC",
        "length_unit": "m",
        "time_unit": "s",
        "world_axes": "BLENDER_Z_UP_RIGHT_HANDED",
        "floors": [
            {
                "floor_id": FLOOR,
                "support_plane": {"point_m": [0, 0, 0], "normal": [0, 0, 1]},
                "support_surface_ids": [FLOOR],
                "source_static_sha256": sha("static-source"),
                "approved_scope_ref": "scope:synthetic",
            }
        ],
        "source_static_sha256": sha("static-source"),
        "objects": _objects(design, geoms),
        "walkable": walks,
        "portals": portals,
        "stairs": [],
    }
    bindings = [
        {
            "run_id": run_id,
            "camera_id": cam,
            "clock_id": f"clock:{run_id}",
            "valid_time_range_s": [0, spec["duration_s"]],
            "visibility_index_ref": f"visibility/index_{event}.json",
            "binding_sha256": sha(f"binding:{run_id}:{cam}"),
        }
        for cam in spec["cameras"]
    ]
    cameras = {
        "schema_version": "controlled-scene.cameras.v1",
        "cameras": _camera_docs(design),
        "run_bindings": bindings,
    }
    n, fps = spec["sample_count_per_camera"], design["events"]["sampling"]["fps"]
    sampling = {
        "fps": fps,
        "image_size_px": [960, 540],
        "format": "PNG_RGB8",
        "sampling_version": "5fps-v1",
        "duration_s": spec["duration_s"],
        "sample_count_per_camera": n,
        "last_timestamp_s": spec["last_timestamp_s"],
    }
    manifest = {
        "schema_version": "controlled-scene.manifest.v1",
        "scene_id": "controlled-l-corridor",
        "scene_version": 1,
        "run_id": run_id,
        "clock_id": f"clock:{run_id}",
        "sampling": sampling,
        "source_sha256": sha("opaque-source"),
        "allowlist": [
            {"role": role, "filename": name, "file_sha256": sha(f"file:{role}")}
            for role, name in (
                ("scene_static", "scene_static.json"),
                ("cameras", "cameras.json"),
                ("rgb_index", "rgb_index.json"),
                ("runtime_profile", "runtime_profile.json"),
            )
        ],
    }
    rgb_index = {
        "schema_version": "controlled-scene.rgb-index.v1",
        "records": [
            {
                "camera_id": cam,
                "frame_index": i,
                "timestamp_s": i / fps,
                "rgb_ref": f"rgb/{cam}/frame_{i:06d}.png",
                "file_sha256": sha(f"rgb:{cam}:{i}"),
            }
            for cam in spec["cameras"]
            for i in range(n)
        ],
        "missing": [],
    }
    runtime_profile = {
        "schema_version": "controlled-scene.runtime-profile.v1",
        "scene_id": "controlled-l-corridor",
        "run_id": run_id,
        "sampling": copy.deepcopy(sampling),
    }
    return {
        "static": static,
        "cameras": cameras,
        "manifest": manifest,
        "rgb_index": rgb_index,
        "runtime_profile": runtime_profile,
    }


def write_bundle(directory: Path, bundle: dict[str, Any]) -> dict[str, str]:
    """Write the bundle to ``directory`` (allowlist hashes filled in); return file hashes."""
    directory.mkdir(parents=True, exist_ok=True)
    names = {
        "static": "scene_static.json",
        "cameras": "cameras.json",
        "rgb_index": "rgb_index.json",
        "runtime_profile": "runtime_profile.json",
    }
    roles = {
        "static": "scene_static",
        "cameras": "cameras",
        "rgb_index": "rgb_index",
        "runtime_profile": "runtime_profile",
    }
    hashes: dict[str, str] = {}
    for key, name in names.items():
        data = (json.dumps(bundle[key], indent=1, sort_keys=True) + "\n").encode()
        (directory / name).write_bytes(data)
        hashes[roles[key]] = hashlib.sha256(data).hexdigest()
    manifest = copy.deepcopy(bundle["manifest"])
    for entry in manifest["allowlist"]:
        entry["file_sha256"] = hashes[entry["role"]]
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return hashes
