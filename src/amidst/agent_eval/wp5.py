"""WP5 evaluation core: plan, per-call executors, guard interface, summary.

Compares Rule, local models (Colab L4) and OpenAI models on DP1, DP3, DP4 and NL (sentence parse).
Main results are latency (median, p95) and cost; accuracy is recorded and ranked last.

No network, clock or key access here: clients, the guard and the clock are injected
(``Context``). Live adapters are built in ``wp5_runner`` and only on explicit approval.
Ground truth is never read; ``accuracy`` fields are filled later by the Mac scoring package.
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from amidst.agent_eval import latency as latency_mod
from amidst.q1q5 import attention_ranking as ar
from amidst.q1q5 import nl_query_parse as nlp

ad = importlib.import_module('amidst.q1q5.agent_decision')

CONFIG_SCHEMA = 'amidst.wp5-config.v1'
ROW_SCHEMA = 'amidst.wp5-call.v1'
TASK_TYPES = ('DP1', 'DP3', 'DP4', 'NL')
MODEL_KINDS = ('RULE', 'LOCAL', 'OPENAI')
_ROOT = Path(__file__).resolve().parents[3]
_DP_NAMES = {ad.DP1: 'DP1', ad.DP3: 'DP3'}
TIMEOUT_FALLBACKS = ('PROVIDER_TIMEOUT', 'TIME_BUDGET', 'TIMEOUT')
# reply came back but was unusable (DP: agent_decision fallback reasons; NL: nl_query_parse SCHEMA_REJECTED)
FORMAT_FALLBACKS = ('INVALID_RESPONSE', 'ILLEGAL_CANDIDATE', 'EXPLANATION_INVALID', 'SCHEMA_REJECTED')


class Wp5Error(ValueError):
    def __init__(self, code: str, detail: str = ''):
        super().__init__(f'{code}: {detail}' if detail else code)
        self.code = code


# ------------------------------------------------------------------ config

def canonical(value) -> bytes:
    return ad.canonical(value)


def load_json(path: Path | str) -> Any:
    p = Path(path)
    return json.loads((p if p.is_absolute() else _ROOT / p).read_text(encoding='utf-8'))


def load_config(path: Path | str = 'configs/agent_eval/wp5_v1.json') -> dict:
    cfg = load_json(path)
    validate_config(cfg)
    return cfg


def validate_config(cfg: Mapping) -> None:
    if cfg.get('schema_version') != CONFIG_SCHEMA:
        raise Wp5Error('CONFIG_INVALID', 'schema_version')
    if set(cfg['task_types']) != set(TASK_TYPES):
        raise Wp5Error('CONFIG_INVALID', 'task_types')
    ids = [m['id'] for m in cfg['models']]
    if len(set(ids)) != len(ids):
        raise Wp5Error('CONFIG_INVALID', 'duplicate model id')
    for m in cfg['models']:
        if m['kind'] not in MODEL_KINDS or m['runs_on'] not in ('mac', 'colab_l4'):
            raise Wp5Error('CONFIG_INVALID', f"model {m['id']}")
        if m['kind'] == 'OPENAI' and m['id'] not in ad.MODELS:
            raise Wp5Error('CONFIG_INVALID', f"OpenAI model {m['id']} not in {ad.MODELS}")
    for name, s in cfg['sets'].items():
        if s['timeout_profile'] not in cfg['timeout_profiles']:
            raise Wp5Error('CONFIG_INVALID', f'{name}.timeout_profile')
        if any(t not in TASK_TYPES for t in s['questions_per_type']):
            raise Wp5Error('CONFIG_INVALID', f'{name}.questions_per_type')
        if any(mid not in ids for mid in s['models']):
            raise Wp5Error('CONFIG_INVALID', f'{name}.models')
        if not s['phases'] or any(p['repeats'] < 1 for p in s['phases']):
            raise Wp5Error('CONFIG_INVALID', f'{name}.phases')


def model_by_id(cfg: Mapping, model_id: str) -> dict:
    for m in cfg['models']:
        if m['id'] == model_id:
            return m
    raise Wp5Error('UNKNOWN_MODEL', model_id)


def price_status(table: Mapping | None) -> str:
    return table.get('status', 'PINNED') if table else 'NONE'


def cost_usd(table: Mapping | None, model: Mapping, prompt: int | None, completion: int | None) -> float | None:
    """Rule and local cost 0.0; OpenAI cost from the table, ``None`` (UNKNOWN, never estimated) without prices or tokens."""
    if model['kind'] in ('RULE', 'LOCAL'):
        return 0.0
    price = ((table or {}).get('models') or {}).get(model['id'])
    if price is None or prompt is None or completion is None:
        return None
    return (prompt * price['input_usd_per_mtok'] + completion * price['output_usd_per_mtok']) / 1e6


# ------------------------------------------------------------------ plan and estimate

def plan_set(cfg: Mapping, set_name: str, *, models: list[str] | None = None, types: list[str] | None = None) -> list[dict]:
    """Per-model call counts for one set (no calls made)."""
    s = cfg['sets'][set_name]
    repeats = sum(p['repeats'] for p in s['phases'])
    q_per_type = {t: n for t, n in s['questions_per_type'].items() if not types or t in types}
    out = []
    for mid in s['models']:
        if models and mid not in models:
            continue
        out.append({'model': mid, 'questions': sum(q_per_type.values()), 'repeats': repeats,
                    'calls': sum(q_per_type.values()) * repeats,
                    'calls_by_type': {t: n * repeats for t, n in q_per_type.items()}})
    return out


def estimate_set(cfg: Mapping, set_name: str, table: Mapping | None, *, models: list[str] | None = None,
                 types: list[str] | None = None) -> dict:
    """Nominal (one call per question) and worst-case (retries / rounds / steps) calls, tokens and USD."""
    tt = cfg['task_types']
    rows = []
    for entry in plan_set(cfg, set_name, models=models, types=types):
        model = model_by_id(cfg, entry['model'])
        tokens_n = tokens_w = 0
        prompt_n = comp_n = prompt_w = comp_w = 0
        calls_w = 0
        for t, n in entry['calls_by_type'].items():
            if model['kind'] == 'RULE':
                continue
            p, o, w = tt[t]['prompt_tokens_est'], tt[t]['max_output_tokens'], tt[t]['worst_case_calls_per_question']
            prompt_n += n * p
            comp_n += n * o
            prompt_w += n * p * w
            comp_w += n * o * w
            calls_w += n * w
        calls_n = 0 if model['kind'] == 'RULE' else entry['calls']
        usd_n = cost_usd(table, model, prompt_n, comp_n)
        usd_w = cost_usd(table, model, prompt_w, comp_w)
        rows.append({'model': entry['model'], 'kind': model['kind'], 'runs_on': model['runs_on'],
                     'questions': entry['questions'], 'repeats': entry['repeats'],
                     'step_executions': entry['calls'], 'model_calls_nominal': calls_n, 'model_calls_worst': calls_w,
                     'prompt_tokens_nominal': prompt_n, 'completion_tokens_nominal': comp_n,
                     'prompt_tokens_worst': prompt_w, 'completion_tokens_worst': comp_w,
                     'usd_nominal': usd_n, 'usd_worst': usd_w})
    openai = [r for r in rows if r['kind'] == 'OPENAI']
    return {'set': set_name, 'price_status': price_status(table), 'models': rows,
            'openai_calls_nominal': sum(r['model_calls_nominal'] for r in openai),
            'openai_calls_worst': sum(r['model_calls_worst'] for r in openai),
            'openai_usd_nominal': _sum([r['usd_nominal'] for r in openai]),
            'openai_usd_worst': _sum([r['usd_worst'] for r in openai])}


def _sum(values):
    return None if any(v is None for v in values) else sum(values)


# ------------------------------------------------------------------ questions

def normalize_question(row: Mapping) -> dict:
    """Question row -> {task_type, question_id, request|text+vocab}. Rejects forbidden keys before any call."""
    tt = row.get('task_type')
    if tt is None:
        req = row.get('request', row)
        tt = _DP_NAMES.get(req.get('decision_point')) if isinstance(req, Mapping) else None
    if tt not in TASK_TYPES:
        raise Wp5Error('QUESTION_INVALID', f'task_type {tt!r}')
    if tt in ('DP1', 'DP3'):
        req = row.get('request', row)
        ad.validate_request(req)
        if _DP_NAMES[req['decision_point']] != tt:
            raise Wp5Error('QUESTION_INVALID', 'decision_point/task_type mismatch')
        return {'task_type': tt, 'question_id': ad.request_sha256(req)[:16], 'request': req,
                'request_sha256': ad.request_sha256(req)}
    if tt == 'DP4':
        req = row['request']
        ar.validate_request(req)
        return {'task_type': tt, 'question_id': ar.request_sha256(req)[:16], 'request': req,
                'request_sha256': ar.request_sha256(req)}
    text, vocab = row['text'], nlp.vocabulary_from_catalog(row['vocab'])
    if not isinstance(text, str) or not text.strip() or len(text) > nlp.MAX_TEXT:
        raise Wp5Error('QUESTION_INVALID', 'NL text')
    sha = nlp.request_sha256(text, vocab)
    return {'task_type': tt, 'question_id': sha[:16], 'text': text, 'vocab': vocab, 'vocab_doc': dict(row['vocab']),
            'request_sha256': sha}


def select_questions(rows: list[Mapping], questions_per_type: Mapping[str, int]) -> list[dict]:
    """Deterministic pick: per type, the first N by ``request_sha256``. Short supply is an error, not a silent shrink."""
    by_type: dict[str, list[dict]] = {t: [] for t in TASK_TYPES}
    for row in rows:
        q = normalize_question(row)
        by_type[q['task_type']].append(q)
    out = []
    for t in TASK_TYPES:
        want = questions_per_type.get(t, 0)
        pool = sorted({q['request_sha256']: q for q in by_type[t]}.values(), key=lambda q: q['request_sha256'])
        if len(pool) < want:
            raise Wp5Error('QUESTIONS_SHORT', f'{t}: need {want}, have {len(pool)}')
        out.extend(pool[:want])
    return out


# ------------------------------------------------------------------ guard interface

class Guard(Protocol):
    """Hook for the shared API-spend guard (`claude/feat-api-budget`). Until that PR merges, ``LocalCapGuard`` stands in.

    reserve() runs before every billable call and returns ``None`` to allow it, else a reason string (the call is skipped
    and recorded as GUARD_BLOCKED). record() runs after every call with what was actually used.
    """
    name: str

    def preflight(self, plan: Mapping) -> str | None: ...
    def reserve(self, *, model: str, task_type: str, est_prompt_tokens: int, est_completion_tokens: int,
                est_usd: float | None) -> str | None: ...
    def record(self, *, model: str, task_type: str, prompt_tokens: int | None, completion_tokens: int | None,
               cost_usd: float | None) -> None: ...


@dataclass
class LocalCapGuard:
    """Placeholder guard: in-memory caps on calls and USD. Not the shared guard; no persistence across processes."""
    max_usd: float | None = None
    max_calls: int | None = None
    name: str = 'LOCAL_CAP_GUARD_PLACEHOLDER'
    calls: int = 0
    spent_usd: float = 0.0
    reserved_usd: float = 0.0
    unknown_cost_calls: int = 0
    blocked: int = 0
    log: list = field(default_factory=list)

    def preflight(self, plan: Mapping) -> str | None:
        nominal = plan.get('openai_usd_nominal')
        if self.max_usd is not None and (nominal is None or nominal > self.max_usd):
            return 'ESTIMATE_UNKNOWN_OR_ABOVE_APPROVED_USD'
        return None

    def reserve(self, *, model, task_type, est_prompt_tokens, est_completion_tokens, est_usd):
        if self.max_calls is not None and self.calls + 1 > self.max_calls:
            self.blocked += 1
            return 'MAX_CALLS'
        if self.max_usd is not None and est_usd is not None and self.spent_usd + est_usd > self.max_usd:
            self.blocked += 1
            return 'TOTAL_USD'
        return None

    def record(self, *, model, task_type, prompt_tokens, completion_tokens, cost_usd):
        self.calls += 1
        if cost_usd is None:
            self.unknown_cost_calls += 1
        else:
            self.spent_usd += cost_usd
        self.log.append((model, task_type, prompt_tokens, completion_tokens, cost_usd))


# ------------------------------------------------------------------ execution context

@dataclass
class Context:
    """Everything a run needs from outside. Live and fake contexts differ only here."""
    decision_provider: Callable[[Mapping], Callable]          # model dict -> call(request, *, timeout_ms, max_output_tokens) -> Attempt
    dp4_ranker: Callable[[Mapping, Mapping], Any]             # (model dict, profile) -> object with .rank(request) -> response
    nl_client: Callable[[Mapping], Any]                       # model dict -> client with .parse(text, vocab, timeout_ms)
    clock_ms: Callable[[], float] = lambda: time.perf_counter() * 1000.0
    price_table: Mapping | None = None


def _decision_params(profile: Mapping, models: list[Mapping], stage: str, ref: str, cfg: Mapping) -> dict:
    """In-memory approved copy of the committed parameter set for the profile (never written back)."""
    params = copy.deepcopy(load_json(profile['params_path']))
    slots = []
    for m in models:
        slot = m.get('budget_slot')
        if slot and slot not in slots:
            slots.append(slot)
    params['models'] = [{'config_id': s, 'api_model_id': None} for s in slots] or params['models'][:1]
    params['price_table'] = None  # USD is enforced by the Guard, not CallBudget (local models share OpenAI budget slots)
    big = 10 ** 9
    params['stages'] = {stage: {'approved': True, 'approval_ref': ref, 'max_calls': big, 'max_tokens': big * 10,
                                'per_model_max_calls': big, 'per_model_max_tokens': big * 10}}
    return params


def execute_call(ctx: Context, cfg: Mapping, profile: Mapping, model: Mapping, q: Mapping, *,
                 params: Mapping | None, budget: Any) -> dict:
    """Run one question once on one model; return the per-call measurement (no GT, no accuracy label)."""
    t = q['task_type']
    kind = model['kind']
    out: dict[str, Any] = {'latency_ms': None, 'prompt_tokens': None, 'completion_tokens': None, 'steps': 0,
                           'fallback_reason': None, 'decision_source': None, 'answer': None, 'matches_rule': None}
    if t in ('DP1', 'DP3'):
        req = q['request']
        rule = ad.RuleDecider().answer(req)
        if kind == 'RULE':
            t0 = ctx.clock_ms()
            ans = ad.RuleDecider().answer(req)
            out.update(latency_ms=ctx.clock_ms() - t0, answer=ans, decision_source='RULE_ONLY', matches_rule=True)
            return out
        provider_kind = 'OPENAI' if kind == 'OPENAI' else 'OLLAMA_LOOPBACK'
        budget.begin_session()
        call = ctx.decision_provider(model)
        rec = ad.decide(req, mode='AGENT_LIVE', params=params, budget=budget, model=model['budget_slot'],
                        call=call, provider_kind=provider_kind)
        owner = getattr(call, 'provider', None) or getattr(call, '__self__', None)   # guarded OpenAI calls carry .provider
        err = getattr(owner, 'last_error', None)   # why the provider said UNAVAILABLE (HTTP status + body head)
        if err:
            out['provider_error'] = err
        diag = getattr(owner, 'last_diag', None)   # raw reply head (model output only), repairs made, why it was invalid
        if diag:
            out['raw_head'], out['normalized'] = diag.get('raw_head'), diag.get('normalized') or []
            out['invalid_before_repair'], out['invalid_after_repair'] = diag.get('invalid_before_repair'), diag.get('invalid_after_repair')
        attempts = [a for a in rec.get('attempts') or [] if isinstance(a, Mapping)]
        out.update(latency_ms=sum(float(a.get('wall_ms', 0.0)) for a in attempts), steps=len(attempts),
                   prompt_tokens=_sum_opt(a.get('prompt_tokens') for a in attempts),
                   completion_tokens=_sum_opt(a.get('completion_tokens') for a in attempts),
                   fallback_reason=rec['fallback_reason'], decision_source=rec['decision_source'],
                   answer=rec['final_answer'])
        out['matches_rule'] = out['answer'] == rule
        out['attempt_outcomes'] = [a.get('outcome') for a in attempts]
        return out
    if t == 'DP4':
        req = q['request']
        rule_resp = ar.rank_attention(req)
        if kind == 'RULE':
            resp = rule_resp
        else:
            ranker = ctx.dp4_ranker(model, profile)
            resp = ranker.rank(req)
            usage = getattr(ranker, 'last_usage', None) or {}
            out['prompt_tokens'], out['completion_tokens'] = usage.get('prompt_tokens'), usage.get('completion_tokens')
        ar.validate_response(resp, req)
        top = [r['camera_id'] for r in resp['ranking'][:3]]
        out.update(latency_ms=float(resp['latency_ms']), steps=int(resp['steps']), fallback_reason=resp['fallback_reason'],
                   decision_source=resp['method'], answer=top,
                   matches_rule=top[:1] == [rule_resp['ranking'][0]['camera_id']],
                   reported_cost_usd=resp['cost_usd'])
        return out
    # NL
    vocab, text = q['vocab'], q['text']
    rule_parse = nlp.parse_rules(text, vocab)
    if kind == 'RULE':
        t0 = ctx.clock_ms()
        parsed = nlp.parse_rules(text, vocab)
        out.update(latency_ms=ctx.clock_ms() - t0, answer=parsed, decision_source='RULES', matches_rule=True)
        return out
    client = ctx.nl_client(model)
    t0 = ctx.clock_ms()
    try:
        res = client.parse(text, vocab, profile['per_call_ms'])
        wall = ctx.clock_ms() - t0
        parsed = nlp.validate_parse(res.parsed, vocab)
        if wall > profile['per_call_ms']:
            raise nlp.NlClientError('TIMEOUT')
        out.update(latency_ms=wall, prompt_tokens=res.prompt_tokens, completion_tokens=res.completion_tokens, steps=1,
                   answer=parsed, decision_source=client.name)
    except (nlp.NlClientError, nlp.NlSchemaError) as exc:
        code = getattr(exc, 'code', 'SCHEMA_REJECTED')
        wall = ctx.clock_ms() - t0
        out.update(latency_ms=min(wall, float(profile['per_call_ms'])) if code == 'TIMEOUT' else wall, steps=1,
                   fallback_reason='TIMEOUT' if code == 'TIMEOUT' else code, decision_source='RULES', answer=rule_parse)
    out['matches_rule'], out['nl_field_agree'] = nl_agreement(out['answer'], rule_parse)
    return out


NL_COMPARED_FIELDS = ('action', 'location', 'target', 'time')


def nl_agreement(answer: Mapping, rule_parse: Mapping) -> tuple[bool, dict[str, bool]]:
    """Does a model's NL parse agree with the rule parse on the STRUCTURED fields (action, location set, target set, time)?

    WP5 (2026-11-16): the old check was ``answer == rule_parse`` over the whole dict, including ``unrecognized`` - free text
    the rules fill with leftover pieces and a model never reproduces - so agreement was 0/24 for both local models even where
    the structured fields matched. ``unrecognized`` is no longer compared; per-field results are returned too."""
    def norm(v):
        return sorted(v) if isinstance(v, list) else v
    per = {k: norm(answer.get(k)) == norm(rule_parse.get(k)) for k in NL_COMPARED_FIELDS}
    return all(per.values()), per


def _sum_opt(values) -> int | None:
    vals = [v for v in values if isinstance(v, int)]
    return sum(vals) if vals else None


def run_set(ctx: Context, cfg: Mapping, set_name: str, questions: list[dict], *, guard: Guard,
            models: list[str] | None = None, types: list[str] | None = None,
            approval_ref: str = 'UNAPPROVED_DRY_RUN') -> list[dict]:
    """Run a set sequentially (one call at a time; model by model). Returns per-call rows."""
    s = cfg['sets'][set_name]
    profile = cfg['timeout_profiles'][s['timeout_profile']]
    tt = cfg['task_types']
    rows: list[dict] = []
    for entry in plan_set(cfg, set_name, models=models, types=types):
        model = model_by_id(cfg, entry['model'])
        params = budget = None
        if model['kind'] != 'RULE':
            params = _decision_params(profile, [model], s['stage'], approval_ref, cfg)
            budget = ad.CallBudget(params, s['stage'])
        for phase in s['phases']:
            for run_index in range(phase['repeats']):
                for q in questions:
                    t = q['task_type']
                    spec = tt[t]
                    p_est, c_est = spec['prompt_tokens_est'], spec['max_output_tokens']
                    est_usd = cost_usd(ctx.price_table, model, p_est * spec['worst_case_calls_per_question'],
                                       c_est * spec['worst_case_calls_per_question'])
                    row = {'schema_version': ROW_SCHEMA, 'set': set_name, 'phase': phase['name'], 'run_index': run_index,
                           'task_type': t, 'question_id': q['question_id'], 'request_sha256': q['request_sha256'],
                           'model': model['id'], 'model_kind': model['kind'], 'runs_on': model['runs_on'],
                           'report_group': profile['report_group'], 'timeout_ms': profile['per_call_ms'],
                           'step_budget_ms': profile['per_step_ms']}
                    if model['kind'] != 'RULE':
                        reason = guard.reserve(model=model['id'], task_type=t, est_prompt_tokens=p_est,
                                               est_completion_tokens=c_est, est_usd=est_usd)
                        if reason:
                            row.update(outcome='GUARD_BLOCKED', guard_reason=reason, latency_ms=None, prompt_tokens=None,
                                       completion_tokens=None, cost_usd=None, timed_out_fallback=False,
                                       fallback_reason=None, steps=0, answer=None, matches_rule=None, accuracy_correct=None)
                            rows.append(row)
                            continue
                    res = execute_call(ctx, cfg, profile, model, q, params=params, budget=budget)
                    cost = res.pop('reported_cost_usd', None)
                    computed = cost_usd(ctx.price_table, model, res['prompt_tokens'], res['completion_tokens'])
                    cost = computed if computed is not None else cost
                    timed_out = res['fallback_reason'] in TIMEOUT_FALLBACKS or 'PROVIDER_TIMEOUT' in (res.get('attempt_outcomes') or [])
                    row.update(res, outcome='OK', cost_usd=cost, timed_out_fallback=bool(timed_out), accuracy_correct=None)
                    rows.append(row)
                    if model['kind'] != 'RULE':
                        guard.record(model=model['id'], task_type=t, prompt_tokens=res['prompt_tokens'],
                                     completion_tokens=res['completion_tokens'], cost_usd=cost)
    return rows


# ------------------------------------------------------------------ summary

def _pct(values: list[float], p: int):
    return latency_mod.nearest_rank_percentile(sorted(values), p) if values else None


def summarize_rows(rows: list[Mapping]) -> dict:
    """Per model x task type: latency, cost, timeout rate first; accuracy block last. Groups are never mixed."""
    groups: dict[tuple, list[Mapping]] = {}
    for r in rows:
        groups.setdefault((r['report_group'], r['model'], r['task_type']), []).append(r)
    cells = []
    for (group, model, t), rs in sorted(groups.items()):
        run = [r for r in rs if r['outcome'] == 'OK']
        lat = [r['latency_ms'] for r in run if r['latency_ms'] is not None]
        costs = [r['cost_usd'] for r in run if r['cost_usd'] is not None]
        n_timeout = sum(1 for r in run if r['timed_out_fallback'])
        n_unavail = sum(1 for r in run if r['fallback_reason'] == 'PROVIDER_UNAVAILABLE')
        n_format = sum(1 for r in run if r['fallback_reason'] in FORMAT_FALLBACKS)
        kept = [r for r in run if not r['fallback_reason']]      # answered by the model itself (not the fallback rule)
        scored = [r for r in run if r.get('accuracy_correct') is not None]
        cells.append({
            'report_group': group, 'model': model, 'task_type': t,
            'n_rows': len(rs), 'n_ok': len(run), 'n_guard_blocked': len(rs) - len(run),
            'latency_ms': {'n': len(lat), 'p50': _pct(lat, 50), 'p95': _pct(lat, 95),
                           'max': max(lat) if lat else None},
            'cost_usd': {'total': sum(costs) if costs else None, 'p50': _pct(costs, 50), 'p95': _pct(costs, 95),
                         'n_unknown': len(run) - len(costs)},
            'tokens': {'prompt': sum(r['prompt_tokens'] or 0 for r in run),
                       'completion': sum(r['completion_tokens'] or 0 for r in run),
                       'n_missing': sum(1 for r in run if r['prompt_tokens'] is None and r['model_kind'] != 'RULE')},
            'timeout_fallback': {'n': n_timeout, 'rate': (n_timeout / len(run)) if run else None},
            'format_error_fallback': {'n': n_format, 'rate': (n_format / len(run)) if run else None,
                                      'reasons': list(FORMAT_FALLBACKS)},
            'fallback_reasons': _count(r['fallback_reason'] for r in run if r['fallback_reason']),
            'fallback_rate': (sum(1 for r in run if r['fallback_reason']) / len(run)) if run else None,
            'provider_unavailable_rate': (n_unavail / len(run)) if run else None,
            'sources': _count(r['decision_source'] for r in run if r['decision_source']),
            'provider_error_sample': next((r['provider_error'] for r in run if r.get('provider_error')), None),
            'accuracy_recorded_only': {
                'n_answers': sum(1 for r in run if r['answer'] is not None),
                'agreement_with_rule': (sum(1 for r in kept if r['matches_rule']) / len(kept)) if kept else None,
                'agreement_denominator': len(kept),
                'n_excluded_fallback': len(run) - len(kept),
                'agreement_note': 'denominator = rows answered by the model itself; rows that fell back to the rule are excluded (they would agree with the rule by construction)',
                'n_scored': len(scored),
                'correct': sum(1 for r in scored if r['accuracy_correct']) if scored else None,
                'note': 'accuracy_correct stays null here; the Mac scoring package fills it from GT. Not a pass condition.'},
        })
    failures, warnings = health_check(cells)
    return {'schema_version': 'amidst.wp5-summary.v1', 'status': 'FAILED' if failures else 'OK',
            'failures': failures, 'warnings': warnings, 'cells': cells,
            'order_note': 'latency and cost first; accuracy_recorded_only is last and is not a result'}


MAX_FALLBACK_RATE = 0.2


def health_check(cells: list[Mapping]) -> tuple[list[str], list[str]]:
    """A model cell that never reached its provider is a FAILED run, not a result (WP5 v1 Colab: DP1/DP3 were 100%
    PROVIDER_UNAVAILABLE and only the NL cell called the model). A high-but-partial fallback rate is a warning."""
    failures: list[str] = []
    warnings: list[str] = []
    for c in cells:
        if c['n_ok'] == 0 or c['task_type'] == 'NL':
            continue
        label = f"{c['model']} {c['task_type']}"
        rate = c['provider_unavailable_rate']
        if c['task_type'] in ('DP1', 'DP3') and rate is not None and rate >= 1.0:
            sample = c.get('provider_error_sample')
            failures.append(f"{label}: 100% PROVIDER_UNAVAILABLE ({c['n_ok']}/{c['n_ok']}); the model was never called. "
                            f"first error: {sample if sample else 'UNKNOWN (no provider_error recorded)'}")
        elif (c['fallback_rate'] or 0.0) > MAX_FALLBACK_RATE:
            warnings.append(f"{label}: fallback rate {c['fallback_rate']:.0%} > {MAX_FALLBACK_RATE:.0%} {c['fallback_reasons']}")
    return failures, warnings


def _count(items) -> dict:
    out: dict[str, int] = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return out


def render_summary_md(summary: Mapping) -> str:
    def f(v, nd=1):
        return '—' if v is None else (f'{v:.{nd}f}' if isinstance(v, float) else str(v))
    lines = []
    if summary.get('status') == 'FAILED':
        lines += ['**RUN FAILED — not a result:**', ''] + [f'- {m}' for m in summary['failures']] + ['']
    if summary.get('warnings'):
        lines += ['**Warnings:**', ''] + [f'- {m}' for m in summary['warnings']] + ['']
    lines += ['Agree w/ Rule = agreeing rows / rows the model answered itself (fallback rows excluded; excluded count in the last column). Accuracy is record only.', '',
              '| group | model | type | n | p50 ms | p95 ms | cost total USD | cost p95 USD | timeout-fallback | format-error-fallback | agree w/ Rule (answered rows) | excluded fallback rows |',
              '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for c in summary['cells']:
        acc = c['accuracy_recorded_only']
        a = acc['agreement_with_rule']
        agree = '—' if a is None else f"{a:.2f} ({acc['agreement_denominator']})"
        lines.append(f"| {c['report_group']} | {c['model']} | {c['task_type']} | {c['n_ok']} | {f(c['latency_ms']['p50'])} | "
                     f"{f(c['latency_ms']['p95'])} | {f(c['cost_usd']['total'], 4)} | {f(c['cost_usd']['p95'], 4)} | "
                     f"{f(c['timeout_fallback']['rate'], 3)} | {f(c['format_error_fallback']['rate'], 3)} | {agree} | {acc['n_excluded_fallback']} |")
    return '\n'.join(lines) + '\n'


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(v) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)
