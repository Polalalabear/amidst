#!/usr/bin/env python3
"""Vision + graph-prediction Agent offline experiment (issue #640). Run with the repo venv (needs Pillow).

  run_vision_agent.py dry-run  [--k 3] [--models terra,sol] [--arms vision,text]   # estimate only, no network, no key
  run_vision_agent.py oracle                                                       # perfect-agent upper bounds (GT, scoring side)
  run_vision_agent.py call --model terra --arm vision --k 3 [--limit-ticks N]      # PAID, through ApiGuard (caller=vision_agent)
  run_vision_agent.py score                                                        # replay every answer table, both time modes

GT is read only through ``gt_scoring_r004`` (scoring side and the oracle upper bound). The request builder never touches it:
trigger ticks come from the rule display, candidate cameras from the DRAFT graph, appearance from the seed observation.
Outputs: ``local/evidence/vision-agent-<date>/`` (LOCAL, git-ignored).
"""
import argparse
import base64
import concurrent.futures as cf
import dataclasses
import hashlib
import io
import json
import os
import sys
import time
import types
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(REPO / 'scripts'))
from amidst.paths import local_dir  # noqa: E402

os.environ.setdefault('AMIDST_DEMO_HOME', str(local_dir() / 'data/demo-owned-v1'))
# the shared ApiGuard ledger lives in the pinned folder's local/, not in the scratchpad clone
os.environ.setdefault('AMIDST_API_USAGE_DIR', str(local_dir() / 'evidence/api-usage'))
from amidst.evaluation import gt_scoring_r004 as sc  # noqa: E402
from amidst.evaluation import vision_agent as va  # noqa: E402
from amidst.q1q5 import api_budget as ab  # noqa: E402
from amidst.q1q5 import cross_camera_demo as ccd  # noqa: E402
from amidst.q1q5.agent_providers import OPENAI_CHAT_URL, default_http_transport  # noqa: E402
from amidst.q1q5.clock_mapping import ClockMapping  # noqa: E402
from amidst.q1q5.openai_gateway import PRICES  # noqa: E402
from amidst.q1q5.scene_graphs import load_scene_graphs  # noqa: E402

DATE = os.environ.get('VISION_AGENT_DATE', '20261120')
OUT = local_dir() / f'evidence/vision-agent-{DATE}'
MEDIA = local_dir() / 'data/r004-cx7r-20261104-01a19f8b'
API = {'terra': 'gpt-6.1-terra', 'sol': 'gpt-6.1-sol'}
LABELS = {'ctrl-lcorr-s1-a4-5fps-v1-r004-d124-v1': 'A4-1', 'ctrl-lcorr-s1-b4-5fps-v1-r004-d124-v1': 'B4-1'}
BUDGET_USD = 50.0
STOP_USD = 45.0          # stop and report before the D339 limit
IMG_TOKENS_EST = 1300    # conservative per 960x540 image (dry-run only; real usage is logged)
MAX_OUT = 1500
CALLER = 'vision_agent'


# ------------------------------------------------------------------------------------------------ data
def load_events():
    from run_cross_camera_demo import load_run, loads, read_pin
    from demo_dependency_config import configuration, owned_path, resolve_job
    from serve_demo_integration import pinned
    from amidst.q1q5.cross_camera_demo import Parameters
    config, root = configuration(None)
    job = resolve_job(loads(pinned(owned_path(root, config['cross_camera_job']), config['cross_camera_job_sha256'])), root)
    graph = loads(read_pin(job['graph']))
    assert graph == load_scene_graphs('r004').camera
    transitions = {(t['from_camera_id'], t['to_camera_id']): t['transition_id'] for t in graph['transitions']}
    params = Parameters(**job['parameters'])
    events = {}
    for spec in job['runs']:
        tracks, _clock, meta = load_run(spec, graph, job['graph_binding'], params)
        run_id = meta['run_id']
        label = LABELS[run_id]
        dur = ClockMapping(_clock).duration_us
        events[label] = Event(label, run_id, tracks, dur, transitions, params)
    return events


