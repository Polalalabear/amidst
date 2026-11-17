"""Synthetic WP5 questions and fake clients for the dry-run and tests. No network, no key, no GT, no media."""
from __future__ import annotations

import hashlib
import importlib
from typing import Any, Mapping

from amidst.agent_eval import wp5
from amidst.q1q5 import attention_ranking as ar
from amidst.q1q5 import nl_query_parse as nlp

ad = importlib.import_module('amidst.q1q5.agent_decision')

SEEN = 10_000_000
CATALOG = {'class_labels': ['person', 'bag'], 'color_labels': ['red', 'blue', 'green'], 'region_ids': ['R1', 'R2', 'R3'],
           'class_aliases': {'人': 'person', '包': 'bag'}, 'color_aliases': {'紅': 'red', '藍': 'blue', '綠': 'green'},
           'region_aliases': {'西入口': 'R1', '大廳': 'R2', '東出口': 'R3'}}
NL_SENTENCES = ['追蹤紅衣的人 從西入口 0:10 到 0:30', '查找大廳的藍色人', '追蹤綠衣的人', '找東出口的人 0:05 到 0:20',
                '查找西入口的紅色包', '追蹤藍衣的人 從大廳', '找人', '追蹤紅色的人 在東出口']


def _scores(med=0.72):
    return {'n': 5, 'min': 0.5, 'median': med, 'max': 0.9}


def _view(id_, camera='CAM_A', first=0, last=1_000_000, colors=('red',)):
    return {'id': id_, 'camera_id': camera, 'first_seen_us': first, 'last_seen_us': last, 'colors': list(colors),
            'scores': _scores(), 'continuation_fraction': 0.1}


def dp1_request(i: int) -> dict:
    cands = []
    for j, cid in enumerate(('B1', 'B2')):
        c = dict(_view(cid, 'CAM_B', 1_600_000, 1_800_000), gap_us=300_000 + 50_000 * (i + j), graph_edge=True,
                 link_kind='CROSS_CAMERA_HANDOFF', rule_eligible=True)
        c['scores'] = _scores(0.7 + 0.05 * j)
        cands.append(c)
    req = {'schema_version': ad.REQUEST_SCHEMA_VERSION, 'decision_point': ad.DP1, 'as_of_us': 2_000_000 + 100_000 * i,
           'topology': {'graph_status': 'GRAPH_NOT_APPROVED', 'edges': [['CAM_A', 'CAM_B']]}, 'current': _view('A1'),
           'candidates': cands, 'rule_answer': ad.ABSTAIN, 'identity_verdict': 'UNCONFIRMED'}
    req['rule_answer'] = ad.RuleDecider().answer(req)
    return req


def dp3_request(i: int) -> dict:
    req = {'schema_version': ad.REQUEST_SCHEMA_VERSION, 'decision_point': ad.DP3, 'as_of_us': 3_000_000 + 100_000 * i,
           'topology': {'graph_status': 'GRAPH_NOT_APPROVED', 'edges': [['CAM_A', 'CAM_B']]}, 'current': _view('A1'),
           'segment': {'start_us': 1_000_000 + 10_000 * i, 'end_us': 2_000_000, 'n_frames': 10 + i, 'box_scores': _scores(0.6)},
           'rule_answer': ad.ACCEPT_SEGMENT, 'identity_verdict': 'UNCONFIRMED'}
    return req


def _zone(zone_id, x0, x1, edge):
    return {'exit_zone_id': zone_id, 'roi_polygon_px': [[x0, 150], [x1, 150], [x1, 260], [x0, 260]],
            'leads_to_edge_ids': [edge], 'mapping_basis': 'MANUAL_ON_STATIC_FRAME'}


def _transition(src, dst, via):
    return {'transition_id': f'T_{src}__{dst}', 'from_camera_id': src, 'to_camera_id': dst, 'via_exit_zone_ids': [via],
            'relation': 'UNKNOWN', 'region_hops': 1, 'nominal_path_length_m': None,
            'path_traversability': 'TOPOLOGICAL_ONLY', 'path_has_unknown_state': True}


def corridor_graph() -> dict:
    cams = [{'camera_id': 'CAM_A', 'exit_zones': [_zone('A:X_R', 580, 640, 'E_AB')]},
            {'camera_id': 'CAM_B', 'exit_zones': [_zone('B:X_L', 0, 60, 'E_AB'), _zone('B:X_R', 580, 640, 'E_BC')]},
            {'camera_id': 'CAM_C', 'exit_zones': [_zone('C:X_L', 0, 60, 'E_BC')]},
            {'camera_id': 'CAM_D', 'exit_zones': []}]
    trans = [_transition('CAM_B', 'CAM_A', 'B:X_L'), _transition('CAM_B', 'CAM_C', 'B:X_R'),
             _transition('CAM_A', 'CAM_B', 'A:X_R'), _transition('CAM_C', 'CAM_B', 'C:X_L')]
    return {'schema_version': 'q-demo.camera-transition-graph.v1', 'approval_status': 'DRAFT', 'cameras': cams,
            'transitions': trans}


