"""Unified Analysis Generator (#731 item 6).

Single CLI command that reads ONLY source files (frozen E5 report JSON, AO-L
zero-latency rescore JSON, optional E7 analysis JSON, optional E6 verdict JSON,
optional #672 target-tracking JSON) and emits:
  1. ``unified_analysis.json`` validated against ``configs/evaluation/unified_analysis_schema_v1.json``
  2. ``unified_analysis.md`` (five-way comparison table, E6 verdict verbatim/pending,
     latency breakdown, hardware provenance, identity=UNCONFIRMED)
  3. Headless PNG charts (via matplotlib ``Agg`` backend) unless ``--no-charts`` is passed.

No numbers are fabricated or recomputed from raw GT here; every metric is read
directly from its recorded source file and linked via ``provenance_source_id``.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = ROOT / "configs" / "evaluation" / "unified_analysis_schema_v1.json"
DEFAULT_DATAPACK_MANIFEST_SHA = "4eee05ba92ac954d4916f3000bd0d7c011297a75253ffe860605e74bca881b98"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def current_git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        ).strip()
        return out if out else "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def validate_against_schema(doc: dict, schema: dict) -> list[str]:
    """Validate ``doc`` against ``unified_analysis_schema_v1.json``.

    Uses ``jsonschema`` when available and falls back to a built-in recursive
    subset validator covering type/const/enum/required/additionalProperties/items.
    """
    try:
        import jsonschema  # type: ignore

        v = jsonschema.Draft202012Validator(schema)
        return [f"{list(e.path)}: {e.message}" for e in v.iter_errors(doc)]
    except ImportError:
        pass

    errors: list[str] = []

    def _type_ok(val, expected: str) -> bool:
        if expected == "null":
            return val is None
        if expected == "boolean":
            return isinstance(val, bool)
        if expected == "integer":
            return isinstance(val, int) and not isinstance(val, bool)
        if expected == "number":
            return isinstance(val, (int, float)) and not isinstance(val, bool)
        if expected == "string":
            return isinstance(val, str)
        if expected == "array":
            return isinstance(val, list)
        if expected == "object":
            return isinstance(val, dict)
        return True

    def _check(val, sub: dict, path: str) -> None:
        if "const" in sub and val != sub["const"]:
            errors.append(f"{path}: expected const {sub['const']!r}, got {val!r}")
            return
        if "enum" in sub and val not in sub["enum"]:
            errors.append(f"{path}: value {val!r} not in enum {sub['enum']!r}")
        if "type" in sub:
            types = sub["type"] if isinstance(sub["type"], list) else [sub["type"]]
            if not any(_type_ok(val, t) for t in types):
                errors.append(f"{path}: expected type {types}, got {type(val).__name__}")
                return
        if isinstance(val, str) and "minLength" in sub and len(val) < sub["minLength"]:
            errors.append(f"{path}: string shorter than minLength {sub['minLength']}")
        if isinstance(val, dict):
            for req in sub.get("required") or []:
                if req not in val:
                    errors.append(f"{path}: missing required key {req!r}")
            props = sub.get("properties") or {}
            if sub.get("additionalProperties") is False:
                extra = set(val.keys()) - set(props.keys())
                if extra:
                    errors.append(f"{path}: unexpected keys {sorted(extra)}")
            for k, v in val.items():
                if k in props:
                    _check(v, props[k], f"{path}.{k}")
        if isinstance(val, list) and "items" in sub:
            for idx, item in enumerate(val):
                _check(item, sub["items"], f"{path}[{idx}]")

    _check(doc, schema, "$")
    return errors


def _empty_metrics() -> dict:
    return {
        "wrong_target_s": None,
        "blind_lock_s": None,
        "correct_rate": None,
        "decision_point_accuracy": None,
        "latency_p50_ms": None,
        "latency_p95_ms": None,
        "expired_rate": None,
        "format_fallback_rate": None,
        "n_segments": None,
        "n_decision_points": None,
    }


def _display_path(path: Path | None, datapack_root: Path | None) -> str:
    if path is None:
        return "MISSING"
    if datapack_root is not None:
        try:
            rel = path.resolve().relative_to(datapack_root.resolve())
            return "local/" + rel.as_posix()
        except ValueError:
            pass
    try:
        rel = path.resolve().relative_to(ROOT.resolve())
        return rel.as_posix()
    except ValueError:
        return path.name


def build_unified_analysis(
    *,
    e5_report_path: Path | None = None,
    aol_zero_latency_path: Path | None = None,
    e7_analysis_path: Path | None = None,
    e6_verdict_path: Path | None = None,
    target_672_path: Path | None = None,
    answer_table_path: Path | None = None,
    datapack_root: Path | None = None,
    datapack_manifest_sha256: str | None = None,
    platform: str = "Windows-smoke-only",
    is_official_benchmark: bool = False,
    hardware_note: str | None = None,
    dataset_scope: str = "e3_16_segments",
) -> dict:
    sources: list[dict] = []
    e5_doc = None
    aol_zl_doc = None
    e7_doc = None
    e6_doc = None
    t672_doc = None

    def _register_json(source_id: str, kind: str, path: Path | None):
        if path is not None and path.is_file():
            sources.append(
                {
                    "source_id": source_id,
                    "kind": kind,
                    "path": _display_path(path, datapack_root),
                    "sha256": sha256_file(path),
                    "status": "LOADED",
                }
            )
            return json.loads(path.read_text(encoding="utf-8"))
        sources.append(
            {
                "source_id": source_id,
                "kind": kind,
                "path": _display_path(path, datapack_root),
                "sha256": "UNKNOWN",
                "status": "MISSING",
            }
        )
        return None

    e5_doc = _register_json("e5_report", "frozen_record", e5_report_path)
    aol_zl_doc = _register_json("aol_zero_latency", "aol_zero_latency", aol_zero_latency_path)
    e7_doc = _register_json("e7_analysis", "e7_analysis", e7_analysis_path)
    e6_doc = _register_json("e6_verdict", "e6_verdict", e6_verdict_path)
    t672_doc = _register_json("target_tracking_672", "other", target_672_path)

    if answer_table_path is not None and answer_table_path.is_file():
        sources.append(
            {
                "source_id": "e3_answer_table",
                "kind": "answer_table",
                "path": _display_path(answer_table_path, datapack_root),
                "sha256": sha256_file(answer_table_path),
                "status": "LOADED",
            }
        )

    entries: list[dict] = []

    # 1. Script Answer reference entry
    ref_metrics = _empty_metrics()
    if e5_doc is not None:
        b1 = (e5_doc.get("per_arm") or {}).get("B1") or {}
        ref_metrics.update(
            wrong_target_s=0.0,
            blind_lock_s=0.0,
            correct_rate=1.0,
            decision_point_accuracy=1.0,
            n_segments=len(b1.get("segments") or []) or len(e5_doc.get("cases") or []),
            n_decision_points=b1.get("dp_total"),
        )
    entries.append(
        {
            "party_id": "script_answer",
            "label": "Script Answer (GT Reference)",
            "category": "reference",
            "status": "AVAILABLE" if e5_doc is not None else "PLACEHOLDER",
            "acceleration": "n/a",
            "metrics": ref_metrics,
            "provenance_source_id": "e3_answer_table" if (answer_table_path and answer_table_path.is_file()) else ("e5_report" if e5_doc else None),
            "notes": "Scoring-side reference only (identity UNCONFIRMED).",
        }
    )

    # 2. Frozen E5 arms: B1, AO, AOL
    def _from_e5_arm(arm_key: str, party_id: str, label: str, category: str, accel: str, notes: str) -> dict:
        m = _empty_metrics()
        if e5_doc is None or arm_key not in (e5_doc.get("per_arm") or {}):
            return {
                "party_id": party_id,
                "label": label,
                "category": category,
                "status": "MISSING",
                "acceleration": accel,
                "metrics": m,
                "provenance_source_id": None,
                "notes": notes,
            }
        pa = e5_doc["per_arm"][arm_key]
        dp_tot = pa.get("dp_total")
        dp_ok = pa.get("dp_correct")
        e5_calls = pa.get("e5_calls") or {}
        n_calls = e5_calls.get("calls") or 0
        exp_rate = round(e5_calls["expired"] / n_calls, 4) if n_calls else (0.0 if arm_key == "AO" else None)
        fmt_rate = e5_calls.get("format_return_rate") if e5_calls else None
        m.update(
            wrong_target_s=pa.get("wrong_person_s"),
            blind_lock_s=pa.get("false_lock_s"),
            correct_rate=pa.get("follow_rate"),
            decision_point_accuracy=round(dp_ok / dp_tot, 4) if (dp_ok is not None and dp_tot) else None,
            latency_p50_ms=pa.get("latency_ms_p50"),
            latency_p95_ms=pa.get("latency_ms_p95"),
            expired_rate=exp_rate,
            format_fallback_rate=fmt_rate,
            n_segments=len(pa.get("segments") or []),
            n_decision_points=dp_tot,
        )
        return {
            "party_id": party_id,
            "label": label,
            "category": category,
            "status": "AVAILABLE",
            "acceleration": accel,
            "metrics": m,
            "provenance_source_id": "e5_report",
            "notes": notes,
        }

    entries.append(_from_e5_arm("B1", "b1_rule", "B1 Rule Baseline", "rule", "none", "Frozen E3/E5 rule baseline."))
    entries.append(_from_e5_arm("AO", "api_ao", "API AO (Offline, K=3)", "api", "api_remote", "Frozen E5 offline A-open arm."))
    entries.append(_from_e5_arm("AOL", "api_aol", "API AO-L (SimLive, K=1)", "api", "api_remote", "Frozen E5 simulated-live arm."))

    # 3. AO-L Zero-Latency approximation
    zl_metrics = _empty_metrics()
    if aol_zl_doc is not None and isinstance(aol_zl_doc.get("summary"), dict):
        s = aol_zl_doc["summary"]
        zl_metrics.update(
            wrong_target_s=s.get("zero_latency_aol_wrong_person_s"),
            blind_lock_s=s.get("zero_latency_aol_false_lock_s"),
            correct_rate=s.get("zero_latency_aol_follow_rate"),
            decision_point_accuracy=s.get("zero_latency_aol_dp_accuracy"),
            latency_p50_ms=0.0,
            latency_p95_ms=0.0,
            expired_rate=0.0,
            format_fallback_rate=0.0,
            n_segments=s.get("n_segments"),
            n_decision_points=s.get("dp_total"),
        )
        entries.append(
            {
                "party_id": "api_aol_zero_latency",
                "label": "API AO-L Zero-Latency (Approx)",
                "category": "api",
                "status": "AVAILABLE",
                "acceleration": "none",
                "metrics": zl_metrics,
                "provenance_source_id": "aol_zero_latency",
                "notes": aol_zl_doc.get("approximation_note", "Approximation: tracker divergence not re-simulated."),
            }
        )
    else:
        entries.append(
            {
                "party_id": "api_aol_zero_latency",
                "label": "API AO-L Zero-Latency (Approx)",
                "category": "api",
                "status": "MISSING",
                "acceleration": "none",
                "metrics": zl_metrics,
                "provenance_source_id": None,
                "notes": "Run scripts/evaluation/rescore_aol_zero_latency.py to populate.",
            }
        )

    # 4. Local / Colab E7 models (from e7_analysis JSON if provided, else PLACEHOLDERs)
    per_model_latency_ms: list[dict] = []
    if e7_doc is not None and isinstance(e7_doc.get("models"), list) and e7_doc["models"]:
        for mdoc in e7_doc["models"]:
            party_id = str(mdoc.get("party_id") or mdoc.get("model_id") or "local_model")
            cat = str(mdoc.get("category") or "local_vlm")
            if cat not in ("local_option", "local_vlm", "local_diffusion"):
                cat = "local_vlm"
            acc_run = mdoc.get("accelerated") or {}
            unacc_run = mdoc.get("unaccelerated") or {}
            em = _empty_metrics()
            em.update(
                wrong_target_s=acc_run.get("wrong_target_s"),
                blind_lock_s=acc_run.get("blind_lock_s"),
                correct_rate=acc_run.get("correct_rate"),
                decision_point_accuracy=acc_run.get("decision_point_accuracy"),
                latency_p50_ms=acc_run.get("latency_p50_ms"),
                latency_p95_ms=acc_run.get("latency_p95_ms"),
                expired_rate=acc_run.get("expired_rate"),
                format_fallback_rate=acc_run.get("format_fallback_rate"),
                n_segments=acc_run.get("n_segments"),
                n_decision_points=acc_run.get("n_decision_points"),
            )
            entries.append(
                {
                    "party_id": party_id,
                    "label": str(mdoc.get("label") or party_id),
                    "category": cat,
                    "status": "AVAILABLE",
                    "acceleration": str(acc_run.get("acceleration_label") or "cuda_bf16"),
                    "metrics": em,
                    "provenance_source_id": "e7_analysis",
                    "notes": str(mdoc.get("notes") or ""),
                }
            )
            hw_label = str((e7_doc.get("hardware") or {}).get("gpu_name") or "Colab")
            for mode_key, run_obj in (("accelerated", acc_run), ("unaccelerated", unacc_run)):
                if run_obj:
                    per_model_latency_ms.append(
                        {
                            "party_id": party_id,
                            "acceleration": mode_key,
                            "p50_ms": run_obj.get("latency_p50_ms"),
                            "p95_ms": run_obj.get("latency_p95_ms"),
                            "format_fallback_rate": run_obj.get("format_fallback_rate"),
                            "decision_agreement_vs_unaccelerated": mdoc.get("decision_agreement_vs_unaccelerated")
                            if mode_key == "accelerated"
                            else 1.0,
                            "sample_size": run_obj.get("sample_size"),
                            "hardware": hw_label if mode_key == "accelerated" else str((e7_doc.get("hardware") or {}).get("cpu_model") or "CPU"),
                        }
                    )
    else:
        for pid, lbl, cat in (
            ("laya_text", "Laya Text-Only (Colab E7)", "local_option"),
            ("qwen_vl", "Qwen-VL 2-8B (Colab E7)", "local_vlm"),
            ("diffusion_vlm", "Vision Diffusion LM (Colab E7)", "local_diffusion"),
        ):
            entries.append(
                {
                    "party_id": pid,
                    "label": lbl,
                    "category": cat,
                    "status": "PLACEHOLDER",
                    "acceleration": "cuda_bf16",
                    "metrics": _empty_metrics(),
                    "provenance_source_id": None,
                    "notes": "Pending Colab Pro execution of notebooks/e7_colab_decider_eval.ipynb.",
                }
            )
            for mode_key in ("accelerated", "unaccelerated"):
                per_model_latency_ms.append(
                    {
                        "party_id": pid,
                        "acceleration": mode_key,
                        "p50_ms": None,
                        "p95_ms": None,
                        "format_fallback_rate": None,
                        "decision_agreement_vs_unaccelerated": None,
                        "sample_size": None,
                        "hardware": "PLACEHOLDER",
                    }
                )

    # 5. Latency breakdown
    aol_pa = (e5_doc.get("per_arm") or {}).get("AOL") if e5_doc else None
    ao_pa = (e5_doc.get("per_arm") or {}).get("AO") if e5_doc else None
    b1_pa = (e5_doc.get("per_arm") or {}).get("B1") if e5_doc else None
    aol_calls = (aol_pa or {}).get("e5_calls") or {}
    zl_sum = (aol_zl_doc or {}).get("summary") or {}
    zl_calls = zl_sum.get("calls") or {}

    actual_rate = zl_sum.get("actual_aol_follow_rate")
    if actual_rate is None and aol_pa is not None:
        actual_rate = aol_pa.get("follow_rate")
    zl_rate = zl_sum.get("zero_latency_aol_follow_rate")
    delta_rate = zl_sum.get("delta_follow_rate")
    if delta_rate is None and actual_rate is not None and zl_rate is not None:
        delta_rate = round(zl_rate - actual_rate, 4)

    exp_calls = zl_calls.get("actual_expired_calls", aol_calls.get("expired"))
    tot_calls = zl_calls.get("total_calls", aol_calls.get("calls"))
    exp_rate = zl_calls.get("actual_expired_rate")
    if exp_rate is None and exp_calls is not None and tot_calls:
        exp_rate = round(exp_calls / tot_calls, 4)

    latency_status = "AVAILABLE" if (aol_zl_doc is not None or e7_doc is not None) else ("PLACEHOLDER" if e5_doc is not None else "MISSING")

    # 6. E6 Verdict (verbatim from source if present, else PENDING)
    if e6_doc is not None:
        e6_verdict = {
            "status": "AVAILABLE",
            "preregistered_verdict_label": str(e6_doc.get("preregistered_verdict_label") or "UNKNOWN"),
            "verbatim_verdict_text": str(e6_doc.get("verbatim_verdict_text") or ""),
            "effective_families": e6_doc.get("effective_families"),
            "unique_decision_points": e6_doc.get("unique_decision_points"),
            "skew_sensitivity_flag": e6_doc.get("skew_sensitivity_flag"),
            "provenance_source_id": "e6_verdict",
        }
    else:
        e6_verdict = {
            "status": "PENDING_PR726_AND_RUN",
            "preregistered_verdict_label": "PENDING",
            "verbatim_verdict_text": "PENDING (awaiting PR #726 merge and #732 Mac execution)",
            "effective_families": None,
            "unique_decision_points": None,
            "skew_sensitivity_flag": None,
            "provenance_source_id": None,
        }

    # 7. #672 Target tracking (if present, else PENDING)
    if t672_doc is not None:
        target_tracking_672 = {
            "status": "AVAILABLE",
            "targets": list(t672_doc.get("targets") or []),
        }
    else:
        target_tracking_672 = {
            "status": "PENDING_676_AND_RUN",
            "targets": [],
        }

    if hardware_note is None:
        hardware_note = (
            "Official numbers come only from Colab (E7) and Mac (#732); "
            "Windows RTX 3060 is smoke-test only."
        )

    return {
        "schema_version": "unified_analysis_v1",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": current_git_commit(),
        "datapack_manifest_sha256": datapack_manifest_sha256 or DEFAULT_DATAPACK_MANIFEST_SHA,
        "identity_status": "UNCONFIRMED",
        "hardware_provenance": {
            "platform": platform,
            "is_official_benchmark": bool(is_official_benchmark),
            "note": hardware_note,
        },
        "sources": sources,
        "five_way_comparison": {
            "dataset_scope": dataset_scope,
            "entries": entries,
        },
        "latency_breakdown": {
            "status": latency_status,
            "aol_zero_latency_approx": {
                "is_approximation": True,
                "approximation_note": str(
                    (aol_zl_doc or {}).get("approximation_note")
                    or "Re-scored existing AO-L responses applied at query time; tracker state divergence is not re-simulated."
                ),
                "api_aol_actual_correct_rate": actual_rate,
                "api_aol_zero_latency_correct_rate": zl_rate,
                "delta_correct_rate": delta_rate,
                "api_aol_expired_calls": exp_calls,
                "api_aol_total_calls": tot_calls,
                "api_aol_expired_rate": exp_rate,
                "api_ao_offline_wrong_target_s": (ao_pa or {}).get("wrong_person_s"),
                "b1_wrong_target_s": (b1_pa or {}).get("wrong_person_s"),
            },
            "per_model_latency_ms": per_model_latency_ms,
        },
        "e6_verdict": e6_verdict,
        "target_tracking_672": target_tracking_672,
    }


def _fmt(v, digits: int = 3) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def render_markdown(doc: dict) -> str:
    hw = doc["hardware_provenance"]
    lb = doc["latency_breakdown"]["aol_zero_latency_approx"]
    e6 = doc["e6_verdict"]
    lines = [
        "# Unified Experiment Analysis (`unified_analysis_v1`)",
        "",
        f"- Generated (UTC): `{doc['generated_at_utc']}`",
        f"- Git commit: `{doc['git_commit']}`",
        f"- Datapack MANIFEST SHA-256: `{doc['datapack_manifest_sha256']}`",
        f"- Identity status: **`{doc['identity_status']}`**",
        f"- Hardware provenance: `{hw['platform']}` (official benchmark: `{hw['is_official_benchmark']}`) — {hw['note']}",
        "",
        f"## Five-Way Comparison (`{doc['five_way_comparison']['dataset_scope']}`)",
        "",
        "| Party | Category | Status | Accel | Follow Rate | Wrong-Target (s) | Blind-Lock (s) | DP Acc | p50 / p95 (ms) | Expired Rate | Fallback Rate | Source |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for e in doc["five_way_comparison"]["entries"]:
        m = e["metrics"]
        lat = f"{_fmt(m['latency_p50_ms'], 0)} / {_fmt(m['latency_p95_ms'], 0)}"
        lines.append(
            f"| {e['label']} | {e['category']} | {e['status']} | {e['acceleration']} | "
            f"{_fmt(m['correct_rate'], 4)} | {_fmt(m['wrong_target_s'], 2)} | {_fmt(m['blind_lock_s'], 2)} | "
            f"{_fmt(m['decision_point_accuracy'], 4)} | {lat} | {_fmt(m['expired_rate'], 4)} | "
            f"{_fmt(m['format_fallback_rate'], 4)} | `{e['provenance_source_id'] or '—'}` |"
        )

    lines += [
        "",
        "## Latency Breakdown & AO-L Zero-Latency Approximation",
        "",
        f"- Is approximation: `{lb['is_approximation']}` — {lb['approximation_note']}",
        f"- API AO-L actual follow rate: `{_fmt(lb['api_aol_actual_correct_rate'], 4)}`",
        f"- API AO-L zero-latency follow rate (approx): `{_fmt(lb['api_aol_zero_latency_correct_rate'], 4)}`",
        f"- Delta follow rate: `{_fmt(lb['delta_correct_rate'], 4)}`",
        f"- API AO-L expired calls: `{_fmt(lb['api_aol_expired_calls'], 0)} / {_fmt(lb['api_aol_total_calls'], 0)}` "
        f"(rate `{_fmt(lb['api_aol_expired_rate'], 4)}`)",
        f"- Offline AO wrong-target (s): `{_fmt(lb['api_ao_offline_wrong_target_s'], 2)}` vs B1 `{_fmt(lb['b1_wrong_target_s'], 2)}`",
        "",
        "## E6 Preregistered Verdict",
        "",
        f"- Status: `{e6['status']}`",
        f"- Label: `{e6['preregistered_verdict_label']}`",
        f"- Verbatim text: {e6['verbatim_verdict_text']}",
        "",
        "## #672 Multi-Target Tracking (Exploratory)",
        "",
        f"- Status: `{doc['target_tracking_672']['status']}` (targets: `{len(doc['target_tracking_672']['targets'])}`)",
        "",
        "## Provenance Sources",
        "",
        "| Source ID | Kind | Status | Path | SHA-256 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for s in doc["sources"]:
        lines.append(f"| `{s['source_id']}` | {s['kind']} | {s['status']} | `{s['path']}` | `{s['sha256'][:16]}...` |" if len(s["sha256"]) > 20 else f"| `{s['source_id']}` | {s['kind']} | {s['status']} | `{s['path']}` | `{s['sha256']}` |")
    lines.append("")
    return "\n".join(lines)


def generate_charts(doc: dict, out_dir: Path) -> list[Path]:
    """Generate headless PNG summary charts using matplotlib Agg backend."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    avail = [
        e
        for e in doc["five_way_comparison"]["entries"]
        if e["status"] == "AVAILABLE" and e["party_id"] != "script_answer" and e["metrics"]["correct_rate"] is not None
    ]
    if not avail:
        return []

    labels = [e["label"] for e in avail]
    follow = [float(e["metrics"]["correct_rate"]) for e in avail]
    wrong_s = [float(e["metrics"]["wrong_target_s"] or 0.0) for e in avail]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    ax1.barh(labels, follow, color="#2563eb")
    ax1.set_xlim(0, 1.05)
    ax1.set_xlabel("Follow Rate (primary, identity UNCONFIRMED)")
    ax1.set_title("Follow Rate Comparison")
    ax1.invert_yaxis()

    ax2.barh(labels, wrong_s, color="#dc2626")
    ax2.set_xlabel("Wrong-Target Seconds (lower is better)")
    ax2.set_title("Wrong-Target Seconds")
    ax2.invert_yaxis()

    fig.suptitle(f"Unified Analysis ({doc['five_way_comparison']['dataset_scope']}) — {doc['hardware_provenance']['platform']}")
    fig.tight_layout()
    chart_path = out_dir / "unified_five_way_comparison.png"
    fig.savefig(chart_path, dpi=150)
    plt.close(fig)
    return [chart_path]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datapack-root", type=Path, default=None, help="Optional datapack root to auto-locate frozen E5 report and answer table")
    parser.add_argument("--e5-report", type=Path, default=None, help="Path to frozen E5 report.json (e.g. evidence/e5-aol-20261124/report.json)")
    parser.add_argument("--aol-zero-latency", type=Path, default=None, help="Path to AO-L zero-latency rescore JSON")
    parser.add_argument("--e7-analysis", type=Path, default=None, help="Optional path to E7 analysis JSON")
    parser.add_argument("--e6-verdict", type=Path, default=None, help="Optional path to E6 verdict JSON")
    parser.add_argument("--target-672", type=Path, default=None, help="Optional path to #672 target tracking JSON")
    parser.add_argument("--answer-table", type=Path, default=None, help="Optional path to E3 answer table summary/events file")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Path to unified_analysis_schema_v1.json")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output directory for unified_analysis.json, .md, and PNGs")
    parser.add_argument("--platform", type=str, default="Windows-smoke-only")
    parser.add_argument("--official-benchmark", action="store_true")
    parser.add_argument("--dataset-scope", choices=("e3_16_segments", "e6_12_segments", "combined"), default="e3_16_segments")
    parser.add_argument("--no-charts", action="store_true", help="Skip PNG chart generation")
    args = parser.parse_args(argv)

    e5_report = args.e5_report
    answer_table = args.answer_table
    if args.datapack_root is not None:
        if e5_report is None:
            cand = args.datapack_root / "evidence" / "e5-aol-20261124" / "report.json"
            if not cand.is_file():
                cand = args.datapack_root / "evidence" / "e5-20261123" / "report.json"
            if cand.is_file():
                e5_report = cand
        if answer_table is None:
            cand_at = args.datapack_root / "evidence" / "e3-answer-table-20261124" / "events.csv"
            if cand_at.is_file():
                answer_table = cand_at

    doc = build_unified_analysis(
        e5_report_path=e5_report,
        aol_zero_latency_path=args.aol_zero_latency,
        e7_analysis_path=args.e7_analysis,
        e6_verdict_path=args.e6_verdict,
        target_672_path=args.target_672,
        answer_table_path=answer_table,
        datapack_root=args.datapack_root,
        platform=args.platform,
        is_official_benchmark=args.official_benchmark,
        dataset_scope=args.dataset_scope,
    )

    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    errors = validate_against_schema(doc, schema)
    if errors:
        print("SCHEMA_VALIDATION_FAILED:", file=sys.stderr)
        for err in errors:
            print("  -", err, file=sys.stderr)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "unified_analysis.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.out_dir / "unified_analysis.md").write_text(render_markdown(doc), encoding="utf-8")
    if not args.no_charts:
        generate_charts(doc, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
