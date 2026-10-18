"""Synthetic text-only safe bundle tests; no source assets, GT or image decoding."""

import hashlib
import json
from dataclasses import replace

import pytest

from amidst.engineering.registry import content_hash
from amidst.workbench.controlled_scene_data import (
    REQUIRED_FILES,
    RequiredInputUnavailable,
    RunRegistration,
    adapt_calibration,
    load_safe_run,
    parse_json,
    read_regular,
)
from amidst.workbench.controlled_scene_evaluation import (
    load_private_manifest_for_frozen_evaluation,
)
from amidst.workbench.scene_errors import DataIntegrityError


def seal(value, key):
    value[key] = content_hash({k: v for k, v in value.items() if k != key})
    return value


def optics():
    return seal({
        "schema_version": "controlled-scene.camera.v1", "camera_id": "CAM_FIXTURE",
        "camera_to_world": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 2], [0, 0, 0, 1]],
        "convention": "BLENDER_NEG_Z_UP_Y", "fx": 800, "fy": 800, "cx": 480, "cy": 270,
        "width": 960, "height": 540, "pixel_origin": "TOP_LEFT_CONTINUOUS",
        "pixel_aspect_xy": [1, 1], "render_resolution_percentage": 100,
        "shift_x": 0, "shift_y": 0, "sensor_fit": "HORIZONTAL", "sensor_width_mm": 36,
        "sensor_height_mm": 20.25, "focal_length_mm": 30, "clip_start": .05, "clip_end": 60,
        "distortion": None, "camera_model": "PINHOLE", "floor_id": "FLOOR_FIXTURE",
        "zone_id": None, "meters_per_unit": 1, "static_validity": "STATIC_SCENE_V1",
    }, "calibration_sha256")


