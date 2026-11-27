"""E8 request assembly (#780; design docs/evaluation/E8_DESIGN_V1.md §2). INFERENCE SIDE ONLY.

One structured request ``e8_level_request_v1`` per (decision point, level, candidate order). laya, Qwen and the GPT arm (#781)
render from the same rows, so every model sees the same information per level; only the format differs.

Levels are cumulative: L0 (E7 bytes) | L0c (E8 compact format, L0 information) | L1 (+ target colour, option colours)
| L2 (+ last B1 position, distances) | L3 (+ camera relations from the scene context) | L4 (+ reference crop and frames, VLM only)
| L3F (L3 with the full scene context instead of the summary, Qwen-7B only, exploratory).

The builder masks each request to its level: a request never carries a field of a higher level. ``keep_display`` is the B1 display
at T (used only to resolve a KEEP answer; never rendered). Nothing here reads Ground Truth, labels or scoring modules; candidate lists
come precomputed from the Mac pack builder (``build_e7_colab_pack.candidates_for_tick`` + ground projection).
Identity stays UNCONFIRMED.
"""
from __future__ import annotations

import json
import math
import random
from typing import Any

from amidst.evaluation.e7_decider_eval import (
    DeciderRequest,
    assemble_ao_prompt,
    build_laya_state_and_questions,
    laya_answer_to_ao_json,
    parse_ao_json_response,
)
from amidst.live_mode.aopen import arms as e6_arms
from amidst.q1q5 import agent_service as ag
from amidst.q1q5 import scene_context as sx

SCHEMA = 'e8_level_request_v1'
LEVELS = ('L0', 'L0c', 'L1', 'L2', 'L3', 'L4', 'L3F')
RANK = {'L0': 0, 'L0c': 0, 'L1': 1, 'L2': 2, 'L3': 3, 'L3F': 3, 'L4': 4}
TEXT_LEVELS = ('L0c', 'L1', 'L2', 'L3')            # closed-loop candidates (design §3.5, Q1)
PERMS = ('p0', 'p1', 'p2')
SEED = 20261128
MERGE_M = 1.5               # same person seen by two cameras (= Tracker 'seen' radius)
OVERLAP_MIN_IOU = 0.05
TICK_S = 0.2
TARGET_COLOR = 'red'
ANSWERS = ('SELECT', 'KEEP', 'NOT_VISIBLE')
NON_CHOICE = ('KEEP', 'NOT_VISIBLE')
E7_TO_E8 = {'SELECT': 'SELECT', 'NOT_VISIBLE': 'NOT_VISIBLE', 'UNCERTAIN': 'KEEP', 'STILL_HERE_OCCLUDED': 'KEEP', 'OWN_BOX': 'OWN_BOX'}

LAYA_QUESTION = {0: 'Which option is the tracked person now?', 1: 'Which option is the red-clothed tracked person now?'}
VLM_SYSTEM = (
    'You are the decision component of a multi-camera tracker. You decide where one target person is NOW. Identity can never be '
    'confirmed; you only say which listed option is most likely the tracked person. Options are frozen person detections; boxes are '
    'in 320x180 pixel frames. Gates, colours, distances and camera relations are information, not prohibitions. '
    'KEEP keeps the tracker\'s current target. NOT_VISIBLE means the target is visible in none of the cameras. '
    'Prefer NOT_VISIBLE over guessing. Reply with ONE JSON object only: '
    '{"answer":"SELECT"|"KEEP"|"NOT_VISIBLE","option":"<option letter>"|null,"confidence":"low"|"medium"|"high"}. '
    'SELECT needs option.')


# ------------------------------------------------------------------------------------------------ options
def letters(n: int) -> list[str]:
    out = []
    for i in range(n):
        s, k = '', i
        while True:
            s = chr(65 + k % 26) + s
            k = k // 26 - 1
            if k < 0:
                break
        out.append(s)
    return out


