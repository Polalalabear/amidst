"""Bounded hybrid point/interval geometry and fail-closed evidence boundaries."""

import copy
import math
from dataclasses import replace

import pytest
from shapely.geometry import box

from amidst.domain.camera import Camera
from amidst.domain.geometry import Plane
from amidst.engineering.hybrid_contact import SourceClip, estimate_contact, k1_endpoint_eligibility
from amidst.engineering.perception_v2 import pixel_sensitivity, project_pixel
from amidst.engineering.registry import content_hash
from amidst.geometry.inverse_projection import InverseProjectionService


@pytest.fixture
def inputs():
    angle = math.pi / 6
    c, s = math.cos(angle), math.sin(angle)
    camera = Camera(
        camera_id="C",
        camera_to_world=((1, 0, 0, 0), (0, c, -s, 0), (0, s, c, 4), (0, 0, 0, 1)),
        fx=100,
        fy=100,
        cx=50,
        cy=50,
        width=100,
        height=100,
    )
    plane = Plane(plane_id="floor", point=(0, 0, 0), normal=(0, 0, 1), floor_id="1F")
    observation = {
        "observation_ref": "observation:one",
        "camera_id": "C",
        "timestamp": 1.2,
        "contact_pixel": [50, 79],
        "world_position": [999, 999, 0],
        "state": "MISSING",
    }
    service = InverseProjectionService(camera, plane)
    point = project_pixel(service, (50, 79))
    component = {
        "contact_pixel": [50, 79],
        "bbox_xyxy": [48, 50, 53, 80],
        "world_position": list(point.world_position),
    }
    quality = {
        "version": "rgb-mask-contact-v2",
        "status": "FLAGGED",
        "reasons": ["CONTACT_OCCLUDED"],
        "pixel_sensitivity_m": pixel_sensitivity(service, (50, 79))["max_displacement_m"],
        "authority": "QUALITY_FLAG_ONLY_POSITION_UNCHANGED",
    }
    declaration = {
        "declaration_source": "PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT",
        "declaration_ref": "setting:test",
        "target_proxy": {
            "shape": "CYLINDER",
            "height_m": 1.7,
            "radius_m": 0.25,
            "label": "SYNTHETIC_CYLINDER_PERSON_SIZED",
        },
        "head_height_prior": {"nominal_m": 1.7, "tolerance_m": 0.1},
        "body_radius_m": 0.25,
        "foot_anchor_band_px": 2,
    }
    config = {
        "source_sha256": "a" * 64,
        "max_segment_length_m": 8,
        "runs": {"run:test": declaration},
    }
    provenance = {
        "scene_id": "test",
        "run_ref": "run:test",
        "source_sha256": "a" * 64,
        "safe_inputs_sha256": "b" * 64,
        "config_sha256": content_hash(config),
        "clock_id": "clock:test",
        "gt_read": False,
        "annotation_sha256": {"occluders": None, "walkable": None},
    }
    return observation, component, quality, camera, plane, provenance, config


def clip(mask, *, unknown=None, meaning="WALKABLE_AREA", camera_id=None):
    value = SourceClip(
        "geometry:test",
        "",
        "a" * 64,
        mask,
        0,
        0.25,
        unknown_geometry=unknown,
        camera_id=camera_id,
        meaning=meaning,
    )
    return replace(value, ref_sha256=value.digest())


def test_segment_uses_declared_prior_and_not_observation_world_position(inputs):
    saved = copy.deepcopy(inputs)
    result = estimate_contact(*inputs)
    assert result["status"] == "READY" and result["estimate_kind"] == "SEGMENT"
    assert result["contact_quality"] == inputs[2]
    assert result["segment"]["height_prior"]["nominal_m"] == 1.7
    assert result["segment"]["length_m"] == pytest.approx(0.2 * math.tan(math.pi / 6))
    assert result["point_m"] is None
    assert [r["effect"] for r in result["constraints_applied"]] == [
        "BOUNDED",
        "NOT_AVAILABLE",
        "NOT_AVAILABLE",
    ]
    assert inputs == saved
    assert result["output_sha256"] == content_hash(
        {k: v for k, v in result.items() if k != "output_sha256"}
    )
    assert result["physical_authority"] == "UNKNOWN" and result["identity_verdict"] == "UNCONFIRMED"


