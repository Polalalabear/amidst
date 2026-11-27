"""E8 W2: offline synthetic-answer baselines through the E7 full-trace replay (no inference, no paid calls).
Usage: python scripts/evaluation/e8_w2_offline_baselines.py <out.json>
(written by session e8-offline-b against claude/feat-e7-laya@179bccb7; that code is on main since #769 / e17a0787)
Synthetic answers replace the model's answer tick by tick (40 ms latency); chain_start='snapshot'; pinned scorer e3_scoring.py.
Confidence-threshold arms are EXPLORATORY (threshold chosen on the same 16 segments)."""
import collections, copy, hashlib, json, random, sys
from pathlib import Path

RO = Path(__file__).resolve().parents[2]; OUT = Path(sys.argv[1])
sys.path.insert(0, str(RO / 'src')); sys.path.insert(0, str(RO / 'scripts/evaluation'))
from amidst.paths import data_dir, evidence_dir
E = evidence_dir()
import e3_f4_run as frozen, e3_f4_score as F, e7_replay_run as R
from amidst.evaluation.e7_replay import snapshot_table
from amidst.live_mode.tracker import Projector, load_cameras

LAT = 0.04
CAM = data_dir() / 'live-assets-20261115/cameras.catalog.json'
S = F.load_scorer(RO / 'src/amidst/evaluation/e3_scoring.py')
raw = json.loads((E / 'e7-run-pertick-20261127/e7-outputs-pertick/e7-run-20261127/e7_raw_comparisons.json').read_text())
reqs = [json.loads(x) for x in (E / 'e7-colab-pack-pertick-20261127/requests/e3_16_segments.jsonl').read_text().splitlines() if x.strip()]
projector = Projector(load_cameras(str(CAM)))
srcs = [(E / 'e3-652-20261122', E / 'f4-658-20261122/runs-final-9', E / 'e5-aol-20261124/runs-9'),
        (E / 'e3-reappearances-20261122', E / 'f4-658-20261122/runs-final-665', E / 'e5-aol-20261124/runs-665')]
TAUS = (0.5, 0.6, 0.7, 0.8, 0.9)
KEYS = ('wrong_camera_s', 'wrong_person_only_s', 'wrong_person_s', 'lost_s', 'false_lock_s')

def parsed(ans, c=None, conf=1.0):
    return {'answer': ans, 'camera_id': c['camera_id'] if c else None, 'detection_id': c['detection_id'] if c else None,
            'box_xyxy': None, 'next_camera_ranking': [], 'confidence': conf, 'reason_codes': ['SYNTH'], 'reason': 'synthetic'}

def synth(cands, mode, rng=None):
    if mode == 'first':
        return parsed('SELECT', cands[0]) if cands else parsed('UNCERTAIN')
    if mode == 'first_red':
        r = [c for c in cands if 'red' in c['colors']]
        return parsed('SELECT', r[0]) if r else parsed('UNCERTAIN')
    if mode == 'random':
        return parsed('SELECT', rng.choice(cands)) if cands else parsed('UNCERTAIN')

def thr(p, tau, fallback):
    if p and p['answer'] == 'SELECT' and (p.get('confidence') or 0) < tau:
        return parsed(fallback)
    return p

agg = collections.defaultdict(lambda: collections.defaultdict(float)); dp = collections.defaultdict(lambda: [0, 0])
def add(arm, sc):
    m = sc['primary']
    for k in KEYS: agg[arm][k] += m[k]
    agg[arm]['correct'] += (m['follow_rate'] or 0) * m['visible_ticks']; agg[arm]['visible'] += m['visible_ticks']
    dp[arm][0] += sum(d['correct'] for d in sc['decision_points']); dp[arm][1] += len(sc['decision_points'])

for root, b1runs, aolruns in srcs:
    cat = json.loads((root / 'CORPUS.json').read_text())
    for case in cat['cases']:
        cid = case['case_id']; a_raw = (root / case['gt_path']).read_bytes()
        assert hashlib.sha256(a_raw).hexdigest() == case['gt_sha256']
        a_log = json.loads(a_raw)
        add('B1', F.run_scores(S, case, a_log, json.loads((b1runs / cid / 'B1.k1.json').read_text())))
        add('AOL', F.run_scores(S, case, a_log, json.loads((aolruns / cid / 'AOL.k1.json').read_text())))
        data = frozen.load_case(root, cid); scene = frozen.live_scene_context(CAM, data['cameras'])
        def run(arm, snaps):
            for s in snaps.values(): s['latency_s'] = LAT
            add(arm, F.run_scores(S, case, a_log, R.replay_case(data, scene, snaps, CAM, 'snapshot', projector=projector)))
        base = snapshot_table(raw[0], reqs, cid)
        rid = {t: f'{cid}|t{t}' for t in base}
        for mode in ('first', 'first_red'):
            run('a_first' if mode == 'first' else 'b_first_red',
                {t: dict(s, parsed=synth(s['candidates'], mode)) for t, s in base.items()})
        for seed in (0, 1, 2):
            run(f'c_random_seed{seed}', {t: dict(s, parsed=synth(s['candidates'], 'random', random.Random(f'{seed}|{rid[t]}')))
                                         for t, s in base.items()})
        for c in raw:
            arm = c['party_id']; snaps = snapshot_table(c, reqs, cid)
            orig = {t: s['parsed'] for t, s in snaps.items()}
            run(f'd_{arm}_raw_40ms', {t: dict(s) for t, s in snaps.items()})
            for tau in TAUS:
                for fb in ('UNCERTAIN', 'NOT_VISIBLE'):
                    run(f'd_{arm}_tau{tau}_{fb}', {t: dict(s, parsed=thr(orig[t], tau, fb)) for t, s in snaps.items()})
            # original latency (sanity vs analysis doc)
            sn = snapshot_table(c, reqs, cid)
            add(f'ref_{arm}_orig_latency', F.run_scores(S, case, a_log, R.replay_case(data, scene, sn, CAM, 'snapshot', projector=projector)))
        print('CASE', cid, flush=True)

out = {'note': 'threshold arms (d_*_tau*) are EXPLORATORY; latency 40 ms for all synthetic arms; ref_* use recorded laya latency',
       'agg': {}}
for a, v in sorted(agg.items()):
    out['agg'][a] = {**{k: round(v[k], 1) for k in KEYS}, 'follow_rate': round(v['correct'] / v['visible'], 3),
                     'dp_correct': dp[a][0], 'dp_total': dp[a][1], 'visible_s': round(v['visible'] / 5, 1)}
# random: mean of seeds
rs = [out['agg'][f'c_random_seed{i}'] for i in range(3)]
out['agg']['c_random_mean3'] = {k: round(sum(r[k] for r in rs) / 3, 3) for k in rs[0]}
OUT.write_text(json.dumps(out, indent=1))
for a, v in out['agg'].items(): print(a, v)
