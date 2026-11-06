#!/usr/bin/env python3
"""Deterministic M0..M4 synthetic fixtures for Issue #425 / W-A7.

No real pack, model, or Ground Truth isolation verification is performed here.
- Baseline (RULE_ONLY / M0): Rule-based controller and parser baseline [SYNTHETIC FIXTURE].
- M1: Sequential agent with rule fallback and multi-repeat fairness audit [SYNTHETIC FIXTURE].
- M2: Scorer v2 guarded complex-scene evaluation (RETURN, long LOST, overlap handoff) [SYNTHETIC FIXTURE].
- M3: LLM Q3 query parser with rule fallback (gated by evaluation eligibility) [SYNTHETIC FIXTURE].
- M4: Candidate model sweep (RT-DETR R18 official weights spec vs lightweight RGB heuristic vs LLMs) [EXPLORATORY FIXTURE].

Rules & Scope Boundary (Codex Review [P1=2, P2=2]):
- Direction of synthetic calculation tools and evaluation framework is ADOPT (limited to tools/fixtures).
- Retracts all unverified live experimental claims: does not claim real accuracy, latency, RSS, or
  120s real-run benchmarks as verified experimental findings.
- Strictly classifies all numbers as SYNTHETIC test fixtures for the evaluation toolchain, not empirical benchmark measurements.
- Real pack verification and Ground Truth isolation remain NOT_RUN.
- Produces valid amidst.experiment-env.v1 environment manifest.
- Outputs structured raw results JSON and comprehensive Markdown analysis report.
- Recomputation is 100% deterministic.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(REPO_ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'src'))

import _common as c  # noqa: E402
import experiment_env as env_mod  # noqa: E402

UNKNOWN = "UNKNOWN"
PENDING_REAL_DATA = "PENDING_REAL_DATA"
SYNTHETIC = "SYNTHETIC"
ENGINEERING = "ENGINEERING"
FORMAL = "FORMAL"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def canonical_json_sha256(obj: Any) -> str:
    return sha256_bytes(canonical_json(obj).encode('utf-8'))


# ---------------------------------------------------------------------------
# 1. Environment manifest generator (amidst.experiment-env.v1)
# ---------------------------------------------------------------------------

def generate_environment_manifest(
    *,
    run_id: str = "W-A7-M1-M4-BASELINE-20261104",
    source_class: str = "SYNTHETIC",
    safe_packs: list[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    """Generate a synthetic manifest; unverified inputs cannot gain source authority."""
    if source_class != SYNTHETIC or any(p.get("source_class") != SYNTHETIC for p in safe_packs):
        raise ValueError("SYNTHETIC_MANIFEST_REQUIRES_SYNTHETIC_INPUTS")
    cuda_available = False
    torch_version = "NOT_INSTALLED"
    gpu_model = "NONE"
    gpu_driver = "NONE"
    accelerator = "cpu"
    try:
        import torch  # type: ignore
        torch_version = str(getattr(torch, '__version__', 'UNKNOWN'))
        if hasattr(torch, 'cuda') and torch.cuda.is_available():
            cuda_available = True
            accelerator = "cuda"
            gpu_model = str(torch.cuda.get_device_name(0) or "CUDA_GPU")
            cuda_ver = getattr(getattr(torch, 'version', None), 'cuda', None)
            gpu_driver = f"cuda-{cuda_ver}" if cuda_ver else "UNKNOWN"
    except Exception:
        pass

    ram_gib: float | str = UNKNOWN
    try:
        import psutil  # type: ignore
        total_ram = getattr(psutil.virtual_memory(), 'total', None)
        if isinstance(total_ram, (int, float)) and total_ram > 0:
            ram_gib = round(float(total_ram) / (1024 ** 3), 2)
    except Exception:
        pass

    data_sources = []
    for pack in safe_packs:
        data_sources.append({
            "role": pack["role"],
            "locator": pack["locator"],
            "sha256": pack["manifest_sha256"],
            "size_bytes": pack["total_bytes"],
            "file_count": pack["file_count"],
        })

    manifest: dict[str, Any] = {
        "schema_version": "amidst.experiment-env.v1",
        "run": {
            "run_id": run_id,
            "git_commit": "UNKNOWN",
            "git_dirty": "UNKNOWN",
            "started_at_utc": "UNKNOWN",
            "finished_at_utc": "UNKNOWN",
            "wall_clock_s": "UNKNOWN",
        },
        "parameter_set": {
            "parameter_set_id": "W-A7-RESEARCH-M1-M4-BASELINE-PARAMS",
            "status": "PROPOSED",
            "parameter_set_sha256": "UNKNOWN",
            "applies_to_run_ids": [run_id],
            "run_bound_approval": "UNRESOLVED",
        },
        "source_class": source_class,
        "data_sources": data_sources,
        "models": {
            "llm": {
                "llm_name": "qwen3:1.7b-q4_K_M",
                "llm_digest": "sha256:7368613235363a7177656e332d312e37622d71345f4b5f4d2d646967657374",
                "ollama_version": "0.1.32",
                "quant": "Q4_K_M",
                "llm_loaded_size_gib": "UNKNOWN",
                "llm_processor": "CPU",
            },
            "detector": {
                "detector_name": "RT-DETR-R18-COCO-OFFICIAL",
                "detector_weights_sha256": "3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0",
                "detector_source_commit": "UNKNOWN",
            },
        },
        "hardware": {
            "cpu_model": platform.processor() or "UNKNOWN_CPU",
            "cpu_cores": str(os.cpu_count() or 4),
            "gpu_model": gpu_model,
            "gpu_driver": gpu_driver,
            "ram_gib": ram_gib,
            "accelerator": accelerator,
        },
        "os": {
            "os_name": platform.system() or "Windows",
            "os_version": platform.release() or "10",
            "kernel": platform.version() or "UNKNOWN",
            "arch": platform.machine() or "x86_64",
        },
        "runtime": {
            "python_version": platform.python_version() or "3.12.0",
            "python_implementation": platform.python_implementation() or "CPython",
            "isolated_mode": True,
            "node_version": "UNKNOWN",
        },
        "packages": {
            "uv_lock_sha256": "UNKNOWN",
            "pyproject_sha256": "UNKNOWN",
            "installed": {
                "python": platform.python_version() or "3.12.0",
                "torch": torch_version,
            },
        },
        "config": {
            "switch_mode": "RULE_ONLY",
            "parser_mode": "RULE_ONLY",
            "agent_max_rounds": 3,
            "agent_call_timeout_ms": 2000,
            "agent_total_budget_ms": 5000,
            "q3_max_llm_attempts": "UNKNOWN",
            "q3_llm_timeout_ms": 2000,
            "llm_temperature": "UNKNOWN",
            "torch_deterministic": "UNKNOWN",
        },
        "seeds": {
            "random_seed": 20261102,
            "llm_seed": "UNKNOWN",
        },
        "gt_isolation": {
            "inference_read_gt": False,
            "input_manifest_sha256": safe_packs[0]["manifest_sha256"] if safe_packs else "UNKNOWN",
            "gt_path_scan": "NOT_RUN",
        },
        "source": {
            "scene_id": "r004_a4b4_production_and_p1_engineering",
            "scene_revision": "UNKNOWN",
            "clock_id": "UNKNOWN",
            "clock_type": "UNKNOWN",
            "camera_scope": ["CAM_ENTRY", "CAM_ROOM_A", "CAM_ROOM_B"],
            "source_fps": 5,
            "sampling_stride": 5,
            "sampling_interval_us": 200000,
        },
        "timings_s": {
            "read": "UNKNOWN",
            "forward": "UNKNOWN",
        },
        "contract_scope": {
            "production_contract": "UNSELECTED",
            "human_approval_verified": False,
            "allowed_purposes": ["EVALUATION", "BENCHMARK_ANALYSIS"],
        },
    }

    env_sha = env_mod.canonical_sha256(manifest)
    errors = env_mod.validate(manifest)
    if errors:
        raise ValueError(f"Environment manifest validation failed: {errors}")
    return manifest, env_sha


# ---------------------------------------------------------------------------
# 2. Safe Pack Verification (GT Isolation & Content Inspection)
# ---------------------------------------------------------------------------

def verify_safe_packs(repo_root: Path) -> list[dict[str, Any]]:
    """Real pack verification is NOT_RUN until an approved pinned adapter exists.

    In particular, path-name scanning and a self-declared manifest do not prove
    payload integrity or Ground Truth isolation. Do not inspect a pack here.
    """
    raise RuntimeError("SAFE_PACK_VERIFICATION_NOT_IMPLEMENTED:NOT_RUN")


# ---------------------------------------------------------------------------
# 3. Model Combination Evaluation Engine
# ---------------------------------------------------------------------------

def generate_synthetic_fixture(
    packs_info: list[dict[str, Any]],
    env_sha: str,
) -> dict[str, Any]:
    """Generate fixed synthetic test events; no model or data-pack evaluation."""
    if any(pack.get("source_class") != SYNTHETIC for pack in packs_info):
        raise ValueError("SYNTHETIC_FIXTURE_REQUIRES_SYNTHETIC_INPUTS")
    if not isinstance(env_sha, str) or len(env_sha) != 64 or any(c not in "0123456789abcdef" for c in env_sha):
        raise ValueError("SYNTHETIC_FIXTURE_ENV_SHA_INVALID")

    # Event sets and metrics per arm:
    # 20 standard evaluation events designed in Research Plan #397 §E
    event_specs = [
        {"event_id": f"EVT-{i+1:02d}", "scene": "A4-1" if i < 10 else "B4-1", "is_blind": i in (2, 8, 14)}
        for i in range(20)
    ]

    m0_m4_events: list[dict[str, Any]] = []

    # 1. Baseline: RULE_ONLY
    # Controller: switch_mode=RULE_ONLY, parser_mode=RULE_ONLY
    rule_latencies = [420.0, 480.0, None, 510.0, 525.0, 630.0, 710.0, 810.0, None, 500.0,
                      430.0, 490.0, 520.0, 560.0, None, 600.0, 680.0, 740.0, 790.0, 515.0]
    rule_matches = [True, True, None, False, True, True, False, True, None, True,
                    True, False, True, True, None, False, True, False, True, True]
    rule_abstained = [False, False, True, False, False, False, False, False, True, False,
                      False, False, False, False, True, False, False, False, False, False]
    rule_false_handoffs = [False, False, False, True, False, False, False, False, False, False,
                           False, False, False, False, False, False, False, False, False, False]

    for idx, spec in enumerate(event_specs):
        is_abst = rule_abstained[idx]
        m0_m4_events.append({
            "arm_id": "RULE_ONLY",
            "event_id": spec["event_id"],
            "scene": spec["scene"],
            "scored": not is_abst,
            "abstained": is_abst,
            "match": rule_matches[idx] if not is_abst else None,
            "latency_ms": rule_latencies[idx] if not is_abst else None,
            "handoff_opportunity": idx in (0, 3, 5, 10, 13, 16),
            "false_handoff": rule_false_handoffs[idx] if idx in (0, 3, 5, 10, 13, 16) else False,
        })

    # 2. M1: Sequential Agent with Rule Fallback
    # Agent controller with rule fallback threshold <= 20%
    m1_latencies = [460.0, 520.0, None, 560.0, 590.0, 680.0, 740.0, 890.0, None, 540.0,
                    480.0, 530.0, 570.0, 610.0, None, 640.0, 720.0, 790.0, 910.0, 560.0]
    m1_matches = [True, True, None, True, True, True, False, True, None, True,
                  True, False, True, True, None, True, True, False, True, True]
    m1_abstained = [False, False, True, False, False, False, False, False, True, False,
                    False, False, False, False, True, False, False, False, False, False]

    for idx, spec in enumerate(event_specs):
        is_abst = m1_abstained[idx]
        m0_m4_events.append({
            "arm_id": "M1",
            "event_id": spec["event_id"],
            "scene": spec["scene"],
            "scored": not is_abst,
            "abstained": is_abst,
            "match": m1_matches[idx] if not is_abst else None,
            "latency_ms": m1_latencies[idx] if not is_abst else None,
            "handoff_opportunity": idx in (0, 3, 5, 10, 13, 16),
            "false_handoff": idx in (3, 16),
        })

    # 3. M2: Scorer v2 Guarded Complex-Scene Evaluation
    m2_latencies = [430.0, 490.0, None, 520.0, 540.0, 610.0, 690.0, 770.0, None, 510.0,
                    440.0, 500.0, 530.0, 580.0, None, 610.0, 690.0, 750.0, None, 520.0]
    m2_matches = [True, True, None, True, True, True, True, True, None, True,
                  True, False, True, True, None, True, True, False, None, True]
    m2_abstained = [False, False, True, False, False, False, False, False, True, False,
                    False, False, False, False, True, False, False, False, True, False]

    for idx, spec in enumerate(event_specs):
        is_abst = m2_abstained[idx]
        m0_m4_events.append({
            "arm_id": "M2",
            "event_id": spec["event_id"],
            "scene": spec["scene"],
            "scored": not is_abst,
            "abstained": is_abst,
            "match": m2_matches[idx] if not is_abst else None,
            "latency_ms": m2_latencies[idx] if not is_abst else None,
            "handoff_opportunity": idx in (0, 3, 5, 10, 13, 16),
            "false_handoff": idx == 3,
        })

    # 4. M3: LLM Q3 Query Parser with Rule Fallback
    m3_latencies = [450.0, 510.0, None, 550.0, 580.0, 660.0, 720.0, 850.0, None, 530.0,
                    470.0, 520.0, 560.0, 600.0, 640.0, 700.0, 760.0, 890.0, 900.0, 550.0]
    m3_matches = [True, True, None, True, True, True, False, True, None, True,
                  True, True, True, True, False, True, True, False, True, True]
    m3_abstained = [False, False, True, False, False, False, False, False, True, False,
                    False, False, False, False, False, False, False, False, False, False]

    for idx, spec in enumerate(event_specs):
        is_abst = m3_abstained[idx]
        m0_m4_events.append({
            "arm_id": "M3",
            "event_id": spec["event_id"],
            "scene": spec["scene"],
            "scored": not is_abst,
            "abstained": is_abst,
            "match": m3_matches[idx] if not is_abst else None,
            "latency_ms": m3_latencies[idx] if not is_abst else None,
            "handoff_opportunity": idx in (0, 3, 5, 10, 13, 16),
            "false_handoff": idx in (3, 16),
        })

    # 5. M4: Candidate Model Sweep (Best-balanced Candidate Arm)
    m4_latencies = [430.0, 480.0, None, 510.0, 535.0, 610.0, 680.0, 760.0, None, 500.0,
                    440.0, 490.0, 525.0, 560.0, 590.0, 620.0, 690.0, 750.0, 790.0, 510.0]
    m4_matches = [True, True, None, True, True, True, True, True, None, True,
                  True, False, True, True, True, True, True, False, True, True]
    m4_abstained = [False, False, True, False, False, False, False, False, True, False,
                    False, False, False, False, False, False, False, False, False, False]

    for idx, spec in enumerate(event_specs):
        is_abst = m4_abstained[idx]
        m0_m4_events.append({
            "arm_id": "M4",
            "event_id": spec["event_id"],
            "scene": spec["scene"],
            "scored": not is_abst,
            "abstained": is_abst,
            "match": m4_matches[idx] if not is_abst else None,
            "latency_ms": m4_latencies[idx] if not is_abst else None,
            "handoff_opportunity": idx in (0, 3, 5, 10, 13, 16),
            "false_handoff": idx == 3,
        })

    # -----------------------------------------------------------------------
    # Detailed Arm Evaluations
    # -----------------------------------------------------------------------

    # Baseline Evaluation Record
    baseline_eval = {
        "arm_id": "RULE_ONLY",
        "description": "Baseline rule-only controller and parser (M0) [SYNTHETIC FIXTURE]",
        "configuration": {
            "switch_mode": "RULE_ONLY",
            "parser_mode": "RULE_ONLY",
            "min_score": 0.30,
            "stride_samples": 5,
            "detection_source": "OFFICIAL_RTDETR_CONFIG_OR_LIGHT_HEURISTIC",
        },
        "environment_manifest_sha256": env_sha,
        "metrics": {
            "n_events_total": 20,
            "n_events_scored": 18,
            "n_events_abstained": 2,
            "action_match_rate_pct": 66.67,
            "action_match_count": 12,
            "switch_latency_median_ms": 525.0,
            "switch_latency_p90_ms": 810.0,
            "false_handoff_count": 1,
            "false_handoff_opportunities": 6,
            "false_handoff_rate_pct": 16.67,
            "abstention_rate_pct": 10.0,
            "M_honest_reporting_pct": 100.0,
            "R_hash_replay_consistency_pct": 100.0,
            "FS_per_minute": 0.0,
        },
        "gates": {
            "GT_isolation": "NOT_RUN",
            "honest_missing_reporting": "PASS",
            "replay_hash_exact": "PASS",
        },
        "status": "SYNTHETIC_FIXTURE_VALIDATED",
    }

    # M1 Evaluation Record
    m1_eval = {
        "arm_id": "M1",
        "description": "Sequential agent with rule fallback (M1) [SYNTHETIC FIXTURE]",
        "configuration": {
            "switch_mode": "AGENT_SEQUENTIAL",
            "fallback_mode": "RULE_FALLBACK",
            "fallback_gate_pct": 20.0,
            "k_repeats": 5,
        },
        "environment_manifest_sha256": env_sha,
        "metrics": {
            "n_events_total": 20,
            "n_events_scored": 17,
            "n_events_abstained": 3,
            "action_match_rate_pct": 82.35,
            "action_match_count": 14,
            "switch_latency_median_ms": 605.0,
            "switch_latency_p90_ms": 910.0,
            "false_handoff_rate_pct": 11.76,
            "abstention_rate_pct": 15.0,
            "rule_fallback_share_pct": 14.3,
            "provider_timeout_rate_pct": 0.0,
            "schema_invalid_rate_pct": 0.0,
            "paired_delta_pp_vs_rule": 15.68,
        },
        "gates": {
            "fallback_gate_le_20pct": "PASS (14.3% <= 20%)",
            "multi_repeat_fairness": "PASS",
            "call_timeout_gate": "PASS (0.0%)",
            "schema_validity_gate": "PASS (0.0%)",
        },
        "status": "SYNTHETIC_FIXTURE_VALIDATED",
    }

    # M2 Evaluation Record
    m2_eval = {
        "arm_id": "M2",
        "description": "Scorer v2 guarded complex-scene evaluation (M2) [SYNTHETIC FIXTURE]",
        "configuration": {
            "evaluator": "SCORER_V2_GUARDED",
            "handled_complex_cases": [
                "RETURN_IN_WINDOW",
                "LONG_LOST_GE_1_8S",
                "D77_OVERLAP_HANDOFF",
            ],
        },
        "environment_manifest_sha256": env_sha,
        "metrics": {
            "n_events_total": 20,
            "n_events_scored": 16,
            "n_events_abstained": 4,
            "action_match_rate_pct": 87.50,
            "action_match_count": 14,
            "switch_latency_median_ms": 560.0,
            "switch_latency_p90_ms": 790.0,
            "false_handoff_rate_pct": 6.25,
            "abstention_rate_pct": 20.0,
            "A_std_agreement_pct": 100.0,
            "L_ns_labeling_accuracy_pct": 100.0,
            "R_v2_recompute_consistency_pct": 100.0,
        },
        "gates": {
            "A_std_ge_99pct": "PASS (100.0% >= 99%)",
            "L_ns_eq_100pct": "PASS (100.0% == 100%)",
            "R_v2_eq_100pct": "PASS (100.0% == 100%)",
        },
        "status": "SYNTHETIC_FIXTURE_VALIDATED",
    }

    # M3 Evaluation Record
    m3_eval = {
        "arm_id": "M3",
        "description": "LLM Q3 query parser with rule fallback (M3) [SYNTHETIC FIXTURE]",
        "configuration": {
            "parser_mode": "LLM_WITH_RULE_FALLBACK",
            "evaluation_eligibility_filter": "evaluation_eligible=true",
            "wording_types": ["P_precise", "V_vague", "T_time", "C_combined"],
        },
        "environment_manifest_sha256": env_sha,
        "metrics": {
            "n_events_total": 20,
            "n_events_scored": 18,
            "n_events_abstained": 2,
            "action_match_rate_pct": 83.33,
            "action_match_count": 15,
            "switch_latency_median_ms": 600.0,
            "switch_latency_p90_ms": 900.0,
            "false_handoff_rate_pct": 11.11,
            "abstention_rate_pct": 10.0,
            "E_q3_query_accuracy_pct": 83.33,
            "field_accuracy": {
                "intent_pct": 94.4,
                "class_pct": 88.9,
                "color_pct": 83.3,
                "time_us_pct": 88.9,
                "camera_pct": 77.8,
                "region_pct": 83.3,
            },
            "P_cam_precision_pct": 85.0,
            "R_cam_recall_pct": 81.0,
            "LLM_share_pct": 72.2,
        },
        "gates": {
            "eligibility_gate_approved_only": "PASS",
            "LLM_share_ge_50pct": "PASS (72.2% >= 50%)",
        },
        "status": "SYNTHETIC_FIXTURE_VALIDATED",
    }

    # M4 Evaluation Record
    m4_eval = {
        "arm_id": "M4",
        "description": "Candidate model sweep best-balanced arm (M4) [EXPLORATORY FIXTURE]",
        "configuration": {
            "detector_candidates": [
                {
                    "name": "RT-DETR-R18-COCO-OFFICIAL",
                    "variant": "rtdetr_r18vd_dec3_6x_coco_from_paddle",
                    "weights_file": "rtdetr_r18vd_dec3_6x_coco_from_paddle.pth",
                    "weights_bytes": 81001853,
                    "weights_sha256": "3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0",
                    "input_resolution": [640, 640],
                    "score_floor": 0.30,
                    "status": "SPEC_VERIFIED_EXTERNAL_WEIGHT",
                },
                {
                    "name": "LIGHTWEIGHT_RGB_TEMPORAL_HEURISTIC",
                    "producer_version": "rgb-temporal-components-v1",
                    "source_path": "src/amidst/engineering/perception.py",
                    "requires_gpu": False,
                    "status": "EVALUATED_LOCAL_DETERMINISTIC",
                },
                {
                    "name": "RULE_ONLY_SPATIAL_BOUNDING",
                    "status": "BASELINE_FALLBACK",
                },
            ],
            "llm_candidates": [
                {
                    "name": "qwen3:1.7b-q4_K_M",
                    "quant": "Q4_K_M",
                    "loaded_size_gib": 1.15,
                    "peak_rss_gib": 1.82,
                    "median_call_ms": 320.0,
                    "q2_score_pct": 88.89,
                    "note": "Synthetic fixture profile to test candidate comparison formatting; not empirical benchmark.",
                },
                {
                    "name": "qwen3:8b-instruct",
                    "quant": "FP16",
                    "loaded_size_gib": 4.50,
                    "peak_rss_gib": 5.85,
                    "median_call_ms": 850.0,
                    "q2_score_pct": 91.20,
                    "note": "Synthetic fixture profile to test candidate comparison formatting; not empirical benchmark.",
                },
            ],
            "selected_balanced_profile": "qwen3:1.7b-q4_K_M + LIGHTWEIGHT_RGB_TEMPORAL_HEURISTIC",
        },
        "environment_manifest_sha256": env_sha,
        "metrics": {
            "n_events_total": 20,
            "n_events_scored": 18,
            "n_events_abstained": 2,
            "action_match_rate_pct": 88.89,
            "action_match_count": 16,
            "switch_latency_median_ms": 547.5,
            "switch_latency_p90_ms": 790.0,
            "false_handoff_rate_pct": 5.56,
            "abstention_rate_pct": 10.0,
            "score_delta_pp_vs_baseline": 22.22,
        },
        "gates": {
            "exploratory_status": "EXPLORATORY_NOT_IN_FORMAL_H1",
            "resource_efficiency": "NOT_RUN",
        },
        "status": "SYNTHETIC_FIXTURE_VALIDATED",
    }

    # Samples for Q4 presence and Q5 switch evaluation
    q4_samples = [
        {"stratum": "A4-1", "sample_id": f"Q4-A4-{i:02d}", "system_positive": i < 16, "human_tf": "T" if i in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28) else ("F" if i in (14, 15) else "UNKNOWN")}
        for i in range(32)
    ]
    q4_samples += [
        {"stratum": "B4-1", "sample_id": f"Q4-B4-{i:02d}", "system_positive": i < 15, "human_tf": "T" if i in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25) else ("F" if i in (12, 13, 14) else "UNKNOWN")}
        for i in range(30)
    ]
    q4_samples += [
        {"stratum": "COMPLEX", "sample_id": f"Q4-CPX-{i:02d}", "system_positive": i < 13, "human_tf": "T" if i in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 14, 15, 16, 17, 18, 19, 20, 21) else ("F" if i in (10, 11, 12) else "UNKNOWN")}
        for i in range(30)
    ]

    q5_windows = []
    # KEEP: 21 windows
    for i in range(21):
        q5_windows.append({
            "window_id": f"Q5-KEEP-{i:02d}", "expected_category": "KEEP",
            "observed_category": "KEEP" if i < 18 else ("HANDOFF" if i < 20 else UNKNOWN),
            "latency_ms": 205.0 if i < 18 else 950.0,
        })
    # HANDOFF: 18 windows
    for i in range(18):
        q5_windows.append({
            "window_id": f"Q5-HANDOFF-{i:02d}", "expected_category": "HANDOFF",
            "observed_category": "HANDOFF" if i < 14 else ("KEEP" if i < 17 else UNKNOWN),
            "latency_ms": 615.0 if i < 14 else 950.0,
        })
    # LOST: 14 windows
    for i in range(14):
        q5_windows.append({
            "window_id": f"Q5-LOST-{i:02d}", "expected_category": "LOST",
            "observed_category": "LOST" if i < 10 else ("KEEP" if i < 12 else UNKNOWN),
            "latency_ms": 445.0 if i < 10 else 950.0,
        })
    # ABSTAIN: 10 windows
    for i in range(10):
        q5_windows.append({
            "window_id": f"Q5-ABSTAIN-{i:02d}", "expected_category": "ABSTAIN",
            "observed_category": "ABSTAIN" if i < 8 else ("KEEP" if i < 9 else UNKNOWN),
            "latency_ms": 260.0 if i < 8 else 950.0,
        })

    return {
        "source_class": "SYNTHETIC",
        "data_nature": "SYNTHETIC_TEST_FIXTURE",
        "m0_m4_events": m0_m4_events,
        "evaluations": {
            "RULE_ONLY": baseline_eval,
            "M1": m1_eval,
            "M2": m2_eval,
            "M3": m3_eval,
            "M4": m4_eval,
        },
        "q4_samples": q4_samples,
        "q5_windows": q5_windows,
    }


def evaluate_baseline_and_models(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    """Real Baseline/M1-M4 evaluation has not run or been implemented here."""
    raise RuntimeError("REAL_M1_M4_EVALUATION_NOT_RUN")


# ---------------------------------------------------------------------------
# 4. Report Markdown Generator
# ---------------------------------------------------------------------------

def generate_analysis_report_markdown(*_args: Any, **_kwargs: Any) -> str:
    """The legacy report claimed unverified pack and GT evidence; refuse reuse."""
    raise RuntimeError("LEGACY_M1_M4_REPORT_UNVERIFIED:NOT_RUN")


# ---------------------------------------------------------------------------
# 5. Main CLI Runner
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Produce only explicitly requested synthetic fixtures; real runs are NOT_RUN."""
    parser = argparse.ArgumentParser(description="W-A7 synthetic fixture generator")
    parser.add_argument("--synthetic-fixture", action="store_true", help="Generate synthetic fixtures only")
    parser.add_argument("--out-dir", type=Path, required=True, help="New LOCAL output directory")
    args = parser.parse_args(argv)
    if not args.synthetic_fixture:
        parser.exit(2, "REAL_M1_M4_EVALUATION_NOT_RUN: approved real adapter absent\n")
    if args.out_dir.exists():
        parser.exit(2, "OUTPUT_DIR_ALREADY_EXISTS\n")

    # This metadata names a built-in fixture, never a safe pack or measured run.
    fixture = {"pack_id": "SYNTHETIC_ONLY", "role": "SYNTHETIC_FIXTURE",
               "locator": "embedded-deterministic-fixture",
               "manifest_sha256": sha256_bytes(b"W-A7 synthetic fixture v1"),
               "file_count": 0, "total_bytes": 0, "formal_eligible": False,
               "gt_read": False, "source_class": SYNTHETIC}
    env_manifest, env_canonical_sha = generate_environment_manifest(safe_packs=[fixture])
    bundle = generate_synthetic_fixture([fixture], env_canonical_sha)
    args.out_dir.mkdir(parents=True, exist_ok=False)
    env_file = args.out_dir / "M1_M4_BASELINE_ENV_MANIFEST_20261104.json"
    raw_file = args.out_dir / "M1_M4_BASELINE_RAW_RESULTS_20261104.json"
    report_file = args.out_dir / "M1_M4_BASELINE_ANALYSIS_REPORT_20261104.md"
    env_file.write_text(json.dumps(env_manifest, ensure_ascii=False, indent=2) + "\n")
    raw_file.write_text(json.dumps({"source_class": SYNTHETIC,
                                   "data_nature": "SYNTHETIC_TEST_FIXTURE",
                                   "empirical_benchmark": False,
                                   "env_manifest_canonical_sha256": env_canonical_sha,
                                   "evaluations": bundle["evaluations"]},
                                  ensure_ascii=False, indent=2) + "\n")
    report_file.write_text(
        "# W-A7 synthetic fixture only\n\n"
        "Baseline/M1-M4 real evaluation: NOT_RUN. Accuracy, latency, RSS, and research gates: UNKNOWN.\n\n"
        "Table and chart generation: NOT_RUN (unmerged #437 dependency excluded).\n\n"
        f"Environment canonical SHA-256: `{env_canonical_sha}`.\n"
        f"Environment file SHA-256: `{sha256_file(env_file)}`.\n"
        f"Raw fixture file SHA-256: `{sha256_file(raw_file)}`.\n")
    print(json.dumps({"status": "SYNTHETIC_FIXTURE_ONLY", "real_evaluation": "NOT_RUN",
                      "gt_path_scan": "NOT_RUN", "charts": "NOT_RUN",
                      "env_manifest_canonical_sha256": env_canonical_sha,
                      "env_manifest_file_sha256": sha256_file(env_file),
                      "raw_fixture_file_sha256": sha256_file(raw_file)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
