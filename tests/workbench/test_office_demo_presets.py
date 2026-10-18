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
        return {
            k: strip_quality(v)
            for k, v in value.items()
            if k not in {"contact_quality", "ground_estimate"}
        }
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


def test_hybrid_endpoints_and_alias_keep_source_observations_unchanged(live):
    from amidst.engineering.registry import content_hash

    catalog, _, _ = live
    office = catalog["blender-office"]
    observations = [
        r
        for camera in office.index._camera_ids
        for r in office.query(camera, 0, 9.8)["observations"]
    ]
    start = next(
        r for r in observations if r["observation_ref"] == "observation:add9f687d311742321e80dff"
    )
    end = next(
        r for r in observations if r["observation_ref"] == "observation:997166541f223b4f923d8bff"
    )
    assert start["ground_estimate"]["reason"] == "HEAD_ANCHOR_UNRELIABLE"
    assert "AMBIGUOUS_MERGE" in start["ground_estimate"]["contact_quality"]["reasons"]
    assert end["ground_estimate"]["reason"] == "SEGMENT_TOO_LONG"
    assert end["ground_estimate"]["diagnostics"]["raw_interval_length_m"] == pytest.approx(
        10.237160757115856
    )
    for row in observations:
        estimate = row["ground_estimate"]
        assert estimate["contact_quality"] == row["contact_quality"]
        assert estimate["provenance"]["run_ref"] == office.run_id
        assert estimate["output_sha256"] == content_hash(
            {k: v for k, v in estimate.items() if k != "output_sha256"}
        )
        assert row["world_position"] is not None
    alias = office.with_display_identity("test-office-alias", "alias", "test")
    assert all(
        r["ground_estimate"]["provenance"]["scene_id"] == "test-office-alias"
        for r in alias.query(start["camera_id"], 0, 9.8)["observations"]
    )
    assert (
        office._ground_estimates[start["observation_ref"]]["provenance"]["scene_id"]
        == "blender-office"
    )


def test_person_run_uses_declared_prior_on_missing_v2_samples(live):
    from amidst.engineering.perception_v2 import ContactConfig
    from amidst.workbench.blender_scene import ValidationRunPin
    from amidst.workbench.contact_scene import ContactQualityScene

    root = (
        Path(os.environ["OFFICE_TEST_ASSETS"]) / "data/engineering/office_person_20261016_v1/office"
    )
    if not root.is_dir():
        pytest.skip("C6 person run LOCAL bundle is not available")
    config_path = REPO / "configs/hybrid_contact_v1.json"
    config = json.loads(config_path.read_text())
    pin = ValidationRunPin(**json.loads((root / "validation_pin.json").read_text()))
    contact = ContactConfig.model_validate_json(
        (REPO / "configs/office_contact_v2.json").read_text()
    )
    with pytest.raises(ValueError, match="CONTACT_TARGET_DECLARATION_MISMATCH"):
        ContactQualityScene(
            root,
            validation_pin=pin,
            perception_version="rgb-mask-contact-v2",
            contact_config=contact,
            hybrid_config=config,
            hybrid_config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
        )
    scene = ContactQualityScene(
        root,
        validation_pin=pin,
        perception_version="rgb-mask-contact-v2",
        contact_config=contact.model_copy(
            update={
                "assumed_target_height_m": 1.7,
                "assumed_target_radius_m": 0.25,
                "max_speed_m_s": 2.0,
            }
        ),
        hybrid_config=config,
        hybrid_config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
    )
    observations = [
        r for camera in scene.index._camera_ids for r in scene.query(camera, 0, 9.8)["observations"]
    ]
    assert len(observations) == 33
    assert all(r["world_position"] is None and r["state"] == "MISSING" for r in observations)
    assert all("contact_quality" not in r for r in observations)
    assert all(r["ground_estimate"]["contact_quality"]["status"] == "FLAGGED" for r in observations)
    ready = [r for r in observations if r["ground_estimate"]["status"] == "READY"]
    assert ready and all(r["ground_estimate"]["estimate_kind"] == "SEGMENT" for r in ready)
    assert all(r["ground_estimate"]["segment"]["height_prior"]["nominal_m"] == 1.7 for r in ready)
    assert all(
        r["ground_estimate"]["contact_quality"]["reasons"] == r["missing_reason"]
        for r in observations
    )


def test_missing_control_data_keeps_office_available(live, tmp_path):
    _, _, _ = live
    assets = Path(os.environ["OFFICE_TEST_ASSETS"])
    presets = json.loads(backend.DEFAULT_PRESETS.read_text())
    presets["presets"][1]["bundle"] = str(tmp_path / "absent-control")
    path = tmp_path / "presets.json"
    path.write_text(json.dumps(presets))
    catalog = backend.load_presets(path, assets / ".local-worktrees/phase1-finalization", assets)
    assert list(catalog) == ["blender-office"]
    app = backend.application(
        catalog, tmp_path / "reviews.db", REPO, assets / ".local-worktrees/phase1-finalization"
    )
    entries = app.workbench.bootstrap()["scenes"]
    assert [r["scene_id"] for r in entries] == ["blender-office", "blender-contact-control"]
    assert entries[1]["status"] == "UNAVAILABLE"
    assert entries[1]["reason"] == "PRESET_DATA_MISSING"
    assert entries[1]["available"] is False
    assert len(catalog["blender-office"].index.observations) == 31