def short_cam(cam: str | None) -> str:
    return (cam or 'none').removeprefix('CAM_')


def _height(box) -> float:
    return float(box[3]) - float(box[1])


def merge_options(cands: list[dict]) -> list[dict]:
    """Cross-camera merge (design §2.4). ``cands`` in canonical order, each with ``ground_xy`` (or None).
    A candidate joins the first earlier group that has no member in its camera and a member within MERGE_M; boxes of one camera
    never merge. Representative = tallest member box (first on ties). Group order = order of its first member."""
    groups: list[list[dict]] = []
    for c in cands:
        xy = c.get('ground_xy')
        home = None
        if xy is not None:
            for g in groups:
                if any(m['camera_id'] == c['camera_id'] for m in g):
                    continue
                if any(m.get('ground_xy') is not None and math.dist(m['ground_xy'], xy) < MERGE_M for m in g):
                    home = g
                    break
        if home is None:
            groups.append([c])
        else:
            home.append(c)
    out = []
    for g in groups:
        rep = max(g, key=lambda m: (_height(m['box']), -g.index(m)))
        out.append({'camera_id': rep['camera_id'], 'detection_id': rep['detection_id'], 'box': list(rep['box']), 'score': rep['score'],
                    'colors': sorted({col for m in g for col in m.get('colors', [])}), 'ground_xy': rep.get('ground_xy'),
                    'members': [[m['camera_id'], m['detection_id']] for m in g]})
    return out


def permute(items: list, perm: str, base_id: str) -> list:
    if perm == 'p0':
        return list(items)
    if perm == 'p1':
        return list(reversed(items))
    if perm == 'p2':
        out = list(items)
        random.Random(f'{SEED}|{base_id}').shuffle(out)
        return out
    raise ValueError('BAD_PERM')


# ------------------------------------------------------------------------------------------------ scene summary (L3)
def scene_relations(scene: dict, last_cam: str | None, est_xy) -> dict:
    """Compact L3 summary from a scene_context (design §2.5): adjacency (graph transitions), overlaps (iou >= 0.05) of the last
    camera, and the ground distance from the last estimate to every camera footprint (the B2/F2 spatial ranking measure)."""
    from e3_f4_run import poly_dist  # scripts/evaluation on sys.path (notebook / tests / pack builder)
    adj = sorted({t['to'] for t in scene.get('camera_transitions', []) if t['from'] == last_cam}
                 | {t['from'] for t in scene.get('camera_transitions', []) if t['to'] == last_cam})
    ovl = {}
    for o in scene.get('overlaps', []):
        if last_cam in o['cameras'] and o['overlap_iou'] >= OVERLAP_MIN_IOU:
            other = next(c for c in o['cameras'] if c != last_cam)
            ovl[other] = round(o['overlap_iou'], 2)
    foot = {}
    if est_xy is not None:
        for c in scene.get('cameras', []):
            d = poly_dist(est_xy, c.get('ground_footprint_polygon_xy_m') or [])
            foot[c['camera_id']] = round(d, 1) if math.isfinite(d) else None
    return {'last_cam': last_cam, 'adjacent': adj, 'overlap_iou': dict(sorted(ovl.items())), 'footprint_dist_m': dict(sorted(foot.items()))}


def relation(cam: str, rel: dict) -> str:
    if rel.get('last_cam') is None:
        return 'other'
    if cam == rel['last_cam']:
        return 'same'
    if cam in rel['adjacent']:
        return 'adj'
    if cam in rel['overlap_iou']:
        return 'ovl'
    return 'other'


# ------------------------------------------------------------------------------------------------ request building
def snapshot_of(row: dict | None) -> dict | None:
    """B1 state at T-1 from a frozen b-log row (design §2.2): state, active camera, estimate, lost ticks, seconds since seen."""
    if row is None:
        return None
    tr = row['tracking']
    lost = tr.get('lost_ticks') or 0
    return {'state': tr.get('state'), 'active_cam': tr.get('active_cam'),
            'est_xy': [round(float(v), 3) for v in tr['est_xy']] if tr.get('est_xy') is not None else None,
            'lost_ticks': lost, 'seen_ago_s': round(lost * TICK_S, 1)}


