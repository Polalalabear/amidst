"""W1 (#644) per-frame evaluation: pure logic (strata labels, answer parsing, per-frame scoring, paired bootstrap, prompts).

No file or network I/O and no GT here. GT enters only as the ``body`` argument of the scoring/stratum functions (scoring side).
Unit of evaluation = one (event, camera, tick) frame. Identity stays UNCONFIRMED: "correct" = the answered box is on the GT target body.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict

SIZE = (960, 540)
HIT_IOU = 0.3
RULE_MIN_SCORE = 0.3
ARMS = ('rule', 'rule_nocolor', 'vision_free', 'text', 'vision_pick')
LLM_ARMS = ('vision_free', 'text', 'vision_pick')


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.0


def center_in(box, body):
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return body[0] <= cx <= body[2] and body[1] <= cy <= body[3]


def box_hits(box, body) -> bool:
    return body is not None and (center_in(box, body) or iou(box, body) >= HIT_IOU)


def inside_fraction(body, w, h) -> float:
    a = (body[2] - body[0]) * (body[3] - body[1])
    if a <= 0:
        return 0.0
    ix = max(0.0, min(body[2], w) - max(body[0], 0.0))
    iy = max(0.0, min(body[3], h) - max(body[1], 0.0))
    return ix * iy / a


# ----------------------------------------------------------------------------------------------- strata (GT, scoring side only)
RED_PX_MIN = 15          # red-clothing pixels inside the GT body box that make T "pixel-visible" (T wears red; see doc §3)
PARTIAL_RATIO = 0.045    # red-pixel share of the body box below this = partly occluded (median of clear frames is 0.07)


def red_pixels(rgb_hsv_crop):
    """(count, share) of strongly red pixels in a PIL-HSV (0-255) crop of the GT body box; numpy array HxWx3."""
    h, s, v = rgb_hsv_crop[..., 0], rgb_hsv_crop[..., 1], rgb_hsv_crop[..., 2]
    red = ((h <= 10) | (h >= 245)) & (s >= 130) & (v >= 70)
    return int(red.sum()), float(red.mean()) if red.size else 0.0


def frame_labels(dets, body, w, h, red_px=0, red_share=0.0) -> dict:
    """GT-derived labels of one frame. ``dets`` = indexed detections (any class, score >= 0.3) as dicts {box,score,cls,verdict_red};
    ``body`` = GT target body box (projected) or None. ``red_px``/``red_share`` = pixel evidence of T inside the body box (GT box + pixels).
    present = T pixel-visible (>= 50% of the body box in frame AND red pixels); in_frustum = geometry only (T may be behind a wall)."""
    frac = inside_fraction(body, w, h) if body else 0.0
    in_frustum = frac >= 0.5
    present = in_frustum and red_px >= RED_PX_MIN
    on = [d for d in dets if present and center_in(d['box'], body)]
    persons_on = [d for d in on if d['cls'] == 'person']
    best = max(on, key=lambda d: d['score'], default=None)
    others_red = [d for d in dets if d['cls'] == 'person' and d['verdict_red'] in ('STRONG', 'WEAK')
                  and not (present and (center_in(d['box'], body) or iou(d['box'], body) >= HIT_IOU))]
    return {'in_frustum': in_frustum, 'present': present, 'inside_frac': round(frac, 3), 'red_px': red_px, 'red_share': round(red_share, 4),
            'body_h_px': (body[3] - body[1]) if body else 0.0, 'n_on_target': len(on),
            'best_score_on_target': best['score'] if best else None, 'best_class_on_target': best['cls'] if best else None,
            'person_on_target': bool(persons_on), 'n_other_red_persons': len(others_red)}


def strata_of(lab: dict, tercile: tuple) -> list:
    """Stratum names (a frame can be in several). ``tercile`` = (lo, hi) body-height cut points (px) of the pixel-visible frames."""
    s = []
    if not lab['present']:
        s.append('neg_occluded' if lab['in_frustum'] else 'neg_absent')       # behind a wall vs outside the view
        if lab['n_other_red_persons']:
            s.append('neg_with_similar')
        return s
    if lab['inside_frac'] < 0.95:
        s.append('partial_edge')            # body box cut by the image border
    elif lab['red_share'] < PARTIAL_RATIO:
        s.append('partial_occluded')        # red-pixel share well below a clear view (wall / vehicle in front)
    if lab['n_on_target'] == 0:
        s.append('visible_nobox')           # T visible in pixels but no RT-DETR box (>= 0.3) on T
    elif not lab['person_on_target']:
        s.append('nonperson_class')         # only boxes of another COCO class on T
    elif lab['best_score_on_target'] < 0.5:
        s.append('lowscore_person')         # T person box exists, score in [0.3, 0.5)
    if lab['body_h_px'] <= tercile[0]:
        s.append('far_small')
    if (lab['inside_frac'] >= 0.95 and lab['red_share'] >= PARTIAL_RATIO and lab['person_on_target']
            and lab['best_score_on_target'] >= 0.5 and lab['body_h_px'] > tercile[0]):
        s.append('easy_visible')
    if lab['n_other_red_persons']:
        s.append('pos_with_similar')
    return s


# ----------------------------------------------------------------------------------------------- answers
def parse_answer(text, det_ids, allow_box):
    """-> (answer, error). answer = {'present': bool, 'det': id|None, 'box': [..]|None}."""
    try:
        doc = json.loads(text)
    except (ValueError, TypeError):
        return None, 'NOT_JSON'
    if not isinstance(doc, dict) or not isinstance(doc.get('present'), bool):
        return None, 'BAD_SHAPE'
    if not doc['present']:
        return {'present': False, 'det': None, 'box': None, 'conf': doc.get('confidence')}, None
    did = doc.get('detection_id')
    if did is not None and did not in det_ids:
        return None, 'BAD_DETECTION_ID'
    box = doc.get('box_xyxy') if allow_box else None
    if box is not None:
        ok = isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in box) \
            and 0 <= box[0] < box[2] <= SIZE[0] + 1 and 0 <= box[1] < box[3] <= SIZE[1] + 1
        box = box if ok else None
    if did is None and box is None:
        return None, 'NO_TARGET_REF'
    return {'present': True, 'det': did, 'box': box, 'conf': doc.get('confidence')}, None


def answer_box(ans, dets_by_id):
    """Box the answer points at: indexed detection (by id) wins over own box."""
    if not ans or not ans['present']:
        return None, None
    if ans['det'] is not None:
        return dets_by_id[ans['det']]['box'], 'DET'
    return ans['box'], 'OWN'


def rule_answer(dets, color, use_color=True):
    """Q4 rule (q4_evidence.candidate_evidence): person, score >= 0.3, colour verdict STRONG/WEAK for the query colour; shown box = best
    by (verdict order, -score)."""
    obs = [d for d in dets if d['cls'] == 'person' and d['score'] >= RULE_MIN_SCORE]
    if use_color:
        order = {'STRONG': 0, 'WEAK': 1}
        obs = [d for d in obs if d['verdict_red'] in order]
        obs.sort(key=lambda d: (order[d['verdict_red']], -d['score']))
    else:
        obs.sort(key=lambda d: -d['score'])
    if not obs:
        return {'present': False, 'det': None, 'box': None}
    return {'present': True, 'det': obs[0]['id'], 'box': None}


def score_frame(ans, dets_by_id, lab, body) -> dict:
    """Outcome of one answer on one frame: TP / FP_wrong_box / FP_absent / FN / TN, plus box IoU when scored."""
    if ans is None:
        return {'out': 'INVALID', 'iou': None, 'src': None}
    box, src = answer_box(ans, dets_by_id)
    if not ans['present'] or box is None:
        return {'out': 'FN' if lab['present'] else 'TN', 'iou': None, 'src': None}
    if not lab['present']:
        return {'out': 'FP_absent', 'iou': None, 'src': src}
    hit = box_hits(box, body)
    return {'out': 'TP' if hit else 'FP_wrong_box', 'iou': round(iou(box, body), 3), 'src': src}


# ----------------------------------------------------------------------------------------------- metrics
def prf(outs):
    """precision / recall / F1 from per-frame outcomes (TP, FP_wrong_box, FP_absent, FN, TN). INVALID is mapped to FN/TN by the caller.
    recall = TP / frames where T is present; precision = TP / answered-present."""
    c = defaultdict(int)
    for o in outs:
        c[o] += 1
    tp, fpw, fpa, fn = c['TP'], c['FP_wrong_box'], c['FP_absent'], c['FN']
    p = tp / (tp + fpw + fpa) if tp + fpw + fpa else None
    r = tp / (tp + fpw + fn) if tp + fpw + fn else None
    f = (2 * p * r / (p + r) if p + r else 0.0) if p is not None and r is not None else None
    return {'tp': tp, 'fp_wrong_box': fpw, 'fp_absent': fpa, 'fn': fn, 'tn': c['TN'], 'precision': p, 'recall': r, 'f1': f}


def bootstrap_ci(values, stat, n_boot=2000, seed=0, alpha=0.05):
    """Percentile bootstrap CI of stat(list) over resampled items."""
    rng = random.Random(seed)
    n = len(values)
    if n == 0:
        return None
    est = [stat([values[rng.randrange(n)] for _ in range(n)]) for _ in range(n_boot)]
    est = sorted(e for e in est if e is not None)
    if not est:
        return None
    return (est[int(alpha / 2 * len(est))], est[min(len(est) - 1, int((1 - alpha / 2) * len(est)))])


def percentile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


# ----------------------------------------------------------------------------------------------- prompts
SYSTEM_PREFIX = (
    'You are the recognition step of a multi-camera person finder in a rendered (synthetic) demo site. Identity can never be confirmed: '
    'you only say whether a person who looks like the same person as the reference crop is visible in the current camera frame.\n'
    'The detector (RT-DETR, COCO classes, threshold 0.3) labels boxes automatically and often mislabels people as other classes '
    '(sports ball, fire hydrant, toothbrush, ...) or misses them; the colour labels are an HSV heuristic. Neither is ground truth.\n'
    'Decide for THIS camera frame only: is the target visible (even partly, even if no detection box covers them)? '
    'Answering present=false is preferred over guessing when you cannot find the person.\n'
    'Reply with one JSON object only: {"present": bool, "detection_id": string|null, "box_xyxy": [x0,y0,x1,y1]|null, '
    '"confidence": "low"|"medium"|"high", "reason": short string}. Boxes are in the 960x540 pixel frame of the image. '
    'If a numbered detection box covers the target, give its id; otherwise give your own box.')
SYSTEM_PICK_SUFFIX = ('\nIn this task you may ONLY answer with the id of an existing numbered detection (any class), or present=false. '
                      'Do not give your own box (set box_xyxy to null).')
SYSTEM_TEXT_SUFFIX = '\nIn this task no images are available: decide from the numbers in the text only.'


def scene_context(label, cameras, neighbours, seed_colors):
    """Fixed per-event prefix text (same bytes for every frame of the event -> prompt-cache friendly)."""
    lines = [f'Scene context [event {label}; synthetic L-shaped corridor site; camera graph is a DRAFT, unapproved]',
             'Cameras of this site: ' + ', '.join(cameras) + '.']
    for c in cameras:
        lines.append(f'- {c}: graph neighbours {", ".join(neighbours.get(c, [])) or "none"}')
    lines.append('Target reference: seed crop (first tracker lock); tracker colour labels of the seed: ' + (', '.join(seed_colors) or 'none') + '.')
    return '\n'.join(lines)


def request_text(cam, t_s, dets, arm):
    lines = [f'Current frame: camera {cam}, t={t_s:.1f} s. Detections (id, class, box x0,y0,x1,y1 px, score, HSV colour labels with verdict STRONG/WEAK):']
    if not dets:
        lines.append('- none above 0.3')
    for d in dets:
        lines.append(f'- {d["id"]} {d["cls"]} [{d["box"][0]:.0f},{d["box"][1]:.0f},{d["box"][2]:.0f},{d["box"][3]:.0f}] score {d["score"]:.2f} '
                     f'colours {",".join(d["colors"]) or "none"}')
    lines.append('Images: reference crop, then the current frame with the detections drawn as numbered boxes.' if arm != 'text'
                 else 'No images. Box sizes and positions are the only geometry you have.')
    return '\n'.join(lines)
