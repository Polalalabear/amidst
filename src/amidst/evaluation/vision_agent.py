"""Vision + graph-prediction Agent: offline replay engine for the A4-1 / B4-1 loss gaps (issue #640).

Pure logic, no file/network I/O and no GT. The Agent is called when the rule display is not ON_CAMERA after the first lock
(GAP / LOST). It is given only system observations: the last displayed camera/time, the seed appearance, the DRAFT camera graph
neighbours and the shared detection index of the candidate cameras at the call tick. Its answer is snapped onto that same index
(IoU) and followed forward by IoU through the index, so the Agent and the rule share one set of detections. An answer that
matches no indexed detection is an ``OWN_BOX`` and is scored separately.

GT enters only through the ``body_of`` callable handed to :func:`overlay` (scoring side) and through the oracle agent that the
scoring script builds (the upper bound, not an Agent). Identity stays UNCONFIRMED; "correct" means "the shown box is on the GT
target body", not identity.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass

TICK = 200_000
SNAP_IOU = 0.3
CHAIN_IOU = 0.3
OWN_IOU = 0.3
MIN_SCORE = 0.3
GRAPH_STATUS = 'DRAFT (camera_graph_v3_1, not approved)'
MODES = ('offline', 'realtime')


# --------------------------------------------------------------------------------------------- geometry / index
def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def center_in(box, body, margin=0.0) -> bool:
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    w, h = body[2] - body[0], body[3] - body[1]
    return body[0] - margin * w <= cx <= body[2] + margin * w and body[1] - margin * h <= cy <= body[3] + margin * h


@dataclass(frozen=True)
class Det:
    id: str            # opaque per (camera, tick): D1, D2, ...
    obs_id: str
    box: tuple
    score: float
    colors: tuple


def colors_of(color_field) -> tuple:
    """System colour labels of one indexed person detection (verdict != NONE); no GT."""
    if not isinstance(color_field, dict):
        return ()
    return tuple(sorted(k for k, v in (color_field.get('verdicts') or {}).items() if v not in ('NONE', 'UNKNOWN')))


def build_index(records, min_score: float = MIN_SCORE) -> dict:
    """{(camera_id, t_us): [Det,...]} of PERSON detections with score >= min_score from detection_index records."""
    out = {}
    for r in records:
        dets = [d for d in (r.get('detections') or []) if d.get('class_label') == 'person' and d['score'] >= min_score]
        dets.sort(key=lambda d: d['observation_id'])
        out[(r['camera_id'], r['timestamp_us'])] = [
            Det(f'D{i + 1}', d['observation_id'], tuple(d['bbox_xyxy_px']), d['score'], colors_of(d.get('color')))
            for i, d in enumerate(dets)]
    return out


# --------------------------------------------------------------------------------------------- rule view
@dataclass
class RuleView:
    """What the rule display shows per tick (system output only)."""
    ticks: list              # all tick times (us)
    kind: dict               # t -> 'ON_CAMERA' | 'GAP' | 'LOST' | 'NONE'
    camera: dict             # t -> camera_id or None
    boxes: dict              # t -> [bbox,...] of the rule's selected observations at t
    first_lock: int | None   # first tick with ON_CAMERA


def rule_view(single_view, selected_obs, duration_us) -> RuleView:
    """single_view: response['single_view']; selected_obs: {(camera, t): [bbox,...]} of the selected sightings."""
    ticks = list(range(0, duration_us, TICK))
    kind, cam, boxes = {}, {}, {}
    for t in ticks:
        seg = next((s for s in single_view if s['range_us'][0] <= t < s['range_us'][1]), None)
        kind[t] = seg['kind'] if seg else 'NONE'
        cam[t] = seg.get('camera_id') if seg else None
        boxes[t] = selected_obs.get((cam[t], t), []) if kind[t] == 'ON_CAMERA' else []
    lock = next((t for t in ticks if kind[t] == 'ON_CAMERA'), None)
    return RuleView(ticks, kind, cam, boxes, lock)


def trigger_ticks(view: RuleView) -> list:
    if view.first_lock is None:
        return []
    return [t for t in view.ticks if t >= view.first_lock and view.kind[t] != 'ON_CAMERA']


def last_known(view: RuleView, t: int):
    """(camera, last tick shown, boxes at that tick) of the latest ON_CAMERA tick before t, or None."""
    for u in range(t - TICK, -1, -TICK):
        if view.kind.get(u) == 'ON_CAMERA':
            return view.camera[u], u, view.boxes[u]
    return None


def allowed_cameras(last_cam: str, transitions, event_cameras) -> list:
    """Last displayed camera plus its DRAFT-graph neighbours that exist in this event (system data only)."""
    nbrs = {b for (a, b) in transitions if a == last_cam} | {a for (a, b) in transitions if b == last_cam}
    return sorted(({last_cam} | nbrs) & set(event_cameras))


# --------------------------------------------------------------------------------------------- answer handling
def parse_answer(text: str, allowed, dets_by_cam: dict, size=(960, 540)):
    """Validate one model reply. Returns (answer_dict, error). Errors -> answer None (counted as INVALID)."""
    try:
        doc = json.loads(text)
    except (ValueError, TypeError):
        return None, 'NOT_JSON'
    if not isinstance(doc, dict) or not isinstance(doc.get('present'), bool):
        return None, 'BAD_SHAPE'
    if not doc['present']:
        return {'present': False, 'camera_id': None, 'detection_id': None, 'box_xyxy': None,
                'confidence': doc.get('confidence'), 'reason': str(doc.get('reason', ''))[:200]}, None
    cam = doc.get('camera_id')
    if cam not in allowed:
        return None, 'BAD_CAMERA'
    did = doc.get('detection_id')
    bad_id = did is not None and did not in {d.id for d in dets_by_cam.get(cam, [])}
    if bad_id:
        did = None
    box = doc.get('box_xyxy')
    if box is not None:
        ok = (isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in box)
              and 0 <= box[0] < box[2] <= size[0] + 1 and 0 <= box[1] < box[3] <= size[1] + 1)
        if not ok:
            box = None
    if did is None and box is None:
        return None, 'BAD_DETECTION_ID' if bad_id else 'NO_TARGET_REF'
    return {'present': True, 'camera_id': cam, 'detection_id': did, 'box_xyxy': box,
            'confidence': doc.get('confidence'), 'reason': str(doc.get('reason', ''))[:200]}, None


def resolve(answer, t, index):
    """Map an answer onto the shared index: ('SNAP', cam, Det) | ('OWN', cam, box) | None."""
    if not answer or not answer.get('present'):
        return None
    cam, dets = answer['camera_id'], index.get((answer['camera_id'], t), [])
    if answer.get('detection_id'):
        det = next((d for d in dets if d.id == answer['detection_id']), None)
        if det:
            return 'SNAP', cam, det
    box = answer.get('box_xyxy')
    if box:
        best = max(dets, key=lambda d: iou(d.box, box), default=None)
        if best is not None and iou(best.box, box) >= SNAP_IOU:
            return 'SNAP', cam, best
        return 'OWN', cam, tuple(box)
    return None


def _follow(index, cam, box, t):
    best = max(index.get((cam, t), []), key=lambda d: iou(d.box, box), default=None)
    return best if best is not None and iou(best.box, box) >= CHAIN_IOU else None


# --------------------------------------------------------------------------------------------- replay
def replay(view: RuleView, index: dict, agent, mode: str):
    """Replay the Agent over the rule's loss ticks.

    ``agent(t) -> answer dict | None`` (stateless in t; answer may carry ``latency_s``). ``offline``: the answer is effective at
    the call tick (latency ignored). ``realtime``: effective at the first tick >= call tick + latency, after the answer is followed
    forward through the index; no new call while one is in flight. Returns (displays, calls)."""
    if mode not in MODES:
        raise ValueError('MODE_INVALID')
    displays, calls = {}, []
    active = None    # {'cam','det'(Det),'call_t'}
    pending = None   # {'call_t','arrive_t','cam','det'(Det)|None,'own':box|None,'latency_s'}
    busy_until = -1
    for t in view.ticks:
        if view.first_lock is None or t < view.first_lock or view.kind[t] == 'ON_CAMERA':
            active, pending = None, None
            continue
        if active is not None:
            nxt = _follow(index, active['cam'], active['det'].box, t)
            active = None if nxt is None else dict(active, det=nxt)
        if pending is not None and t >= pending['arrive_t']:
            if pending['det'] is not None:                 # follow the answer forward from the call tick to now
                det, ok = pending['det'], True
                for u in range(pending['call_t'] + TICK, t + 1, TICK):
                    det = _follow(index, pending['cam'], det.box, u)
                    if det is None:
                        ok = False
                        break
                if ok:
                    active = {'cam': pending['cam'], 'det': det, 'call_t': pending['call_t']}
                    calls[pending['idx']]['effective_t'] = t
                else:
                    calls[pending['idx']]['expired'] = True
            else:                                           # own box: stale, shown once at arrival
                displays[t] = {'src': 'AGENT', 'kind': 'OWN', 'cam': pending['cam'], 'box': pending['own'], 'call_t': pending['call_t']}
                calls[pending['idx']]['effective_t'] = t
            pending = None
        if active is not None:
            displays[t] = {'src': 'AGENT', 'kind': 'SNAP', 'cam': active['cam'], 'box': active['det'].box,
                           'det_id': active['det'].id, 'obs_id': active['det'].obs_id, 'call_t': active['call_t']}
            continue
        if t in displays or pending is not None or t < busy_until:
            continue
        answer = agent(t)
        lat = float(answer.get('latency_s') or 0.0) if answer else 0.0
        res = resolve(answer, t, index)
        calls.append({'call_t': t, 'latency_s': lat, 'answered': bool(answer), 'present': bool(answer and answer.get('present')),
                      'resolved': res[0] if res else None, 'camera_id': res[1] if res else None})
        if mode == 'offline' or lat <= 0:
            if res and res[0] == 'SNAP':
                active = {'cam': res[1], 'det': res[2], 'call_t': t}
                displays[t] = {'src': 'AGENT', 'kind': 'SNAP', 'cam': res[1], 'box': res[2].box, 'det_id': res[2].id,
                               'obs_id': res[2].obs_id, 'call_t': t}
                calls[-1]['effective_t'] = t
            elif res:
                displays[t] = {'src': 'AGENT', 'kind': 'OWN', 'cam': res[1], 'box': res[2], 'call_t': t}
                calls[-1]['effective_t'] = t
            continue
        arrive = t + -(-int(round(lat * 1e6)) // TICK) * TICK
        busy_until = arrive
        if res:
            pending = {'call_t': t, 'arrive_t': arrive, 'cam': res[1], 'det': res[2] if res[0] == 'SNAP' else None,
                       'own': res[2] if res[0] == 'OWN' else None, 'idx': len(calls) - 1}
    return displays, calls


# --------------------------------------------------------------------------------------------- scoring overlay
def overlay(rule_rows, displays, body_of):
    """Rule per-tick rows (GT scorer output) with the Agent displays substituted on loss ticks.

    ``body_of(camera, t) -> [x0,y0,x1,y1] | None`` is the GT target body box (scoring side only). SNAP ticks are scored exactly like
    rule ON_CAMERA ticks; OWN_BOX ticks keep the rule's GAP class and are tallied separately (``own``)."""
    rows = []
    for r in rule_rows:
        d = displays.get(r['t_us'])
        if d is None or r['kind'] == 'ON_CAMERA':
            rows.append(dict(r, src='RULE'))
            continue
        body = body_of(d['cam'], r['t_us'])
        if d['kind'] == 'SNAP':
            hit = body is not None and center_in(d['box'], body, 0.0)
            cls = 'CORRECT' if hit else ('WRONG_PERSON' if r['t_visible'] else 'FALSE_LOCK')
            rows.append(dict(r, src='AGENT', kind='ON_CAMERA', camera=d['cam'], cls=cls))
        else:
            hit = body is not None and iou(d['box'], body) >= OWN_IOU
            rows.append(dict(r, src='AGENT_OWN', own='OWN_CORRECT' if hit else 'OWN_WRONG'))
    return rows


