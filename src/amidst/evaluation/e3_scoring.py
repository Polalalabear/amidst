"""E3 unified GT scorer (F1, issue #660): one judgement for every displayed box, two criteria, four error classes.

Pure functions, no file or network I/O. Ground Truth (the target's projected body box, the cameras where the target is visible,
world positions of actors) is handed in by the caller on the scoring side only; nothing under ``src/amidst/q1q5`` or
``src/amidst/live_mode`` may import this module (``tests/evaluation/test_e3_scoring.py`` checks it). The preregistration that
fixes these definitions before E3 runs is ``docs/evaluation/E3_PREREGISTRATION_20261122.md``.

Definitions (frozen by the preregistration):

* **Box judgement** (:func:`judge_box`): the same function for rule boxes, indexed detections chosen by the Agent and boxes the
  Agent drew itself. The GT body box is clipped to the image first. ``primary`` = box centre inside the body box OR IoU >= 0.3
  (the W1 definition); ``iou`` = IoU >= 0.3. ``iou`` hits are a subset of ``primary`` hits.
* **Tick classes** (:func:`classify`), denominator = ticks where the target is GT-visible in at least one camera:
  ``CORRECT``; ``MISLOCALIZED`` (right camera, box centre on the target but IoU < 0.3: only possible under ``iou``);
  ``WRONG_PERSON`` (right camera, box not on the target); ``WRONG_CAMERA`` (shown camera does not see the target, another camera
  does); ``LOST`` (nothing shown while the target is visible). Outside the denominator: ``FALSE_LOCK`` (something shown, target
  visible nowhere), ``BLIND_OK`` (nothing shown, target visible nowhere) and ``BLIND_HOLD`` (camera-only hold through a detector
  flicker while the target is visible nowhere; neither an error nor counted).
* **Camera-only display** (no box at that tick, e.g. the rule holding a camera through a one-tick detection flicker): judged at
  camera level; the caller sets ``hold_ok`` when the target is visible in that camera within +-0.6 s (the D325 hold rule).
* **Positional display** (LIVE, no box): ``CORRECT`` when the estimate is within 1.5 m of the target, ``WRONG_PERSON`` when it is
  within 1.5 m of another actor instead, otherwise ``MISLOCALIZED``; the ``iou`` criterion is ``None`` (not available) for it.

Identity stays UNCONFIRMED: ``CORRECT`` means the shown box/estimate lies on the GT target, not that identity was established.
"""
from __future__ import annotations

import math
import random
import statistics
from collections import Counter
from dataclasses import dataclass, field

SCHEMA = 'e3.score.v1'
TICK_US = 200_000
IOU_HIT = 0.3
POS_HIT_M = 1.5
HOLD_US = 600_000
CRITERIA = ('primary', 'iou')
VISIBLE_CLASSES = ('CORRECT', 'MISLOCALIZED', 'WRONG_PERSON', 'WRONG_CAMERA', 'LOST')
ERROR_CLASSES = ('WRONG_PERSON', 'MISLOCALIZED', 'LOST', 'WRONG_CAMERA')
BLIND_CLASSES = ('FALSE_LOCK', 'BLIND_OK', 'BLIND_HOLD')


# --------------------------------------------------------------------------------------------- box judgement
def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def center_in(box, body) -> bool:
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return body[0] <= cx <= body[2] and body[1] <= cy <= body[3]


def clip_box(body, size):
    """Body box clipped to the image ``size=(w, h)``; None when nothing is left."""
    if size is None:
        return tuple(body)
    b = (max(0.0, body[0]), max(0.0, body[1]), min(float(size[0]), body[2]), min(float(size[1]), body[3]))
    return b if b[2] > b[0] and b[3] > b[1] else None