def build_request(*, case_id: str, dataset_group: str, tick: int, level: str, perm: str, cands: list[dict], camera_ids: list[str],
                  snapshot: dict | None, keep_display: dict | None, scene: dict | None = None, e7_row: dict | None = None,
                  image_refs: dict | None = None, scene_sha256: str | None = None) -> dict:
    """One masked ``e8_level_request_v1`` row. ``cands`` = canonical candidate list (detection_id, camera_id, box, score, colors,
    ground_xy). ``e7_row`` (L0 only) = the E7 request fields (variable_text built by the Mac builder for this order)."""
    if level not in LEVELS or perm not in PERMS:
        raise ValueError('BAD_LEVEL_OR_PERM')
    base = f'{case_id}|t{tick}'
    req: dict[str, Any] = {'schema': SCHEMA, 'request_id': f'{base}|{level}|{perm}', 'base_id': base, 'case_id': case_id,
                           'dataset_group': dataset_group, 'tick': tick, 'now_s': round(tick * TICK_S, 1), 'level': level, 'perm': perm,
                           'camera_ids': list(camera_ids), 'keep_display': keep_display, 'identity': 'UNCONFIRMED'}
    r = RANK[level]
    if level == 'L0':
        if e7_row is None:
            raise ValueError('L0_NEEDS_E7_ROW')
        req['e7'] = {'variable_text': e7_row['variable_text'], 'candidates': e7_row['candidates'], 'camera_ids': e7_row['camera_ids']}
        return req
    opts = permute(merge_options(cands), perm, base)
    rel = scene_relations(scene, snapshot and snapshot['active_cam'], snapshot and snapshot['est_xy']) if r >= 3 and scene else None
    est = snapshot and snapshot.get('est_xy')
    out = []
    for key, o in zip(letters(len(opts)), opts):
        item = {'key': key, 'camera_id': o['camera_id'], 'detection_id': o['detection_id'], 'box': o['box'], 'score': o['score'],
                'members': o['members']}
        if r >= 1:
            item['colors'] = o['colors']
        if r >= 2:
            item['ground_xy'] = [round(v, 2) for v in o['ground_xy']] if o['ground_xy'] is not None else None
            item['distance_m'] = (round(math.dist(o['ground_xy'], est), 2) if o['ground_xy'] is not None and est is not None else None)
        if r >= 3 and rel is not None:
            item['relation'] = relation(o['camera_id'], rel)
        out.append(item)
    req['options'] = out
    if r >= 1:
        req['target_color'] = TARGET_COLOR
    if r >= 2:
        req['snapshot'] = snapshot
    if r >= 3:
        req['scene_summary'] = rel
    if level == 'L3F':
        req['scene_context_sha256'] = scene_sha256 or (sx.sha256_of(scene) if scene else None)
    if level == 'L4':
        req['image_refs'] = image_refs or {}
    return req


# ------------------------------------------------------------------------------------------------ rendering
def _f(v, fmt='{:.1f}'):
    return '?' if v is None else fmt.format(v)


def _score(s) -> str:
    return f'{float(s):.2f}'.lstrip('0') if float(s) < 1 else f'{float(s):.2f}'


def laya_option_text(o: dict, level: str) -> str:
    """Compact option text, most decisive field first (laya head budget 192/256 tokens, design §2.6)."""
    r = RANK[level]
    parts = []
    if r >= 1:
        parts.append('+'.join(o.get('colors') or []) or 'none')
    if r >= 2:
        parts.append(_f(o.get('distance_m')) + 'm')
    parts.append(short_cam(o['camera_id']))
    if r >= 3 and 'relation' in o:
        parts.append(o['relation'])
    parts.append(_score(o['score']))
    return ' '.join(parts)


