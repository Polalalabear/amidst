"""Slide-ready PNG charts for the RQ1 contact report (Traditional Chinese labels)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from amidst.engineering.contact_rq1 import ALL_CAMERAS, ErrorRow, time_series  # noqa: E402

FONT_FALLBACK = [
    "PingFang TC",
    "Heiti TC",
    "Noto Sans CJK TC",
    "Microsoft JhengHei",
    "Arial Unicode MS",
    "DejaVu Sans",
]

# Validated categorical slots (light surface); fixed role -> color, never cycled.
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
MUTED = "#c9c8c2"
VERSION_COLOR = {"v1": "#2a78d6", "v2": "#eb6834"}
VERSION_LABEL = {"v1": "v1 外框底邊", "v2": "v2 遮罩最低點"}
REASON_COLOR = {
    "V1": VERSION_COLOR["v1"],
    "KEPT": VERSION_COLOR["v2"],
    "LOW_INCIDENCE": "#1baf7a",
    "TOUCHES_IMAGE_EDGE": "#eda100",
    "CONTACT_OCCLUDED": "#e87ba4",
}
REASON_LABEL = {
    "KEPT": "保留",
    "LOW_INCIDENCE": "入射角過低",
    "TOUCHES_IMAGE_EDGE": "觸及畫面邊緣",
    "CONTACT_OCCLUDED": "接地點被遮擋",
    "UNSPECIFIED": "未註明",
}
CAMERA_LABEL = {"FRONT": "前方攝影機", "REAR": "後方攝影機"}


def camera_label(camera_id: str) -> str:
    if camera_id == ALL_CAMERAS:
        return "合計"
    suffix = camera_id.rsplit("_", 1)[-1]
    return CAMERA_LABEL.get(suffix, camera_id)


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": FONT_FALLBACK,
            "axes.unicode_minus": False,
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": TEXT_SECONDARY,
            "axes.titlecolor": TEXT_PRIMARY,
            "xtick.color": TEXT_SECONDARY,
            "ytick.color": TEXT_SECONDARY,
            "text.color": TEXT_PRIMARY,
            "font.size": 12,
            "axes.titlesize": 14,
            "axes.titleweight": "semibold",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
        }
    )


def _grid(axis: Axes, which: Literal["x", "y"] = "y") -> None:
    axis.grid(axis=which, color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)


def _nan(value: float | None) -> float:
    return math.nan if value is None else value


def error_over_time_chart(rows: Sequence[ErrorRow], output: Path) -> Path:
    _style()
    series = time_series(rows)
    cameras = sorted(series)
    figure, axes = plt.subplots(
        len(cameras), 1, figsize=(11, 3.4 * len(cameras)), sharex=True, squeeze=False
    )
    top = max(
        [v for points in series.values() for _, a, b in points for v in (a, b) if v is not None],
        default=1.0,
    )
    for axis, camera in zip(axes[:, 0], cameras, strict=True):
        points = series[camera]
        times = [t for t, _, _ in points]
        for version, index in (("v1", 1), ("v2", 2)):
            values = [_nan(point[index]) for point in points]
            axis.plot(
                times,
                values,
                color=VERSION_COLOR[version],
                linewidth=2,
                marker="o",
                markersize=4.5,
                markeredgecolor=SURFACE,
                markeredgewidth=1,
                label=VERSION_LABEL[version],
            )
        rejected = [t for t, v1, v2 in points if v2 is None]
        axis.scatter(
            rejected,
            [0.0] * len(rejected),
            marker="|",
            s=90,
            color=TEXT_SECONDARY,
            linewidths=1.5,
            label="v2 無位置（被拒絕）",
            clip_on=False,
            zorder=3,
        )
        axis.set_ylim(0, top * 1.15)
        axis.set_ylabel("誤差（公尺）")
        axis.set_title(camera_label(camera), loc="left")
        _grid(axis)
    axes[-1, 0].set_xlabel("時間（秒）")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper right", ncol=3, bbox_to_anchor=(0.99, 0.995))
    figure.suptitle(
        "接地點誤差隨時間變化：v1 vs v2", x=0.01, ha="left", fontsize=16, fontweight="semibold"
    )
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    figure.savefig(output, dpi=160)
    plt.close(figure)
    return output


def error_distribution_chart(
    paired: Mapping[str, Mapping[str, Sequence[float]]], output: Path
) -> Path:
    """Paired-only box + strip per camera and combined; same points in both versions."""
    _style()
    groups = [*sorted(paired), ALL_CAMERAS]

    def values(group: str, version: str) -> list[float]:
        if group == ALL_CAMERAS:
            return [v for per in paired.values() for v in per[version]]
        return list(paired[group][version])

    figure, axis = plt.subplots(figsize=(11, 5.6))
    width = 0.34
    pair_total = len(values(ALL_CAMERAS, "v1"))
    for group_index, group in enumerate(groups):
        for offset, version in ((-0.2, "v1"), (0.2, "v2")):
            data = values(group, version)
            if not data:
                continue
            x = group_index + offset
            box = axis.boxplot(
                [data],
                positions=[x],
                widths=width,
                patch_artist=True,
                showfliers=False,
                medianprops={"color": TEXT_PRIMARY, "linewidth": 2},
                whiskerprops={"color": VERSION_COLOR[version], "linewidth": 1.5},
                capprops={"color": VERSION_COLOR[version], "linewidth": 1.5},
            )
            for patch in box["boxes"]:
                patch.set_facecolor(VERSION_COLOR[version])
                patch.set_alpha(0.25)
                patch.set_edgecolor(VERSION_COLOR[version])
                patch.set_linewidth(1.5)
            spread = [x + width * 0.35 * ((i * 0.618) % 1 - 0.5) for i in range(len(data))]
            axis.scatter(
                spread,
                data,
                s=18,
                color=VERSION_COLOR[version],
                edgecolors=SURFACE,
                linewidths=0.6,
                zorder=3,
            )
            mean = sum(data) / len(data)
            axis.annotate(
                f"平均 {mean:.3f}\n最大 {max(data):.3f}",
                (x, max(data)),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=10,
                color=TEXT_SECONDARY,
            )
    axis.set_xticks(range(len(groups)))
    axis.set_xticklabels([f"{camera_label(g)}\n（{len(values(g, 'v1'))} 配對點）" for g in groups])
    axis.set_ylabel("誤差（公尺）")
    axis.set_ylim(0, axis.get_ylim()[1] * 1.18)
    _grid(axis)
    figure.legend(
        handles=[
            Patch(facecolor=VERSION_COLOR[v], alpha=0.6, label=VERSION_LABEL[v])
            for v in ("v1", "v2")
        ],
        loc="upper right",
        ncol=2,
        bbox_to_anchor=(0.99, 0.995),
    )
    axis.set_title(
        f"誤差分布（僅 v1、v2 皆有位置的 {pair_total} 個配對點）", loc="left", fontsize=16
    )
    figure.tight_layout(rect=(0, 0, 1, 0.97))
    figure.savefig(output, dpi=160)
    plt.close(figure)
    return output


def _stack(axis: Axes, y: float, segments: Sequence[tuple[str, int]], end_label: str) -> None:
    left = 0.0
    for key, count in segments:
        if count <= 0:
            continue
        axis.barh(
            y,
            count,
            left=left,
            height=0.62,
            color=REASON_COLOR.get(key, MUTED),
            edgecolor=SURFACE,
            linewidth=2,
        )
        if count >= 2:
            axis.text(
                left + count / 2,
                y,
                str(count),
                ha="center",
                va="center",
                fontsize=11,
                color=TEXT_PRIMARY,
                fontweight="semibold",
            )
        left += count
    axis.text(left + 0.4, y, end_label, va="center", fontsize=11, color=TEXT_SECONDARY)


def coverage_rejection_chart(report: Mapping[str, Any], output: Path) -> Path:
    """Left: auditorium timestamps kept/rejected per camera; right: Office positions."""
    _style()
    auditorium = report["auditorium"]
    office = report["office"]
    cameras = sorted(k for k in auditorium["rejection"] if k != ALL_CAMERAS)
    order = ["KEPT", "LOW_INCIDENCE", "TOUCHES_IMAGE_EDGE", "CONTACT_OCCLUDED"]

    def segments(by_primary: Mapping[str, int], kept: int) -> list[tuple[str, int]]:
        extra = [(k, v) for k, v in sorted(by_primary.items()) if k not in order]
        return [("KEPT", kept), *[(k, by_primary.get(k, 0)) for k in order[1:]], *extra]

    figure, (left, right) = plt.subplots(1, 2, figsize=(13.5, 4.8), sharey=True)
    labels: list[str] = []
    drawn: set[str] = set()
    for index, camera in enumerate(cameras):
        coverage = auditorium["coverage"]
        rejection = auditorium["rejection"][camera]
        total = coverage["v1"][camera]["total"]
        y_v1, y_v2 = index * 2.4, index * 2.4 + 1
        v1_count = coverage["v1"][camera]["with_position"]
        _stack(left, y_v1, [("V1", v1_count)], f"有位置 {v1_count}/{total}")
        audit_segments = segments(rejection["by_primary"], rejection["kept"])
        _stack(left, y_v2, audit_segments, f"有位置 {rejection['kept']}/{total}")
        office_entry = office.get(camera, {})
        office_v1 = office_entry.get("v1_positions", 0)
        _stack(right, y_v1, [("V1", office_v1)], f"{office_v1} 個位置")
        office_segments = segments(
            office_entry.get("v2_by_primary", {}), office_entry.get("v2_kept", 0)
        )
        _stack(
            right,
            y_v2,
            office_segments,
            f"保留 {office_entry.get('v2_kept', 0)}／拒絕 {office_entry.get('v2_rejected', 0)}",
        )
        drawn |= {key for key, count in (*audit_segments, *office_segments) if count > 0}
        labels += [f"{camera_label(camera)}  v1", f"{camera_label(camera)}  v2"]
    ticks = [i * 2.4 + d for i in range(len(cameras)) for d in (0, 1)]
    left.set_yticks(ticks)
    left.set_yticklabels(labels)
    left.invert_yaxis()
    union = auditorium["coverage"]["v2"][ALL_CAMERAS]
    left.set_title(
        f"驗證 run：有位置的時刻（v2 合併兩鏡頭 {union['with_position']}/{union['total']}）",
        loc="left",
    )
    left.set_xlabel("時刻數")
    office_all = office[ALL_CAMERAS]
    right.set_title(
        f"Office 原 run：位置數 {office_all['v1_positions']} → {office_all['v2_kept']}",
        loc="left",
    )
    right.set_xlabel("位置數")
    for axis in (left, right):
        _grid(axis, "x")
        axis.set_xlim(0, axis.get_xlim()[1] * 1.25)
    figure.legend(
        handles=[
            Patch(color=VERSION_COLOR["v1"], label="v1 有位置"),
            *[
                Patch(color=REASON_COLOR[k], label=f"v2 {REASON_LABEL[k]}")
                for k in order
                if k in drawn
            ],
        ],
        loc="lower center",
        ncol=len(order) + 1,
        bbox_to_anchor=(0.5, 0.0),
    )
    figure.suptitle(
        "覆蓋率與 v2 拒絕原因（多重原因以第一項計）",
        x=0.01,
        ha="left",
        fontsize=16,
        fontweight="semibold",
    )
    figure.tight_layout(rect=(0, 0.08, 1, 0.94))
    figure.savefig(output, dpi=160)
    plt.close(figure)
    return output
