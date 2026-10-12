"""SUBSTITUTE RGB/geometry and transport exercise isolated physical port contracts."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest
from test_blender_physical import source
from test_blender_ports import PixelScene

from amidst.workbench.blender_association import BaselineAssociationIndex
from amidst.workbench.blender_physical import BlenderPhysicalIndex
from amidst.workbench.blender_physical_ports import run_physical_port_probe


class SubstitutePhysicalScene(PixelScene):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self._physical_source = replace(source(), site_id="fixture-site")
        self.physical = BlenderPhysicalIndex(
            BaselineAssociationIndex(self.index.snapshot()), self._physical_source)

    def snapshot(self):
        return {**super().snapshot(), "cameras": self.inputs["cameras"]}

    def export_physical_source(self):
        constraints = self._physical_source
        return {"units": "METRES", "summary": {
            "physical_source_sha256": constraints.physical_source_sha256,
            "coverage": constraints.coverage,
            "policy": constraints.contract.policy.model_dump(mode="json"),
            "portals_summary": constraints.portals_summary}}

    def physical_cross_camera_reconstruction(self, cameras, start, end, top_k):
        return self.physical.reconstruct(cameras, start, end, top_k)


class SubstituteTransportMedia:
    """Opaque fixture bytes, explicitly not playable school-source video evidence."""

    def __init__(self, *, corrupt: bool = False) -> None:
        self.corrupt = corrupt

    def manifest(self, _scene):
        return {"status": "AVAILABLE", "items": [
            {"kind": kind, "media_ref": ref, "sha256": hashlib.sha256(raw).hexdigest(),
             "byte_count": len(raw)} for kind, ref, raw in (
                 ("PHYSICAL_POSITION_VELOCITY_CURVES", "curve", b"substitute-curve"),
                 ("PHYSICAL_CROSS_CAMERA_VIDEO", "video", b"substitute-video"))]}

    def media(self, _scene, ref):
        if self.corrupt:
            return "video/mp4", b"changed"
        return (("image/png", b"substitute-curve") if ref == "curve" else
                ("video/mp4", b"substitute-video"))


def test_physical_ports_rerun_full_pool_isolate_truth_and_preserve_optional_media(tmp_path):
    scene = SubstitutePhysicalScene(tmp_path)
    result = run_physical_port_probe(scene)
    ports = {p["port"]: p for p in result["ports"]}
    assert result["status"] == "PASS"
    assert result["summary"]["ports_total"] == 20
    assert result["summary"]["deferred"] == 3
    physical = ports["physical.candidate_filter"]["output"]
    assert physical["rerun_parity"] is True
    assert physical["original_observations_preserved"] is True
    assert physical["gt_poisoning_changes_decisions"] is False
    assert physical["search"]["old_top_k_pool_only"] is False
    assert physical["long_gap_chord_is_observed_motion"] is False
    assert ports["physical.source_constraints"]["output"]["geometry_is_partial"] is True
    assert ports["physical.reranked_top_k"]["output"]["baseline_retained"] is True
    assert ports["physical.video"]["status"] == "DEFERRED"
    for name in ("graph.gaps", "history.delta"):
        assert ports[name]["data_kind"] == "SUBSTITUTE"


def test_physical_binary_hash_mismatch_fails_only_its_port(tmp_path):
    scene = SubstitutePhysicalScene(tmp_path)
    good = run_physical_port_probe(scene, physical_media=SubstituteTransportMedia())
    assert good["status"] == "PASS"
    assert good["summary"]["physical_video_materialized"] is True
    bad = run_physical_port_probe(scene, physical_media=SubstituteTransportMedia(corrupt=True))
    assert bad["status"] == "FAIL"
    failures = [p["port"] for p in bad["ports"] if p["status"] == "FAIL"]
    assert failures == ["physical.video"]
    assert bad["summary"]["physical_status"] == good["summary"]["physical_status"]


@pytest.mark.parametrize("boundary", ["manifest", "media"])
def test_optional_physical_artifact_failure_preserves_other_ports_without_private_error(
    tmp_path, boundary,
):
    import json

    class StaleMedia(SubstituteTransportMedia):
        def manifest(self, scene):
            if boundary == "manifest":
                raise ValueError("PHYSICAL_MEDIA_STALE:/private/secret/source.blend")
            return super().manifest(scene)

        def media(self, scene, ref):
            raise OSError("/Users/private-owner/secret/video.mp4")

    result = run_physical_port_probe(SubstitutePhysicalScene(tmp_path), physical_media=StaleMedia())
    assert result["status"] == "FAIL"
    assert [p["port"] for p in result["ports"] if p["status"] == "FAIL"] == ["physical.video"]
    assert result["summary"]["ports_total"] == 20
    names = ("physical.source_constraints", "physical.candidate_filter", "physical.reranked_top_k")
    for name in names:
        assert next(p["status"] for p in result["ports"] if p["port"] == name) == "PASS"
    video = next(p for p in result["ports"] if p["port"] == "physical.video")
    assert video["output"]["manifest"]["reason"] == "INVALID_OR_STALE_ARTIFACT"
    assert video["output"]["produced_at_query"] is False
    assert "/private/" not in json.dumps(result) and "/Users/" not in json.dumps(result)
