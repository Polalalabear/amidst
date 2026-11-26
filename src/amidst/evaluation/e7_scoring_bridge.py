"""E7 Scoring Bridge (SCORING SIDE ONLY).

This module is the ONLY E7 module permitted to read the uploaded Colab answer
table (D385). Decider adapters in ``e7_decider_eval.py`` NEVER import this
module or receive answer tables.

D385 COMPLIANCE (Label-Only Colab Answer Table):
    Colab answer tables MUST contain ONLY pre-matched label fields:
    ``expected_answer``, ``expected_camera_ids``, ``expected_detection_ids``
    (plus optional metadata ``request_id``, ``case_id``, ``tick``, ``gt_regime``).
    Raw GT coordinates, boxes, visibility tables, trajectories, actor lists, and
    depth maps are STRICTLY FORBIDDEN and hard-rejected with
    ``ValueError("D385_FORBIDDEN_GT_FIELD: ...")``.

    Because Colab has no GT boxes, any ``OWN_BOX`` decider output on a visible
    target is marked ``NEEDS_MAC_SCORING`` (counted separately, never inflated as
    correct) and finalized on Mac.

Produces ``e7_analysis_<date>.json`` (directly consumable by
``scripts/evaluation/generate_unified_analysis.py``), ``e7_analysis_<date>.md``,
and headless PNG charts.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "e7_analysis_v1"

ALLOWED_ANSWER_ENTRY_FIELDS = frozenset(
    {
        "request_id",
        "expected_answer",
        "expected_camera_ids",
        "expected_detection_ids",
        "case_id",
        "tick",
        "gt_regime",
    }
)

FORBIDDEN_GT_FIELDS = frozenset(
    {
        "gt_visible",
        "gt_boxes",
        "actors",
        "depth",
        "visibility",
        "trajectories",
        "world_xy",
        "gt_body_box",
    }
)


def _scan_forbidden_gt_fields(obj: Any, path: str) -> None:
    """Recursively reject any forbidden GT field anywhere inside a Colab answer table."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_GT_FIELDS:
                raise ValueError(
                    f"D385_FORBIDDEN_GT_FIELD: forbidden GT field {k!r} found at {path or '<root>'}. "
                    "Colab answer tables must be label-only (D385)."
                )
            _scan_forbidden_gt_fields(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _scan_forbidden_gt_fields(item, f"{path}[{idx}]")


def validate_colab_answer_entry(answer_entry: dict[str, Any], *, key: str = "") -> None:
    """Enforce D385 strict field allowlist and forbidden-GT-field rejection on one entry."""
    if not isinstance(answer_entry, dict):
        raise ValueError(f"D385_INVALID_ANSWER_ENTRY: entry {key!r} must be a dict")
    _scan_forbidden_gt_fields(answer_entry, key or "<entry>")
    unknown = set(answer_entry.keys()) - ALLOWED_ANSWER_ENTRY_FIELDS
    if unknown:
        raise ValueError(
            f"D385_DISALLOWED_ANSWER_FIELD: entry {key!r} contains non-allowlisted fields {sorted(unknown)}. "
            f"Allowed fields: {sorted(ALLOWED_ANSWER_ENTRY_FIELDS)}"
        )


def validate_colab_answer_table(answer_table: dict[str, Any]) -> None:
    """Validate an entire Colab answer table against D385 allowlist and forbidden GT fields."""
    if not isinstance(answer_table, dict):
        raise ValueError("D385_INVALID_ANSWER_TABLE: answer table must be a JSON object mapping request_id -> entry")
    for k in answer_table:
        if k in FORBIDDEN_GT_FIELDS:
            raise ValueError(
                f"D385_FORBIDDEN_GT_FIELD: top-level key {k!r} is forbidden in Colab answer table (D385)."
            )
    for req_id, entry in answer_table.items():
        validate_colab_answer_entry(entry, key=str(req_id))


def _expected_dets_for_camera(raw_expected_dets: Any, cam: str | None) -> set[str] | None:
    if raw_expected_dets is None:
        return None
    if isinstance(raw_expected_dets, dict):
        if cam is None:
            return set()
        vals = raw_expected_dets.get(cam)
        return set(vals) if isinstance(vals, (list, tuple, set)) else set()
    if isinstance(raw_expected_dets, (list, tuple, set)):
        return set(raw_expected_dets)
    return set()


def score_single_decision(
    decision_record: dict[str, Any],
    answer_entry: dict[str, Any],
) -> dict[str, Any]:
    """Score one E7 decider output against one D385 label-only answer-table entry.

    Uses ONLY ``expected_answer``, ``expected_camera_ids``, and pre-matched
    ``expected_detection_ids`` (never ``gt_visible`` or ``gt_boxes``).
    When the decider outputs ``OWN_BOX`` on a visible target (cannot be scored
    without GT boxes), returns ``outcome="NEEDS_MAC_SCORING"`` with
    ``correct=False`` so accuracy is never inflated.
    """
    validate_colab_answer_entry(answer_entry, key=str(decision_record.get("request_id", "")))

    parsed = decision_record.get("parsed")
    if parsed is None:
        return {
            "outcome": "FALLBACK",
            "correct": False,
            "fallback_reason": decision_record.get("fallback_reason"),
        }

    ans = parsed.get("answer")
    cam = parsed.get("camera_id")
    det_id = parsed.get("detection_id")

    expected_answer = answer_entry.get("expected_answer")
    expected_cams = set(answer_entry.get("expected_camera_ids") or [])
    raw_expected_dets = answer_entry.get("expected_detection_ids")

    is_blind_expected = expected_answer == "NOT_VISIBLE" or (expected_answer is None and not expected_cams)
    if is_blind_expected:
        if ans == "NOT_VISIBLE":
            return {"outcome": "BLIND_OK", "correct": True}
        if ans == "UNCERTAIN":
            return {"outcome": "BLIND_UNCERTAIN", "correct": False}
        return {"outcome": "FALSE_LOCK", "correct": False}

    if expected_answer == "UNCERTAIN":
        if ans == "UNCERTAIN":
            return {"outcome": "CORRECT", "correct": True}
        if ans == "OWN_BOX":
            return {"outcome": "NEEDS_MAC_SCORING", "correct": False, "needs_mac_scoring": True}
        return {"outcome": "MISMATCH", "correct": False}

    # Target is expected present/visible (or occluded on expected camera)
    if ans in ("NOT_VISIBLE", "UNCERTAIN"):
        return {"outcome": "LOST", "correct": False}
    if ans == "OWN_BOX":
        return {"outcome": "NEEDS_MAC_SCORING", "correct": False, "needs_mac_scoring": True}
    if ans == "STILL_HERE_OCCLUDED":
        hit_cam = cam in expected_cams
        return {"outcome": "CORRECT" if hit_cam else "WRONG_CAMERA", "correct": hit_cam}
    if ans == "SELECT":
        if cam not in expected_cams:
            return {"outcome": "WRONG_CAMERA", "correct": False}
        exp_dets = _expected_dets_for_camera(raw_expected_dets, cam)
        if exp_dets is None:
            return {"outcome": "GT_UNKNOWN", "correct": False}
        hit = det_id in exp_dets
        return {"outcome": "CORRECT" if hit else "WRONG_PERSON", "correct": hit}

    return {"outcome": "FALLBACK", "correct": False}


def score_e7_comparison(
    comparison_run: dict[str, Any],
    answer_table: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Attach accuracy metrics to an ``e7_decider_eval.run_acceleration_comparison`` dict (scoring side ONLY)."""
    validate_colab_answer_table(answer_table)

    out = dict(comparison_run)
    for mode_key in ("accelerated", "unaccelerated"):
        block = dict(comparison_run[mode_key])
        records = block.get("records") or []
        scored = 0
        correct = 0
        wrong_target = 0
        blind_lock = 0
        needs_mac_scoring = 0
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
            if res["outcome"] == "NEEDS_MAC_SCORING":
                needs_mac_scoring += 1
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
        block["needs_mac_scoring_count"] = needs_mac_scoring
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
        "| Model | Mode | Accel p50/p95 (ms) | Unaccel p50/p95 (ms) | Accel Fallback | Unaccel Fallback | Agreement | DP Acc (Accel) | Needs Mac Scoring | Sample (Acc/Unacc) |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for m in report["models"]:
        a, u = m["accelerated"], m["unaccelerated"]
        lines.append(
            f"| {m['label']} | `{m['input_mode']}` | "
            f"{a['latency_p50_ms']} / {a['latency_p95_ms']} | "
            f"{u['latency_p50_ms']} / {u['latency_p95_ms']} | "
            f"{a['format_fallback_rate']:.4f} | {u['format_fallback_rate']:.4f} | "
            f"{m['decision_agreement_vs_unaccelerated']} | {a.get('decision_point_accuracy')} | "
            f"{a.get('needs_mac_scoring_count', 0)} | "
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
