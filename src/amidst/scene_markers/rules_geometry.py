"""Floor, walkable, obstacle and portal geometry rules.

Polygon work uses shapely; ``polygons_of`` and ``union_all`` come from the K7 map verifier
(``amidst.evaluation.map_verification``) and are imported, not copied.
"""

from __future__ import annotations

import math
from typing import Any

from shapely.geometry import LinearRing, LineString, Point, Polygon, box
from shapely.validation import explain_validity

from amidst.evaluation.map_verification import polygons_of, union_all

from .context import (
    Context,
    as_dict,
    as_list,
    bounds_of,
    is_num,
    point2,
    polygon_from,
    ring_is_ccw,
    ring_points,
    signed_area,
)
from .report import Collector, Skip, rule


def _area(geometry: Any) -> float:
    return float(polygons_of(geometry).area)


def _walk_label(walk: dict[str, Any]) -> str | None:
    return walk.get("id") if isinstance(walk.get("id"), str) else None


@rule(
    "FLR-001",
    "所有可走地板的支撐面都在 z=0、法向 +Z，單一樓層；地板頂面與障礙物底面為 0",
    "D36；契約 §3.1（首版只有一層、一個平面）；設計稿 §1",
)
def floor_z_zero(ctx: Context, out: Collector) -> None:
    tol = ctx.params.floor_z_tol_m
    floors = ctx.floors
    if len(floors) != 1:
        out.err(
            "FLOOR_COUNT",
            "scene_static",
            "$.floors",
            f"首版只有一層、一個平面（D36）；實際 {len(floors)} 層",
        )
    for index, floor in enumerate(floors):
        plane = floor.get("support_plane")
        if not isinstance(plane, dict):
            continue
        point, normal = plane.get("point_m"), plane.get("normal")
        if (
            isinstance(point, list)
            and len(point) == 3
            and all(is_num(v) for v in point)
            and abs(point[2]) > tol
        ):
            out.err(
                "FLOOR_Z_NOT_ZERO",
                "scene_static",
                f"$.floors[{index}].support_plane.point_m",
                f"支撐面 z 必須為 0（D36），實際 {point[2]}",
                floor.get("floor_id"),
            )
        if isinstance(normal, list) and len(normal) == 3 and all(is_num(v) for v in normal):
            length = math.sqrt(sum(v * v for v in normal))
            if (
                length == 0
                or abs(normal[0] / length) > 1e-6
                or abs(normal[1] / length) > 1e-6
                or normal[2] / length < 1 - 1e-6
            ):
                out.err(
                    "FLOOR_NORMAL",
                    "scene_static",
                    f"$.floors[{index}].support_plane.normal",
                    "支撐面法向必須是 +Z（不設高低差或分層）",
                    floor.get("floor_id"),
                )
    for index, walk in enumerate(ctx.walkable):
        for ring_name, rings in (
            ("polygon_m", [walk.get("polygon_m")]),
            ("holes_m", walk.get("holes_m") or []),
        ):
            for ring in rings:
                for vertex in ring if isinstance(ring, list) else []:
                    if (
                        isinstance(vertex, list)
                        and len(vertex) == 3
                        and is_num(vertex[2])
                        and abs(vertex[2]) > tol
                    ):
                        out.err(
                            "FLOOR_Z_NOT_ZERO",
                            "scene_static",
                            f"$.walkable[{index}].{ring_name}",
                            f"可走地板頂點 z 必須為 0（D36），實際 {vertex[2]}",
                            _walk_label(walk),
                        )
                        break
    for index, obj in enumerate(ctx.objects):
        bounds = bounds_of(obj)
        if bounds is None:
            continue
        if obj.get("class") == "WALKABLE" and abs(bounds[1][2]) > tol:
            out.err(
                "FLOOR_Z_NOT_ZERO",
                "scene_static",
                f"$.objects[{index}].bounds_m",
                f"WALKABLE 的地板頂面（zmax）必須為 0，實際 {bounds[1][2]}",
                obj.get("id"),
            )
        if obj.get("class") == "OBSTACLE" and abs(bounds[0][2]) > ctx.params.bounds_tol_m:
            out.err(
                "OBSTACLE_NOT_ON_FLOOR",
                "scene_static",
                f"$.objects[{index}].bounds_m",
                f"OBSTACLE 底面（zmin）必須在地板 z=0，實際 {bounds[0][2]}",
                obj.get("id"),
            )


