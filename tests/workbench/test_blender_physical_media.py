"""Actual source-RGB decoding, disconnected curves and strictly bound media reads."""

import copy
import json
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from matplotlib.figure import Figure
from PIL import Image
from test_blender_scene import bundle as bundle

from amidst.workbench import blender_physical_media as media
from amidst.workbench.blender_association import BaselineAssociationIndex
from amidst.workbench.blender_scene import load_blender_scene


def physical_result(value: dict[str, Any]) -> dict[str, Any]:
    """Explicit synthetic display fixture; does not certify school physics."""
    result = copy.deepcopy(value)
    result["rejected_candidates"] = []
    result["geometry_context"] = {"units": "METRES", "partial": True,
                                   "support_polygons": [], "colliders": []}
    for candidate in result["candidates"]:
        candidate["physical"] = {
            "verdict": "UNKNOWN", "reasons": [],
            "unknowns": [{"code": "PORTAL_APERTURE_UNAPPROVED", "status": "UNKNOWN"}],
            "scores": {"ranking_score": candidate.get("score", 0)},
            "complete_physical_validation": False,
        }
    return result


class FixtureScene:
    """Proxy test RGB with prebuilt synthetic physical output, never school approval."""

    def __init__(self, scene: Any) -> None:
        self.scene = scene
        self.physical = self
        snapshot = scene.snapshot()
        cameras = sorted(row["camera_id"] for row in snapshot["cameras"])
        base = BaselineAssociationIndex(scene.index.snapshot()).reconstruct(cameras, 0, 9.8, 3)
        self.result = physical_result(base)
        self.result.update({"physical_sha256": "f" * 64,
            "base_association_sha256": base["association_sha256"],
            "physical_source_sha256": "a" * 64,
            "evidence_hashes": {"synthetic_fixture": "b" * 64},
            "authority_coverage": {"physical_complete": False,
                                   "collision_free_certified": False}})
        self.result["summary"]["physical_rejected"] = 0
        self.inputs = {"schema_version": "workbench.blender-physical-source-inputs.v1",
            "summary": {"schema_version": "workbench.blender-physical-source.v1",
                "status": "AVAILABLE", "source_sha256": snapshot["source_binding"]["source_sha256"],
                "physical_source_sha256": "a" * 64,
                "evidence_hashes": {"synthetic_fixture": "b" * 64},
                "coverage": {"physical_complete": False}},
            "units": "METRES", "surfaces": [], "geometry_is_partial": True,
            "gt_used": False, "agent_used": False}

    def __getattr__(self, name: str) -> Any:
        return getattr(self.scene, name)

    def reconstruct(self, *_args: Any) -> dict[str, Any]:
        return copy.deepcopy(self.result)

    def export_physical_source(self) -> dict[str, Any]:
        return copy.deepcopy(self.inputs)


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


def test_curve_segments_do_not_connect_missing_or_disconnected_points() -> None:
    rows = samples()
    rows[4]["state"] = "INFERRED_CROSS_CAMERA"
    groups = media.curve_segments(rows)
    assert [[s["timestamp"] for s in group] for group in groups] == [[0, 0.2], [0.6, 0.8], [1]]
    assert [[s["timestamp"] for s in group] for group in media.curve_segments(rows, 0.6)] == [
        [0, 0.2], [0.6]]
    figure = Figure()
    axis = figure.subplots()
    media._plot_path(axis, {"samples": rows}, "#ffffff", 1.0, coordinate=0)
    assert [list(line.get_xdata()) for line in axis.lines] == [[0, 0.2], [0.6, 0.8]]
    assert [line.get_linestyle() for line in axis.lines] == ["-", "--"]


def test_no_cross_evidence_one_baseline_and_missing_camera_not_fabricated_k() -> None:
    reconstruction = {
        "status": "NO_CROSS_CAMERA_EVIDENCE",
        "candidates": [{"rank": 1, "candidate_ref": "candidate:PRIVATE_OPAQUE", "score": 0,
                        "paths": [{"samples": samples(), "velocities": [], "gaps": []}]}],
        "camera_coverage": [{"camera_id": "CAM_B", "state": "MISSING"}],
    }
    figure = media.render_curve_figure(physical_result(reconstruction), ["CAM_A", "CAM_B"])
    labels = [text.get_text() for text in figure.texts]
    labels.extend(text.get_text() for axis in figure.axes for text in axis.texts)
    assert len(figure.axes) == 2
    assert any("retained 1/3" in label for label in labels)
    assert any("MISSING camera: CAM_B" in label for label in labels)
    assert any("SYNTHETIC target/motion" in label for label in labels)
    assert any("heuristic" in label for label in labels)
    assert all("candidate:" not in label and "event:" not in label for label in labels)
    assert media._current_state([], 0.0).startswith("MISSING")


