"""Scheduling must use only registered graph ids and backend tracking state."""

from amidst.live_mode.scheduler import CameraScheduler, load_graph
import pytest
import json


def graph():
    ids = list("ABCDE")
    return {
        "schema_version": "q-demo.camera-transition-graph.v1",
        "cameras": [{"camera_id": c} for c in ids],
        "transitions": [{"from_camera_id": a, "to_camera_id": b} for a, b in zip(ids, ids[1:])],
    }


def test_tracking_uses_active_and_direct_neighbors_only():
    s = CameraScheduler(graph(), expand_every=3)
    assert s.plan("B", 0, list("ABCDE"))["camera_ids"] == list("ABC")


def test_lost_expands_after_n_rounds_then_falls_back_to_full_search():
    s = CameraScheduler(graph(), expand_every=3)
    assert s.plan("B", 2, list("ABCDE"))["camera_ids"] == list("ABC")
    assert s.plan("B", 3, list("ABCDE"))["camera_ids"] == list("ABCD")
    assert s.plan("B", 6, list("ABCDE"))["camera_ids"] == list("ABCDE")


def test_switch_changes_neighbors_and_reacquisition_resets_expansion():
    s = CameraScheduler(graph(), expand_every=3)
    assert s.plan("D", 0, list("ABCDE"))["camera_ids"] == list("CDE")
    assert s.plan("B", 0, list("ABCDE"))["reason"] == "ACTIVE_NEIGHBORS"


def test_unknown_graph_scope_search_and_explicit_camera_subset_do_not_invent_edges():
    s = CameraScheduler(graph())
    assert s.plan("ENTRY", 0, ["A", "B", "ENTRY"])["camera_ids"] == ["A", "B", "ENTRY"]
    assert s.plan("ENTRY", 0, ["A", "B", "ENTRY"])["reason"] == "GRAPH_SCOPE_UNKNOWN"
    assert s.plan(None, 0, ["A", "B"])["camera_ids"] == ["A", "B"]
    assert s.plan("B", 0, ["B", "D"])["camera_ids"] == ["B"]


def test_graph_load_is_hash_and_camera_catalog_bound(tmp_path):
    import hashlib

    p = tmp_path / "graph.json"
    doc = graph()
    doc["camera_catalog_sha256"] = "a" * 64
    p.write_text(json.dumps(doc))
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    g, meta = load_graph(p, digest, "a" * 64, list("ABCDE") + ["ENTRY"])
    assert g == doc and meta["graph_sha256"] == digest
    with pytest.raises(ValueError, match="GRAPH_HASH_MISMATCH"):
        load_graph(p, "b" * 64, "a" * 64, list("ABCDE"))
    with pytest.raises(ValueError, match="GRAPH_CATALOG_MISMATCH"):
        load_graph(p, digest, "b" * 64, list("ABCDE"))


def test_server_does_not_infer_unselected_images_or_fabricate_empty_observations():
    from amidst.live_mode.server import State
    from types import SimpleNamespace
    from PIL import Image
    import io, threading

    state = object.__new__(State)
    state.registered_cameras = list("ABCDE")
    state.scheduler = CameraScheduler(graph(), expand_every=1)
    state.args = SimpleNamespace(det_width=320, det_height=180, min_score=0.35)
    state.lock = threading.Lock()
    state.decider = None
    tracker = SimpleNamespace(active="B", lost=0)

    def update(*a):
        tracker.active = "D"
        return {"state": "TRACKING", "active_cam": "D", "lost_ticks": 0}

    tracker.update = update
    state.tracker = tracker
    sizes = []

    def detect(images):
        sizes.append(len(images))
        return [[] for im in images], {}

    state.det = SimpleNamespace(detect=detect)
    buf = io.BytesIO()
    Image.new("RGB", (320, 180)).save(buf, format="JPEG")
    result = state.infer(
        {"tick": 1, "available_cameras": list("ABCDE")}, {c: buf.getvalue() for c in "ABCDE"}, True
    )
    assert sizes == [3] and list(result["dets"]) == list("ABC")
    assert result["schedule"]["next_camera_ids"] == list("CDE")
