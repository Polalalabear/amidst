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
TICK_US = 200_000          # r004 index cadence (5 fps); LIVE logs carry their own cadence. Always passed explicitly (#662 Opus 5)
IOU_HIT = 0.3
POS_HIT_M = 1.5
HOLD_US = 600_000
CRITERIA = ('primary', 'iou')
VISIBLE_CLASSES = ('CORRECT', 'MISLOCALIZED', 'WRONG_PERSON', 'WRONG_CAMERA', 'LOST')
ERROR_CLASSES = ('WRONG_PERSON', 'MISLOCALIZED', 'LOST', 'WRONG_CAMERA')
BLIND_CLASSES = ('FALSE_LOCK', 'BLIND_OK', 'BLIND_HOLD')
UNKNOWN_CLASSES = ('GT_UNKNOWN',)   # target visible in the shown camera, a box is shown, but the GT body box is missing
GT_UNKNOWN_STOP = 0.05            # preregistration §9: stop when GT_UNKNOWN > 5 % of GT-visible ticks in any group


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
    tick_us: int | None = None          # tick length; metrics() refuses ticks whose tick_us disagrees with its argument


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
        if tick.body is None:                          # GT box missing for a visible target: not scoreable, never WRONG_PERSON
            return 'GT_UNKNOWN'
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


def reacquire_episodes(ticks, classes, tick_us: int) -> list:
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


def resolve_tick_us(ticks, tick_us) -> int:
    """The tick length: the argument and every tick's own ``tick_us`` must agree; at least one must be given (no default)."""
    own = {t.tick_us for t in ticks if t.tick_us is not None}
    if len(own) > 1:
        raise ValueError(f'TICK_US_MIXED: {sorted(own)}')
    if tick_us is None:
        if not own:
            raise ValueError('TICK_US_REQUIRED')
        return own.pop()
    if own and own != {tick_us}:
        raise ValueError(f'TICK_US_MISMATCH: argument {tick_us}, ticks {sorted(own)}')
    return tick_us


def metrics(ticks, criterion: str = 'primary', tick_us: int | None = None) -> dict:
    """All per-event tracking metrics under one criterion. Denominator = GT-visible ticks (GT_UNKNOWN excluded, counted apart)."""
    ticks = sorted(ticks, key=lambda t: t.t_us)
    tick_us = resolve_tick_us(ticks, tick_us)
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
        'counts': {c: cnt[c] for c in VISIBLE_CLASSES + BLIND_CLASSES + UNKNOWN_CLASSES},
        'gt_unknown_share': round(cnt['GT_UNKNOWN'] / (nv + cnt['GT_UNKNOWN']), 4) if nv + cnt['GT_UNKNOWN'] else None,
        'gt_unknown_stop': bool(nv + cnt['GT_UNKNOWN']) and cnt['GT_UNKNOWN'] / (nv + cnt['GT_UNKNOWN']) > GT_UNKNOWN_STOP,
        'counts_by_src': {s: dict(v) for s, v in sorted(by_src.items())},
    }


def score_event(ticks, tick_us: int | None = None) -> dict:
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


def cluster_bootstrap(clusters: dict, stat, n_boot: int = BOOT_N, seed: int = BOOT_SEED, level: float = 0.95):
    """Percentile interval (``level``, default 95 %) of ``stat(list of cluster values)`` resampling whole clusters
    (E3: one cluster = one segment)."""
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
    a = (1 - level) / 2
    return [est[int(a * len(est))], est[min(len(est) - 1, int((1 - a) * len(est)))]]


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


