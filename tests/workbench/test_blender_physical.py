"""Explicit substitute geometry proves boundaries; never school acceptance evidence."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, replace
from typing import Any

import pytest
from test_blender_association import fixture, gap_input

from amidst.architectural_scale import ArchitecturalScale
from amidst.engineering.registry import content_hash
from amidst.physical_authority import (
    PhysicalAuthorityResolution,
    PhysicalPolicy,
    ReadOnlyPhysicalAuthorityProvider,
    canonical_geometry_sha256,
)
from amidst.physical_collision import CollisionNumerics, CylinderCollisionConsumer
from amidst.physical_policy_contract import PhysicalPolicyContract, PhysicalPolicyRuntime
from amidst.scene_geometry import (
    Authority,
    FloorAuthority,
    GeometryRole,
    GeometrySupport,
    GeometrySurface,
    SceneGeometrySnapshot,
)
from amidst.walkable_clearance import WalkableClearanceDomain
from amidst.workbench.blender_association import BaselineAssociationIndex
from amidst.workbench.blender_physical import BlenderPhysicalIndex

Json = dict[str, Any]
SOURCE = "1" * 64
APPROVAL = "SUBSTITUTE_GEOMETRY_ONLY_NOT_SCHOOL_APPROVAL"


def wall(*, x: float = 0, low: float = -5, high: float = 5, label: str = "wall") -> Json:
    return {
        "surface_id": label,
        "source_object_id": "SUBSTITUTE_ANALYTIC_WALL",
        "source_face_indices": [0, 1],
        "role": "WALL",
        "floor_ids": ["1F"],
        "vertices": [[x, low, -1.0], [x, high, -1.0], [x, high, 4.0], [x, low, 4.0]],
        "triangles": [[0, 1, 2], [0, 2, 3]],
        "semantic_authority": "APPROVED",
        "physical_authority": "APPROVED",
        "support": "SURFACE",
        "blocks_movement": True,
        "approval_id": APPROVAL,
        "evidence_ids": ["SUBSTITUTE_DECLARED_COMPONENT"],
    }


def contract(ratio: float = 1) -> PhysicalPolicyContract:
    policy = PhysicalPolicy(
        policy_id="substitute-cylinder",
        config_version="substitute-only-v1",
        authority=Authority.APPROVED,
        body_model="UPRIGHT_CYLINDER",
        trajectory_reference="FLOOR_CONTACT_POINT",
        body_radius_m=0.30,
        body_height_m=1.70,
        body_clearance_m=0.05,
        portal_horizontal_clearance_m=0.05,
        portal_vertical_clearance_m=0.10,
        collision_tolerance_m=0.001,
        clearance_comparison="MINIMUM_INCLUSIVE",
        collision_comparison="CONTACT_INCLUSIVE",
        approval_id=APPROVAL,
        evidence_ids=("SUBSTITUTE_POLICY",),
    )
    scale = ArchitecturalScale(
        source_asset_sha256=SOURCE,
        metres_per_blender_unit=ratio,
        authority=Authority.APPROVED,
        approval_id=APPROVAL,
        evidence_ids=("SUBSTITUTE_SCALE",),
    )
    runtime = PhysicalPolicyRuntime(
        source_asset_sha256=SOURCE,
        authority="APPROVED",
        approval_id=APPROVAL,
        policy_config="substitute-policy",
        architectural_scale_config="substitute-scale",
        legal_support_contact="APPROVED_SUPPORT_ONLY",
        portal_clearance_combination="MAXIMUM",
        stair_direction="BIDIRECTIONAL",
        navigation_allowed_roles=("WALKABLE", "STAIR"),
        navigation_outside_approved_support="FORBIDDEN",
        walkable_representation="RAW_SUPPORT_SURFACE",
        footprint_preprocess="UNION_THEN_EROSION",
    )
    return PhysicalPolicyContract(policy, scale, runtime)


@dataclass(frozen=True)
class SubstituteSource:
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
    site_id: str | None = "site-one"

    def verify(self) -> None:
        pass

    def public_snapshot(self) -> Json:
        return {
            "data_status": "SUBSTITUTE",
            "coverage": self.coverage,
            "source_sha256": self.source_sha256,
            "portals": self.portals_summary,
        }


def source(
    walls: list[Json] | None = None,
    *,
    ratio: float = 1,
    support: bool = True,
    extent: float = 10,
    max_triangles: int = 64,
) -> SubstituteSource:
    policy = contract(ratio)
    floor = FloorAuthority(
        floor_id="1F",
        point=(0.0, 0.0, 0.0),
        normal=(0.0, 0.0, 1.0),
        authority=Authority.APPROVED,
        approval_id=APPROVAL,
        evidence_ids=("SUBSTITUTE_FLOOR",),
    )
    native = copy.deepcopy(walls or [])
    for row in native:
        row["vertices"] = [[v / ratio for v in p] for p in row["vertices"]]
    model = SceneGeometrySnapshot.model_validate_json(
        json.dumps(
            {
                "source_sha256": SOURCE,
                "scene_id": "SUBSTITUTE_ONLY",
                "unit_scale_m": ratio,
                "scale_authority": "APPROVED",
                "scale_approval_id": APPROVAL,
                "surfaces": native,
                "floors": [floor.model_dump(mode="json")],
            }
        )
    )
    digest = canonical_geometry_sha256(model)
    numerics = CollisionNumerics(
        distance_error_budget_m=1e-9,
        maximum_distance_iterations=128,
        maximum_triangles_per_segment=max_triangles,
    )
    consumers = ()
    if walls:
        resolution = PhysicalAuthorityResolution.model_validate_json(
            json.dumps(
                {
                    "source_sha256": SOURCE,
                    "geometry_sha256": digest,
                    "level": "PARTIAL_APPROVED",
                    "policy": policy.policy.model_dump(mode="json"),
                    "scopes": [
                        {
                            "scope_id": "substitute-known-components",
                            "purpose": "KNOWN_COLLISION_PRUNING",
                            "floor_ids": ["1F"],
                            "surface_ids": [row["surface_id"] for row in walls],
                            "coverage": "PARTIAL",
                            "authority": "APPROVED",
                            "approval_id": APPROVAL,
                            "evidence_ids": ["SUBSTITUTE_SCOPE"],
                        }
                    ],
                }
            )
        )
        provider = ReadOnlyPhysicalAuthorityProvider(model, resolution, SOURCE, digest)
        consumers = (
            CylinderCollisionConsumer.from_provider(
                provider, "substitute-known-components", policy, numerics
            ),
        )
    domains = {}
    if support:
        surface = GeometrySurface(
            surface_id="substitute-support",
            source_object_id="SUBSTITUTE_SUPPORT",
            source_face_indices=(0, 1),
            role=GeometryRole.WALKABLE,
            floor_ids=("1F",),
            vertices=tuple(
                (x / ratio, y / ratio, 0.0)
                for x, y in (
                    (-extent, -extent),
                    (extent, -extent),
                    (extent, extent),
                    (-extent, extent),
                )
            ),
            triangles=((0, 1, 2), (0, 2, 3)),
            semantic_authority=Authority.APPROVED,
            physical_authority=Authority.APPROVED,
            support=GeometrySupport.SURFACE,
            approval_id=APPROVAL,
            evidence_ids=(f"SOURCE_SHA256:{SOURCE}",),
        )
        domains["1F"] = WalkableClearanceDomain.from_surfaces(
            (surface,),
            floor=floor,
            scale=policy.scale,
            policy=policy.policy,
            expected_source_sha256=SOURCE,
        )
    return SubstituteSource(
        SOURCE,
        digest,
        content_hash([digest, ratio, extent, support]),
        {"substitute_geometry": digest},
        policy,
        numerics,
        consumers,
        domains,
        {"site-one": domains["1F"]} if domains else {},
        {"approved_apertures": 0, "status": "HUMAN_REVIEW"},
        {"partial": True, "complete_body_clearance": False},
    )


def run(snapshot: Json, physical_source: SubstituteSource | None, top_k: int = 3) -> Json:
    base = BaselineAssociationIndex(snapshot)
    index = BlenderPhysicalIndex(base, physical_source)
    return index.reconstruct(base._cameras, *base._full["source_time_range"], top_k)


def crossing(*, right: float = 0.6, y: float = 0) -> Json:
    return fixture(
        [
            ("A", "a", {0: [-1.2, y, 0], 0.2: [-1.0, y, 0]}),
            ("B", "b", {right: [1.0, y, 0], right + 0.2: [1.2, y, 0]}),
        ]
    )


def codes(candidate: Json, field: str = "checks") -> set[str]:
    return {row["code"] for row in candidate["physical"][field]}


def test_continuous_short_cross_camera_wall_rejects_only_linked_hypothesis() -> None:
    result = run(crossing(), source([wall()]), 5)
    assert result["status"] == "ALL_CANDIDATES_REJECTED"
    assert not result["candidates"]
    assert result["search"]["considered"] == 2 and result["search"]["rejected"] == 1
    rejected = result["rejected_candidates"][0]
    assert "COLLISION_CONTACT" in codes(rejected, "reasons")
    assert rejected["physical"]["evidence_counts"]["known_collision_rejections"] > 0
    assert result["baseline_candidate"]["physical"]["verdict"] == "UNKNOWN"
    assert not result["baseline_candidate"]["selected_edge_refs"]


def test_actual_component_opening_keeps_doorway_hypothesis_without_aperture_approval() -> None:
    opening = [wall(high=-1.0, label="lower"), wall(low=1.0, label="upper")]
    result = run(crossing(), source(opening))
    assert result["status"] == "READY" and len(result["candidates"]) == 1
    candidate = result["candidates"][0]
    assert candidate["physical"]["verdict"] == "UNKNOWN"
    assert not candidate["physical"]["reasons"]
    assert candidate["physical"]["evidence_counts"]["supported_intervals"] > 0
    assert result["geometry_context"]["portals"]["approved_apertures"] == 0
    assert not candidate["physical"]["complete_physical_validation"]


def test_long_missing_gap_never_sweeps_chord_through_known_wall() -> None:
    result = run(crossing(right=2), source([wall()]))
    assert not result["rejected_candidates"]
    candidate = result["candidates"][0]
    gap = next(
        row
        for row in candidate["physical"]["unknowns"]
        if row["code"] == "MISSING_GAP_ROUTE_UNOBSERVED"
    )["sample_checks"][0]
    assert gap["chord_collision_tested"] is False
    assert gap["minimum_time_lower_bound_s"] == 0.25
    assert gap["available_time_s"] == 1.8 and gap["time_lower_bound_satisfied"]
    assert gap["complete_route_authority_available"] is False
    assert any(p["world_position"] is None for p in candidate["paths"][0]["samples"])
    assert all(
        v["time_range"][1] <= 0.2 or v["time_range"][0] >= 2
        for v in candidate["paths"][0]["velocities"]
    )


@pytest.mark.parametrize("extent", [0.5, 1.05])
def test_missing_partial_support_or_clearance_does_not_reject(extent: float) -> None:
    result = run(crossing(), source(extent=extent))
    assert result["candidates"][0]["physical"]["verdict"] == "UNKNOWN"
    assert not result["rejected_candidates"]
    assert codes(result["candidates"][0]) & {
        "OUTSIDE_APPROVED_WALKABLE",
        "INSUFFICIENT_WALKABLE_CLEARANCE",
    }


def test_no_source_is_unknown_and_preserves_association_order_except_separate_baseline() -> None:
    snapshot = gap_input()
    base = BaselineAssociationIndex(snapshot)
    before = base.reconstruct(base._cameras, 0, 0.8, 5)
    index = BlenderPhysicalIndex(base, None)
    after = index.reconstruct(base._cameras, 0, 0.8, 5)
    assert [c["candidate_ref"] for c in after["candidates"]] == [
        c["candidate_ref"] for c in before["candidates"] if c["selected_edge_refs"]
    ]
    assert after["candidates"][0]["score"] == before["candidates"][0]["score"]
    assert "SOURCE_EVIDENCE_UNAVAILABLE" in codes(after["candidates"][0])
    assert after["authority_coverage"]["status"] == "UNAVAILABLE"


def test_connected_path_also_checks_separate_isolated_point_inside_collider() -> None:
    snapshot = fixture(
        [
            ("A", "safe", {0: [-1.0, 0, 0], 0.2: [-1.0, 0.1, 0]}),
            ("B", "isolated", {2.0: [0.0, 0, 0]}),
        ]
    )
    result = run(snapshot, source([wall()]))
    assert result["status"] == "ALL_CANDIDATES_REJECTED"
    candidate = next(c for c in result["rejected_candidates"] if c["selected_edge_refs"])
    assert candidate["physical"]["evidence_counts"]["point_occupancy_checks"] == 1
    assert any(
        check["time_range"] == [2.0, 2.0]
        for row in candidate["physical"]["reasons"]
        for check in row["sample_checks"]
    )


def test_original_overlap_support_inside_collider_is_not_hidden_by_clear_primary() -> None:
    snapshot = fixture(
        [
            ("A", "a", {0: [0.6, 0, 0], 0.2: [0.6, 0.1, 0]}),
            ("B", "b", {0.2: [0.2, 0.1, 0]}),
        ]
    )
    result = run(snapshot, source([wall()]))
    associated = next(c for c in result["rejected_candidates"] if c["selected_edge_refs"])
    assert associated["physical"]["evidence_counts"]["point_occupancy_checks"] == 1
    assert any(
        check.get("point_basis") == "ORIGINAL_OVERLAP_SUPPORT"
        for row in associated["physical"]["reasons"]
        for check in row["sample_checks"]
    )
    support = [p for path in associated["paths"] for p in path["samples"] if p["overlap_support"]]
    assert support[0]["world_position"][0] == 0.6
    assert support[0]["overlap_support"][0]["world_position"][0] == 0.2


def test_collision_numeric_budget_refuses_validation_without_false_rejection() -> None:
    snapshot = fixture([("A", "a", {0: [0.0, 0.0, 0.0], 0.2: [0.0, 0.0, 0.0]})])
    result = run(snapshot, source([wall(x=0.34, low=0.34, high=0.5)], max_triangles=1))
    assert result["candidates"] and not result["rejected_candidates"]
    assert "COLLISION_TRIANGLE_BUDGET_EXCEEDED" in codes(result["candidates"][0])


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("source_sha256", "2" * 64, "SOURCE_SCOPE_MISMATCH"),
        ("geometry_model_sha256", "2" * 64, "COLLIDER_SCOPE_MISMATCH"),
        ("physical_source_sha256", "invalid", "DIGEST_REQUIRED"),
    ],
)
def test_source_and_geometry_binding_fail_closed(field: str, value: str, message: str) -> None:
    item = replace(source([wall()]), **{field: value})
    with pytest.raises(ValueError, match=message):
        BlenderPhysicalIndex(BaselineAssociationIndex(crossing()), item)


def test_public_metadata_poison_is_refused() -> None:
    item = replace(source(), coverage={"ground_truth": {"label": "secret"}})
    with pytest.raises(ValueError, match="PUBLIC_METADATA_INVALID"):
        BlenderPhysicalIndex(BaselineAssociationIndex(gap_input()), item)


def test_wrong_floor_support_and_scale_are_refused() -> None:
    item = source()
    bad_floor = item.support_domains["1F"].floor.model_copy(update={"floor_id": "2F"})
    bad = replace(item.support_domains["1F"], floor=bad_floor)
    with pytest.raises(ValueError, match="SUPPORT_SCOPE_MISMATCH"):
        BlenderPhysicalIndex(
            BaselineAssociationIndex(gap_input()), replace(item, support_domains={"1F": bad})
        )
    with pytest.raises(ValueError, match="SUPPORT_SCOPE_MISMATCH"):
        BlenderPhysicalIndex(
            BaselineAssociationIndex(gap_input()), replace(item, contract=contract(0.0247))
        )


def test_metres_conversion_once_keeps_same_collision_and_display() -> None:
    a = run(crossing(), source([wall()], ratio=1))
    b = run(crossing(), source([wall()], ratio=0.0247))
    assert a["search"]["rejected"] == b["search"]["rejected"] == 1
    for one, two in zip(
        a["geometry_context"]["support_polygons"][0]["exterior"],
        b["geometry_context"]["support_polygons"][0]["exterior"],
        strict=True,
    ):
        assert one == pytest.approx(two)


def test_full_pool_can_promote_candidate_not_in_old_top_five() -> None:
    ys = [-2.0, -0.7, 0.7, 2.0]
    snapshot = fixture(
        [
            *[("A", str(i), {0: [-2.0, y, 0], 0.2: [-2.0, y, 0]}) for i, y in enumerate(ys)],
            *[("B", str(i), {1.0: [2.0, y, 0], 1.2: [2.0, y, 0]}) for i, y in enumerate(ys)],
        ]
    )
    obstacles = [wall(low=y - 0.025, high=y + 0.025, label=str(i)) for i, y in enumerate(ys)]
    result = run(snapshot, source(obstacles), 5)
    assert result["search"]["considered"] > 5
    assert len(result["decision_ledger"]) == result["search"]["considered"]
    assert result["search"]["old_top_k_pool_only"] is False
    assert result["search"]["rejected"] > 5
    assert result["search"]["rejected_curves_truncated"]
    assert len(result["rejected_candidates"]) == 5
    assert any(c["original_rank"] > 5 for c in result["candidates"])
    assert all(c["physical"]["verdict"] != "REJECTED" for c in result["candidates"])
    assert len({c["candidate_ref"] for c in result["candidates"]}) == len(result["candidates"])


def test_baseline_does_not_displace_associated_unknown_candidates_by_gap_penalty() -> None:
    result = run(crossing(right=2), source())
    assert all(c["selected_edge_refs"] for c in result["candidates"])
    assert result["baseline_candidate"]["is_unassociated_baseline"]
    assert not result["search"]["unassociated_baseline_in_ranking"]


def test_narrow_window_and_single_camera_do_not_change_canonical_refs_or_scores() -> None:
    base = BaselineAssociationIndex(crossing())
    index = BlenderPhysicalIndex(base, source())
    full = index.reconstruct(["A", "B"], 0, 0.8, 3)
    narrow = index.reconstruct(["B", "A"], 0.2, 0.6, 1)
    index.reconstruct(["A"], 0, 0.2, 3)
    again = index.reconstruct(["A", "B"], 0, 0.8, 3)
    assert full == again
    assert full["physical_sha256"] == narrow["physical_sha256"]
    assert full["decision_ledger_sha256"] == narrow["decision_ledger_sha256"]
    assert full["candidates"][0]["candidate_ref"] == narrow["candidates"][0]["candidate_ref"]
    assert full["candidates"][0]["physical"] == narrow["candidates"][0]["physical"]
    assert all(
        0.2 <= p["timestamp"] <= 0.6
        for path in narrow["candidates"][0]["paths"]
        for p in path["samples"]
    )
    assert narrow["retrieval"]["physical_checks_at_query"] == 0


def test_original_association_index_and_search_counter_are_immutable() -> None:
    base = BaselineAssociationIndex(gap_input())
    before = base.reconstruct(["A", "B"], 0, 0.8, 5)
    counter = base._route_prefix_rejections
    BlenderPhysicalIndex(base, source())
    assert base.reconstruct(["A", "B"], 0, 0.8, 5) == before
    assert base._route_prefix_rejections == counter


@pytest.mark.parametrize(
    "cameras,start,end,k",
    [
        (["missing"], 0, 0.8, 3),
        (["A"], float("nan"), 0.8, 3),
        (["A"], 0, float("inf"), 3),
        (["A"], 0, 0.8, 0),
        (["A"], 0, 0.8, 6),
        (["A"], 0, 0.8, True),
    ],
)
def test_query_scope_numeric_and_top_k_budgets_are_validated(
    cameras: list[str],
    start: float,
    end: float,
    k: int,
) -> None:
    index = BlenderPhysicalIndex(BaselineAssociationIndex(gap_input()), None)
    with pytest.raises(ValueError):
        index.reconstruct(cameras, start, end, k)


def test_checks_are_compact_and_hash_bound_without_hiding_occurrence_counts() -> None:
    result = run(
        fixture([("A", "a", {round(i * 0.2, 2): [1.0, 1.0, 0] for i in range(20)})]), source()
    )
    physical = result["candidates"][0]["physical"]
    assert physical["check_records_count"] > len(physical["checks"])
    assert sum(c["occurrence_count"] for c in physical["checks"]) == physical["check_records_count"]
    assert all(len(c["sample_checks"]) <= 2 for c in physical["checks"])
    assert len(physical["checks_sha256"]) == len(physical["decision_sha256"]) == 64


def test_no_projected_points_returns_no_result_without_fabricated_alternative() -> None:
    for physical_source in (None, source()):
        result = run(fixture([("A", "a", {0: None, 0.2: None})]), physical_source)
        assert result["status"] == "NO_RESULT"
        assert not result["candidates"] and not result["rejected_candidates"]
        assert result["search"]["fabricated_candidates"] is False
        assert result["baseline_candidate"]["physical"]["verdict"] == "UNKNOWN"
        assert "NO_USABLE_PROJECTED_BODY_EVIDENCE" in codes(result["baseline_candidate"])
        assert all(row["verdict"] == "UNKNOWN" for row in result["decision_ledger"])
        if physical_source is None:
            assert "SOURCE_EVIDENCE_UNAVAILABLE" in codes(result["baseline_candidate"])


def test_source_verified_each_query_without_rechecking_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []
    monkeypatch.setattr(SubstituteSource, "verify", lambda _: calls.append(True))
    index = BlenderPhysicalIndex(BaselineAssociationIndex(gap_input()), source())
    before = len(calls)
    monkeypatch.setattr(
        WalkableClearanceDomain,
        "validate_segment",
        lambda *_: pytest.fail("geometry recomputed at query"),
    )
    index.reconstruct(["A", "B"], 0, 0.8)
    assert len(calls) == before + 1


def test_beam_pool_truncation_and_global_optimality_are_explicit() -> None:
    ys = [-2.0, -1.0, 0.0, 1.0, 2.0]
    snapshot = fixture(
        [
            *[("A", str(i), {0: [-2.0, y, 0], 0.2: [-2.0, y, 0]}) for i, y in enumerate(ys)],
            *[("B", str(i), {1.0: [2.0, y, 0], 1.2: [2.0, y, 0]}) for i, y in enumerate(ys)],
        ]
    )
    result = run(snapshot, None, 5)
    assert result["search"]["considered"] == 256
    assert result["search"]["truncated"] and not result["search"]["complete"]
    assert result["search"]["score_optimality"] == "BOUNDED_POOL_NOT_GLOBALLY_CERTIFIED"
    assert len(result["decision_ledger"]) == 256
    assert len(result["candidates"]) == 5
    assert not result["baseline_candidate"]["selected_edge_refs"]


def test_ledger_declares_all_reranks_and_baseline_is_not_silently_ranked() -> None:
    result = run(crossing(), source())
    for candidate in result["candidates"]:
        row = next(
            r for r in result["decision_ledger"] if r["candidate_ref"] == candidate["candidate_ref"]
        )
        assert row["rerank"] == candidate["rank"] and row["selected_for_ranking"]
    baseline = next(r for r in result["decision_ledger"] if r["is_unassociated_baseline"])
    assert baseline["rerank"] is None and not baseline["selected_for_ranking"]


def test_wrong_site_and_nonfinite_metadata_are_refused() -> None:
    base = BaselineAssociationIndex(gap_input())
    with pytest.raises(ValueError, match="SOURCE_SITE_MISMATCH"):
        BlenderPhysicalIndex(base, replace(source(), site_id="other-site"))
    with pytest.raises(ValueError, match="PUBLIC_METADATA_INVALID"):
        BlenderPhysicalIndex(base, replace(source(), coverage={"score": float("nan")}))


def test_gt_poison_never_changes_physical_rank_hash_or_output() -> None:
    snapshot = gap_input()
    poison = copy.deepcopy(snapshot)
    poison["ground_truth"] = {"identity": "secret", "path": "/private/hidden.blend"}
    poison["actor_trajectory"] = [{"speed": 999}]
    for measurement in poison["measurements"]:
        measurement["secret_gt"] = "secret"
    expected, actual = run(snapshot, source()), run(poison, source())
    assert expected == actual
    assert "secret" not in json.dumps(actual)


def test_checks_budget_leaves_unknown_instead_of_claiming_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("amidst.workbench.blender_physical.MAX_CHECKS", 1)
    result = run(
        fixture([("A", "a", {0: [0.0, 0.0, 0.0], 0.2: [0.2, 0.0, 0.0], 0.4: [0.4, 0.0, 0.0]})]),
        source(),
    )
    assert "PHYSICAL_CHECK_BUDGET" in codes(result["candidates"][0])
    assert result["candidates"][0]["physical"]["verdict"] == "UNKNOWN"
    assert not result["candidates"][0]["physical"]["complete_physical_validation"]


def test_stale_source_is_refused_at_query(monkeypatch: pytest.MonkeyPatch) -> None:
    index = BlenderPhysicalIndex(BaselineAssociationIndex(gap_input()), source())

    def stale(_: SubstituteSource) -> None:
        raise ValueError("PHYSICAL_SOURCE_STALE")

    monkeypatch.setattr(SubstituteSource, "verify", stale)
    with pytest.raises(ValueError, match="SOURCE_STALE"):
        index.reconstruct(["A", "B"], 0, 0.8)


def test_ledger_sums_same_reason_across_distinct_geometry_scopes() -> None:
    item = source([wall(x=-0.5, label="left"), wall(x=0.5, label="right")])
    original = item.collision_consumers[0]
    split = []
    for surface in original.inputs.surfaces:
        scope = original.inputs.scope.model_copy(
            update={
                "scope_id": "substitute-scope-" + surface.surface_id,
                "surface_ids": (surface.surface_id,),
            }
        )
        inputs = replace(original.inputs, scope=scope, surfaces=(surface,))
        split.append(CylinderCollisionConsumer(inputs, item.contract, item.numerics))
    item = replace(item, collision_consumers=tuple(split))
    snapshot = fixture([("A", "a", {0: [-2.0, 0.0, 0.0], 0.8: [2.0, 0.0, 0.0]})])
    result = run(snapshot, item)
    assert result["status"] == "ALL_CANDIDATES_REJECTED"
    candidate = result["rejected_candidates"][0]
    collisions = [
        row for row in candidate["physical"]["reasons"] if row["code"] == "COLLISION_CONTACT"
    ]
    assert len({row["geometry_ref"] for row in collisions}) == 2
    expected = sum(row["occurrence_count"] for row in collisions)
    assert expected >= 2
    ledger = next(
        row
        for row in result["decision_ledger"]
        if row["candidate_ref"] == candidate["candidate_ref"]
    )
    assert ledger["reason_codes"]["COLLISION_CONTACT"] == expected


def test_original_secondary_connected_segment_cannot_hide_crossing_between_clear_points() -> None:
    snapshot = fixture(
        [
            (
                "A",
                "primary",
                {0: [-0.36, 0.0, 0.0], 0.2: [-0.36, 0.0, 0.0], 0.4: [-0.36, 0.0, 0.0]},
            ),
            ("B", "secondary", {0: [-0.36, 0.0, 0.0], 0.2: [0.36, 0.0, 0.0]}),
        ]
    )
    item = source([wall()])
    assert (
        item.collision_consumers[0].validate(((-0.36, 0.0, 0.0), (0.36, 0.0, 0.0))).state
        == "REJECTED"
    )
    result = run(snapshot, item)
    associated = next(row for row in result["rejected_candidates"] if row["selected_edge_refs"])
    counts = associated["physical"]["evidence_counts"]
    assert counts["secondary_connected_intervals"] == 1
    assert counts["secondary_known_collision_rejections"] == 1
    assert counts["connected_intervals"] == 2
    assert associated["physical"]["scores"]["support_evidence_bonus"] == 0.25
    assert any(
        check.get("check_basis") == "ORIGINAL_SECONDARY_CONNECTED_SEGMENT"
        and check["time_range"] == [0.0, 0.2]
        for row in associated["physical"]["reasons"]
        for check in row["sample_checks"]
    )
    assert all(p["world_position"][0] == -0.36 for p in associated["paths"][0]["samples"])
    assert result["baseline_candidate"]["physical"]["verdict"] == "REJECTED"