def binding(run="fixture-data", clock="clock:fixture-data"):
    return seal({"run_id": run, "camera_id": "CAM_FIXTURE", "clock_id": clock,
                 "valid_time_range_s": [0, .6], "visibility_index_ref": None}, "binding_sha256")


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path.resolve() / "run"
    (root / "safe_bundle").mkdir(parents=True)
    geom = {"vertices_m": [[0, 0, .7], [1, 0, .7], [0, 1, .7]], "faces": [[0, 1, 2]]}
    files = {
        "geometry:WALK_FIXTURE": geom,
        "scene_static": {"schema_version": "controlled-scene.static.v1",
                         "scene_id": "fixture-scene", "scene_version": 1, "frame_id": "world",
                         "length_unit": "m", "time_unit": "s",
                         "world_axes": "BLENDER_Z_UP_RIGHT_HANDED",
                         "source_static_sha256": "b" * 64, "floors": [{
                             "floor_id": "FLOOR_FIXTURE", "source_static_sha256": "b" * 64,
                             "support_plane": {"point_m": [0, 0, .7], "normal": [0, 0, 1]},
                             "support_surface_ids": ["WALK_FIXTURE"],
                             "approved_scope_ref": "fixture-only"}],
                         "objects": [{"id": "WALK_FIXTURE", "class": "WALKABLE",
                                      "allowed_purposes": ["WALKABILITY"],
                                      "approval_status": "APPROVED",
                                      "scope_ref": "fixture-only",
                                      "approval_ref": "fixture-approval",
                                      "approval_sha256": "e" * 64, "display_only": False,
                                      "source_mesh": "fixture-triangle", "geometry_version": 1,
                                      "geometry_encoding_version": "world-triangles-v1",
                                      "bounds_m": [[0, 0, .7], [1, 1, .7]],
                                      "source_method": "ANNOTATED_AT_CREATION",
                                      "source_object_id": "WALK_FIXTURE",
                                      "transform_applied": "WORLD_METRES",
                                      "geometry_ref": "safe_bundle/geometry.json",
                                      "geometry_sha256": "pending"}]},
        "cameras": {"cameras": [optics()], "run_bindings": [binding()]},
        "event_query": {"schema_version": "controlled-scene.event-query.v1",
                        "event_id": "FIXTURE", "run_id": "fixture-data", "duration_s": .6,
                        "sampling_version": "5fps-v1", "camera_ids": ["CAM_FIXTURE"],
                        "suggested_queries": []},
        "runtime_profile": {"schema_version": "controlled-scene.runtime-profile.v1",
                            "run_id": "fixture-data", "clock_id": "clock:fixture-data",
                            "sampling_version": "5fps-v1", "camera_ids": ["CAM_FIXTURE"],
                            "required_inputs": sorted(REQUIRED_FILES), "api_available": []},
        "rgb_index": {"schema_version": "controlled-scene.rgb-index.v1", "run_id": "fixture-data",
                      "clock_id": "clock:fixture-data", "records": [], "missing": [{
                          "camera_id": "CAM_FIXTURE", "frame_index": 1, "timestamp_s": .2,
                          "reason": "RGB_RECORD_ABSENT"}]},
    }
    for i in [0, 2]:
        ref = f"rgb/CAM_FIXTURE/frame_{i:06d}.png"
        # Arbitrary test text, deliberately not an image or renderer output.
        data = f"SYNTHETIC TEXT RECORD {i}".encode()
        path = root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        files["rgb_index"]["records"].append({"camera_id": "CAM_FIXTURE", "frame_index": i,
                                               "timestamp_s": i / 5, "rgb_ref": ref,
                                               "file_sha256": hashlib.sha256(data).hexdigest()})
    manifest = {"schema_version": "controlled-scene.manifest.v1", "scene_id": "fixture-scene",
                "scene_version": 1, "run_id": "fixture-data", "clock_id": "clock:fixture-data",
                "source_sha256": "a" * 64, "data_origin": "ACTUAL_BLENDER",
                "config_pins": {"body_prior_sha256": "c" * 64,
                                "detector_config_sha256": "d" * 64},
                "sampling": {"fps": 5, "image_size_px": [960, 540], "format": "PNG_RGB8",
                             "sampling_version": "5fps-v1", "duration_s": .6,
                             "sample_count_per_camera": 3, "last_timestamp_s": .4},
                "allowlist": {}}

    def persist():
        order = ["geometry:WALK_FIXTURE", *sorted(REQUIRED_FILES)]
        for kind in order:
            name = "geometry.json" if kind.startswith("geometry:") else kind + ".json"
            raw = json.dumps(files[kind]).encode()
            (root / "safe_bundle" / name).write_bytes(raw)
            manifest["allowlist"][kind] = {"path": "safe_bundle/" + name,
                                           "file_sha256": hashlib.sha256(raw).hexdigest()}
            if kind.startswith("geometry:"):
                files["scene_static"]["objects"][0]["geometry_sha256"] = (
                    hashlib.sha256(raw).hexdigest())
        return persist_manifest()

    def persist_manifest():
        raw = json.dumps(manifest).encode()
        (root / "safe_bundle/manifest.json").write_bytes(raw)
        return RunRegistration(root, hashlib.sha256(raw).hexdigest(), "fixture-scene",
                               "fixture-data", "a" * 64)

    reg = persist()
    return root, files, manifest, reg, persist, persist_manifest


def test_safe_loader_never_reads_private_or_docs(bundle, monkeypatch):
    root, _, _, reg, _, _ = bundle
    import amidst.workbench.controlled_scene_data as module

    reader, opened = module.read_regular, []

    def audit(base, path, **kw):
        opened.append(path)
        assert path.startswith("safe_bundle/")
        return reader(base, path, **kw)

    monkeypatch.setattr(module, "read_regular", audit)
    result = load_safe_run(reg)
    assert result.files["scene_static"]["floors"][0]["support_plane"]["point_m"][2] == .7
    assert len(opened) == 7
    assert not (root / "private_evaluation").exists()


