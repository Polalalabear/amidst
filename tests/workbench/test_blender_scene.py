"""Source-bound RGB import, pixel-preserving media and stale-bundle rejection."""

import gzip
import hashlib
import json
import struct
import zlib
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw
from PIL.PngImagePlugin import PngInfo

from amidst.workbench import blender_scene as blender
from amidst.workbench.reviews import ReviewStore


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True).encode()
    if path.suffix == ".gz":
        raw = gzip.compress(raw, mtime=0)
    path.write_bytes(raw)
    return sha(raw)


@pytest.fixture
def bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    repo, canonical = tmp_path / "repo", tmp_path / "canonical"
    source = canonical / "blender/school_v3.blend"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"immutable test source; never loaded by Blender")
    source_sha = sha(source.read_bytes())
    monkeypatch.setattr(blender, "SOURCE_SHA256", source_sha)
    geometry = {"source_sha256": source_sha,
                "evaluated_scene": {"name": "Scene", "frame": 220, "subframe": 0.0},
                "geometry_modified": False, "saved": False,
                "meshes": [{"source_object_id": name, "full_object_exported": True,
                            "geometry_sha256": letter * 64,
                            "vertices": [[1200, 1800, 20], [1450, 1800, 20],
                                         [1450, 2100, 20], [1200, 1800, 120]],
                            "triangles": [[0, 1, 2], [0, 1, 3]]}
                           for name, letter in [("group_0", "a"), ("group_0.002", "b")]]}
    support = {"source_sha256": source_sha, "scale_m_per_bu": 0.0247,
               "authority_scope": "SUPPORTED_PERMISSION_INTERSECTION",
               "floor_authorities": [{"floor_id": "1F", "point": [0, 0, 20],
                                       "normal": [0, 0, 1], "authority": "APPROVED"}],
               "walkable_reviews": [{"walkable_id": "WALK_1F_OFFICE", "authority": "APPROVED",
                                     "source_selection_complete": True,
                                     "source_support_height_bu": 20,
                                     "support_surface_ids": ["source-support"]}],
               "support_surfaces": [{"surface_id": "source-support",
                                     "vertices": [[1200, 1800, 20], [1450, 2100, 20]]}]}
    scale = {"source_asset_sha256": source_sha, "authority": "APPROVED",
             "metres_per_blender_unit": 0.0247}
    pins = {ref: write_json(repo / ref, value) for ref, value in [
        (blender._GEOMETRY, geometry), (blender._SUPPORT, support), (blender._SCALE, scale)]}
    monkeypatch.setattr(blender, "_PINS", pins)
    info = PngInfo()
    info.add_text("File", "/private/source/school_v3.blend")
    info.add_text("TrajectoryID", "DO_NOT_EXPORT_SIMULATOR_ACTOR")
    site_root = canonical / "data/pilot/school_v3_multisite_20261005/office"
    camera_ids = ("CAM_A", "CAM_B")
    cameras = [{"camera_id": camera_id,
                "camera_to_world": [[1, 0, 0, 1300], [0, 1, 0, 2000],
                                    [0, 0, 1, 160], [0, 0, 0, 1]],
                "fx": 640, "fy": 640, "cx": 480, "cy": 270,
                "width": 960, "height": 540, "clip_start": 0.1, "clip_end": 1000,
                "convention": "BLENDER_NEG_Z_UP_Y", "pixel_origin": "TOP_LEFT_CONTINUOUS",
                "floor_id": "1F", "zone_id": "TEST_SOURCE"} for camera_id in camera_ids]
    timestamps = []
    for index in range(50):
        image = Image.new("RGB", (960, 540), (70, 70, 70))
        x = 100 + index * 8
        ImageDraw.Draw(image).rectangle((x, 190, x + 30, 250), fill=(240, 110, 20))
        output = BytesIO()
        image.save(output, format="PNG", pnginfo=info)
        png = output.getvalue()
        per_camera = []
        for camera_id in camera_ids:
            relative = f"frames/{camera_id}/frame_{index:03d}.png"
            path = site_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png)
            per_camera.append({"camera_id": camera_id, "render": {"path": relative,
                                                                   "sha256": sha(png)},
                               "visibility": "DO_NOT_USE_RENDERER_VISIBILITY",
                               "observation": {"target_id": "DO_NOT_USE_TARGET_ID"},
                               "blender_projection": {"pixel": [9999, 9999], "depth": -1}})
        timestamps.append({"index": index, "timestamp": index / 5,
                           "ground_truth": {"position": [9999, 9999, 9999]},
                           "per_camera": per_camera})
    dataset = {"data_kind": "SYNTHETIC", "site_id": "office", "sampling_fps": 5,
               "timestamps": timestamps, "cameras": cameras,
               "source_scene": {"sha256_before": source_sha, "sha256_after": source_sha},
               "trajectory": {"secret": "DO_NOT_EXPORT_SIMULATION_RECIPE"},
               "render_policy": {"source_scene_saved": False, "geometry_frame": 220,
                                 "geometry_subframe": 0,
                                 "png_label_policy":
                                     "SYNTHETIC_PROVENANCE_TEXT_CHUNKS_RENDERED_PIXELS_UNCHANGED"}}
    dataset_sha = write_json(site_root / "dataset.json", dataset)
    monkeypatch.setattr(blender, "SITE_PINS", {"office": dataset_sha})
    root = repo / "data/engineering/local_run/blender_camera_v1"
    receipt = blender.materialize_blender_workbench(repo, canonical, root, ["office"])
    assert receipt["source_before"] == receipt["source_after"]
    assert receipt["rendered"] is receipt["source_copied"] is receipt["media_copied"] is False
    return root / "office", canonical, repo


