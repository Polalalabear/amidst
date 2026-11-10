"""Question bank builder and extractor for Agent decision evaluation (WP4, Gates 1-2).

Contract: docs/contracts/AGENT_EVAL_TOOLCHAIN_GATES_V1.md §1.
Design: docs/design/AGENT_DECISION_V1.md §3.3, §4.1-§4.2.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import copy
import hashlib
import importlib
import json
from pathlib import Path
import random

ad = importlib.import_module('amidst.q1q5.agent_decision')

QUESTION_VERSION = 'amidst.agent-eval-question.v1'
QUESTION_CLASSES = ('REAL', 'SYNTHETIC_PERTURBATION')
EXTRA_FORBIDDEN = (
    'visib' + 'ility',
    'dep' + 'th',
    'traject' + 'ory',
    'gt_' + 'private',
    'scoring_' + 'private',
    'ground' + '_truth',
)


def is_forbidden_key(key: object) -> bool:
    low = str(key).lower()
    return low in ad.FORBIDDEN_KEYS or low.startswith('gt_') or any(low == e for e in EXTRA_FORBIDDEN)


def scan_no_forbidden_keys(value: object, code: str = 'FORBIDDEN_INFERENCE_INPUT') -> None:
    if isinstance(value, Mapping):
        for k, v in value.items():
            if not isinstance(k, str):
                raise ad.AgentDecisionError(code, 'non-string key')
            if is_forbidden_key(k):
                raise ad.AgentDecisionError(code, k)
            scan_no_forbidden_keys(v, code)
    elif isinstance(value, (list, tuple)):
        for item in value:
            scan_no_forbidden_keys(item, code)


def allowed_answers_for_request(request: Mapping) -> list[str]:
    dp = request['decision_point']
    if dp == ad.DP1:
        return [c['id'] for c in request['candidates']] + [ad.ABSTAIN]
    if dp == ad.DP3:
        return [ad.ACCEPT_SEGMENT, ad.REJECT_SEGMENT]
    raise ad.AgentDecisionError('REQUEST_INVALID', f'unknown decision_point {dp!r}')


def reorder_request_candidates(request: Mapping, candidate_order_seed: int) -> dict:
    """Return a copy of ``request`` with candidates deterministically permuted by ``candidate_order_seed``."""
    out = copy.deepcopy(dict(request))
    if out.get('decision_point') == ad.DP1 and candidate_order_seed != 0:
        cands = list(out['candidates'])
        rng = random.Random(f"{ad.request_sha256(out)}:{candidate_order_seed}")
        rng.shuffle(cands)
        out['candidates'] = cands
    return out


def build_questions(
    requests: Iterable[Mapping],
    *,
    source_run: str,
    commit: str,
    params_sha256: str,
    scene_sha256: str,
    candidate_order_seed: int = 0,
    question_class: str = 'REAL',
) -> list[dict]:
    """Validate every request and wrap into versioned evaluation question records.

    Any FORBIDDEN key or invalid request fails the entire batch with AgentDecisionError.
    """
    if not isinstance(source_run, str) or not source_run:
        raise ad.AgentDecisionError('REQUEST_INVALID', 'source_run')
    if not isinstance(commit, str) or not commit:
        raise ad.AgentDecisionError('REQUEST_INVALID', 'commit')
    if not isinstance(params_sha256, str) or not ad.SHA256.fullmatch(params_sha256):
        raise ad.AgentDecisionError('REQUEST_INVALID', 'params_sha256')
    if not isinstance(scene_sha256, str) or not ad.SHA256.fullmatch(scene_sha256):
        raise ad.AgentDecisionError('REQUEST_INVALID', 'scene_sha256')
    if type(candidate_order_seed) is not int:
        raise ad.AgentDecisionError('REQUEST_INVALID', 'candidate_order_seed')
    if question_class not in QUESTION_CLASSES:
        raise ad.AgentDecisionError('REQUEST_INVALID', 'question_class')

    req_list = [copy.deepcopy(dict(r)) for r in requests]
    # Validate the entire batch upfront so any forbidden key rejects the whole batch.
    for req in req_list:
        scan_no_forbidden_keys(req)
        ad.validate_request(req)

    questions: list[dict] = []
    for req in req_list:
        sha = ad.request_sha256(req)
        q = {
            'schema_version': QUESTION_VERSION,
            'decision_point': req['decision_point'],
            'source_run': source_run,
            'commit': commit,
            'params_sha256': params_sha256,
            'scene_sha256': scene_sha256,
            'request_sha256': sha,
            'candidate_order_seed': candidate_order_seed,
            'question_class': question_class,
            'allowed_answers': allowed_answers_for_request(req),
            'request': req,
        }
        scan_no_forbidden_keys(q)
        questions.append(q)
    return questions


def write_question_bank(questions: Sequence[Mapping], out_dir: str | Path) -> dict:
    """Write ``requests_v1.jsonl`` and ``MANIFEST.json`` deterministically and return the manifest."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    lines: list[bytes] = []
    for q in questions:
        scan_no_forbidden_keys(q)
        ad.validate_request(q['request'])
        lines.append(ad.canonical(q) + b'\n')

    requests_bytes = b''.join(lines)
    requests_file = out_path / 'requests_v1.jsonl'
    requests_file.write_bytes(requests_bytes)
    requests_sha256 = hashlib.sha256(requests_bytes).hexdigest()

    first = questions[0] if questions else {}
    manifest = {
        'commit': first.get('commit', ''),
        'params_sha256': first.get('params_sha256', ''),
        'scene_sha256': first.get('scene_sha256', ''),
        'n_questions': len(questions),
        'requests_sha256': requests_sha256,
    }
    scan_no_forbidden_keys(manifest)
    manifest_file = out_path / 'MANIFEST.json'
    manifest_file.write_bytes(ad.canonical(manifest) + b'\n')
    return manifest