class Event:
    def __init__(self, label, run_id, tracks, dur, transitions, params):
        self.label, self.dur, self.transitions = label, dur, transitions
        self.cams = sorted(sc.cams_of(label))
        d = sc.D / f'demo-owned-v1/data/indexes/{label}'
        meta = json.load(open(d / 'detection_index.json'))
        records = [json.loads(line) for line in open(d / meta['records_ref'])]
        self.index = va.build_index(records)
        self.raw = sc.load_index(label)            # observation_id -> (cam, t, box, class, score) for the GT scorer
        self.gt = sc.gt_traj(label)                # GT: scoring side only
        resp = ccd.response(tracks, transitions, as_of_us=dur, parameters=params, clock_mapping_sha256='vision-agent')[0]
        self.rule_resp = resp
        sel = {}
        for s in resp['sightings']:
            if s.get('selected_for_single_view', True):
                for oid in s['observation_ids']:
                    if oid in self.raw:
                        c, t, b, _k, _s = self.raw[oid]
                        sel.setdefault((c, t), []).append(b)
        self.view = va.rule_view(resp['single_view'], sel, dur)
        self.rule_rows = sc.score(label, resp, self.raw, self.gt, dur)
        first = min((s for s in resp['sightings'] if s.get('selected_for_single_view', True)), key=lambda s: s['range_us'][0])
        oid = first['observation_ids'][0]
        c, t, b, _k, _s = self.raw[oid]
        det = next((x for x in self.index.get((c, t), []) if x.obs_id == oid), None)
        self.seed = {'camera_id': c, 't': t, 'box': b, 'colors': list(det.colors) if det else []}

    def frame_path(self, cam, t):
        return MEDIA / self.label / 'safe/media' / cam / f'{t // va.TICK:06d}.png'

    def body_of(self, cam, t):
        foot = self.gt.get(t)
        return sc.t_body(cam, foot) if foot else None

    def verify_ticks(self):
        """Rule ON_CAMERA ticks whose selected box has score < 0.45 (every 2nd one): the 'gate as information' verification set."""
        sc_by = {}
        for s in self.rule_resp['sightings']:
            if s.get('selected_for_single_view', True):
                for oid in s['observation_ids']:
                    c, t, _b, _k, sco = self.raw[oid]
                    sc_by[(c, t)] = max(sc_by.get((c, t), 0), sco)
        low = [t for t in self.view.ticks if self.view.kind[t] == 'ON_CAMERA' and sc_by.get((self.view.camera[t], t), 1) < 0.45]
        return low[::2]

    def context(self, t, info=False):
        showing = self.view.kind[t] == 'ON_CAMERA'
        if showing:
            cam, last_t = self.view.camera[t], t
        else:
            cam, last_t, _boxes = va.last_known(self.view, t)
        nbrs = va.allowed_cameras(cam, self.transitions, self.cams)
        allowed = sorted(set(self.cams) | {cam}) if info else nbrs
        return {'rule_showing': showing, 'graph_info_only': info, 'rule_scores': None,'t_s': t / 1e6, 'last_camera': cam, 'last_t_s': last_t / 1e6, 'last_t': last_t, 't': t,
                'seed': {'camera_id': self.seed['camera_id'], 't_s': self.seed['t'] / 1e6, 'colors': self.seed['colors']},
                'neighbours': [c for c in nbrs if c != cam], 'allowed': allowed,
                'dets': {c: self.index.get((c, t), []) for c in allowed}}


# ------------------------------------------------------------------------------------------------ images
def _jpeg(im, q=85):
    buf = io.BytesIO()
    im.convert('RGB').save(buf, 'JPEG', quality=q)
    return buf.getvalue()


