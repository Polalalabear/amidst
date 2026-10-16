"""Blind-interval hypothesis generation (task K1, contract draft K0 BH v1).

Pure and deterministic: no file, network, clock or RNG access. Inputs are the
two blind-interval endpoint states (interval-observation v1 ``ground_estimate``),
a :class:`~amidst.blind_hypothesis.floor_map.FloorMap`, the versioned
configuration mapping (speed range etc., never GT) and camera-visibility negative
evidence with its resolved visible-floor footprints. Output is a
``workbench.blind-hypothesis.v1`` response: up to K representative paths and one
reachable region per clock step, all ``INFERRED_HYPOTHESIS``; ranking is
configured plausibility, not probability; physical authority stays ``UNKNOWN``
and identity ``UNCONFIRMED``.

Method (contract §4): a floor lattice inside the walkable map; geodesic forward/
backward reach bounds the reachable regions, intersected with the unseen mask.
Endpoint regions seed the lattice only through cells they can see along the map
(never through a wall, never moved onto the map); reach is widened by one cell
diagonal and region cells are read as squares.
Candidate routes join the start and end shortest-path trees through a via cell
(skipping via cells within ``min_separation_m`` of routes already pooled), are
string-pulled inside each region and sampled at constant speed along the route,
so speeds are not limited by lattice directions. Each candidate re-checks speed,
walkable and unseen on its own samples; K representatives are chosen by score
with the contract's separation rule.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import shapely
from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points, unary_union
from shapely.prepared import PreparedGeometry, prep

from amidst.blind_hypothesis.floor_map import ANNOTATION_MAP_KIND, FloorMap

REQUEST_SCHEMA = "office-demo.blind-hypothesis-request.v1"
RESPONSE_SCHEMA = "workbench.blind-hypothesis.v1"
CONFIG_SCHEMA = "office-demo.blind-hypothesis-config.v1"
INTERVAL_OBSERVATION_SCHEMA = "office-demo.interval-observation.v1"
PRODUCER = "blind-hypothesis"
PRODUCER_VERSION = "v1"
MAX_SPEED_M_S = 8.0
EVIDENCE_STATE = "INFERRED_HYPOTHESIS"
RANKING_BASIS = "CONFIGURED_PLAUSIBILITY_NOT_PROBABILITY"
REQUIRED_VISIBILITY_METHOD = "SOURCE_MESH_RAYCAST"
NEGATIVE_EVIDENCE_ORIGINS = frozenset({"BLIND_INTERVAL_BASELINE", "RETRIEVAL_FEEDBACK"})
FLOOR_Z_TOLERANCE_M = 1e-3
CLOCK_TOLERANCE_S = 1e-6
_EPS = 1e-9
_ROUND = 6
# Seed / anchor visibility tolerance: absorbs float error of nearest points that lie
# exactly on a map boundary; far below any wall thickness.
_VISIBILITY_TOL_M = 1e-7
DEFAULT_MAX_ENDPOINT_SUBSTITUTION_S = 1.0
SUBSTITUTION_RULE = "SAME_TRACK_NEAREST_USABLE_OUTWARD_V1"

_REQUEST_KEYS = frozenset(
    {
        "schema_version",
        "session_ref",
        "scene_id",
        "candidate_ref",
        "start",
        "end",
        "top_k",
        "negative_evidence",
        "previous_response_sha256",
    }
)
_ENDPOINT_KEYS = frozenset(
    {"observation_ref", "camera_id", "timestamp_s", "evidence_state", "ground_estimate"}
)
_ENDPOINT_OPTIONAL_KEYS = frozenset({"substitution"})  # contract §3.1; absent == null
_SUBSTITUTION_KEYS = frozenset(
    {
        "rule",
        "track_ref",
        "original",
        "substitute",
        "time_offset_s",
        "max_offset_s",
        "skipped_observation_refs",
    }
)
_SUBSTITUTION_ORIGINAL_KEYS = frozenset(
    {"observation_ref", "timestamp_s", "ground_estimate_status", "ground_estimate_reason"}
)
_SUBSTITUTION_SUBSTITUTE_KEYS = frozenset({"observation_ref", "timestamp_s"})
_NEGATIVE_EVIDENCE_KEYS = frozenset(
    {
        "negative_evidence_ref",
        "origin",
        "camera_id",
        "frame_refs",
        "visibility_ref",
        "detection_result",
        "detection_producer",
        "retrieval_query_id",
        "sha256",
        "visible_floor",
    }
)


class HypothesisRequestError(ValueError):
    """The request is malformed (wrong shape or forbidden fields); not evidence."""


class _Unknown(Exception):
    def __init__(self, reason: str, **detail: Any) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


# --------------------------------------------------------------------------- config


@dataclass(frozen=True)
class HypothesisConfig:
    config_ref: str
    config_sha256: str
    speed_min_m_s: float
    speed_max_m_s: float
    nominal_speed_m_s: float
    weight_length: float
    weight_turn: float
    weight_speed: float
    grid_step_m: float
    time_step_s: float
    body_radius_m: float
    lattice_metric_factor: float
    max_blind_interval_s: float
    max_time_steps: int
    max_grid_cells: int
    max_candidate_paths: int
    min_separation_m: float
    max_negative_evidence: int
    max_region_samples: int
    max_endpoint_substitution_s: float = DEFAULT_MAX_ENDPOINT_SUBSTITUTION_S

    @property
    def half_diagonal_m(self) -> float:
        """Largest offset between a point and the centre of its grid cell."""
        return self.grid_step_m * math.sqrt(2.0) / 2.0

    @property
    def reach_slack_m(self) -> float:
        """Additive widening of every reachable region (a full cell diagonal).

        Seeds are exact (visible from the endpoint region) and region cells are read
        as squares, so the gap between the lattice geodesic and the continuous one
        is bounded by about one diagonal; checked by the visibility-graph
        regression in the unit tests (not proved).
        """
        return self.grid_step_m * math.sqrt(2.0)


def _finite(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("not a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("not finite")
    return number


def _strict_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("not an integer")
    return value


def parse_config(
    config: Mapping[str, Any], *, scene_id: str, config_sha256: str
) -> HypothesisConfig:
    """Parse the versioned configuration for one scene; raise on any violation."""

    if config.get("schema_version") != CONFIG_SCHEMA:
        raise ValueError("unsupported config schema")
    speed = config["speed_range_m_s"]
    if speed.get("source") != "CONFIGURED_NOT_GT":
        raise ValueError("speed range must be configuration, not GT")
    low, high = _finite(speed["min"]), _finite(speed["max"])
    if not 0.0 <= low < high <= MAX_SPEED_M_S:
        raise ValueError("speed range outside contract bounds")
    scene = config["scenes"][scene_id]
    weights = config["plausibility_weights"]
    limits = config["limits"]
    parsed = HypothesisConfig(
        config_ref=str(config["config_ref"]),
        config_sha256=config_sha256,
        speed_min_m_s=low,
        speed_max_m_s=high,
        nominal_speed_m_s=_finite(config["nominal_speed_m_s"]),
        weight_length=_finite(weights["path_length_m"]),
        weight_turn=_finite(weights["turn_rad"]),
        weight_speed=_finite(weights["speed_deviation_m_s"]),
        grid_step_m=_finite(config["grid_step_m"]),
        time_step_s=_finite(scene["time_step_s"]),
        body_radius_m=_finite(scene["body_radius_m"]),
        lattice_metric_factor=_finite(config["lattice_metric_factor"]),
        max_blind_interval_s=_finite(limits["max_blind_interval_s"]),
        max_time_steps=_strict_int(limits["max_time_steps"]),
        max_grid_cells=_strict_int(limits["max_grid_cells"]),
        max_candidate_paths=_strict_int(limits["max_candidate_paths"]),
        min_separation_m=_finite(limits["min_separation_m"]),
        max_negative_evidence=_strict_int(limits["max_negative_evidence"]),
        max_region_samples=_strict_int(limits["max_region_samples"]),
        max_endpoint_substitution_s=_finite(
            limits.get("max_endpoint_substitution_s", DEFAULT_MAX_ENDPOINT_SUBSTITUTION_S)
        ),
    )
    positive = (
        parsed.grid_step_m,
        parsed.time_step_s,
        parsed.lattice_metric_factor,
        parsed.max_blind_interval_s,
        parsed.min_separation_m,
        parsed.max_endpoint_substitution_s,
    )
    if min(positive) <= 0 or parsed.body_radius_m < 0 or parsed.lattice_metric_factor < 1.0:
        raise ValueError("non-positive lattice, clock or limit setting")
    if min(parsed.weight_length, parsed.weight_turn, parsed.weight_speed) < 0:
        raise ValueError("negative plausibility weight")
    if not 0.0 <= parsed.nominal_speed_m_s <= high:
        raise ValueError("nominal speed outside configured range")
    return parsed


# ------------------------------------------------------------------------ helpers


def canonical_sha256(payload: Any) -> str:
    """SHA-256 of canonical JSON (sorted keys, compact, no NaN). IO-Q7 is open."""

    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _r(value: float) -> float:
    return round(float(value), _ROUND)


def _xyz(x: float, y: float, z: float) -> list[float]:
    return [_r(x), _r(y), _r(z)]


@dataclass(frozen=True)
class _Endpoint:
    observation_ref: str
    camera_id: str
    timestamp_s: float
    kind: str
    region: BaseGeometry  # floor-plane geometry the endpoint may occupy
    anchor: tuple[float, float]
    # Contract §5 ``endpoint_substitutions`` entry (D7), copied unchanged; None if the
    # caller did not substitute. The module never substitutes by itself.
    substitution: dict[str, Any] | None = None


def _substitution_record(
    raw: Any, label: str, observation_ref: str, timestamp: float, max_offset_s: float
) -> dict[str, Any]:
    """Check what the module can see of a §3.1.1 record and return the §5 entry."""

    def invalid(code: str) -> _Unknown:
        return _Unknown("ENDPOINT_SUBSTITUTION_INVALID", endpoint=label, problem=code)

    if not isinstance(raw, Mapping) or set(raw) != _SUBSTITUTION_KEYS:
        raise invalid("SHAPE")
    original, substitute = raw["original"], raw["substitute"]
    if (
        not isinstance(original, Mapping)
        or set(original) != _SUBSTITUTION_ORIGINAL_KEYS
        or not isinstance(substitute, Mapping)
        or set(substitute) != _SUBSTITUTION_SUBSTITUTE_KEYS
    ):
        raise invalid("SHAPE")
    skipped = raw["skipped_observation_refs"]
    if not isinstance(skipped, list) or not all(isinstance(ref, str) for ref in skipped):
        raise invalid("SHAPE")
    if raw["rule"] != SUBSTITUTION_RULE:
        raise invalid("RULE")
    try:
        offset = _finite(raw["time_offset_s"])
        record_max = _finite(raw["max_offset_s"])
        original_ts = _finite(original["timestamp_s"])
        substitute_ts = _finite(substitute["timestamp_s"])
    except (TypeError, ValueError):
        raise invalid("SHAPE") from None
    if original["ground_estimate_status"] != "UNKNOWN":
        raise invalid("ORIGINAL_NOT_UNKNOWN")
    if (
        substitute["observation_ref"] != observation_ref
        or abs(substitute_ts - timestamp) > CLOCK_TOLERANCE_S
        or original["observation_ref"] == observation_ref
    ):
        raise invalid("SUBSTITUTE_NOT_THE_ENDPOINT")
    if abs(substitute_ts - original_ts - offset) > CLOCK_TOLERANCE_S:
        raise invalid("TIME_OFFSET_INCONSISTENT")
    if (offset >= 0) if label == "start" else (offset <= 0):
        raise invalid("NOT_OUTWARD")
    if abs(record_max - max_offset_s) > CLOCK_TOLERANCE_S:
        raise invalid("MAX_OFFSET_INCONSISTENT")
    if abs(offset) > max_offset_s + CLOCK_TOLERANCE_S:
        raise invalid("OFFSET_TOO_LARGE")
    return {
        "endpoint": label.upper(),
        "original_observation_ref": original["observation_ref"],
        "original_timestamp_s": original_ts,
        "original_reason": original["ground_estimate_reason"],
        "substitute_observation_ref": observation_ref,
        "substitute_timestamp_s": timestamp,
        "time_offset_s": _r(offset),
        "max_offset_s": record_max,
        "rule": raw["rule"],
        "track_ref": raw["track_ref"],
        "skipped_observation_refs": list(skipped),
    }


def _endpoint(
    raw: Any, label: str, floor_z_m: float | None, cfg: HypothesisConfig
) -> tuple[_Endpoint | None, dict[str, Any] | None]:
    """Validate one endpoint; return (endpoint, None) or (None, trace problem)."""

    def problem(code: str) -> tuple[None, dict[str, Any]]:
        return None, {"step": "ENDPOINT_REJECTED", "endpoint": label, "problem": code}

    if (
        not isinstance(raw, Mapping)
        or not _ENDPOINT_KEYS <= set(raw)
        or set(raw) - _ENDPOINT_KEYS - _ENDPOINT_OPTIONAL_KEYS
    ):
        raise HypothesisRequestError(
            f"{label}: endpoint fields must be {sorted(_ENDPOINT_KEYS)} "
            f"plus optional {sorted(_ENDPOINT_OPTIONAL_KEYS)}"
        )
    if raw["evidence_state"] != "PROJECTED_OBSERVATION":
        return problem("EVIDENCE_STATE_NOT_PROJECTED_OBSERVATION")
    estimate = raw["ground_estimate"]
    if estimate is None:
        return problem("GROUND_ESTIMATE_NOT_PRODUCED")
    if not isinstance(estimate, Mapping):
        return problem("GROUND_ESTIMATE_MALFORMED")
    if estimate.get("schema_version") != INTERVAL_OBSERVATION_SCHEMA:
        return problem("GROUND_ESTIMATE_SCHEMA")
    if estimate.get("status") != "READY":
        return problem(f"GROUND_ESTIMATE_{estimate.get('status')}:{estimate.get('reason')}")
    if estimate.get("evidence_state") != "PROJECTED_OBSERVATION":
        return problem("GROUND_ESTIMATE_EVIDENCE_STATE")
    provenance = estimate.get("provenance")
    if not isinstance(provenance, Mapping) or provenance.get("gt_read") is not False:
        return problem("GROUND_ESTIMATE_GT_READ_NOT_FALSE")
    try:
        timestamp = _finite(raw["timestamp_s"])
        same_time = abs(_finite(estimate.get("timestamp_s")) - timestamp) <= CLOCK_TOLERANCE_S
    except (TypeError, ValueError):
        return problem("TIMESTAMP_INVALID")
    if (
        estimate.get("observation_ref") != raw["observation_ref"]
        or estimate.get("camera_id") != raw["camera_id"]
        or not same_time
    ):
        return problem("GROUND_ESTIMATE_OBSERVATION_MISMATCH")
    kind = estimate.get("estimate_kind")
    try:
        if kind == "POINT":
            quality = estimate.get("contact_quality")
            if not isinstance(quality, Mapping) or quality.get("status") != "PASS":
                return problem("POINT_WITHOUT_CONTACT_QUALITY_PASS")
            point = [_finite(v) for v in estimate["point_m"]]
            radius = _finite(estimate["pixel_sensitivity_m"])
            if len(point) != 3 or radius <= 0:
                return problem("POINT_INVALID")
            zs = [point[2]]
            region = Point(point[0], point[1]).buffer(radius, quad_segs=16)
            anchor = (point[0], point[1])
        elif kind == "SEGMENT":
            segment = estimate["segment"]
            near = [_finite(v) for v in segment["near_m"]]
            far = [_finite(v) for v in segment["far_m"]]
            if len(near) != 3 or len(far) != 3:
                return problem("SEGMENT_INVALID")
            zs = [near[2], far[2]]
            region = LineString([(near[0], near[1]), (far[0], far[1])])
            if region.length <= 0:
                region = Point(near[0], near[1])
            centroid = region.centroid
            anchor = (float(centroid.x), float(centroid.y))
        else:
            return problem(f"ESTIMATE_KIND_{kind}")
    except (KeyError, TypeError, ValueError):
        return problem("GROUND_ESTIMATE_MALFORMED")
    if floor_z_m is not None and any(abs(z - floor_z_m) > FLOOR_Z_TOLERANCE_M for z in zs):
        return problem("FLOOR_Z_MISMATCH")
    substitution = None
    if raw.get("substitution") is not None:
        substitution = _substitution_record(
            raw["substitution"],
            label,
            str(raw["observation_ref"]),
            timestamp,
            cfg.max_endpoint_substitution_s,
        )
    return (
        _Endpoint(
            observation_ref=str(raw["observation_ref"]),
            camera_id=str(raw["camera_id"]),
            timestamp_s=timestamp,
            kind=str(kind),
            region=region,
            anchor=anchor,
            substitution=substitution,
        ),
        None,
    )


@dataclass(frozen=True)
class _Evidence:
    ref: str
    camera_id: str
    step_indices: tuple[int, ...]
    # Footprint eroded by the body radius (sample check, contract §4.3): a sample
    # inside it conflicts with the negative evidence. None: camera sees no floor.
    eroded_visible: BaseGeometry | None
    # Footprint eroded by body radius + half cell diagonal (region mask): a cell is
    # pruned only if its whole square is inside, so a sample that passes the sample
    # check is never in a pruned cell. Always a subset of ``eroded_visible``.
    eroded_region: BaseGeometry | None


def _negative_evidence(
    entries: Any, times: Sequence[float], cfg: HypothesisConfig
) -> list[_Evidence]:
    if not isinstance(entries, list):
        raise HypothesisRequestError("negative_evidence must be a list")
    if len(entries) > cfg.max_negative_evidence:
        raise _Unknown("NEGATIVE_EVIDENCE_INVALID", problem="TOO_MANY_ENTRIES")
    parsed: list[_Evidence] = []
    seen: set[str] = set()
    half = cfg.time_step_s / 2.0
    for order, entry in enumerate(entries, start=1):

        def bad(code: str, order: int = order) -> _Unknown:
            return _Unknown("NEGATIVE_EVIDENCE_INVALID", order=order, problem=code)

        if not isinstance(entry, Mapping) or set(entry) != _NEGATIVE_EVIDENCE_KEYS:
            raise bad("FIELDS")
        try:
            claimed_ok = entry["sha256"] == canonical_sha256(
                {key: value for key, value in entry.items() if key != "sha256"}
            )
        except (TypeError, ValueError):
            claimed_ok = False
        if not claimed_ok:
            # The entry hash is recomputed (canonical JSON without ``sha256``): a re-run
            # compares entries by it, so a claimed value alone would prove nothing.
            raise bad("SHA256_MISMATCH")
        ref = entry["negative_evidence_ref"]
        if not isinstance(ref, str) or not ref or ref in seen:
            raise bad("REF_MISSING_OR_DUPLICATE")
        seen.add(ref)
        if entry["origin"] not in NEGATIVE_EVIDENCE_ORIGINS:
            raise bad("ORIGIN")
        if entry["detection_result"] != "NO_DETECTION":
            raise bad("DETECTION_RESULT_NOT_NO_DETECTION")
        producer = entry["detection_producer"]
        if not isinstance(producer, Mapping) or not producer.get("producer"):
            raise bad("DETECTION_PRODUCER")
        visible = entry["visible_floor"]
        if not isinstance(visible, Mapping) or visible.get("method") != REQUIRED_VISIBILITY_METHOD:
            raise bad("VISIBILITY_METHOD_NOT_SOURCE_MESH_RAYCAST")
        frames = entry["frame_refs"]
        if not isinstance(frames, list) or not frames:
            raise bad("FRAMES")
        indices: set[int] = set()
        for frame in frames:
            try:
                ts = _finite(frame["timestamp_s"])
            except (KeyError, TypeError, ValueError):
                raise bad("FRAME_TIMESTAMP") from None
            matches = [i for i, t in enumerate(times) if abs(ts - t) < half - _EPS]
            if len(matches) != 1:
                raise bad("FRAME_OUTSIDE_BLIND_INTERVAL")
            indices.add(matches[0])
        try:
            rings = visible["polygons"]
            polygons = [Polygon([(float(x), float(y)) for x, y in ring]) for ring in rings]
        except (KeyError, TypeError, ValueError):
            raise bad("VISIBLE_FLOOR_POLYGONS") from None
        if any(not p.is_valid or p.area <= 0 for p in polygons):
            raise bad("VISIBLE_FLOOR_POLYGONS")
        eroded: BaseGeometry | None = None
        eroded_region: BaseGeometry | None = None
        if polygons:
            footprint = unary_union(polygons)
            shrunk = footprint.buffer(-cfg.body_radius_m)
            eroded = None if shrunk.is_empty else shrunk
            shrunk_region = footprint.buffer(-(cfg.body_radius_m + cfg.half_diagonal_m))
            eroded_region = None if shrunk_region.is_empty else shrunk_region
        parsed.append(
            _Evidence(ref, str(entry["camera_id"]), tuple(sorted(indices)), eroded, eroded_region)
        )
    return parsed


# ------------------------------------------------------------------------ lattice


class _Lattice:
    """Grid cells (centres at integer multiples of the step) inside the map."""

    def __init__(
        self,
        floor_map: FloorMap,
        cfg: HypothesisConfig,
        start: _Endpoint,
        end: _Endpoint,
        duration_s: float,
        walk_union: BaseGeometry,
    ) -> None:
        g = cfg.grid_step_m
        self.g = g
        self.walkable_ref = floor_map.descriptor.walkable_ref
        # Walkable (TRUE) regions come first so a cell in both a TRUE and an UNKNOWN
        # region is labelled TRUE: the unconfirmed label never hides a verified area.
        unknown_map = dict(getattr(floor_map, "unknown_regions", {}) or {})
        self.region_ids = sorted(floor_map.regions) + sorted(unknown_map)
        self.unknown_ids = frozenset(unknown_map)
        all_regions = {**floor_map.regions, **unknown_map}
        self.regions = {name: all_regions[name] for name in self.region_ids}
        default_tier = (
            "ANNOTATION_ONLY" if floor_map.descriptor.kind == ANNOTATION_MAP_KIND else "UNKNOWN"
        )
        tiers = getattr(floor_map, "region_tiers", {}) or {}
        self.tier_of = {
            name: "UNKNOWN" if name in self.unknown_ids else str(tiers.get(name, default_tier))
            for name in self.region_ids
        }
        self.confirmed_union = unary_union(
            [*floor_map.regions.values(), *floor_map.portals.values()]
        )
        self.unknown_union = unary_union(list(unknown_map.values())) if unknown_map else None
        self.map_regions_prepared = prep(unary_union(list(self.regions.values())))
        self.prepared: dict[str, PreparedGeometry] = {
            name: prep(geom) for name, geom in self.regions.items()
        }
        self.portal_ids = sorted(floor_map.portals)
        self.portals = {name: floor_map.portals[name] for name in self.portal_ids}
        # Sample-level walkable check: walkable polygons (TRUE and UNKNOWN) plus portal
        # footprints (a doorway is passable even where no threshold is annotated).
        self.walk_union = walk_union
        self.walk_prepared = prep(self.walk_union)
        # Slightly widened copy for visibility tests of seed / anchor segments.
        self.walk_tolerant = self.walk_union.buffer(_VISIBILITY_TOL_M)
        shapely.prepare(self.walk_tolerant)

        budget = (
            cfg.speed_max_m_s * duration_s * cfg.lattice_metric_factor
            + start.region.hausdorff_distance(Point(start.anchor))
            + end.region.hausdorff_distance(Point(end.anchor))
            + 2.0 * g
        )
        sx, sy = start.anchor
        ex, ey = end.anchor
        lo_x, hi_x = min(sx, ex) - budget, max(sx, ex) + budget
        lo_y, hi_y = min(sy, ey) - budget, max(sy, ey) + budget
        ix = np.arange(math.floor(lo_x / g), math.ceil(hi_x / g) + 1)
        iy = np.arange(math.floor(lo_y / g), math.ceil(hi_y / g) + 1)
        if ix.size * iy.size > 50 * cfg.max_grid_cells:
            raise _Unknown("SEARCH_BUDGET_EXHAUSTED", limit="MAX_GRID_CELLS", stage="BBOX")
        gx, gy = np.meshgrid(ix, iy, indexing="ij")
        gx, gy = gx.ravel(), gy.ravel()
        xs, ys = gx * g, gy * g
        inside_ellipse = np.hypot(xs - sx, ys - sy) + np.hypot(xs - ex, ys - ey) <= budget + _EPS
        gx, gy, xs, ys = (
            gx[inside_ellipse],
            gy[inside_ellipse],
            xs[inside_ellipse],
            ys[inside_ellipse],
        )
        region_index = np.full(xs.shape, -1, dtype=int)
        for index, name in enumerate(self.region_ids):
            hit = shapely.intersects_xy(self.regions[name], xs, ys) & (region_index < 0)
            region_index[hit] = index
        keep = region_index >= 0
        if int(keep.sum()) > cfg.max_grid_cells:
            raise _Unknown("SEARCH_BUDGET_EXHAUSTED", limit="MAX_GRID_CELLS", stage="LATTICE")
        order = np.lexsort((gy[keep], gx[keep]))
        self.ij: list[tuple[int, int]] = [
            (int(a), int(b)) for a, b in zip(gx[keep][order], gy[keep][order], strict=True)
        ]
        self.xs = xs[keep][order].astype(float)
        self.ys = ys[keep][order].astype(float)
        self.region_of = [self.region_ids[i] for i in region_index[keep][order]]
        self.unknown_cell = np.array(
            [name in self.unknown_ids for name in self.region_of], dtype=bool
        )
        self.index = {cell: k for k, cell in enumerate(self.ij)}
        self._edge_cache: dict[tuple[int, int], tuple[bool, str | None]] = {}
        self._pair_cache: dict[tuple[str, str, str], PreparedGeometry] = {}

    def __len__(self) -> int:
        return len(self.ij)

    def xy(self, k: int) -> tuple[float, float]:
        return float(self.xs[k]), float(self.ys[k])

    def edge(self, a: int, b: int) -> tuple[bool, str | None]:
        """Whether the straight move between cells stays walkable (symmetric).

        Valid inside one walkable polygon (closed set, so polygons that touch or
        overlap connect), or across a portal footprint joining the two cells'
        regions; the portal id is returned in that case.
        """

        if a == b:
            return True, None
        key = (a, b) if a < b else (b, a)
        cached = self._edge_cache.get(key)
        if cached is not None:
            return cached
        segment = LineString([self.xy(a), self.xy(b)])
        ra, rb = self.region_of[a], self.region_of[b]
        result: tuple[bool, str | None] = (False, None)
        if self.prepared[ra].covers(segment) or self.prepared[rb].covers(segment):
            result = (True, None)
        elif ra != rb:
            for portal in self.portal_ids:
                if not self.portals[portal].intersects(segment):
                    continue
                pair = (min(ra, rb), max(ra, rb), portal)
                joined = self._pair_cache.get(pair)
                if joined is None:
                    joined = prep(
                        unary_union([self.regions[ra], self.regions[rb], self.portals[portal]])
                    )
                    self._pair_cache[pair] = joined
                if joined.covers(segment):
                    result = (True, portal)
                    break
        self._edge_cache[key] = result
        return result

    def region_at(self, x: float, y: float) -> str | None:
        """First region id (TRUE regions before UNKNOWN ones) covering the point."""
        point = Point(x, y)
        for name in self.region_ids:
            if self.prepared[name].covers(point):
                return name
        return None

    def offsets(self, radius_m: float) -> list[tuple[int, int, float]]:
        reach = int(math.floor(radius_m / self.g + _EPS))
        found = []
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                distance = math.hypot(dx, dy) * self.g
                if distance <= radius_m + _EPS:
                    found.append((dx, dy, distance))
        return sorted(found, key=lambda item: (item[2], item[0], item[1]))

    def neighbours(
        self, k: int, offsets: Sequence[tuple[int, int, float]]
    ) -> list[tuple[int, float]]:
        i, j = self.ij[k]
        result = []
        for dx, dy, distance in offsets:
            other = self.index.get((i + dx, j + dy))
            if other is not None and self.edge(k, other)[0]:
                result.append((other, distance))
        return result

    def visible_seeds(self, support: BaseGeometry) -> tuple[np.ndarray, np.ndarray]:
        """Seed costs and anchors for one endpoint (contract §4.1, D11).

        A cell is a seed only if the straight segment from the nearest point of
        ``support`` (endpoint region within the map) to the cell centre stays on
        the walkable map, so a seed is never reached through a wall. Cost is that
        segment's length. Returns (cost, anchor_xy); cost is inf for non-seeds.
        """

        lines = shapely.shortest_line(support, shapely.points(self.xs, self.ys))
        coords = shapely.get_coordinates(lines).reshape(-1, 2, 2)
        anchors = coords[:, 0, :]
        cost = np.hypot(coords[:, 1, 0] - anchors[:, 0], coords[:, 1, 1] - anchors[:, 1])
        visible = shapely.covers(self.walk_tolerant, lines)
        return np.where(visible, cost, math.inf), anchors


def _geodesic(
    lattice: _Lattice, seeds: np.ndarray, neighbours: Sequence[Sequence[tuple[int, float]]]
) -> tuple[np.ndarray, np.ndarray]:
    """Multi-source Dijkstra; seeds hold start costs. Returns (distance, predecessor)."""

    distance = np.full(len(lattice), math.inf)
    predecessor = np.full(len(lattice), -1, dtype=int)
    heap: list[tuple[float, tuple[int, int], int]] = []
    for k in np.flatnonzero(np.isfinite(seeds)):
        distance[k] = seeds[k]
        heap.append((float(seeds[k]), lattice.ij[int(k)], int(k)))
    heapq.heapify(heap)
    while heap:
        d, _, k = heapq.heappop(heap)
        if d > distance[k]:
            continue
        for other, step in neighbours[k]:
            candidate = d + step
            if candidate < distance[other] - _EPS:
                distance[other] = candidate
                predecessor[other] = k
                heapq.heappush(heap, (candidate, lattice.ij[other], other))
    return distance, predecessor


# ------------------------------------------------------------------------ response


def _base_response(
    request: Mapping[str, Any],
    cfg: HypothesisConfig | None,
    raw_config: Mapping[str, Any],
    config_sha256: str,
    floor_map: FloorMap | None,
    source_binding: Mapping[str, Any],
    visibility_index_ref: Mapping[str, Any] | None,
) -> dict[str, Any]:
    descriptor = floor_map.descriptor if floor_map is not None else None
    start = request.get("start") if isinstance(request.get("start"), Mapping) else {}
    end = request.get("end") if isinstance(request.get("end"), Mapping) else {}
    start_s, end_s = start.get("timestamp_s"), end.get("timestamp_s")
    duration = (
        _r(end_s - start_s)
        if isinstance(start_s, (int, float)) and isinstance(end_s, (int, float))
        else None
    )
    speed = raw_config.get("speed_range_m_s") if isinstance(raw_config, Mapping) else None
    configuration: dict[str, Any] = {
        "speed_range_m_s": {
            "min": cfg.speed_min_m_s if cfg else (speed or {}).get("min"),
            "max": cfg.speed_max_m_s if cfg else (speed or {}).get("max"),
            "source": "CONFIGURED_NOT_GT",
            "config_ref": raw_config.get("config_ref") if isinstance(raw_config, Mapping) else None,
            "config_sha256": config_sha256,
        },
        "walkable_ref": {
            "annotation_ref": descriptor.walkable_ref if descriptor else "UNKNOWN",
            "sha256": descriptor.sha256 if descriptor else None,
            "map_kind": descriptor.kind if descriptor else "UNKNOWN",
        },
        "portal_ref": {
            "annotation_ref": descriptor.portal_ref if descriptor else "UNKNOWN",
            "sha256": descriptor.sha256 if descriptor else None,
            "map_kind": descriptor.kind if descriptor else "UNKNOWN",
        },
        "visibility_index_ref": dict(visibility_index_ref)
        if visibility_index_ref is not None
        else {"index_ref": "UNKNOWN", "sha256": None, "method": "UNKNOWN"},
        "body_radius_m": cfg.body_radius_m if cfg else None,
        "grid_step_m": cfg.grid_step_m if cfg else None,
        "time_step_s": cfg.time_step_s if cfg else None,
        "nominal_speed_m_s": cfg.nominal_speed_m_s if cfg else None,
        "plausibility_weights": {
            "path_length_m": cfg.weight_length,
            "turn_rad": cfg.weight_turn,
            "speed_deviation_m_s": cfg.weight_speed,
        }
        if cfg
        else None,
        "lattice_metric_factor": cfg.lattice_metric_factor if cfg else None,
        "reach_slack_m": _r(cfg.reach_slack_m) if cfg else None,
        "region_mask_extra_erosion_m": _r(cfg.half_diagonal_m) if cfg else None,
    }
    limits: dict[str, Any] = {
        "max_blind_interval_s": cfg.max_blind_interval_s if cfg else None,
        "max_time_steps": cfg.max_time_steps if cfg else None,
        "max_grid_cells": cfg.max_grid_cells if cfg else None,
        "max_candidate_paths": cfg.max_candidate_paths if cfg else None,
        "min_separation_m": cfg.min_separation_m if cfg else None,
        "max_negative_evidence": cfg.max_negative_evidence if cfg else None,
        "max_region_samples": cfg.max_region_samples if cfg else None,
        "max_endpoint_substitution_s": cfg.max_endpoint_substitution_s if cfg else None,
        "hit": [],
    }
    return {
        "schema_version": RESPONSE_SCHEMA,
        "status": "UNKNOWN",
        "reason": None,
        "interval": {
            "start_s": start_s,
            "end_s": end_s,
            "duration_s": duration,
            "start_observation_ref": start.get("observation_ref"),
            "end_observation_ref": end.get("observation_ref"),
        },
        "endpoint_substitutions": [],
        "configuration": configuration,
        "hypotheses": [],
        "pruned_hypotheses": [],
        "reachable_regions": [],
        "rejected_counts": {"speed": 0, "walkable": 0, "unseen": 0, "diversity": 0},
        "negative_evidence_applied": [],
        "pruning_log": [],
        "limits": limits,
        "trace": [],
        "evidence_state": EVIDENCE_STATE,
        "ranking_basis": RANKING_BASIS,
        "physical_authority": "UNKNOWN",
        "identity_verdict": "UNCONFIRMED",
        "agent_used": False,
        "reconstruction_rng": "NOT_USED",
        "provenance": {
            "scene_id": request.get("scene_id"),
            "run_ref": source_binding.get("run_ref", "UNKNOWN"),
            "clock_id": source_binding.get("clock_id", "UNKNOWN"),
            "source_sha256": source_binding.get("source_sha256"),
            "safe_inputs_sha256": source_binding.get("safe_inputs_sha256"),
            "producer": PRODUCER,
            "producer_version": PRODUCER_VERSION,
            "config_sha256": config_sha256,
            "annotation_sha256": {
                "walkable": descriptor.sha256 if descriptor else None,
                "portals": descriptor.sha256 if descriptor else None,
            },
            "floor_map_kind": descriptor.kind if descriptor else "UNKNOWN",
            "gt_read": False,
        },
        "output_sha256": None,
    }


def _seal(response: dict[str, Any]) -> dict[str, Any]:
    body = {key: value for key, value in response.items() if key != "output_sha256"}
    response["output_sha256"] = canonical_sha256(body)
    return response


def verify_output_sha256(response: Mapping[str, Any]) -> bool:
    body = {key: value for key, value in response.items() if key != "output_sha256"}
    return response.get("output_sha256") == canonical_sha256(body)


# ------------------------------------------------------------------------ main


def generate_blind_hypotheses(
    request: Mapping[str, Any],
    *,
    config: Mapping[str, Any],
    config_sha256: str,
    floor_map: FloorMap | None,
    source_binding: Mapping[str, Any],
    visibility_index_ref: Mapping[str, Any] | None = None,
    previous_response: Mapping[str, Any] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Compute a ``workbench.blind-hypothesis.v1`` response; never raises on evidence.

    ``HypothesisRequestError`` is raised only for malformed requests (unknown or
    missing fields such as an attempt to pass GT). Evidence problems produce a
    sealed ``UNKNOWN`` response with ``hypotheses: []`` and the reason in ``trace``.
    ``should_stop`` is the caller's cooperative deadline (checked between stages).

    Pruning re-run (contract §6): a request with ``previous_response_sha256`` needs
    the ``previous_response`` object that hash identifies (the module looks nothing
    up). It is verified against the hash and the new evidence list must extend the
    old one (append-only); otherwise the answer is ``UNKNOWN``,
    ``NEGATIVE_EVIDENCE_NOT_APPEND_ONLY``. See :mod:`amidst.blind_hypothesis.pruning`.
    """

    if not isinstance(request, Mapping) or set(request) != _REQUEST_KEYS:
        raise HypothesisRequestError(f"request fields must be exactly {sorted(_REQUEST_KEYS)}")
    if request["schema_version"] != REQUEST_SCHEMA:
        raise HypothesisRequestError("unsupported request schema")
    top_k = request["top_k"]
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 5:
        raise HypothesisRequestError("top_k must be a strict integer 1-5")
    if previous_response is not None and request["previous_response_sha256"] is None:
        raise HypothesisRequestError("previous_response requires previous_response_sha256")

    scene_id = str(request["scene_id"])
    cfg: HypothesisConfig | None
    try:
        cfg = parse_config(config, scene_id=scene_id, config_sha256=config_sha256)
    except (KeyError, TypeError, ValueError, AttributeError):
        cfg = None
    response = _base_response(
        request, cfg, config, config_sha256, floor_map, source_binding, visibility_index_ref
    )
    trace: list[dict[str, Any]] = response["trace"]
    try:
        if cfg is None:
            raise _Unknown("SPEED_CONFIG_UNAVAILABLE")
        _run(request, cfg, floor_map, response, top_k, previous_response, should_stop)
        response["status"] = "READY"
    except _Unknown as unknown:
        response["status"] = "UNKNOWN"
        response["reason"] = unknown.reason
        response["hypotheses"] = []
        response["pruned_hypotheses"] = []
        response["reachable_regions"] = []
        trace.append({"step": "FAIL_CLOSED", "reason": unknown.reason, **unknown.detail})
    return _seal(response)


