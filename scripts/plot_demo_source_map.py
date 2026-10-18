"""Plot C7 source floor, body-centre domains, furniture and opening candidates."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import shape


def paint(ax, geometry, color, *, alpha=1, linewidth=0.4, zorder=1):
    if geometry.is_empty:
        return
    if geometry.geom_type == "Polygon":
        x, y = geometry.exterior.xy
        ax.fill(x, y, color=color, alpha=alpha, zorder=zorder)
        for ring in geometry.interiors:
            x, y = ring.xy
            ax.fill(x, y, color="white", zorder=zorder + 0.1)
    elif geometry.geom_type in {"LineString", "LinearRing"}:
        x, y = geometry.xy
        ax.plot(x, y, color=color, lw=linewidth, zorder=zorder)
    else:
        for piece in getattr(geometry, "geoms", []):
            paint(ax, piece, color, alpha=alpha, linewidth=linewidth, zorder=zorder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    data = json.loads(args.input.read_text())
    variants = data["variants"]
    figure, axes = plt.subplots(
        1, len(variants), figsize=(15, 8), sharex=True, sharey=True, squeeze=False
    )
    for ax, (name, variant) in zip(axes.flat, variants.items(), strict=True):
        paint(ax, shape(data["floor"]["geometry"]), "#e1e5e9")
        for region in variant["regions"]:
            paint(ax, shape(region["geometry"]), "#a2cfac", zorder=2)
        for obstacle in variant["obstacle_footprints"]:
            if not any(
                (obstacle.get("parent") or "").startswith(p)
                for p in data["config"]["furniture_assembly_prefixes"]
            ):
                paint(ax, shape(obstacle["footprint"]), "#59606b", zorder=3)
        for index, item in enumerate(variant["furniture"], 1):
            geometry = shape(item["geometry"])
            paint(ax, geometry, "#c78551", zorder=4)
            centre = geometry.representative_point()
            ax.text(centre.x, centre.y, str(index), ha="center", va="center", fontsize=6, zorder=6)
        for portal in variant["portals"]:
            paint(ax, shape(portal["geometry"]), "#647bd3", alpha=0.65, zorder=5)
        p = variant["parameters"]
        ax.set_title(
            f"{name}: r={p['body_radius_m']} m, h={p['body_height_m']} m\n"
            f"{len(variant['regions'])} connected regions, "
            f"{len(variant['portals'])} opening candidates"
        )
        ax.set_aspect("equal")
        ax.set_xlabel("Source X (m)")
        ax.grid(alpha=0.15)
    axes[0, 0].set_ylabel("Source Y (m)")
    figure.suptitle(
        "C7: source-derived Demo camera neighbourhoods (no annotation / target input)\n"
        "Green: body centres | Grey: source obstacles | "
        "Brown: individual furniture | Blue: geometric openings"
    )
    figure.text(
        0.5,
        0.015,
        "Semantic room / door labels and real navigation NOT CERTIFIED; "
        "outside ROI UNKNOWN; K7 review pending.",
        ha="center",
    )
    figure.tight_layout(rect=(0, 0.07, 1, 0.92))
    figure.savefig(args.output, dpi=150)
    plt.close(figure)


if __name__ == "__main__":
    main()
