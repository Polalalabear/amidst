"""E5 A-open request, validation and lifecycle. Transport injection never adopts rule decisions.

Production transport is created only by e5_run.guarded_transport (ApiGuard); tests inject local fakes.
The full E5_EXTRA below must be copied to the preregistration appendix by Claude before any pilot.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from copy import deepcopy

from amidst.live_mode.advisor import crop_jpeg
from amidst.live_mode.people import PeopleTracker
from amidst.live_mode.service_decider import _jpeg
from amidst.q1q5 import agent_service as ag
from amidst.q1q5 import scene_context as sx

from .neutral import NeutralTracker, chain_box

MODEL = 'gpt-6.1-terra'
E5_EXTRA = '''
E5 A-OPEN OVERRIDES (apply instead of conflicting format or pixel-size instructions above):
You directly control the target. SELECT any listed (camera_id, detection_id), or OWN_BOX a missed person.
Your selected or drawn box becomes the target without rule colour, score, graph or distance vetoes.
All request frames are 320x180 pixels, NOT 960x540. OWN_BOX uses these actual pixels:
0 <= x0 < x1 <= 320 and 0 <= y0 < y1 <= 180. Do not rescale coordinates.
Candidates are frozen person detections with score >= 0.15 (CAM_ENTRY >= 0.05).
Rule gates and rule_state are information only; AO_STATE describes the independently displayed target.
Between your answers a neutral tracker follows only same-camera IoU >= 0.3, coasts two ticks,
then becomes LOST. It never switches cameras or chooses a new target by itself.
Return exactly one JSON object with these fields:
{"answer":"SELECT|OWN_BOX|NOT_VISIBLE|UNCERTAIN|STILL_HERE_OCCLUDED",
 "camera_id":null,"detection_id":null,"box_xyxy":null,"next_camera_ranking":[],
 "confidence":"low|medium|high","reason_codes":[],"reason":"short explanation"}.
Use one answer value, not the pipe-separated list. SELECT requires camera_id and detection_id.
OWN_BOX requires camera_id and box_xyxy. Every answer must include next_camera_ranking:
at most three known camera IDs, most likely first. This ranking drives the next search order.
If you cannot judge, answer UNCERTAIN: the current target is unchanged. If the target is absent
from all shown frames, answer NOT_VISIBLE: clear the target, but still provide your ranking.
STILL_HERE_OCCLUDED is valid only for the current target's camera and an existing target.
It holds only the last ground position, without a box, for ten ticks (2 seconds); no automatic
reacquisition occurs during that hold. UNCERTAIN does not extend it. A new valid OCCLUDED restarts
that hold; SELECT/OWN_BOX takes over; NOT_VISIBLE clears it.
Identity remains UNCONFIRMED. Scene edges do not certify physical traversal or collision safety.
'''.strip()
ANSWERS = {'SELECT', 'OWN_BOX', 'NOT_VISIBLE', 'UNCERTAIN', 'STILL_HERE_OCCLUDED'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def parse_answer(text, inp, size=(320, 180)):
    try:
        doc = json.loads(text)
    except (ValueError, TypeError):
        return None, 'FORMAT_INVALID'
    if not isinstance(doc, dict) or not isinstance(doc.get('answer'), str) or doc['answer'] not in ANSWERS:
        return None, 'FORMAT_INVALID'
    cams = {cam for cam, _ in inp.frames}
    cam, detection = doc.get('camera_id'), doc.get('detection_id')
    answer = doc['answer']
    if answer == 'SELECT' and not any(c.camera_id == cam and c.id == detection for c in inp.candidates):
        return None, 'UNKNOWN_DETECTION'
    box = doc.get('box_xyxy')
    if answer == 'OWN_BOX':
        try:
            finite = isinstance(box, list) and all(type(x) in (int, float) and math.isfinite(x) for x in box)
        except OverflowError:
            finite = False
        if not (isinstance(box, list) and len(box) == 4
                and finite
                and 0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1]
                and isinstance(cam, str) and cam in cams):
            return None, 'BAD_OWN_BOX'
    if answer == 'STILL_HERE_OCCLUDED' and (not isinstance(cam, str) or cam not in cams):
        return None, 'BAD_CAMERA'
    rank = []
    raw = doc.get('next_camera_ranking')
    if isinstance(raw, list):
        for c in raw:
            if isinstance(c, str) and c in cams and c not in rank:
                rank.append(c)
    codes = doc.get('reason_codes')
    return {'answer': answer, 'camera_id': cam if answer in ('SELECT', 'OWN_BOX', 'STILL_HERE_OCCLUDED') else None,
            'detection_id': detection if answer == 'SELECT' else None,
            'box_xyxy': list(box) if answer == 'OWN_BOX' else None, 'next_camera_ranking': rank[:3],
            'ranking_supplied': bool(rank), 'next_camera_hint_raw': doc.get('next_camera_hint'),
            'confidence': doc.get('confidence'), 'reason_codes': [str(c)[:40] for c in codes][:4] if isinstance(codes, list) else [],
            'reason': str(doc.get('reason', ''))[:200]}, None


class AOpenDecider:
    """One synchronous transport call, then delayed application on the replay capture clock.

    Like E3 Recording(run_async=False), simlive measures the model synchronously but releases its
    answer only at the first capture tick strictly after its measured latency. No wall-clock sleep.
    """
    def __init__(self, transport, scene, projector, *, mode='offline', poll_s=2.0, min_interval_s=1.0,
                 call_cap=1, timeout_s=30.0, size=(320, 180), wall_clock=time.monotonic):
        if mode not in ('offline', 'simlive'):
            raise ValueError('BAD_MODE')
        if any(not math.isfinite(x) or x <= 0 for x in (poll_s, min_interval_s, timeout_s)) or call_cap < 0:
            raise ValueError('BAD_LIMIT')
        if tuple(size) != (320, 180):
            raise ValueError('E5_FRAME_SIZE')
        self.transport, self.scene, self.mode = transport, scene, mode
        self.poll_s, self.min_interval_s, self.call_cap, self.timeout_s = poll_s, min_interval_s, call_cap, timeout_s
        self.size, self.wall_clock = size, wall_clock
        self.neutral = NeutralTracker(projector, size)
        self.reference = None
        self.ranking, self.calls = [], []
        self.pending = None
        self.last_ask_tick = None
        self.cap_recorded = False
        self.seed_tick = None
        self.seed_people = PeopleTracker()
        self.budget_exhausted = False

    def build_input(self, tick, frames, dets, rule_state):
        cands, shots = [], []
        order = [c for c in self.ranking if c in frames] + [c for c in frames if c not in self.ranking]
        for cam in order:
            boxes = []
            for d in dets.get(cam, []):
                cid = f'D{len(boxes) + 1}'
                colors = tuple(c for c in ('red', 'blue') if d.get('color') == c or d.get(c) in ('STRONG', 'WEAK'))
                cands.append(ag.Candidate(cid, cam, tuple(d['bbox']), float(d['score']), 'person', colors))
                boxes.append((cid, d['bbox']))
            shots.append((cam, _jpeg(frames[cam], boxes)))
        rule = {k: deepcopy(rule_state.get(k)) for k in ('state', 'active_cam', 'lost_ticks')}
        inp = ag.DecisionInput(self.scene, tick / 5, cands, seed_colors=('red',), reference_jpeg=self.reference,
                               frames=shots, rule_display={'kind': rule['state'], 'camera_id': rule['active_cam']},
                               rule_answer=rule, last_camera=self.neutral.tracking()['active_cam'])
        body = ag.build_body(MODEL, inp)
        prefix = body['input'][0]['content'][0]['text']
        body['input'][0]['content'][0]['text'] = prefix + '\n\n' + E5_EXTRA
        var = ag.variable_text(inp).replace('DETECTIONS (all classes with score>=0.3;',
                                           'DETECTIONS (person score>=0.15, CAM_ENTRY>=0.05;')
        var += '\nAO_STATE=' + json.dumps({'tracking': self.neutral.tracking(), 'neutral_status': self.neutral.status,
                                          'ranking': self.ranking}, sort_keys=True)
        body['input'][-1]['content'][0]['text'] = var
        request = {'t_s': tick / 5, 'images': {c: sha(b) for c, b in shots}, 'reference': sha(self.reference),
                   'candidates': len(cands), 'candidate_list': [
                       {'detection_id': c.id, 'camera_id': c.camera_id, 'box': list(c.box), 'score': c.score,
                        'class_label': c.class_label, 'colors': list(c.colors), **ag.gate_of(c, inp.seed_colors)} for c in cands],
                   'variable_text': var, 'prefix_sha256': sha((prefix + '\n\n' + E5_EXTRA).encode()), 'rule_state': rule,
                   'body_sha256': sha(json.dumps(body, sort_keys=True).encode())}
        return inp, body, request

    def _ask(self, tick, kind, frames, dets, rule_state):
        inp, body, request = self.build_input(tick, frames, dets, rule_state)
        rec = {'tick': tick, 'ask_tick': tick, 'kind': kind, 'answer': None, 'camera_id': None, 'detection_id': None,
               'box_xyxy': None, 'next_camera_ranking': [], 'ranking_supplied': False, 'next_camera_hint_raw': None,
               'confidence': None, 'reason_codes': [], 'reason': '', 'applied': False, 'source': 'NEUTRAL',
               'fallback_reason': None, 'usage': {}, 'scene_context_sha256': sx.sha256_of(self.scene), 'request': request,
               'error': None, 'model': MODEL, 'pending_at_end': True}
        t0 = self.wall_clock()
        try:
            response = self.transport(body)
            elapsed = self.wall_clock() - t0
            measured = response.get('latency_s', elapsed)
            latency = float(measured) if measured is not None else elapsed
            if not math.isfinite(latency) or latency < 0:
                raise ValueError('BAD_LATENCY')
            rec['usage'] = response.get('usage') or {}
            if max(elapsed, latency) > self.timeout_s:
                rec['fallback_reason'] = 'PROVIDER_TIMEOUT'
            else:
                ans, err = parse_answer(response.get('text'), inp, self.size)
                rec['fallback_reason'] = err
                if ans is not None:
                    rec.update(ans, source='AGENT')
        except Exception as exc:  # transport/ApiGuard failures never change the target
            elapsed = self.wall_clock() - t0
            latency = elapsed
            msg = str(exc)
            rec['error'] = type(exc).__name__ + ':' + msg[:200]
            rec['fallback_reason'] = ('CALL_BUDGET_EXHAUSTED' if isinstance(exc, PermissionError) and msg.startswith('GUARD_DENIED:')
                                      else 'PROVIDER_TIMEOUT' if isinstance(exc, TimeoutError) else 'PROVIDER_ERROR')
        # Preserve measured model latency (same convention as E3); elapsed also bounds timeout.
        rec.update(latency_ms=round(latency * 1000), model_latency_s=latency)
        self.budget_exhausted = rec['fallback_reason'] == 'CALL_BUDGET_EXHAUSTED'
        self.calls.append(rec)
        self.pending = {'rec': rec, 'inp': inp, 'tick': tick, 'history': [],
                        'delay_s': min(latency, self.timeout_s) if self.mode == 'simlive' else 0}
        self.last_ask_tick = tick

    def _poll(self, tick):
        p = self.pending
        if p is None or tick <= p['tick'] or (tick - p['tick']) / 5 <= p['delay_s']:
            return None
        self.pending = None
        r, inp = p['rec'], p['inp']
        r.update(tick=tick, applied_tick=tick, pending_at_end=False)
        if r['fallback_reason'] is not None:
            return r
        ans, cam = r['answer'], r['camera_id']
        if ans in ('SELECT', 'OWN_BOX'):
            box = (next(list(c.box) for c in inp.candidates if c.camera_id == cam and c.id == r['detection_id'])
                   if ans == 'SELECT' else r['box_xyxy'])
            if self.mode == 'simlive':
                box = chain_box(box, cam, p['history'])
                r['ticks_chained'] = len(p['history'])
                if box is None:
                    r.update(source='NEUTRAL', fallback_reason='EXPIRED')
                    return r
            self.neutral.adopt(tick, cam, box, 'AGENT_' + ans)
            r['applied'] = True
        elif ans == 'NOT_VISIBLE':
            self.neutral.clear()
            r['applied'] = True
        elif ans == 'STILL_HERE_OCCLUDED':
            r['applied'] = self.neutral.occlude(tick, cam)
            if not r['applied']:
                r.update(source='NEUTRAL', fallback_reason='OCCLUDED_NO_TARGET')
        # EXPIRED returned above: only accepted answers can steer later requests.
        # OCCLUDED_NO_TARGET remains a valid call, as specified by the Opus ruling.
        self.ranking = list(r['next_camera_ranking'])
        return r

    def step(self, tick, dets, frames, rule_state):
        events, source = [], 'NEUTRAL' if self.neutral.target else 'NONE'
        prev_cam = self.neutral.tracking()['active_cam']
        if self.pending is not None:
            self.pending['history'].append({c: [{'bbox': list(d['bbox'])} for d in ds] for c, ds in dets.items()})
        self.neutral.step(tick, self.neutral.target, dets)
        result = self._poll(tick)
        if result is not None:
            source = result['source']
            events.append({'tick': tick, 'type': 'ADJUDICATED', 'cam': result['camera_id'],
                           'detail': {k: result[k] for k in ('answer', 'applied', 'fallback_reason', 'source')}})
            cam = self.neutral.tracking()['active_cam']
            if result['applied'] and cam is not None and cam != prev_cam:
                events.append({'tick': tick, 'type': 'ACQUIRE' if prev_cam is None else 'SWITCH', 'cam': cam,
                               'detail': {'from': prev_cam, 'by': 'AGENT'}})
        if self.reference is None:
            # The E3 reference crop uses PeopleTracker only for the B1 seed. These groups never
            # filter AO candidates or participate in neutral continuation or answer adoption.
            people = self.seed_people.update(tick / 5, [(c, d, d['est_xy']) for c, ds in dets.items()
                                                        for d in ds if d.get('est_xy') is not None])
            if any(e['type'] == 'ACQUIRE' for e in rule_state.get('events', [])) and rule_state.get('est_xy') and people:
                p = min(people, key=lambda q: math.dist(q['xy'], rule_state['est_xy']))
                ref_cam, ref_det = next(((c, d) for c, d in p['dets'] if c == rule_state.get('active_cam')),
                                        max(p['dets'], key=lambda cd: cd[1]['bbox'][3] - cd[1]['bbox'][1]))
                if ref_cam in frames:
                    self.reference = crop_jpeg(frames[ref_cam], ref_det['bbox'])
                    self.seed_tick = tick
        if self.reference is not None and self.pending is None and not self.budget_exhausted:
            elapsed = math.inf if self.last_ask_tick is None else (tick - self.last_ask_tick) / 5
            kind = ('FIRST' if self.last_ask_tick is None else 'LOST_EARLY' if self.neutral.tracking()['state'] == 'LOST'
                    and elapsed >= self.min_interval_s else 'POLL' if elapsed >= max(self.poll_s, self.min_interval_s) else None)
            if kind is not None:
                if len(self.calls) >= self.call_cap:
                    if not self.cap_recorded:
                        events.append({'tick': tick, 'type': 'CALL_CAP_REACHED', 'cam': None, 'detail': {}})
                        self.cap_recorded = True
                else:
                    self._ask(tick, kind, frames, dets, rule_state)
                    events.append({'tick': tick, 'type': 'ADJUDICATE_ASK', 'cam': None, 'detail': {'kind': kind}})
                    if len(self.calls) == self.call_cap and not self.cap_recorded:
                        events.append({'tick': tick, 'type': 'CALL_CAP_REACHED', 'cam': None, 'detail': {}})
                        self.cap_recorded = True
        if self.neutral.reason:
            events.append({'tick': tick, 'type': self.neutral.reason, 'cam': None, 'detail': {}})
        if result is None:
            source = 'NEUTRAL' if self.neutral.target else 'NONE'
        return {'tick': tick, 'tracking': self.neutral.tracking(), 'ranking': list(self.ranking),
                'decision_source': source, 'neutral_status': self.neutral.status, 'events': events}
