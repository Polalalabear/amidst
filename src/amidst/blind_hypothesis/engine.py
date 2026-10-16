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

from amidst.blind_hypothesis.floor_map import FloorMap

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
    )
    positive = (
        parsed.grid_step_m,
        parsed.time_step_s,
        parsed.lattice_metric_factor,
        parsed.max_blind_interval_s,
        parsed.min_separation_m,
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


def _endpoint(
    raw: Any, label: str, floor_z_m: float | None
) -> tuple[_Endpoint | None, dict[str, Any] | None]:
    """Validate one endpoint; return (endpoint, None) or (None, trace problem)."""

    def problem(code: str) -> tuple[None, dict[str, Any]]:
        return None, {"step": "ENDPOINT_REJECTED", "endpoint": label, "problem": code}

    if not isinstance(raw, Mapping) or set(raw) != _ENDPOINT_KEYS:
        raise HypothesisRequestError(f"{label}: endpoint fields must be exactly {_ENDPOINT_KEYS}")
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
    return (
        _Endpoint(
            observation_ref=str(raw["observation_ref"]),
            camera_id=str(raw["camera_id"]),
            timestamp_s=timestamp,
            kind=str(kind),
            region=region,
            anchor=anchor,
        ),
        None,
    )


@dataclass(frozen=True)
class _Evidence:
    ref: str
    camera_id: str
    step_indices: tuple[int, ...]
    eroded_visible: BaseGeometry | None  # None: camera sees no floor there


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
        if polygons:
            shrunk = unary_union(polygons).buffer(-cfg.body_radius_m)
            eroded = None if shrunk.is_empty else shrunk
        parsed.append(_Evidence(ref, str(entry["camera_id"]), tuple(sorted(indices)), eroded))
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
    ) -> None:
        g = cfg.grid_step_m
        self.g = g
        self.walkable_ref = floor_map.descriptor.walkable_ref
        self.region_ids = sorted(floor_map.regions)
        self.regions = {name: floor_map.regions[name] for name in self.region_ids}
        self.prepared: dict[str, PreparedGeometry] = {
            name: prep(geom) for name, geom in self.regions.items()
        }
        self.portal_ids = sorted(floor_map.portals)
        self.portals = {name: floor_map.portals[name] for name in self.portal_ids}
        # Sample-level walkable check: walkable polygons plus portal footprints
        # (a doorway is passable even where no threshold surface is annotated).
        self.walk_union = unary_union([*self.regions.values(), *self.portals.values()])
        self.walk_prepared = prep(self.walk_union)
        self.snap_m = g * math.sqrt(2.0) / 2.0

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

    def distances_to(self, geometry: BaseGeometry) -> np.ndarray:
        return np.asarray(shapely.distance(geometry, shapely.points(self.xs, self.ys)), dtype=float)


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
    }
    limits: dict[str, Any] = {
        "max_blind_interval_s": cfg.max_blind_interval_s if cfg else None,
        "max_time_steps": cfg.max_time_steps if cfg else None,
        "max_grid_cells": cfg.max_grid_cells if cfg else None,
        "max_candidate_paths": cfg.max_candidate_paths if cfg else None,
        "min_separation_m": cfg.min_separation_m if cfg else None,
        "max_negative_evidence": cfg.max_negative_evidence if cfg else None,
        "max_region_samples": cfg.max_region_samples if cfg else None,
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
    should_stop: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Compute a ``workbench.blind-hypothesis.v1`` response; never raises on evidence.

    ``HypothesisRequestError`` is raised only for malformed requests (unknown or
    missing fields such as an attempt to pass GT). Evidence problems produce a
    sealed ``UNKNOWN`` response with ``hypotheses: []`` and the reason in ``trace``.
    ``should_stop`` is the caller's cooperative deadline (checked between stages).
    """

    if not isinstance(request, Mapping) or set(request) != _REQUEST_KEYS:
        raise HypothesisRequestError(f"request fields must be exactly {sorted(_REQUEST_KEYS)}")
    if request["schema_version"] != REQUEST_SCHEMA:
        raise HypothesisRequestError("unsupported request schema")
    top_k = request["top_k"]
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 5:
        raise HypothesisRequestError("top_k must be a strict integer 1-5")

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
        _run(request, cfg, floor_map, response, top_k, should_stop)
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
    should_stop: Callable[[], bool] | None,
) -> None:
    trace: list[dict[str, Any]] = response["trace"]
    if request["previous_response_sha256"] is not None:
        # Contract §6 re-run pruning belongs to K5; fail closed instead of ignoring it.
        raise _Unknown("PRUNING_RERUN_NOT_IMPLEMENTED")

    floor_z = floor_map.floor_z_m if floor_map is not None else None
    start, start_problem = _endpoint(request["start"], "start", floor_z)
    end, end_problem = _endpoint(request["end"], "end", floor_z)
    problems = [p for p in (start_problem, end_problem) if p is not None]
    trace.extend(problems)
    if any(p["problem"] == "FLOOR_Z_MISMATCH" for p in problems):
        raise _Unknown("PROVENANCE_MISMATCH")
    if start is None or end is None:
        raise _Unknown("ENDPOINT_UNUSABLE")
    if floor_map is None:
        raise _Unknown("WALKABLE_ANNOTATION_UNAVAILABLE")
    assert floor_z is not None

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

    # Endpoint support and the straight-line speed bound, before any lattice work.
    walk_union = unary_union(list(floor_map.regions.values()))
    snap_m = cfg.grid_step_m * math.sqrt(2.0) / 2.0
    for label, endpoint in (("start", start), ("end", end)):
        if endpoint.region.distance(walk_union) > snap_m + _EPS:
            raise _Unknown(
                "ENDPOINT_OUTSIDE_WALKABLE",
                endpoint=label,
                distance_to_walkable_m=_r(endpoint.region.distance(walk_union)),
            )
    gap_m = start.region.distance(end.region)
    if gap_m > cfg.speed_max_m_s * duration + _EPS:
        raise _Unknown("ENDPOINTS_UNREACHABLE", straight_line_m=_r(gap_m))

    _check_stop(should_stop, "LATTICE")
    lattice = _Lattice(floor_map, cfg, start, end, duration)
    trace.append(
        {"step": "LATTICE_BUILT", "cells": len(lattice), "map_kind": floor_map.descriptor.kind}
    )

    # Endpoint regions on the lattice.
    d_start = lattice.distances_to(start.region)
    d_end = lattice.distances_to(end.region)
    for label, distances in (("start", d_start), ("end", d_end)):
        if not np.any(distances <= lattice.snap_m + _EPS):
            raise _Unknown("ENDPOINT_OUTSIDE_WALKABLE", endpoint=label)

    # Geodesic reach (contract §4.4) on a 16-neighbour lattice (primitive moves
    # up to two cells, metric error below 3 %; lattice_metric_factor covers it).
    _check_stop(should_stop, "GEODESIC")
    moves = [
        (dx, dy, d)
        for dx, dy, d in lattice.offsets(lattice.g * math.sqrt(5.0))
        if math.gcd(dx, dy) == 1
    ]
    adjacency = [lattice.neighbours(k, moves) for k in range(len(lattice))]
    seeds_s = np.where(d_start <= lattice.snap_m + _EPS, d_start, math.inf)
    seeds_e = np.where(d_end <= lattice.snap_m + _EPS, d_end, math.inf)
    geo_s, pred_s = _geodesic(lattice, seeds_s, adjacency)
    geo_e, pred_e = _geodesic(lattice, seeds_e, adjacency)

    # Unseen mask (contract §4.3): a cell is excluded at t_i when its body disc
    # lies fully (closed set) inside a visible footprint at t_i.
    unseen_masks = []
    for i in range(len(times)):
        unseen = np.ones(len(lattice), dtype=bool)
        for item in evidence:
            if i in item.step_indices and item.eroded_visible is not None:
                unseen &= ~shapely.intersects_xy(item.eroded_visible, lattice.xs, lattice.ys)
        unseen_masks.append(unseen)

    vmax = cfg.speed_max_m_s
    factor = cfg.lattice_metric_factor
    regions: list[np.ndarray] = []
    removed_by_unseen = 0
    for i, t in enumerate(times):
        forward = geo_s <= vmax * (t - start.timestamp_s) * factor + lattice.snap_m + _EPS
        backward = geo_e <= vmax * (end.timestamp_s - t) * factor + lattice.snap_m + _EPS
        reach = forward & backward
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
        if removed_by_unseen:
            raise _Unknown("REACHABLE_SET_EMPTY", empty_at_s=empty[:10])
        raise _Unknown("ENDPOINTS_UNREACHABLE", empty_at_s=empty[:10])
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
        always_visible = ~np.logical_or.reduce(unseen_masks)
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
    pool, separation_excluded = _route_pool(
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
        in_any_region,
        response["limits"]["hit"],
        should_stop,
    )
    trace.append(
        {
            "step": "ROUTE_POOL_BUILT",
            "candidates": len(pool),
            "via_cells_excluded_by_separation": separation_excluded,
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
    response["hypotheses"] = selected


def _max_separation(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    return max(
        math.dist(sa["position_m"], sb["position_m"])
        for sa, sb in zip(a["samples"], b["samples"], strict=True)
    )


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
    return {
        "timestamp_s": t,
        "kind": "SAMPLE_SET",
        "polygons": None,
        "samples": [[_r(x), _r(y)] for x, y in points[: cfg.max_region_samples]],
        "cell_size_m": cfg.grid_step_m,
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
    in_any_region: np.ndarray,
    hit: list[str],
    should_stop: Callable[[], bool] | None,
) -> tuple[list[dict[str, Any]], int]:
    """Bounded, deterministic candidate pool.

    Via cells are visited by lattice route length (ties by cell index). A via cell
    closer than ``min_separation_m`` to a route already in the pool is skipped, so
    the pool spreads over alternatives instead of near-copies of the best route.
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
    excluded = 0
    for via in order:
        if len(pool) >= cfg.max_candidate_paths:
            hit.append("MAX_CANDIDATE_PATHS")
            break
        if len(pool) % 32 == 0:
            _check_stop(should_stop, "ROUTES")
        x, y = lattice.xy(via)
        if near is not None and shapely.intersects_xy(near, x, y):
            excluded += 1
            continue
        cells = list(reversed(_cell_chain(via, pred_s)))[:-1] + _cell_chain(via, pred_e)
        first, last = Point(lattice.xy(cells[0])), Point(lattice.xy(cells[-1]))
        anchor_s = nearest_points(start.region, first)[0]
        anchor_e = nearest_points(end.region, last)[0]
        polyline = _string_pull(lattice, cells, (anchor_s.x, anchor_s.y), (anchor_e.x, anchor_e.y))
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
        route_zone = (
            LineString(polyline).buffer(cfg.min_separation_m)
            if len(polyline) > 1
            else Point(polyline[0]).buffer(cfg.min_separation_m)
        )
        near = route_zone if near is None else near.union(route_zone)
    return pool, excluded


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
    conflicts = []
    covered = [False] * len(times)
    for item in evidence:
        for i in item.step_indices:
            covered[i] = True
            if item.eroded_visible is not None and item.eroded_visible.intersects(
                Point(positions[i])
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
        unseen_result = "FAIL"
    elif all(covered):
        unseen_result = "PASS"
    else:
        unseen_result = "UNKNOWN"

    portals: list[str] = []
    for a, b in zip(cells, cells[1:], strict=False):
        if lattice.region_of[a] == lattice.region_of[b]:
            continue
        crossed = lattice.edge(a, b)[1]
        if crossed is None:
            step = LineString([lattice.xy(a), lattice.xy(b)])
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
            },
            "unseen": {
                "result": unseen_result,
                "conflicts": conflicts,
                "steps_without_negative_evidence": covered.count(False),
            },
        },
        "physical_authority": "UNKNOWN",
    }
