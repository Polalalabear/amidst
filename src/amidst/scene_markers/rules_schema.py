"""Schema / required-field / enum rules (contract §3.1–§3.7, §3.10, §3.11)."""

from __future__ import annotations

import re
from typing import Any

from .context import Context, is_int, is_num, nonempty_str, point2, ring_points
from .contract import (
    APPROVAL_STATUSES,
    BINDING_REQUIRED,
    CAMERA_REQUIRED,
    COLLISION_SCOPES,
    FLOOR_REQUIRED,
    MANIFEST_REQUIRED,
    OBJECT_CLASSES,
    OBJECT_REQUIRED,
    OPENING_REQUIRED,
    PORTAL_REQUIRED,
    PORTAL_STATE,
    PURPOSES,
    RGB_MISSING_REQUIRED,
    RGB_RECORD_REQUIRED,
    RUNTIME_PROFILE_REQUIRED,
    SAMPLING_REQUIRED,
    SCHEMA_VERSION_PATTERN,
    SOLID_CLASSES,
    SOLID_REQUIRED,
    SOLID_ROLES,
    SOURCE_METHODS,
    STATIC_REQUIRED,
    STATIC_SCHEMA_VERSION,
    WALK_APPROVAL_REQUIRED,
    WALK_REQUIRED,
    WALK_STATUSES,
)
from .report import Collector, rule


def _missing(
    out: Collector,
    scope: str,
    base: str,
    record: dict[str, Any],
    required: tuple[str, ...],
    id_: str | None = None,
) -> None:
    for key in required:
        if key not in record:
            out.err("FIELD_MISSING", scope, f"{base}.{key}", f"缺少必填欄位 {key}", id_)


def _bounds_ok(raw: Any) -> bool:
    if not (isinstance(raw, list) and len(raw) == 2):
        return False
    lo, hi = raw
    return (
        isinstance(lo, list)
        and isinstance(hi, list)
        and len(lo) == 3
        and len(hi) == 3
        and all(is_num(v) for v in lo + hi)
        and all(a <= b for a, b in zip(lo, hi, strict=True))
    )


@rule(
    "SCH-001",
    "scene_static 頂層必填欄位、schema_version、單位、世界座標系",
    "契約 §3.1；設計稿 §5 E 介面",
)
def sch_static(ctx: Context, out: Collector) -> None:
    doc = ctx.static
    if not isinstance(doc, dict):
        out.err("SCENE_STATIC_MISSING", "scene_static", "$", "scene_static.json 不可用")
        return
    _missing(out, "scene_static", "$", doc, STATIC_REQUIRED)
    expectations = {
        "schema_version": STATIC_SCHEMA_VERSION,
        "length_unit": "m",
        "time_unit": "s",
        "world_axes": "BLENDER_Z_UP_RIGHT_HANDED",
    }
    for key, expected in expectations.items():
        if key in doc and doc[key] != expected:
            out.err(
                "FIELD_VALUE",
                "scene_static",
                f"$.{key}",
                f"{key} 必須是 {expected!r}（fail closed）",
            )
    if "scene_id" in doc and (
        not nonempty_str(doc["scene_id"]) or re.search(r"(^|[-_])v?[0-9]+$", str(doc["scene_id"]))
    ):
        out.warn(
            "SCENE_ID_FORMAT",
            "scene_static",
            "$.scene_id",
            "scene_id 不含版本號（例如 controlled-l-corridor）",
        )
    if "scene_version" in doc and not (is_int(doc["scene_version"]) and doc["scene_version"] >= 1):
        out.err(
            "FIELD_VALUE", "scene_static", "$.scene_version", "scene_version 必須是 >= 1 的整數"
        )
    if "frame_id" in doc and not nonempty_str(doc["frame_id"]):
        out.err("FIELD_VALUE", "scene_static", "$.frame_id", "frame_id 必須是非空字串")
    for key in ("floors", "objects", "walkable", "portals", "stairs"):
        if key in doc and not isinstance(doc[key], list):
            out.err("FIELD_TYPE", "scene_static", f"$.{key}", f"{key} 必須是陣列")


