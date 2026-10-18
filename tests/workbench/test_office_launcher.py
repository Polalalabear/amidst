"""Lifecycle guards: PID reuse, unknown owners, stale source and failed startup."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "office_launcher", ROOT / "scripts/start_office_demo.py"
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_pid_reuse_and_unknown_cwd_never_authorize_signals(monkeypatch, tmp_path):
    record = {"pid": 321, "process_identity": "original", "nonce": "one"}
    monkeypatch.setattr(launcher, "process_identity", lambda pid: "reused")
    monkeypatch.setattr(
        launcher.os, "kill", lambda *args: pytest.fail("must not signal reused PID")
    )
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(record))
    launcher.stop_managed(record, path)
    assert path.exists()
    assert not launcher.owned({"pid": True})
    identity = f"start-time {launcher.__file__} --_serve"
    record["process_identity"] = identity
    monkeypatch.setattr(launcher, "process_identity", lambda pid: identity)
    monkeypatch.setattr(launcher, "command", lambda *args: "n/unrelated/checkout")
    assert not launcher.owned(record)


def test_explicit_stop_is_bounded_and_never_escalates(monkeypatch, tmp_path):
    record = {"pid": 321, "nonce": "one"}
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(record))
    signals = []
    monkeypatch.setattr(launcher, "owned", lambda record: True)
    monkeypatch.setattr(launcher.os, "kill", lambda *args: signals.append(args))
    monkeypatch.setattr(launcher.time, "sleep", lambda delay: None)
    with pytest.raises(RuntimeError, match="5 秒"):
        launcher.stop_managed(record, path)
    assert signals == [(321, launcher.signal.SIGTERM)]
    assert path.exists()


def test_stop_retains_a_newer_runtime_record(monkeypatch, tmp_path):
    record = {"pid": 321, "nonce": "old"}
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps({"pid": 654, "nonce": "new"}))
    states = iter([True, False])
    monkeypatch.setattr(launcher, "owned", lambda record: next(states))
    monkeypatch.setattr(launcher.os, "kill", lambda *args: None)
    launcher.stop_managed(record, path)
    assert json.loads(path.read_text())["pid"] == 654


def test_source_mismatch_fails_before_any_http_or_signals(monkeypatch):
    config = dict.fromkeys(
        [
            "repo",
            "commit",
            "fingerprint",
            "app_sha256",
            "style_sha256",
            "scene_sha256",
            "cross_camera_sha256",
        ],
        "expected",
    )
    record = config | {"pid": 321, "url": "http://127.0.0.1:12345/", "fingerprint": "stale"}
    monkeypatch.setattr(launcher, "owned", lambda record: True)
    monkeypatch.setattr(launcher, "listener", lambda pid: record["url"])
    monkeypatch.setattr(launcher, "fetch", lambda *args: pytest.fail("no HTTP for stale source"))
    with pytest.raises(RuntimeError, match="來源已改變"):
        launcher.readiness(record, config)


def test_listener_must_be_unique_loopback(monkeypatch):
    monkeypatch.setattr(launcher, "command", lambda *args: "p321\nn127.0.0.1:43210")
    assert launcher.listener(321) == "http://127.0.0.1:43210/"
    for value in ["n*:43210", "n127.0.0.1:43210\nn127.0.0.1:43211"]:
        monkeypatch.setattr(launcher, "command", lambda *args, value=value: value)
        with pytest.raises(RuntimeError, match="listener"):
            launcher.listener(321)


def test_failed_preflight_preserves_existing_service(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "RUNTIME", tmp_path / "runtime")
    monkeypatch.setattr(launcher.sys, "argv", ["launcher", "restart", "--no-open"])
    monkeypatch.setattr(launcher, "inventory", lambda record: None)
    monkeypatch.setattr(
        launcher, "preflight", lambda: (_ for _ in ()).throw(RuntimeError("broken"))
    )
    monkeypatch.setattr(
        launcher, "stop_managed", lambda *args: pytest.fail("must preserve service")
    )
    with pytest.raises(RuntimeError, match="broken"):
        launcher.main()


def test_child_initialization_failure_never_reports_ready(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(launcher, "RUNTIME", tmp_path / "runtime")
    monkeypatch.setattr(launcher.sys, "argv", ["launcher", "start", "--no-open"])
    monkeypatch.setattr(launcher, "inventory", lambda record: None)
    monkeypatch.setattr(launcher, "preflight", lambda: {})
    monkeypatch.setattr(launcher, "command", lambda *args: "")

    class Child:
        pid = 321

        def poll(self):
            return 1

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: Child())
    with pytest.raises(RuntimeError, match="initialize failed"):
        launcher.main()
    assert "WORKBENCH_READY=YES" not in capsys.readouterr().out
    assert not (launcher.RUNTIME / "runtime.json").exists()


def test_occupied_loopback_port_is_preserved(monkeypatch, tmp_path):
    import socket
    from types import SimpleNamespace

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import office_demo_backend

    monkeypatch.setattr(launcher, "RUNTIME", tmp_path)
    monkeypatch.setattr(launcher, "preflight", lambda: {})
    monkeypatch.setattr(office_demo_backend, "load_presets", lambda *args: {})
    monkeypatch.setattr(
        office_demo_backend, "application", lambda *args: SimpleNamespace(workbench=None)
    )
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        monkeypatch.setenv("OFFICE_PORT", str(occupied.getsockname()[1]))
        with pytest.raises(OSError, match="Address already in use"):
            launcher.serve()
        assert occupied.fileno() >= 0
        assert not (tmp_path / "runtime.json").exists()
        assert list(tmp_path.iterdir()) == []  # Failed child's temporary state is removed.


@pytest.mark.parametrize("availability", ["ready", "unavailable", "quality_failed"])
def test_readiness_matches_complete_preset_catalog(monkeypatch, capsys, availability):
    import hashlib

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import office_demo_backend as backend

    ids = ["blender-office", "blender-contact-control"]
    body = b"cameraTilesHTML sourcePlaybackStep"
    sha = hashlib.sha256(body).hexdigest()
    config = dict.fromkeys(["repo", "commit", "fingerprint"], "expected") | {
        "app_sha256": sha,
        "style_sha256": sha,
        "scene_sha256": sha,
        "cross_camera_sha256": sha,
        "scene_ids": ids,
        "default_scene_id": ids[0],
    }
    record = config | {"pid": 321, "url": "http://127.0.0.1:12345/"}
    bootstrap = {"scenes": [{"scene_id": sid} for sid in ids]}
    if availability == "unavailable":
        bootstrap["scenes"][1].update(
            status="UNAVAILABLE", available=False, reason="PRESET_DATA_MISSING"
        )
    monkeypatch.setattr(launcher, "owned", lambda _: True)
    monkeypatch.setattr(launcher, "listener", lambda _: record["url"])
    monkeypatch.setattr(launcher, "VENDOR_FILES", {})
    monkeypatch.setattr(
        launcher, "fetch", lambda url: b"\x89PNG\r\n\x1a\n" if "api/media?" in url else body
    )
    monkeypatch.setattr(
        backend,
        "preset_specs",
        lambda *args: (
            ids[0],
            [{"scene_id": sid, "config": {"camera_ids": ["CAM_A", "CAM_B"]}} for sid in ids],
        ),
    )

    def json_response(url, payload=None):
        if url.endswith("__office_launcher"):
            return record
        if url.endswith("api/bootstrap"):
            return bootstrap
        if url.endswith("api/session"):
            return {"session_ref": "token"}
        if url.endswith("api/scene"):
            return {
                "snapshot": {
                    "source_binding": {},
                    **(
                        {
                            "contact_quality_status": {
                                "status": "NOT_EVALUATED",
                                "reason": "QUALITY_COMPONENT_MISMATCH",
                            }
                        }
                        if availability == "quality_failed"
                        else {}
                    ),
                }
            }
        assert url.endswith("api/timeline")
        return {
            "frames": [{"timestamp": payload["timestamp"], "frame_ref": "frame"} for _ in range(2)]
        }

    monkeypatch.setattr(launcher, "json_fetch", json_response)
    assert launcher.readiness(record, config) == record["url"]
    output = capsys.readouterr().out
    assert ("PRESET_READINESS=DEGRADED" in output) == (availability != "ready")
    bootstrap["scenes"].pop()
    with pytest.raises(RuntimeError, match="catalog"):
        launcher.readiness(record, config)


@pytest.mark.parametrize("missing_optional", [False, True, "unreadable"])
def test_fingerprint_binds_presets_and_every_fixture(monkeypatch, tmp_path, missing_optional):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import office_demo_backend as backend

    repo = tmp_path / "repo"
    names = [
        "scripts/office_demo_backend.py",
        "scripts/materialize_office_display.py",
        "configs/office_demo_presets_v1.json",
        "configs/office_contact_v2.json",
        "configs/hybrid_contact_v1_1.json",
        "configs/office_demo_display_v1.json",
        "data/engineering/office_display_v1.json.gz",
        *(
            "frontend/workbench/" + n
            for n in ("app.mjs", "scene.mjs", "cross-camera.mjs", "style.css")
        ),
    ]
    for name in names:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    asset = repo / "assets"
    asset.mkdir()
    frame = asset / "frame.png"
    frame.write_bytes(b"rgb")
    source, dataset = repo / "source", asset / "dataset.json"
    source.write_text("immutable")
    dataset.write_text("fixture")
    bundle = repo / "bundle"
    bundle.mkdir()
    safe = bundle / "safe_inputs.json"
    safe.write_text(
        json.dumps(
            {
                "frames": [
                    {"camera_id": cam, "local_path": str(frame), "byte_count": 3}
                    for cam in ("CAM_A", "CAM_B")
                    for _ in range(50)
                ]
            }
        )
    )
    (bundle / "manifest.json").write_text(
        json.dumps(
            {"source_path": str(source), "dataset_path": str(dataset), "asset_root": str(asset)}
        )
    )
    fixture_paths = [repo / "fixture-a.json", repo / "fixture-b.json"]
    for path in fixture_paths:
        path.write_text("{}")
    specs = [
        {
            "scene_id": str(i),
            "bundle_path": bundle,
            "fixture_path": path,
            "config": {
                "safe_inputs_sha256": launcher.digest(safe),
                "camera_ids": ["CAM_A", "CAM_B"],
            },
        }
        for i, path in enumerate(fixture_paths)
    ]
    if missing_optional is True:
        specs[1]["bundle_path"] = repo / "absent-optional"
    monkeypatch.setattr(backend, "preset_specs", lambda *args: ("0", specs))
    monkeypatch.setattr(launcher, "REPO", repo)
    monkeypatch.setattr(launcher, "UI_REPO", repo)
    monkeypatch.setattr(launcher, "PRESETS", repo / "configs/office_demo_presets_v1.json")
    monkeypatch.setattr(launcher, "VENDOR_FILES", {})

    def command(*args):
        if "--show-toplevel" in args:
            return str(repo)
        if "status" in args or "ls-files" in args:
            return ""
        return "test-ref"

    monkeypatch.setattr(launcher, "command", command)
    if missing_optional == "unreadable":
        original_digest = launcher.digest

        def deny_optional(path):
            if path == fixture_paths[1]:
                raise PermissionError("test optional fixture is unreadable")
            return original_digest(path)

        monkeypatch.setattr(launcher, "digest", deny_optional)
        assert launcher.preflight()["fingerprint"]
        return
    previous = launcher.preflight()["fingerprint"]
    for path in [launcher.PRESETS, *fixture_paths]:
        path.write_text(path.read_text() + " ")
        current = launcher.preflight()["fingerprint"]
        assert current != previous
        previous = current
