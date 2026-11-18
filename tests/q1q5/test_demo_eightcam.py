"""The optional workbench run binds only the pinned A4-1 safe observations."""
import os
import sys
from pathlib import Path

import pytest

SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts")
sys.path.insert(0, SCRIPTS)
try:
    import demo_dependency_config as dependency
    from demo_eightcam import RUN_ID, prepare_eightcam
finally:
    sys.path.remove(SCRIPTS)


def test_missing_optional_eightcam_source_preserves_unknown(tmp_path):
    assert prepare_eightcam(None) == (None, "ROOT_NOT_CONFIGURED")
    assert prepare_eightcam(tmp_path / "missing") == (None, "SAFE_BUNDLE_MISSING")
    assert prepare_eightcam(tmp_path) == (None, "SAFE_BUNDLE_INCOMPLETE")


def test_real_eightcam_binds_every_frame_to_the_detector_index():
    root = os.environ.get("AMIDST_ROOT_8CAM")
    if not root:
        pytest.skip("AMIDST_ROOT_8CAM needed for the #529 LOCAL bundle")
    bundle, reason = prepare_eightcam(root)
    assert reason is None
    assert len(bundle.read_files) == 2007
    index, clock, settings, catalog, graph, frames = bundle.load()
    interval, by_camera, clock_id = frames
    assert index.manifest["run_id"] == RUN_ID
    assert clock.duration_us == 50_000_000 and interval == 200_000
    assert clock_id == settings["clock_id"]
    assert len(by_camera) == len(catalog["cameras"]) == 8
    assert all(len(samples) == 250 for samples in by_camera.values())
    assert "CAM_ENTRY" in by_camera
    assert "CAM_ENTRY" not in {camera["camera_id"] for camera in graph["cameras"]}


def test_guard_limits_eightcam_to_explicit_read_only_files(monkeypatch, tmp_path):
    demo, external = tmp_path / "owned", tmp_path / "safe"
    allowed, unrelated = external / "000000.png", external / "other.json"
    hooks = []
    monkeypatch.setattr(dependency, "REPO", tmp_path / "repo")
    monkeypatch.setattr(sys, "prefix", str(dependency.REPO / ".venv"))
    monkeypatch.setattr(sys, "base_prefix", str(demo / "runtime" / "python"))
    monkeypatch.setattr(sys, "addaudithook", hooks.append)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    dependency.install_owned_io_guard(demo, approved_read_files=(allowed,))
    (audit,) = hooks

    audit("open", (allowed, "r", os.O_RDONLY))
    with pytest.raises(ValueError, match="EXTERNAL_PINNED_INPUT_READ_ONLY"):
        audit("open", (allowed, "w", os.O_WRONLY))
    with pytest.raises(ValueError, match="EXTERNAL_LOCAL_INPUT_DENIED"):
        audit("open", (unrelated, "r", os.O_RDONLY))
