"""Workbench LLM switch: default off, off changes nothing, on without a usable provider falls back to rules with a reason."""
import json
import threading
import types
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from amidst.live_mode.llm_switch import resolve
from amidst.q1q5.api_budget import GuardConfig

pytest.importorskip("PIL.Image")
server = pytest.importorskip("amidst.live_mode.server")


def make_state(provider="openai", advisor="off"):
    st = object.__new__(server.State)
    st.lock = threading.Lock()
    st.guard = None
    st.args = types.SimpleNamespace(advisor=advisor, advisor_provider=provider, advisor_model="sol6.1", advisor_timeout_s=5.0, advisor_fake_delay_s=0.0,
                                    advisor_lost_min_candidates=2, advisor_apply="reseed", gate_m=4.0, device="cpu", threads=1)
    st.args.det_resize_mode = "letterbox"
    st.args.min_score = 0.15
    st.args.camera_min_scores = {"CAM_ENTRY": 0.05}
    st.args.det_width, st.args.det_height = 320, 180
    st.args.schedule, st.args.expand_every = "adaptive", 1
    st.graph_meta = {"graph_sha256": "a" * 64}
    st.n6 = False
    st.llm_switch = {"requested": advisor, "effective": advisor, "available": True, "reason": None, "reason_code": None, "reason_text": None}
    return st


def test_default_is_off_and_off_builds_no_decider():
    assert resolve("off", "openai", env={})["effective"] == "off"
    st = make_state()
    assert st.args.advisor == "off" and st._new_decider() is None          # rule-only path, nothing can call a model
    r = st.set_llm_mode("off")
    assert r["effective"] == "off" and st.decider is None and st.guard is None   # off never even builds a guard


def test_off_after_on_goes_back_to_the_exact_rule_path():
    st = make_state(provider="fake")
    assert st.set_llm_mode("review")["effective"] == "review" and st.decider is not None
    assert st.set_llm_mode("off")["effective"] == "off" and st.decider is None and st.args.advisor == "off"


@pytest.mark.parametrize("env,cfg,reason", [
    ({}, GuardConfig(), "GUARD_NOT_APPROVED"),                                                        # guard off, budget 0
    ({"OPENAI_API_KEY": "k"}, GuardConfig(enabled=True, max_usd_total=0.0), "GUARD_NOT_APPROVED"),    # key but no budget
    ({}, GuardConfig(enabled=True, max_usd_total=1.0), "NO_API_KEY"),                                 # approved but no key
])
def test_on_without_usable_provider_falls_back_to_rules_with_a_reason(env, cfg, reason):
    for mode in ("review", "lead", "agent"):
        r = resolve(mode, "openai", env=env, guard_cfg=cfg)
        assert r["requested"] == mode and r["effective"] == "off" and r["available"] is False
        assert r["reason"] == reason and r["reason_text"]


def test_set_llm_mode_unavailable_keeps_rules_and_reports(monkeypatch):
    for k in ("AMIDST_API_ENABLED", "AMIDST_API_MAX_USD_TOTAL", "OPENAI_API_KEY", "AMIDST_API_CONFIG_FILE"):
        monkeypatch.delenv(k, raising=False)
    st = make_state()
    r = st.set_llm_mode("review")
    assert r["effective"] == "off" and r["reason_text"] and st.decider is None and st.guard is None and st.args.advisor == "off"


def test_config_endpoint_default_off_and_only_the_advisor_fields_are_accepted(monkeypatch):
    for k in ("AMIDST_API_ENABLED", "AMIDST_API_MAX_USD_TOTAL", "OPENAI_API_KEY", "AMIDST_API_CONFIG_FILE"):
        monkeypatch.delenv(k, raising=False)
    st = make_state()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(st))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        get = lambda: json.loads(urllib.request.urlopen(base + "/config").read())  # noqa: E731

        def post(body):
            req = urllib.request.Request(base + "/config", data=json.dumps(body).encode(), method="POST")
            try:
                with urllib.request.urlopen(req) as resp:
                    return resp.status, json.loads(resp.read())
            except urllib.error.HTTPError as e:
                return e.code, None
        c = get()
        assert c["advisor"] == "off" and c["llm_switch"]["requested"] == "off"
        assert post({"advisor": "bogus"})[0] == 400 and post({})[0] == 400 and post({"advisor": 1})[0] == 400
        code, res = post({"advisor": "review", "gt_xy": [0, 0], "api_key": "x"})        # extra fields are ignored, never stored
        assert code == 200 and res["effective"] == "off" and res["reason_text"]
        c = get()
        assert c["advisor"] == "off" and c["llm_switch"]["requested"] == "review" and c["llm_switch"]["available"] is False
        for bad_model in (["sol6.1"], {"a": 1}, 5, True, "nope"):                       # #577: non-string / unknown model is rejected, not ignored
            assert post({"advisor": "review", "advisor_model": bad_model})[0] == 400, bad_model
        assert st.args.advisor_model == "sol6.1"
        assert post({"advisor": "review", "advisor_model": None})[0] == 200
        assert "gt_xy" not in c and "api_key" not in json.dumps(c) and not hasattr(st.args, "gt_xy")
    finally:
        srv.shutdown()


