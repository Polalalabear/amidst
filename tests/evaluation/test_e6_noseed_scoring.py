"""D405: groups that never start (B1 without ACQUIRE -> R-N seed null, Agent seed_tick None) are scored, never dropped.

Synthetic GT and run logs only; the REAL pinned scorer (e3_f4_score.run_scores) and the real verdict code run on them.
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts' / 'evaluation'))
import e3_f4_score as F4  # noqa: E402
import e6_verdict_run as C  # noqa: E402
from amidst.evaluation import e6_verdict as V  # noqa: E402

SEL = 'DEANCHOR_HIST'
NO_SEED_CASES = {'E6-S04', 'E6-S07'}
N_TICKS = 400
DPS = [(10, 'VISIBLE'), (110, 'VISIBLE'), (210, 'FULL_BLIND'), (310, 'TRUE_DEPARTURE')]
BOX = [100.0, 40.0, 130.0, 150.0]


def a_log(cid):
    ticks = []
    for t in range(N_TICKS):
        present = t < 300
        visible = t < 200
        ticks.append({'tick': t, 'actors': [{'id': 'T', 'present': present, 'xy': [1.0, 1.0],
                                              'gt_visible': ['CAM_A'] if visible else [], 'gt_boxes': {'CAM_A': BOX} if visible else {}}]})
    return {'actor_id': 'T', 'case': cid, 'ticks': ticks}


def tracking(state, cam=None, box=None):
    if state == 'TRACKING':
        return {'state': 'TRACKING', 'active_cam': cam, 'est_xy': [1.0, 1.0], 'lost_ticks': 0, 'box': box}
    return {'state': state, 'active_cam': None, 'est_xy': None, 'lost_ticks': 0 if state == 'NEEDS_PICK' else 1, 'box': None}


def doc(arm, cid, mode, k=1):
    rows = []
    for t in range(N_TICKS):
        if mode == 'follows' and t < 200:
            tr = tracking('TRACKING', 'CAM_A', BOX)
        elif mode == 'wrong' and t < 300:
            tr = tracking('TRACKING', 'CAM_A', [10.0, 10.0, 20.0, 40.0])
        elif mode == 'needs_pick':
            tr = tracking('NEEDS_PICK')
        else:
            tr = tracking('LOST')
        rows.append({'tick': t, 'tracking': tr, 'ranking': [], 'events': []})
    return {'schema_version': 'x', 'arm': arm, 'k': k, 'case_id': cid, 'rows': rows, 'calls': [],
            'seed': None if mode in ('needs_pick', 'never_started') else {'tick': 0}, 'seed_tick': None if mode == 'never_started' else 0}


def build(tmp_path):
    gt = tmp_path / 'gt'
    (gt / 'gt-boxes').mkdir(parents=True)
    cases, roots = [], {n: tmp_path / 'runs' / n for n in ('b1', 'ao', 'arms', 'rn')}
    for i in range(1, 13):
        cid = f'E6-S{i:02d}'
        raw = json.dumps(a_log(cid)).encode()
        (gt / 'gt-boxes' / f'{cid}.a-log.json').write_bytes(raw)
        cases.append({'case_id': cid, 'family_id': f'E6-F{i:02d}', 'gt_path': f'gt-boxes/{cid}.a-log.json', 'gt_sha256': hashlib.sha256(raw).hexdigest(),
                      'actual_decision_points': [{'dp_id': f'{cid}-DP{j + 1}', 'type': 'X', 'tick': t, 'gt_regime': r} for j, (t, r) in enumerate(DPS)]})
        ns = cid in NO_SEED_CASES
        docs = [('b1', doc('B1', cid, 'needs_pick' if ns else 'wrong')),                                   # B1 stayed in NEEDS_PICK on S04/S07
                ('rn', doc('RN_U', cid, 'never_started' if ns else 'wrong')),
                ('rn', doc('RN_N', cid, 'never_started' if ns else 'wrong'))]
        docs += [('ao', doc('AO', cid, 'never_started' if ns else 'wrong', k)) for k in (1, 2, 3)]
        docs += [('arms', doc('DEANCHOR', cid, 'never_started' if ns else 'wrong', k)) for k in (1, 2, 3)]
        docs += [('arms', doc(SEL, cid, 'never_started' if ns else 'follows', k)) for k in (1, 2, 3)]
        for name, d in docs:
            p = roots[name] / cid / f"{d['arm']}.k{d['k']}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(d))
    spec = {'status': 'FROZEN_PRE_SCORING_D399', 'formal_cases': cases}
    return spec, gt, list(roots.values())


def test_no_seed_documents_are_scored_with_the_pinned_scorer_and_not_dropped(tmp_path):
    spec, gt, runs = build(tmp_path)
    S = F4.load_scorer(REPO / 'src/amidst/evaluation/e3_scoring.py')
    groups = ['AO_ORIG', 'B1', 'DEANCHOR', SEL, 'RN_U']
    segments, points, quality = C.score(spec, gt, runs, S, F4.run_scores, groups)
    assert len(segments) == 12 * len(groups)                                  # every (case, group), including the never-started ones
    seg = {(s['case_id'], s['group']): s for s in segments}
    for cid in NO_SEED_CASES:
        for g in groups:
            s = seg[(cid, g)]
            assert s['wrong_person_s'] == [0.0] * len(s['wrong_person_s'])    # never showed anyone
            assert s['blind_false_lock_s'] == [0.0] * len(s['blind_false_lock_s'])
            assert s['follow_rate'] == [0.0] * len(s['follow_rate'])           # visible ticks still in the denominator, none correct
            assert all(v > 0 for v in s['visible_ticks']) and all(v > 0 for v in s['lost_s'])
    # decision points: all 48 per group stay in the denominator; never-started groups are wrong on VISIBLE windows, right on blind/departure
    per = {}
    for p in points:
        per.setdefault(p['group'], []).append(p)
    assert all(len(v) == 48 for v in per.values())
    for p in per[SEL]:
        if p['case_id'] in NO_SEED_CASES:
            assert p['full_track_correct'] == ([False] * 3 if p['gt_regime'] == 'VISIBLE' else [True] * 3)
    # the verdict code runs on these inputs without crashing; paired differences on the no-seed families are exactly 0 by construction
    verdict = V.verdict_e6(segments, points, selected_agent=SEL)
    assert verdict['M'] == 12 and verdict['N_dp'] == 48 and verdict['status'] in ('FORMAL', 'EXPLORATORY')
    wp = {(s['case_id'], s['group']): sum(s['wrong_person_s']) / len(s['wrong_person_s']) for s in segments}
    for cid in NO_SEED_CASES:
        assert wp[(cid, SEL)] - wp[(cid, 'B1')] == 0.0 and wp[(cid, 'DEANCHOR')] - wp[(cid, 'AO_ORIG')] == 0.0
    assert quality['DEANCHOR']['runs'] == 36


def test_verdict_cli_with_no_seed_runs_end_to_end(tmp_path):
    spec, gt, runs = build(tmp_path)
    spec_path = tmp_path / 'frozen.json'
    spec_path.write_text(json.dumps(spec))
    out = tmp_path / 'out'
    C.main(['--frozen-spec', str(spec_path), '--gt-root', str(gt), '--runs', *map(str, [r for r in runs if r.name != 'rn']), '--selected-agent', SEL,
            '--out', str(out)])
    v = json.loads((out / 'verdict_e6.json').read_text())
    assert v['M'] == 12 and v['N_dp'] == 48 and set(v['groups']) >= {'B1', 'AO_ORIG', 'DEANCHOR', SEL}
