"""Synthetic text-only safe bundle tests; no source assets, GT or image decoding."""

import hashlib
import json
from dataclasses import replace

import pytest

from amidst.engineering.registry import content_hash
from amidst.workbench.controlled_scene_data import (
    D55_RGB_INDEX_PINS,
    REQUIRED_FILES,
    RGB_INDEX_ADAPTER_NAME,
    RGB_INDEX_ADAPTER_VERSION,
    RequiredInputUnavailable,
    RunRegistration,
    adapt_calibration,
    adapt_rgb_index,
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


def legacy_index(files, manifest):
    """SYNTHETIC D55-shaped metadata; never copies an actual run or image."""
    index = files["rgb_index"]
    index["frames"] = index.pop("records")
    index.update({
        "scene_id": manifest["scene_id"], "scene_version": manifest["scene_version"],
        "source_sha256": manifest["source_sha256"], "data_origin": manifest["data_origin"],
        "sampling": manifest["sampling"], "rgb_ref_base": "RUN_ROOT",
        "expected_grid": {"camera_ids": ["CAM_FIXTURE"], "frame_index_start": 0,
                          "frame_index_end_exclusive": 3, "timestamp_rule": "frame_index / fps"},
    })
    return index


def approve_test_pin(monkeypatch, raw, run_id):
    """Only tests extend the server-owned table with a small synthetic byte hash."""
    import amidst.workbench.controlled_scene_data as module

    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(module, "D55_RGB_INDEX_PINS", {**D55_RGB_INDEX_PINS, digest: run_id})
    return digest


def test_d57_production_pin_list_is_exact():
    assert D55_RGB_INDEX_PINS == {
        "9e43237e9c9ac9ea4f2bc97f65e49103a0ec3946b1b555b9d7fbf59850e97d47":
            "ctrl-lcorr-s1-a-5fps-v1-r001",
        "a5392a6fc5b51257adb82827df376f42290690cbdb52160888eb241f256ecc39":
            "ctrl-lcorr-s1-b1-5fps-v1-r001",
    }


def test_d57_loader_adapts_only_pinned_legacy_in_memory(bundle, monkeypatch):
    root, files, manifest, _, persist, _ = bundle
    legacy_index(files, manifest)
    reg = persist()
    path = root / "safe_bundle/rgb_index.json"
    raw = path.read_bytes()
    original_manifest = (root / "safe_bundle/manifest.json").read_bytes()
    digest = approve_test_pin(monkeypatch, raw, reg.run_id)
    run = load_safe_run(reg)
    assert "frames" not in run.files["rgb_index"]
    assert run.files["rgb_index"]["records"] == files["rgb_index"]["frames"]
    assert run.files["rgb_index"]["sampling"] == files["rgb_index"]["sampling"]
    assert path.read_bytes() == raw
    assert (root / "safe_bundle/manifest.json").read_bytes() == original_manifest
    assert run.input_adapter_receipts == ({
        "adapter_name": RGB_INDEX_ADAPTER_NAME, "adapter_version": RGB_INDEX_ADAPTER_VERSION,
        "source_file_sha256": digest, "source_schema_version": "controlled-scene.rgb-index.v1",
        "source_collection": "frames", "target_collection": "records", "adapted": True,
        "normalized_content_sha256": content_hash(run.files["rgb_index"]),
    },)
    assert not (root / "private_evaluation").exists()


def test_d57_native_records_keeps_manifest_pin_and_reports_identity(bundle):
    _, files, _, reg, _, _ = bundle
    run = load_safe_run(reg)
    assert run.files["rgb_index"] == files["rgb_index"]
    assert run.input_adapter_receipts[0]["adapted"] is False
    assert run.input_adapter_receipts[0]["source_collection"] == "records"
    assert run.input_adapter_receipts[0]["source_file_sha256"] not in D55_RGB_INDEX_PINS


def test_d57_unlisted_legacy_hash_fails_even_with_matching_manifest_pin(bundle):
    _, files, manifest, _, persist, _ = bundle
    legacy_index(files, manifest)
    with pytest.raises(DataIntegrityError, match="LEGACY_RGB_INDEX_PIN_NOT_APPROVED"):
        load_safe_run(persist())


def test_d57_byte_hash_mismatch_fails_before_json_parsing():
    with pytest.raises(DataIntegrityError, match="SAFE_FILE_HASH_MISMATCH"):
        adapt_rgb_index(b"not JSON", expected_file_sha256="0" * 64)


@pytest.mark.parametrize("case", ["dual", "dual_empty_frames", "neither"])
def test_d57_ambiguous_or_absent_collection_key_fails_closed(bundle, case):
    _, files, _, _, persist, _ = bundle
    index = files["rgb_index"]
    if case == "neither":
        index.pop("records")
    else:
        index["frames"] = [] if case == "dual_empty_frames" else index["records"]
    with pytest.raises(DataIntegrityError, match="RGB_INDEX_COLLECTION_KEY_MISMATCH"):
        load_safe_run(persist())


def test_d57_legacy_schema_must_be_exact_even_with_approved_hash(monkeypatch):
    raw = b'{"schema_version":"controlled-scene.rgb-index.v2","run_id":"test","frames":[]}'
    digest = approve_test_pin(monkeypatch, raw, "test")
    with pytest.raises(DataIntegrityError, match="RGB_INDEX_SCHEMA_VERSION_UNSUPPORTED"):
        adapt_rgb_index(raw, expected_file_sha256=digest)


def test_d57_legacy_pin_also_binds_run_id(monkeypatch):
    raw = b'{"schema_version":"controlled-scene.rgb-index.v1","run_id":"test","frames":[]}'
    digest = approve_test_pin(monkeypatch, raw, "other-run")
    with pytest.raises(DataIntegrityError, match="LEGACY_RGB_INDEX_PIN_NOT_APPROVED"):
        adapt_rgb_index(raw, expected_file_sha256=digest)


@pytest.mark.parametrize("field", ["source_sha256", "sampling", "expected_grid"])
def test_d57_legacy_metadata_still_has_to_match_registered_run(bundle, monkeypatch, field):
    root, files, manifest, _, persist, _ = bundle
    index = legacy_index(files, manifest)
    if field == "source_sha256":
        index[field] = "b" * 64
    elif field == "sampling":
        index[field] = {**manifest["sampling"], "duration_s": 2}
    else:
        index[field]["frame_index_end_exclusive"] = 10
    reg = persist()
    approve_test_pin(monkeypatch, (root / "safe_bundle/rgb_index.json").read_bytes(), reg.run_id)
    with pytest.raises(DataIntegrityError, match="RGB_INDEX_BINDING_MISMATCH"):
        load_safe_run(reg)


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


def test_pinned_rgb_disappearing_is_integrity_error_not_missing(bundle):
    root, _, _, reg, _, _ = bundle
    run = load_safe_run(reg)
    (root / "rgb/CAM_FIXTURE/frame_000000.png").unlink()  # synthetic test text only
    with pytest.raises(DataIntegrityError, match="PINNED_RGB_RECORD_MISSING"):
        run.read_rgb("CAM_FIXTURE", 0)
    assert run.read_rgb("CAM_FIXTURE", 1) is None  # explicit missing[] keeps its meaning


def test_pinned_index_omitting_expected_sample_is_integrity_error(bundle):
    _, files, _, _, persist, _ = bundle
    files["rgb_index"]["records"].pop()
    with pytest.raises(DataIntegrityError, match="RGB_INDEX_INCOMPLETE"):
        load_safe_run(persist())


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
