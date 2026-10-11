"""Deterministic, bounded RGB frame retrieval without an Agent or truth input.

Only sanitized camera/time/media and an independently bound floor plane enter
this module. Pixel measurements are recomputed once at import. Querying reads
the import-built camera/time feature index and never opens source images.
"""

from __future__ import annotations

import copy
import hashlib
import math
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

from amidst.domain.camera import Camera
from amidst.domain.common import Provenance
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.engineering.perception import Measurement, RGBFrame, produce_perception
from amidst.engineering.registry import content_hash, opaque_ref
from amidst.geometry.inverse_projection import InverseProjectionError, InverseProjectionService

Json = dict[str, Any]
MAX_CAMERAS = 4
MAX_WINDOW_SECONDS = 10.0
MAX_TOP_K = 5
MAX_INPUT_FRAMES = 400
MAX_FRAMES_PER_CAMERA = 128
BASELINE_VERSION = "rgb-floor-frame-diversity-v1"

Name = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,149}$")]
Sha = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Ref = Annotated[str, Field(pattern=r"^[a-z]+:[0-9a-f]{24}$")]


class _SafeInput(BaseModel):
    # The adapter can carry display fields; only this explicit allowlist is read.
    model_config = ConfigDict(extra="ignore", frozen=True, validate_default=True)


class _Binding(_SafeInput):
    source_sha256: Sha
    dataset_sha256: Sha
    site_id: Name
    run_id: Name
    clock_id: Name
    scale_sha256: Sha


class _CameraInput(_SafeInput):
    camera_id: Name
    camera_ref: Ref
    calibration: Camera

    @model_validator(mode="after")
    def matched_camera(self) -> _CameraInput:
        if self.camera_id != self.calibration.camera_id:
            raise ValueError("CAMERA_CALIBRATION_MISMATCH")
        return self


class _FrameInput(_SafeInput):
    frame_ref: Ref
    camera_id: Name
    timestamp: Annotated[FiniteFloat, Field(ge=0)]
    width: Annotated[int, Field(gt=0, le=1920, strict=True)]
    height: Annotated[int, Field(gt=0, le=1080, strict=True)]
    sha256: Sha
    byte_count: Annotated[int, Field(gt=0, strict=True)]
    local_path: Path


class _FloorInput(_SafeInput):
    point: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    normal: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    source_sha256: Sha
    authority: Literal["APPROVED"]
    floor_id: Name = "1F"


class _Inputs(_SafeInput):
    source_binding: _Binding
    cameras: tuple[_CameraInput, ...]
    frames: tuple[_FrameInput, ...]
    floor_plane: _FloorInput


def _measurement_key(row: Measurement) -> tuple[float, int, int, str]:
    return (row.uncertainty, int(row.status != "DETECTED"),
            row.local_alternative_count, row.observation_id)


