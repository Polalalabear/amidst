"""E7 Scoring Bridge (SCORING SIDE ONLY).

This module is the ONLY E7 module permitted to read the uploaded answer table
(D385) and import ``amidst.evaluation.e3_scoring``. Decider adapters in
``e7_decider_eval.py`` NEVER import this module or receive answer tables.

Produces ``e7_analysis_<date>.json`` (directly consumable by
``scripts/evaluation/generate_unified_analysis.py``), ``e7_analysis_<date>.md``,
and headless PNG charts.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from amidst.evaluation import e3_scoring as S

SCHEMA_VERSION = "e7_analysis_v1"


def score_single_decision(
    decision_record: dict[str, Any],
    answer_entry: dict[str, Any],
    *,
    size: tuple[int, int] = (320, 180),
) -> dict[str, Any]:
    """Score one E7 decider output against one answer-table entry using ``e3_scoring.judge_box`` rules."""
    parsed = decision_record.get("parsed")
    gt_visible = set(answer_entry.get("gt_visible") or [])
    gt_boxes = answer_entry.get("gt_boxes") or {}

    if parsed is None:
        return {"outcome": "FALLBACK", "correct": False, "fallback_reason": decision_record.get("fallback_reason")}

    ans = parsed.get("answer")
    cam = parsed.get("camera_id")

    if not gt_visible:
        if ans == "NOT_VISIBLE":
            return {"outcome": "BLIND_OK", "correct": True}
        if ans == "UNCERTAIN":
            return {"outcome": "BLIND_UNCERTAIN", "correct": False}
        return {"outcome": "FALSE_LOCK", "correct": False}

    # Target is GT-visible in at least one camera
    if ans in ("NOT_VISIBLE", "UNCERTAIN"):
        return {"outcome": "LOST", "correct": False}
    if ans == "STILL_HERE_OCCLUDED":
        return {"outcome": "CORRECT" if cam in gt_visible else "WRONG_CAMERA", "correct": cam in gt_visible}
    if ans in ("SELECT", "OWN_BOX"):
        if cam not in gt_visible:
            return {"outcome": "WRONG_CAMERA", "correct": False}
        box = parsed.get("box_xyxy")
        if box is None and ans == "SELECT":
            box = answer_entry.get("candidate_boxes", {}).get(f"{cam}|{parsed.get('detection_id')}")
        body = gt_boxes.get(cam)
        if box is not None and body is not None:
            j = S.judge_box(box, body, size)
            return {
                "outcome": "CORRECT" if j["primary"] else "WRONG_PERSON",
                "correct": bool(j["primary"]),
                "iou": j["iou"],
            }
        # Fallback to camera + expected detection_id match when boxes are omitted in lightweight answer tables
        exp_dets = set(answer_entry.get("expected_detection_ids", {}).get(cam) or [])
        if exp_dets:
            hit = parsed.get("detection_id") in exp_dets
            return {"outcome": "CORRECT" if hit else "WRONG_PERSON", "correct": hit}
        return {"outcome": "GT_UNKNOWN", "correct": False}

    return {"outcome": "FALLBACK", "correct": False}


def score_e7_comparison(
    comparison_run: dict[str, Any],
    answer_table: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Attach accuracy metrics to an ``e7_decider_eval.run_acceleration_comparison`` dict (scoring side ONLY)."""
    out = dict(comparison_run)
    for mode_key in ("accelerated", "unaccelerated"):
        block = dict(comparison_run[mode_key])
        records = block.get("records") or []
        scored = 0
        correct = 0
        wrong_target = 0
        blind_lock = 0
        segments: set[str] = set()
        for r in records:
            ans_entry = answer_table.get(r["request_id"])
            if ans_entry is None:
                continue
            scored += 1
            segments.add(r["case_id"])
            res = score_single_decision(r, ans_entry)
            if res["correct"]:
                correct += 1
            if res["outcome"] in ("WRONG_PERSON", "WRONG_CAMERA"):
                wrong_target += 1
            if res["outcome"] == "FALSE_LOCK":
                blind_lock += 1
        block["n_decision_points"] = scored
        block["n_segments"] = len(segments)
        block["decision_point_accuracy"] = round(correct / scored, 4) if scored else None
        block["correct_rate"] = block["decision_point_accuracy"]
        block["wrong_target_count"] = wrong_target
        block["blind_lock_count"] = blind_lock
        block["wrong_target_s"] = None
        block["blind_lock_s"] = None
        block["expired_rate"] = 0.0
        out[mode_key] = block
    return out


