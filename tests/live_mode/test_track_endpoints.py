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
from amidst.q1q5.api_budget import GuardConfig

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

    def infer(tick, left=(), colors=("red", "red"), path="/infer", *, status=200):
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
        assert code == status, body
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
        "lost_ticks": 0, "target": {"color": None, "mode": "IDLE"}, "gate_m_effective": 3.0,
    }
    assert out["schedule"]["camera_ids"] == list(CAMERAS)
    for detections in out["dets"].values():
        assert set(detections[0]) == {"bbox", "score", "color", "red_ratio", "blue_ratio", "est_xy", "reject_reason"}
    preview = request("/track/candidates")[1]
    assert {c["color"] for c in preview["candidates"]} == {"red", "blue"}
    assert all(set(c) == CANDIDATE_KEYS for c in preview["candidates"])
    assert request("/track/state")[1] == dict(initial, tick=4)
    assert request("/track/pick", {"session_id": session_id, "cand_id": preview["candidates"][0]["cand_id"]}) == (
        409, {"error": "TRACK_MODE_CONFLICT"}
    )
    assert state.tracker.est is None


def test_non_monotonic_infer_leaves_tracking_and_scheduler_untouched(live_server):
    state, request, infer = live_server
    infer(1, (8,))
    request("/track/start", {"color": "red", "session_id": state.selection.session_id})
    assert infer(3, (8,))["tracking"]["state"] == "TRACKING"
    state.det.detect = Mock(wraps=state.det.detect)
    state.scheduler.plan = Mock(wraps=state.scheduler.plan)
    state.scheduler.observe = Mock(wraps=state.scheduler.observe)
    state.tracker.update = Mock(wraps=state.tracker.update)
    latest = state.selection.latest
    for tick in (3, 2):
        assert infer(tick, (42,), status=409) == {"error": "NON_MONOTONIC_TICK", "next_tick": 4}
    assert infer(-1, status=400) == {"error": "INVALID_TICK"}
    state.det.detect.assert_not_called()
    state.scheduler.plan.assert_not_called()
    state.scheduler.observe.assert_not_called()
    state.tracker.update.assert_not_called()
    assert state.selection.latest is latest

    assert infer(2, (42,), path="/detect")["tracking"] is None
    assert state.selection.latest is latest
    assert infer(4, (8,))["tick"] == 4
    assert request("/reset", {})[0] == 200
    assert infer(0)["tracking"]["state"] == "IDLE"


def test_advisor_budget_does_not_enable_live_sentence_api(live_server):
    state, request, _ = live_server
    state.guard = SimpleNamespace(config=GuardConfig(enabled=True, max_usd_total=1))
    state.llm_switch["effective"] = "review"
    state.sentence_parser.client_factory = Mock()
    code, body = request("/track/start", {"session_id": state.selection.session_id, "sentence": "找紅衣"})
    assert code == 200 and body["parse"]["parser"] == "RULES"
    state.sentence_parser.client_factory.assert_not_called()


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



def test_config_reports_gate_settings_and_neutral_memory_name(live_server):
    state, request, _ = live_server
    state.args.advisor_model = 'terra6.1'
    code, cfg = request('/config')
    assert code == 200
    assert (cfg['gate_m'], cfg['max_gate_m'], cfg['gate_growth_m_s']) == (3.0, 8, 0)
    assert cfg['schedule_policy']['recent_candidate_s'] == cfg['schedule_policy']['recent_red_s'] == 2.0


def test_lost_candidates_have_signed_ids_and_rule_rejection_reason(live_server):
    state, request, infer = live_server
    session = state.selection.session_id
    request('/track/start', {'color': 'red', 'session_id': session})
    infer(0, (8,))
    out = infer(1, (52,))  # +4.4 m from seed, outside gate=3, but still a manual candidate
    assert out['tracking']['lost_ticks'] == 1 and out['tracking']['gate_m_effective'] == 3
    candidate = request('/track/candidates')[1]['candidates'][0]
    for cam in CAMERAS:
        assert out['dets'][cam][0]['reject_reason'] == 'OUT_OF_GATE'
        assert out['dets'][cam][0]['cand_id'] == candidate['cand_id']
    # Exposing an ID is not permission to bypass explicit reselect and session/epoch validation.
    assert state.selection.mode == 'TRACKING'
    assert request('/track/pick', {'session_id': session, 'cand_id': candidate['cand_id']})[0] == 409
    wrong = infer(2, (8,), colors=('blue', 'blue'))
    assert all(d['reject_reason'] == 'COLOR_MISMATCH' and 'cand_id' not in d for ds in wrong['dets'].values() for d in ds)
    recovered = infer(3, (10,))
    assert recovered['tracking']['lost_ticks'] == 0
    assert all(d['reject_reason'] is None for ds in recovered['dets'].values() for d in ds)


