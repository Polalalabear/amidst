"""Focused unit tests for AO-L zero-latency rescoring and Unified Analysis Generator."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "configs" / "evaluation" / "unified_analysis_schema_v1.json"


def _load_script(name: str, rel_path: str):
    path = REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


RESCORE = _load_script("rescore_aol_zero_latency", "scripts/evaluation/rescore_aol_zero_latency.py")
UNIFIED = _load_script("generate_unified_analysis", "scripts/evaluation/generate_unified_analysis.py")


def test_aol_zero_latency_rescoring_synthetic():
    """Verify an EXPIRED AO-L call is recovered at ask_tick and is_approximation is True."""
    target_box = [20.0, 60.0, 50.0, 130.0]
    dets_by_tick = {t: {"CAM_EXT_CAR": [{"bbox": target_box, "score": 0.9}]} for t in range(10)}

    # Actual AO-L: asked at tick 0, EXPIRED at tick 5 -> LOST on all 10 ticks
    aol_doc = {
        "case_id": "SYNTH-1",
        "arm": "AOL",
        "rows": [
            {
                "tick": t,
                "tracking": {"state": "LOST", "active_cam": None, "est_xy": None, "lost_ticks": 1, "box": None},
                "ranking": [],
            }
            for t in range(10)
        ],
        "calls": [
            {
                "ask_tick": 0,
                "tick": 5,
                "answer": "SELECT",
                "camera_id": "CAM_EXT_CAR",
                "detection_id": "D1",
                "box_xyxy": None,
                "next_camera_ranking": ["CAM_EXT_CAR"],
                "applied": False,
                "fallback_reason": "EXPIRED",
                "latency_ms": 1000,
                "request": {
                    "candidate_list": [
                        {"detection_id": "D1", "camera_id": "CAM_EXT_CAR", "box": target_box, "score": 0.9}
                    ]
                },
            }
        ],
    }

    zl_rows, stats = RESCORE.replay_zero_latency_rows(aol_doc, dets_by_tick, RESCORE._FallbackProjector())
    assert stats["total_calls"] == 1
    assert stats["actual_expired_calls"] == 1
    assert stats["zero_latency_applied_calls"] == 1
    assert stats["recovered_from_expired"] == 1

    # Scoring side only: GT a-log
    a_log = {
        "actor_id": "T1",
        "ticks": [
            {
                "tick": t,
                "actors": [
                    {
                        "id": "T1",
                        "present": True,
                        "xy": [1.0, 1.0],
                        "gt_visible": ["CAM_EXT_CAR"],
                        "gt_boxes": {"CAM_EXT_CAR": [18.0, 58.0, 52.0, 132.0]},
                    }
                ],
            }
            for t in range(10)
        ],
    }
    case = {
        "case_id": "SYNTH-1",
        "family": "A",
        "decision_points": [{"tick": 0, "timestamp_us": 0, "type": "START"}],
    }
    scored = RESCORE.score_zero_latency_case(case, a_log, aol_doc, zl_rows)
    assert scored["actual_aol"]["follow_rate"] == 0.0
    assert scored["zero_latency_aol"]["follow_rate"] == 1.0
    assert scored["actual_aol"]["dp_correct"] == 0
    assert scored["zero_latency_aol"]["dp_correct"] == 1

    summary = RESCORE._aggregate_cases([scored], stats)
    assert summary["delta_follow_rate"] == 1.0
    assert summary["calls"]["actual_expired_rate"] == 1.0


def test_unified_analysis_schema_and_source_preservation(tmp_path: Path):
    # Create synthetic frozen E5 report + AO-L zero-latency rescore JSON + E7 analysis JSON
    e5_path = tmp_path / "e5_report.json"
    e5_doc = {
        "schema_version": "e5.report.v1",
        "identity": "UNCONFIRMED",
        "cases": ["E3-A1", "E3-A2"],
        "per_arm": {
            "B1": {
                "segments": ["E3-A1", "E3-A2"],
                "wrong_person_s": 114.0,
                "follow_rate": 0.759,
                "lost_s": 85.0,
                "false_lock_s": 109.4,
                "dp_correct": 28,
                "dp_total": 68,
                "latency_ms_p50": None,
                "latency_ms_p95": None,
            },
            "AO": {
                "segments": ["E3-A1", "E3-A2"],
                "wrong_person_s": 243.07,
                "follow_rate": 0.651,
                "lost_s": 44.67,
                "false_lock_s": 174.87,
                "dp_correct": 15,
                "dp_total": 68,
                "latency_ms_p50": 4557,
                "latency_ms_p95": 11052,
                "e5_calls": {"calls": 1848, "expired": 0, "format_return_rate": 0.0},
            },
            "AOL": {
                "segments": ["E3-A1", "E3-A2"],
                "wrong_person_s": 110.2,
                "follow_rate": 0.248,
                "lost_s": 510.6,
                "false_lock_s": 31.8,
                "dp_correct": 6,
                "dp_total": 68,
                "latency_ms_p50": 4784,
                "latency_ms_p95": 10524,
                "e5_calls": {"calls": 186, "expired": 98, "format_return_rate": 0.0},
            },
        },
    }
    e5_path.write_text(json.dumps(e5_doc), encoding="utf-8")

    zl_path = tmp_path / "aol_zl.json"
    zl_doc = {
        "schema_version": "aol_zero_latency_rescore_v1",
        "identity_status": "UNCONFIRMED",
        "is_approximation": True,
        "approximation_note": RESCORE.APPROXIMATION_NOTE,
        "summary": {
            "n_segments": 16,
            "actual_aol_follow_rate": 0.248,
            "zero_latency_aol_follow_rate": 0.58,
            "delta_follow_rate": 0.332,
            "zero_latency_aol_wrong_person_s": 120.4,
            "zero_latency_aol_false_lock_s": 45.2,
            "zero_latency_aol_dp_accuracy": 0.3529,
            "dp_total": 68,
            "calls": {"total_calls": 186, "actual_expired_calls": 98, "actual_expired_rate": 0.5269},
        },
    }
    zl_path.write_text(json.dumps(zl_doc), encoding="utf-8")

    out_dir = tmp_path / "out"
    rc = UNIFIED.main(
        [
            "--e5-report",
            str(e5_path),
            "--aol-zero-latency",
            str(zl_path),
            "--out-dir",
            str(out_dir),
            "--platform",
            "Windows-smoke-only",
        ]
    )
    assert rc == 0
    assert (out_dir / "unified_analysis.json").is_file()
    assert (out_dir / "unified_analysis.md").is_file()

    doc = json.loads((out_dir / "unified_analysis.json").read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert UNIFIED.validate_against_schema(doc, schema) == []

    # Verify frozen E5 numbers preserved verbatim & identity UNCONFIRMED
    assert doc["identity_status"] == "UNCONFIRMED"
    assert doc["latency_breakdown"]["aol_zero_latency_approx"]["is_approximation"] is True
    by_party = {e["party_id"]: e for e in doc["five_way_comparison"]["entries"]}
    assert by_party["b1_rule"]["metrics"]["wrong_target_s"] == 114.0
    assert by_party["b1_rule"]["metrics"]["correct_rate"] == 0.759
    assert by_party["api_ao"]["metrics"]["wrong_target_s"] == 243.07
    assert by_party["api_aol"]["metrics"]["correct_rate"] == 0.248
    assert by_party["api_aol_zero_latency"]["metrics"]["correct_rate"] == 0.58
    assert doc["e6_verdict"]["status"] == "PENDING_PR726_AND_RUN"

    # Negative schema check: identity_status != UNCONFIRMED must fail validation
    bad = json.loads(json.dumps(doc))
    bad["identity_status"] = "CONFIRMED"
    assert UNIFIED.validate_against_schema(bad, schema)
