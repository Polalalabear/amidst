"""Independent tiny source fixtures; no school approval or Blender process claimed."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest
from shapely import from_wkb

from amidst.physical_authority import canonical_geometry_sha256
from amidst.scene_geometry import SceneGeometrySnapshot
from amidst.workbench import blender_physical_source as source

Json = dict[str, Any]
SOURCE = "c" * 64
APPROVAL = "SYNTHETIC_SOURCE_TEST_ONLY_NOT_SCHOOL_AUTHORITY"


@pytest.fixture
def physical_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    policy = {"policy_id": "synthetic-cylinder", "config_version": "test",
        "authority": "APPROVED", "body_model": "UPRIGHT_CYLINDER",
        "trajectory_reference": "FLOOR_CONTACT_POINT", "body_radius_m": .3,
        "body_height_m": 1.7, "body_clearance_m": .05,
        "portal_horizontal_clearance_m": .05, "portal_vertical_clearance_m": .1,
        "collision_tolerance_m": .001, "clearance_comparison": "MINIMUM_INCLUSIVE",
        "collision_comparison": "CONTACT_INCLUSIVE", "approval_id": APPROVAL,
        "evidence_ids": ["SYNTHETIC_POLICY"]}
    ratio = .0247
    # Exact ring triangles; the central 2x2 metre hole must never be filled.
    points_m = [[0, 0, .494], [10, 0, .494], [10, 10, .494], [0, 10, .494],
                [4, 4, .494], [6, 4, .494], [6, 6, .494], [4, 6, .494]]
    triangles = [[0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                 [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]]
    support = {"surface_id": "source-ring", "source_object_id": "not-a-role-name",
        "source_face_indices": list(range(8)), "role": "WALKABLE", "floor_ids": ["1F"],
        "vertices": [[v / ratio for v in p] for p in points_m], "triangles": triangles,
        "semantic_authority": "APPROVED", "physical_authority": "APPROVED",
        "support": "SURFACE", "approval_id": APPROVAL,
        "evidence_ids": ["SOURCE_SHA256:" + SOURCE]}
    cube = {"surface_id": "source-solid", "source_object_id": "door-walkable-misleading-name",
        "source_face_indices": [0, 1, 2, 3], "role": "OBSTACLE", "floor_ids": ["1F"],
        "vertices": [[100, 100, 20], [110, 100, 20], [100, 110, 20], [100, 100, 40]],
        "triangles": [[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]],
        "semantic_authority": "APPROVED", "physical_authority": "APPROVED", "support": "VOLUME",
        "approval_id": APPROVAL, "evidence_ids": ["SYNTHETIC_EXACT_SOURCE"],
        "blocks_movement": True}
    geometry = {"source_sha256": SOURCE, "scene_id": "SYNTHETIC_ONLY", "unit_scale_m": ratio,
        "scale_authority": "APPROVED", "scale_approval_id": APPROVAL, "physical_complete": False,
        "floors": [{"floor_id": "1F", "point": [0, 0, 20], "normal": [0, 0, 1],
                    "authority": "APPROVED", "approval_id": APPROVAL,
                    "evidence_ids": ["SYNTHETIC_SOURCE_FLOOR"]}], "surfaces": [support, cube]}
    model_hash = canonical_geometry_sha256(SceneGeometrySnapshot.model_validate_json(
        json.dumps(geometry)))
    resolution = {"source_sha256": SOURCE, "geometry_sha256": model_hash,
        "level": "PARTIAL_APPROVED", "policy": policy, "scopes": [{"scope_id": "known-solid",
            "purpose": "KNOWN_COLLISION_PRUNING", "floor_ids": ["1F"],
            "surface_ids": ["source-solid"], "coverage": "PARTIAL", "authority": "APPROVED",
            "approval_id": APPROVAL, "evidence_ids": ["SYNTHETIC_SOURCE_SCOPE"]}]}
    floor_support = {"source_sha256": SOURCE, "walkable_reviews": [{
        "walkable_id": name, "authority": "APPROVED", "source_selection_complete": True,
        "approved_scope": "EXACT_SOURCE_SUPPORTED_SUBDOMAIN_ONLY",
        "support_surface_ids": ["source-ring"], "support_area_m2": 96,
        "full_annotation_supported": True} for name in source._SITE_SUPPORT.values()]}
    values = {"geometry_archive": geometry, "authority_resolution": resolution,
        "floor_support": floor_support,
        "portal_review": {"source_sha256": SOURCE, "pair_count": 0, "approved_pair_count": 0},
        "local_scope_review": {"source_sha256": SOURCE, "approved_scope_count": 0},
        "source_archive": {"source_sha256": SOURCE, "private_locator": "/private/fake.blend"},
        "architectural_scale": {"source_asset_sha256": SOURCE,
            "metres_per_blender_unit": ratio, "authority": "APPROVED", "approval_id": APPROVAL,
            "evidence_ids": ["SYNTHETIC_SCALE"]},
        "body_policy": policy,
        "policy_runtime": {"source_asset_sha256": SOURCE, "authority": "APPROVED",
            "approval_id": APPROVAL, "policy_config": source._PATHS["body_policy"],
            "architectural_scale_config": source._PATHS["architectural_scale"],
            "legal_support_contact": "APPROVED_SUPPORT_ONLY",
            "portal_clearance_combination": "MAXIMUM", "stair_direction": "BIDIRECTIONAL",
            "navigation_allowed_roles": ["WALKABLE", "STAIR"],
            "navigation_outside_approved_support": "FORBIDDEN",
            "walkable_representation": "RAW_SUPPORT_SURFACE",
            "footprint_preprocess": "UNION_THEN_EROSION"},
        "collision_numerics": {"distance_error_budget_m": 1e-10,
            "maximum_distance_iterations": 128, "maximum_triangles_per_segment": 25000}}
    pins = {}
    for alias, value in values.items():
        path = repo / source._PATHS[alias]
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(value, sort_keys=True).encode()
        if path.suffix == ".gz":
            raw = gzip.compress(raw, mtime=0)
        path.write_bytes(raw)
        pins[alias] = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(source, "_PINS", pins)
    monkeypatch.setattr(source, "SOURCE_SHA256", SOURCE)
    source._CACHE.clear()
    return repo


def test_exact_source_roles_scaled_once_holes_and_local_context(physical_repo: Path) -> None:
    inputs = source.load_physical_source(physical_repo, "office")
    domain = inputs.support_domains["1F"]
    assert len(inputs.collision_consumers) == 1
    assert len(inputs.collision_consumers[0].meshes) == 1
    assert inputs.collision_consumers[0].meshes[0][0].role.value == "OBSTACLE"
    assert inputs.collision_consumers[0].meshes[0][0].source_object_id.startswith("door-walkable")
    assert not inputs.collision_consumers[0].meshes[0][1].flags.writeable
    assert domain.required_clearance_m == .35
    assert len(from_wkb(domain.union_wkb).interiors) == 1
    dto = inputs.export_safe_inputs()
    ring = next(r for r in dto["surfaces"] if r["surface_id"] == "source-ring")
    assert ring["vertices"][1] == [10.0, 0.0, .494]
    assert ring["triangles"] == [list(t) for t in domain.support_surfaces[0].triangles]
    assert dto["geometry_is_partial"] is True
    summary = inputs.public_summary()
    assert summary["coverage"]["physical_complete"] is False
    assert summary["coverage"]["collision_free_certified"] is False
    display = summary["physical_presentation"]
    assert len(display["outlines"][0]["holes"]) == 1
    assert display["units"] == "METRES" and display["display_only"] is True
    assert summary["site_context"]["collision_scope_restricted_by_site_box"] is False
    assert summary["portals_summary"]["approved_apertures"] == 0
    assert all(s not in json.dumps(dto) for s in (
        "/private/", "private_locator", "ground_truth", "TrajectoryID",
        "local_path", "relative_path"))


def test_queries_do_not_decode_sources_or_large_raw_archives(
    physical_repo: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = source.load_physical_source(physical_repo, "office")

    def no_decode(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("query attempted source JSON decode")

    monkeypatch.setattr(source, "_pinned_json", no_decode)
    inputs.verify()
    assert inputs.public_summary()["status"] == "AVAILABLE"
    other = source.load_physical_source(physical_repo, "classroom101")
    assert other.physical_source_sha256 == inputs.physical_source_sha256
    assert other.collision_consumers is inputs.collision_consumers


@pytest.mark.parametrize("alias", ["architectural_scale", "body_policy", "policy_runtime",
                                  "floor_support", "geometry_archive"])
def test_changed_pin_refused_without_source_refresh(
    physical_repo: Path, alias: str,
) -> None:
    inputs = source.load_physical_source(physical_repo, "office")
    path = physical_repo / source._PATHS[alias]
    before = path.stat()
    raw = path.read_bytes()
    path.write_bytes(raw + b"changed")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises(ValueError, match="PHYSICAL_SOURCE_STALE"):
        inputs.verify()
    with pytest.raises(ValueError, match="PHYSICAL_SOURCE_STALE"):
        source.load_physical_source(physical_repo, "office")


def test_symlink_and_foreign_site_rejected(physical_repo: Path) -> None:
    inputs = source.load_physical_source(physical_repo, "office")
    path = physical_repo / source._PATHS["portal_review"]
    backup = path.with_suffix(".original")
    path.rename(backup)
    path.symlink_to(backup)
    with pytest.raises(ValueError, match="PHYSICAL_SOURCE_STALE"):
        inputs.verify()
    with pytest.raises(ValueError, match="PHYSICAL_SOURCE_SITE_DENIED"):
        source.load_physical_source(physical_repo, "unknown")


def test_public_copy_and_mutated_contract_evidence_refused(physical_repo: Path) -> None:
    inputs = source.load_physical_source(physical_repo, "office")
    public = inputs.public_summary()
    public["coverage"]["physical_complete"] = True
    assert inputs.public_summary()["coverage"]["physical_complete"] is False
    inputs.evidence_hashes["body_policy"] = "f" * 64
    with pytest.raises(ValueError, match="PHYSICAL_SOURCE_STALE"):
        inputs.verify()
