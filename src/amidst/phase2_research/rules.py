"""Versioned single-local-track region alerts over actual projected samples only."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.association import ConfiguredRegion, ProjectedMeasurement
from amidst.engineering.local_association import InferenceBundle
from amidst.engineering.local_behavior import BehaviorConfig

Json = dict[str, Any]
KINDS = ("REGION_ENTRY", "REGION_EXIT", "SUSTAINED_DWELL")


def validate_policy(policy: Json) -> None:
    if set(policy) != {
        "version",
        "side_samples",
        "max_gap_s",
        "dwell_duration_s",
        "dwell_radius_m",
        "dwell_speed_m_s",
    }:
        raise ValueError("REGION_RULE_POLICY_DENIED")
    if policy["version"] != "single-region-rules-v1" or type(policy["side_samples"]) is not int:
        raise ValueError("REGION_RULE_VERSION_DENIED")
    if not 2 <= policy["side_samples"] <= 8:
        raise ValueError("REGION_RULE_SAMPLES_DENIED")
    if any(
        isinstance(policy[key], bool)
        or not isinstance(policy[key], (int, float))
        or not math.isfinite(policy[key])
        or policy[key] <= 0
        for key in ("max_gap_s", "dwell_duration_s", "dwell_radius_m", "dwell_speed_m_s")
    ):
        raise ValueError("REGION_RULE_THRESHOLDS_DENIED")


def _point(row: ProjectedMeasurement) -> tuple[float, float, float]:
    assert row.point is not None
    return row.point.world_position


def compose_rules(inference: InferenceBundle, config: BehaviorConfig, policy: Json) -> Json:
    """Preserve trigger and retraction history; never treat track identity as a person."""
    validate_policy(policy)
    if inference.scope != config.scope:
        raise ValueError("REGION_RULE_SCOPE_DENIED")
    config_hash = digest(
        {
            "policy": policy,
            "regions": [region.model_dump(mode="json") for region in config.regions],
            "scope": config.scope.model_dump(mode="json"),
        }
    )
    tracks: dict[str, list[ProjectedMeasurement]] = defaultdict(list)
    for row in inference.projected_measurements:
        tracks[row.local_track_id].append(row)
    events: list[Json] = []
    for track_id, original in sorted(tracks.items()):
        ordered = sorted(original, key=lambda row: (row.timestamp, row.observation_id))
        chunks: list[list[ProjectedMeasurement]] = []
        current: list[ProjectedMeasurement] = []
        for row in ordered:
            if (
                row.point is None
                or row.status != "PROJECTED"
                or current
                and row.timestamp - current[-1].timestamp > policy["max_gap_s"]
            ):
                if current:
                    chunks.append(current)
                current = []
            if row.point is not None and row.status == "PROJECTED":
                current.append(row)
        if current:
            chunks.append(current)
        for chunk in chunks:
            for region in config.regions:
                x0, y0, x1, y1 = region.bounds_xy_m
                inside = [
                    x0 <= _point(row)[0] <= x1 and y0 <= _point(row)[1] <= y1 for row in chunk
                ]
                runs: list[tuple[bool, int, int]] = []
                start = 0
                for end in range(1, len(chunk) + 1):
                    if end == len(chunk) or inside[end] != inside[start]:
                        runs.append((inside[start], start, end - 1))
                        start = end

                def emit(
                    kind: str,
                    begin: int,
                    end: int,
                    confirmation: int,
                    *,
                    retract: int | None = None,
                    unknown: bool = False,
                    chunk: list[ProjectedMeasurement] = chunk,
                    track_id: str = track_id,
                    region: ConfiguredRegion = region,
                ) -> None:
                    evidence = chunk[begin : end + 1]
                    if not evidence:
                        return
                    dedupe = digest(
                        [config_hash, track_id, region.region_id, kind, evidence[0].observation_id]
                    )
                    refs = list(dict.fromkeys(row.frame_ref for row in evidence))
                    picked = [0, len(evidence) // 2, len(evidence) - 1]
                    frames = {
                        evidence[index].frame_ref: {
                            "frame_ref": evidence[index].frame_ref,
                            "camera_id": evidence[index].camera_id,
                            "timestamp": evidence[index].timestamp,
                            "evidence_state": "PROJECTED",
                        }
                        for index in picked
                    }
                    lifecycle = [
                        {
                            "transition": "UNKNOWN" if unknown else "TRIGGER",
                            "at": chunk[confirmation].timestamp,
                            "reason": "LEFT_CENSORED" if unknown else "SUSTAINED_VISIBLE_EVIDENCE",
                        }
                    ]
                    if retract is not None:
                        lifecycle.append(
                            {
                                "transition": "RETRACT",
                                "at": chunk[retract].timestamp,
                                "reason": "CONDITION_ENDED_BY_VISIBLE_SAMPLE",
                            }
                        )
                    events.append(
                        {
                            "event_id": "region-event:" + dedupe[:24],
                            "dedupe_key": dedupe,
                            "kind": kind,
                            "local_track_id": track_id,
                            "region_id": region.region_id,
                            "camera_id": evidence[0].camera_id,
                            "time_range": [evidence[0].timestamp, evidence[-1].timestamp],
                            "support_state": "UNKNOWN" if unknown else "SUPPORTED",
                            "state": "UNKNOWN"
                            if unknown
                            else "RETRACTED"
                            if retract is not None
                            else "TRIGGERED",
                            "active": not unknown and retract is None,
                            "lifecycle": lifecycle,
                            "rule_version": policy["version"],
                            "config_sha256": config_hash,
                            "evidence_count": len(evidence),
                            "source_frames": list(frames.values()),
                            "all_evidence_sha256": digest(refs),
                            "missing_evidence": ["NO_VISIBLE_PRIOR_OUTSIDE_SAMPLES"]
                            if unknown
                            else [],
                            "uncertainty": "Provisional local track; no global identity or intent.",
                        }
                    )

                for run_index, (is_inside, begin, end) in enumerate(runs):
                    if not is_inside:
                        continue
                    size = end - begin + 1
                    previous = runs[run_index - 1] if run_index else None
                    following = runs[run_index + 1] if run_index + 1 < len(runs) else None
                    confirmed = size >= policy["side_samples"]
                    prior_outside = previous is not None and (
                        previous[2] - previous[1] + 1 >= policy["side_samples"]
                    )
                    exit_confirmed = following is not None and (
                        following[2] - following[1] + 1 >= policy["side_samples"]
                    )
                    if confirmed:
                        emit(
                            "REGION_ENTRY",
                            max(0, begin - policy["side_samples"]),
                            begin + policy["side_samples"] - 1,
                            begin + policy["side_samples"] - 1,
                            retract=following[1] + policy["side_samples"] - 1
                            if exit_confirmed and following is not None
                            else None,
                            unknown=not prior_outside,
                        )
                    if confirmed and exit_confirmed:
                        assert following is not None
                        emit(
                            "REGION_EXIT",
                            end - policy["side_samples"] + 1,
                            following[1] + policy["side_samples"] - 1,
                            following[1] + policy["side_samples"] - 1,
                        )
                    cursor = begin
                    while cursor < end:
                        finish = cursor
                        origin = _point(chunk[cursor])
                        while finish < end:
                            left, right = chunk[finish], chunk[finish + 1]
                            dt = right.timestamp - left.timestamp
                            if (
                                dt <= 0
                                or math.dist(origin, _point(right)) > policy["dwell_radius_m"]
                                or math.dist(_point(left), _point(right)) / dt
                                > policy["dwell_speed_m_s"]
                            ):
                                break
                            finish += 1
                        trigger = next(
                            (
                                index
                                for index in range(cursor + 1, finish + 1)
                                if chunk[index].timestamp - chunk[cursor].timestamp
                                >= policy["dwell_duration_s"]
                            ),
                            None,
                        )
                        if trigger is not None:
                            emit(
                                "SUSTAINED_DWELL",
                                cursor,
                                finish,
                                trigger,
                                retract=finish + 1 if finish + 1 < len(chunk) else None,
                            )
                        cursor = finish + 1
    unique = {event["dedupe_key"]: event for event in events}
    return {
        "schema_version": "phase2.region-rules.v1",
        "config_sha256": config_hash,
        "rule_version": policy["version"],
        "events": sorted(
            unique.values(), key=lambda event: (event["time_range"][0], event["event_id"])
        ),
        "denominators": {
            "local_tracks": len(tracks),
            "regions": len(config.regions),
            "projected_samples": sum(
                row.point is not None for row in inference.projected_measurements
            ),
        },
        "limitations": [
            "Configured synthetic regions only.",
            "Retraction ends an alert condition; historical trigger is retained.",
            "Missing projection/sample gaps break evidence; no invented samples.",
            "No independent REGION_ENTRY/EXIT behavior labels; precision is N/A.",
        ],
    }
