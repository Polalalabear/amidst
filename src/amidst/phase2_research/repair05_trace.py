"""GT-free instrumentation of the inherited, unchanged local assignment algorithm."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.perception import Measurement, PerceptionResult
from amidst.phase2_research.repair05_tracker import Strategy, local_functions
from amidst.research_accuracy import pixel

Json = dict[str, Any]
Prediction = Callable[[list[Measurement], float, pixel.PixelContinuityConfig], tuple[float, float]]


def contact_key(row: Measurement) -> str:
    return digest(
        [
            row.camera_id,
            row.timestamp,
            row.frame_ref,
            row.bbox_xyxy,
            row.contact_pixel,
            row.input_sha256,
        ]
    )


def _history_reason(
    row: Measurement,
    track: str,
    history: list[Measurement],
    config: pixel.PixelContinuityConfig,
    prediction_function: Prediction = pixel._prediction,
) -> Json:
    last = history[-1]
    dt = row.timestamp - last.timestamp
    prediction = prediction_function(history, row.timestamp, config)
    displacement = math.dist(row.contact_pixel, last.contact_pixel)
    residual = math.dist(row.contact_pixel, prediction)
    colors = [sample.appearance for sample in history[-3:]]
    mean = tuple(math.fsum(color[c] for color in colors) / len(colors) for c in range(3))
    appearance = math.dist(row.appearance, mean) / config.appearance_scale
    width, height = row.bbox_xyxy[2] - row.bbox_xyxy[0], row.bbox_xyxy[3] - row.bbox_xyxy[1]
    old_width = last.bbox_xyxy[2] - last.bbox_xyxy[0]
    old_height = last.bbox_xyxy[3] - last.bbox_xyxy[1]
    shape = (abs(math.log(width / old_width)) + abs(math.log(height / old_height))) / 2
    cost = residual / config.max_prediction_error_px + config.appearance_weight * appearance
    cost += config.shape_weight * shape
    reason = (
        "GAP_EXPIRED"
        if not 0 < dt <= config.max_gap_s
        else "DISPLACEMENT_GATE"
        if displacement > 28 * max(1, dt / 0.2)
        else "PREDICTION_GATE"
        if residual > config.max_prediction_error_px
        else "UNMATCHED_COST_GATE"
        if cost >= config.unmatched_cost
        else "ADMITTED"
    )
    return {
        "track_key": digest(track),
        "last_contact_key": contact_key(last),
        "last_frame_ref": last.frame_ref,
        "dt_s": dt,
        "prediction": prediction,
        "displacement_px": displacement,
        "prediction_residual_px": residual,
        "appearance_cost": appearance,
        "shape_cost": shape,
        "assignment_cost": cost,
        "reason": reason,
        "prediction_anchor_has_partial": any(
            sample.status == "MERGED_OR_PARTIAL" for sample in history[-2:]
        ),
        "history_last_contact_keys": [contact_key(sample) for sample in history[-3:]],
    }


def trace_assignment(
    perception: PerceptionResult,
    config: pixel.PixelContinuityConfig,
    *,
    strategy: Strategy = "BASELINE",
) -> tuple[PerceptionResult, Json]:
    """Observe actual candidate/history/assignment calls without changing their results.

    Hooks are injected into a private function-globals copy. The inherited module
    remains untouched throughout concurrent calls and failures.
    """
    functions = local_functions(strategy)
    original_candidates, original_assign = functions["_candidates"], functions["_assign"]
    pending: list[tuple[Measurement, list[Json]]] = []
    decisions: dict[str, Json] = {}

    def candidates(
        measurement: Measurement,
        histories: dict[str, list[Measurement]],
        config: pixel.PixelContinuityConfig,
    ) -> list[pixel._Candidate]:
        row, policy = measurement, config
        actual: list[pixel._Candidate] = original_candidates(row, histories, policy)
        recorded = [
            _history_reason(row, key, history, policy, functions["_prediction"])
            for key, history in histories.items()
        ]
        admitted = {digest(candidate.track_id) for candidate in actual}
        if admitted != {item["track_key"] for item in recorded if item["reason"] == "ADMITTED"}:
            raise ValueError("REPAIR05_TRACE_CANDIDATE_EXPLANATION_MISMATCH")
        pending.append((row, recorded))
        return actual

    def assign(
        options: list[list[pixel._Candidate]],
        quarantined: list[bool],
        config: pixel.PixelContinuityConfig,
    ) -> list[str | None]:
        policy = config
        actual: list[str | None] = original_assign(options, quarantined, policy)
        if len(pending) != len(options):
            raise ValueError("REPAIR05_TRACE_FRAME_ALIGNMENT_MISMATCH")
        for (row, histories), choices, quarantine, selected in zip(
            pending,
            options,
            quarantined,
            actual,
            strict=True,
        ):
            merge_evidence = pixel._merged(
                row, choices, policy.model_copy(update={"merge_quarantine": True})
            )
            reason = (
                "QUARANTINED_MERGE"
                if quarantine
                else "CONTINUATION"
                if selected
                else "NO_RELIABLE_HISTORY"
                if not histories
                else "GLOBAL_COMPETITION_UNMATCHED"
                if choices
                else "NO_ELIGIBLE_CONTINUATION"
            )
            decisions[contact_key(row)] = {
                "contact_key": contact_key(row),
                "camera_id": row.camera_id,
                "timestamp": row.timestamp,
                "frame_ref": row.frame_ref,
                "input_sha256": row.input_sha256,
                "source_status": row.status,
                "decision": reason,
                "quarantined": quarantine,
                "merge_evidence": merge_evidence,
                "selected_history_key": digest(selected) if selected else None,
                "candidate_count": len(choices),
                "histories": histories,
                "global_competing_contacts": sum(
                    any(candidate.track_id == selected for candidate in other) for other in options
                )
                if selected
                else 0,
            }
        pending.clear()
        return actual

    functions["_candidates"], functions["_assign"] = candidates, assign
    result: PerceptionResult = functions["reassociate_perception_v2"](perception, config=config)
    if len(decisions) != len(perception.measurements):
        raise ValueError("REPAIR05_TRACE_CONTACT_POPULATION_MISMATCH")
    for row in result.measurements:
        decisions[contact_key(row)]["result_track_key"] = digest(row.local_track_id)
        decisions[contact_key(row)]["result_status"] = row.status
        decisions[contact_key(row)]["result_alternative_count"] = row.local_alternative_count
        decisions[contact_key(row)]["result_uncertainty"] = row.uncertainty
    rows = list(decisions.values())
    selected_histories = [
        item
        for row in rows
        for item in row["histories"]
        if item["track_key"] == row["selected_history_key"]
    ]
    return result, {
        "schema_version": "phase2.repair05.assignment-trace.v1",
        "gt_or_reference_content_read": False,
        "input_contact_count": len(perception.measurements),
        "decision_counts": dict(Counter(row["decision"] for row in rows)),
        "candidate_exclusion_counts": dict(
            Counter(item["reason"] for row in rows for item in row["histories"])
        ),
        "merge_evidence_contacts": sum(row["merge_evidence"] for row in rows),
        "merge_evidence_continued_without_quarantine": sum(
            row["merge_evidence"] and row["decision"] == "CONTINUATION" for row in rows
        ),
        "continuations_from_partial_prediction_anchor": sum(
            item["prediction_anchor_has_partial"] for item in selected_histories
        ),
        "decisions": rows,
        "interpretation": "Mechanical assignment reasons; not reference-confirmed identity errors.",
    }
