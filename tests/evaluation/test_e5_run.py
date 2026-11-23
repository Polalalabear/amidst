"""Synthetic E5 replay through the actual B1 sidecar and both frozen/E5 score readers.

Only fabricated images, detections, camera calibration and scoring annotations; no local dataset.
"""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUN = load('e5_run', ROOT / 'scripts/evaluation/e5_run.py')
SCORE = load('e5_score', ROOT / 'scripts/evaluation/e5_score.py')
S = load('e5_test_pinned_scorer', ROOT / 'src/amidst/evaluation/e3_scoring.py')
BOX = [100, 40, 140, 130]


@pytest.fixture
def synthetic(tmp_path):
    catalog = tmp_path / 'cameras.json'
    catalog.write_text(json.dumps({'cameras': [
        {'camera_id': c, 'camera_to_world': [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 5], [0, 0, 0, 1]],
         'fx': 100, 'fy': 100, 'cx': 160, 'cy': 90, 'width': 320, 'height': 180} for c in ('CAM_W2', 'CAM_B')]}))
    image = tmp_path / 'frame.png'
    with Image.new('RGB', (320, 180), 'black') as im:
        im.save(image)
    ticks = [(t, {'CAM_W2': [{'bbox': list(BOX), 'color': 'red', 'score': .8}],
                   'CAM_B': [{'bbox': list(BOX), 'color': 'blue', 'score': .15}]},
              {'CAM_W2': image, 'CAM_B': image}) for t in range(24)]
    case = {'case_id': 'SYNTH', 'ticks': ticks, 'cameras': ['CAM_W2', 'CAM_B'],
            'index_content_sha256': '1' * 64, 'records_file_sha256': '2' * 64, 'rgb_index_sha256': '3' * 64}
    scene = {'cameras': [{'camera_id': c} for c in case['cameras']]}
    return case, catalog, scene


def reply(kind='SELECT', camera='CAM_B', latency=0, **kw):
    doc = {'answer': kind, 'camera_id': camera, 'detection_id': 'D1', 'box_xyxy': BOX,
           'next_camera_ranking': [camera], 'confidence': 'medium', **kw}
    return {'text': json.dumps(doc), 'latency_s': latency, 'usage': {'input_tokens': 50, 'output_tokens': 10}}


def score_fixture(case):
    scoring_case = {'case_id': case['case_id'], 'family': 'SYNTHETIC', 'diagnostic_events': [],
                    'decision_points': [{'tick': 3, 'type': 'REAPPEAR', 'timestamp_us': 600000,
                                         'cameras': ['CAM_B'], 'evaluation_window_us': [600000, 1000000]}]}
    annotations = {'actor_id': 'synthetic_target', 'ticks': [
        {'tick': t, 'actors': [{'id': 'synthetic_target', 'present': True, 'xy': [-2, -2],
                              'gt_visible': ['CAM_B'], 'gt_boxes': {'CAM_B': BOX}}]} for t in range(24)]}
    return scoring_case, annotations


@pytest.mark.parametrize('mode,kind', [('offline', 'SELECT'), ('offline', 'OWN_BOX'), ('simlive', 'SELECT'), ('simlive', 'OWN_BOX')])
def test_generated_log_is_read_by_e3_and_e5_score(synthetic, mode, kind):
    case, catalog, scene = synthetic
    original = copy.deepcopy(case)
    responses = []
    def transport(body):
        responses.append(body)
        return reply(kind, latency=.4 if mode == 'simlive' else 0)
    doc = RUN.replay(case, catalog, scene, transport, mode=mode)
    # Real B1 sidecar acquires red W2; AO freely chooses blue CAM_B and has no red fallback.
    assert doc['seed_tick'] == 0 and doc['calls'][0]['request']['rule_state']['active_cam'] == 'CAM_W2'
    assert doc['rows'][0]['tracking']['state'] == 'LOST'
    apply_tick = 1 if mode == 'offline' else 3
    assert doc['rows'][apply_tick]['tracking']['active_cam'] == 'CAM_B'
    assert doc['rows'][apply_tick]['tracking']['box'] == BOX
    assert doc['calls'][0]['applied'] is True
    assert doc['schema_version'] == 'e5.b-log.v1' and doc['identity'] == 'UNCONFIRMED'
    assert doc['config']['call_cap_per_segment'] == 4 and len(doc['prompt_extra_sha256']) == 64
    assert doc['source_sha256']['scripts/evaluation/e3_f4_run.py']
    assert case == original  # B1 projection did not modify frozen observation objects
    assert len(responses) == len(doc['calls'])
    c, annotation = score_fixture(case)
    roundtrip = json.loads(json.dumps(doc, allow_nan=False))
    frozen = SCORE.F.run_scores(S, c, annotation, roundtrip)
    scored = SCORE.run_e5(S, c, annotation, roundtrip)
    assert frozen['n_ticks'] == scored['n_ticks'] == 24
    assert scored['e5']['unknown_reasons'] == {} and scored['e5']['provider_errors'] == 0
    assert scored['e5']['applied'] == len(doc['calls'])
    assert scored['decision_points'][0]['topk']['hit1'] == (mode == 'offline')
    assert scored['e5']['calls'] == len(responses)