@rule("SCH-002", "floors[]：支撐面、source hash、核准範圍", "契約 §3.1")
def sch_floors(ctx: Context, out: Collector) -> None:
    floors = ctx.floors
    if not floors:
        out.err("FLOORS_EMPTY", "scene_static", "$.floors", "floors[] 至少要宣告一層")
    for index, floor in enumerate(floors):
        base = f"$.floors[{index}]"
        id_ = floor.get("floor_id") if isinstance(floor.get("floor_id"), str) else None
        _missing(out, "scene_static", base, floor, FLOOR_REQUIRED, id_)
        plane = floor.get("support_plane")
        if isinstance(plane, dict):
            for key in ("point_m", "normal"):
                vec = plane.get(key)
                if not (isinstance(vec, list) and len(vec) == 3 and all(is_num(v) for v in vec)):
                    out.err(
                        "FIELD_TYPE",
                        "scene_static",
                        f"{base}.support_plane.{key}",
                        f"support_plane.{key} 必須是三個有限數",
                        id_,
                    )
        elif "support_plane" in floor:
            out.err(
                "FIELD_TYPE",
                "scene_static",
                f"{base}.support_plane",
                "support_plane 必須是物件",
                id_,
            )
        ids = floor.get("support_surface_ids")
        if "support_surface_ids" in floor and not (
            isinstance(ids, list) and ids and all(nonempty_str(i) for i in ids)
        ):
            out.err(
                "FIELD_TYPE",
                "scene_static",
                f"{base}.support_surface_ids",
                "support_surface_ids 必須是非空字串陣列",
                id_,
            )


def _check_object(out: Collector, index: int, obj: dict[str, Any]) -> None:
    base = f"$.objects[{index}]"
    id_ = obj.get("id") if isinstance(obj.get("id"), str) else None
    _missing(out, "scene_static", base, obj, OBJECT_REQUIRED, id_)
    if "class" in obj and obj["class"] not in OBJECT_CLASSES:
        out.err(
            "ENUM_VALUE",
            "scene_static",
            f"{base}.class",
            f"class 必須是 {', '.join(OBJECT_CLASSES)}",
            id_,
        )
    if "source_method" in obj and obj["source_method"] not in SOURCE_METHODS:
        out.err(
            "ENUM_VALUE",
            "scene_static",
            f"{base}.source_method",
            "source_method 必須是 ANNOTATED_AT_CREATION 或 UNKNOWN",
            id_,
        )
    if "approval_status" in obj and obj["approval_status"] not in APPROVAL_STATUSES:
        out.err(
            "ENUM_VALUE",
            "scene_static",
            f"{base}.approval_status",
            "approval_status 必須是 APPROVED／NOT_EVALUATED／REJECTED",
            id_,
        )
    if "transform_applied" in obj and obj["transform_applied"] != "WORLD_METRES":
        out.err(
            "FIELD_VALUE",
            "scene_static",
            f"{base}.transform_applied",
            "transform_applied 必須是 WORLD_METRES",
            id_,
        )
    purposes = obj.get("allowed_purposes")
    if "allowed_purposes" in obj and not (
        isinstance(purposes, list) and all(p in PURPOSES for p in purposes)
    ):
        out.err(
            "ENUM_VALUE",
            "scene_static",
            f"{base}.allowed_purposes",
            f"allowed_purposes 必須是 {', '.join(PURPOSES)} 的子集",
            id_,
        )
    if "display_only" in obj and not isinstance(obj["display_only"], bool):
        out.err(
            "FIELD_TYPE", "scene_static", f"{base}.display_only", "display_only 必須是布林", id_
        )
    if "bounds_m" in obj and not _bounds_ok(obj["bounds_m"]):
        out.err(
            "FIELD_TYPE",
            "scene_static",
            f"{base}.bounds_m",
            "bounds_m 必須是 [[xmin,ymin,zmin],[xmax,ymax,zmax]] 且 min<=max",
            id_,
        )
    if "geometry_version" in obj and not (
        is_int(obj["geometry_version"]) and obj["geometry_version"] >= 1
    ):
        out.err(
            "FIELD_VALUE",
            "scene_static",
            f"{base}.geometry_version",
            "geometry_version 必須是 >= 1 的整數（初版 1）",
            id_,
        )
    for key in ("source_mesh", "source_object_id", "geometry_ref", "geometry_encoding_version"):
        if key in obj and not nonempty_str(obj[key]):
            out.err("FIELD_VALUE", "scene_static", f"{base}.{key}", f"{key} 必須是非空字串", id_)
    for key in ("scope_ref", "approval_ref", "approval_sha256"):
        if key in obj and obj[key] is not None and not isinstance(obj[key], str):
            out.err("FIELD_TYPE", "scene_static", f"{base}.{key}", f"{key} 必須是字串或 null", id_)


