import importlib.util
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("start_live", REPO / "scripts/start_live_mode.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def args(tmp_path, port=8797):
    return SimpleNamespace(
        port=port,
        cameras=tmp_path / "missing-cameras.json",
        assets=tmp_path / "assets",
        models=tmp_path / "models",
        device="cpu",
    )


def test_missing_catalog_fails_before_model_or_network(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher.socket, "socket", lambda *a: pytest.fail("socket before catalog"))
    with pytest.raises(ValueError, match="CAMERA_CATALOG_MISSING.*--cameras"):
        launcher.command(args(tmp_path))


@pytest.mark.parametrize("port", [8785, 0, 65536])
def test_pinned_or_invalid_port_is_rejected_before_assets(tmp_path, port):
    with pytest.raises(ValueError, match="LIVE_PORT_INVALID"):
        launcher.command(args(tmp_path, port))


def test_valid_entry_always_disables_advisor_and_rejects_occupied_port(tmp_path, monkeypatch):
    a = args(tmp_path, 0)
    import json

    a.cameras.write_text(
        json.dumps(
            {"schema_version": "controlled-scene.cameras.v1", "cameras": [{"camera_id": "fixture"}]}
        )
    )
    for f in ["character.glb", "scene.glb", "cameras.three.json"]:
        (a.assets).mkdir(exist_ok=True)
        (a.assets / f).write_bytes(b"fixture")
    (a.models / "source/rtdetr_pytorch/src").mkdir(parents=True)
    (a.models / "rtdetr_r18vd_dec3_6x_coco_from_paddle.pth").write_bytes(b"fixture")
    monkeypatch.setattr(launcher.importlib.util, "find_spec", lambda name: object())
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        a.port = reserved.getsockname()[1]
        with pytest.raises(ValueError, match="LIVE_PORT_IN_USE"):
            launcher.command(a)
    cmd = launcher.command(a)
    assert cmd[-2:] == ["--advisor", "off"]
    assert "--cameras" in cmd and "--assets" in cmd


def test_geometry_document_cannot_be_passed_as_safe_camera_catalog(tmp_path):
    import json

    a = args(tmp_path)
    a.cameras.write_text(json.dumps({"schema_version": "r004.scene-geometry.v1", "cameras": [{}]}))
    with pytest.raises(ValueError, match="CAMERA_CATALOG_INVALID"):
        launcher.command(a)
