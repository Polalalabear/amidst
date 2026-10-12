"""Camera-local motion curves derived only from sanitized RGB floor projections.

Projected positions are not directly observed 3D. Linear gap filling and finite
differences are explicit inference, bounded by an engineering policy rather than
human, navigation, collision or whole-scene physical certification. No images,
filesystem locators, simulator answers, Ground Truth or Agent enter this module.
"""

from __future__ import annotations

import copy
import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Sequence
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from amidst.domain.geometry import Plane
from amidst.engineering.registry import content_hash, opaque_ref

Json = dict[str, Any]
MAX_CAMERAS = 4
MAX_WINDOW_S = 10.0
MAX_POINTS = 400
MAX_TRACKS = 32
MAX_INTERPOLATION_GAP_S = 1.0
MAX_SPEED_M_S = 8.0
MOTION_VERSION = "camera-local-floor-motion-v1"
Name = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,149}$")]
Sha = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Ref = Annotated[str, Field(pattern=r"^[a-z]+:[0-9a-f]{24}$")]
Time = Annotated[FiniteFloat, Field(ge=0)]
Vector = tuple[FiniteFloat, FiniteFloat, FiniteFloat]


class _Safe(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, validate_default=True)


class _Binding(_Safe):
    source_sha256: Sha
    dataset_sha256: Sha
    site_id: Name
    run_id: Name
    clock_id: Name
    scale_sha256: Sha
    units: Literal["METRES"] = "METRES"
    normalized_units: Literal["METRES"] = "METRES"
    time_unit: Literal["SECONDS"] = "SECONDS"


class _Floor(_Safe):
    point: Vector
    normal: Vector
    floor_id: Name
    source_sha256: Sha
    authority: Literal["APPROVED"]
    units: Literal["METRES"] = "METRES"


class _Frame(_Safe):
    frame_ref: Ref
    camera_id: Name
    timestamp: Time
    source_image_sha256: Sha


class _Measurement(_Safe):
    observation_ref: Ref
    track_ref: Ref
    frame_ref: Ref
    camera_id: Name
    timestamp: Time
    bbox_xyxy: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]
    contact_pixel: tuple[FiniteFloat, FiniteFloat]
    uncertainty: Annotated[FiniteFloat, Field(ge=0, le=1)]
    measurement_status: Literal["DETECTED", "MERGED_OR_PARTIAL"]
    source_image_sha256: Sha
    measurement_basis: Literal["RGB_PIXELS"]


class _Projection(_Safe):
    observation_ref: Ref
    frame_ref: Ref
    camera_id: Name
    timestamp: Time
    projection_status: Literal["PROJECTED", "PROJECTION_MISSING"]
    projection_reason: Name | None = None
    world_position: Vector | None
    projection_quality: Annotated[FiniteFloat, Field(ge=0, le=1)] | None = None
    geometry_authority: Literal["SOURCE_BOUND_FLOOR_INTERSECTION_ONLY"]
    units: Literal["METRES"] = "METRES"


class _Track(_Safe):
    track_ref: Ref
    camera_id: Name
    observation_refs: tuple[Ref, ...]
    timestamps: tuple[Time, ...]
    missing_timestamps: tuple[Time, ...]
    status: Literal["COMPLETE", "FRAGMENTED"]
    termination_reason: Literal["SEQUENCE_END", "LOST_OR_LEFT_VIEW"]
    authority: Literal["CAMERA_LOCAL_PIXEL_COMPONENT_TRACK"]


class _Snapshot(_Safe):
    schema_version: Literal["workbench.frame-baseline-index.v1"]
    source_binding: _Binding
    source_features: Sha
    feature_sha256: Sha | None = None
    calibration_sha256: Sha
    producer_sha256: Sha
    floor_plane: _Floor
    frames: Annotated[tuple[_Frame, ...], Field(min_length=1, max_length=MAX_POINTS)]
    measurements: Annotated[tuple[_Measurement, ...], Field(max_length=MAX_POINTS)]
    projected_measurements: Annotated[tuple[_Projection, ...], Field(max_length=MAX_POINTS)]
    local_tracks: Annotated[tuple[_Track, ...], Field(max_length=MAX_TRACKS)]
    units: Literal["METRES"] = "METRES"
    position_units: Literal["METRES"] = "METRES"


