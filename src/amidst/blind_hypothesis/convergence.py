"""Band-width convergence summary of a pruning chain (task K5).

Pure post-processing of a chain of ``workbench.blind-hypothesis.v1`` responses
(the first run, then one re-run per appended negative-evidence step) for the
workbench charts and the RQ2 evaluation: the reachable-region area per clock time
before and after each step, and how many hypotheses were pruned. The numbers are
read from the responses; nothing is recomputed from geometry, no GT is involved,
and an area is an inferred-hypothesis extent, not a probability or a position.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from amidst.blind_hypothesis.engine import verify_output_sha256

SUMMARY_KIND = "BLIND_HYPOTHESIS_PRUNING_CONVERGENCE"
BASIS = "REACHABLE_REGION_AREA_NOT_PROBABILITY"


def _areas(response: Mapping[str, Any]) -> list[dict[str, float]]:
    return [
        {"timestamp_s": r["timestamp_s"], "area_m2": r["area_m2"]}
        for r in response.get("reachable_regions") or []
    ]


def pruning_convergence_summary(responses: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarise ``responses`` (first run first); the chain must share one interval.

    ``chain_verified`` is true only if every response's ``output_sha256`` is
    consistent and each re-run's new ``pruning_log`` entries cite the hash of the
    response before it. Per-step rows give the area at every ``t_i``, the mean and
    the largest extent (band width), pruning counts and the step's ``pruning_log``
    entries; ``per_timestamp`` compares the first and last READY response.
    """

    steps: list[dict[str, Any]] = []
    verified = bool(responses)
    previous: Mapping[str, Any] | None = None
    for index, response in enumerate(responses):
        verified = verified and verify_output_sha256(response)
        log = list(response.get("pruning_log") or [])
        old_log = list((previous or {}).get("pruning_log") or [])
        new_log = log[len(old_log) :]
        if (
            previous is not None
            and (
                log[: len(old_log)] != old_log  # earlier log entries must be carried over unchanged
                or any(
                    e.get("previous_response_sha256") != previous.get("output_sha256")
                    for e in new_log
                )
                or response.get("interval") != previous.get("interval")
                or (response.get("negative_evidence_applied") or [])[
                    : len(previous.get("negative_evidence_applied") or [])
                ]
                != (previous.get("negative_evidence_applied") or [])
            )
        ):
            verified = False
        areas = _areas(response)
        regions = response.get("reachable_regions") or []
        steps.append(
            {
                "index": index,
                "response_sha256": response.get("output_sha256"),
                "status": response.get("status"),
                "reason": response.get("reason"),
                "negative_evidence_applied": list(response.get("negative_evidence_applied") or []),
                "active_hypotheses": len(response.get("hypotheses") or []),
                "hypotheses_pruned": len(response.get("pruned_hypotheses") or []),
                "region_areas": areas,
                "region_mean_area_m2": round(sum(a["area_m2"] for a in areas) / len(areas), 6)
                if areas
                else None,
                "region_max_extent_m": max((r["max_extent_m"] for r in regions), default=None),
                "pruning_log": new_log,
            }
        )
        previous = response

    ready = [(s, r) for s, r in zip(steps, responses, strict=True) if s["status"] == "READY"]
    per_timestamp: list[dict[str, Any]] = []
    totals: dict[str, Any] = {
        "hypotheses_pruned": sum(s["hypotheses_pruned"] for s in steps),
        "negative_evidence_steps": max(len(steps) - 1, 0),
        "mean_area_first_m2": None,
        "mean_area_last_m2": None,
        "mean_area_ratio": None,
    }
    if len(ready) >= 2:
        first, last = ready[0][0], ready[-1][0]
        last_by_time = {a["timestamp_s"]: a["area_m2"] for a in last["region_areas"]}
        for entry in first["region_areas"]:
            t, first_area = entry["timestamp_s"], entry["area_m2"]
            last_area = last_by_time.get(t)
            if last_area is None:
                continue
            per_timestamp.append(
                {
                    "timestamp_s": t,
                    "area_first_m2": first_area,
                    "area_last_m2": last_area,
                    "area_removed_m2": round(first_area - last_area, 6),
                    "fraction_removed": round(1 - last_area / first_area, 6) if first_area else 0.0,
                }
            )
        totals["mean_area_first_m2"] = first["region_mean_area_m2"]
        totals["mean_area_last_m2"] = last["region_mean_area_m2"]
        if first["region_mean_area_m2"]:
            totals["mean_area_ratio"] = round(
                last["region_mean_area_m2"] / first["region_mean_area_m2"], 6
            )
    return {
        "summary_kind": SUMMARY_KIND,
        "basis": BASIS,
        "chain_verified": verified,
        "steps": steps,
        "per_timestamp": per_timestamp,
        "totals": totals,
    }