def test_quality_mapping_failure_keeps_office_and_original_observations(
    live, monkeypatch, tmp_path
):
    from amidst.workbench import contact_scene

    catalog, _, _ = live
    original = catalog["blender-office"]

    def fail(*args):
        raise ValueError("QUALITY_COMPONENT_MISMATCH")

    monkeypatch.setattr(contact_scene, "match_quality", fail)
    degraded = backend.load_scene(original.root, json.loads(backend.DEFAULT_CONFIG.read_text()))
    assert degraded.index.snapshot() == original.index.snapshot()
    assert degraded.snapshot()["contact_quality_status"] == {
        "status": "NOT_EVALUATED",
        "reason": "QUALITY_COMPONENT_MISMATCH",
    }
    for camera in json.loads(backend.DEFAULT_CONFIG.read_text())["camera_ids"]:
        observations = degraded.query(camera, 0, 9.8)["observations"]
        assert strip_quality(observations) == [
            r for r in original.index.observations if r["camera_id"] == camera
        ]
        assert all(r["contact_quality"]["status"] == "NOT_EVALUATED" for r in observations)
        assert all(
            r["contact_quality"]["reasons"] == ["QUALITY_COMPONENT_MISMATCH"] for r in observations
        )
    app = backend.application(
        degraded,
        tmp_path / "reviews.db",
        REPO,
        Path(os.environ["OFFICE_TEST_ASSETS"]) / ".local-worktrees/phase1-finalization",
    )
    assert app.workbench.bootstrap()["scenes"][0]["scene_id"] == "blender-office"
    for response in (
        degraded.cross_camera_reconstruction(
            json.loads(backend.DEFAULT_CONFIG.read_text())["camera_ids"], 0, 9.8
        ),
        degraded.physical_review(
            json.loads(backend.DEFAULT_CONFIG.read_text())["camera_ids"], 0, 9.8
        ),
    ):
        flags = [r["contact_quality"] for r in walk(response) if r.get("observation_ref")]
        assert flags and all(r["status"] == "NOT_EVALUATED" for r in flags)


def test_missing_default_and_optional_hash_mismatch_remain_fatal(monkeypatch, tmp_path):
    specs = [
        {
            "scene_id": sid,
            "label": sid,
            "description": sid,
            "bundle_path": tmp_path,
            "config": {},
            "perception_version": "rgb-mask-contact-v1",
            "load_error": None,
        }
        for sid in ("office", "control")
    ]
    monkeypatch.setattr(backend, "preset_specs", lambda *args: ("office", specs))

    def missing(*args, **kwargs):
        raise FileNotFoundError("PRESET_DATA_MISSING")

    monkeypatch.setattr(backend, "load_scene", missing)
    with pytest.raises(FileNotFoundError):
        backend.load_presets(tmp_path, tmp_path, tmp_path)
    # Place the optional entry first to exercise rejection before default loading.
    specs.reverse()

    def corrupted(*args, **kwargs):
        raise ValueError("FIXTURE_SAFE_INPUT_HASH_MISMATCH")

    monkeypatch.setattr(backend, "load_scene", corrupted)
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        backend.load_presets(tmp_path, tmp_path, tmp_path)


def test_quality_hash_error_is_not_downgraded(live, monkeypatch):
    from amidst.workbench import contact_scene

    def fail(*args):
        raise ValueError("QUALITY_RGB_HASH_MISMATCH")

    monkeypatch.setattr(contact_scene, "match_quality", fail)
    original = live[0]["blender-office"]
    with pytest.raises(ValueError, match="QUALITY_RGB_HASH_MISMATCH"):
        backend.load_scene(original.root, json.loads(backend.DEFAULT_CONFIG.read_text()))


def test_person_split_preset_uses_pinned_config_and_d18_defaults(live):
    assets = Path(os.environ["OFFICE_TEST_ASSETS"])
    catalog = backend.load_presets(
        REPO / "configs/office_demo_presets_person_v1.json",
        assets / ".local-worktrees/phase1-finalization",
        assets,
    )
    assert list(catalog) == ["blender-office", "blender-contact-control", "blender-office-person"]
    person = catalog["blender-office-person"]
    fixture = json.loads((REPO / "configs/office_demo_office_person_fixture_v1.json").read_text())
    assert person.run_id == fixture["run_id"]
    assert person.snapshot()["demo_defaults"]["selected_timestamp"] == 4.6
    assert (
        person.snapshot()["demo_defaults"]["observation_ref"]
        == fixture["blind_interval"]["start_observation_ref"]
    )
    observations = {r["observation_ref"]: r for r in person.index.observations}
    assert len(observations) == 33
    assert all(
        r["state"] == "MISSING" and r["world_position"] is None for r in observations.values()
    )
    interval = fixture["blind_interval"]
    for endpoint in ("start", "end"):
        row = observations[interval[endpoint + "_observation_ref"]]
        assert row["timestamp"] == interval[endpoint + "_s"]
        assert row["camera_id"] == interval[endpoint + "_camera_id"]
    assert not [r for r in observations.values() if 4.6 < r["timestamp"] < 8.2]
    assert fixture["next_observed_timestamp"] == 8.2
    assert interval["interior_time_range_s"] == [4.8, 8.0]
    assert interval["endpoint_substitution"] == "NOT_PERFORMED"
    assert all(
        g["provenance"]["run_parameters"]["body_radius_m"] == 0.25
        for g in person._ground_estimates.values()
    )


def test_person_contact_config_integrity_rejected_before_scene_load():
    from amidst.workbench.scene_errors import DataIntegrityError

    fixture = json.loads((REPO / "configs/office_demo_office_person_fixture_v1.json").read_text())
    fixture["contact_config_sha256"] = "0" * 64
    with pytest.raises(DataIntegrityError, match="FIXTURE_CONTACT_CONFIG_HASH_MISMATCH"):
        backend.contact_config_path(fixture)
    fixture["contact_config"] = "../outside.json"
    with pytest.raises(DataIntegrityError, match="FIXTURE_CONTACT_CONFIG_PATH_REJECTED"):
        backend.contact_config_path(fixture)
