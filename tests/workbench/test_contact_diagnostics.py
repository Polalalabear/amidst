"""Contact QA cannot manufacture feet, identities or positions through a gap."""

import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from amidst.domain.camera import Camera
from amidst.domain.geometry import Plane
from amidst.engineering.perception import _components
from amidst.geometry.inverse_projection import InverseProjectionService
from tests.workbench.test_frame_baseline import rgb_inputs

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "contact_qa", ROOT / "scripts/diagnose_office_contact.py"
)
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


def test_diagonal_contour_is_one_alternative_not_a_canonical_identity():
    mask = np.zeros((24, 24), dtype=bool)
    mask[2:10, 2:6] = True
    mask[10:18, 6:10] = True
    assert len(_components(mask)) == 2
    alternative = qa.components8(mask)
    assert len(alternative) == 1
    assert len(alternative[0][4]) == 64
    assert mask.sum() == 64
    mask[10:18, 6:10] = False
    mask[12:20, 12:16] = True
    assert len(qa.components8(mask)) == 2  # No bridging of empty space.


def test_visible_bottom_sample_does_not_certify_ground_contact(tmp_path):
    inputs = rgb_inputs(tmp_path)
    projector = InverseProjectionService(
        Camera.model_validate(inputs["cameras"][0]["calibration"]),
        Plane(plane_id="qa", point=(0, 0, 0), normal=(0, 0, 1), floor_id="1F"),
    )
    mask = np.zeros((64, 64), dtype=bool)
    mask[10:30, 10:20] = True
    mask[30:35, 10] = True
    result = qa.contact_diagnostic(_components(mask)[0], projector)
    assert result["contact_pixel"] == [14.5, 34]
    assert result["bbox_contact_to_nearest_bottom_mask_pixel_px"] == 4.5
    assert result["visible_bottom_median_pixel"] == [10, 34]
    assert result["proxy_world_position"] != result["visible_bottom_median_proxy_world_position"]
    assert result["visible_bottom_is_feet"] is False
    assert result["proposed_person_world_position"] is None
    assert result["ground_contact"] == "UNKNOWN"
    assert result["sensitivity_is_error_bound"] is False
    assert len(result["pixel_perturbations"]) == 4


def test_truth_pollution_cannot_change_qa_and_missing_stays_missing(tmp_path):
    inputs = rgb_inputs(tmp_path)
    # An anchor with no frame is never supplied a synthetic observation.
    clean = qa.diagnose(inputs, anchors=(0.4, 5.0))
    dirty = copy.deepcopy(inputs)
    dirty["ground_truth"] = {"feet": [99, 99, 99]}
    dirty["trajectory"] = {"identity": "secret"}
    for frame in dirty["frames"]:
        frame["ground_truth"] = {"feet": [99, 99, 99]}
        frame["world_position"] = [99, 99, 99]
    assert qa.diagnose(dirty, anchors=(0.4, 5.0)) == clean
    assert len(clean["samples"]) == 2
    assert all(s["timestamp"] == 0.4 and not s["canonical_replacement"] for s in clean["samples"])
    assert "secret" not in json.dumps(clean)
    blank = qa.diagnose(rgb_inputs(tmp_path / "blank", blank=True), anchors=(0.4,))
    assert all(
        s["quality"] == "NO_MEASUREMENT"
        and not s["mask8_proxy_alternatives"]
        and s["proposed_person_world_position"] is None
        for s in blank["samples"]
    )
    assert clean["canonical_observations_unchanged"] is True


def test_modified_rgb_is_rejected(tmp_path):
    inputs = rgb_inputs(tmp_path)
    Path(inputs["frames"][0]["local_path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="RGB_HASH_MISMATCH"):
        qa.diagnose(inputs)
