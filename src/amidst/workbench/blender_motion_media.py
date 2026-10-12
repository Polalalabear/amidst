"""Explicit source-bound diagnostic motion plots/video; lazy runtime serving only.

RGB remains read-only. Encoding does not call Blender, simulate hidden motion or
open truth. Camera-local pixel projections and bounded inferred curve samples
are rendered as diagnostics, with missing intervals left visibly disconnected.
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
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
from numpy.typing import NDArray
from PIL import Image

from amidst.engineering.registry import content_hash, opaque_ref

Json = dict[str, Any]
FPS = 5
FRAME_COUNT = 50
WIDTH, HEIGHT = 1280, 720
TIME_RANGE = [0.0, 9.8]
_SCHEMA = "workbench.blender-motion-media.v1"
_REF = re.compile(r"^motion-media:[0-9a-f]{24}$")
_BACKGROUND = "#101821"
_FOREGROUND = "#d4e3ed"
_PROJECTED, _INFERRED, _SPEED = "#63d8db", "#f2bd63", "#ba9df0"
_RENDER_CONFIG = {"width": WIDTH, "height": HEIGHT, "fps": FPS, "frame_count": FRAME_COUNT,
                  "labels": "CAMERA_LOCAL_ORDINAL_ONLY", "gaps": "DISCONNECTED",
                  "codec": "libx264", "pixel_format": "yuv420p", "crf": 22,
                  "faststart": True, "source_sampling": "EXACT_REGISTERED_FRAME_ONLY"}
_SOURCE_TYPES = {"rgb": "ACTUAL_BLENDER_CAMERA_RGB", "target_and_motion": "SYNTHETIC_SUBSTITUTE",
                 "position": "PROJECTED_OR_BOUNDED_INFERRED_DIAGNOSTIC",
                 "model": "PARTIAL_SOURCE_CONTEXT", "identity_behavior": "UNKNOWN"}
_LIMITATIONS = ["Diagnostic reconstruction of camera-local pixel tracks.",
                "Projected 3D is derived; finite differences do not confirm behavior.",
                "Missing intervals stay disconnected; no extrapolation.",
                "The final source frame at 9.8 s occupies the last 0.2 s of the video."]
_PUBLIC_KEYS = set("schema_version status items source_binding source_features "
                   "reconstruction_sha256 algorithm_sha256 renderer_sha256 render_config_sha256 "
                   "input_frames_sha256 render_model_sha256 encoder_sha256 encoder_version "
                   "selection "
                   "validation source_image_status source_types agent_used formal_acceptance "
                   "source_copied source_modified limitations".split())
_ITEM_KEYS = set("media_ref kind mime_type byte_count sha256 time_range duration_s fps frame_count "
                 "width height".split())


class MotionScene(Protocol):
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
    from amidst.workbench import blender_motion

    return _file_sha(Path(blender_motion.__file__))


def _media_ref(features: str, reconstruction: str, kind: str,
               renderer: str, artifact: str) -> str:
    # Registry kinds are alphabetic; the external media namespace includes a dash.
    suffix = opaque_ref("motionmedia", features, reconstruction, kind, renderer, artifact)
    return "motion-media:" + suffix.split(":", 1)[1]


def _encoder() -> tuple[Path, str, str]:
    from imageio_ffmpeg import get_ffmpeg_exe, get_ffmpeg_version  # type: ignore[import-untyped]

    path = Path(cast(str, get_ffmpeg_exe())).resolve()
    return path, _file_sha(path), cast(str, get_ffmpeg_version())


def _reconstruct(scene: MotionScene, cameras: Sequence[str]) -> Json:
    from amidst.workbench.blender_motion import BaselineMotionIndex

    return BaselineMotionIndex(scene.index.snapshot()).reconstruct(
        cameras, TIME_RANGE[0], TIME_RANGE[1])


def _public_inputs(scene: MotionScene, camera_ids: Sequence[str]) -> tuple[list[Json], str]:
    inputs = scene.export_safe_inputs()
    rows = [{key: row[key] for key in (
        "frame_ref", "camera_id", "timestamp", "sha256", "byte_count")}
        for row in inputs["frames"] if row["camera_id"] in camera_ids and
        TIME_RANGE[0] <= row["timestamp"] <= TIME_RANGE[1]]
    rows.sort(key=lambda row: (row["camera_id"], row["timestamp"], row["frame_ref"]))
    return rows, content_hash(rows)


def curve_segments(samples: Sequence[Json], until: float = math.inf) -> list[list[Json]]:
    """Never connect across explicit missing/null or producer-disconnected samples."""
    result: list[list[Json]] = []
    current: list[Json] = []
    for sample in samples:
        if sample["timestamp"] > until:
            break
        position = sample.get("world_position")
        valid = (sample.get("state") in {"PROJECTED_OBSERVATION", "INFERRED_INTERPOLATION"}
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
    axis.set_title(title, loc="left", color=_FOREGROUND, fontsize=11, pad=8)
    axis.set_xlabel(xlabel, color=_FOREGROUND, fontsize=9)
    axis.set_ylabel(ylabel, color=_FOREGROUND, fontsize=9)
    axis.tick_params(colors="#90a6b6", labelsize=8)
    for spine in axis.spines.values():
        spine.set_color("#324553")
    axis.grid(color="#324553", alpha=0.35, linewidth=0.5)


def _plot_track(axis: Any, track: Json, ordinal: int, until: float,
                *, coordinate: int | None = None) -> None:
    for segment in curve_segments(track["samples"], until):
        for sample in segment:
            position = sample["world_position"]
            inferred = sample["state"] == "INFERRED_INTERPOLATION"
            x = sample["timestamp"] if coordinate is not None else position[0]
            y = position[coordinate] if coordinate is not None else position[1]
            axis.scatter([x], [y], s=7, color=_INFERRED if inferred else _PROJECTED,
                         marker=("o", "s", "^")[coordinate] if coordinate is not None else "o",
                         zorder=4, alpha=0.8)
        for first, second in zip(segment, segment[1:], strict=False):
            inferred = "INFERRED_INTERPOLATION" in {first["state"], second["state"]}
            if coordinate is None:
                xs = [first["world_position"][0], second["world_position"][0]]
                ys = [first["world_position"][1], second["world_position"][1]]
            else:
                xs = [first["timestamp"], second["timestamp"]]
                ys = [first["world_position"][coordinate], second["world_position"][coordinate]]
            axis.plot(xs, ys, color=_INFERRED if inferred else _PROJECTED,
                      linestyle="--" if inferred else "-", linewidth=1.1, alpha=0.8)
    visible = [s for group in curve_segments(track["samples"], until) for s in group]
    if visible and coordinate is None:
        point = visible[-1]["world_position"]
        axis.annotate(f"Local track {ordinal}", point[:2], color=_FOREGROUND,
                      fontsize=7, xytext=(5, 4), textcoords="offset points")


def _plot_speed(axis: Any, tracks: Sequence[Json], until: float) -> None:
    count = 0
    for track in tracks:
        previous = None
        for row in track["velocities"]:
            if row["timestamp"] > until:
                continue
            count += 1
            axis.scatter([row["timestamp"]], [row["speed_m_s"]], s=7, color=_SPEED)
            if previous is not None and abs(
                previous["time_range"][1] - row["time_range"][0]) < 1e-8:
                axis.plot([previous["timestamp"], row["timestamp"]],
                          [previous["speed_m_s"], row["speed_m_s"]], color=_SPEED,
                          linewidth=1, alpha=0.75)
            previous = row
    axis.set_xlim(TIME_RANGE)
    # Stable full-window bounds prevent plot rescaling from flickering during playback.
    speeds = [row["speed_m_s"] for track in tracks for row in track["velocities"]]
    axis.set_ylim(0, max(1.0, max(speeds, default=0.0) * 1.1))
    if not count:
        axis.text(0.5, 0.5, "MISSING velocity: no valid connected interval",
                  transform=axis.transAxes, ha="center", color="#90a6b6", fontsize=9)


def _camera_tracks(reconstruction: Json, camera_id: str) -> list[Json]:
    return [track for track in reconstruction["tracks"] if track["camera_id"] == camera_id]


def _shade_gaps(axis: Any, tracks: Sequence[Json]) -> None:
    for track in tracks:
        for gap in track["gaps"]:
            start, end = gap["time_range"]
            if end > start:
                axis.axvspan(start, end, color="#7e8994", alpha=0.08, linewidth=0)


def render_curve_figure(reconstruction: Json, camera_ids: Sequence[str]) -> Figure:
    """Two camera-local position and speed panels; no hidden identities or paths."""
    figure = Figure(figsize=(WIDTH / 100, HEIGHT / 100), dpi=100, facecolor=_BACKGROUND)
    grid = figure.subplots(len(camera_ids), 2, squeeze=False)
    for index, camera_id in enumerate(camera_ids):
        tracks = _camera_tracks(reconstruction, camera_id)
        position_axis, speed_axis = grid[index]
        _style(position_axis, f"{camera_id} | derived X / Y / Z", "Source time (s)", "Position (m)")
        _style(speed_axis, "INFERRED finite-difference speed", "Source time (s)", "Speed (m/s)")
        for ordinal, track in enumerate(tracks, 1):
            for coordinate in range(3):
                _plot_track(position_axis, track, ordinal, TIME_RANGE[1], coordinate=coordinate)
        position_axis.set_xlim(TIME_RANGE)
        position_axis.text(0.98, 0.95, "X: circle | Y: square | Z: triangle",
                           transform=position_axis.transAxes, ha="right",
                           color="#90a6b6", fontsize=8)
        _shade_gaps(position_axis, tracks)
        _shade_gaps(speed_axis, tracks)
        if not any(curve_segments(track["samples"]) for track in tracks):
            position_axis.text(0.5, 0.5, "MISSING: no projected pixel component",
                               transform=position_axis.transAxes, ha="center",
                               color="#90a6b6", fontsize=10)
        _plot_speed(speed_axis, tracks, TIME_RANGE[1])
    figure.suptitle("Blender diagnostic curves | camera-local tracks, unknown identity / behavior",
                   color=_FOREGROUND, fontsize=14, y=0.98)
    figure.text(0.05, 0.025, "OBSERVED pixels -> PROJECTED derived (cyan) | INFERRED short gap "
                "(dashed amber) | MISSING gaps stay disconnected | SYNTHETIC target / motion",
                color="#90a6b6", fontsize=9)
    figure.subplots_adjust(left=0.07, right=0.97, top=0.9, bottom=0.11, hspace=0.42, wspace=0.2)
    return figure


def _current_state(tracks: Sequence[Json], timestamp: float) -> str:
    states = []
    for track in tracks:
        for sample in track["samples"]:
            if abs(sample["timestamp"] - timestamp) <= 1e-8:
                states.append(sample["state"])
    if "PROJECTED_OBSERVATION" in states:
        return "OBSERVED pixels / PROJECTED derived; identity UNKNOWN"
    if "INFERRED_INTERPOLATION" in states:
        return "INFERRED short gap; uncertainty retained"
    return "MISSING projected evidence; no extrapolation"


def _video_frame(scene: MotionScene, reconstruction: Json, camera_ids: Sequence[str],
                 timestamp: float, snapshot: Json, image_status: Counter[str]) -> NDArray[np.uint8]:
    figure = Figure(figsize=(WIDTH / 100, HEIGHT / 100), dpi=100, facecolor=_BACKGROUND)
    canvas = FigureCanvasAgg(figure)
    grid = figure.add_gridspec(2, 2, height_ratios=[1, 0.95])
    timeline = scene.frames(camera_ids, timestamp)["frames"]
    for index, camera_id in enumerate(camera_ids):
        axis = figure.add_subplot(grid[0, index])
        row = next(r for r in timeline if r["camera_id"] == camera_id)
        tracks = _camera_tracks(reconstruction, camera_id)
        status = _current_state(tracks, timestamp)
        if row.get("media_ref") and row.get("status") == "EXACT":
            _, raw = scene.media(row["media_ref"])
            with Image.open(BytesIO(raw)) as image:
                pixels = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
            axis.imshow(pixels)
            image_status["SOURCE_RGB_EXACT"] += 1
        else:
            axis.set_facecolor("#1b2833")
            axis.text(0.5, 0.5, "MISSING source frame", transform=axis.transAxes,
                      ha="center", va="center", color=_FOREGROUND, fontsize=14)
            image_status["MISSING_SOURCE_FRAME"] += 1
        axis.set_title(f"{camera_id}\n{status}", color=_FOREGROUND, fontsize=9, loc="left", pad=7)
        axis.set_axis_off()
    xy, speed = figure.add_subplot(grid[1, 0]), figure.add_subplot(grid[1, 1])
    _style(xy, "Derived position XY | partial source context", "X (m)", "Y (m)")
    _style(speed, "INFERRED interval speed | missing intervals disconnected", "Source time (s)",
           "Speed (m/s)")
    meshes = snapshot.get("presentation", {}).get("meshes", [])
    for mesh in meshes:
        vertices = mesh["vertices"]
        # Original source-triangle outlines only; these are not movement constraints.
        outlines = []
        for triangle in mesh["triangles"]:
            corners = [vertices[v] for v in triangle]
            outlines.append([[p[0], p[1]] for p in corners + corners[:1]])
        xy.add_collection(LineCollection(outlines, colors="#42515e", alpha=0.12,
                                         linewidths=0.35))
    for camera_id in camera_ids:
        for ordinal, track in enumerate(_camera_tracks(reconstruction, camera_id), 1):
            _plot_track(xy, track, ordinal, timestamp)
    all_points = [point for mesh in meshes for point in mesh["vertices"]]
    all_points.extend(sample["world_position"] for track in reconstruction["tracks"]
                      for sample in track["samples"] if sample.get("world_position") is not None)
    for coordinate in range(2):
        values = [point[coordinate] for point in all_points]
        low, high = min(values, default=-1.0), max(values, default=1.0)
        padding = max(0.5, (high - low) * 0.05)
        if coordinate == 0:
            xy.set_xlim(low - padding, high + padding)
        else:
            xy.set_ylim(low - padding, high + padding)
    xy.set_aspect("equal", adjustable="box")
    _plot_speed(speed, reconstruction["tracks"], timestamp)
    _shade_gaps(speed, reconstruction["tracks"])
    speed.axvline(timestamp, color=_FOREGROUND, alpha=0.45, linewidth=0.8)
    figure.suptitle(f"Blender diagnostic reconstruction | source time {timestamp:.1f} s",
                   color=_FOREGROUND, fontsize=14, y=0.98)
    figure.text(0.045, 0.025, "SYNTHETIC target / motion | camera-local tracks only | "
                "PROJECTED is derived 3D | dashed = INFERRED short gap | "
                "MISSING gaps have no connecting line", color="#90a6b6", fontsize=9)
    figure.subplots_adjust(left=0.065, right=0.97, top=0.865, bottom=0.11, hspace=0.33, wspace=0.2)
    canvas.draw()  # type: ignore[no-untyped-call]
    rgba = canvas.buffer_rgba()  # type: ignore[no-untyped-call]
    pixels = np.asarray(rgba, dtype=np.uint8)[..., :3].copy()
    return pixels


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
        raise ValueError("MOTION_VIDEO_DECODE_FAILED") from None
    if result.returncode or progress.get("progress") != "end" or frames != FRAME_COUNT or (
        abs(duration - FRAME_COUNT / FPS) > 0.05
        or "Video: h264" not in log or "yuv420p" not in log
        or f"{WIDTH}x{HEIGHT}" not in log
    ):
        raise ValueError("MOTION_VIDEO_DECODE_FAILED")
    raw = path.read_bytes()
    if raw.find(b"moov") < 0 or raw.find(b"mdat") < 0 or raw.find(b"moov") > raw.find(b"mdat"):
        raise ValueError("MOTION_VIDEO_FASTSTART_MISSING")
    probe = shutil.which("ffprobe")
    if probe:
        entries = "stream=codec_name,pix_fmt,width,height,nb_frames"
        checked = subprocess.run([probe, "-v", "error", "-select_streams", "v:0",
                                  "-show_entries", entries,
                                  "-of", "json", str(path)], capture_output=True,
                                 timeout=30, check=False)
        if checked.returncode:
            raise ValueError("MOTION_VIDEO_PROBE_FAILED")
        rows = json.loads(checked.stdout)["streams"]
        if len(rows) != 1 or rows[0]["codec_name"] != "h264" or (
            rows[0]["pix_fmt"] != "yuv420p" or rows[0]["width"] != WIDTH
            or rows[0]["height"] != HEIGHT or int(rows[0]["nb_frames"]) != FRAME_COUNT
        ):
            raise ValueError("MOTION_VIDEO_PROBE_FAILED")
    return {"status": "PASS", "method": "FFMPEG_FULL_DECODE" if probe else
            "FFMPEG_FULL_DECODE_FALLBACK", "ffprobe_available": bool(probe),
            "frame_count": frames, "duration_s": duration, "width": WIDTH, "height": HEIGHT,
            "codec": "h264", "pixel_format": "yuv420p", "faststart": True}


def materialize_motion_artifacts(scene: MotionScene, output: Path) -> Json:
    """Create one site's explicit local plot/video package at a fresh destination."""
    output = output.resolve()
    if output.exists():
        raise FileExistsError("MOTION_OUTPUT_EXISTS")
    snapshot = scene.snapshot()
    camera_ids = sorted(row["camera_id"] for row in snapshot["cameras"])
    if len(camera_ids) != 2:
        raise ValueError("MOTION_PRESENTATION_CAMERA_BUDGET")
    reconstruction = _reconstruct(scene, camera_ids)
    if reconstruction["source_features"] != scene.index.source_features:
        raise ValueError("MOTION_SOURCE_FEATURES_MISMATCH")
    frames, inputs_hash = _public_inputs(scene, camera_ids)
    model_hash = content_hash(snapshot.get("presentation", {}))
    encoder, encoder_hash, encoder_version = _encoder()
    output.mkdir(parents=True)
    figure = render_curve_figure(reconstruction, camera_ids)
    curve_path = output / "curves.png"
    figure.savefig(curve_path, facecolor=_BACKGROUND, metadata={
        "Software": "Amidst local diagnostic renderer",
        "Description": "Camera-local derived curves; synthetic target/motion; unknown identity"})
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
            raise ValueError("MOTION_VIDEO_ENCODING_FAILED")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        process.kill()
        process.wait()
        raise ValueError("MOTION_VIDEO_ENCODING_FAILED") from None
    finally:
        process.stderr.close()
    validation = _full_decode(video_path, encoder)
    artifacts = []
    private = []
    for kind, path, mime in [("POSITION_VELOCITY_CURVES", curve_path, "image/png"),
                             ("RECONSTRUCTION_VIDEO", video_path, "video/mp4")]:
        value = {"media_ref": _media_ref(scene.index.source_features,
                                        reconstruction["reconstruction_sha256"], kind,
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
              "reconstruction_sha256": reconstruction["reconstruction_sha256"],
              "algorithm_sha256": _algorithm_sha(), "renderer_sha256": _renderer_sha(),
              "render_config_sha256": content_hash(_RENDER_CONFIG),
              "input_frames_sha256": inputs_hash, "render_model_sha256": model_hash,
              "encoder_sha256": encoder_hash, "encoder_version": encoder_version,
              "selection": {"camera_ids": camera_ids, "time_range": list(TIME_RANGE)},
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


class MotionMediaProvider:
    """Lazy verified artifacts; no encoding, synthesis or caller locators on reads."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _load(self, scene: MotionScene) -> tuple[Json, Path] | None:
        snapshot = scene.snapshot()
        site = snapshot["source_binding"]["site_id"]
        if site not in {"office", "classroom101", "auditorium"}:
            raise ValueError("MOTION_MEDIA_SCOPE_DENIED")
        folder = self.root / site
        path = folder / "manifest.json"
        if not path.exists():
            return None
        if folder.is_symlink() or path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError("MOTION_MEDIA_SCOPE_DENIED")
        try:
            if path.stat().st_size > 1024 * 1024:
                raise ValueError("MOTION_MEDIA_STALE")
            value = json.loads(path.read_bytes())
            if set(value) != {"schema_version", "public", "artifacts", "input_frames",
                              "input_frames_sha256"} or value["schema_version"] != _SCHEMA:
                raise ValueError("MOTION_MEDIA_STALE")
            public = value["public"]
            if set(public) != _PUBLIC_KEYS or public["schema_version"] != _SCHEMA or (
                public["source_types"] != _SOURCE_TYPES or public["limitations"] != _LIMITATIONS
                or any(public[key] is not False for key in (
                    "agent_used", "formal_acceptance", "source_copied", "source_modified"))
            ):
                raise ValueError("MOTION_MEDIA_STALE")
            cameras = sorted(row["camera_id"] for row in snapshot["cameras"])
            reconstruction = _reconstruct(scene, cameras)
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
                raise ValueError("MOTION_MEDIA_STALE")
            if (public["source_features"] != scene.index.source_features
                or public["source_binding"] != reconstruction["source_binding"]
                or public["reconstruction_sha256"] != reconstruction["reconstruction_sha256"]
                or public["algorithm_sha256"] != _algorithm_sha()
                or public["renderer_sha256"] != _renderer_sha()
                or public["render_config_sha256"] != content_hash(_RENDER_CONFIG)
                or public["encoder_sha256"] != encoder_hash
                or public["encoder_version"] != encoder_version
                or public["input_frames_sha256"] != inputs_hash
                or value["input_frames_sha256"] != inputs_hash
                or content_hash(value["input_frames"]) != inputs_hash
                or public["render_model_sha256"] != content_hash(snapshot.get("presentation", {}))
                or public["selection"] != {"camera_ids": cameras, "time_range": TIME_RANGE}
                or public["status"] != "AVAILABLE"
                or len(public["items"]) != 2 or len(value["artifacts"]) != 2
            ):
                raise ValueError("MOTION_MEDIA_STALE")
            source = {row["frame_ref"]: row for row in scene.export_safe_inputs()["frames"]}
            for row in value["input_frames"]:
                original = source[row["frame_ref"]]
                original_path = Path(original["local_path"])
                if original_path.is_symlink() or original_path.resolve() != original_path or (
                    original_path.stat().st_size != row["byte_count"]
                ) or (
                    _file_sha(original_path) != row["sha256"]
                ):
                    raise ValueError("MOTION_MEDIA_STALE")
            for item, private in zip(public["items"], value["artifacts"], strict=True):
                expected = {"POSITION_VELOCITY_CURVES": ("curves.png", "image/png"),
                            "RECONSTRUCTION_VIDEO": ("reconstruction.mp4", "video/mp4")}
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
                        public["reconstruction_sha256"], item["kind"],
                        public["renderer_sha256"], item["sha256"])
                ):
                    raise ValueError("MOTION_MEDIA_SCOPE_DENIED")
                artifact = folder / private["relative_path"]
                if artifact.is_symlink() or not artifact.resolve().is_relative_to(folder) or (
                    artifact.stat().st_size != item["byte_count"]
                    or _file_sha(artifact) != item["sha256"]
                ):
                    raise ValueError("MOTION_MEDIA_STALE")
            if [item["kind"] for item in public["items"]] != [
                "POSITION_VELOCITY_CURVES", "RECONSTRUCTION_VIDEO"]:
                raise ValueError("MOTION_MEDIA_STALE")
            # Every public object uses a fixed contract; private filenames are never returned.
            return value, folder
        except (OSError, KeyError, TypeError, ValueError):
            raise ValueError("MOTION_MEDIA_STALE") from None

    def manifest(self, scene: MotionScene) -> Json:
        loaded = self._load(scene)
        if loaded is None:
            return {"status": "UNAVAILABLE", "items": [], "reason": "NOT_MATERIALIZED"}
        return copy.deepcopy(loaded[0]["public"])

    def media(self, scene: MotionScene, ref: str) -> tuple[str, bytes]:
        if _REF.fullmatch(ref) is None:
            raise ValueError("MOTION_MEDIA_SCOPE_DENIED")
        loaded = self._load(scene)
        if loaded is None:
            raise ValueError("MOTION_MEDIA_UNAVAILABLE")
        manifest, folder = loaded
        for item, private in zip(manifest["public"]["items"], manifest["artifacts"], strict=True):
            if item["media_ref"] == ref:
                raw = (folder / private["relative_path"]).read_bytes()
                if _sha(raw) != item["sha256"]:
                    raise ValueError("MOTION_MEDIA_STALE")
                return item["mime_type"], raw
        raise ValueError("MOTION_MEDIA_SCOPE_DENIED")
