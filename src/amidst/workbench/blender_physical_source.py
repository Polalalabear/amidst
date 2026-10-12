"""Pinned source-only physical inputs, without Blender or simulator observations.

Exact source triangles and existing approval scopes enter typed continuous consumers.
Partial scopes support known-positive pruning; they do not certify missing walls,
portal apertures, ceiling clearance, building completeness or collision-free routes.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from shapely import from_wkb
from shapely.geometry import MultiPolygon, Polygon

from amidst.architectural_scale import ArchitecturalScale
from amidst.engineering.registry import content_hash
from amidst.physical_authority import (
    PhysicalAuthorityResolution,
    PhysicalPolicy,
    PhysicalPurpose,
    ReadOnlyPhysicalAuthorityProvider,
    canonical_geometry_sha256,
)
from amidst.physical_collision import CollisionNumerics, CylinderCollisionConsumer
from amidst.physical_policy_contract import PhysicalPolicyContract, PhysicalPolicyRuntime
from amidst.scene_geometry import Authority, GeometryRole, GeometrySupport, SceneGeometrySnapshot
from amidst.walkable_clearance import WalkableClearanceDomain
from amidst.workbench.source_presentation import SOURCE_SHA256

Json = dict[str, Any]
_BASE = "data/scene_audit/phase1_physical_policy_approval_20261006/"
_PATHS = {
    "geometry_archive": _BASE + "geometry.json.gz",
    "authority_resolution": _BASE + "physical_authority.json",
    "floor_support": _BASE + "floor_support_details.json.gz",
    "portal_review": _BASE + "portal_clearance.json",
    "local_scope_review": _BASE + "local_physical_scopes.json",
    "source_archive": _BASE + "source_evidence.json.gz",
    "architectural_scale": "configs/architectural_scale_school_v3.json",
    "body_policy": "configs/physical_authority_policy_school_v3.json",
    "policy_runtime": "configs/physical_policy_runtime_school_v3.json",
    "collision_numerics": "configs/physical_collision_numerics_v1.json",
}
_PINS = {
    "geometry_archive": "bd2287428bba9d983285dbf5f0bd301963a6a2bceb988a27fa6ab6b898e182fc",
    "authority_resolution": "dbea2bf7f375db161d0b6c9a664b9eba511c9dcc28b61091a4e8fbd53379d60d",
    "floor_support": "6a37b041a368e3e576da4c3f3894708462c0504956f82ad599082acd816b23d0",
    "portal_review": "7e351a570f9fffe195a7ce4d72d3b4206fcc1e2eb534c10487e930eceb861fbe",
    "local_scope_review": "19a472c7fae5bf3e3dc63bc314c3e751467fc8abac636e237c300719ac557c71",
    "source_archive": "6d30e591d6210707f2b6175bf96dc2fe2395fe0202b24bd0a6df7ee87a5d997c",
    "architectural_scale": "7e3615a3b0b4485585da9c0f7beefb96955517f7a321910fc008c041f99a3eaf",
    "body_policy": "2427b3670ac8c3748c75deb172fd1f3bfb7da853fb49a7ad2cd5aac2ef8af7ea",
    "policy_runtime": "704b0f2fb115b691ff61249dc8d4521e39a06467aec0bcca913119fce0491f08",
    "collision_numerics": "cca85ae64f56538f4e2b5352c4962c82d468a3d00622b6c99f35e8a329ac795b",
}
_SITE_SUPPORT = {"office": "WALK_1F_OFFICE", "classroom101": "WALK_1F_CLASS101",
                 "auditorium": "WALK_1F_AUDITORIUM"}
Fingerprint = tuple[int, int, int, int, int]
_CACHE: dict[tuple[str, tuple[tuple[str, Fingerprint], ...]], PhysicalSourceInputs] = {}


def _path(repo: Path, alias: str) -> Path:
    root = repo.resolve()
    target = root / _PATHS[alias]
    current = root
    for component in Path(_PATHS[alias]).parts:
        current = current / component
        if current.is_symlink():
            raise ValueError("PHYSICAL_SOURCE_STALE")
    if not target.is_file() or not target.resolve().is_relative_to(root):
        raise ValueError("PHYSICAL_SOURCE_STALE")
    return target


def _fingerprint(path: Path) -> Fingerprint:
    s = path.stat()
    return s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_ino, s.st_dev


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _pinned_json(repo: Path, alias: str) -> Json:
    path = _path(repo, alias)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != _PINS[alias]:
        raise ValueError("PHYSICAL_SOURCE_STALE")
    value = json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)
    if not isinstance(value, dict):
        raise ValueError("PHYSICAL_SOURCE_STALE")
    return value


@dataclass(frozen=True, slots=True)
class PhysicalSourceInputs:
    source_sha256: str
    geometry_model_sha256: str
    physical_source_sha256: str
    evidence_hashes: dict[str, str]
    contract: PhysicalPolicyContract
    numerics: CollisionNumerics
    collision_consumers: tuple[CylinderCollisionConsumer, ...]
    support_domains: dict[str, WalkableClearanceDomain]
    site_support_domains: dict[str, WalkableClearanceDomain]
    portals_summary: Json
    coverage: Json
    site_id: str | None = None
    _repo: Path = field(default=Path("."), repr=False)
    _fingerprints: dict[str, Fingerprint] = field(default_factory=dict, repr=False)
    _summary: Json = field(default_factory=dict, repr=False)
    _geometry: SceneGeometrySnapshot | None = field(default=None, repr=False)

    def verify(self) -> None:
        """Check immutable import fingerprints; never scan/decode large geometry on query."""
        try:
            for alias, expected in self._fingerprints.items():
                path = _path(self._repo, alias)
                if _fingerprint(path) != expected:
                    raise ValueError("PHYSICAL_SOURCE_STALE")
                if expected[0] <= 256 * 1024 and _file_sha(path) != self.evidence_hashes[alias]:
                    raise ValueError("PHYSICAL_SOURCE_STALE")
            if (self.source_sha256 != SOURCE_SHA256
                or self.contract.scale.source_asset_sha256 != SOURCE_SHA256
                or self.contract.runtime.source_asset_sha256 != SOURCE_SHA256
                or content_hash(self.contract.policy.model_dump(mode="json")) !=
                    self.evidence_hashes["body_policy_model"]
                or content_hash(self.contract.scale.model_dump(mode="json")) !=
                    self.evidence_hashes["architectural_scale_model"]
                or content_hash(self.contract.runtime.model_dump(mode="json")) !=
                    self.evidence_hashes["policy_runtime_model"]
                or content_hash(self.numerics.model_dump(mode="json")) !=
                    self.evidence_hashes["collision_numerics_model"]
                or content_hash(self._summary) != self.physical_source_sha256
            ):
                raise ValueError("PHYSICAL_SOURCE_STALE")
        except (OSError, KeyError, ValueError):
            raise ValueError("PHYSICAL_SOURCE_STALE") from None

    def public_summary(self) -> Json:
        self.verify()
        result = copy.deepcopy(self._summary)
        result["physical_source_sha256"] = self.physical_source_sha256
        if self.site_id is not None:
            domain = self.site_support_domains[self.site_id]
            result["physical_presentation"] = self.presentation()
            result["site_context"] = {"site_id": self.site_id,
                "declared_walkable_id": _SITE_SUPPORT[self.site_id],
                "approved_support_surfaces": len(domain.support_surfaces),
                "camera_or_track_room_ownership_confirmed": False,
                "collision_scope_restricted_by_site_box": False}
        return result

    def presentation(self) -> Json:
        """Bounded display outlines, preserving holes; not a body-clearance certificate."""
        self.verify()
        if self.site_id is None:
            return {"status": "UNAVAILABLE", "reason": "SITE_CONTEXT_REQUIRED"}
        domain = self.site_support_domains[self.site_id]
        shape = from_wkb(domain.union_wkb)
        if isinstance(shape, Polygon):
            polygons = [shape]
        elif isinstance(shape, MultiPolygon):
            polygons = list(shape.geoms)
        else:
            return {"status": "UNAVAILABLE", "reason": "SOURCE_SUPPORT_DISPLAY_TYPE"}
        vertex_count = sum(len(p.exterior.coords) + sum(len(r.coords) for r in p.interiors)
                           for p in polygons)
        if len(polygons) > 64 or vertex_count > 2048:
            return {"status": "UNAVAILABLE", "reason": "SOURCE_SUPPORT_DISPLAY_BUDGET"}
        factor = domain.scale.metres_per_blender_unit
        z = domain.floor.point[2] * factor
        outlines = [{"outer": [[float(x) * factor, float(y) * factor, z]
                               for x, y in polygon.exterior.coords],
                     "holes": [[[float(x) * factor, float(y) * factor, z]
                                for x, y in ring.coords] for ring in polygon.interiors]}
                    for polygon in polygons]
        return {"status": "AVAILABLE", "schema_version": "physical-support-display.v1",
            "source_sha256": self.source_sha256, "units": "METRES", "site_id": self.site_id,
            "authority": "SOURCE_APPROVED_SUPPORT_ONLY", "display_only": True,
            "body_clearance": "UNKNOWN", "portal_aperture": "HUMAN_REVIEW",
            "source_domain_sha256": hashlib.sha256(domain.union_wkb).hexdigest(),
            "actual_triangle_heights_retained_in_consumers": True,
            "display_height_basis": "APPROVED_FLOOR_ANCHOR_ONLY",
            "outlines": outlines, "polygon_count": len(polygons), "vertex_count": vertex_count}

    def public_snapshot(self) -> Json:
        return self.public_summary()

    def export_safe_inputs(self) -> Json:
        """Local GT-free DTO; exact triangles in metres, no filesystem locators."""
        summary = self.public_summary()
        if self._geometry is None:
            raise ValueError("PHYSICAL_SOURCE_STALE")
        factor = self.contract.scale.metres_per_blender_unit
        selected = {surface.surface_id for domain in self.support_domains.values()
                    for surface in domain.support_surfaces}
        selected.update(surface.surface_id for consumer in self.collision_consumers
                        for surface, _ in consumer.meshes)
        rows = []
        for surface in self._geometry.surfaces:
            if surface.surface_id not in selected:
                continue
            rows.append({"surface_id": surface.surface_id, "role": surface.role.value,
                "support": surface.support.value, "floor_ids": list(surface.floor_ids),
                "semantic_authority": surface.semantic_authority.value,
                "physical_authority": surface.physical_authority.value,
                "blocks_movement": surface.blocks_movement,
                "vertices": [[value * factor for value in vertex] for vertex in surface.vertices],
                "triangles": [list(triangle) for triangle in surface.triangles],
                "source_face_indices": list(surface.source_face_indices),
                "approval_id": surface.approval_id, "evidence_ids": list(surface.evidence_ids)})
        return {"schema_version": "workbench.blender-physical-source-inputs.v1",
                "summary": summary, "units": "METRES", "surfaces": rows,
                "geometry_is_partial": True, "gt_used": False, "agent_used": False}


def _build(repo: Path, fingerprints: dict[str, Fingerprint]) -> PhysicalSourceInputs:
    geometry = SceneGeometrySnapshot.model_validate_json(
        json.dumps(_pinned_json(repo, "geometry_archive")))
    model_hash = canonical_geometry_sha256(geometry)
    resolution = PhysicalAuthorityResolution.model_validate_json(
        json.dumps(_pinned_json(repo, "authority_resolution")))
    provider = ReadOnlyPhysicalAuthorityProvider(geometry, resolution, SOURCE_SHA256, model_hash)
    policy = PhysicalPolicy.model_validate_json(
        json.dumps(_pinned_json(repo, "body_policy")))
    scale = ArchitecturalScale.model_validate_json(
        json.dumps(_pinned_json(repo, "architectural_scale")))
    runtime = PhysicalPolicyRuntime.model_validate_json(
        json.dumps(_pinned_json(repo, "policy_runtime")))
    numerics = CollisionNumerics.model_validate_json(
        json.dumps(_pinned_json(repo, "collision_numerics")))
    contract = PhysicalPolicyContract(policy, scale, runtime)
    if (geometry.source_sha256 != SOURCE_SHA256 or geometry.unit_scale_m !=
        scale.metres_per_blender_unit or resolution.policy != policy
        or runtime.policy_config != _PATHS["body_policy"]
        or runtime.architectural_scale_config != _PATHS["architectural_scale"]
    ):
        raise ValueError("PHYSICAL_SOURCE_STALE")
    support = _pinned_json(repo, "floor_support")
    portals = _pinned_json(repo, "portal_review")
    local = _pinned_json(repo, "local_scope_review")
    if any(value["source_sha256"] != SOURCE_SHA256 for value in (support, portals, local)):
        raise ValueError("PHYSICAL_SOURCE_STALE")
    floor = next(row for row in geometry.floors if row.floor_id == "1F")
    approved_support = tuple(surface for surface in geometry.surfaces
        if surface.role == GeometryRole.WALKABLE and surface.support == GeometrySupport.SURFACE
        and surface.semantic_authority == Authority.APPROVED
        and surface.physical_authority == Authority.APPROVED and surface.floor_ids == ("1F",))
    domain = WalkableClearanceDomain.from_surfaces(approved_support, floor=floor, scale=scale,
        policy=policy, expected_source_sha256=SOURCE_SHA256)
    scopes = tuple(scope for scope in resolution.scopes
        if scope.authority == Authority.APPROVED
        and scope.purpose == PhysicalPurpose.KNOWN_COLLISION_PRUNING and scope.floor_ids == ("1F",))
    collision = tuple(CylinderCollisionConsumer.from_provider(provider, scope.scope_id,
                      contract, numerics) for scope in scopes)
    for consumer in collision:
        for _, triangles_m in consumer.meshes:
            triangles_m.flags.writeable = False
        for _, point_m, normal in consumer.floor_planes:
            point_m.flags.writeable = False
            normal.flags.writeable = False
    site_domains = {}
    support_index = {surface.surface_id: surface for surface in approved_support}
    site_reviews = []
    for site, walkable_id in _SITE_SUPPORT.items():
        review = next(row for row in support["walkable_reviews"]
                      if row["walkable_id"] == walkable_id)
        if (review["authority"] != "APPROVED" or review["source_selection_complete"] is not True
                or review["approved_scope"] != "EXACT_SOURCE_SUPPORTED_SUBDOMAIN_ONLY"):
            raise ValueError("PHYSICAL_SOURCE_STALE")
        selected = tuple(support_index[ref] for ref in review["support_surface_ids"])
        site_domains[site] = WalkableClearanceDomain.from_surfaces(
            selected, floor=floor, scale=scale,
            policy=policy, expected_source_sha256=SOURCE_SHA256)
        site_reviews.append({"site_id": site, "walkable_id": walkable_id,
            "support_surface_count": len(selected), "support_area_m2": review["support_area_m2"],
            "full_annotation_supported": review["full_annotation_supported"],
            "source_selection_complete": True,
            "body_or_ceiling_clearance_approved": False})
    collider_ids = {surface.surface_id for consumer in collision for surface, _ in consumer.meshes}
    portal_summary = {"count": len(geometry.portals), "approved_apertures": 0,
        "state": "HUMAN_REVIEW", "actual_clear_width_m": None, "actual_clear_height_m": None,
        "diagnostic_pair_count": portals["pair_count"], "approved_diagnostic_pairs":
        portals["approved_pair_count"], "evidence_sha256": _PINS["portal_review"]}
    if portals["approved_pair_count"] != 0 or any(
        portal.authority == Authority.APPROVED for portal in geometry.portals
    ):
        raise ValueError("PHYSICAL_SOURCE_STALE")
    coverage = {"level": resolution.level.value, "known_collision_scope_count": len(collision),
        "known_collider_component_count": len(collider_ids),
        "approved_support_surface_count": len(approved_support),
        "geometry_surface_count": len(geometry.surfaces), "physical_complete": False,
        "complete_local_scope_count": local["approved_scope_count"],
        "collision_free_certified": False, "body_or_ceiling_clearance_approved": False,
        "wall_or_aperture_completeness_verified": False,
        "source_permission_union_preserves_holes": True,
        "no_name_based_collision": True, "no_aabb_or_hull_as_collider": True,
        "unknowns": ["UNCLASSIFIED_SOURCE_GEOMETRY", "PORTAL_APERTURE_UNAPPROVED",
                     "CEILING_CLEARANCE_UNAPPROVED", "GLOBAL_COMPLETENESS_UNAPPROVED"]}
    evidence = {**_PINS, "geometry_model": model_hash,
        "body_policy_model": content_hash(policy.model_dump(mode="json")),
        "architectural_scale_model": content_hash(scale.model_dump(mode="json")),
        "policy_runtime_model": content_hash(runtime.model_dump(mode="json")),
        "collision_numerics_model": content_hash(numerics.model_dump(mode="json")),
        "support_union": hashlib.sha256(domain.union_wkb).hexdigest()}
    summary = {"schema_version": "workbench.blender-physical-source.v1", "status": "AVAILABLE",
        "source_sha256": SOURCE_SHA256, "geometry_model_sha256": model_hash,
        "evidence_hashes": evidence, "units": "METRES", "native_units": "BLENDER_UNITS",
        "metres_per_blender_unit": scale.metres_per_blender_unit,
        "floor": {"floor_id": "1F",
                  "point": [v * scale.metres_per_blender_unit for v in floor.point],
                  "normal": list(floor.normal), "authority": "APPROVED"},
        "policy": policy.model_dump(mode="json"), "coverage": coverage,
        "portals_summary": portal_summary, "site_support_reviews": site_reviews,
        "agent_used": False, "gt_used": False, "formal_acceptance": False,
        "source_modified": False, "source_copied": False, "opened_blender": False,
        "limitations": ["Known component positives only; no whole-building collision-free claim.",
            "Walkable permission and source support retain holes and source triangle heights.",
            "Portal annotations do not establish actual opening width, height or passage.",
            "Partial model absence never proves clearance; body/ceiling remain unknown."]}
    return PhysicalSourceInputs(SOURCE_SHA256, model_hash, content_hash(summary), evidence,
        contract, numerics, collision, {"1F": domain}, site_domains, portal_summary, coverage,
        _repo=repo, _fingerprints=fingerprints, _summary=summary, _geometry=geometry)


def load_physical_source(repo: Path, site: str) -> PhysicalSourceInputs:
    """Explicit pinned import; site context never crops approved collision inputs."""
    if site not in _SITE_SUPPORT:
        raise ValueError("PHYSICAL_SOURCE_SITE_DENIED")
    root = repo.resolve()
    try:
        fingerprints = {}
        for alias, pin in _PINS.items():
            path = _path(root, alias)
            before = _fingerprint(path)
            if before[0] > 64 * 1024 * 1024 or _file_sha(path) != pin:
                raise ValueError("PHYSICAL_SOURCE_STALE")
            after = _fingerprint(path)
            if before != after:
                raise ValueError("PHYSICAL_SOURCE_STALE")
            fingerprints[alias] = after
        key = str(root), tuple(sorted(fingerprints.items()))
        if key not in _CACHE:
            value = _build(root, fingerprints)
            value.verify()
            if len(_CACHE) >= 2:
                _CACHE.pop(next(iter(_CACHE)))
            _CACHE[key] = value
        result = replace(_CACHE[key], site_id=site)
        result.verify()
        return result
    except (OSError, KeyError, StopIteration, ValueError):
        raise ValueError("PHYSICAL_SOURCE_STALE") from None