def test_pass_returns_v2_point_without_changing_existing_v1_position(inputs):
    inputs[2].update(status="PASS", reasons=[])
    result = estimate_contact(*inputs)
    assert result["status"] == "READY" and result["estimate_kind"] == "POINT"
    assert result["point_m"] == inputs[1]["world_position"]
    assert inputs[0]["world_position"] == [999, 999, 0]
    assert result["constraints_applied"] == []


@pytest.mark.parametrize(
    "status,reasons,reason",
    [
        ("FLAGGED", ["LOW_INCIDENCE", "AMBIGUOUS_MERGE"], "HEAD_ANCHOR_UNRELIABLE"),
        ("FLAGGED", ["TOUCHES_IMAGE_EDGE"], "HEAD_ANCHOR_UNRELIABLE"),
        ("FLAGGED", ["UNRECOGNIZED"], "HEAD_ANCHOR_UNRELIABLE"),
        ("NOT_EVALUATED", ["AMBIGUOUS_MAPPING"], "CONTACT_QUALITY_NOT_EVALUATED"),
    ],
)
def test_flags_are_preserved_without_endpoint_substitution(inputs, status, reasons, reason):
    inputs[2].update(status=status, reasons=reasons)
    result = estimate_contact(*inputs)
    assert result["reason"] == reason and result["estimate_kind"] == "NONE"
    assert result["contact_quality"] == inputs[2]
    assert result["observation_ref"] == inputs[0]["observation_ref"]
    assert result["timestamp_s"] == 1.2
    assert result["diagnostics"]["endpoint_substitution"] == "NOT_PERFORMED"


@pytest.mark.parametrize("change", ["missing", "zero", "nan", "negative", "too_tall"])
def test_invalid_run_prior_never_uses_default_height(inputs, change):
    prior = inputs[-1]["runs"]["run:test"]["head_height_prior"]
    if change == "missing":
        inputs[-1]["runs"].clear()
    elif change == "zero":
        prior["tolerance_m"] = 0
    elif change == "nan":
        prior["tolerance_m"] = float("nan")
    elif change == "negative":
        prior["tolerance_m"] = -0.1
    else:
        prior["nominal_m"] = 3
    result = estimate_contact(*inputs)
    assert result["reason"] == "HEIGHT_PRIOR_UNAVAILABLE"


def test_clips_are_ordered_and_do_not_snap(inputs):
    occluder = clip(box(-10, 1.29, 10, 2), meaning="FOOT_HIDDEN_FROM_THIS_CAMERA", camera_id="C")
    walkable = clip(box(-10, 1.31, 10, 1.36))
    result = estimate_contact(*inputs, occluder=occluder, walkable=walkable)
    assert result["status"] == "READY"
    assert result["segment"]["near_m"][1] == pytest.approx(1.31)
    assert result["segment"]["far_m"][1] == pytest.approx(1.36)
    assert [s["effect"] for s in result["constraints_applied"]] == ["BOUNDED", "CLIPPED", "CLIPPED"]
    assert result["pixel_sensitivity_m"] > 0


def test_unknown_walkable_region_is_kept_and_its_length_reported(inputs):
    region = clip(box(-10, 1, 10, 1.32), unknown=box(-10, 1.32, 10, 2))
    result = estimate_contact(*inputs, walkable=region)
    assert result["status"] == "READY"
    assert result["segment"]["far_m"][1] > 1.32
    assert result["constraints_applied"][-1]["walkable_unknown_length_m"] > 0


@pytest.mark.parametrize(
    "mask,reason",
    [
        (box(50, 50, 60, 60), "SEGMENT_EMPTY_AFTER_CONSTRAINTS"),
        (box(-10, 1, 10, 1.30).union(box(-10, 1.35, 10, 2)), "SEGMENT_NON_CONTIGUOUS"),
    ],
)
def test_empty_or_disjoint_clips_fail_closed(inputs, mask, reason):
    result = estimate_contact(*inputs, walkable=clip(mask))
    assert result["reason"] == reason and result["segment"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_sha256", "c" * 64),
        ("ref_sha256", "f" * 64),
        ("tier", "ANNOTATION_ONLY"),
        ("body_radius_m", 0.1482),
        ("floor_z_m", 0.12),
    ],
)
def test_mismatched_clip_provenance_is_rejected(inputs, field, value):
    region = replace(clip(box(-10, 1, 10, 2)), **{field: value})
    assert estimate_contact(*inputs, walkable=region)["reason"] == "PROVENANCE_MISMATCH"


