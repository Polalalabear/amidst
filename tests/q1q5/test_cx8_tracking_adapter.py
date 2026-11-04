"""SYNTHETIC detection-index rows only; no real RGB, GT or renderer data."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cx8 = load("run_cx8_rule_tracking")


def row(camera, i, ts, score=None, state="SAMPLED"):
    dets = None if score is None else [{"score": score, "observation_id": f"o{camera}{i}"}]
    return {"frame_ref": f"frame:R:{camera}:{i}", "camera_id": camera, "frame_index": i,
            "timestamp_us": ts, "frame_state": state, "detections": dets}


def receipt(rows, floor=0.5, gap=1_000_000):
    return cx8.build_receipt(rows, run_id="R", score_floor=floor, max_gap_us=gap, records_sha256="0" * 64)


def test_handoff_between_cameras_and_unconfirmed_identity():
    rows = [row("C1", 0, 0, 0.9), row("C1", 1, 1_000_000, 0.8), row("C1", 2, 2_000_000, 0.1),
            row("C2", 0, 3_000_000, 0.9), row("C2", 1, 4_000_000, 0.7)]
    r = receipt(rows)
    assert r["mode"] == "RULE_ONLY" and r["identity"] == "UNCONFIRMED"
    assert [(s["camera_id"], s["start_us"], s["end_us"]) for s in r["segments"]] == [
        ("C1", 0, 1_000_000), ("C2", 3_000_000, 4_000_000)]
    (sw,) = [s for s in r["switches"] if s["from_camera"] == "C1"]
    assert sw["to_camera"] == "C2" and sw["decision_us"] == 1_000_000 and sw["gap_us"] == 2_000_000


def test_multiple_returns_on_one_camera_split_by_gap():
    rows = [row("C1", 0, 0, 0.9), row("C1", 1, 5_000_000, 0.9)]
    assert len(receipt(rows)["segments"]) == 2
    assert len(receipt(rows, gap=10_000_000)["segments"]) == 1


def test_unsampled_frames_are_not_evidence():
    r = receipt([row("C1", 0, 0, None, "NOT_SAMPLED"), row("C1", 1, 1, 0.99, "NOT_SAMPLED")])
    assert r["segments"] == [] and r["switches"] == []


def test_deterministic():
    rows = [row("C2", 0, 0, 0.9), row("C1", 0, 10, 0.9)]
    assert json.dumps(receipt(rows), sort_keys=True) == json.dumps(receipt(list(reversed(rows))), sort_keys=True)


def test_disk_guard(monkeypatch):
    monkeypatch.setattr(cx8.shutil, "disk_usage", lambda p: SimpleNamespace(free=8 * 1024 ** 3 - 1))
    with pytest.raises(SystemExit):
        cx8.require_free_space(ROOT)
    monkeypatch.setattr(cx8.shutil, "disk_usage", lambda p: SimpleNamespace(free=8 * 1024 ** 3))
    assert cx8.require_free_space(ROOT) == 8 * 1024 ** 3
    index = load("build_q1q5_detection_index")
    monkeypatch.setattr(index.shutil, "disk_usage", lambda p: SimpleNamespace(free=1))
    with pytest.raises(SystemExit):
        index.require_free_space(ROOT)


def test_cli_rejects_output_inside_repo(tmp_path):
    records = tmp_path / "r.jsonl"
    records.write_text("")
    with pytest.raises(SystemExit):
        cx8.main(["--repo", str(ROOT), "--records", str(records), "--run-id", "R",
                  "--output", str(ROOT / "out.json"), "--score-floor", "0.5", "--max-gap-us", "1"])
