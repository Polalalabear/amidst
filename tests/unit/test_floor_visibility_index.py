"""C5 three-probe union, conservative cell labels and source-bound footprint hashes."""

import copy
from types import SimpleNamespace

import pytest

from amidst.engineering.registry import content_hash
from amidst.geometry.floor_visibility_index import build_visibility_index
from amidst.geometry.visibility_policy import (
    cell_status,
    predicted_leg_area_px,
    probe_status,
    sample_status,
    union_status,
)


def test_three_probe_union_and_fov_clip_precede_rays():
    # Matches C6 probe_visibility/is_visible semantics (9937135); no planning outputs used.
    camera = {
        "camera_to_world": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 4], [0, 0, 0, 1]],
        "clip_start": 0.1,
        "clip_end": 10.0,
        "fx": 10.0,
        "fy": 10.0,
        "cx": 50.0,
        "cy": 50.0,
        "width": 100,
        "height": 100,
    }
    assert probe_status(camera, [0, 0, 0], lambda: "OCCLUDED") == "OCCLUDED"
    assert probe_status(camera, [0, 0, 1.7], lambda: "VISIBLE") == "VISIBLE"
    assert union_status(["OCCLUDED", "OCCLUDED", "VISIBLE"]) == "VISIBLE"
    assert union_status(["OCCLUDED", "UNKNOWN", "OCCLUDED"]) == "UNKNOWN"
    assert probe_status(camera, [0, 0, 5], lambda: pytest.fail("clipped ray called")) == "CLIPPED"
    assert (
        probe_status(camera, [100, 0, 0], lambda: pytest.fail("out of FOV ray called"))
        == "OUTSIDE_FOV"
    )
    assert cell_status(["VISIBLE"] + ["NOT_VISIBLE"] * 8) == "UNKNOWN_MIXED"
    assert cell_status(["NOT_VISIBLE"] * 9) == "SAMPLED_NOT_VISIBLE_NOT_CONTINUOUS_BLIND_PROOF"
    assert cell_status(["VISIBLE"] * 9) == "SAMPLED_VISIBLE"


@pytest.mark.parametrize("code,polygons", [(1, 1), (0, 0), (2, 0)])
@pytest.mark.parametrize("minimum_px", [111.999, 112.0])
def test_index_preserves_sample_resolution_unknown_and_source_hash(
    code, polygons, minimum_px, monkeypatch
):
    config = {
        "cell_size_m": 0.25,
        "height_m": 1.7,
        "body_radius_m": 0.25,
        "valid_time_range_s": [0.0, 1.0],
        "floor_z_m": 0.0,
        "floor_clearance_m": 0.002,
        "probe_offsets_m": [0.002, 0.852, 1.702],
        "run_id": "synthetic",
        "clock_id": "SYNTHETIC_5HZ",
        "visibility_rule": "FOOT_AND_TORSO_PROBES_VISIBLE",
        "detectability_factor": 4,
        "detector": {
            "producer": "test",
            "version": "v1",
            "difference_threshold": 30,
            "min_pixels": 28,
        },
    }
    rays = {
        "source_sha256": "a" * 64,
        "gt_read": False,
        "renderer_visibility_read": False,
        "safe_inputs_sha256": "b" * 64,
        "config_sha256": "c" * 64,
        "config": config,
        "sample_grid": {
            "origin_m": [0.0, 0.0],
            "step_m": 0.125,
            "nx": 3,
            "ny": 3,
            "order": "X_MAJOR_Y_MINOR",
        },
        "mesh_counts": {},
        "cameras": [
            {
                "camera_id": "A",
                "sample_status_codes": [code] * 9,
                "probe_status_codes": [[code] * 3 for _ in range(9)],
                "probe_order": ["foot", "waist", "head"],
                "probe_visible_counts": {"111" if code == 1 else "000": 9},
                "head_or_torso_only_visible_samples": 0,
            }
        ],
    }
    rays["output_sha256"] = content_hash(rays)
    physical = {
        "source_sha256": "a" * 64,
        "floor": {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            }
        },
    }
    params = {"target_proxy": {"height_m": 1.7}, "body_radius_m": 0.25}
    calibration = {
        "camera_to_world": [[1, 0, 0, 0], [0, 0, -1, -10], [0, 1, 0, 1], [0, 0, 0, 1]],
        "fx": 1000.0,
        "fy": 1000.0,
        "cx": 500,
        "cy": 500,
        "width": 1000,
        "height": 1000,
        "clip_start": 0.1,
        "clip_end": 100,
    }
    import amidst.geometry.floor_visibility_index as builder

    monkeypatch.setattr(
        builder,
        "predicted_leg_area_px",
        lambda cal, xy, *a: minimum_px if xy == [0.25, 0.25] else 200.0,
    )
    result = build_visibility_index(
        rays,
        physical,
        ray_file_sha256="d" * 64,
        physical_file_sha256="e" * 64,
        run_parameters=params,
        calibration_sha256=content_hash([calibration]),
        calibrations={"A": calibration},
        floor_sha256="0" * 64,
    )
    entry = result["entries"][0]
    assert len(entry["polygons"]) == (polygons if minimum_px >= 112 else 0)
    assert len(entry["suggestion_polygons"]) == polygons
    assert entry["sampling"]["cell_min_predicted_px"] == [minimum_px]
    assert entry["cells_removed"]["detectability"] == (1 if code == 1 and minimum_px < 112 else 0)
    assert result["entries"][0]["sampling"]["continuous_unsampled_visibility"] == "UNKNOWN"
    assert result["output_sha256"] == content_hash(
        {k: v for k, v in result.items() if k != "output_sha256"}
    )
    bad = copy.deepcopy(rays)
    bad["gt_read"] = True
    bad["output_sha256"] = content_hash({k: v for k, v in bad.items() if k != "output_sha256"})
    with pytest.raises(ValueError, match="SOURCE"):
        build_visibility_index(
            bad,
            physical,
            ray_file_sha256="d" * 64,
            physical_file_sha256="e" * 64,
            run_parameters=params,
            calibration_sha256=content_hash([calibration]),
            calibrations={"A": calibration},
            floor_sha256="0" * 64,
        )
    # The union rule may still rank the same cell, but cannot emit evidence polygons.
    suggestion_only = copy.deepcopy(rays)
    suggestion_only["config"]["visibility_rule"] = "ANY_PROBE_VISIBLE"
    suggestion_only["output_sha256"] = content_hash(
        {k: v for k, v in suggestion_only.items() if k != "output_sha256"}
    )
    alternative = build_visibility_index(
        suggestion_only,
        physical,
        ray_file_sha256="d" * 64,
        physical_file_sha256="e" * 64,
        run_parameters=params,
        calibration_sha256=content_hash([calibration]),
        calibrations={"A": calibration},
        floor_sha256="0" * 64,
    )
    assert alternative["entries"][0]["polygons"] == []
    assert alternative["entries"][0]["negative_evidence_eligible"] is False