@rule("SCH-003", "objects[]：必填欄位、enum、bounds、用途、核准欄位", "契約 §3.3")
def sch_objects(ctx: Context, out: Collector) -> None:
    for index, obj in enumerate(ctx.objects):
        _check_object(out, index, obj)


@rule("SCH-004", "walkable[]：必填欄位、status、approval 結構", "契約 §3.4")
def sch_walkable(ctx: Context, out: Collector) -> None:
    for index, walk in enumerate(ctx.walkable):
        base = f"$.walkable[{index}]"
        id_ = walk.get("id") if isinstance(walk.get("id"), str) else None
        _missing(out, "scene_static", base, walk, WALK_REQUIRED, id_)
        if "status" in walk and walk["status"] not in WALK_STATUSES:
            out.err(
                "ENUM_VALUE",
                "scene_static",
                f"{base}.status",
                "status 必須是 WALKABLE／BLOCKED／UNKNOWN",
                id_,
            )
        if "polygon_m" in walk and ring_points(walk["polygon_m"]) is None:
            out.err(
                "FIELD_TYPE",
                "scene_static",
                f"{base}.polygon_m",
                "polygon_m 必須是至少三個有限座標的環",
                id_,
            )
        if "holes_m" in walk and (
            not isinstance(walk["holes_m"], list)
            or any(ring_points(h) is None for h in walk["holes_m"])
        ):
            out.err(
                "FIELD_TYPE",
                "scene_static",
                f"{base}.holes_m",
                "holes_m 必須是環的陣列（可為空）",
                id_,
            )
        conns = walk.get("connections")
        if "connections" in walk:
            if not isinstance(conns, list):
                out.err(
                    "FIELD_TYPE",
                    "scene_static",
                    f"{base}.connections",
                    "connections 必須是陣列",
                    id_,
                )
            else:
                for ci, conn in enumerate(conns):
                    if not (
                        isinstance(conn, dict) and "to_walk_id" in conn and "via_portal_id" in conn
                    ):
                        out.err(
                            "FIELD_MISSING",
                            "scene_static",
                            f"{base}.connections[{ci}]",
                            "connection 需有 to_walk_id 與 via_portal_id（可為 null）",
                            id_,
                        )
        approval = walk.get("approval")
        if "approval" in walk:
            if not isinstance(approval, dict):
                out.err(
                    "FIELD_TYPE", "scene_static", f"{base}.approval", "approval 必須是物件", id_
                )
            else:
                _missing(
                    out, "scene_static", f"{base}.approval", approval, WALK_APPROVAL_REQUIRED, id_
                )
                if "status" in approval and approval["status"] not in APPROVAL_STATUSES:
                    out.err(
                        "ENUM_VALUE",
                        "scene_static",
                        f"{base}.approval.status",
                        "approval.status 必須是 APPROVED／NOT_EVALUATED／REJECTED",
                        id_,
                    )
                if "verified_by" in approval and not isinstance(approval["verified_by"], list):
                    out.err(
                        "FIELD_TYPE",
                        "scene_static",
                        f"{base}.approval.verified_by",
                        "verified_by 必須是陣列",
                        id_,
                    )