def test_materialization_extracts_only_safe_fields_and_source_scale(
    bundle: tuple[Path, Path, Path],
) -> None:
    root, _, _ = bundle
    inputs = json.loads((root / "safe_inputs.json").read_text())
    text = json.dumps(inputs)
    assert all(word not in text for word in ["ground_truth", "trajectory", "visibility",
                                            "blender_projection", "DO_NOT_"])
    assert inputs["floor_plane"]["point"] == [0, 0, 0.494]
    assert inputs["cameras"][0]["calibration"]["camera_to_world"][0][3] == 32.11
    assert inputs["cameras"][0]["calibration"]["clip_end"] == 24.7
    assert inputs["presentation"]["display_triangle_count"] > 0
    assert inputs["presentation"]["authority"] == "PARTIAL_DISPLAY_CONTEXT"
    assert all(not m["derivation"]["new_caps_created"]
               for m in inputs["presentation"]["meshes"])


def test_adapter_real_pixel_queries_reopen_and_public_no_paths(
    bundle: tuple[Path, Path, Path],
) -> None:
    root, _, _ = bundle
    first, reopened = blender.load_blender_scene(root), blender.load_blender_scene(root)
    result = first.frame_query(["CAM_A", "CAM_B"], 0, 1, 0.4, 3)
    assert result == reopened.frame_query(["CAM_A", "CAM_B"], 0, 1, 0.4, 3)
    assert len(result["items"]) == 3
    public = json.dumps([first.snapshot(), first.summary(), result, first.query("CAM_A", 0, 1),
                         first.frames(["CAM_A", "CAM_B"], 0.4), first.live_scope()])
    assert all(word not in public for word in ["local_path", "/private/", "canonical/",
                                             "ground_truth", "trajectory", "DO_NOT_"])
    assert first.snapshot()["capabilities"]["frame_query"] is True
    assert first.snapshot()["capabilities"]["navigation_guidance"] is False
    assert first.query("CAM_A", 0, 1)["events"] == []
    assert first.evaluation()["status"] == "UNAVAILABLE"
    with pytest.raises(ValueError, match="BASELINE_EVENT_NOT_GENERATED"):
        first.event("event:unknown")
    with pytest.raises(ValueError):
        first.frame_query(["CAM_FOREIGN"], 0, 1, 0.4, 3)


