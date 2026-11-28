"""Focused unit tests for AO-L zero-latency rescoring (including replay calibration & UNCERTAIN split) and Unified Analysis Generator."""
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
    """Verify EXPIRED recovery, UNCERTAIN no-op split, replay calibration, and is_approximation=True."""
    target_box = [20.0, 60.0, 50.0, 130.0]
    dets_by_tick = {t: {"CAM_EXT_CAR": [{"bbox": target_box, "score": 0.9}]} for t in range(10)}

    # Actual AO-L: call 1 asked at tick 0, EXPIRED at tick 5 -> LOST on all 10 ticks
    # Call 2 asked at tick 2, UNCERTAIN (no-op), applied=True at applied_tick=3
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
                "applied_tick": 5,
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
            },
            {
                "ask_tick": 2,
                "tick": 3,
                "applied_tick": 3,
                "answer": "UNCERTAIN",
                "camera_id": None,
                "detection_id": None,
                "box_xyxy": None,
                "next_camera_ranking": [],
                "applied": True,
                "fallback_reason": None,
                "latency_ms": 200,
                "request": {"candidate_list": []},
            },
        ],
    }

    zl_rows, stats = RESCORE.replay_zero_latency_rows(aol_doc, dets_by_tick, RESCORE._FallbackProjector())
    assert stats["total_calls"] == 2
    assert stats["actual_expired_calls"] == 1
    assert stats["zero_latency_replayed_calls"] == 2
    assert stats["zero_latency_actionable_calls"] == 1
    assert stats["zero_latency_uncertain_noop_calls"] == 1
    assert stats["zero_latency_applied_calls"] == 1
    assert stats["recovered_from_expired"] == 1

    cal_rows, cal_stats = RESCORE.replay_applied_tick_calibration(aol_doc, dets_by_tick, RESCORE._FallbackProjector())
    assert cal_stats["applied_calls_input"] == 1
    assert cal_stats["applied_calls_actionable"] == 0
    assert cal_stats["applied_calls_uncertain_noop"] == 1

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
    scored = RESCORE.score_zero_latency_case(case, a_log, aol_doc, zl_rows, calibration_rows=cal_rows)
    assert scored["actual_aol"]["follow_rate"] == 0.0
    assert scored["replay_calibration_aol"]["follow_rate"] == 0.0
    assert scored["zero_latency_aol"]["follow_rate"] == 1.0
    assert scored["actual_aol"]["dp_correct"] == 0
    assert scored["zero_latency_aol"]["dp_correct"] == 1

    summary = RESCORE._aggregate_cases([scored], stats, cal_totals=cal_stats)
    assert summary["delta_follow_rate"] == 1.0
    assert summary["calls"]["actual_expired_rate"] == 0.5
    assert summary["replay_calibration"]["recorded_aol_follow_rate"] == 0.0
    assert summary["replay_calibration"]["replayed_applied_tick_follow_rate"] == 0.0
    assert summary["replay_calibration"]["calibration_delta_follow_rate"] == 0.0


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

    # E8 (#780) is optional: absent by default, added (and schema-checked) only with --e8-results
    assert "e8" not in doc and not any(src["source_id"] == "e8_results" for src in doc["sources"])
    e8_path = tmp_path / "unified_e8_section.json"
    e8_path.write_text(json.dumps({"schema": "e8_unified_v1", "conclusion": "INCONCLUSIVE", "accuracy": {}, "first_option_rate": {},
                                   "verdicts": {"H1a": "EXPLORATORY"}, "part2": {}, "early_switch_s": {},
                                   "identity_status": "UNCONFIRMED", "selection": {"selected": None}}), encoding="utf-8")
    out_e8 = tmp_path / "out_e8"
    assert UNIFIED.main(["--e5-report", str(e5_path), "--e8-results", str(e8_path), "--out-dir", str(out_e8), "--no-charts"]) == 0
    doc8 = json.loads((out_e8 / "unified_analysis.json").read_text(encoding="utf-8"))
    assert doc8["e8"]["conclusion"] == "INCONCLUSIVE" and UNIFIED.validate_against_schema(doc8, schema) == []
    assert any(src["source_id"] == "e8_results" and src["status"] == "LOADED" for src in doc8["sources"])
    assert "## E8 Information Ladder" in (out_e8 / "unified_analysis.md").read_text(encoding="utf-8")
    bad8 = json.loads(json.dumps(doc8))
    bad8["e8"]["identity_status"] = "CONFIRMED"
    assert UNIFIED.validate_against_schema(bad8, schema)


