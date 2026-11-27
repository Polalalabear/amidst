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
               'calls': [{'answer': 'UNCERTAIN', 'fallback_reason': None, 'request': {'body_sha256': 'ab' * 32}}], 'history': [],
               'stopped_early': None}
        doc.update(doc_extra or {})
        return doc
    monkeypatch.setattr(R, 'replay', fake_replay)


def test_paid_run_outputs_manifest_and_no_scoring_fields(tmp_path, monkeypatch):
    stub_env(monkeypatch)
    a = args(tmp_path)
    n = R.paid_run(a, transport=lambda body: None)
    out = tmp_path / 'out'
    files = sorted(p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file())
    assert {'PRECHECK.json', 'STATUS.json', 'MANIFEST.sha256'} <= set(files)
    assert json.loads((out / 'STATUS.json').read_text())['status'] == 'COMPLETE' and 'E3-A1/DEANCHOR.k1.json' in files
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


# ---- atomic writes, status, stop on guard denial ---------------------------------------------------------
def test_serialization_failure_leaves_no_half_file_and_marks_incomplete(tmp_path, monkeypatch):
    stub_env(monkeypatch, doc_extra={'bad': {1, 2}})            # a set cannot be serialized
    with pytest.raises(TypeError):
        R.paid_run(args(tmp_path), transport=lambda body: None)
    out = tmp_path / 'out'
    assert not list(out.rglob('*.k1.json')) and not list(out.rglob('*.tmp'))
    status = json.loads((out / 'STATUS.json').read_text())
    assert status['status'] == 'INCOMPLETE' and 'TypeError' in status['reason']
    assert 'STATUS.json' in (out / 'MANIFEST.sha256').read_text()


def test_leftover_temp_file_is_not_a_skip_and_is_removed(tmp_path, monkeypatch):
    stub_env(monkeypatch)
    out = tmp_path / 'out'
    (out / 'E3-A1').mkdir(parents=True)
    (out / 'E3-A1' / 'DEANCHOR.k1.json.tmp').write_text('{"half"')
    R.paid_run(args(tmp_path), transport=lambda body: None)
    assert (out / 'E3-A1' / 'DEANCHOR.k1.json').exists() and not list(out.rglob('*.tmp'))
    assert json.loads((out / 'E3-A1' / 'DEANCHOR.k1.json').read_text())['arm'] == 'DEANCHOR'
    assert '.tmp' not in (out / 'MANIFEST.sha256').read_text()


def test_unexpected_exception_still_writes_status_and_manifest(tmp_path, monkeypatch):
    stub_env(monkeypatch)
    n = {'i': 0}
    real = R.replay

    def boom(*a, **k):
        n['i'] += 1
        if n['i'] == 3:
            raise RuntimeError('synthetic fault')
        return real(*a, **k)
    monkeypatch.setattr(R, 'replay', boom)
    with pytest.raises(RuntimeError):
        R.paid_run(args(tmp_path), transport=lambda body: None)
    out = tmp_path / 'out'
    assert json.loads((out / 'STATUS.json').read_text())['status'] == 'INCOMPLETE'
    manifest = (out / 'MANIFEST.sha256').read_text()
    assert 'E3-A1/DEANCHOR.k1.json' in manifest and 'E3-A1/DEANCHOR_HIST_SUM.k1.json' not in manifest


def test_guard_denial_stops_the_run_with_reason(tmp_path, monkeypatch):
    stub_env(monkeypatch)
    real, seen = R.replay, []

    def stopping(arm, case, *a, **k):
        seen.append((case['case_id'], arm))
        doc = real(arm, case, *a, **k)
        doc['calls'][0]['fallback_reason'] = 'CALL_BUDGET_EXHAUSTED'
        doc['stopped_early'] = {'tick': 4, 'reason': 'PermissionError:GUARD_DENIED:TOTAL_BUDGET'}
        return doc
    monkeypatch.setattr(R, 'replay', stopping)
    with pytest.raises(SystemExit, match='CALL_BUDGET_EXHAUSTED'):
        R.paid_run(args(tmp_path), transport=lambda body: None)
    assert seen == [('E3-A1', 'DEANCHOR')]                       # nothing after the first denied arm
    out = tmp_path / 'out'
    st = json.loads((out / 'STATUS.json').read_text())
    assert st['status'] == 'STOPPED' and 'TOTAL_BUDGET' in st['reason']
    assert (out / 'E3-A1' / 'DEANCHOR.k1.json').exists() and (out / 'MANIFEST.sha256').exists()


