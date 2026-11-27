"""E6 arms paid-path tests (#721). Fake transports/openers and stubbed replays only: no network, key, model or paid call."""
import hashlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts' / 'evaluation'))
import e6_arms_run as R  # noqa: E402

BASE = {'actual_total_usd': 38.17, 'cap_usd': 90.0, 'effective_at': '2026-11-24T21:51:00+08:00'}


def args(tmp_path, **kw):
    base = dict(paid=True, max_usd=10.0, k=1, cases=['E3-A1', 'E3-B1', 'E3-C1'], arms=list(R.ARMS), out=tmp_path / 'out',
                baseline_json=tmp_path / 'base.json', extra_ledger=None, root=tmp_path, cameras=tmp_path / 'cam.json')
    base.update(kw)
    (tmp_path / 'base.json').write_text(json.dumps(base_doc(kw.pop('baseline', None))))
    return SimpleNamespace(**base)


def base_doc(over=None):
    return {**BASE, **(over or {})}


# ---- refusals ------------------------------------------------------------------------------------------
def test_without_paid_flag_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(R, 'estimate', lambda a: pytest.fail('must refuse before estimating'))
    with pytest.raises(SystemExit, match='PAID_RUN_NOT_AUTHORIZED'):
        R.main(['--root', str(tmp_path), '--cameras', str(tmp_path / 'c.json'), '--cases', 'E3-A1', '--k', '1'])


@pytest.mark.parametrize('kw,msg', [
    ({'k': 3}, 'PAID_COMBINATION_REFUSED'),
    ({'cases': ['E3-A2']}, 'PAID_COMBINATION_REFUSED'),
    ({'cases': ['E3-A1', 'E3-A1']}, 'PAID_COMBINATION_REFUSED'),
    ({'max_usd': 10.01}, 'PAID_BUDGET_REFUSED'),
    ({'max_usd': 0}, 'PAID_BUDGET_REFUSED'),
    ({'max_usd': float('nan')}, 'PAID_BUDGET_REFUSED'),
    ({'max_usd': None}, 'PAID_BUDGET_REFUSED'),
    ({'paid': False}, 'PAID_RUN_NOT_AUTHORIZED'),
])
def test_bad_paid_requests_are_refused(tmp_path, kw, msg):
    with pytest.raises(SystemExit, match=msg):
        R.check_paid_request(args(tmp_path, **kw))


def test_paid_and_dry_run_are_exclusive(tmp_path):
    with pytest.raises(SystemExit):
        R.main(['--root', str(tmp_path), '--cameras', 'c', '--cases', 'E3-A1', '--paid', '--dry-run'])


# ---- cumulative cap ------------------------------------------------------------------------------------
def test_estimate_over_max_refused(tmp_path):
    (tmp_path / 'b.json').write_text(json.dumps(BASE))
    with pytest.raises(SystemExit, match='ESTIMATE_OVER_MAX_USD'):
        R.cumulative_check(tmp_path / 'b.json', [], 10.5, 10.0)


def test_cumulative_over_cap_refused_and_boundary_allowed(tmp_path):
    (tmp_path / 'b.json').write_text(json.dumps({**BASE, 'actual_total_usd': 82.4}))
    with pytest.raises(SystemExit, match='CUMULATIVE_OVER_CAP'):
        R.cumulative_check(tmp_path / 'b.json', [], 7.66, 10.0)
    got = R.cumulative_check(tmp_path / 'b.json', [], 7.6, 10.0)        # 82.4 + 7.6 == 90 exactly
    assert got['baseline_actual_usd'] == 82.4 and got['cap_usd'] == 90.0


def test_new_ledger_rows_count_old_rows_do_not(tmp_path):
    led = tmp_path / 'led'
    led.mkdir()
    rows = [{'ts': '2026-11-24T10:00:00Z', 'outcome': 'OK', 'est_cost_usd': 5.0},       # before effective_at (13:51Z): ignored
            {'ts': '2026-11-25T10:00:00Z', 'outcome': 'OK', 'est_cost_usd': 40.0},
            {'ts': '2026-11-25T11:00:00Z', 'outcome': 'DENIED', 'est_cost_usd': None}]
    (led / 'usage.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\nnot json\n')
    (tmp_path / 'b.json').write_text(json.dumps(BASE))
    with pytest.raises(SystemExit, match='CUMULATIVE_OVER_CAP'):
        R.cumulative_check(tmp_path / 'b.json', [led], 12.0 - 0.0, 20.0)        # 38.17 + 40 + 12 > 90
    assert R.cumulative_check(tmp_path / 'b.json', [led], 7.66, 10.0)['new_ledger_usd'] == 40.0


# ---- guarded transport and ledger row format -----------------------------------------------------------
class FakeResp:
    def __init__(self, doc):
        self.raw = json.dumps(doc).encode()

    def read(self):
        return self.raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_opener(req, timeout):
    return FakeResp({'id': 'r1', 'status': 'completed',
                     'output': [{'content': [{'type': 'output_text', 'text': '{"answer":"UNCERTAIN"}'}]}],
                     'usage': {'input_tokens': 1000, 'output_tokens': 50, 'input_tokens_details': {'cached_tokens': 0}}})