def test_effective_gate_is_value_used_before_reacquisition_resets_seen_time(live_server):
    state, request, infer = live_server
    request('/track/start', {'color': 'red', 'session_id': state.selection.session_id})
    infer(0, (8,))
    state.tracker.growth = 2.0
    assert infer(1)['tracking']['gate_m_effective'] == 4.0
    recovered = infer(2, (52,))  # 4.4m now fits gate=5, despite being outside the base 3m
    assert recovered['tracking']['gate_m_effective'] == 5.0 and recovered['tracking']['lost_ticks'] == 0
    assert recovered['dets']['left'][0]['reject_reason'] is None
    assert state.tracker.t_seen == 1.0
    assert infer(3)['tracking']['gate_m_effective'] == 4.0
    assert infer(20)['tracking']['gate_m_effective'] == 8.0


def test_response_diagnostics_leave_red_advisor_off_tracking_and_schedule_unchanged(live_server, monkeypatch):
    state, request, infer = live_server
    def run():
        request('/reset', {})
        request('/track/start', {'color': 'red', 'session_id': state.selection.session_id})
        rows = [infer(0, (8,)), infer(1), infer(2, (52,), colors=('blue', 'blue')), infer(3, (52,)), infer(4, (10,))]
        for row in rows:
            row.pop('timing_ms')
            for ds in row['dets'].values():
                for det in ds:
                    det.pop('reject_reason', None)
                    det.pop('cand_id', None)
        return rows
    with_diagnostics = run()
    monkeypatch.setattr(state, '_diagnose_detections', lambda *args: None)
    assert run() == with_diagnostics


def test_diagnostic_classification_precedence_and_projection_unknown(live_server):
    state, _, _ = live_server
    state.selection.color = 'red'
    dets = {'A': [{'color': 'red', 'est_xy': [3, 0]}, {'color': 'red', 'est_xy': [3.1, 0]},
                  {'color': 'blue', 'est_xy': [10, 0]}, {'color': 'red', 'est_xy': None}],
            'B': [{'color': 'blue', 'est_xy': [0, 0]}]}
    state._diagnose_detections(dets, None, {'A'}, [0, 0], 3)
    assert [d['reject_reason'] for d in dets['A']] == [None, 'OUT_OF_GATE', 'COLOR_MISMATCH', None]
    assert dets['B'][0]['reject_reason'] == 'CAM_NOT_SCHEDULED'



def test_lost_transitive_candidate_group_ids_do_not_change_selection_state(live_server):
    state, _, _ = live_server
    state.selection.start('red', False)
    out = {cam: [{'bbox': (i, 0, i + 1, 3), 'est_xy': [i * 1.2, 0], 'color': 'red', 'score': .9 - i / 10}]
           for i, cam in enumerate('ABC')}
    state.selection.observe(1, .5, out)
    before = state.selection.state()
    candidate = state.selection.snapshot('red')['candidates'][0]
    state._diagnose_detections(out, {'state': 'TRACKING', 'lost_ticks': 1}, set('ABC'), [0, 0], 1)
    assert {d['cand_id'] for ds in out.values() for d in ds} == {candidate['cand_id']}
    assert state.selection.state() == before