def test_media_strips_private_png_text_and_preserves_pixels_and_idat(
    bundle: tuple[Path, Path, Path],
) -> None:
    root, _, _ = bundle
    scene = blender.load_blender_scene(root)
    frame = scene.export_safe_inputs()["frames"][0]
    raw = Path(frame["local_path"]).read_bytes()
    media_type, served = scene.media(frame["frame_ref"])
    assert media_type == "image/png"
    assert b"/private/" not in served and b"TrajectoryID" not in served
    assert sha(served) == frame["served_sha256"] and sha(raw) == frame["sha256"]
    assert Image.open(BytesIO(raw)).tobytes() == Image.open(BytesIO(served)).tobytes()
    assert b"IDAT" in served
    assert blender.strip_png_text(served) == served
    with pytest.raises(ValueError, match="MEDIA_SCOPE_DENIED"):
        scene.media("/etc/passwd")


def test_source_readonly_objects_fit_existing_strict_review_baseline(
    bundle: tuple[Path, Path, Path], tmp_path: Path,
) -> None:
    root, _, _ = bundle
    scene = blender.load_blender_scene(root)
    snapshot = scene.snapshot()
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    store = ReviewStore(tmp_path / "source-review.sqlite3", {
        scene.scene_id: {key: snapshot[key] for key in keys}})
    state = store.state(scene.scene_id)
    assert state["current_version"] == 0
    assert state["baseline_objects"] == snapshot["objects"]
    assert snapshot["cameras"][0]["calibration"]["clip_end"] == 24.7
    assert "clip_end" not in snapshot["objects"][0]["properties"]
    for obj in snapshot["objects"]:
        assert obj["editable_fields"] == []
        with pytest.raises(ValueError, match="FIELD_NOT_EDITABLE"):
            store.save_draft(scene.scene_id, obj["object_id"], {"label": "attempt"},
                             0, "test", "readonly source")
    assert store.state(scene.scene_id)["drafts"] == []


@pytest.mark.parametrize("resource", ["safe_inputs.json", "manifest.json", "source", "dataset"])
def test_changed_binding_refused(bundle: tuple[Path, Path, Path], resource: str) -> None:
    root, canonical, _ = bundle
    scene = blender.load_blender_scene(root)
    path = {"source": canonical / "blender/school_v3.blend",
            "dataset": canonical / "data/pilot/school_v3_multisite_20261005/office/dataset.json"
            }.get(resource, root / resource)
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="BLENDER_SCENE_STALE"):
        scene.snapshot()


def test_changed_or_symlink_media_refused(bundle: tuple[Path, Path, Path], tmp_path: Path) -> None:
    root, _, _ = bundle
    scene = blender.load_blender_scene(root)
    frame = scene.export_safe_inputs()["frames"][0]
    path = Path(frame["local_path"])
    original = path.read_bytes()
    path.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="BLENDER_MEDIA_HASH_MISMATCH"):
        scene.media(frame["frame_ref"])
    foreign = tmp_path / "foreign.png"
    foreign.write_bytes(original)
    path.unlink()
    path.symlink_to(foreign)
    with pytest.raises(ValueError, match="MEDIA_SCOPE_DENIED"):
        scene.media(frame["frame_ref"])


def test_extensible_metadata_refused_even_with_self_consistent_bundle_hash(
    bundle: tuple[Path, Path, Path],
) -> None:
    root, _, _ = bundle
    inputs = json.loads((root / "safe_inputs.json").read_text())
    inputs["source_binding"]["private_source_path"] = "/private/source.blend"
    raw = blender._json_bytes(inputs)
    (root / "safe_inputs.json").write_bytes(raw)
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["inputs_sha256"] = sha(raw)
    (root / "manifest.json").write_bytes(blender._json_bytes(manifest))
    with pytest.raises(ValueError, match="BLENDER_SCENE_STALE"):
        blender.load_blender_scene(root)


def test_png_corruption_and_trailing_payload_refused() -> None:
    output = BytesIO()
    Image.new("RGB", (2, 2)).save(output, format="PNG")
    png = output.getvalue()
    for raw in (b"not-png", png[:-1], png + b"private payload", png[:35] + b"broken" + png[41:]):
        with pytest.raises(ValueError, match="INVALID_BLENDER_PNG"):
            blender.strip_png_text(raw)
    payload = b"iTXt" + b"private\x00data"
    chunk = struct.pack(">I", len(payload) - 4) + payload + struct.pack(">I", zlib.crc32(payload))
    assert blender.strip_png_text(png[:-12] + chunk + png[-12:]) == png