def _check_stop(should_stop: Callable[[], bool] | None, stage: str) -> None:
    if should_stop is not None and should_stop():
        raise _Unknown("SEARCH_BUDGET_EXHAUSTED", limit="DEADLINE", stage=stage)


def _run(
    request: Mapping[str, Any],
    cfg: HypothesisConfig,
    floor_map: FloorMap | None,
    response: dict[str, Any],
    top_k: int,
    previous_response: Mapping[str, Any] | None,
    should_stop: Callable[[], bool] | None,
) -> None:
    from amidst.blind_hypothesis import pruning  # imports this module; resolved lazily

    trace: list[dict[str, Any]] = response["trace"]
    rerun = request["previous_response_sha256"] is not None
    trace.append(pruning.request_fingerprint_step(request))
    if rerun:
        pruning.check_previous(request, previous_response, response)

    floor_z = floor_map.floor_z_m if floor_map is not None else None
    start, start_problem = _endpoint(request["start"], "start", floor_z, cfg)
    end, end_problem = _endpoint(request["end"], "end", floor_z, cfg)
    problems = [p for p in (start_problem, end_problem) if p is not None]
    trace.extend(problems)
    if any(p["problem"] == "FLOOR_Z_MISMATCH" for p in problems):
        raise _Unknown("PROVENANCE_MISMATCH")
    if start is None or end is None:
        raise _Unknown("ENDPOINT_UNUSABLE")
    if floor_map is None:
        raise _Unknown("WALKABLE_ANNOTATION_UNAVAILABLE")
    assert floor_z is not None
    for endpoint in (start, end):
        if endpoint.substitution is not None:
            # Copied unchanged for the UI (contract §3.1.1: display is mandatory).
            response["endpoint_substitutions"].append(dict(endpoint.substitution))
            trace.append(
                {
                    "step": "ENDPOINT_SUBSTITUTED",
                    "endpoint": endpoint.substitution["endpoint"],
                    "original_timestamp_s": endpoint.substitution["original_timestamp_s"],
                    "substitute_timestamp_s": endpoint.substitution["substitute_timestamp_s"],
                    "time_offset_s": endpoint.substitution["time_offset_s"],
                }
            )

    # Interval and clock grid.
    duration = end.timestamp_s - start.timestamp_s
    steps = round(duration / cfg.time_step_s)
    if duration <= 0 or abs(steps * cfg.time_step_s - duration) > CLOCK_TOLERANCE_S or steps < 2:
        raise _Unknown("INTERVAL_INVALID", duration_s=_r(duration))
    if duration > cfg.max_blind_interval_s + CLOCK_TOLERANCE_S or steps - 1 > cfg.max_time_steps:
        raise _Unknown("INTERVAL_TOO_LONG", duration_s=_r(duration))
    times = [_r(start.timestamp_s + i * cfg.time_step_s) for i in range(1, steps)]

    evidence = _negative_evidence(request["negative_evidence"], times, cfg)
    response["negative_evidence_applied"] = [e.ref for e in evidence]
    trace.append(pruning.evidence_fingerprint_step(request["negative_evidence"]))

    # Endpoint support and the straight-line speed bound, before any lattice work.
    # An endpoint region must itself intersect the map (regions, UNKNOWN regions and
    # portals); it is never moved or extended to the nearest walkable point (D11).
    unknown_map = getattr(floor_map, "unknown_regions", {}) or {}
    walk_union = unary_union(
        [*floor_map.regions.values(), *unknown_map.values(), *floor_map.portals.values()]
    )
    supports: dict[str, BaseGeometry] = {}
    for label, endpoint in (("start", start), ("end", end)):
        support = endpoint.region.intersection(walk_union)
        if support.is_empty:
            raise _Unknown(
                "ENDPOINT_OUTSIDE_WALKABLE",
                endpoint=label,
                distance_to_walkable_m=_r(endpoint.region.distance(walk_union)),
            )
        supports[label] = support
    gap_m = start.region.distance(end.region)
    if gap_m > cfg.speed_max_m_s * duration + _EPS:
        raise _Unknown("ENDPOINTS_UNREACHABLE", straight_line_m=_r(gap_m))

    _check_stop(should_stop, "LATTICE")
    lattice = _Lattice(floor_map, cfg, start, end, duration, walk_union)
    trace.append(
        {"step": "LATTICE_BUILT", "cells": len(lattice), "map_kind": floor_map.descriptor.kind}
    )

    # Endpoint regions on the lattice: visible seeds only (contract §4.1).
    seeds_s, anchors_s = lattice.visible_seeds(supports["start"])
    seeds_e, anchors_e = lattice.visible_seeds(supports["end"])
    for label, seeds in (("start", seeds_s), ("end", seeds_e)):
        finite_seeds = seeds[np.isfinite(seeds)]
        trace.append(
            {
                "step": "ENDPOINT_CELLS",
                "endpoint": label,
                "seed_cells": int(finite_seeds.size),
                "min_cell_offset_m": _r(finite_seeds.min()) if finite_seeds.size else None,
            }
        )
        if not finite_seeds.size:
            raise _Unknown("ENDPOINT_OUTSIDE_WALKABLE", endpoint=label, problem="NO_VISIBLE_CELL")

    # Geodesic reach (contract §4.4) on a 16-neighbour lattice (primitive moves
    # up to two cells, metric error below 3 %; lattice_metric_factor covers it).
    _check_stop(should_stop, "GEODESIC")
    moves = [
        (dx, dy, d)
        for dx, dy, d in lattice.offsets(lattice.g * math.sqrt(5.0))
        if math.gcd(dx, dy) == 1
    ]
    adjacency = [lattice.neighbours(k, moves) for k in range(len(lattice))]
    geo_s, pred_s = _geodesic(lattice, seeds_s, adjacency)
    geo_e, pred_e = _geodesic(lattice, seeds_e, adjacency)

    # Unseen masks (contract §4.3). Region mask: a cell is excluded at t_i only when
    # its whole square lies inside a visible footprint (``eroded_region``). Route
    # mask: the cell centre's body disc lies inside (``eroded_visible``), used only
    # to steer route trees away from floor that is visible at every step.
    unseen_masks = []
    route_masks = []
    for i in range(len(times)):
        unseen = np.ones(len(lattice), dtype=bool)
        route_unseen = np.ones(len(lattice), dtype=bool)
        for item in evidence:
            if i not in item.step_indices:
                continue
            if item.eroded_region is not None:
                unseen &= ~shapely.intersects_xy(item.eroded_region, lattice.xs, lattice.ys)
            if item.eroded_visible is not None:
                route_unseen &= ~shapely.intersects_xy(item.eroded_visible, lattice.xs, lattice.ys)
        unseen_masks.append(unseen)
        route_masks.append(route_unseen)

    vmax = cfg.speed_max_m_s
    factor = cfg.lattice_metric_factor
    slack = cfg.reach_slack_m
    regions: list[np.ndarray] = []
    reaches: list[np.ndarray] = []
    reach_only_empty = False
    removed_by_unseen = 0
    for i, t in enumerate(times):
        forward = geo_s <= vmax * (t - start.timestamp_s) * factor + slack + _EPS
        backward = geo_e <= vmax * (end.timestamp_s - t) * factor + slack + _EPS
        reach = forward & backward
        reach_only_empty = reach_only_empty or not reach.any()
        reaches.append(reach)
        removed_by_unseen += int((reach & ~unseen_masks[i]).sum())
        regions.append(reach & unseen_masks[i])
    trace.append(
        {
            "step": "UNSEEN_MASK_APPLIED",
            "evidence_entries": len(evidence),
            "cells_removed": removed_by_unseen,
        }
    )
    if not all(region.any() for region in regions):
        empty = [times[i] for i, region in enumerate(regions) if not region.any()]
        # Empty by speed alone (no unseen mask applied) means unreachable even
        # without negative evidence; otherwise the evidence emptied the region.
        if reach_only_empty:
            raise _Unknown("ENDPOINTS_UNREACHABLE", empty_at_s=empty[:10])
        raise _Unknown(
            "REACHABLE_SET_EMPTY",
            empty_at_s=empty[:10],
            first_emptying_negative_evidence_ref=_first_emptying_entry(evidence, reaches, lattice),
        )
    response["reachable_regions"] = [
        _region_record(lattice, times[i], region, cfg, response["limits"]["hit"])
        for i, region in enumerate(regions)
    ]

    # Representative routes (contract §4.5-4.7): via-cell routes on the geodesic
    # trees, string-pulled, then sampled at constant speed along the route.
    _check_stop(should_stop, "ROUTES")
    in_any_region = np.zeros(len(lattice), dtype=bool)
    for region in regions:
        in_any_region |= region
    # Floor visible at every gap step cannot host the target at any sample time;
    # route trees avoid it (regions above keep the contract's unmasked reach).
    always_visible = np.zeros(len(lattice), dtype=bool)
    if evidence:
        always_visible = ~np.logical_or.reduce(route_masks)
    if always_visible.any():
        route_adjacency = [
            [] if always_visible[k] else [(o, d) for o, d in adjacency[k] if not always_visible[o]]
            for k in range(len(lattice))
        ]
        geo_s, pred_s = _geodesic(
            lattice, np.where(always_visible, math.inf, seeds_s), route_adjacency
        )
        geo_e, pred_e = _geodesic(
            lattice, np.where(always_visible, math.inf, seeds_e), route_adjacency
        )
    pool, separation_excluded, anchor_rejected = _route_pool(
        lattice,
        cfg,
        start,
        end,
        evidence,
        times,
        floor_z,
        geo_s,
        geo_e,
        pred_s,
        pred_e,
        anchors_s,
        anchors_e,
        supports["start"],
        supports["end"],
        in_any_region,
        response["limits"]["hit"],
        should_stop,
    )
    trace.append(
        {
            "step": "ROUTE_POOL_BUILT",
            "candidates": len(pool),
            "via_cells_excluded_by_separation": separation_excluded,
            "anchor_segment_rejected": anchor_rejected,
        }
    )

    _check_stop(should_stop, "SELECT")
    rejected = {"speed": 0, "walkable": 0, "unseen": 0, "diversity": 0}
    passing = []
    for candidate in pool:
        failed = [name for name, check in candidate["checks"].items() if check["result"] == "FAIL"]
        for name in failed:
            rejected[name] += 1
        if not failed:
            passing.append(candidate)
    passing.sort(key=lambda h: (-h["plausibility"]["score"], h["hypothesis_ref"]))
    selected: list[dict[str, Any]] = []
    for candidate in passing:
        if len(selected) >= top_k:
            break
        if any(
            _max_separation(candidate, other) < cfg.min_separation_m - _EPS for other in selected
        ):
            rejected["diversity"] += 1
            continue
        selected.append(candidate)
    response["rejected_counts"] = rejected
    trace.append({"step": "REPRESENTATIVES_SELECTED", "k": len(selected), "passing": len(passing)})
    if not selected:
        raise _Unknown("NO_HYPOTHESIS_PASSED_CHECKS")
    for rank, hypothesis in enumerate(selected, start=1):
        hypothesis["rank"] = rank
        _label_walkable_links(hypothesis, lattice, start, end)
    response["hypotheses"] = selected
    trace.append(_sample_region_consistency(lattice, regions, selected, cfg.grid_step_m))
    if rerun:
        assert previous_response is not None
        previous_applied = len(previous_response["negative_evidence_applied"])
        pruning.apply_pruning(
            previous_response,
            response,
            request["negative_evidence"],
            evidence,
            times,
            _region_areas_by_entry(evidence, reaches, lattice, cfg, previous_applied),
            previous_applied,
            _unseen_check,
        )