@rule(
    "WLK-001",
    "walk polygon 合法：不自交、外環逆時針、洞順時針、面積 > 0",
    "契約 §3.4（逆時針、不自交）；設計稿 §1.1.1（holes_m 為 CW，U11）",
)
def walk_polygon_valid(ctx: Context, out: Collector) -> None:
    for index, walk in enumerate(ctx.walkable):
        base, id_ = f"$.walkable[{index}]", _walk_label(walk)
        outer = ring_points(walk.get("polygon_m"))
        if outer is None:
            continue  # SCH-004 reports the malformed ring
        if not LinearRing(outer).is_simple:
            out.err(
                "POLYGON_SELF_INTERSECT", "scene_static", f"{base}.polygon_m", "polygon_m 自交", id_
            )
            continue
        if abs(signed_area(outer)) <= 0:
            out.err(
                "POLYGON_DEGENERATE", "scene_static", f"{base}.polygon_m", "polygon_m 面積為 0", id_
            )
            continue
        if not ring_is_ccw(outer):
            out.err(
                "POLYGON_ORIENTATION",
                "scene_static",
                f"{base}.polygon_m",
                "polygon_m 必須逆時針（CCW）",
                id_,
            )
        holes = as_list(walk.get("holes_m"))
        for hi, hole_raw in enumerate(holes):
            hole = ring_points(hole_raw)
            if hole is None:
                continue
            if abs(signed_area(hole)) <= 0 or not LinearRing(hole).is_simple:
                out.err(
                    "POLYGON_SELF_INTERSECT",
                    "scene_static",
                    f"{base}.holes_m[{hi}]",
                    "洞退化或自交",
                    id_,
                )
            elif ring_is_ccw(hole):
                out.err(
                    "POLYGON_ORIENTATION",
                    "scene_static",
                    f"{base}.holes_m[{hi}]",
                    "holes_m 必須順時針（CW，設計稿 §1.1.1）",
                    id_,
                )
        poly = polygon_from(walk.get("polygon_m"), walk.get("holes_m"))
        if poly is not None and not poly.is_valid:
            out.err(
                "POLYGON_INVALID",
                "scene_static",
                base,
                f"polygon 不合法：{explain_validity(poly)}",
                id_,
            )


@rule(
    "WLK-002",
    "洞必須在外環內部、不與外環共邊或相接；洞之間不重疊",
    "設計稿 §1.1.1（不輸出與外環共邊的無效洞）",
)
def walk_holes_interior(ctx: Context, out: Collector) -> None:
    tol = ctx.params.geometry_tol_m
    for index, walk in enumerate(ctx.walkable):
        outer = ring_points(walk.get("polygon_m"))
        holes = [ring_points(h) for h in as_list(walk.get("holes_m"))]
        if outer is None:
            continue
        outer_poly = Polygon(outer)
        solid_holes: list[Polygon] = []
        for hi, hole in enumerate(holes):
            if hole is None:
                continue
            hole_poly = Polygon(hole)
            if (
                not outer_poly.buffer(-tol).contains(hole_poly)
                or hole_poly.distance(outer_poly.exterior) <= tol
            ):
                out.err(
                    "HOLE_NOT_INTERIOR",
                    "scene_static",
                    f"$.walkable[{index}].holes_m[{hi}]",
                    "洞必須完全在外環內部且不接觸外環；與外環共邊的洞應改為外環的差集",
                    _walk_label(walk),
                )
            for other in solid_holes:
                if hole_poly.intersection(other).area > tol:
                    out.err(
                        "HOLES_OVERLAP",
                        "scene_static",
                        f"$.walkable[{index}].holes_m[{hi}]",
                        "洞之間重疊",
                        _walk_label(walk),
                    )
            solid_holes.append(hole_poly)


@rule(
    "WLK-003",
    "walkable 之間面積不重複（重疊地板有唯一歸屬）",
    "契約 §3.4「面積不得重複計算」；設計稿 §1.1",
)
def walk_no_overlap(ctx: Context, out: Collector) -> None:
    polys = ctx.walk_polygons()
    ids = sorted(polys)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            if not (polys[a].is_valid and polys[b].is_valid):
                continue
            overlap = polys[a].intersection(polys[b]).area
            if overlap > ctx.params.overlap_area_tol_m2:
                out.err(
                    "WALK_OVERLAP",
                    "scene_static",
                    "$.walkable",
                    f"{a} 與 {b} 重疊 {overlap:.6f} m²；重疊處只能歸一個 walkable",
                    a,
                )


