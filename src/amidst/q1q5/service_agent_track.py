"""F3 (#657, X2): agent_service decider for the 8785 main tracking screen (``q_core_track`` -> ``cross_camera_demo.associate``).

``associate(..., decider=ServiceTrackDecider(...))`` with ``agent_mode=True``: at a loss the model decides (see associate), with every
index detection of every camera at that time (score >= 0.3, all classes; C5), annotated frames, the reference crop and the scene
context. SELECT of a detection that belongs to a local track adopts that track, also one the rule rejects (RULE_OVERRIDE recorded).
STILL_HERE_OCCLUDED / NOT_VISIBLE / a box with no local track -> WAIT (stay lost; the rule does not cut on its own meanwhile).
A failed call -> None: the rule decides that loss (RULE_FALLBACK, with the contract fallback_reason in the audit row).

Cadence (cost): asked at the first lost time of an episode, again when the set of candidate tracks changes, and at most every
``recheck_us`` otherwise. Answers are cached by (time, candidate set) for the life of the decider, so replaying the same run (every
``q_core_track`` call recomputes from the start) never pays twice. Identity stays UNCONFIRMED; no GT enters.
"""
from __future__ import annotations

import time

from amidst.q1q5 import agent_service as ag
from amidst.q1q5.service_agent_q5 import annotate, body_sha256, colors_of, crop_jpeg, fallback_code

AUDIT_REASON = 'AGENT_SERVICE_DECISION'
RECHECK_US = 1_000_000


