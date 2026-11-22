#!/usr/bin/env python3
"""F1 (#660): recompute the frozen D325 / vision-agent pilot / W1 / W2 answer files with the unified E3 scorer. No API calls.

  e3_recompute_frozen.py [--out DIR]     # default: local/evidence/e3-scorer-20261122 (LOCAL, git-ignored)

Reads the frozen LOCAL answer files read-only (never rewrites them) and writes ``recompute.json`` to --out.
GT (r004 gt_private frame journal) is read only through ``gt_scoring_r004`` on this scoring side. Run with the repo venv.
"""
import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(REPO / 'scripts'))
from amidst.evaluation import e3_scoring as e3  # noqa: E402
from amidst.evaluation import gt_scoring_r004 as sc  # noqa: E402
from amidst.evaluation import vision_agent as va  # noqa: E402
from amidst.paths import local_dir  # noqa: E402

EV = local_dir() / 'evidence'
D325 = EV / 'eval-recorded-llm-20261118'
PILOT = EV / 'vision-agent-20261120'
W1 = EV / 'w1-frame-eval-20261120'
W2 = EV / 'w2-active-agent-20261120'
SIZE = (960, 540)       # every r004 camera (camera_catalog.json)
TICK = va.TICK


# --------------------------------------------------------------------------------------------- GT side (scoring only)
def pixel_labels():
    """W1 per-(event, camera, tick) pixel-evidence labels for EVERY r004 frame (frozen LOCAL, scoring side): present = GT body box
    >= 50 % inside the image AND >= 15 red pixels inside it (the target wears red). Detector-independent."""
    out = defaultdict(set)
    for r in json.loads((W1 / 'frames_all_labels.json').read_text()):
        if r['lab']['present']:
            out[(r['event'], r['t_us'])].add(r['camera'])
    return out


class GT:
    """r004 GT visibility (E3 preregistration §5): T visible in camera c at t when EITHER
    (a) some index detection (any class, score >= 0.3) has its centre in T's projected body box (the D325 criterion), OR
    (b) the W1 pixel-evidence label says present (body >= 50 % in frame and >= 15 red pixels in it).
    (a) alone made visibility depend on the detector: an Agent box on a target the detector missed was a 'false lock'.
    ``detector_only=True`` reproduces the D325 denominator for the comparison table."""

    def __init__(self, label, idx, dur, pixels=None, detector_only=False):
        self.label, self.dur = label, dur
        self.cams = sorted(sc.cams_of(label))
        self.gt = sc.gt_traj(label)
        allbox = defaultdict(list)
        for _oid, (c, t, b, _k, s) in idx.items():
            if s >= 0.3:
                allbox[(c, t)].append(b)
        self.vis, self.bodies = {}, {}
        for t in range(0, dur, TICK):
            foot = self.gt.get(t)
            if foot is None:
                continue
            for c in self.cams:
                body = sc.t_body(c, foot)
                self.bodies[(c, t)] = body
                det = bool(body) and any(sc.box_on_target(b, body, 0.0) for b in allbox.get((c, t), []))
                pix = not detector_only and pixels is not None and c in pixels.get((label, t), ())
                if det or pix:
                    self.vis.setdefault(t, set()).add(c)

    def ticks(self):
        return [t for t in range(0, self.dur, TICK) if t in self.gt]

    def body(self, cam, t):
        return self.bodies.get((cam, t))

    def hold_ok(self, cam, t):
        return any(cam in self.vis.get(t + d, ()) for d in range(-e3.HOLD_US, e3.HOLD_US + 1, TICK))

    def tick(self, t, disp):
        """disp = None (nothing shown) or (camera, [boxes], src)."""
        vis = frozenset(self.vis.get(t, ()))
        if disp is None:
            return e3.Tick(t, None, visible=vis)
        cam, boxes, src = disp
        return e3.Tick(t, cam, boxes=tuple(tuple(b) for b in boxes), visible=vis, body=self.body(cam, t), size=SIZE,
                       hold_ok=(not boxes) and self.hold_ok(cam, t), src=src)

    def score(self, displays):
        return e3.score_event([self.tick(t, displays.get(t)) for t in self.ticks()], tick_us=e3.TICK_US)   # r004 index 5 fps