def _option_line(o: dict, level: str) -> str:
    b = o['box']
    s = f"{o['key']} {short_cam(o['camera_id'])} {o['detection_id']} s{_score(o['score'])} [{b[0]:.0f},{b[1]:.0f},{b[2]:.0f},{b[3]:.0f}]"
    r = RANK[level]
    if r >= 1:
        s += ' ' + ('+'.join(o.get('colors') or []) or 'none')
    if r >= 2:
        xy = o.get('ground_xy')
        s += f" xy({_f(xy and xy[0])},{_f(xy and xy[1])}) d{_f(o.get('distance_m'))}m"
    if r >= 3 and 'relation' in o:
        s += ' ' + o['relation']
    if len(o['members']) > 1:
        s += ' also ' + ','.join(f'{short_cam(c)}:{d}' for c, d in o['members'][1:])
    return s


def _keep_text(req: dict) -> str:
    snap = req.get('snapshot')
    if snap is None:
        return 'keep current target'
    return f"keep current target {short_cam(snap.get('active_cam'))}"


def render_laya(req: dict) -> tuple[dict, dict, dict]:
    """-> (state, questions, option_map). L0 = the exact E7 rendering (build_laya_state_and_questions)."""
    if req['level'] == 'L0':
        return build_laya_state_and_questions(e7_decider_request(req))
    r = RANK[req['level']]
    if req['level'] in ('L4', 'L3F'):
        raise ValueError('LAYA_TEXT_LEVELS_ONLY')
    criteria, omap = {}, {}
    for o in req['options']:
        criteria[o['key']] = laya_option_text(o, req['level'])
        omap[o['key']] = {'answer': 'SELECT', 'option': o['key']}
    criteria['KEEP'] = _keep_text(req)
    criteria['NOT_VISIBLE'] = 'not visible in any camera'
    omap['KEEP'] = {'answer': 'KEEP', 'option': None}
    omap['NOT_VISIBLE'] = {'answer': 'NOT_VISIBLE', 'option': None}
    state: dict[str, Any] = {}
    if r >= 1:
        state['target'] = f"{req['target_color']} clothes (tracker colour label)"
    if r >= 2:
        s = req['snapshot']
        state['last'] = ('none' if s is None or s.get('est_xy') is None else
                         f"{short_cam(s['active_cam'])} ({s['est_xy'][0]:.1f},{s['est_xy'][1]:.1f}) {s['seen_ago_s']:.1f}s ago, {s['state']}")
    state['options'] = '; '.join(_option_line(o, req['level']) for o in req['options']) or 'none'
    if r >= 3 and req.get('scene_summary'):
        g = req['scene_summary']
        state['graph'] = (f"adj {','.join(map(short_cam, g['adjacent'])) or '-'}; ovl "
                          + (','.join(f'{short_cam(c)} {v:.2f}' for c, v in g['overlap_iou'].items()) or '-')
                          + '; footprint_m ' + (','.join(f'{short_cam(c)} {_f(v)}' for c, v in g['footprint_dist_m'].items()) or '-'))
    state['now_s'] = req['now_s']
    q = LAYA_QUESTION[min(r, 1)]
    return state, {'pick': {'type': 'choice', 'instructions': q, 'criteria': criteria}}, omap


def e7_decider_request(req: dict, input_mode: str = 'text_only') -> DeciderRequest:
    e7 = req['e7']
    return DeciderRequest(request_id=req['request_id'], case_id=req['case_id'], dataset_group=req['dataset_group'], tick=req['tick'],
                          variable_text=e7['variable_text'], candidates=tuple(e7['candidates']), camera_ids=tuple(e7['camera_ids']),
                          image_paths={}, input_mode=input_mode)


def _gate_text(o: dict) -> str:
    c = ag.Candidate(o['key'], o['camera_id'], tuple(o['box']), float(o['score']), 'person', tuple(o.get('colors') or ()))
    g = ag.gate_of(c, (TARGET_COLOR,))
    return f"rule_eligible={str(g['rule_eligible']).lower()} gate={','.join(g['reasons']) or '-'}"


