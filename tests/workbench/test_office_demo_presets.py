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


@pytest.mark.parametrize("failure", ["missing", "invalid_json", "scene_mismatch"])
def test_optional_fixture_layer_failures(monkeypatch, tmp_path, capsys, failure):
    (tmp_path / "default.json").write_text(json.dumps({"scene_id": "default"}))
    optional = tmp_path / "optional.json"
    if failure != "missing":
        optional.write_text("{" if failure == "invalid_json" else '{"scene_id":"wrong"}')
    presets = tmp_path / "presets.json"
    presets.write_text(
        json.dumps(
            {
                "schema_version": "office-demo.presets.v1",
                "default_scene_id": "default",
                "presets": [
                    {"scene_id": sid, "fixture": file, "bundle_root": "assets", "bundle": "bundle"}
                    for sid, file in [("default", "default.json"), ("optional", "optional.json")]
                ],
            }
        )
    )
    monkeypatch.setattr(backend, "REPO", tmp_path)
    if failure == "scene_mismatch":
        with pytest.raises(ValueError, match="PRESET_FIXTURE_SCENE_MISMATCH"):
            backend.preset_specs(presets, tmp_path, tmp_path)
    else:
        _, specs = backend.preset_specs(presets, tmp_path, tmp_path)
        assert specs[1]["config"] is None and specs[1]["load_error"]
        err = capsys.readouterr().err
        assert '"scene_id": "optional"' in err
        assert ("FileNotFoundError" if failure == "missing" else "JSONDecodeError") in err
        assert str(tmp_path) not in err


@pytest.mark.parametrize("failure", ["size", "symlink", "frame_count", "camera"])
def test_bundle_integrity_branches_reject(failure, tmp_path):
    asset = tmp_path / "assets"
    asset.mkdir()
    frame = asset / "image.png"
    frame.write_bytes(b"RGB")
    manifest = {"source_path": str(frame), "dataset_path": str(frame), "asset_root": str(asset)}
    safe = {
        "frames": [
            {"camera_id": cam, "local_path": str(frame), "byte_count": 3}
            for cam in ("A", "B")
            for _ in range(50)
        ]
    }
    expected = "PRESET_MEDIA_INTEGRITY_MISMATCH"
    if failure == "size":
        safe["frames"][0]["byte_count"] = 4
    elif failure == "symlink":
        link = asset / "link.png"
        link.symlink_to(frame)
        safe["frames"][0]["local_path"] = str(link)
    elif failure == "frame_count":
        safe["frames"].pop()
        expected = "PRESET_FRAME_CAMERA_MISMATCH"
    else:
        safe["frames"][0]["camera_id"] = "UNKNOWN"
        expected = "PRESET_FRAME_CAMERA_MISMATCH"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    path = tmp_path / "safe_inputs.json"
    path.write_text(json.dumps(safe))
    with pytest.raises(ValueError, match=expected):
        backend.validate_bundle_files(
            tmp_path, {"safe_inputs_sha256": backend.raw_hash(path), "camera_ids": ["A", "B"]}
        )


def test_optional_real_fixture_binding_and_stale_manifest_are_fatal(live, monkeypatch, tmp_path):
    assets = Path(os.environ["OFFICE_TEST_ASSETS"])
    evidence = assets / ".local-worktrees/phase1-finalization"
    presets = json.loads(backend.DEFAULT_PRESETS.read_text())
    optional = presets["presets"][1]
    fixture = json.loads((REPO / optional["fixture"]).read_text())
    fixture["run_id"] = "wrong-run"
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(fixture))
    optional["fixture"] = str(fixture_path)
    path = tmp_path / "presets.json"
    path.write_text(json.dumps(presets))
    with pytest.raises(ValueError, match="FIXTURE_BINDING_MISMATCH:run_id"):
        backend.load_presets(path, evidence, assets)
    # Inject stale manifest metadata in memory; never copy/write source/calibration/media.
    control = live[0]["blender-contact-control"]
    manifest = json.loads((control.root / "manifest.json").read_text())
    manifest["source_integrity"]["byte_count"] += 1
    original_read = Path.read_bytes

    def stale_read(file):
        if file == control.root / "manifest.json":
            return json.dumps(manifest).encode()
        return original_read(file)

    monkeypatch.setattr(Path, "read_bytes", stale_read)
    optional["fixture"] = str(REPO / "configs/office_demo_contact_control_fixture_v1.json")
    path.write_text(json.dumps(presets))
    with pytest.raises(ValueError, match="BLENDER_SCENE_STALE"):
        backend.load_presets(path, evidence, assets)


