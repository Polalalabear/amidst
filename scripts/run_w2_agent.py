#!/usr/bin/env python3
"""W2 (#645) E2a trial: active Agent decider on the full A4-1 / B4-1 tracking, plus the prompt-cache strategy comparison.

  run_w2_agent.py scene                          # build + print scene context (hash, size); no network
  run_w2_agent.py dry-run [--k 2]                # estimate, no network
  run_w2_agent.py call --group A|B|C --k 2       # PAID through ApiGuard (caller=w2_agent)
  run_w2_agent.py cache --n 40 --n-state 15      # PAID: cache strategy comparison (none / prefix / state)
  run_w2_agent.py score                          # replay + GT scoring (offline and realtime), writes tables

Groups: A = images + scene context; B = scene context, no images (text only); C = images, no scene context. Rule = baseline.
GT is read only through Event.body_of / gt_scoring_r004 on the scoring side. Run with the repo venv (Pillow). Outputs: LOCAL evidence dir.
"""
import argparse
import concurrent.futures as cf
import dataclasses
import hashlib
import io
import json
import math
import os
import statistics
import sys
import time
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(REPO / 'scripts'))
import run_vision_agent as rv  # noqa: E402  (events, frame paths, guard helpers)
from amidst.evaluation import gt_scoring_r004 as sc  # noqa: E402
from amidst.evaluation import vision_agent as va  # noqa: E402
from amidst.paths import local_dir  # noqa: E402
from amidst.q1q5 import agent_service as ag  # noqa: E402
from amidst.q1q5 import api_budget as ab  # noqa: E402
from amidst.q1q5 import scene_context as sx  # noqa: E402
from amidst.q1q5.agent_providers import default_http_transport  # noqa: E402
from amidst.q1q5.openai_gateway import PRICES  # noqa: E402

DATE = os.environ.get('W2_AGENT_DATE', '20261120')
OUT = local_dir() / f'evidence/w2-active-agent-{DATE}'
MODEL = 'gpt-6.1-terra'
RESPONSES_URL = 'https://api.openai.com/v1/responses'
CALLER = 'w2_agent'
BUDGET_USD = 20.0
STOP_USD = 12.0       # W2 stops here; total account stop is 40 (see brief)
CACHED_READ_X, CACHE_WRITE_X = 0.05, 1.25     # docs (prompt-caching guide, 2026-11-20): GPT-6.1 Terra read 0.05x, 30m write 1.25x
GRAPH_DIR = REPO / 'configs/q1q5/graphs/r004'
CATALOG = sc.D / 'r004-cx7r-20261104-01a19f8b/bundle/safe_bundle/provenance/camera_catalog.json'
GROUPS = {'A': dict(images=True, scene=True), 'B': dict(images=False, scene=True), 'C': dict(images=True, scene=False),
          'A2': dict(images=True, scene=True, two_stage=True), 'C2': dict(images=True, scene=False, two_stage=True)}


# --------------------------------------------------------------------------------------------- scene + detections
GEOMETRY = REPO / 'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json'


def scene_for(label, with_static=False):
    """``with_static`` (D346): add wall-clipped coverage from the static occluders/doors. Off by default so W2 stays reproducible."""
    docs = {n: json.load(open(GRAPH_DIR / n)) for n in ('region_graph_v3_1.json', 'camera_graph_v3_1.json', 'tracking_scope_v3_1.json')}
    sha = {n: hashlib.sha256(open(GRAPH_DIR / n, 'rb').read()).hexdigest() for n in docs}
    sha['camera_catalog.json'] = hashlib.sha256(open(CATALOG, 'rb').read()).hexdigest()
    return sx.build(docs['region_graph_v3_1.json'], docs['camera_graph_v3_1.json'], json.load(open(CATALOG)), sorted(sc.cams_of(label)),
                    sha, docs['tracking_scope_v3_1.json'], static=sx.static_geometry(GEOMETRY.read_bytes()) if with_static else None)