def test_material_with_transparency_is_unknown_when_hit():
    from export_floor_visibility import opaque_material

    assert opaque_material(None)
    assert opaque_material(SimpleNamespace(diffuse_color=(1, 1, 1, 1), use_nodes=False))
    assert not opaque_material(SimpleNamespace(diffuse_color=(1, 1, 1, 0.5), use_nodes=False))


@pytest.mark.parametrize(
    "probes,strict,any_probe",
    [
        (["VISIBLE", "VISIBLE", "OCCLUDED"], "VISIBLE", "VISIBLE"),
        (["VISIBLE", "VISIBLE", "UNKNOWN"], "VISIBLE", "VISIBLE"),
        (["OCCLUDED", "VISIBLE", "VISIBLE"], "NOT_VISIBLE", "VISIBLE"),
        (["VISIBLE", "OCCLUDED", "VISIBLE"], "NOT_VISIBLE", "VISIBLE"),
        (["UNKNOWN", "VISIBLE", "VISIBLE"], "UNKNOWN", "VISIBLE"),
        (["OCCLUDED", "OCCLUDED", "UNKNOWN"], "UNKNOWN", "UNKNOWN"),
        (["CLIPPED", "OUTSIDE_FOV", "OCCLUDED"], "NOT_VISIBLE", "NOT_VISIBLE"),
    ],
)
def test_d21_sample_rule(probes, strict, any_probe):
    assert sample_status(probes, "FOOT_AND_TORSO_PROBES_VISIBLE") == strict
    assert sample_status(probes, "ANY_PROBE_VISIBLE") == any_probe
    with pytest.raises(ValueError):
        sample_status(probes, "INVALID")


def test_predicted_leg_area_uses_calibration_only_and_clip_guard():
    calibration = {
        "camera_to_world": [[1, 0, 0, 0], [0, 0, -1, -10], [0, 1, 0, 1], [0, 0, 0, 1]],
        "fx": 1000.0,
        "fy": 1000.0,
        "cx": 500.0,
        "cy": 500.0,
        "clip_start": 0.1,
        "clip_end": 100.0,
    }
    assert predicted_leg_area_px(calibration, [0, 0], 0, 0.002, 0.852, 0.25) == pytest.approx(
        4250.0
    )
    calibration["fx"] = calibration["fy"] = 100.0
    assert predicted_leg_area_px(calibration, [0, 0], 0, 0.002, 0.852, 0.25) == pytest.approx(42.5)
    calibration["clip_end"] = 9.0
    assert predicted_leg_area_px(calibration, [0, 0], 0, 0.002, 0.852, 0.25) == 0


def test_region_comparison_distinguishes_time_sum_from_xy_union_and_rejects_truncation():
    from package_c5_receipt import region_comparison

    def response(rows):
        return {
            "reachable_regions": [
                {
                    "timestamp_s": float(i),
                    "samples": xs,
                    "cell_size_m": 0.25,
                    "area_m2": len(xs) * 0.25**2,
                    "truncated": False,
                }
                for i, xs in enumerate(rows)
            ]
        }

    before = response([[[0, 0], [0.25, 0]], [[0.25, 0], [0.5, 0]]])
    after = response([[[0.25, 0]], [[0.25, 0]]])
    result = region_comparison(before, after)
    assert result["before"]["sum_cells"] == 4 and result["before"]["union_cells"] == 3
    assert result["after"]["sum_cells"] == 2 and result["after"]["union_cells"] == 1
    assert result["sum_reduction_percent"] == 50.0
    assert result["union_reduction_percent"] == pytest.approx(200 / 3)
    before["reachable_regions"][0]["truncated"] = True
    with pytest.raises(ValueError, match="TRUNCATED"):
        region_comparison(before, after)
