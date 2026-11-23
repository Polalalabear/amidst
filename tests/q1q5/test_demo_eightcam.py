"""The optional workbench sources bind the pinned A4-1/B4-1 observations."""

import os
import sys
from pathlib import Path

import pytest

SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts")
sys.path.insert(0, SCRIPTS)
try:
    import demo_dependency_config as dependency
    from demo_eightcam import RUN_DESCRIPTOR, RUN_ID, EightCamSource, prepare_eightcam
    from serve_demo_integration import Demo
finally:
    sys.path.remove(SCRIPTS)


def test_missing_optional_eightcam_source_preserves_unknown(tmp_path):
    assert prepare_eightcam(None) == (None, "ROOT_NOT_CONFIGURED")
    assert prepare_eightcam(tmp_path / "missing") == (None, "SAFE_BUNDLE_MISSING")
    assert prepare_eightcam(tmp_path) == (None, "SAFE_BUNDLE_INCOMPLETE")


def test_noncanonical_autodiscovered_root_is_unknown_but_explicit_source_stays_strict(tmp_path):
    bad_root = tmp_path / ".." / tmp_path.name
    assert prepare_eightcam(bad_root, required=False) == (
        None,
        "EIGHTCAM_CANONICAL_ROOT_REQUIRED",
    )
    with pytest.raises(ValueError, match="EIGHTCAM_CANONICAL_ROOT_REQUIRED"):
        prepare_eightcam(bad_root)


def test_corrupt_auto_bundle_leaves_four_recorded_runs_available(tmp_path):
    if "AMIDST_DEMO_HOME" not in os.environ:
        pytest.skip("AMIDST_DEMO_HOME needed for the four recorded workbench runs")
    config, owned = dependency.configuration()
    bundle = tmp_path / "bundle"
    descriptor = bundle / RUN_DESCRIPTOR
    descriptor.parent.mkdir(parents=True)
    descriptor.write_text("{}")
    broken = EightCamSource(bundle, {RUN_DESCRIPTOR: "0" * 64})
    kwargs = {
        "job_path": dependency.owned_path(owned, config["cross_camera_job"]),
        "job_pin": config["cross_camera_job_sha256"],
        "owned_root": owned,
        "eightcam": broken,
    }
    artifacts = dependency.owned_path(owned, config["artifacts_root"])
    p1_bundle = dependency.owned_path(owned, config["p1_bundle"])
    demo = Demo(
        artifacts, p1_bundle, tmp_path / "optional-state", **kwargs, eightcam_required=False
    )
    bootstrap = demo.bootstrap()
    assert bootstrap["eightcam"] == {
        "run_id": RUN_ID,
        "status": "UNKNOWN",
        "reason": "BYTE_PIN_MISMATCH",
    }
    assert len(bootstrap["runs"]) == 4
    assert all(run["run_id"] != RUN_ID for run in bootstrap["runs"])
    assert all(run_id != RUN_ID for _, run_id in demo.rgb.frames)
    with pytest.raises(ValueError, match="BYTE_PIN_MISMATCH"):
        Demo(artifacts, p1_bundle, tmp_path / "required-state", **kwargs)


def test_real_eightcam_binds_every_frame_to_the_detector_index():
    root = os.environ.get("AMIDST_ROOT_8CAM")
    if not root:
        pytest.skip("AMIDST_ROOT_8CAM needed for the #529 LOCAL bundle")
    bundle, reason = prepare_eightcam(root)
    assert reason is None
    assert len(bundle.read_files) == 3692
    index, clock, settings, catalog, graph, frames = bundle.load()
    interval, by_camera, clock_id = frames
    assert index.manifest["run_id"] == RUN_ID
    assert clock.duration_us == 50_000_000 and interval == 200_000
    assert clock_id == settings["clock_id"]
    assert len(by_camera) == len(catalog["cameras"]) == 8
    assert all(len(samples) == 250 for samples in by_camera.values())
    assert "CAM_ENTRY" in by_camera
    assert "CAM_ENTRY" not in {camera["camera_id"] for camera in graph["cameras"]}
    secondary = bundle.sources[1]
    index, clock, settings, catalog, graph, frames = secondary.load()
    assert index.manifest["run_id"] == secondary.run_id
    assert secondary.title.startswith("B4-1-8CAM")
    assert clock.duration_us == 42_000_000
    assert all(len(samples) == 210 for samples in frames[1].values())
    assert len(index.records) == 1680
    broken = EightCamSource(bundle.root, dict(bundle.pins), "B4-1")
    broken.pins["indexes/B4-1/detection_index.json"] = "0" * 64
    with pytest.raises(ValueError, match="BYTE_PIN_MISMATCH"):
        broken.load()


