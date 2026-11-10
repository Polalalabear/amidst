"""Enhanced deterministic rule baseline R1 for Agent evaluation (WP4, Gate 5).

Contract: docs/contracts/AGENT_EVAL_TOOLCHAIN_GATES_V1.md §3.
Design: docs/design/AGENT_DECISION_V1.md §3.1, §8.2 Q6.
"""
from __future__ import annotations

from collections.abc import Mapping
import copy
import importlib
import json
from pathlib import Path

ad = importlib.import_module('amidst.q1q5.agent_decision')

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PARAMS_PATH = ROOT / 'configs/q1q5/agent_r1_params_v1.json'
VALID_TIE_FIELDS = ('gap_us', 'graph_edge', 'score_median', 'id')


def load_params(path: str | Path | None = None) -> dict:
    """Load R1 parameter configuration; defaults to configs/q1q5/agent_r1_params_v1.json."""
    target = Path(path) if path is not None else DEFAULT_PARAMS_PATH
    data = json.loads(target.read_text(encoding='utf-8'))
    _validate_r1_params(data)
    return data


def _validate_r1_params(params: Mapping) -> None:
    if not isinstance(params, Mapping):
        raise ad.AgentDecisionError('PARAMS_INVALID', 'R1 params must be a mapping')
    required = {'dp1_tie_order', 'dp3_reject_continuation_fraction'}
    if set(params.keys()) != required:
        raise ad.AgentDecisionError('PARAMS_INVALID', 'R1 params keys')
    for key, entry in params.items():
        if not isinstance(entry, Mapping) or set(entry.keys()) != {'value', 'status'}:
            raise ad.AgentDecisionError('PARAMS_INVALID', f'R1 params.{key}')
        if not isinstance(entry['status'], str) or not entry['status']:
            raise ad.AgentDecisionError('PARAMS_INVALID', f'R1 params.{key}.status')
    order = params['dp1_tie_order']['value']
    if not isinstance(order, list) or tuple(order) != VALID_TIE_FIELDS:
        raise ad.AgentDecisionError('PARAMS_INVALID', 'dp1_tie_order.value')
    thresh = params['dp3_reject_continuation_fraction']['value']
    if type(thresh) not in (int, float) or not 0 < float(thresh) < 1:
        raise ad.AgentDecisionError('PARAMS_INVALID', 'dp3_reject_continuation_fraction.value')


def _candidate_sort_key(candidate: Mapping, tie_order: list[str]) -> tuple:
    parts = []
    for field in tie_order:
        if field == 'gap_us':
            parts.append(int(candidate['gap_us']))
        elif field == 'graph_edge':
            parts.append(0 if candidate['graph_edge'] else 1)
        elif field == 'score_median':
            parts.append(-float(candidate['scores']['median']))
        elif field == 'id':
            parts.append(str(candidate['id']))
        else:
            raise ad.AgentDecisionError('PARAMS_INVALID', f'unknown tie field {field!r}')
    return tuple(parts)


class R1Decider:
    """R1 deterministic baseline decider with parameterized tie-breaking and DP3 continuation gate."""

    def __init__(self, params: Mapping | None = None):
        loaded = copy.deepcopy(dict(params)) if params is not None else load_params()
        _validate_r1_params(loaded)
        self._params = loaded

    def params_report(self) -> dict:
        return copy.deepcopy(self._params)

    def answer(self, request: Mapping) -> str:
        ad.validate_request(request)
        dp = request['decision_point']
        if dp == ad.DP3:
            threshold = float(self._params['dp3_reject_continuation_fraction']['value'])
            if float(request['current']['continuation_fraction']) > threshold:
                return ad.REJECT_SEGMENT
            return ad.ACCEPT_SEGMENT

        eligible = [c for c in request['candidates'] if c.get('rule_eligible')]
        if not eligible:
            return ad.ABSTAIN
        tie_order = list(self._params['dp1_tie_order']['value'])
        best = min(eligible, key=lambda c: _candidate_sort_key(c, tie_order))
        return str(best['id'])