def test_empty_ranking_remains_miss_with_legacy_hint(synthetic):
    case, catalog, scene = synthetic
    doc = RUN.replay(case, catalog, scene, lambda body: reply(next_camera_ranking=[], next_camera_hint='CAM_B'))
    assert doc['rows'][2]['ranking'] == []
    assert doc['calls'][0]['ranking_supplied'] is False and doc['calls'][0]['next_camera_hint_raw'] == 'CAM_B'
    c, annotation = score_fixture(case)
    scored = SCORE.run_e5(S, c, annotation, doc)
    assert scored['decision_points'][0]['topk']['hit1'] is False


def test_cap_event_only_and_errors_reach_e5_categories(synthetic):
    case, catalog, scene = synthetic
    kinds = iter([reply('NOT_VISIBLE'), {'text': 'bad json', 'latency_s': 0}, TimeoutError('timed out')])
    def transport(body):
        result = next(kinds)
        if isinstance(result, Exception):
            raise result
        return result
    doc = RUN.replay(case, catalog, scene, transport, call_cap_factor=1.0)
    c, annotation = score_fixture(case)
    scored = SCORE.run_e5(S, c, annotation, doc)
    assert scored['e5']['calls'] == 3 and scored['e5']['call_cap_reached'] == 1
    assert scored['e5']['provider_timeout'] == 1 and scored['e5']['format_rejected'] == 1
    assert scored['e5']['unknown_reasons'] == {}
    assert all(row['tracking']['state'] == 'LOST' for row in doc['rows'])


def test_aol_pending_at_segment_end_is_logged_once(synthetic):
    case, catalog, scene = synthetic
    doc = RUN.replay(case, catalog, scene, lambda body: reply(latency=20), mode='simlive')
    assert len(doc['calls']) == 1 and doc['pending_at_end'] and doc['calls'][0]['pending_at_end']
    assert not doc['calls'][0]['applied'] and not any(r['tracking']['active_cam'] for r in doc['rows'])


def test_sidecar_projection_mutations_do_not_leak_to_frozen_inputs(synthetic):
    case, catalog, scene = synthetic
    calls = []
    class Sidecar:
        def _infer_tracking(self, tick, t_s, dets, frames, size):
            calls.append(dets)
            dets['CAM_W2'][0].update(est_xy=[99, 99])
            return {'state': 'LOST', 'active_cam': None, 'lost_ticks': 99, 'events': []}
    before = copy.deepcopy(case)
    doc = RUN.replay(case, catalog, scene, lambda body: pytest.fail('no reference: no call'), sidecar=Sidecar())
    assert len(calls) == 24 and case == before and doc['calls'] == []
    assert all(r['tracking']['state'] == 'LOST' for r in doc['rows'])


def cli_args(tmp_path, catalog):
    return ['--root', str(tmp_path), '--cameras', str(catalog), '--out', str(tmp_path / 'out'),
            '--usage-dir', str(tmp_path / 'ledger'), '--cases', 'SYNTH', '--budget-usd', '1']


def test_cli_dry_run_never_constructs_transport_or_ledger(synthetic, tmp_path, monkeypatch, capsys):
    case, catalog, scene = synthetic
    monkeypatch.setattr(RUN.frozen, 'load_case', lambda *args: case)
    monkeypatch.setattr(RUN, 'guarded_transport', lambda *args: pytest.fail('dry-run must not create transport'))
    assert RUN.main(cli_args(tmp_path, catalog) + ['--dry-run']) == 0
    assert 'DRY_RUN' in capsys.readouterr().out
    assert not (tmp_path / 'ledger').exists() and not (tmp_path / 'out').exists()