@rule(
    "WLK-004",
    "connections 對稱；via_portal_id 與 portal.connects 一致；via 為 null 時兩塊地板必須共邊",
    "契約 §3.4 connections",
)
def walk_connections(ctx: Context, out: Collector) -> None:
    polys = ctx.walk_polygons()
    edges: dict[tuple[str, str], list[Any]] = {}
    for walk in ctx.walkable:
        id_ = _walk_label(walk)
        seen: set[tuple[Any, Any]] = set()
        for conn in walk.get("connections") or []:
            if not isinstance(conn, dict):
                continue
            to, via = conn.get("to_walk_id"), conn.get("via_portal_id")
            if to == id_:
                out.err("CONNECTION_SELF", "scene_static", "$.walkable", "connection 指向自己", id_)
            if (to, via) in seen:
                out.err(
                    "CONNECTION_DUPLICATE",
                    "scene_static",
                    "$.walkable",
                    f"connection 重複：{to}",
                    id_,
                )
            seen.add((to, via))
            if isinstance(id_, str) and isinstance(to, str):
                edges.setdefault((id_, to), []).append(via)
    by_walk = {w.get("id"): w for w in ctx.walkable}
    for (a, b), vias in edges.items():
        if b not in by_walk:
            continue  # dangling: ID-004
        for via in vias:
            if via not in edges.get((b, a), []):
                out.err(
                    "CONNECTION_ASYMMETRIC",
                    "scene_static",
                    "$.walkable",
                    f"{a}→{b}（via {via}）在 {b} 沒有對稱的反向 connection；必須雙向各寫一次",
                    a,
                )
            if via is None:
                pa, pb = polys.get(a), polys.get(b)
                if pa is not None and pb is not None and pa.is_valid and pb.is_valid:
                    shared = pa.boundary.intersection(pb.boundary).length
                    if shared <= ctx.params.geometry_tol_m:
                        out.err(
                            "CONNECTION_NO_SHARED_EDGE",
                            "scene_static",
                            "$.walkable",
                            f"{a}↔{b} 的 via_portal_id 為 null，但兩塊地板沒有共邊；null "
                            "只用於連續地板接界，不代表可以穿牆",
                            a,
                        )
            else:
                portal = next((p for p in ctx.portals if p.get("id") == via), None)
                if portal is not None and set(portal.get("connects") or []) != {a, b}:
                    out.err(
                        "CONNECTION_PORTAL_MISMATCH",
                        "scene_static",
                        "$.walkable",
                        f"{a}→{b} 經 {via}，但 {via}.connects 不是這兩塊地板",
                        a,
                    )


@rule(
    "WLK-005", "walkable 連通關係與設計稿 §1.1 對稱表一致", "設計稿 §1.1 對稱 connections", "design"
)
def walk_connections_design(ctx: Context, out: Collector) -> None:
    if ctx.design is None:
        raise Skip("沒有 design_reference")
    expected_pairs = {
        (e["a"], e["b"], e["via_portal_id"]) for e in ctx.design["walkable_connections"]["edges"]
    } | {(e["b"], e["a"], e["via_portal_id"]) for e in ctx.design["walkable_connections"]["edges"]}
    actual = {
        (w.get("id"), c.get("to_walk_id"), c.get("via_portal_id"))
        for w in ctx.walkable
        for c in (w.get("connections") or [])
        if isinstance(c, dict)
    }
    for item in sorted(expected_pairs - actual, key=str):
        out.err(
            "CONNECTION_MISSING",
            "scene_static",
            "$.walkable",
            f"設計稿預期的連通 {item[0]}→{item[1]}（via {item[2]}）不存在",
            item[0],
        )
    for item in sorted(actual - expected_pairs, key=str):
        out.err(
            "CONNECTION_UNEXPECTED",
            "scene_static",
            "$.walkable",
            f"設計稿沒有的連通 {item[0]}→{item[1]}（via {item[2]}）；不自動補連通",
            item[0] if isinstance(item[0], str) else None,
        )


