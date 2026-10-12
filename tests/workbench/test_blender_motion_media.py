"""Actual source-RGB decoding, disconnected curves and strictly bound media reads."""

import json
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from matplotlib.figure import Figure
from PIL import Image
from test_blender_scene import bundle as bundle

from amidst.workbench import blender_motion_media as media
from amidst.workbench.blender_scene import load_blender_scene


def samples() -> list[dict[str, Any]]:
    return [
        {"timestamp": 0.0, "world_position": [0.0, 0.0, 0.5],
         "state": "PROJECTED_OBSERVATION", "connect_from_previous": False},
        {"timestamp": 0.2, "world_position": [0.2, 0.0, 0.5],
         "state": "PROJECTED_OBSERVATION", "connect_from_previous": True},
        {"timestamp": 0.4, "world_position": None, "state": "MISSING",
         "connect_from_previous": False},
        {"timestamp": 0.6, "world_position": [9.0, 0.0, 0.5],
         "state": "PROJECTED_OBSERVATION", "connect_from_previous": False},
        {"timestamp": 0.8, "world_position": [9.2, 0.0, 0.5],
         "state": "INFERRED_INTERPOLATION", "connect_from_previous": True},
        {"timestamp": 1.0, "world_position": [20.0, 0.0, 0.5],
         "state": "PROJECTED_OBSERVATION", "connect_from_previous": False},
    ]


def test_curve_segments_do_not_bridge_missing_disconnected_or_future_points() -> None:
    groups = media.curve_segments(samples())
    assert [[s["timestamp"] for s in group] for group in groups] == [[0, 0.2], [0.6, 0.8], [1]]
    assert [[s["timestamp"] for s in group] for group in media.curve_segments(samples(), 0.6)] == [
        [0, 0.2], [0.6]]
    figure = Figure()
    axis = figure.subplots()
    media._plot_track(axis, {"samples": samples()}, 1, 1.0, coordinate=0)
    assert [list(line.get_xdata()) for line in axis.lines] == [[0, 0.2], [0.6, 0.8]]
    assert [line.get_linestyle() for line in axis.lines] == ["-", "--"]


def test_empty_camera_curves_explicit_missing_and_no_opaque_identity() -> None:
    reconstruction = {"tracks": [{"camera_id": "CAM_A", "track_ref": "track:PRIVATE_OPAQUE",
                                  "samples": samples(), "velocities": [], "gaps": []}]}
    figure = media.render_curve_figure(reconstruction, ["CAM_A", "CAM_B"])
    labels = [text.get_text() for text in figure.texts]
    labels.extend(text.get_text() for axis in figure.axes for text in axis.texts)
    assert any("MISSING" in label for label in labels)
    assert any("SYNTHETIC target" in label for label in labels)
    assert any("PROJECTED derived" in label for label in labels)
    assert all("track:" not in label and "event:" not in label for label in labels)
    assert media._current_state([], 0.0).startswith("MISSING")
    assert media._current_state(reconstruction["tracks"], 0.8).startswith("INFERRED")


def test_video_speed_bounds_remain_stable_and_intervals_do_not_bridge() -> None:
    velocities = [{"timestamp": 0.1, "time_range": [0.0, 0.2], "speed_m_s": 1.0},
                  {"timestamp": 0.7, "time_range": [0.6, 0.8], "speed_m_s": 7.0}]
    figure = Figure()
    first, final = figure.subplots(1, 2)
    media._plot_speed(first, [{"velocities": velocities}], 0.2)
    media._plot_speed(final, [{"velocities": velocities}], 9.8)
    assert first.get_ylim() == final.get_ylim() == (0.0, 7.700000000000001)
    assert not first.lines and not final.lines