def _unseen_masks_for(
    evidence: Sequence[_Evidence], step: int, lattice: _Lattice
) -> list[np.ndarray | None]:
    """Per entry, the cells kept at clock step ``step`` (None: entry does not act there).

    An entry that acts there without pruning anything keeps every cell (all True), so
    area bookkeeping still counts the step.
    """

    masks: list[np.ndarray | None] = []
    for item in evidence:
        if step not in item.step_indices:
            masks.append(None)
        elif item.eroded_region is None:
            # Acts at this step but prunes nothing (no footprint, or eroded away).
            masks.append(np.ones(len(lattice), dtype=bool))
        else:
            masks.append(~shapely.intersects_xy(item.eroded_region, lattice.xs, lattice.ys))
    return masks


def _first_emptying_entry(
    evidence: Sequence[_Evidence], reaches: Sequence[np.ndarray], lattice: _Lattice
) -> str | None:
    """Ref of the first entry (in application order) whose prefix empties a region."""

    if not evidence:
        return None
    running = [reach.copy() for reach in reaches]
    for step in range(len(reaches)):
        for j, mask in enumerate(_unseen_masks_for(evidence, step, lattice)):
            if mask is None:
                continue
            running[step] &= mask
            if not running[step].any():
                return evidence[j].ref
    return None