def count_ambiguous_episodes(questions: Sequence[Mapping], *, max_step_us: int = 200_000) -> dict:
    """Count DP1 ambiguity episodes (D203: consecutive ambiguous timestamps within max_step_us)."""
    by_run: dict[str, list[int]] = {}
    ambiguous_points = 0
    for q in questions:
        req = q['request']
        if req['decision_point'] != ad.DP1:
            continue
        eligible = [c for c in req['candidates'] if c.get('rule_eligible')]
        if len(eligible) >= 2:
            ambiguous_points += 1
            by_run.setdefault(q.get('source_run', 'unknown'), []).append(int(req['as_of_us']))

    episodes_by_run: dict[str, list[dict]] = {}
    total_episodes = 0
    for run_id, times in sorted(by_run.items()):
        eps: list[dict] = []
        last: int | None = None
        for t in sorted(set(times)):
            if last is None or t - last > max_step_us:
                eps.append({'start_us': t, 'end_us': t, 'n_timestamps': 1})
            else:
                eps[-1]['end_us'] = t
                eps[-1]['n_timestamps'] += 1
            last = t
        episodes_by_run[run_id] = eps
        total_episodes += len(eps)
    return {
        'n_ambiguous_timestamps': ambiguous_points,
        'n_ambiguous_episodes': total_episodes,
        'episodes_by_run': episodes_by_run,
    }


def extract_requests_from_run(
    tracks,
    transitions,
    *,
    as_of_us: int,
    parameters,
    clock_mapping_sha256: str,
    params: Mapping,
    graph_status: str = 'GRAPH_NOT_APPROVED',
) -> tuple[list[dict], tuple]:
    """Extract all DP1 and DP3 requests from a run without altering associate()/response() output."""
    wiring = importlib.import_module('amidst.q1q5.agent_wiring')
    ccd = importlib.import_module('amidst.q1q5.cross_camera_demo')

    captured: list[dict] = []
    # Use a copy of params with max session rounds so extraction never truncates on long runs.
    extract_params = copy.deepcopy(dict(params))
    extract_params['per_session'] = {'max_rounds': ad.PARAM_MAX['session_max_rounds']}
    budget = ad.CallBudget(extract_params, next(iter(extract_params['stages'])))
    model_id = extract_params['models'][0]['config_id']

    def _spy_provider(request, *, timeout_ms, max_output_tokens):
        captured.append(copy.deepcopy(request))
        return ad.Attempt(ad.CALL_REPLAY_MISS, 0.0)

    inner = wiring.AgentDecider(
        params=extract_params,
        mode='AGENT_REPLAY',
        budget=budget,
        model=model_id,
        call=_spy_provider,
        provider_kind='OPENAI',
        graph_status=graph_status,
    )

    class _PassiveExtractor:
        def handoff(self, ctx):
            budget.begin_session()
            inner.handoff(ctx)
            return None, None

        def continuation(self, ctx):
            budget.begin_session()
            inner.continuation(ctx)
            return None, None

    res = ccd.response(
        tracks,
        transitions,
        as_of_us=as_of_us,
        parameters=parameters,
        clock_mapping_sha256=clock_mapping_sha256,
        decider=_PassiveExtractor(),
    )
    return captured, res
