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

from .decider import E5_EXTRA, MODEL, AOpenDecider, sha

ARMS = ('DEANCHOR', 'DEANCHOR_HIST', 'DEANCHOR_HIST_SUM')
SELF = 'SELF_ANSWER_UNVERIFIED'
SYS = 'SYSTEM_OBSERVED'
MAX_HISTORY = 8
MAX_SENTENCES = 3
MAX_SENTENCE_CHARS = 200

# Inference-side key blacklist (case-insensitive substrings of keys/text). Scoring-side data must never get here.
_FORBIDDEN_KEY = re.compile('(?i)(?:ground_?truth|(?:^|[^a-z0-9])gt_|actors|visib|depth|trajector|renderer_track|expected)')
_FORBIDDEN_TEXT = re.compile('(?i)(?:ground_?truth|(?:^|[^a-z0-9])gt_[a-z]|renderer_track|trajector)')

# E5_EXTRA minus the line that points at the rule state / displayed AO target (not provided in E6 requests).
E5_BASE = '\n'.join(ln for ln in E5_EXTRA.splitlines() if 'AO_STATE' not in ln)

E6_EXTRA = '''
E6 DE-ANCHOR OVERRIDES (apply instead of conflicting instructions above, and together with the A-OPEN rules):
No rule display, rule answer, rule gate result, or currently displayed target box is provided in this request.
Decide from the frames alone: compare every listed person with the TARGET REFERENCE crop (the original first-lock
crop) as if you saw this situation for the first time. Never assume that a person is the target because you or
anyone chose that person earlier. Cameras are listed in a fixed order, not ranked by earlier answers.
STILL_HERE_OCCLUDED is accepted only if the system already holds a target in that camera; otherwise it is ignored.
If you cannot judge, answer UNCERTAIN or NOT_VISIBLE; do not guess.
'''.strip()

E6_HIST_EXTRA = '''
HISTORY (when present) is maintained by a script. Fields under SELF_ANSWER_UNVERIFIED are your own earlier answers:
they are NOT verified and may be wrong; never treat them as evidence about who the target is. Fields under
SYSTEM_OBSERVED are what the system measured (times, cameras, whether an answer was applied, how long the pixel
tracker kept overlapping a box). SYSTEM_OBSERVED never confirms identity.
'''.strip()

E6_SUM_EXTRA = '''
Also include in your JSON a "summary": at most 3 short sentences, each {"text": "...", "sources": ["H1", ...]}
citing only history ids shown in HISTORY. A sentence with no valid source id causes the whole summary to be
discarded. Summaries are shown back to you only as unverified notes.
'''.strip()


@dataclass(frozen=True)
class ArmConfig:
    name: str
    history: bool
    summary: bool

    @staticmethod
    def of(name):
        if name not in ARMS:
            raise ValueError('BAD_ARM')
        return ArmConfig(name, name != 'DEANCHOR', name == 'DEANCHOR_HIST_SUM')

    def extra(self):
        parts = [E6_EXTRA]
        if self.history:
            parts.append(E6_HIST_EXTRA)
        if self.summary:
            parts.append(E6_SUM_EXTRA)
        return '\n\n'.join(parts)


