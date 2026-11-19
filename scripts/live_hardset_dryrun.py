"""#597 ApiGuard dry-run: estimated spend of the LIVE hard-case LLM comparison. Makes no API call and writes nothing.

Only decision points call the model (advisor.py: one question at a time, at least ``min_interval_s`` apart, the rule answer is
kept while it waits). Upper bound of questions per case = case length / 3.5 s (the wait for an answer, guide §5); the real
count is smaller and is read from the rule-mode replay once it exists (``--rule-counts``).

Token model, per call (advisor.py): the guard is charged EST_PROMPT_TOKENS in and MAX_OUT out (worst case, what the guard
checks against its caps); the typical line uses the measured ~807 prompt tokens and the completion size implied by the
measured live spend (D297: USD 0.12 / 43 calls on sol6.1).

    python scripts/live_hardset_dryrun.py [--cases H1-1,...] [--k 3] [--models terra6.1,sol6.1] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from amidst.live_mode.advisor import EST_PROMPT_TOKENS, MAX_OUT  # noqa: E402
from amidst.q1q5.api_budget import GuardConfig, estimate_run  # noqa: E402

WAIT_S = 3.5
TYPICAL_PROMPT, TYPICAL_OUT = 807, 120      # measured prompt size; completion size implied by D297 (USD 0.0028 per call on sol6.1)
FIRST_NINE = ("H1-1", "H1-2", "H1-3", "H4-1", "H4-2", "H4-3", "H5-1", "H5-2", "H5-3")


def load(cases_arg):
    cfg = json.loads((ROOT / "configs/evaluation/live_hardset_v1.json").read_text("utf-8"))
    prices = json.loads((ROOT / "configs/agent_eval/wp5_price_table_v1.json").read_text("utf-8"))["models"]
    lengths = {c["case_id"]: c["length_s"] for c in cfg["cases"] if c["source"] == "GENERATED"}
    wanted = cases_arg.split(",") if cases_arg else list(lengths)
    unknown = [c for c in wanted if c not in lengths]
    if unknown:
        raise SystemExit(f"unknown or non-generated cases: {unknown}")
    return {c: lengths[c] for c in wanted}, {k: {"input_usd_per_mtok": v["input_usd_per_mtok"], "output_usd_per_mtok": v["output_usd_per_mtok"]} for k, v in prices.items()}


def estimate(lengths, models, k, prices, rule_counts=None, guard=None):
    out = {"cases": lengths, "k": k, "per_model": {}, "basis": "rule_counts" if rule_counts else "upper_bound_length_div_3.5s"}
    per_case = {c: (rule_counts[c] if rule_counts and c in rule_counts else int(L // WAIT_S)) for c, L in lengths.items()}
    out["questions_per_case"] = per_case
    n = sum(per_case.values())
    for m in models:
        worst = estimate_run(questions=n, calls_per_question=k, model=m, avg_prompt_tokens=EST_PROMPT_TOKENS, avg_output_tokens=MAX_OUT, prices=prices, config=guard)
        typ = estimate_run(questions=n, calls_per_question=k, model=m, avg_prompt_tokens=TYPICAL_PROMPT, avg_output_tokens=TYPICAL_OUT, prices=prices, config=guard)
        out["per_model"][m] = {"worst_case": worst, "typical": typ}
    out["total_worst_usd"] = round(sum(v["worst_case"]["est_total_usd"] for v in out["per_model"].values()), 4)
    out["total_typical_usd"] = round(sum(v["typical"]["est_total_usd"] for v in out["per_model"].values()), 4)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cases", help="comma separated case ids (default: all generated cases); 'nine' = H1/H4/H5 first nine")
    ap.add_argument("--k", type=int, default=3, help="repetitions per case and model (D325 used 3)")
    ap.add_argument("--models", default="terra6.1,sol6.1")
    ap.add_argument("--rule-counts", help="JSON {case: decision points} from the rule-mode replay (replaces the upper bound)")
    ap.add_argument("--cap-usd-total", type=float, default=10.0, help="hypothetical guard total budget for would_exceed (D306 notice line)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    lengths, prices = load(",".join(FIRST_NINE) if args.cases == "nine" else args.cases)
    counts = json.loads(Path(args.rule_counts).read_text("utf-8")) if args.rule_counts else None
    base = GuardConfig()   # the shipped defaults: per day USD 5 / 200 calls, per call USD 0.05 / 4000 tokens
    guard = GuardConfig(enabled=True, max_usd_total=args.cap_usd_total, max_usd_per_day=base.max_usd_per_day, max_calls_per_day=base.max_calls_per_day,
                        max_usd_per_call=base.max_usd_per_call, max_tokens_per_call=base.max_tokens_per_call, max_calls_per_min=base.max_calls_per_min, prices=prices)
    res = estimate(lengths, args.models.split(","), args.k, prices, counts, guard)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    print(f"cases {len(lengths)}  K={args.k}  basis={res['basis']}  questions/case: {sum(res['questions_per_case'].values())} total")
    for m, v in res["per_model"].items():
        for kind in ("worst_case", "typical"):
            e = v[kind]
            print(f"{m:9s} {kind:10s} calls {e['calls']:5d}  per call USD {e['est_cost_per_call_usd']:.5f}  total USD {e['est_total_usd']:.3f}  would_exceed {e.get('would_exceed') or '-'}")
    print(f"TOTAL worst USD {res['total_worst_usd']:.3f}   typical USD {res['total_typical_usd']:.3f}   (no API call was made)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
