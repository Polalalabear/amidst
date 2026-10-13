"""Mechanical development attribution from frozen, GT-free assignment decisions."""

from __future__ import annotations

from collections import Counter
from typing import Any

Json = dict[str, Any]


def predecessor(row: Json) -> str | None:
    return next(
        (
            item["last_contact_key"]
            for item in row["histories"]
            if item["track_key"] == row["selected_history_key"]
        ),
        None,
    )


def summarize(traces: dict[str, Json]) -> Json:
    baseline = {row["contact_key"]: row for row in traces["baseline"]["decisions"]}
    result: Json = {}
    for name, trace in traces.items():
        rows = trace["decisions"]
        if {row["contact_key"] for row in rows} != set(baseline):
            raise ValueError("REPAIR05_ATTRIBUTION_POPULATION_CHANGED")
        merged = {row["contact_key"] for row in rows if row["merge_evidence"]}
        selected = [
            item
            for row in rows
            for item in row["histories"]
            if item["track_key"] == row["selected_history_key"]
        ]
        unmatched = [row for row in rows if row["decision"] == "NO_ELIGIBLE_CONTINUATION"]
        active_gate_counts: Counter[str] = Counter()
        for row in unmatched:
            active = {
                item["reason"] for item in row["histories"] if item["reason"] != "GAP_EXPIRED"
            }
            active_gate_counts.update(
                [
                    next(iter(active))
                    if len(active) == 1
                    else "MIXED_ACTIVE_GATES"
                    if active
                    else "ALL_HISTORY_EXPIRED"
                ]
            )
        result[name] = {
            "contact_count": len(rows),
            "merge_evidence_contacts": len(merged),
            "continued_merge_evidence_contacts": sum(
                row["merge_evidence"] and row["decision"] == "CONTINUATION" for row in rows
            ),
            "continuations_using_merge_evidence_prediction_anchor": sum(
                bool(merged.intersection(item["history_last_contact_keys"][-2:]))
                for item in selected
            ),
            "no_continuation_active_gate_groups": dict(active_gate_counts),
            "assignment_decisions_changed_from_baseline": sum(
                (row["decision"], predecessor(row))
                != (
                    baseline[row["contact_key"]]["decision"],
                    predecessor(baseline[row["contact_key"]]),
                )
                for row in rows
            ),
            "prediction_rejections_with_three_observed_history_contacts": sum(
                item["reason"] == "PREDICTION_GATE" and len(item["history_last_contact_keys"]) == 3
                for row in rows
                for item in row["histories"]
            ),
        }
    return {
        "schema_version": "phase2.repair05.mechanical-attribution.v1",
        "variants": result,
        "reference_identity_error_causation": "UNVERIFIED_NO_REFERENCE_LABELS_USED",
        "no_test_data_used": True,
    }
