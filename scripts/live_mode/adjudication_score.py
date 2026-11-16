"""Score adjudication_probe.py output against answers_private.jsonl (evaluation only; run on the Mac).

Reports, per model and variant: valid-answer rate, accuracy over valid answers and over all calls, latency of valid
answers (median, p90), tokens and cost. The rule tracker's own pick on the same questions is the baseline.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

PRICES = {"terra6.1": (1.0, 5.0), "sol6.1": (2.0, 10.0), "astra6": (10.0, 50.0)}


def pct(v, p):
    v = sorted(v)
    if not v:
        return None
    i = (len(v) - 1) * p
    lo, hi = int(i), min(int(i) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (i - lo))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", required=True)
    ap.add_argument("--calls", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ans = {r["qid"]: r for r in map(json.loads, (Path(a.questions) / "answers_private.jsonl").read_text().splitlines()) if r}
    calls = [json.loads(line) for line in Path(a.calls).read_text().splitlines() if line.strip()]
    groups: dict = {}
    for c in calls:
        groups.setdefault((c["model"], c["variant"]), []).append(c)
    rows = []
    for (m, v), cs in sorted(groups.items()):
        ran = [c for c in cs if c.get("guard_allowed")]
        valid = [c for c in ran if c.get("valid")]
        right = [c for c in valid if c["choice"] == ans[c["qid"]]["answer"]]
        lat = [c["latency_ms"] for c in valid]
        pin, pout = PRICES[m]
        usd = [((c.get("prompt_tokens") or 0) * pin + (c.get("completion_tokens") or 0) * pout) / 1e6 for c in ran if c.get("prompt_tokens")]
        rows.append({"model": m, "variant": v, "calls": len(ran), "valid": len(valid), "valid_rate": round(len(valid) / len(ran), 3) if ran else None,
                     "correct": len(right), "accuracy_of_valid": round(len(right) / len(valid), 3) if valid else None,
                     "accuracy_of_all_calls": round(len(right) / len(ran), 3) if ran else None,
                     "latency_ms_valid_p50": pct(lat, 0.5), "latency_ms_valid_p90": pct(lat, 0.9),
                     "prompt_tokens_mean": round(statistics.mean([c["prompt_tokens"] for c in ran if c.get("prompt_tokens")])) if usd else None,
                     "completion_tokens_mean": round(statistics.mean([c["completion_tokens"] for c in ran if c.get("completion_tokens")])) if usd else None,
                     "usd_per_call": round(statistics.mean(usd), 5) if usd else None, "usd_total": round(sum(usd), 4),
                     "errors": sum(1 for c in cs if c.get("error")), "denied": sum(1 for c in cs if c.get("guard_allowed") is False)})
    qids = sorted({c["qid"] for c in calls})
    matched = [ans[q] for q in qids if ans[q]["rule_matched"]]
    base = {"questions": len(qids), "answer_is_none": sum(1 for q in qids if ans[q]["answer"] == 0),
            "rule_matched": len(matched), "rule_pick_correct": sum(1 for x in matched if x["rule_pick"] == x["answer"]),
            "chance_accuracy": round(statistics.mean([1 / (len(ans[q]["candidate_actors"]) + 1) for q in qids]), 3) if qids else None}
    Path(a.out).write_text(json.dumps({"baseline": base, "rows": rows}, indent=1, ensure_ascii=False))
    print(json.dumps(base))
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