@rule(
    "WLK-006",
    "挖洞與設計稿 10 處清單一致（逐處移除、各 walk 面積、總面積 2.0705 m²、唯一內部洞）",
    "設計稿 §1.1.1（10 處、總面積 2.0705 m²、扣除後 136.8095 m²）",
    "design",
)
def walk_cutouts(ctx: Context, out: Collector) -> None:
    design = ctx.design
    if design is None:
        raise Skip("沒有 design_reference")
    p = ctx.params
    pre = {k: Polygon(v) for k, v in design["walkable_precut_polygons_m"]["polygons"].items()}
    cuts = design["cutouts"]["items"]
    walks = ctx.walk_polygons()
    if len(cuts) != 10:
        out.err(
            "TEMPLATE_CUTS_COUNT",
            "template",
            "design_reference.cutouts",
            f"template 的挖除清單應為 10 處，實際 {len(cuts)}（設計稿 §1.1.1）",
        )
    if (
        abs(sum(c["area_m2"] for c in cuts) - design["cutouts"]["total_area_m2"])
        > p.cut_item_area_tol_m2
    ):
        out.err(
            "TEMPLATE_CUTS_TOTAL",
            "template",
            "design_reference.cutouts",
            "template 的各處面積加總與 total_area_m2 不符",
        )
    boxes = {
        c["object_id"]: box(c["xy_box_m"][0], c["xy_box_m"][2], c["xy_box_m"][1], c["xy_box_m"][3])
        for c in cuts
    }
    per_owner: dict[str, list[dict[str, Any]]] = {}
    for c in cuts:
        per_owner.setdefault(c["owner"], []).append(c)
        owner_pre = pre.get(c["owner"])
        if (
            owner_pre is not None
            and abs(owner_pre.intersection(boxes[c["object_id"]]).area - c["area_m2"])
            > p.cut_item_area_tol_m2
        ):
            out.err(
                "TEMPLATE_CUT_AREA",
                "template",
                "design_reference.cutouts",
                f"template 內 {c['object_id']} 與 {c['owner']} 挖前 polygon 的交集面積和清單不符",
                c["object_id"],
            )
    for c in cuts:
        cut_box = boxes[c["object_id"]]
        for wid, poly in walks.items():
            if poly.is_valid and poly.intersection(cut_box).area > p.cut_item_area_tol_m2:
                owner_note = (
                    "（歸屬 " + c["owner"] + "）"
                    if wid == c["owner"]
                    else "（非歸屬 walk，亦不得保留）"
                )
                out.err(
                    "CUT_NOT_REMOVED",
                    "scene_static",
                    "$.walkable",
                    f"{wid} 仍包含應挖除的 {c['object_id']} 範圍 {owner_note}",
                    c["object_id"],
                )
        if c["owner"] not in walks:
            out.err(
                "CUT_OWNER_MISSING",
                "scene_static",
                "$.walkable",
                f"挖除 {c['object_id']} 的歸屬 walkable {c['owner']} 不存在",
                c["object_id"],
            )
    expected_holes = design["cutouts"]["hole_walks"]
    for walk in ctx.walkable:
        n_holes = len(walk.get("holes_m") or [])
        if n_holes != expected_holes.get(walk.get("id"), 0):
            out.err(
                "HOLE_COUNT",
                "scene_static",
                "$.walkable",
                f"holes_m 數量應為 {expected_holes.get(walk.get('id'), 0)}，實際 {n_holes}；只有 "
                "SCREEN_R102 是內部洞，其餘應改外環",
                _walk_label(walk),
            )
    removed_total = 0.0
    for owner, owner_cuts in per_owner.items():
        owner_poly, poly_pre = walks.get(owner), pre.get(owner)
        if owner_poly is None or poly_pre is None or not owner_poly.is_valid:
            continue
        removed = poly_pre.area - owner_poly.area
        removed_total += removed
        expected_removed = sum(c["area_m2"] for c in owner_cuts)
        if abs(removed - expected_removed) > p.cut_item_area_tol_m2 * len(owner_cuts):
            out.err(
                "CUT_AREA_MISMATCH",
                "scene_static",
                "$.walkable",
                f"{owner} 挖除面積 {removed:.4f} m² 與設計稿 {expected_removed:.4f} m² 不符",
                owner,
            )
        expected_shape = poly_pre.difference(union_all(boxes[c["object_id"]] for c in owner_cuts))
        drift = owner_poly.symmetric_difference(expected_shape).area
        if drift > p.walk_shape_tol_m2:
            out.err(
                "WALK_SHAPE_MISMATCH",
                "scene_static",
                "$.walkable",
                f"{owner} 與設計稿挖除後的形狀差 {drift:.4f} m²（容差 {p.walk_shape_tol_m2}）",
                owner,
            )
        added = owner_poly.difference(poly_pre).area
        if added > p.walk_shape_tol_m2:
            out.err(
                "WALK_AREA_ADDED",
                "scene_static",
                "$.walkable",
                f"{owner} 多出設計稿挖前範圍以外的面積 {added:.4f} m²",
                owner,
            )
    for wid, poly_pre in pre.items():
        if (
            wid not in per_owner
            and wid in walks
            and walks[wid].is_valid
            and abs(walks[wid].area - poly_pre.area) > p.walk_shape_tol_m2
        ):
            out.err(
                "WALK_SHAPE_MISMATCH",
                "scene_static",
                "$.walkable",
                f"{wid} 無挖除項，面積應等於設計稿 {poly_pre.area:.4f} m²",
                wid,
            )
    if all(w in walks and walks[w].is_valid for w in pre):
        total_removed = sum(pre[w].area - walks[w].area for w in pre)
        if abs(total_removed - design["cutouts"]["total_area_m2"]) > p.cut_total_area_tol_m2:
            out.err(
                "CUT_TOTAL_MISMATCH",
                "scene_static",
                "$.walkable",
                f"挖除總面積 {total_removed:.4f} m² 與設計稿 "
                f"{design['cutouts']['total_area_m2']} m² 不符（容差 {p.cut_total_area_tol_m2}）",
            )
        total_exported = sum(walks[w].area for w in pre)
        expected_total = design["walkable_precut_polygons_m"]["postcut_total_area_m2"]
        if abs(total_exported - expected_total) > p.walk_total_area_tol_m2:
            out.err(
                "WALK_TOTAL_MISMATCH",
                "scene_static",
                "$.walkable",
                f"扣除後可走總面積 {total_exported:.4f} m² 與設計稿 {expected_total} m² 不符",
            )
    else:
        out.err(
            "WALK_SET_INCOMPLETE",
            "scene_static",
            "$.walkable",
            "設計稿的六個 WALK_* 沒有全部可用，無法核對總面積",
        )