def all_detections(label):
    d = sc.D / f'demo-owned-v1/data/indexes/{label}'
    meta = json.load(open(d / 'detection_index.json'))
    out = {}
    for line in open(d / meta['records_ref']):
        r = json.loads(line)
        dets = sorted([x for x in (r.get('detections') or []) if x['score'] >= ag.INDEX_FLOOR], key=lambda x: x['observation_id'])
        out[(r['camera_id'], r['timestamp_us'])] = [ag.Candidate(f'D{i + 1}', r['camera_id'], tuple(x['bbox_xyxy_px']), x['score'], x['class_label'],
                                                                  va.colors_of(x.get('color'))) for i, x in enumerate(dets)]
    return out


def decision_ticks(ev):
    """Every rule-loss tick after first lock + every rule ON_CAMERA tick whose selected box has score<0.45 + every 4th other ON_CAMERA tick."""
    view = ev.view
    lock = view.first_lock
    low = set(ev.verify_ticks_all())
    out, n = [], 0
    for t in view.ticks:
        if lock is None or t < lock:
            continue
        if view.kind[t] != 'ON_CAMERA' or t in low:
            out.append(t)
        else:
            n += 1
            if n % 4 == 0:
                out.append(t)
    return out


def verify_ticks_all(self):
    sc_by = {}
    for s in self.rule_resp['sightings']:
        if s.get('selected_for_single_view', True):
            for oid in s['observation_ids']:
                c, t, _b, _k, sco = self.raw[oid]
                sc_by[(c, t)] = max(sc_by.get((c, t), 0), sco)
    return [t for t in self.view.ticks if self.view.kind[t] == 'ON_CAMERA' and sc_by.get((self.view.camera[t], t), 1) < 0.45]


rv.Event.verify_ticks_all = verify_ticks_all


class Ctx:
    """Per-event cached stuff for building DecisionInput (system data only)."""

    def __init__(self, ev):
        self.ev = ev
        self.scene = scene_for(ev.label)
        self.dets = all_detections(ev.label)
        from PIL import Image
        seed = Image.open(ev.frame_path(ev.seed['camera_id'], ev.seed['t']))
        x0, y0, x1, y1 = ev.seed['box']
        w, h = x1 - x0, y1 - y0
        self.ref_jpeg = rv._jpeg(seed.crop((max(0, x0 - .15 * w), max(0, y0 - .1 * h), min(seed.width, x1 + .15 * w), min(seed.height, y1 + .1 * h))))
        self.overlap = {(o['cameras'][0], o['cameras'][1]) for o in self.scene['overlaps']}

    def frames(self, t):
        from PIL import Image, ImageDraw
        out = []
        for cam in self.ev.cams:
            im = Image.open(self.ev.frame_path(cam, t)).convert('RGB')
            dr = ImageDraw.Draw(im)
            for c in self.dets.get((cam, t), []):
                dr.rectangle(c.box, outline=(255, 220, 0), width=2)
                dr.rectangle((c.box[0], c.box[1], c.box[0] + 26, c.box[1] + 14), fill=(255, 220, 0))
                dr.text((c.box[0] + 3, c.box[1] + 1), c.id, fill=(0, 0, 0))
            dr.rectangle((0, 0, 150, 14), fill=(0, 0, 0))
            dr.text((3, 1), cam, fill=(255, 255, 255))
            out.append((cam, rv._jpeg(im)))
        return out

    def input_for(self, t, group):
        ev, view = self.ev, self.ev.view
        g = GROUPS[group]
        showing = view.kind[t] == 'ON_CAMERA'
        if showing:
            last_cam, last_t = view.camera[t], t
        else:
            lk = va.last_known(view, t)
            last_cam, last_t = (lk[0], lk[1]) if lk else (None, None)
        cands = []
        for cam in ev.cams:
            for c in self.dets.get((cam, t), []):
                ov = last_cam is not None and cam != last_cam and ((cam, last_cam) in self.overlap or (last_cam, cam) in self.overlap)
                cands.append(dataclasses.replace(c, overlap_camera=ov))
        rule_answer = None
        if showing:
            ids = [c.id for c in cands if c.camera_id == last_cam and any(va.iou(c.box, b) >= 0.5 for b in view.boxes[t])]
            rule_answer = {'camera_id': last_cam, 'detection_ids': ids}
        return ag.DecisionInput(
            scene_context=self.scene, include_scene=g['scene'], t_s=t / 1e6, candidates=cands, seed_colors=tuple(ev.seed['colors']),
            reference_jpeg=self.ref_jpeg if g['images'] else None, frames=self.frames(t) if g['images'] else [],
            rule_display={'kind': view.kind[t], 'camera_id': last_cam, 'last_t_s': None if last_t is None else last_t / 1e6},
            rule_answer=rule_answer, last_camera=last_cam)


