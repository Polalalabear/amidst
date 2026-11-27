"""E6 arms (D377/D396, #721): DEANCHOR, DEANCHOR_HIST, DEANCHOR_HIST_SUM on top of the E5 A-open decider.

The original AO request path (decider.py) is untouched. These arms only replace request construction:
  * no current tracking box, no rule display, no rule answer, no rule gates, no ranking-driven frame order;
  * every call compares against the original seed reference crop;
  * HIST: a script-maintained history whose fields are labelled SELF_ANSWER_UNVERIFIED or SYSTEM_OBSERVED;
  * SUM: the model's own short summary of earlier history, kept only if every sentence cites known history ids.
Inference side only: nothing here reads scoring inputs. Identity stays UNCONFIRMED.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

from amidst.live_mode.service_decider import _jpeg
from amidst.q1q5 import agent_service as ag
from amidst.q1q5 import scene_context as sx

from .decider import MODEL, AOpenDecider, sha

ARMS = ('DEANCHOR', 'DEANCHOR_HIST', 'DEANCHOR_HIST_SUM')
ABLATIONS = ('none', 'NO_IMAGE', 'NO_SPATIAL')     # D403: only applied to the receipt's SELECTED_AGENT
SELF = 'SELF_ANSWER_UNVERIFIED'
SYS = 'SYSTEM_OBSERVED'
MAX_HISTORY = 8
MAX_SENTENCES = 3
MAX_SENTENCE_CHARS = 200

# Inference-side key blacklist (case-insensitive substrings of keys/text). Scoring-side data must never get here.
_FORBIDDEN_KEY = re.compile('(?i)(?:ground_?truth|(?:^|[^a-z0-9])gt_|actors|visib|depth|trajector|renderer_track|expected)')
_FORBIDDEN_TEXT = re.compile('(?i)(?:ground_?truth|(?:^|[^a-z0-9])gt_[a-z]|renderer_track|trajector)')

# Static E6 text. Neutral on purpose: nothing hints at a rule gate, a displayed target or a "previous display" (Opus D398).
# The original AO path keeps SYSTEM_TEXT/E5_EXTRA; E6 never uses them.
E6_SYSTEM_TEXT = (
    'You are the decision component of a multi-camera tracker. You decide where one target person is NOW. '
    'Identity can never be confirmed; you only say which detected person looks most like the same person as the reference crop. '
    'The scene context below (JSON) describes the site: region connectivity and exit zones, the camera graph with its approval level, '
    'each camera position/yaw/FOV/ground footprint and overlaps. Edges are topological only; a missing or DRAFT edge is information, '
    'not a prohibition. You may select ANY listed detection, or draw your own box when no listed box covers the person.')

E6_BASE = '''
E6 ANSWER FORMAT. All request frames are 320x180 pixels. OWN_BOX uses these actual pixels:
0 <= x0 < x1 <= 320 and 0 <= y0 < y1 <= 180. Do not rescale coordinates.
Candidates are person detections with score >= 0.15 (CAM_ENTRY >= 0.05).
Return exactly one JSON object with these fields:
{"answer":"SELECT|OWN_BOX|NOT_VISIBLE|UNCERTAIN|STILL_HERE_OCCLUDED",
 "camera_id":null,"detection_id":null,"box_xyxy":null,"next_camera_ranking":[],
 "confidence":"low|medium|high","reason_codes":[],"reason":"short explanation"}.
Use one answer value, not the pipe-separated list. SELECT requires camera_id and detection_id (a listed detection).
OWN_BOX requires camera_id and box_xyxy. Every answer must include next_camera_ranking:
at most three known camera IDs, most likely first. This ranking drives the next search order.
UNCERTAIN: you cannot judge from these frames. NOT_VISIBLE: the person you look for is in none of the shown frames
(still give your ranking). STILL_HERE_OCCLUDED: you judge the person to be in a shown camera but hidden (give camera_id).
Identity remains UNCONFIRMED. Scene edges do not certify physical traversal or collision safety.
'''.strip()

E6_EXTRA = '''
E6 DE-ANCHOR RULES:
Decide from the frames alone: compare every listed person with the TARGET REFERENCE crop (the original first-match
crop) as if you saw this situation for the first time. Never assume that a person is the target because you or
anyone chose that person earlier. Cameras are listed in a fixed order, not ranked by earlier answers.
If you cannot judge, answer UNCERTAIN or NOT_VISIBLE; do not guess.
'''.strip()

E6_PREV_EXTRA = '''
PREVIOUS_ANSWER (when present) is your own latest earlier answer, kept by a script, under SELF_ANSWER_UNVERIFIED:
it is NOT verified and may be wrong; never treat it as evidence about who the target is.
'''.strip()

E6_HIST_EXTRA = '''
HISTORY (when present) is maintained by a script. Fields under SELF_ANSWER_UNVERIFIED are your own
earlier answers: they are NOT verified and may be wrong; never treat them as evidence about who the target is. Fields
under SYSTEM_OBSERVED are what the system measured (times, cameras, whether an answer was applied, how long the pixel
tracker kept an overlapping box after it). SYSTEM_OBSERVED never confirms identity.
'''.strip()

E6_SUM_EXTRA = '''
Also include in your JSON a "summary": at most 3 short sentences, each {"text": "...", "sources": ["H1", ...]}
citing only history ids shown in HISTORY. A sentence with no valid source id causes the whole summary to be
discarded. Summaries are shown back to you only as unverified notes.
'''.strip()


def check_ablation(ablation):
    if ablation not in ABLATIONS:
        raise ValueError('BAD_ABLATION')
    return ablation


def strip_spatial(scene):
    """NO_SPATIAL: keep only the camera ids. Drops regions/edges, camera graph and transitions, camera positions/yaw/FOV/footprints,
    overlaps and any ground-plane geometry (so no camera or target plane coordinates reach the request)."""
    return {'schema': scene.get('schema'), 'identity': 'UNCONFIRMED',
            'cameras': [{'camera_id': c['camera_id']} for c in scene.get('cameras', [])]}


# Static text per ablation: sentences that mention a removed field are removed or reworded (D403).
E6_SYSTEM_TEXT_NO_IMAGE = E6_SYSTEM_TEXT.replace('looks most like the same person as the reference crop',
                                                 'most likely is the person the user asks for')
E6_SYSTEM_TEXT_NO_SPATIAL = (
    'You are the decision component of a multi-camera tracker. You decide where one target person is NOW. '
    'Identity can never be confirmed; you only say which detected person looks most like the same person as the reference crop. '
    'The scene context below (JSON) lists the camera ids. '
    'You may select ANY listed detection, or draw your own box when no listed box covers the person.')
E6_BASE_NO_IMAGE = (E6_BASE.replace('All request frames are 320x180 pixels.', 'Box coordinates are in a 320x180 pixel frame.')
                    .replace('you cannot judge from these frames', 'you cannot judge from these inputs')
                    .replace('is in none of the shown frames', 'is none of the listed detections'))
E6_BASE_NO_SPATIAL = E6_BASE.replace(' Scene edges do not certify physical traversal or collision safety.', '')
E6_EXTRA_NO_IMAGE = '''
E6 DE-ANCHOR RULES:
Decide from the listed detections alone, as if you saw this situation for the first time. Never assume that a person is
the target because you or anyone chose that person earlier. Cameras are listed in a fixed order, not ranked by earlier answers.
If you cannot judge, answer UNCERTAIN or NOT_VISIBLE; do not guess.
'''.strip()
CAMERA_PROPS_SENTENCE = ' Camera properties are in the scene context.'


def static_prefix(scene, extra, ablation='none'):
    check_ablation(ablation)
    system = {'none': E6_SYSTEM_TEXT, 'NO_IMAGE': E6_SYSTEM_TEXT_NO_IMAGE, 'NO_SPATIAL': E6_SYSTEM_TEXT_NO_SPATIAL}[ablation]
    base = {'none': E6_BASE, 'NO_IMAGE': E6_BASE_NO_IMAGE, 'NO_SPATIAL': E6_BASE_NO_SPATIAL}[ablation]
    if ablation == 'NO_SPATIAL':
        scene = strip_spatial(scene)
    return system + '\n\nSCENE_CONTEXT_SHA256=' + sx.sha256_of(scene) + '\nSCENE_CONTEXT=' + sx.serialize(scene) + '\n\n' + base + '\n\n' + extra


def reference_text(colour='red', ablation='none'):
    """Static track-layer text: the colour is the user's query condition, not a tracker label. NO_IMAGE: the query only."""
    if ablation == 'NO_IMAGE':
        return f'TARGET: the user\'s query is "a person wearing {colour}".'
    return (f'TARGET REFERENCE (crop taken when the user\'s query "a person wearing {colour}" was first matched). '
            'The reference crop follows.')


