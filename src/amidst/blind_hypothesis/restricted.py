"""Restricted-policy layer for blind-interval hypotheses (D15, contract §3.2.1).

A *restricted region* is a floor area the user confirmed, region by region, as off
limits **by policy**. It is not a physical obstacle: the layer is separate from the
walkable map (``walkable_ref`` / ``portal_ref``), may overlap any walkable region
(``SOURCE_DERIVED``, ``ANNOTATION_ONLY`` or ``walkable: UNKNOWN``), never replaces the
physical tier, and changes **labels only** (no constraint, reachability, check result
or ranking). Its tier is always ``RESTRICTED_POLICY``.

Input is the mapping C7's ``load_restricted_policy`` returns for one variant::

    {"restricted_ref": {"map_ref", "sha256", "source", "tier"},
     "restricted_regions": [{"region_id", "tier", "geometry" (GeoJSON), "confirmation_ref",
                             "physical_obstacle": False, "affects_walkability": False,
                             "affects_ranking": False, ...}, ...]}

Extra row fields (annotation record/file hashes, ``decision``) are accepted and ignored
by the algorithm; they are covered by the file hash in ``restricted_ref.sha256``.
:func:`parse_restricted_layer` is pure and fail-closed: any deviation raises
:class:`RestrictedLayerError` with a ``problem`` code, and the engine answers
``UNKNOWN`` / ``RESTRICTED_POLICY_INVALID``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.geometry.base import BaseGeometry

RESTRICTED_TIER = "RESTRICTED_POLICY"
RESTRICTED_SOURCE = "USER_CONFIRMED_ANNOTATION"
RESTRICTED_INVALID_REASON = "RESTRICTED_POLICY_INVALID"
_REF_KEYS = frozenset({"map_ref", "sha256", "source", "tier"})
_SHA256 = re.compile(r"[0-9a-f]{64}")
_POLICY_ONLY_FLAGS = ("physical_obstacle", "affects_walkability", "affects_ranking")


class RestrictedLayerError(ValueError):
    """The restricted-policy input violates contract §3.2.1; ``problem`` is a code."""

    def __init__(self, problem: str, **detail: Any) -> None:
        super().__init__(problem)
        self.problem = problem
        self.detail = detail


@dataclass(frozen=True)
class RestrictedLayer:
    """A validated restricted-policy layer (immutable)."""

    ref: Mapping[str, str]
    regions: Mapping[str, BaseGeometry]
    confirmation_refs: Mapping[str, str]
    # Raw ``{region_id, tier, geometry, confirmation_ref}`` rows in region-id order,
    # exactly as given; the engine hashes them (canonical JSON) for the fingerprint.
    rows: tuple[Mapping[str, Any], ...]

    @property
    def region_ids(self) -> list[str]:
        return sorted(self.regions)


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _polygonal(geometry: Any, region_id: str) -> BaseGeometry:
    if not isinstance(geometry, Mapping) or geometry.get("type") not in ("Polygon", "MultiPolygon"):
        raise RestrictedLayerError("GEOMETRY_INVALID", region_id=region_id)
    try:
        polygon = shape(geometry)
    except (TypeError, ValueError, KeyError, IndexError, AttributeError) as error:
        raise RestrictedLayerError("GEOMETRY_INVALID", region_id=region_id) from error
    if (
        not isinstance(polygon, (Polygon, MultiPolygon))
        or polygon.is_empty
        or not polygon.is_valid
        or not math.isfinite(polygon.area)
        or polygon.area <= 0
    ):
        raise RestrictedLayerError("GEOMETRY_INVALID", region_id=region_id)
    return polygon


def parse_restricted_layer(raw: Any) -> RestrictedLayer:
    """Validate a C7 restricted-policy mapping; raise :class:`RestrictedLayerError`."""

    if not isinstance(raw, Mapping) or not {"restricted_ref", "restricted_regions"} <= set(raw):
        raise RestrictedLayerError("LAYER_FORMAT")
    ref = raw["restricted_ref"]
    if (
        not isinstance(ref, Mapping)
        or set(ref) != _REF_KEYS
        or not _nonempty_str(ref["map_ref"])
        or not isinstance(ref["sha256"], str)
        or _SHA256.fullmatch(ref["sha256"]) is None
        or ref["source"] != RESTRICTED_SOURCE
        or ref["tier"] != RESTRICTED_TIER
    ):
        raise RestrictedLayerError("REF_INVALID")
    rows = raw["restricted_regions"]
    # A layer without a user-confirmed region is expressed as "no layer" (null), not
    # as an empty one: refuse to echo a ref that labels nothing.
    if not isinstance(rows, (list, tuple)) or not rows:
        raise RestrictedLayerError("REGIONS_EMPTY")

    regions: dict[str, BaseGeometry] = {}
    confirmations: dict[str, str] = {}
    kept: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not _nonempty_str(row.get("region_id")):
            raise RestrictedLayerError("REGION_FORMAT")
        region_id = row["region_id"]
        if region_id in regions:
            raise RestrictedLayerError("REGION_ID_DUPLICATE", region_id=region_id)
        if row.get("tier") != RESTRICTED_TIER:
            raise RestrictedLayerError("TIER_INVALID", region_id=region_id)
        if not _nonempty_str(row.get("confirmation_ref")):
            raise RestrictedLayerError("CONFIRMATION_MISSING", region_id=region_id)
        # C7 states the layer is policy only; anything else is not this layer.
        if any(row.get(flag) is not False for flag in _POLICY_ONLY_FLAGS):
            raise RestrictedLayerError("AUTHORITY_INVALID", region_id=region_id)
        regions[region_id] = _polygonal(row.get("geometry"), region_id)
        confirmations[region_id] = row["confirmation_ref"]
        kept[region_id] = {
            "region_id": region_id,
            "tier": RESTRICTED_TIER,
            "geometry": row["geometry"],
            "confirmation_ref": row["confirmation_ref"],
        }
    order = sorted(regions)
    return RestrictedLayer(
        ref={key: ref[key] for key in sorted(_REF_KEYS)},
        regions={name: regions[name] for name in order},
        confirmation_refs={name: confirmations[name] for name in order},
        rows=tuple(kept[name] for name in order),
    )
