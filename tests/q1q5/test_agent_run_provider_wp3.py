"""WP3 gate: CLI dry-run, stage-cap refusal and cross-platform path resolution (#511).

Tests scripts/agent_decision/run_provider.py with fake transports and tmp_path;
zero network calls, zero real API keys.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from amidst.q1q5 import agent_decision as ad
from amidst.q1q5.agent_decision import RuleDecider
from amidst.q1q5.agent_providers import FakeClock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / 'scripts/agent_decision/run_provider.py'
FORMAL = json.loads((ROOT / 'configs/q1q5/agent_decision_params_v1.json').read_text(encoding='utf-8'))
STAGE = 'PILOT_AND_CONSISTENCY'


def _load_cli_module():
    spec = importlib.util.spec_from_file_location('run_provider_wp3', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dp1_request(index: int = 0) -> dict:
    req = {
        'schema_version': ad.REQUEST_SCHEMA_VERSION,
        'decision_point': ad.DP1,
        'as_of_us': 2_000_000 + index * 100_000,
        'topology': {'graph_status': 'GRAPH_NOT_APPROVED', 'edges': [['CAM_A', 'CAM_B']]},
        'current': {
            'id': 'A1',
            'camera_id': 'CAM_A',
            'first_seen_us': 0,
            'last_seen_us': 1_000_000,
            'colors': ['red'],
            'scores': {'n': 5, 'min': 0.5, 'median': 0.7, 'max': 0.9},
            'continuation_fraction': 0.1,
        },
        'candidates': [{
            'id': 'B1',
            'camera_id': 'CAM_B',
            'first_seen_us': 1_600_000,
            'last_seen_us': 1_800_000,
            'colors': ['red'],
            'scores': {'n': 5, 'min': 0.5, 'median': 0.7, 'max': 0.9},
            'continuation_fraction': 0.1,
            'gap_us': 400_000,
            'graph_edge': True,
            'link_kind': 'CROSS_CAMERA_HANDOFF',
            'rule_eligible': True,
        }],
        'rule_answer': 'B1',
        'identity_verdict': 'UNCONFIRMED',
    }
    req['rule_answer'] = RuleDecider().answer(req)
    return req


class _EnvKeyTrap(dict):
    def _trip(self, *_a, **_k):
        raise AssertionError('OPENAI_API_KEY must not be read in dry-run or refused live mode')

    def __getitem__(self, key):
        if key == 'OPENAI_API_KEY':
            self._trip()
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key == 'OPENAI_API_KEY':
            self._trip()
        return super().get(key, default)

    def __contains__(self, key):
        if key == 'OPENAI_API_KEY':
            self._trip()
        return super().__contains__(key)


def _block_network(monkeypatch):
    def _deny(*_a, **_k):
        raise AssertionError('network access is forbidden')

    for attr in ('connect', 'connect_ex', 'create_connection', 'getaddrinfo'):
        if hasattr(socket, attr):
            monkeypatch.setattr(socket, attr, _deny)
        if hasattr(socket.socket, attr):
            monkeypatch.setattr(socket.socket, attr, _deny)


# ------------------------------------------------------------------ 1. Default dry-run matches dry_run_estimate()

def test_default_without_flags_runs_dry_run_and_matches_dry_run_estimate(tmp_path, monkeypatch, capsys):
    cli = _load_cli_module()
    _block_network(monkeypatch)
    monkeypatch.setattr(os, 'environ', _EnvKeyTrap({**os.environ, 'OPENAI_API_KEY': 'sk-test-FAKE'}))

    transport_calls = 0

    def forbidden_transport(**_kw):
        nonlocal transport_calls
        transport_calls += 1
        raise AssertionError('transport must not be called in dry-run')

    # 1) No flags at all -> defaults to 16 questions, k=1, 3 models -> 16x1x3 = 48 calls
    out_pilot = tmp_path / 'pilot_dry_run.json'
    rc1 = cli.main(['--out', str(out_pilot)], transport=forbidden_transport)
    assert rc1 == 0 and transport_calls == 0
    stdout1 = json.loads(capsys.readouterr().out.strip())
    expected_pilot = ad.dry_run_estimate(FORMAL, questions=16, k=1, stage=STAGE)
    assert stdout1['mode'] == 'DRY_RUN' and stdout1['provider_calls'] == 0
    assert stdout1['calls'] == 16 * 1 * 3 == 48
    assert stdout1['tokens'] == 48 * 1800 == 86_400
    assert stdout1['estimate'] == expected_pilot
    assert json.loads(out_pilot.read_text(encoding='utf-8')) == stdout1

    # 2) Consistency k=5 -> 16x5x3 = 240 calls
    rc2 = cli.main(['--questions', '16', '--k', '5', '--stage', STAGE], transport=forbidden_transport)
    assert rc2 == 0 and transport_calls == 0
    stdout2 = json.loads(capsys.readouterr().out.strip())
    expected_cons = ad.dry_run_estimate(FORMAL, questions=16, k=5, stage=STAGE)
    assert stdout2['calls'] == 16 * 5 * 3 == 240
    assert stdout2['tokens'] == 240 * 1800 == 432_000
    assert stdout2['estimate'] == expected_cons
    assert stdout2['fits_stage'] is True


# ------------------------------------------------------------------ 2. Live flag refused when exceeding stage caps or unapproved

def test_live_flag_is_refused_when_estimate_exceeds_stage_cap_or_stage_unapproved(tmp_path, monkeypatch, capsys):
    cli = _load_cli_module()
    _block_network(monkeypatch)
    monkeypatch.setattr(os, 'environ', _EnvKeyTrap({**os.environ, 'OPENAI_API_KEY': 'sk-test-FAKE'}))

    transport_calls = 0

    def forbidden_transport(**_kw):
        nonlocal transport_calls
        transport_calls += 1
        raise AssertionError('transport must not be called when live is refused')

    # Exceeds PILOT_AND_CONSISTENCY max_calls (17 x 6 x 3 = 306 > 288)
    rc_over = cli.main(
        ['--questions', '17', '--k', '6', '--stage', STAGE, '--live', '--out', str(tmp_path / 'over.json')],
        transport=forbidden_transport,
    )
    assert rc_over != 0 and transport_calls == 0
    out_over = json.loads(capsys.readouterr().out.strip())
    assert out_over['status'] == 'REFUSED'
    assert out_over['reason'] == 'CALL_BUDGET_EXHAUSTED'
    assert out_over['fits_stage'] is False
    assert out_over['provider_calls'] == 0

    # Unapproved stage FORMAL (approved=false)
    rc_unapproved = cli.main(
        ['--questions', '4', '--k', '1', '--stage', 'FORMAL', '--live'],
        transport=forbidden_transport,
    )
    assert rc_unapproved != 0 and transport_calls == 0
    out_unapproved = json.loads(capsys.readouterr().out.strip())
    assert out_unapproved['status'] == 'REFUSED'
    assert out_unapproved['reason'] == 'MODE_NOT_AUTHORIZED'
    assert out_unapproved['stage_approved'] is False


# ------------------------------------------------------------------ 3. Repo-relative paths & AMIDST_ROOT portability (Windows & Linux)

def test_paths_resolve_via_amidst_root_across_windows_and_posix(tmp_path, monkeypatch, capsys):
    cli = _load_cli_module()
    _block_network(monkeypatch)

    # Set up a portable mirror root in tmp_path and point AMIDST_ROOT to it (#509 convention)
    fake_root = tmp_path / 'amidst_portable_root'
    cfg_dir = fake_root / 'configs' / 'q1q5'
    cfg_dir.mkdir(parents=True)
    (cfg_dir / 'agent_decision_params_v1.json').write_text(json.dumps(FORMAL), encoding='utf-8')

    req_dir = fake_root / 'local' / 'data'
    req_dir.mkdir(parents=True)
    reqs = [_dp1_request(i) for i in range(4)]
    (req_dir / 'requests_v1.jsonl').write_text(
        ''.join(ad.canonical(r).decode('ascii') + '\n' for r in reqs),
        encoding='utf-8',
    )

    monkeypatch.setenv('AMIDST_ROOT', str(fake_root))

    # Both POSIX-style and Windows-style relative paths must resolve cleanly under AMIDST_ROOT
    for rel_params, rel_reqs in (
        ('configs/q1q5/agent_decision_params_v1.json', 'local/data/requests_v1.jsonl'),
        (r'configs\q1q5\agent_decision_params_v1.json', r'local\data\requests_v1.jsonl'),
    ):
        rc = cli.main(['--params', rel_params, '--requests', rel_reqs, '--k', '2', '--stage', STAGE])
        assert rc == 0
        out = json.loads(capsys.readouterr().out.strip())
        assert out['mode'] == 'DRY_RUN'
        assert out['questions'] == 4 and out['k'] == 2 and out['calls'] == 4 * 2 * 3 == 24

    # Live + Replay end-to-end via CLI with fake transport and relative recording path under AMIDST_ROOT
    clock = FakeClock()

    def fake_live_transport(*, url, headers, body, timeout_s):
        clock.advance_ms(80.0)
        resp = {'action': 'SELECT', 'candidate_id': 'B1', 'reason_codes': ['GRAPH_EDGE'], 'rationale': 'ok'}
        return 200, json.dumps({
            'id': 'chatcmpl-cli',
            'model': 'astra6-2026-11',
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': json.dumps(resp)}}],
            'usage': {'prompt_tokens': 1000, 'completion_tokens': 30},
        }).encode('utf-8')

    rc_live = cli.main(
        [
            '--params', 'configs/q1q5/agent_decision_params_v1.json',
            '--requests', 'local/data/requests_v1.jsonl',
            '--stage', STAGE,
            '--model', 'astra6',
            '--recording', 'local/data/recorded_cli.jsonl',
            '--live',
        ],
        transport=fake_live_transport,
        env={'OPENAI_API_KEY': 'sk-test-FAKE-CLI-KEY'},
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
    )
    assert rc_live == 0
    live_out = json.loads(capsys.readouterr().out.strip())
    assert live_out['mode'] == 'AGENT_LIVE' and live_out['decisions'] == 4
    assert (fake_root / 'local/data/recorded_cli.jsonl').is_file()

    # Subprocess invocation of run_provider.py (default dry-run) works with AMIDST_ROOT
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--questions', '16', '--k', '1'],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
        env={**os.environ, 'AMIDST_ROOT': str(fake_root), 'PYTHONPATH': str(ROOT / 'src')},
    )
    sub_out = json.loads(proc.stdout.strip())
    assert sub_out['mode'] == 'DRY_RUN' and sub_out['calls'] == 48