def test_obstacle_footprint_is_not_accepted_as_occluder_shadow(inputs):
    region = clip(box(-10, 1, 10, 2))
    assert estimate_contact(*inputs, occluder=region)["reason"] == "PROVENANCE_MISMATCH"


def test_upward_head_ray_and_camera_below_prior_fail_closed(inputs):
    inputs[1]["bbox_xyxy"] = [48, -100, 53, 79]
    assert estimate_contact(*inputs)["status"] == "UNKNOWN"
    inputs[1]["bbox_xyxy"] = [48, 50, 53, 79]
    inputs[-1]["runs"]["run:test"]["head_height_prior"]["nominal_m"] = 4
    inputs[-1]["runs"]["run:test"]["target_proxy"]["height_m"] = 4
    inputs[-1]["runs"]["run:test"]["target_proxy"]["label"] = "SYNTHETIC_CYLINDER_NOT_HUMAN_SIZED"
    assert estimate_contact(*inputs)["reason"] == "HEAD_RAY_NOT_DESCENDING"


def test_over_limit_interval_is_unknown_and_retains_diagnostic_length(inputs):
    inputs[-1]["max_segment_length_m"] = 0.01
    result = estimate_contact(*inputs)
    assert result["reason"] == "SEGMENT_TOO_LONG" and result["estimate_kind"] == "NONE"
    assert result["diagnostics"]["raw_interval_length_m"] > 0.01
    assert result["diagnostics"]["raw_near_m"] is not None
    assert result["diagnostics"]["raw_far_m"] is not None
    assert (
        result["diagnostics"]["raw_coordinates_use"] == "DIAGNOSTIC_ONLY_NOT_POSITION_OR_ENDPOINT"
    )
    assert result["diagnostics"]["raw_coordinates_usable_as_position"] is False
    assert result["diagnostics"]["raw_coordinates_usable_as_endpoint"] is False
    assert k1_endpoint_eligibility(result)["eligible"] is False


def test_d17_low_incidence_skips_even_supplied_occluder_and_sensitivity(inputs):
    inputs[2]["reasons"] = ["LOW_INCIDENCE"]
    baseline = estimate_contact(*inputs)
    # This mask empties the segment if mistakenly applied (including ±1px).
    occluder = clip(box(50, 50, 60, 60), meaning="FOOT_HIDDEN_FROM_THIS_CAMERA", camera_id="C")
    result = estimate_contact(*inputs, occluder=occluder)
    assert result == baseline
    assert result["status"] == "READY"
    assert result["constraints_applied"][1]["effect"] == "NOT_APPLICABLE"
    assert result["provenance"]["annotation_sha256"]["occluders"] is None
    assert k1_endpoint_eligibility(result)["eligible"] is True
    inputs[2]["reasons"].append("CONTACT_OCCLUDED")
    assert (
        estimate_contact(*inputs, occluder=occluder)["reason"] == "SEGMENT_EMPTY_AFTER_CONSTRAINTS"
    )


@pytest.mark.parametrize("effect", ["CLIPPED", "NO_CHANGE", "EMPTIED", "NOT_AVAILABLE"])
def test_d17_guard_rejects_low_incidence_with_occluder_applied(inputs, effect):
    inputs[2]["reasons"] = ["LOW_INCIDENCE"]
    result = estimate_contact(*inputs)
    result["constraints_applied"][1]["effect"] = effect
    assert k1_endpoint_eligibility(result)["reasons"] == ["D17_OCCLUDER_BEHIND_NOT_APPLICABLE"]
    result["constraints_applied"] = []
    assert not k1_endpoint_eligibility(result)["eligible"]


def test_d17_contact_occluded_and_d8_still_apply(inputs):
    inputs[2]["reasons"] = ["LOW_INCIDENCE", "CONTACT_OCCLUDED"]
    assert k1_endpoint_eligibility(estimate_contact(*inputs))["eligible"] is True
    inputs[2]["reasons"].append("AMBIGUOUS_MERGE")
    rejected = estimate_contact(*inputs)
    assert rejected["status"] == "UNKNOWN" and not k1_endpoint_eligibility(rejected)["eligible"]


def test_gt_or_source_mismatch_and_missing_quality_fail_closed(inputs):
    inputs[-2]["gt_read"] = True
    assert estimate_contact(*inputs)["reason"] == "PROVENANCE_MISMATCH"
    inputs[-2]["gt_read"] = False
    args = list(inputs)
    args[2] = None
    assert estimate_contact(*args)["reason"] == "CONTACT_QUALITY_MISSING"


