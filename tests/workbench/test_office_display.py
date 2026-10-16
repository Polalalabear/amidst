"""Validate the committed display-only subset against the independent Task C inventory."""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from amidst.workbench.office_display import attach_office_display, load_office_display

REPO = Path(__file__).resolve().parents[2]
CONFIG = json.loads((REPO / "configs/office_demo_display_v1.json").read_bytes())
SCOPE = {"scene_id": "blender-office", "units": "METRES",
         "inputs_sha256": CONFIG["office_inputs_sha256"],
         **{k: CONFIG[k] for k in ("source_sha256", "scale_sha256", "metres_per_bu",
                                   "model_revision")}}


@pytest.fixture(scope="module")
def display():
    return load_office_display(REPO, SCOPE)


def test_exact_source_inventory_and_shared_definitions(display):
    instances, geometries = display["instances"], display["geometries"]
    chairs = [r for r in instances if r["kind"] == "CHAIR"]
    lectern = [r for r in instances if r["kind"] == "LECTERN"]
    assert len(chairs) == 80 and len(lectern) == 14 and len(geometries) == 19
    assert set(Counter(r["assembly"] for r in chairs).values()) == {5}
    assert len({r["assembly"] for r in chairs}) == 16
    assert {r["assembly"] for r in lectern} == {"N1 Hamburg"}
    assert len({r["geometry_ref"] for r in chairs}) == 6  # Two exact armrest variants.
    assert sum(len(g["triangles"]) for g in geometries.values()) == 117103
    assert sum(len(geometries[r["geometry_ref"]]["triangles"]) for r in instances) == 611598


def test_world_transforms_bounds_and_coordinates_match_independent_source_inventory(display):
    specs = {r["object_id"]: r for r in CONFIG["objects"]}
    points = []
    for row in display["instances"]:
        vertices = np.array(display["geometries"][row["geometry_ref"]]["vertices"])
        expected = np.array(specs[row["object_id"]]["matrix_world_bu"])
        actual = np.array(row["matrix_world_metres"])
        world = vertices @ actual[:3, :3].T + actual[:3, 3]
        source = (vertices @ expected[:3, :3].T + expected[:3, 3]) * .0247
        assert np.max(np.abs(world - source)) < 1e-12
        bounds = np.array(specs[row["object_id"]]["source_bounds_metres"])
        assert np.all(world.min(axis=0) >= bounds[0] - 1e-5)
        assert np.all(world.max(axis=0) <= bounds[1] + 1e-5)
        assert row["transform_max_error_metres"] < 1e-5
        points.extend([world.min(axis=0), world.max(axis=0)])
    for mesh in display["architecture"]:
        points.extend(mesh["vertices"])
        low, high = np.array(mesh["excluded_office_bounds_metres"])
        # The complementary pieces occupy at least one outside half-space.
        for indices in mesh["triangles"]:
            triangle = np.array([mesh["vertices"][i] for i in indices])
            assert any(np.all(triangle[:, a] <= low[a] + 1e-9)
                       or np.all(triangle[:, a] >= high[a] - 1e-9) for a in range(3))
    assert np.allclose([np.min(points, axis=0), np.max(points, axis=0)],
                       display["bounds_metres"], atol=1e-10, rtol=0)
    assert display["coordinate_frame"] == "RIGHT_HANDED_XYZ_Z_UP"
    assert display["geometry_local_units"] == "NATIVE_BU" and display["units"] == "METRES"


def test_additive_attachment_preserves_every_original_field_and_inference_input(display):
    original = {"presentation": {"meshes": [{"ref": "original-office"}],
                                 "authority": "PARTIAL_DISPLAY_CONTEXT"},
                "bounds": [1, 2, 3, 4], "baseline": {"observations": [[1, 2, 3]]},
                "capabilities": {"navigation_guidance": False}, "cameras": [[4, 5, 6]]}
    scene = SimpleNamespace(_snapshot=copy.deepcopy(original), live_scope=lambda: SCOPE,
                            index=object(), association=object(), physical=object())
    identities = [scene.index, scene.association, scene.physical]
    attach_office_display(scene, REPO)
    extended = scene._snapshot["presentation"].pop("supplemental_display")
    assert scene._snapshot == original
    assert identities == [scene.index, scene.association, scene.physical]
    assert extended == display
    assert extended["authority"] == "PARTIAL_DISPLAY_CONTEXT"
    assert extended["display_only"] is True
    assert extended["physical_authority_changed"] is False
    assert extended["navigation_authority"] == "UNKNOWN"
    assert extended["whole_auditorium_complete"] is False


@pytest.mark.parametrize("key,value", [("source_sha256", "f" * 64),
                                      ("scale_sha256", "f" * 64),
                                      ("inputs_sha256", "f" * 64),
                                      ("metres_per_bu", 1), ("scene_id", "blender-auditorium")])
def test_foreign_source_scale_fixture_or_site_is_rejected(key, value):
    with pytest.raises(ValueError, match="SCOPE_MISMATCH"):
        load_office_display(REPO, SCOPE | {key: value})


def test_missing_tampered_or_oversized_companion_is_not_silently_used(tmp_path):
    (tmp_path / "configs").mkdir()
    config = copy.deepcopy(CONFIG)
    config["asset"] = "broken.gz"
    (tmp_path / "configs/office_demo_display_v1.json").write_text(json.dumps(config))
    with pytest.raises(FileNotFoundError):
        load_office_display(tmp_path, SCOPE)
    (tmp_path / "broken.gz").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="ASSET_MISMATCH"):
        load_office_display(tmp_path, SCOPE)
    config["asset_sha256"] = hashlib.sha256(b"tampered").hexdigest()
    config["max_asset_bytes"] = 1
    (tmp_path / "configs/office_demo_display_v1.json").write_text(json.dumps(config))
    with pytest.raises(ValueError, match="ASSET_MISMATCH"):
        load_office_display(tmp_path, SCOPE)


def test_compact_resource_limits_and_no_private_locators(display):
    path = REPO / CONFIG["asset"]
    raw = gzip.decompress(path.read_bytes())
    assert path.stat().st_size < 2 * 1024**2 < CONFIG["max_asset_bytes"]
    assert len(raw) < 6 * 1024**2 < CONFIG["max_raw_bytes"]
    assert not any(marker in raw for marker in (b"/Users/", b"/private/", b"ground_truth",
                                                b"dataset_path", b"local_path"))
    assert display["source_sha256"] == CONFIG["source_sha256"]
    assert len(display["architecture"]) == 2
    assert sum(len(m["triangles"]) for m in display["architecture"]) == 366