def judge_box(box, body, size=None) -> dict:
    """The single box judgement. ``body`` = GT target body box in that camera (scoring side) or None."""
    b = clip_box(body, size) if body is not None else None
    if b is None or box is None:
        return {'center_in': False, 'iou': 0.0, 'primary': False, 'iou_hit': False}
    v = iou(box, b)
    c = center_in(box, b)
    return {'center_in': c, 'iou': round(v, 4), 'primary': c or v >= IOU_HIT, 'iou_hit': v >= IOU_HIT}


# --------------------------------------------------------------------------------------------- per-tick rows
@dataclass(frozen=True)
class Tick:
    """One scored tick. Display fields are system output; ``visible``/``body``/``pos_*``/``hold_ok`` are GT-side annotations."""
    t_us: int
    shown_camera: str | None            # camera the display shows, None = nothing shown (GAP / LOST / hidden)
    boxes: tuple = ()                   # boxes shown on that camera at this tick ((x0,y0,x1,y1), ...); empty = camera-only
    visible: frozenset = frozenset()    # GT: cameras where the target is visible at this tick
    body: tuple | None = None           # GT: target body box in the shown camera (pixels) or None
    size: tuple | None = None           # image size of the shown camera
    hold_ok: bool = False               # GT: camera-only display and the target is visible in that camera within +-0.6 s
    pos_hit: bool | None = None         # GT: LIVE estimate within 1.5 m of the target (None = not positional)
    pos_other: bool | None = None       # GT: LIVE estimate within 1.5 m of another actor
    src: str = 'RULE'                   # who produced the display (RULE / AGENT / AGENT_OWN / ...), for breakdowns only
    extra: dict = field(default_factory=dict, compare=False)


def box_judgements(tick: Tick) -> list:
    return [judge_box(b, tick.body, tick.size) for b in tick.boxes]


def classify(tick: Tick, criterion: str = 'primary'):
    """Class of one tick under ``criterion`` ('primary' | 'iou'); None when the criterion is not available (positional, iou)."""
    if criterion not in CRITERIA:
        raise ValueError('CRITERION_INVALID')
    cam = tick.shown_camera
    if cam is None:
        return 'LOST' if tick.visible else 'BLIND_OK'
    if not tick.visible:
        return 'BLIND_HOLD' if (not tick.boxes and tick.pos_hit is None and tick.hold_ok) else 'FALSE_LOCK'
    if tick.boxes:
        if cam not in tick.visible:
            return 'WRONG_CAMERA'
        js = box_judgements(tick)
        if any(j['iou_hit'] for j in js):
            return 'CORRECT'
        if any(j['primary'] for j in js):
            return 'CORRECT' if criterion == 'primary' else 'MISLOCALIZED'
        return 'WRONG_PERSON'
    if tick.pos_hit is not None:                       # LIVE positional display without a box
        if criterion == 'iou':
            return None
        if cam not in tick.visible and not tick.pos_hit:
            return 'WRONG_CAMERA'
        if tick.pos_hit:
            return 'CORRECT'
        return 'WRONG_PERSON' if tick.pos_other else 'MISLOCALIZED'
    # camera-only display (no box this tick): camera-level judgement with the +-0.6 s hold rule
    if cam in tick.visible or tick.hold_ok:
        return 'CORRECT'
    return 'WRONG_CAMERA'


# --------------------------------------------------------------------------------------------- metrics
def _pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def reacquire_episodes(ticks, classes, tick_us=TICK_US) -> list:
    """Episodes of not-CORRECT GT-visible ticks (blind ticks are skipped, they neither end nor extend an episode).
    latency = GT-visible seconds from the first tick of the episode to the next CORRECT tick; censored when the event ends first."""
    eps, cur = [], None
    for t, c in zip(ticks, classes):
        if c not in VISIBLE_CLASSES:
            continue
        if c == 'CORRECT':
            if cur is not None:
                eps.append(dict(cur, end_t_s=t.t_us / 1e6, censored=False))
                cur = None
        else:
            if cur is None:
                cur = {'start_t_s': t.t_us / 1e6, 'visible_ticks': 0, 'classes': Counter()}
            cur['visible_ticks'] += 1
            cur['classes'][c] += 1
    if cur is not None:
        eps.append(dict(cur, end_t_s=None, censored=True))
    for e in eps:
        e['latency_s'] = round(e['visible_ticks'] * tick_us / 1e6, 3)
        e['classes'] = dict(e['classes'])
    return eps


