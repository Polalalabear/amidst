"""DP4 attention ranking: multi-step tool-using Agent ranker (D210, D214, N3).

Contract: docs/contracts/DP4_ATTENTION_RANKING_V1.md (§3, §4.3).
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import copy
import math

from amidst.q1q5 import attention_ranking as ar
from amidst.q1q5.attention_api import attempt_cost_usd, rule_fallback

TOOL_NAMES = ar.AGENT_TOOLS
_OUTCOMES = ('OK', 'TIMEOUT', 'UNAVAILABLE', 'RETRYABLE', 'REPLAY_MISS')


class AgentRanker:
    """Multi-step DP4 ranker with bounded tool loop, step cap and USD budget cap."""

    def __init__(
        self,
        call: Callable[..., object],
        *,
        max_steps: int = 5,
        budget_usd: float | None = 0.02,
        timeout_ms: int = 3000,
        max_output_tokens: int = 512,
        price_per_mtok: tuple[float, float] | None = None,
        params: ar.AttentionParams = ar.DEFAULT_PARAMS,
    ) -> None:
        self.call = call
        self.max_steps = max_steps
        self.budget_usd = budget_usd
        self.timeout_ms = timeout_ms
        self.max_output_tokens = max_output_tokens
        self.price_per_mtok = price_per_mtok
        self.params = params

    def _run_tool(
        self,
        tool_name: str,
        args: Mapping,
        request: Mapping,
        nodes: set[str],
    ) -> tuple[dict | None, str | None]:
        try:
            ar.scan_forbidden(args)
        except ar.AttentionInputError:
            return None, 'INVALID_RESPONSE'

        if tool_name == 'get_graph_neighbors':
            if set(args) != {'camera_id'} or not isinstance(args['camera_id'], str):
                return None, 'INVALID_RESPONSE'
            cam_id = args['camera_id']
            if cam_id not in nodes:
                return None, 'ILLEGAL_CANDIDATE'
            neighbors = [
                {
                    'to_camera_id': t.get('to_camera_id'),
                    'relation': t.get('relation'),
                    'via_exit_zone_ids': list(t.get('via_exit_zone_ids', [])),
                }
                for t in request['graph'].get('transitions', [])
                if isinstance(t, Mapping) and t.get('from_camera_id') == cam_id
            ]
            return {'camera_id': cam_id, 'neighbors': neighbors}, None

        if tool_name == 'get_recent_detections':
            if set(args) != {'camera_id'} or not isinstance(args['camera_id'], str):
                return None, 'INVALID_RESPONSE'
            cam_id = args['camera_id']
            if cam_id not in nodes:
                return None, 'ILLEGAL_CANDIDATE'
            summary = next(
                (copy.deepcopy(dict(s)) for s in request['camera_summaries'] if s['camera_id'] == cam_id),
                None,
            )
            return {
                'camera_id': cam_id,
                'status': 'OK' if summary is not None else 'NO_DATA',
                'summary': summary,
            }, None

        if tool_name == 'update_hypothesis':
            if set(args) != {'ranking'}:
                return None, 'INVALID_RESPONSE'
            probe = {
                'schema_version': ar.RESPONSE_SCHEMA,
                'method': 'AGENT',
                'requested_method': 'AGENT',
                'ranking': copy.deepcopy(args['ranking']),
                'latency_ms': 0.0,
                'cost_usd': 0.0,
                'steps': 1,
                'fallback_reason': None,
            }
            try:
                ar.validate_response(probe, request)
            except ar.AttentionInputError as exc:
                reason = 'ILLEGAL_CANDIDATE' if exc.code == 'ILLEGAL_CANDIDATE' else 'INVALID_RESPONSE'
                return None, reason
            return {'status': 'UPDATED', 'ranking': copy.deepcopy(args['ranking'])}, None

        return None, 'INVALID_RESPONSE'

    def rank(self, request: Mapping) -> dict:
        nodes = set(ar.validate_request(request))
        clean_request = copy.deepcopy(dict(request))
        ar.scan_forbidden(clean_request)

        tool_results: list[dict] = []
        total_wall_ms = 0.0
        total_cost = 0.0
        cost_known = self.price_per_mtok is not None
        steps = 0

        def fallback(reason: str) -> dict:
            return rule_fallback(
                request,
                params=self.params,
                requested_method='AGENT',
                fallback_reason=reason,
                wall_ms=total_wall_ms,
                cost_usd=(total_cost if cost_known else None) if steps > 0 else (0.0 if cost_known else None),
                steps=steps,
            )

        if self.budget_usd is not None and self.budget_usd < 0:
            return fallback('CALL_BUDGET_EXHAUSTED')
        if self.max_steps < 1:
            return fallback('ROUND_LIMIT')

        for step in range(1, self.max_steps + 1):
            payload = {
                'request': copy.deepcopy(clean_request),
                'tool_results': copy.deepcopy(tool_results),
                'step': step,
            }
            ar.scan_forbidden(payload)
            try:
                attempt = self.call(
                    payload,
                    timeout_ms=self.timeout_ms,
                    max_output_tokens=self.max_output_tokens,
                )
            except Exception:
                steps += 1
                cost_known = False
                return fallback('PROVIDER_UNAVAILABLE')

            steps += 1
            outcome = getattr(attempt, 'outcome', None)
            wall_ms = getattr(attempt, 'wall_ms', None)
            if outcome not in _OUTCOMES or type(wall_ms) not in (int, float) or not math.isfinite(wall_ms) or wall_ms < 0:
                cost_known = False
                return fallback('INVALID_RESPONSE')

            total_wall_ms += float(wall_ms)
            step_cost, step_cost_known = attempt_cost_usd(
                getattr(attempt, 'prompt_tokens', None),
                getattr(attempt, 'completion_tokens', None),
                self.price_per_mtok,
            )
            if step_cost_known:
                total_cost += step_cost
            else:
                cost_known = False

            if outcome == 'TIMEOUT' or wall_ms > self.timeout_ms:
                return fallback('PROVIDER_TIMEOUT')
            if outcome in ('UNAVAILABLE', 'RETRYABLE'):
                return fallback('PROVIDER_UNAVAILABLE')
            if outcome == 'REPLAY_MISS':
                return fallback('REPLAY_MISS')

            if self.budget_usd is not None and cost_known and total_cost > self.budget_usd:
                return fallback('CALL_BUDGET_EXHAUSTED')

            raw = getattr(attempt, 'response', None)
            if not isinstance(raw, Mapping):
                return fallback('INVALID_RESPONSE')

            action = raw.get('action')
            if action == 'FINAL':
                if set(raw) != {'action', 'ranking'}:
                    return fallback('INVALID_RESPONSE')
                resp = {
                    'schema_version': ar.RESPONSE_SCHEMA,
                    'method': 'AGENT',
                    'requested_method': 'AGENT',
                    'ranking': copy.deepcopy(raw['ranking']),
                    'latency_ms': round(total_wall_ms, 3),
                    'cost_usd': total_cost if cost_known else None,
                    'steps': steps,
                    'fallback_reason': None,
                }
                try:
                    ar.validate_response(resp, request)
                except ar.AttentionInputError as exc:
                    reason = 'ILLEGAL_CANDIDATE' if exc.code == 'ILLEGAL_CANDIDATE' else 'INVALID_RESPONSE'
                    return fallback(reason)
                return resp

            if action == 'TOOL':
                if set(raw) != {'action', 'tool', 'args'}:
                    return fallback('INVALID_RESPONSE')
                tool_name = raw['tool']
                args = raw['args']
                if not isinstance(tool_name, str) or tool_name not in TOOL_NAMES or not isinstance(args, Mapping):
                    return fallback('INVALID_RESPONSE')
                tool_out, err_reason = self._run_tool(tool_name, args, request, nodes)
                if err_reason is not None:
                    return fallback(err_reason)
                ar.scan_forbidden(tool_out)
                tool_results.append({'step': step, 'tool': tool_name, 'result': tool_out})
                continue

            return fallback('INVALID_RESPONSE')

        return fallback('ROUND_LIMIT')
