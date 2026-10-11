"""Blender-like RGB fixture reruns pixels, with Graph/history explicitly substituted."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from test_frame_baseline import rgb_inputs

from amidst.engineering.registry import content_hash
from amidst.workbench.blender_ports import _image_chunks, run_blender_port_probe
from amidst.workbench.blender_scene import strip_png_text
from amidst.workbench.frame_baseline import BaselineFrameIndex


class PixelScene:
    """Tiny safe adapter exercising original/served PNG bytes, without raw Blender exports."""

    def __init__(self, root: Path) -> None:
        self.scene_id = "blender-fixture"
        self.inputs = rgb_inputs(root)
        for frame in self.inputs["frames"]:
            path = frame["local_path"]
            with Image.open(path) as image:
                rgb = image.copy()
            info = PngInfo()
            info.add_text("File", "/private/secret.blend")
            info.add_text("TrajectoryID", "private-simulator-id")
            rgb.save(path, pnginfo=info)
            raw = path.read_bytes()
            frame["sha256"] = hashlib.sha256(raw).hexdigest()
            frame["byte_count"] = len(raw)
            served = strip_png_text(raw)
            frame["served_sha256"] = hashlib.sha256(served).hexdigest()
            frame["served_byte_count"] = len(served)
        self.index = BaselineFrameIndex(self.inputs)

    def export_safe_inputs(self):
        return copy.deepcopy(self.inputs)

    def live_scope(self):
        return {"scene_id": self.scene_id, "source_hash": "1" * 64,
                "source_features": self.index.source_features}

    def snapshot(self):
        return {"presentation": {
            "meshes": [{"mesh_ref": "mesh:fixture", "vertices": [[0, 0, 0]],
                        "triangles": [[0, 0, 0]]}],
            "authority": "PARTIAL_DISPLAY_CONTEXT", "display_triangle_count": 1,
            "default_material": "DISPLAY_ONLY_SMOOTH_GRAY", "source_archive_sha256": "3" * 64,
            "evaluated_scene": {"name": "Fixture", "frame": 220, "subframe": 0},
            "archive_is_whole_scene": False, "selected_object_count": 1,
            "selected_objects_complete": True, "truncated": False,
            "whole_scene_occlusion_proof": False, "physical_authority_changed": False,
            "source_geometry_modified": False,
        }}

    def frames(self, camera_ids, timestamp):
        return self.index.frames(camera_ids, timestamp)

    def media(self, ref):
        frame = next(row for row in self.inputs["frames"] if row["frame_ref"] == ref)
        return "image/png", strip_png_text(frame["local_path"].read_bytes())


@pytest.fixture(scope="module")
def blender_probe(tmp_path_factory):
    scene = PixelScene(tmp_path_factory.mktemp("blender-port-fixture"))
    before = content_hash(scene.index.snapshot())
    result = run_blender_port_probe(scene)
    assert content_hash(scene.index.snapshot()) == before
    return result


def test_actual_pixels_projection_repository_retrieval_and_source_media(blender_probe):
    result = blender_probe
    assert result["status"] == "PASS"
    assert result["selected_scene_used_as_input"] is True
    assert result["summary"]["passed"] == result["summary"]["total"] == 11
    assert result["summary"]["deferred"] == 1
    assert result["summary"]["ports_total"] == 12
    assert result["summary"]["actual_blender_ports"] == 9
    assert result["summary"]["substitute_ports"] == 2
    assert result["summary"]["selected_scene_used_as_input"] is True
    assert result["summary"]["source_rgb_frames"] == 10
    assert result["summary"]["operator_run_modified"] is False
    assert result["summary"]["rerun_matches_operator_index"] is True
    ports = {row["port"]: row for row in result["ports"]}
    assert ports["perception.measurements"]["output"]["measurements"] == 10
    assert ports["perception.measurements"]["output"]["local_tracks"] == 2
    assert ports["geometry.projected"]["output"]["projected_measurements"] == 10
    assert ports["geometry.projected"]["output"]["sample"]["world_position"] is not None
    assert ports["repository.snapshot"]["output"]["canonical_refs_and_order_preserved"] is True
    assert ports["retrieval.features"]["output"]["retrieval"]["global_scan"] is False
    assert ports["baseline.top_k"]["output"]["deterministic_repeat_matches"] is True
    items = ports["baseline.top_k"]["output"]["items"]
    assert [(row["camera_id"], row["timestamp"]) for row in items] == [
        ("CAM_A", 0.4), ("CAM_B", 0.4), ("CAM_A", 0.2)]
    assert ports["truth.isolation"]["output"]["safe_snapshot_unchanged"] is True
    assert ports["truth.isolation"]["output"]["query_unchanged"] is True
    for sample in ports["source.rgb"]["output"]["public_media_samples"]:
        assert sample["original_sha256"] != sample["served_sha256"]
        assert sample["pixels_unchanged"] is True
        assert sample["public_text_metadata_removed"] is True
        assert sample["manifest_hashes_match"] is True


def test_substitute_graph_and_history_have_independent_scope_and_no_blender_claim(blender_probe):
    ports = {row["port"]: row for row in blender_probe["ports"]}
    for name in ["graph.gaps", "history.delta"]:
        port = ports[name]
        assert port["data_kind"] == "SUBSTITUTE"
        assert port["source_binding"]["source_sha256"] != (
            blender_probe["source_binding"]["source_sha256"])
        assert port["source_binding"]["run_id"] == "blender-port-substitute-v1"
        assert port["status"] == "PASS"
    assert ports["graph.gaps"]["input"]["blender_pixels_used"] is False
    assert ports["graph.gaps"]["output"]["gaps"] == 4
    assert ports["graph.gaps"]["output"]["sample_candidate_count"] > 0
    assert ports["graph.gaps"]["output"]["blender_events_generated"] is False
    delta = ports["history.delta"]["output"]["delta"]
    assert delta["schema_version"] == "workbench.scene-review-delta.v1"
    assert ports["history.delta"]["output"]["replay_matches"] is True
    assert ports["history.delta"]["output"]["needs_rerun"] is True
    assert '"objects"' not in json.dumps(delta)
    assert ports["reconstruction.video"]["status"] == "DEFERRED"
    assert ports["reconstruction.video"]["output"]["materialization_status"] == "NOT_MATERIALIZED"


def test_report_never_exposes_locators_truth_identity_labels_or_media_bytes(blender_probe):
    raw = json.dumps(blender_probe)
    for forbidden in ("local_path", "/private/", "private-simulator-id", "secret.blend",
                      "TrajectoryID", "ground_truth", "forbidden_position", "MUST_NOT_BE_READ"):
        assert forbidden not in raw
    assert "agent_input" not in blender_probe
    assert "agent_output" not in blender_probe
    assert blender_probe["summary"]["agent_calls"] == 0
    assert blender_probe["summary"]["external_model_calls"] == 0
    assert blender_probe["summary"]["blend_copies"] == 0


def test_probe_does_not_call_agent_or_navigation_guidance(tmp_path: Path, monkeypatch) -> None:
    import amidst.workbench.navigation_guidance as guidance

    def prohibited(*_args, **_kwargs):
        raise AssertionError("Agent or navigation preprocessor called")

    monkeypatch.setattr(guidance, "mock_decide", prohibited)
    monkeypatch.setattr(guidance, "GuidanceIndex", prohibited)
    scene = PixelScene(tmp_path)
    result = run_blender_port_probe(scene)
    assert result["status"] == "PASS"
    assert result["summary"]["agent_calls"] == 0


def test_png_digest_helper_rejects_truncated_or_non_image_inputs() -> None:
    for raw in (b"fake", b"\x89PNG\r\n\x1a\n", b"\x89PNG\r\n\x1a\n\xff\xff\xff\xffIDAT"):
        with pytest.raises(ValueError, match="INVALID_PROBE_MEDIA"):
            _image_chunks(raw)


def test_bad_public_image_pixels_or_metadata_are_reported_as_failed_ports(tmp_path: Path) -> None:
    scene = PixelScene(tmp_path)
    original_media = scene.media

    def unsanitized_media(ref):
        frame = next(row for row in scene.inputs["frames"] if row["frame_ref"] == ref)
        return "image/png", frame["local_path"].read_bytes()

    scene.media = unsanitized_media
    result = run_blender_port_probe(scene)
    source = next(row for row in result["ports"] if row["port"] == "source.rgb")
    assert source["status"] == "FAIL"
    assert result["status"] == "FAIL"
    scene.media = original_media


def test_operator_index_mismatch_is_a_failed_repository_receipt(tmp_path: Path) -> None:
    scene = PixelScene(tmp_path)
    scene.inputs["frames"][0]["sha256"] = "f" * 64
    result = run_blender_port_probe(scene)
    repository = next(row for row in result["ports"] if row["port"] == "repository.snapshot")
    assert repository["output"]["rerun_matches_operator_index"] is False
    assert repository["status"] == "FAIL"
    assert result["status"] == "FAIL"
