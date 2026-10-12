"""Numeric, provenance and scope checks for source-bound camera-local motion."""

from __future__ import annotations

import copy
import json
from collections import UserDict
from pathlib import Path
from typing import Any

import pytest
from test_frame_baseline import rgb_inputs

from amidst.engineering.registry import content_hash, opaque_ref
from amidst.workbench.blender_motion import BaselineMotionIndex
from amidst.workbench.frame_baseline import BaselineFrameIndex


def source_snapshot(
    positions: dict[float, list[float] | None], *, times: tuple[float, ...] | None = None,
    second_camera: bool = False, site: str = "office", merged_at: float | None = None,
) -> dict[str, Any]:
    """Explicit sanitized fixture, independent of any simulator/geometry answers."""
    clock = times or tuple(sorted(positions))
    cameras = ["CAM_A", "CAM_B"] if second_camera else ["CAM_A"]
    frames, measurements, projected, tracks = [], [], [], []
    for camera in cameras:
        frame_refs = {}
        for timestamp in clock:
            ref = opaque_ref("frame", site, camera, str(timestamp))
            frame_refs[timestamp] = ref
            frames.append({"frame_ref": ref, "camera_id": camera, "timestamp": timestamp,
                           "source_image_sha256": "6" * 64})
        if camera == "CAM_B":
            continue
        track_ref = opaque_ref("track", site, camera, "local-1")
        refs = []
        for timestamp, position in sorted(positions.items()):
            ref = opaque_ref("observation", site, camera, str(timestamp))
            refs.append(ref)
            measurements.append({
                "observation_ref": ref, "track_ref": track_ref,
                "frame_ref": frame_refs[timestamp], "camera_id": camera, "timestamp": timestamp,
                "bbox_xyxy": [8, 10, 16, 34], "contact_pixel": [11.5, 33],
                "uncertainty": 0.6 if timestamp == merged_at else 0.25,
                "measurement_status": "MERGED_OR_PARTIAL" if timestamp == merged_at else "DETECTED",
                "source_image_sha256": "6" * 64, "measurement_basis": "RGB_PIXELS",
            })
            projected.append({
                "observation_ref": ref, "frame_ref": frame_refs[timestamp],
                "camera_id": camera, "timestamp": timestamp,
                "projection_status": "PROJECTED" if position is not None else "PROJECTION_MISSING",
                "projection_reason": None if position is not None else "FAR_CLIPPED",
                "world_position": position, "projection_quality": 0.8 if position else None,
                "geometry_authority": "SOURCE_BOUND_FLOOR_INTERSECTION_ONLY",
            })
        if refs:
            first, last = min(positions), max(positions)
            missing = [t for t in clock if first < t < last and t not in positions]
            tracks.append({
                "track_ref": track_ref, "camera_id": camera, "observation_refs": refs,
                "timestamps": sorted(positions), "missing_timestamps": missing,
                "status": "FRAGMENTED" if missing else "COMPLETE",
                "termination_reason": "SEQUENCE_END",
                "authority": "CAMERA_LOCAL_PIXEL_COMPONENT_TRACK",
            })
    feature_sha256 = content_hash([frames, measurements, projected, tracks])
    return {
        "schema_version": "workbench.frame-baseline-index.v1",
        "source_binding": {"source_sha256": "1" * 64, "dataset_sha256": content_hash(site),
                           "site_id": site, "run_id": "motion-fixture-v1", "clock_id": "seconds",
                           "scale_sha256": "2" * 64},
        "source_features": feature_sha256, "feature_sha256": feature_sha256,
        "calibration_sha256": "3" * 64, "producer_sha256": "4" * 64,
        "floor_plane": {"point": [0, 0, 0], "normal": [0, 0, 1], "floor_id": "1F",
                        "source_sha256": "1" * 64, "authority": "APPROVED"},
        "frames": frames, "measurements": measurements, "projected_measurements": projected,
        "local_tracks": tracks,
    }