def _unique(rows: Sequence[Any], key: str) -> dict[str, Any]:
    indexed = {getattr(row, key): row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError("MOTION_DUPLICATE_REFERENCE")
    return indexed


class BaselineMotionIndex:
    """Import full local-track curves once; query windows never regroup their events."""

    def __init__(self, snapshot: Json) -> None:
        value = _Snapshot.model_validate(snapshot)
        if value.floor_plane.source_sha256 != value.source_binding.source_sha256:
            raise ValueError("MOTION_FLOOR_SOURCE_MISMATCH")
        if value.feature_sha256 is not None and value.feature_sha256 != value.source_features:
            raise ValueError("MOTION_FEATURE_BINDING_MISMATCH")
        floor = Plane(plane_id="motion-source-floor", point=value.floor_plane.point,
                      normal=value.floor_plane.normal, floor_id=value.floor_plane.floor_id)
        frames = _unique(value.frames, "frame_ref")
        measurements = _unique(value.measurements, "observation_ref")
        projected = _unique(value.projected_measurements, "observation_ref")
        _unique(value.local_tracks, "track_ref")
        if set(measurements) != set(projected):
            raise ValueError("MOTION_PROJECTION_BINDING_MISMATCH")
        camera_times: dict[str, list[float]] = defaultdict(list)
        frame_at: dict[tuple[str, float], _Frame] = {}
        for frame in value.frames:
            identity = (frame.camera_id, float(frame.timestamp))
            if identity in frame_at:
                raise ValueError("MOTION_DUPLICATE_FRAME_TIME")
            frame_at[identity] = frame
            camera_times[frame.camera_id].append(float(frame.timestamp))
        if len(camera_times) > MAX_CAMERAS:
            raise ValueError("MOTION_CAMERA_BUDGET")
        all_times = [float(row.timestamp) for row in value.frames]
        if max(all_times) - min(all_times) > MAX_WINDOW_S:
            raise ValueError("MOTION_IMPORT_WINDOW_BUDGET")
        assigned: set[str] = set()
        for track in value.local_tracks:
            if track.camera_id not in camera_times or not track.observation_refs:
                raise ValueError("MOTION_TRACK_SCOPE_MISMATCH")
            rows = []
            for ref in track.observation_refs:
                measurement = measurements.get(ref)
                if (measurement is None or measurement.camera_id != track.camera_id
                        or measurement.track_ref != track.track_ref):
                    raise ValueError("MOTION_TRACK_SCOPE_MISMATCH")
                rows.append(measurement)
            times = tuple(row.timestamp for row in rows)
            if times != track.timestamps or tuple(sorted(set(times))) != times:
                raise ValueError("MOTION_TRACK_TIME_MISMATCH")
            if assigned.intersection(track.observation_refs):
                raise ValueError("MOTION_TRACK_REFERENCE_REUSED")
            assigned.update(track.observation_refs)
        if assigned != set(measurements):
            raise ValueError("MOTION_UNASSIGNED_MEASUREMENT")
        for measurement in value.measurements:
            bound_frame = frames.get(measurement.frame_ref)
            projection = projected[measurement.observation_ref]
            if bound_frame is None or (measurement.camera_id, measurement.timestamp,
                                 measurement.source_image_sha256) != (
                    bound_frame.camera_id, bound_frame.timestamp, bound_frame.source_image_sha256):
                raise ValueError("MOTION_PIXEL_FRAME_MISMATCH")
            if (projection.camera_id, projection.timestamp, projection.frame_ref) != (
                    measurement.camera_id, measurement.timestamp, measurement.frame_ref):
                raise ValueError("MOTION_PROJECTION_BINDING_MISMATCH")
            if projection.world_position is not None:
                distance = sum((p - q) * n for p, q, n in zip(
                    projection.world_position, floor.point, floor.normal, strict=True))
                if not math.isfinite(distance) or abs(distance) > 1e-6:
                    raise ValueError("MOTION_FLOOR_UNIT_MISMATCH")
        self.source_features = value.source_features
        self._binding = value.source_binding.model_dump(mode="json")
        self._floor = value.floor_plane.model_dump(mode="json")
        self._source_hashes = {"calibration_sha256": value.calibration_sha256,
                               "pixel_producer_sha256": value.producer_sha256}
        self._camera_ids = frozenset(camera_times)
        self._camera_times = {camera: tuple(sorted(times))
                              for camera, times in camera_times.items()}
        self._pixel_times = {camera: tuple(sorted(row.timestamp for row in value.measurements
                                                if row.camera_id == camera))
                             for camera in camera_times}
        self._projected_times = {
            camera: tuple(sorted({row.timestamp for row in value.projected_measurements
                                  if row.camera_id == camera
                                  and row.projection_status == "PROJECTED"
                                  and row.world_position is not None})) for camera in camera_times}
        self._time_range = [min(all_times), max(all_times)]
        self._policy = {
            "algorithm_version": MOTION_VERSION, "max_gap_s": MAX_INTERPOLATION_GAP_S,
            "max_speed_m_s": MAX_SPEED_M_S, "authority": "CONFIGURED_ENGINEERING_CAP",
            "position_units": "METRES", "speed_units": "METRES_PER_SECOND",
            "max_cameras": MAX_CAMERAS, "max_window_s": MAX_WINDOW_S,
            "max_points": MAX_POINTS, "max_tracks": MAX_TRACKS,
            "cross_camera_identity_merge": False, "track_stitching": False,
            "extrapolation": False, "collision_checked": False, "navigation_checked": False,
            "uncertainty_authority": "PIXEL_COMPONENT_HEURISTIC_NOT_PROBABILITY",
        }
        self._tracks: dict[str, Json] = {}
        camera_tracks: dict[str, list[str]] = {camera: [] for camera in camera_times}
        for track in sorted(value.local_tracks, key=lambda row: (row.camera_id, row.track_ref)):
            curve = self._build_track(track, measurements, projected,
                                      sorted(camera_times[track.camera_id]), frame_at)
            self._tracks[track.track_ref] = curve
            camera_tracks[track.camera_id].append(track.track_ref)
        if sum(len(row["samples"]) for row in self._tracks.values()) > MAX_POINTS:
            raise ValueError("MOTION_CANONICAL_POINT_BUDGET")
        self._camera_tracks = {key: tuple(refs) for key, refs in camera_tracks.items()}
        self._sample_times = {ref: tuple(row["timestamp"] for row in track["samples"])
                              for ref, track in self._tracks.items()}
        self.reconstruction_sha256 = content_hash({
            "source_binding": self._binding, "source_features": self.source_features,
            "source_hashes": self._source_hashes, "floor_plane": self._floor,
            "policy": self._policy, "tracks": list(self._tracks.values()),
        })

    def _build_track(self, track: _Track, measurements: dict[str, Any],
                     projections: dict[str, Any], camera_times: list[float],
                     frame_at: dict[tuple[str, float], _Frame]) -> Json:
        observed = [measurements[ref] for ref in track.observation_refs]
        first, last = float(observed[0].timestamp), float(observed[-1].timestamp)
        if any(not first < timestamp < last for timestamp in track.missing_timestamps):
            raise ValueError("MOTION_MISSING_TIME_SCOPE_MISMATCH")
        times = sorted(set(camera_times[bisect_left(camera_times, first):
                                        bisect_right(camera_times, last)])
                       | set(track.missing_timestamps))
        samples: dict[float, Json] = {}
        for timestamp in times:
            frame = frame_at.get((track.camera_id, timestamp))
            samples[timestamp] = {
                "timestamp": timestamp, "world_position": None, "state": "MISSING",
                "pixel_observed": False, "frame_ref": frame.frame_ref if frame else None,
                "observation_ref": None, "source_observation_refs": [],
                "source_frame_refs": [], "uncertainty": None,
                "measurement_status": "NO_MEASUREMENT", "projection_incidence": None,
                "connect_from_previous": False, "missing_reason": "NO_PIXEL_MEASUREMENT",
            }
        for row in observed:
            projection = projections[row.observation_ref]
            valid = projection.projection_status == "PROJECTED" and (
                projection.world_position is not None)
            samples[float(row.timestamp)] = {
                "timestamp": float(row.timestamp),
                "world_position": list(projection.world_position) if valid else None,
                "state": "PROJECTED_OBSERVATION" if valid else "MISSING",
                "pixel_observed": True, "frame_ref": row.frame_ref,
                "observation_ref": row.observation_ref,
                "source_observation_refs": [row.observation_ref],
                "source_frame_refs": [row.frame_ref], "uncertainty": row.uncertainty,
                "measurement_status": row.measurement_status,
                "bbox_xyxy": list(row.bbox_xyxy), "contact_pixel": list(row.contact_pixel),
                "projection_incidence": projection.projection_quality,
                "connect_from_previous": False,
                "missing_reason": None if valid else "INVALID_PROJECTION",
                "projection_reason": projection.projection_reason,
            }
        velocities, gaps = [], []
        for a, b in zip(observed, observed[1:], strict=False):
            left, right = samples[float(a.timestamp)], samples[float(b.timestamp)]
            dt = float(b.timestamp - a.timestamp)
            positions = (left["world_position"], right["world_position"])
            speed = None
            reason = None
            if any(position is None for position in positions):
                reason = "INVALID_PROJECTION"
            elif dt > MAX_INTERPOLATION_GAP_S:
                reason = "LONG_GAP"
            else:
                speed = math.dist(*positions) / dt
                if not math.isfinite(speed):
                    reason, speed = "NUMERICAL_FAILURE", None
                elif speed > MAX_SPEED_M_S:
                    reason = "SPEED_CAP"
            source_refs = [a.observation_ref, b.observation_ref]
            frame_refs = [a.frame_ref, b.frame_ref]
            interval = [float(a.timestamp), float(b.timestamp)]
            if reason is not None:
                gaps.append({"gap_ref": opaque_ref("gap", track.track_ref, content_hash(interval),
                                                   reason),
                             "time_range": interval, "state": "MISSING", "reason": reason,
                             "source_observation_refs": source_refs,
                             "implied_speed_m_s": speed})
                for timestamp in times:
                    if a.timestamp < timestamp < b.timestamp:
                        samples[timestamp]["missing_reason"] = reason
                continue
            assert positions[0] is not None and positions[1] is not None and speed is not None
            right["connect_from_previous"] = True
            interpolated = 0
            for timestamp in times:
                if not a.timestamp < timestamp < b.timestamp:
                    continue
                fraction = (timestamp - a.timestamp) / dt
                samples[timestamp] = {
                    "timestamp": timestamp,
                    "world_position": [x + fraction * (y - x)
                                       for x, y in zip(*positions, strict=True)],
                    "state": "INFERRED_INTERPOLATION", "pixel_observed": False,
                    "frame_ref": None, "observation_ref": None,
                    "source_observation_refs": source_refs, "source_frame_refs": frame_refs,
                    "uncertainty": max(a.uncertainty, b.uncertainty),
                    "measurement_status": "INFERRED_FROM_PROJECTED_ENDPOINTS",
                    "projection_incidence": None, "connect_from_previous": True,
                    "missing_reason": None,
                }
                interpolated += 1
            velocities.append({
                "interval_ref": opaque_ref("interval", track.track_ref, content_hash(interval)),
                "timestamp": (a.timestamp + b.timestamp) / 2, "time_range": interval,
                "velocity_xyz": [(y - x) / dt for x, y in zip(*positions, strict=True)],
                "speed_m_s": speed, "state": "INFERRED_FINITE_DIFFERENCE",
                "source_observation_refs": source_refs, "source_frame_refs": frame_refs,
                "endpoint_uncertainties": [a.uncertainty, b.uncertainty],
                "interpolated_sample_count": interpolated,
            })
        ordered = [samples[timestamp] for timestamp in sorted(samples)]
        segments: list[list[Json]] = []
        for sample in ordered:
            if sample["world_position"] is None:
                continue
            if not segments or not sample["connect_from_previous"]:
                segments.append([])
            segments[-1].append(sample)
        events = []
        scope_hash = content_hash(self._binding)
        for segment in segments:
            canonical_range = [segment[0]["timestamp"], segment[-1]["timestamp"]]
            refs = list(dict.fromkeys(ref for row in segment
                                      for ref in row["source_observation_refs"]))
            events.append({
                "event_ref": opaque_ref("event", scope_hash, track.track_ref,
                                        content_hash(segment)),
                "kind": "PROVISIONAL_LOCAL_MOTION_SEGMENT" if len(segment) > 1
                else "PROVISIONAL_PROJECTED_SAMPLE",
                "canonical_time_range": canonical_range, "source_observation_refs": refs,
                "sample_count": len(segment), "identity_verdict": "UNCONFIRMED",
                "behavior_verdict": "UNKNOWN", "physical_basis": "FLOOR_INTERSECTION_ONLY",
                "authority": "PROVISIONAL_ENGINEERING_MOTION",
            })
        return {
            "track_ref": track.track_ref, "camera_id": track.camera_id,
            "canonical_time_range": [first, last], "source_track_status": track.status,
            "termination_reason": track.termination_reason,
            "identity_verdict": "UNCONFIRMED", "behavior_verdict": "UNKNOWN",
            "samples": ordered, "velocities": velocities, "gaps": gaps, "events": events,
        }

    def reconstruct(self, camera_ids: Sequence[str], start: float, end: float) -> Json:
        if (isinstance(camera_ids, (str, bytes)) or not 1 <= len(camera_ids) <= MAX_CAMERAS
                or len(set(camera_ids)) != len(camera_ids)
                or any(camera not in self._camera_ids for camera in camera_ids)):
            raise ValueError("MOTION_CAMERA_SCOPE_DENIED")
        if (isinstance(start, bool) or isinstance(end, bool) or not math.isfinite(start)
                or not math.isfinite(end) or start < 0 or end < start
                or end - start > MAX_WINDOW_S):
            raise ValueError("MOTION_FINITE_WINDOW_REQUIRED")
        selected = []
        coverage = []
        points_read = 0
        tracks_read = 0
        for camera in sorted(camera_ids):
            frame_times = self._camera_times[camera]
            pixel_times, projected_times = self._pixel_times[camera], self._projected_times[camera]
            frame_count = bisect_right(frame_times, end) - bisect_left(frame_times, start)
            pixel_count = bisect_right(pixel_times, end) - bisect_left(pixel_times, start)
            projected_count = (bisect_right(projected_times, end)
                               - bisect_left(projected_times, start))
            coverage.append({"camera_id": camera, "time_range": [start, end],
                             "source_frame_count": frame_count,
                             "pixel_observation_count": pixel_count,
                             "projected_frame_count": projected_count,
                             "missing_projected_frame_count": frame_count - projected_count,
                             "state": "MISSING" if projected_count == 0 else
                             "PARTIAL" if projected_count < frame_count else "PROJECTED_COVERAGE",
                             "identity_verdict": "UNCONFIRMED", "behavior_verdict": "UNKNOWN"})
            for ref in self._camera_tracks[camera]:
                track = self._tracks[ref]
                first, last = track["canonical_time_range"]
                if first > end or last < start:
                    continue
                tracks_read += 1
                times = self._sample_times[ref]
                low, high = bisect_left(times, start), bisect_right(times, end)
                points_read += high - low
                result = {key: copy.deepcopy(value) for key, value in track.items()
                          if key not in {"samples", "velocities", "gaps", "events"}}
                result["samples"] = copy.deepcopy(track["samples"][low:high])
                if result["samples"] and low > 0:
                    result["samples"][0]["canonical_connect_from_previous"] = (
                        result["samples"][0]["connect_from_previous"])
                    result["samples"][0]["connect_from_previous"] = False
                    result["samples"][0]["window_clipped_before"] = True
                result["velocities"] = [copy.deepcopy(row) for row in track["velocities"]
                                        if start <= row["timestamp"] <= end]
                for name, range_key in (("gaps", "time_range"), ("events", "canonical_time_range")):
                    result[name] = [copy.deepcopy(row) for row in track[name]
                                    if row[range_key][0] <= end and row[range_key][1] >= start]
                selected.append(result)
        if points_read > MAX_POINTS or tracks_read > MAX_TRACKS:
            raise ValueError("MOTION_QUERY_BUDGET")
        states = [row["state"] for track in selected for row in track["samples"]]
        velocities = sum(len(track["velocities"]) for track in selected)
        usable = any(state != "MISSING" for state in states) or velocities > 0
        return {
            "schema_version": "workbench.blender-motion.v1", "status": "READY" if usable
            else "NO_RESULT", "source_binding": copy.deepcopy(self._binding),
            "source_features": self.source_features,
            "reconstruction_sha256": self.reconstruction_sha256,
            "source_hashes": copy.deepcopy(self._source_hashes),
            "floor_plane": copy.deepcopy(self._floor), "policy": copy.deepcopy(self._policy),
            "source_time_range": list(self._time_range),
            "selection": {"camera_ids": sorted(camera_ids), "time_range": [start, end]},
            "tracks": selected, "camera_coverage": coverage,
            "agent_used": False, "formal_acceptance": False,
            "summary": {"tracks": len(selected), "samples": len(states),
                        "projected_samples": states.count("PROJECTED_OBSERVATION"),
                        "inferred_samples": states.count("INFERRED_INTERPOLATION"),
                        "missing_samples": states.count("MISSING"),
                        "velocity_samples": velocities,
                        "gap_intervals": sum(len(track["gaps"]) for track in selected),
                        "events": sum(len(track["events"]) for track in selected)},
            "retrieval": {"camera_lookups": len(camera_ids), "tracks_read": tracks_read,
                          "points_read": points_read, "frames_read": 0, "bytes_read": 0,
                          "global_scan": False, "import_built_index": True},
            "limitations": [
                "3D positions are floor projections of actual RGB pixels, not observed 3D.",
                "Interpolation and midpoint finite differences are provisional inference.",
                "The speed cap is configured engineering policy, not human-physics certification.",
                "No camera/track identity stitching, behavior classification or extrapolation.",
                "Whole-scene walkability, navigation, occlusion and collision are not certified.",
                "The rendered target and its motion remain synthetic substitutes.",
            ],
        }
