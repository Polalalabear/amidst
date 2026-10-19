"""Validation context and small defensive helpers shared by the rules."""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, TypeGuard

from shapely.geometry import LinearRing, Polygon

from .contract import HEX64
from .params import ValidationParams

Json = Any


def is_num(value: Any) -> TypeGuard[float]:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def is_int(value: Any) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def is_hex64(value: Any) -> bool:
    return isinstance(value, str) and HEX64.match(value) is not None


def nonempty_str(value: Any) -> TypeGuard[str]:
    return isinstance(value, str) and value.strip() != ""


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def bounds_of(record: dict[str, Any]) -> list[list[float]] | None:
    """``bounds_m`` as [[xmin,ymin,zmin],[xmax,ymax,zmax]] when well formed, else None."""
    raw = record.get("bounds_m")
    if (
        isinstance(raw, list)
        and len(raw) == 2
        and all(isinstance(b, list) and len(b) == 3 and all(is_num(v) for v in b) for b in raw)
    ):
        return [[float(v) for v in b] for b in raw]
    return None


def dicts(value: Any) -> list[dict[str, Any]]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def iter_nodes(value: Any, path: str = "$") -> Iterator[tuple[str, str | None, Any]]:
    """Yield (path, key, value) for every dict member and list item below ``value``."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield f"{path}.{key}", key, item
            yield from iter_nodes(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield f"{path}[{index}]", None, item
            yield from iter_nodes(item, f"{path}[{index}]")


def point2(raw: Any) -> tuple[float, float] | None:
    if isinstance(raw, list | tuple) and len(raw) in (2, 3) and all(is_num(v) for v in raw):
        return (float(raw[0]), float(raw[1]))
    return None


def ring_points(raw: Any) -> list[tuple[float, float]] | None:
    """A ring as 2-D points, dropping a repeated closing vertex; None when malformed."""
    if not isinstance(raw, list):
        return None
    pts = [point2(p) for p in raw]
    if any(p is None for p in pts) or len(pts) < 3:
        return None
    out = [p for p in pts if p is not None]
    if out[0] == out[-1]:
        out = out[:-1]
    return out if len(out) >= 3 else None


def signed_area(points: list[tuple[float, float]]) -> float:
    return 0.5 * sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1], strict=True)
    )


def polygon_from(outer_raw: Any, holes_raw: Any) -> Polygon | None:
    """Shapely polygon from an exported outer ring and holes; None if malformed.  Not repaired."""
    outer = ring_points(outer_raw)
    if outer is None:
        return None
    holes: list[list[tuple[float, float]]] = []
    for hole_raw in holes_raw if isinstance(holes_raw, list) else []:
        hole = ring_points(hole_raw)
        if hole is None:
            return None
        holes.append(hole)
    return Polygon(outer, holes)


def ring_is_ccw(points: list[tuple[float, float]]) -> bool:
    return LinearRing(points).is_ccw


@dataclass
class Context:
    params: ValidationParams
    template: dict[str, Any] | None = None
    static: dict[str, Any] | None = None
    cameras_doc: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None
    rgb_index: dict[str, Any] | None = None  # normalised (records[]); None if fail-closed
    rgb_index_raw: dict[str, Any] | None = None  # as read from the file
    rgb_adapters: list[dict[str, Any]] = field(default_factory=list)
    rgb_index_error: tuple[str, str] | None = None
    runtime_profile: dict[str, Any] | None = None
    file_sha256: dict[str, str] = field(default_factory=dict)
    load_issues: list[tuple[str, str, str, str]] = field(
        default_factory=list
    )  # (code, scope, field, message)
    design_enabled: bool = True

    @property
    def design(self) -> dict[str, Any] | None:
        if not self.design_enabled or not isinstance(self.template, dict):
            return None
        ref = self.template.get("design_reference")
        return ref if isinstance(ref, dict) else None

    @property
    def docs(self) -> dict[str, Any]:
        named = {
            "scene_static": self.static,
            "cameras": self.cameras_doc,
            "manifest": self.manifest,
            "rgb_index": self.rgb_index_raw if self.rgb_index_raw is not None else self.rgb_index,
            "runtime_profile": self.runtime_profile,
        }
        return {k: v for k, v in named.items() if v is not None}

    def section(self, name: str) -> list[dict[str, Any]]:
        return dicts((self.static or {}).get(name))

    @property
    def objects(self) -> list[dict[str, Any]]:
        return self.section("objects")

    @property
    def walkable(self) -> list[dict[str, Any]]:
        return self.section("walkable")

    @property
    def portals(self) -> list[dict[str, Any]]:
        return self.section("portals")

    @property
    def floors(self) -> list[dict[str, Any]]:
        return self.section("floors")

    def _camera_source(self, name: str) -> list[dict[str, Any]]:
        # U02: cameras.json wins; scene_static.json is accepted as the fallback location.
        if isinstance(self.cameras_doc, dict) and name in self.cameras_doc:
            return dicts(self.cameras_doc.get(name))
        return dicts((self.static or {}).get(name))

    @property
    def cameras(self) -> list[dict[str, Any]]:
        return self._camera_source("cameras")

    @property
    def run_bindings(self) -> list[dict[str, Any]]:
        return self._camera_source("run_bindings")

    @property
    def solids(self) -> list[dict[str, Any]]:
        """objects[] entries of class WALL/OBSTACLE (§3.5 fields merged into the record, U01)."""
        return [o for o in self.objects if o.get("class") in ("WALL", "OBSTACLE")]

    def object_by_id(self, id_: str) -> dict[str, Any] | None:
        return next((o for o in self.objects if o.get("id") == id_), None)

    def walk_polygons(self) -> dict[str, Polygon]:
        out: dict[str, Polygon] = {}
        for w in self.walkable:
            poly = polygon_from(w.get("polygon_m"), w.get("holes_m"))
            if poly is not None and isinstance(w.get("id"), str):
                out[w["id"]] = poly
        return out
