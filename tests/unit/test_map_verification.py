"""K7 map verification on synthetic maps and synthetic annotations (no real assets)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from shapely.geometry import LineString, Point, Polygon, box, mapping

from amidst.evaluation import map_verification as mv

R = 0.25
UNIT = 0.1  # metres per annotation unit in the synthetic annotation


def _geo(geom: Any) -> dict[str, Any]:
    return dict(mapping(geom))


def _portal(pid: str, axis: int, wall: float, interval: tuple[float, float]) -> dict[str, Any]:
    lo, hi = interval
    line = [[(lo + hi) / 2, wall - 0.3], [(lo + hi) / 2, wall + 0.3]]
    if axis == 1:
        line = [[wall - 0.3, (lo + hi) / 2], [wall + 0.3, (lo + hi) / 2]]
    return {
        "portal_id": pid,
        "axis": axis,
        "wall_coordinate_m": wall,
        "opening_interval_m": [lo, hi],
        "opening_width_m": hi - lo,
        "crossing_line_m": line,
    }


def make_map(
    *,
    obstacles: list[Polygon] | None = None,
    walls: list[LineString] | None = None,
    chairs: list[Polygon] | None = None,
    portals: list[dict[str, Any]] | None = None,
    support: Polygon | None = None,
) -> dict[str, Any]:
    support = support or box(0, 0, 10, 10)
    obstacles = obstacles or []
    walls = walls or []
    footprints = [{"footprint": _geo(o)} for o in obstacles]
    footprints += [{"footprint": _geo(w)} for w in walls]
    blocked = [o.buffer(R, quad_segs=16) for o in obstacles] + [
        w.buffer(R, quad_segs=16) for w in walls
    ]
    free = support.buffer(-R, quad_segs=16)
    for b in blocked:
        free = free.difference(b)
    furniture = [
        {"assembly_id": f"chair{i}", "kind_from_source_parent": "CHAIR", "geometry": _geo(c)}
        for i, c in enumerate(chairs or [])
    ]
    variant = {
        "parameters": {"body_radius_m": R},
        "effective_conservative_buffer_radius_m": R,
        "regions": [
            {"region_id": f"r{i}", "walkable": "TRUE", "geometry": _geo(g)}
            for i, g in enumerate(getattr(free, "geoms", [free]))
        ],
        "unknown_regions": [],
        "portals": portals or [],
        "obstacle_footprints": footprints,
        "furniture": furniture,
    }
    return {
        "roi_m": [[0, 0, 0], [10, 10, 3]],
        "floor": {"geometry": _geo(support)},
        "variants": {"person": variant},
    }


def make_annotation(
    zone: Polygon,
    obstacles: dict[str, Polygon] | None = None,
    portals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def surface(name: str, role: str, geom: Polygon) -> dict[str, Any]:
        coords = list(geom.exterior.coords)[:-1]
        verts = [[x / UNIT, y / UNIT, 0.0] for x, y in coords]
        tris = [[0, i, i + 1] for i in range(1, len(verts) - 1)]
        return {
            "surface_id": name,
            "role": role,
            "floor_ids": ["1F"],
            "vertices": verts,
            "triangles": tris,
        }

    surfaces = [surface("WALK_1F_ROOM", "WALKABLE", zone)]
    surfaces += [surface(n, "OBSTACLE", g) for n, g in (obstacles or {}).items()]
    surfaces += [surface(n, "PORTAL", g) for n, g in (portals or {}).items()]
    return {"unit_scale_m": UNIT, "surfaces": surfaces}


def _ctx(zone: Polygon, ann: mv.Annotation, var: mv.VariantMap) -> mv.ComparisonContext:
    return mv.build_context(zone, list(ann.obstacles.values()), var)


def variant_of(doc: dict[str, Any]) -> mv.VariantMap:
    return mv.load_variant(doc, "person")


def test_iou_and_reconstruction_perfect_room() -> None:
    doc = make_map(obstacles=[box(4, 4, 6, 6)])
    ann = mv.load_annotation(make_annotation(box(0, 0, 10, 10), {"OBSTACLE_1F_X": box(4, 4, 6, 6)}))
    var = variant_of(doc)
    zone = ann.zones["WALK_1F_ROOM"]
    out = mv.compare_zone(zone, _ctx(zone, ann, var), Polygon())
    assert out["iou_eroded"] == pytest.approx(1.0, abs=0.01)
    assert out["annotation_only_blocks"]["count"] == 0
    assert mv.reconstruction_check(var)["iou"] == pytest.approx(1.0, abs=1e-3)


def test_annotation_obstacle_missing_from_source_is_reported() -> None:
    doc = make_map()  # source says free; annotation claims a 2x2 m obstacle
    ann = mv.load_annotation(make_annotation(box(0, 0, 10, 10), {"OBSTACLE_1F_X": box(4, 4, 6, 6)}))
    zone = ann.zones["WALK_1F_ROOM"]
    out = mv.compare_zone(zone, _ctx(zone, ann, variant_of(doc)), Polygon())
    assert out["iou_eroded"] < 0.95
    assert out["derived_only_blocks"]["count"] == 1
    assert out["derived_only_blocks"]["total_area_m2"] > 3.0
    assert out["derived_inside_annotation_obstacle_m2"] > 3.0


def test_portal_pairing_both_directions_and_width_rule() -> None:
    wall = [LineString([(0, 5), (4, 5)]), LineString([(6, 5), (10, 5)])]
    wide = _portal("portal:wide", 0, 5.0, (4.0, 6.0))
    stray = _portal("portal:stray", 1, 9.0, (1.0, 3.0))
    doc = make_map(walls=wall, portals=[wide, stray])
    ann_doc = make_annotation(
        box(0, 0, 10, 10),
        portals={
            "PORTAL_1F_DOOR": box(4.0, 4.8, 6.0, 5.2),
            "PORTAL_1F_GHOST": box(0.1, 8.0, 0.5, 9.5),
        },
    )
    ann = mv.load_annotation(ann_doc)
    result = mv.match_portals(ann, variant_of(doc))
    assert set(result["paired"]) == {"PORTAL_1F_DOOR"}
    assert [u["portal"] for u in result["unmatched_annotation"]] == ["PORTAL_1F_GHOST"]
    assert [u["portal"] for u in result["unmatched_derived"]] == ["portal:stray"]


def test_portal_narrower_than_body_diameter_is_not_paired() -> None:
    wall = [LineString([(0, 5), (4.6, 5)]), LineString([(5.0, 5), (10, 5)])]
    narrow = _portal("portal:narrow", 0, 5.0, (4.6, 5.0))
    doc = make_map(walls=wall, portals=[narrow])
    ann = mv.load_annotation(
        make_annotation(box(0, 0, 10, 10), portals={"PORTAL_1F_DOOR": box(4.5, 4.8, 5.1, 5.2)})
    )
    result = mv.match_portals(ann, variant_of(doc))
    assert not result["paired"]
    assert result["unmatched_annotation"][0]["reason"] == "NO_OPENING"


def test_route_violation_reports_time_distance_zone_only() -> None:
    doc = make_map(obstacles=[box(4, 4, 6, 6)])
    var = variant_of(doc)
    zones = {"WALK_1F_ROOM": box(0, 0, 10, 10)}
    pts = [(1.0, 1.0), (3.0, 5.0), (3.8, 5.0), (5.0, 5.0), (8.0, 8.0)]
    times = [0.0, 0.2, 0.4, 0.6, 0.8]
    res = mv.evaluate_route(pts, times, var, zones)
    assert res["violation_count"] == 2
    assert [v["t_s"] for v in res["violations"]] == [0.4, 0.6]
    assert res["violations"][1]["distance_m"] == pytest.approx(1.25, abs=0.01)
    assert res["violation_intervals"][0]["first_t_s"] == 0.4
    assert res["violation_intervals"][0]["zone"] == "WALK_1F_ROOM"
    assert res["min_clearance_inside_m"] > 0
    assert "points" not in res and "route" not in res


def test_thin_features_flag_narrow_passage_but_not_wide() -> None:
    # gap 0.78 m wide between obstacles => walkable passage 0.28 m wide => ok (> cell)
    ok = make_map(obstacles=[box(2, 0, 4, 10), box(4.78, 0, 7, 10)])
    # gap 0.66 m => passage 0.16 m wide => narrower than the 0.25 m cell
    thin = make_map(obstacles=[box(2, 0, 4, 10), box(4.66, 0, 7, 10)])
    assert mv.thin_features(variant_of(ok))["narrow_walkable"]["count"] == 0
    narrow = mv.thin_features(variant_of(thin))["narrow_walkable"]
    assert narrow["count"] >= 1
    assert narrow["elongated_count"] >= 1
    assert narrow["largest"][0]["width_m"] < 0.25


def test_thin_raw_obstacle_and_zero_thickness_walls_listed() -> None:
    doc = make_map(obstacles=[box(4, 1, 4.1, 3)], walls=[LineString([(6, 1), (6, 3)])])
    info = mv.thin_features(variant_of(doc))
    assert info["raw_obstacle_thinner_than_cell"]["count"] == 1
    assert info["zero_thickness_wall_lines"]["count"] == 1
    assert info["zero_thickness_wall_lines"]["inflated_barrier_width_m"] == pytest.approx(0.5)


def test_seating_hull_conflicts_with_walkable_true_d11() -> None:
    chairs = [box(2 + i, 2 + j, 2.6 + i, 2.6 + j) for i in (0, 1.2) for j in (0, 1.2)]
    var = variant_of(make_map(chairs=chairs))
    check = mv.seating_check(var)
    assert len(check["hulls"]) == 1
    hull = check["hulls"][0]
    assert hull["chairs"] == 4
    assert hull["d11_conflict"] is True
    assert hull["recommended_grade"] == "UNKNOWN"
    assert hull["walkable_unknown_area_m2"] == 0.0


def test_grade_rules_are_applied_in_fixed_order() -> None:
    ok = mv.grade_zone(
        coverage=1.0, iou_value=0.9, unmatched_annotation_portals=0, route_violations=0
    )
    assert ok["grade"] == "SOURCE_DERIVED_VERIFIED"
    low_cov = mv.grade_zone(
        coverage=0.2, iou_value=0.99, unmatched_annotation_portals=0, route_violations=0
    )
    assert low_cov["grade"] == "ANNOTATION_ONLY"
    bad = mv.grade_zone(
        coverage=1.0, iou_value=0.5, unmatched_annotation_portals=1, route_violations=3
    )
    assert bad["grade"] == "UNKNOWN"
    assert bad["reasons"] == ["IOU_BELOW_MIN", "ANNOTATED_PORTAL_UNPAIRED", "ROUTE_VIOLATION"]
    assert mv.grade_zone(
        coverage=1.0, iou_value=None, unmatched_annotation_portals=0, route_violations=0
    )["reasons"] == ["IOU_UNDEFINED"]


def test_output_must_be_outside_input_directories(tmp_path: Path) -> None:
    inputs = tmp_path / "in"
    inputs.mkdir()
    source = inputs / "map.json"
    source.write_text("{}")
    outputs = tmp_path / "out"
    outputs.mkdir()
    mv.ensure_output_outside_inputs(outputs / "result.json", [source])
    with pytest.raises(ValueError):
        mv.ensure_output_outside_inputs(inputs / "result.json", [source])
    with pytest.raises(ValueError):
        mv.ensure_output_outside_inputs(source, [source])


def test_pick_variant_matches_radius() -> None:
    doc = make_map()
    assert mv.pick_variant(doc, 0.25) == "person"
    assert mv.pick_variant(doc, 0.1482) is None


def test_point_helpers_do_not_mutate_inputs() -> None:
    doc = make_map()
    before = mv.load_variant(doc, "person").walkable.area
    mv.evaluate_route([(1.0, 1.0)], [0.0], variant_of(doc), {})
    assert mv.load_variant(doc, "person").walkable.area == before
    assert Point(1, 1).within(variant_of(doc).walkable)
