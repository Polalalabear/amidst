"""C5 three-probe union, conservative cell labels and source-bound footprint hashes."""

import copy
from types import SimpleNamespace

import pytest

from amidst.engineering.registry import content_hash
from amidst.geometry.floor_visibility_index import build_visibility_index
from amidst.geometry.visibility_policy import cell_status, probe_status, union_status


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
def test_index_preserves_sample_resolution_unknown_and_source_hash(code, polygons):
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
    }
    rays = {
        "source_sha256": "a" * 64,
        "gt_read": False,
        "renderer_visibility_read": False,
        "safe_inputs_sha256": "b" * 64,
        "config_sha256": "c" * 64,
        "config": config,
        "sample_grid": {"origin_m": [0.0, 0.0], "step_m": 0.125, "nx": 3, "ny": 3},
        "mesh_counts": {},
        "cameras": [
            {
                "camera_id": "A",
                "sample_status_codes": [code] * 9,
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
    result = build_visibility_index(
        rays,
        physical,
        ray_file_sha256="d" * 64,
        physical_file_sha256="e" * 64,
        run_parameters=params,
        calibration_sha256="f" * 64,
        floor_sha256="0" * 64,
    )
    assert len(result["entries"][0]["polygons"]) == polygons
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
            calibration_sha256="f" * 64,
            floor_sha256="0" * 64,
        )


def test_material_with_transparency_is_unknown_when_hit():
    from export_floor_visibility import opaque_material

    assert opaque_material(None)
    assert opaque_material(SimpleNamespace(diffuse_color=(1, 1, 1, 1), use_nodes=False))
    assert not opaque_material(SimpleNamespace(diffuse_color=(1, 1, 1, 0.5), use_nodes=False))
