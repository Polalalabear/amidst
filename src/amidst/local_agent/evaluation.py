"""Measured local-model receipts; evaluator does not provide truth to the Agent."""

from __future__ import annotations

import math
from typing import Any


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def summarize_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    receipts = [r for c in cases for r in c["model_receipts"]]
    durations = [float(r["duration_ms"]) for r in receipts]
    prompts = [float(r["prompt_tokens"]) for r in receipts]
    outputs = [float(r["output_tokens"]) for r in receipts]
    return {
        "schema_version": "local.agent.evaluation.v1", "case_denominator": len(cases),
        "completed_count": sum(c["state"] == "COMPLETED" for c in cases),
        "clarification_count": sum(c["state"] == "NEEDS_CLARIFICATION" for c in cases),
        "failed_count": sum(c["state"] == "FAILED" for c in cases),
        "unresolved_count": sum(c["state"] != "COMPLETED" for c in cases),
        "model_call_denominator": len(receipts),
        "request_attempt_denominator": sum(c["metrics"].get("model_request_attempt_count", 0)
                                           for c in cases),
        "usage_unknown_request_count": sum(c["metrics"].get("usage_unknown_request_count", 0)
                                           for c in cases),
        "duration_ms": {"p50": percentile(durations, .5), "p95": percentile(durations, .95)},
        "prompt_tokens": {"total": sum(prompts), "p50": percentile(prompts, .5),
                          "p95": percentile(prompts, .95)},
        "output_tokens": {"total": sum(outputs), "p50": percentile(outputs, .5),
                          "p95": percentile(outputs, .95)},
        "true_model_execution": bool(receipts) and all(
            r["provider"] == "OLLAMA_LOOPBACK" for r in receipts),
        "semantic_factuality": "REQUIRES_SEPARATE_TASK_REVIEW",
        "generalization_claim": False, "token_saving_claim": False,
        "formal_acceptance": False,
    }