def reject_forbidden(obj, where='value'):
    """Recursively refuse scoring-side key names or text. ValueError, never silently dropped."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if _FORBIDDEN_KEY.search(str(k)):
                raise ValueError(f'FORBIDDEN_KEY:{where}.{k}')
            reject_forbidden(v, f'{where}.{k}')
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            reject_forbidden(v, f'{where}[{i}]')
    elif isinstance(obj, str) and _FORBIDDEN_TEXT.search(obj):
        raise ValueError(f'FORBIDDEN_TEXT:{where}')


class HistoryLedger:
    """Script-maintained history. One entry per applied-or-not answer; SYSTEM_OBSERVED fields are updated by the script."""

    def __init__(self):
        self.entries = []

    def add(self, rec, tick):
        n = len(self.entries) + 1
        if self.entries:
            self.entries[-1][SYS]['follow_ended'] = True
        e = {'id': f'H{n}',
             SYS: {'asked_tick': rec.get('ask_tick', tick), 'applied_tick': tick, 't_s': round(tick / 5, 1),
                   'camera_asked_about': rec.get('camera_id'), 'applied': bool(rec.get('applied')),
                   'fallback_reason': rec.get('fallback_reason'), 'kind': rec.get('kind'),
                   'followed_ticks': 0, 'followed_s': 0.0, 'follow_ended': rec.get('answer') not in ('SELECT', 'OWN_BOX')
                   or not rec.get('applied')},
             SELF: {'answer': rec.get('answer'), 'camera_id': rec.get('camera_id'), 'detection_id': rec.get('detection_id'),
                    'box_xyxy': rec.get('box_xyxy'), 'confidence': rec.get('confidence'),
                    'next_camera_ranking': list(rec.get('next_camera_ranking') or [])}}
        reject_forbidden(e, e['id'])
        self.entries.append(e)
        return e

    def observe(self, neutral_status):
        """Called once per tick after the neutral tracker step: extends how long the latest applied pick was followed."""
        if not self.entries:
            return
        e = self.entries[-1]
        s = e[SYS]
        if s['follow_ended'] or not s['applied']:
            return
        if neutral_status == 'FOLLOWING':
            s['followed_ticks'] += 1
            s['followed_s'] = round(s['followed_ticks'] / 5, 1)
        else:
            s['follow_ended'] = True

    def view(self):
        return json.loads(json.dumps(self.entries[-MAX_HISTORY:]))

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


def variable_text(arm: ArmConfig, t_s, cands, cams, history=None, notes=None):
    lines = [f'NOW t={t_s:.1f}s. No rule display, rule answer or displayed target box is provided.',
             'DETECTIONS (person score>=0.15, CAM_ENTRY>=0.05; observations only):']
    for c in cands:
        lines.append(f'- {c.camera_id} {c.id}: {c.class_label} score {c.score:.2f} box '
                     f'[{c.box[0]:.0f},{c.box[1]:.0f},{c.box[2]:.0f},{c.box[3]:.0f}] colours {",".join(c.colors) or "none"}')
    lines.append('CAMERAS THIS CALL (fixed order): ' + ', '.join(cams) + '. Camera properties are in the scene context.')
    if arm.history:
        lines.append('HISTORY=' + json.dumps(history or [], sort_keys=True))
    if arm.summary and notes:
        lines.append('PRIOR_NOTES (your own earlier summary; ' + SELF + ')=' + json.dumps(notes, sort_keys=True))
    return '\n'.join(lines)


class ArmDecider(AOpenDecider):
    """AOpenDecider with E6 request construction. Application, neutral tracking and parsing are inherited unchanged."""

    def __init__(self, arm, transport, scene, projector, **kw):
        self.arm = ArmConfig.of(arm)
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
            shots.append((cam, _jpeg(frames[cam], boxes)))
        inp = ag.DecisionInput(self.scene, tick / 5, cands, seed_colors=('red',), reference_jpeg=self.reference, frames=shots)
        body = ag.build_body(MODEL, inp)
        prefix = body['input'][0]['content'][0]['text']
        extra = self.arm.extra()
        body['input'][0]['content'][0]['text'] = prefix + '\n\n' + E5_BASE + '\n\n' + extra
        history = self.ledger.view() if self.arm.history else None
        self._shown = {e['id'] for e in history} if history else set()
        var = variable_text(self.arm, tick / 5, cands, [c for c, _ in shots], history, self.notes if self.arm.summary else None)
        reject_forbidden(var, 'variable_text')
        body['input'][-1]['content'][0]['text'] = var
        full_prefix = prefix + '\n\n' + E5_BASE + '\n\n' + extra
        request = {'t_s': tick / 5, 'arm': self.arm.name, 'images': {c: sha(b) for c, b in shots}, 'reference': sha(self.reference),
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
            if self.arm.summary:
                self.notes = p.get('summary')   # None when validation failed: not passed on
        return result

    def step(self, tick, dets, frames, rule_state):
        row = super().step(tick, dets, frames, rule_state)
        self.ledger.observe(self.neutral.status)
        return row


def scene_sha(scene):
    return sx.sha256_of(scene)