def ticks_from_live(a_ticks, b_ticks, target: str, *, tick_us: int, size: tuple) -> list:
    """Scored ticks from aligned LIVE A/B logs (``live-ab.a-log.v1`` / ``live-ab.b-log.v1`` rows of one tracking segment).

    A rows (scoring side): ``actors`` = [{id, present, xy, gt_visible[, gt_boxes{cam: box}]}]. B rows (system): ``tracking`` =
    {state, active_cam, est_xy, lost_ticks[, box]}. Ticks whose A row is missing or ambiguous are skipped (the caller reports
    them as UNKNOWN, as ``scripts/live_ab_score.py`` does). ``tick_us`` (LIVE: 50_000) and ``size`` (capture (w, h)) are required:
    every Tick carries them, so seconds cannot be off by the r004 cadence and GT boxes are clipped to the image."""
    if not isinstance(tick_us, int) or tick_us <= 0:
        raise ValueError('TICK_US_REQUIRED')
    if not (isinstance(size, (tuple, list)) and len(size) == 2):
        raise ValueError('SIZE_REQUIRED')
    size = tuple(size)
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
            out.append(Tick(t_us, None, visible=vis, size=size, src='SYSTEM', tick_us=tick_us))
            continue
        cam, est = tr['active_cam'], tr['est_xy']
        box = tr.get('box')
        body = (gt.get('gt_boxes') or {}).get(cam) if gt.get('present') else None
        if box is not None:
            out.append(Tick(t_us, cam, boxes=(tuple(box),), visible=vis, body=tuple(body) if body else None, size=size, src='SYSTEM',
                            tick_us=tick_us))
            continue
        hit = bool(gt.get('present')) and _dist(est, gt['xy']) <= POS_HIT_M
        other = any(x.get('present') and k != target and _dist(est, x['xy']) <= POS_HIT_M for k, x in actors.items())
        out.append(Tick(t_us, cam, visible=vis, size=size, pos_hit=hit, pos_other=other, src='SYSTEM', tick_us=tick_us))
    return out


# --------------------------------------------------------------------------------------------- verdicts (preregistration §6)
# Pure functions: intervals, McNemar results, random expectations and sample counts in, one of four verdicts out. The E3 report
# applies these to the numbers; the version of this file at the PR #662 merge commit decides (preregistration §6.0).
SUPPORTED, NOT_SUPPORTED, INCONCLUSIVE, EXPLORATORY = 'SUPPORTED', 'NOT_SUPPORTED', 'INCONCLUSIVE', 'EXPLORATORY'
VERDICT_ZH = {SUPPORTED: '成立', NOT_SUPPORTED: '不成立', INCONCLUSIVE: '無法判斷', EXPLORATORY: '探索性'}
MIN_POINTS, MIN_SEGMENTS, MIN_REAPPEAR, MIN_LAYER_FRAMES = 40, 8, 30, 50
FOLLOW_MARGIN = 0.05
P_ALPHA = 0.05
H5_LAYERS = ('similar_clothing', 'occlusion', 'far_small', 'no_person_box', 'non_person_box')
H5_LEVEL = 0.99        # Bonferroni over the 5 hard layers (0.05 / 5)


def side(ci):
    """'below' (whole interval < 0), 'above' (> 0) or 'zero' (contains 0) for an interval [lo, hi]."""
    lo, hi = ci
    return 'below' if hi < 0 else 'above' if lo > 0 else 'zero'


def _out(verdict, reasons, **extra):
    return {'verdict': verdict, 'verdict_zh': VERDICT_ZH[verdict], 'reasons': reasons, **extra}


def verdict_h1(wp_diff_ci, follow_diff_ci, mc: dict, n_points: int, n_segments: int, iou_follow_diff=None) -> dict:
    """H1 primary test: A2 vs B1 offline (A3 vs B1 is the secondary test, same rule, reported apart). Differences are A - B1;
    ``wp_diff_ci`` wrong-person seconds, ``follow_diff_ci`` follow rate, ``mc`` = mcnemar(agent majority, B1)."""
    note = None
    if iou_follow_diff is not None and iou_follow_diff < -FOLLOW_MARGIN:
        note = 'DEPENDS_ON_BOX_CRITERION'
    agent_sig = mc['p'] < P_ALPHA and mc['favours'] == 'agent'
    rule_sig = mc['p'] < P_ALPHA and mc['favours'] == 'baseline'
    supported = side(wp_diff_ci) == 'below' and follow_diff_ci[0] > -FOLLOW_MARGIN and agent_sig
    against = side(wp_diff_ci) == 'above' or follow_diff_ci[1] < -FOLLOW_MARGIN or rule_sig
    reasons = {'wrong_person': side(wp_diff_ci), 'follow_lower': follow_diff_ci[0], 'follow_upper': follow_diff_ci[1],
               'mcnemar_p': mc['p'], 'mcnemar_favours': mc['favours']}
    if n_points < MIN_POINTS or n_segments < MIN_SEGMENTS:
        return _out(EXPLORATORY, reasons, robustness=note, would_be=(SUPPORTED if supported and not against else
                                                                     NOT_SUPPORTED if against else INCONCLUSIVE))
    if against:
        return _out(NOT_SUPPORTED, reasons, robustness=note)
    if supported:
        return _out(SUPPORTED, reasons, robustness=note)
    return _out(INCONCLUSIVE, reasons, robustness=note)


