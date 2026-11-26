#!/usr/bin/env python3
"""Generate Amidst Q1-Q5 report figures from a unified_analysis_v1 JSON file.

Rules enforced:
- Reads ONLY a unified_analysis_v1 JSON file (no raw metric recalculation).
- Never imports or modifies scripts/evaluation/.
- Runs headlessly via matplotlib Agg backend.
- Marks PLACEHOLDER/MISSING entries explicitly and preserves UNCONFIRMED identity
  and Colab-vs-demo hardware caveats on every figure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REQUIRED_TOP_LEVEL_KEYS = (
    "schema_version",
    "datapack_manifest_sha256",
    "identity_status",
    "hardware_provenance",
    "sources",
    "five_way_comparison",
    "latency_breakdown",
    "e6_verdict",
)

EXPECTED_SCHEMA_VERSION = "unified_analysis_v1"

PALETTE = {
    "rule": "#1d4ed8",
    "api_ao": "#dc2626",
    "api_aol": "#ea580c",
    "api_zero": "#0d9488",
    "local": "#7c3aed",
    "reference": "#0f766e",
    "placeholder": "#cbd5e1",
    "placeholder_edge": "#64748b",
    "ink": "#0f172a",
    "muted": "#475569",
    "grid": "#e2e8f0",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_unified_analysis(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Input JSON root must be an object.")
    missing = [k for k in REQUIRED_TOP_LEVEL_KEYS if k not in data]
    if missing:
        raise ValueError(f"Missing required unified_analysis_v1 keys: {', '.join(missing)}")
    if data.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported schema_version: {data.get('schema_version')!r} "
            f"(expected {EXPECTED_SCHEMA_VERSION!r})"
        )
    fw = data.get("five_way_comparison")
    if not isinstance(fw, dict) or not isinstance(fw.get("entries"), list) or not fw["entries"]:
        raise ValueError("five_way_comparison.entries must be a non-empty list.")
    lb = data.get("latency_breakdown")
    if not isinstance(lb, dict) or "aol_zero_latency_approx" not in lb:
        raise ValueError("latency_breakdown.aol_zero_latency_approx is required.")
    return data


def _configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 11.5,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "axes.edgecolor": "#cbd5e1",
            "axes.linewidth": 0.9,
            "xtick.color": PALETTE["ink"],
            "ytick.color": PALETTE["ink"],
            "text.color": PALETTE["ink"],
            "figure.facecolor": "white",
            "axes.facecolor": "#ffffff",
            "svg.fonttype": "none",
        }
    )


def _save_fig(fig: plt.Figure, out_dir: Path, stem: str) -> list[Path]:
    svg_path = out_dir / f"{stem}.svg"
    png_path = out_dir / f"{stem}.png"
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    # Strip matplotlib's trailing spaces on SVG path lines so git diff --check stays clean
    cleaned_svg = "\n".join(line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines()) + "\n"
    svg_path.write_text(cleaned_svg, encoding="utf-8")
    fig.savefig(png_path, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    return [svg_path, png_path]


def _entry_by_id(entries: list[dict[str, Any]], party_id: str) -> dict[str, Any] | None:
    for item in entries:
        if item.get("party_id") == party_id:
            return item
    return None


def build_fig1_e3_e5_summary(data: dict[str, Any], out_dir: Path) -> list[Path]:
    """Fig 1: E3/E5 frozen comparison (B1 Rule vs API AO offline K=3 vs API AO-L simlive K=1)."""
    entries = data["five_way_comparison"]["entries"]
    selected_ids = ["b1_rule", "api_ao", "api_aol"]
    labels = ["B1 Rule\n(E3/E5)", "API AO\n(Offline K=3)", "API AO-L\n(SimLive K=1)"]
    colors = [PALETTE["rule"], PALETTE["api_ao"], PALETTE["api_aol"]]

    wrong_s: list[float] = []
    blind_s: list[float] = []
    correct_pct: list[float] = []
    avail_flags: list[bool] = []

    for pid in selected_ids:
        entry = _entry_by_id(entries, pid)
        m = (entry or {}).get("metrics", {})
        is_avail = bool(entry and entry.get("status") == "AVAILABLE")
        avail_flags.append(is_avail)
        wrong_s.append(float(m["wrong_target_s"]) if m.get("wrong_target_s") is not None else 0.0)
        blind_s.append(float(m["blind_lock_s"]) if m.get("blind_lock_s") is not None else 0.0)
        correct_pct.append(
            float(m["correct_rate"]) * 100.0 if m.get("correct_rate") is not None else 0.0
        )

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
    fig.subplots_adjust(wspace=0.28, bottom=0.22, top=0.82)

    # Left panel: Wrong-Target s & Blind-Lock s (lower is better)
    x = np.arange(len(labels))
    w = 0.34
    bars_wp = axes[0].bar(x - w / 2, wrong_s, width=w, color="#dc2626", alpha=0.88, label="Wrong-Target (s)")
    bars_bl = axes[0].bar(x + w / 2, blind_s, width=w, color="#f59e0b", alpha=0.88, label="Blind-Lock (s)")
    axes[0].set_title("Error Duration (16 segments; lower is better)")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels)
    axes[0].set_ylabel("Seconds (s)")
    axes[0].grid(axis="y", color=PALETTE["grid"], linestyle="--", linewidth=0.8)
    axes[0].set_axisbelow(True)
    axes[0].legend(frameon=False, loc="upper right")
    max_s = max(max(wrong_s, default=1.0), max(blind_s, default=1.0), 10.0)
    axes[0].set_ylim(0, max_s * 1.22)
    for bar, ok in zip(bars_wp, avail_flags):
        val = bar.get_height()
        txt = f"{val:.1f}s" if ok else "N/A"
        axes[0].text(bar.get_x() + bar.get_width() / 2, val + max_s * 0.02, txt, ha="center", va="bottom", fontsize=8.5)
    for bar, ok in zip(bars_bl, avail_flags):
        val = bar.get_height()
        txt = f"{val:.1f}s" if ok else "N/A"
        axes[0].text(bar.get_x() + bar.get_width() / 2, val + max_s * 0.02, txt, ha="center", va="bottom", fontsize=8.5)

    # Right panel: Follow / Correct Rate (%) (higher is better)
    bars_cr = axes[1].bar(x, correct_pct, width=0.52, color=colors, alpha=0.9)
    axes[1].set_title("Follow / Correct Rate (higher is better)")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels)
    axes[1].set_ylabel("Correct Rate (%)")
    axes[1].set_ylim(0, 100)
    axes[1].grid(axis="y", color=PALETTE["grid"], linestyle="--", linewidth=0.8)
    axes[1].set_axisbelow(True)
    for bar, ok in zip(bars_cr, avail_flags):
        val = bar.get_height()
        txt = f"{val:.1f}%" if ok else "PLACEHOLDER"
        axes[1].text(bar.get_x() + bar.get_width() / 2, val + 2.2, txt, ha="center", va="bottom", fontsize=9, fontweight="bold")

    fig.suptitle(
        "E3 / E5 Frozen Evaluation Summary: Rule Baseline vs Open Agent (AO / AO-L)",
        fontsize=13,
        fontweight="bold",
        y=0.96,
    )
    fig.text(
        0.5,
        0.05,
        f"Frozen verdicts unchanged — E3: Not Supported | E5: H8a Not Supported, H8b Not Supported, "
        f"H8c Inconclusive, H8d (AO-L, K=1) Not Supported\n"
        f"Identity: {data['identity_status']} | Datapack MANIFEST SHA-256: {data['datapack_manifest_sha256'][:16]}...",
        ha="center",
        va="center",
        fontsize=8.5,
        color=PALETTE["muted"],
    )
    return _save_fig(fig, out_dir, "fig1_e3_e5_summary")


def build_fig2_five_way_comparison(data: dict[str, Any], out_dir: Path) -> list[Path]:
    """Fig 2: Five-way comparison across reference, rule, API, and local models (PLACEHOLDER slots clearly hatched)."""
    entries = data["five_way_comparison"]["entries"]
    labels = [e.get("label", e.get("party_id", "?")) for e in entries]
    y_pos = np.arange(len(entries))

    fig, ax = plt.subplots(figsize=(11.5, 5.6))
    fig.subplots_adjust(left=0.28, right=0.95, top=0.84, bottom=0.18)

    category_colors = {
        "reference": PALETTE["reference"],
        "rule": PALETTE["rule"],
        "api": PALETTE["api_ao"],
        "local_option": PALETTE["local"],
        "local_vlm": "#6d28d9",
        "local_diffusion": "#9333ea",
    }

    for idx, entry in enumerate(entries):
        status = entry.get("status", "PLACEHOLDER")
        metrics = entry.get("metrics") or {}
        cr = metrics.get("correct_rate")
        pid = entry.get("party_id", "")
        if status == "AVAILABLE" and cr is not None:
            val = float(cr) * 100.0
            color = PALETTE["api_aol"] if pid == "api_aol" else category_colors.get(entry.get("category", ""), PALETTE["rule"])
            if pid == "api_aol_zero_latency":
                color = PALETTE["api_zero"]
            ax.barh(idx, val, height=0.62, color=color, alpha=0.9)
            dp_acc = metrics.get("decision_point_accuracy")
            suffix = f"  (DP acc: {dp_acc * 100:.1f}%)" if dp_acc is not None else ""
            ax.text(val + 1.5, idx, f"{val:.1f}%{suffix}", va="center", ha="left", fontsize=9, fontweight="bold")
        else:
            # Explicit hatched PLACEHOLDER bar so pending #732 slots are unmistakable
            ax.barh(
                idx,
                100.0,
                height=0.62,
                color=PALETTE["placeholder"],
                edgecolor=PALETTE["placeholder_edge"],
                hatch="///",
                alpha=0.45,
                linewidth=0.9,
            )
            tag = "PLACEHOLDER (awaiting #732)" if status == "PLACEHOLDER" else f"{status} (no value)"
            ax.text(50.0, idx, tag, va="center", ha="center", fontsize=8.8, fontweight="bold", color="#334155")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 118)
    ax.set_xlabel("Follow / Correct Rate (%)")
    ax.set_title(
        f"Five-Way Comparison ({data['five_way_comparison'].get('dataset_scope', 'unknown scope')}): "
        "Script Answer / Rule / API / Local Models",
        fontsize=12,
        fontweight="bold",
        pad=12,
    )
    ax.grid(axis="x", color=PALETTE["grid"], linestyle="--", linewidth=0.8)
    ax.set_axisbelow(True)

    e6_text = data.get("e6_verdict", {}).get("verbatim_verdict_text", "PENDING")
    fig.text(
        0.5,
        0.04,
        f"E7 local models are exploratory (Colab Pro GPU latency != local demo latency) | E6 status: {e6_text}\n"
        f"Identity: {data['identity_status']} | Source schema: {data['schema_version']} | "
        f"Datapack SHA-256: {data['datapack_manifest_sha256'][:16]}...",
        ha="center",
        va="center",
        fontsize=8.3,
        color=PALETTE["muted"],
    )
    return _save_fig(fig, out_dir, "fig2_five_way_comparison")


def build_fig3_latency_breakdown(data: dict[str, Any], out_dir: Path) -> list[Path]:
    """Fig 3: Per-model latency (p50/p95 ms) and AO-L zero-latency approximation diagnostic."""
    lb = data["latency_breakdown"]
    per_model = lb.get("per_model_latency_ms") or []
    approx = lb.get("aol_zero_latency_approx") or {}

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.9))
    fig.subplots_adjust(wspace=0.32, bottom=0.22, top=0.82)

    # Left panel: p50 / p95 latency
    ax0 = axes[0]
    if per_model:
        y = np.arange(len(per_model))
        names = [f"{m.get('party_id', '?')}\n({m.get('acceleration', '?')})" for m in per_model]
        max_ms = max(
            [float(m["p95_ms"]) for m in per_model if m.get("p95_ms") is not None]
            + [float(m["p50_ms"]) for m in per_model if m.get("p50_ms") is not None]
            + [12000.0]
        )
        for idx, m in enumerate(per_model):
            p50 = m.get("p50_ms")
            p95 = m.get("p95_ms")
            if p50 is not None and p95 is not None:
                ax0.barh(idx - 0.17, float(p50), height=0.32, color="#2563eb", label="p50 (ms)" if idx == 0 else "")
                ax0.barh(idx + 0.17, float(p95), height=0.32, color="#ef4444", alpha=0.85, label="p95 (ms)" if idx == 0 else "")
                ax0.text(float(p95) + max_ms * 0.02, idx, f"{int(p50)} / {int(p95)} ms", va="center", fontsize=8.2)
            else:
                ax0.barh(
                    idx,
                    max_ms * 0.88,
                    height=0.58,
                    color=PALETTE["placeholder"],
                    edgecolor=PALETTE["placeholder_edge"],
                    hatch="///",
                    alpha=0.45,
                )
                ax0.text(
                    max_ms * 0.44,
                    idx,
                    "PLACEHOLDER (Colab != demo)",
                    va="center",
                    ha="center",
                    fontsize=8.2,
                    fontweight="bold",
                    color="#334155",
                )
        ax0.set_yticks(y)
        ax0.set_yticklabels(names, fontsize=8.8)
        ax0.invert_yaxis()
        ax0.set_xlim(0, max_ms * 1.28)
        ax0.legend(frameon=False, loc="lower right")
    else:
        ax0.text(0.5, 0.5, "No latency entries", ha="center", va="center")
    ax0.set_xlabel("Latency (ms)")
    ax0.set_title("Per-Model Latency (p50 / p95 ms)")
    ax0.grid(axis="x", color=PALETTE["grid"], linestyle="--", linewidth=0.8)
    ax0.set_axisbelow(True)

    # Right panel: AO-L Expired Rate & Zero-Latency Approximation Diagnostic
    ax1 = axes[1]
    actual_cr = approx.get("api_aol_actual_correct_rate")
    zero_cr = approx.get("api_aol_zero_latency_correct_rate")
    exp_rate = approx.get("api_aol_expired_rate")
    exp_calls = approx.get("api_aol_expired_calls")
    tot_calls = approx.get("api_aol_total_calls")

    bar_labels = ["AO-L Actual\nCorrect Rate", "AO-L Zero-Latency\n(APPROXIMATION)", "AO-L Expired\nCall Rate"]
    x1 = np.arange(len(bar_labels))
    vals = [
        float(actual_cr) * 100.0 if actual_cr is not None else None,
        float(zero_cr) * 100.0 if zero_cr is not None else None,
        float(exp_rate) * 100.0 if exp_rate is not None else None,
    ]
    bar_colors = [PALETTE["api_aol"], PALETTE["api_zero"], "#64748b"]

    for i, (v, c) in enumerate(zip(vals, bar_colors)):
        if v is not None:
            ax1.bar(i, v, width=0.52, color=c, alpha=0.9)
            extra = f"\n({exp_calls}/{tot_calls})" if i == 2 and exp_calls is not None and tot_calls is not None else ""
            ax1.text(i, v + 2.5, f"{v:.1f}%{extra}", ha="center", va="bottom", fontsize=8.8, fontweight="bold")
        else:
            ax1.bar(
                i,
                85.0,
                width=0.52,
                color=PALETTE["placeholder"],
                edgecolor=PALETTE["placeholder_edge"],
                hatch="///",
                alpha=0.45,
            )
            ax1.text(i, 42.5, "PLACEHOLDER\n(awaiting #732)", ha="center", va="center", fontsize=8.2, fontweight="bold", color="#334155")

    ax1.set_xticks(x1)
    ax1.set_xticklabels(bar_labels, fontsize=8.8)
    ax1.set_ylim(0, 105)
    ax1.set_ylabel("Percentage (%)")
    ax1.set_title("AO-L Bottleneck & Zero-Latency Diagnostic")
    ax1.grid(axis="y", color=PALETTE["grid"], linestyle="--", linewidth=0.8)
    ax1.set_axisbelow(True)

    fig.suptitle(
        "Latency Breakdown & AO-L Zero-Latency Diagnostic (Approximation)",
        fontsize=13,
        fontweight="bold",
        y=0.96,
    )
    approx_note = approx.get("approximation_note", "Approximation only; tracker state not re-simulated.")
    fig.text(
        0.5,
        0.05,
        f"APPROXIMATION NOTE: {approx_note}\n"
        f"Hardware note: Colab Pro GPU latency != local demo latency | Identity: {data['identity_status']}",
        ha="center",
        va="center",
        fontsize=8.2,
        color=PALETTE["muted"],
    )
    return _save_fig(fig, out_dir, "fig3_latency_breakdown")


def build_all_figures(input_path: Path, out_dir: Path) -> dict[str, Any]:
    if not input_path.is_file():
        raise FileNotFoundError(f"Input JSON not found: {input_path}")
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    data = validate_unified_analysis(raw)

    out_dir.mkdir(parents=True, exist_ok=True)
    _configure_style()

    generated_paths: list[Path] = []
    generated_paths.extend(build_fig1_e3_e5_summary(data, out_dir))
    generated_paths.extend(build_fig2_five_way_comparison(data, out_dir))
    generated_paths.extend(build_fig3_latency_breakdown(data, out_dir))

    try:
        rel_input = input_path.resolve().relative_to(Path(__file__).resolve().parents[2]).as_posix()
    except ValueError:
        rel_input = input_path.name

    manifest = {
        "schema_version": data["schema_version"],
        "input_file": rel_input,
        "input_sha256": sha256_file(input_path),
        "git_commit": data.get("git_commit", "UNKNOWN"),
        "datapack_manifest_sha256": data["datapack_manifest_sha256"],
        "identity_status": data["identity_status"],
        "figures": [
            {
                "filename": p.name,
                "format": p.suffix.lstrip("."),
                "bytes": p.stat().st_size,
                "sha256": sha256_file(p),
            }
            for p in generated_paths
        ],
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_input = Path(__file__).resolve().parent / "sample_placeholder_input.json"
    default_out = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Build Amidst Q1-Q5 report figures from a unified_analysis_v1 JSON file."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input,
        help="Path to unified_analysis_v1 JSON input.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=default_out,
        help="Directory where SVG/PNG figures and manifest.json will be written.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = build_all_figures(args.input, args.out_dir)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Generated {len(manifest['figures'])} figure files in {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
