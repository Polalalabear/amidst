from __future__ import annotations

import json
from pathlib import Path

import pytest

from amidst.evaluation.rq1_ground_interval import (
    FrozenPredictionError,
    FrozenPredictions,
    GroundTruthError,
    evaluate_rq1,
    gt_contact_at,
    load_frozen_predictions,
    load_ground_truth,
    point_segment_distance,
    sha256_file,
)

SRC = "a" * 64


def _obs(ref: str, t: float, near: list[float], far: list[float]) -> dict:
    return {
        "observation_ref": ref,
        "camera_id": "CAM",
        "basis": "FOOT_RAY_PIXEL_BAND",
        "timestamp_s": t,
        "status": "READY",
        "estimate_kind": "SEGMENT",
        "segment": {"near_m": near, "far_m": far, "length_m": 1.0},
    }


def _write(tmp: Path) -> tuple[Path, Path]:
    preds = {
        "run_id": "r",
        "source_sha256": SRC,
        "gt_read": False,
        "observations": [
            _obs("o1", 0.0, [0.0, 0.0, 1.0], [1.0, 0.0, 1.0]),
            _obs("o2", 0.5, [0.0, 0.0, 1.0], [1.0, 0.0, 1.0]),
        ],
    }
    gt = {
        "source_asset_sha256": SRC,
        "samples": [
            {"timestamp": 0.0, "foot_position": [10.0, 10.0, 40.0]},
            {"timestamp": 1.0, "foot_position": [30.0, 10.0, 40.0]},
        ],
    }
    p, g = tmp / "p.json", tmp / "g.json"
    p.write_text(json.dumps(preds))
    g.write_text(json.dumps(gt))
    return p, g


def test_point_segment_distance_geometry() -> None:
    assert point_segment_distance((0.5, 1.0), (0, 0), (1, 0)) == (1.0, 0.5)
    d, t = point_segment_distance((-1.0, 0.0), (0, 0), (1, 0))
    assert (d, t) == (1.0, 0.0)
    d, t = point_segment_distance((3.0, 4.0), (0, 0), (1, 0))
    assert t == 1.0 and d == pytest.approx((4 + 16) ** 0.5)
    assert point_segment_distance((0.0, 2.0), (0, 0), (0, 0)) == (2.0, 0.0)


def test_gt_alignment_exact_interpolated_and_out_of_range(tmp_path: Path) -> None:
    p, g = _write(tmp_path)
    preds = load_frozen_predictions(p, sha256_file(p))
    track = load_ground_truth(g, sha256_file(g), preds, m_per_unit=0.1)
    assert gt_contact_at(track, 0.0) == ((1.0, 1.0, 4.0), "EXACT")
    xyz, mode = gt_contact_at(track, 0.5)
    assert mode == "LINEAR_INTERPOLATION" and xyz[0] == pytest.approx(2.0)
    with pytest.raises(GroundTruthError):
        gt_contact_at(track, 1.5)


def test_evaluate_coverage_and_scale(tmp_path: Path) -> None:
    p, g = _write(tmp_path)
    preds = load_frozen_predictions(p, sha256_file(p))
    track = load_ground_truth(g, sha256_file(g), preds, m_per_unit=0.1)
    res = evaluate_rq1(preds, track, {"zero": 0.0, "radius": 0.25})
    o1, o2 = res["per_observation"]
    assert o1["distance_to_segment_m"] == pytest.approx(1.0)  # GT (1,1) vs segment on y=0
    assert o1["position_on_segment"] == 1.0
    assert not o1["covered_zero"] and not o1["covered_radius"]
    assert o2["time_alignment"] == "LINEAR_INTERPOLATION"
    assert res["summary"]["ALL"]["coverage_radius"]["covered"] == 0


def test_gt_refused_without_verified_predictions(tmp_path: Path) -> None:
    p, g = _write(tmp_path)
    with pytest.raises(FrozenPredictionError):
        load_frozen_predictions(p, "0" * 64)  # wrong SHA: no verified object exists
    with pytest.raises(FrozenPredictionError):
        FrozenPredictions("x", "r", SRC, (), object())  # cannot forge verification
    with pytest.raises(GroundTruthError):
        load_ground_truth(g, sha256_file(g), None, m_per_unit=0.1)  # type: ignore[arg-type]


def test_gt_sha_and_source_checks(tmp_path: Path) -> None:
    p, g = _write(tmp_path)
    preds = load_frozen_predictions(p, sha256_file(p))
    with pytest.raises(GroundTruthError):
        load_ground_truth(g, "0" * 64, preds, m_per_unit=0.1)
    data = json.loads(g.read_text())
    data["source_asset_sha256"] = "b" * 64
    g.write_text(json.dumps(data))
    with pytest.raises(GroundTruthError):
        load_ground_truth(g, sha256_file(g), preds, m_per_unit=0.1)


def test_determinism(tmp_path: Path) -> None:
    p, g = _write(tmp_path)
    preds = load_frozen_predictions(p, sha256_file(p))
    track = load_ground_truth(g, sha256_file(g), preds, m_per_unit=0.1)
    a = json.dumps(evaluate_rq1(preds, track, {"z": 0.0}), sort_keys=True)
    b = json.dumps(evaluate_rq1(preds, track, {"z": 0.0}), sort_keys=True)
    assert a == b