def test_numeric_projection_interpolation_and_midpoint_finite_difference() -> None:
    snapshot = source_snapshot({0: [0, 0, 0], 0.4: [0.4, 0.8, 0]},
                               times=(0, 0.2, 0.4), merged_at=0.4)
    result = BaselineMotionIndex(snapshot).reconstruct(["CAM_A"], 0, 0.4)
    track = result["tracks"][0]
    assert [row["state"] for row in track["samples"]] == [
        "PROJECTED_OBSERVATION", "INFERRED_INTERPOLATION", "PROJECTED_OBSERVATION"]
    inferred = track["samples"][1]
    assert inferred["world_position"] == pytest.approx([0.2, 0.4, 0])
    assert inferred["pixel_observed"] is False
    assert inferred["frame_ref"] is None and inferred["observation_ref"] is None
    assert len(inferred["source_observation_refs"]) == 2
    assert inferred["uncertainty"] == 0.6
    assert track["samples"][2]["measurement_status"] == "MERGED_OR_PARTIAL"
    velocity = track["velocities"][0]
    assert velocity["timestamp"] == 0.2
    assert velocity["time_range"] == [0, 0.4]
    assert velocity["velocity_xyz"] == pytest.approx([1, 2, 0])
    assert velocity["speed_m_s"] == pytest.approx(5 ** 0.5)
    assert velocity["state"] == "INFERRED_FINITE_DIFFERENCE"
    assert velocity["endpoint_uncertainties"] == [0.25, 0.6]
    assert track["events"][0]["canonical_time_range"] == [0, 0.4]
    assert result["policy"]["authority"] == "CONFIGURED_ENGINEERING_CAP"
    assert result["policy"]["collision_checked"] is False
    assert result["agent_used"] is False
    assert track["identity_verdict"] == "UNCONFIRMED" and track["behavior_verdict"] == "UNKNOWN"


@pytest.mark.parametrize("positions,times,reason", [
    ({0: [0, 0, 0], 1.2: [1.2, 0, 0]}, (0, 0.2, 0.4, 0.6, 0.8, 1, 1.2), "LONG_GAP"),
    ({0: [0, 0, 0], 0.2: [2, 0, 0]}, (0, 0.2), "SPEED_CAP"),
    ({0: [0, 0, 0], 0.2: None, 0.4: [0.4, 0, 0]}, (0, 0.2, 0.4), "INVALID_PROJECTION"),
])
def test_long_gap_speed_cap_and_invalid_projection_never_connect_or_fill(
    positions, times, reason,
) -> None:
    result = BaselineMotionIndex(source_snapshot(positions, times=times)).reconstruct(
        ["CAM_A"], min(times), max(times))
    track = result["tracks"][0]
    assert track["velocities"] == []
    assert all(row["state"] != "INFERRED_INTERPOLATION" for row in track["samples"])
    assert all(row["connect_from_previous"] is False for row in track["samples"])
    assert all(row["state"] == "MISSING" and row["reason"] == reason for row in track["gaps"])
    assert track["samples"][-1]["world_position"] is not None
    assert track["events"][-1]["kind"] == "PROVISIONAL_PROJECTED_SAMPLE"
    json.dumps(result, allow_nan=False)


def test_exact_gap_and_speed_boundaries_are_inclusive() -> None:
    index = BaselineMotionIndex(source_snapshot({0: [0, 0, 0], 1: [8, 0, 0]},
                                                times=(0, 0.2, 0.4, 0.6, 0.8, 1)))
    result = index.reconstruct(["CAM_A"], 0, 1)
    assert result["summary"]["inferred_samples"] == 4
    assert result["tracks"][0]["velocities"][0]["speed_m_s"] == 8
    assert result["tracks"][0]["gaps"] == []