@rule(
    "SCH-005",
    "牆與障礙物：footprint、base_z、height、role、collision_scope、body policy",
    "契約 §3.5（欄位合併於 objects[]，U01）",
)
def sch_solids(ctx: Context, out: Collector) -> None:
    for index, obj in enumerate(ctx.objects):
        if obj.get("class") not in SOLID_CLASSES:
            continue
        base = f"$.objects[{index}]"
        id_ = obj.get("id") if isinstance(obj.get("id"), str) else None
        _missing(out, "scene_static", base, obj, SOLID_REQUIRED, id_)
        if "role" in obj and obj["role"] not in SOLID_ROLES:
            out.err(
                "ENUM_VALUE", "scene_static", f"{base}.role", "role 必須是 PHYSICAL 或 DISPLAY", id_
            )
        if "collision_scope" in obj and obj["collision_scope"] not in COLLISION_SCOPES:
            out.err(
                "ENUM_VALUE",
                "scene_static",
                f"{base}.collision_scope",
                "collision_scope 必須是 EXACT_MESH／FOOTPRINT_EXTRUDED／UNKNOWN",
                id_,
            )
        if "footprint_m" in obj and ring_points(obj["footprint_m"]) is None:
            out.err(
                "FIELD_TYPE",
                "scene_static",
                f"{base}.footprint_m",
                "footprint_m 必須是至少三個有限座標的環",
                id_,
            )
        for key in ("base_z_m", "height_m"):
            if key in obj and not is_num(obj[key]):
                out.err("FIELD_TYPE", "scene_static", f"{base}.{key}", f"{key} 必須是有限數", id_)
        if is_num(obj.get("height_m")) and obj["height_m"] <= 0:
            out.err("FIELD_VALUE", "scene_static", f"{base}.height_m", "height_m 必須 > 0", id_)
        for key in ("body_policy_ref", "floor_id"):
            if key in obj and not nonempty_str(obj[key]):
                out.err(
                    "FIELD_VALUE", "scene_static", f"{base}.{key}", f"{key} 必須是非空字串", id_
                )
        if obj.get("collision_scope") == "EXACT_MESH" and not nonempty_str(obj.get("geometry_ref")):
            out.err(
                "EXACT_MESH_UNRESOLVABLE",
                "scene_static",
                f"{base}.geometry_ref",
                "EXACT_MESH 必須有可解析的 geometry_ref",
                id_,
            )