def test_curve_and_video_axes_use_full_window_stable_bounds() -> None:
    velocities = [{"timestamp": 0.1, "time_range": [0, 0.2], "speed_m_s": 1.0},
                  {"timestamp": 0.7, "time_range": [0.6, 0.8], "speed_m_s": 7.0}]
    reconstruction = {"candidates": [{"paths": [{"samples": samples(),
                                               "velocities": velocities}]}]}
    bounds = media._bounds(reconstruction)
    assert bounds[1] == (0.0, 7.700000000000001)
    figure = Figure()
    first, final = figure.subplots(1, 2)
    media._plot_speed(first, [{"velocities": velocities}], "#ffffff", 0.2)
    media._plot_speed(final, [{"velocities": velocities}], "#ffffff", 9.8)
    assert not first.lines and not final.lines


@pytest.mark.parametrize("key", ["association_edge_ref", "association_edge_refs"])
def test_adjacent_projected_handoff_is_drawn_as_inference(key: str) -> None:
    rows = samples()[:2]
    rows[1][key] = "edge:opaque" if key == "association_edge_ref" else ["edge:opaque"]
    figure = Figure()
    axis = figure.subplots()
    media._plot_path(axis, {"samples": rows}, "#ffffff", 1, coordinate=0)
    assert [line.get_linestyle() for line in axis.lines] == ["--"]
    assert [line.get_color() for line in axis.lines] == [media._INFERRED]


def test_long_missing_bridge_3d_relation_only_after_both_endpoints() -> None:
    figure = Figure()
    early = figure.add_subplot(121, projection="3d")
    final = figure.add_subplot(122, projection="3d")
    reconstruction = {"graph": {"nodes": [
        {"node_ref": "node:left", "samples": [{"timestamp": 0, "world_position": [1, 2, 0.5]}]},
        {"node_ref": "node:right", "samples": [{"timestamp": 2, "world_position": [4, 5, 0.5]}]},
    ], "edges": [{"edge_ref": "edge:gap", "from_node_ref": "node:left",
                  "to_node_ref": "node:right", "bridge_missing": True}]}}
    candidate = {"selected_edge_refs": ["edge:gap"]}
    media._plot_missing_association_edges(early, reconstruction, candidate, 1)
    media._plot_missing_association_edges(final, reconstruction, candidate, 2)
    assert not early.lines
    assert len(final.lines) == 2
    assert final.lines[0].get_linestyle() == "--"
    assert final.lines[0].get_color() == "#9aa6b0"
    assert [list(row) for row in final.lines[0].get_data_3d()] == [[1, 4], [2, 5], [0.5, 0.5]]


def test_simultaneous_overlap_sources_remain_independent_hollow_points() -> None:
    rows = samples()[:2]
    rows[0]["overlap_support"] = [{"world_position": [3, 4, 0.5],
                                  "state": "PROJECTED_OBSERVATION", "uncertainty": 0.2}]
    figure = Figure()
    axis = figure.subplots()
    media._plot_path(axis, {"samples": rows}, "#ffffff", 1, coordinate=0)
    assert [list(line.get_ydata()) for line in axis.lines] == [[0, 0.2]]
    assert [list(row) for row in axis.collections[-1].get_offsets()] == [[0, 3]]
    assert axis.collections[-1].get_facecolors().size == 0
    assert media._overlap_points({"samples": rows})[0]["world_position"] == [3, 4, 0.5]


def test_split_local_hard_gaps_are_preserved_as_shading_and_counts() -> None:
    candidate = {"rank": 1, "score": 0, "paths": [{"samples": samples(),
                                                 "velocities": [], "gaps": []}],
                 "unresolved_local_gaps": [{"time_range": [0.4, 0.6],
                                            "state": "MISSING", "reason": "SPEED_CAP"}]}
    reconstruction = {"status": "NO_CROSS_CAMERA_EVIDENCE", "candidates": [candidate],
                      "camera_coverage": []}
    figure = media.render_curve_figure(physical_result(reconstruction), ["CAM_A"])
    assert all(len(axis.patches) == 1 for axis in figure.axes)
    assert "gaps 1" in figure.axes[0].get_title(loc="left")