def _footprint(obj: dict[str, Any]) -> Polygon | None:
    ring = ring_points(obj.get("footprint_m"))
    return Polygon(ring) if ring is not None else None


@rule(
    "OBS-001",
    "牆／障礙物 footprint 合法，且和 bounds_m、base_z／height 一致",
    "契約 §3.5、§3.3（bounds 只是外框）",
)
def solid_footprint(ctx: Context, out: Collector) -> None:
    tol = ctx.params.bounds_tol_m
    for index, obj in enumerate(ctx.objects):
        if obj.get("class") not in ("WALL", "OBSTACLE"):
            continue
        base, id_ = f"$.objects[{index}]", obj.get("id")
        poly = _footprint(obj)
        if poly is None:
            continue
        if not poly.is_valid or poly.area <= 0:
            out.err(
                "FOOTPRINT_INVALID",
                "scene_static",
                f"{base}.footprint_m",
                f"footprint 不合法或面積為 0：{explain_validity(poly)}",
                id_,
            )
            continue
        bounds = bounds_of(obj)
        if bounds is not None:
            minx, miny, maxx, maxy = poly.bounds
            if (
                max(
                    abs(minx - bounds[0][0]),
                    abs(miny - bounds[0][1]),
                    abs(maxx - bounds[1][0]),
                    abs(maxy - bounds[1][1]),
                )
                > tol
            ):
                out.err(
                    "FOOTPRINT_BOUNDS_MISMATCH",
                    "scene_static",
                    f"{base}.bounds_m",
                    "footprint 的外框與 bounds_m 的 XY 不一致",
                    id_,
                )
            if is_num(obj.get("base_z_m")) and is_num(obj.get("height_m")):
                if (
                    abs(obj["base_z_m"] - bounds[0][2]) > tol
                    or abs(obj["base_z_m"] + obj["height_m"] - bounds[1][2]) > tol
                ):
                    out.err(
                        "Z_BOUNDS_MISMATCH",
                        "scene_static",
                        f"{base}.bounds_m",
                        "base_z_m／height_m 與 bounds_m 的 z 範圍不一致",
                        id_,
                    )