def test_private_named_file_is_not_even_opened_as_safe_alias(bundle, monkeypatch):
    _, _, m, _, _, persist_manifest = bundle
    m["allowlist"]["cameras"]["path"] = "safe_bundle/production_manifest.json"
    reg = persist_manifest()
    import amidst.workbench.controlled_scene_data as module

    reader, opened = module.read_regular, []

    def audit(root, path, **kwargs):
        opened.append(path)
        return reader(root, path, **kwargs)

    monkeypatch.setattr(module, "read_regular", audit)
    with pytest.raises(DataIntegrityError, match="SAFE_ALLOWLIST_REJECTED"):
        load_safe_run(reg)
    assert "safe_bundle/production_manifest.json" not in opened


def test_rgb_missing_does_not_fallback_and_hash_is_fatal(bundle):
    root, _, _, reg, _, _ = bundle
    run = load_safe_run(reg)
    assert run.read_rgb("CAM_FIXTURE", 1) is None
    assert run.read_rgb("CAM_FIXTURE", 0) == b"SYNTHETIC TEXT RECORD 0"
    (root / "rgb/CAM_FIXTURE/frame_000000.png").write_bytes(b"changed test text")
    with pytest.raises(DataIntegrityError, match="RGB_RECORD_HASH_MISMATCH"):
        run.read_rgb("CAM_FIXTURE", 0)


@pytest.mark.parametrize("kind", sorted(REQUIRED_FILES))
def test_missing_required_input_never_ready(bundle, kind):
    root, _, _, reg, _, _ = bundle
    (root / reg_path(reg, kind)).unlink()
    with pytest.raises(RequiredInputUnavailable):
        load_safe_run(reg)


def reg_path(reg, kind):
    m = json.loads((reg.run_root / "safe_bundle/manifest.json").read_text())
    return m["allowlist"][kind]["path"]


@pytest.mark.parametrize("case", ["manifest_hash", "safe_hash", "source", "clock", "allowlist",
                                "config_pin", "private_field", "missing_index", "origin"])
def test_manifest_boundaries(bundle, case):
    root, files, m, reg, persist, persist_manifest = bundle
    expected = DataIntegrityError
    if case == "manifest_hash":
        reg = replace(reg, manifest_sha256="0" * 64)
    elif case == "safe_hash":
        (root / "safe_bundle/cameras.json").write_text("{}")
    elif case == "source":
        reg = replace(reg, source_sha256="f" * 64)
    elif case == "clock":
        m["clock_id"] = "clock:wrong"
        reg = persist_manifest()
    elif case == "allowlist":
        m["allowlist"]["cameras"]["path"] = "private_evaluation/production_manifest.json"
        reg = persist_manifest()
    elif case == "config_pin":
        m["config_pins"]["body_prior_sha256"] = "bad"
        reg = persist_manifest()
    elif case == "private_field":
        files["runtime_profile"]["designed_blind_intervals"] = []
        reg = persist()
    elif case == "missing_index":
        del m["allowlist"]["rgb_index"]
        reg = persist_manifest()
        expected = RequiredInputUnavailable
    elif case == "origin":
        m["data_origin"] = "SYNTHETIC_FIXTURE"
        reg = persist_manifest()
    with pytest.raises(expected):
        load_safe_run(reg)


@pytest.mark.parametrize("field,value", [("clock_id", "other"), ("run_id", "other"),
                                        ("camera_id", "other")])
def test_calibration_run_binding_separate(field, value):
    c, b = optics(), binding()
    b[field] = value
    seal(b, "binding_sha256")
    with pytest.raises(DataIntegrityError, match="BINDING_MISMATCH"):
        adapt_calibration(c, b, run_id="fixture-data", clock_id="clock:fixture-data", duration_s=.6)