@rule(
    "SCH-006", "portals[]、stairs[]：開口、connects、state；首版 stairs 為空或標未使用", "契約 §3.6"
)
def sch_portals(ctx: Context, out: Collector) -> None:
    for index, portal in enumerate(ctx.portals):
        base = f"$.portals[{index}]"
        id_ = portal.get("id") if isinstance(portal.get("id"), str) else None
        _missing(out, "scene_static", base, portal, PORTAL_REQUIRED, id_)
        opening = portal.get("opening_m")
        if isinstance(opening, dict):
            _missing(out, "scene_static", f"{base}.opening_m", opening, OPENING_REQUIRED, id_)
            for key in ("a", "b"):
                if key in opening and point2(opening[key]) is None:
                    out.err(
                        "FIELD_TYPE",
                        "scene_static",
                        f"{base}.opening_m.{key}",
                        f"opening_m.{key} 必須是 [x,y]",
                        id_,
                    )
            for key in ("width_m", "sill_z_m", "height_m"):
                if key in opening and not is_num(opening[key]):
                    out.err(
                        "FIELD_TYPE",
                        "scene_static",
                        f"{base}.opening_m.{key}",
                        f"opening_m.{key} 必須是有限數",
                        id_,
                    )
        elif "opening_m" in portal:
            out.err("FIELD_TYPE", "scene_static", f"{base}.opening_m", "opening_m 必須是物件", id_)
        connects = portal.get("connects")
        if "connects" in portal and not (
            isinstance(connects, list)
            and len(connects) == 2
            and all(nonempty_str(c) for c in connects)
        ):
            out.err(
                "PORTAL_CONNECTS",
                "scene_static",
                f"{base}.connects",
                "connects 必須是兩個 walk ID；缺一側就是 UNKNOWN",
                id_,
            )
        if "state" in portal and portal["state"] != PORTAL_STATE:
            out.err(
                "FIELD_VALUE",
                "scene_static",
                f"{base}.state",
                "首版 state 固定為 OPEN（沒有動態門）",
                id_,
            )
    for index, stair in enumerate((ctx.static or {}).get("stairs") or []):
        if not (
            isinstance(stair, dict)
            and stair.get("used_in_first_round") is False
            and stair.get("acceptance") == "NOT_ACCEPTED"
        ):
            out.err(
                "STAIR_NOT_ALLOWED",
                "scene_static",
                f"$.stairs[{index}]",
                "首版 stairs 必須為空；預留實體須標 used_in_first_round:false、acceptance:"
                "NOT_ACCEPTED",
            )


@rule("SCH-007", "cameras[]：光學欄位齊全、列舉值、針孔模型、無 run 欄位", "契約 §3.7")
def sch_cameras(ctx: Context, out: Collector) -> None:
    from .contract import CAMERA_CONVENTION, CAMERA_RUN_FIELDS, PIXEL_ORIGIN

    cams = ctx.cameras
    if not cams:
        out.err("CAMERAS_EMPTY", "cameras", "$.cameras", "cameras[] 不可為空")
    for index, cam in enumerate(cams):
        base = f"$.cameras[{index}]"
        id_ = cam.get("camera_id") if isinstance(cam.get("camera_id"), str) else None
        _missing(out, "cameras", base, cam, CAMERA_REQUIRED, id_)
        for key, expected in (
            ("convention", CAMERA_CONVENTION),
            ("pixel_origin", PIXEL_ORIGIN),
            ("camera_model", "PINHOLE"),
        ):
            if key in cam and cam[key] != expected:
                out.err(
                    "FIELD_VALUE", "cameras", f"{base}.{key}", f"{key} 必須是 {expected!r}", id_
                )
        if "distortion" in cam and cam["distortion"] is not None:
            out.err(
                "FIELD_VALUE",
                "cameras",
                f"{base}.distortion",
                "distortion 必須是 null（針孔、無畸變）",
                id_,
            )
        if "meters_per_unit" in cam and cam["meters_per_unit"] != 1.0:
            out.err(
                "FIELD_VALUE",
                "cameras",
                f"{base}.meters_per_unit",
                "meters_per_unit 必須是 1.0",
                id_,
            )
        for key in (
            "fx",
            "fy",
            "cx",
            "cy",
            "sensor_width_mm",
            "sensor_height_mm",
            "focal_length_mm",
            "clip_start",
            "clip_end",
            "shift_x",
            "shift_y",
            "pixel_aspect_xy",
            "render_resolution_percentage",
        ):
            if key in cam and not is_num(cam[key]):
                out.err("FIELD_TYPE", "cameras", f"{base}.{key}", f"{key} 必須是有限數", id_)
        for key in ("width", "height"):
            if key in cam and not (is_int(cam[key]) and cam[key] > 0):
                out.err("FIELD_TYPE", "cameras", f"{base}.{key}", f"{key} 必須是正整數", id_)
        if (
            is_num(cam.get("clip_start"))
            and is_num(cam.get("clip_end"))
            and not 0 < cam["clip_start"] < cam["clip_end"]
        ):
            out.err(
                "FIELD_VALUE",
                "cameras",
                f"{base}.clip_start",
                "必須 0 < clip_start < clip_end",
                id_,
            )
        if "schema_version" in cam and not (
            isinstance(cam["schema_version"], str)
            and SCHEMA_VERSION_PATTERN.match(cam["schema_version"])
        ):
            out.err(
                "SCHEMA_VERSION_FORMAT",
                "cameras",
                f"{base}.schema_version",
                "schema_version 格式需為 controlled-scene.<name>.v<N>（值 UNKNOWN，U05）",
                id_,
            )
        for key in CAMERA_RUN_FIELDS:
            if key in cam:
                out.err(
                    "RUN_FIELD_IN_OPTICS",
                    "cameras",
                    f"{base}.{key}",
                    f"光學校正不得含 run 綁定欄位 {key}（應放在 run_bindings[]）",
                    id_,
                )