def metrics(ticks, criterion: str = 'primary', tick_us: int = TICK_US) -> dict:
    """All per-event tracking metrics under one criterion. Denominator = GT-visible ticks."""
    ticks = sorted(ticks, key=lambda t: t.t_us)
    classes = [classify(t, criterion) for t in ticks]
    sec = tick_us / 1e6
    if any(c is None for c in classes):
        return {'criterion': criterion, 'available': False, 'reason': 'NO_BOX_FOR_IOU', 'ticks': len(ticks)}
    cnt = Counter(classes)
    nv = sum(cnt[c] for c in VISIBLE_CLASSES)
    rate = (lambda c: round(cnt[c] / nv, 4) if nv else None)
    eps = reacquire_episodes(ticks, classes, tick_us)
    done = [e['latency_s'] for e in eps if not e['censored']]
    ious = []
    for t in ticks:
        if t.shown_camera is not None and t.boxes and t.shown_camera in t.visible:
            ious.append(max(j['iou'] for j in box_judgements(t)))
    wrong_eps, prev = 0, False
    for c in classes:
        cur = c in ('WRONG_PERSON', 'WRONG_CAMERA')
        wrong_eps += cur and not prev
        prev = cur
    by_src = {}
    for t, c in zip(ticks, classes):
        if t.shown_camera is not None:
            by_src.setdefault(t.src, Counter())[c] += 1
    return {
        'criterion': criterion, 'available': True, 'ticks': len(ticks), 'tick_s': sec,
        'visible_ticks': nv, 'visible_s': round(nv * sec, 3),
        'follow_rate': rate('CORRECT'),
        'error_share': {c: rate(c) for c in ERROR_CLASSES},
        'wrong_person_s': round((cnt['WRONG_PERSON'] + cnt['WRONG_CAMERA']) * sec, 3),
        'wrong_person_only_s': round(cnt['WRONG_PERSON'] * sec, 3),
        'wrong_camera_s': round(cnt['WRONG_CAMERA'] * sec, 3),
        'mislocalized_s': round(cnt['MISLOCALIZED'] * sec, 3),
        'lost_s': round(cnt['LOST'] * sec, 3),
        'false_lock_s': round(cnt['FALSE_LOCK'] * sec, 3),
        'wrong_person_episodes': wrong_eps,
        'reacquire': {'episodes': len(eps), 'censored': sum(e['censored'] for e in eps),
                      'median_s': _pct(done, .5), 'p90_s': _pct(done, .9),
                      'mean_s': round(statistics.mean(done), 3) if done else None},
        'box_iou': {'n': len(ious), 'mean': round(statistics.mean(ious), 4) if ious else None,
                    'median': _pct(ious, .5)},
        'counts': {c: cnt[c] for c in VISIBLE_CLASSES + BLIND_CLASSES},
        'counts_by_src': {s: dict(v) for s, v in sorted(by_src.items())},
    }


def score_event(ticks, tick_us: int = TICK_US) -> dict:
    """Both criteria for one event/run."""
    return {'schema_version': SCHEMA, 'primary': metrics(ticks, 'primary', tick_us), 'iou': metrics(ticks, 'iou', tick_us),
            'identity': 'UNCONFIRMED'}


# --------------------------------------------------------------------------------------------- decision points and statistics
DP_WINDOW_US = 3_000_000
BOOT_N = 2000
BOOT_SEED = 660