def build_images(ev: Event, ctx: dict) -> list:
    """[(label, jpeg_bytes)] seed crop, last-known frame with tracker box, then current frames with numbered detection boxes."""
    from PIL import Image, ImageDraw
    out = []
    seed = Image.open(ev.frame_path(ev.seed['camera_id'], ev.seed['t']))
    x0, y0, x1, y1 = ev.seed['box']
    w, h = x1 - x0, y1 - y0
    crop = seed.crop((max(0, x0 - 0.15 * w), max(0, y0 - 0.1 * h), min(seed.width, x1 + 0.15 * w), min(seed.height, y1 + 0.1 * h)))
    out.append(('seed_crop', _jpeg(crop)))
    last = Image.open(ev.frame_path(ctx['last_camera'], ctx['last_t'])).convert('RGB')
    dr = ImageDraw.Draw(last)
    for b in ev.view.boxes[ctx['last_t']]:
        dr.rectangle(b, outline=(0, 255, 0), width=3)
    out.append(('last_known', _jpeg(last)))
    for cam in ctx['allowed']:
        im = Image.open(ev.frame_path(cam, ctx['t'])).convert('RGB')
        dr = ImageDraw.Draw(im)
        for d in ctx['dets'][cam]:
            dr.rectangle(d.box, outline=(255, 220, 0), width=2)
            dr.rectangle((d.box[0], d.box[1], d.box[0] + 26, d.box[1] + 14), fill=(255, 220, 0))
            dr.text((d.box[0] + 3, d.box[1] + 1), d.id, fill=(0, 0, 0))
        dr.rectangle((0, 0, 150, 14), fill=(0, 0, 0))
        dr.text((3, 1), cam, fill=(255, 255, 255))
        out.append((f'cam_{cam}', _jpeg(im)))
    return out