BODY = {'model': 'x', 'max_output_tokens': 300,
        'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': 'hello ' * 50}]}]}


def test_guarded_transport_writes_ledger_row_and_never_stores_prompt_or_key(tmp_path):
    transport, guard = R.guarded_transport(1.0, tmp_path / 'led', 5.0, env={'OPENAI_API_KEY': 'sk-test-secret'}, opener=fake_opener)
    resp = transport(BODY)
    assert resp['text'] == '{"answer":"UNCERTAIN"}'
    raw = (tmp_path / 'led' / 'usage.jsonl').read_text()
    row = json.loads(raw.splitlines()[0])
    assert set(row) == {'ts', 'caller', 'model', 'outcome', 'reason', 'prompt_tokens', 'completion_tokens', 'cached_tokens', 'est_cost_usd'}
    assert row['caller'] == 'e6arms' and row['model'] == 'gpt-6.1-terra' and row['outcome'] == 'OK'
    assert row['prompt_tokens'] == 1000 and row['completion_tokens'] == 50
    assert row['est_cost_usd'] == pytest.approx((1000 * 1.0 + 50 * 5.0) / 1e6)
    assert 'sk-test-secret' not in raw and 'hello' not in raw


def test_guard_denies_over_budget_and_missing_key(tmp_path):
    transport, _ = R.guarded_transport(0.0001, tmp_path / 'led', 5.0, env={'OPENAI_API_KEY': 'k'}, opener=fake_opener)
    with pytest.raises(PermissionError, match='GUARD_DENIED'):
        transport(BODY)
    transport2, _ = R.guarded_transport(1.0, tmp_path / 'led2', 5.0, env={}, opener=fake_opener)
    with pytest.raises(PermissionError, match='NO_API_KEY'):
        transport2(BODY)


# ---- paid_run with stubs: output files ----------------------------------------------------------------
def stub_env(monkeypatch, doc_extra=None, est=7.66):
    monkeypatch.setattr(R, 'estimate', lambda a: {'est_total_usd_upper_bound': est, 'arms': {}})
    monkeypatch.setattr(R.frozen, 'load_case', lambda root, cid: {'case_id': cid, 'cameras': []})
    monkeypatch.setattr(R.frozen, 'live_scene_context', lambda cams, c: {'cameras': []})

    def fake_replay(arm, case, cams, scene, transport, k=1, **kw):
        doc = {'schema_version': R.SCHEMA, 'case_id': case['case_id'], 'arm': arm, 'k': k,
               'config': {}, 'rows': [{'tick': 0, 'tracking': {'state': 'LOST'}}],
               'calls': [{'answer': 'UNCERTAIN', 'fallback_reason': None, 'request': {'body_sha256': 'ab' * 32}}], 'history': []}
        doc.update(doc_extra or {})
        return doc
    monkeypatch.setattr(R, 'replay', fake_replay)


def test_paid_run_outputs_manifest_and_no_scoring_fields(tmp_path, monkeypatch):
    stub_env(monkeypatch)
    a = args(tmp_path)
    n = R.paid_run(a, transport=lambda body: None)
    out = tmp_path / 'out'
    files = sorted(p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file())
    assert 'PRECHECK.json' in files and 'MANIFEST.sha256' in files and 'E3-A1/DEANCHOR.k1.json' in files
    assert len([f for f in files if f.endswith('.k1.json')]) == 9
    manifest = (out / 'MANIFEST.sha256').read_text().splitlines()
    assert len(manifest) == n == len(files) - 1
    for line in manifest:
        digest, rel = line.split('  ', 1)
        assert hashlib.sha256((out / rel).read_bytes()).hexdigest() == digest

    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    import re
    bad = re.compile(r'(?i)(?:ground_?truth|(?:^|_)gt_|actors|visib|depth|trajector|renderer_track|expected)')
    for f in files:
        if f.endswith('.json'):
            assert not [k for k in keys(json.loads((out / f).read_text())) if bad.search(k)], f
    # existing outputs are skipped, never overwritten
    before = (out / 'E3-A1' / 'DEANCHOR.k1.json').read_bytes()
    R.paid_run(a, transport=lambda body: None)
    assert (out / 'E3-A1' / 'DEANCHOR.k1.json').read_bytes() == before


def test_scoring_side_key_in_output_aborts_before_writing(tmp_path, monkeypatch):
    stub_env(monkeypatch, doc_extra={'gt_visible': {'CAM_A': True}})
    with pytest.raises(ValueError, match='FORBIDDEN_KEY'):
        R.paid_run(args(tmp_path), transport=lambda body: None)
    assert not list((tmp_path / 'out').rglob('*.k1.json'))


def test_paid_run_refuses_over_cap_before_any_call(tmp_path, monkeypatch):
    stub_env(monkeypatch)
    calls = []
    a = args(tmp_path, baseline={'actual_total_usd': 85.0})
    with pytest.raises(SystemExit, match='CUMULATIVE_OVER_CAP'):
        R.paid_run(a, transport=lambda body: calls.append(body))
    assert not calls and not list((tmp_path / 'out').rglob('*.k1.json'))
