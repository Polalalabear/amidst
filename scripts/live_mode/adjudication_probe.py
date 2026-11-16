"""Adjudication probe for live mode: ask OpenAI models which numbered candidate matches the reference.

Questions come from frontend/live-mode/measure/adj_build.mjs (questions.jsonl + img/). This script never reads
answers_private.jsonl; scoring is a separate step (adjudication_score.py).

Variants:
  image  reference crop + one camera frame with numbered boxes (pixels the system already has; no coordinates, no actor ids)
  text   pixel-derived features only (upper/lower colour, box height, distance from the last estimate, speed needed)

Default is a dry run (0 calls). --live needs --approved-usd; every call goes through ApiGuard (own ledger under --out).
The API key is read from OPENAI_API_KEY at call time and is never written or printed.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from amidst.q1q5.api_budget import ApiGuard, GuardConfig

URL = "https://api.openai.com/v1/chat/completions"
# D237 (issue #93): config id -> API model id and USD per million tokens (input, output), pinned 2026-11-15.
MODELS = {"terra6.1": ("gpt-6.1-terra", 1.0, 5.0), "sol6.1": ("gpt-6.1-sol", 2.0, 10.0), "astra6": ("gpt-6-astra", 10.0, 50.0)}
SYSTEM = ("A camera system tracks one person (the target). It sees camera pixels only. Identity is never confirmed: "
          "you only judge which candidate best matches the target's appearance and movement. "
          "Answer 0 when no candidate matches. Reply in JSON.")
MAX_OUT = 400  # includes reasoning tokens


def schema(k: int) -> dict:
    return {"type": "json_schema", "json_schema": {"name": "adjudication", "strict": True, "schema": {
        "type": "object", "additionalProperties": False, "required": ["choice", "reason"],
        "properties": {"choice": {"type": "integer", "enum": list(range(0, k + 1))},
                       "reason": {"type": "string", "description": "Traditional Chinese, at most 40 characters"}}}}}


def data_url(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()


def col(c: dict) -> str:
    return f"hue {c['h_deg']} deg, saturation {c['s']}, brightness {c['v']}"


def build(q: dict, root: Path, variant: str) -> list:
    k = q["n_candidates"]
    ask = f"Which numbered person (1-{k}) is the target? 0 if none."
    if variant == "image":
        return [{"type": "text", "text": "Image 1: the target when the system first locked on. Image 2: a camera frame now, "
                 f"candidates are numbered in yellow boxes. {ask}"},
                {"type": "image_url", "image_url": {"url": data_url(root / q["reference"]), "detail": "high"}},
                {"type": "image_url", "image_url": {"url": data_url(root / q["frame"]), "detail": "high"}}]
    r = q["reference_features"]
    lines = [f"Target at first lock: upper body {col(r['upper'])}; lower body {col(r['lower'])}; box height {r['box_height_px']} px.",
             f"Seconds since the target was last matched: {q['seconds_since_last_match']}.", f"Candidates in camera {q['camera']}:"]
    for c in q["candidates"]:
        lines.append(f"{c['number']}: upper body {col(c['upper'])}; lower body {col(c['lower'])}; box height {c['box_height_px']} px; "
                     f"detector score {c['detector_score']}; {c['metres_from_last_estimate']} m from the last estimated position; "
                     f"speed needed {c['speed_needed_m_s']} m/s (walking is about 1.2, running about 2.5).")
    return [{"type": "text", "text": "\n".join(lines) + "\n" + ask}]


def call(api_model: str, q: dict, root: Path, variant: str, timeout_s: float):
    body = {"model": api_model, "max_completion_tokens": MAX_OUT, "response_format": schema(q["n_candidates"]),
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": build(q, root, variant)}]}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"latency_ms": (time.perf_counter() - t0) * 1000, "error": f"HTTP {exc.code}: {exc.read()[:300].decode('utf-8', 'replace')}"}, 0, 0
    wall = (time.perf_counter() - t0) * 1000
    usage = data.get("usage") or {}
    out = {"latency_ms": wall, "api_model": data.get("model"), "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
           "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"), "finish_reason": data["choices"][0].get("finish_reason")}
    try:
        ans = json.loads(data["choices"][0]["message"]["content"])
        out.update(choice=ans.get("choice"), reason=ans.get("reason"),
                   valid=isinstance(ans.get("choice"), int) and 0 <= ans["choice"] <= q["n_candidates"])
    except (TypeError, ValueError, KeyError):
        out.update(choice=None, reason=None, valid=False)
    return out, usage.get("prompt_tokens"), usage.get("completion_tokens")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", required=True, help="directory with questions.jsonl and img/")
    ap.add_argument("--out", required=True)
    ap.add_argument("--models", default="terra6.1,sol6.1,astra6")
    ap.add_argument("--variants", default="image,text")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--approved-usd", type=float, default=0.0)
    ap.add_argument("--calls-per-min", type=int, default=10)
    ap.add_argument("--image-tokens-est", type=int, default=2500, help="assumed prompt tokens for the two images (unknown until measured)")
    ap.add_argument("--timeout-s", type=float, default=30.0)
    a = ap.parse_args()
    root = Path(a.questions)
    qs = [json.loads(line) for line in (root / "questions.jsonl").read_text().splitlines() if line.strip()]
    if a.limit:
        qs = qs[: a.limit]
    models, variants = a.models.split(","), a.variants.split(",")
    est_prompt = {"image": 250 + a.image_tokens_est, "text": 450}
    plan = [(q, v, m) for q in qs for v in variants for m in models]  # models interleaved per question
    worst = sum((est_prompt[v] * MODELS[m][1] + MAX_OUT * MODELS[m][2]) / 1e6 for _, v, m in plan)
    per = {m: round(sum((est_prompt[v] * MODELS[m][1] + MAX_OUT * MODELS[m][2]) / 1e6 for _, v, mm in plan if mm == m), 4) for m in models}
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    est = {"questions": len(qs), "calls": len(plan), "worst_case_usd": round(worst, 4), "worst_case_usd_by_model": per,
           "assumed_prompt_tokens": est_prompt, "max_output_tokens": MAX_OUT, "minutes_at_rate_limit": round(len(plan) / a.calls_per_min, 1)}
    (out / "estimate.json").write_text(json.dumps(est, indent=1))
    print(json.dumps(est))
    if not a.live:
        print("DRY RUN: 0 calls")
        return 0
    if a.approved_usd <= 0 or worst > a.approved_usd:
        print(f"REFUSED: worst case {worst:.4f} USD exceeds --approved-usd {a.approved_usd}")
        return 2
    if not os.environ.get("OPENAI_API_KEY"):
        print("REFUSED: OPENAI_API_KEY is not set")
        return 2
    prices = {MODELS[m][0]: {"input_usd_per_mtok": MODELS[m][1], "output_usd_per_mtok": MODELS[m][2]} for m in models}
    guard = ApiGuard(GuardConfig(enabled=True, max_usd_total=a.approved_usd, max_usd_per_day=a.approved_usd, max_calls_per_day=len(plan) + 5,
                                 max_usd_per_call=0.08, max_tokens_per_call=6000, max_calls_per_min=a.calls_per_min, prices=prices),
                     usage_dir=out / "guard-ledger")
    with open(out / "calls.jsonl", "a", encoding="utf-8") as fh:
        for q, v, m in plan:
            api_model = MODELS[m][0]
            box = {}

            def fn():
                box["r"], pt, ct = call(api_model, q, root, v, a.timeout_s)
                return box["r"], pt, ct
            row = {"qid": q["qid"], "variant": v, "model": m, "n_candidates": q["n_candidates"]}
            try:
                res = guard.run("live_adjudication", api_model, est_prompt[v], MAX_OUT, fn)
                row.update(box.get("r") or {}, guard_allowed=res.allowed, guard_reason=res.reason, charged_usd=res.est_cost_usd)
            except Exception as exc:  # noqa: BLE001 - recorded, never fatal for the run
                row.update(error=f"{type(exc).__name__}: {str(exc)[:200]}")
            fh.write(json.dumps(row, ensure_ascii=False) + "\n"); fh.flush()
            if row.get("guard_allowed") is False and row.get("guard_reason") in ("TOTAL_BUDGET", "DAILY_COST_CAP", "DAILY_CALL_CAP"):
                print("STOPPED by guard:", row["guard_reason"])
                return 3
            time.sleep(60.0 / a.calls_per_min + 0.3)
    print("DONE", len(plan), "calls planned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
