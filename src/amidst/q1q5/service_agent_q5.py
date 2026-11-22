"""F3 (#657, H6): the 8785 Q5 Agent mode decided by ``agent_service`` (D340). Rule mode is untouched.

``switch_mode='RULE_ONLY'`` runs exactly ``RuleController``. ``'AGENT_SEQUENTIAL'`` keeps the shared controller (index linking,
timeline, decision journal) but at every search the model decides, and the rule gates are information, not filters:

* X1   the Agent is asked even when the rule snapshot is empty (``GRAPH_NOT_APPROVED`` / UNKNOWN / TOPOLOGICAL_ONLY edges excluded);
       it sees every tracking camera and the graph with each edge's approval level in ``scene_context``, and may switch to any of them.
* C2   it may select any detection, also one the rule would reject (``RULE_OVERRIDE:<reasons>`` is recorded).
* C3   it is asked at every search, also with zero or one rule candidate; it may answer STILL_HERE_OCCLUDED / NOT_VISIBLE.
* C4   detections of cameras overlapping the current one are listed (``overlap_camera``), never dropped.
* C5   every index detection with score >= 0.3, all classes, is listed; score/colour/class are ``gate`` information.

The rule's own answer is still computed (same evidence calls) and attached as information. Only when the model fails (transport,
guard denial, timeout, invalid reply) or the session round limit is reached does the rule answer execute, as ``RULE_FALLBACK``
with a contract ``fallback_reason``. Every model call is in the decision record (``llm_calls``) and in ``trace()``.
Identity stays UNCONFIRMED. No Ground Truth, renderer trajectory, visibility or depth enters this module.
"""
from __future__ import annotations

import hashlib
import io
import json
import time
from copy import deepcopy
from dataclasses import replace

from amidst.q1q5 import agent_service as ag
from amidst.q1q5.linker import LinkError, LocalLinker
from amidst.q1q5.q5_controller import RuleController, require
from amidst.q1q5.store import canonical_hash

TRACE_SCHEMA = 'q-demo.agent-service-trace.v1'
PROMPT_REF = 'agent-service:'
AGENT_PARAMETER_NAMES = ('agent_max_rounds', 'agent_total_budget_ms', 'agent_call_timeout_ms', 'agent_max_illegal_submissions',
                         'session_max_agent_rounds')
OWN_BOX_MIN_IOU = 0.3


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def body_sha256(body: dict) -> str:
    return _sha(json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode())


def colors_of(observation: dict) -> tuple:
    verdicts = (observation.get('color') or {}).get('verdicts') or {}
    return tuple(sorted(k for k, v in verdicts.items() if v in ('STRONG', 'WEAK')))


def iou(a, b) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def fallback_code(record: ag.DecisionRecord) -> str:
    """agent_service fallback reason -> the contract's closed ``fallback_reason`` list (§8)."""
    reason = record.fallback_reason or ''
    if reason == 'NO_TRANSPORT':
        return 'MODE_NOT_AUTHORIZED'
    if reason.startswith('INVALID_RESPONSE'):
        return 'INVALID_RESPONSE'
    err = (record.error or '').upper()
    if reason in ('TRANSPORT:TimeoutError', 'TRANSPORT:timeout') or err == 'TIMEOUT':
        return 'PROVIDER_TIMEOUT'
    if reason == 'TRANSPORT:PermissionError' or err in ('GUARD_NOT_APPROVED', 'NO_API_KEY', 'MODEL_NOT_ENABLED', 'DENIED') \
            or err.startswith('GUARD_DENIED') or err.startswith('BUDGET') or err.startswith('DAILY') or err.startswith('MAX_'):
        return 'MODE_NOT_AUTHORIZED'
    return 'PROVIDER_UNAVAILABLE'


def annotate(png_or_jpeg: bytes, boxes, label: str) -> bytes:
    """Current frame with numbered boxes (the ids the Agent answers with) -> JPEG. Rendered synthetic frames only (D340)."""
    from PIL import Image, ImageDraw
    im = Image.open(io.BytesIO(png_or_jpeg)).convert('RGB')
    dr = ImageDraw.Draw(im)
    for cid, box in boxes:
        dr.rectangle(box, outline=(255, 220, 0), width=2)
        dr.rectangle((box[0], box[1], box[0] + 26, box[1] + 14), fill=(255, 220, 0))
        dr.text((box[0] + 3, box[1] + 1), cid, fill=(0, 0, 0))
    dr.rectangle((0, 0, 150, 14), fill=(0, 0, 0))
    dr.text((3, 1), label, fill=(255, 255, 255))
    out = io.BytesIO()
    im.save(out, 'JPEG', quality=85)
    return out.getvalue()


