"""Conservative partial-contact continuity over a fixed RGB detector population."""

from __future__ import annotations

from collections import defaultdict

from amidst.engineering.perception import LocalTrack, Measurement, PerceptionResult
from amidst.research_accuracy import pixel


def reassociate(
    perception: PerceptionResult,
    config: pixel.PixelContinuityConfig,
    *,
    partial_mode: str = "STRICT",
) -> PerceptionResult:
    if partial_mode == "STRICT":
        return pixel.reassociate_perception_v2(perception, config=config)
    if partial_mode != "UNAMBIGUOUS_PARTIAL":
        raise ValueError("PARTIAL_CONTINUITY_POLICY_DENIED")
    # Validate immutable inherited detector identity before using its measured contacts.
    validated = pixel.reassociate_perception_v2(perception, config=config)
    grouped: dict[str, dict[float, list[Measurement]]] = defaultdict(lambda: defaultdict(list))
    for row in perception.measurements:
        grouped[row.camera_id][row.timestamp].append(row)
    measurements, tracks = [], []
    for camera_id, camera_rows in sorted(grouped.items()):
        histories: dict[str, list[Measurement]] = {}
        reliable: dict[str, list[Measurement]] = {}
        for _, rows in sorted(camera_rows.items()):
            rows.sort(key=lambda row: (row.bbox_xyxy[0], row.bbox_xyxy[1], row.observation_id))
            options = [pixel._candidates(row, reliable, config) for row in rows]
            quarantine = [
                pixel._merged(row, candidates, config)
                for row, candidates in zip(rows, options, strict=True)
            ]
            for index, (row, candidates) in enumerate(zip(rows, options, strict=True)):
                if (
                    row.status == "MERGED_OR_PARTIAL"
                    and len(candidates) == 1
                    and candidates[0].cost <= 0.6
                    and sum(
                        any(candidate.track_id == candidates[0].track_id for candidate in other)
                        for other in options
                    )
                    == 1
                ):
                    quarantine[index] = False
            assigned = pixel._assign(options, quarantine, config)
            for row, candidates, uncertain, selected in zip(
                rows, options, quarantine, assigned, strict=True
            ):
                track_id = (
                    selected or f"track-abc:{perception.run_id}:{camera_id}:{len(histories):04d}"
                )
                histories.setdefault(track_id, [])
                updated = row.model_copy(
                    update={
                        "local_track_id": track_id,
                        "status": "MERGED_OR_PARTIAL" if uncertain else row.status,
                        "local_alternative_count": max(
                            row.local_alternative_count,
                            len(candidates) - 1,
                            len(candidates) if uncertain else 0,
                        ),
                        "uncertainty": max(row.uncertainty, 0.75 if uncertain else 0.4),
                    }
                )
                histories[track_id].append(updated)
                measurements.append(updated)
                # A continued partial contact never becomes a reliable prediction anchor.
                if not uncertain and row.status == "DETECTED":
                    reliable.setdefault(track_id, []).append(updated)
        timestamps = [
            row.timestamp for row in perception.frame_statuses if row.camera_id == camera_id
        ]
        for track_id, history in histories.items():
            times = tuple(row.timestamp for row in history)
            observed = set(times)
            missing = tuple(
                timestamp
                for timestamp in timestamps
                if times[0] < timestamp < times[-1] and timestamp not in observed
            )
            tracks.append(
                LocalTrack(
                    local_track_id=track_id,
                    camera_id=camera_id,
                    run_id=perception.run_id,
                    model_id=perception.model_id,
                    observation_ids=tuple(row.observation_id for row in history),
                    timestamps=times,
                    status="FRAGMENTED" if missing else "COMPLETE",
                    missing_timestamps=missing,
                    termination_reason="SEQUENCE_END"
                    if times[-1] == max(timestamps)
                    else "LOST_OR_LEFT_VIEW",
                )
            )
    return validated.model_copy(
        update={"measurements": tuple(measurements), "tracks": tuple(tracks)}
    )