def build_content(ev, ctx, arm):  # noqa: C901
    text = va.request_text(ctx, with_images=(arm == 'vision'))
    content = [{'type': 'text', 'text': text}]
    imgs = build_images(ev, ctx) if arm == 'vision' else []
    for label, jpg in imgs:
        content.append({'type': 'text', 'text': f'[{label}]'})
        content.append({'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(jpg).decode()}})
    return content, text, [(label, hashlib.sha256(j).hexdigest()[:16], len(j)) for label, j in imgs]


# ------------------------------------------------------------------------------------------------ estimate / dry-run
def estimate(ev, t, arm, info=False):
    ctx = ev.context(t, info)
    text = va.request_text(ctx, with_images=(arm == 'vision'))
    n_img = (2 + len(ctx['allowed'])) if arm == 'vision' else 0
    return int(len(va.SYSTEM_PROMPT + text) / 3.2) + n_img * IMG_TOKENS_EST, n_img


def prices():
    return {a: {'input_usd_per_mtok': PRICES[a][0], 'output_usd_per_mtok': PRICES[a][1]} for a in PRICES}


def cmd_dry_run(args, events):
    models = args.models.split(',')
    arms = args.arms.split(',')
    rows, total = [], 0.0
    for m in models:
        for arm in arms:
            calls, tok, worst = 0, 0, 0.0
            for ev in events.values():
                for t in va.trigger_ticks(ev.view):
                    p, _n = estimate(ev, t, arm)
                    calls += args.k
                    tok += p * args.k
                    worst += args.k * ab.estimate_cost(prices(), API[m], p, MAX_OUT)
            typical = tok * PRICES[API[m]][0] / 1e6 + calls * 250 * PRICES[API[m]][1] / 1e6
            rows.append((m, arm, calls, tok, round(typical, 3), round(worst, 3)))
            total += typical
    print('model arm calls est_prompt_tokens typical_usd worst_usd(max_out=%d)' % MAX_OUT)
    for r in rows:
        print(*r)
    print('TOTAL typical USD %.3f ; budget %.0f (stop %.0f)' % (total, BUDGET_USD, STOP_USD))
    for ev in events.values():
        print(ev.label, 'trigger ticks', len(va.trigger_ticks(ev.view)), 'seed', ev.seed)


# ------------------------------------------------------------------------------------------------ paid calls
def ledger_spent(path):
    spent = 0.0
    if path.exists():
        for line in open(path):
            r = json.loads(line)
            if r.get('caller') == CALLER and isinstance(r.get('est_cost_usd'), (int, float)):
                spent += r['est_cost_usd']
    return spent


def make_guard():
    base = ab.GuardConfig.from_env()
    probe = ab.ApiGuard(dataclasses.replace(base, enabled=True))
    existing = sum(r['est_cost_usd'] for r in probe._rows() if isinstance(r.get('est_cost_usd'), (int, float)) and r.get('outcome') != 'DENIED')
    cfg = dataclasses.replace(base, enabled=True, max_usd_total=existing + BUDGET_USD, max_usd_per_day=BUDGET_USD,
                              max_calls_per_day=6000, max_calls_per_min=120, max_usd_per_call=0.05, max_tokens_per_call=20000, prices=prices())
    return ab.ApiGuard(cfg), probe.ledger_path


def post(api_model, content, timeout_s=60):
    key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not key:
        raise PermissionError('NO_API_KEY')
    body = json.dumps({'model': api_model, 'messages': [{'role': 'system', 'content': va.SYSTEM_PROMPT},
                       {'role': 'user', 'content': content}], 'max_completion_tokens': MAX_OUT,
                       'response_format': {'type': 'json_object'}}).encode()
    try:
        _s, raw = default_http_transport(url=OPENAI_CHAT_URL, headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
                                         body=body, timeout_s=timeout_s)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'HTTP_{exc.code}:{exc.read(300)!r}') from None
    data = json.loads(raw)
    ch = data['choices'][0]
    usage = data.get('usage') or {}
    return ch['message'].get('content') or '', ch.get('finish_reason'), usage.get('prompt_tokens'), usage.get('completion_tokens')


def one_call(guard, ev, t, arm, model, info=False):
    ctx = ev.context(t, info)
    content, _text, img_meta = build_content(ev, ctx, arm)
    est_p, _n = estimate(ev, t, arm, info)
    t0 = time.time()
    info = {'t_us': t, 'event': ev.label, 'kind': 'verify' if ctx['rule_showing'] else 'gap', 'group': 'info' if ctx['graph_info_only'] else 'gate', 'images': img_meta, 'allowed': ctx['allowed'], 'error': None}
    for attempt in (1, 2):                       # one retry on transport errors only
        try:
            t0 = time.time()
            out = guard.run(CALLER, API[model], est_p, MAX_OUT, lambda: _unpack(post(API[model], content)))
            lat = time.time() - t0
            if not out.allowed:
                info.update(error='GUARD_DENIED:' + str(out.reason), latency_s=0.0)
                return info
            text, finish, pt, ct = out.value
            info.update(latency_s=round(lat, 3), finish=finish, prompt_tokens=pt, completion_tokens=ct, cost_usd=out.cost_usd if hasattr(out, 'cost_usd') else None,
                        raw=text, attempts=attempt)
            ans, err = va.parse_answer(text, ctx['allowed'], ctx['dets']) if finish == 'stop' else (None, 'FINISH_' + str(finish))
            info.update(answer=ans, error=err)
            return info
        except Exception as exc:  # noqa: BLE001
            info.update(error=f'{type(exc).__name__}:{str(exc)[:200]}', latency_s=round(time.time() - t0, 3), attempts=attempt)
    return info


def _unpack(r):
    text, finish, pt, ct = r
    return (text, finish, pt, ct), pt, ct


def cmd_call(args, events):
    guard, ledger = make_guard()
    OUT.mkdir(parents=True, exist_ok=True)
    info = args.group == 'info'
    pre = 'info_' if info else ''
    jobs = [(ev, t) for ev in events.values() for t in sorted(set(va.trigger_ticks(ev.view)) | (set(ev.verify_ticks()) if info else set()))][: args.limit_ticks or None]
    for k in range(args.k):
        path = OUT / f'{pre}answers_{args.model}_{args.arm}_k{k}.json'
        if path.exists() and not args.force:
            print('skip existing', path.name)
            continue
        spent = ledger_spent(ledger)
        if spent >= STOP_USD:
            print(f'STOP: vision_agent spend {spent:.3f} >= {STOP_USD}')
            return
        t0 = time.time()
        with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
            res = list(pool.map(lambda j: one_call(guard, j[0], j[1], args.arm, args.model, info), jobs))
        path.write_text(json.dumps({'model': args.model, 'api_model': API[args.model], 'arm': args.arm, 'group': args.group, 'k': k, 'wall_s': round(time.time() - t0, 1),
                                    'answers': res}, ensure_ascii=False, indent=1))
        err = sum(1 for r in res if r.get('error'))
        print(f'{path.name}: {len(res)} calls, errors {err}, wall {time.time() - t0:.0f}s, vision_agent spend so far {ledger_spent(ledger):.4f}', flush=True)


# ------------------------------------------------------------------------------------------------ oracle / score
def oracle_agent(ev, scope, latency_s=0.0):
    """Perfect agent (GT on the scoring side): any indexed person box whose centre is on the GT body in the allowed cameras."""
    def agent(t):
        cams = ev.cams if scope.endswith('all') else ev.context(t)['allowed']
        for cam in cams:
            body = ev.body_of(cam, t)
            if body is None:
                continue
            if scope.startswith('own'):     # perfect own box: the GT body clipped to the image (needs T inside the frame and detected by anything)
                cm = sc.CAMS[cam]
                box = [max(0.0, body[0]), max(0.0, body[1]), min(float(cm['width']), body[2]), min(float(cm['height']), body[3])]
                row = ev.rule_rows[t // va.TICK]
                if cam in row['t_visible'] and box[2] > box[0] and box[3] > box[1]:
                    return {'present': True, 'camera_id': cam, 'detection_id': None, 'box_xyxy': box, 'latency_s': latency_s}
                continue
            for d in ev.index.get((cam, t), []):
                if va.center_in(d.box, body, 0.0):
                    return {'present': True, 'camera_id': cam, 'detection_id': d.id, 'box_xyxy': None, 'latency_s': latency_s}
        return {'present': False, 'camera_id': None, 'detection_id': None, 'box_xyxy': None, 'latency_s': latency_s}
    return agent


def table_agent(rec, ev):
    by_t = {a['t_us']: a for a in rec['answers'] if a['event'] == ev.label}

    def agent(t):
        a = by_t.get(t)
        if a is None or not a.get('answer'):
            return None if a is None or a.get('error') else None
        return dict(a['answer'], latency_s=a.get('latency_s', 0.0))
    return agent


def evaluate(ev, agent, mode):
    if agent is None:
        rows = [dict(r, src='RULE') for r in ev.rule_rows]
        displays, calls = {}, []
    else:
        displays, calls = va.replay(ev.view, ev.index, agent, mode)
        rows = va.overlay(ev.rule_rows, displays, ev.body_of)
    m = sc.metrics(rows)
    m.update(va.episode_stats(ev.view, ev.rule_rows, rows))
    m['agent_calls'] = len(calls)
    m['agent_shown_s'] = round(sum(r.get('src') == 'AGENT' for r in rows) * va.TICK / 1e6, 1)
    return m, rows, calls


def cmd_oracle(args, events):
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    for label, ev in events.items():
        res[label] = {'rule': evaluate(ev, None, 'offline')[0]}
        for scope in ('all', 'graph', 'own_all', 'own_graph'):
            for lat in (0.0, 2.0, 4.0):
                mode = 'offline' if lat == 0 else 'realtime'
                res[label][f'oracle_{scope}_lat{lat:g}'] = evaluate(ev, oracle_agent(ev, scope, lat), mode)[0]
    (OUT / 'oracle.json').write_text(json.dumps(res, indent=1))
    for label, r in res.items():
        print(label)
        for k, m in r.items():
            print(f'  {k:24s} follow {m["follow_rate"]} lost_s {m["lost_s_while_visible"]} wrong_s {m["wrong_total_s"]} comb_lost_s {m.get("combined_lost_s_while_visible")} early_s {m.get("early_reconnect_s_total")} wrongconn {m.get("wrong_connections")}')


def recognition(ev, rec):
    """Per-tick recognition: Agent answer vs rule display (RT-DETR index + rule), GT on the scoring side only.
    Positive = the target is detectable (by anything, D325 criterion) in a candidate camera at that tick."""
    by_t = {a['t_us']: a for a in rec['answers'] if a['event'] == ev.label}
    ans = table_agent(rec, ev)
    acc = {}
    def bump(key, name):
        acc.setdefault(key, {}).setdefault(name, 0)
        acc[key][name] += 1
    for t, a in sorted(by_t.items()):
        row = ev.rule_rows[t // va.TICK]
        cams = ev.cams if rec.get('group') == 'info' else ev.context(t)['allowed']
        pos = [c for c in cams if c in row['t_visible'] and ev.body_of(c, t) is not None]
        best = max((d.score for c in cams if ev.body_of(c, t) for d in ev.index.get((c, t), []) if va.center_in(d.box, ev.body_of(c, t), 0.0)), default=None)
        stratum = 'no_person_box' if best is None else ('score<0.45' if best < 0.45 else 'score>=0.45')
        kind = a.get('kind', 'gap')
        res = va.resolve(ans(t), t, ev.index)
        a_ok = False
        if res:
            body = ev.body_of(res[1], t)
            box = res[2].box if res[0] == 'SNAP' else res[2]
            a_ok = body is not None and (va.center_in(box, body, 0.0) or va.iou(box, body) >= va.OWN_IOU)
        r_pred = ev.view.kind[t] == 'ON_CAMERA'
        r_ok = r_pred and ev.body_of(ev.view.camera[t], t) is not None and any(va.center_in(b, ev.body_of(ev.view.camera[t], t), 0.0) for b in ev.view.boxes[t])
        for who, pred, ok in (('agent', bool(res), a_ok), ('rule', r_pred, r_ok)):
            for key in ('all', kind, stratum if pos else 'target_absent'):
                bump((who, key), 'ticks')
                if ok:
                    bump((who, key), 'TP')
                elif pred:
                    bump((who, key), 'FP')
                if pos and not ok:
                    bump((who, key), 'FN')
        for key in ('all', kind):
            if a_ok and not r_ok:
                bump(('cmp', key), 'agent_right_rule_wrong')
            elif r_ok and not a_ok:
                bump(('cmp', key), 'rule_right_agent_wrong')
            elif a_ok and r_ok:
                bump(('cmp', key), 'both_right')
            elif pos:
                bump(('cmp', key), 'both_wrong_target_present')
    out = {}
    for (who, key), c in acc.items():
        tp, fp, fn = c.get('TP', 0), c.get('FP', 0), c.get('FN', 0)
        c = dict(c)
        if who != 'cmp':
            c['precision'] = round(tp / (tp + fp), 3) if tp + fp else None
            c['recall'] = round(tp / (tp + fn), 3) if tp + fn else None
        out[f'{who}/{key}'] = c
    return out


def cmd_score(args, events):
    out, rec_out = {}, {}
    files = sorted(OUT.glob('answers_*_k*.json')) + sorted(OUT.glob('info_answers_*_k*.json'))
    for f in files:
        rec = json.loads(f.read_text())
        key = ('info_' if f.name.startswith('info_') else '') + f'{rec["model"]}_{rec["arm"]}'
        for label, ev in events.items():
            for mode in va.MODES:
                m, rows, calls = evaluate(ev, table_agent(rec, ev), mode)
                out.setdefault(key, {}).setdefault(label, {}).setdefault(mode, []).append(
                    {'k': rec['k'], 'metrics': m, 'switch_rows': [{'t_s': r['t_us'] / 1e6, 'camera': r['camera'], 'cls': r['cls']} for r in rows if r.get('src') == 'AGENT']})
            rec_out.setdefault(key, {}).setdefault(label, []).append({'k': rec['k'], 'recognition': recognition(ev, rec)})
    (OUT / 'scores.json').write_text(json.dumps(out, indent=1))
    (OUT / 'recognition.json').write_text(json.dumps(rec_out, indent=1))
    print('wrote', OUT / 'scores.json', 'and recognition.json from', len(files), 'answer tables')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('dry-run')
    d.add_argument('--k', type=int, default=3)
    d.add_argument('--models', default='terra,sol')
    d.add_argument('--arms', default='vision,text')
    sub.add_parser('oracle')
    c = sub.add_parser('call')
    c.add_argument('--model', choices=list(API), required=True)
    c.add_argument('--arm', choices=('vision', 'text'), required=True)
    c.add_argument('--k', type=int, default=3)
    c.add_argument('--workers', type=int, default=4)
    c.add_argument('--limit-ticks', type=int, default=0)
    c.add_argument('--force', action='store_true')
    c.add_argument('--group', choices=('gate', 'info'), default='gate')
    sub.add_parser('score')
    args = ap.parse_args()
    events = load_events()
    {'dry-run': cmd_dry_run, 'oracle': cmd_oracle, 'call': cmd_call, 'score': cmd_score}[args.cmd](args, events)


if __name__ == '__main__':
    main()
