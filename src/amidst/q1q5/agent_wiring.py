"""Agent decision WP2: wire WP1's decide() into cross_camera_demo.associate().

Design: docs/design/AGENT_DECISION_V1.md §2.5. associate() takes an optional injected
``decider`` (default None = rule-only, byte-identical output). AgentDecider is that object:
it turns the local-track state at a decision point into a WP1 request (opaque ids, only
observations at or before the decision time), calls decide(), and maps the record back.

No file, network, clock or process-state I/O here. The provider is a plain callable
(WP3 supplies real ones; tests use fakes/replay stubs). No API key is read. Any request
that cannot be built or validated falls back to the rule and is audited, never raised.
Identity stays UNCONFIRMED; a SELECT only means "this association hypothesis was chosen".
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import re
from statistics import median

from amidst.q1q5 import agent_decision as ad

AGENT_DECISION_AUDIT = 'AGENT_DECISION_RECORD'
AGENT_REQUEST_REJECTED_AUDIT = 'AGENT_REQUEST_REJECTED'
_CURRENT_ID = 'T0'


def _camera(camera_id: str) -> str:
    """Map a camera id onto the schema's CAM_[A-Z0-9_]{1,40} form (identity if already valid)."""
    if ad.CAMERA_ID.fullmatch(camera_id):
        return camera_id
    return 'CAM_' + re.sub(r'[^A-Z0-9_]', '_', camera_id.upper())[:36]


def _scores(values) -> dict:
    values = sorted(values)
    return {'n': len(values), 'min': values[0], 'median': median(values), 'max': values[-1]}


def _track_summary(track, up_to_us: int, camera_map, colors, id_):
    obs = [o for o in track.observations if o.timestamp_us <= up_to_us]
    continuation = sum(o.evidence_kind == 'BOX_CONTINUATION' for o in obs)
    return {'id': id_, 'camera_id': camera_map(track.camera_id), 'first_seen_us': obs[0].timestamp_us,
            'last_seen_us': obs[-1].timestamp_us,
            'colors': [c for c in ad.COLORS if c in colors],
            'scores': _scores(o.score for o in obs), 'continuation_fraction': continuation / len(obs)}