def render_vlm(req: dict, scene: dict | None = None) -> dict:
    """-> {'system','text','images':[(label, relpath)],'max_new_tokens'}. L0 = exact E7 prompt (assemble_ao_prompt)."""
    if req['level'] == 'L0':
        return {'system': None, 'text': assemble_ao_prompt(e7_decider_request(req)), 'images': [], 'max_new_tokens': 256}
    r, lv = RANK[req['level']], req['level']
    lines = [f"NOW t={req['now_s']:.1f}s."]
    if r >= 1:
        lines.append(e6_arms.reference_text(req['target_color'], 'none' if lv == 'L4' else 'NO_IMAGE'))
    if r >= 2:
        lines.append('TRACKER_STATE=' + json.dumps(req['snapshot'], sort_keys=True))
    lines.append('OPTIONS (person detections; score>=0.15, CAM_ENTRY>=0.05; one person seen by several cameras is one option):')
    for o in req['options']:
        ln = '- ' + _option_line(o, lv)
        if r >= 1:
            ln += ' ' + _gate_text(o)
        lines.append(ln)
    lines.append(f"- KEEP: {_keep_text(req)}")
    lines.append('- NOT_VISIBLE: not visible in any camera')
    if r >= 3 and req.get('scene_summary') and lv != 'L3F':
        lines.append('CAMERA_RELATIONS=' + json.dumps(req['scene_summary'], sort_keys=True))
    if lv == 'L3F':
        if scene is None or sx.sha256_of(scene) != req.get('scene_context_sha256'):
            raise ValueError('L3F_SCENE_MISMATCH')
        lines.append('SCENE_CONTEXT_SHA256=' + req['scene_context_sha256'] + '\nSCENE_CONTEXT=' + sx.serialize(scene))
    images = []
    if lv == 'L4':
        refs = req.get('image_refs') or {}
        if refs.get('reference'):
            images.append(('TARGET REFERENCE', refs['reference']))
        images += [(f'[frame {cam}]', p) for cam, p in sorted((refs.get('frames') or {}).items())]
    lines.append('Respond with ONLY the JSON object.')
    return {'system': VLM_SYSTEM, 'text': '\n'.join(lines), 'images': images, 'max_new_tokens': 48}


# ------------------------------------------------------------------------------------------------ answers
def _strip_fence(text: str) -> str:
    t = text.strip()
    if t.startswith('```'):
        ls = t.splitlines()
        if len(ls) >= 3 and ls[-1].strip().startswith('```'):
            t = '\n'.join(ls[1:-1]).strip()
    return t


def parse_e8_answer(text: Any, req: dict) -> tuple[dict | None, str | None]:
    """E8 VLM JSON -> ({'answer','option','confidence'}, None) or (None, error). No retries."""
    if not isinstance(text, str):
        return None, 'FORMAT_INVALID'
    try:
        doc = json.loads(_strip_fence(text))
    except (ValueError, TypeError):
        return None, 'FORMAT_INVALID'
    if not isinstance(doc, dict) or doc.get('answer') not in ANSWERS:
        return None, 'FORMAT_INVALID'
    opt = doc.get('option')
    if doc['answer'] == 'SELECT':
        if opt not in {o['key'] for o in req['options']}:
            return None, 'UNKNOWN_OPTION'
    else:
        opt = None
    return {'answer': doc['answer'], 'option': opt, 'confidence': doc.get('confidence')}, None


def laya_choice_answer(answer: Any, omap: dict) -> tuple[dict | None, str | None]:
    """laya ``answers['pick']`` -> E8 answer (non-L0)."""
    choice = answer.get('choice') if isinstance(answer, dict) else None
    spec = omap.get(choice) if isinstance(choice, str) else None
    if spec is None:
        return None, 'LAYA_INVALID_CHOICE'
    conf = answer.get('confidence')
    return {**spec, 'confidence': conf if isinstance(conf, (int, float)) and not isinstance(conf, bool) else None}, None