# --------------------------------------------------------------------------------------------- transport (ApiGuard)
def price_usd(usage, in_mt, out_mt):
    unc = usage['input_tokens'] - usage['cached_tokens'] - usage['cache_write_tokens']
    return (unc + CACHED_READ_X * usage['cached_tokens'] + CACHE_WRITE_X * usage['cache_write_tokens']) * in_mt / 1e6 + usage['output_tokens'] * out_mt / 1e6


def make_transport(guard, est_tokens=9000):
    in_mt, out_mt = PRICES[MODEL]

    def transport(body):
        key = os.environ.get('OPENAI_API_KEY', '').strip()
        if not key:
            raise PermissionError('NO_API_KEY')
        payload = json.dumps(body).encode()

        def call():
            t0 = time.time()
            try:
                _s, raw = default_http_transport(url=RESPONSES_URL, headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
                                                 body=payload, timeout_s=90)
            except urllib.error.HTTPError as exc:
                raise RuntimeError(f'HTTP_{exc.code}:{exc.read(400)!r}') from None
            r = ag.parse_response(json.loads(raw))
            r['latency_s'] = round(time.time() - t0, 3)
            u = r['usage']
            r['cost_usd'] = round(price_usd(u, in_mt, out_mt), 6)
            billed_in = int((u['input_tokens'] - u['cached_tokens'] - u['cache_write_tokens']) + CACHED_READ_X * u['cached_tokens'] + CACHE_WRITE_X * u['cache_write_tokens'])
            return r, billed_in, u['output_tokens']
        out = guard.run(CALLER, MODEL, est_tokens, body['max_output_tokens'], call)
        if not out.allowed:
            raise PermissionError('GUARD_DENIED:' + str(out.reason))
        return out.value
    return transport


def guard():
    base = ab.GuardConfig.from_env()
    probe = ab.ApiGuard(dataclasses.replace(base, enabled=True))
    existing = sum(r['est_cost_usd'] for r in probe._rows() if isinstance(r.get('est_cost_usd'), (int, float)) and r.get('outcome') != 'DENIED')
    pr = {MODEL: {'input_usd_per_mtok': PRICES[MODEL][0], 'output_usd_per_mtok': PRICES[MODEL][1]}}
    cfg = dataclasses.replace(base, enabled=True, max_usd_total=existing + BUDGET_USD, max_usd_per_day=BUDGET_USD + 40, max_calls_per_day=30000,
                              max_calls_per_min=120, max_usd_per_call=0.08, max_tokens_per_call=40000, prices=pr)
    return ab.ApiGuard(cfg), probe.ledger_path


def spent(path):
    s = 0.0
    if path.exists():
        for line in open(path):
            r = json.loads(line)
            if r.get('caller') == CALLER and isinstance(r.get('est_cost_usd'), (int, float)):
                s += r['est_cost_usd']
    return s


# --------------------------------------------------------------------------------------------- commands
def cmd_scene(args, ctxs):
    for label, c in ctxs.items():
        text = sx.serialize(c.scene)
        print(label, 'bytes', len(text), 'est tokens', len(text) // 3.5, 'sha256', sx.sha256_of(c.scene), 'incomplete', c.scene['incomplete'])
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f'scene_context_{label}.json').write_text(text)


def cmd_dry(args, ctxs):
    in_mt, out_mt = PRICES[MODEL]
    tot = 0
    for g in GROUPS:
        n = sum(len(decision_ticks(c.ev)) for c in ctxs.values())
        tok = {'A': 9000, 'B': 3800, 'C': 7000}[g]
        usd = n * args.k * (tok * 0.5 * in_mt + 150 * out_mt) / 1e6      # ~half of prompt cached after warm-up (assumption)
        tot += usd
        print(g, 'calls', n * args.k, 'est USD', round(usd, 2))
    print('TOTAL est USD', round(tot, 2), '(rough, cached share assumed 50%)', {l: len(decision_ticks(c.ev)) for l, c in ctxs.items()})