def test_narrow_windows_keep_canonical_event_endpoints_ids_and_hash_without_extrapolation() -> None:
    index = BaselineMotionIndex(source_snapshot({0: [0, 0, 0], 0.4: [0.4, 0, 0]},
                                                times=(0, 0.2, 0.4)))
    full = index.reconstruct(["CAM_A"], 0, 0.4)
    narrow = index.reconstruct(["CAM_A"], 0.2, 0.4)
    assert narrow["reconstruction_sha256"] == full["reconstruction_sha256"]
    assert narrow["tracks"][0]["events"] == full["tracks"][0]["events"]
    assert narrow["tracks"][0]["canonical_time_range"] == [0, 0.4]
    assert [row["timestamp"] for row in narrow["tracks"][0]["samples"]] == [0.2, 0.4]
    first = narrow["tracks"][0]["samples"][0]
    assert first["connect_from_previous"] is False
    assert first["canonical_connect_from_previous"] is True
    assert first["window_clipped_before"] is True
    empty = index.reconstruct(["CAM_A"], 0.6, 0.8)
    assert empty["status"] == "NO_RESULT" and empty["tracks"] == []
    assert index.reconstruct(["CAM_A"], 0, 0.4) == full


def test_fragmented_tracks_are_not_stitched_even_with_matching_camera_and_positions() -> None:
    snapshot = source_snapshot({0: [0, 0, 0], 0.2: [0.2, 0, 0],
                                0.4: [0.4, 0, 0], 0.6: [0.6, 0, 0]})
    original = snapshot["local_tracks"][0]
    new_ref = opaque_ref("track", "different-camera-local-fragment")
    second = copy.deepcopy(original)
    second["track_ref"] = new_ref
    second["observation_refs"] = original["observation_refs"][2:]
    second["timestamps"] = original["timestamps"][2:]
    original["observation_refs"] = original["observation_refs"][:2]
    original["timestamps"] = original["timestamps"][:2]
    snapshot["local_tracks"].append(second)
    for row in snapshot["measurements"][2:]:
        row["track_ref"] = new_ref
    result = BaselineMotionIndex(snapshot).reconstruct(["CAM_A"], 0, 0.6)
    assert result["summary"]["tracks"] == 2
    assert result["summary"]["velocity_samples"] == 2
    assert all(track["samples"][0]["connect_from_previous"] is False for track in result["tracks"])
    assert sorted(track["canonical_time_range"] for track in result["tracks"]) == [
        [0, 0.2], [0.4, 0.6]]
    assert result["policy"]["track_stitching"] is False


def test_camera_without_measurements_preserves_missing_source_frame_coverage() -> None:
    index = BaselineMotionIndex(source_snapshot({0: [0, 0, 0], 0.2: [0.2, 0, 0]},
                                                second_camera=True))
    result = index.reconstruct(["CAM_B"], 0, 0.2)
    assert result["status"] == "NO_RESULT" and result["tracks"] == []
    assert result["camera_coverage"] == [{
        "camera_id": "CAM_B", "time_range": [0, 0.2], "source_frame_count": 2,
        "pixel_observation_count": 0, "projected_frame_count": 0,
        "missing_projected_frame_count": 2, "state": "MISSING",
        "identity_verdict": "UNCONFIRMED", "behavior_verdict": "UNKNOWN",
    }]
    empty = BaselineMotionIndex(source_snapshot({}, times=(0, 0.2)))
    assert empty.reconstruct(["CAM_A"], 0, 0.2)["summary"]["samples"] == 0


@pytest.mark.parametrize("field,where", [
    ("units", "source_binding"), ("normalized_units", "source_binding"),
    ("time_unit", "source_binding"), ("units", "floor_plane"),
    ("units", None), ("position_units", None), ("units", "projection"),
])
def test_explicit_incompatible_units_are_rejected(field, where) -> None:
    snapshot = source_snapshot({0: [0, 0, 0]})
    if where == "projection":
        snapshot["projected_measurements"][0][field] = "NATIVE_BU"
    elif where is None:
        snapshot[field] = "NATIVE_BU"
    else:
        snapshot[where][field] = "NATIVE_BU"
    with pytest.raises(ValueError):
        BaselineMotionIndex(snapshot)


