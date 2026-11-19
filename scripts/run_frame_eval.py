#!/usr/bin/env python3
"""W1 (#644) per-frame evaluation, Agent (sees image) vs RT-DETR+HSV rule. Run with the repo venv (needs Pillow, matplotlib).

  run_frame_eval.py frames                      # build the GT-stratified frame table + sample (no network)
  run_frame_eval.py dry-run [--k 3]             # cost estimate only
  run_frame_eval.py call --model terra --arm vision_free|text|vision_pick --k 3        # PAID, through ApiGuard (caller=frame_eval)
  run_frame_eval.py score                       # metrics, paired bootstrap, chart, tables
Outputs: local/evidence/w1-frame-eval-<date>/ (LOCAL, git-ignored). GT is read only by the scoring side (frames table labels, score).
"""
import argparse
import base64
import concurrent.futures as cf
import dataclasses
import hashlib
import io
import json
import os
import random
import sys
import time
import urllib.error

import numpy as np
from PIL import Image
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(REPO / 'scripts'))
from amidst.paths import local_dir  # noqa: E402

os.environ.setdefault('AMIDST_DEMO_HOME', str(local_dir() / 'data/demo-owned-v1'))
os.environ.setdefault('AMIDST_API_USAGE_DIR', str(local_dir() / 'evidence/api-usage'))
from amidst.evaluation import frame_eval as fe  # noqa: E402
from amidst.evaluation import gt_scoring_r004 as sc  # noqa: E402
from amidst.q1q5 import api_budget as ab  # noqa: E402
from amidst.q1q5.agent_providers import OPENAI_CHAT_URL, default_http_transport  # noqa: E402
from amidst.q1q5.openai_gateway import PRICES  # noqa: E402

DATE = os.environ.get('W1_DATE', '20261120')
OUT = local_dir() / f'evidence/w1-frame-eval-{DATE}'
MEDIA = local_dir() / 'data/r004-cx7r-20261104-01a19f8b'
API = {'terra': 'gpt-6.1-terra', 'sol': 'gpt-6.1-sol'}
LABELS = ('A4-1', 'B4-1')
PER_STRATUM = 60
MIN_GAP_S = 0.4
BUDGET_USD = 50.0
STOP_USD = 45.0
IMG_TOKENS_EST = 1300
MAX_OUT = 600
CALLER = 'frame_eval'
SEED_CACHE = OUT / 'seeds.json'


# --------------------------------------------------------------------------------------------- data
def seeds():
    """Seed crop box / camera / time / colours per event = the rule's first lock (system observation), cached."""
    if SEED_CACHE.exists():
        return json.loads(SEED_CACHE.read_text())
    import run_vision_agent as rva
    out = {}
    for label, ev in rva.load_events().items():
        out[label] = {'camera_id': ev.seed['camera_id'], 't': ev.seed['t'], 'box': list(ev.seed['box']), 'colors': ev.seed['colors'],
                      'neighbours': {c: sorted({b for (a, b) in ev.transitions if a == c} | {a for (a, b) in ev.transitions if b == c})
                                     for c in ev.cams}, 'cams': ev.cams}
    OUT.mkdir(parents=True, exist_ok=True)
    SEED_CACHE.write_text(json.dumps(out, indent=1))
    return out


def load_dets(label):
    d = sc.D / f'demo-owned-v1/data/indexes/{label}'
    meta = json.load(open(d / 'detection_index.json'))
    out = {}
    for line in open(d / meta['records_ref']):
        r = json.loads(line)
        dets = sorted(r['detections'] or [], key=lambda x: x['observation_id'])
        out[(r['camera_id'], r['timestamp_us'])] = [
            {'id': f'D{i + 1}', 'obs_id': x['observation_id'], 'box': list(x['bbox_xyxy_px']), 'score': x['score'], 'cls': x['class_label'],
             'verdict_red': ((x.get('color') or {}).get('verdicts') or {}).get('red'),
             'colors': sorted(k for k, v in ((x.get('color') or {}).get('verdicts') or {}).items() if v in ('STRONG', 'WEAK'))}
            for i, x in enumerate(dets)]
    return out