def run_points(tr, ctxs, group, k, workers, limit=0):
    jobs = [(c, t) for c in ctxs.values() for t in decision_ticks(c.ev)][: limit or None]

    def one(job):
        c, t = job
        inp = c.input_for(t, group)
        rec = {'event': c.ev.label, 't_us': t, 'group': group, 'k': k, 'rule_kind': c.ev.view.kind[t]}
        two = GROUPS[group].get('two_stage')
        for attempt in (1, 2):
            try:
                s1_lat = 0.0
                if two:                                   # stage 1: the Agent picks where to look from the scene context only
                    s1 = None
                    try:
                        r1 = tr(ag.build_select_body(MODEL, inp, c.ev.cams))
                        s1, e1 = ag.parse_select(r1['text'], set(c.ev.cams))
                        rec['stage1'] = {'look_at': s1['look_at'] if s1 else None, 'error': e1, 'usage': r1['usage'], 'latency_s': r1['latency_s'],
                                         'reason_codes': s1['reason_codes'] if s1 else None}
                        s1_lat = r1['latency_s']
                    except Exception as exc:  # noqa: BLE001
                        rec['stage1'] = {'look_at': None, 'error': f'{type(exc).__name__}:{str(exc)[:160]}'}
                        if attempt == 1 and 'GUARD' not in str(exc):
                            continue
                    if s1 is None:
                        rec.update(source='RULE', fallback='STAGE1_FAILED', answer=None, usage=None, latency_s=None, error=rec['stage1']['error'], attempts=attempt)
                        break
                    inp = ag.restrict(inp, s1['look_at'][:2])
                d = ag.decide(inp, mode='AGENT', transport=tr, model=MODEL, cache='prefix')
                rec.update(source=d.decision_source, fallback=d.fallback_reason, answer=d.answer if d.agent_used else None, usage=d.usage,
                           latency_s=None if d.latency_s is None else round(d.latency_s + s1_lat, 3), error=d.error, attempts=attempt)
                if d.fallback_reason and d.fallback_reason.startswith('TRANSPORT') and attempt == 1:
                    continue
                break
            except Exception as exc:  # noqa: BLE001
                rec.update(error=f'{type(exc).__name__}:{str(exc)[:200]}', attempts=attempt)
        return rec
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, jobs))


def cmd_call(args, ctxs):
    g, ledger = guard()
    tr = make_transport(g)
    OUT.mkdir(parents=True, exist_ok=True)
    for k in range(args.k):
        path = OUT / f'answers_{args.group}_k{k}.json'
        if path.exists() and not args.force:
            print('skip', path.name)
            continue
        if spent(ledger) >= STOP_USD:
            print('STOP: w2 spend', spent(ledger))
            return
        t0 = time.time()
        res = run_points(tr, ctxs, args.group, k, args.workers, args.limit)
        path.write_text(json.dumps({'group': args.group, 'k': k, 'model': MODEL, 'wall_s': round(time.time() - t0, 1), 'answers': res}, indent=1))
        bad = sum(1 for r in res if r.get('source') != 'AGENT')
        print(path.name, len(res), 'fallbacks/errors', bad, 'w2 spend', round(spent(ledger), 4), flush=True)


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, math.ceil(p / 100 * len(xs)) - 1)] if xs else None