@rule("SCH-008", "run_bindings[]：欄位齊全、clock 格式", "契約 §3.7（run 綁定）、§4 clock ID")
def sch_bindings(ctx: Context, out: Collector) -> None:
    bindings = ctx.run_bindings
    if not bindings:
        out.err("RUN_BINDINGS_EMPTY", "cameras", "$.run_bindings", "run_bindings[] 不可為空")
    for index, binding in enumerate(bindings):
        base = f"$.run_bindings[{index}]"
        id_ = binding.get("camera_id") if isinstance(binding.get("camera_id"), str) else None
        _missing(out, "cameras", base, binding, BINDING_REQUIRED, id_)
        trange = binding.get("valid_time_range_s")
        if "valid_time_range_s" in binding and not (
            isinstance(trange, list)
            and len(trange) == 2
            and all(is_num(v) for v in trange)
            and trange[0] < trange[1]
        ):
            out.err(
                "FIELD_TYPE",
                "cameras",
                f"{base}.valid_time_range_s",
                "valid_time_range_s 必須是 [start, end) 且 start < end",
                id_,
            )
        if (
            nonempty_str(binding.get("run_id"))
            and nonempty_str(binding.get("clock_id"))
            and binding["clock_id"] != f"clock:{binding['run_id']}"
        ):
            out.err(
                "CLOCK_ID_FORMAT",
                "cameras",
                f"{base}.clock_id",
                "clock_id 必須是 clock:<run_id>",
                id_,
            )


@rule("SCH-009", "safe manifest：欄位、sampling 結構", "契約 §3.10、§4")
def sch_manifest(ctx: Context, out: Collector) -> None:
    doc = ctx.manifest
    if not isinstance(doc, dict):
        out.err("MANIFEST_MISSING", "manifest", "$", "manifest.json 不可用")
        return
    _missing(out, "manifest", "$", doc, MANIFEST_REQUIRED)
    if "schema_version" in doc and not (
        isinstance(doc["schema_version"], str)
        and SCHEMA_VERSION_PATTERN.match(doc["schema_version"])
    ):
        out.err(
            "SCHEMA_VERSION_FORMAT",
            "manifest",
            "$.schema_version",
            "schema_version 格式需為 controlled-scene.<name>.v<N>（值 UNKNOWN，U05）",
        )
    sampling = doc.get("sampling")
    if isinstance(sampling, dict):
        _missing(out, "manifest", "$.sampling", sampling, SAMPLING_REQUIRED)
        if "format" in sampling and sampling["format"] != "PNG_RGB8":
            out.err("FIELD_VALUE", "manifest", "$.sampling.format", "format 必須是 PNG_RGB8")
        size = sampling.get("image_size_px")
        if "image_size_px" in sampling and not (
            isinstance(size, list) and len(size) == 2 and all(is_int(v) and v > 0 for v in size)
        ):
            out.err(
                "FIELD_TYPE",
                "manifest",
                "$.sampling.image_size_px",
                "image_size_px 必須是 [寬, 高] 正整數",
            )
        for key in ("fps", "duration_s", "last_timestamp_s"):
            if key in sampling and not is_num(sampling[key]):
                out.err("FIELD_TYPE", "manifest", f"$.sampling.{key}", f"{key} 必須是有限數")
        if "sample_count_per_camera" in sampling and not (
            is_int(sampling["sample_count_per_camera"]) and sampling["sample_count_per_camera"] > 0
        ):
            out.err(
                "FIELD_TYPE",
                "manifest",
                "$.sampling.sample_count_per_camera",
                "sample_count_per_camera 必須是正整數",
            )
    elif "sampling" in doc:
        out.err("FIELD_TYPE", "manifest", "$.sampling", "sampling 必須是物件")