class BaselineFrameIndex:
    """One site/run's immutable, class-agnostic pixel and projection index."""

    def __init__(self, inputs: Json) -> None:
        value = _Inputs.model_validate(inputs)
        if value.floor_plane.source_sha256 != value.source_binding.source_sha256:
            raise ValueError("FLOOR_SOURCE_MISMATCH")
        camera_ids = [row.camera_id for row in value.cameras]
        if not 1 <= len(camera_ids) <= MAX_CAMERAS or len(set(camera_ids)) != len(camera_ids):
            raise ValueError("CAMERA_IMPORT_BUDGET")
        if not 1 <= len(value.frames) <= MAX_INPUT_FRAMES:
            raise ValueError("FRAME_IMPORT_BUDGET")
        camera_map = {row.camera_id: row.calibration for row in value.cameras}
        identities = [(row.camera_id, row.timestamp) for row in value.frames]
        refs = [row.frame_ref for row in value.frames]
        if len(set(identities)) != len(identities) or len(set(refs)) != len(refs):
            raise ValueError("FRAME_IMPORT_DUPLICATE")
        per_camera = Counter(row.camera_id for row in value.frames)
        if any(count > MAX_FRAMES_PER_CAMERA for count in per_camera.values()):
            raise ValueError("FRAME_IMPORT_BUDGET")
        for row in value.frames:
            camera = camera_map.get(row.camera_id)
            if camera is None or (row.width, row.height) != (camera.width, camera.height):
                raise ValueError("FRAME_CAMERA_MISMATCH")
        self._binding = value.source_binding.model_dump(mode="json")
        self._camera_ids = frozenset(camera_ids)
        self._plane_binding = {
            "source_sha256": value.floor_plane.source_sha256,
            "authority": value.floor_plane.authority,
            "floor_id": value.floor_plane.floor_id,
            "point": list(value.floor_plane.point), "normal": list(value.floor_plane.normal),
        }
        self._calibration_sha256 = content_hash({key: camera.model_dump(mode="json")
                                                for key, camera in sorted(camera_map.items())})
        plane = Plane(plane_id="baseline-source-floor", point=value.floor_plane.point,
                      normal=value.floor_plane.normal, floor_id=value.floor_plane.floor_id)
        projectors = {key: InverseProjectionService(camera, plane)
                      for key, camera in camera_map.items()}
        rgb = tuple(RGBFrame(media_ref=row.frame_ref, camera_id=row.camera_id,
                             timestamp=row.timestamp, path=row.local_path, sha256=row.sha256,
                             width=row.width, height=row.height) for row in value.frames)
        pixels = produce_perception(rgb, model_id="blender-" + value.source_binding.site_id,
                                    run_id=value.source_binding.run_id)
        measurements: dict[str, list[Measurement]] = defaultdict(list)
        public_measurements: dict[str, Json] = {}
        for number, measurement in enumerate(pixels.measurements):
            measurements[measurement.frame_ref].append(measurement)
            public = self._project(measurement, number, projectors[measurement.camera_id])
            public_measurements[measurement.observation_id] = public
        self._observations = tuple(public_measurements.values())
        self._local_tracks = tuple({
            "track_ref": opaque_ref("track", track.local_track_id),
            "camera_id": track.camera_id,
            "observation_refs": [public_measurements[ref]["observation_ref"]
                                 for ref in track.observation_ids],
            "timestamps": list(track.timestamps), "status": track.status,
            "missing_timestamps": list(track.missing_timestamps),
            "termination_reason": track.termination_reason,
            "authority": "CAMERA_LOCAL_PIXEL_COMPONENT_TRACK",
            "identity_verdict": "UNCONFIRMED",
        } for track in pixels.tracks)
        statuses = {row.frame_ref: row for row in pixels.frame_statuses}
        records: dict[str, Json] = {}
        buckets: dict[str, list[Json]] = {key: [] for key in camera_ids}
        for row in sorted(value.frames, key=lambda f: (f.camera_id, f.timestamp, f.frame_ref)):
            status = statuses[row.frame_ref]
            found = measurements.get(row.frame_ref, [])
            selected = min(found, key=_measurement_key) if found else None
            feature = public_measurements[selected.observation_id] if selected else {}
            record = {
                "frame_ref": row.frame_ref, "media_ref": row.frame_ref,
                "camera_id": row.camera_id, "timestamp": float(row.timestamp),
                "width": row.width, "height": row.height, "source_image_sha256": row.sha256,
                "byte_count": row.byte_count, "frame_status": status.status,
                "measurement_count": len(found), "image_measurement": selected is not None,
                "measurement_status": feature.get("measurement_status", "NO_MEASUREMENT"),
                "bbox_xyxy": feature.get("bbox_xyxy"),
                "contact_pixel": feature.get("contact_pixel"),
                "uncertainty": feature.get("uncertainty"),
                "projection_status": feature.get("projection_status", "NOT_ATTEMPTED"),
                "projection_reason": feature.get("projection_reason"),
                "world_position": feature.get("world_position"),
                "projection_quality": feature.get("projection_quality"),
                "observation_ref": feature.get("observation_ref"),
                "track_ref": feature.get("track_ref"),
                "measurement_basis": "RGB_PIXELS",
                "geometry_authority": "SOURCE_BOUND_FLOOR_INTERSECTION_ONLY",
                "identity_verdict": "UNCONFIRMED", "behavior_verdict": "UNKNOWN",
            }
            records[row.frame_ref] = record
            buckets[row.camera_id].append(record)
        self._records = records
        self._buckets = {key: tuple(rows) for key, rows in buckets.items()}
        self._times = {key: tuple(row["timestamp"] for row in rows)
                       for key, rows in self._buckets.items()}
        self._steps = {key: min((b - a for a, b in zip(times, times[1:], strict=False)
                               if b > a), default=0.0) for key, times in self._times.items()}
        self._baseline_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        self.source_features = content_hash({"binding": self._binding,
                                            "floor": self._plane_binding,
                                            "calibration_sha256": self._calibration_sha256,
                                            "records": list(records.values()),
                                            "observations": self._observations,
                                            "producer_sha256": pixels.producer_sha256,
                                            "baseline_sha256": self._baseline_sha256,
                                            "baseline_version": BASELINE_VERSION})
        self._telemetry = {
            "import_frames_read": len(value.frames),
            "import_bytes_expected": sum(row.byte_count for row in value.frames),
            "import_camera_count": len(camera_ids), "pixel_measurements": len(pixels.measurements),
            "local_tracks": len(pixels.tracks),
            "projected_measurements": sum(row["projection_status"] == "PROJECTED"
                                           for row in self._observations),
            "frame_status_counts": dict(Counter(row.status for row in pixels.frame_statuses)),
            "complete": pixels.complete, "producer_sha256": pixels.producer_sha256,
            "input_manifest_sha256": pixels.input_manifest_sha256,
            "gt_used": False, "agent_calls": 0, "external_model_calls": 0,
        }

    @staticmethod
    def _project(row: Measurement, frame_id: int, projector: InverseProjectionService) -> Json:
        point = None
        reason = None
        frame = ObservationFrame(frame_id=frame_id, timestamp=row.timestamp,
                                 target_id=row.local_track_id, camera_id=row.camera_id,
                                 status=VisibilityStatus.OBSERVED, point_2d=row.contact_pixel,
                                 provenance=Provenance.OBSERVED)
        try:
            point = projector.project_frame(frame)
        except InverseProjectionError as error:
            reason = error.failure.value
        return {
            "observation_ref": opaque_ref("observation", row.observation_id, row.input_sha256),
            "track_ref": opaque_ref("track", row.local_track_id),
            "frame_ref": row.frame_ref, "camera_id": row.camera_id,
            "timestamp": float(row.timestamp), "bbox_xyxy": list(row.bbox_xyxy),
            "contact_pixel": list(row.contact_pixel), "uncertainty": row.uncertainty,
            "measurement_status": row.status,
            "local_alternative_count": row.local_alternative_count,
            "projection_status": "PROJECTED" if point else "PROJECTION_MISSING",
            "projection_reason": reason,
            "world_position": list(point.world_position) if point else None,
            "projection_quality": point.projection_quality if point else None,
            "source_image_sha256": row.input_sha256, "measurement_basis": "RGB_PIXELS",
            "geometry_authority": "SOURCE_BOUND_FLOOR_INTERSECTION_ONLY",
            "identity_verdict": "UNCONFIRMED", "behavior_verdict": "UNKNOWN",
        }

    @property
    def frame_records(self) -> list[Json]:
        return copy.deepcopy(list(self._records.values()))

    @property
    def observations(self) -> list[Json]:
        return copy.deepcopy(list(self._observations))

    @property
    def telemetry(self) -> Json:
        return copy.deepcopy(self._telemetry)

    def snapshot(self) -> Json:
        measurements = [{key: row[key] for key in (
            "observation_ref", "track_ref", "frame_ref", "camera_id", "timestamp",
            "bbox_xyxy", "contact_pixel", "uncertainty", "measurement_status",
            "local_alternative_count", "source_image_sha256", "measurement_basis",
            "identity_verdict", "behavior_verdict",
        )} for row in self._observations]
        projected = [{key: row[key] for key in (
            "observation_ref", "frame_ref", "camera_id", "timestamp", "projection_status",
            "projection_reason", "world_position", "projection_quality", "geometry_authority",
        )} for row in self._observations]
        return {
            "schema_version": "workbench.frame-baseline-index.v1",
            "source_binding": copy.deepcopy(self._binding), "source_features": self.source_features,
            "calibration_sha256": self._calibration_sha256,
            "floor_plane": copy.deepcopy(self._plane_binding), "telemetry": self.telemetry,
            "frames": self.frame_records, "measurements": copy.deepcopy(measurements),
            "projected_measurements": copy.deepcopy(projected),
            "local_tracks": copy.deepcopy(list(self._local_tracks)),
            "producer_sha256": self._telemetry["producer_sha256"],
            "baseline_sha256": self._baseline_sha256,
            "feature_sha256": self.source_features, "import_telemetry": self.telemetry,
            "source_types": self._source_types(), "agent_used": False,
            "formal_acceptance": False, "baseline_version": BASELINE_VERSION,
        }

    @staticmethod
    def _source_types() -> Json:
        return {
            "rgb": "ACTUAL_BLENDER_CAMERA_RENDER",
            "geometry_and_camera": "ACTUAL_SOURCE_BLEND_DERIVATION",
            "target_and_motion": "SUBSTITUTE_SYNTHETIC_TARGET_AND_PATH",
            "measurement": "RECOMPUTED_RGB_PIXELS_CLASS_AGNOSTIC",
            "projection": "SOURCE_BOUND_FLOOR_INTERSECTION_WITH_UNCERTAINTY",
            "identity_and_behavior": "UNKNOWN",
        }

    def _validate_cameras(self, camera_ids: Sequence[str]) -> None:
        if (isinstance(camera_ids, (str, bytes)) or not 1 <= len(camera_ids) <= MAX_CAMERAS
                or len(set(camera_ids)) != len(camera_ids)
                or any(key not in self._camera_ids for key in camera_ids)):
            raise ValueError("CAMERA_SCOPE_DENIED")

    def get_frame(self, frame_ref: str) -> Json:
        row = self._records.get(frame_ref)
        if row is None:
            raise ValueError("FRAME_SCOPE_DENIED")
        return copy.deepcopy(row)

    def frames(self, camera_ids: Sequence[str], timestamp: float) -> Json:
        self._validate_cameras(camera_ids)
        if isinstance(timestamp, bool) or not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("INVALID_FRAME_TIME")
        frames = []
        for camera_id in camera_ids:
            times = self._times[camera_id]
            selected = None
            if times and times[0] <= timestamp <= times[-1]:
                i = bisect_left(times, timestamp)
                nearby = [j for j in (i - 1, i) if 0 <= j < len(times)]
                best = min(nearby, key=lambda j: (abs(times[j] - timestamp), times[j]))
                if abs(times[best] - timestamp) <= self._steps[camera_id] * 0.51:
                    selected = self._buckets[camera_id][best]
            frames.append({
                "camera_id": camera_id, "requested_timestamp": timestamp,
                "timestamp": selected["timestamp"] if selected else None,
                "media_ref": selected["media_ref"] if selected else None,
                "frame_ref": selected["frame_ref"] if selected else None,
                "status": "MISSING" if selected is None else
                "EXACT" if selected["timestamp"] == timestamp else "NEAREST_AVAILABLE",
                "time_offset_s": selected["timestamp"] - timestamp if selected else None,
            })
        return {"frames": frames, "retrieval": {
            "camera_lookups": len(camera_ids), "frames_read": 0, "bytes_read": 0,
            "global_scan": False, "import_built_index": True}}

    def query(self, camera_ids: Sequence[str], start: float, end: float,
              target_timestamp: float, top_k: int = 3, behavior_intent: str = "walking") -> Json:
        self._validate_cameras(camera_ids)
        if any(isinstance(t, bool) or not math.isfinite(t) for t in (start, end, target_timestamp)):
            raise ValueError("INVALID_TIME_RANGE")
        if (start < 0 or end < start or end - start > MAX_WINDOW_SECONDS
                or not start <= target_timestamp <= end):
            raise ValueError("FINITE_FRAME_WINDOW_REQUIRED")
        if type(top_k) is not int or not 1 <= top_k <= MAX_TOP_K:
            raise ValueError("TOP_K_BUDGET")
        if behavior_intent not in {"walking", "running", "enter_exit"}:
            raise ValueError("BEHAVIOR_INTENT_DENIED")
        scoped: list[Json] = []
        best_by_camera: list[Json] = []
        records_read = 0
        for camera_id in sorted(camera_ids):
            times = self._times[camera_id]
            low, high = bisect_left(times, start), bisect_right(times, end)
            rows = self._buckets[camera_id][low:high]
            records_read += len(rows)
            eligible = []
            for row in rows:
                if not row["image_measurement"]:
                    continue
                item = copy.deepcopy(row)
                item["rank_key"] = [int(row["measurement_status"] != "DETECTED"),
                                    int(row["projection_status"] != "PROJECTED"),
                                    round(abs(row["timestamp"] - target_timestamp), 12),
                                    row["timestamp"], camera_id, row["frame_ref"]]
                eligible.append(item)
            eligible.sort(key=lambda item: item["rank_key"])
            if eligible:
                best_by_camera.append(eligible[0])
            scoped.extend(eligible)
        best_by_camera.sort(key=lambda item: item["rank_key"])
        first_refs = {row["frame_ref"] for row in best_by_camera}
        remainder = sorted((row for row in scoped if row["frame_ref"] not in first_refs),
                           key=lambda item: item["rank_key"])
        selected = [*best_by_camera, *remainder][:top_k]
        for rank, row in enumerate(selected, 1):
            row["rank"] = rank
            row["selection_reason"] = ("FIRST_BEST_PER_CAMERA" if row["frame_ref"] in first_refs
                                       else "REMAINING_SCOPED_RANK")
            row["rank_reasons"] = [
                "RELIABLE_COMPONENT_FIRST" if row["measurement_status"] == "DETECTED"
                else "PARTIAL_OR_MERGED_COMPONENT",
                "VALID_FLOOR_PROJECTION" if row["projection_status"] == "PROJECTED"
                else "FLOOR_PROJECTION_UNAVAILABLE",
                "NEAREST_REQUESTED_TIME_WITH_STABLE_TIE_BREAK",
            ]
        return {
            "schema_version": "workbench.frame-baseline-query.v1",
            "status": "READY" if selected else "NO_RESULT", "items": selected,
            "provider": "LOCAL_DETERMINISTIC_BASELINE", "agent_used": False,
            "scope": copy.deepcopy(self._binding), "source_features": self.source_features,
            "source_types": self._source_types(), "formal_acceptance": False,
            "selection": {"camera_ids": sorted(camera_ids), "time_range": [start, end],
                          "target_timestamp": target_timestamp, "top_k": top_k,
                          "behavior_intent": behavior_intent,
                          "intent_authority": "USER_SELECTED_INTENT"},
            "behavior_verdict": "UNKNOWN", "identity_verdict": "UNCONFIRMED",
            "ranking": {"version": BASELINE_VERSION, "score_is_probability": False,
                        "time_distance_decimal_places": 12,
                        "camera_diversity": "BEST_PER_CAMERA_THEN_REMAINING_SCOPED_RANK",
                        "key_order": ["measurement_quality", "projection_available",
                                      "time_distance_s", "timestamp", "camera_id", "frame_ref"]},
            "retrieval": {"camera_lookups": len(camera_ids), "records_read": records_read,
                          "eligible_frames": len(scoped), "returned_frames": len(selected),
                          "omitted_frames": max(0, len(scoped) - len(selected)),
                          "frames_read": 0, "bytes_read": 0, "global_scan": False,
                          "import_built_index": True},
            "limitations": [
                "Pixel components and local tracks do not identify people or classify behavior.",
                "A floor intersection does not establish visibility or walkable support.",
                "The rendered target and its motion are synthetic substitutes.",
            ],
        }
