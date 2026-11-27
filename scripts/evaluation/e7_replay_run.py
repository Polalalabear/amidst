"""E7 real-latency replay + E5-rule scoring (#767, R1). Mac only; NO model inference.

Replays recorded E7 answers (checkpoint ``accelerated.records`` + their measured latency) through the unchanged E5 AO-L machinery
(``e7_replay.ReplayAOpenDecider`` over ``AOpenDecider`` simlive) on the frozen E3 detections, then scores the per-tick result with
``e3_f4_score.run_scores`` (pinned E3 scorer) exactly as E5 does, and lists the frozen B1 / AO / AOL numbers next to it.

Reads: E7 checkpoint + request jsonl (inference side), frozen E3 roots (detections, frames for the B1 colour judge) and, ONLY inside
``score_case``, the GT sidecars. Frames given to the decider are blank stubs (the reference crop is never sent anywhere).

Usage (see the PR for the exact command and SHA-256s):
  python scripts/evaluation/e7_replay_run.py --checkpoint e7_raw_comparisons_checkpoint.json --requests e3_16_segments.jsonl \
      --cameras cameras.catalog.json --scorer src/amidst/evaluation/e3_scoring.py --baseline e5-aol-20261124/report.json \
      --source ROOT_652 CATALOG_652 --source ROOT_665 CATALOG_665 --out OUT_DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(HERE))

import e3_f4_run as frozen  # noqa: E402
import e3_f4_score as F  # noqa: E402
import e5_run as E5R  # noqa: E402
from amidst.evaluation.e7_replay import CHAIN_STARTS, ReplayAOpenDecider, snapshot_table  # noqa: E402

TICK_US, SIZE = 200_000, (320, 180)
SCHEMA = 'e7_replay_v1'
POLL_S, MIN_INTERVAL_S, CALL_CAP_FACTOR, TIMEOUT_S = 2.0, 1.0, 1.5, 30.0   # = e5_run defaults (AOL)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def replay_case(case_data, scene, snapshots, catalog, chain_start, *, projector):
    """One case through ReplayAOpenDecider; same per-tick loop as ``e5_run.replay`` but with blank stub frames."""
    from PIL import Image
    ticks = case_data['ticks']
    duration = (ticks[-1][0] - ticks[0][0] + 1) * TICK_US / 1e6 if ticks else 0
    cap = math.ceil(duration / POLL_S * CALL_CAP_FACTOR)
    d = ReplayAOpenDecider(snapshots, scene, projector, chain_start=chain_start, poll_s=POLL_S, min_interval_s=MIN_INTERVAL_S,
                           call_cap=cap, timeout_s=TIMEOUT_S)
    blank = {cam: Image.new('RGB', SIZE) for cam in case_data['cameras']}   # stub: only cropped to seed the unused reference
    import copy
    sidecar = E5R.make_sidecar(catalog)   # fresh B1 sidecar per run, as e5_run.main does (its tracker state must not leak between runs)
    rows, prev = [], None
    for tick, frozen_dets, _paths in ticks:
        if prev is not None and tick != prev + 1:
            raise ValueError('NONCONTIGUOUS_TICKS')
        prev = tick
        dets = copy.deepcopy(frozen_dets)
        rule = sidecar._infer_tracking(tick, tick * TICK_US / 1e6, dets, {}, SIZE)
        rows.append(d.step(tick, copy.deepcopy(dets), blank, copy.deepcopy(rule)))
    return {'schema_version': 'e5.b-log.v1', 'case_id': case_data['case_id'], 'arm': 'E7REPLAY', 'k': 1, 'tick_us': TICK_US,
            'size': list(SIZE), 'config': {'chain_start': chain_start, 'poll_s': POLL_S, 'min_interval_s': MIN_INTERVAL_S,
                                           'call_cap_per_segment': cap, 'timeout_s': TIMEOUT_S, 'mode': 'simlive'},
            'rows': rows, 'calls': d.calls, 'seed_tick': d.seed_tick, 'pending_at_end': d.pending is not None, 'identity': 'UNCONFIRMED'}


def aggregate(scores_by_case, cases):
    """Same totals as ``e5_score.build_report`` per_arm (primary criterion): seconds summed over segments, DP over all points."""
    segs = []
    for c in cases:
        m = scores_by_case[c['case_id']]['primary']
        segs.append({'wp': m['wrong_person_s'], 'correct': (m['follow_rate'] or 0) * m['visible_ticks'], 'visible': m['visible_ticks'],
                     'lost': m['lost_s'], 'fl': m['false_lock_s']})
    dps = [d['correct'] for c in cases for d in scores_by_case[c['case_id']]['decision_points']]
    iou = [scores_by_case[c['case_id']]['iou_conservative'] for c in cases]
    calls = [x for c in cases for x in scores_by_case[c['case_id']].get('_calls', [])]
    reasons = {}
    for x in calls:
        r = x.get('fallback_reason') or 'APPLIED_OR_VALID'
        reasons[r] = reasons.get(r, 0) + 1
    return {'segments': [c['case_id'] for c in cases], 'wrong_target_s': round(sum(s['wp'] for s in segs), 3),
            'follow_rate': round(sum(s['correct'] for s in segs) / sum(s['visible'] for s in segs), 4),
            'lost_s': round(sum(s['lost'] for s in segs), 3), 'blind_lock_s': round(sum(s['fl'] for s in segs), 3),
            'dp_correct': sum(dps), 'dp_total': len(dps),
            'iou_conservative_follow_rate': round(sum((i['follow_rate'] or 0) * i['visible_ticks'] for i in iou)
                                                  / sum(i['visible_ticks'] for i in iou), 4),
            'calls': len(calls), 'call_outcomes': reasons,
            'applied': sum(1 for x in calls if x.get('applied')),
            'latency_s_p50': sorted(x['model_latency_s'] for x in calls)[len(calls) // 2] if calls else None}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--checkpoint', type=Path, required=True)
    ap.add_argument('--requests', type=Path, required=True)
    ap.add_argument('--cameras', type=Path, required=True)
    ap.add_argument('--scorer', type=Path, required=True)
    ap.add_argument('--baseline', type=Path, required=True, help='frozen E5 report.json (per_arm B1 / AO / AOL)')
    ap.add_argument('--source', nargs=2, action='append', required=True, metavar=('ROOT', 'CATALOG'))
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--parties', nargs='*', default=None, help='party ids to replay (default: all with parsed answers, i.e. qwen_vl)')
    a = ap.parse_args(argv)

    S = F.load_scorer(a.scorer)
    raw_cmp = json.loads(a.checkpoint.read_text())
    requests = [json.loads(x) for x in a.requests.read_text().splitlines() if x.strip()]
    base = json.loads(a.baseline.read_text())['per_arm']
    from amidst.live_mode.tracker import Projector, load_cameras
    projector = Projector(load_cameras(str(a.cameras)))
    runs = [c for c in raw_cmp if (a.parties is None or c['party_id'] in a.parties)]

    cases, case_root = [], {}
    for root, cat in a.source:
        catalog = json.loads(Path(cat).read_text())
        for case in catalog['cases']:
            cases.append(case)
            case_root[case['case_id']] = (Path(root), case)
    out = {'schema_version': SCHEMA, 'identity_status': 'UNCONFIRMED', 'frozen_baselines': {
        k: {x: base[k][x] for x in ('wrong_person_s', 'follow_rate', 'lost_s', 'false_lock_s', 'dp_correct', 'dp_total')}
        for k in ('B1', 'AO', 'AOL')}, 'arms': {}, 'inputs': {
            'checkpoint_sha256': sha(a.checkpoint.read_bytes()), 'requests_sha256': sha(a.requests.read_bytes()),
            'scorer_sha256': sha(a.scorer.read_bytes()), 'baseline_report_sha256': sha(a.baseline.read_bytes()),
            'cameras_catalog_sha256': sha(a.cameras.read_bytes())}, 'config': {
        'poll_s': POLL_S, 'min_interval_s': MIN_INTERVAL_S, 'call_cap_factor': CALL_CAP_FACTOR, 'timeout_s': TIMEOUT_S,
        'source_answers': 'checkpoint accelerated.records (GPU bf16), measured latency_ms',
        'metric_names': 'wrong_target_s = E5 wrong_person_s; blind_lock_s = E5 false_lock_s'}}
    docs = {}
    for case in cases:
        cid = case['case_id']
        root, entry = case_root[cid]
        data = frozen.load_case(root, cid)
        scene = frozen.live_scene_context(a.cameras, data['cameras'])
        a_raw = (root / entry['gt_path']).read_bytes()
        if sha(a_raw) != entry['gt_sha256']:
            raise SystemExit('GT_PIN_MISMATCH ' + cid)
        a_log = json.loads(a_raw)      # GT: scoring side only, never passed to the replay
        for c in runs:
            snaps = snapshot_table(c, requests, cid)
            for cs in CHAIN_STARTS:
                b_doc = replay_case(data, scene, snaps, a.cameras, cs, projector=projector)
                sc = F.run_scores(S, entry, a_log, b_doc)
                sc['_calls'] = b_doc['calls']
                key = f"{c['party_id']}|{c['input_mode']}|chain_{cs}"
                docs.setdefault(key, {})[cid] = sc
        print('CASE', cid, flush=True)
    for key, by_case in docs.items():
        out['arms'][key] = aggregate(by_case, cases)
    a.out.mkdir(parents=True, exist_ok=True)
    jp = a.out / 'e7_replay_20261127.json'
    jp.write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
    print('WROTE', jp, sha(jp.read_bytes()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
