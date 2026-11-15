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
import hashlib
import importlib
import json
from pathlib import Path
import sys
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
    p.add_argument('--skip-types', default='', help='comma separated task types to leave out (for example DP4 until #532 is wired)')
    p.add_argument('--arm', choices=['mac', 'colab_l4'], help='which machine this process runs on (D175)')
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
    if args.arm:
        models = [m for m in models if wp5.model_by_id(cfg, m)['runs_on'] == args.arm]
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
    return call


def _attempt_with_usage(inner, request, timeout_ms, max_output_tokens):
    attempt = inner(request, timeout_ms=timeout_ms, max_output_tokens=max_output_tokens)
    return attempt, getattr(attempt, 'prompt_tokens', None), getattr(attempt, 'completion_tokens', None)


def live_context(cfg, table, api_guard=None):
    """Real clients. Built only after every LIVE gate has passed. DP4 is a reserved hook until #532 (ApiRanker) merges.
    OpenAI clients exist only with an ``ApiGuard``; without one the paid layer is refused."""
    from amidst.q1q5 import agent_providers as prov
    from amidst.q1q5 import api_budget as ab
    from amidst.q1q5 import nl_query_parse as nlp
    prices = wp5_prices(table)

    def decision_provider(model):
        if model['kind'] == 'OPENAI':
            if api_guard is None:
                raise wp5.Wp5Error('LIVE_NEEDS_API_GUARD', 'OpenAI calls must go through ApiGuard')
            return guarded_decision_call(api_guard, cfg, model, prov.OpenAIProvider(model=model['id']).call)
        digest = model.get('digest')
        return prov.OllamaProvider(model=model['id'], model_digest=None if (digest or '').startswith('UNKNOWN') else digest).call

    def nl_client(model):
        if model['kind'] == 'OPENAI':
            if api_guard is None:
                raise wp5.Wp5Error('LIVE_NEEDS_API_GUARD', 'OpenAI calls must go through ApiGuard')
            return ab.GuardedNlClient(nlp.OpenAINlClient(model=model['id'], prices=prices, max_output_tokens=ab.NL_MAX_OUTPUT_TOKENS),
                                      api_guard, caller='wp5_nl', max_output_tokens=ab.NL_MAX_OUTPUT_TOKENS)
        return nlp.OllamaNlClient(model=model['id'])

    def dp4_ranker(model, profile):
        raise wp5.Wp5Error('DP4_LIVE_NOT_WIRED', 'awaiting #532 (attention_api.ApiRanker); rerun with --skip-types DP4 or wire this hook')

    return wp5.Context(decision_provider=decision_provider, dp4_ranker=dp4_ranker, nl_client=nl_client, price_table=table)


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
    except wp5.Wp5Error as exc:
        print(str(exc), file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'estimate.json').write_bytes(ad.canonical({'mode': 'DRY_RUN' if not (args.fake or args.live) else 'RUN',
                                                      'provider_calls': 0, 'estimate': estimate}) + b'\n')
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
            ctx = context or live_context(cfg, table, api_guard)
            if 'DP4' in types and context is None:
                ctx.dp4_ranker(None, None)  # raises DP4_LIVE_NOT_WIRED while the hook is reserved
            approval = (f'user approved USD {args.approved_usd} for set {args.set_name}' if needs_money
                        else f'NO_SPEND (Rule/local models only) for set {args.set_name}')
        else:
            ctx, _ = wp5_fake.fake_context(cfg, table, timeout_every=args.fake_timeout_every)
            ctx = context or ctx
            approval = 'FAKE_RUN_NO_SPEND'
        if args.questions:
            rows_in = [json.loads(ln) for ln in Path(args.questions).read_text(encoding='utf-8').splitlines() if ln.strip()]
        else:
            rows_in = wp5_fake.synthetic_rows(max(cfg['sets'][args.set_name]['questions_per_type'].values()))
        questions = wp5.select_questions(rows_in, {t: n for t, n in cfg['sets'][args.set_name]['questions_per_type'].items() if t in types})
    except (wp5.Wp5Error, ad.AgentDecisionError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    rows = wp5.run_set(ctx, cfg, args.set_name, questions, guard=guard, models=models, types=types, approval_ref=approval)
    summary = wp5.summarize_rows(rows)
    write_outputs(out, rows, summary, {
        'mode': 'LIVE' if args.live else 'FAKE', 'set': args.set_name, 'arm': args.arm, 'models': models, 'types': types,
        'guard': guard.name, 'api_guard': 'ApiGuard' if (args.live and needs_money) else None, 'guard_calls': guard.calls, 'guard_spent_usd': guard.spent_usd,
        'guard_blocked': guard.blocked, 'price_status': wp5.price_status(table), 'approval_ref': approval,
        'config_sha256': wp5.sha256_file(Path(args.config) if Path(args.config).is_absolute() else wp5._ROOT / args.config)})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