def test_replay_stops_immediately_when_guard_denies(tmp_path):
    from PIL import Image
    img = tmp_path / 'f.png'
    Image.new('RGB', (320, 180), 'black').save(img)
    det = {'A': [{'bbox': [10, 10, 30, 90], 'score': 0.5, 'color': 'red', 'est_xy': [1, 2]}]}
    ticks = [(t, det, {'A': img}) for t in range(60)]
    case = {'case_id': 'E3-A1', 'ticks': ticks, 'index_content_sha256': 'a', 'records_file_sha256': 'b', 'rgb_index_sha256': 'c'}
    sidecar = SimpleNamespace(_infer_tracking=lambda tick, t, dets, x, size: {
        'state': 'LOST', 'active_cam': 'A', 'est_xy': [1, 2], 'lost_ticks': 9, 'events': [{'type': 'ACQUIRE'}] if tick == 0 else []})

    class Proj:
        def ground(self, *a):
            return [1, 2]
    calls = []

    def denied(body):
        calls.append(1)
        raise PermissionError('GUARD_DENIED:TOTAL_BUDGET')
    doc = R.replay('DEANCHOR', case, tmp_path / 'cam.json', {'cameras': [{'camera_id': 'A'}]}, denied, sidecar=sidecar, projector=Proj())
    assert len(calls) == 1 and doc['calls'][0]['fallback_reason'] == 'CALL_BUDGET_EXHAUSTED'
    assert doc['stopped_early']['tick'] == 1 and 'GUARD_DENIED:TOTAL_BUDGET' in doc['stopped_early']['reason']
    assert len(doc['rows']) == 1


def test_estimate_pads_prompt_with_the_largest_history():
    pads = {arm: R.worst_case_history_tokens(arm) for arm in R.ARMS}
    assert 0 < pads['DEANCHOR'] < pads['DEANCHOR_HIST'] < pads['DEANCHOR_HIST_SUM']
    assert pads['DEANCHOR_HIST'] > 8 * 60          # eight full entries, not an empty history


# ---- formal K=3 run on E6-S01..S12 (batch-3 gate) ---------------------------------------------------------
FORMAL = [f'E6-S{i:02d}' for i in range(1, 13)]


def formal_args(tmp_path, **kw):
    base = dict(k=3, cases=list(FORMAL), arms=['DEANCHOR', 'DEANCHOR_HIST'], max_usd=32.0, receipt=tmp_path / 'freeze' / 'BATCH3_FREEZE.json')
    base.update(kw)
    return args(tmp_path, **base)


def write_receipt(tmp_path, **over):
    doc = {'SELECTED_AGENT': 'DEANCHOR_HIST', 'code_commit_sha': 'a' * 40, 'prompt_and_config_sha256': 'b' * 64, 'params': {},
           'formal_dry_run_estimate': {}, 'scorer_sha256': 'c' * 64}
    doc.update(over)
    (tmp_path / 'freeze').mkdir(exist_ok=True)
    (tmp_path / 'freeze' / 'BATCH3_FREEZE.json').write_text(json.dumps(doc))


@pytest.fixture
def approved(monkeypatch):
    monkeypatch.setenv('E6_BATCH3_APPROVED', '1')


