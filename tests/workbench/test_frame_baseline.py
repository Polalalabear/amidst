"""Real RGB components feed bounded, deterministic frame retrieval without truth."""

from __future__ import annotations

import copy
import hashlib
import json
from collections import UserDict
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw

from amidst.engineering.registry import content_hash, opaque_ref
from amidst.workbench.frame_baseline import BaselineFrameIndex


def rgb_inputs(root: Path, *, site: str = "fixture-site", blank: bool = False) -> dict[str, Any]:
    """Independent PNG fixture: geometry/calibration configured, pixels actually measured."""
    root.mkdir(parents=True, exist_ok=True)
    cameras = []
    frames = []
    for camera_id in ("CAM_A", "CAM_B"):
        cameras.append({
            "camera_id": camera_id, "camera_ref": opaque_ref("camera", site, camera_id),
            "calibration": {
                "camera_id": camera_id,
                "camera_to_world": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 3], [0, 0, 0, 1]],
                "fx": 64, "fy": 64, "cx": 32, "cy": 32, "width": 64, "height": 64,
                "clip_start": 0.1, "clip_end": 100,
                "convention": "BLENDER_NEG_Z_UP_Y", "pixel_origin": "TOP_LEFT_CONTINUOUS",
                "meters_per_unit": 1,
            },
        })
        for number in range(5):
            image = Image.new("RGB", (64, 64), (0, 0, 0))
            if not blank:
                x = 4 + number * 10
                ImageDraw.Draw(image).rectangle((x, 26, x + 7, 49), fill=(255, 90, 0))
            path = root / f"{camera_id}-{number}.png"
            image.save(path)
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            frames.append({
                "frame_ref": opaque_ref("frame", site, camera_id, str(number), digest),
                "camera_id": camera_id, "timestamp": number / 5,
                "width": 64, "height": 64, "sha256": digest,
                "byte_count": len(raw), "local_path": path,
            })
    return {
        "source_binding": {
            "source_sha256": "1" * 64, "dataset_sha256": content_hash(site),
            "site_id": site, "run_id": "baseline-fixture-v1", "clock_id": "configured-seconds",
            "scale_sha256": "2" * 64,
        },
        "cameras": cameras, "frames": frames,
        "floor_plane": {"point": [0, 0, 0], "normal": [0, 0, 1],
                        "source_sha256": "1" * 64, "authority": "APPROVED"},
    }


def test_actual_rgb_measurements_projection_and_camera_diversity(tmp_path: Path) -> None:
    index = BaselineFrameIndex(rgb_inputs(tmp_path))
    result = index.query(["CAM_B", "CAM_A"], 0, 0.8, 0.4, 3)
    assert result["status"] == "READY"
    assert [(row["camera_id"], row["timestamp"]) for row in result["items"]] == [
        ("CAM_A", 0.4), ("CAM_B", 0.4), ("CAM_A", 0.2)]
    first = result["items"][0]
    assert first["bbox_xyxy"] == [24, 26, 32, 50]
    assert first["contact_pixel"] == [27.5, 49]
    assert first["world_position"] == pytest.approx([-0.2109375, -0.796875, 0])
    assert first["projection_status"] == "PROJECTED"
    assert first["selection_reason"] == "FIRST_BEST_PER_CAMERA"
    assert result["items"][2]["selection_reason"] == "REMAINING_SCOPED_RANK"
    assert result["behavior_verdict"] == "UNKNOWN"
    assert result["ranking"]["score_is_probability"] is False
    assert result["agent_used"] is False
    assert index.telemetry["pixel_measurements"] == 10
    assert index.telemetry["projected_measurements"] == 10
    assert index.telemetry["local_tracks"] == 2
    assert len(index.observations) == len(index.frame_records) == 10
    assert result["retrieval"] == {
        "camera_lookups": 2, "records_read": 10, "eligible_frames": 10,
        "returned_frames": 3, "omitted_frames": 7, "frames_read": 0, "bytes_read": 0,
        "global_scan": False, "import_built_index": True,
    }