@pytest.mark.parametrize('color', ['red', 'blue'])
def test_agent_offline_request_uses_selected_target_and_applies_far_candidate(live_server, monkeypatch, color):
    from amidst.live_mode.service_decider import ServiceLiveDecider
    from amidst.live_mode.people import PeopleTracker
    state, request, infer = live_server
    seen = []
    def transport(body):
        seen.append(body)
        return {'text': json.dumps({'answer': 'SELECT', 'camera_id': 'left', 'detection_id': 'D1',
                                    'reason_codes': [], 'reason': 'synthetic'}), 'usage': {}, 'latency_s': 0}
    def factory(_context):
        return ServiceLiveDecider(transport, PeopleTracker(), {'schema_version': 'SYNTHETIC', 'cameras': [{'camera_id': c} for c in CAMERAS]},
                                  run_async=False, min_interval_s=100, clock=lambda: 0)
    monkeypatch.setattr(state, '_live_scene_context', lambda: {'schema_version': 'SYNTHETIC'})
    monkeypatch.setattr(state, '_new_service_decider', factory)
    assert request('/config', {'advisor': 'agent'})[1]['effective'] == 'agent'
    request('/track/start', {'color': color, 'session_id': state.selection.session_id})
    infer(1, (8,), colors=(color, color))
    assert seen
    text = seen[0]['input'][1]['content'][0]['text']
    assert f'labels: {color}' in text
    assert 'SCENE_CONTEXT=' in seen[0]['input'][0]['content'][0]['text']
    out = infer(2, (8,), colors=(color, color))['tracking']
    assert out['decision_source'] == 'AGENT' and out['advisor']['last']['applied']
    assert out['identity_verdict'] == 'UNCONFIRMED'
    # After the response is consumed, a lost-phase reply may override the 3 m rule gate.
    state.decider._last_end = -1e9
    state.decider.last_t = -1e9
    state.decider.lost_n = 1
    far = infer(3, (70,), colors=(color, color))['tracking']
    assert far['lost_ticks'] == 1
    result = infer(4, (70,), colors=(color, color))['tracking']
    assert result['decision_source'] == 'AGENT' and result['lost_ticks'] == 0
    assert result['advisor']['last']['applied']


def test_blue_far_candidate_can_be_reselected_with_relock_fallback(live_server):
    state, request, infer = live_server
    state.args.relock = "fallback"
    session = state.selection.session_id
    start = {"color": "blue", "session_id": session}
    request("/track/start", start)
    blue = ("blue", "red")

    initial = infer(0, (8,), colors=blue)["tracking"]
    assert initial["target"]["color"] == "blue" and initial["active_cam"] == "left"
    assert infer(1, (8,), colors=("red", "red"))["tracking"]["lost_ticks"] == 1

    far = infer(47, (58,), colors=blue)
    tracking = far["tracking"]
    assert tracking["unseen_s"] == 23.5 and tracking["state"] == "NEEDS_CONFIRM"
    assert len(tracking["confirm_candidates"]) == 1
    assert tracking["confirm_candidates"][0]["dist_m"] == pytest.approx(5)
    assert far["dets"]["left"][0]["reject_reason"] == "OUT_OF_GATE"

    code, reselect = request("/track/start", {**start, "reselect": True})
    assert code == 200 and reselect["mode"] == "NEEDS_PICK"
    candidate, = reselect["candidates"]
    code, picked = request("/track/pick", {"session_id": session, "cand_id": candidate["cand_id"]})
    assert code == 200 and picked["picked"] == candidate
    resumed = infer(48, (59,), colors=blue)["tracking"]
    assert resumed["state"] == "TRACKING" and resumed["lost_ticks"] == 0
    assert resumed["target"]["color"] == "blue" and resumed["est_xy"] != initial["est_xy"]


def test_startup_agent_without_authorization_uses_rules(live_server, monkeypatch):
    state, _request, _infer = live_server
    from amidst.live_mode.server import State
    import copy
    for key in ('AMIDST_API_ENABLED', 'AMIDST_API_MAX_USD_TOTAL', 'AMIDST_API_CONFIG_FILE', 'OPENAI_API_KEY'):
        monkeypatch.delenv(key, raising=False)
    args = copy.copy(state.args)
    args.advisor, args.advisor_provider = 'agent', 'openai'
    denied = State(args)
    assert denied.args.advisor == 'off' and denied.decider is None and denied.guard is None
    assert denied.llm_switch['requested'] == 'agent'
    assert denied.llm_switch['reason'] == 'GUARD_NOT_APPROVED'