@rule(
    "OBS-002",
    "牆／障礙物不佔用 walkable（障礙物與 walkable 的重疊歸屬已從 walkable 扣除）",
    "契約 §3.4、§3.5；設計稿 §1.1.1",
)
def solids_exclude_walkable(ctx: Context, out: Collector) -> None:
    walks = [p for p in ctx.walk_polygons().values() if p.is_valid]
    if not walks:
        return
    floor_union = union_all(walks)
    for obj in ctx.solids:
        poly = _footprint(obj)
        if poly is None or not poly.is_valid or obj.get("role") == "DISPLAY":
            continue
        if not is_num(obj.get("base_z_m")) or obj["base_z_m"] >= ctx.params.blocking_height_m:
            continue  # lintel / header above body height does not occupy the floor
        overlap = _area(poly.intersection(floor_union))
        if overlap > ctx.params.overlap_area_tol_m2:
            out.err(
                "SOLID_OVERLAPS_WALKABLE",
                "scene_static",
                "$.walkable",
                f"{obj.get('id')} 佔用的 {overlap:.4f} m² 仍在 walkable 內；必須從歸屬的 walk 扣除",
                obj.get("id"),
            )


@rule(
    "OBS-003",
    "遮屏淨距：包絡 r=.30 外至名義路線 >= .10 m",
    "D38；設計稿 §1.2（路線資料來源 UNKNOWN，U09）",
    "design",
)
def screen_clearance(ctx: Context, out: Collector) -> None:
    design = ctx.design
    if design is None:
        raise Skip("沒有 design_reference")
    spec = design["clearance_checks"]
    line = LineString(spec["reference_polyline_m"])
    p = ctx.params
    for obstacle_id in spec["obstacle_ids"]:
        obj = ctx.object_by_id(obstacle_id)
        poly = _footprint(obj) if obj else None
        if poly is None or not poly.is_valid:
            out.err(
                "CLEARANCE_UNKNOWN",
                "scene_static",
                "$.objects",
                "找不到可用的 footprint，無法核對淨距",
                obstacle_id,
            )
            continue
        clearance = poly.distance(line) - p.envelope_radius_m
        if clearance < p.min_clearance_m - p.clearance_tol_m:
            out.err(
                "CLEARANCE_TOO_SMALL",
                "scene_static",
                "$.objects",
                f"包絡 r={p.envelope_radius_m} m 外淨距 {clearance:.6f} m < {p.min_clearance_m} m",
                obstacle_id,
            )


@rule(
    "OBS-004",
    "牆／障礙物外框與設計稿附錄 A 的 AABB 一致",
    "設計稿 附錄 A（D52 若改牆須更新 template，U10）",
    "design",
)
def solids_design_aabb(ctx: Context, out: Collector) -> None:
    design = ctx.design
    if design is None:
        raise Skip("沒有 design_reference")
    tol = ctx.params.bounds_tol_m
    for item in design["solids_aabb_m"]["items"]:
        obj = ctx.object_by_id(item["id"])
        if obj is None:
            continue  # ID-005 reports the missing object
        bounds = bounds_of(obj)
        flat = [v for b in bounds for v in b] if bounds is not None else None
        expected = [v for b in item["bounds_m"] for v in b]
        if (
            flat is None
            or len(flat) != 6
            or any(abs(a - b) > tol for a, b in zip(flat, expected, strict=True))
        ):
            out.err(
                "AABB_MISMATCH",
                "scene_static",
                "$.objects",
                f"bounds_m 與設計稿附錄 A 不一致（容差 {tol} m）",
                item["id"],
            )