def from_e7_parsed(parsed: dict | None, err: str | None) -> tuple[dict | None, str | None]:
    """L0: E7 AO answer (parse_ao_json_response output) -> E8 answer; SELECT keeps (camera, detection) as its target."""
    if parsed is None:
        return None, err or 'FORMAT_INVALID'
    a = E7_TO_E8[parsed['answer']]
    return {'answer': a, 'camera_id': parsed.get('camera_id'), 'detection_id': parsed.get('detection_id'),
            'box_xyxy': parsed.get('box_xyxy'), 'confidence': parsed.get('confidence')}, None


def display_of(ans: dict | None, req: dict) -> dict:
    """Resolve an E8 answer to what would be shown (design §2.3): {'kind': 'BOX'|'NONE'|'INVALID'|'NEEDS_MAC', camera_id, detection_id}."""
    if ans is None:
        return {'kind': 'INVALID', 'camera_id': None, 'detection_id': None}
    a = ans['answer']
    if a == 'KEEP':
        k = req.get('keep_display')
        return ({'kind': 'BOX', 'camera_id': k['camera_id'], 'detection_id': k['detection_id'], 'via': 'KEEP'} if k
                else {'kind': 'NONE', 'camera_id': None, 'detection_id': None, 'via': 'KEEP'})
    if a == 'NOT_VISIBLE':
        return {'kind': 'NONE', 'camera_id': None, 'detection_id': None, 'via': 'NOT_VISIBLE'}
    if a == 'OWN_BOX':
        return {'kind': 'NEEDS_MAC', 'camera_id': ans.get('camera_id'), 'detection_id': None, 'box_xyxy': ans.get('box_xyxy')}
    if 'option' in ans:
        o = next(o for o in req['options'] if o['key'] == ans['option'])
        return {'kind': 'BOX', 'camera_id': o['camera_id'], 'detection_id': o['detection_id'], 'via': 'SELECT'}
    return {'kind': 'BOX', 'camera_id': ans['camera_id'], 'detection_id': ans['detection_id'], 'via': 'SELECT'}


# ------------------------------------------------------------------------------------------------ records (no GT; scored by e8_score)
def make_record(req: dict, group: str, ans: dict | None, err: str | None, **extra) -> dict:
    """One scored-ready record. ``first_option``: the chosen option is the first in this order (position bias, §5.4)."""
    disp = display_of(ans, req)
    first = None
    if ans is not None and ans.get('answer') == 'SELECT':
        if 'option' in ans and req.get('options'):
            first = ans['option'] == req['options'][0]['key']
        elif req.get('e7') and req['e7']['candidates']:
            c0 = req['e7']['candidates'][0]
            first = (ans.get('camera_id'), ans.get('detection_id')) == (c0['camera_id'], c0['detection_id'])
    return {'request_id': req['request_id'], 'base_id': req['base_id'], 'case_id': req['case_id'], 'group': group, 'level': req['level'],
            'perm': req['perm'], 'answer': ans and ans.get('answer'), 'error': err, 'display': disp, 'first_option': first, **extra}



