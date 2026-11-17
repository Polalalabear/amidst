"""Workbench -> live server same-origin proxy: loopback only, only the switch fields, unreachable means unavailable."""
import json
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from amidst.workbench import live_llm_proxy as proxy

HOST = "127.0.0.1:8016"
JSON_CT = "application/json"
LIVE_CFG = {"advisor": "off", "advisor_provider": None, "device": "mps", "threads": 4, "glb": True,
            "llm_switch": {"requested": "off", "effective": "off", "available": True, "reason": None, "reason_text": None, "provider": "openai",
                           "model": "sol6.1", "models": ["sol6.1"], "secret": "must-not-pass"}}


class FakeLive:
    def __init__(self, cfg=None, down=False):
        self.cfg, self.down, self.posts = json.loads(json.dumps(cfg or LIVE_CFG)), down, []

    def __call__(self, method, url, body):
        if self.down:
            raise URLError("refused")
        assert url.startswith("http://127.0.0.1:8791/") or url.startswith("http://localhost:")
        if method == "POST":
            self.posts.append(json.loads(body))
            self.cfg["llm_switch"]["requested"] = self.posts[-1]["advisor"]
            self.cfg["advisor"] = self.cfg["llm_switch"]["effective"] = self.posts[-1]["advisor"]
        return self.cfg


def call(method="GET", body=b"", live=None, origin=None, ct=JSON_CT, env=None):
    return proxy.handle(method, HOST, origin, ct, body, env=env if env is not None else {}, fetch=live or FakeLive())


def test_default_is_off_and_only_status_fields_come_back():
    code, data = call()
    assert code == 200 and data["reachable"] is True and data["advisor"] == "off" and data["llm_switch"]["requested"] == "off"
    assert "secret" not in data["llm_switch"] and "device" not in data and "threads" not in data


def test_live_server_not_running_reports_unavailable_never_on():
    code, data = call(live=FakeLive(down=True))
    assert code == 200 and data["reachable"] is False and data["advisor"] == "off"
    assert data["llm_switch"]["available"] is False and data["llm_switch"]["requested"] == "off" and "8791" in data["llm_switch"]["reason_text"]
    code, data = call("POST", b'{"advisor":"review"}', live=FakeLive(down=True))      # a failed switch-on is not reported as on
    assert data["reachable"] is False and data["llm_switch"]["effective"] == "off"
    old = dict(LIVE_CFG); old.pop("llm_switch")                                          # an older live server without the switch
    assert call(live=FakeLive(old))[1]["reachable"] is False


def test_post_forwards_only_the_two_validated_fields():
    live = FakeLive()
    code, data = call("POST", b'{"advisor":"review","advisor_model":"sol6.1","gt_xy":[0,0],"api_key":"x"}', live=live)
    assert code == 200 and live.posts == [{"advisor": "review", "advisor_model": "sol6.1"}]
    assert data["advisor"] == "review"
    for bad in (b"{}", b"[]", b"nope", b'{"advisor":"bogus"}', b'{"advisor":1}', b'{"advisor":"off","advisor_model":"x"}'.replace(b'"x"', b'"%s"' % (b"m" * 30))):
        assert call("POST", bad, live=live)[0] == 400
    assert len(live.posts) == 1


def test_post_needs_same_origin_and_json():
    live = FakeLive()
    assert call("POST", b'{"advisor":"off"}', live=live, origin="http://evil.example")[0] == 403
    assert call("POST", b'{"advisor":"off"}', live=live, origin="http://localhost:8016")[0] == 403      # not the Host the page was served from
    assert call("POST", b'{"advisor":"off"}', live=live, origin=f"http://{HOST}")[0] == 200
    assert call("POST", b'{"advisor":"off"}', live=live, ct="text/plain")[0] == 403
    assert call("DELETE", live=live)[0] == 405


@pytest.mark.parametrize("url", ["http://192.168.1.5:8791", "http://example.com:8791", "https://127.0.0.1:8791", "http://127.0.0.1:8785",
                                 "http://127.0.0.1:8016", "http://127.0.0.1:80", "http://127.0.0.1:8791/x", "http://u:p@127.0.0.1:8791", "http://127.0.0.1:99999"])
def test_live_address_must_be_local_unprivileged_and_not_the_demo_or_self(url):
    code, data = call(env={"AMIDST_LIVE_URL": url}, live=FakeLive())
    assert code == 500 and data["error_code"].startswith("LIVE_URL")


def test_live_address_default_and_override():
    assert proxy.live_target({}, 8016) == ("127.0.0.1", 8791)
    assert proxy.live_target({"AMIDST_LIVE_URL": "http://localhost:8797"}, 8016) == ("localhost", 8797)


def test_application_routes_live_llm_through_the_same_host_and_origin_guards(monkeypatch):
    monkeypatch.setenv("AMIDST_LIVE_URL", "http://127.0.0.1:59999")   # nothing listens there
    service = pytest.importorskip("amidst.workbench.service")
    app = object.__new__(service.Application)
    app.workbench = SimpleNamespace(controlled_scene=None)

    def run(method, path="/api/live_llm", host=HOST, origin=None, body=b""):
        out = {}
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "HTTP_HOST": host, "SERVER_PORT": "8016", "CONTENT_TYPE": JSON_CT,
               "CONTENT_LENGTH": str(len(body)), "wsgi.input": __import__("io").BytesIO(body), **({"HTTP_ORIGIN": origin} if origin else {})}
        raw = b"".join(app(env, lambda status, headers: out.update(status=status)))
        return out["status"], raw
    assert run("GET", host="evil.example:8016")[0].startswith("403")                     # shared loopback Host guard
    status, raw = run("GET")
    assert status.startswith("200") and json.loads(raw)["llm_switch"]["effective"] == "off"
    assert run("POST", origin="http://evil.example", body=b'{"advisor":"off"}')[0].startswith("403")