def test_real_encode_decode_and_bound_private_free_runtime(
    bundle: tuple[Path, Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, _ = bundle
    scene = FixtureScene(load_blender_scene(root))
    pool = tmp_path / "physical-pool"
    provider = media.PhysicalMediaProvider(pool)
    assert provider.manifest(scene) == {"status": "UNAVAILABLE", "items": [],
                                         "reason": "NOT_MATERIALIZED"}
    before = scene.export_safe_inputs()
    public = media.materialize_physical_artifacts(scene, pool / "office")
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
    assert public["selection"]["top_k"] == 3
    assert public["rejected_candidate_count"] == public["rejected_candidate_count_video"] == 0
    assert public["authority_coverage"]["collision_free_certified"] is False
    assert 1 <= public["candidate_count"] <= 3
    assert not any(text in json.dumps(public) for text in (
        "local_path", "relative_path", "/private/", "TrajectoryID", "DO_NOT_"))
    assert {row["kind"] for row in public["items"]} == {
        "PHYSICAL_POSITION_VELOCITY_CURVES", "PHYSICAL_CROSS_CAMERA_VIDEO"}
    for item in public["items"]:
        mime, raw = provider.media(scene, item["media_ref"])
        assert mime == item["mime_type"] and media._sha(raw) == item["sha256"]
        if mime == "image/png":
            with Image.open(BytesIO(raw)) as image:
                assert image.size == (1280, 720)
        else:
            assert b"moov" in raw and raw.find(b"moov") < raw.find(b"mdat")
    with pytest.raises(FileExistsError, match="PHYSICAL_OUTPUT_EXISTS"):
        media.materialize_physical_artifacts(scene, pool / "office")

    def no_encoding(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("GET-equivalent reads attempted encoding")

    monkeypatch.setattr(media, "_video_frame", no_encoding)
    original_reconstruct = media._reconstruct
    monkeypatch.setattr(media, "_reconstruct", no_encoding)
    assert provider.manifest(scene) == public
    for invalid_ref in ("/etc/passwd", "physical-media:" + "f" * 24):
        with pytest.raises(ValueError, match="PHYSICAL_MEDIA_SCOPE_DENIED"):
            provider.media(scene, invalid_ref)
    manifest_path = pool / "office/manifest.json"
    original_manifest = manifest_path.read_bytes()
    original = json.loads(original_manifest)
    changes = [
        ("renderer_sha256", "f" * 64), ("physical_sha256", "e" * 64),
        ("source_features", "d" * 64), ("input_frames_sha256", "c" * 64),
        ("private_source_path", "/private/unapproved.blend"),
        ("validation", {**public["validation"], "private_path": "/private/unapproved"}),
        ("source_image_status", {"/private/unapproved": 100}),
        ("encoder_version", "/private/unapproved"),
        ("motion_algorithm_sha256", "a" * 64), ("candidate_count", 99),
        ("physical_source_sha256", "c" * 64), ("physical_inputs_sha256", "d" * 64),
        ("base_association_sha256", "e" * 64), ("source_adapter_sha256", "1" * 64),
        ("authority_coverage", {"physical_complete": True}),
        ("evidence_hashes", {"private_source_path": "/private/unapproved"}),
        ("geometry_context_sha256", "2" * 64), ("rejected_candidate_count", 3),
        ("selection", {"camera_ids": ["CAM_A"], "time_range": [0, 2], "top_k": 1}),
    ]
    for field, value in changes:
        changed = json.loads(original_manifest)
        changed["public"][field] = value
        manifest_path.write_text(json.dumps(changed))
        with pytest.raises(ValueError, match="PHYSICAL_MEDIA_STALE"):
            provider.manifest(scene)
    manifest_path.write_bytes(original_manifest)
    changed = json.loads(original_manifest)
    changed["public"]["items"][0]["width"] = "/private/unapproved"
    manifest_path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="PHYSICAL_MEDIA_STALE"):
        provider.manifest(scene)
    manifest_path.write_bytes(original_manifest)
    changed = json.loads(original_manifest)
    changed["artifacts"][0]["relative_path"] = "../foreign.png"
    manifest_path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="PHYSICAL_MEDIA_STALE"):
        provider.manifest(scene)
    manifest_path.write_bytes(original_manifest)
    video_path = pool / "office/reconstruction.mp4"
    video = video_path.read_bytes()
    video_path.write_bytes(video + b"corruption")
    with pytest.raises(ValueError, match="PHYSICAL_MEDIA_STALE"):
        provider.media(scene, public["items"][1]["media_ref"])
    video_path.write_bytes(video)
    source_path = Path(before["frames"][0]["local_path"])
    source = source_path.read_bytes()
    source_path.write_bytes(source + b"corruption")
    with pytest.raises(ValueError, match="PHYSICAL_MEDIA_STALE"):
        provider.manifest(scene)
    source_path.write_bytes(source)
    assert provider.manifest(scene) == public
    rebuilds = []

    def rebuilt(candidate_scene: media.PhysicalScene, cameras: list[str]) -> dict[str, Any]:
        rebuilds.append(tuple(cameras))
        return original_reconstruct(candidate_scene, cameras)

    monkeypatch.setattr(media, "_reconstruct", rebuilt)
    with monkeypatch.context() as changed_code:
        changed_code.setattr(media, "_algorithm_sha", lambda: "1" * 64)
        with pytest.raises(ValueError, match="PHYSICAL_MEDIA_STALE"):
            provider.manifest(scene)
    assert len(rebuilds) == 1
    assert provider.manifest(scene) == public
    original_snapshot = scene.index.snapshot
    with monkeypatch.context() as truth_poison:
        truth_poison.setattr(scene.index, "snapshot", lambda: {
            **original_snapshot(), "ground_truth": {"secret": "DO_NOT_EXPORT_SIMULATOR_ACTOR"}})
        assert provider.manifest(scene) == public
    assert len(rebuilds) == 2
    assert provider.manifest(scene) == public
    source_inputs = copy.deepcopy(scene.inputs)
    scene.inputs["summary"]["evidence_hashes"]["synthetic_fixture"] = "9" * 64
    with pytest.raises(ValueError, match="PHYSICAL_MEDIA_STALE"):
        provider.manifest(scene)
    assert len(rebuilds) == 3
    scene.inputs = source_inputs
    assert provider.manifest(scene) == public
    assert original["public"] == public


def test_rejected_examples_are_separate_from_retained_top_k() -> None:
    result = physical_result({"status": "READY", "camera_coverage": [], "candidates": [
        {"rank": 1, "paths": [{"samples": samples(), "velocities": [], "gaps": []}]}]})
    rejected = copy.deepcopy(result["candidates"][0])
    rejected.pop("rank")
    rejected["rejection_rank"] = 1
    rejected["physical"]["verdict"] = "REJECTED"
    rejected["physical"]["reasons"] = [{"code": "KNOWN_COMPONENT_COLLISION", "status": "FAIL"}]
    result["rejected_candidates"] = [rejected]
    figure = media.render_curve_figure(result, [])
    assert len(figure.axes) == 4
    assert "retained 1/3; rejected examples 1" in figure.texts[0].get_text()
    assert "Rejected example 1 REJECTED" in figure.axes[2].get_title(loc="left")
    assert "KNOWN_COMPONENT_COLLISION" in figure.axes[3].texts[0].get_text()
    assert len(result["candidates"]) == 1 and "rank" not in result["rejected_candidates"][0]


def test_source_support_holes_remain_display_only_with_stable_spatial_bounds() -> None:
    result = physical_result({"status": "NO_RESULT", "candidates": [],
                              "graph": {"nodes": [], "edges": []}})
    exterior = [[0, 0, 0.5], [8, 0, 0.5], [8, 8, 0.5], [0, 8, 0.5], [0, 0, 0.5]]
    hole = [[3, 3, 0.5], [5, 3, 0.5], [5, 5, 0.5], [3, 5, 0.5], [3, 3, 0.5]]
    result["geometry_context"]["support_polygons"] = [{"exterior": exterior, "holes": [hole]}]
    figure = Figure()
    early = figure.add_subplot(121, projection="3d")
    late = figure.add_subplot(122, projection="3d")
    media._spatial_plot(early, result, {}, 0)
    media._spatial_plot(late, result, {}, 9.8)
    assert len(early.lines) == 2
    assert all(line.get_linestyle() == ":" for line in early.lines)
    assert early.get_xlim() == late.get_xlim()
    assert "source support only" in early.get_title(loc="left")
    assert len(early.collections) == 0


@pytest.mark.parametrize("field,value", [
    ("private_source_path", "/private/source.blend"), ("ground_truth", [999, 999]),
    ("raw_features", [1, 2]), ("unexpected", {"local_path": "/etc/passwd"}),
    ("floor", {"point": [float("nan"), 0, 0]}),
    ("floor", {"local_path": "/private/source"}),
    ("evidence_hashes", {"locator": "/Users/private/source"}),
])
def test_physical_source_dto_rejects_private_or_nonfinite_fields(
    bundle: tuple[Path, Path, Path], field: str, value: Any,
) -> None:
    scene = FixtureScene(load_blender_scene(bundle[0]))
    scene.inputs["summary"][field] = value
    with pytest.raises(ValueError, match="PHYSICAL_MEDIA_SOURCE_INVALID"):
        media._physical_inputs(scene)