def episode_stats(view: RuleView, rule_rows, agent_rows) -> dict:
    """Per rule-loss episode: MISSED seconds rule vs agent, first correct agent display, early reconnect seconds; plus wrong
    connections (an Agent display run whose first tick is not on the target)."""
    trig = set(trigger_ticks(view))
    eps, cur = [], []
    for t in view.ticks:
        if t in trig:
            cur.append(t)
        elif cur:
            eps.append(cur)
            cur = []
    if cur:
        eps.append(cur)
    by_t_rule = {r['t_us']: r for r in rule_rows}
    by_t_ag = {r['t_us']: r for r in agent_rows}
    out = []
    for ep in eps:
        end_t = ep[-1] + TICK
        reconnect = end_t if end_t in view.kind and view.kind[end_t] == 'ON_CAMERA' else None
        if not any(by_t_rule[t]['t_visible'] for t in ep):
            continue        # the target is not detectable anywhere in this episode: nothing to win or lose
        first = next((t for t in ep if (by_t_ag[t].get('src') == 'AGENT' and by_t_ag[t]['cls'] == 'CORRECT')
                      or by_t_ag[t].get('own') == 'OWN_CORRECT'), None)
        missed_rule = sum(by_t_rule[t]['cls'] == 'MISSED' for t in ep)
        missed_ag = sum(by_t_ag[t]['cls'] == 'MISSED' and by_t_ag[t].get('own') != 'OWN_CORRECT' for t in ep)
        out.append({'start_s': ep[0] / 1e6, 'end_s': end_t / 1e6, 'missed_s_rule': missed_rule * TICK / 1e6,
                    'missed_s_agent': missed_ag * TICK / 1e6, 'first_agent_correct_s': None if first is None else first / 1e6,
                    'early_reconnect_s': 0.0 if first is None or reconnect is None else round((reconnect - first) / 1e6, 1),
                    'rule_reconnect_s': None if reconnect is None else reconnect / 1e6})
    wrong, right, prev_cam, prev_t = 0, 0, None, None
    for r in agent_rows:
        if r.get('src') != 'AGENT':
            prev_cam, prev_t = None, None
            continue
        start = not (prev_cam == r['camera'] and prev_t == r['t_us'] - TICK)
        if start:
            wrong += r['cls'] in ('WRONG_PERSON', 'FALSE_LOCK')
            right += r['cls'] == 'CORRECT'
        prev_cam, prev_t = r['camera'], r['t_us']
    own = Counter(r['own'] for r in agent_rows if r.get('src') == 'AGENT_OWN')
    tv = sum(bool(r['t_visible']) for r in agent_rows)
    covered = sum(r['cls'] == 'MISSED' and r.get('own') == 'OWN_CORRECT' for r in agent_rows)
    n_correct = sum(r['cls'] == 'CORRECT' for r in agent_rows)
    n_missed = sum(r['cls'] == 'MISSED' for r in agent_rows)
    return {'combined_follow_rate': round((n_correct + covered) / tv, 4) if tv else None,
            'combined_lost_s_while_visible': round((n_missed - covered) * TICK / 1e6, 1),
            'own_box_on_missed_ticks': covered,
            'own_box_wrong_s': round(own['OWN_WRONG'] * TICK / 1e6, 1),
            'own_box_correct_s': round(own['OWN_CORRECT'] * TICK / 1e6, 1),'episodes': out, 'wrong_connections': wrong, 'right_connections': right,
            'early_reconnect_s_total': round(sum(e['early_reconnect_s'] for e in out), 1),
            'own_box_correct_ticks': own['OWN_CORRECT'], 'own_box_wrong_ticks': own['OWN_WRONG']}