@pytest.mark.parametrize(
    "marker",
    ["PRESET_DEFAULT_OBSERVATION_MISMATCH", "FRAME_CAMERA_MISMATCH", "FLOOR_SOURCE_MISMATCH"],
)
def test_new_integrity_markers_are_not_optional_availability(marker):
    from amidst.workbench.scene_errors import integrity_error

    assert integrity_error(ValueError(marker))


def test_real_default_observation_mismatch_is_fatal(live, tmp_path):
    assets = Path(os.environ["OFFICE_TEST_ASSETS"])
    presets = json.loads(backend.DEFAULT_PRESETS.read_text())
    fixture = json.loads((REPO / presets["presets"][1]["fixture"]).read_text())
    fixture["observation_ref"] = "observation:" + "0" * 24
    altered = tmp_path / "fixture.json"
    altered.write_text(json.dumps(fixture))
    presets["presets"][1]["fixture"] = str(altered)
    path = tmp_path / "presets.json"
    path.write_text(json.dumps(presets))
    with pytest.raises(ValueError, match="PRESET_DEFAULT_OBSERVATION_MISMATCH"):
        backend.load_presets(path, assets / ".local-worktrees/phase1-finalization", assets)


@pytest.mark.parametrize("failure", ["frame", "floor"])
def test_real_index_integrity_branches(live, failure):
    import copy

    from amidst.workbench.frame_baseline import BaselineFrameIndex
    from amidst.workbench.scene_errors import integrity_error

    inputs = copy.deepcopy(live[0]["blender-office"]._inputs)
    if failure == "frame":
        inputs["frames"][0]["width"] += 1
    else:
        inputs["floor_plane"]["source_sha256"] = "0" * 64
    with pytest.raises(ValueError) as caught:
        BaselineFrameIndex(inputs)
    assert integrity_error(caught.value)


def test_optional_preset_bug_logs_type_and_scene_without_message(monkeypatch, tmp_path, capsys):
    spec = {
        "scene_id": "optional",
        "label": "optional",
        "description": "test",
        "bundle_path": tmp_path,
        "config": {},
        "perception_version": "rgb-mask-contact-v2",
        "load_error": None,
    }
    monkeypatch.setattr(backend, "preset_specs", lambda *a: ("default", [spec]))

    def fail(*a, **k):
        raise RuntimeError("private /path must never reach public or stderr")

    monkeypatch.setattr(backend, "load_scene", fail)
    catalog = backend.load_presets(tmp_path, tmp_path, tmp_path)
    assert catalog.unavailable[0]["reason"] == "PRESET_LOAD_FAILED"
    err = capsys.readouterr().err
    assert '"scene_id": "optional"' in err and '"error_type": "RuntimeError"' in err
    assert "private" not in err


def test_v2_quality_bug_degrades_without_changing_missing_or_index(live, capsys):
    import copy

    from amidst.workbench.contact_scene import ContactQualityScene

    original = live[0]["blender-contact-control"]
    degraded = copy.copy(original)
    degraded._snapshot = copy.deepcopy(original._snapshot)
    before = copy.deepcopy(original.index.observations)
    ContactQualityScene._set_qualities(degraded, {"frames": [{"components": [{}]}]}, None)
    assert degraded._snapshot["contact_quality_status"] == {
        "status": "NOT_EVALUATED",
        "reason": "QUALITY_MAPPING_FAILED",
    }
    assert degraded.index.observations == before
    assert set(degraded._qualities) == {
        r["observation_ref"] for r in before if r["world_position"] is not None
    }
    assert all(q["status"] == "NOT_EVALUATED" for q in degraded._qualities.values())
    assert any(r["state"] == "MISSING" and r["world_position"] is None for r in before)
    err = capsys.readouterr().err
    assert '"error_type": "KeyError"' in err and original.scene_id in err


def test_v2_prediction_hash_and_v1_telemetry_hash_reject_before_downgrade(live, monkeypatch):
    from amidst.workbench import contact_scene
    from amidst.workbench.frame_baseline import BaselineFrameIndex

    fixture = json.loads((REPO / "configs/office_demo_contact_control_fixture_v1.json").read_text())
    monkeypatch.setattr(
        contact_scene,
        "produce_contact_v2",
        lambda *a: {"frames": [{"reasons": ["RGB_HASH_MISMATCH"]}]},
    )
    with pytest.raises(ValueError, match="RGB_HASH_MISMATCH"):
        backend.load_scene(
            live[0]["blender-contact-control"].root,
            fixture,
            perception_version="rgb-mask-contact-v2",
        )
    monkeypatch.setattr(
        BaselineFrameIndex,
        "telemetry",
        property(lambda _: {"frame_status_counts": {"HASH_MISMATCH": 1}}),
    )
    with pytest.raises(ValueError, match="RGB_HASH_MISMATCH"):
        backend.load_scene(
            live[0]["blender-office"].root, json.loads(backend.DEFAULT_CONFIG.read_text())
        )
