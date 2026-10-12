"""Bounded candidate association media using source RGB and derived kinematics.

Candidate paths are provisional hypotheses, never confirmed cross-camera identity.
Rendering preserves missing spans, heuristic uncertainty and source provenance.
The source Blender file, source RGB and historical artifacts remain read-only.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import shutil
import subprocess
from collections import Counter
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from numpy.typing import NDArray
from PIL import Image

from amidst.engineering.registry import content_hash, opaque_ref

Json = dict[str, Any]
FPS = 5
FRAME_COUNT = 50
WIDTH, HEIGHT = 1280, 720
TIME_RANGE = [0.0, 9.8]
TOP_K = 3
_SCHEMA = "workbench.blender-association-media.v1"
_REF = re.compile(r"^cross-media:[0-9a-f]{24}$")
_BACKGROUND = "#101821"
_FOREGROUND = "#d4e3ed"
_INFERRED = "#f2bd63"
_CANDIDATE_COLORS = ("#63d8db", "#ba9df0", "#83d99f")
_RENDER_CONFIG = {"width": WIDTH, "height": HEIGHT, "fps": FPS, "frame_count": FRAME_COUNT,
                  "labels": "CANDIDATE_AND_PATH_ORDINAL_ONLY", "gaps": "DISCONNECTED",
                  "codec": "libx264", "pixel_format": "yuv420p", "crf": 22,
                  "faststart": True, "source_sampling": "EXACT_REGISTERED_FRAME_ONLY"}
_SOURCE_TYPES = {"rgb": "ACTUAL_BLENDER_CAMERA_RGB", "target_and_motion": "SYNTHETIC_SUBSTITUTE",
                 "position": "PROJECTED_OR_BOUNDED_INFERRED_DIAGNOSTIC",
                 "association": "INFERRED_UNCONFIRMED_MULTIPLE_HYPOTHESES",
                 "model": "PARTIAL_SOURCE_CONTEXT", "identity_behavior": "UNKNOWN"}
_LIMITATIONS = ["Provisional local-track associations; cross-camera identity is unconfirmed.",
                "Projected 3D is derived; uncertainty and compatibility are not probability.",
                "Missing motion stays disconnected; grey 3D edges denote association only.",
                "The final source frame at 9.8 s occupies the last 0.2 s of the video."]
_PUBLIC_KEYS = set("schema_version status items source_binding source_features "
                   "association_sha256 algorithm_sha256 renderer_sha256 render_config_sha256 "
                   "input_frames_sha256 render_model_sha256 encoder_sha256 encoder_version "
                   "selection candidate_count association_status motion_algorithm_sha256 "
                   "validation source_image_status source_types agent_used formal_acceptance "
                   "source_copied source_modified limitations".split())
_ITEM_KEYS = set("media_ref kind mime_type byte_count sha256 time_range duration_s fps frame_count "
                 "width height".split())


class AssociationScene(Protocol):
    scene_id: str
    index: Any

    def snapshot(self) -> Json: ...
    def export_safe_inputs(self) -> Json: ...
    def frames(self, camera_ids: Sequence[str], timestamp: float) -> Json: ...
    def media(self, ref: str) -> tuple[str, bytes]: ...


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _renderer_sha() -> str:
    return _file_sha(Path(__file__))


def _algorithm_sha() -> str:
    from amidst.workbench import blender_association

    return _file_sha(Path(blender_association.__file__))


def _motion_algorithm_sha() -> str:
    from amidst.workbench import blender_motion

    return _file_sha(Path(blender_motion.__file__))


def _media_ref(features: str, reconstruction: str, kind: str,
               renderer: str, artifact: str) -> str:
    # Registry kinds are alphabetic; the external media namespace includes a dash.
    suffix = opaque_ref("crossmedia", features, reconstruction, kind, renderer, artifact)
    return "cross-media:" + suffix.split(":", 1)[1]


def _encoder() -> tuple[Path, str, str]:
    from imageio_ffmpeg import get_ffmpeg_exe, get_ffmpeg_version  # type: ignore[import-untyped]

    path = Path(cast(str, get_ffmpeg_exe())).resolve()
    return path, _file_sha(path), cast(str, get_ffmpeg_version())


def _reconstruct(scene: AssociationScene, cameras: Sequence[str]) -> Json:
    from amidst.workbench.blender_association import BaselineAssociationIndex

    return BaselineAssociationIndex(scene.index.snapshot()).reconstruct(
        cameras, TIME_RANGE[0], TIME_RANGE[1], TOP_K)


def _public_inputs(scene: AssociationScene, camera_ids: Sequence[str]) -> tuple[list[Json], str]:
    inputs = scene.export_safe_inputs()
    rows = [{key: row[key] for key in (
        "frame_ref", "camera_id", "timestamp", "sha256", "byte_count")}
        for row in inputs["frames"] if row["camera_id"] in camera_ids and
        TIME_RANGE[0] <= row["timestamp"] <= TIME_RANGE[1]]
    rows.sort(key=lambda row: (row["camera_id"], row["timestamp"], row["frame_ref"]))
    return rows, content_hash(rows)


def curve_segments(samples: Sequence[Json], until: float = math.inf) -> list[list[Json]]:
    """Never connect explicit missing, disconnected or future candidate evidence."""
    result: list[list[Json]] = []
    current: list[Json] = []
    for sample in samples:
        if sample["timestamp"] > until:
            break
        position = sample.get("world_position")
        valid = (sample.get("state") in {"PROJECTED_OBSERVATION", "INFERRED_INTERPOLATION",
                                         "INFERRED_CROSS_CAMERA"}
                 and isinstance(position, list) and len(position) == 3
                 and all(type(v) in (int, float) and math.isfinite(v) for v in position))
        if not valid or not sample.get("connect_from_previous", False):
            if current:
                result.append(current)
            current = []
        if valid:
            current.append(dict(sample))
    if current:
        result.append(current)
    return result


def _style(axis: Any, title: str, xlabel: str = "", ylabel: str = "") -> None:
    axis.set_facecolor(_BACKGROUND)
    axis.set_title(title, loc="left", color=_FOREGROUND, fontsize=10, pad=6)
    axis.set_xlabel(xlabel, color=_FOREGROUND, fontsize=8)
    axis.set_ylabel(ylabel, color=_FOREGROUND, fontsize=8)
    axis.tick_params(colors="#90a6b6", labelsize=7)
    for spine in axis.spines.values():
        spine.set_color("#324553")
    axis.grid(color="#324553", alpha=0.35, linewidth=0.5)


def _sample_style(first: Json, second: Json | None, color: str) -> tuple[str, str]:
    states = {first["state"]}
    if second is not None:
        states.add(second["state"])
    if "INFERRED_CROSS_CAMERA" in states or (second is not None and
                                               (second.get("association_edge_ref")
                                                or second.get("association_edge_refs")
                                                or (first.get("node_ref") is not None
                                                    and second.get("node_ref") is not None
                                                    and first["node_ref"] != second["node_ref"]))):
        return _INFERRED, "--"
    if "INFERRED_INTERPOLATION" in states:
        return color, ":"
    return color, "-"


def _overlap_points(path: Json, until: float = math.inf) -> list[Json]:
    rows = []
    for sample in path["samples"]:
        if sample["timestamp"] > until:
            break
        for support in sample.get("overlap_support", []):
            p = support["world_position"]
            if (support["state"] in {"PROJECTED_OBSERVATION", "INFERRED_INTERPOLATION"}
                and isinstance(p, list) and len(p) == 3
                and all(type(v) in (int, float) and math.isfinite(v) for v in p)):
                rows.append({**support, "timestamp": sample["timestamp"]})
    return rows


def _plot_path(axis: Any, path: Json, color: str, until: float,
               *, coordinate: int | None = None, spatial_3d: bool = False,
               line_width: float = 1.3) -> None:
    for segment in curve_segments(path["samples"], until):
        for sample in segment:
            p = sample["world_position"]
            point_color, _ = _sample_style(sample, None, color)
            if spatial_3d:
                axis.scatter([p[0]], [p[1]], [p[2]], s=8, color=point_color, alpha=0.8)
            else:
                assert coordinate is not None
                axis.scatter([sample["timestamp"]], [p[coordinate]], s=6,
                             color=point_color, marker=("o", "s", "^")[coordinate], alpha=0.8)
        for first, second in zip(segment, segment[1:], strict=False):
            line_color, line_style = _sample_style(first, second, color)
            if spatial_3d:
                axis.plot([first["world_position"][0], second["world_position"][0]],
                          [first["world_position"][1], second["world_position"][1]],
                          [first["world_position"][2], second["world_position"][2]],
                          color=line_color, linestyle=line_style, linewidth=line_width, alpha=0.85)
            else:
                assert coordinate is not None
                axis.plot([first["timestamp"], second["timestamp"]],
                          [first["world_position"][coordinate],
                           second["world_position"][coordinate]],
                          color=line_color, linestyle=line_style, linewidth=line_width, alpha=0.85)
    # Simultaneous cameras remain independent source values, never an average or jump.
    for support in _overlap_points(path, until):
        p = support["world_position"]
        edge_color = color if support["state"] == "PROJECTED_OBSERVATION" else _INFERRED
        if spatial_3d:
            axis.scatter([p[0]], [p[1]], [p[2]], s=16, facecolors="none",
                         edgecolors=edge_color, alpha=0.65, linewidths=0.6)
        else:
            assert coordinate is not None
            axis.scatter([support["timestamp"]], [p[coordinate]], s=13, facecolors="none",
                         edgecolors=edge_color, marker=("o", "s", "^")[coordinate],
                         alpha=0.65, linewidths=0.6)


def _plot_speed(axis: Any, paths: Sequence[Json], color: str, until: float) -> None:
    for path in paths:
        previous = None
        for row in path["velocities"]:
            if row["timestamp"] > until:
                continue
            inferred = row.get("state") == "INFERRED_CROSS_CAMERA"
            line_color = _INFERRED if inferred else color
            axis.scatter([row["timestamp"]], [row["speed_m_s"]], s=7, color=line_color)
            if previous is not None and abs(
                previous["time_range"][1] - row["time_range"][0]) < 1e-8:
                axis.plot([previous["timestamp"], row["timestamp"]],
                          [previous["speed_m_s"], row["speed_m_s"]], color=line_color,
                          linestyle="--" if inferred else "-", linewidth=1, alpha=0.75)
            previous = row


def _bounds(reconstruction: Json) -> tuple[tuple[float, float], tuple[float, float]]:
    points = [s["world_position"][coordinate] for c in reconstruction["candidates"]
              for path in c["paths"] for s in path["samples"]
              if s.get("world_position") is not None for coordinate in range(3)]
    points.extend(s["world_position"][coordinate] for c in reconstruction["candidates"]
                  for path in c["paths"] for s in _overlap_points(path) for coordinate in range(3))
    speeds = [v["speed_m_s"] for c in reconstruction["candidates"]
              for path in c["paths"] for v in path["velocities"]]
    low, high = min(points, default=0), max(points, default=1)
    pad = max(0.5, (high - low) * 0.05)
    return (low - pad, high + pad), (0.0, max(1.0, max(speeds, default=0) * 1.1))


def _shade_gaps(axis: Any, paths: Sequence[Json]) -> None:
    for path in paths:
        for gap in path["gaps"]:
            start, end = gap["time_range"]
            if end > start:
                axis.axvspan(start, end, color="#7e8994", alpha=0.07, linewidth=0)


def _candidate_gap_tracks(candidate: Json) -> list[Json]:
    return list(candidate["paths"]) + [{"gaps": candidate.get("unresolved_local_gaps", [])}]


def _candidate_label(candidate: Json) -> str:
    uncertainties = [s["uncertainty"] for p in candidate["paths"]
                     for s in list(p["samples"]) + _overlap_points(p)
                     if s.get("uncertainty") is not None]
    u = (f" | u {min(uncertainties):.2f}-{max(uncertainties):.2f} heuristic"
         if uncertainties else " | uncertainty UNKNOWN")
    gaps = sum(len(path["gaps"]) for path in _candidate_gap_tracks(candidate))
    return f"Candidate {candidate['rank']} | score {candidate['score']:.3f}" + u + f" | gaps {gaps}"


def _coverage_label(reconstruction: Json) -> str:
    missing = [row["camera_id"] for row in reconstruction["camera_coverage"]
               if row["state"] == "MISSING"]
    return " | MISSING camera: " + ", ".join(missing) if missing else ""


def render_curve_figure(reconstruction: Json, camera_ids: Sequence[str]) -> Figure:
    """Candidate XYZ/time and interval-speed panels with explicit provenance."""
    del camera_ids  # Coverage comes from the same source-bound reconstruction.
    figure = Figure(figsize=(WIDTH / 100, HEIGHT / 100), dpi=100, facecolor=_BACKGROUND)
    candidates = reconstruction["candidates"]
    grid = figure.subplots(max(1, len(candidates)), 2, squeeze=False)
    position_bounds, speed_bounds = _bounds(reconstruction)
    if not candidates:
        for axis in grid[0]:
            _style(axis, "MISSING: no valid candidate evidence", "Source time (s)")
            axis.set_xlim(TIME_RANGE[0], TIME_RANGE[1])
        grid[0][0].text(0.5, 0.5, "MISSING: no valid local track", ha="center",
                        transform=grid[0][0].transAxes, color=_FOREGROUND)
    for index, candidate in enumerate(candidates):
        position, speed = grid[index]
        color = _CANDIDATE_COLORS[index % len(_CANDIDATE_COLORS)]
        _style(position, _candidate_label(candidate), "Source time (s)", "Derived X/Y/Z (m)")
        _style(speed, "INFERRED interval speed", "Source time (s)", "Speed (m/s)")
        for path in candidate["paths"]:
            for coordinate in range(3):
                _plot_path(position, path, color, TIME_RANGE[1], coordinate=coordinate)
        _plot_speed(speed, candidate["paths"], color, TIME_RANGE[1])
        if not any(p["velocities"] for p in candidate["paths"]):
            speed.text(0.5, 0.5, "MISSING: no valid connected velocity interval",
                       transform=speed.transAxes, ha="center", color="#90a6b6", fontsize=8)
        position.set_xlim(TIME_RANGE)
        position.set_ylim(position_bounds)
        speed.set_xlim(TIME_RANGE)
        speed.set_ylim(speed_bounds)
        _shade_gaps(position, _candidate_gap_tracks(candidate))
        _shade_gaps(speed, _candidate_gap_tracks(candidate))
        position.text(0.99, 0.95, "X circle | Y square | Z triangle", ha="right",
                      transform=position.transAxes, fontsize=7, color="#90a6b6")
    figure.suptitle(f"Blender candidate association | {len(candidates)} / {TOP_K} requested | "
                   + reconstruction["status"] + _coverage_label(reconstruction),
                   color=_FOREGROUND, fontsize=12, y=0.98)
    figure.text(0.045, 0.037, "OBSERVED pixels -> projected solid | local INFERRED dotted | "
                "cross-camera INFERRED amber dashed | hollow: overlap source points",
                color="#90a6b6", fontsize=8)
    figure.text(0.045, 0.017, "MISSING motion stays disconnected | SYNTHETIC target/motion | "
                "u heuristic; score not probability; identity UNCONFIRMED",
                color="#90a6b6", fontsize=8)
    figure.subplots_adjust(left=0.075, right=0.97, top=0.9, bottom=0.105, hspace=0.48, wspace=0.2)
    return figure


def _current_state(tracks: Sequence[Json], timestamp: float) -> str:
    states = [s["state"] for track in tracks for s in track["samples"]
              if abs(s["timestamp"] - timestamp) <= 1e-8]
    if "PROJECTED_OBSERVATION" in states:
        return "OBSERVED pixels / derived projection; identity UNCONFIRMED"
    if "INFERRED_INTERPOLATION" in states:
        return "INFERRED local gap; heuristic uncertainty"
    return "MISSING projected evidence; no extrapolation"


def _plot_missing_association_edges(axis: Any, reconstruction: Json, candidate: Json,
                                    timestamp: float, color: str = "#9aa6b0") -> None:
    nodes = {row["node_ref"]: row for row in reconstruction["graph"]["nodes"]}
    selected = set(candidate["selected_edge_refs"])
    for edge in reconstruction["graph"]["edges"]:
        if edge["edge_ref"] not in selected or not edge["bridge_missing"]:
            continue
        left = nodes[edge["from_node_ref"]]["samples"][-1]
        right = nodes[edge["to_node_ref"]]["samples"][0]
        if max(left["timestamp"], right["timestamp"]) > timestamp:
            continue
        a, b = left["world_position"], right["world_position"]
        axis.plot([a[0], b[0]], [a[1], b[1]], [a[2], b[2]], color="#9aa6b0",
                  linestyle="--", linewidth=2.5, alpha=0.65)
        axis.plot([a[0], b[0]], [a[1], b[1]], [a[2], b[2]], color=color,
                  linestyle="--", linewidth=0.8, alpha=0.8)


def _spatial_plot(axis: Any, reconstruction: Json, snapshot: Json, timestamp: float) -> None:
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # type: ignore[import-untyped]

    axis.set_facecolor(_BACKGROUND)
    meshes = snapshot.get("presentation", {}).get("meshes", [])
    for mesh in meshes:
        vertices = mesh["vertices"]
        triangles = [[vertices[v] for v in face] for face in mesh["triangles"]]
        axis.add_collection3d(Poly3DCollection(triangles, facecolors="#71808b", alpha=0.06,
                                             edgecolors="#71808b", linewidths=0.1))
    for index, candidate in enumerate(reconstruction["candidates"]):
        color = _CANDIDATE_COLORS[index % len(_CANDIDATE_COLORS)]
        for path in candidate["paths"]:
            _plot_path(axis, path, color, timestamp, spatial_3d=True,
                       line_width=max(1.2, 4.0 - index * 1.3))
        _plot_missing_association_edges(axis, reconstruction, candidate, timestamp, color)
    points = [v for mesh in meshes for v in mesh["vertices"]]
    points.extend(s["world_position"] for c in reconstruction["candidates"] for p in c["paths"]
                  for s in p["samples"] if s.get("world_position") is not None)
    points.extend(s["world_position"] for c in reconstruction["candidates"]
                  for p in c["paths"] for s in _overlap_points(p))
    ranges = []
    for coordinate, setter in enumerate((axis.set_xlim, axis.set_ylim, axis.set_zlim)):
        values = [p[coordinate] for p in points]
        low, high = min(values, default=0), max(values, default=1)
        padding = max(0.5, (high - low) * 0.05)
        setter(low - padding, high + padding)
        ranges.append(high - low + 2 * padding)
    axis.set_box_aspect(ranges)
    axis.view_init(elev=27, azim=-56)
    axis.tick_params(colors="#90a6b6", labelsize=6, pad=0)
    for name in ("x", "y", "z"):
        getattr(axis, f"set_{name}label")(f"{name.upper()} (m)", color=_FOREGROUND, fontsize=7)
    axis.set_title("Candidate paths 3D | PARTIAL source context", color=_FOREGROUND,
                   fontsize=9, loc="left", pad=3)
    labels = [_candidate_label(c) + f", {len(c['selected_edge_refs'])} edges"
              for c in reconstruction["candidates"]]
    axis.text2D(0.0, 0.02, "\n".join(labels) +
                "\nGrey outlined edges: association only, MISSING positions; "
                "hollow: overlap sources",
                transform=axis.transAxes, color=_FOREGROUND, fontsize=7)


def _video_frame(scene: AssociationScene, reconstruction: Json, camera_ids: Sequence[str],
                 timestamp: float, snapshot: Json, image_status: Counter[str]) -> NDArray[np.uint8]:
    figure = Figure(figsize=(WIDTH / 100, HEIGHT / 100), dpi=100, facecolor=_BACKGROUND)
    canvas = FigureCanvasAgg(figure)
    grid = figure.add_gridspec(3, 2, height_ratios=[0.9, 0.9, 0.65])
    timeline = scene.frames(camera_ids, timestamp)["frames"]
    for index, camera_id in enumerate(camera_ids):
        axis = figure.add_subplot(grid[0, index])
        row = next(r for r in timeline if r["camera_id"] == camera_id)
        tracks = [t for t in reconstruction["tracks"] if t["camera_id"] == camera_id]
        if row.get("media_ref") and row.get("status") == "EXACT":
            _, raw = scene.media(row["media_ref"])
            with Image.open(BytesIO(raw)) as image:
                pixels = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
            axis.imshow(pixels)
            image_status["SOURCE_RGB_EXACT"] += 1
        else:
            axis.text(0.5, 0.5, "MISSING source RGB", transform=axis.transAxes,
                      ha="center", va="center", color=_FOREGROUND, fontsize=14)
            image_status["MISSING_SOURCE_FRAME"] += 1
        axis.set_title(f"{camera_id}\n{_current_state(tracks, timestamp)}", color=_FOREGROUND,
                       fontsize=8, loc="left", pad=5)
        axis.set_axis_off()
    spatial = figure.add_subplot(grid[1:, 0], projection="3d")
    _spatial_plot(spatial, reconstruction, snapshot, timestamp)
    position, speed = figure.add_subplot(grid[1, 1]), figure.add_subplot(grid[2, 1])
    _style(position, "Candidate derived X/Y/Z | same source clock",
           "Source time (s)", "Position (m)")
    _style(speed, "INFERRED speed | gaps disconnected", "Source time (s)", "Speed (m/s)")
    for index, candidate in enumerate(reconstruction["candidates"]):
        color = _CANDIDATE_COLORS[index % len(_CANDIDATE_COLORS)]
        for path in candidate["paths"]:
            for coordinate in range(3):
                _plot_path(position, path, color, timestamp, coordinate=coordinate,
                           line_width=max(0.8, 3.0 - index))
        _plot_speed(speed, candidate["paths"], color, timestamp)
        _shade_gaps(position, _candidate_gap_tracks(candidate))
        _shade_gaps(speed, _candidate_gap_tracks(candidate))
    position_bounds, speed_bounds = _bounds(reconstruction)
    position.set_ylim(position_bounds)
    speed.set_ylim(speed_bounds)
    for axis in (position, speed):
        axis.set_xlim(TIME_RANGE[0], TIME_RANGE[1])
        axis.axvline(timestamp, color=_FOREGROUND, alpha=0.5, linewidth=0.8)
    figure.suptitle(f"Blender candidate association | {timestamp:.1f} s | "
                   f"{len(reconstruction['candidates'])}/{TOP_K} requested | "
                   + reconstruction["status"] + _coverage_label(reconstruction),
                   color=_FOREGROUND, fontsize=12, y=0.98)
    figure.text(0.035, 0.037, "ACTUAL Blender RGB | SYNTHETIC target/motion | projected solid; "
                "local INFERRED dotted; cross-camera INFERRED amber dashed | "
                "hollow overlap sources",
                color="#90a6b6", fontsize=8)
    figure.text(0.035, 0.017, "MISSING motion disconnected; grey outlined edges association only | "
                "u heuristic; score not probability; identity UNCONFIRMED",
                color="#90a6b6", fontsize=8)
    figure.subplots_adjust(left=0.065, right=0.97, top=0.885, bottom=0.105,
                           hspace=0.42, wspace=0.22)
    canvas.draw()  # type: ignore[no-untyped-call]
    return np.asarray(canvas.buffer_rgba(), dtype=np.uint8)[..., :3].copy()  # type: ignore[no-untyped-call]


def _full_decode(path: Path, encoder: Path) -> Json:
    """Actually decode every frame; optional ffprobe supplements, never replaces it."""
    command = [str(encoder), "-nostdin", "-hide_banner", "-v", "info", "-i", str(path),
               "-map", "0:v:0", "-f", "null", "-progress", "pipe:1", "-"]
    result = subprocess.run(command, capture_output=True, timeout=120, check=False)
    progress = {}
    for line in result.stdout.decode(errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            progress[key] = value.strip()
    log = result.stderr.decode(errors="replace")
    try:
        frames = int(progress["frame"])
        duration = int(progress["out_time_us"]) / 1_000_000
    except (KeyError, ValueError):
        raise ValueError("ASSOCIATION_VIDEO_DECODE_FAILED") from None
    if result.returncode or progress.get("progress") != "end" or frames != FRAME_COUNT or (
        abs(duration - FRAME_COUNT / FPS) > 0.05
        or "Video: h264" not in log or "yuv420p" not in log
        or f"{WIDTH}x{HEIGHT}" not in log
    ):
        raise ValueError("ASSOCIATION_VIDEO_DECODE_FAILED")
    raw = path.read_bytes()
    if raw.find(b"moov") < 0 or raw.find(b"mdat") < 0 or raw.find(b"moov") > raw.find(b"mdat"):
        raise ValueError("ASSOCIATION_VIDEO_FASTSTART_MISSING")
    probe = shutil.which("ffprobe")
    if probe:
        entries = "stream=codec_name,pix_fmt,width,height,nb_frames"
        checked = subprocess.run([probe, "-v", "error", "-select_streams", "v:0",
                                  "-show_entries", entries,
                                  "-of", "json", str(path)], capture_output=True,
                                 timeout=30, check=False)
        if checked.returncode:
            raise ValueError("ASSOCIATION_VIDEO_PROBE_FAILED")
        rows = json.loads(checked.stdout)["streams"]
        if len(rows) != 1 or rows[0]["codec_name"] != "h264" or (
            rows[0]["pix_fmt"] != "yuv420p" or rows[0]["width"] != WIDTH
            or rows[0]["height"] != HEIGHT or int(rows[0]["nb_frames"]) != FRAME_COUNT
        ):
            raise ValueError("ASSOCIATION_VIDEO_PROBE_FAILED")
    return {"status": "PASS", "method": "FFMPEG_FULL_DECODE" if probe else
            "FFMPEG_FULL_DECODE_FALLBACK", "ffprobe_available": bool(probe),
            "frame_count": frames, "duration_s": duration, "width": WIDTH, "height": HEIGHT,
            "codec": "h264", "pixel_format": "yuv420p", "faststart": True}


def materialize_association_artifacts(scene: AssociationScene, output: Path) -> Json:
    """Create one site's explicit local plot/video package at a fresh destination."""
    output = output.resolve()
    if output.exists():
        raise FileExistsError("ASSOCIATION_OUTPUT_EXISTS")
    snapshot = scene.snapshot()
    camera_ids = sorted(row["camera_id"] for row in snapshot["cameras"])
    if len(camera_ids) != 2:
        raise ValueError("ASSOCIATION_PRESENTATION_CAMERA_BUDGET")
    reconstruction = _reconstruct(scene, camera_ids)
    if reconstruction["source_features"] != scene.index.source_features:
        raise ValueError("ASSOCIATION_SOURCE_FEATURES_MISMATCH")
    frames, inputs_hash = _public_inputs(scene, camera_ids)
    model_hash = content_hash(snapshot.get("presentation", {}))
    encoder, encoder_hash, encoder_version = _encoder()
    output.mkdir(parents=True)
    figure = render_curve_figure(reconstruction, camera_ids)
    curve_path = output / "curves.png"
    figure.savefig(curve_path, facecolor=_BACKGROUND, metadata={
        "Software": "Amidst local diagnostic renderer",
        "Description": "Candidate curves; synthetic target/motion; unconfirmed identity"})
    video_path = output / "reconstruction.mp4"
    command = [str(encoder), "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "pipe:0", "-an",
               "-c:v", "libx264", "-crf", str(_RENDER_CONFIG["crf"]), "-pix_fmt", "yuv420p",
               "-threads", "1", "-fflags", "+bitexact", "-flags:v", "+bitexact",
               "-map_metadata", "-1", "-movflags", "+faststart", str(video_path)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE)
    assert process.stdin is not None and process.stderr is not None
    statuses: Counter[str] = Counter()
    try:
        for index in range(FRAME_COUNT):
            pixels = _video_frame(scene, reconstruction, camera_ids, index / FPS,
                                  snapshot, statuses)
            process.stdin.write(pixels.tobytes())
        process.stdin.close()
        process.stderr.read()
        if process.wait(timeout=120) != 0:
            raise ValueError("ASSOCIATION_VIDEO_ENCODING_FAILED")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        process.kill()
        process.wait()
        raise ValueError("ASSOCIATION_VIDEO_ENCODING_FAILED") from None
    finally:
        process.stderr.close()
    validation = _full_decode(video_path, encoder)
    artifacts = []
    private = []
    for kind, path, mime in [("ASSOCIATION_POSITION_VELOCITY_CURVES", curve_path, "image/png"),
                             ("CROSS_CAMERA_RECONSTRUCTION_VIDEO", video_path, "video/mp4")]:
        value = {"media_ref": _media_ref(scene.index.source_features,
                                        reconstruction["association_sha256"], kind,
                                        _renderer_sha(), _file_sha(path)),
                 "kind": kind, "mime_type": mime, "byte_count": path.stat().st_size,
                 "sha256": _file_sha(path), "time_range": list(TIME_RANGE),
                 "duration_s": FRAME_COUNT / FPS if mime == "video/mp4" else None,
                 "fps": FPS if mime == "video/mp4" else None,
                 "frame_count": FRAME_COUNT if mime == "video/mp4" else 1,
                 "width": WIDTH, "height": HEIGHT}
        artifacts.append(value)
        private.append({"media_ref": value["media_ref"], "relative_path": path.name})
    public = {"schema_version": _SCHEMA, "status": "AVAILABLE", "items": artifacts,
              "source_binding": copy.deepcopy(reconstruction["source_binding"]),
              "source_features": scene.index.source_features,
              "association_sha256": reconstruction["association_sha256"],
              "algorithm_sha256": _algorithm_sha(), "renderer_sha256": _renderer_sha(),
              "render_config_sha256": content_hash(_RENDER_CONFIG),
              "input_frames_sha256": inputs_hash, "render_model_sha256": model_hash,
              "encoder_sha256": encoder_hash, "encoder_version": encoder_version,
              "selection": {"camera_ids": camera_ids, "time_range": list(TIME_RANGE),
                            "top_k": TOP_K},
              "candidate_count": len(reconstruction["candidates"]),
              "association_status": reconstruction["status"],
              "motion_algorithm_sha256": _motion_algorithm_sha(),
              "validation": validation, "source_image_status": dict(statuses),
              "source_types": copy.deepcopy(_SOURCE_TYPES),
              "agent_used": False, "formal_acceptance": False,
              "source_copied": False, "source_modified": False,
              "limitations": list(_LIMITATIONS)}
    manifest = {"schema_version": _SCHEMA, "public": public, "artifacts": private,
                "input_frames": frames, "input_frames_sha256": inputs_hash}
    (output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True,
        ensure_ascii=False, allow_nan=False, indent=2) + "\n")
    return public