# --------------------------------------------------------------------------------------------- prompts
SYSTEM_PROMPT = (
    'You help re-acquire a person that a camera tracker has just lost. Cameras are connected by a camera graph that is a DRAFT '
    '(unapproved): an edge only says a walk between two cameras is topologically possible, never that it happened. '
    'The target is described by a seed crop and the tracker\'s colour labels; identity can never be confirmed, you only say which '
    'detected person looks most like the same person as the seed. '
    'Decide whether the target is visible NOW in one of the candidate cameras. If a numbered detection box fits, answer its id; '
    'if the person is visible but no numbered box covers them, give your own box in the image pixel frame (x0,y0,x1,y1; images are '
    '960x540); if you cannot find the target, answer present=false (preferred over guessing). '
    'Reply with one JSON object only: {"present": bool, "camera_id": string|null, "detection_id": string|null, '
    '"box_xyxy": [x0,y0,x1,y1]|null, "confidence": "low"|"medium"|"high", "reason": short string}.')


def request_text(ctx: dict, with_images: bool) -> str:
    """The text of one request. ctx comes from the script: t_s, last_camera, last_t_s, seed, allowed, dets (camera -> [Det]), edges."""
    if ctx.get('rule_showing'):
        first = (f'Now: t={ctx["t_s"]:.1f} s. The tracker currently shows the target in {ctx["last_camera"]} (green box) but its '
                 'detection score is low, so please verify: where is the target really?')
    else:
        first = (f'Now: t={ctx["t_s"]:.1f} s. The tracker last showed the target in {ctx["last_camera"]} at t={ctx["last_t_s"]:.1f} s '
                 f'({ctx["t_s"] - ctx["last_t_s"]:.1f} s ago) and has shown nothing since.')
    lines = [
        first,
        f'Target seed (system observation, first lock): camera {ctx["seed"]["camera_id"]} at t={ctx["seed"]["t_s"]:.1f} s, '
        f'tracker colour labels: {", ".join(ctx["seed"]["colors"]) or "none"}.',
        f'Camera graph [{GRAPH_STATUS}] neighbours of {ctx["last_camera"]}: {", ".join(ctx["neighbours"]) or "none"}'
        + (' (graph is INFORMATION ONLY: any listed camera may be chosen, even without an edge).' if ctx.get('graph_info_only') else '.'),
        'Candidate cameras ' + ('(all cameras of the site)' if ctx.get('graph_info_only') else '(the last camera and its graph neighbours)')
        + ' with person detections at this instant (id, box x0,y0,x1,y1 px, score, tracker colour labels):']
    for cam in ctx['allowed']:
        dets = ctx['dets'].get(cam, [])
        if not dets:
            lines.append(f'- {cam}: no person detection')
        for d in dets:
            lines.append(f'- {cam} {d.id}: box [{d.box[0]:.0f},{d.box[1]:.0f},{d.box[2]:.0f},{d.box[3]:.0f}] score {d.score:.2f} '
                         f'colours {",".join(d.colors) or "none"}')
    if with_images:
        lines.append('Images follow in this order: seed crop; last-known frame (tracker box in green); then one current frame per '
                     'candidate camera in the order above (detections drawn as numbered boxes).')
    else:
        lines.append('No images are available; decide from the text only.')
    return '\n'.join(lines)