@rule(
    "PRT-001",
    "門：寬度＝兩端距離、兩端落在相連的兩塊 walkable 上、connections 互相對應",
    "契約 §3.6、§3.4；設計稿 §1",
)
def portal_geometry(ctx: Context, out: Collector) -> None:
    polys = ctx.walk_polygons()
    tol = ctx.params.bounds_tol_m
    by_walk = {w.get("id"): w for w in ctx.walkable}
    for index, portal in enumerate(ctx.portals):
        id_, opening = portal.get("id"), portal.get("opening_m")
        base = f"$.portals[{index}]"
        if not isinstance(opening, dict):
            continue
        a, b = opening.get("a"), opening.get("b")
        if not (
            isinstance(a, list)
            and isinstance(b, list)
            and len(a) == 2
            and len(b) == 2
            and all(is_num(v) for v in a + b)
        ):
            continue
        if is_num(opening.get("width_m")) and abs(math.dist(a, b) - opening["width_m"]) > tol:
            out.err(
                "PORTAL_WIDTH",
                "scene_static",
                f"{base}.opening_m.width_m",
                f"width_m 與兩端距離 {math.dist(a, b):.4f} 不一致",
                id_,
            )
        if is_num(opening.get("sill_z_m")) and opening["sill_z_m"] < 0:
            out.err(
                "PORTAL_SILL",
                "scene_static",
                f"{base}.opening_m.sill_z_m",
                "sill_z_m 不可為負",
                id_,
            )
        if is_num(opening.get("height_m")) and opening["height_m"] <= 0:
            out.err(
                "PORTAL_HEIGHT",
                "scene_static",
                f"{base}.opening_m.height_m",
                "height_m 必須 > 0",
                id_,
            )
        connects = portal.get("connects")
        if not (isinstance(connects, list) and len(connects) == 2):
            continue
        if connects[0] == connects[1]:
            out.err(
                "PORTAL_CONNECTS",
                "scene_static",
                f"{base}.connects",
                "connects 兩側必須是不同的 walkable",
                id_,
            )
        for side in connects:
            poly = polys.get(side)
            if poly is None or not poly.is_valid:
                continue
            for end in (a, b):
                if poly.distance(Point(end)) > tol:
                    out.err(
                        "PORTAL_OFF_WALKABLE",
                        "scene_static",
                        f"{base}.opening_m",
                        f"開口端點 {end} 不在 {side} 上（門洞地板必須有實體支撐）",
                        id_,
                    )
        for here, there in (connects, connects[::-1]):
            conns = (by_walk.get(here) or {}).get("connections") or []
            if not any(
                isinstance(c, dict)
                and c.get("to_walk_id") == there
                and c.get("via_portal_id") == id_
                for c in conns
            ):
                out.err(
                    "PORTAL_CONNECTION_MISSING",
                    "scene_static",
                    f"{base}.connects",
                    f"{here} 沒有經 {id_} 通往 {there} 的 connection",
                    id_,
                )


@rule(
    "PRT-002",
    "門的位置、尺寸、sill_z 與設計稿一致",
    "設計稿 §1 表（門寬 1.2、高 2.4、sill_z=0）",
    "design",
)
def portal_design(ctx: Context, out: Collector) -> None:
    design = ctx.design
    if design is None:
        raise Skip("沒有 design_reference")
    tol = ctx.params.bounds_tol_m
    for item in design["portals"]["items"]:
        portal = next((p for p in ctx.portals if p.get("id") == item["id"]), None)
        if portal is None:
            out.err(
                "PORTAL_MISSING",
                "scene_static",
                "$.portals",
                "設計稿預期的門不在 portals[]",
                item["id"],
            )
            continue
        opening = as_dict(portal.get("opening_m"))
        if set(portal.get("connects") or []) != set(item["connects"]):
            out.err(
                "PORTAL_CONNECTS_MISMATCH",
                "scene_static",
                "$.portals",
                f"connects 應為 {item['connects']}",
                item["id"],
            )
        end_a, end_b = point2(opening.get("a")), point2(opening.get("b"))
        expected_ends = [item["a"], item["b"]]
        same = False
        if end_a is not None and end_b is not None:
            same = all(
                math.dist(e, x) <= tol for e, x in zip((end_a, end_b), expected_ends, strict=True)
            ) or all(
                math.dist(e, x) <= tol
                for e, x in zip((end_a, end_b), expected_ends[::-1], strict=True)
            )
        if not same:
            out.err(
                "PORTAL_POSITION", "scene_static", "$.portals", "開口兩端與設計稿不一致", item["id"]
            )
        for key in ("width_m", "sill_z_m", "height_m"):
            if not is_num(opening.get(key)) or abs(opening[key] - item[key]) > tol:
                out.err(
                    "PORTAL_DIMENSION",
                    "scene_static",
                    f"$.portals.opening_m.{key}",
                    f"{key} 應為 {item[key]}",
                    item["id"],
                )