def _region_areas_by_entry(
    evidence: Sequence[_Evidence],
    reaches: Sequence[np.ndarray],
    lattice: _Lattice,
    cfg: HypothesisConfig,
    first_new: int,
) -> list[tuple[float, float]]:
    """``(before, after)`` mean region area (m²) per entry ``first_new..`` (contract §6).

    Entry ``j`` acts only on its own clock steps; its area is the mean over them of
    the cell count times the cell area, with entries ``< j`` (resp. ``<= j``)
    applied. An entry that covers no step reports ``(0.0, 0.0)``.
    """

    running = [reach.copy() for reach in reaches]
    cell_area = cfg.grid_step_m**2
    before = [0.0] * len(evidence)
    after = [0.0] * len(evidence)
    for step in range(len(reaches)):
        for j, mask in enumerate(_unseen_masks_for(evidence, step, lattice)):
            if mask is None:
                continue
            before[j] += float(running[step].sum()) * cell_area
            running[step] &= mask
            after[j] += float(running[step].sum()) * cell_area
    result = []
    for j in range(first_new, len(evidence)):
        steps = max(len(evidence[j].step_indices), 1)
        result.append((_r(before[j] / steps), _r(after[j] / steps)))
    return result


def _max_separation(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    return max(
        math.dist(sa["position_m"], sb["position_m"])
        for sa, sb in zip(a["samples"], b["samples"], strict=True)
    )


def _label_walkable_links(
    hypothesis: dict[str, Any], lattice: _Lattice, start: _Endpoint, end: _Endpoint
) -> None:
    """Label every link (endpoint to first sample ... last sample to endpoint), D11.

    A link is ``UNKNOWN`` if a positive-length part of it lies in a ``walkable:
    UNKNOWN`` region and not in a confirmed region or portal. ``result`` is then
    ``UNKNOWN`` unless a sample already left the map (``FAIL``).
    """

    check = hypothesis["checks"]["walkable"]
    route = hypothesis["route_m"]
    chain = [
        (start.timestamp_s, (route[0][0], route[0][1])),
        *(
            (s["timestamp_s"], (s["position_m"][0], s["position_m"][1]))
            for s in hypothesis["samples"]
        ),
        (end.timestamp_s, (route[-1][0], route[-1][1])),
    ]
    segments = []
    for (t0, p0), (t1, p1) in zip(chain, chain[1:], strict=False):
        link: BaseGeometry = Point(p0) if math.dist(p0, p1) <= _EPS else LineString([p0, p1])

        def share(area: BaseGeometry, link: BaseGeometry = link) -> bool:
            inter = area.intersection(link)
            return not inter.is_empty and (inter.length > _EPS or isinstance(link, Point))

        refs = [name for name in lattice.region_ids if share(lattice.regions[name])]
        unconfirmed = lattice.unknown_union is not None and share(
            lattice.unknown_union.difference(lattice.confirmed_union)
        )
        segments.append(
            {
                "from_timestamp_s": t0,
                "to_timestamp_s": t1,
                "walkable": "UNKNOWN" if unconfirmed else "TRUE",
                "area_refs": refs,
                "tiers": sorted({lattice.tier_of[name] for name in refs}),
            }
        )
    crossed = any(item["walkable"] == "UNKNOWN" for item in segments)
    check["segments"] = segments
    check["unconfirmed_area_crossed"] = crossed
    if check["result"] == "PASS" and crossed:
        check["result"] = "UNKNOWN"


def _sample_region_consistency(
    lattice: _Lattice,
    regions: Sequence[np.ndarray],
    selected: Sequence[Mapping[str, Any]],
    grid_step_m: float,
) -> dict[str, Any]:
    """Trace entry: representative samples whose grid-cell square is not in R(t_i).

    A sample may lie in the square of any cell whose centre is within half a step
    on both axes. Samples whose squares have no centre on the map (a strip along a
    wall narrower than half a step) are counted as ``wall_strip_exempt``. Diagnostic
    only: the checks recomputed on the samples stay authoritative.
    """

    outside = exempt = total = 0
    for hypothesis in selected:
        for i, sample in enumerate(hypothesis["samples"]):
            total += 1
            fx, fy = sample["position_m"][0] / grid_step_m, sample["position_m"][1] / grid_step_m
            in_region = on_map = False
            for a in range(math.ceil(fx - 0.5 - 1e-6), math.floor(fx + 0.5 + 1e-6) + 1):
                for b in range(math.ceil(fy - 0.5 - 1e-6), math.floor(fy + 0.5 + 1e-6) + 1):
                    k = lattice.index.get((a, b))
                    if k is not None and regions[i][k]:
                        in_region = True
                    on_map = on_map or lattice.map_regions_prepared.covers(
                        Point(a * grid_step_m, b * grid_step_m)
                    )
            if in_region:
                continue
            if on_map:
                outside += 1
            else:
                exempt += 1
    return {
        "step": "SAMPLE_REGION_CONSISTENCY",
        "samples_checked": total,
        "samples_outside_region_cell": outside,
        "wall_strip_exempt": exempt,
    }


def _region_record(
    lattice: _Lattice, t: float, mask: np.ndarray, cfg: HypothesisConfig, hit: list[str]
) -> dict[str, Any]:
    indices = np.flatnonzero(mask)
    points = [(float(lattice.xs[k]), float(lattice.ys[k])) for k in indices]
    extent = 0.0
    if len(points) > 1:
        hull = MultiPoint(points).convex_hull
        coords = list(hull.exterior.coords) if isinstance(hull, Polygon) else list(hull.coords)
        extent = max(math.dist(a, b) for a in coords for b in coords)
    truncated = len(points) > cfg.max_region_samples
    if truncated and "MAX_REGION_SAMPLES" not in hit:
        hit.append("MAX_REGION_SAMPLES")
    # Over the cap, keep evenly spaced cells (cells are in x-major order, so a
    # prefix would cut away the whole western side of the band).
    kept = (
        list(range(len(points)))
        if not truncated
        else [
            (2 * n + 1) * len(points) // (2 * cfg.max_region_samples)
            for n in range(cfg.max_region_samples)
        ]
    )
    return {
        "timestamp_s": t,
        "kind": "SAMPLE_SET",
        "polygons": None,
        "samples": [[_r(points[n][0]), _r(points[n][1])] for n in kept],
        "cell_size_m": cfg.grid_step_m,
        "walkable_unknown_sample_indices": [
            slot for slot, n in enumerate(kept) if lattice.unknown_cell[indices[n]]
        ],
        "area_m2": _r(len(points) * cfg.grid_step_m**2),
        "max_extent_m": _r(extent),
        "evidence_state": EVIDENCE_STATE,
        "truncated": truncated,
    }


def _turn(points: Sequence[tuple[float, float]]) -> float:
    headings = []
    for a, b in zip(points, points[1:], strict=False):
        if math.dist(a, b) > _EPS:
            headings.append(math.atan2(b[1] - a[1], b[0] - a[0]))
    total = 0.0
    for h0, h1 in zip(headings, headings[1:], strict=False):
        delta = abs(h1 - h0) % (2 * math.pi)
        total += min(delta, 2 * math.pi - delta)
    return total


def _cell_chain(start_cell: int, predecessor: np.ndarray) -> list[int]:
    chain = [start_cell]
    while predecessor[chain[-1]] >= 0:
        chain.append(int(predecessor[chain[-1]]))
    return chain


def _string_pull(
    lattice: _Lattice,
    cells: Sequence[int],
    start_anchor: tuple[float, float],
    end_anchor: tuple[float, float],
) -> list[tuple[float, float]]:
    """Shortcut lattice zigzags inside one region; portal crossings stay lattice edges."""

    points = [start_anchor, *(lattice.xy(k) for k in cells), end_anchor]
    labels = [
        lattice.region_of[cells[0]],
        *(lattice.region_of[k] for k in cells),
        lattice.region_of[cells[-1]],
    ]
    last = len(points) - 1
    pulled = [points[0]]
    i = 0
    while i < last:
        j = min(last, i + 64)
        while j > i + 1:
            if len(set(labels[i : j + 1])) == 1 and lattice.prepared[labels[i]].covers(
                LineString([points[i], points[j]])
            ):
                break
            j -= 1
        pulled.append(points[j])
        i = j
    deduped = [pulled[0]]
    for point in pulled[1:]:
        if math.dist(point, deduped[-1]) > _EPS:
            deduped.append(point)
    return deduped


def _settle_anchors(
    lattice: _Lattice,
    polyline: Sequence[tuple[float, float]],
    support_s: BaseGeometry,
    support_e: BaseGeometry,
) -> list[tuple[float, float]]:
    """Move each anchor to the nearest point of its endpoint support to the next vertex.

    Seeds give every via cell its own anchor, so routes that string-pull to the same
    line would otherwise differ by anchor jitter and flood the pool with near-copies.
    An anchor only moves within its (map-clipped) endpoint region and only if the new
    first/last link stays on the map, so the route still starts inside the endpoint.
    """

    points = list(polyline)
    if len(points) < 2:
        return points
    for _ in range(3):
        moved = False
        for index, neighbour, support in ((0, 1, support_s), (-1, -2, support_e)):
            target = points[neighbour]
            near = nearest_points(support, Point(target))[0]
            candidate = (float(near.x), float(near.y))
            if math.dist(candidate, points[index]) <= _EPS or math.dist(candidate, target) <= _EPS:
                continue
            if lattice.walk_tolerant.covers(LineString([candidate, target])):
                points[index] = candidate
                moved = True
        if not moved:
            break
    return points


def _sample_route(
    polyline: Sequence[tuple[float, float]], fractions: Sequence[float]
) -> tuple[list[tuple[float, float]], float]:
    """Constant-speed positions along the polyline at the given arc fractions."""

    lengths = [math.dist(a, b) for a, b in zip(polyline, polyline[1:], strict=False)]
    total = sum(lengths)
    if total <= _EPS:
        return [polyline[0] for _ in fractions], 0.0
    positions = []
    segment, walked = 0, 0.0
    for fraction in fractions:
        target = fraction * total
        while segment < len(lengths) - 1 and walked + lengths[segment] < target - _EPS:
            walked += lengths[segment]
            segment += 1
        a, b = polyline[segment], polyline[segment + 1]
        share = (
            0.0
            if lengths[segment] <= _EPS
            else min(1.0, max(0.0, (target - walked) / lengths[segment]))
        )
        positions.append((a[0] + share * (b[0] - a[0]), a[1] + share * (b[1] - a[1])))
    return positions, total


def _route_pool(
    lattice: _Lattice,
    cfg: HypothesisConfig,
    start: _Endpoint,
    end: _Endpoint,
    evidence: Sequence[_Evidence],
    times: Sequence[float],
    floor_z: float,
    geo_s: np.ndarray,
    geo_e: np.ndarray,
    pred_s: np.ndarray,
    pred_e: np.ndarray,
    anchors_s: np.ndarray,
    anchors_e: np.ndarray,
    support_s: BaseGeometry,
    support_e: BaseGeometry,
    in_any_region: np.ndarray,
    hit: list[str],
    should_stop: Callable[[], bool] | None,
) -> tuple[list[dict[str, Any]], int, int]:
    """Bounded, deterministic candidate pool; returns (pool, excluded, anchor_rejected).

    Via cells are visited by lattice route length (ties by cell index). A via cell
    closer than ``min_separation_m`` to a route that **passed** speed, walkable and
    unseen is skipped, so the pool spreads over alternatives instead of near-copies
    of the best route. A failing candidate only excludes via cells within one grid
    step, so a failed shortest route does not hide nearby routes that would pass.
    The anchor (nearest endpoint point to the first / last cell) must see that cell
    along the walkable map; a candidate whose anchor segment does not is skipped.
    """

    finite = np.isfinite(geo_s) & np.isfinite(geo_e) & in_any_region
    order = sorted(
        (int(k) for k in np.flatnonzero(finite)),
        key=lambda k: (float(geo_s[k] + geo_e[k]), lattice.ij[k]),
    )
    duration = end.timestamp_s - start.timestamp_s
    fractions = [(t - start.timestamp_s) / duration for t in times]
    pool: list[dict[str, Any]] = []
    seen: set[tuple[tuple[float, float], ...]] = set()
    near: BaseGeometry | None = None
    failed_near: BaseGeometry | None = None
    excluded = 0
    anchor_rejected = 0
    for via in order:
        if len(pool) >= cfg.max_candidate_paths:
            hit.append("MAX_CANDIDATE_PATHS")
            break
        if len(pool) % 32 == 0:
            _check_stop(should_stop, "ROUTES")
        x, y = lattice.xy(via)
        if (near is not None and shapely.intersects_xy(near, x, y)) or (
            failed_near is not None and shapely.intersects_xy(failed_near, x, y)
        ):
            excluded += 1
            continue
        cells = list(reversed(_cell_chain(via, pred_s)))[:-1] + _cell_chain(via, pred_e)
        anchor_s = (float(anchors_s[cells[0], 0]), float(anchors_s[cells[0], 1]))
        anchor_e = (float(anchors_e[cells[-1], 0]), float(anchors_e[cells[-1], 1]))
        if not (
            lattice.walk_tolerant.covers(LineString([anchor_s, lattice.xy(cells[0])]))
            and lattice.walk_tolerant.covers(LineString([lattice.xy(cells[-1]), anchor_e]))
        ):
            anchor_rejected += 1
            continue
        polyline = _settle_anchors(
            lattice, _string_pull(lattice, cells, anchor_s, anchor_e), support_s, support_e
        )
        key = tuple((_r(px), _r(py)) for px, py in polyline)
        if key in seen:
            continue
        seen.add(key)
        positions, length = _sample_route(polyline, fractions)
        pool.append(
            _hypothesis(
                cells, polyline, positions, length, lattice, cfg, evidence, times, duration, floor_z
            )
        )
        passed = all(check["result"] != "FAIL" for check in pool[-1]["checks"].values())
        radius = cfg.min_separation_m if passed else cfg.grid_step_m
        route_zone = (
            LineString(polyline).buffer(radius)
            if len(polyline) > 1
            else Point(polyline[0]).buffer(radius)
        )
        if passed:
            near = route_zone if near is None else near.union(route_zone)
        else:
            failed_near = route_zone if failed_near is None else failed_near.union(route_zone)
    return pool, excluded, anchor_rejected


def _unseen_check(
    evidence: Sequence[_Evidence], positions: Sequence[Sequence[float]], times: Sequence[float]
) -> dict[str, Any]:
    """Contract §5.1 ``checks.unseen`` for samples ``positions`` (x, y first) at ``times``."""

    conflicts = []
    covered = [False] * len(times)
    for item in evidence:
        for i in item.step_indices:
            covered[i] = True
            if item.eroded_visible is not None and item.eroded_visible.intersects(
                Point(positions[i][0], positions[i][1])
            ):
                conflicts.append(
                    {
                        "timestamp_s": times[i],
                        "camera_id": item.camera_id,
                        "negative_evidence_ref": item.ref,
                    }
                )
    conflicts.sort(key=lambda c: (c["timestamp_s"], c["camera_id"], c["negative_evidence_ref"]))
    if conflicts:
        result = "FAIL"
    elif all(covered):
        result = "PASS"
    else:
        result = "UNKNOWN"
    return {
        "result": result,
        "conflicts": conflicts,
        "steps_without_negative_evidence": covered.count(False),
    }


def _hypothesis(
    cells: Sequence[int],
    polyline: Sequence[tuple[float, float]],
    positions: Sequence[tuple[float, float]],
    path_length: float,
    lattice: _Lattice,
    cfg: HypothesisConfig,
    evidence: Sequence[_Evidence],
    times: Sequence[float],
    duration: float,
    floor_z: float,
) -> dict[str, Any]:
    dt = cfg.time_step_s
    mean_speed = path_length / duration
    chord_points = [polyline[0], *positions, polyline[-1]]
    max_step = max(
        math.dist(a, b) / dt for a, b in zip(chord_points, chord_points[1:], strict=False)
    )
    deviation = abs(mean_speed - cfg.nominal_speed_m_s)  # constant speed along the route
    turn = _turn(polyline)
    cost = cfg.weight_length * path_length + cfg.weight_turn * turn + cfg.weight_speed * deviation

    # Constant speed: every step moves at mean_speed along the route, so the
    # route speed bounds every chord speed (max_step <= mean_speed).
    speed_pass = (
        mean_speed <= cfg.speed_max_m_s + _EPS
        and max_step <= cfg.speed_max_m_s + _EPS
        and mean_speed >= cfg.speed_min_m_s - _EPS
    )
    violations = [
        {"timestamp_s": t, "position_m": _xyz(x, y, floor_z)}
        for t, (x, y) in zip(times, positions, strict=True)
        if not lattice.walk_prepared.covers(Point(x, y))
    ]
    unseen = _unseen_check(evidence, positions, times)

    # Portals crossed, in order: along lattice links between cells of different
    # regions, and along the anchor-to-cell links (seeds are visible through a
    # doorway, so the first or last link may itself cross a portal).
    nodes = [
        (polyline[0], lattice.region_at(*polyline[0])),
        *((lattice.xy(k), lattice.region_of[k]) for k in cells),
        (polyline[-1], lattice.region_at(*polyline[-1])),
    ]
    portals: list[str] = []
    for index, ((p0, label0), (p1, label1)) in enumerate(zip(nodes, nodes[1:], strict=False)):
        if label0 == label1 or label0 is None or label1 is None:
            continue
        step = LineString([p0, p1])
        crossed = None
        if 1 <= index <= len(cells) - 1:
            crossed = lattice.edge(cells[index - 1], cells[index])[1]
        if crossed is None:
            crossed = next(
                (name for name in lattice.portal_ids if lattice.portals[name].intersects(step)),
                None,
            )
        if crossed is not None and (not portals or portals[-1] != crossed):
            portals.append(crossed)

    samples = [
        {"timestamp_s": t, "position_m": _xyz(x, y, floor_z), "evidence_state": EVIDENCE_STATE}
        for t, (x, y) in zip(times, positions, strict=True)
    ]
    ref = (
        "hyp:"
        + canonical_sha256(
            {
                "samples": [[s["timestamp_s"], *s["position_m"]] for s in samples],
                "config_sha256": cfg.config_sha256,
            }
        )[:24]
    )
    return {
        "hypothesis_ref": ref,
        "rank": None,
        "status": "ACTIVE",
        "pruned_by": None,
        "plausibility": {
            "score": _r(-cost),
            "basis": RANKING_BASIS,
            "components": {
                "path_length_m": _r(path_length),
                "turn_rad": _r(turn),
                "speed_deviation_m_s": _r(deviation),
            },
        },
        "samples": samples,
        "route_m": [_xyz(x, y, floor_z) for x, y in polyline],
        "portal_sequence": portals,
        "checks": {
            "speed": {
                "result": "PASS" if speed_pass else "FAIL",
                "max_step_speed_m_s": _r(max_step),
                "mean_speed_m_s": _r(mean_speed),
                "limit_m_s": [cfg.speed_min_m_s, cfg.speed_max_m_s],
            },
            "walkable": {
                "result": "FAIL" if violations else "PASS",
                "walkable_ref": lattice.walkable_ref,
                "violations": violations,
                # Filled for the selected representatives by _label_walkable_links.
                "unconfirmed_area_crossed": False,
                "segments": [],
            },
            "unseen": unseen,
        },
        "physical_authority": "UNKNOWN",
    }