@rule(
    "SCH-010",
    "rgb_index：records[]／missing[] 結構",
    "契約 v1.1 §3.11、§2.3（v1.0 @2643771 未分 records／missing）",
)
def sch_rgb_index(ctx: Context, out: Collector) -> None:
    doc = ctx.rgb_index
    if not isinstance(doc, dict):
        out.err("RGB_INDEX_MISSING", "rgb_index", "$", "rgb_index.json 不可用")
        return
    for key in ("records", "missing"):
        if not isinstance(doc.get(key), list):
            out.err(
                "FIELD_TYPE",
                "rgb_index",
                f"$.{key}",
                f"{key} 必須是陣列（v1.1：records[] 與 missing[] 分開）",
            )
    for kind, required in (("records", RGB_RECORD_REQUIRED), ("missing", RGB_MISSING_REQUIRED)):
        for index, item in enumerate(doc.get(kind) or []):
            base = f"$.{kind}[{index}]"
            if not isinstance(item, dict):
                out.err("FIELD_TYPE", "rgb_index", base, f"{kind} 項目必須是物件")
                continue
            _missing(
                out,
                "rgb_index",
                base,
                item,
                required,
                item.get("camera_id") if isinstance(item.get("camera_id"), str) else None,
            )
            if "frame_index" in item and not (
                is_int(item["frame_index"]) and item["frame_index"] >= 0
            ):
                out.err(
                    "FIELD_TYPE",
                    "rgb_index",
                    f"{base}.frame_index",
                    "frame_index 必須是 >= 0 的整數",
                )
            if "timestamp_s" in item and not is_num(item["timestamp_s"]):
                out.err(
                    "FIELD_TYPE", "rgb_index", f"{base}.timestamp_s", "timestamp_s 必須是有限數"
                )
            if kind == "missing" and "reason" in item and not nonempty_str(item["reason"]):
                out.err(
                    "FIELD_VALUE",
                    "rgb_index",
                    f"{base}.reason",
                    "missing[].reason 必須是非空字串（例如 RGB_RECORD_ABSENT）",
                )


@rule("SCH-011", "runtime_profile：最小欄位", "契約 §3.11（欄位清單 UNKNOWN，U04）")
def sch_runtime_profile(ctx: Context, out: Collector) -> None:
    doc = ctx.runtime_profile
    if not isinstance(doc, dict):
        out.err("RUNTIME_PROFILE_MISSING", "runtime_profile", "$", "runtime_profile.json 不可用")
        return
    _missing(out, "runtime_profile", "$", doc, RUNTIME_PROFILE_REQUIRED)
    if "schema_version" in doc and not (
        isinstance(doc["schema_version"], str)
        and SCHEMA_VERSION_PATTERN.match(doc["schema_version"])
    ):
        out.err(
            "SCHEMA_VERSION_FORMAT",
            "runtime_profile",
            "$.schema_version",
            "schema_version 格式需為 controlled-scene.<name>.v<N>（U05）",
        )
