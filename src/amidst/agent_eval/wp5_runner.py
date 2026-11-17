"""WP5 one-command runner: DRY_RUN (default), --fake (full flow, fake clients), --live (needs approval).

    python -m amidst.agent_eval.wp5_runner --set pilot --out OUT                       # estimate only, 0 calls
    python -m amidst.agent_eval.wp5_runner --set pilot --fake --out OUT                # whole flow with fake clients
    python -m amidst.agent_eval.wp5_runner --set pilot --questions Q.jsonl --arm mac \
        --live --approved-usd N --price-table PINNED.json --out OUT                     # after the user approves N

LIVE refuses unless: an approved USD figure is given, the price table is PINNED (dated, sourced), the models belong to
``--arm`` (OpenAI and Rule run on the Mac, local models on the Colab L4), and every requested task type is wired.
No key is read here; providers read OPENAI_API_KEY at call time. Ground truth is never read.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import math
from pathlib import Path
import statistics
import sys
import urllib.error
from typing import Sequence

from amidst.agent_eval import wp5, wp5_fake

ad = importlib.import_module('amidst.q1q5.agent_decision')


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='amidst.agent_eval.wp5_runner', description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--config', default='configs/agent_eval/wp5_v1.json')
    p.add_argument('--set', dest='set_name', required=True)
    p.add_argument('--questions', help='JSONL; rows are DP1/DP3 requests, DP4 requests, or NL {text, vocab}')
    p.add_argument('--out', required=True)
    p.add_argument('--models', help='comma separated model ids (default: all in the set, filtered by --arm)')
    p.add_argument('--skip-types', default='', help='comma separated task types to leave out')
    p.add_argument('--dp4-method', choices=['API','AGENT'], default='API', help='single-call ranking or bounded tool loop; use separate output directories')
    p.add_argument('--all-openai', action='store_true', help='with --arm and no --models: run every OpenAI model of the set, not only the config default_openai_model (D237)')
    p.add_argument('--arm', choices=['mac', 'colab_l4', 'windows'], help='which machine this process runs on (D175); windows runs the same local models as colab_l4 but its latency is never reported (no L4)')
    p.add_argument('--price-table', help='override the price table path')
    p.add_argument('--fake', action='store_true', help='run the whole flow with fake clients (no network, no key)')
    p.add_argument('--fake-timeout-every', type=int, default=None, help='fake backend: every Nth model call times out')
    p.add_argument('--live', action='store_true')
    p.add_argument('--approved-usd', type=float, default=None, help='the amount the user approved in chat for this set')
    return p


def _select(cfg, args) -> tuple[list[str], list[str]]:
    s = cfg['sets'][args.set_name]
    models = [m for m in (args.models.split(',') if args.models else s['models'])]
    unknown = [m for m in models if m not in s['models']]
    if unknown:
        raise wp5.Wp5Error('UNKNOWN_MODEL', ','.join(unknown))
    default = cfg.get('default_openai_model')
    if args.arm and not args.models and not args.all_openai and default:
        models = [m for m in models if wp5.model_by_id(cfg, m)['kind'] != 'OPENAI' or m == default]  # D237: terra is the default OpenAI model
    if args.arm:
        want = 'colab_l4' if args.arm == 'windows' else args.arm  # the Windows machine takes the local-model share
        models = [m for m in models if wp5.model_by_id(cfg, m)['runs_on'] == want]
    skip = [t for t in args.skip_types.split(',') if t]
    types = [t for t in wp5.TASK_TYPES if t not in skip and cfg['sets'][args.set_name]['questions_per_type'].get(t)]
    return models, types


def make_api_guard(table, approved_usd, env=None):
    """The shared spend guard (D165/D166) for a LIVE run: caps and daily/per-minute limits come from the server
    environment (``AMIDST_API_*``); the CLI only supplies the approved total and the PINNED price table.
    Every OpenAI call below goes through ``ApiGuard.run`` (ledger in ``AMIDST_API_USAGE_DIR``)."""
    import dataclasses
    from amidst.q1q5 import api_budget as ab
    cfg = dataclasses.replace(ab.GuardConfig.from_env(env), enabled=True, max_usd_total=float(approved_usd), prices=wp5_prices(table))
    return ab.ApiGuard(cfg)


def guarded_decision_call(api_guard, cfg, model, inner):
    """Wrap a DP1/DP3 OpenAI ``call`` so it only runs when ``ApiGuard`` allows it. A denial is an UNAVAILABLE attempt
    (the decider falls back to the rule); the reason is in the guard ledger."""
    def call(request, *, timeout_ms, max_output_tokens):
        spec = cfg['task_types'][wp5._DP_NAMES.get(request.get('decision_point'), 'DP1')]
        out = api_guard.run('wp5_decision', model['id'], spec['prompt_tokens_est'], max_output_tokens,
                            lambda: _attempt_with_usage(inner, request, timeout_ms, max_output_tokens))
        if not out.allowed:
            return ad.Attempt(ad.CALL_UNAVAILABLE, 0.0)
        return out.value
    call.provider = getattr(inner, '__self__', None)   # execute_call reads last_error / last_diag from it
    return call


def _attempt_with_usage(inner, request, timeout_ms, max_output_tokens):
    """``(attempt, prompt_tokens, completion_tokens)`` for ``ApiGuard.run``. A request the API rejected before running the
    model (HTTP 4xx other than 429) was not billed: record 0/0 instead of letting the guard charge the worst-case estimate
    (WP5 ledger: 11 rows of 400 rejections carried null tokens and were charged USD 0.034 that OpenAI never billed)."""
    attempt = inner(request, timeout_ms=timeout_ms, max_output_tokens=max_output_tokens)
    pt, ct = getattr(attempt, 'prompt_tokens', None), getattr(attempt, 'completion_tokens', None)
    status = ((getattr(getattr(inner, '__self__', None), 'last_error', None) or {}).get('http_status'))
    if pt is None and ct is None and attempt.outcome == ad.CALL_UNAVAILABLE and isinstance(status, int) and 400 <= status < 500 and status != 429:
        pt, ct = 0, 0
    return attempt, pt, ct


def live_context(cfg, table, api_guard=None, *, dp4_method='API'):
    """Real clients. Built only after every LIVE gate has passed.
    OpenAI clients exist only with an ``ApiGuard``; without one the paid layer is refused."""
    from amidst.q1q5 import agent_providers as prov
    from amidst.q1q5 import api_budget as ab
    from amidst.q1q5 import nl_query_parse as nlp
    prices = wp5_prices(table)

    def decision_provider(model):
        if model['kind'] == 'OPENAI':
            if api_guard is None:
                raise wp5.Wp5Error('LIVE_NEEDS_API_GUARD', 'OpenAI calls must go through ApiGuard')
            return guarded_decision_call(api_guard, cfg, model, prov.OpenAIProvider(model=model['id'], api_model_id=api_model_id(cfg, model['id'])).call)
        digest = model.get('digest')
        return prov.OllamaProvider(model=model['id'], model_digest=None if (digest or '').startswith('UNKNOWN') else digest).call

    def nl_client(model):
        if model['kind'] == 'OPENAI':
            if api_guard is None:
                raise wp5.Wp5Error('LIVE_NEEDS_API_GUARD', 'OpenAI calls must go through ApiGuard')
            return ab.GuardedNlClient(nlp.OpenAINlClient(model=model['id'], api_model_id=api_model_id(cfg, model['id']), prices=prices, max_output_tokens=ab.NL_MAX_OUTPUT_TOKENS),
                                      api_guard, caller='wp5_nl', max_output_tokens=ab.NL_MAX_OUTPUT_TOKENS)
        return nlp.OllamaNlClient(model=model['id'])

    def dp4_ranker(model, profile):
        if model['kind'] == 'OPENAI' and api_guard is None:
            raise wp5.Wp5Error('LIVE_NEEDS_API_GUARD', 'DP4 OpenAI calls must go through ApiGuard')
        return Dp4Ranker(cfg, model, profile, table, api_guard, dp4_method)

    return wp5.Context(decision_provider=decision_provider, dp4_ranker=dp4_ranker, nl_client=nl_client, price_table=table)


def dp4_schema(method):
    from amidst.q1q5 import attention_ranking as ar

    ranking = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "camera_id": {"type": "string"},
                "score": {"type": "number", "minimum": 0, "maximum": 1},
                "reason": {"type": "string", "enum": list(ar.REASONS)},
            },
            "required": ["camera_id", "score", "reason"],
            "additionalProperties": False,
        },
    }
    props = {"ranking": ranking}
    if method == "AGENT":
        props.update(
            action={"type": "string", "enum": ["FINAL", "TOOL"]},
            tool={"type": "string", "enum": list(ar.AGENT_TOOLS)},
            args={"type": "object"},
        )
    return {
        "type": "object",
        "properties": props,
        "required": ["action"] if method == "AGENT" else ["ranking"],
        "additionalProperties": False,
    }


def dp4_messages(payload, method):
    prompt = (
        "Rank only camera ids from request.graph (or graph). Return at least the first three, "
        "or all nodes if fewer, unique and descending score [0,1]. Reasons must match the schema. "
        "Identity is unconfirmed; physical navigation unknown. "
    )
    prompt += (
        'Return exactly {"ranking":[...]}.'
        if method == "API"
        else 'Return exactly {"action":"FINAL","ranking":[...]} or '
        '{"action":"TOOL","tool":name,"args":{...}}. Tools: get_graph_neighbors(camera_id), '
        "get_recent_detections(camera_id), update_hypothesis(ranking). Use the supplied tool_results; "
        "never invent detections or graph nodes."
    )
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": ad.canonical(payload).decode("ascii")},
    ]


def dp4_input_estimate(cfg, args):
    """No provider/tokenizer: serialized first-call payload heuristic, kept distinct from config reserves."""
    spec = cfg["task_types"]["DP4"]
    if not cfg["sets"][args.set_name]["questions_per_type"].get(
        "DP4"
    ) or "DP4" in args.skip_types.split(","):
        return None
    rows = (
        [json.loads(s) for s in Path(args.questions).read_text().splitlines() if s.strip()]
        if args.questions
        else wp5_fake.synthetic_rows(cfg["sets"][args.set_name]["questions_per_type"]["DP4"])
    )
    questions = wp5.select_questions(
        rows, {"DP4": cfg["sets"][args.set_name]["questions_per_type"]["DP4"]}
    )
    sizes = []
    for q in questions:
        payload = (
            q["request"]
            if args.dp4_method == "API"
            else {"request": q["request"], "tool_results": [], "step": 1}
        )
        sizes.append(
            len(
                ad.canonical(
                    {
                        "messages": dp4_messages(payload, args.dp4_method),
                        "response_schema": dp4_schema(args.dp4_method),
                    }
                )
            )
        )
    tokens = [math.ceil(n / 4) for n in sizes]
    return {
        "method": args.dp4_method,
        "questions": len(questions),
        "configured_prompt_tokens_per_call": spec["prompt_tokens_est"],
        "max_output_tokens": spec["max_output_tokens"],
        "configured_worst_calls_per_question": spec["worst_case_calls_per_question"],
        "first_call_utf8_bytes": {
            "min": min(sizes),
            "max": max(sizes),
            "mean": statistics.mean(sizes),
        },
        "first_call_tokens_heuristic": {
            "min": min(tokens),
            "max": max(tokens),
            "mean": statistics.mean(tokens),
        },
        "estimator": "ceil(serialized messages + response schema UTF8 bytes / 4), NOT a tokenizer or billed usage",
        "agent_later_steps": "UNKNOWN: depends on model tool choices/results; config reserve and ApiGuard apply each round",
    }


class Dp4Provider:
    """DP4 wire format on existing validated HTTP transports; no DP1/DP3 normalization."""

    def __init__(self, base, kind, method):
        self.base, self.kind, self.method = base, kind, method
        self.last_error = None

    def call(self, payload, *, timeout_ms, max_output_tokens):
        from amidst.q1q5 import agent_providers as prov, attention_ranking as ar

        ar.scan_forbidden(payload)
        ar.validate_request(payload["request"] if self.method == "AGENT" else payload)
        self.last_error = None
        body = self.base._build_payload(payload, max_output_tokens=max_output_tokens)
        body["messages"] = dp4_messages(payload, self.method)
        if self.kind == "OPENAI":
            body["response_format"]["json_schema"]["name"] = (
                "dp4_attention_" + self.method.lower() + "_v1"
            )
        headers = {"Content-Type": "application/json"}
        if self.kind == "OPENAI":
            key = self.base._read_api_key_now()  # reached only inside ApiGuard.run
            if key is None:
                return ad.Attempt("UNAVAILABLE", 0.0)
            headers["Authorization"] = f"Bearer {key}"
            del key
        url = self.base.endpoint if self.kind == "OPENAI" else f"{self.base.endpoint}/api/chat"
        start = self.base._clock_ms()
        try:
            result = self.base._transport(
                url=url, headers=headers, body=ad.canonical(body), timeout_s=timeout_ms / 1000
            )
        except urllib.error.HTTPError as exc:
            self.last_error = {"http_status": exc.code, "detail": "HTTP_ERROR"}
            return ad.Attempt(
                prov._status_outcome(exc.code), max(0.0, self.base._clock_ms() - start)
            )
        except Exception as exc:
            wall = max(0.0, self.base._clock_ms() - start)
            return ad.Attempt(
                "TIMEOUT" if prov._is_timeout_exception(exc) else "UNAVAILABLE",
                wall or (float(timeout_ms) if prov._is_timeout_exception(exc) else 0.0),
            )
        finally:
            headers.clear()
        status, raw, reported = prov._normalize_transport_output(result)
        wall = reported if reported is not None else max(0.0, self.base._clock_ms() - start)
        if status != 200:
            self.last_error = {"http_status": status, "detail": "HTTP_ERROR"}
            return ad.Attempt(prov._status_outcome(status), wall)
        ok, data = prov._parse_json_bytes(raw)
        if not ok or not isinstance(data, dict):
            return ad.Attempt("OK", wall, None)
        pt, ct = prov._extract_tokens(data)
        if self.kind == "OPENAI" and isinstance(data.get("model"), str):
            self.base.last_api_model_id = data["model"]
        if self.kind == "LOCAL" and isinstance(data.get("model_digest") or data.get("digest"), str):
            self.base.model_digest = (data.get("model_digest") or data.get("digest")).removeprefix(
                "sha256:"
            )
        response = (
            prov._extract_openai_response_object(data)
            if self.kind == "OPENAI"
            else prov._extract_ollama_response_object(data)
        )
        return ad.Attempt("TIMEOUT" if wall > timeout_ms else "OK", wall, response, pt, ct)


def make_dp4_provider(cfg, model, method):
    from amidst.q1q5 import agent_providers as prov

    if model["kind"] == "OPENAI":
        base = prov.OpenAIProvider(
            model=model["id"],
            api_model_id=api_model_id(cfg, model["id"]),
            response_schema=dp4_schema(method),
        )
    else:
        digest = model.get("digest")
        base = prov.OllamaProvider(
            model=model["id"],
            model_digest=None if (digest or "").startswith("UNKNOWN") else digest,
            response_schema=dp4_schema(method),
        )
    return Dp4Provider(base, model["kind"], method)


class Dp4Ranker:
    """Per-question usage and guard wrapper; each Agent round is separately guarded."""

    def __init__(self, cfg, model, profile, table, api_guard, method):
        from amidst.q1q5.attention_api import ApiRanker
        from amidst.q1q5.attention_agent import AgentRanker

        self.provider = make_dp4_provider(cfg, model, method)
        self.last_usage = None
        self.attempts = []
        self.last_trace = []
        self.time_exhausted = False
        spec = cfg["task_types"]["DP4"]

        def call(payload, *, timeout_ms, max_output_tokens):
            remaining = profile["per_step_ms"] - sum(a.wall_ms for a in self.attempts)
            if remaining <= 0:
                self.time_exhausted = True
                return ad.Attempt("TIMEOUT", 0.0, None, 0, 0)
            effective = min(timeout_ms, max(1, int(remaining)))
            allowed, reason = True, None
            if model["kind"] == "OPENAI":
                reserve = max(
                    spec["prompt_tokens_est"],
                    math.ceil(
                        len(
                            ad.canonical(
                                {
                                    "messages": dp4_messages(payload, method),
                                    "response_schema": dp4_schema(method),
                                }
                            )
                        )
                        / 4
                    ),
                )
                result = api_guard.run(
                    "wp5_dp4",
                    model["id"],
                    reserve,
                    max_output_tokens,
                    lambda: _attempt_with_usage(
                        self.provider.call, payload, effective, max_output_tokens
                    ),
                )
                attempt = (
                    result.value if result.allowed else ad.Attempt("UNAVAILABLE", 0.0, None, 0, 0)
                )
                allowed, reason = result.allowed, result.reason
                status = (self.provider.last_error or {}).get("http_status")
                if (
                    attempt.outcome == "UNAVAILABLE"
                    and attempt.prompt_tokens is None
                    and attempt.completion_tokens is None
                    and isinstance(status, int)
                    and 400 <= status < 500
                    and status != 429
                ):
                    attempt = ad.Attempt(attempt.outcome, attempt.wall_ms, attempt.response, 0, 0)
            else:
                attempt = self.provider.call(
                    payload, timeout_ms=effective, max_output_tokens=max_output_tokens
                )
            self.attempts.append(attempt)
            base = getattr(self.provider, "base", None)
            self.last_trace.append(
                {
                    "messages": dp4_messages(payload, method),
                    "prompt_sha256": hashlib.sha256(
                        ad.canonical(dp4_messages(payload, method))
                    ).hexdigest(),
                    "model": model["id"],
                    "provider_meta": base.provider_meta() if base else {},
                    "outcome": attempt.outcome,
                    "wall_ms": attempt.wall_ms,
                    "guard_allowed": allowed,
                    "guard_reason": reason,
                    "prompt_tokens": attempt.prompt_tokens,
                    "completion_tokens": attempt.completion_tokens,
                }
            )
            if attempt.wall_ms > effective and attempt.outcome == "OK":
                return ad.Attempt(
                    "TIMEOUT",
                    attempt.wall_ms,
                    None,
                    attempt.prompt_tokens,
                    attempt.completion_tokens,
                )
            return attempt

        prices = wp5_prices(table).get(model["id"])
        price = (
            ((prices["input_usd_per_mtok"], prices["output_usd_per_mtok"]) if prices else None)
            if model["kind"] == "OPENAI"
            else (0.0, 0.0)
        )
        common = dict(
            timeout_ms=profile["per_call_ms"],
            max_output_tokens=spec["max_output_tokens"],
            price_per_mtok=price,
        )
        self.ranker = (
            ApiRanker(call, **common)
            if method == "API"
            else AgentRanker(
                call, max_steps=spec["worst_case_calls_per_question"], budget_usd=None, **common
            )
        )

    def rank(self, request):
        self.attempts = []
        self.last_trace = []
        self.time_exhausted = False
        response = self.ranker.rank(request)
        self.last_usage = {
            key: (
                sum(getattr(a, key) for a in self.attempts)
                if self.attempts and all(getattr(a, key) is not None for a in self.attempts)
                else None
            )
            for key in ("prompt_tokens", "completion_tokens")
        }
        if self.time_exhausted:
            response.update(fallback_reason="TIME_BUDGET", steps=len(self.attempts))
        return response


def api_model_id(cfg, model_id):
    """The real OpenAI API id for a config id, from the committed (FORMAL) parameter set (D237). Raises when unmapped,
    so a LIVE call can never send a config id such as 'astra6' to the API."""
    params = wp5.load_json(cfg['timeout_profiles']['formal']['params_path'])
    mapped = {m['config_id']: m.get('api_model_id') for m in params['models']}
    if not mapped.get(model_id):
        raise wp5.Wp5Error('API_MODEL_ID_UNMAPPED', model_id)
    return mapped[model_id]


def wp5_prices(table):
    return dict((table or {}).get('models') or {})


def write_outputs(out: Path, rows, summary, extra: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    body = b''.join(ad.canonical(r) + b'\n' for r in rows)
    (out / 'calls.jsonl').write_bytes(body)
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')  # insertion order: latency, cost, timeout first, accuracy last
    (out / 'summary.md').write_text(wp5.render_summary_md(summary), encoding='utf-8')
    manifest = dict(extra, n_rows=len(rows), calls_sha256=hashlib.sha256(body).hexdigest())
    (out / 'MANIFEST.json').write_bytes(ad.canonical(manifest) + b'\n')


def main(argv: Sequence[str] | None = None, *, context: wp5.Context | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        cfg = wp5.load_config(args.config)
        table = wp5.load_json(args.price_table or cfg['price_table_path'])
        models, types = _select(cfg, args)
        estimate = wp5.estimate_set(cfg, args.set_name, table, models=models, types=types)
        dp4_estimate = None if args.live else dp4_input_estimate(cfg,args)
    except (ValueError,OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'estimate.json').write_bytes(ad.canonical({'mode': 'DRY_RUN' if not (args.fake or args.live) else 'RUN',
                                                      'provider_calls': 0, 'estimate': estimate,
                                                      'dp4_input_estimate':dp4_estimate}) + b'\n')
    if not (args.fake or args.live):
        return 0
    if args.fake and args.live:
        print('--fake and --live are exclusive', file=sys.stderr)
        return 2

    needs_money = any(wp5.model_by_id(cfg, m)['kind'] == 'OPENAI' for m in models)
    guard = wp5.LocalCapGuard(max_usd=args.approved_usd if (args.live and needs_money) else None)
    try:
        if args.live:
            if needs_money and (args.approved_usd is None or args.approved_usd <= 0):
                raise wp5.Wp5Error('LIVE_NEEDS_APPROVAL', '--approved-usd must be the amount the user approved in chat')
            if needs_money and wp5.price_status(table) != 'PINNED':
                raise wp5.Wp5Error('LIVE_NEEDS_PINNED_PRICES', f'price table status {wp5.price_status(table)}')
            if not args.arm:
                raise wp5.Wp5Error('LIVE_NEEDS_ARM', '--arm mac|colab_l4')
            if not args.questions:
                raise wp5.Wp5Error('LIVE_NEEDS_QUESTIONS', '--questions')
            if not models:
                raise wp5.Wp5Error('NO_MODELS', f'no model of the set runs on {args.arm}')
            verdict = guard.preflight(estimate) if needs_money else None
            if verdict:
                raise wp5.Wp5Error('LIVE_GUARD_REFUSED', verdict)
            api_guard = make_api_guard(table, args.approved_usd) if needs_money else None
            ctx = context or live_context(cfg, table, api_guard,dp4_method=args.dp4_method)
            approval = (f'user approved USD {args.approved_usd} for set {args.set_name}' if needs_money
                        else f'NO_SPEND (Rule/local models only) for set {args.set_name}')
        else:
            ctx, _ = wp5_fake.fake_context(cfg, table, timeout_every=args.fake_timeout_every,dp4_method=args.dp4_method)
            ctx = context or ctx
            approval = 'FAKE_RUN_NO_SPEND'
        if args.questions:
            rows_in = [json.loads(ln) for ln in Path(args.questions).read_text(encoding='utf-8').splitlines() if ln.strip()]
        else:
            rows_in = wp5_fake.synthetic_rows(max(cfg['sets'][args.set_name]['questions_per_type'].values()))
        questions = wp5.select_questions(rows_in, {t: n for t, n in cfg['sets'][args.set_name]['questions_per_type'].items() if t in types})
    except (ValueError,OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    rows = wp5.run_set(ctx, cfg, args.set_name, questions, guard=guard, models=models, types=types, approval_ref=approval)
    summary = wp5.summarize_rows(rows)
    write_outputs(out, rows, summary, {
        'mode': 'LIVE' if args.live else 'FAKE', 'set': args.set_name, 'arm': args.arm, 'models': models, 'types': types,
        'dp4_method':args.dp4_method,
        'guard': guard.name, 'api_guard': 'ApiGuard' if (args.live and needs_money) else None, 'guard_calls': guard.calls, 'guard_spent_usd': guard.spent_usd,
        'guard_blocked': guard.blocked, 'price_status': wp5.price_status(table), 'approval_ref': approval,
        'config_sha256': wp5.sha256_file(Path(args.config) if Path(args.config).is_absolute() else wp5._ROOT / args.config),
        'status': summary['status']})
    for msg in summary['warnings']:
        print(f'WARNING: {msg}', file=sys.stderr)
    if summary['status'] == 'FAILED':
        print('RUN FAILED (results are NOT valid; do not report them):', file=sys.stderr)
        for msg in summary['failures']:
            print(f'  - {msg}', file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
