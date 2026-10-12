"""Bounded source-authorized physical screening of cross-camera hypotheses.

Known, approved colliders can reject explicit connected segments. Missing motion
is never turned into a straight trajectory, and partial geometry cannot prove
free space, missing doorways or disconnection. Ranking rewards documented local
support and penalizes missing positions under an explicit engineering policy.
"""

from __future__ import annotations

import copy
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from shapely import from_wkb
from shapely.geometry import MultiPolygon, Polygon

from amidst.engineering.registry import content_hash, opaque_ref
from amidst.physical_collision import CollisionNumerics, CylinderCollisionConsumer
from amidst.physical_policy_contract import PhysicalPolicyContract
from amidst.scene_geometry import Coordinate
from amidst.walkable_clearance import WalkableClearanceDomain
from amidst.workbench.blender_association import (
    BEAM_WIDTH,
    MAX_TOP_K,
    BaselineAssociationIndex,
)

Json = dict[str, Any]
PHYSICAL_VERSION = "source-authorized-cross-camera-physical-v1"
POOL_LIMIT = 256
MAX_REJECTED = 5
MAX_CHECKS = 1000
MAX_GEOMETRY_VERTICES = 2048
SUPPORT_BONUS = 0.25
MISSING_PENALTY = 0.25


class PhysicalSource(Protocol):
    """Already pinned/validated server source, never caller-supplied geometry JSON."""

    @property
    def source_sha256(self) -> str: ...
    @property
    def geometry_model_sha256(self) -> str: ...
    @property
    def physical_source_sha256(self) -> str: ...
    @property
    def evidence_hashes(self) -> Mapping[str, str]: ...
    @property
    def contract(self) -> PhysicalPolicyContract: ...
    @property
    def numerics(self) -> CollisionNumerics: ...
    @property
    def collision_consumers(self) -> tuple[CylinderCollisionConsumer, ...]: ...
    @property
    def support_domains(self) -> Mapping[str, WalkableClearanceDomain]: ...
    @property
    def site_support_domains(self) -> Mapping[str, WalkableClearanceDomain]: ...
    @property
    def portals_summary(self) -> Json: ...
    @property
    def coverage(self) -> Json: ...
    @property
    def site_id(self) -> str | None: ...
    def verify(self) -> None: ...
    def public_snapshot(self) -> Json: ...


def _row(
    code: str,
    status: str,
    interval: list[float],
    geometry_ref: str | None = None,
    authority: str = "PARTIAL_SOURCE_AUTHORITY",
    **values: Any,
) -> Json:
    return {
        "code": code,
        "status": status,
        "time_range": interval,
        "geometry_ref": geometry_ref,
        "authority": authority,
        **values,
    }


def _coordinate(position: Any) -> Coordinate:
    if (
        not isinstance(position, (list, tuple))
        or len(position) != 3
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in position)
    ):
        raise ValueError("PHYSICAL_FINITE_METRE_COORDINATE_REQUIRED")
    return float(position[0]), float(position[1]), float(position[2])