@pytest.mark.parametrize("mutation,code", [
    ("floor_source", "MOTION_FLOOR_SOURCE_MISMATCH"),
    ("floor_units", "MOTION_FLOOR_UNIT_MISMATCH"),
    ("feature_hash", "MOTION_FEATURE_BINDING_MISMATCH"),
    ("camera_crossing", "MOTION_TRACK_SCOPE_MISMATCH"),
    ("pixel_time", "MOTION_PIXEL_FRAME_MISMATCH"),
    ("projection_time", "MOTION_PROJECTION_BINDING_MISMATCH"),
    ("duplicate", "MOTION_DUPLICATE_REFERENCE"),
    ("unassigned", "MOTION_UNASSIGNED_MEASUREMENT"),
])
def test_source_clock_and_track_bindings_fail_closed(mutation, code) -> None:
    snapshot = source_snapshot({0: [0, 0, 0], 0.2: [0.2, 0, 0]})
    if mutation == "floor_source":
        snapshot["floor_plane"]["source_sha256"] = "9" * 64
    elif mutation == "floor_units":
        snapshot["projected_measurements"][0]["world_position"][2] = 2
    elif mutation == "feature_hash":
        snapshot["feature_sha256"] = "9" * 64
    elif mutation == "camera_crossing":
        snapshot["local_tracks"][0]["camera_id"] = "OTHER_CAMERA"
    elif mutation == "pixel_time":
        snapshot["measurements"][0]["timestamp"] = 0.1
        snapshot["local_tracks"][0]["timestamps"][0] = 0.1
    elif mutation == "projection_time":
        snapshot["projected_measurements"][0]["timestamp"] = 0.1
    elif mutation == "duplicate":
        snapshot["frames"].append(snapshot["frames"][0])
    elif mutation == "unassigned":
        snapshot["local_tracks"] = []
    with pytest.raises(ValueError, match=code):
        BaselineMotionIndex(snapshot)


@pytest.mark.parametrize("arguments", [
    ([], 0, 1), (["OTHER"], 0, 1), (["CAM_A", "CAM_A"], 0, 1),
    (["CAM_A"], -1, 1), (["CAM_A"], 0, 11), (["CAM_A"], 1, 0),
    (["CAM_A"], float("nan"), 1), (["CAM_A"], 0, float("inf")),
    (["CAM_A"], True, 1),
])
def test_runtime_bounds(arguments) -> None:
    index = BaselineMotionIndex(source_snapshot({0: [0, 0, 0]}))
    with pytest.raises(ValueError):
        index.reconstruct(*arguments)


def test_import_bounds_and_nonfinite_input_are_rejected() -> None:
    snapshot = source_snapshot({0: [0, 0, 0]})
    excessive = copy.deepcopy(snapshot)
    excessive["frames"] *= 401
    with pytest.raises(ValueError):
        BaselineMotionIndex(excessive)
    excessive_tracks = copy.deepcopy(snapshot)
    excessive_tracks["local_tracks"] *= 33
    with pytest.raises(ValueError):
        BaselineMotionIndex(excessive_tracks)
    nonfinite = copy.deepcopy(snapshot)
    nonfinite["projected_measurements"][0]["world_position"][0] = float("nan")
    with pytest.raises(ValueError):
        BaselineMotionIndex(nonfinite)
    oversized_window = source_snapshot({0: [0, 0, 0], 11: [1, 0, 0]})
    with pytest.raises(ValueError, match="MOTION_IMPORT_WINDOW_BUDGET"):
        BaselineMotionIndex(oversized_window)


def test_overflow_is_missing_not_nonfinite_public_json() -> None:
    index = BaselineMotionIndex(source_snapshot({0: [1e308, 0, 0], 0.2: [-1e308, 0, 0]}))
    result = index.reconstruct(["CAM_A"], 0, 0.2)
    gap = result["tracks"][0]["gaps"][0]
    assert gap["reason"] == "NUMERICAL_FAILURE"
    assert gap["implied_speed_m_s"] is None
    assert result["tracks"][0]["velocities"] == []
    json.dumps(result, allow_nan=False)


