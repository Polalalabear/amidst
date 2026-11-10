"""Office 4.4 -> 8.6 s (FRONT -> blind interval -> REAR) fixture for task K1.

Endpoints come from the existing source observations in the committed workbench
frame-query receipt; the walkable map comes from the approved ``WALK_*`` /
``PORTAL_*`` annotations (interim until K7). Nothing here invents a coordinate or
a path: where the inputs needed for hypotheses do not exist yet, the expected
result is fail-closed ``UNKNOWN``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from shapely.geometry import MultiPoint, Point
from shapely.ops import unary_union

from amidst.blind_hypothesis import (
    REQUEST_SCHEMA,
    floor_map_from_scene_geometry,
    generate_blind_hypotheses,
    verify_output_sha256,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "blind_hypothesis_v1.json"
FIXTURE_PATH = ROOT / "configs" / "office_demo_fixture_v1.json"
FRAME_QUERIES_PATH = (
    ROOT / "data" / "engineering" / "blender_workbench_20261011" / "frame_queries.json"
)
PRESETS_VALIDATION_PATH = ROOT / "docs" / "engineering" / "OFFICE_PRESETS_20261016.json"
SCENE = "blender-office"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def office() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text())
    scene = config["scenes"][SCENE]
    map_cfg = scene["floor_map"]
    geometry_path = ROOT / map_cfg["geometry_ref"]
    geometry = json.loads(geometry_path.read_text())
    floor_map = floor_map_from_scene_geometry(
        geometry,
        geometry_ref=map_cfg["geometry_ref"],
        geometry_sha256=_sha256(geometry_path),
        floor_id=map_cfg["floor_id"],
        metres_per_unit=map_cfg["metres_per_blender_unit"],
        floor_z_m=scene["floor_z_m"],
        walkable_ids=map_cfg["walkable_ids"],
        portal_ids=map_cfg["portal_ids"],
    )
    fixture = json.loads(FIXTURE_PATH.read_text())
    items = json.loads(FRAME_QUERIES_PATH.read_text())["office"]["response"]["items"]
    by_time = {(item["camera_id"], item["timestamp"]): item for item in items}
    return {
        "config": config,
        "config_sha256": _sha256(CONFIG_PATH),
        "geometry": geometry,
        "geometry_sha256": _sha256(geometry_path),
        "floor_map": floor_map,
        "fixture": fixture,
        "start": by_time[("CAM_1F_AUDITORIUM_FRONT", fixture["selected_timestamp"])],
        "end": by_time[("CAM_1F_AUDITORIUM_REAR", fixture["next_observed_timestamp"])],
        "presets": json.loads(PRESETS_VALIDATION_PATH.read_text()),
    }


def test_office_inputs_are_source_bound(office: dict[str, Any]) -> None:
    config, fixture = office["config"], office["fixture"]
    map_cfg = config["scenes"][SCENE]["floor_map"]
    assert office["geometry_sha256"] == map_cfg["geometry_sha256"]
    assert office["geometry"]["source_sha256"] == fixture["source_sha256"]
    assert config["speed_range_m_s"]["source"] == "CONFIGURED_NOT_GT"
    assert config["freeze_status"] == "DRAFT_NOT_FROZEN"

    start, end = office["start"], office["end"]
    assert start["observation_ref"] == fixture["observation_ref"]
    assert (start["timestamp"], end["timestamp"]) == (4.4, 8.6)
    assert end["observation_ref"] == "observation:997166541f223b4f923d8bff"
    for item in (start, end):
        assert item["projection_status"] == "PROJECTED"
        assert item["identity_verdict"] == "UNCONFIRMED"
        assert abs(item["world_position"][2] - office["floor_map"].floor_z_m) < 1e-9


def _office_endpoint(
    item: dict[str, Any], ground_estimate: dict[str, Any] | None
) -> dict[str, Any]:
    return {
        "observation_ref": item["observation_ref"],
        "camera_id": item["camera_id"],
        "timestamp_s": item["timestamp"],
        "evidence_state": "PROJECTED_OBSERVATION",
        "ground_estimate": ground_estimate,
    }


def _unknown_ground_estimate(
    item: dict[str, Any], reason: str, quality: dict[str, Any]
) -> dict[str, Any]:
    """Interval-observation v1 object for an observation the contract marks UNKNOWN."""

    return {
        "schema_version": "office-demo.interval-observation.v1",
        "observation_ref": item["observation_ref"],
        "camera_id": item["camera_id"],
        "timestamp_s": item["timestamp"],
        "status": "UNKNOWN",
        "reason": reason,
        "evidence_state": "PROJECTED_OBSERVATION",
        "estimate_kind": "NONE",
        "basis": "NONE",
        "point_m": None,
        "segment": None,
        "contact_quality": quality,
        "provenance": {"gt_read": False},
    }


def test_office_4_4_to_8_6_fails_closed_without_usable_ground_estimates(
    office: dict[str, Any],
) -> None:
    """Interval observation v1 §4.1: 4.4 s carries AMBIGUOUS_MERGE, so its estimate
    is UNKNOWN/HEAD_ANCHOR_UNRELIABLE. The 8.6 s REAR estimate has not been produced
    (hybrid estimator pending; its contact_quality reasons are UNKNOWN here)."""

    reasons_4_4 = office["presets"]["required_flag_reasons"]["4.4"]
    assert all("AMBIGUOUS_MERGE" in reasons for reasons in reasons_4_4)
    quality = {"version": "rgb-mask-contact-v2", "status": "FLAGGED", "reasons": reasons_4_4[0]}
    start = _office_endpoint(
        office["start"],
        _unknown_ground_estimate(office["start"], "HEAD_ANCHOR_UNRELIABLE", quality),
    )
    end = _office_endpoint(office["end"], None)
    fixture = office["fixture"]
    request = {
        "schema_version": REQUEST_SCHEMA,
        "session_ref": "session:office-k1-fixture",
        "scene_id": SCENE,
        "candidate_ref": None,
        "start": start,
        "end": end,
        "top_k": fixture["top_k"],
        "negative_evidence": [],
        "previous_response_sha256": None,
    }
    response = generate_blind_hypotheses(
        request,
        config=office["config"],
        config_sha256=office["config_sha256"],
        floor_map=office["floor_map"],
        source_binding={
            "run_ref": "UNKNOWN",
            "clock_id": "BLENDER_PILOT_CONFIGURED_SECONDS_5HZ",
            "source_sha256": fixture["source_sha256"],
            "safe_inputs_sha256": fixture["safe_inputs_sha256"],
        },
    )

    assert response["status"] == "UNKNOWN"
    assert response["reason"] == "ENDPOINT_UNUSABLE"
    assert response["hypotheses"] == [] and response["reachable_regions"] == []
    assert {
        "step": "ENDPOINT_REJECTED",
        "endpoint": "start",
        "problem": "GROUND_ESTIMATE_UNKNOWN:HEAD_ANCHOR_UNRELIABLE",
    } in response["trace"]
    assert {
        "step": "ENDPOINT_REJECTED",
        "endpoint": "end",
        "problem": "GROUND_ESTIMATE_NOT_PRODUCED",
    } in response["trace"]
    assert response["interval"]["duration_s"] == 4.2
    assert response["configuration"]["walkable_ref"]["map_kind"] == "ANNOTATION_WALK_PORTAL"
    assert response["configuration"]["walkable_ref"]["sha256"] == office["geometry_sha256"]
    assert response["physical_authority"] == "UNKNOWN"
    assert response["identity_verdict"] == "UNCONFIRMED"
    assert response["provenance"]["gt_read"] is False
    assert verify_output_sha256(response)


def test_office_annotation_map_support_for_existing_projections(office: dict[str, Any]) -> None:
    """Diagnostic only: where the existing v1 projected points sit on the interim
    annotation map. Neither point is a contract endpoint (both are FLAGGED)."""

    floor_map = office["floor_map"]
    start_xy = office["start"]["world_position"][:2]
    end_xy = office["end"]["world_position"][:2]
    assert floor_map.region_at(*start_xy) == "WALK_1F_OFFICE"
    assert floor_map.region_at(*end_xy) is None

    scale = office["config"]["scenes"][SCENE]["floor_map"]["metres_per_blender_unit"]
    obstacle = next(
        s for s in office["geometry"]["surfaces"] if s["surface_id"] == "OBSTACLE_1F_OFFICE_01"
    )
    footprint = MultiPoint([(v[0] * scale, v[1] * scale) for v in obstacle["vertices"]]).convex_hull
    assert footprint.contains(Point(end_xy))
    walkable = unary_union(list(floor_map.regions.values()))
    assert walkable.distance(Point(end_xy)) > 2.5  # measured 2.67 m

    # The office connects to the auditorium and the corridor only through portals.
    assert set(floor_map.portals) == {
        "PORTAL_1F_AUDITORIUM",
        "PORTAL_1F_AUDITORIUM_OFFICE",
        "PORTAL_1F_OFFICE",
    }


def test_office_annotation_gaps_are_reported_not_bridged(office: dict[str, Any]) -> None:
    """K7 cross-check input: annotation surfaces that should meet at a doorway but
    leave a gap no portal footprint covers. The module does not bridge them."""

    regions, portals = office["floor_map"].regions, office["floor_map"].portals
    gaps = {
        ("WALK_1F_AUDITORIUM_OFFICE_THRESHOLD", "WALK_1F_AUDITORIUM"): 0.1235,
        ("WALK_1F_CORRIDOR_03", "WALK_1F_AUDITORIUM_THRESHOLD"): 0.1696,
    }
    for (a, b), expected in gaps.items():
        assert regions[a].distance(regions[b]) == pytest.approx(expected, abs=1e-4)
        assert not any(
            p.intersects(regions[a]) and p.intersects(regions[b]) for p in portals.values()
        )
