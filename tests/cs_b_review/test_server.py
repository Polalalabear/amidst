import importlib.util
import json
import os
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("csrv", ROOT / "scripts" / "cs_b_review_server.py")
csrv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(csrv)

FIXTURE = Path(__file__).parent / "fixtures" / "SYNTHETIC-ctrl-run"
REF = "rgb/CAM_W1/frame_000001.png"


@pytest.fixture()
def served(tmp_path):
    run = tmp_path / "run-x"
    shutil.copytree(FIXTURE, run)
    srv = csrv.build_server([run], 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    yield base, run, srv
    srv.shutdown()
    srv.server_close()


def get(url):
    try:
        with urllib.request.urlopen(url) as r:
            return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def test_binds_loopback_only(served):
    assert served[2].server_address[0] == "127.0.0.1"


def test_page_screening_and_listed_rgb(served):
    base, run, _ = served
    assert get(base + "/")[0] == 200
    assert get(base + "/app.js")[0] == 200
    s, body, h = get(base + "/api/runs/run-x/screening")
    assert s == 200 and json.loads(body)["schema_version"] == "d47_screening_v1"
    assert len(h["X-Screening-SHA256"]) == 64
    s, body, _ = get(f"{base}/rgb/run-x/{REF}")
    assert s == 200 and body.startswith(b"\x89PNG")
    s, body, _ = get(base + "/api/runs")
    assert json.loads(body)[0]["index_error"] is None


@pytest.mark.parametrize("path", [
    "/safe_bundle/rgb_index.json", "/acceptance/", "/rgb/run-x/", "/rgb/run-x/rgb/CAM_W1/",
    "/rgb/run-x/../acceptance/d47_screening.json", "/rgb/run-x/%2e%2e/acceptance/d47_screening.json",
    "/rgb/run-x/rgb/CAM_W1/../../../acceptance/d47_screening.json",
    "/rgb/run-x/rgb/CAM_W1/frame_000099.png", "/rgb/unknown/" + REF,
    "/api/runs/other/screening", "/tools/cs_b_review/index.html",
])
def test_not_whitelisted(served, path):
    s, _, _ = get(served[0] + path)
    assert s in (403, 404)


def test_unlisted_file_on_disk_refused(served):
    base, run, _ = served
    (run / "safe_bundle" / "rgb" / "CAM_W1" / "extra.png").write_bytes(b"x")
    assert get(f"{base}/rgb/run-x/rgb/CAM_W1/extra.png")[0] == 404


def test_sha_mismatch_refused(served):
    base, run, _ = served
    p = run / "safe_bundle" / REF
    p.write_bytes(p.read_bytes() + b"tamper")
    s, body, _ = get(f"{base}/rgb/run-x/{REF}")
    assert s == 409 and "SHA-256 mismatch" in json.loads(body)["error"]


def test_symlink_refused(served):
    base, run, _ = served
    p = run / "safe_bundle" / REF
    target = run / "elsewhere.png"
    p.rename(target)
    os.symlink(target, p)
    assert get(f"{base}/rgb/run-x/{REF}")[0] == 403


def test_symlinked_screening_refused(served):
    base, run, _ = served
    p = run / "acceptance" / "d47_screening.json"
    real = run / "real.json"
    p.rename(real)
    os.symlink(real, p)
    assert get(base + "/api/runs/run-x/screening")[0] == 403


def test_read_only_methods(served):
    base, run, _ = served
    req = urllib.request.Request(base + "/api/runs", data=b"{}", method="POST")
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 405


def test_symlinked_run_dir_refused(tmp_path):
    link = tmp_path / "link"
    os.symlink(FIXTURE, link)
    with pytest.raises(SystemExit):
        csrv.build_server([link], 0)