def test_formal_requires_approval_env(tmp_path, monkeypatch):
    monkeypatch.delenv('E6_BATCH3_APPROVED', raising=False)
    write_receipt(tmp_path)
    with pytest.raises(SystemExit, match='FORMAL_NOT_APPROVED'):
        R.check_paid_request(formal_args(tmp_path))
    monkeypatch.setenv('E6_BATCH3_APPROVED', '0')
    with pytest.raises(SystemExit, match='FORMAL_NOT_APPROVED'):
        R.check_paid_request(formal_args(tmp_path))


def test_formal_requires_receipt_with_all_keys(tmp_path, approved):
    with pytest.raises(SystemExit, match='FORMAL_RECEIPT_MISSING'):
        R.check_paid_request(formal_args(tmp_path))
    (tmp_path / 'freeze').mkdir()
    (tmp_path / 'freeze' / 'BATCH3_FREEZE.json').write_text('not json')
    with pytest.raises(SystemExit, match='FORMAL_RECEIPT_UNREADABLE'):
        R.check_paid_request(formal_args(tmp_path))
    write_receipt(tmp_path)
    doc = json.loads((tmp_path / 'freeze' / 'BATCH3_FREEZE.json').read_text())
    del doc['scorer_sha256']
    (tmp_path / 'freeze' / 'BATCH3_FREEZE.json').write_text(json.dumps(doc))
    with pytest.raises(SystemExit, match='FORMAL_RECEIPT_INCOMPLETE'):
        R.check_paid_request(formal_args(tmp_path))
    write_receipt(tmp_path, SELECTED_AGENT='AO_ORIG')
    with pytest.raises(SystemExit, match='FORMAL_RECEIPT_BAD_SELECTED_AGENT'):
        R.check_paid_request(formal_args(tmp_path))


def test_formal_default_receipt_location(tmp_path, approved, monkeypatch):
    monkeypatch.delenv('E6_FREEZE_DIR', raising=False)
    ev = tmp_path / 'evidence'
    (ev / 'api-usage').mkdir(parents=True)
    (ev / 'e6-batch3-freeze-20261127').mkdir()
    (ev / 'e6-batch3-freeze-20261127' / 'BATCH3_FREEZE.json').write_text(
        json.dumps({'SELECTED_AGENT': 'DEANCHOR', 'code_commit_sha': 'a', 'prompt_and_config_sha256': 'b', 'params': {},
                    'formal_dry_run_estimate': {}, 'scorer_sha256': 'c'}))
    a = formal_args(tmp_path, receipt=None, arms=['DEANCHOR'], baseline_json=ev / 'api-usage' / 'RECONCILIATION_20261124.json')
    assert R.check_paid_request(a)[1] == 'FORMAL'
    monkeypatch.setenv('E6_FREEZE_DIR', str(tmp_path / 'elsewhere'))
    with pytest.raises(SystemExit, match='FORMAL_RECEIPT_MISSING'):
        R.check_paid_request(a)


@pytest.mark.parametrize('arms', [['DEANCHOR'], ['DEANCHOR_HIST'], ['AO_ORIG', 'DEANCHOR'], ['DEANCHOR', 'DEANCHOR_HIST', 'DEANCHOR_HIST_SUM'],
                                  ['DEANCHOR', 'DEANCHOR_HIST_SUM']])
def test_formal_arms_must_be_deanchor_plus_selected(tmp_path, approved, arms):
    write_receipt(tmp_path)                                     # SELECTED_AGENT = DEANCHOR_HIST
    with pytest.raises((SystemExit, ValueError)):
        R.check_paid_request(formal_args(tmp_path, arms=arms))


def test_formal_deanchor_selected_means_deanchor_only(tmp_path, approved):
    write_receipt(tmp_path, SELECTED_AGENT='DEANCHOR')
    assert R.check_paid_request(formal_args(tmp_path, arms=['DEANCHOR']))[1] == 'FORMAL'
    with pytest.raises(SystemExit, match='FORMAL_ARMS_REFUSED'):
        R.check_paid_request(formal_args(tmp_path, arms=['DEANCHOR', 'DEANCHOR_HIST']))


