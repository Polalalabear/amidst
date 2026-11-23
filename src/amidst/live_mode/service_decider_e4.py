"""E4 (#681, D355): conditional Agent override on the LIVE path. Exploratory; preregistration docs/evaluation/E4_PREREGISTRATION_20261123.md.

Same question lifecycle, people tracker, reference crop and ApiGuard transport as ``service_decider.ServiceLiveDecider`` (E3). Differences
(preregistration §3, every parameter fixed there):

* (a) trusted rule track: while the rule track is stable, a SELECT is only a candidate; it never reseeds the tracker;
* (b) conditional override: only when the rule is lost or degraded, and only after STALE / NOT_SEEN / CONTESTED / UNREACHABLE /
  APPEARANCE checks pass;
* (c) short-term memory of the last trusted position with a time limit (used for the reachability check only);
* (d) UNCERTAIN as its own answer, and ``next_camera_ranking`` (up to 3 cameras) on every answer;
* (e) every call records its candidate list, the chosen ``detection_id``, the variable request text, the prefix and image SHA-256s,
  the trust state and the validation result.

GT never enters this module. Identity stays UNCONFIRMED.
"""
from __future__ import annotations

import collections
import hashlib
import json
import math

from amidst.q1q5 import agent_service as ag

from .service_decider import ServiceLiveDecider

N_STABLE = 5            # ticks (1.0 s at 200 ms)
STEP_MAX_M = 1.0        # max estimate step per tick while stable
SCORE_MIN = 0.4         # display box score (the rule's linking threshold)
BOX_RADIUS_M = 1.5      # display box: nearest detection within this distance of the estimate (same rule as E3)
MAX_AGE_S = 1.0
SEEN_S = 0.6
REACH_MARGIN_M = 1.5
V_MAX = 2.0
MEMORY_TTL_S = 8.0
ANSWERS_E4 = ag.ANSWERS + ('UNCERTAIN',)

E4_EXTRA = (
    '\n\nE4 ADDENDUM (overrides the answer format above where they differ). '
    'Extra answer type "UNCERTAIN": you cannot tell whether any listed person is the target. '
    'If no listed person is clearly the target, answer NOT_VISIBLE (target out of every listed view) or UNCERTAIN (cannot tell). '
    'Selecting a different person is the most costly error; a missed SELECT is cheap because the rule tracker keeps running. '
    'Always add "next_camera_ranking": a list of up to 3 camera_id strings, most likely first, of where the target will be seen '
    'next (or now), for EVERY answer type, not only NOT_VISIBLE.')


def _sha(b: bytes | str) -> str:
    return hashlib.sha256(b.encode() if isinstance(b, str) else b).hexdigest()


def parse_e4(text: str, inp: ag.DecisionInput):
    """-> (answer, None) | (None, error). UNCERTAIN is accepted; every answer carries next_camera_ranking (filtered to known cameras)."""
    try:
        doc = json.loads(text)
    except (ValueError, TypeError):
        return None, 'NOT_JSON'
    if not isinstance(doc, dict) or doc.get('answer') not in ANSWERS_E4:
        return None, 'BAD_ANSWER_TYPE'
    cams = {c.camera_id for c in inp.candidates} | {cam for cam, _ in inp.frames} | ({inp.last_camera} if inp.last_camera else set())
    known = {c['camera_id'] for c in inp.scene_context['cameras']} if inp.scene_context else cams
    if doc['answer'] == 'UNCERTAIN':
        out = {'answer': 'UNCERTAIN', 'camera_id': None, 'detection_id': None, 'box_xyxy': None, 'next_camera_hint': None,
               'confidence': doc.get('confidence'), 'reason': str(doc.get('reason', ''))[:200],
               'reason_codes': [str(c)[:40] for c in doc.get('reason_codes') or []][:ag.MAX_REASON_CODES] if isinstance(doc.get('reason_codes'), list) else []}
    else:
        out, err = ag.parse_answer(text, inp)
        if out is None:
            return None, err
    raw = doc.get('next_camera_ranking')
    rank = []
    for c in raw if isinstance(raw, list) else []:
        if isinstance(c, str) and c in known and c not in rank:
            rank.append(c)
    if not rank and out.get('next_camera_hint'):
        rank = [out['next_camera_hint']]
    out['next_camera_ranking'] = rank[:3]
    out['ranking_supplied'] = isinstance(raw, list)
    return out, None