def test_same_optical_hash_across_clocks_and_no_scale():
    c = optics()
    a = adapt_calibration(c, binding(), run_id="fixture-data", clock_id="clock:fixture-data",
                          duration_s=.6)
    b = adapt_calibration(c, binding("other", "clock:other"), run_id="other",
                          clock_id="clock:other", duration_s=.6)
    assert a.optical_metadata["calibration_sha256"] == b.optical_metadata["calibration_sha256"]
    assert a.optics.camera_to_world == b.optics.camera_to_world
    c["camera_to_world"][0][0] = 2
    seal(c, "calibration_sha256")
    with pytest.raises(DataIntegrityError, match="NONRIGID"):
        adapt_calibration(c, binding(), run_id="fixture-data", clock_id="clock:fixture-data",
                          duration_s=.6)


@pytest.mark.parametrize("case", ["geometry", "purpose", "duplicate", "grid", "index_clock"])
def test_static_geometry_and_index_guards(bundle, case):
    _, files, _, _, persist, _ = bundle
    if case == "geometry":
        files["geometry:WALK_FIXTURE"]["faces"] = []
    elif case == "purpose":
        files["scene_static"]["objects"][0]["approval_status"] = "NOT_EVALUATED"
    elif case == "duplicate":
        files["scene_static"]["objects"] *= 2
    elif case == "grid":
        files["rgb_index"]["records"][0]["timestamp_s"] = .1
    else:
        files["rgb_index"]["clock_id"] = "wrong"
    with pytest.raises(DataIntegrityError):
        load_safe_run(persist())


@pytest.mark.parametrize("case", ["calibration_hash", "binding_hash", "dimensions", "sensor",
                                "display_authority", "approval_pin", "geometry_reference"])
def test_calibration_and_geometry_pin_guards(bundle, case):
    _, files, _, _, persist, _ = bundle
    c = files["cameras"]["cameras"][0]
    if case == "calibration_hash":
        c["fx"] += 1
    elif case == "binding_hash":
        files["cameras"]["run_bindings"][0]["clock_id"] = "other"
    elif case == "dimensions":
        c["width"] = 512
        seal(c, "calibration_sha256")
    elif case == "sensor":
        c["sensor_width_mm"] = -1
        seal(c, "calibration_sha256")
    elif case == "display_authority":
        files["scene_static"]["objects"][0]["display_only"] = True
    elif case == "approval_pin":
        files["scene_static"]["objects"][0]["approval_sha256"] = "bad"
    else:
        files["scene_static"]["objects"][0]["geometry_ref"] = "safe_bundle/other.json"
    with pytest.raises(DataIntegrityError):
        load_safe_run(persist())


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'[]'])
def test_strict_json(raw):
    with pytest.raises(DataIntegrityError):
        parse_json(raw)


def test_symlink_ancestors_and_escape_rejected(tmp_path):
    root = tmp_path.resolve()
    (root / "text").write_text("secret test text")
    (root / "link").symlink_to(root / "text")
    (root / "directory").symlink_to(root, target_is_directory=True)
    for relative in ["link", "directory/text", "../text", "/text", "a/../text", "a\\text"]:
        with pytest.raises(DataIntegrityError):
            read_regular(root, relative)


def test_private_manifest_only_after_frozen_hash_check(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    raw = b'{"run_id":"SYNTHETIC","evaluation_entries":[]}'
    (root / "production_manifest.json").write_bytes(raw)
    output = b"synthetic frozen output text"
    import amidst.workbench.controlled_scene_evaluation as module

    reader, opened = module.read_regular, []

    def audit(*args, **kwargs):
        opened.append(args[1])
        return reader(*args, **kwargs)

    monkeypatch.setattr(module, "read_regular", audit)
    with pytest.raises(DataIntegrityError, match="FROZEN_OUTPUT"):
        load_private_manifest_for_frozen_evaluation(
            root, manifest_sha256=hashlib.sha256(raw).hexdigest(), frozen_output=output,
            frozen_output_sha256="0" * 64)
    assert opened == []
    assert load_private_manifest_for_frozen_evaluation(
        root, manifest_sha256=hashlib.sha256(raw).hexdigest(), frozen_output=output,
        frozen_output_sha256=hashlib.sha256(output).hexdigest())["run_id"] == "SYNTHETIC"
    assert opened == ["production_manifest.json"]