@pytest.mark.parametrize('kw,msg', [
    ({'k': 1}, 'PAID_COMBINATION_REFUSED'),
    ({'k': 2}, 'PAID_COMBINATION_REFUSED'),
    ({'cases': FORMAL[:11]}, 'PAID_COMBINATION_REFUSED'),
    ({'cases': FORMAL + ['E3-A1']}, 'PAID_COMBINATION_REFUSED'),
    ({'cases': FORMAL[:-1] + ['E6-S01']}, 'PAID_COMBINATION_REFUSED'),
    ({'max_usd': 32.01}, 'PAID_BUDGET_REFUSED'),
    ({'max_usd': 0}, 'PAID_BUDGET_REFUSED'),
    ({'paid': False}, 'PAID_RUN_NOT_AUTHORIZED'),
])
def test_formal_bad_requests(tmp_path, approved, kw, msg):
    write_receipt(tmp_path)
    with pytest.raises(SystemExit, match=msg):
        R.check_paid_request(formal_args(tmp_path, **kw))


def test_formal_ok_and_returns_receipt_info(tmp_path, approved):
    write_receipt(tmp_path)
    cap, mode, receipt = R.check_paid_request(formal_args(tmp_path))
    assert (cap, mode) == (32.0, 'FORMAL') and receipt['SELECTED_AGENT'] == 'DEANCHOR_HIST'
    assert receipt['sha256'] == hashlib.sha256((tmp_path / 'freeze' / 'BATCH3_FREEZE.json').read_bytes()).hexdigest()
    assert R.check_paid_request(args(tmp_path))[1] == 'DIAGNOSTIC'          # diagnostic path unchanged


def test_diagnostic_does_not_need_formal_gate(tmp_path, monkeypatch):
    monkeypatch.delenv('E6_BATCH3_APPROVED', raising=False)
    cap, mode, receipt = R.check_paid_request(args(tmp_path))
    assert (cap, mode, receipt) == (10.0, 'DIAGNOSTIC', None)


def test_formal_paid_run_writes_three_replicates_per_arm(tmp_path, approved, monkeypatch):
    stub_env(monkeypatch, est=20.0)
    write_receipt(tmp_path)
    a = formal_args(tmp_path)
    R.paid_run(a, transport=lambda body: None)
    out = tmp_path / 'out'
    runs = sorted(p.relative_to(out).as_posix() for p in out.rglob('*.k?.json'))
    assert len(runs) == 12 * 2 * 3 and 'E6-S12/DEANCHOR_HIST.k3.json' in runs and 'E6-S01/DEANCHOR.k1.json' in runs
    assert json.loads((out / 'E6-S05' / 'DEANCHOR.k2.json').read_text())['k'] == 2
    pre = json.loads((out / 'PRECHECK.json').read_text())
    assert pre['mode'] == 'FORMAL' and pre['receipt']['SELECTED_AGENT'] == 'DEANCHOR_HIST'
    assert json.loads((out / 'STATUS.json').read_text())['status'] == 'COMPLETE'


def test_formal_estimate_over_32_or_cumulative_over_90_refused(tmp_path, approved, monkeypatch):
    stub_env(monkeypatch, est=33.0)
    write_receipt(tmp_path)
    with pytest.raises(SystemExit, match='ESTIMATE_OVER_MAX_USD'):
        R.paid_run(formal_args(tmp_path), transport=lambda body: pytest.fail('no call'))
    stub_env(monkeypatch, est=30.0)
    led = tmp_path / 'ao-ledger'
    led.mkdir()
    (led / 'usage.jsonl').write_text(json.dumps({'ts': '2026-11-28T00:00:00Z', 'outcome': 'OK', 'est_cost_usd': 25.0}) + '\n')
    a = formal_args(tmp_path, extra_ledger=[str(led)])
    with pytest.raises(SystemExit, match='CUMULATIVE_OVER_CAP'):                 # 38.17 + 25 + 30 > 90
        R.paid_run(a, transport=lambda body: pytest.fail('no call'))
