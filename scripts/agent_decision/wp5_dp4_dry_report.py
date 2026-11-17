"""DP4 first-call heuristic and config-consistent budget scenarios. No provider/network/key access."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from amidst.agent_eval import wp5


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    cfg = wp5.load_config()
    prices = wp5.load_json(cfg["price_table_path"])
    openai = [m["id"] for m in cfg["models"] if m["kind"] == "OPENAI"]
    cases = {
        "A": [("pilot", ["terra6.1"]), ("formal", ["terra6.1"])],
        "B": [("pilot", ["terra6.1"]), ("formal", ["terra6.1"]), ("pilot", ["sol6.1", "astra6"])],
        "C": [("pilot", openai), ("formal", openai)],
    }
    scenarios = {}
    for name, selections in cases.items():
        estimates = [wp5.estimate_set(cfg, s, prices, models=models) for s, models in selections]
        nominal = sum(e["openai_usd_nominal"] for e in estimates)
        worst = sum(e["openai_usd_worst"] for e in estimates)
        scenarios[name] = {
            "model_calls_nominal": sum(e["openai_calls_nominal"] for e in estimates),
            "model_calls_worst_config": sum(e["openai_calls_worst"] for e in estimates),
            "usd_nominal_config": round(nominal, 8),
            "usd_worst_config": round(worst, 8),
            "unapproved_ceiling_rounded_usd": math.ceil(worst),
        }
    inputs, dp4_totals = {}, {}
    for method in ["API", "AGENT"]:
        configured = []
        heuristic = []
        for s in ["pilot", "formal"]:
            doc = json.loads((a.work / f"dry-{method.lower()}-{s}/estimate.json").read_text())
            assert doc["mode"] == "DRY_RUN" and doc["provider_calls"] == 0
            inputs[f"{method}_{s}"] = doc["dp4_input_estimate"]
            configured.append(doc["estimate"])
            n = cfg["sets"][s]["questions_per_type"]["DP4"] * sum(
                p["repeats"] for p in cfg["sets"][s]["phases"]
            )
            p = doc["dp4_input_estimate"]["first_call_tokens_heuristic"]["max"]
            heuristic.append(
                sum(wp5.cost_usd(prices, wp5.model_by_id(cfg, m), n * p, n * 300) for m in openai)
            )
        dp4_totals[method] = {
            "openai_calls_nominal": sum(e["openai_calls_nominal"] for e in configured),
            "openai_calls_config_worst": sum(e["openai_calls_worst"] for e in configured),
            "usd_nominal_config": round(sum(e["openai_usd_nominal"] for e in configured), 8),
            "usd_worst_config": round(sum(e["openai_usd_worst"] for e in configured), 8),
            "usd_first_call_heuristic_not_bound": round(sum(heuristic), 8),
            "implementation_max_steps_per_question": 1
            if method == "API"
            else cfg["task_types"]["DP4"]["worst_case_calls_per_question"],
        }
    source = {
        p: hashlib.sha256((wp5._ROOT / p).read_bytes()).hexdigest()
        for p in ["configs/agent_eval/wp5_v1.json", cfg["price_table_path"]]
    }
    out = {
        "scope": "SYNTHETIC_DRY_RUN_NOT_BILLED",
        "provider_calls": 0,
        "source_sha256": source,
        "price_date": prices["date"],
        "price_source": prices["source"],
        "inputs": inputs,
        "dp4_pilot_plus_formal_three_openai_models": dp4_totals,
        "config_scenarios": scenarios,
        "limits": [
            "UTF8 bytes/4 is a heuristic, not tokenizer or billed usage",
            "Agent later tool rounds and real question tokens/latency are UNKNOWN",
            "Config reserves stay 2500 input / 300 max output / 5 worst calls; API is one call",
            "All USD values use the committed dated price table; no spend approval is granted",
        ],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"DP4": dp4_totals, "scenarios": scenarios}, indent=2))


if __name__ == "__main__":
    main()
