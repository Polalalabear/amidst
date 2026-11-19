"""Exercise the A/B HTTP contract against a real server and synthetic camera observations."""
import io
import json
import re
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from amidst.live_mode import server as live

CANDIDATE_KEYS = {"cand_id", "tick", "cam", "bbox", "score", "color", "est_xy"}
CAMERAS = ("left", "right")


@pytest.fixture
def live_server(monkeypatch, tmp_path):
    catalog = tmp_path / "cameras.json"
    catalog.write_text('{"cameras": []}')
    # Top-down, ten pixels per metre. Both cameras see the same ground coordinates.
    calibration = {
        "camera_to_world": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 10], [0, 0, 0, 1]],
        "fx": 100, "fy": 100, "cx": 0, "cy": 0, "width": 96, "height": 60,
    }
    monkeypatch.setattr(live, "load_cameras", lambda _: [
        dict(calibration, camera_id=cam) for cam in CAMERAS
    ])
    graph = {"cameras": [{"camera_id": cam} for cam in CAMERAS], "transitions": []}
    monkeypatch.setattr(live, "load_graph", lambda *_: (graph, {"graph_sha256": "a" * 64}))
    boxes = []

    def detect(images):
        return [list(boxes) for _ in images], {}

    monkeypatch.setattr(live, "LiveDetector", lambda *_a, **_kw: SimpleNamespace(detect=detect))
    state = live.State(SimpleNamespace(
        cameras=str(catalog), camera_graph=None, graph_sha256=None, expand_every=1,
        schedule="adaptive", models=tmp_path, device="cpu", threads=1, det_resize_mode="letterbox",
        assets=tmp_path, advisor="off", advisor_provider="fake", gate_m=3.0, gate_growth=0,
        max_gate=8, det_width=96, det_height=60, camera_min_scores={}, min_score=0.15,
    ))
    backend = ThreadingHTTPServer(("127.0.0.1", 0), live.make_handler(state))
    thread = threading.Thread(target=backend.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()

    def request(path, req=None, *, raw=None, headers=None):
        method = "GET" if req is None and raw is None else "POST"
        data = json.dumps(req).encode() if raw is None and req is not None else raw
        conn = HTTPConnection("127.0.0.1", backend.server_port, timeout=3)
        try:
            conn.request(method, path, body=data, headers=headers or {})
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    jpeg = {}
    for color in ("red", "blue"):
        data = io.BytesIO()
        Image.new("RGB", (96, 60), color).save(data, format="JPEG")
        jpeg[color] = data.getvalue()

    def infer(tick, left=(), colors=("red", "red"), path="/infer"):
        boxes[:] = [
            {"bbox": [x, 0, x + 10, 30], "score": 0.9, "actor_id": "never-serialized"}
            for x in left
        ]
        frames = [(cam, jpeg[color]) for cam, color in zip(CAMERAS, colors)]
        header = json.dumps({
            "tick": tick, "t_capture_ms": 500 * tick, "available_cameras": list(CAMERAS),
            "frames": [{"cam": cam, "bytes": len(data)} for cam, data in frames],
        }).encode()
        code, body = request(path, raw=struct.pack("<I", len(header)) + header + b"".join(data for _, data in frames))
        assert code == 200
        return body

    try:
        yield state, request, infer
    finally:
        backend.shutdown()
        backend.server_close()
        thread.join(timeout=2)


def test_idle_preview_is_read_only_and_start_with_no_infer_autolocks_once(live_server):
    state, request, infer = live_server
    code, initial = request("/track/state")
    session_id = initial["session_id"]
    assert code == 200 and re.fullmatch("[a-f0-9]{16}", session_id)
    assert initial == {"mode": "IDLE", "color": None, "session_id": session_id, "tick": None}
    assert request("/track/candidates") == (200, {"tick": None, "color": "any", "candidates": []})
    out = infer(0, (8,), path="/detect")
    assert out["tracking"] is None and request("/track/state")[1] == initial
    assert request("/track/start", {"color": "red", "session_id": session_id}) == (
        200, {"mode": "ACQUIRING", "color": "red", "tick": None, "candidates": []}
    )
    assert infer(1)["tracking"]["state"] == "SEARCHING"
    result = infer(2, (8,))
    assert result["tracking"]["target"] == {"color": "red", "mode": "TRACKING"}
    assert result["tracking"]["events"] == [
        {"tick": 2, "cam": "left", "type": "ACQUIRE", "detail": {"by": "AUTO_SINGLE"}}
    ]
    assert infer(3, (8,))["tracking"]["events"] == []
    assert request("/track/stop", {"session_id": session_id}) == (200, {"mode": "IDLE"})
    assert request("/track/stop", {"session_id": session_id}) == (200, {"mode": "IDLE"})

    out = infer(4, (8,), ("red", "blue"))
    assert set(out) == {"tick", "dets", "tracking", "timing_ms", "schedule"}
    assert out["tracking"] == {
        "state": "IDLE", "active_cam": None, "seen_cams": [], "est_xy": None, "events": [],
        "lost_ticks": 0, "target": {"color": None, "mode": "IDLE"},
    }
    assert out["schedule"]["camera_ids"] == list(CAMERAS)
    for detections in out["dets"].values():
        assert set(detections[0]) == {"bbox", "score", "color", "red_ratio", "blue_ratio", "est_xy"}
    preview = request("/track/candidates")[1]
    assert {c["color"] for c in preview["candidates"]} == {"red", "blue"}
    assert all(set(c) == CANDIDATE_KEYS for c in preview["candidates"])
    assert request("/track/state")[1] == dict(initial, tick=4)
    assert request("/track/pick", {"session_id": session_id, "cand_id": preview["candidates"][0]["cand_id"]}) == (
        409, {"error": "TRACK_MODE_CONFLICT"}
    )
    assert state.tracker.est is None


def test_initial_needs_pick_is_latched_through_single_detection(live_server):
    state, request, infer = live_server
    session_id = state.selection.session_id
    start = {"color": "red", "session_id": session_id}
    request("/track/start", start)
    assert request("/track/pick", {"session_id": session_id, "cand_id": "bad"})[0] == 409
    assert infer(1, (8, 42))["tracking"]["state"] == "NEEDS_PICK"
    latest = infer(2, (8,))["tracking"]
    assert latest["state"] == "NEEDS_PICK" and latest["est_xy"] is None and latest["events"] == []
    candidates = request("/track/candidates")[1]["candidates"]
    assert len(candidates) == 1 and candidates[0]["tick"] == 2
    code, picked = request("/track/pick", {"session_id": session_id, "cand_id": candidates[0]["cand_id"]})
    assert (code, picked) == (200, {"mode": "TRACKING", "color": "red", "picked": candidates[0]})
    assert state.tracker.t_seen == pytest.approx(1.0)
    out = infer(3, (8,))["tracking"]
    assert out["events"][0]["detail"] == {"by": "USER_PICK"}
    assert out["events"][0]["tick"] == 2
    assert infer(4, (8,))["tracking"]["events"] == []


@pytest.mark.parametrize("age", [6, 7])
def test_stale_boundary_and_unknown_id(live_server, age):
    state, request, infer = live_server
    session_id = state.selection.session_id
    start = {"session_id": session_id, "color": "red"}
    infer(1, (8, 40))
    code, result = request("/track/start", start)
    assert code == 200 and result["mode"] == "NEEDS_PICK"
    candidate = result["candidates"][0]
    for tick in range(2, 2 + age):
        infer(tick)
    bad_id = candidate["cand_id"][:-1] + ("1" if candidate["cand_id"][-1] == "0" else "0")
    assert request("/track/pick", {"session_id": session_id, "cand_id": bad_id}) == (
        404, {"error": "CANDIDATE_UNKNOWN"}
    )
    code, result = request("/track/pick", {"session_id": session_id, "cand_id": candidate["cand_id"]})
    if age == 6:
        assert (code, result["picked"]) == (200, candidate)
    else:
        assert (code, result) == (409, {"error": "CANDIDATE_STALE"})


def test_epochs_color_and_reset_invalidate_ids(live_server):
    state, request, infer = live_server
    original = state.selection.session_id
    start = {"session_id": original, "color": "red"}
    infer(0, (8, 40), ("red", "blue"))
    red = request("/track/start", start)[1]["candidates"][0]
    blue = request("/track/candidates?color=blue")[1]["candidates"][0]
    assert request("/track/pick", {"session_id": original, "cand_id": blue["cand_id"]}) == (
        404, {"error": "CANDIDATE_UNKNOWN"}
    )
    request("/track/stop", {"session_id": original})
    request("/track/start", start)
    assert request("/track/pick", {"session_id": original, "cand_id": red["cand_id"]}) == (
        409, {"error": "CANDIDATE_STALE"}
    )
    code, response = request("/reset", {})
    new = response["session_id"]
    assert code == 200 and response["ok"] is True and new != original
    assert request("/track/state")[1] == {"session_id": new, "tick": None, "mode": "IDLE", "color": None}
    for endpoint, fields in (("start", {"color": "red"}), ("pick", {"cand_id": red["cand_id"]}), ("stop", {})):
        assert request("/track/" + endpoint, {"session_id": original, **fields}) == (
            409, {"error": "SESSION_MISMATCH"}
        )
    infer(0, (8, 40))
    start["session_id"] = new
    assert request("/track/start", start)[1]["candidates"][0]["cand_id"] != red["cand_id"]
    assert request("/track/pick", {"session_id": new, "cand_id": red["cand_id"]}) == (
        404, {"error": "CANDIDATE_UNKNOWN"}
    )


def test_reselect_keeps_track_and_pauses_advisor_until_pick(live_server):
    state, request, infer = live_server
    session_id = state.selection.session_id
    advisor = Mock()
    advisor.step.side_effect = lambda _tick, _clock, _tracker, tracking, *_args: tracking
    state._new_decider = lambda: advisor
    request("/track/start", {"session_id": session_id, "color": "red"})
    infer(1, (8,))
    assert advisor.step.call_count == 1
    old_tracker = state.tracker
    select = {"session_id": session_id, "color": "red", "reselect": True}
    assert request("/track/start", dict(select, color="blue")) == (409, {"error": "TRACK_MODE_CONFLICT"})
    code, result = request("/track/start", select)
    assert code == 200 and result["mode"] == "NEEDS_PICK" and len(result["candidates"]) == 1
    assert request("/track/start", select) == (409, {"error": "TRACK_MODE_CONFLICT"})
    waiting = infer(2, (9, 50))["tracking"]
    assert waiting["state"] == "TRACKING" and waiting["target"]["mode"] == "NEEDS_PICK"
    assert state.tracker is old_tracker and waiting["est_xy"] == pytest.approx([1.4, -3.0])
    assert advisor.step.call_count == 1
    chosen = request("/track/candidates")[1]["candidates"][-1]
    assert request("/track/pick", {"session_id": session_id, "cand_id": chosen["cand_id"]})[0] == 200
    assert state.tracker is not old_tracker
    assert infer(3, (10, 51))["tracking"]["est_xy"] == pytest.approx([5.6, -3.0])
    assert advisor.step.call_count == 2
    assert request("/track/start", {"session_id": session_id, "color": "blue"})[1]["mode"] == "ACQUIRING"
    assert state.tracker.est is None
    blue = infer(4, (8,), ("red", "blue"))["tracking"]
    assert blue["target"] == {"color": "blue", "mode": "TRACKING"} and blue["active_cam"] == "right"


@pytest.mark.parametrize("field,value,error", [
    ("session_id", "bad", "SESSION_REQUIRED"),
    ("color", 2, "COLOR_UNSUPPORTED"),
    ("sentence", "x" * 81, "INVALID_SENTENCE"),
    ("sentence", None, "INVALID_SENTENCE"),
    ("reselect", 1, "INVALID_RESELECT"),
])
def test_start_typed_fields(live_server, field, value, error):
    state, request, _ = live_server
    body = {"session_id": state.selection.session_id, "color": "red", field: value}
    assert request("/track/start", body) == (400, {"error": error})
    assert request("/track/state")[1]["mode"] == "IDLE"


def test_requests_are_whitelisted_and_errors_do_not_echo_values(live_server):
    state, request, _ = live_server
    for endpoint in ("start", "pick", "stop"):
        assert request(f"/track/{endpoint}", []) == (400, {"error": "INVALID_JSON_OBJECT"})
        assert request(f"/track/{endpoint}", {}) == (400, {"error": "SESSION_REQUIRED"})
        assert request(f"/track/{endpoint}", {"gt": "sensitive"}) == (
            400, {"error": "FIELD_NOT_ALLOWED", "fields": ["gt"]}
        )
    for endpoint in ("candidates", "state"):
        assert request(f"/track/{endpoint}?actor_id=redacted") == (
            400, {"error": "FIELD_NOT_ALLOWED", "fields": ["actor_id"]}
        )
    assert request("/track/candidates?color=purple") == (400, {"error": "COLOR_UNSUPPORTED"})
    assert request("/track/state", headers={"Origin": "https://other.invalid"}) == (
        403, {"error": "ORIGIN_NOT_ALLOWED"}
    )
    assert request("/track/start", {"session_id": state.selection.session_id, "sentence": "查找紅衣"})[1]["parse"] == {
        "parser": "RULES", "ignored": ["action"], "unrecognized_count": 0,
    }


def test_reset_during_parse_leaves_the_new_session_idle(live_server):
    state, request, _ = live_server
    old_session = state.selection.session_id
    entered, release = threading.Event(), threading.Event()

    def parse(*_):
        entered.set()
        assert release.wait(2)
        return "red", None

    state.sentence_parser.parse = parse
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(request, "/track/start", {"session_id": old_session, "sentence": "紅"})
        try:
            assert entered.wait(2)
            code, new_session = request("/reset", {})
            assert code == 200 and new_session["session_id"] != old_session
        finally:
            release.set()
        assert pending.result(timeout=3) == (409, {"error": "SESSION_MISMATCH"})
    assert request("/track/state")[1]["mode"] == "IDLE"
