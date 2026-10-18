"""K7 independent verification of a source-derived floor map (pure functions, shapely only).

Inputs are plain JSON documents: a C7 source-map bundle, the human annotation geometry
(``WALK_*`` / ``OBSTACLE_*`` / ``PORTAL_*``), and offline renderer routes.  Nothing here imports
the C7 builder.  Ground Truth routes are used for offline evaluation only: the results must not
flow back into a map or into inference (CP1 D10).  Grading rules are fixed in
``GRADING_RULES`` before any map is judged.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import shapely
from shapely.geometry import MultiPolygon, Point, Polygon, box, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

GRADING_RULES: dict[str, Any] = {
    "version": "k7-grading-rules.v1",
    "iou_min": 0.80,
    "coverage_min": 0.50,
    "min_mismatch_block_m2": 0.25,
    "mismatch_opening_m": 0.05,
    "portal_min_width_factor": 2.0,
    "portal_perpendicular_slack_m": 0.6,
    "route_violation_tolerance_m": 1e-4,
    "grid_step_m": 0.25,
    "thin_min_area_m2": 0.005,
    "seating_link_distance_m": 1.5,
    "grades": ["SOURCE_DERIVED_VERIFIED", "ANNOTATION_ONLY", "UNKNOWN"],
    "decision": (
        "ANNOTATION_ONLY if map coverage of the zone < coverage_min; otherwise "
        "SOURCE_DERIVED_VERIFIED only when IoU >= iou_min AND every annotated portal of the "
        "zone is "
        "paired with a derived opening of width >= 2 x body radius AND the zone has 0 route "
        "violations; any other outcome is UNKNOWN. Thin features and unmatched derived openings "
        "are reported but do not change the grade. Seating hulls are graded separately (D11)."
    ),
}


ELONGATED_MIN_LENGTH_M = 0.5  # two lattice cells; shorter residue is corner/tip noise


def _parts(geometry: BaseGeometry) -> list[BaseGeometry]:
    if geometry.is_empty:
        return []
    if hasattr(geometry, "geoms"):
        out: list[BaseGeometry] = []
        for part in geometry.geoms:
            out.extend(_parts(part))
        return out
    return [geometry]


def polygons_of(geometry: BaseGeometry) -> BaseGeometry:
    """Polygonal part of any geometry (lines and points dropped)."""
    polys = [p for p in _parts(geometry) if isinstance(p, Polygon) and p.area > 0]
    return unary_union(polys) if polys else Polygon()


def lines_of(geometry: BaseGeometry) -> BaseGeometry:
    lines = [p for p in _parts(geometry) if p.geom_type in ("LineString", "LinearRing")]
    return unary_union(lines) if lines else Polygon()


def _clean(geometry: BaseGeometry) -> BaseGeometry:
    return geometry if geometry.is_valid else shapely.make_valid(geometry)


def iou(a: BaseGeometry, b: BaseGeometry) -> float | None:
    union = a.union(b).area
    if union <= 0:
        return None
    return float(a.intersection(b).area / union)


# ----------------------------------------------------------------------------- map loading


@dataclass(frozen=True)
class VariantMap:
    """One C7 body-centre variant, read directly from the JSON."""

    name: str
    radius_m: float
    effective_buffer_m: float
    walkable: BaseGeometry
    unknown: BaseGeometry
    support: BaseGeometry
    obstacle_polygons: BaseGeometry
    obstacle_lines: BaseGeometry
    roi: BaseGeometry
    portals: tuple[dict[str, Any], ...]
    chairs: tuple[tuple[str, BaseGeometry], ...]
    region_count: int


def load_variant(map_doc: dict[str, Any], variant: str) -> VariantMap:
    data = map_doc["variants"][variant]
    if "roi_geometry" in map_doc:
        roi = _clean(shape(map_doc["roi_geometry"]))
    else:
        (x0, y0, _), (x1, y1, _) = map_doc["roi_m"]
        roi = box(x0, y0, x1, y1)
    regions = [_clean(shape(r["geometry"])) for r in data["regions"] if r.get("walkable") == "TRUE"]
    unknown = [_clean(shape(r["geometry"])) for r in data.get("unknown_regions", [])]
    footprints = [_clean(shape(o["footprint"])) for o in data["obstacle_footprints"]]
    chairs = tuple(
        (f["assembly_id"], _clean(shape(f["geometry"])))
        for f in data.get("furniture", [])
        if f.get("kind_from_source_parent") == "CHAIR"
    )
    return VariantMap(
        name=variant,
        radius_m=float(data["parameters"]["body_radius_m"]),
        effective_buffer_m=float(data["effective_conservative_buffer_radius_m"]),
        walkable=unary_union(regions) if regions else Polygon(),
        unknown=unary_union(unknown) if unknown else Polygon(),
        support=_clean(shape(map_doc["floor"]["geometry"])),
        obstacle_polygons=polygons_of(unary_union(footprints)),
        obstacle_lines=lines_of(unary_union(footprints)),
        roi=roi,
        portals=tuple(data["portals"]),
        chairs=chairs,
        region_count=len(data["regions"]),
    )


def pick_variant(map_doc: dict[str, Any], body_radius_m: float, tol_m: float = 1e-3) -> str | None:
    for name, data in map_doc["variants"].items():
        if abs(float(data["parameters"]["body_radius_m"]) - body_radius_m) <= tol_m:
            return str(name)
    return None


# ------------------------------------------------------------------------ annotation loading


@dataclass(frozen=True)
class Annotation:
    zones: dict[str, BaseGeometry]
    thresholds: dict[str, BaseGeometry]
    obstacles: dict[str, BaseGeometry]
    portals: dict[str, dict[str, Any]]


def _surface_polygon(surface: dict[str, Any], unit: float) -> BaseGeometry:
    verts = surface["vertices"]
    tris = [
        Polygon([(verts[i][0] * unit, verts[i][1] * unit) for i in tri])
        for tri in surface["triangles"]
    ]
    tris = [t for t in tris if t.area > 0]
    return unary_union(tris) if tris else Polygon()


def load_annotation(doc: dict[str, Any], floor_id: str = "1F") -> Annotation:
    unit = float(doc["unit_scale_m"])
    zones: dict[str, BaseGeometry] = {}
    thresholds: dict[str, BaseGeometry] = {}
    obstacles: dict[str, BaseGeometry] = {}
    portals: dict[str, dict[str, Any]] = {}
    for s in doc["surfaces"]:
        if s.get("floor_ids") != [floor_id]:
            continue
        name = s["surface_id"]
        if s["role"] == "WALKABLE":
            (thresholds if name.endswith("_THRESHOLD") else zones)[name] = _surface_polygon(s, unit)
        elif s["role"] == "OBSTACLE":
            obstacles[name] = _surface_polygon(s, unit)
        elif s["role"] == "PORTAL":
            xs = [v[0] * unit for v in s["vertices"]]
            ys = [v[1] * unit for v in s["vertices"]]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            width_axis = 0 if (x1 - x0) >= (y1 - y0) else 1
            portals[name] = {
                "bounds_m": (x0, y0, x1, y1),
                "width_axis": width_axis,
                "width_m": max(x1 - x0, y1 - y0),
                "thickness_m": min(x1 - x0, y1 - y0),
            }
    return Annotation(zones, thresholds, obstacles, portals)


# ------------------------------------------------------------------------------- IoU / blocks


def mismatch_blocks(
    a_minus_b: BaseGeometry, kind: str, min_area: float, opening: float, limit: int = 12
) -> dict[str, Any]:
    """Blocks of a difference region above ``min_area`` after removing hairline slivers."""
    opened = a_minus_b.buffer(-opening).buffer(opening) if not a_minus_b.is_empty else a_minus_b
    blocks = [p for p in _parts(opened) if isinstance(p, Polygon) and p.area > min_area]
    blocks.sort(key=lambda p: -p.area)
    return {
        "kind": kind,
        "count": len(blocks),
        "total_area_m2": round(sum(p.area for p in blocks), 4),
        "largest": [
            {
                "area_m2": round(p.area, 4),
                "centroid_m": [round(p.centroid.x, 3), round(p.centroid.y, 3)],
                "bounds_m": [round(v, 3) for v in p.bounds],
            }
            for p in blocks[:limit]
        ],
        "_geometry": unary_union(blocks) if blocks else Polygon(),
    }


def seating_hulls(
    chairs: Sequence[tuple[str, BaseGeometry]], link_distance: float
) -> list[tuple[list[str], BaseGeometry]]:
    """Single-linkage clusters of chair footprints; each hull is a D11 seating zone."""
    clusters: list[tuple[list[str], list[BaseGeometry]]] = []
    for cid, geom in chairs:
        linked = [c for c in clusters if any(geom.distance(g) <= link_distance for g in c[1])]
        merged_ids = [cid]
        merged_geoms = [geom]
        for c in linked:
            merged_ids += c[0]
            merged_geoms += c[1]
            clusters.remove(c)
        clusters.append((merged_ids, merged_geoms))
    return [(sorted(ids), unary_union(gs).convex_hull) for ids, gs in clusters]


@dataclass(frozen=True)
class ComparisonContext:
    """Per-variant geometry that does not depend on the zone (computed once)."""

    variant: VariantMap
    obstacle_list: tuple[BaseGeometry, ...]
    obstacles: BaseGeometry
    ann_walk_eroded: BaseGeometry
    ann_all_eroded: BaseGeometry
    raw_free: BaseGeometry
    inner_roi: BaseGeometry


def build_context(
    annotation_walk_union: BaseGeometry,
    annotation_obstacles: Sequence[BaseGeometry],
    variant: VariantMap,
) -> ComparisonContext:
    r = variant.radius_m
    obstacles = union_all(annotation_obstacles)
    walk_eroded = annotation_walk_union.buffer(-r, quad_segs=16)
    return ComparisonContext(
        variant=variant,
        obstacle_list=tuple(annotation_obstacles),
        obstacles=obstacles,
        ann_walk_eroded=walk_eroded,
        ann_all_eroded=walk_eroded.difference(obstacles.buffer(r, quad_segs=16)),
        raw_free=variant.support.difference(variant.obstacle_polygons),
        inner_roi=variant.roi.buffer(-r),
    )


def _window(geometry: BaseGeometry, domain: BaseGeometry) -> BaseGeometry:
    x0, y0, x1, y1 = domain.bounds
    return shapely.clip_by_rect(geometry, x0 - 1, y0 - 1, x1 + 1, y1 + 1)


def compare_zone(
    zone: BaseGeometry,
    ctx: ComparisonContext,
    exclusion: BaseGeometry,
    rules: dict[str, Any] = GRADING_RULES,
) -> dict[str, Any]:
    """Compare derived body-centre area with the annotation on the same (eroded) footing.

    The comparison domain is the ``WALK_*`` zone plus every ``OBSTACLE_*`` annotation touching it:
    an annotated obstacle that the source mesh leaves free is a disagreement about the room, even
    though the zone polygon itself omits that obstacle.
    """
    variant = ctx.variant
    r = variant.radius_m
    near = zone.buffer(0.1)
    touching = [o for o in ctx.obstacle_list if o.intersects(near)]
    domain = union_all([zone, *touching])
    coverage = zone.intersection(variant.roi).area / zone.area if zone.area > 0 else 0.0

    def clip(g: BaseGeometry) -> BaseGeometry:
        return (
            _window(g, domain)
            .intersection(domain)
            .intersection(ctx.inner_roi)
            .difference(exclusion)
        )

    derived = clip(variant.walkable)
    zone_only_a = (
        _window(ctx.ann_all_eroded, zone)
        .intersection(zone)
        .intersection(ctx.inner_roi)
        .difference(exclusion)
    )
    zone_only_d = (
        _window(variant.walkable, zone)
        .intersection(zone)
        .intersection(ctx.inner_roi)
        .difference(exclusion)
    )
    a_all = clip(ctx.ann_all_eroded)
    a_walk = clip(ctx.ann_walk_eroded)
    raw_derived = clip(ctx.raw_free)
    raw_ann = domain.intersection(ctx.inner_roi).difference(exclusion).difference(ctx.obstacles)
    min_area = rules["min_mismatch_block_m2"]
    op = rules["mismatch_opening_m"]
    ann_only = mismatch_blocks(a_all.difference(derived), "ANNOTATION_ONLY_BLOCK", min_area, op)
    der_only = mismatch_blocks(derived.difference(a_all), "DERIVED_ONLY_BLOCK", min_area, op)
    obstacle_conflict = derived.intersection(ctx.obstacles.buffer(r, quad_segs=16))
    return {
        "coverage": round(coverage, 4),
        "zone_area_m2": round(zone.area, 4),
        "touching_obstacles": len(touching),
        "domain_area_m2": round(domain.area, 4),
        "derived_area_m2": round(derived.area, 4),
        "annotation_eroded_area_m2": round(a_all.area, 4),
        "iou_eroded": _round(iou(derived, a_all)),
        "iou_eroded_walk_only": _round(iou(derived, a_walk)),
        "iou_eroded_zone_polygon_only": _round(iou(zone_only_d, zone_only_a)),
        "iou_raw": _round(iou(raw_derived, raw_ann)),
        "annotation_only_blocks": ann_only,
        "derived_only_blocks": der_only,
        "derived_inside_annotation_obstacle_m2": round(obstacle_conflict.area, 4),
    }


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def reconstruction_check(variant: VariantMap) -> dict[str, Any]:
    """Rebuild the body-centre domain from raw support/obstacles with the nominal radius once."""
    r = variant.radius_m
    inner = variant.roi.buffer(-r)
    rebuilt = variant.support.buffer(-r, quad_segs=16).difference(
        variant.obstacle_polygons.union(variant.obstacle_lines).buffer(r, quad_segs=16)
    )
    got = variant.walkable.intersection(inner)
    exp = rebuilt.intersection(inner)
    return {
        "rebuilt_area_m2": round(exp.area, 4),
        "map_area_m2": round(got.area, 4),
        "iou": _round(iou(got, exp)),
        "symmetric_difference_m2": round(got.symmetric_difference(exp).area, 4),
    }


# --------------------------------------------------------------------------------- portals


def match_portals(
    annotation: Annotation,
    variant: VariantMap,
    rules: dict[str, Any] = GRADING_RULES,
) -> dict[str, Any]:
    """Pair annotation ``PORTAL_*`` boxes with derived openings in both directions."""
    min_width = rules["portal_min_width_factor"] * variant.radius_m
    slack = rules["portal_perpendicular_slack_m"]
    derived = list(variant.portals)
    paired: dict[str, Any] = {}
    used: set[str] = set()
    unmatched_annotation: list[dict[str, Any]] = []
    not_evaluated: list[dict[str, Any]] = []
    for name, p in sorted(annotation.portals.items()):
        x0, y0, x1, y1 = p["bounds_m"]
        if not variant.roi.covers(box(x0, y0, x1, y1)):
            if variant.roi.intersects(box(x0, y0, x1, y1)):
                not_evaluated.append({"portal": name, "reason": "PARTLY_OUTSIDE_MAP_ROI"})
            continue
        long_side = max(x1 - x0, y1 - y0)
        short_side = max(min(x1 - x0, y1 - y0), 1e-9)
        # A box that is not clearly elongated gives no reliable wall direction: try both axes.
        axes = [p["width_axis"]] if long_side / short_side >= 1.5 else [0, 1]
        best: tuple[float, dict[str, Any]] | None = None
        faces: list[str] = []
        for axis in axes:
            lo, hi = (x0, x1) if axis == 0 else (y0, y1)
            perp_lo, perp_hi = (y0, y1) if axis == 0 else (x0, x1)
            for d in derived:
                if d["axis"] != axis:
                    continue
                wall = d["wall_coordinate_m"]
                if not (perp_lo - slack <= wall <= perp_hi + slack):
                    continue
                ilo, ihi = d["opening_interval_m"]
                overlap = min(hi, ihi) - max(lo, ilo)
                if overlap < min_width:
                    continue
                faces.append(d["portal_id"])
                if best is None or overlap > best[0]:
                    best = (overlap, d)
        if best is None:
            unmatched_annotation.append(
                {
                    "portal": name,
                    "annotation_width_m": round(p["width_m"], 3),
                    "reason": "NO_OPENING",
                }
            )
            continue
        overlap, d = best
        crossing = _crossing_walkable(d, variant)
        wide_enough = d["opening_width_m"] >= min_width
        ok = wide_enough and crossing["both_sides_walkable"]
        entry = {
            "portal": name,
            "derived": d["portal_id"],
            "derived_width_m": round(d["opening_width_m"], 4),
            "annotation_width_m": round(p["width_m"], 4),
            "overlap_m": round(overlap, 4),
            "min_required_width_m": round(min_width, 4),
            "derived_wide_enough": wide_enough,
            "both_sides_walkable": crossing["both_sides_walkable"],
            "other_candidate_openings": [f for f in faces if f != d["portal_id"]],
        }
        if ok:
            paired[name] = entry
            used.add(d["portal_id"])
            used.update(entry["other_candidate_openings"])
        else:
            unmatched_annotation.append({**entry, "reason": "OPENING_TOO_NARROW_OR_BLOCKED"})
    unmatched_derived = [
        {
            "portal": d["portal_id"],
            "width_m": round(d["opening_width_m"], 3),
            "axis": d["axis"],
            "centre_m": [round(c, 3) for c in _portal_centre(d)],
        }
        for d in derived
        if d["portal_id"] not in used
    ]
    return {
        "paired": paired,
        "unmatched_annotation": unmatched_annotation,
        "unmatched_derived": unmatched_derived,
        "not_evaluated": not_evaluated,
    }


def _portal_centre(portal: dict[str, Any]) -> tuple[float, float]:
    (ax, ay), (bx, by) = portal["crossing_line_m"]
    return ((ax + bx) / 2, (ay + by) / 2)


def _crossing_walkable(portal: dict[str, Any], variant: VariantMap) -> dict[str, Any]:
    cx, cy = _portal_centre(portal)
    axis = portal["axis"]
    delta = 0.5
    before = Point(cx, cy - delta) if axis == 0 else Point(cx - delta, cy)
    after = Point(cx, cy + delta) if axis == 0 else Point(cx + delta, cy)
    tol = 1e-3
    return {
        "both_sides_walkable": bool(
            variant.walkable.distance(before) <= tol and variant.walkable.distance(after) <= tol
        ),
    }


# ---------------------------------------------------------------------------------- routes


def evaluate_route(
    points: Sequence[tuple[float, float]],
    times: Sequence[float],
    variant: VariantMap,
    zones: dict[str, BaseGeometry],
    rules: dict[str, Any] = GRADING_RULES,
) -> dict[str, Any]:
    """Offline GT route check: body-centre samples against the derived walkable area (D10)."""
    tol = rules["route_violation_tolerance_m"]
    walkable = variant.walkable
    violations: list[dict[str, Any]] = []
    inside_clearances: list[float] = []
    zones_hit: dict[str, int] = {}
    boundary = walkable.boundary
    for (x, y), t in zip(points, times, strict=True):
        pt = Point(x, y)
        zone = next((n for n, z in zones.items() if z.covers(pt)), None)
        if zone:
            zones_hit[zone] = zones_hit.get(zone, 0) + 1
        d = walkable.distance(pt)
        if d > tol:
            violations.append({"t_s": round(float(t), 3), "distance_m": round(d, 4), "zone": zone})
        else:
            inside_clearances.append(boundary.distance(pt))
    in_roi = all(variant.roi.covers(Point(p)) for p in points)
    return {
        "samples": len(points),
        "inside_roi": in_roi,
        "violation_count": len(violations),
        "violations": violations,
        "violation_intervals": _intervals(violations),
        "min_clearance_inside_m": round(min(inside_clearances), 4) if inside_clearances else None,
        "zones_hit": zones_hit,
    }


def _intervals(violations: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for v in violations:
        zone = v["zone"]
        if out and out[-1]["zone"] == zone and v["t_s"] - out[-1]["last_t_s"] <= 0.5:
            cur = out[-1]
            cur["last_t_s"] = v["t_s"]
            cur["count"] += 1
            cur["max_distance_m"] = max(cur["max_distance_m"], v["distance_m"])
        else:
            out.append(
                {
                    "first_t_s": v["t_s"],
                    "last_t_s": v["t_s"],
                    "count": 1,
                    "max_distance_m": v["distance_m"],
                    "zone": zone,
                }
            )
    return out


# ---------------------------------------------------------------------------- thin features


def _width_of(piece: BaseGeometry) -> float:
    circle = shapely.maximum_inscribed_circle(piece, tolerance=0.002)
    return float(2 * circle.length)


def _thin_pieces(
    residue: BaseGeometry, min_area: float, kind: str, limit: int = 20
) -> dict[str, Any]:
    pieces = [p for p in _parts(residue) if isinstance(p, Polygon) and p.area >= min_area]
    pieces.sort(key=lambda p: -p.area)
    all_rows: list[dict[str, Any]] = []
    for p in pieces:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            rect = p.minimum_rotated_rectangle
        if isinstance(rect, Polygon):
            coords = list(rect.exterior.coords)
            sides = sorted(math.dist(coords[i], coords[i + 1]) for i in range(2))
        else:
            sides = [0.0, rect.length]
        all_rows.append(
            {
                "area_m2": round(p.area, 4),
                "width_m": round(_width_of(p), 4),
                "length_m": round(sides[1], 3),
                "centroid_m": [round(p.centroid.x, 3), round(p.centroid.y, 3)],
                "bounds_m": [round(v, 3) for v in p.bounds],
            }
        )
    rows = all_rows[:limit]
    return {
        "kind": kind,
        "count": len(pieces),
        "elongated_count": sum(1 for r in all_rows if r["length_m"] >= ELONGATED_MIN_LENGTH_M),
        "elongated_min_length_m": ELONGATED_MIN_LENGTH_M,
        "total_area_m2": round(sum(p.area for p in pieces), 4),
        "largest": rows,
        "_geometry": unary_union(pieces) if pieces else Polygon(),
    }


def thin_features(variant: VariantMap, rules: dict[str, Any] = GRADING_RULES) -> dict[str, Any]:
    """Features thinner/narrower than one lattice cell (K1 contract section 12.4)."""
    h = rules["grid_step_m"] / 2
    min_area = rules["thin_min_area_m2"]
    walk = variant.walkable
    opened = walk.buffer(-h, quad_segs=16).buffer(h, quad_segs=16)
    narrow = walk.difference(opened.buffer(1e-6))
    closed = walk.buffer(h, quad_segs=16).buffer(-h, quad_segs=16)
    thin_barrier = closed.difference(walk.buffer(1e-6))
    raw = variant.obstacle_polygons
    raw_opened = raw.buffer(-h, quad_segs=16).buffer(h, quad_segs=16) if not raw.is_empty else raw
    raw_thin = raw.difference(raw_opened.buffer(1e-6)) if not raw.is_empty else raw
    lines = variant.obstacle_lines
    line_parts = [p for p in _parts(lines) if p.geom_type == "LineString"]
    return {
        "grid_step_m": rules["grid_step_m"],
        "narrow_walkable": _thin_pieces(narrow, min_area, "WALKABLE_NARROWER_THAN_CELL"),
        "thin_barrier_in_walkable": _thin_pieces(
            thin_barrier, min_area, "BARRIER_THINNER_THAN_CELL"
        ),
        "raw_obstacle_thinner_than_cell": _thin_pieces(
            raw_thin, min_area, "RAW_OBSTACLE_THINNER_THAN_CELL"
        ),
        "zero_thickness_wall_lines": {
            "count": len(line_parts),
            "total_length_m": round(sum(p.length for p in line_parts), 3),
            "inflated_barrier_width_m": round(2 * variant.effective_buffer_m, 4),
            "clearance_below_0p15_m_rule": variant.effective_buffer_m < 0.15,
        },
    }


# ------------------------------------------------------------------------------------ grading


def grade_zone(
    *,
    coverage: float,
    iou_value: float | None,
    unmatched_annotation_portals: int,
    route_violations: int,
    rules: dict[str, Any] = GRADING_RULES,
) -> dict[str, Any]:
    """Apply the frozen rule set; returns the grade and every reason that applied."""
    if coverage < rules["coverage_min"]:
        return {"grade": "ANNOTATION_ONLY", "reasons": ["MAP_COVERAGE_BELOW_MIN"]}
    reasons: list[str] = []
    if iou_value is None or iou_value < rules["iou_min"]:
        reasons.append("IOU_BELOW_MIN" if iou_value is not None else "IOU_UNDEFINED")
    if unmatched_annotation_portals > 0:
        reasons.append("ANNOTATED_PORTAL_UNPAIRED")
    if route_violations > 0:
        reasons.append("ROUTE_VIOLATION")
    if reasons:
        return {"grade": "UNKNOWN", "reasons": reasons}
    return {"grade": "SOURCE_DERIVED_VERIFIED", "reasons": []}


def seating_check(variant: VariantMap, rules: dict[str, Any] = GRADING_RULES) -> dict[str, Any]:
    """D11: seating hulls must not be ``walkable: TRUE``."""
    out = []
    for ids, hull in seating_hulls(variant.chairs, rules["seating_link_distance_m"]):
        true_area = variant.walkable.intersection(hull).area
        unknown_area = variant.unknown.intersection(hull).area
        out.append(
            {
                "chairs": len(ids),
                "hull_area_m2": round(hull.area, 4),
                "hull_bounds_m": [round(v, 3) for v in hull.bounds],
                "walkable_true_area_m2": round(true_area, 4),
                "walkable_unknown_area_m2": round(unknown_area, 4),
                "d11_conflict": true_area > 0.0,
                "recommended_grade": "UNKNOWN" if true_area > 0.0 else "OK",
                "_geometry": hull,
            }
        )
    return {"hulls": out, "unknown_region_count": len(_parts(variant.unknown))}


def ensure_output_outside_inputs(output: Path, inputs: Iterable[Path]) -> None:
    """Refuse to write inside (or onto) any input path or its parent directory."""
    out = output.resolve()
    for item in inputs:
        src = item.resolve()
        folder = src if src.is_dir() else src.parent
        if out == src or out == folder or folder in out.parents:
            raise ValueError(f"refusing to write {out}: inside input location {folder}")


def strip_geometry(value: Any) -> Any:
    """Drop private ``_geometry`` keys before JSON serialisation."""
    if isinstance(value, dict):
        return {k: strip_geometry(v) for k, v in value.items() if k != "_geometry"}
    if isinstance(value, list):
        return [strip_geometry(v) for v in value]
    return value


def union_all(geoms: Iterable[BaseGeometry]) -> BaseGeometry:
    items = [g for g in geoms if not g.is_empty]
    return unary_union(items) if items else MultiPolygon()