def dp4_request(i: int) -> dict:
    step = 20 if i % 2 == 0 else -20
    start = 300 if step > 0 else 330
    elapsed = 1_500_000 + 250_000 * i
    boxes = [{'time_us': SEEN - (4 - k) * 200_000,
              'bbox_xyxy_px': [start + step * k * 2, 100, start + step * k * 2 + 40, 200]} for k in range(5)]
    last = boxes.pop()
    return {'schema_version': ar.REQUEST_SCHEMA, 'as_of_us': SEEN + elapsed, 'elapsed_us': elapsed,
            'last_observation': {'camera_id': 'CAM_B', 'time_us': SEEN, 'bbox_xyxy_px': last['bbox_xyxy_px'],
                                 'recent_boxes': boxes, 'direction_estimate': None},
            'graph': corridor_graph(), 'camera_summaries': []}


def synthetic_rows(per_type: int = 40) -> list[dict]:
    rows: list[dict] = []
    for i in range(per_type):
        rows.append({'task_type': 'DP1', 'request': dp1_request(i)})
        rows.append({'task_type': 'DP3', 'request': dp3_request(i)})
        rows.append({'task_type': 'DP4', 'request': dp4_request(i)})
        rows.append({'task_type': 'NL', 'text': NL_SENTENCES[i % len(NL_SENTENCES)] + ('' if i < len(NL_SENTENCES) else f' 第{i}段'),
                     'vocab': CATALOG})
    return rows


# ------------------------------------------------------------------ fake clients

def _h(*parts) -> int:
    return int(hashlib.sha256('|'.join(map(str, parts)).encode()).hexdigest()[:8], 16)


class FakeBackend:
    """Deterministic fake. Token counts equal the config estimates, so the dry-run flow reproduces the plan arithmetic."""

    def __init__(self, cfg: Mapping, *, timeout_every: int | None = None, dp4_method: str = 'API'):
        self.cfg, self.timeout_every, self.calls = cfg, timeout_every, 0
        self.dp4_method = dp4_method

    def _latency(self, model: Mapping, key) -> float:
        base = 150.0 if model['kind'] == 'LOCAL' else 400.0
        return base + (_h(model['id'], key) % 600)

    def decision_provider(self, model: Mapping):
        spec = self.cfg['task_types']

        def call(request, *, timeout_ms, max_output_tokens):
            self.calls += 1
            t = wp5._DP_NAMES[request['decision_point']]
            if t == 'DP1':
                resp = {'action': 'SELECT', 'candidate_id': next((c['id'] for c in request['candidates'] if c['rule_eligible']), None),
                        'reason_codes': ['GRAPH_EDGE'], 'rationale': 'fake'}
            else:
                resp = {'action': ad.ACCEPT_SEGMENT, 'reason_codes': ['GRAPH_EDGE'], 'rationale': 'fake'}
            wall = self._latency(model, ad.request_sha256(request))
            if self.timeout_every and self.calls % self.timeout_every == 0:
                return ad.Attempt('TIMEOUT', float(timeout_ms), None, None, None)
            return ad.Attempt('OK', wall, resp, spec[t]['prompt_tokens_est'], max(1, spec[t]['max_output_tokens'] // 2))
        return call

    def dp4_ranker(self, model: Mapping, profile: Mapping):
        spec = self.cfg['task_types']['DP4']
        backend = self

        class _Ranker:
            last_usage: dict | None = None

            def rank(self, request):
                backend.calls += 1
                resp = ar.rank_attention(request)
                resp = dict(resp, method=backend.dp4_method, requested_method=backend.dp4_method, latency_ms=backend._latency(model, ar.request_sha256(request)),
                            steps=1, cost_usd=None)
                self.last_usage = {'prompt_tokens': spec['prompt_tokens_est'], 'completion_tokens': spec['max_output_tokens'] // 2}
                return resp
        return _Ranker()

    def nl_client(self, model: Mapping):
        spec = self.cfg['task_types']['NL']
        backend = self
        label = 'LOCAL' if model['kind'] == 'LOCAL' else 'API'

        class _Client:
            name = label

            def parse(self, text, vocab, timeout_ms):
                backend.calls += 1
                backend._last = backend._latency(model, text)
                return nlp.ClientResult(nlp.parse_rules(text, vocab), spec['prompt_tokens_est'], spec['max_output_tokens'] // 2, None)
        return _Client()


def fake_context(cfg: Mapping, table: Mapping | None, *, timeout_every: int | None = None,
                 dp4_method: str = 'API') -> tuple[wp5.Context, FakeBackend]:
    backend = FakeBackend(cfg, timeout_every=timeout_every, dp4_method=dp4_method)
    clock = _FakeClock(backend)
    ctx = wp5.Context(decision_provider=backend.decision_provider, dp4_ranker=backend.dp4_ranker,
                      nl_client=backend.nl_client, clock_ms=clock, price_table=table)
    return ctx, backend


class _FakeClock:
    """NL latency = the fake's deterministic number: the first read is t0, the second adds it."""

    def __init__(self, backend):
        self.backend, self.t, self.reads = backend, 0.0, 0

    def __call__(self) -> float:
        self.reads += 1
        if getattr(self.backend, '_last', None) is not None:
            self.t += self.backend._last
            self.backend._last = None
        else:
            self.t += 0.01
        return self.t