class AssociationMediaProvider:
    """Lazy verified artifacts; no encoding, synthesis or caller locators on reads."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._reconstructions: dict[tuple[str, str, str, str, tuple[str, ...]], Json] = {}

    def _cached_reconstruction(self, scene: AssociationScene, cameras: Sequence[str]) -> Json:
        # Only import-time association work is cached. Source, model, artifact and
        # privacy guards still run on every read. A changed source/code hash misses.
        key = (scene.index.source_features, content_hash(scene.index.snapshot()),
               _algorithm_sha(), _motion_algorithm_sha(), tuple(cameras))
        if key not in self._reconstructions:
            value = _reconstruct(scene, cameras)
            if len(self._reconstructions) >= 3:
                self._reconstructions.pop(next(iter(self._reconstructions)))
            self._reconstructions[key] = value
        return self._reconstructions[key]

    def _load(self, scene: AssociationScene) -> tuple[Json, Path] | None:
        snapshot = scene.snapshot()
        site = snapshot["source_binding"]["site_id"]
        if site not in {"office", "classroom101", "auditorium"}:
            raise ValueError("ASSOCIATION_MEDIA_SCOPE_DENIED")
        folder = self.root / site
        path = folder / "manifest.json"
        if not path.exists():
            return None
        if folder.is_symlink() or path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError("ASSOCIATION_MEDIA_SCOPE_DENIED")
        try:
            if path.stat().st_size > 1024 * 1024:
                raise ValueError("ASSOCIATION_MEDIA_STALE")
            value = json.loads(path.read_bytes())
            if set(value) != {"schema_version", "public", "artifacts", "input_frames",
                              "input_frames_sha256"} or value["schema_version"] != _SCHEMA:
                raise ValueError("ASSOCIATION_MEDIA_STALE")
            public = value["public"]
            if set(public) != _PUBLIC_KEYS or public["schema_version"] != _SCHEMA or (
                public["source_types"] != _SOURCE_TYPES or public["limitations"] != _LIMITATIONS
                or any(public[key] is not False for key in (
                    "agent_used", "formal_acceptance", "source_copied", "source_modified"))
            ):
                raise ValueError("ASSOCIATION_MEDIA_STALE")
            cameras = sorted(row["camera_id"] for row in snapshot["cameras"])
            reconstruction = self._cached_reconstruction(scene, cameras)
            _, inputs_hash = _public_inputs(scene, cameras)
            _, encoder_hash, encoder_version = _encoder()
            validation = public["validation"]
            probe_available = validation["ffprobe_available"]
            expected_validation = {
                "status": "PASS", "method": "FFMPEG_FULL_DECODE" if probe_available else
                "FFMPEG_FULL_DECODE_FALLBACK", "ffprobe_available": probe_available,
                "frame_count": FRAME_COUNT, "duration_s": FRAME_COUNT / FPS,
                "width": WIDTH, "height": HEIGHT, "codec": "h264",
                "pixel_format": "yuv420p", "faststart": True}
            image_status = public["source_image_status"]
            if type(probe_available) is not bool or validation != expected_validation or (
                not isinstance(image_status, dict)
                or not set(image_status).issubset({"SOURCE_RGB_EXACT", "MISSING_SOURCE_FRAME"})
                or any(type(v) is not int or v < 0 for v in image_status.values())
                or sum(image_status.values()) != FRAME_COUNT * len(cameras)
            ):
                raise ValueError("ASSOCIATION_MEDIA_STALE")
            if (public["source_features"] != scene.index.source_features
                or public["source_binding"] != reconstruction["source_binding"]
                or public["association_sha256"] != reconstruction["association_sha256"]
                or public["algorithm_sha256"] != _algorithm_sha()
                or public["motion_algorithm_sha256"] != _motion_algorithm_sha()
                or type(public["candidate_count"]) is not int
                or public["candidate_count"] != len(reconstruction["candidates"])
                or public["association_status"] != reconstruction["status"]
                or public["renderer_sha256"] != _renderer_sha()
                or public["render_config_sha256"] != content_hash(_RENDER_CONFIG)
                or public["encoder_sha256"] != encoder_hash
                or public["encoder_version"] != encoder_version
                or public["input_frames_sha256"] != inputs_hash
                or value["input_frames_sha256"] != inputs_hash
                or content_hash(value["input_frames"]) != inputs_hash
                or public["render_model_sha256"] != content_hash(snapshot.get("presentation", {}))
                or public["selection"] != {"camera_ids": cameras, "time_range": TIME_RANGE,
                                            "top_k": TOP_K}
                or public["status"] != "AVAILABLE"
                or len(public["items"]) != 2 or len(value["artifacts"]) != 2
            ):
                raise ValueError("ASSOCIATION_MEDIA_STALE")
            source = {row["frame_ref"]: row for row in scene.export_safe_inputs()["frames"]}
            for row in value["input_frames"]:
                original = source[row["frame_ref"]]
                original_path = Path(original["local_path"])
                if original_path.is_symlink() or original_path.resolve() != original_path or (
                    original_path.stat().st_size != row["byte_count"]
                ) or (
                    _file_sha(original_path) != row["sha256"]
                ):
                    raise ValueError("ASSOCIATION_MEDIA_STALE")
            for item, private in zip(public["items"], value["artifacts"], strict=True):
                expected = {"ASSOCIATION_POSITION_VELOCITY_CURVES": ("curves.png", "image/png"),
                            "CROSS_CAMERA_RECONSTRUCTION_VIDEO":
                                ("reconstruction.mp4", "video/mp4")}
                if item["kind"] not in expected or _REF.fullmatch(item["media_ref"]) is None or (
                    set(item) != _ITEM_KEYS
                    or set(private) != {"media_ref", "relative_path"}
                    or private["media_ref"] != item["media_ref"]
                    or private["relative_path"] != expected[item["kind"]][0]
                    or item["mime_type"] != expected[item["kind"]][1]
                    or item["time_range"] != TIME_RANGE or item["width"] != WIDTH
                    or item["height"] != HEIGHT
                    or item["frame_count"] != (
                        FRAME_COUNT if item["mime_type"] == "video/mp4" else 1)
                    or item["duration_s"] != (
                        FRAME_COUNT / FPS if item["mime_type"] == "video/mp4" else None)
                    or item["fps"] != (FPS if item["mime_type"] == "video/mp4" else None)
                    or item["media_ref"] != _media_ref(public["source_features"],
                        public["association_sha256"], item["kind"],
                        public["renderer_sha256"], item["sha256"])
                ):
                    raise ValueError("ASSOCIATION_MEDIA_SCOPE_DENIED")
                artifact = folder / private["relative_path"]
                if artifact.is_symlink() or not artifact.resolve().is_relative_to(folder) or (
                    artifact.stat().st_size != item["byte_count"]
                    or _file_sha(artifact) != item["sha256"]
                ):
                    raise ValueError("ASSOCIATION_MEDIA_STALE")
            if [item["kind"] for item in public["items"]] != [
                "ASSOCIATION_POSITION_VELOCITY_CURVES", "CROSS_CAMERA_RECONSTRUCTION_VIDEO"]:
                raise ValueError("ASSOCIATION_MEDIA_STALE")
            # Every public object uses a fixed contract; private filenames are never returned.
            return value, folder
        except (OSError, KeyError, TypeError, ValueError):
            raise ValueError("ASSOCIATION_MEDIA_STALE") from None

    def manifest(self, scene: AssociationScene) -> Json:
        loaded = self._load(scene)
        if loaded is None:
            return {"status": "UNAVAILABLE", "items": [], "reason": "NOT_MATERIALIZED"}
        return copy.deepcopy(loaded[0]["public"])

    def media(self, scene: AssociationScene, ref: str) -> tuple[str, bytes]:
        if _REF.fullmatch(ref) is None:
            raise ValueError("ASSOCIATION_MEDIA_SCOPE_DENIED")
        loaded = self._load(scene)
        if loaded is None:
            raise ValueError("ASSOCIATION_MEDIA_UNAVAILABLE")
        manifest, folder = loaded
        for item, private in zip(manifest["public"]["items"], manifest["artifacts"], strict=True):
            if item["media_ref"] == ref:
                raw = (folder / private["relative_path"]).read_bytes()
                if _sha(raw) != item["sha256"]:
                    raise ValueError("ASSOCIATION_MEDIA_STALE")
                return item["mime_type"], raw
        raise ValueError("ASSOCIATION_MEDIA_SCOPE_DENIED")
