"""Plot the fixed-clock C6 proposals and their explicitly repeated nodes."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

root = Path(__file__).resolve().parents[1]
data = json.loads((root / "docs/engineering/C6_FIXED_FRAME_SCREEN_20261017.json").read_text())
parent = json.loads((root / "docs/engineering/C6_PRESCREEN_20261017.json").read_text())
routes = data["candidates"]
fig, axes = plt.subplots(3, 5, figsize=(16, 10), sharex=True, sharey=True)
allpoints = np.array([p[:2] for r in routes for p in r["waypoints_m"]])
lo = allpoints.min(axis=0) - 0.5
hi = allpoints.max(axis=0) + 0.5
grid = np.array([[r["grid_xy"][0] * 0.25, r["grid_xy"][1] * 0.25] for r in parent["grid_evidence"]])
grid = grid[np.all((grid >= lo) & (grid <= hi), axis=1)]
for ax, r in zip(axes.flat, routes, strict=True):
    p = np.array(r["waypoints_m"])
    ax.scatter(grid[:, 0], grid[:, 1], s=3, c="#ddd", zorder=0)
    ax.plot(p[:, 0], p[:, 1], color="#4576a5", lw=1.5)
    b = np.array([s["foot_position_m"] for s in r["samples"] if not s["visible_cameras"]])
    ax.scatter(b[:, 0], b[:, 1], s=7, color="#c24747")
    ax.scatter(*p[0, :2], marker="o", color="#18814e", s=40, zorder=3)
    ax.scatter(*p[-1, :2], marker="s", color="#7426a0", s=35, zorder=3)
    ax.set_title(
        f"{r['benchmark_id'][-3:]} / gap {r['raw_gap_id'].split('-')[-1]}\n"
        f"{r['prescreen']['configured_render_duration_s']:.2f}s, "
        f"turns={r['turns_in_blind']}, repeated nodes={r['revisited_grid_node_count']}",
        fontsize=9,
    )
    ax.set_aspect("equal")
    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.tick_params(labelsize=7)
for ax in axes[-1]:
    ax.set_xlabel("X (m)")
for ax in axes[:, 0]:
    ax.set_ylabel("Y (m)")
fig.suptitle(
    "C6: 15 proposed frame-qualified routes (NOT RENDERED / coordinator review pending)\n"
    "All CLASS101 → CORRIDOR_02; fixed 5 Hz, phase 0 s, speed 1.5 m/s",
    fontsize=13,
)
fig.text(
    0.5,
    0.01,
    "Green circle: start | Purple square: end | Red: blind render frames | "
    "Blue: original polyline | Grey: source-supported grid\n"
    "All routes have between-frame visible fragments; C7 recheck pending; "
    "not certified for navigation.",
    ha="center",
    fontsize=9,
)
fig.tight_layout(rect=(0, 0.05, 1, 0.94))
fig.savefig(root / "docs/engineering/C6_FIXED_FRAME_ROUTES_20261017.png", dpi=150)
plt.close(fig)