def test_poison_extra_fields_do_not_change_motion_or_leak_private_data() -> None:
    snapshot = source_snapshot({0: [0, 0, 0], 0.4: [0.4, 0, 0]}, times=(0, 0.2, 0.4))
    original = BaselineMotionIndex(snapshot).reconstruct(["CAM_A"], 0, 0.4)
    dirty = copy.deepcopy(snapshot)
    dirty["ground_truth"] = {"identity": "SECRET", "position": [9, 9, 9]}
    dirty["recipe"] = {"trajectory": "/private/SECRET.blend"}
    dirty["source_binding"]["native_units"] = "NATIVE_BU"
    for field in ("measurements", "projected_measurements", "frames", "local_tracks"):
        for row in dirty[field]:
            row["ground_truth"] = "SECRET"
            row["local_path"] = "/private/SECRET.png"
            row["visibility"] = "SIMULATOR_ANSWER"
    poisoned = BaselineMotionIndex(dirty).reconstruct(["CAM_A"], 0, 0.4)
    assert poisoned == original
    encoded = json.dumps(poisoned, allow_nan=False)
    assert all(token not in encoded for token in
               ("SECRET", "/private/", "ground_truth", "local_path", "SIMULATOR_ANSWER"))


def test_motion_has_no_filesystem_or_image_reads_and_is_deterministic(monkeypatch) -> None:
    def prohibited(*_args, **_kwargs):
        raise AssertionError("motion read a file or image")

    monkeypatch.setattr(Path, "read_bytes", prohibited)
    index = BaselineMotionIndex(source_snapshot({0: [0, 0, 0], 0.2: [0.2, 0, 0]}))

    class NoScan(UserDict):
        def __iter__(self):
            raise AssertionError("scanned global track index")

        def values(self):
            raise AssertionError("scanned global track index")

    index._tracks = NoScan(index._tracks)
    index._camera_tracks = NoScan(index._camera_tracks)
    a = index.reconstruct(["CAM_A"], 0, 0.2)
    b = index.reconstruct(["CAM_A"], 0, 0.2)
    assert a == b
    assert a["retrieval"]["global_scan"] is False
    assert a["retrieval"]["frames_read"] == a["retrieval"]["bytes_read"] == 0


def test_real_rgb_snapshot_compatibility_and_output_is_detached(tmp_path: Path) -> None:
    source = BaselineFrameIndex(rgb_inputs(tmp_path)).snapshot()
    index = BaselineMotionIndex(source)
    result = index.reconstruct(["CAM_A", "CAM_B"], 0, 0.8)
    assert result["summary"]["projected_samples"] == 10
    assert result["summary"]["velocity_samples"] == 8
    assert result["summary"]["tracks"] == 2
    untouched = copy.deepcopy(result)
    result["tracks"][0]["samples"][0]["world_position"][0] = 999
    assert index.reconstruct(["CAM_B", "CAM_A"], 0, 0.8) == untouched
    assert source["measurements"][0]["contact_pixel"] != [999, 999]


def test_sites_runs_and_cameras_do_not_share_motion_event_identity() -> None:
    first = source_snapshot({0: [0, 0, 0], 0.2: [0.2, 0, 0]}, site="office")
    second = source_snapshot({0: [0, 0, 0], 0.2: [0.2, 0, 0]}, site="auditorium")
    a = BaselineMotionIndex(first).reconstruct(["CAM_A"], 0, 0.2)
    b = BaselineMotionIndex(second).reconstruct(["CAM_A"], 0, 0.2)
    assert a["tracks"][0]["events"][0]["event_ref"] != b["tracks"][0]["events"][0]["event_ref"]
    changed_run = copy.deepcopy(first)
    changed_run["source_binding"]["run_id"] = "different-run"
    c = BaselineMotionIndex(changed_run).reconstruct(["CAM_A"], 0, 0.2)
    assert a["reconstruction_sha256"] != c["reconstruction_sha256"]
    assert a["tracks"][0]["events"][0]["event_ref"] != c["tracks"][0]["events"][0]["event_ref"]