def test_valid_upward_camera_ray_has_explicit_descending_failure(inputs):
    args = list(inputs)
    angle = 2 * math.pi / 3
    c, s = math.cos(angle), math.sin(angle)
    args[3] = args[3].model_copy(
        update={"camera_to_world": ((1, 0, 0, 0), (0, c, -s, 0), (0, s, c, 4), (0, 0, 0, 1))}
    )
    assert estimate_contact(*args)["reason"] == "HEAD_RAY_NOT_DESCENDING"


def test_nonrigid_camera_pose_fails_closed(inputs):
    args = list(inputs)
    args[3] = args[3].model_copy(
        update={"camera_to_world": ((2, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 4), (0, 0, 0, 1))}
    )
    assert estimate_contact(*args)["reason"] == "PROJECTION_FAILED"


def test_foot_band_matches_two_rays_and_radius_without_head_prior(inputs, monkeypatch):
    import amidst.engineering.hybrid_contact as hybrid

    inputs[2]["reasons"] = ["LOW_INCIDENCE"]
    declaration = inputs[-1]["runs"]["run:test"]
    declaration["head_height_prior"] = {"tolerance_m": "UNKNOWN"}
    monkeypatch.setattr(hybrid, "_height_segment", lambda *_: pytest.fail("No head fallback"))
    saved = copy.deepcopy(inputs)
    result = estimate_contact(*inputs)
    assert result["status"] == "READY" and result["basis"] == "FOOT_RAY_PIXEL_BAND"
    segment = result["segment"]
    assert segment["height_prior"] is None and segment["ray_origin_m"] is None
    assert segment["ray_direction"] is None
    assert segment["foot_band"]["band_px"] == 2
    service = InverseProjectionService(inputs[3], inputs[4])
    u, v = inputs[1]["contact_pixel"]
    raw = [list(project_pixel(service, (u, v + d)).world_position) for d in (2, -2)]
    assert segment["raw_near_m"] == raw[0] and segment["raw_far_m"] == raw[1]
    assert segment["near_m"] == pytest.approx(raw[0])
    assert math.dist(segment["far_m"], raw[1]) == pytest.approx(0.25)
    assert segment["length_m"] == pytest.approx(math.dist(*raw) + 0.25)
    assert result["image_anchor_px"] == [u, v]
    assert result["contact_quality"] == inputs[2] and inputs == saved
    assert result["constraints_applied"][0]["kind"] == "FOOT_RAY_PIXEL_BAND"
    assert k1_endpoint_eligibility(result)["eligible"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("foot_anchor_band_px", 0),
        ("foot_anchor_band_px", True),
        ("foot_anchor_band_px", float("nan")),
        ("body_radius_m", None),
        ("body_radius_m", 0),
    ],
)
def test_invalid_band_declaration_is_unknown_without_head_fallback(inputs, field, value):
    inputs[2]["reasons"] = ["LOW_INCIDENCE"]
    inputs[-1]["runs"]["run:test"][field] = value
    result = estimate_contact(*inputs)
    assert result["reason"] == "FOOT_BAND_UNAVAILABLE" and result["segment"] is None


def test_missing_band_declaration_is_unknown_without_head_fallback(inputs):
    inputs[2]["reasons"] = ["LOW_INCIDENCE"]
    del inputs[-1]["runs"]["run:test"]["foot_anchor_band_px"]
    result = estimate_contact(*inputs)
    assert result["status"] == "UNKNOWN" and result["reason"] == "FOOT_BAND_UNAVAILABLE"
    assert result["basis"] == "NONE" and result["segment"] is None


def test_failed_band_ray_never_shortens_or_uses_head(inputs):
    inputs[2]["reasons"] = ["LOW_INCIDENCE"]
    inputs[-1]["runs"]["run:test"]["foot_anchor_band_px"] = 1000
    result = estimate_contact(*inputs)
    assert result["reason"] == "PROJECTION_FAILED" and result["basis"] == "NONE"


def test_v11_guard_rejects_historical_head_fallback(inputs):
    inputs[2]["reasons"] = ["LOW_INCIDENCE"]
    g = estimate_contact(*inputs)
    g["basis"] = "HEAD_RAY_HEIGHT_PRIOR"
    assert "V1_1_FOOT_BAND_REQUIRED" in k1_endpoint_eligibility(g)["reasons"]
    g["basis"] = "FUTURE_UNKNOWN"
    assert not k1_endpoint_eligibility(g)["eligible"]
