"""Renderer/evaluation-only SYNTHETIC static references; no real RGB or actor data."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("d124_c1", REPO / "scripts/check_r004_d124_c1.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


@pytest.fixture
def method():
    return CHECK.load_method((REPO / CHECK.METHOD_PATH).read_bytes())


def camera():
    return {"camera_id": "CAM_W1", "camera_to_world": [[1, 0, 0, 0], [0, 1, 0, 0],
            [0, 0, 1, 0], [0, 0, 0, 1]], "clip_start": 0.1, "clip_end": 100,
            "fx": 1, "fy": 1, "cx": 1, "cy": 1, "width": 2, "height": 2}


def test_early_witness_rejects_only_static_reference_and_has_63_samples(method):
    result = CHECK.static_reference(method, camera(), [], [[0, 0, -4], [0.1, 0, -4]])
    assert result["first_static_witness_s"] == 8.0
    assert result["required_t_V_earliest_s"] == 10.4
    assert result["selected_t_V_necessary_condition"] == "FAIL_ON_SELECTED_STATIC_REFERENCE"
    cage = result["declared_cage"]
    assert cage["sample_count"] == 63
    assert {row["height_m"] for row in cage["samples"]} == set(CHECK.HEIGHTS)
    assert cage["full_cage_necessary_condition"] == "NOT_SUFFICIENT_FOR_PASS"


def test_late_or_absent_witness_never_claims_body_visibility_pass(method):
    late = CHECK.static_reference(method, camera(), [], [[-40, 0, -4], [0, 0, -4]])
    assert late["first_static_witness_s"] >= 10.4
    assert late["selected_t_V_necessary_condition"] == "NOT_REFUTED_ON_SELECTED_STATIC_REFERENCE"
    absent = CHECK.static_reference(method, camera(), [], [[-40, 0, -4], [-39, 0, -4]])
    assert absent["first_static_witness_s"] is None
    assert absent["selected_t_V_necessary_condition"] == "UNKNOWN_NO_STATIC_WITNESS"


@pytest.mark.parametrize("location", ["safe", "safe_static", "public", "repo"])
def test_output_cannot_enter_safe_or_nonprivate_paths(tmp_path, location):
    repo = tmp_path / "repo"
    repo.mkdir()
    folder = repo / "gt_private" if location == "repo" else tmp_path / location / "gt_private"
    if location == "public":
        folder = tmp_path / "public"
    folder.mkdir(parents=True)
    with pytest.raises(ValueError):
        CHECK.private_output(folder / "report.json", repo)


def test_private_output_refuses_existing_or_symlinked_file(tmp_path):
    folder = tmp_path / "gt_private"
    folder.mkdir()
    target = folder / "report.json"
    assert CHECK.private_output(target, tmp_path / "repo") == target
    target.write_text("retained")
    with pytest.raises(ValueError):
        CHECK.private_output(target, tmp_path / "repo")
    link = folder / "link.json"
    link.symlink_to(target)
    with pytest.raises(ValueError):
        CHECK.private_output(link, tmp_path / "repo")
    assert target.read_text() == "retained"


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}'])
def test_metadata_rejects_ambiguous_or_nonfinite_bytes(raw):
    with pytest.raises(ValueError):
        CHECK.strict_json(raw)


def test_small_report_keeps_eight_gib_disk_floor(tmp_path):
    output = tmp_path / "report.json"
    CHECK.require_output_space(output, disk_usage=lambda _: SimpleNamespace(free=8 * 1024**3))
    with pytest.raises(ValueError, match="STOP_BELOW_8_GIB"):
        CHECK.require_output_space(output, 1,
                                   disk_usage=lambda _: SimpleNamespace(free=8 * 1024**3))
    with pytest.raises(ValueError, match="STOP_BELOW_8_GIB"):
        CHECK.require_output_space(output,
                                   disk_usage=lambda _: SimpleNamespace(free=8 * 1024**3 - 1))


def test_audit_binds_config_to_synthetic_pinned_inputs(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    static = tmp_path / "static"
    paths = {"catalog": static / "safe_static/cameras.json",
             "geometry": static / "safe_static/static_geometry.PROPOSED.json",
             "route": repo / CHECK.ROUTE_PATH, "freeze": repo / CHECK.FREEZE_PATH,
             "method": repo / CHECK.METHOD_PATH}
    # Entire authored fixture is synthetic; no actual script/keyframe/GT input.
    times = [8000000, 8110731, 8155024, 11000000]
    route_raw = json.dumps({"planning_waypoints": [
        {"planned_source_time_us": t, "foot_anchor_world_m": [(t - 8000000) / 1000000, 0, -4],
         "interpolation_to_next": "LINEAR_PROPOSED"} for t in times]}).encode()
    freeze = {"source_pins": {"source_sha256": CHECK.SOURCE_SHA256},
              "runs": [{"scenario": "A4-1", "producer_script": {
                  "path": CHECK.ROUTE_PATH, "sha256": CHECK.digest(route_raw)}}]}
    values = {"catalog": json.dumps({"cameras": [camera()]}).encode(),
              "geometry": json.dumps({"source_sha256": CHECK.SOURCE_SHA256, "objects": []}).encode(),
              "route": route_raw, "method": (REPO / CHECK.METHOD_PATH).read_bytes()}
    freeze["source_pins"]["catalog_sha256"] = CHECK.digest(values["catalog"])
    values["freeze"] = json.dumps(freeze).encode()
    pins = {key: CHECK.digest(raw) for key, raw in values.items()}
    monkeypatch.setattr(CHECK, "PINS", pins)
    for key, path in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(values[key])
    config = {"source_sha256": CHECK.SOURCE_SHA256,
              "freeze": {"path": CHECK.FREEZE_PATH, "sha256": pins["freeze"]},
              "catalog_sha256": pins["catalog"],
              "boundary": "PRIVATE_PRODUCER_ONLY_NEVER_INFERENCE_INPUT",
              "render": {"fps": 5, "sample_interval_us": 200000},
              "runs": {"A4-1": {"new_run_id": CHECK.NEW_RUN_ID,
                  "new_clock_id": "clock:r004:a4:declared-demo:v1:d124-v1",
                  "source_duration_us": 50000000, "sample_count_per_camera": 250}}}
    producer = repo / "producer.json"
    producer.write_text(json.dumps(config))
    kwargs = dict(repo=repo, static_root=static, new_run_id=CHECK.NEW_RUN_ID,
                  producer_config=producer, producer_config_sha256=CHECK.digest(producer.read_bytes()))
    report = CHECK.audit(**kwargs)
    assert report["input_sha256"]["producer_config"] == kwargs["producer_config_sha256"]
    assert report["source_range_s"] == [8.0, 11.0]
    assert report["whole_body_visibility"] == report["detector_visibility"] == "UNKNOWN"
    assert report["actual_t_V_s"] is None and report["scoring_changed"] is False
    assert report["rgb_read"] is report["render_performed"] is report["inference_performed"] is False
    with pytest.raises(ValueError, match="producer config pin mismatch"):
        CHECK.audit(**(kwargs | {"producer_config_sha256": "0" * 64}))
    with pytest.raises(ValueError, match="new run required"):
        CHECK.audit(**(kwargs | {"new_run_id": "original-run"}))
    producer.write_text(json.dumps(config | {"catalog_sha256": "0" * 64}))
    with pytest.raises(ValueError, match="catalog binding mismatch"):
        CHECK.audit(**(kwargs | {"producer_config_sha256": CHECK.digest(producer.read_bytes())}))