def test_config_cors_only_for_the_allowed_workbench_origins_and_never_star(monkeypatch):
    for k in ("AMIDST_API_ENABLED", "AMIDST_API_MAX_USD_TOTAL", "OPENAI_API_KEY", "AMIDST_API_CONFIG_FILE"):
        monkeypatch.delenv(k, raising=False)
    st = make_state()
    st.args.workbench_ports = [8785, 8797]
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(st))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    base = f"http://127.0.0.1:{port}"

    def call(method, origin=None, body=None):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        req = urllib.request.Request(base + "/config", data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers)
    try:
        for ok in ("http://127.0.0.1:8785", "http://localhost:8797", "http://[::1]:8785"):   # #577: IPv6 loopback workbench origin
            code, h = call("GET", ok)
            assert code == 200 and h["Access-Control-Allow-Origin"] == ok
            code, h = call("OPTIONS", ok)
            assert code == 204 and h["Access-Control-Allow-Origin"] == ok and "POST" in h["Access-Control-Allow-Methods"]
        for bad in ("http://127.0.0.1:9999", "http://evil.example", "http://127.0.0.1.evil.example:8785", "null", "https://127.0.0.1:8785"):
            assert "Access-Control-Allow-Origin" not in call("GET", bad)[1]          # no header, so the browser blocks the read
            assert call("OPTIONS", bad)[0] == 403
            assert call("POST", bad, b'{"advisor":"review"}')[0] == 403              # and may not change the switch
        assert st.llm_switch["requested"] == "off"                                    # none of the rejected posts got through
        assert call("POST", "http://127.0.0.1:8785", b'{"advisor":"review"}')[0] == 200
        assert call("POST", base, b'{"advisor":"off"}')[0] == 200                     # the live page's own origin (B screen)
        assert call("POST", None, b'{"advisor":"off"}')[0] == 200                     # no Origin header: scripts and curl
        assert all("*" != v for v in call("GET", "http://127.0.0.1:8785")[1].values())
    finally:
        srv.shutdown()


def test_post_config_rejects_a_foreign_host_header_but_local_curl_still_works(monkeypatch):
    import http.client
    for k in ("AMIDST_API_ENABLED", "AMIDST_API_MAX_USD_TOTAL", "OPENAI_API_KEY", "AMIDST_API_CONFIG_FILE"):
        monkeypatch.delenv(k, raising=False)
    st = make_state()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(st))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    def post(host, origin=None):
        c = http.client.HTTPConnection("127.0.0.1", port)
        h = {"Host": host, "Content-Type": "application/json", **({"Origin": origin} if origin else {})}
        c.request("POST", "/config", body=b'{"advisor":"review"}', headers=h)
        return c.getresponse().status
    try:
        for bad in ("evil.example", f"evil.example:{port}", "127.0.0.1", "127.0.0.1:9", f"127.0.0.1.evil.example:{port}", f"192.168.1.5:{port}"):
            assert post(bad) == 403, bad                                       # no Origin (rebinding same-origin) is still refused
        assert st.llm_switch["requested"] == "off"                            # none of them changed the switch
        for ok in (f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"):
            assert post(ok) == 200, ok                                         # local curl: no Origin header
        assert post(f"127.0.0.1:{port}", origin=f"http://127.0.0.1:{port}") == 200   # the live page itself
    finally:
        srv.shutdown()


def test_agent_mode_does_not_start_silently_without_a_scene_context(tmp_path, capsys):
    """#666 M3: a scene context that cannot be built is reported (llm_switch, log), never a silent Agent run without spatial information."""
    st = make_state(provider="fake")
    st.args.cameras = str(tmp_path / "missing.catalog.json")
    st.registered_cameras = []
    r = st.set_llm_mode("agent")
    assert r["requested"] == "agent" and r["effective"] == "off" and r["available"] is False
    assert r["reason_code"].startswith("SCENE_CONTEXT_UNAVAILABLE:") and "SCENE_CONTEXT_UNAVAILABLE" in r["reason_text"]
    assert st.decider is None and st.args.advisor == "off" and st.llm_switch == r
    assert "SCENE_CONTEXT_UNAVAILABLE" in capsys.readouterr().out


def test_agent_mode_starts_when_the_scene_context_builds(monkeypatch):
    st = make_state(provider="fake")
    monkeypatch.setattr(server.State, "_live_scene_context", lambda self: (setattr(self, "scene_context_error", None), {"scene": 1})[1])
    r = st.set_llm_mode("agent")
    assert r["effective"] == "agent" and st.decider is not None and st.decider.scene_context == {"scene": 1}


def test_mode_switch_checks_existing_guard_configuration(monkeypatch):
    st = make_state()
    st.guard = types.SimpleNamespace(config=GuardConfig(enabled=False, max_usd_total=0))
    monkeypatch.setenv('AMIDST_API_ENABLED', '1')
    monkeypatch.setenv('AMIDST_API_MAX_USD_TOTAL', '5')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-key')
    r = st.set_llm_mode('agent')
    assert r['effective'] == 'off' and r['reason'] == 'GUARD_NOT_APPROVED'
    assert st.decider is None