def _public(value: Any) -> bool:
    if isinstance(value, dict):
        return not {
            "local_path",
            "private_path",
            "ground_truth",
            "trajectory",
            "input_frames",
        }.intersection(value) and all(_public(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return all(_public(child) for child in value)
    if isinstance(value, str):
        return "/Users/" not in value and "/private/" not in value
    return (
        value is None
        or type(value) in (bool, int)
        or (type(value) is float and math.isfinite(value))
    )


def _code_counts(rows: Sequence[Json]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts[row["code"]] += row["occurrence_count"]
    return dict(counts)


class BlenderPhysicalIndex:
    """Screen a fresh full beam pool once, rather than filtering an old Top-3/5."""

    def __init__(self, base: BaselineAssociationIndex, source: PhysicalSource | None) -> None:
        # The legacy helper records prefix refusals while searching. A private copy
        # preserves the old scene/manifest/index and its precomputed query results.
        self._base = copy.deepcopy(base)
        self._source = source
        self._binding = copy.deepcopy(base._full["source_binding"])
        self.source_features = base.source_features
        self.base_association_sha256 = base.association_sha256
        self._floor_id = base._full["floor_plane"]["floor_id"]
        self._source_range = list(base._full["source_time_range"])
        self._policy: Json = {
            "algorithm_version": PHYSICAL_VERSION,
            "source_authority_required": "APPROVED_PURPOSE_SPECIFIC_EXACT_GEOMETRY",
            "pool_limit": POOL_LIMIT,
            "beam_width": BEAM_WIDTH,
            "max_top_k": MAX_TOP_K,
            "max_rejected_curves": MAX_REJECTED,
            "max_checks_per_path": MAX_CHECKS,
            "support_evidence_bonus_weight": SUPPORT_BONUS,
            "missing_position_penalty_weight": MISSING_PENALTY,
            "ranking_authority": "CONFIGURED_EVIDENCE_SCORE_NOT_PROBABILITY",
            "unknown_retained": True,
            "partial_absence_rejects": False,
            "missing_gap_straight_collision_rejects": False,
            "source_positions_changed": False,
            "source_motion_changed": False,
            "source_units": "METRES",
            "identity_confirmed": False,
            "behavior_confirmed": False,
            "whole_scene_physics_certified": False,
            "rejection_authority": "NOMINAL_PROJECTED_BODY_HYPOTHESIS_ONLY",
            "agent_used": False,
        }
        self._evidence: dict[str, str] = {}
        self._coverage: Json = {
            "status": "UNAVAILABLE",
            "complete_physical_validation": False,
            "reason": "SOURCE_EVIDENCE_UNAVAILABLE",
        }
        self._consumers: tuple[CylinderCollisionConsumer, ...] = ()
        self._domain: WalkableClearanceDomain | None = None
        self._consumer_bounds: list[tuple[Coordinate, Coordinate]] = []
        self._support_cache: dict[tuple[Coordinate, Coordinate], Json] = {}
        self._collision_cache: dict[tuple[Coordinate, Coordinate], list[Json]] = {}
        self._path_checks: dict[str, Json] = {}
        if source is not None:
            self._bind_source(source)
        self.geometry_context = self._geometry_context()
        self._canonical: dict[tuple[str, ...], Json] = {}
        for cameras in self._base._canonical:
            self._canonical[cameras] = self._build_pool(cameras)
        self.physical_sha256 = content_hash(
            {
                "source_binding": self._binding,
                "base_association_sha256": self.base_association_sha256,
                "physical_source_sha256": source.physical_source_sha256 if source else None,
                "evidence_hashes": self._evidence,
                "policy": self._policy,
                "pools": [
                    {
                        "camera_ids": list(cameras),
                        "ledger": value["decision_ledger"],
                        "search": value["search"],
                    }
                    for cameras, value in self._canonical.items()
                ],
            }
        )
        self.reconstruction_sha256 = self.physical_sha256

    def _bind_source(self, source: PhysicalSource) -> None:
        source.verify()
        digests = [
            source.source_sha256,
            source.geometry_model_sha256,
            source.physical_source_sha256,
            *source.evidence_hashes.values(),
        ]
        if any(
            not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
            for value in digests
        ):
            raise ValueError("PHYSICAL_SOURCE_DIGEST_REQUIRED")
        if source.source_sha256 != self._binding["source_sha256"]:
            raise ValueError("PHYSICAL_SOURCE_SCOPE_MISMATCH")
        if source.site_id not in (None, self._binding["site_id"]):
            raise ValueError("PHYSICAL_SOURCE_SITE_MISMATCH")
        source.contract.scale.require_source_sha256(source.source_sha256)
        self._evidence = dict(source.evidence_hashes)
        snapshot = source.public_snapshot()
        if not _public(snapshot):
            raise ValueError("PHYSICAL_SOURCE_PUBLIC_METADATA_INVALID")
        self._coverage = {**copy.deepcopy(snapshot), "complete_physical_validation": False}
        self._domain = source.support_domains.get(self._floor_id)
        if self._domain is not None and (
            self._domain.source_sha256 != source.source_sha256
            or self._domain.scale != source.contract.scale
            or self._domain.policy != source.contract.policy
            or self._domain.floor.floor_id != self._floor_id
        ):
            raise ValueError("PHYSICAL_SUPPORT_SCOPE_MISMATCH")
        consumers = []
        for consumer in source.collision_consumers:
            if (
                consumer.inputs.source_sha256 != source.source_sha256
                or consumer.inputs.geometry_sha256 != source.geometry_model_sha256
                or consumer.contract != source.contract
            ):
                raise ValueError("PHYSICAL_COLLIDER_SCOPE_MISMATCH")
            # Revalidate/rebuild internal arrays from frozen authority models.
            checked = CylinderCollisionConsumer(consumer.inputs, source.contract, source.numerics)
            if self._floor_id not in checked.inputs.scope.floor_ids:
                continue
            consumers.append(checked)
            points = [
                tuple(float(v) for v in p)
                for _, triangles in checked.meshes
                for triangle in triangles
                for p in triangle
            ]
            if not points:
                raise ValueError("PHYSICAL_COLLISION_GEOMETRY_MISSING")
            self._consumer_bounds.append(
                (
                    _coordinate([min(p[a] for p in points) for a in range(3)]),
                    _coordinate([max(p[a] for p in points) for a in range(3)]),
                )
            )
        self._consumers = tuple(consumers)

    def _geometry_context(self) -> Json:
        source = self._source
        context: Json = {
            "units": "METRES",
            "source_sha256": self._binding["source_sha256"],
            "physical_source_sha256": source.physical_source_sha256 if source else None,
            "scope": "PARTIAL_SOURCE_PERMISSION_NOT_COLLISION_FREE",
            "partial": True,
            "display_height_basis": "APPROVED_FLOOR_ANCHOR_ONLY",
            "actual_triangle_heights_retained_in_checks": True,
            "support_polygons": [],
            "colliders": [],
            "portals": {
                "approved_apertures": 0,
                "status": "UNKNOWN",
                "reason": "APERTURE_HUMAN_REVIEW" if source else "SOURCE_EVIDENCE_UNAVAILABLE",
            },
        }
        if source is None:
            return context
        domain = source.site_support_domains.get(self._binding["site_id"])
        if domain is None:
            return context
        if (
            domain.source_sha256 != source.source_sha256
            or domain.scale != source.contract.scale
            or domain.policy != source.contract.policy
            or domain.floor.floor_id != self._floor_id
        ):
            raise ValueError("PHYSICAL_SITE_SUPPORT_SCOPE_MISMATCH")
        geometry = from_wkb(domain.union_wkb)
        if isinstance(geometry, Polygon):
            polygons = [geometry]
        elif isinstance(geometry, MultiPolygon):
            polygons = list(geometry.geoms)
        else:
            raise ValueError("PHYSICAL_SUPPORT_POLYGON_REQUIRED")
        ratio = source.contract.scale.metres_per_blender_unit
        height = domain.floor.point[2] * ratio
        vertices = 0
        for ordinal, polygon in enumerate(polygons):
            vertices += len(polygon.exterior.coords) + sum(
                len(ring.coords) for ring in polygon.interiors
            )
            if vertices > MAX_GEOMETRY_VERTICES or ordinal >= 64:
                context["overlay_truncated"] = True
                break
            ref = opaque_ref(
                "geometry",
                source.physical_source_sha256,
                self._binding["site_id"],
                str(ordinal),
                content_hash(polygon.wkb.hex()),
            )
            context["support_polygons"].append(
                {
                    "geometry_ref": ref,
                    "display_label": f"來源支持區域 {ordinal + 1}",
                    "authority": "APPROVED",
                    "role": "SOURCE_SUPPORTED_WALKABLE_ONLY",
                    "exterior": [
                        [x * ratio, y * ratio, height] for x, y in polygon.exterior.coords
                    ],
                    "holes": [
                        [[x * ratio, y * ratio, height] for x, y in ring.coords]
                        for ring in polygon.interiors
                    ],
                }
            )
        return context

    def _support(self, start: Coordinate, end: Coordinate) -> Json:
        key = (start, end)
        if key in self._support_cache:
            return self._support_cache[key]
        domain = self._domain
        if domain is None:
            result = {
                "code": "APPROVED_SUPPORT_UNAVAILABLE",
                "status": "UNKNOWN",
                "supported": False,
            }
        else:
            ratio = domain.scale.metres_per_blender_unit
            a: Coordinate = (start[0] / ratio, start[1] / ratio, start[2] / ratio)
            b: Coordinate = (end[0] / ratio, end[1] / ratio, end[2] / ratio)
            decision = domain.validate_segment(a, b)
            result = {
                "code": "APPROVED_SOURCE_SUPPORT" if decision.valid else decision.reason,
                "status": "SUPPORTED_LOCAL_ONLY" if decision.valid else "UNKNOWN",
                "supported": decision.valid,
                "clearance_m": decision.clearance_m,
                "required_clearance_m": decision.required_clearance_m,
            }
        self._support_cache[key] = result
        return result

    def _collision(self, start: Coordinate, end: Coordinate) -> list[Json]:
        key = (start, end)
        if key in self._collision_cache:
            return self._collision_cache[key]
        if not self._consumers:
            rows = [
                {
                    "code": "APPROVED_COLLIDER_SCOPE_UNAVAILABLE",
                    "status": "UNKNOWN",
                    "geometry_ref": None,
                    "tested_triangles": 0,
                }
            ]
        else:
            rows = []
            assert self._source is not None
            radius = self._source.contract.footprint_radius_m
            height = self._source.contract.parameter("body_height_m")
            clearance = self._source.contract.parameter("body_clearance_m")
            lower = [min(start[a], end[a]) - (radius if a < 2 else clearance) for a in range(3)]
            upper = [
                max(start[a], end[a]) + (radius if a < 2 else height + clearance) for a in range(3)
            ]
            for consumer, (low, high) in zip(self._consumers, self._consumer_bounds, strict=True):
                geometry_ref = opaque_ref(
                    "geometry", self._source.physical_source_sha256, consumer.inputs.scope.scope_id
                )
                if any(upper[a] < low[a] or lower[a] > high[a] for a in range(3)):
                    # Exact collider bounds accelerate, without certifying free space.
                    continue
                decision = consumer.validate((start, end))
                rows.append(
                    {
                        "code": "KNOWN_COMPONENTS_NOT_INTERSECTED"
                        if not decision.reasons
                        else decision.reasons[0].split(":")[0],
                        "status": "REJECTED"
                        if decision.state == "REJECTED"
                        else "UNKNOWN"
                        if decision.state == "UNVALIDATED"
                        else "SUPPORTED_LOCAL_ONLY",
                        "geometry_ref": geometry_ref,
                        "tested_triangles": decision.tested_triangles,
                        "scope_id": consumer.inputs.scope.scope_id,
                        "scope_coverage": str(consumer.inputs.scope.coverage),
                    }
                )
            if not rows:
                rows = [
                    {
                        "code": "KNOWN_COMPONENTS_OUTSIDE_SWEPT_BOUNDS",
                        "status": "SUPPORTED_LOCAL_ONLY",
                        "geometry_ref": None,
                        "tested_triangles": 0,
                    }
                ]
        self._collision_cache[key] = rows
        return rows

    def _check_path(self, path: Json) -> Json:
        if path["path_ref"] in self._path_checks:
            return self._path_checks[path["path_ref"]]
        checks, connected, supported, rejected, triangles = [], 0, 0, 0, 0
        covered: set[tuple[float, Coordinate]] = set()
        swept: set[tuple[float, Coordinate, float, Coordinate]] = set()
        samples = path["samples"]
        # Isolated projected samples still have conditional body occupancy checks.
        for a, b in zip(samples, samples[1:], strict=False):
            if (
                not b["connect_from_previous"]
                or a["world_position"] is None
                or b["world_position"] is None
            ):
                continue
            if connected >= MAX_CHECKS:
                checks.append(
                    _row("PHYSICAL_CHECK_BUDGET", "UNKNOWN", path["canonical_time_range"])
                )
                break
            connected += 1
            start, end = _coordinate(a["world_position"]), _coordinate(b["world_position"])
            covered.update(((a["timestamp"], start), (b["timestamp"], end)))
            swept.add((a["timestamp"], start, b["timestamp"], end))
            interval = [a["timestamp"], b["timestamp"]]
            support = self._support(start, end)
            supported += int(support["supported"])
            checks.append(
                _row(
                    support["code"],
                    support["status"],
                    interval,
                    authority="APPROVED_SUPPORT_ONLY",
                    clearance_m=support.get("clearance_m"),
                    required_clearance_m=support.get("required_clearance_m"),
                )
            )
            for collision in self._collision(start, end):
                triangles += collision["tested_triangles"]
                rejected += int(collision["status"] == "REJECTED")
                checks.append(
                    _row(
                        collision["code"],
                        collision["status"],
                        interval,
                        collision["geometry_ref"],
                        "APPROVED_KNOWN_COMPONENTS_ONLY",
                        tested_triangles=collision["tested_triangles"],
                    )
                )
        secondary, secondary_supported, secondary_rejected = 0, 0, 0
        for node_ref in path["node_refs"]:
            node = self._base._nodes[node_ref]
            for a, b in zip(node["samples"], node["samples"][1:], strict=False):
                if (
                    not b["connect_from_previous"]
                    or a["world_position"] is None
                    or b["world_position"] is None
                ):
                    continue
                start, end = _coordinate(a["world_position"]), _coordinate(b["world_position"])
                key = (a["timestamp"], start, b["timestamp"], end)
                if key in swept:
                    continue
                if connected + secondary >= MAX_CHECKS:
                    checks.append(
                        _row("PHYSICAL_CHECK_BUDGET", "UNKNOWN", path["canonical_time_range"])
                    )
                    break
                swept.add(key)
                covered.update(((a["timestamp"], start), (b["timestamp"], end)))
                secondary += 1
                interval = [a["timestamp"], b["timestamp"]]
                segment_basis = {
                    "check_basis": "ORIGINAL_SECONDARY_CONNECTED_SEGMENT",
                    "source_node_ref": node_ref,
                    "source_camera_id": node["camera_id"],
                }
                support = self._support(start, end)
                secondary_supported += int(support["supported"])
                checks.append(
                    _row(
                        support["code"],
                        support["status"],
                        interval,
                        authority="APPROVED_SUPPORT_ONLY",
                        **segment_basis,
                    )
                )
                for collision in self._collision(start, end):
                    collision_rejected = int(collision["status"] == "REJECTED")
                    rejected += collision_rejected
                    secondary_rejected += collision_rejected
                    triangles += collision["tested_triangles"]
                    checks.append(
                        _row(
                            collision["code"],
                            collision["status"],
                            interval,
                            collision["geometry_ref"],
                            "APPROVED_KNOWN_COMPONENTS_ONLY",
                            tested_triangles=collision["tested_triangles"],
                            **segment_basis,
                        )
                    )
        points = [
            (sample["timestamp"], _coordinate(sample["world_position"]), "PRIMARY_POSITION")
            for sample in samples
            if sample["world_position"] is not None
        ] + [
            (
                sample["timestamp"],
                _coordinate(support["world_position"]),
                "ORIGINAL_OVERLAP_SUPPORT",
            )
            for sample in samples
            for support in sample.get("overlap_support", [])
        ]
        point_checks, supported_points = 0, 0
        for timestamp, point, basis in points:
            if (timestamp, point) in covered:
                continue
            if connected + secondary + point_checks >= MAX_CHECKS:
                checks.append(
                    _row("PHYSICAL_CHECK_BUDGET", "UNKNOWN", path["canonical_time_range"])
                )
                break
            covered.add((timestamp, point))
            point_checks += 1
            interval = [timestamp, timestamp]
            support = self._support(point, point)
            supported_points += int(support["supported"])
            checks.append(
                _row(
                    support["code"],
                    support["status"],
                    interval,
                    authority="APPROVED_SUPPORT_ONLY",
                    point_basis=basis,
                )
            )
            for collision in self._collision(point, point):
                rejected += int(collision["status"] == "REJECTED")
                triangles += collision["tested_triangles"]
                checks.append(
                    _row(
                        collision["code"],
                        collision["status"],
                        interval,
                        collision["geometry_ref"],
                        "APPROVED_KNOWN_COMPONENTS_ONLY",
                        tested_triangles=collision["tested_triangles"],
                        point_basis=basis,
                    )
                )
        for gap in path["gaps"]:
            interval = gap["time_range"]
            endpoints = [
                sample
                for sample in samples
                if sample["timestamp"] in interval and sample["world_position"] is not None
            ]
            necessity: Json = {}
            if len(endpoints) == 2:
                start, end = (_coordinate(row["world_position"]) for row in endpoints)
                distance = math.dist(start, end)
                seconds = interval[1] - interval[0]
                probe = self._support(start, end)
                necessity = {
                    "endpoint_distance_lower_bound_m": distance,
                    "lower_bound_authority": "PROJECTED_ENDPOINTS_AND_CONFIGURED_SPEED_ONLY",
                    "configured_max_speed_m_s": self._base._policy["max_speed_m_s"],
                    "minimum_time_lower_bound_s": distance / self._base._policy["max_speed_m_s"],
                    "available_time_s": seconds,
                    "time_lower_bound_satisfied": distance
                    <= seconds * self._base._policy["max_speed_m_s"] + 1e-9,
                    "straight_support_probe": probe["code"],
                    "support_probe_is_trajectory": False,
                    "partial_support_disconnection_rejects": False,
                    "approved_aperture_available": False,
                    "complete_route_authority_available": False,
                }
            # Never sweep the missing endpoint chord against a collider.
            checks.append(
                _row(
                    "MISSING_GAP_ROUTE_UNOBSERVED",
                    "UNKNOWN",
                    interval,
                    necessity="NO_APPROVED_COMPLETE_ROUTE_OR_APERTURE",
                    chord_collision_tested=False,
                    **necessity,
                )
            )
        checks.append(
            _row(
                "WHOLE_SCENE_BODY_CLEARANCE_UNKNOWN",
                "UNKNOWN",
                path["canonical_time_range"],
                authority="PARTIAL_SOURCE_AUTHORITY",
            )
        )
        if self._source is None:
            checks.append(
                _row("SOURCE_EVIDENCE_UNAVAILABLE", "UNKNOWN", path["canonical_time_range"])
            )
        result = {
            "checks": checks,
            "connected_intervals": connected,
            "supported_intervals": supported,
            "secondary_connected_intervals": secondary,
            "secondary_supported_intervals": secondary_supported,
            "secondary_known_collision_rejections": secondary_rejected,
            "point_occupancy_checks": point_checks,
            "supported_points": supported_points,
            "known_collision_rejections": rejected,
            "tested_triangles": triangles,
            "long_missing_gaps": len(path["gaps"]),
            "missing_duration_s": sum(
                g["time_range"][1] - g["time_range"][0] for g in path["gaps"]
            ),
        }
        self._path_checks[path["path_ref"]] = result
        return result

    def _check_candidate(self, candidate: Json, original_rank: int) -> Json:
        checks, connected, supported, rejected, triangles, gaps, missing_s = [], 0, 0, 0, 0, 0, 0.0
        point_checks, supported_points = 0, 0
        secondary, secondary_supported, secondary_rejected = 0, 0, 0
        for path in candidate["paths"]:
            decision = self._check_path(path)
            checks.extend(decision["checks"])
            connected += decision["connected_intervals"]
            supported += decision["supported_intervals"]
            secondary += decision["secondary_connected_intervals"]
            secondary_supported += decision["secondary_supported_intervals"]
            secondary_rejected += decision["secondary_known_collision_rejections"]
            point_checks += decision["point_occupancy_checks"]
            supported_points += decision["supported_points"]
            rejected += decision["known_collision_rejections"]
            triangles += decision["tested_triangles"]
            gaps += decision["long_missing_gaps"]
            missing_s += decision["missing_duration_s"]
        for gap in candidate["unresolved_local_gaps"]:
            checks.append(
                _row(
                    "ORIGINAL_LOCAL_HARD_GAP_UNRESOLVED",
                    "UNKNOWN",
                    gap["time_range"],
                    source_reason=gap["reason"],
                )
            )
        if not any(
            sample["world_position"] is not None
            for path in candidate["paths"]
            for sample in path["samples"]
        ):
            checks.append(_row("NO_USABLE_PROJECTED_BODY_EVIDENCE", "UNKNOWN", self._source_range))
            if self._source is None:
                checks.append(_row("SOURCE_EVIDENCE_UNAVAILABLE", "UNKNOWN", self._source_range))
        compact = self._compact_checks(checks)
        unknowns = [row for row in compact if row["status"] == "UNKNOWN"]
        reasons = [row for row in compact if row["status"] == "REJECTED"]
        bonus = SUPPORT_BONUS * supported / max(1, connected) if self._source else 0.0
        duration = max(0.2, self._source_range[1] - self._source_range[0])
        penalty = MISSING_PENALTY * min(1.0, missing_s / duration) if self._source else 0.0
        score = float(candidate["score"] + bonus - penalty)
        verdict = "REJECTED" if rejected else "UNKNOWN" if unknowns else "SUPPORTED_LOCAL_ONLY"
        physical = {
            "verdict": verdict,
            "reasons": reasons,
            "unknowns": unknowns,
            "checks": compact,
            "check_records_count": len(checks),
            "checks_sha256": content_hash(checks),
            "expanded_check_records_exported": False,
            "scores": {
                "base_compatibility": candidate["score"],
                "support_evidence_bonus": bonus,
                "missing_position_penalty": penalty,
                "ranking_score": score,
            },
            "evidence_counts": {
                "connected_intervals": connected,
                "supported_intervals": supported,
                "secondary_connected_intervals": secondary,
                "secondary_supported_intervals": secondary_supported,
                "secondary_known_collision_rejections": secondary_rejected,
                "point_occupancy_checks": point_checks,
                "supported_points": supported_points,
                "unknown_intervals": sum(row["status"] == "UNKNOWN" for row in checks),
                "known_collision_rejections": rejected,
                "long_missing_gaps": gaps,
                "tested_triangles": triangles,
            },
            "complete_physical_validation": False,
        }
        physical["decision_sha256"] = content_hash(physical)
        return {
            **candidate,
            "original_rank": original_rank,
            "score": score,
            "cost": -score,
            "physical": physical,
        }

    @staticmethod
    def _compact_checks(checks: list[Json]) -> list[Json]:
        grouped: dict[tuple[str, str, str | None, str], list[Json]] = {}
        for row in checks:
            key = (row["code"], row["status"], row["geometry_ref"], row["authority"])
            grouped.setdefault(key, []).append(row)
        result = []
        for (code, status, geometry_ref, authority), rows in sorted(
            grouped.items(), key=lambda pair: tuple(str(v) for v in pair[0])
        ):
            result.append(
                {
                    "code": code,
                    "status": status,
                    "geometry_ref": geometry_ref,
                    "authority": authority,
                    "time_range": [
                        min(row["time_range"][0] for row in rows),
                        max(row["time_range"][1] for row in rows),
                    ],
                    "occurrence_count": len(rows),
                    "check_sha256": content_hash(rows),
                    "sample_checks": copy.deepcopy(rows[:2]),
                    "sample_limit": 2,
                    "samples_truncated": len(rows) > 2,
                }
            )
        return result

    def _build_pool(self, cameras: tuple[str, ...]) -> Json:
        nodes = [
            ref for ref in self._base._ordered if self._base._nodes[ref]["camera_id"] in cameras
        ]
        node_set = set(nodes)
        edges = sorted(
            (
                ref
                for ref, row in self._base._edges.items()
                if row["from_node_ref"] in node_set and row["to_node_ref"] in node_set
            ),
            key=lambda ref: (-self._base._edges[ref]["compatibility_score"], ref),
        )
        beam: list[tuple[str, ...]] = [()]
        pruned, evaluated = False, 1
        prefix_before = self._base._route_prefix_rejections
        for edge in edges:
            expanded = list(beam)
            for state in beam:
                proposal = tuple(sorted((*state, edge)))
                evaluated += 1
                if self._base._consistent(proposal):
                    expanded.append(proposal)
            expanded = sorted(set(expanded), key=lambda state: (-self._base._score(state), state))
            pruned |= len(expanded) > BEAM_WIDTH
            beam = expanded[:BEAM_WIDTH]
        prefix_rejections = self._base._route_prefix_rejections - prefix_before
        pool = [
            self._check_candidate(self._base._candidate(state, nodes), rank)
            for rank, state in enumerate(beam[:POOL_LIMIT], 1)
        ]
        has_association = any(row["selected_edge_refs"] for row in pool)
        all_retained = [row for row in pool if row["physical"]["verdict"] != "REJECTED"]
        retained = sorted(
            (row for row in all_retained if row["selected_edge_refs"] or not has_association),
            key=lambda row: (-row["score"], row["candidate_ref"]),
        )
        rejected = sorted(
            (row for row in pool if row["physical"]["verdict"] == "REJECTED"),
            key=lambda row: (-row["score"], row["candidate_ref"]),
        )
        baseline = self._check_candidate(self._base._candidate((), nodes), 0)
        ranks = {row["candidate_ref"]: rank for rank, row in enumerate(retained, 1)}
        ledger = [
            {
                "candidate_ref": row["candidate_ref"],
                "original_rank": row["original_rank"],
                "rerank": ranks.get(row["candidate_ref"]),
                "is_unassociated_baseline": row["is_unassociated_baseline"],
                "selected_for_ranking": row["candidate_ref"] in ranks,
                "verdict": row["physical"]["verdict"],
                "scores": row["physical"]["scores"],
                "decision_sha256": row["physical"]["decision_sha256"],
                "reason_codes": _code_counts(row["physical"]["reasons"]),
                "unknown_codes": _code_counts(row["physical"]["unknowns"]),
            }
            for row in pool
        ]
        return {
            "candidates": retained[:MAX_TOP_K],
            "rejected_candidates": rejected[:MAX_REJECTED],
            "baseline_candidate": baseline,
            "decision_ledger": ledger,
            "search": {
                "algorithm": "FULL_BOUNDED_BEAM_POOL_THEN_PHYSICAL_SCREEN_AND_RERANK",
                "pool_budget": POOL_LIMIT,
                "considered": len(pool),
                "retained": len(all_retained),
                "rankable_retained": len(retained),
                "unassociated_baseline_in_ranking": not has_association,
                "rejected": len(rejected),
                "unknown": sum(row["physical"]["verdict"] == "UNKNOWN" for row in pool),
                "supported_local_only": sum(
                    row["physical"]["verdict"] == "SUPPORTED_LOCAL_ONLY" for row in pool
                ),
                "old_top_k_pool_only": False,
                "beam_width": BEAM_WIDTH,
                "edges_considered": len(edges),
                "hypotheses_evaluated": evaluated,
                "prefix_route_guard_rejections": prefix_rejections,
                "truncated": bool(pruned),
                "complete": not pruned and not prefix_rejections,
                "ranking_scope": "SELECTED_CAMERAS_FULL_SOURCE_TIME",
                "physical_candidate_pool_complete": not pruned and not prefix_rejections,
                "score_optimality": "BOUNDED_POOL_NOT_GLOBALLY_CERTIFIED"
                if pruned or prefix_rejections
                else "EXACT_WITHIN_SOURCE_GRAPH_AND_CONFIGURED_POLICY",
            },
        }

    def reconstruct(
        self, camera_ids: Sequence[str], start: float, end: float, top_k: int = 3
    ) -> Json:
        # Existing validated query guards enforce cameras, finite time and K bounds.
        if self._source is not None:
            self._source.verify()
        local = self._base.reconstruct(camera_ids, start, end, top_k)
        cameras = tuple(sorted(camera_ids))
        canonical = self._canonical[cameras]
        candidates = [
            self._base._slice_candidate(row, start, end) for row in canonical["candidates"][:top_k]
        ]
        rejected = [
            self._base._slice_candidate(row, start, end) for row in canonical["rejected_candidates"]
        ]
        usable = any(
            p["world_position"] is not None
            for c in [*candidates, *rejected]
            for path in c["paths"]
            for p in path["samples"]
        )
        if not usable:
            candidates, rejected = [], []
        for rank, candidate in enumerate(candidates, 1):
            candidate["rank"] = rank
        for rank, candidate in enumerate(rejected, 1):
            candidate["rejection_rank"] = rank
        baseline = self._base._slice_candidate(canonical["baseline_candidate"], start, end)
        status = (
            "NO_RESULT"
            if not usable
            else "ALL_CANDIDATES_REJECTED"
            if not candidates
            else "READY"
            if any(c["selected_edge_refs"] for c in candidates)
            else "NO_CROSS_CAMERA_EVIDENCE"
        )
        search = {
            **canonical["search"],
            "requested_top_k": top_k,
            "returned_top_k": len(candidates),
            "rejected_curves_returned": len(rejected),
            "rejected_curves_truncated": canonical["search"]["rejected"] > len(rejected),
            "fabricated_candidates": False,
            "display_window_reranks": False,
        }
        return {
            **local,
            "schema_version": "workbench.blender-physical.v1",
            "status": status,
            "association_result_reason": "NO_USABLE_POINTS"
            if status == "NO_RESULT"
            else "KNOWN_COLLISION_REJECTED_BOUNDED_POOL"
            if status == "ALL_CANDIDATES_REJECTED"
            else "PHYSICAL_SCREENED_CANDIDATES_AVAILABLE"
            if status == "READY"
            else "NO_ELIGIBLE_CROSS_CAMERA_EDGE",
            "base_association_sha256": self.base_association_sha256,
            "physical_sha256": self.physical_sha256,
            "reconstruction_sha256": self.physical_sha256,
            "physical_source_sha256": self._source.physical_source_sha256 if self._source else None,
            "evidence_hashes": dict(self._evidence),
            "authority_coverage": copy.deepcopy(self._coverage),
            "geometry_context": copy.deepcopy(self.geometry_context),
            "physical_policy": copy.deepcopy(self._policy),
            "candidates": candidates,
            "rejected_candidates": rejected,
            "baseline_candidate": baseline,
            "search": search,
            "decision_ledger": copy.deepcopy(canonical["decision_ledger"]),
            "decision_ledger_sha256": content_hash(canonical["decision_ledger"]),
            "summary": {
                **local["summary"],
                "candidates": len(candidates),
                "physical_pool_considered": canonical["search"]["considered"],
                "physical_rejected": canonical["search"]["rejected"],
                "physical_unknown": canonical["search"]["unknown"],
                "physical_retained": canonical["search"]["retained"],
            },
            "retrieval": {
                **local["retrieval"],
                "physical_checks_at_query": 0,
                "physical_pool_built_at_import": True,
            },
            "limitations": [
                *local["limitations"],
                "Unknown geometry, apertures and long-gap motion remain UNKNOWN and retained.",
                "Rejection applies only to the configured projected/inferred body hypothesis.",
                "Partial collision scopes/support do not certify whole-scene free space.",
                "Ranking is a configured evidence score over a bounded pool, not probability.",
            ],
        }
