"""Replaceable walkable-floor map for blind-interval hypotheses.

The algorithm in :mod:`amidst.blind_hypothesis.engine` depends only on the
:class:`FloorMap` protocol: walkable region polygons and portal footprints on the
floor plane, in METRES, source world axes. Until K7 (#30) passes, the map is built
from the ``WALK_*`` / ``PORTAL_*`` annotations of the approved scene geometry
snapshot; afterwards a builder for the C7 (#29) source-mesh-derived map returns the
same :class:`PolygonFloorMap` shape, so the algorithm does not change.

Builders are pure: callers read and hash files; this module only transforms data.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from shapely.geometry import MultiPoint, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

ANNOTATION_MAP_KIND = "ANNOTATION_WALK_PORTAL"


class FloorMapError(ValueError):
    """Map input does not satisfy the floor-map contract."""


@dataclass(frozen=True)
class FloorMapDescriptor:
    """Provenance of a floor map, echoed in the hypothesis response."""

    kind: str
    map_ref: str
    sha256: str
    walkable_ref: str
    portal_ref: str
    floor_id: str


class FloorMap(Protocol):
    """What the hypothesis algorithm needs from a walkable map."""

    @property
    def descriptor(self) -> FloorMapDescriptor: ...

    @property
    def floor_z_m(self) -> float: ...

    @property
    def regions(self) -> Mapping[str, BaseGeometry]:
        """Walkable polygons by id (floor plane, metres)."""
        ...

    @property
    def portals(self) -> Mapping[str, BaseGeometry]:
        """Portal floor footprints by id; crossing between regions needs one."""
        ...

    @property
    def unknown_regions(self) -> Mapping[str, BaseGeometry]:
        """Regions with ``walkable: UNKNOWN`` (contract §3.2, D11): the lattice may
        pass through them, but a route that does is labelled unconfirmed. Ids are
        disjoint from :attr:`regions`. A map without this property has none."""
        ...


@dataclass(frozen=True)
class PolygonFloorMap:
    """Concrete :class:`FloorMap` shared by annotation and derived-map builders."""

    descriptor: FloorMapDescriptor
    floor_z_m: float
    regions: Mapping[str, BaseGeometry]
    portals: Mapping[str, BaseGeometry]
    unknown_regions: Mapping[str, BaseGeometry] = field(default_factory=dict)
    # Contract §3.2 ``tier`` by region id (``SOURCE_DERIVED`` / ``ANNOTATION_ONLY`` /
    # ``UNKNOWN``); ids not listed fall back to the map kind (see the engine).
    region_tiers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not math.isfinite(self.floor_z_m):
            raise FloorMapError("floor_z_m must be finite")
        if not self.regions and not self.unknown_regions:
            raise FloorMapError("floor map has no walkable region")
        ids = [*self.regions, *self.unknown_regions, *self.portals]
        if len(set(ids)) != len(ids):
            raise FloorMapError("region and portal ids must be unique")
        for name, geometry in [
            *self.regions.items(),
            *self.unknown_regions.items(),
            *self.portals.items(),
        ]:
            if geometry.is_empty or not geometry.is_valid or geometry.area <= 0:
                raise FloorMapError(f"invalid or empty footprint: {name}")
        if any(
            self.region_tiers.get(name, "UNKNOWN") != "UNKNOWN" for name in self.unknown_regions
        ):
            raise FloorMapError("a walkable: UNKNOWN region must have tier UNKNOWN")

    def region_at(self, x: float, y: float) -> str | None:
        """First region id (lexical order) whose polygon covers the point."""
        point = Point(x, y)
        for name in sorted(self.regions):
            if self.regions[name].covers(point):
                return name
        for name in sorted(self.unknown_regions):
            if self.unknown_regions[name].covers(point):
                return name
        return None


def _surface_footprint(surface: Mapping[str, Any], scale: float) -> BaseGeometry:
    vertices = surface.get("vertices")
    triangles = surface.get("triangles")
    if not isinstance(vertices, list) or not isinstance(triangles, list) or not triangles:
        raise FloorMapError(f"surface without triangles: {surface.get('surface_id')}")
    pieces = []
    for triangle in triangles:
        ring = [(float(vertices[i][0]) * scale, float(vertices[i][1]) * scale) for i in triangle]
        piece = Polygon(ring)
        if piece.area > 0:
            pieces.append(piece)
    if not pieces:
        raise FloorMapError(f"surface has no floor-plane area: {surface.get('surface_id')}")
    return unary_union(pieces)


def _portal_footprint(surface: Mapping[str, Any], scale: float) -> BaseGeometry:
    vertices = surface.get("vertices")
    if not isinstance(vertices, list) or len(vertices) < 3:
        raise FloorMapError(f"portal without vertices: {surface.get('surface_id')}")
    hull = MultiPoint([(float(v[0]) * scale, float(v[1]) * scale) for v in vertices]).convex_hull
    if hull.area <= 0:
        raise FloorMapError(f"portal has no floor-plane footprint: {surface.get('surface_id')}")
    return hull


def floor_map_from_scene_geometry(
    geometry: Mapping[str, Any],
    *,
    geometry_ref: str,
    geometry_sha256: str,
    floor_id: str,
    metres_per_unit: float,
    floor_z_m: float,
    walkable_ids: Iterable[str] | None = None,
    portal_ids: Iterable[str] | None = None,
) -> PolygonFloorMap:
    """Build the interim annotation map from a ``scene-geometry-v1`` snapshot.

    Walkable regions are surfaces with role ``WALKABLE`` and id prefix ``WALK_``;
    portals are role ``PORTAL`` with prefix ``PORTAL_``. Only ``floor_id`` is used.
    Vertices are scaled by ``metres_per_unit`` (no offset); the annotation's own
    Z is ignored and ``floor_z_m`` (source-bound floor plane) is used instead.
    ``walkable_ids`` / ``portal_ids`` restrict the map to a demo area; an id that
    is requested but absent is an error, never silently dropped.
    """

    if geometry.get("schema_version") != "scene-geometry-v1":
        raise FloorMapError("unsupported geometry schema")
    if geometry.get("coordinate_convention") != "RIGHT_HANDED_Z_UP":
        raise FloorMapError("unsupported coordinate convention")
    if not (math.isfinite(metres_per_unit) and metres_per_unit > 0):
        raise FloorMapError("metres_per_unit must be positive")
    surfaces = geometry.get("surfaces")
    if not isinstance(surfaces, list):
        raise FloorMapError("geometry has no surfaces")

    def pick(role: str, prefix: str, wanted: Iterable[str] | None) -> dict[str, BaseGeometry]:
        found = {
            str(s["surface_id"]): s
            for s in surfaces
            if s.get("role") == role
            and str(s.get("surface_id", "")).startswith(prefix)
            and floor_id in (s.get("floor_ids") or [])
        }
        if wanted is not None:
            wanted_set = sorted(set(wanted))
            missing = [name for name in wanted_set if name not in found]
            if missing:
                raise FloorMapError(f"requested {role} ids not in geometry: {missing}")
            found = {name: found[name] for name in wanted_set}
        build = _surface_footprint if role == "WALKABLE" else _portal_footprint
        return {name: build(found[name], metres_per_unit) for name in sorted(found)}

    regions = pick("WALKABLE", "WALK_", walkable_ids)
    portals = pick("PORTAL", "PORTAL_", portal_ids)
    descriptor = FloorMapDescriptor(
        kind=ANNOTATION_MAP_KIND,
        map_ref=geometry_ref,
        sha256=geometry_sha256,
        walkable_ref=f"{geometry_ref}#WALK_*@{floor_id}",
        portal_ref=f"{geometry_ref}#PORTAL_*@{floor_id}",
        floor_id=floor_id,
    )
    return PolygonFloorMap(descriptor, float(floor_z_m), regions, portals)


def polygon_floor_map(
    *,
    descriptor: FloorMapDescriptor,
    floor_z_m: float,
    regions: Mapping[str, Sequence[Sequence[float]]],
    portals: Mapping[str, Sequence[Sequence[float]]] | None = None,
    unknown_regions: Mapping[str, Sequence[Sequence[float]]] | None = None,
    region_tiers: Mapping[str, str] | None = None,
) -> PolygonFloorMap:
    """Build a map from plain ``[[x, y], ...]`` rings (metres); used by tests and
    by any later derived-map producer that already outputs rings.
    ``unknown_regions`` are ``walkable: UNKNOWN`` areas (D11)."""

    return PolygonFloorMap(
        descriptor,
        float(floor_z_m),
        {name: Polygon(ring) for name, ring in sorted(regions.items())},
        {name: Polygon(ring) for name, ring in sorted((portals or {}).items())},
        {name: Polygon(ring) for name, ring in sorted((unknown_regions or {}).items())},
        dict(region_tiers or {}),
    )