@dataclass(frozen=True)
class ArmConfig:
    name: str
    history: str      # 'previous' (one SELF_ANSWER_UNVERIFIED entry, nothing else) | 'full' (HISTORY with SYSTEM_OBSERVED)
    summary: bool

    @staticmethod
    def of(name):
        if name not in ARMS:
            raise ValueError('BAD_ARM')
        return ArmConfig(name, 'previous' if name == 'DEANCHOR' else 'full', name == 'DEANCHOR_HIST_SUM')

    def extra(self, ablation='none'):
        parts = [E6_EXTRA_NO_IMAGE if ablation == 'NO_IMAGE' else E6_EXTRA, E6_PREV_EXTRA if self.history == 'previous' else E6_HIST_EXTRA]
        if self.summary:
            parts.append(E6_SUM_EXTRA)
        return '\n\n'.join(parts)


def reject_forbidden(obj, where='value', *, text=True):
    """Recursively refuse scoring-side key names or text. ValueError, never silently dropped."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if _FORBIDDEN_KEY.search(str(k)):
                raise ValueError(f'FORBIDDEN_KEY:{where}.{k}')
            reject_forbidden(v, f'{where}.{k}', text=text)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            reject_forbidden(v, f'{where}[{i}]', text=text)
    elif text and isinstance(obj, str) and _FORBIDDEN_TEXT.search(obj):
        raise ValueError(f'FORBIDDEN_TEXT:{where}')


class HistoryLedger:
    """Script-maintained history. One entry per answer; SYSTEM_OBSERVED fields are updated by the script.

    followed_s counts FOLLOWING ticks of the neutral tracker after an applied SELECT/OWN_BOX, until the tracker is LOST
    (or holds an occlusion) or a later *applied* pick replaces it. UNCERTAIN or unapplied answers never cut it short.
    """

    def __init__(self):
        self.entries = []
        self.active = None            # entry whose pick the tracker is currently following

    def add(self, rec, tick):
        n = len(self.entries) + 1
        picked = rec.get('answer') in ('SELECT', 'OWN_BOX') and bool(rec.get('applied'))
        if picked or (rec.get('applied') and rec.get('answer') in ('NOT_VISIBLE', 'STILL_HERE_OCCLUDED')):
            if self.active is not None:
                self.active[SYS]['follow_ended'] = True      # replaced (or cleared) by a later applied answer
            self.active = None
        e = {'id': f'H{n}',
             SYS: {'asked_tick': rec.get('ask_tick', tick), 'applied_tick': tick, 't_s': round(tick / 5, 1),
                   'camera_asked_about': rec.get('camera_id'), 'applied': bool(rec.get('applied')),
                   'fallback_reason': rec.get('fallback_reason'), 'kind': rec.get('kind'),
                   'followed_ticks': 0, 'followed_s': 0.0, 'follow_ended': not picked},
             SELF: {'answer': rec.get('answer'), 'camera_id': rec.get('camera_id'), 'detection_id': rec.get('detection_id'),
                    'box_xyxy': rec.get('box_xyxy'), 'confidence': rec.get('confidence'),
                    'next_camera_ranking': list(rec.get('next_camera_ranking') or [])}}
        reject_forbidden(e, e['id'])
        self.entries.append(e)
        if picked:
            self.active = e
        return e

    def observe(self, neutral_status):
        """Once per tick after the neutral tracker step."""
        e = self.active
        if e is None:
            return
        s = e[SYS]
        if neutral_status == 'FOLLOWING':
            s['followed_ticks'] += 1
            s['followed_s'] = round(s['followed_ticks'] / 5, 1)
        elif neutral_status != 'COASTING':          # LOST or OCCLUDED_HOLD ends the follow; COASTING neither counts nor ends
            s['follow_ended'] = True
            self.active = None

    def view(self):
        return json.loads(json.dumps(self.entries[-MAX_HISTORY:]))

    def previous(self):
        """DEANCHOR: only the latest answer, under SELF_ANSWER_UNVERIFIED. No SYSTEM_OBSERVED field (prereg 2.1, D398)."""
        if not self.entries:
            return None
        return {SELF: json.loads(json.dumps(self.entries[-1][SELF]))}

    def ids(self):
        return {e['id'] for e in self.entries[-MAX_HISTORY:]}


def validate_summary(raw, shown_ids: Iterable[str]):
    """Return a cleaned list of {'text','sources'} or None. All-or-nothing: any bad sentence drops the whole summary."""
    shown = set(shown_ids)
    if not isinstance(raw, list) or not raw or len(raw) > MAX_SENTENCES or not shown:
        return None
    out = []
    for s in raw:
        if not isinstance(s, dict) or not isinstance(s.get('text'), str) or not s['text'].strip():
            return None
        src = s.get('sources')
        if (not isinstance(src, list) or not src or any(not isinstance(i, str) or i not in shown for i in src)
                or len(s['text']) > MAX_SENTENCE_CHARS):
            return None
        out.append({'text': s['text'].strip(), 'sources': sorted(set(src))})
    try:
        reject_forbidden(out, 'summary')
    except ValueError:
        return None
    return out


def variable_text(arm: ArmConfig, t_s, cands, cams, history=None, notes=None, previous=None, ablation='none'):
    lines = [f'NOW t={t_s:.1f}s.',
             'DETECTIONS (person score>=0.15, CAM_ENTRY>=0.05; observations only):']
    for c in cands:
        lines.append(f'- {c.camera_id} {c.id}: {c.class_label} score {c.score:.2f} box '
                     f'[{c.box[0]:.0f},{c.box[1]:.0f},{c.box[2]:.0f},{c.box[3]:.0f}] colours {",".join(c.colors) or "none"}')
    lines.append('CAMERAS THIS CALL (fixed order): ' + ', '.join(cams) + ('.' if ablation == 'NO_SPATIAL' else '.' + CAMERA_PROPS_SENTENCE))
    if arm.history == 'previous':
        lines.append('PREVIOUS_ANSWER=' + json.dumps(previous, sort_keys=True))
    elif arm.history == 'full':
        lines.append('HISTORY=' + json.dumps(history or [], sort_keys=True))
    if arm.summary and notes:
        lines.append('PRIOR_NOTES (your own earlier summary; ' + SELF + ')=' + json.dumps(notes, sort_keys=True))
    return '\n'.join(lines)


class ArmDecider(AOpenDecider):
    """AOpenDecider with E6 request construction. Application, neutral tracking and parsing are inherited unchanged."""

    def __init__(self, arm, transport, scene, projector, *, ablation='none', **kw):
        self.arm = ArmConfig.of(arm)
        self.ablation = check_ablation(ablation)
        self.ledger = HistoryLedger()
        self.notes = None
        self._raw_text = None
        self._shown = set()

        def spy(body):
            resp = transport(body)
            self._raw_text = resp.get('text') if isinstance(resp, dict) else None
            return resp
        super().__init__(spy, scene, projector, **kw)

    def build_input(self, tick, frames, dets, rule_state):
        cands, shots = [], []
        for cam in frames:                       # fixed capture order; self.ranking never reorders (de-anchor)
            boxes = []
            for d in dets.get(cam, []):
                cid = f'D{len(boxes) + 1}'
                colors = tuple(c for c in ('red', 'blue') if d.get('color') == c or d.get(c) in ('STRONG', 'WEAK'))
                cands.append(ag.Candidate(cid, cam, tuple(d['bbox']), float(d['score']), 'person', colors))
                boxes.append((cid, d['bbox']))
            shots.append((cam, _jpeg(frames[cam], boxes) if self.ablation != 'NO_IMAGE' else None))
        no_img = self.ablation == 'NO_IMAGE'
        scene = strip_spatial(self.scene) if self.ablation == 'NO_SPATIAL' else self.scene
        inp = ag.DecisionInput(scene, tick / 5, cands, seed_colors=('red',), reference_jpeg=None if no_img else self.reference,
                               frames=[] if no_img else shots)
        body = ag.build_body(MODEL, inp)
        full_prefix = static_prefix(self.scene, self.arm.extra(self.ablation), self.ablation)
        body['input'][0]['content'][0]['text'] = full_prefix
        body['input'][1]['content'][0]['text'] = reference_text('red', self.ablation)
        history = self.ledger.view() if self.arm.history == 'full' else None
        self._shown = {e['id'] for e in history} if history else set()
        previous = self.ledger.previous() if self.arm.history == 'previous' else None
        var = variable_text(self.arm, tick / 5, cands, [c for c, _ in shots], history,
                            self.notes if self.arm.summary else None, previous, self.ablation)
        reject_forbidden(var, 'variable_text')
        body['input'][-1]['content'][0]['text'] = var
        request = {'t_s': tick / 5, 'arm': self.arm.name, 'ablation': self.ablation,
                   'images': {} if no_img else {c: sha(b) for c, b in shots}, 'reference': None if no_img else sha(self.reference),
                   'candidates': len(cands), 'candidate_list': [
                       {'detection_id': c.id, 'camera_id': c.camera_id, 'box': list(c.box), 'score': c.score,
                        'class_label': c.class_label, 'colors': list(c.colors)} for c in cands],
                   'variable_text': var, 'history_ids': sorted(self._shown), 'prefix_sha256': sha(full_prefix.encode()),
                   'body_sha256': sha(json.dumps(body, sort_keys=True).encode())}
        return inp, body, request

    def _ask(self, tick, kind, frames, dets, rule_state):
        self._raw_text = None
        super()._ask(tick, kind, frames, dets, rule_state)
        rec = self.calls[-1]
        rec['arm'] = self.arm.name
        rec['ablation'] = self.ablation
        self.pending['shown'] = set(self._shown)
        self.pending['summary'] = None
        if self.arm.summary and rec['fallback_reason'] is None and self._raw_text:
            try:
                doc = json.loads(self._raw_text)
                raw = doc.get('summary') if isinstance(doc, dict) else None
            except ValueError:
                raw = None
            self.pending['summary'] = validate_summary(raw, self.pending['shown'])
            rec['summary_valid'] = self.pending['summary'] is not None
            rec['summary_present'] = raw is not None

    def _poll(self, tick):
        p = self.pending
        result = super()._poll(tick)
        if result is not None and p is not None:
            self.ledger.add(result, tick)
            if self.arm.summary and result['fallback_reason'] is None:
                self.notes = p.get('summary')   # None when validation failed: not passed on; failed calls keep older notes
        return result

    def step(self, tick, dets, frames, rule_state):
        row = super().step(tick, dets, frames, rule_state)
        self.ledger.observe(self.neutral.status)
        return row


def scene_sha(scene):
    return sx.sha256_of(scene)
