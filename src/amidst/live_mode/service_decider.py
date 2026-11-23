"""F3 (#657, H6): LIVE Agent mode decided by ``agent_service`` (``--advisor agent``; D340). review/lead/off are unchanged.

The image advisor (advisor.py) only asks when the rule has already put the target in a shortlist: red people only (L224), a
SILENT_PICK needs two people within the 3 m gate (L284), a LOST question needs two candidates (L286-287), and the request is two
images and a count (C7 in AGENT_VS_RULE_HYPOTHESES_20261120 §4.2). In agent mode none of these gates remove anyone:

* every detected person is a candidate, any colour; colour, score and distance are listed as information;
* the Agent is asked with zero, one or many people in view, when the target is lost, and every ``recheck_s`` while tracked;
* the request has the scene context (graph with approval levels, camera poses/FOV/footprints) and every camera's current frame
  with numbered boxes; it may answer SELECT, STILL_HERE_OCCLUDED or NOT_VISIBLE (+ next camera).

Every paid call goes through ApiGuard (``guarded_responses_transport``). Denials, timeouts and invalid replies fall back to the rule
tracker (RULE_FALLBACK + fallback_reason). Identity stays UNCONFIRMED; only camera pixels and calibration-derived data leave.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import threading
import time
import urllib.request

from amidst.q1q5 import agent_service as ag

from .advisor import GUARD_REASON, crop_jpeg

RESPONSES_URL = 'https://api.openai.com/v1/responses'
MAX_OUT = 1500


def _jpeg(img, boxes) -> bytes:
    from PIL import ImageDraw
    im = img.convert('RGB').copy()
    d = ImageDraw.Draw(im)
    t = max(2, im.width // 320)
    for cid, (x0, y0, x1, y1) in boxes:
        d.rectangle([x0, y0, x1, y1], outline=(255, 220, 0), width=t)
        d.rectangle([x0, y0, x0 + 26, y0 + 14], fill=(255, 220, 0))
        d.text((x0 + 3, y0 + 1), cid, fill=(0, 0, 0))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=85)
    return buf.getvalue()


def guarded_responses_transport(guard, api_model: str, timeout_s: float, *, env=None, opener=urllib.request.urlopen):
    """agent_service transport for the LIVE server: one Responses call inside ``ApiGuard.run``; the key is read at call time only."""
    env = os.environ if env is None else env

    def transport(body):
        est = max(500, sum(len(p.get('text', '')) for it in body['input'] for p in it['content'] if p.get('type') == 'input_text') // 3
                  + 1100 * sum(1 for it in body['input'] for p in it['content'] if p.get('type') == 'input_image'))
        from amidst.q1q5.api_budget import estimate_run
        cfg = getattr(guard, 'config', None)
        transport.last_estimate = estimate_run(questions=1, model=api_model, avg_prompt_tokens=est,
                                               avg_output_tokens=body['max_output_tokens'],
                                               prices=cfg.prices if cfg is not None else None, config=cfg)

        def fn():
            key = env.get('OPENAI_API_KEY', '').strip()
            if not key:
                raise PermissionError('NO_API_KEY')
            t0 = time.time()
            req = urllib.request.Request(RESPONSES_URL, data=json.dumps(body).encode(), method='POST',
                                         headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
            with opener(req, timeout=timeout_s) as resp:
                out = ag.parse_response(json.loads(resp.read()))
            out['latency_s'] = round(time.time() - t0, 3)
            return out, out['usage'].get('input_tokens'), out['usage'].get('output_tokens')
        g = guard.run('live_agent', api_model, est, body['max_output_tokens'], fn)
        if not g.allowed:
            raise PermissionError('GUARD_DENIED:' + str(g.reason))
        return g.value
    return transport


def fallback_of(record: ag.DecisionRecord) -> str:
    reason, err = record.fallback_reason or '', record.error or ''
    if reason.startswith('INVALID_RESPONSE'):
        return 'INVALID_RESPONSE'
    if 'Timeout' in reason or 'timed out' in err:
        return 'PROVIDER_TIMEOUT'
    if err.startswith('GUARD_DENIED:'):
        return GUARD_REASON.get(err.split(':', 1)[1], 'PROVIDER_UNAVAILABLE')
    if err == 'NO_API_KEY' or reason == 'NO_TRANSPORT':
        return 'MODE_NOT_AUTHORIZED'
    return 'PROVIDER_UNAVAILABLE'


class ServiceLiveDecider:
    """Same ``step`` contract as advisor.LiveDecider. One question at a time, asked in a worker thread."""

    any_color = True        # server: run for any target colour (the image advisor runs for red only)
    mode = 'agent'

    def __init__(self, transport, people, scene_context=None, *, model: str = 'gpt-6.1-terra', timeout_s: float = 12.0, recheck_s: float = 4.0,
                 lost_ticks_before_ask: int = 2, min_interval_s: float = 1.0, lock_keep_s: float = 1.5, gate_m: float = 3.0,
                 clock=time.monotonic, run_async: bool = True):
        self.transport, self.people, self.scene_context, self.model = transport, people, scene_context, model
        self.timeout_s, self.recheck, self.lost_n, self.min_interval, self.keep, self.gate = timeout_s, recheck_s, lost_ticks_before_ask, min_interval_s, lock_keep_s, gate_m
        self.clock, self.run_async = clock, run_async
        self.reference = None
        self._lock = threading.Lock()
        self._pending = None
        self._done = None
        self._seq = 0
        self._last_end = -1e9
        self.last = None
        self.last_t = -1e9
        self.ask_t = -1e9
        self.locked = None
        self.lock_seen = -1e9
        self.lock_xy = None
        self.prev_est = None
        self.next_camera_hint = None
        self.calls = 0
        self.records = []

    # ------------------------------------------------------------------------------------------- question lifecycle
    def busy(self):
        return self._pending is not None

    def _ask(self, inp, ids, kind):
        self._seq += 1
        self._pending = {'seq': self._seq, 't0': self.clock(), 'ids': ids, 'kind': kind}
        self.calls += 1
        args = (self._seq, inp)
        if self.run_async:
            threading.Thread(target=self._work, args=args, daemon=True).start()
        else:
            self._work(*args)

    def _work(self, seq, inp):
        request_sha = None
        def recorded_transport(body):
            nonlocal request_sha
            request_sha = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
            return self.transport(body)
        try:
            rec = ag.decide(inp, mode='AGENT', transport=recorded_transport, model=self.model)
        except Exception as exc:  # noqa: BLE001 - never break tracking
            rec = ag.DecisionRecord('RULE', True, False, True, 'TRANSPORT:' + type(exc).__name__, None, None, error=str(exc)[:200])
        with self._lock:
            if self._pending is not None and self._pending['seq'] == seq:
                self._pending['request_sha256'] = request_sha
                self._done = rec

    def _poll(self):
        p = self._pending
        if p is None:
            return None
        with self._lock:
            rec, self._done = self._done, None
        elapsed = self.clock() - p['t0']
        if rec is None and elapsed <= self.timeout_s:
            return None
        if elapsed > self.timeout_s:
            rec = ag.DecisionRecord('RULE', True, False, True, 'TIME_BUDGET', None, None)
        self._pending = None
        self._last_end = self.clock()
        return p, rec, round(elapsed * 1000)

    # ------------------------------------------------------------------------------------------- request
    def build_input(self, t_s, people, frames, tracking):
        cands, ids, shots = [], {}, []
        for cam in sorted(frames):
            boxes = []
            for p in people:
                for c, det in p['dets']:
                    if c != cam:
                        continue
                    cid = f'D{len(boxes) + 1}'
                    ids[(cam, cid)] = p['pid']
                    colors = tuple(sorted(k for k in ('red', 'blue') if det.get('color') == k or det.get(k) in ('STRONG', 'WEAK')))
                    cands.append(ag.Candidate(cid, cam, tuple(det['bbox']), float(det.get('score', 1.0)), 'person', colors))
                    boxes.append((cid, det['bbox']))
            shots.append((cam, _jpeg(frames[cam], boxes)))
        return ag.DecisionInput(
            scene_context=self.scene_context, t_s=t_s, candidates=cands, seed_colors=tuple(c for c in [tracking.get('target', {}).get('color')] if c),
            reference_jpeg=self.reference, frames=shots,
            rule_display={'kind': tracking.get('state'), 'camera_id': tracking.get('active_cam'), 'last_t_s': None},
            rule_answer={'state': tracking.get('state'), 'active_cam': tracking.get('active_cam'), 'lost_ticks': tracking.get('lost_ticks')},
            last_camera=tracking.get('active_cam'), include_scene=self.scene_context is not None), ids

    # ------------------------------------------------------------------------------------------- one tick
    def step(self, tick, t_s, tracker, tracking, dets, frames):
        out, events = dict(tracking), list(tracking.get('events') or [])
        cands = [(cam, d, d['est_xy']) for cam, lst in dets.items() for d in lst if d.get('est_xy')]     # every person, any colour
        people = self.people.update(t_s, cands)
        by_pid = {p['pid']: p for p in people}
        if any(e['type'] == 'ACQUIRE' for e in events) and out.get('est_xy') and people:
            p = min(people, key=lambda q: math.dist(q['xy'], out['est_xy']))
            cam, det = next(((c, d) for c, d in p['dets'] if c == out.get('active_cam')), max(p['dets'], key=lambda cd: cd[1]['bbox'][3] - cd[1]['bbox'][1]))
            if cam in frames:
                self.reference = crop_jpeg(frames[cam], det['bbox'])
            self.locked = None
        res = self._poll()
        if res is not None:
            q, rec, ms = res
            applied = False
            ans = rec.answer if rec.agent_used else None
            source = 'AGENT' if rec.agent_used else 'RULE_FALLBACK'
            reason = None if rec.agent_used else ('TIME_BUDGET' if rec.fallback_reason == 'TIME_BUDGET' else fallback_of(rec))
            if ans is not None:
                self.next_camera_hint = ans.get('next_camera_hint')
                if ans['answer'] == 'SELECT':
                    pid = q['ids'].get((ans['camera_id'], ans['detection_id']))
                    seen = self.people.last_seen(pid) if pid is not None else None
                    if seen is not None and t_s - seen <= self.keep and not self.people.contested_since(pid, self.ask_t):
                        self.locked, self.lock_seen, self.lock_xy, applied = pid, seen, list(self.people.tracks[pid]['xy']), True
                    else:
                        source, reason = 'RULE_FALLBACK', 'TIME_BUDGET'
                elif ans['answer'] == 'NOT_VISIBLE':
                    self.locked = None
            self.last = {'kind': q['kind'], 'answer': ans and ans['answer'], 'camera_id': ans and ans.get('camera_id'),
                         'next_camera_hint': ans and ans.get('next_camera_hint'), 'reason': ans and ans.get('reason'),
                         'reason_codes': ans and ans.get('reason_codes'), 'latency_ms': ms, 'applied': applied, 'model': self.model,
                         'source': source, 'fallback_reason': reason, 'request_sha256': q.get('request_sha256'),
                         'identity_verdict': 'UNCONFIRMED'}
            self.last_t = t_s
            self.records.append({'tick': tick, **self.last, 'usage': rec.usage, 'scene_context_sha256': rec.scene_context_sha256})
            events.append({'tick': tick, 'type': 'ADJUDICATED', 'cam': ans and ans.get('camera_id'),
                           'detail': {'answer': ans and ans['answer'], 'applied': applied, 'source': source, 'latency_ms': ms}})
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
                self.locked = None                         # one correction; the rule tracker continues from here (reseed)
        matched = out.get('state') == 'TRACKING' and (out.get('lost_ticks') or 0) == 0
        lost = not matched and out.get('state') != 'SEARCHING' and (out.get('lost_ticks') or 0) >= self.lost_n
        near = [p for p in people if self.prev_est is not None and math.dist(p['xy'], self.prev_est) <= self.gate]
        kind = ('LOST' if lost else 'AMBIGUOUS' if matched and len(near) >= 2 else 'RECHECK' if matched and t_s - self.last_t >= self.recheck else None)
        if (kind and self.reference is not None and not self.busy() and self.clock() - self._last_end >= self.min_interval and frames):
            inp, ids = self.build_input(t_s, people, frames, out)
            self._ask(inp, ids, kind)
            self.ask_t = t_s
            events.append({'tick': tick, 'type': 'ADJUDICATE_ASK', 'cam': out.get('active_cam'),
                           'detail': {'kind': kind, 'candidates': len(inp.candidates), 'cameras': len(inp.frames)}})
        fresh = self.last is not None and t_s - self.last_t <= 3.0
        out['decision_source'] = (self.last['source'] if fresh else 'RULE_ONLY') if self.last else 'RULE_ONLY'
        out['fallback_reason'] = self.last['fallback_reason'] if fresh and self.last['source'] == 'RULE_FALLBACK' else None
        pm = None if self._pending is None else round((self.clock() - self._pending['t0']) * 1000)
        out['advisor'] = {'state': 'ASKING' if self.busy() else 'IDLE', 'pending_ms': pm, 'last': self.last, 'next_camera_hint': self.next_camera_hint}
        out['identity_verdict'] = 'UNCONFIRMED'
        out['events'] = events
        if out.get('est_xy'):
            self.prev_est = out['est_xy']
        return out