def crop_jpeg(png_or_jpeg: bytes, box) -> bytes:
    from PIL import Image
    im = Image.open(io.BytesIO(png_or_jpeg)).convert('RGB')
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    c = im.crop((max(0, x0 - .15 * w), max(0, y0 - .1 * h), min(im.width, x1 + .15 * w), min(im.height, y1 + .1 * h)))
    out = io.BytesIO()
    c.save(out, 'JPEG', quality=90)
    return out.getvalue()


class ServiceAgentController(RuleController):
    """Q5 controller whose AGENT_SEQUENTIAL decisions come from ``agent_service.decide``."""

    def __init__(self, *args, transport, scene_context=None, frame_reader=None, model: str = 'gpt-6.1-terra', model_digest: str | None = None,
                 authorized: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.transport, self.scene_context, self.frame_reader = transport, scene_context, frame_reader
        self.model = model
        self.model_digest = model_digest or _sha(('openai:' + model).encode())
        self.authorized = authorized
        self.agent_records = []
        self._metadata = None
        self._agent_pick = None
        self._last_seen = None
        self._reference = None
        self.agent_values = None

    # ------------------------------------------------------------------------------------------------- mode + parameters
    def _validate_mode(self):
        require(self.request['switch_mode'] in {'RULE_ONLY', 'AGENT_SEQUENTIAL'}, 'Unsupported switch mode', 'FORBIDDEN_INFERENCE_INPUT')

    def _prepare(self):
        reason = super()._prepare()
        if reason is not None or self.request['switch_mode'] == 'RULE_ONLY':
            return reason
        if not self.authorized or self.transport is None:
            self.fallback_reason = 'MODE_NOT_AUTHORIZED'
            return None
        items = {x['name']: x for x in self.bindings.parameter_set['parameters']}
        if not set(AGENT_PARAMETER_NAMES) <= items.keys() or any(items[n].get('status') != 'APPROVED' or type(items[n].get('value')) is not int
                                                                  or items[n]['value'] <= 0 for n in AGENT_PARAMETER_NAMES):
            return 'PARAMETERS_NOT_APPROVED'
        self.agent_values = {n: items[n]['value'] for n in AGENT_PARAMETER_NAMES}
        return None

    def _agent_on(self) -> bool:
        return self.request['switch_mode'] == 'AGENT_SEQUENTIAL'

    def _decider(self):
        return 'RULE_FALLBACK' if self.fallback_reason else 'RULE_ONLY'

    def _selection_metadata(self):
        return self._metadata or super()._selection_metadata()

    def _emit(self, *args, **kwargs):
        full = kwargs.pop('full_submitted', None)
        if full is not None:
            kwargs['submitted'] = full
        return super()._emit(*args, **kwargs)

    def trace(self):
        data = {'schema_version': TRACE_SCHEMA, 'session_id': self.session_id,
                'scene_context_sha256': ag.sx.sha256_of(self.scene_context) if self.scene_context else None, 'records': deepcopy(self.agent_records)}
        data['content_sha256'] = canonical_hash(data)
        return data

    # ------------------------------------------------------------------------------------------------- search hooks
    def _search(self, tracker, *args, **kwargs):
        row, _obs = self.observations[tracker.last['observation_id']]
        self._last_seen = (row['camera_id'], row['timestamp_us'])
        self._metadata, self._agent_pick = None, None
        return super()._search(tracker, *args, **kwargs)

    def _sample_rows(self, decision_time: int):
        """The first INFERRED index row at or after the decision time (and the playback cursor) of every tracking camera."""
        start = max(decision_time, self.cursor)
        best = {}
        for (camera, _frame), row in self.records.items():
            ts = row['timestamp_us']
            if (camera not in self.metadata or row['frame_state'] != 'INFERRED' or ts < start or ts >= self.right
                    or not any(a <= ts < b for a, b in self.available[camera])):
                continue
            if camera not in best or ts < best[camera]['timestamp_us']:
                best[camera] = row
        if not best:
            return None, {}
        t = min(r['timestamp_us'] for r in best.values())
        return t, {c: r for c, r in best.items() if r['timestamp_us'] == t}

    def _reference_jpeg(self):
        if self._reference is not None or self.frame_reader is None:
            return self._reference or None
        first = next((d for d in self.decisions if d['entry_observation_id']), None)
        oid = first['entry_observation_id'] if first else None
        seed = next((s for s in self.timeline if s['kind'] == 'ON_CAMERA'), None)
        oid = oid or (seed['observation_ids'][0] if seed else None)
        if oid is None:
            return None
        row, obs = self.observations[oid]
        try:
            self._reference = crop_jpeg(self.frame_reader(row['camera_id'], row['frame_index']), obs['bbox_xyxy_px'])
        except Exception:  # noqa: BLE001 - missing frame -> text-only reference, recorded as frames_attached=0
            self._reference = b''
        return self._reference or None

    def _seed_colors(self):
        if self.color_label:
            return (self.color_label,)
        seed = next((s for s in self.timeline if s['kind'] == 'ON_CAMERA'), None)
        return colors_of(self.observations[seed['observation_ids'][0]][1]) if seed else ()

    def build_input(self, decision_time: int, rule_answer: dict):
        t, rows = self._sample_rows(decision_time)
        last_cam, last_t = self._last_seen or (self.current_camera, None)
        overlaps = set()
        for o in (self.scene_context or {}).get('overlaps', []):
            a, b = o['cameras'][0], o['cameras'][1]
            if last_cam in (a, b):
                overlaps.add(b if a == last_cam else a)
        cands, ids, frames = [], {}, []
        for camera in sorted(rows):
            row = rows[camera]
            dets = sorted([o for o in (row['detections'] or []) if o['score'] >= ag.INDEX_FLOOR], key=lambda o: o['observation_id'])
            boxes = []
            for i, o in enumerate(dets):
                cid = f'D{i + 1}'
                ids[(camera, cid)] = o['observation_id']
                box = tuple(float(v) for v in o['bbox_xyxy_px'])
                cands.append(ag.Candidate(cid, camera, box, float(o['score']), o['class_label'], colors_of(o), camera in overlaps))
                boxes.append((cid, box))
            if self.frame_reader is not None:
                try:
                    frames.append((camera, annotate(self.frame_reader(camera, row['frame_index']), boxes, camera)))
                except Exception:  # noqa: BLE001 - a frame that cannot be read is simply not attached (recorded count)
                    pass
        inp = ag.DecisionInput(
            scene_context=self.scene_context, t_s=(t if t is not None else decision_time) / 1e6, candidates=cands,
            seed_colors=self._seed_colors(), reference_jpeg=self._reference_jpeg(), frames=frames,
            rule_display={'kind': 'SEARCHING', 'camera_id': last_cam, 'last_t_s': None if last_t is None else last_t / 1e6},
            rule_answer=rule_answer, last_camera=last_cam, include_scene=self.scene_context is not None)
        return inp, t, rows, ids

    # ------------------------------------------------------------------------------------------------- the decision
    def _select(self, snapshot, decision_time):
        if not self._agent_on():
            return super()._select(snapshot, decision_time)
        rule = super()._select(snapshot, decision_time)                 # information + the fallback answer
        if self.agent_values is None:                                     # MODE_NOT_AUTHORIZED: whole session is the rule
            return self._as_fallback(rule)
        if (self.session_agent_rounds_used >= self.agent_values['session_max_agent_rounds']
                or self._episode_agent_rounds >= self.agent_values['agent_max_rounds']):
            self.fallback_reason = self.fallback_reason or 'ROUND_LIMIT'
            return self._as_fallback(rule)
        selected = rule[0]
        rule_answer = ({'action': 'SWITCH', 'camera_id': selected[0]['camera_id'], 'observation_id': selected[1]['entry_observation_id']}
                       if selected else {'action': 'RETURN_TO_ORIGIN', 'camera_id': self.current_camera, 'snapshot_candidates': len(snapshot['candidates'])})
        inp, t, rows, ids = self.build_input(decision_time, rule_answer)
        seen = {}

        def transport(body):
            seen['body_sha256'] = body_sha256(body)
            out = self.transport(body)
            seen['raw_sha256'] = _sha(str(out.get('text', '')).encode())
            return out

        self.agent_attempted = True
        self._episode_agent_rounds += 1
        self.session_agent_rounds_used += 1
        started = time.perf_counter()
        record = ag.decide(inp, mode='AGENT', transport=transport, model=self.model)
        self._episode_budget_ms = int((time.perf_counter() - started) * 1000)
        call = {'model': self.model, 'model_digest': self.model_digest, 'prompt_sha256': seen.get('body_sha256') or _sha(b''),
                'prompt_ref': PROMPT_REF + (record.scene_context_sha256 or 'no-scene'), 'raw_output_sha256': seen.get('raw_sha256'),
                'validation': 'PASS' if record.agent_used else (record.fallback_reason or 'FAILED')[:60]}
        self.agent_records.append({'searching_index': self.searching_index, 'decision_time_us': decision_time, 'sample_time_us': t,
                             'cameras': sorted(rows), 'detections': len(inp.candidates), 'frames_attached': len(inp.frames),
                             'reference_attached': bool(inp.reference_jpeg), 'request_sha256': call['prompt_sha256'],
                             'rule_answer': deepcopy(rule_answer), 'decision_source': record.decision_source, 'agent_used': record.agent_used,
                             'fallback_reason': record.fallback_reason, 'answer': deepcopy(record.answer) if record.agent_used else None,
                             'usage': deepcopy(record.usage), 'latency_s': record.latency_s, 'error': record.error})
        if not record.agent_used:
            self.fallback_reason = self.fallback_reason or fallback_code(record)
            return self._as_fallback(rule, [call])
        ans = record.answer
        submitted = {'action': None, 'candidate_ref': None, 'agent_answer': deepcopy(ans), 'rule_answer': deepcopy(rule_answer),
                     'sample_time_us': t, 'rationale': ans.get('reason') or None}
        pick = None
        if ans['answer'] == 'SELECT':
            pick = ids.get((ans['camera_id'], ans['detection_id']))
        elif ans['answer'] == 'OWN_BOX':
            row = rows.get(ans['camera_id'])
            scored = sorted(((iou(o['bbox_xyxy_px'], ans['box_xyxy']), o['observation_id']) for o in (row['detections'] or []) if row
                             and o['score'] >= ag.INDEX_FLOOR), reverse=True) if row else []
            if scored and scored[0][0] >= OWN_BOX_MIN_IOU:
                pick = scored[0][1]
                submitted['own_box_matched_iou'] = round(scored[0][0], 3)
            else:
                submitted['own_box_matched_iou'] = None      # no index observation under the box: nothing to enter, keep searching
        if pick is not None:
            row, obs = self.observations[pick]
            ref = next((c['candidate_ref'] for c in snapshot['candidates'] if c['camera_id'] == row['camera_id']), None)
            submitted.update(action='SWITCH', candidate_ref=ref, camera_id=row['camera_id'], observation_id=pick,
                             in_rule_snapshot=ref is not None)
            self._agent_pick = (row, obs, submitted, [call])
            return None, [], []
        submitted['action'] = 'RETURN_TO_ORIGIN'
        self._metadata = {'decided_by': 'AGENT', 'llm_calls': [call], 'full_submitted': submitted}
        return None, [], []

    def _as_fallback(self, rule, calls=()):
        selected, considered, tools = rule
        for c in considered:
            c['decided_by'] = 'RULE_FALLBACK'
        self._metadata = {'decided_by': 'RULE_FALLBACK', 'llm_calls': list(calls)}
        return selected, considered, tools

    def _agent_linker(self, row, observation):
        """Linker seeded by an Agent pick. The rule linker refuses a seed that fails its colour/score gate; here those gates are
        information (D340), so the pick is linked with the colour gate off and the score floor lowered to the pick's own score.
        Geometry linking (IoU, centre distance, gap) is the rule's. A non-person class cannot seed a person track (None)."""
        if observation['class_label'] != 'person':
            return None
        try:
            return self._new_linker(row, observation)
        except LinkError:
            camera = row['camera_id']
            meta = self.metadata[camera]
            params = self.link_parameters[camera]
            params = replace(params, min_score=min(params.min_score, observation['score']))
            return LocalLinker(row, observation['observation_id'], parameters=params, stride_samples=meta['stride_samples'],
                               index_grid_origin_frame=meta['index_grid_origin_frame'], color_label=None)

    def _commit_selection(self, snapshot, decision_time, selected, considered, calls, tracker):
        if self._agent_pick is None:
            return super()._commit_selection(snapshot, decision_time, selected, considered, calls, tracker)
        row, obs, submitted, llm_calls = self._agent_pick
        self._agent_pick = None
        ts = row['timestamp_us']
        require(ts >= decision_time and ts >= self.cursor and self.left <= ts < self.right and row['camera_id'] in self.metadata,
                'Agent switch outside the query/playback scope')
        new_tracker = self._agent_linker(row, obs)
        if new_tracker is None:                       # e.g. a non-person box: adopted as an answer, nothing to track from
            submitted.update(action='RETURN_TO_ORIGIN', not_linkable='CLASS_NOT_PERSON:' + obs['class_label'])
            self._metadata = {'decided_by': 'AGENT', 'llm_calls': llm_calls, 'full_submitted': submitted}
            return super()._commit_selection(snapshot, decision_time, None, [], [], tracker)
        submitted['linked_without_rule_gates'] = new_tracker.color_label is None and self.color_label is not None
        decision = self._emit('SEARCHING', 'SWITCHING', decision_time, decision_time=decision_time, snapshot=snapshot, considered=[], tool_calls=[],
                              submitted=submitted, action='SWITCH', candidate_ref=submitted['candidate_ref'], entry_id=obs['observation_id'],
                              decided_by='AGENT', llm_calls=llm_calls)
        self._emit('SWITCHING', 'PLAYING', ts, decision_time=decision_time, snapshot=snapshot, entry_id=obs['observation_id'],
                   candidate_ref=submitted['candidate_ref'], decided_by='AGENT', cause_decision_id=decision['decision_id'])
        self._gap(ts, ['SEARCHING', 'SWITCHING'], self.current_camera)
        self._observe(row, obs, 'SWITCH', 'AGENT', decision['decision_id'])
        return 'SWITCH', new_tracker


class ServiceAgentFactory:
    """``run.agent_factory`` for the agent_service Agent mode. ``availability()`` reads the gateway heartbeat (costs nothing)."""

    def __init__(self, transport, *, scene_context=None, frame_reader=None, model: str = 'gpt-6.1-terra'):
        self.transport, self.scene_context, self.frame_reader, self.model = transport, scene_context, frame_reader, model

    def __call__(self, request, **kwargs):
        return ServiceAgentController(request, transport=self.transport, scene_context=self.scene_context, frame_reader=self.frame_reader,
                                      model=self.model, **kwargs)

    def availability(self):
        check = getattr(self.transport, 'availability', None)
        return check() if check else (True, None)


def r004_scene_context(graphs, catalog: dict, catalog_sha256: str, camera_ids, repo_root) -> dict:
    """scene_context for an r004 run: the pinned v3_1 graphs, the run's camera catalog and the D346 static walls (only cameras the F2
    wall gate VALIDATED are clipped; the rest are listed SCENE_CONTEXT_INCOMPLETE). Committed configuration only, no GT."""
    from pathlib import Path

    from amidst.q1q5 import scene_context as sx
    from amidst.q1q5.scene_graphs import R004_PINS
    root = Path(repo_root)
    geometry = (root / 'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json').read_bytes()
    gate = (root / 'docs/evaluation/F2_WALL_GATE_20261122.json').read_bytes()
    sha = {'region_graph_v3_1.json': R004_PINS['region_graph_v3_1.json'], 'camera_graph_v3_1.json': R004_PINS['camera_graph_v3_1.json'],
           'tracking_scope_v3_1.json': R004_PINS['tracking_scope_v3_1.json'], 'camera_catalog.json': catalog_sha256}
    return sx.build(graphs.region, graphs.camera, catalog, sorted(camera_ids), sha, graphs.tracking_scope,
                    static=sx.static_geometry(geometry, gate, 'r004'))


def pinned_frame_reader(by_camera: dict):
    """``frame_reader(camera_id, frame_index)`` over the server's pinned RGB table ``{camera: {frame: (path, sha256)}}``; the bytes
    are re-hashed on every read (a changed file is an error, never a silent substitute)."""
    def read(camera_id, frame_index):
        path, pin = by_camera[camera_id][frame_index]
        raw = open(path, 'rb').read()
        require(_sha(raw) == pin, 'RGB pin mismatch')
        return raw
    return read
