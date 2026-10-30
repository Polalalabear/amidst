"""Integrity and semantic checks for the standalone A/B audit extractor."""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "ab_gap_audit", Path(__file__).resolve().parents[2] / "scripts/audit_q1q5_ab_gap.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


@pytest.fixture
def frozen(tmp_path):
    bundle = tmp_path / "bundle"
    pins = {"files": {}, "scene_id": "s", "run_id": "r", "clock_id": "c"}
    scope = {"scene_id": "s", "run_id": "r", "clock_id": "c"}
    manifest, records = [], []
    for camera in ["A", "B"]:
        for frame in range(160):
            raw = f"hash-only RGB fixture {camera}:{frame}".encode()
            ref = f"media/{camera}-{frame:04d}.png"
            path = bundle / "dynamic-rgb-v2/safe" / ref
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            rgb_hash = audit.digest(raw)
            manifest.append(
                {
                    "camera_id": camera,
                    "frame_index": frame,
                    "timestamp_s": frame / 20,
                    "rgb_ref": ref,
                    "file_sha256": rgb_hash,
                }
            )
            detections = []
            if (camera, frame) in {("A", 24), ("A", 60), ("B", 103)}:
                detections = [
                    {
                        "class_label": "person",
                        "observation_id": f"{camera}:{frame}",
                        "score": 0.323 if frame == 60 else 0.52,
                        "bbox_xyxy_px": [1, 2, 3, 4],
                    }
                ]
            records.append(
                {
                    "camera_id": camera,
                    "frame_index": frame,
                    "timestamp_us": frame * 50_000,
                    "frame_ref": f"r:{camera}:{frame}",
                    "rgb_file_sha256": rgb_hash,
                    "frame_state": "INFERRED",
                    "detections": detections,
                }
            )

    def write(key, value):
        raw = (
            "".join(json.dumps(x) + "\n" for x in value).encode()
            if key in {"records", "links", "decisions"}
            else json.dumps(value).encode()
        )
        path = bundle / audit.FILES[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        pins["files"][audit.FILES[key]] = audit.digest(raw)
        return audit.digest(raw)

    static_hash = write(
        "static",
        {
            "scene_id": "s",
            "source_blend_file_sha256": "0" * 64,
            "cameras": {},
            "image_size_px": [960, 540],
        },
    )
    rgb_hash = write("rgb", {**scope, "static_file_sha256": static_hash, "records": manifest})
    records_hash = write("records", records)
    write(
        "index",
        {
            **scope,
            "rgb_index_sha256": rgb_hash,
            "records_file_sha256": records_hash,
            "detector": {"index_score_floor": 0.3},
        },
    )
    write(
        "response",
        {
            "decision_source": "RULE_ONLY",
            "identity_verdict": "UNCONFIRMED",
            "resolved_scope": {"run_ids": ["r"]},
            "timeline": [
                {"kind": "GAP", "camera_shown": "A", "range_us": [0, 1_000_000]},
                {
                    "kind": "ON_CAMERA",
                    "camera_id": "A",
                    "observation_ids": ["A:24"],
                    "range_us": [1_000_000, 1_250_000],
                },
                {"kind": "GAP", "camera_shown": "A", "range_us": [1_250_000, 5_150_000]},
                {
                    "kind": "ON_CAMERA",
                    "camera_id": "B",
                    "observation_ids": ["B:103"],
                    "range_us": [5_150_000, 8_000_000],
                },
            ],
        },
    )
    write(
        "parameters",
        {
            "parameters": [
                {"name": "query_min_score", "value": 0.5},
                {"name": "link_min_score", "value": 0.4},
            ]
        },
    )
    for key in ["camera_graph", "region_graph", "switch_evidence", "switch_snapshot"]:
        write(key, {})
    write("links", [])
    write("decisions", [])
    return bundle, pins, write


def test_detection_gap_does_not_become_visual_blindness(frozen):
    bundle, pins, _ = frozen
    report, rows = audit.extract(bundle, pins)
    assert report["sampling"]["rgb_verified"] == len(rows) == 320
    gap = report["detection_gap"]
    assert gap["zero_stored_person_sample_interval_us"] == [3_050_000, 5_150_000]
    assert (gap["time_samples"], gap["camera_frames"]) == (42, 84)
    row = gap["last_a_stored_person"]
    assert (row["person_count_ge_0_3"], row["person_count_ge_0_4"], row["person_count_ge_0_5"]) == (
        1,
        0,
        0,
    )
    assert row["controller_kind"] == "GAP" and row["supported_observations"] == 0
    assert report["visual_blind_interval_us"] is report["physical_blind_interval_us"] is None
    assert all(r["visual_presence"] == "UNREVIEWED" for r in rows)


def test_tampered_rgb_rejected(frozen):
    bundle, pins, _ = frozen
    (bundle / "dynamic-rgb-v2/safe/media/A-0061.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA256_MISMATCH"):
        audit.extract(bundle, pins)


def test_record_cannot_be_rebound_to_another_rgb(frozen):
    bundle, pins, write = frozen
    records = [json.loads(x) for x in (bundle / audit.FILES["records"]).read_text().splitlines()]
    records[61]["rgb_file_sha256"] = "0" * 64
    new_hash = write("records", records)
    index = json.loads((bundle / audit.FILES["index"]).read_text())
    index["records_file_sha256"] = new_hash
    write("index", index)
    with pytest.raises(ValueError, match="INDEX_RGB_PIN_MISMATCH"):
        audit.extract(bundle, pins)


def test_duplicate_frame_rejected_even_with_updated_file_pins(frozen):
    bundle, pins, write = frozen
    records = [json.loads(x) for x in (bundle / audit.FILES["records"]).read_text().splitlines()]
    records[61] = records[60]
    new_hash = write("records", records)
    index = json.loads((bundle / audit.FILES["index"]).read_text())
    index["records_file_sha256"] = new_hash
    write("index", index)
    with pytest.raises(ValueError, match="DUPLICATE_INDEX_FRAME"):
        audit.extract(bundle, pins)


def test_unpinned_input_and_path_escape_rejected(frozen):
    bundle, pins, _ = frozen
    pins["files"]["unapproved.json"] = "0" * 64
    with pytest.raises(ValueError, match="UNEXPECTED_INPUT_SET"):
        audit.extract(bundle, pins)
    with pytest.raises(ValueError, match="PATH_OUTSIDE_SAFE_ROOT"):
        audit.within(bundle, "../outside")


def test_gapped_controller_timeline_rejected(frozen):
    bundle, pins, write = frozen
    response = json.loads((bundle / audit.FILES["response"]).read_text())
    response["timeline"][2]["range_us"][0] += 50_000
    write("response", response)
    with pytest.raises(ValueError, match="TIMELINE_GRID_OR_COVERAGE_MISMATCH"):
        audit.extract(bundle, pins)