class ServiceTrackDecider:
    agent_mode = True

    def __init__(self, transport, index_records, *, scene_context=None, frame_reader=None, model: str = 'gpt-6.1-terra',
                 recheck_us: int = RECHECK_US, max_calls: int = 60, cameras=None):
        self.transport, self.scene_context, self.frame_reader, self.model = transport, scene_context, frame_reader, model
        self.recheck_us, self.max_calls = recheck_us, max_calls
        self.rows = {}
        self.obs = {}
        for r in index_records:
            if r.get('frame_state') != 'INFERRED' or (cameras and r['camera_id'] not in cameras):
                continue
            self.rows.setdefault(r['timestamp_us'], {})[r['camera_id']] = r
            for o in r['detections'] or []:
                self.obs[o['observation_id']] = (r, o)
        self.cache = {}
        self.calls = 0
        self.records = []
        self._episode = None          # (current track_ref, last asked time, candidate set)
        self._reference = {}
        self._served = set()

    # ------------------------------------------------------------------------------------------- associate() protocol
    def continuation(self, ctx):
        return None, None

    def handoff(self, ctx):
        t, cur = ctx['timestamp_us'], ctx['current']
        considered = ctx['considered']
        refs = tuple(sorted(c['track'].track_ref for c in considered))
        key = (t, cur.track_ref, refs)
        if key not in self.cache:
            ep = self._episode
            due = (ep is None or ep[0] != cur.track_ref or ep[2] != refs or t - ep[1] >= self.recheck_us)
            if not due:                 # cached too, so a replay of the same run takes exactly the same path (and pays nothing)
                self.cache[key] = (None, None) if ep[3] else (('WAIT', None), None)   # after a failed call the rule keeps deciding
                return self.cache[key]
            if self.calls >= self.max_calls:
                self.cache[key] = (None, {'reason': AUDIT_REASON, 'timestamp_us': t, 'decision_source': 'RULE', 'fallback_reason': 'ROUND_LIMIT',
                                          'identity_verdict': 'UNCONFIRMED'})
            else:
                self.cache[key] = self._ask(ctx, refs)
            self._episode = (cur.track_ref, t, refs, self.cache[key][0] is None)
        choice, row = self.cache[key]
        hit = key in self._served
        self._served.add(key)
        return choice, (None if row is None else dict(row, cached=hit))

    # ------------------------------------------------------------------------------------------- one model call
    def _reference_jpeg(self, anchor):
        if anchor is None or self.frame_reader is None:
            return None
        oid = next((o.observation_id for o in anchor.observations if o.evidence_kind != 'BOX_CONTINUATION'), None)
        if oid not in self._reference:
            pair = self.obs.get(oid)
            try:
                self._reference[oid] = crop_jpeg(self.frame_reader(pair[0]['camera_id'], pair[0]['frame_index']), pair[1]['bbox_xyxy_px']) if pair else None
            except Exception:  # noqa: BLE001
                self._reference[oid] = None
        return self._reference[oid]

    def build_input(self, ctx):
        t, cur = ctx['timestamp_us'], ctx['current']
        rows = self.rows.get(t, {})
        last = [o for o in cur.observations if o.timestamp_us < t]
        cands, ids, frames = [], {}, []
        for camera in sorted(rows):
            boxes = []
            dets = sorted([o for o in (rows[camera]['detections'] or []) if o['score'] >= ag.INDEX_FLOOR], key=lambda o: o['observation_id'])
            for i, o in enumerate(dets):
                cid = f'D{i + 1}'
                ids[(camera, cid)] = o['observation_id']
                box = tuple(float(v) for v in o['bbox_xyxy_px'])
                cands.append(ag.Candidate(cid, camera, box, float(o['score']), o['class_label'], colors_of(o)))
                boxes.append((cid, box))
            if self.frame_reader is not None:
                try:
                    frames.append((camera, annotate(self.frame_reader(camera, rows[camera]['frame_index']), boxes, camera)))
                except Exception:  # noqa: BLE001
                    pass
        eligible = sorted({c['track'].camera_id for c in ctx['considered'] if c['eligible']})
        inp = ag.DecisionInput(
            scene_context=self.scene_context, t_s=t / 1e6, candidates=cands, seed_colors=tuple(sorted(ctx['current_colors'])),
            reference_jpeg=self._reference_jpeg(ctx.get('anchor')), frames=frames,
            rule_display={'kind': 'LOST', 'camera_id': cur.camera_id, 'last_t_s': last[-1].timestamp_us / 1e6 if last else None},
            rule_answer={'rule_eligible_cameras': eligible, 'rule_would_cut': len(eligible) == 1},
            last_camera=cur.camera_id, include_scene=self.scene_context is not None)
        return inp, ids

    def _ask(self, ctx, refs):
        t = ctx['timestamp_us']
        inp, ids = self.build_input(ctx)
        by_obs = {}
        for c in ctx['considered']:
            o = next((o for o in c['track'].observations if o.timestamp_us == t), None)
            if o is not None:
                by_obs[o.observation_id] = c['track'].track_ref
        seen = {}

        def transport(body):
            seen['sha'] = body_sha256(body)
            return self.transport(body)
        self.calls += 1
        started = time.perf_counter()
        rec = ag.decide(inp, mode='AGENT', transport=transport, model=self.model)
        row = {'reason': AUDIT_REASON, 'timestamp_us': t, 'from_track_ref': ctx['current'].track_ref, 'candidate_tracks': list(refs),
               'detections': len(inp.candidates), 'frames_attached': len(inp.frames), 'reference_attached': bool(inp.reference_jpeg),
               'request_sha256': seen.get('sha'), 'model': self.model, 'scene_context_sha256': rec.scene_context_sha256,
               'decision_source': rec.decision_source, 'fallback_reason': None if rec.agent_used else fallback_code(rec),
               'answer': rec.answer if rec.agent_used else None, 'usage': rec.usage, 'latency_s': rec.latency_s or round(time.perf_counter() - started, 3),
               'rule_answer': inp.rule_answer, 'identity_verdict': 'UNCONFIRMED'}
        self.records.append(row)
        if not rec.agent_used:
            return None, row
        ans = rec.answer
        if ans['answer'] in ('SELECT', 'OWN_BOX'):
            oid = ids.get((ans.get('camera_id'), ans.get('detection_id'))) if ans['answer'] == 'SELECT' else None
            ref = by_obs.get(oid)
            if ref is not None:
                row['adopted_track_ref'] = ref
                return ('SELECT', ref), row
            row['not_adoptable'] = 'NO_LOCAL_TRACK_FOR_DETECTION' if ans['answer'] == 'SELECT' else 'OWN_BOX_NOT_LINKED'
        return ('WAIT', None), row