class NoScan(UserDict[str, Any]):
    def __iter__(self):
        raise AssertionError("query scanned global catalog")

    def values(self):
        raise AssertionError("query scanned global catalog")

    def items(self):
        raise AssertionError("query scanned global catalog")


def test_query_only_camera_time_features_and_no_runtime_pixel_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = BaselineFrameIndex(rgb_inputs(tmp_path))
    index._records = NoScan(index._records)
    index._buckets = NoScan(index._buckets)
    index._times = NoScan(index._times)

    def forbidden_read(*_args, **_kwargs):
        raise AssertionError("query opened a file")

    monkeypatch.setattr(Path, "read_bytes", forbidden_read)
    first = index.query(["CAM_A"], 0.2, 0.4, 0.4, 3, "running")
    second = index.query(["CAM_A"], 0.2, 0.4, 0.4, 3, "running")
    assert first == second
    assert first["retrieval"]["records_read"] == 2
    assert first["retrieval"]["returned_frames"] == 2
    assert first["selection"]["behavior_intent"] == "running"
    assert index.frames(["CAM_A"], 0.4)["frames"][0]["status"] == "EXACT"
    assert index.get_frame(first["items"][0]["frame_ref"])["timestamp"] == 0.4


def test_truth_recipe_and_private_extra_fields_cannot_affect_features_or_output(
    tmp_path: Path,
) -> None:
    inputs = rgb_inputs(tmp_path)
    clean = BaselineFrameIndex(inputs)
    contaminated = copy.deepcopy(inputs)
    contaminated["ground_truth"] = {"position": [99, 99, 99], "identity": "secret"}
    contaminated["trajectory"] = {"private": "/private/secret.blend", "behavior": "running"}
    contaminated["source_binding"]["private_locator"] = "/private/secret.blend"
    for row in contaminated["frames"]:
        row["world_position"] = [99, 99, 99]
        row["visibility"] = "OCCLUDED"
        row["ground_truth"] = "secret"
    dirty = BaselineFrameIndex(contaminated)
    assert clean.source_features == dirty.source_features
    result = dirty.query(["CAM_A", "CAM_B"], 0, 0.8, 0.4)
    assert result == clean.query(["CAM_A", "CAM_B"], 0, 0.8, 0.4)
    for public in [result, dirty.snapshot(), dirty.observations, dirty.frame_records]:
        text = json.dumps(public)
        assert "local_path" not in text
        assert "/private/" not in text
        assert str(tmp_path) not in text
        assert "ground_truth" not in text
        assert "secret" not in text


def test_site_split_same_camera_names_never_mix_frame_refs(tmp_path: Path) -> None:
    first = BaselineFrameIndex(rgb_inputs(tmp_path / "first", site="office"))
    second = BaselineFrameIndex(rgb_inputs(tmp_path / "second", site="auditorium"))
    a = first.query(["CAM_A"], 0, 0.8, 0.4)
    b = second.query(["CAM_A"], 0, 0.8, 0.4)
    assert a["scope"]["site_id"] == "office"
    assert b["scope"]["site_id"] == "auditorium"
    assert {r["frame_ref"] for r in a["items"]}.isdisjoint(r["frame_ref"] for r in b["items"])
    with pytest.raises(ValueError, match="FRAME_SCOPE_DENIED"):
        second.get_frame(a["items"][0]["frame_ref"])


@pytest.mark.parametrize("updates", [
    {"camera_ids": []}, {"camera_ids": ["UNKNOWN"]},
    {"camera_ids": ["CAM_A", "CAM_A"]}, {"start": -1},
    {"end": 11}, {"start": 0.5, "end": 0.2}, {"target_timestamp": 2},
    {"target_timestamp": float("nan")}, {"start": float("inf")}, {"end": True},
    {"top_k": 0}, {"top_k": 6}, {"top_k": True}, {"behavior_intent": "confirmed_walking"},
])
def test_finite_scope_and_budget_negative_checks(tmp_path: Path, updates: dict[str, Any]) -> None:
    index = BaselineFrameIndex(rgb_inputs(tmp_path))
    request = {"camera_ids": ["CAM_A"], "start": 0, "end": 0.8,
               "target_timestamp": 0.4, "top_k": 3}
    with pytest.raises(ValueError):
        index.query(**(request | updates))