# H2 combination table (preregistration §6.2): primary metric = wrong-person seconds difference (A - B), 'below' = Agent better.
H2_TABLE = {
    ('below', 'below'): SUPPORTED,        # both image effects present (also needs the D-class exit condition)
    ('zero', 'below'): NOT_SUPPORTED,     # gain only with spatial info: interaction, not "the gain comes from images"
    ('below', 'zero'): INCONCLUSIVE,
    ('zero', 'zero'): INCONCLUSIVE,       # no difference observed
}


def verdict_h2(a1b1_wp_ci, a2b2_wp_ci, d_exit_diff_ci, n_points: int, n_segments: int) -> dict:
    """H2: image main effect. ``a1b1_wp_ci`` / ``a2b2_wp_ci`` wrong-person-second differences; ``d_exit_diff_ci`` = A2 - B2 accuracy
    of "has left" judgements on D-class points. Any 'above' (Agent worse) -> NOT_SUPPORTED."""
    key = (side(a1b1_wp_ci), side(a2b2_wp_ci))
    if 'above' in key:
        v = NOT_SUPPORTED
    else:
        v = H2_TABLE[key]
        if v == SUPPORTED and not d_exit_diff_ci[0] > -FOLLOW_MARGIN:
            v = INCONCLUSIVE
    reasons = {'a1_b1': key[0], 'a2_b2': key[1], 'd_exit_lower': d_exit_diff_ci[0],
               'interaction': key == ('zero', 'below')}
    if n_points < MIN_POINTS or n_segments < MIN_SEGMENTS:
        return _out(EXPLORATORY, reasons, would_be=v)
    return _out(v, reasons)


def verdict_h4(top1_diff_ci, a2_top1_rate: float, a2_random_top1_rate: float, a2_top1_ci, a2_latency_median, a1_latency_median,
               n_reappear: int) -> dict:
    """H4: spatial ranking. One decision point per reappearance; no hint counts as a miss (caller). ``top1_diff_ci`` = A2 - A1."""
    above_random = a2_top1_ci[0] > a2_random_top1_rate
    faster = a2_latency_median is not None and a1_latency_median is not None and a2_latency_median < a1_latency_median
    supported = side(top1_diff_ci) == 'above' and above_random and faster
    against = side(top1_diff_ci) != 'above' or a2_top1_rate <= a2_random_top1_rate
    v = SUPPORTED if supported else NOT_SUPPORTED if against else INCONCLUSIVE
    reasons = {'top1_diff': side(top1_diff_ci), 'a2_top1': a2_top1_rate, 'random_top1': a2_random_top1_rate,
               'a2_top1_lower_above_random': above_random, 'faster_reacquire': faster}
    if n_reappear < MIN_REAPPEAR:
        return _out(EXPLORATORY, reasons, would_be=v)
    return _out(v, reasons)


def verdict_h5(layers: dict, precision_diff_ci) -> dict:
    """H5: per-frame recognition. ``layers`` = {layer: {'n': present frames, 'recall_diff_ci': 99 % interval (Agent - rule)}} for the
    five hard layers; ``precision_diff_ci`` = 95 % interval of the precision difference pooled over the judged hard layers.
    Bootstrap unit = segment. Layers with n < 50 are not judged; fewer than two judged layers -> EXPLORATORY."""
    judged = {k: v for k, v in layers.items() if k in H5_LAYERS and v['n'] >= MIN_LAYER_FRAMES}
    up = [k for k, v in judged.items() if side(v['recall_diff_ci']) == 'above']
    down = [k for k, v in judged.items() if side(v['recall_diff_ci']) == 'below']
    if precision_diff_ci[1] < -FOLLOW_MARGIN or len(down) >= 2:
        v = NOT_SUPPORTED
    elif len(up) >= 2 and precision_diff_ci[0] > -FOLLOW_MARGIN:
        v = SUPPORTED
    else:
        v = INCONCLUSIVE
    reasons = {'judged_layers': sorted(judged), 'recall_up': sorted(up), 'recall_down': sorted(down),
               'precision_lower': precision_diff_ci[0], 'precision_upper': precision_diff_ci[1]}
    if len(judged) < 2:
        return _out(EXPLORATORY, reasons, would_be=v)
    return _out(v, reasons)