def decision_point_correct(ticks, t_dp_us: int, window_us: int = DP_WINDOW_US, criterion: str = 'primary') -> bool:
    """Preregistration §4.3: correct when the window [t_dp, t_dp + window] has at least one CORRECT tick and no WRONG_PERSON /
    WRONG_CAMERA tick; a window that is LOST throughout is not correct."""
    cls = [classify(t, criterion) for t in ticks if t_dp_us <= t.t_us <= t_dp_us + window_us]
    return 'CORRECT' in cls and not any(c in ('WRONG_PERSON', 'WRONG_CAMERA') for c in cls)


def majority(values) -> bool:
    """K-run majority vote (K=3 in E3); ties (even K) count as not correct."""
    values = list(values)
    return sum(bool(v) for v in values) * 2 > len(values)


def mcnemar(pairs) -> dict:
    """Exact two-sided McNemar test on paired booleans (agent_correct, baseline_correct)."""
    b = sum(1 for a, r in pairs if a and not r)     # agent right, baseline wrong
    c = sum(1 for a, r in pairs if r and not a)     # baseline right, agent wrong
    n = b + c
    if n == 0:
        return {'agent_only': 0, 'baseline_only': 0, 'p': 1.0, 'favours': None}
    tail = sum(math.comb(n, i) for i in range(0, min(b, c) + 1)) / 2 ** n
    return {'agent_only': b, 'baseline_only': c, 'p': min(1.0, 2 * tail), 'favours': 'agent' if b > c else ('baseline' if c > b else None)}


def cluster_bootstrap(clusters: dict, stat, n_boot: int = BOOT_N, seed: int = BOOT_SEED):
    """95 % percentile interval of ``stat(list of cluster values)`` resampling whole clusters (E3: one cluster = one segment)."""
    keys = sorted(clusters)
    if not keys:
        return None
    rng = random.Random(seed)
    est = []
    for _ in range(n_boot):
        v = stat([clusters[keys[rng.randrange(len(keys))]] for _ in keys])
        if v is not None:
            est.append(v)
    est.sort()
    if not est:
        return None
    return [est[int(.025 * len(est))], est[min(len(est) - 1, int(.975 * len(est)))]]


# --------------------------------------------------------------------------------------------- camera ranking (H4)
def random_topk(n_cams: int, n_visible: int, k: int) -> float:
    """P(at least one of k uniformly chosen cameras sees the target)."""
    if n_visible <= 0:
        return 0.0
    if n_cams - n_visible < k:
        return 1.0
    return 1 - math.comb(n_cams - n_visible, k) / math.comb(n_cams, k)


def camera_topk(items, ks=(1, 3)) -> dict:
    """items: iterable of (ranked camera list, visible camera set, n_cams). Only items with the target visible somewhere count."""
    out = {'n': 0}
    for k in ks:
        out[f'top{k}'] = 0
        out[f'random_top{k}'] = 0.0
    for ranked, vis, n in items:
        vis = set(vis)
        if not vis:
            continue
        out['n'] += 1
        for k in ks:
            out[f'top{k}'] += bool(set(ranked[:k]) & vis)
            out[f'random_top{k}'] += random_topk(n, len(vis), k)
    for k in ks:
        n = out['n']
        out[f'top{k}_rate'] = round(out[f'top{k}'] / n, 4) if n else None
        out[f'random_top{k}_rate'] = round(out[f'random_top{k}'] / n, 4) if n else None
        out[f'random_top{k}'] = round(out[f'random_top{k}'], 3)
    return out


# --------------------------------------------------------------------------------------------- per-frame presence (H5)
def frame_outcome(pred_present: bool, box, gt_present: bool, body, size=None, criterion: str = 'primary') -> str:
    """TP / FP_wrong_box / FP_absent / FN / TN for one frame answer, with the same box judgement as tracking."""
    if not pred_present or box is None:
        return 'FN' if gt_present else 'TN'
    if not gt_present:
        return 'FP_absent'
    j = judge_box(box, body, size)
    return 'TP' if j['primary' if criterion == 'primary' else 'iou_hit'] else 'FP_wrong_box'