def test_run_all_stage1_budget_check_reads_apiguard_usage_jsonl_and_excludes_denied(tmp_path: Path):
    """P2-2: run_all.sh Stage 1 reads real ApiGuard usage.jsonl est_cost_usd, excludes DENIED, and enforces cap."""
    import re
    import subprocess

    script_text = (REPO_ROOT / "scripts" / "experiments" / "run_all.sh").read_text(encoding="utf-8")
    m = re.search(r"BUDGET_CHECK_PY='\n(.*?)\n'", script_text, flags=re.S)
    assert m is not None, "BUDGET_CHECK_PY snippet not found in scripts/experiments/run_all.sh"
    budget_py = m.group(1)

    usage_dir = tmp_path / "api-usage"
    usage_dir.mkdir()
    ledger = usage_dir / "usage.jsonl"

    # Case 1: Under cap (base 38.17 + 12.50 = 50.67 <= 90.00); DENIED row with 100.0 MUST be excluded
    rows_under = [
        {"ts": "2026-11-26T10:00:00Z", "caller": "e6", "model": "gpt-4o-mini", "outcome": "OK", "est_cost_usd": 7.25},
        {"ts": "2026-11-26T10:01:00Z", "caller": "e6", "model": "gpt-4o-mini", "outcome": "DENIED", "est_cost_usd": 100.0},
        {"ts": "2026-11-26T10:02:00Z", "caller": "e6", "model": "gpt-4o-mini", "outcome": "ERROR", "est_cost_usd": 5.25},
    ]
    ledger.write_text("\n".join(json.dumps(r) for r in rows_under) + "\n", encoding="utf-8")

    ok = subprocess.run(
        [sys.executable, "-c", budget_py, "38.17", "90.00", str(usage_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok.returncode == 0, f"Expected pass under cap, got rc={ok.returncode}: {ok.stdout} {ok.stderr}"
    assert "new_ledger=12.5000" in ok.stdout
    assert "total=50.6700" in ok.stdout
    assert "1 DENIED excluded" in ok.stdout

    # Case 2: Over cap (base 38.17 + 55.00 = 93.17 > 90.00) -> non-zero exit with BUDGET_CAP_EXCEEDED
    rows_over = [
        {"ts": "2026-11-26T10:00:00Z", "caller": "e6", "model": "gpt-4o-mini", "outcome": "OK", "est_cost_usd": 55.00},
    ]
    ledger.write_text("\n".join(json.dumps(r) for r in rows_over) + "\n", encoding="utf-8")

    fail = subprocess.run(
        [sys.executable, "-c", budget_py, "38.17", "90.00", str(usage_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert fail.returncode != 0, "Expected non-zero exit when total exceeds cap"
    assert "BUDGET_CAP_EXCEEDED" in (fail.stderr + fail.stdout)


def test_run_all_stage1_strict_mode_fails_closed_on_missing_ledger(tmp_path: Path):
    """--execute passes strict=1: unset dir, missing dir or missing usage.jsonl stop the run; dry-run (strict 0) only warns."""
    import re
    import subprocess

    text = (REPO_ROOT / "scripts" / "experiments" / "run_all.sh").read_text(encoding="utf-8")
    py = re.search(r"BUDGET_CHECK_PY='\n(.*?)\n'", text, flags=re.S).group(1)

    def run(dir_arg, strict):
        return subprocess.run([sys.executable, "-c", py, "38.17", "90.00", dir_arg, strict], capture_output=True, text=True)

    empty = tmp_path / "empty"
    empty.mkdir()
    for arg in ("", str(tmp_path / "nope"), str(empty)):
        bad = run(arg, "1")
        assert bad.returncode != 0 and "LEDGER_REQUIRED" in (bad.stderr + bad.stdout), arg
        warn = run(arg, "0")
        assert warn.returncode == 0 and "WARNING" in warn.stdout, arg
    (empty / "usage.jsonl").write_text("")
    assert run(str(empty), "1").returncode == 0
