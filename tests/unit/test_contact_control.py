"""Route selection policy and evaluation isolation, without Blender or footage."""
import importlib.util
from pathlib import Path

from amidst.workbench.blender_scene import ValidationRunPin

ROOT = Path(__file__).parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


planner = load("contact_control_planner", ROOT / "scripts/plan_blender_pilot_sites.py")


def test_every_frame_requires_visible_middle_bottom_and_incidence():
    good = {"status":"visible", "bottom_status":"visible", "bottom_incidence":0.4}
    shallow = dict(good, bottom_incidence=0.18)
    assert planner.contact_coverage([{"camera_visibility":[good,good]},
                                     {"camera_visibility":[good,shallow]}],0.25) == (True,1)
    assert planner.contact_coverage([{"camera_visibility":[shallow,shallow]}],0.25) == (False,0)
    assert planner.contact_coverage([{"camera_visibility":[dict(good,bottom_status="occluded")]}],0.25) == (False,0)


def test_pin_does_not_allow_impersonating_baseline():
    import pytest
    with pytest.raises(ValueError):
        ValidationRunPin("office", "blender-pilot-office-baseline-v1", "a"*64, "b"*64)
    with pytest.raises(ValueError):
        ValidationRunPin("office", "blender-contact-control-test-v1", "bad", "b"*64)


def test_posthoc_comparison_reports_same_frame_pairs_and_missing_coverage():
    runner = load("contact_control_runner", ROOT / "scripts/run_contact_validation.py")
    prediction = {"source_binding":{"source_sha256":"a"*64}, "frames":[], "speed_transitions":[]}
    dataset = {"source_scene":{"sha256_before":"a"*64}, "timestamps":[]}
    plan = {"contact_visibility_policy":{"min_incidence":0.25}, "samples":[]}
    for i in range(50):
        dataset["timestamps"].append({"index":i, "timestamp":i/5,
                                      "ground_truth":{"foot_position":[0,0,0]}})
        plan["samples"].append({"timestamp":i/5, "foot_position":[0,0,0],
                                "camera_visibility":[{"camera_id":"C", "status":"visible",
                                                      "bottom_status":"visible", "bottom_incidence":0.5}]})
        prediction["frames"].append({"camera_id":"C", "timestamp":i/5,
                                     "old_components":[{"world_position":[1,0,0]}],
                                     "components":[{"world_position":[0.5,0,0] if i<25 else None,
                                                    "reasons":[] if i<25 else ["LOW_INCIDENCE"]}]})
    result = runner.evaluate(prediction,dataset,plan)
    assert result["summary"]["v1"]["projected_count"] == 50
    assert result["summary"]["v2"]["projected_count"] == 25
    assert result["paired_same_frames"]["v1"] == {"count":25,"mean_m":1,"max_m":1}
    assert result["paired_same_frames"]["v2"] == {"count":25,"mean_m":0.5,"max_m":0.5}
    assert result["acceptance"] == "PASS"
