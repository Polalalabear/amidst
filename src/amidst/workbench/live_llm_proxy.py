"""Same-origin proxy from the workbench to the live-mode server's settings entry (D265).

The workbench page talks only to its own backend (`/api/live_llm`); this module forwards to the live server's existing
`/config` (GET to read, POST to set `advisor` and `advisor_model`). Nothing else is forwarded, nothing else is returned.

- The live address is `AMIDST_LIVE_URL` (default http://127.0.0.1:8791). Only loopback hosts and unprivileged ports are
  accepted; the pinned demo port 8785 and the workbench's own port are refused.
- If the live server is not running or cannot be reached, the answer says so (`reachable: false`, reason text) and the
  switch is reported as off and unavailable; it is never reported as on.
- No API key, ground truth or frame data passes through: the request body is rebuilt from two validated fields and the
  response is reduced to a fixed set of status fields.
"""
from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEFAULT_LIVE_URL = "http://127.0.0.1:8791"
PINNED_DEMO_PORT = 8785
MODES = ("off", "review", "lead")
SWITCH_KEYS = ("requested", "effective", "available", "reason", "reason_text", "provider", "model", "models")
TIMEOUT_S = 3.0


class ProxyError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status, self.code = status, code


def live_target(env: Mapping | None = None, own_port: int | None = None) -> tuple[str, int]:
    """(host, port) of the live server, or ProxyError when the configured address is not an allowed local one."""
    env = os.environ if env is None else env
    parts = urlsplit(env.get("AMIDST_LIVE_URL") or DEFAULT_LIVE_URL)
    try:
        port = parts.port or 8791
    except ValueError:
        raise ProxyError(500, "LIVE_URL_INVALID") from None
    if (parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost") or parts.path not in ("", "/") or parts.query
            or parts.username or parts.password or not 1024 <= port <= 65535 or port in (PINNED_DEMO_PORT, own_port)):
        raise ProxyError(500, "LIVE_URL_NOT_ALLOWED")
    return parts.hostname, port


def unreachable(host: str, port: int, why: str = "LIVE_UNREACHABLE") -> dict:
    text = {"LIVE_UNREACHABLE": f"live 伺服器沒有啟動或連不上（{host}:{port}）",
            "LIVE_NO_SWITCH": f"live 伺服器（{host}:{port}）版本不支援 LLM 決策開關"}[why]
    return {"reachable": False, "advisor": "off", "advisor_provider": None,
            "llm_switch": {"requested": "off", "effective": "off", "available": False, "reason": why, "reason_text": text}}


def _fetch(method: str, url: str, body: bytes | None) -> dict:
    req = Request(url, data=body, method=method, headers={"Content-Type": "application/json"} if body is not None else {})
    with urlopen(req, timeout=TIMEOUT_S) as resp:   # noqa: S310 - scheme and host are validated by live_target
        return json.loads(resp.read())


def _public(cfg: dict, host: str, port: int) -> dict:
    sw = cfg.get("llm_switch")
    if not isinstance(sw, dict):
        return unreachable(host, port, "LIVE_NO_SWITCH")
    return {"reachable": True, "advisor": cfg.get("advisor"), "advisor_provider": cfg.get("advisor_provider"),
            "llm_switch": {k: sw.get(k) for k in SWITCH_KEYS if k in sw}}


def read_state(host: str, port: int, fetch: Callable = _fetch) -> dict:
    try:
        return _public(fetch("GET", f"http://{host}:{port}/config", None), host, port)
    except (URLError, OSError, ValueError):   # refused, timed out, not JSON: all mean "cannot use it"
        return unreachable(host, port)


def handle(method: str, host_header: str, origin: str | None, content_type: str, raw: bytes,
           env: Mapping | None = None, fetch: Callable = _fetch) -> tuple[int, dict]:
    """(status, JSON body) for GET/POST /api/live_llm. ``host_header`` is the workbench's own Host (loopback already checked)."""
    own_port = int(host_header.rsplit(":", 1)[1]) if ":" in host_header else 80
    try:
        host, port = live_target(env, own_port)
    except ProxyError as e:
        return e.status, {"error_code": e.code}
    if method == "GET":
        return 200, read_state(host, port, fetch)
    if method != "POST":
        return 405, {"error_code": "METHOD"}
    if origin not in (None, f"http://{host_header}"):
        return 403, {"error_code": "ORIGIN_DENIED"}
    if content_type.split(";")[0] != "application/json":
        return 403, {"error_code": "JSON_REQUIRED"}
    try:
        req = json.loads(raw)
        mode, model = req["advisor"], req.get("advisor_model")
    except (ValueError, KeyError, TypeError, AttributeError):
        return 400, {"error_code": "BAD_REQUEST"}
    if mode not in MODES or not (model is None or (isinstance(model, str) and 0 < len(model) <= 20)):
        return 400, {"error_code": "BAD_REQUEST"}
    body = {"advisor": mode, **({"advisor_model": model} if model else {})}   # rebuilt: nothing else is forwarded
    try:
        fetch("POST", f"http://{host}:{port}/config", json.dumps(body).encode())
    except (URLError, OSError, ValueError):
        return 200, unreachable(host, port)
    return 200, read_state(host, port, fetch)