def test_real_encode_decode_and_bound_private_free_runtime(
    bundle: tuple[Path, Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, _ = bundle
    scene = load_blender_scene(root)
    pool = tmp_path / "motion-pool"
    provider = media.MotionMediaProvider(pool)
    assert provider.manifest(scene) == {"status": "UNAVAILABLE", "items": [],
                                         "reason": "NOT_MATERIALIZED"}
    before = scene.export_safe_inputs()
    public = media.materialize_motion_artifacts(scene, pool / "office")
    assert public["validation"]["status"] == "PASS"
    assert public["validation"]["frame_count"] == 50
    assert public["validation"]["duration_s"] == 10
    assert public["validation"]["codec"] == "h264"
    assert public["validation"]["pixel_format"] == "yuv420p"
    assert public["validation"]["faststart"] is True
    assert public["source_image_status"] == {"SOURCE_RGB_EXACT": 100}
    assert scene.export_safe_inputs() == before
    assert provider.manifest(scene) == public
    assert public["agent_used"] is public["formal_acceptance"] is False
    assert not any(text in json.dumps(public) for text in (
        "local_path", "relative_path", "/private/", "TrajectoryID", "DO_NOT_"))
    assert {row["kind"] for row in public["items"]} == {
        "POSITION_VELOCITY_CURVES", "RECONSTRUCTION_VIDEO"}
    for item in public["items"]:
        mime, raw = provider.media(scene, item["media_ref"])
        assert mime == item["mime_type"] and media._sha(raw) == item["sha256"]
        if mime == "image/png":
            with Image.open(BytesIO(raw)) as image:
                assert image.size == (1280, 720)
        else:
            assert b"moov" in raw and raw.find(b"moov") < raw.find(b"mdat")
    with pytest.raises(FileExistsError, match="MOTION_OUTPUT_EXISTS"):
        media.materialize_motion_artifacts(scene, pool / "office")

    def no_encoding(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("GET-equivalent reads attempted encoding")

    monkeypatch.setattr(media, "_video_frame", no_encoding)
    assert provider.manifest(scene) == public
    for invalid_ref in ("/etc/passwd", "motion-media:" + "f" * 24):
        with pytest.raises(ValueError, match="MOTION_MEDIA_SCOPE_DENIED"):
            provider.media(scene, invalid_ref)
    manifest_path = pool / "office/manifest.json"
    original_manifest = manifest_path.read_bytes()
    original = json.loads(original_manifest)
    changes = [
        ("renderer_sha256", "f" * 64), ("reconstruction_sha256", "e" * 64),
        ("source_features", "d" * 64), ("input_frames_sha256", "c" * 64),
        ("private_source_path", "/private/unapproved.blend"),
        ("validation", {**public["validation"], "private_path": "/private/unapproved"}),
        ("source_image_status", {"/private/unapproved": 100}),
        ("encoder_version", "/private/unapproved"),
    ]
    for field, value in changes:
        changed = json.loads(original_manifest)
        changed["public"][field] = value
        manifest_path.write_text(json.dumps(changed))
        with pytest.raises(ValueError, match="MOTION_MEDIA_STALE"):
            provider.manifest(scene)
    manifest_path.write_bytes(original_manifest)
    changed = json.loads(original_manifest)
    changed["public"]["items"][0]["width"] = "/private/unapproved"
    manifest_path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="MOTION_MEDIA_STALE"):
        provider.manifest(scene)
    manifest_path.write_bytes(original_manifest)
    changed = json.loads(original_manifest)
    changed["artifacts"][0]["relative_path"] = "../foreign.png"
    manifest_path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="MOTION_MEDIA_STALE"):
        provider.manifest(scene)
    manifest_path.write_bytes(original_manifest)
    video_path = pool / "office/reconstruction.mp4"
    video = video_path.read_bytes()
    video_path.write_bytes(video + b"corruption")
    with pytest.raises(ValueError, match="MOTION_MEDIA_STALE"):
        provider.media(scene, public["items"][1]["media_ref"])
    video_path.write_bytes(video)
    source_path = Path(before["frames"][0]["local_path"])
    source = source_path.read_bytes()
    source_path.write_bytes(source + b"corruption")
    with pytest.raises(ValueError, match="MOTION_MEDIA_STALE"):
        provider.manifest(scene)
    source_path.write_bytes(source)
    assert provider.manifest(scene) == public
    assert original["public"] == public