def test_guard_limits_eightcam_to_explicit_read_only_files(monkeypatch, tmp_path):
    demo, external = tmp_path / "owned", tmp_path / "safe"
    allowed, unrelated = external / "000000.png", external / "other.json"
    hooks = []
    monkeypatch.setattr(dependency, "REPO", tmp_path / "repo")
    monkeypatch.setattr(sys, "prefix", str(dependency.REPO / ".venv"))
    monkeypatch.setattr(sys, "base_prefix", str(demo / "runtime" / "python"))
    monkeypatch.setattr(sys, "addaudithook", hooks.append)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    reads_active = True
    dependency.install_owned_io_guard(
        demo,
        approved_read_files=(allowed,),
        approved_reads_active=lambda: reads_active,
    )
    (audit,) = hooks

    audit("open", (allowed, "r", os.O_RDONLY))
    with pytest.raises(ValueError, match="EXTERNAL_PINNED_INPUT_READ_ONLY"):
        audit("open", (allowed, "w", os.O_WRONLY))
    with pytest.raises(ValueError, match="EXTERNAL_LOCAL_INPUT_DENIED"):
        audit("open", (unrelated, "r", os.O_RDONLY))
    reads_active = False
    with pytest.raises(ValueError, match="EXTERNAL_LOCAL_INPUT_DENIED"):
        audit("open", (allowed, "r", os.O_RDONLY))
    audit("open", (demo / "existing-run.png", "r", os.O_RDONLY))


def test_both_eightcam_runs_are_registered_with_estimates_and_missing_sources_unknown(tmp_path):
    if not os.environ.get("AMIDST_DEMO_HOME") or not os.environ.get("AMIDST_ROOT_8CAM"):
        pytest.skip("owned demo and pinned 8CAM bundle required")
    config, owned = dependency.configuration()
    bundle, reason = prepare_eightcam(os.environ["AMIDST_ROOT_8CAM"])
    demo = Demo(
        dependency.owned_path(owned, config["artifacts_root"]),
        dependency.owned_path(owned, config["p1_bundle"]),
        tmp_path / "state",
        job_path=dependency.owned_path(owned, config["cross_camera_job"]),
        job_pin=config["cross_camera_job_sha256"],
        owned_root=owned,
        eightcam=bundle,
        eightcam_reason=reason,
    )
    bootstrap = demo.bootstrap()
    assert len(bootstrap["runs"]) == 6
    assert len([r for r in bootstrap["eightcam_runs"] if r["status"] == "READY"]) == 2
    missing = [r for r in bootstrap["eightcam_runs"] if r["status"] == "UNKNOWN"]
    assert {r["label"] for r in missing} == {"B-05-8CAM", "r005-8CAM"}
    assert all(r["run_id"] is None for r in missing)
    token = demo.call("session", {"role": "demo"})["session_ref"]
    for source in bundle.sources:
        run = next(r for r in demo.api.runs.values() if r.catalog["run_id"] == source.run_id)
        result = demo.call(
            "q_core_track",
            {
                "schema_version": "q-core.track-request.v1",
                "session_ref": token,
                "scene_id": run.catalog["scene_id"],
                "run_id": source.run_id,
                "feature": {"class_label": "person", "color_label": None},
                "region_ids": [],
                "time": None,
                "playback_now_us": 9_400_000,
            },
        )
        assert "display_estimate" in result
        if result["display_estimate"]["est_xy"] != "UNKNOWN":
            assert (
                result["display_estimate"]["calibration_sha256"]
                == bundle.pins["provenance/camera_catalog.json"]
            )
            assert result["display_estimate"]["last_observed_us"] <= 9_400_000
        from amidst.q1q5.store import canonical_hash

        assert result["output_sha256"] == canonical_hash(result, exclude=("output_sha256", "stats"))


@pytest.mark.parametrize("source_number", [0, 1])
def test_pinned_eightcam_core_adapter_produces_selected_projection_without_service(source_number):
    from types import SimpleNamespace

    from amidst.q1q5.scene_graphs import load_scene_graphs
    from amidst.q1q5.store import canonical_hash

    root = os.environ.get("AMIDST_ROOT_8CAM")
    if not root:
        pytest.skip("pinned 8CAM bundle required")
    bundle, _ = prepare_eightcam(root)
    source = bundle.sources[source_number]
    run, _, positions, calibration = Demo.load_eightcam(source, load_scene_graphs("r004"))
    key = (run.catalog["scene_id"], source.run_id)
    demo = Demo.__new__(Demo)
    demo.api = SimpleNamespace(runs={key: run})
    demo.core_track_keys = {key}
    demo.calibrations = {key: calibration}
    demo.cross, demo.positions = {}, {key: positions}
    demo.authorize = lambda *args: None
    payload = {
        "schema_version": "q-core.track-request.v1",
        "session_ref": "test",
        "scene_id": key[0],
        "run_id": key[1],
        "feature": {"class_label": "person", "color_label": None},
        "region_ids": [],
        "time": None,
        "playback_now_us": 9_400_000,
    }
    base = demo.call("q_core_track", payload)
    sight = base["sightings"][0]
    result = demo.call(
        "q_core_track",
        dict(payload, manual_seed={"track_ref": sight["track_ref"], "at_us": sight["range_us"][0]}),
    )
    assert result["manual_seed"]["applied"]
    assert result["single_view"]
    assert len(result["display_estimate"]["est_xy"]) == 2, result["display_estimate"]
    assert result["display_estimate"]["calibration_sha256"] == calibration[1]
    assert result["display_estimate"]["last_observed_us"] <= 9_400_000
    assert result["output_sha256"] == canonical_hash(result, exclude=("output_sha256", "stats"))
    output = os.environ.get("AMIDST_TEST_EVIDENCE")
    if output:
        import json

        (Path(output) / f"eightcam-estimate-{source_number}.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
