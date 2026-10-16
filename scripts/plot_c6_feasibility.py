"""Plot C6 planning evidence, with no source media or inference inputs."""

import argparse
import json
from pathlib import Path


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.suffix != ".png":
        raise ValueError("OUTPUT_MUST_BE_NEW_PNG")
    data = json.loads(args.input.read_text())
    if data["inference_input_eligible"] or data["render_executed"]:
        raise ValueError("C6_PLANNING_ONLY_REQUIRED")
    spacing = data["config"]["grid_spacing_m"]
    scale = data["config"]["metres_per_blender_unit"]
    grid = data["grid_evidence"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 7.2), constrained_layout=True)
    for ax in axes:
        ax.scatter(
            [r["grid_xy"][0] * spacing for r in grid],
            [r["grid_xy"][1] * spacing for r in grid],
            s=7,
            color="#cbd0d6",
            marker="s",
            label="Supported body-clear grid",
        )
        ax.set(xlabel="Source X (m)", ylabel="Source Y (m)", aspect="equal")
        ax.grid(alpha=0.15)
    colors = ("#3465a4", "#d97706", "#8054b5", "#098b78", "#b04465")
    for i, (camera, color) in enumerate(zip(data["calibrations_scene_units"], colors, strict=True)):
        rows = [
            r for r in grid if any(i in indices for indices in r["visible_camera_indices_by_probe"])
        ]
        label = data["config"]["regions"][i]["region_id"]
        axes[0].scatter(
            [r["grid_xy"][0] * spacing for r in rows],
            [r["grid_xy"][1] * spacing for r in rows],
            color=color,
            s=8,
            marker="s",
            alpha=0.8,
            label=label,
        )
        x, y = [camera["camera_to_world"][k][3] * scale for k in (0, 1)]
        for ax in axes:
            ax.scatter([x], [y], marker="^", color=color, edgecolor="black", s=65, zorder=5)
        axes[0].annotate(label, (x, y), xytext=(5, 5), textcoords="offset points", fontsize=7)
    gap_count = 0
    control_count = 0
    for candidate in data["candidates"]:
        samples = candidate["samples"]
        points = [s["foot_position_m"] for s in samples]
        gap = candidate["role"] == "VISIBLE_BLIND_VISIBLE"
        color = "#b55d14" if gap else "#087e51"
        label = None
        if gap:
            gap_count += 1
            if gap_count == 1:
                label = "Visible / blind / visible candidates"
        else:
            control_count += 1
            if control_count == 1:
                label = "Full-probe visible controls"
        axes[1].plot(
            [p[0] for p in points],
            [p[1] for p in points],
            color=color,
            lw=1.0,
            alpha=0.65,
            label=label,
        )
        axes[1].scatter([points[0][0]], [points[0][1]], s=13, color=color)
        if gap:
            blind = [s["foot_position_m"] for s in samples if not s["visible_cameras"]]
            axes[1].scatter(
                [p[0] for p in blind], [p[1] for p in blind], s=5, color="#282d35", zorder=4
            )
    axes[0].set_title("Any of bottom / torso / head probes visible")
    axes[1].set_title(f"{gap_count} gap candidates + {control_count} controls (0.25 m samples)")
    for ax in axes:
        ax.legend(loc="upper left", fontsize=7)
    fig.suptitle(
        "C6 source-mesh feasibility - five camera neighborhoods\n"
        "Planning only: RGB detection, continuous support and navigation unverified",
        fontsize=12,
    )
    fig.savefig(args.output, dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    main()
