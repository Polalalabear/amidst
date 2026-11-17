"""The merged path must retain detection configuration and apply thresholds after scheduling."""

import io
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

from PIL import Image

from amidst.live_mode.scheduler import CameraScheduler
from amidst.live_mode.server import State, make_handler


def test_scheduled_batches_keep_entry_override_and_do_not_fabricate_skipped_observations():
    state = object.__new__(State)
    state.registered_cameras = ["CAM_ENTRY", "CAM_WIDE", "CAM_W1", "CAM_W2"]
    graph = {
        "cameras": [{"camera_id": c} for c in state.registered_cameras if c != "CAM_ENTRY"],
        "transitions": [
            {"from_camera_id": "CAM_WIDE", "to_camera_id": c} for c in ["CAM_W1", "CAM_W2"]
        ],
    }
    state.scheduler = CameraScheduler(graph)
    state.args = SimpleNamespace(
        det_width=320, det_height=180, min_score=0.15, camera_min_scores={"CAM_ENTRY": 0.05}
    )
    state.lock = threading.Lock()
    state.decider = None
    state.tracker = SimpleNamespace(active=None, lost=0)

    def update(*a):
        state.tracker.active = "CAM_WIDE"
        return {"state": "TRACKING", "active_cam": "CAM_WIDE"}

    state.tracker.update = update
    batches = []

    def detect(images):
        batches.append(len(images))
        return [[{"bbox": [0, 0, 20, 40], "score": 0.08}] for _ in images], {}

    state.det = SimpleNamespace(detect=detect)
    data = io.BytesIO()
    Image.new("RGB", (320, 180), "red").save(data, format="JPEG")
    frames = {c: data.getvalue() for c in state.registered_cameras}
    header = {"tick": 0, "t_capture_ms": 1000, "available_cameras": state.registered_cameras}
    first = state.infer(header, frames, True)
    assert len(first["dets"]["CAM_ENTRY"]) == 1
    assert first["dets"]["CAM_W1"] == []
    second = state.infer(dict(header, tick=1, t_capture_ms=1500), frames, True)
    assert batches == [4, 4]
    assert "CAM_ENTRY" in second["dets"]
    third = state.infer(dict(header, tick=2, t_capture_ms=4001), frames, True)
    assert batches == [4, 4, 3]
    assert "CAM_ENTRY" not in third["dets"]
    assert second["schedule"]["reason"] == "ACTIVE_NEIGHBORS"


def test_config_exposes_both_detection_and_scheduling_contracts():
    args = SimpleNamespace(
        device="cpu",
        threads=4,
        det_resize_mode="letterbox",
        min_score=0.15,
        camera_min_scores={"CAM_ENTRY": 0.05},
        det_width=320,
        det_height=180,
        schedule="adaptive",
        expand_every=1,
        advisor="off",
    )
    state = SimpleNamespace(args=args, graph_meta={"graph_sha256": "a" * 64}, n6=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/config") as response:
            cfg = json.load(response)
        assert cfg["det_resize_mode"] == "letterbox" and cfg["min_score"] == 0.15
        assert cfg["camera_min_scores"] == {"CAM_ENTRY": 0.05} and cfg["det_size"] == [320, 180]
        assert cfg["schedule_mode"] == "adaptive" and cfg["schedule_policy"]["expand_every"] == 1
        assert cfg["schedule_policy"]["graph_sha256"] == "a" * 64 and cfg["advisor"] == "off"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
