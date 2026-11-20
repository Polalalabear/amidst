"""Active Agent decision service (W2, #645; hypothesis plan AGENT_VS_RULE_HYPOTHESES_20261120 §4.1 C1-C6, §4.3).

One interface for the Agent mode (rule mode stays the default and is untouched: ``decision_mode='RULE'`` never builds a request,
never calls the transport). In AGENT mode the model decides; the rule gates are *information* attached to every candidate.

Three-layer request (Responses API ``input``), prefix-cache friendly:
  1. fixed prefix  : instructions + the whole ``scene_context`` (byte-stable; ``scene_context_sha256`` is the ``prompt_cache_key``)
  2. per-track     : reference crop + appearance text (identical for every call of one track)
  3. per-call      : time, rule display, gate results, every detection (all classes, low scores too), current frames

Answer types: SELECT (any considered detection, also ``rule_eligible=false`` -> ``RULE_OVERRIDE:<reasons>``), OWN_BOX, STILL_HERE_OCCLUDED,
NOT_VISIBLE (+ ``next_camera_hint``). More than 4 ``reason_codes`` are truncated, never a reason to fall back (C6).
Identity stays UNCONFIRMED. No Ground Truth enters this module; the transport is injected (tests use a fake, no network).
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field

from amidst.q1q5 import scene_context as sx

MODES = ('RULE', 'AGENT')
ANSWERS = ('SELECT', 'OWN_BOX', 'STILL_HERE_OCCLUDED', 'NOT_VISIBLE')
MAX_REASON_CODES = 4
LINK_MIN_SCORE = 0.4        # the rule's linking threshold (cross_camera_demo.Parameters.min_score); information here, not a gate
INDEX_FLOOR = 0.3

SYSTEM_TEXT = (
    'You are the decision component of a multi-camera tracker. You decide where one target person is NOW. '
    'Identity can never be confirmed; you only say which detected person looks most like the same person as the reference crop. '
    'The scene context below (JSON) describes the site: region connectivity and exit zones, the camera graph with its approval level, '
    'each camera position/yaw/FOV/ground footprint and overlaps. Edges are topological only; a missing or DRAFT edge is information, '
    'not a prohibition. Rule gates (score, class, colour) are information too: you may select ANY listed detection, including '
    'low-score or non-person-class boxes that sit on a person, and you may draw your own box when no listed box covers the person. '
    'Answer with one JSON object: {"answer": "SELECT"|"OWN_BOX"|"STILL_HERE_OCCLUDED"|"NOT_VISIBLE", "camera_id": string|null, '
    '"detection_id": string|null, "box_xyxy": [x0,y0,x1,y1]|null (960x540 px), "next_camera_hint": string|null, '
    '"confidence": "low"|"medium"|"high", "reason_codes": [at most 4 short codes], "reason": short text}. '
    'SELECT needs camera_id+detection_id; OWN_BOX needs camera_id+box_xyxy; STILL_HERE_OCCLUDED means the target is still in the '
    'camera of the previous display but hidden (give camera_id); NOT_VISIBLE means not visible in any listed camera (give '
    'next_camera_hint, the camera most likely to see the target next, or null). Prefer NOT_VISIBLE over guessing.')


@dataclass(frozen=True)
class Candidate:
    id: str                   # opaque per (camera, call): D1, D2 ...
    camera_id: str
    box: tuple
    score: float
    class_label: str
    colors: tuple = ()
    overlap_camera: bool = False      # C4: the camera overlaps the camera of the last display (information)


def gate_of(c: Candidate, seed_colors) -> dict:
    """Rule gates as information (C2/C5): never removes the candidate."""
    reasons = []
    if c.class_label != 'person':
        reasons.append(f'CLASS_NOT_PERSON:{c.class_label}')
    if c.score < LINK_MIN_SCORE:
        reasons.append(f'SCORE_BELOW_{LINK_MIN_SCORE}')
    if seed_colors and not set(seed_colors) & set(c.colors):
        reasons.append('COLOUR_NO_MATCH')
    return {'rule_eligible': not reasons, 'reasons': reasons}


@dataclass
class DecisionInput:
    scene_context: dict
    t_s: float
    candidates: list                          # [Candidate] all detections of the considered cameras (score >= INDEX_FLOOR)
    seed_colors: tuple = ()
    reference_jpeg: bytes | None = None       # per-track layer
    frames: list = field(default_factory=list)  # [(camera_id, jpeg bytes)] current frames with numbered boxes
    rule_display: dict = field(default_factory=dict)   # {'kind','camera_id','last_t_s'} information from the rule
    rule_answer: dict | None = None
    last_camera: str | None = None
    include_scene: bool = True


def _b64(jpeg: bytes) -> str:
    return 'data:image/jpeg;base64,' + base64.b64encode(jpeg).decode()


def prefix_text(scene_context: dict | None) -> str:
    if scene_context is None:
        return SYSTEM_TEXT
    return SYSTEM_TEXT + '\n\nSCENE_CONTEXT_SHA256=' + sx.sha256_of(scene_context) + '\nSCENE_CONTEXT=' + sx.serialize(scene_context)


def track_layer(inp: DecisionInput) -> list:
    parts = [{'type': 'input_text', 'text': 'TARGET REFERENCE (system observation at first lock). Tracker colour labels: '
              + (', '.join(inp.seed_colors) or 'none') + '. The reference crop follows.'}]
    if inp.reference_jpeg:
        parts.append({'type': 'input_image', 'image_url': _b64(inp.reference_jpeg), 'detail': 'high'})
    return parts


def variable_text(inp: DecisionInput) -> str:
    rd = inp.rule_display or {}
    lines = [f'NOW t={inp.t_s:.1f}s. Rule display: {rd.get("kind", "NONE")} camera={rd.get("camera_id")} (last shown at t={rd.get("last_t_s")}). '
             f'Rule answer (information only): {json.dumps(inp.rule_answer, sort_keys=True) if inp.rule_answer else "none"}.',
             'DETECTIONS (all classes with score>=%.1f; gate = rule gates as information):' % INDEX_FLOOR]
    for c in inp.candidates:
        g = gate_of(c, inp.seed_colors)
        lines.append(f'- {c.camera_id} {c.id}: {c.class_label} score {c.score:.2f} box [{c.box[0]:.0f},{c.box[1]:.0f},{c.box[2]:.0f},{c.box[3]:.0f}] '
                     f'colours {",".join(c.colors) or "none"} rule_eligible={str(g["rule_eligible"]).lower()} '
                     f'gate={",".join(g["reasons"]) or "-"}{" overlap_with_last_camera" if c.overlap_camera else ""}')
    cams = sorted({c.camera_id for c in inp.candidates} | {cam for cam, _ in inp.frames})
    lines.append('CAMERAS THIS CALL: ' + ', '.join(cams) + '. Camera properties are in the scene context; they are not repeated here.')
    return '\n'.join(lines)


def build_body(model: str, inp: DecisionInput, *, cache: str = 'prefix', nonce: str | None = None, previous_response_id: str | None = None,
               max_output_tokens: int = 1500) -> dict:
    """Responses-API body. cache: 'prefix' (implicit caching, key = scene hash), 'none' (explicit mode, no breakpoints = no caching),
    'state' (previous_response_id chain; first call carries the full prefix)."""
    scene = inp.scene_context if inp.include_scene else None
    key = sx.sha256_of(inp.scene_context)[:32] if inp.scene_context else 'no-scene'
    prefix = prefix_text(scene)
    if nonce:                               # only for the 'none' arm sanity: guarantees a different prefix
        prefix = f'NONCE={nonce}\n' + prefix
    var = [{'type': 'input_text', 'text': variable_text(inp)}]
    for cam, jpeg in inp.frames:
        var += [{'type': 'input_text', 'text': f'[frame {cam}]'}, {'type': 'input_image', 'image_url': _b64(jpeg), 'detail': 'high'}]
    if previous_response_id:
        items = [{'role': 'user', 'content': var}]
    else:
        items = [{'role': 'developer', 'content': [{'type': 'input_text', 'text': prefix}]},
                 {'role': 'user', 'content': track_layer(inp)}, {'role': 'user', 'content': var}]
    body = {'model': model, 'input': items, 'max_output_tokens': max_output_tokens, 'text': {'format': {'type': 'json_object'}}}
    if previous_response_id:
        body['previous_response_id'] = previous_response_id
    if cache == 'none':
        body['prompt_cache_options'] = {'mode': 'explicit'}
    elif cache in ('prefix', 'state'):
        body['prompt_cache_key'] = key
    if cache == 'state':
        body['store'] = True
    return body


def parse_answer(text: str, inp: DecisionInput):
    """Validate one reply -> (answer dict, None) or (None, error). reason_codes are truncated to 4 (C6)."""
    try:
        doc = json.loads(text)
    except (ValueError, TypeError):
        return None, 'NOT_JSON'
    if not isinstance(doc, dict) or doc.get('answer') not in ANSWERS:
        return None, 'BAD_ANSWER_TYPE'
    codes = doc.get('reason_codes') or []
    codes = [str(c)[:40] for c in codes][:MAX_REASON_CODES] if isinstance(codes, list) else []
    cams = {c.camera_id for c in inp.candidates} | {cam for cam, _ in inp.frames} | ({inp.last_camera} if inp.last_camera else set())
    known_cams = {c['camera_id'] for c in inp.scene_context['cameras']} if inp.scene_context else cams
    out = {'answer': doc['answer'], 'camera_id': doc.get('camera_id'), 'detection_id': None, 'box_xyxy': None, 'reason_codes': codes,
           'next_camera_hint': doc.get('next_camera_hint') if doc.get('next_camera_hint') in known_cams else None,
           'confidence': doc.get('confidence'), 'reason': str(doc.get('reason', ''))[:200]}
    if doc['answer'] == 'SELECT':
        cand = next((c for c in inp.candidates if c.camera_id == doc.get('camera_id') and c.id == doc.get('detection_id')), None)
        if cand is None:
            return None, 'UNKNOWN_DETECTION'
        out['detection_id'] = cand.id
        g = gate_of(cand, inp.seed_colors)
        if not g['rule_eligible']:                                           # C2
            out['reason_codes'] = (['RULE_OVERRIDE:' + '|'.join(g['reasons'])] + codes)[:MAX_REASON_CODES]
            out['rule_override'] = g['reasons']
    elif doc['answer'] == 'OWN_BOX':
        box = doc.get('box_xyxy')
        ok = (isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in box)
              and 0 <= box[0] < box[2] <= 961 and 0 <= box[1] < box[3] <= 541 and doc.get('camera_id') in cams)
        if not ok:
            return None, 'BAD_OWN_BOX'
        out['box_xyxy'] = [float(v) for v in box]
    elif doc['answer'] == 'STILL_HERE_OCCLUDED' and doc.get('camera_id') not in cams:
        return None, 'BAD_CAMERA'
    return out, None


def parse_response(raw: dict) -> dict:
    """Responses-API JSON -> {text, usage{input,cached,cache_write,output}, response_id, status}."""
    text = ''
    for item in raw.get('output') or []:
        for part in item.get('content') or []:
            if part.get('type') == 'output_text':
                text += part.get('text', '')
    u = raw.get('usage') or {}
    d = u.get('input_tokens_details') or {}
    return {'text': text, 'response_id': raw.get('id'), 'status': raw.get('status'),
            'usage': {'input_tokens': u.get('input_tokens'), 'cached_tokens': d.get('cached_tokens', 0) or 0,
                      'cache_write_tokens': d.get('cache_write_tokens', 0) or 0, 'output_tokens': u.get('output_tokens')}}


@dataclass
class DecisionRecord:
    decision_source: str                  # RULE | AGENT
    agent_attempted: bool
    agent_used: bool
    fallback_used: bool
    fallback_reason: str | None
    answer: dict | None
    scene_context_sha256: str | None
    usage: dict | None = None
    latency_s: float | None = None
    error: str | None = None


def decide(inp: DecisionInput, *, mode: str = 'RULE', transport=None, model: str = 'gpt-6.1-terra', cache: str = 'prefix', **kw) -> DecisionRecord:
    """RULE: return the rule answer, no request, no transport. AGENT: ask the model; invalid/failed -> rule answer + fallback_reason.
    ``transport(body) -> parse_response()-shaped dict (+latency_s)`` must go through ApiGuard when it spends money."""
    if mode not in MODES:
        raise ValueError('DECISION_MODE_INVALID')
    sha = sx.sha256_of(inp.scene_context) if inp.scene_context else None
    if mode == 'RULE':
        return DecisionRecord('RULE', False, False, False, None, inp.rule_answer, sha)
    if transport is None:
        return DecisionRecord('RULE', True, False, True, 'NO_TRANSPORT', inp.rule_answer, sha)
    try:
        resp = transport(build_body(model, inp, cache=cache, **kw))
    except Exception as exc:  # noqa: BLE001  (guard denial, transport failure)
        return DecisionRecord('RULE', True, False, True, 'TRANSPORT:' + type(exc).__name__, inp.rule_answer, sha, error=str(exc)[:200])
    ans, err = parse_answer(resp.get('text', ''), inp)
    if ans is None:
        return DecisionRecord('RULE', True, False, True, 'INVALID_RESPONSE:' + str(err), inp.rule_answer, sha, resp.get('usage'),
                              resp.get('latency_s'), err)
    return DecisionRecord('AGENT', True, True, False, None, ans, sha, resp.get('usage'), resp.get('latency_s'))