def frame_path(label, cam, t):
    return MEDIA / label / 'safe/media' / cam / f'{t // 200000:06d}.png'


def cmd_frames(args):
    sd = seeds()
    rows = []
    for label in LABELS:
        gt = sc.gt_traj(label)
        dets = load_dets(label)
        for (cam, t), ds in sorted(dets.items()):
            foot = gt.get(t)
            body = sc.t_body(cam, foot) if foot else None
            cm = sc.CAMS[cam]
            red = (0, 0.0)
            if body and fe.inside_fraction(body, cm['width'], cm['height']) >= 0.5:
                x0, y0, x1, y1 = [int(round(v)) for v in body]
                x0, y0, x1, y1 = max(0, x0), max(0, y0), min(cm['width'], x1), min(cm['height'], y1)
                if x1 > x0 and y1 > y0:
                    hsv = np.asarray(Image.open(frame_path(label, cam, t)).convert('HSV'), dtype=np.int32)[y0:y1, x0:x1]
                    red = fe.red_pixels(hsv)
            lab = fe.frame_labels(ds, body, cm['width'], cm['height'], *red)
            rows.append({'event': label, 'camera': cam, 't_us': t, 'body': body, 'lab': lab, 'dets': ds})
    pres = sorted(r['lab']['body_h_px'] for r in rows if r['lab']['present'])
    terc = (pres[len(pres) // 3], pres[2 * len(pres) // 3])
    for r in rows:
        r['strata'] = fe.strata_of(r['lab'], terc)
    rng = random.Random(644)
    by_stratum = {}
    for name in ['easy_visible', 'partial_occluded', 'partial_edge', 'far_small', 'lowscore_person', 'nonperson_class', 'visible_nobox', 'pos_with_similar', 'neg_absent', 'neg_occluded', 'neg_with_similar']:
        cand = [i for i, r in enumerate(rows) if name in r['strata']]
        rng.shuffle(cand)
        pick = []
        for i in cand:
            if all(not (rows[i]['event'] == rows[j]['event'] and rows[i]['camera'] == rows[j]['camera']
                        and abs(rows[i]['t_us'] - rows[j]['t_us']) < MIN_GAP_S * 1e6) for j in pick):
                pick.append(i)
            if len(pick) >= PER_STRATUM:
                break
        by_stratum[name] = {'available': len(cand), 'sampled': pick, 'n_after_gap': len(pick)}
    print('body_h terciles (px):', terc)
    for k, v in by_stratum.items():
        print(f'{k:18s} available {v["available"]:5d} sampled {v["n_after_gap"]}')
    OUT.mkdir(parents=True, exist_ok=True)
    union = sorted({i for v in by_stratum.values() for i in v['sampled']})
    sample = [{'idx': i, **{k: rows[i][k] for k in ('event', 'camera', 't_us', 'body', 'lab', 'strata')}} for i in union]
    (OUT / 'frames_all_labels.json').write_text(json.dumps([{k: r[k] for k in ('event', 'camera', 't_us', 'lab', 'strata')} for r in rows]))
    (OUT / 'sample.json').write_text(json.dumps({'tercile_body_h_px': terc, 'per_stratum': {k: {'available': v['available'], 'frames': [(rows[i]['event'], rows[i]['camera'], rows[i]['t_us']) for i in v['sampled']]} for k, v in by_stratum.items()},
                                                 'frames': [{k: s[k] for k in ('event', 'camera', 't_us', 'strata')} for s in sample]}, indent=1))
    print('union frames', len(union))


# --------------------------------------------------------------------------------------------- requests
def load_sample():
    return json.loads((OUT / 'sample.json').read_text())


def _jpeg(im, q=85):
    buf = io.BytesIO()
    im.convert('RGB').save(buf, 'JPEG', quality=q)
    return buf.getvalue()


def seed_crop(label, sd):
    from PIL import Image
    im = Image.open(frame_path(label, sd['camera_id'], sd['t']))
    x0, y0, x1, y1 = sd['box']
    w, h = x1 - x0, y1 - y0
    return _jpeg(im.crop((max(0, x0 - 0.15 * w), max(0, y0 - 0.1 * h), min(im.width, x1 + 0.15 * w), min(im.height, y1 + 0.1 * h))))


def frame_image(label, cam, t, dets):
    from PIL import Image, ImageDraw
    im = Image.open(frame_path(label, cam, t)).convert('RGB')
    dr = ImageDraw.Draw(im)
    for d in dets:
        b = d['box']
        dr.rectangle(b, outline=(255, 220, 0), width=2)
        dr.rectangle((b[0], b[1], b[0] + 26, b[1] + 14), fill=(255, 220, 0))
        dr.text((b[0] + 3, b[1] + 1), d['id'], fill=(0, 0, 0))
    dr.rectangle((0, 0, 150, 14), fill=(0, 0, 0))
    dr.text((3, 1), cam, fill=(255, 255, 255))
    return _jpeg(im)


def build_messages(label, cam, t, arm, sd, dets_by_frame, crops):
    dets = dets_by_frame[label][(cam, t)]
    ctx = fe.scene_context(label, sd[label]['cams'], sd[label]['neighbours'], sd[label]['colors'])
    system = fe.SYSTEM_PREFIX + (fe.SYSTEM_PICK_SUFFIX if arm == 'vision_pick' else '') + (fe.SYSTEM_TEXT_SUFFIX if arm == 'text' else '') + '\n\n' + ctx
    text = fe.request_text(cam, t / 1e6, dets, arm)
    content = [{'type': 'text', 'text': text}]
    if arm != 'text':
        for lab, jpg in (('reference_crop', crops[label]), ('current_frame', frame_image(label, cam, t, dets))):
            content.append({'type': 'text', 'text': f'[{lab}]'})
            content.append({'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(jpg).decode()}})
    return system, content, dets


def prices():
    return {a: {'input_usd_per_mtok': PRICES[a][0], 'output_usd_per_mtok': PRICES[a][1]} for a in PRICES}


def est_tokens(system, text, arm):
    return int(len(system + text) / 3.2) + (0 if arm == 'text' else 2 * IMG_TOKENS_EST)


def cmd_dry_run(args):
    sd, smp = seeds(), load_sample()
    dets = {l: load_dets(l) for l in LABELS}
    crops = {l: seed_crop(l, sd[l]) for l in LABELS}
    tot = 0.0
    for m in args.models.split(','):
        for arm in args.arms.split(','):
            tok = 0
            for f in smp['frames']:
                system, content, _ = build_messages(f['event'], f['camera'], f['t_us'], arm, sd, dets, crops)
                tok += est_tokens(system, content[0]['text'], arm)
            usd = args.k * (tok * PRICES[API[m]][0] + len(smp['frames']) * 120 * PRICES[API[m]][1]) / 1e6
            tot += usd
            print(f'{m} {arm}: frames {len(smp["frames"])} k {args.k} est_prompt_tokens/call {tok // len(smp["frames"])} typical_usd {usd:.3f}')
    print(f'TOTAL typical USD {tot:.3f}')


# --------------------------------------------------------------------------------------------- calls
def make_guard():
    base = ab.GuardConfig.from_env()
    probe = ab.ApiGuard(dataclasses.replace(base, enabled=True))
    existing = sum(r['est_cost_usd'] for r in probe._rows() if isinstance(r.get('est_cost_usd'), (int, float)) and r.get('outcome') != 'DENIED')
    cfg = dataclasses.replace(base, enabled=True, max_usd_total=existing + BUDGET_USD, max_usd_per_day=BUDGET_USD, max_calls_per_day=6000,
                              max_calls_per_min=120, max_usd_per_call=0.05, max_tokens_per_call=20000, prices=prices())
    return ab.ApiGuard(cfg), probe.ledger_path


def ledger_spent(path):
    s = 0.0
    if path.exists():
        for line in open(path):
            r = json.loads(line)
            if r.get('caller') == CALLER and isinstance(r.get('est_cost_usd'), (int, float)):
                s += r['est_cost_usd']
    return s


def post(api_model, system, content, timeout_s=90):
    key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not key:
        raise PermissionError('NO_API_KEY')
    body = json.dumps({'model': api_model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': content}],
                       'max_completion_tokens': MAX_OUT, 'response_format': {'type': 'json_object'}}).encode()
    try:
        _s, raw = default_http_transport(url=OPENAI_CHAT_URL, headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
                                         body=body, timeout_s=timeout_s)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'HTTP_{exc.code}:{exc.read(300)!r}') from None
    data = json.loads(raw)
    ch = data['choices'][0]
    u = data.get('usage') or {}
    cached = ((u.get('prompt_tokens_details') or {}).get('cached_tokens'))
    return ch['message'].get('content') or '', ch.get('finish_reason'), u.get('prompt_tokens'), u.get('completion_tokens'), cached


def one_call(guard, f, arm, model, sd, dets, crops):
    system, content, ds = build_messages(f['event'], f['camera'], f['t_us'], arm, sd, dets, crops)
    est_p = est_tokens(system, content[0]['text'], arm)
    rec = {'event': f['event'], 'camera': f['camera'], 't_us': f['t_us'], 'error': None, 'system_sha': hashlib.sha256(system.encode()).hexdigest()[:12]}
    for attempt in (1, 2):
        try:
            t0 = time.time()
            out = guard.run(CALLER, API[model], est_p, MAX_OUT, lambda: ((r := post(API[model], system, content)), r[2], r[3]))
            lat = time.time() - t0
            if not out.allowed:
                rec.update(error='GUARD_DENIED:' + str(out.reason))
                return rec
            text, finish, pt, ct, cached = out.value
            ans, err = fe.parse_answer(text, {d['id'] for d in ds}, arm != 'vision_pick') if finish == 'stop' else (None, 'FINISH_' + str(finish))
            rec.update(latency_s=round(lat, 3), finish=finish, prompt_tokens=pt, completion_tokens=ct, cached_tokens=cached, raw=text, answer=ans,
                       error=err, attempts=attempt)
            return rec
        except Exception as exc:  # noqa: BLE001
            rec.update(error=f'{type(exc).__name__}:{str(exc)[:200]}', attempts=attempt)
    return rec


def cmd_call(args):
    sd, smp = seeds(), load_sample()
    dets = {l: load_dets(l) for l in LABELS}
    crops = {l: seed_crop(l, sd[l]) for l in LABELS}
    guard, ledger = make_guard()
    frames = smp['frames'][: args.limit or None]
    for k in range(args.k):
        path = OUT / f'answers_{args.model}_{args.arm}_k{k}.json'
        if path.exists() and not args.force:
            print('skip', path.name)
            continue
        if ledger_spent(ledger) >= STOP_USD:
            print('STOP: spend limit')
            return
        t0 = time.time()
        with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
            res = list(pool.map(lambda f: one_call(guard, f, args.arm, args.model, sd, dets, crops), frames))
        path.write_text(json.dumps({'model': args.model, 'api_model': API[args.model], 'arm': args.arm, 'k': k, 'wall_s': round(time.time() - t0, 1), 'answers': res}, indent=1))
        print(f'{path.name}: {len(res)} calls, errors {sum(1 for r in res if r.get("error"))}, wall {time.time() - t0:.0f}s, frame_eval spend {ledger_spent(ledger):.4f}', flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('frames')
    d = sub.add_parser('dry-run')
    d.add_argument('--k', type=int, default=3)
    d.add_argument('--models', default='terra')
    d.add_argument('--arms', default='vision_free,text,vision_pick')
    c = sub.add_parser('call')
    c.add_argument('--model', choices=list(API), required=True)
    c.add_argument('--arm', choices=fe.LLM_ARMS, required=True)
    c.add_argument('--k', type=int, default=3)
    c.add_argument('--workers', type=int, default=4)
    c.add_argument('--limit', type=int, default=0)
    c.add_argument('--force', action='store_true')
    sub.add_parser('score')
    args = ap.parse_args()
    {'frames': cmd_frames, 'dry-run': cmd_dry_run, 'call': cmd_call, 'score': lambda a: __import__('frame_eval_score').main()}[args.cmd](args)


if __name__ == '__main__':
    main()