# ------------------------------------------------------------------------------------------------ baseline policies (design §2.8)
def baseline_answer(policy: str, req: dict) -> dict:
    """FIRST (L0c+), FIRST_RED (L1+), RANDOM, NEAREST_RED (L2+, no gate), B1 (=KEEP). Computed on the request's own option order."""
    opts = req['options']
    if policy == 'B1':
        return {'answer': 'KEEP', 'option': None}
    if policy == 'FIRST':
        return {'answer': 'SELECT', 'option': opts[0]['key']} if opts else {'answer': 'NOT_VISIBLE', 'option': None}
    if policy == 'FIRST_RED':
        o = next((o for o in opts if TARGET_COLOR in o['colors']), None)
        return {'answer': 'SELECT', 'option': o['key']} if o else {'answer': 'NOT_VISIBLE', 'option': None}
    if policy == 'RANDOM':
        pick = random.Random(f"{SEED}|{req['request_id']}").randrange(len(opts) + 1)
        return {'answer': 'SELECT', 'option': opts[pick]['key']} if pick < len(opts) else {'answer': 'NOT_VISIBLE', 'option': None}
    if policy == 'NEAREST_RED':
        red = [o for o in opts if TARGET_COLOR in o['colors'] and o.get('distance_m') is not None]
        o = min(red, key=lambda o: o['distance_m'], default=None)
        return {'answer': 'SELECT', 'option': o['key']} if o else {'answer': 'NOT_VISIBLE', 'option': None}
    raise ValueError('BAD_POLICY')


# ------------------------------------------------------------------------------------------------ model glue (Part 1 and Part 2)
FRAME_SIZE = (320, 180)
LAYA_LIMITS = {'laya_text': (512, 192), 'laya_typed': (1024, 256)}   # (max_len, head_max_len), HF @246177e5 rl_agent_config.json
LAYA_OPTION_CAP = 48


def answer_with_laya(req: dict, laya_raw) -> tuple[dict | None, str | None]:
    """laya_raw(state, questions) -> answers['pick'] (``build_laya_native_inference_fn(...).raw`` with accelerated bound)."""
    state, questions, omap = render_laya(req)
    pick = laya_raw(state, questions)
    if req['level'] == 'L0':
        e7 = req['e7']
        raw = laya_answer_to_ao_json(pick, omap, tuple(e7['camera_ids']))
        return from_e7_parsed(*parse_ao_json_response(raw, tuple(e7['camera_ids']), tuple(e7['candidates']), FRAME_SIZE))
    return laya_choice_answer(pick, omap)


def answer_with_vlm(req: dict, vlm_raw, *, scene: dict | None = None) -> tuple[dict | None, str | None]:
    """vlm_raw(system, text, image_relpaths, max_new_tokens) -> generated text (images resolved by the caller)."""
    v = render_vlm(req, scene)
    text = vlm_raw(v['system'], v['text'], v['images'], v['max_new_tokens'])
    if req['level'] == 'L0':
        e7 = req['e7']
        return from_e7_parsed(*parse_ao_json_response(text, tuple(e7['camera_ids']), tuple(e7['candidates']), FRAME_SIZE))
    return parse_e8_answer(text, req)


def laya_truncation(state: dict, questions: dict, tokenize, model: str) -> dict:
    """APPROXIMATE audit of laya's input limits (design §2.6, V6) with laya's own tokenizer: options are 'key: text', each capped at
    48 tokens, evenly shrunk when the head (question + options) exceeds head_max_len; the state is cut from the right when the whole
    sequence exceeds max_len. ``tokenize(text) -> list``. The exact rl_common packing is not re-implemented; this is a covariate."""
    max_len, head_max = LAYA_LIMITS[model]
    q = questions['pick']
    n_instr = len(tokenize(q['instructions']))
    opts = [min(LAYA_OPTION_CAP, len(tokenize(f'{k}: {v}'))) for k, v in q['criteria'].items()]
    head = 2 + n_instr + sum(1 + n for n in opts) + 1
    n_state = len(tokenize(json.dumps(state, ensure_ascii=False)))
    shrunk = head > head_max
    used_head = min(head, head_max)
    return {'n_options': len(opts), 'head_tokens': head, 'options_shrunk': shrunk,
            'per_option_budget': (head_max - 16) // max(1, len(opts)) if shrunk else None,
            'state_tokens': n_state, 'state_truncated': used_head + n_state + 1 > max_len, 'approximate': True}


BASELINE_LEVEL = {'FIRST': 'L0c', 'RANDOM': 'L0c', 'FIRST_RED': 'L1', 'NEAREST_RED': 'L2', 'B1': 'L0c'}
