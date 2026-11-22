"""Focused corruption and isolation checks for #652's new pixel-only adapter."""
import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/evaluation/e3_cases" / f"{name}.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def fixture(tmp_path):
    indexer = module("index")
    frames = []
    for camera in range(8):
        cam = f"CAM_{camera}"
        rel = f"pixels/SAMPLE/00000-{cam}.jpg"
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (320, 180), (camera * 20, 25, 80)).save(p, format="JPEG")
        frames.append({"cam": cam, "path": rel, "sha256": indexer.sha(p.read_bytes()), "bytes": p.stat().st_size})
    wire = [{"tick": i, "t_capture_ms": i * 200, "frames": frames} for i in range(2)]
    source = tmp_path / "SAMPLE.replay1.wire.json"
    source.write_text(json.dumps(wire))
    return indexer, source, wire


def test_rgb_adapter_reads_only_pixels_and_preserves_decoded_rgb(tmp_path):
    indexer, _, _ = fixture(tmp_path)
    # There is deliberately no case, actor trajectory or GT sidecar to read.
    run = indexer.PixelRun(tmp_path, "SAMPLE")
    assert run.manifest["sampling"]["duration_s"] == .2
    assert len(run.rows) == 8
    for row in run.rows.values():
        assert Image.open(tmp_path / row["relative_path"]).size == (320, 180)
    assert run.files["rgb_index"]["provenance"]["gt_read"] is False


@pytest.mark.parametrize("corruption,match", [("hash", "JPEG_HASH"), ("clock", "CAPTURE_GRID"),
                                             ("path", "UNSAFE_PIXEL"), ("camera", "CAMERA_GRID")])
def test_rgb_adapter_rejects_incomplete_or_unbound_inputs(tmp_path, corruption, match):
    indexer, source, wire = fixture(tmp_path)
    if corruption == "hash":
        wire[0]["frames"][0]["sha256"] = "0" * 64
    elif corruption == "clock":
        wire[0]["t_capture_ms"] = 10
    elif corruption == "path":
        wire[0]["frames"][0]["path"] = "../gt/answers.jpg"
    else:
        wire[1]["frames"] = wire[1]["frames"][:-1]
        wire[0]["frames"] = wire[0]["frames"][:-1]
        match = "EIGHT_CAMERAS"
    source.write_text(json.dumps(wire))
    with pytest.raises(ValueError, match=match):
        indexer.PixelRun(tmp_path, "SAMPLE")


def test_fallback_has_explicit_unknown_origin_and_unreachable_camera():
    b = module("baseline")
    graph = json.loads((ROOT / "configs/q1q5/graphs/r004/camera_graph_v3.json").read_text())
    row = b.graph_ranking(graph, "CAM_W2")
    assert row["basis"] == "GRAPH_DISTANCE_FALLBACK"
    assert next(r["rank"] for r in row["ranking"] if r["camera_id"] == "CAM_WIDE") > 3
    assert all(r["camera_id"] != "CAM_ENTRY" for r in row["ranking"])
    assert b.graph_ranking(graph, "CAM_ENTRY")["status"] == "UNKNOWN_ORIGIN_OUTSIDE_GRAPH"