class AgentDecider:
    """Injectable decider for associate(). ``mode`` OFF/RULE_ONLY never calls decide()."""

    def __init__(self, *, params: Mapping, mode: str = ad.DEFAULT_MODE, budget: ad.CallBudget | None = None,
                 model: str | None = None, call: ad.Provider | None = None, provider_kind: str = 'NONE',
                 provider_meta: Mapping | None = None, graph_status: str = 'GRAPH_NOT_APPROVED'):
        if mode not in ad.MODES:
            raise ad.AgentDecisionError('MODE_INVALID', str(mode))
        ad.validate_params(params)
        self.params, self.mode, self.budget, self.model = params, mode, budget, model
        self.call, self.provider_kind, self.provider_meta = call, provider_kind, provider_meta
        self.graph_status = graph_status
        self.records: list[dict] = []

    @property
    def active(self) -> bool:
        return self.mode in ad.AGENT_MODES

    # ------------------------------------------------------------ shared
    def _run(self, request: dict, timestamp_us: int, point: str, rejected_context: dict):
        """decide() one request; return (record, audit_row). A bad request is audited, not raised."""
        try:
            record = ad.decide(request, mode=self.mode, params=self.params, budget=self.budget, model=self.model,
                               call=self.call, provider_kind=self.provider_kind, provider_meta=self.provider_meta)
        except ad.AgentDecisionError as exc:
            if exc.code not in ('REQUEST_INVALID', 'FORBIDDEN_INFERENCE_INPUT'):
                raise  # configuration / provider-contract errors are bugs, not data problems
            return None, {'reason': AGENT_REQUEST_REJECTED_AUDIT, 'timestamp_us': timestamp_us,
                          'decision_point': point, 'code': exc.code, 'detail': exc.detail,
                          'identity_verdict': ad.UNCONFIRMED, **rejected_context}
        self.records.append(record)
        return record, {'reason': AGENT_DECISION_AUDIT, 'timestamp_us': timestamp_us, 'decision_point': point,
                        'decision_source': record['decision_source'], 'fallback_reason': record['fallback_reason'],
                        'request_sha256': record['request_sha256'], 'final_answer': record['final_answer'],
                        'rule_answer': record['rule_answer'], 'record': record,
                        'identity_verdict': ad.UNCONFIRMED}

    def _topology(self, transitions) -> dict:
        edges = sorted([_camera(a), _camera(b)] for a, b in transitions)
        return {'graph_status': self.graph_status, 'edges': edges}

    # ------------------------------------------------------------ DP1
    def handoff(self, ctx: Mapping):
        """DP1. Returns (None, None) to use the rule, else (('SELECT', track_ref) | ('ABSTAIN', None), audit)."""
        if not self.active:
            return None, None
        t, step = ctx['timestamp_us'], ctx['sample_interval_us']
        known = ctx['known_colors']
        eligible = [c for c in ctx['considered'] if c['eligible']]
        ineligible = [c for c in ctx['considered'] if not c['eligible']]
        ordered = (eligible + ineligible)[:ad.MAX_CANDIDATES]
        ids = {}
        for i, item in enumerate(ordered):  # opaque ids; the table lives only in this call
            ids[f'{chr(65 + i)}{i + 1}'] = item['track'].track_ref
        by_id = dict(zip(ids, ordered))
        candidates = []
        for opaque, item in by_id.items():
            track = item['track']
            summary = _track_summary(track, t, _camera, known(track, t), opaque)
            summary.update({'gap_us': item['row']['gap_us'], 'graph_edge': item['graph_edge'],
                            'link_kind': item['row']['link_kind'], 'rule_eligible': item['eligible']})
            candidates.append(summary)
        rule_ids = [c['id'] for c in candidates if c['rule_eligible']]
        rule = rule_ids[0] if len(rule_ids) == 1 else ad.ABSTAIN
        try:
            request = {'schema_version': ad.REQUEST_SCHEMA_VERSION, 'decision_point': ad.DP1, 'as_of_us': t + step,
                       'topology': self._topology(ctx['transitions']),
                       'current': _track_summary(ctx['current'], t, _camera, ctx['current_colors'], _CURRENT_ID),
                       'candidates': candidates, 'rule_answer': rule, 'identity_verdict': ad.UNCONFIRMED}
        except (ValueError, IndexError, TypeError) as exc:  # e.g. non-finite score
            return None, {'reason': AGENT_REQUEST_REJECTED_AUDIT, 'timestamp_us': t, 'decision_point': ad.DP1,
                          'code': 'REQUEST_INVALID', 'detail': type(exc).__name__, 'identity_verdict': ad.UNCONFIRMED}
        if len(eligible) > ad.MAX_CANDIDATES:
            return None, {'reason': AGENT_REQUEST_REJECTED_AUDIT, 'timestamp_us': t, 'decision_point': ad.DP1,
                          'code': 'REQUEST_INVALID', 'detail': 'too many eligible candidates',
                          'identity_verdict': ad.UNCONFIRMED}
        record, audit = self._run(request, t, ad.DP1, {})
        if record is None or record['decision_source'] != 'AGENT':
            return None, audit  # fallback == rule answer; associate() applies the rule itself
        answer = record['final_answer']
        if answer == ad.ABSTAIN:
            return ('ABSTAIN', None), audit
        return ('SELECT', ids[answer]), audit

    # ------------------------------------------------------------ DP3
    def continuation(self, ctx: Mapping):
        """DP3 for one run of BOX_CONTINUATION observations. Returns ('ACCEPT'|'REJECT'|None, audit)."""
        if not self.active:
            return None, None
        run, track = ctx['run'], ctx['track']
        start, end = run[0].timestamp_us, ctx['segment_end_us']
        try:
            request = {'schema_version': ad.REQUEST_SCHEMA_VERSION, 'decision_point': ad.DP3,
                       'as_of_us': end, 'topology': self._topology({}),
                       'current': _track_summary(track, run[-1].timestamp_us, _camera,
                                                 ctx['known_colors'](track, run[-1].timestamp_us), _CURRENT_ID),
                       'segment': {'start_us': start, 'end_us': end, 'n_frames': len(run),
                                   'box_scores': _scores(o.score for o in run)},
                       'rule_answer': ad.ACCEPT_SEGMENT, 'identity_verdict': ad.UNCONFIRMED}
        except (ValueError, IndexError, TypeError) as exc:
            return None, {'reason': AGENT_REQUEST_REJECTED_AUDIT, 'timestamp_us': start, 'decision_point': ad.DP3,
                          'code': 'REQUEST_INVALID', 'detail': type(exc).__name__, 'identity_verdict': ad.UNCONFIRMED}
        record, audit = self._run(request, start, ad.DP3, {})
        if record is None or record['decision_source'] != 'AGENT':
            return None, audit
        return ('REJECT' if record['final_answer'] == ad.REJECT_SEGMENT else 'ACCEPT'), audit
