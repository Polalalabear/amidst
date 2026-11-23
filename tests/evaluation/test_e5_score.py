"""E5 (#684) scoring wrapper: contract §7 call categories, control events, H8a-H8d wiring. SYNTHETIC e5.b-log.v1 data only
(no network, no model, no real GT)."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCORER = ROOT / 'src/amidst/evaluation/e3_scoring.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


E5 = load('e5_score', ROOT / 'scripts/evaluation/e5_score.py')
F4 = sys.modules['e3_f4_score']
needs_scorer = pytest.mark.skipif(not SCORER.is_file(), reason='e3_scoring.py not in this checkout')

BODY, WRONG = (100, 40, 140, 130), (250, 40, 290, 130)
N, DPS = 24, (2, 6, 10, 14, 18)


def call(reason=None, applied=False, answer='SELECT', **kw):
    return {'tick': 0, 'kind': 'POLL', 'answer': answer, 'applied': applied, 'fallback_reason': reason, 'model_latency_s': 1.0,
            'usage': {'input_tokens': 10, 'output_tokens': 2}, 'source': 'AGENT' if not reason else 'NEUTRAL', **kw}


# ---------------------------------------------------------------------------------------------- call categories (contract §7)
def test_every_fallback_reason_lands_in_its_category():
    calls = ([call('PROVIDER_TIMEOUT', answer=None)] + [call('PROVIDER_ERROR', answer=None)]
             + [call(r, answer=None) for r in ('FORMAT_INVALID', 'UNKNOWN_DETECTION', 'BAD_OWN_BOX', 'BAD_CAMERA')]
             + [call('CALL_BUDGET_EXHAUSTED', answer=None), call('EXPIRED', applied=False), call('OCCLUDED_NO_TARGET', answer='STILL_HERE_OCCLUDED'),
                call(applied=True), call(answer='UNCERTAIN')])
    e = E5.normalize_calls(calls)
    assert (e['provider_timeout'], e['provider_error'], e['provider_errors']) == (1, 1, 2)
    assert e['format_rejected'] == 4 and e['format_reasons'] == {'FORMAT_INVALID': 1, 'UNKNOWN_DETECTION': 1, 'BAD_OWN_BOX': 1, 'BAD_CAMERA': 1}
    assert (e['budget_denied'], e['expired'], e['occluded_no_target'], e['applied']) == (1, 1, 1, 1)
    assert e['calls'] == 11 and e['unknown_reasons'] == {} and e['rerun_needed_budget'] is True
    # valid = answered calls that are not provider/format/budget failures: EXPIRED, OCCLUDED_NO_TARGET, applied, UNCERTAIN
    assert e['valid_calls'] == 4 and e['answer_counts'] == {'SELECT': 2, 'STILL_HERE_OCCLUDED': 1, 'UNCERTAIN': 1}


def test_occluded_no_target_is_valid_not_error_unlike_e3_api_breakdown():
    calls = [call('OCCLUDED_NO_TARGET', answer='STILL_HERE_OCCLUDED')] * 5 + [call(applied=True)] * 5
    e = E5.normalize_calls(calls)
    assert e['provider_errors'] == 0 and e['provider_error_rate'] == 0.0 and e['valid_calls'] == 10 and e['provider_error_stop'] is False
    assert F4.api_breakdown(calls)['error'] == 5          # the E3 function would have called these errors (hence the wrapper)


def test_unknown_reason_is_reported_not_guessed():
    e = E5.normalize_calls([call('RULE_FALLBACK', answer=None), call(applied=True)])
    assert e['unknown_reasons'] == {'RULE_FALLBACK': 1} and e['valid_calls'] == 1 and e['provider_errors'] == 0


def test_call_cap_reached_is_an_event_not_a_call():
    rows = [{'tick': 3, 'events': [{'tick': 3, 'type': 'CALL_CAP_REACHED', 'cam': None, 'detail': {}}]},
            {'tick': 4, 'events': [{'tick': 4, 'type': 'SWITCH'}]}, {'tick': 5}]
    e = E5.normalize_calls([call(applied=True)] * 3, rows)
    assert e['call_cap_reached'] == 1 and e['calls'] == 3 and e['provider_errors'] == 0 and e['valid_calls'] == 3
    assert E5.normalize_calls([], rows)['calls'] == 0 and E5.normalize_calls([], rows)['provider_error_rate'] == 0.0


def test_provider_error_rate_over_10_percent_raises_stop_flag():
    ok = [call(applied=True)] * 9
    assert E5.normalize_calls(ok + [call('PROVIDER_TIMEOUT', answer=None)])['provider_error_stop'] is False       # exactly 10 %
    e = E5.normalize_calls(ok + [call('PROVIDER_TIMEOUT', answer=None), call('PROVIDER_ERROR', answer=None)])
    assert e['provider_error_rate'] == round(2 / 11, 4) and e['provider_error_stop'] is True
    assert E5.normalize_calls([call('FORMAT_INVALID', answer=None)] * 5 + ok)['provider_error_stop'] is False      # format errors are not provider errors


def test_format_return_rate_over_20_percent_raises_flag():
    ok = [call(applied=True)] * 8
    assert E5.normalize_calls(ok + [call('BAD_OWN_BOX', answer=None)] * 2)['format_return_flag'] is False          # exactly 20 %
    e = E5.normalize_calls(ok + [call('BAD_OWN_BOX', answer=None)] * 3)
    assert e['format_return_rate'] == round(3 / 11, 4) and e['format_return_flag'] is True and e['provider_error_stop'] is False


# ---------------------------------------------------------------------------------------------- end to end with the pinned scorer
def case_and_gt(cid):
    ticks = [{'tick': k, 'actors': [{'id': 'T', 'present': True, 'xy': [0.0, 0.0], 'gt_visible': ['CAM_W2'], 'gt_boxes': {'CAM_W2': list(BODY)}}]}
             for k in range(N)]
    dps = [{'tick': k, 'type': 'REAPPEAR', 'timestamp_us': k * 200_000, 'cameras': ['CAM_W2'], 'evaluation_window_us': [k * 200_000, k * 200_000 + 400_000]}
           for k in DPS]
    return {'case_id': cid, 'family': 'X', 'decision_points': dps, 'diagnostic_events': []}, {'actor_id': 'T', 'ticks': ticks}


def doc(arm, cid, shown, ranking, k=1, calls=(), events_at=None):
    rows = []
    for t in range(N):
        tr = ({'state': 'TRACKING', 'active_cam': 'CAM_W2', 'est_xy': [0.0, 0.0], 'lost_ticks': 0, 'box': list(shown)} if shown
              else {'state': 'LOST', 'active_cam': None, 'est_xy': None, 'lost_ticks': 1, 'box': None})
        rows.append({'tick': t, 'tracking': tr, 'ranking': list(ranking), 'events': [{'tick': t, 'type': 'CALL_CAP_REACHED'}] if t == events_at else []})
    return {'schema_version': 'e5.b-log.v1' if arm in ('AO', 'AOL') else 'e3.b-log', 'case_id': cid, 'arm': arm, 'k': k, 'rows': rows, 'calls': list(calls)}


def score(arms_docs, ncases=8):
    S = load('e3_scoring_pinned_t', SCORER)
    cases, per = [], {}
    for i in range(ncases):
        cid = f'S{i}'
        case, a_log = case_and_gt(cid)
        cases.append(case)
        b1 = next(d for d in arms_docs(cid) if d['arm'] == 'B1')
        b1c = F4.run_scores(S, case, a_log, b1)['classes']
        for d in arms_docs(cid):
            per.setdefault((cid, d['arm']), []).append(E5.run_e5(S, case, a_log, d, b1c))
    return E5.build_report(S, cases, per), per


@needs_scorer
def test_ao_beats_b1_and_ranking_drives_h8c_empty_ranking_is_a_miss():
    def docs(cid):
        ao = [doc('AO', cid, BODY, ['CAM_W2'], k=k, calls=[call(applied=True)] * 3) for k in (1, 2, 3)]
        return [doc('B1', cid, WRONG, []), *ao]               # B1: wrong person, no ranking; AO: right person, ranked
    rep, per = score(docs)
    assert rep['per_arm']['AO']['follow_rate'] == 1.0 and rep['per_arm']['B1']['follow_rate'] == 0.0
    h8c = rep['comparisons']['AO-B1|topk']
    assert rep['per_arm']['B1']['top1'][0] == 0 and rep['per_arm']['B1']['ranked_points'] == 0       # empty ranking = miss
    assert rep['per_arm']['AO']['top1'] == (8 * 5 * 3, 8 * 5 * 3) and rep['per_arm']['B1']['top1'][1] == 8 * 5   # denominators 120 vs 40
    assert h8c['top1_diff'] == 1.0
    v = rep['verdicts']
    assert v['H8a']['verdict'] == 'SUPPORTED' and v['H8a']['n_segments'] == 8 and v['H8a']['n_points'] == 40
    assert v['H8c']['verdict'] == 'SUPPORTED' and v['H8c']['verdict_zh'] == '成立'
    assert v['H8d']['verdict'] == 'UNKNOWN' and v['H8d']['note'] == '未執行'          # no AOL arm -> not run
    assert 'AOL-B1' not in rep['comparisons']


@needs_scorer
def test_ao_without_ranking_is_not_supported_for_h8c_even_if_tracking_wins():
    def docs(cid):
        return [doc('B1', cid, WRONG, ['CAM_W2']), doc('AO', cid, BODY, [], calls=[call(applied=True)])]   # AO tracks well but never ranks
    rep, _ = score(docs)
    assert rep['per_arm']['AO']['top1'][0] == 0 and rep['verdicts']['H8c']['verdict'] == 'NOT_SUPPORTED'       # upper < 0
    assert rep['verdicts']['H8a']['verdict'] == 'SUPPORTED'                                                    # H8a does not look at ranking


@needs_scorer
def test_ao_and_aol_are_judged_apart_and_aol_is_labelled_k1():
    def docs(cid):
        return [doc('B1', cid, WRONG, ['CAM_W2']), doc('AO', cid, BODY, ['CAM_W2'], k=1), doc('AO', cid, BODY, ['CAM_W2'], k=2),
                doc('AO', cid, BODY, ['CAM_W2'], k=3), doc('AOL', cid, WRONG, ['CAM_W2'], k=1, calls=[call('EXPIRED')])]
    rep, per = score(docs)
    v = rep['verdicts']
    assert v['H8a']['verdict'] == 'SUPPORTED' and v['H8d']['verdict'] == 'INCONCLUSIVE'      # AOL is as wrong as B1 here: no difference
    assert 'K=1' in v['H8d']['note'] and 'H8b' in v and 'H8c' in v
    assert [len(per[(f'S0', a)]) for a in ('AO', 'AOL', 'B1')] == [3, 1, 1]
    assert rep['per_arm']['AOL']['e5_calls']['expired'] == 8 and rep['per_arm']['AO']['e5_calls']['expired'] == 0


@needs_scorer
def test_stop_flags_and_cap_events_reach_the_report():
    def docs(cid):
        bad = [call(applied=True)] * 5 + [call('PROVIDER_ERROR', answer=None)] * 2 + [call('BAD_CAMERA', answer=None)] * 3 + [call('CALL_BUDGET_EXHAUSTED', answer=None)]
        return [doc('B1', cid, WRONG, []), doc('AO', cid, BODY, ['CAM_W2'], calls=bad, events_at=5)]
    rep, _ = score(docs, ncases=2)
    s = rep['stop']
    assert len(s['provider_error_runs']) == 2 and len(s['format_return_runs']) == 2 and len(s['budget_denied_runs']) == 2
    ao = rep['per_arm']['AO']['e5_calls']
    assert ao['calls'] == 22 and ao['call_cap_reached'] == 2 and ao['provider_errors'] == 4 and ao['budget_denied'] == 2
    md = E5.render_md(rep)
    assert '| AO |' in md and 'CALL_CAP_REACHED' in md and '| H8a |' in md and 'UNKNOWN' in md
    json.dumps(rep, default=list)