def build_e7_analysis_report(
    *,
    hardware: dict[str, Any],
    manifest_verification: dict[str, Any],
    scored_models: list[dict[str, Any]],
    dataset_scope: str = "e3_16_segments",
    frozen_e5_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble ``e7_analysis_<date>.json`` compatible with ``generate_unified_analysis.py``."""
    frozen_summary = {}
    if frozen_e5_report:
        per_arm = frozen_e5_report.get("per_arm") or {}
        for arm in ("B1", "AO", "AOL"):
            if arm in per_arm:
                pa = per_arm[arm]
                frozen_summary[arm] = {
                    "follow_rate": pa.get("follow_rate"),
                    "wrong_person_s": pa.get("wrong_person_s"),
                    "false_lock_s": pa.get("false_lock_s"),
                    "dp_correct": pa.get("dp_correct"),
                    "dp_total": pa.get("dp_total"),
                    "latency_ms_p50": pa.get("latency_ms_p50"),
                    "latency_ms_p95": pa.get("latency_ms_p95"),
                }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "identity_status": "UNCONFIRMED",
        "dataset_scope": dataset_scope,
        "hardware": hardware,
        "manifest_verification": manifest_verification,
        "frozen_baselines": frozen_summary,
        "models": scored_models,
    }


def render_e7_markdown(report: dict[str, Any]) -> str:
    hw = report["hardware"]
    mv = report["manifest_verification"]
    lines = [
        f"# E7 Local / Colab Decider Evaluation (`{report['dataset_scope']}`)",
        "",
        f"- Generated (UTC): `{report['generated_at_utc']}`",
        f"- Identity status: **`{report['identity_status']}`**",
        f"- GPU: `{hw.get('gpu_name')}` (VRAM: `{hw.get('gpu_vram_mb')}` MB, driver: `{hw.get('gpu_driver_version')}`)",
        f"- CPU / RAM: `{hw.get('cpu_model')}` ({hw.get('cpu_count')} cores) / `{hw.get('ram_gb')}` GB",
        f"- CUDA / cuDNN / Python: `{hw.get('cuda_version')}` / `{hw.get('cudnn_version')}` / `{hw.get('python_version')}`",
        f"- Git commit: `{hw.get('git_commit')}`",
        f"- Upload pack MANIFEST: `{mv.get('status')}` ({mv.get('files_verified')} files verified, SHA-256 `{str(mv.get('manifest_sha256', ''))[:16]}...`)",
        "",
        "## Acceleration Comparison (Accelerated vs Unaccelerated)",
        "",
        "| Model | Mode | Accel p50/p95 (ms) | Unaccel p50/p95 (ms) | Accel Fallback | Unaccel Fallback | Agreement | DP Acc (Accel) | Sample (Acc/Unacc) |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for m in report["models"]:
        a, u = m["accelerated"], m["unaccelerated"]
        lines.append(
            f"| {m['label']} | `{m['input_mode']}` | "
            f"{a['latency_p50_ms']} / {a['latency_p95_ms']} | "
            f"{u['latency_p50_ms']} / {u['latency_p95_ms']} | "
            f"{a['format_fallback_rate']:.4f} | {u['format_fallback_rate']:.4f} | "
            f"{m['decision_agreement_vs_unaccelerated']} | {a.get('decision_point_accuracy')} | "
            f"{a['sample_size']} / {u['sample_size']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_e7_outputs(report: dict[str, Any], out_dir: Path, date_tag: str | None = None) -> dict[str, Path]:
    """Write ``e7_analysis_<date>.json``, ``e7_analysis_<date>.md``, and optional PNG chart."""
    tag = date_tag or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"e7_analysis_{tag}.json"
    md_path = out_dir / f"e7_analysis_{tag}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_e7_markdown(report), encoding="utf-8")
    out = {"json": json_path, "md": md_path}
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if report["models"]:
            labels = [m["label"] for m in report["models"]]
            acc_p50 = [float(m["accelerated"]["latency_p50_ms"] or 0.0) for m in report["models"]]
            unacc_p50 = [float(m["unaccelerated"]["latency_p50_ms"] or 0.0) for m in report["models"]]
            fig, ax = plt.subplots(figsize=(8.5, 4.0))
            y = range(len(labels))
            ax.barh([i - 0.18 for i in y], acc_p50, height=0.35, label="Accelerated p50 (ms)", color="#2563eb")
            ax.barh([i + 0.18 for i in y], unacc_p50, height=0.35, label="Unaccelerated p50 (ms)", color="#f59e0b")
            ax.set_yticks(list(y))
            ax.set_yticklabels(labels)
            ax.set_xlabel("Latency p50 (ms)")
            ax.set_title("E7 Decider Latency: Accelerated vs Unaccelerated")
            ax.legend()
            fig.tight_layout()
            png_path = out_dir / f"e7_latency_{tag}.png"
            fig.savefig(png_path, dpi=150)
            plt.close(fig)
            out["png"] = png_path
    except Exception:
        pass
    return out