def test_no_measurement_or_empty_window_returns_no_result_and_missing_frames(
    tmp_path: Path,
) -> None:
    blank = BaselineFrameIndex(rgb_inputs(tmp_path / "blank", blank=True))
    assert blank.query(["CAM_A"], 0, 0.8, 0.4)["status"] == "NO_RESULT"
    assert blank.query(["CAM_A"], 0, 0.8, 0.4)["items"] == []
    assert blank.telemetry["pixel_measurements"] == 0
    measured = BaselineFrameIndex(rgb_inputs(tmp_path / "measured"))
    empty = measured.query(["CAM_A"], 2, 3, 2.5)
    assert empty["status"] == "NO_RESULT"
    assert empty["retrieval"]["records_read"] == 0
    assert measured.frames(["CAM_A"], 2)["frames"][0]["status"] == "MISSING"


def test_pixel_hash_failure_and_missing_image_are_explicit_no_result(tmp_path: Path) -> None:
    inputs = rgb_inputs(tmp_path)
    inputs["frames"][0]["sha256"] = "f" * 64
    inputs["frames"][1]["local_path"].unlink()
    index = BaselineFrameIndex(inputs)
    assert index.frame_records[0]["frame_status"] == "HASH_MISMATCH"
    assert index.frame_records[1]["frame_status"] == "MISSING_IMAGE"
    result = index.query(["CAM_A"], 0, 0.2, 0.1)
    assert result["status"] == "NO_RESULT"
    assert index.telemetry["complete"] is False


def test_missing_projection_keeps_real_pixel_evidence_without_fabricated_world(
    tmp_path: Path,
) -> None:
    inputs = rgb_inputs(tmp_path)
    for row in inputs["cameras"]:
        row["calibration"]["clip_end"] = 0.2
    index = BaselineFrameIndex(inputs)
    result = index.query(["CAM_A"], 0, 0.8, 0.4)
    assert result["status"] == "READY"
    assert all(row["projection_status"] == "PROJECTION_MISSING" for row in result["items"])
    assert all(row["projection_reason"] == "FAR_CLIPPED" for row in result["items"])
    assert all(row["world_position"] is None for row in result["items"])
    assert all(row["bbox_xyxy"] for row in result["items"])


def test_import_rejects_source_camera_time_and_frame_scope_mismatches(tmp_path: Path) -> None:
    inputs = rgb_inputs(tmp_path)
    wrong_source = copy.deepcopy(inputs)
    wrong_source["floor_plane"]["source_sha256"] = "9" * 64
    with pytest.raises(ValueError, match="FLOOR_SOURCE_MISMATCH"):
        BaselineFrameIndex(wrong_source)
    duplicated = copy.deepcopy(inputs)
    duplicated["frames"].append(duplicated["frames"][0])
    with pytest.raises(ValueError, match="FRAME_IMPORT_DUPLICATE"):
        BaselineFrameIndex(duplicated)
    unknown = copy.deepcopy(inputs)
    unknown["frames"][0]["camera_id"] = "OTHER"
    with pytest.raises(ValueError, match="FRAME_CAMERA_MISMATCH"):
        BaselineFrameIndex(unknown)


def test_safe_outputs_are_detached_from_internal_index(tmp_path: Path) -> None:
    index = BaselineFrameIndex(rgb_inputs(tmp_path))
    first = index.query(["CAM_A"], 0, 0.8, 0.4)
    first["items"][0]["bbox_xyxy"][0] = 999
    observations = index.observations
    observations[0]["world_position"][0] = 999
    frame = index.get_frame(first["items"][0]["frame_ref"])
    frame["contact_pixel"][0] = 999
    second = index.query(["CAM_A"], 0, 0.8, 0.4)
    assert second["items"][0]["bbox_xyxy"][0] == 24
    assert all(row["world_position"][0] != 999 for row in index.observations)
