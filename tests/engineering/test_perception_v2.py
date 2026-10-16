"""Synthetic masks exercise v2 guards independently of rendered footage."""
import math

import numpy as np
import pytest

from amidst.domain.camera import Camera
from amidst.domain.geometry import Plane
from amidst.engineering.perception import _components
from amidst.engineering.perception_v2 import (
    ContactConfig, components8, measure_component, pixel_sensitivity, project_pixel,
)
from amidst.geometry.inverse_projection import InverseProjectionService


def projector():
    # Camera at (0,-5,5), aimed 45 degrees down towards origin.
    s = math.sqrt(0.5)
    pose = [[1,0,0,0], [0,s,-s,-5], [0,s,s,5], [0,0,0,1]]
    camera = Camera(camera_id="C", camera_to_world=pose, width=200, height=200,
                    fx=100, fy=100, cx=100, cy=100, clip_start=0.01)
    return InverseProjectionService(camera, Plane(plane_id="floor", point=(0,0,0), normal=(0,0,1), floor_id="1F"))


def config(**changes):
    return ContactConfig(assumed_target_height_m=2, assumed_target_radius_m=0.1,
                         height_tolerance_px=2, **changes)


def mask(top=75, bottom=100, left=99, right=102):
    m = np.zeros((200,200), dtype=bool)
    m[top:bottom+1, left:right] = True
    return m


def test_bottom_row_median_uses_mask_support_not_bbox_center():
    m = mask(left=95,right=106)
    m[100,:] = False
    m[100,102:105] = True
    result = measure_component(components8(m)[0], projector(), config())
    assert result["contact_pixel"] == [103,100]


def test_complete_target_and_occluded_bottom():
    p = projector()
    # Configured 2m height at the floor contact projects near row 75.
    full = measure_component(components8(mask())[0], p, config())
    assert full["status"] == "OBSERVED", full
    hidden = measure_component(components8(mask(bottom=85))[0], p, config())
    assert hidden["status"] == "MISSING"
    assert "CONTACT_OCCLUDED" in hidden["reasons"]
    assert hidden["world_position"] is None
    assert hidden["interpolation_allowed"] is False


def test_image_edge_rejects_contact():
    result = measure_component(components8(mask(left=0,right=3))[0], projector(), config())
    assert "TOUCHES_IMAGE_EDGE" in result["reasons"]
    assert result["world_position"] is None


def test_diagonal_components_merge_and_distinct_objects_risk_is_explicit():
    m = np.zeros((30,30), dtype=bool)
    m[2:8,2:8] = True
    m[8:14,8:14] = True
    assert len(_components(m)) == 2
    assert len(components8(m)) == 1
    m[8:14,8:14] = False
    m[9:15,9:15] = True
    assert len(components8(m)) == 2
    # Even independent objects merge if they touch diagonally. This is topology,
    # not confirmed identity; height/width guards can reject but cannot prove it.


def test_low_incidence_rejects_and_one_pixel_sensitivity_is_in_metres():
    p = projector()
    result = measure_component(components8(mask())[0], p, config(min_incidence=0.9))
    assert "LOW_INCIDENCE" in result["reasons"]
    assert result["world_position"] is None
    sensitivity = pixel_sensitivity(p, (100,100))
    base = project_pixel(p, (100,100)).world_position
    expected = math.dist(base, project_pixel(p,(100,101)).world_position)
    assert sensitivity["samples"][3]["displacement_m"] == pytest.approx(expected)
    assert sensitivity["max_displacement_m"] > 0


def test_wide_merged_objects_fail_configured_target_width():
    row = measure_component(components8(mask(left=85, right=116))[0], projector(), config())
    assert "AMBIGUOUS_MERGE" in row["reasons"]
    assert row["world_position"] is None


def test_gt_pollution_does_not_change_v2_and_bad_rgb_is_missing(tmp_path):
    import importlib.util
    from pathlib import Path
    from amidst.engineering.perception_v2 import produce_contact_v2
    path = Path(__file__).parents[1] / "workbench/test_frame_baseline.py"
    spec = importlib.util.spec_from_file_location("contact_v2_rgb_fixtures", path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    inputs = fixture.rgb_inputs(tmp_path)
    first = produce_contact_v2(inputs, config())
    inputs["ground_truth"] = {"position":[9999,9999,9999]}
    inputs["trajectory"] = "MUST_NOT_READ"
    inputs["visibility"] = {"bottom":"visible"}
    assert produce_contact_v2(inputs, config()) == first
    damaged = inputs["frames"][0]
    damaged["local_path"].write_bytes(b"invalid")
    result = produce_contact_v2(inputs, config())
    row = next(f for f in result["frames"] if f["frame_ref"] == damaged["frame_ref"])
    assert row["status"] == "MISSING"
    assert row["reasons"] == ["RGB_HASH_MISMATCH"]
    assert row["world_position"] is None
    assert not result["complete"]
