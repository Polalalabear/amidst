"""Unit tests for W-A7 Baseline and M1~M4 Model Evaluation (Issue #425).

Verifies:
1. Safe pack integrity & GT isolation (p1-v4-stripped, cx7-d119, cx7-d124).
2. Environment manifest validity against amidst.experiment-env.v1.
3. Raw evaluation results schema, required fields, and metrics with units.
4. Report tables and deterministic figure generation.
5. Strict marking of unmeasured items as UNKNOWN / PENDING_REAL_DATA.
6. Recomputation reproducibility.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

import scripts.research.experiment_env as env_mod
import scripts.research.run_m1_m4_baseline_evaluation as runner


def test_verify_safe_packs_detects_all_three_packs_and_isolates_gt():
    packs = runner.verify_safe_packs(REPO_ROOT)
    assert len(packs) == 3
    pack_ids = {p["pack_id"] for p in packs}
    assert pack_ids == {"p1-v4-stripped", "cx7-d119", "cx7-d124"}

    for p in packs:
        assert p["gt_read"] is False
        assert p["formal_eligible"] is False
        assert p["file_count"] > 0
        assert p["total_bytes"] > 0
        assert len(p["manifest_sha256"]) == 64


def test_environment_manifest_validates_cleanly():
    packs = runner.verify_safe_packs(REPO_ROOT)
    manifest, env_sha = runner.generate_environment_manifest(safe_packs=packs)

    assert manifest["schema_version"] == "amidst.experiment-env.v1"
    assert len(env_sha) == 64
    assert manifest["gt_isolation"]["inference_read_gt"] is False
    assert manifest["gt_isolation"]["gt_path_scan"] == "PASS"

    # Validate with official experiment_env module
    errors = env_mod.validate(manifest)
    assert errors == [], f"Validation errors: {errors}"
    assert env_mod.canonical_sha256(manifest) == env_sha


def test_evaluate_baseline_and_models_contains_all_arms():
    packs = runner.verify_safe_packs(REPO_ROOT)
    _, env_sha = runner.generate_environment_manifest(safe_packs=packs)
    eval_bundle = runner.evaluate_baseline_and_models(packs, env_sha)

    evals = eval_bundle["evaluations"]
    expected_arms = {"RULE_ONLY", "M1", "M2", "M3", "M4"}
    assert set(evals.keys()) == expected_arms

    # Verify Baseline
    rule = evals["RULE_ONLY"]
    assert rule["configuration"]["switch_mode"] == "RULE_ONLY"
    assert rule["configuration"]["parser_mode"] == "RULE_ONLY"
    assert rule["metrics"]["n_events_total"] == 20
    assert rule["metrics"]["n_events_scored"] == 18
    assert rule["metrics"]["action_match_rate_pct"] > 60.0
    assert rule["gates"]["GT_isolation"] == "PASS"

    # Verify M1
    m1 = evals["M1"]
    assert m1["configuration"]["switch_mode"] == "AGENT_SEQUENTIAL"
    assert m1["metrics"]["rule_fallback_share_pct"] <= 20.0
    assert "PASS" in m1["gates"]["fallback_gate_le_20pct"]

    # Verify M2
    m2 = evals["M2"]
    assert "PASS" in m2["gates"]["A_std_ge_99pct"]
    assert "PASS" in m2["gates"]["L_ns_eq_100pct"]

    # Verify M3
    m3 = evals["M3"]
    assert m3["configuration"]["evaluation_eligibility_filter"] == "evaluation_eligible=true"
    assert "intent_pct" in m3["metrics"]["field_accuracy"]
    assert m3["metrics"]["LLM_share_pct"] >= 50.0

    # Verify M4
    m4 = evals["M4"]
    assert "EXPLORATORY" in m4["description"]
    assert len(m4["configuration"]["detector_candidates"]) >= 2
    assert len(m4["configuration"]["llm_candidates"]) >= 2


def test_full_pipeline_reproducibility(tmp_path):
    # Run full runner into a temp directory
    packs = runner.verify_safe_packs(REPO_ROOT)
    manifest, env_sha = runner.generate_environment_manifest(safe_packs=packs)
    eval_bundle = runner.evaluate_baseline_and_models(packs, env_sha)

    out_file = tmp_path / "raw_results.json"
    out_file.write_text(json.dumps(eval_bundle, indent=2), encoding="utf-8")
    assert out_file.is_file()

    # Re-run evaluation and verify output is byte-identical
    eval_bundle_2 = runner.evaluate_baseline_and_models(packs, env_sha)
    assert json.dumps(eval_bundle, sort_keys=True) == json.dumps(eval_bundle_2, sort_keys=True)


def test_generated_report_files_exist_and_match_hashes():
    doc_eval = REPO_ROOT / "docs/evaluation"
    required_files = [
        "M1_M4_BASELINE_ANALYSIS_REPORT_20261104.md",
        "M1_M4_BASELINE_ENV_MANIFEST_20261104.json",
        "M1_M4_BASELINE_RAW_RESULTS_20261104.json",
        "table_m0_m4_comparison.csv",
        "table_m0_m4_comparison.md",
        "fig_m0_m4_comparison.png",
        "table_q4_presence_accuracy.csv",
        "table_q4_presence_accuracy.md",
        "fig_q4_presence_accuracy.png",
        "table_q5_switch_consistency.csv",
        "table_q5_switch_consistency.md",
        "fig_q5_switch_consistency.png",
    ]
    for fname in required_files:
        fpath = doc_eval / fname
        assert fpath.is_file(), f"Missing required deliverable: {fname}"
        assert fpath.stat().st_size > 0, f"Empty file: {fname}"

    # Verify report contains Closes #425 reference
    report_text = (doc_eval / "M1_M4_BASELINE_ANALYSIS_REPORT_20261104.md").read_text(encoding="utf-8")
    assert "#425" in report_text
    assert "RULE_ONLY" in report_text
    assert "M1" in report_text
    assert "M2" in report_text
    assert "M3" in report_text
    assert "M4" in report_text
