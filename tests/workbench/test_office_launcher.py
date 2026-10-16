"""Lifecycle guards: PID reuse, unknown owners, stale source and failed startup."""
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('office_launcher', ROOT / 'scripts/start_office_demo.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_pid_reuse_and_unknown_cwd_never_authorize_signals(monkeypatch, tmp_path):
    record = {'pid': 321, 'process_identity': 'original', 'nonce': 'one'}
    monkeypatch.setattr(launcher, 'process_identity', lambda pid: 'reused')
    monkeypatch.setattr(launcher.os, 'kill', lambda *args: pytest.fail('must not signal reused PID'))
    path = tmp_path / 'runtime.json'
    path.write_text(json.dumps(record))
    launcher.stop_managed(record, path)
    assert path.exists()
    assert not launcher.owned({'pid': True})
    identity = f'start-time {launcher.__file__} --_serve'
    record['process_identity'] = identity
    monkeypatch.setattr(launcher, 'process_identity', lambda pid: identity)
    monkeypatch.setattr(launcher, 'command', lambda *args: 'n/unrelated/checkout')
    assert not launcher.owned(record)


def test_explicit_stop_is_bounded_and_never_escalates(monkeypatch, tmp_path):
    record = {'pid': 321, 'nonce': 'one'}
    path = tmp_path / 'runtime.json'
    path.write_text(json.dumps(record))
    signals = []
    monkeypatch.setattr(launcher, 'owned', lambda record: True)
    monkeypatch.setattr(launcher.os, 'kill', lambda *args: signals.append(args))
    monkeypatch.setattr(launcher.time, 'sleep', lambda delay: None)
    with pytest.raises(RuntimeError, match='5 秒'):
        launcher.stop_managed(record, path)
    assert signals == [(321, launcher.signal.SIGTERM)]
    assert path.exists()


def test_stop_retains_a_newer_runtime_record(monkeypatch, tmp_path):
    record = {'pid': 321, 'nonce': 'old'}
    path = tmp_path / 'runtime.json'
    path.write_text(json.dumps({'pid': 654, 'nonce': 'new'}))
    states = iter([True, False])
    monkeypatch.setattr(launcher, 'owned', lambda record: next(states))
    monkeypatch.setattr(launcher.os, 'kill', lambda *args: None)
    launcher.stop_managed(record, path)
    assert json.loads(path.read_text())['pid'] == 654


def test_source_mismatch_fails_before_any_http_or_signals(monkeypatch):
    config = dict.fromkeys(['repo', 'commit', 'fingerprint', 'app_sha256', 'style_sha256',
                           'scene_sha256', 'cross_camera_sha256'], 'expected')
    record = config | {'pid': 321, 'url': 'http://127.0.0.1:12345/', 'fingerprint': 'stale'}
    monkeypatch.setattr(launcher, 'owned', lambda record: True)
    monkeypatch.setattr(launcher, 'listener', lambda pid: record['url'])
    monkeypatch.setattr(launcher, 'fetch', lambda *args: pytest.fail('no HTTP for stale source'))
    with pytest.raises(RuntimeError, match='來源已改變'):
        launcher.readiness(record, config)


def test_listener_must_be_unique_loopback(monkeypatch):
    monkeypatch.setattr(launcher, 'command', lambda *args: 'p321\nn127.0.0.1:43210')
    assert launcher.listener(321) == 'http://127.0.0.1:43210/'
    for value in ['n*:43210', 'n127.0.0.1:43210\nn127.0.0.1:43211']:
        monkeypatch.setattr(launcher, 'command', lambda *args: value)
        with pytest.raises(RuntimeError, match='listener'):
            launcher.listener(321)


def test_failed_preflight_preserves_existing_service(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, 'RUNTIME', tmp_path / 'runtime')
    monkeypatch.setattr(launcher.sys, 'argv', ['launcher', 'restart', '--no-open'])
    monkeypatch.setattr(launcher, 'inventory', lambda record: None)
    monkeypatch.setattr(launcher, 'preflight', lambda: (_ for _ in ()).throw(RuntimeError('broken')))
    monkeypatch.setattr(launcher, 'stop_managed', lambda *args: pytest.fail('must preserve service'))
    with pytest.raises(RuntimeError, match='broken'):
        launcher.main()


def test_child_initialization_failure_never_reports_ready(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(launcher, 'RUNTIME', tmp_path / 'runtime')
    monkeypatch.setattr(launcher.sys, 'argv', ['launcher', 'start', '--no-open'])
    monkeypatch.setattr(launcher, 'inventory', lambda record: None)
    monkeypatch.setattr(launcher, 'preflight', lambda: {})
    monkeypatch.setattr(launcher, 'command', lambda *args: '')
    class Child:
        pid = 321
        def poll(self):
            return 1
    monkeypatch.setattr(subprocess, 'Popen', lambda *args, **kwargs: Child())
    with pytest.raises(RuntimeError, match='initialize failed'):
        launcher.main()
    assert 'WORKBENCH_READY=YES' not in capsys.readouterr().out
    assert not (launcher.RUNTIME / 'runtime.json').exists()