def cmd_cache(args, ctxs):
    g, ledger = guard()
    tr = make_transport(g)
    OUT.mkdir(parents=True, exist_ok=True)
    pts = [(c, t) for c in ctxs.values() for t in decision_ticks(c.ev)]
    step = max(1, len(pts) // args.n)
    pts = pts[::step][: args.n]
    results = {}
    for arm in ('none', 'prefix', 'state'):
        sel = pts[: args.n_state] if arm == 'state' else pts
        rows, prev = [], None
        for i, (c, t) in enumerate(sel):
            inp = c.input_for(t, 'A')
            if arm == 'state' and (i == 0 or c.ev.label != sel[i - 1][0].ev.label):
                prev = None                                  # new event -> new scene -> new chain
            kw = {'cache': arm}
            if arm == 'none':
                kw['nonce'] = f'{arm}-{i}-{time.time_ns()}'
            if arm == 'state' and prev:
                kw['previous_response_id'] = prev
            resp, err = None, None
            try:
                body = ag.build_body(MODEL, inp, **kw)
                resp = tr(body)
            except Exception as exc:  # noqa: BLE001
                err = f'{type(exc).__name__}:{str(exc)[:200]}'
            row = {'event': c.ev.label, 't_us': t, 'arm': arm, 'error': err}
            if resp:
                ans, perr = ag.parse_answer(resp['text'], inp)
                row.update(usage=resp['usage'], latency_s=resp['latency_s'], cost_usd=resp['cost_usd'], answer=ans, parse_error=perr)
                prev = resp['response_id'] if arm == 'state' else None
            rows.append(row)
            if spent(ledger) >= STOP_USD:
                print('STOP budget')
                break
        results[arm] = rows
        print(arm, len(rows), 'errors', sum(1 for r in rows if r['error']), 'w2 spend', round(spent(ledger), 4), flush=True)
    (OUT / 'cache_comparison.json').write_text(json.dumps(results, indent=1))


# --------------------------------------------------------------------------------------------- scoring
def to_va_answer(rec):
    """Service answer -> (va-format answer, kind). kind: SHOW | STILL | HIDE."""
    a = rec.get('answer')
    lat = rec.get('latency_s') or 0.0
    if not a:
        return None, None
    if a['answer'] == 'SELECT':
        return {'present': True, 'camera_id': a['camera_id'], 'detection_id': None, 'box_xyxy': a['_box'], 'latency_s': lat}, 'SHOW'
    if a['answer'] == 'OWN_BOX':
        return {'present': True, 'camera_id': a['camera_id'], 'detection_id': None, 'box_xyxy': a['box_xyxy'], 'latency_s': lat}, 'SHOW'
    return {'present': False, 'camera_id': None, 'detection_id': None, 'box_xyxy': None, 'latency_s': lat}, ('STILL' if a['answer'] == 'STILL_HERE_OCCLUDED' else 'HIDE')


def prepare(rec, ctx, t):
    a = rec.get('answer')
    if a and a['answer'] == 'SELECT':
        cand = next((c for c in ctx.dets.get((a['camera_id'], t), []) if c.id == a['detection_id']), None)
        a['_box'] = list(cand.box) if cand else None


def evaluate(ctx, recs, mode):
    ev = ctx.ev
    by_t = {r['t_us']: r for r in recs if r['event'] == ev.label}
    kinds = {}
    for t, r in by_t.items():
        prepare(r, ctx, t)
    ans = {}
    for t, r in by_t.items():
        a, kd = to_va_answer(r)
        if a is not None:
            ans[t] = a
            kinds[t] = kd
    displays, calls = va.replay(ev.view, ev.index, lambda t: ans.get(t), mode)
    rows = va.overlay(ev.rule_rows, displays, ev.body_of)
    byrow = {r['t_us']: i for i, r in enumerate(rows)}
    changed = {'help': 0, 'harm': 0, 'asked_on_camera': 0}
    tick = va.TICK
    for t, a in ans.items():
        if ev.view.kind[t] != 'ON_CAMERA':
            continue
        changed['asked_on_camera'] += 1
        kd = kinds[t]
        at = t if mode == 'offline' else t + -(-int(round((a.get('latency_s') or 0) * 1e6)) // tick) * tick
        if at not in byrow or ev.view.kind.get(at) != 'ON_CAMERA' or ev.view.camera.get(at) != ev.view.camera[t]:
            continue
        i = byrow[at]
        r = rows[i]
        before = r['cls']
        if kd == 'STILL':
            continue
        if kd == 'HIDE':
            new = dict(r, src='AGENT_HIDE', kind='NONE', cls='MISSED' if r['t_visible'] else 'BLIND_OK')
        else:
            res = va.resolve(a, t, ev.index)
            if res is None:
                continue
            cam = res[1]
            box = res[2].box if res[0] == 'SNAP' else res[2]
            if mode == 'realtime' and at != t:                 # follow the box forward through the index; stale answers are dropped
                det, ok = (res[2] if res[0] == 'SNAP' else None), res[0] == 'SNAP'
                for u in range(t + tick, at + 1, tick):
                    det = va._follow(ev.index, cam, det.box, u) if det else None
                    if det is None:
                        ok = False
                        break
                if not ok:
                    continue
                box = det.box
            body = ev.body_of(cam, at)
            hit = body is not None and (va.center_in(box, body, 0.0) or (res[0] == 'OWN' and va.iou(box, body) >= va.OWN_IOU))   # own box: centre-in-body OR IoU>=0.3 (#647 definition)
            new = dict(r, src='AGENT_ON', kind='ON_CAMERA', camera=cam, cls='CORRECT' if hit else ('WRONG_PERSON' if r['t_visible'] else 'FALSE_LOCK'))
        rows[i] = new
        if before == 'CORRECT' and new['cls'] != 'CORRECT':
            changed['harm'] += 1
        elif before != 'CORRECT' and new['cls'] == 'CORRECT':
            changed['help'] += 1
    m = sc.metrics(rows)
    m.update(va.episode_stats(ev.view, ev.rule_rows, rows))
    m.update(changed)
    m['agent_asked'] = len(ans)
    m['calls'] = len(by_t)
    m['fallbacks'] = sum(1 for r in by_t.values() if r.get('source') != 'AGENT')
    return m


def agg(ms):
    keys = ['follow_rate', 'lost_s_while_visible', 'wrong_total_s', 'combined_follow_rate', 'combined_lost_s_while_visible', 'own_box_wrong_s',
            'help', 'harm', 'wrong_connections', 'fallbacks']
    out = {}
    for k in keys:
        vals = [m[k] for m in ms if m.get(k) is not None]
        out[k] = round(statistics.mean(vals), 3) if vals else None
        if len(vals) > 1:
            out[k + '_range'] = [min(vals), max(vals)]
    return out


def h4_camera_hits(ctx, recs, group):
    """Stage-1 'where to look' accuracy (scoring side, GT via rule_rows.t_visible). Loss ticks only (rule not ON_CAMERA) with the target
    detectable somewhere; baselines: last displayed camera, last + DRAFT-graph neighbours, random k."""
    ev = ctx.ev
    n = len(ev.cams)
    acc = {'ticks': 0, 'top1': 0, 'top2': 0, 'top3': 0, 'last_cam': 0, 'graph_nbrs': 0, 'random_top1': 0.0, 'random_top2': 0.0, 'random_top3': 0.0, 'n_cams': n}
    per = []
    for r in recs:
        if r['event'] != ev.label or r['rule_kind'] == 'ON_CAMERA' or not (r.get('stage1') or {}).get('look_at'):
            continue
        t = r['t_us']
        vis = set(ev.rule_rows[t // va.TICK]['t_visible'])
        if not vis:
            continue
        lk = va.last_known(ev.view, t)
        last = lk[0] if lk else None
        nb = set(va.allowed_cameras(last, ev.transitions, ev.cams)) if last else set()
        picks = r['stage1']['look_at']
        acc['ticks'] += 1
        for kk in (1, 2, 3):
            acc[f'top{kk}'] += bool(set(picks[:kk]) & vis)
        acc['last_cam'] += last in vis
        acc['graph_nbrs'] += bool(nb & vis)
        for kk in (1, 2, 3):
            acc[f'random_top{kk}'] += 1 - math.comb(n - len(vis), kk) / math.comb(n, kk) if n - len(vis) >= kk else 1.0
        per.append({'t_s': t / 1e6, 'last': last, 'picks': picks, 'target_visible_in': sorted(vis)})
    return acc, per


def cmd_score(args, ctxs):
    res = {}
    for label, c in ctxs.items():
        rule = sc.metrics([dict(r) for r in c.ev.rule_rows])
        res[label] = {'rule': {'follow_rate': rule['follow_rate'], 'lost_s_while_visible': rule['lost_s_while_visible'], 'wrong_total_s': rule['wrong_total_s'],
                               'decision_points': len(decision_ticks(c.ev))}}
        for g in GROUPS:
            files = sorted(OUT.glob(f'answers_{g}_k*.json'))
            for mode in va.MODES:
                ms = [evaluate(c, json.loads(f.read_text())['answers'], mode) for f in files]
                if ms:
                    res[label][f'{g}/{mode}'] = agg(ms)
                    res[label][f'{g}/{mode}']['k'] = len(ms)
    h4 = {}
    for g in ('A2', 'C2'):
        for label, c in ctxs.items():
            tot, perk = None, []
            for f in sorted(OUT.glob(f'answers_{g}_k*.json')):
                a, per = h4_camera_hits(c, json.loads(f.read_text())['answers'], g)
                tot = a if tot is None else {k: (tot[k] + a[k] if k != 'n_cams' else a[k]) for k in a}
                perk.append(per)
            if tot:
                h4[f'{g}/{label}'] = tot
    res['h4_camera_choice'] = h4
    (OUT / 'scores.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


def cmd_cache_report(args, ctxs):
    data = json.loads((OUT / 'cache_comparison.json').read_text())
    ref = {}
    for f in sorted(OUT.glob('answers_A_k*.json')):
        for r in json.loads(f.read_text())['answers']:
            if r.get('answer'):
                ref.setdefault((r['event'], r['t_us']), []).append(r['answer'])
    key = lambda a: (a['answer'], a.get('camera_id'), a.get('detection_id'))  # noqa: E731
    lines = ['| 策略 | 呼叫 | 輸入 token 平均 | cached_tokens 平均 | 命中率 | cache 寫入 token 平均 | 延遲 p50 s | 延遲 p95 s | USD／決策點 | 答案同基準 |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    summ = {}
    for arm, rows in data.items():
        ok = [r for r in rows if r.get('usage')]
        if not ok:
            continue
        inp = [r['usage']['input_tokens'] for r in ok]
        cac = [r['usage']['cached_tokens'] for r in ok]
        wr = [r['usage']['cache_write_tokens'] for r in ok]
        lat = [r['latency_s'] for r in ok]
        same = tot = 0
        diff = []
        for r in ok:
            refs = ref.get((r['event'], r['t_us']))
            if r.get('answer') and refs:
                tot += 1
                if key(r['answer']) in [key(a) for a in refs]:
                    same += 1
                else:
                    diff.append((r['event'], r['t_us'] / 1e6, key(r['answer']), [key(a) for a in refs]))
        hit = sum(cac) / sum(inp)
        summ[arm] = {'n': len(ok), 'input': statistics.mean(inp), 'cached': statistics.mean(cac), 'hit': hit, 'write': statistics.mean(wr), 'p50': pct(lat, 50), 'p95': pct(lat, 95),
                     'usd': statistics.mean(r['cost_usd'] for r in ok), 'same': f'{same}/{tot}', 'diff': diff}
        s = summ[arm]
        lines.append(f"| {arm} | {s['n']} | {s['input']:.0f} | {s['cached']:.0f} | {s['hit']:.2f} | {s['write']:.0f} | {s['p50']:.2f} | {s['p95']:.2f} | {s['usd']:.4f} | {s['same']} |")
    (OUT / 'cache_table.md').write_text('\n'.join(lines) + '\n\n' + json.dumps(summ, indent=1, default=str))
    print('\n'.join(lines))
    for arm, s in summ.items():
        for d in s['diff']:
            print('DIFF', arm, d)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('scene')
    d = sub.add_parser('dry-run')
    d.add_argument('--k', type=int, default=2)
    c = sub.add_parser('call')
    c.add_argument('--group', choices=list(GROUPS), required=True)
    c.add_argument('--k', type=int, default=2)
    c.add_argument('--workers', type=int, default=4)
    c.add_argument('--limit', type=int, default=0)
    c.add_argument('--force', action='store_true')
    ca = sub.add_parser('cache')
    ca.add_argument('--n', type=int, default=40)
    ca.add_argument('--n-state', type=int, default=15)
    sub.add_parser('score')
    sub.add_parser('cache-report')
    args = ap.parse_args()
    events = rv.load_events()
    ctxs = {label: Ctx(ev) for label, ev in events.items()}
    {'scene': cmd_scene, 'dry-run': cmd_dry, 'call': cmd_call, 'cache': cmd_cache, 'score': cmd_score, 'cache-report': cmd_cache_report}[args.cmd](args, ctxs)


if __name__ == '__main__':
    main()