class ServiceLiveDeciderE4(ServiceLiveDecider):
    """Same ``step`` contract as ServiceLiveDecider."""

    mode = 'agent-e4'

    def __init__(self, *a, target_color: str = 'red', **k):
        super().__init__(*a, **k)
        self.target_color = target_color
        self._ok_hist = collections.deque(maxlen=N_STABLE)
        self._last_est = None
        self.trusted = False
        self.memory = None                # (xy, camera, t_s) of the last trusted tick
        self.next_camera_ranking = []
        self.calls_log, self.model_latency, self.chain_log = [], [], []
        self.prefix_sha256 = None

    # ------------------------------------------------------------------------------------------- request / transport
    def build_input(self, t_s, people, frames, tracking):
        inp, ids = super().build_input(t_s, people, frames, tracking)
        cands = [{'detection_id': c.id, 'camera_id': c.camera_id, 'box': list(c.box), 'score': c.score, 'colors': list(c.colors),
                  'pid': ids.get((c.camera_id, c.id))} for c in inp.candidates]
        var = ag.variable_text(inp)
        self.calls_log.append({'t_s': round(t_s, 3), 'images': {cam: _sha(b) for cam, b in inp.frames},
                               'reference': _sha(inp.reference_jpeg) if inp.reference_jpeg else None,
                               'candidates': len(inp.candidates), 'candidate_list': cands, 'scene': inp.include_scene,
                               'variable_text': var, 'trusted': self.trusted})
        return inp, ids

    def _work(self, seq, inp):
        sha = None
        try:
            from amidst.q1q5 import scene_context as sx
            sha = sx.sha256_of(inp.scene_context) if inp.scene_context else None
            body = ag.build_body(self.model, inp)
            dev = body['input'][0]['content'][0]
            dev['text'] = dev['text'] + E4_EXTRA
            self.prefix_sha256 = _sha(dev['text'])
            resp = self.transport(body)
            ans, err = parse_e4(resp.get('text', ''), inp)
            if ans is None:
                rec = ag.DecisionRecord('RULE', True, False, True, 'INVALID_RESPONSE:' + str(err), inp.rule_answer, sha, resp.get('usage'),
                                        resp.get('latency_s'), err)
            else:
                rec = ag.DecisionRecord('AGENT', True, True, False, None, ans, sha, resp.get('usage'), resp.get('latency_s'))
        except Exception as exc:  # noqa: BLE001 - guard denial / transport failure never breaks tracking
            rec = ag.DecisionRecord('RULE', True, False, True, 'TRANSPORT:' + type(exc).__name__, None, sha, error=str(exc)[:200])
        with self._lock:
            if self._pending is not None and self._pending['seq'] == seq:
                self._done = rec

    def _poll(self):
        with self._lock:
            rec = self._done
        res = super()._poll()
        if res is not None:
            self.model_latency.append(None if rec is None else rec.latency_s)
        return res

    # ------------------------------------------------------------------------------------------- (a) + (c)
    def _update_trust(self, t_s, out, dets):
        est, cam = out.get('est_xy'), out.get('active_cam')
        ok = out.get('state') == 'TRACKING' and not out.get('lost_ticks') and est is not None and cam is not None
        if ok and self._last_est is not None and math.dist(est, self._last_est) > STEP_MAX_M:
            ok = False
        if ok:
            near = [d for d in dets.get(cam, []) if d.get('est_xy') is not None and math.dist(d['est_xy'], est) <= BOX_RADIUS_M]
            box = min(near, key=lambda d: math.dist(d['est_xy'], est)) if near else None
            ok = box is not None and box.get('color') == self.target_color and float(box.get('score', 0.0)) >= SCORE_MIN
        self._ok_hist.append(ok)
        self._last_est = list(est) if est is not None else None
        self.trusted = len(self._ok_hist) == N_STABLE and all(self._ok_hist)
        if self.trusted:
            self.memory = (list(est), cam, t_s)
        return self.trusted

    # ------------------------------------------------------------------------------------------- (b)
    def _validate(self, ans, q, t_s, lost):
        if self.trusted and not lost:
            return 'CANDIDATE_ONLY_TRUSTED', None
        pid = q['ids'].get((ans['camera_id'], ans['detection_id']))
        if t_s - self.ask_t > MAX_AGE_S:
            return 'STALE', pid
        seen = self.people.last_seen(pid) if pid is not None else None
        if seen is None or t_s - seen > SEEN_S:
            return 'NOT_SEEN', pid
        if self.people.contested_since(pid, self.ask_t):
            return 'CONTESTED', pid
        xy = self.people.tracks[pid]['xy']
        fresh = self.memory is not None and t_s - self.memory[2] <= MEMORY_TTL_S
        if fresh and math.dist(xy, self.memory[0]) > REACH_MARGIN_M + V_MAX * (t_s - self.memory[2]):
            return 'UNREACHABLE', pid
        if not fresh and ans.get('confidence') != 'high':
            return 'MEMORY_EXPIRED_LOW_CONFIDENCE', pid
        person = next((p for p in getattr(self.people, 'latest', None) or [] if p['pid'] == pid), None)
        colour_ok = person is not None and any(d.get('color') == self.target_color for _, d in person['dets'])
        if not colour_ok and ans.get('confidence') != 'high':
            return 'APPEARANCE', pid
        return 'APPLIED', pid

    # ------------------------------------------------------------------------------------------- one tick
    def step(self, tick, t_s, tracker, tracking, dets, frames):
        out, events = dict(tracking), list(tracking.get('events') or [])
        cands = [(cam, d, d['est_xy']) for cam, lst in dets.items() for d in lst if d.get('est_xy')]
        people = self.people.update(t_s, cands)
        self.people.latest = people
        by_pid = {p['pid']: p for p in people}
        if any(e['type'] == 'ACQUIRE' for e in events) and out.get('est_xy') and people:
            from .advisor import crop_jpeg
            p = min(people, key=lambda r: math.dist(r['xy'], out['est_xy']))
            cam, det = next(((c, d) for c, d in p['dets'] if c == out.get('active_cam')), max(p['dets'], key=lambda cd: cd[1]['bbox'][3] - cd[1]['bbox'][1]))
            if cam in frames:
                self.reference = crop_jpeg(frames[cam], det['bbox'])
            self.locked = None
        trusted = self._update_trust(t_s, out, dets)
        matched = out.get('state') == 'TRACKING' and (out.get('lost_ticks') or 0) == 0
        lost = not matched and (out.get('state') == 'SEARCHING' or (out.get('lost_ticks') or 0) >= self.lost_n)
        res = self._poll()
        if res is not None:
            q, rec, ms = res
            applied, validation, pid = False, None, None
            ans = rec.answer if rec.agent_used else None
            source = 'AGENT' if rec.agent_used else 'RULE_FALLBACK'
            from .service_decider import fallback_of
            reason = None if rec.agent_used else ('TIME_BUDGET' if rec.fallback_reason == 'TIME_BUDGET' else fallback_of(rec))
            if ans is not None:
                self.next_camera_ranking = list(ans.get('next_camera_ranking') or [])
                self.next_camera_hint = self.next_camera_ranking[0] if self.next_camera_ranking else None
                if ans['answer'] == 'SELECT':
                    validation, pid = self._validate(ans, q, t_s, lost)
                    if validation == 'APPLIED':
                        self.locked, self.lock_seen, self.lock_xy, applied = pid, self.people.last_seen(pid), list(self.people.tracks[pid]['xy']), True
                elif ans['answer'] == 'NOT_VISIBLE':
                    validation = 'NOT_VISIBLE_IGNORED_TRUSTED' if trusted and not lost else 'NOT_VISIBLE_RELEASED'
                    if validation == 'NOT_VISIBLE_RELEASED':
                        self.locked = None
                elif ans['answer'] == 'UNCERTAIN':
                    validation = 'UNCERTAIN'
                else:
                    validation = 'RECORDED_ONLY'          # OWN_BOX / STILL_HERE_OCCLUDED: recorded, not applied (as E3)
            self.last = {'kind': q['kind'], 'answer': ans and ans['answer'], 'camera_id': ans and ans.get('camera_id'),
                         'detection_id': ans and ans.get('detection_id'), 'pid': pid, 'confidence': ans and ans.get('confidence'),
                         'next_camera_hint': self.next_camera_hint if ans else None, 'next_camera_ranking': ans and ans.get('next_camera_ranking'),
                         'ranking_supplied': ans and ans.get('ranking_supplied'), 'reason': ans and ans.get('reason'),
                         'reason_codes': ans and ans.get('reason_codes'), 'latency_ms': ms, 'applied': applied, 'model': self.model,
                         'source': source, 'fallback_reason': reason, 'validation': validation, 'trusted': trusted, 'lost': lost,
                         'error': rec.error, 'prefix_sha256': self.prefix_sha256}
            self.last_t = t_s
            self.records.append({'tick': tick, **self.last, 'usage': rec.usage, 'scene_context_sha256': rec.scene_context_sha256})
            events.append({'tick': tick, 'type': 'ADJUDICATED', 'cam': ans and ans.get('camera_id'),
                           'detail': {'answer': ans and ans['answer'], 'applied': applied, 'source': source, 'latency_ms': ms, 'validation': validation}})
        if self.locked is not None:
            me = by_pid.get(self.locked)
            if me is not None:
                cam = max(me['dets'], key=lambda cd: cd[1]['bbox'][3] - cd[1]['bbox'][1])[0]
                prev = tracker.active
                tracker.est, tracker.state, tracker.lost, tracker.active = list(me['xy']), 'TRACKING', 0, cam
                tracker.last_seen[cam] = tick
                tracker.t_seen = t_s
                out.update(state='TRACKING', est_xy=list(me['xy']), active_cam=cam, seen_cams=sorted({c for c, _ in me['dets']}), lost_ticks=0)
                if prev is not None and cam != prev:
                    events.append({'tick': tick, 'type': 'SWITCH', 'cam': cam, 'detail': {'from': prev, 'by': 'AGENT'}})
            self.locked = None
        kind = ('LOST' if lost else 'DEGRADED' if matched and not trusted else 'RECHECK' if matched and t_s - self.last_t >= self.recheck else None)
        if kind and self.reference is not None and not self.busy() and self.clock() - self._last_end >= self.min_interval and frames:
            inp, ids = self.build_input(t_s, people, frames, out)
            self._ask(inp, ids, kind)
            self.ask_t = t_s
            events.append({'tick': tick, 'type': 'ADJUDICATE_ASK', 'cam': out.get('active_cam'),
                           'detail': {'kind': kind, 'candidates': len(inp.candidates), 'cameras': len(inp.frames), 'trusted': trusted}})
        fresh = self.last is not None and t_s - self.last_t <= 3.0
        out['decision_source'] = (self.last['source'] if fresh else 'RULE_ONLY') if self.last else 'RULE_ONLY'
        out['fallback_reason'] = self.last['fallback_reason'] if fresh and self.last['source'] == 'RULE_FALLBACK' else None
        pm = None if self._pending is None else round((self.clock() - self._pending['t0']) * 1000)
        out['advisor'] = {'state': 'ASKING' if self.busy() else 'IDLE', 'pending_ms': pm, 'last': self.last,
                          'next_camera_hint': self.next_camera_hint, 'next_camera_ranking': list(self.next_camera_ranking), 'trusted': trusted}
        out['events'] = events
        if out.get('est_xy'):
            self.prev_est = out['est_xy']
        return out
