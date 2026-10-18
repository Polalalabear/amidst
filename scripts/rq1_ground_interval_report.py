"""Generate the RQ1 ground-interval metrics JSON and figures (evaluation only; reads GT).

Order is enforced: frozen predictions are SHA-verified first, then GT is loaded.

    python scripts/rq1_ground_interval_report.py --predictions <C4A predictions json> \
        --out-json docs/engineering/RQ1_GROUND_INTERVAL_RESULTS_20261018.json \
        --fig-dir docs/engineering/figures
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from amidst.evaluation.rq1_ground_interval import (  # noqa: E402
    evaluate_rq1,
    load_frozen_predictions,
    load_ground_truth,
)

BASIS_STYLE = {
    "FOOT_RAY_PIXEL_BAND": ("#0072B2", "o", "Foot pixel band"),
    "HEAD_RAY_HEIGHT_PRIOR": ("#D55E00", "s", "Head-ray height prior"),
}
INK = "#222222"
MUTED = "#666666"


def _style(ax: plt.Axes) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(True, color="#dddddd", linewidth=0.6)
    ax.set_axisbelow(True)


def figure_distance(result: dict, tol: float, path: Path) -> None:
    rows = result["per_observation"]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 6.4), sharex=True)
    for basis, (color, marker, label) in BASIS_STYLE.items():
        rs = [r for r in rows if r["basis"] == basis]
        t = [r["timestamp_s"] for r in rs]
        a1.scatter(
            t,
            [r["distance_to_segment_m"] for r in rs],
            c=color,
            marker=marker,
            s=36,
            edgecolors="white",
            linewidths=0.8,
            label=label,
        )
        a2.scatter(
            t,
            [r["segment_length_m"] for r in rs],
            c=color,
            marker=marker,
            s=36,
            edgecolors="white",
            linewidths=0.8,
            label=label,
        )
    a1.axhline(tol, color=MUTED, linewidth=1.2, linestyle="--")
    a1.text(
        0.01,
        tol,
        f" tolerance {tol:g} m (D5 body radius)",
        color=MUTED,
        va="bottom",
        transform=a1.get_yaxis_transform(),
        fontsize=9,
    )
    a1.set_ylabel("GT contact to segment (m)", color=INK)
    a2.set_ylabel("Interval length (m)", color=INK)
    a2.set_xlabel("Time (s)", color=INK)
    a1.set_title("RQ1: GT floor contact vs. single-camera ground interval", color=INK, loc="left")
    a1.legend(frameon=False, loc="upper center")
    for ax in (a1, a2):
        _style(ax)
        ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(path, dpi=150, metadata={"Software": None})
    plt.close(fig)


def figure_plan(result: dict, track_xy: list[tuple[float, float]], obs: tuple, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(
        [p[0] for p in track_xy],
        [p[1] for p in track_xy],
        color="#999999",
        linewidth=2.5,
        label="GT floor contact (evaluation only)",
        zorder=1,
    )
    seen: set[str] = set()
    for o in obs:
        color, _, label = BASIS_STYLE[o["basis"]]
        s = o["segment"]
        ax.plot(
            [s["near_m"][0], s["far_m"][0]],
            [s["near_m"][1], s["far_m"][1]],
            color=color,
            linewidth=3,
            solid_capstyle="round",
            zorder=2,
            label=label if label not in seen else None,
        )
        seen.add(label)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)", color=INK)
    ax.set_ylabel("y (m)", color=INK)
    ax.set_title("Plan view: predicted intervals along the GT path", color=INK, loc="left")
    ax.legend(frameon=False, loc="best")
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150, metadata={"Software": None})
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("configs/rq1_ground_interval_v1.json"))
    ap.add_argument("--predictions", type=Path, required=True)
    ap.add_argument("--ground-truth", type=Path, help="override the config GT path")
    ap.add_argument("--out-json", type=Path, required=True)
    ap.add_argument("--fig-dir", type=Path, required=True)
    args = ap.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    # 1. Freeze: verify the prediction hash before any GT is opened.
    preds = load_frozen_predictions(args.predictions, cfg["predictions"]["sha256"])
    if preds.run_id != cfg["run_id"]:
        raise SystemExit("run_id mismatch")
    # 2. Only now read GT.
    gt_cfg = cfg["ground_truth"]
    track = load_ground_truth(
        args.ground_truth or Path(gt_cfg["path"]),
        gt_cfg["sha256"],
        preds,
        m_per_unit=cfg["scale"]["m_per_scene_unit"],
        contact_field=gt_cfg["contact_field"],
    )
    tols = cfg["tolerances_m"]
    result = evaluate_rq1(
        preds, track, tols, exact_tol_s=cfg["time_alignment"]["exact_match_tolerance_s"]
    )
    limit = cfg["plane_height_check_tolerance_m"]
    worst = max(abs(r["plane_height_residual_m"]) for r in result["per_observation"])
    if worst > limit:
        raise SystemExit(f"GT/prediction plane height residual {worst:.4f} m exceeds {limit} m")

    out = {
        "schema_version": "office-demo.rq1-ground-interval-results.v1",
        "run_id": preds.run_id,
        "predictions_sha256": preds.sha256,
        "ground_truth_sha256": track.sha256,
        "config_sha256": __import__("hashlib").sha256(args.config.read_bytes()).hexdigest(),
        "tolerances_m": tols,
        "m_per_scene_unit": cfg["scale"]["m_per_scene_unit"],
        "contact_field": gt_cfg["contact_field"],
        "time_alignment": cfg["time_alignment"]["method"],
        "plane_height_max_abs_residual_m": worst,
        **result,
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.fig_dir.mkdir(parents=True, exist_ok=True)
    figure_distance(result, tols["body_radius_d5"], args.fig_dir / "rq1_distance_and_length.png")
    figure_plan(
        result,
        [(p[0], p[1]) for p in track.contact_xyz_m],
        tuple(preds.observations),
        args.fig_dir / "rq1_plan_view.png",
    )
    print(json.dumps(out["summary"]["ALL"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
