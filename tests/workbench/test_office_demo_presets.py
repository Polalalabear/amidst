"""Focused preset isolation, frozen Office regression, and contact-quality contracts."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import numpy as np
import pytest

from amidst.workbench.contact_scene import component_mapping, quality

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "office_demo_backend", REPO / "scripts/office_demo_backend.py"
)
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


def strip_quality(value):
    if isinstance(value, dict):
        return {k: strip_quality(v) for k, v in value.items() if k != "contact_quality"}
    if isinstance(value, list):
        return [strip_quality(v) for v in value]
    return value


def walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


@pytest.fixture(scope="module")
def live(tmp_path_factory):
    if not os.environ.get("OFFICE_TEST_ASSETS"):
        pytest.skip("Set OFFICE_TEST_ASSETS to the existing immutable asset checkout")
    assets = Path(os.environ["OFFICE_TEST_ASSETS"])
    evidence = assets / ".local-worktrees/phase1-finalization"
    catalog = backend.load_presets(backend.DEFAULT_PRESETS, evidence, assets)
    app = backend.application(
        catalog, tmp_path_factory.mktemp("presets") / "review.db", REPO, evidence
    )
    token = app.workbench.session({"role": "research"})["session_ref"]
    return catalog, app.workbench, token


def test_catalog_and_independent_control(live):
    catalog, workbench, token = live
    ids = [s["scene_id"] for s in workbench.bootstrap()["scenes"]]
    assert ids == ["blender-office", "blender-contact-control"]
    office, control = (catalog[s] for s in ids)
    assert office.run_id == "blender-pilot-office-baseline-v1"
    assert control.run_id == "blender-contact-control-auditorium-v1"
    assert office.index.source_features != control.index.source_features
    assert not {r["frame_ref"] for r in office.index.frame_records} & {
        r["frame_ref"] for r in control.index.frame_records
    }
    assert not {r["observation_ref"] for r in office.index.observations} & {
        r["observation_ref"] for r in control.index.observations
    }
    config = json.loads((REPO / "configs/office_demo_contact_control_fixture_v1.json").read_text())
    defaults = control.snapshot()["demo_defaults"]
    assert defaults["observation_ref"] == config["observation_ref"]
    assert defaults["selected_timestamp"] == config["selected_timestamp"]
    source_prediction = json.loads(
        (
            Path(os.environ["OFFICE_TEST_ASSETS"])
            / "data/engineering/contact_control_20261016_v1/auditorium/predictions.json"
        ).read_text()
    )
    expected = {
        (f["frame_ref"], tuple(c["contact_pixel"])): c
        for f in source_prediction["frames"]
        for c in f["components"]
    }
    for camera in config["camera_ids"]:
        result = workbench.call(
            "query",
            {
                "session_ref": token,
                "scene_id": control.scene_id,
                "camera_id": camera,
                "start": 0,
                "end": 9.8,
            },
        )
        for row in result["observations"]:
            original = expected[row["frame_ref"], tuple(row["contact_pixel"])]
            assert row["world_position"] == original["world_position"]
            if original["world_position"] is None:
                assert row["state"] == "MISSING" and row["missing_reason"] == original["reasons"]
                assert "contact_quality" not in row
            else:
                assert row["contact_quality"]["status"] == "PASS"


def test_missing_layers_are_successful_unavailable_responses(live):
    catalog, workbench, token = live
    control = catalog["blender-contact-control"]
    cameras = [r["camera_id"] for r in control.snapshot()["cameras"]]
    scope = {"session_ref": token, "scene_id": control.scene_id}
    for action in (
        "motion_reconstruction",
        "cross_camera_reconstruction",
        "physical_cross_camera_reconstruction",
        "physical_review",
        "target_reconstruction",
    ):
        request = scope | {"camera_ids": cameras, "start": 0, "end": 9.8}
        if action in {
            "cross_camera_reconstruction",
            "physical_cross_camera_reconstruction",
            "target_reconstruction",
        }:
            request["top_k"] = 3
        if action == "target_reconstruction":
            request["observation_ref"] = control.snapshot()["demo_defaults"]["observation_ref"]
        result = workbench.call(action, request)
        assert result["status"] == "UNAVAILABLE"
        assert result["scope"]["run_id"] == control.run_id
    for provider in (
        workbench.motion_media_provider,
        workbench.association_media_provider,
        workbench.physical_media_provider,
    ):
        assert provider.manifest(control)["status"] == "UNAVAILABLE"
    with pytest.raises(ValueError):
        control.media(catalog["blender-office"].index.frame_records[0]["frame_ref"])


def test_frozen_office_responses_equal_except_quality(live):
    catalog, workbench, token = live
    office = catalog["blender-office"]
    config = json.loads(backend.DEFAULT_CONFIG.read_text())
    cameras = config["camera_ids"]
    results = {
        "snapshot": office.snapshot(),
        "query": [office.query(cam, 0, 9.8) for cam in cameras],
        "cross": office.cross_camera_reconstruction(cameras, 0, 9.8, 3),
        "motion": office.motion_reconstruction(cameras, 0, 9.8),
        "target": workbench.call(
            "target_reconstruction",
            {
                "session_ref": token,
                "scene_id": office.scene_id,
                "camera_ids": cameras,
                "start": 0,
                "end": 9.8,
                "top_k": 3,
                "observation_ref": config["observation_ref"],
            },
        ),
        "physical": office.physical_cross_camera_reconstruction(cameras, 0, 9.8, 3),
        "review": office.physical_review(cameras, 0, 9.8),
    }
    expected = json.loads((REPO / "tests/fixtures/office_demo_v1_response_hashes.json").read_text())
    for name, value in results.items():
        digest = hashlib.sha256(
            json.dumps(
                strip_quality(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        assert digest == expected[name], name
    observations = [r for q in results["query"] for r in q["observations"]]
    assert len(observations) == 31
    assert all("contact_quality" in r for r in observations)
    for timestamp in (0.4, 0.6, 1.8, 2.0, 4.4):
        flagged = [r for r in observations if r["timestamp"] == timestamp]
        assert flagged and all(r["contact_quality"]["status"] == "FLAGGED" for r in flagged)
        assert all(r["contact_quality"]["reasons"] for r in flagged)
    merged = [r for r in observations if r["timestamp"] == 4.4]
    assert len(merged) == 2
    assert all("AMBIGUOUS_MERGE" in r["contact_quality"]["reasons"] for r in merged)
    assert all(r["world_position"] is not None for r in observations)
    assert (
        next(r for r in observations if r["observation_ref"] == config["observation_ref"])[
            "track_ref"
        ]
        == config["track_ref"]
    )
    for value in results.values():
        for row in walk(value):
            if row.get("observation_ref") in office._qualities:
                assert row["contact_quality"] == office._qualities[row["observation_ref"]]


def test_hash_and_catalog_guards(tmp_path):
    fixture = json.loads(backend.DEFAULT_CONFIG.read_text())
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "safe_inputs.json").write_text("{}")
    with pytest.raises(ValueError, match="FIXTURE_SAFE_INPUT_HASH_MISMATCH"):
        backend.load_scene(bundle, fixture)


def test_person_run_uses_hash_pinned_per_run_height_config(tmp_path, monkeypatch):
    from amidst.workbench import contact_scene

    bundle = tmp_path / "person"
    bundle.mkdir()
    (bundle / "safe_inputs.json").write_text("{}")
    contact_path = tmp_path / "contact.json"
    config = json.loads((REPO / "configs/office_person_contact_v2.json").read_text())
    contact_path.write_text(json.dumps(config))
    fixture = {
        "safe_inputs_sha256": hashlib.sha256(b"{}").hexdigest(),
        "contact_config": str(contact_path),
        "contact_config_sha256": hashlib.sha256(contact_path.read_bytes()).hexdigest(),
    }
    captured = []

    class StopAfterConfig(Exception):
        pass

    def capture(*args, **kwargs):
        captured.append(kwargs["contact_config"])
        raise StopAfterConfig

    monkeypatch.setattr(contact_scene, "ContactQualityScene", capture)
    with pytest.raises(StopAfterConfig):
        backend.load_scene(bundle, fixture, perception_version="rgb-mask-contact-v2")
    assert captured[0].assumed_target_height_m == 1.7
    assert captured[0].assumed_target_radius_m == 0.25
    contact_path.write_text("{}")
    with pytest.raises(ValueError, match="FIXTURE_CONTACT_CONFIG_HASH_MISMATCH"):
        backend.load_scene(bundle, fixture)
    presets = json.loads(backend.DEFAULT_PRESETS.read_text())
    presets["presets"].append(presets["presets"][0])
    path = tmp_path / "presets.json"
    path.write_text(json.dumps(presets))
    with pytest.raises(ValueError, match="DUPLICATE_PRESET_SCENE"):
        backend.preset_specs(path, tmp_path, tmp_path)


def test_unmatched_quality():
    assert quality(None) == {
        "version": "rgb-mask-contact-v2",
        "status": "NOT_EVALUATED",
        "reasons": [],
        "pixel_sensitivity_m": None,
        "authority": "QUALITY_FLAG_ONLY_POSITION_UNCHANGED",
    }


def test_mask_ownership_precedes_bbox_and_fallback_is_unambiguous():
    # Two 4-connected components share one 8-connected owner; the proxy point
    # lies outside the actual mask, so contact-point membership is insufficient.
    masks = [np.array([[0, 0], [1, 0], [2, 1], [3, 1]])]
    rows = [{"bbox_xyxy": [0, 0, 2, 4]}]
    assert component_mapping(np.array([[0, 0], [1, 0]]), masks, [9, 9], rows) == (0, [])
    assert component_mapping(np.array([[2, 1], [3, 1]]), masks, [9, 9], rows) == (0, [])
    assert component_mapping(None, masks, [1, 3], rows) == (0, [])
    assert component_mapping(None, masks, [2, 4], rows) == (None, [])
    assert component_mapping(None, masks, [1, 3], rows + rows) == (None, ["AMBIGUOUS_MAPPING"])
    assert component_mapping(np.array([[7, 7]]), masks, [1, 3], rows) == (None, [])