def test_cli_writes_readable_outputs_and_skips_existing_without_loading(synthetic, tmp_path, monkeypatch):
    case, catalog, scene = synthetic
    monkeypatch.setattr(RUN.frozen, 'load_case', lambda *args: case)
    monkeypatch.setattr(RUN.frozen, 'live_scene_context', lambda *args: scene)
    monkeypatch.setattr(RUN, 'guarded_transport', lambda *args: (lambda body: reply(), object()))
    args = cli_args(tmp_path, catalog) + ['--k', '1']
    RUN.main(args)
    path = tmp_path / 'out/SYNTH/AO.k1.json'
    raw = path.read_bytes()
    doc = json.loads(raw)
    assert doc['schema_version'] == 'e5.b-log.v1' and doc['config']['cost_cap_usd'] == 1
    monkeypatch.setattr(RUN.frozen, 'load_case', lambda *args: pytest.fail('existing output must skip before loading'))
    RUN.main(args)
    assert path.read_bytes() == raw


@pytest.mark.parametrize('reason', ['budget', 'provider'])
def test_cli_preserves_failed_run_and_stops_remaining_k(synthetic, tmp_path, monkeypatch, reason):
    case, catalog, scene = synthetic
    monkeypatch.setattr(RUN.frozen, 'load_case', lambda *args: case)
    monkeypatch.setattr(RUN.frozen, 'live_scene_context', lambda *args: scene)
    def fail(body):
        if reason == 'budget':
            raise PermissionError('GUARD_DENIED:TOTAL_BUDGET')
        raise TimeoutError('timed out')
    monkeypatch.setattr(RUN, 'guarded_transport', lambda *args: (fail, object()))
    with pytest.raises(SystemExit, match='CALL_BUDGET_EXHAUSTED' if reason == 'budget' else 'PROVIDER_ERROR_RATE'):
        RUN.main(cli_args(tmp_path, catalog))
    assert (tmp_path / 'out/SYNTH/AO.k1.json').is_file()
    assert not (tmp_path / 'out/SYNTH/AO.k2.json').exists()


def test_guarded_transport_calls_apiguard_with_e5_caller(monkeypatch, tmp_path):
    from amidst.live_mode import service_decider
    from amidst.q1q5 import api_budget
    seen = []
    class Guard:
        def __init__(self, config, usage_dir):
            assert config.max_usd_total == config.max_usd_per_day == 2.5
            assert usage_dir == tmp_path and config.enabled
        def run(self, *args, **kw):
            seen.append(args)
            return 'guarded'
    monkeypatch.setattr(api_budget, 'ApiGuard', Guard)
    def factory(guard, model, timeout):
        assert model == 'gpt-6.1-terra' and timeout == 30
        return lambda body: guard.run('live_agent', model, 10, 20, lambda: pytest.fail('no external call'))
    monkeypatch.setattr(service_decider, 'guarded_responses_transport', factory)
    transport, _ = RUN.guarded_transport(2.5, tmp_path, 30)
    assert transport({}) == 'guarded' and seen[0][0] == 'e5'


def test_cli_prompt_only_and_invalid_limits(capsys):
    RUN.main(['--print-prompt'])
    assert RUN.E5_EXTRA in capsys.readouterr().out
    with pytest.raises(SystemExit):
        RUN.main([])
    for val in ('0', '-1', 'nan', 'inf'):
        with pytest.raises(SystemExit):
            RUN.main(['--root', '.', '--cameras', 'x', '--out', 'y', '--usage-dir', 'z', '--cases', 'S', '--budget-usd', val])


def test_reference_matches_frozen_e3_first_acquire(synthetic):
    case, catalog, scene = synthetic
    ao = RUN.replay(case, catalog, scene, lambda body: reply())
    _, calls, _ = RUN.frozen.replay(case, 'A2', catalog, {}, scene, lambda body: reply())
    assert calls and ao['calls'][0]['request']['reference'] == calls[0]['request']['reference']
    assert ao['seed_tick'] / 5 == calls[0]['request']['t_s']