def frame_prf(outcomes) -> dict:
    c = Counter(outcomes)
    tp, fpw, fpa, fn, tn = c['TP'], c['FP_wrong_box'], c['FP_absent'], c['FN'], c['TN']
    p = tp / (tp + fpw + fpa) if tp + fpw + fpa else None
    r = tp / (tp + fpw + fn) if tp + fpw + fn else None
    f = (2 * p * r / (p + r) if p + r else 0.0) if p is not None and r is not None else None
    return {'tp': tp, 'fp_wrong_box': fpw, 'fp_absent': fpa, 'fn': fn, 'tn': tn, 'precision': p, 'recall': r, 'f1': f}


# --------------------------------------------------------------------------------------------- API cost / latency / adoption
def api_stats(records) -> dict:
    """records: dicts with optional latency_s, cost_usd, adopted (bool: the Agent answer was used), error (truthy = failed)."""
    recs = list(records)
    lat = [r['latency_s'] for r in recs if isinstance(r.get('latency_s'), (int, float)) and r['latency_s'] > 0]
    cost = [r['cost_usd'] for r in recs if isinstance(r.get('cost_usd'), (int, float))]
    n = len(recs)
    adopted = sum(bool(r.get('adopted')) for r in recs)
    return {'decisions': n, 'errors': sum(bool(r.get('error')) for r in recs),
            'adoption_rate': round(adopted / n, 4) if n else None,
            'latency_p50_s': _pct(lat, .5), 'latency_p95_s': _pct(lat, .95),
            'cost_usd_total': round(sum(cost), 6) if cost else None,
            'cost_usd_per_decision': round(sum(cost) / len(cost), 6) if cost else None}


# --------------------------------------------------------------------------------------------- LIVE adapter (live-ab logs)
def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def ticks_from_live(a_ticks, b_ticks, target: str, tick_us: int = 50_000) -> list:
    """Scored ticks from aligned LIVE A/B logs (``live-ab.a-log.v1`` / ``live-ab.b-log.v1`` rows of one tracking segment).

    A rows (scoring side): ``actors`` = [{id, present, xy, gt_visible[, gt_boxes{cam: box}]}]. B rows (system): ``tracking`` =
    {state, active_cam, est_xy, lost_ticks[, box]}. Ticks whose A row is missing or ambiguous are skipped (the caller reports
    them as UNKNOWN, as ``scripts/live_ab_score.py`` does)."""
    a_by = {}
    for r in a_ticks:
        a_by.setdefault(r['tick'], []).append(r)
    out = []
    for b in b_ticks:
        src = a_by.get(b['tick'], [])
        if len(src) != 1:
            continue
        actors = {x['id']: x for x in src[0].get('actors') or []}
        gt = actors.get(target)
        if gt is None:
            continue
        vis = frozenset(gt.get('gt_visible') or []) if gt.get('present') else frozenset()
        tr = b.get('tracking') or {}
        state = tr.get('state')
        showing = state == 'TRACKING' and not tr.get('lost_ticks') and tr.get('est_xy') is not None and tr.get('active_cam')
        t_us = int(b['tick']) * tick_us
        if not showing:
            out.append(Tick(t_us, None, visible=vis, src='SYSTEM'))
            continue
        cam, est = tr['active_cam'], tr['est_xy']
        box = tr.get('box')
        body = (gt.get('gt_boxes') or {}).get(cam) if gt.get('present') else None
        if box is not None:
            out.append(Tick(t_us, cam, boxes=(tuple(box),), visible=vis, body=tuple(body) if body else None, src='SYSTEM'))
            continue
        hit = bool(gt.get('present')) and _dist(est, gt['xy']) <= POS_HIT_M
        other = any(x.get('present') and k != target and _dist(est, x['xy']) <= POS_HIT_M for k, x in actors.items())
        out.append(Tick(t_us, cam, visible=vis, pos_hit=hit, pos_other=other, src='SYSTEM'))
    return out