# --------------------------------------------------------------------------------------------- displays
def rule_displays(single_view, sightings, idx, dur):
    sel = defaultdict(list)
    for s in sightings:
        if s.get('selected_for_single_view', True):
            for oid in s['observation_ids']:
                if oid in idx:
                    c, t, b, _k, _s = idx[oid]
                    sel[(c, t)].append(b)
    out = {}
    for t in range(0, dur, TICK):
        seg = next((s for s in single_view if s['range_us'][0] <= t < s['range_us'][1]), None)
        if seg and seg['kind'] == 'ON_CAMERA':
            out[t] = (seg['camera_id'], sel.get((seg['camera_id'], t), []), 'RULE')
    return out


def overlay_displays(rule, view, agent_disp):
    """Agent displays replace the rule display on rule-loss ticks only (the va.overlay contract)."""
    out = dict(rule)
    for t, d in agent_disp.items():
        if view.kind.get(t) == 'ON_CAMERA':
            continue
        out[t] = (d['cam'], [d['box']], 'AGENT' if d['kind'] == 'SNAP' else 'AGENT_OWN')
    return out


def w2_displays(ev, dets, recs, mode):
    """Mirror of run_w2_agent.evaluate, producing displays instead of classes (same replay, same on-camera replacement rules)."""
    import run_w2_agent as w2
    by_t = {r['t_us']: r for r in recs if r['event'] == ev.label}
    ctx = type('C', (), {'dets': dets})()
    ans, kinds = {}, {}
    for t, r in by_t.items():
        w2.prepare(r, ctx, t)
        a, kd = w2.to_va_answer(r)
        if a is not None:
            ans[t], kinds[t] = a, kd
    agent_disp, _calls = va.replay(ev.view, ev.index, lambda t: ans.get(t), mode)
    out = overlay_displays(ev.rule_disp, ev.view, agent_disp)
    for t, a in ans.items():
        if ev.view.kind[t] != 'ON_CAMERA' or kinds[t] == 'STILL':
            continue
        at = t if mode == 'offline' else t + -(-int(round((a.get('latency_s') or 0) * 1e6)) // TICK) * TICK
        if ev.view.kind.get(at) != 'ON_CAMERA' or ev.view.camera.get(at) != ev.view.camera[t]:
            continue
        if kinds[t] == 'HIDE':
            out.pop(at, None)
            continue
        res = va.resolve(a, t, ev.index)
        if res is None:
            continue
        cam = res[1]
        box = res[2].box if res[0] == 'SNAP' else res[2]
        if mode == 'realtime' and at != t:
            det, ok = (res[2] if res[0] == 'SNAP' else None), res[0] == 'SNAP'
            for u in range(t + TICK, at + 1, TICK):
                det = va._follow(ev.index, cam, det.box, u) if det else None
                if det is None:
                    ok = False
                    break
            if not ok:
                continue
            box = det.box
        out[at] = (cam, [box], 'AGENT_ON' if res[0] == 'SNAP' else 'AGENT_ON_OWN')
    return out, by_t


# --------------------------------------------------------------------------------------------- aggregation helpers
KEYS = ('follow_rate', 'wrong_person_s', 'mislocalized_s', 'lost_s', 'wrong_camera_s', 'false_lock_s')


def mean_of(scores):
    out = {'k': len(scores)}
    for crit in e3.CRITERIA:
        ms = [s[crit] for s in scores if s[crit].get('available')]
        if not ms:
            out[crit] = None
            continue
        o = {k: round(statistics.mean(m[k] for m in ms), 4) for k in KEYS}
        o['follow_rate_range'] = [min(m['follow_rate'] for m in ms), max(m['follow_rate'] for m in ms)]
        ious = [m['box_iou']['mean'] for m in ms if m['box_iou']['mean'] is not None]
        o['box_iou_mean'] = round(statistics.mean(ious), 4) if ious else None
        lat = [m['reacquire']['median_s'] for m in ms if m['reacquire']['median_s'] is not None]
        o['reacquire_median_s'] = round(statistics.mean(lat), 3) if lat else None
        o['reacquire_episodes'] = round(statistics.mean(m['reacquire']['episodes'] for m in ms), 2)
        o['error_share'] = {c: round(statistics.mean(m['error_share'][c] for m in ms), 4) for c in e3.ERROR_CLASSES}
        o['visible_s'] = ms[0]['visible_s']
        o['counts_by_src'] = [m['counts_by_src'] for m in ms]
        out[crit] = o
    return out


def both(ev, disps):
    """Main result (GT visibility = detector OR pixel evidence) and the detector-only sensitivity (D325 denominator)."""
    return {'new': mean_of([ev.gts.score(d) for d in disps]), 'new_detector_only': mean_of([ev.gts_det.score(d) for d in disps])}


# --------------------------------------------------------------------------------------------- experiments
def do_rule_and_d325(events):
    res = {}
    for label, ev in events.items():
        res[f'rule/{label}'] = both(ev, [ev.rule_disp])
    for model in ('terra6.1', 'sol6.1'):
        for label, ev in events.items():
            files = sorted(D325.glob(f'raw/{model}_{label}_k*.json'))
            disps, pub, recs, cost = [], [], [], 0.0
            for f in files:
                d = json.loads(f.read_text())
                disps.append(rule_displays(d['single_view'], d['sightings'], ev.raw, ev.dur))
                pub.append(d['metrics'])
                cost += d['cost_usd']
                for r in d['decision_records']:
                    wall = [a.get('wall_ms') for a in r.get('attempts', []) if a.get('outcome') == 'OK']
                    recs.append({'latency_s': (wall[-1] / 1000) if wall else None, 'adopted': r['decision_source'] == 'AGENT'})
            api = e3.api_stats(recs)
            api['cost_usd_total'] = round(cost, 4)
            res[f'D325/{model}/{label}'] = {**both(ev, disps), 'api': api, 'published': {
                'follow_rate': round(statistics.mean(p['follow_rate'] for p in pub), 4),
                'lost_s': round(statistics.mean(p['lost_s_while_visible'] for p in pub), 3),
                'wrong_person_s': round(statistics.mean(p['wrong_person_s'] for p in pub), 3),
                'false_lock_s': round(statistics.mean(p['false_lock_s_while_blind'] for p in pub), 3)}}
    return res


def do_pilot(events):
    pub = json.loads((PILOT / 'scores.json').read_text())
    res = {}
    files = sorted(PILOT.glob('answers_*_k*.json')) + sorted(PILOT.glob('info_answers_*_k*.json'))
    groups = defaultdict(list)
    for f in files:
        rec = json.loads(f.read_text())
        groups[('info_' if f.name.startswith('info_') else '') + f'{rec["model"]}_{rec["arm"]}'].append(rec)
    for key, recs in sorted(groups.items()):
        for label, ev in events.items():
            for mode in va.MODES:
                disps, api = [], []
                for rec in recs:
                    by_t = {a['t_us']: a for a in rec['answers'] if a['event'] == label}

                    def agent(t, by_t=by_t):
                        a = by_t.get(t)
                        if a is None or not a.get('answer'):
                            return None
                        return dict(a['answer'], latency_s=a.get('latency_s', 0.0))
                    disp, calls = va.replay(ev.view, ev.index, agent, mode)
                    disps.append(overlay_displays(ev.rule_disp, ev.view, disp))
                    eff = {c['call_t'] for c in calls if c.get('effective_t') is not None}
                    api += [{'latency_s': a.get('latency_s'), 'error': a.get('error'), 'adopted': t in eff} for t, a in by_t.items()]
                p = [m['metrics'] for m in pub[key][label][mode]]
                res[f'pilot/{key}/{label}/{mode}'] = {**both(ev, disps), 'api': e3.api_stats(api), 'published': {
                    'follow_rate': round(statistics.mean(m['follow_rate'] for m in p), 4),
                    'combined_follow_rate': round(statistics.mean(m['combined_follow_rate'] for m in p), 4),
                    'lost_s': round(statistics.mean(m['lost_s_while_visible'] for m in p), 3),
                    'combined_lost_s': round(statistics.mean(m['combined_lost_s_while_visible'] for m in p), 3),
                    'wrong_total_s': round(statistics.mean(m['wrong_total_s'] for m in p), 3),
                    'own_box_wrong_s': round(statistics.mean(m['own_box_wrong_s'] for m in p), 3)}}
    return res


def do_w2(events):
    import run_w2_agent as w2
    from amidst.q1q5.openai_gateway import PRICES
    pub = json.loads((W2 / 'scores.json').read_text())
    res, h4 = {}, {}
    dets = {label: w2.all_detections(label) for label in events}
    in_mt, out_mt = PRICES[w2.MODEL]
    for g in w2.GROUPS:
        files = sorted(W2.glob(f'answers_{g}_k*.json'))
        if not files:
            continue
        for label, ev in events.items():
            for mode in va.MODES:
                disps, api = [], []
                for f in files:
                    recs = json.loads(f.read_text())['answers']
                    disp, by_t = w2_displays(ev, dets[label], recs, mode)
                    disps.append(disp)
                    for r in by_t.values():
                        s1 = r.get('stage1') or {}
                        us = [x for x in (r.get('usage'), s1.get('usage')) if x]
                        lat = (r.get('latency_s') or 0) + (s1.get('latency_s') or 0)
                        api.append({'latency_s': lat or None, 'error': r.get('error'), 'adopted': r.get('source') == 'AGENT',
                                    'cost_usd': sum(w2.price_usd(u, in_mt, out_mt) for u in us) if us else None})
                p = pub[label].get(f'{g}/{mode}', {})
                res[f'W2/{g}/{label}/{mode}'] = {**both(ev, disps), 'api': e3.api_stats(api), 'published': {
                    k: p.get(k) for k in ('follow_rate', 'lost_s_while_visible', 'wrong_total_s', 'combined_follow_rate',
                                          'combined_lost_s_while_visible', 'own_box_wrong_s')}}
            if g in ('A2', 'C2'):
                items, item_t = [], []
                for f in files:
                    for r in json.loads(f.read_text())['answers']:
                        if r['event'] != label or r['rule_kind'] == 'ON_CAMERA' or not (r.get('stage1') or {}).get('look_at'):
                            continue
                        items.append((r['stage1']['look_at'], ev.gts.vis.get(r['t_us'], set()), len(ev.cams)))
                        item_t.append(r['t_us'])
                det_items = [(pk, ev.gts_det.vis.get(t, set()), n) for (pk, _v, n), t in zip(items, item_t)]
                h4[f'W2/{g}/{label}'] = {'new': e3.camera_topk(items, (1, 2, 3)), 'new_detector_only': e3.camera_topk(det_items, (1, 2, 3)),
                                         'published': pub['h4_camera_choice'].get(f'{g}/{label}')}
    return res, h4


def do_w1():
    import frame_eval_score as fs
    from amidst.evaluation import frame_eval as fe
    _smp, frames = fs.load()
    out = {}
    pub = {False: json.loads((W1 / 'w1_scores.json').read_text()), True: json.loads((W1 / 'w1_scores_majority.json').read_text())}
    orig = fe.box_hits
    try:
        for crit in e3.CRITERIA:
            def hits(box, body, crit=crit):
                return e3.judge_box(box, body, SIZE)['primary' if crit == 'primary' else 'iou_hit']
            fe.box_hits = hits
            for majority in (False, True):
                res = fs.outcome_fracs(frames, majority)
                for arm, m in res.items():
                    met = fs.metrics_from(fs.sums(m, list(frames)))
                    out.setdefault(arm, {})[f'{crit}/{"majority" if majority else "mean"}'] = {
                        k: (round(v, 4) if v is not None else None) for k, v in met.items()}
    finally:
        fe.box_hits = orig
    for arm in out:
        for majority in (False, True):
            p = pub[majority].get('overall_ci', {}).get(arm)
            out[arm][f'published/{"majority" if majority else "mean"}'] = {k: v['est'] for k, v in p.items()} if p else None
    return out


# --------------------------------------------------------------------------------------------- main
def load():
    import run_vision_agent as rv
    events = rv.load_events()
    pixels = pixel_labels()
    for label, ev in events.items():
        ev.gts = GT(label, ev.raw, ev.dur, pixels)
        ev.gts_det = GT(label, ev.raw, ev.dur, detector_only=True)
        ev.rule_disp = rule_displays(ev.rule_resp['single_view'], ev.rule_resp['sightings'], ev.raw, ev.dur)
    return events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=EV / 'e3-scorer-20261122')
    ap.add_argument('--skip-w1', action='store_true')
    args = ap.parse_args()
    for p in (D325, PILOT, W1, W2):
        if args.out.resolve() == p.resolve():
            raise SystemExit('OUTPUT_OVERWRITES_FROZEN_INPUT')
    events = load()
    res = {'schema_version': 'e3.recompute.v1', 'scorer': e3.SCHEMA}
    res.update(do_rule_and_d325(events))
    res.update(do_pilot(events))
    w2res, h4 = do_w2(events)
    res.update(w2res)
    res['h4'] = h4
    if not args.skip_w1:
        res['W1'] = do_w1()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'recompute.json').write_text(json.dumps(res, indent=1, sort_keys=True, default=list) + '\n')
    print('wrote', args.out / 'recompute.json')


if __name__ == '__main__':
    main()
