"""In-process WSGI fixture and exact static allowlist checks; no listeners or real media."""

import json
from io import BytesIO

import pytest

from amidst.engineering.registry import content_hash
from amidst.workbench.controlled_scene_api import (
    ACTIONS,
    CAMERAS,
    RUN,
    SCENE,
    ControlledSceneAPI,
    fixture_layers,
)
from amidst.workbench.controlled_scene_static import LINE_FILES, STATIC_FILES
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.scene_errors import DataIntegrityError
from amidst.workbench.service import Application, Workbench


@pytest.fixture
def server(tmp_path):
    root = tmp_path.resolve()
    api = ControlledSceneAPI(fixture_mode=True)
    wb = Workbench({}, ReviewStore(root / "reviews.sqlite3", {}), controlled_scene=api)
    app = Application(wb, root, vendor_root=root / "vendor")
    token = wb.session({"role": "research"})["session_ref"]
    return app, api, token, root


def http(app, path, payload=None, method="POST", **extra):
    raw = json.dumps(payload or {}).encode()
    env = {"HTTP_HOST": "127.0.0.1:12345", "SERVER_PORT": "12345",
           "REQUEST_METHOD": method, "PATH_INFO": path, "wsgi.input": BytesIO(raw),
           "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(raw)), **extra}
    result = {}

    def start(status, headers):
        result.update(status=int(status.split()[0]), headers=dict(headers))

    body = b"".join(app(env, start))
    return result["status"], body, result["headers"]


def request(action, token):
    p = {"schema_version": "controlled-scene." + action.replace("_", "-") + "-request.v1",
         "session_ref": token, "scene_id": SCENE, "run_id": RUN}
    if action == "candidate_cameras":
        p.update(target_region_ref="AREA_FIXTURE", target_polygon=None, time_range_s=[0, 20],
                 query_intent="PASS_THROUGH", surrounding_policy_ref="fixture-surround-policy-v1",
                 camera_ids=None, page_size=4, cursor=None, layout_capacity=4)
    elif action == "synced_frames":
        p.update(t_s=12.47, camera_ids=list(CAMERAS))
    elif action in {"person_layer", "curve_layer"}:
        p.update(time_range_s=[12, 13])
    else:
        p["pick"] = {"layer": "curve", "ref": "fixture-curve-1", "segment_index": 0,
                     "result_sha256": fixture_layers()["curves"][0]["result_sha256"],
                     "t_click_s": 12.47}
    return p


@pytest.mark.parametrize("action", sorted(ACTIONS))
def test_five_endpoints_provenance_and_hash(server, action):
    app, _, token, _ = server
    code, raw, _ = http(app, "/api/" + action, request(action, token))
    assert code == 200
    value = json.loads(raw)
    assert value["data_origin"] == "SYNTHETIC_FIXTURE" and value["fixture_marker"] == "FIXTURE"
    assert value["provenance"]["gt_read"] is False
    assert value["identity_verdict"] == "UNCONFIRMED" and value["agent_used"] is False
    assert value["resolved_scope"]["run_id"] == RUN
    assert token not in raw.decode() and "local_path" not in raw.decode()
    digest = value.pop("output_sha256")
    assert digest == content_hash(value)


@pytest.mark.parametrize("action", sorted(ACTIONS))
def test_integrity_shape_entire_request_no_tiles_or_geometry(server, action):
    app, api, token, _ = server
    api._layers["estimates"][0]["bbox_height_px"] = 99
    code, raw, _ = http(app, "/api/" + action, request(action, token))
    assert code == 409
    assert json.loads(raw) == {"schema_version": "controlled-scene.error.v1", "error": {
        "error_class": "DataIntegrityError", "reason": "FIXTURE_HASH_MISMATCH"}}


@pytest.mark.parametrize("action", sorted(ACTIONS))
def test_missing_inference_uncertainty_fail_closed(server, action):
    app, api, token, _ = server
    del api._layers["curves"][0]["segments"][0]["uncertainty"]
    api._fixture_pin = content_hash(api._layers)
    code, raw, _ = http(app, "/api/" + action, request(action, token))
    assert code == 409
    assert json.loads(raw)["error"]["reason"] == "INFERENCE_UNCERTAINTY_MISSING_OR_INVALID"


@pytest.mark.parametrize("action", sorted(ACTIONS))
@pytest.mark.parametrize("case", ["session", "scene", "run", "private", "source_pin", "schema"])
def test_scope_and_no_caller_source_pin(server, action, case):
    app, _, token, _ = server
    p = request(action, token)
    if case == "session":
        p["session_ref"] = "invalid"
    elif case == "scene":
        p["scene_id"] = "other"
    elif case == "run":
        p["run_id"] = "actual-run-that-is-not-registered"
    elif case == "private":
        p["actor_id"] = "forbidden"
    elif case == "source_pin":
        p["source_sha256"] = "0" * 64
    else:
        p["schema_version"] = "wrong"
    code, raw, _ = http(app, "/api/" + action, p)
    assert code in {400, 403, 409}
    assert "tiles" not in json.loads(raw)


def test_explicit_fixture_bootstrap_and_disabled_default(server, tmp_path):
    app, _, _, _ = server
    code, raw, _ = http(app, "/api/bootstrap", method="GET",
                        QUERY_STRING="surface=workbench-v2")
    assert code == 200 and json.loads(raw)["data_origin"] == "SYNTHETIC_FIXTURE"
    legacy = json.loads(http(app, "/api/bootstrap", method="GET")[1])
    assert legacy["scenes"] == [] and legacy["data_origin"] == "LEGACY_RUNTIME"
    wb = Workbench({}, ReviewStore(tmp_path / "disabled.db", {}))
    assert wb.controlled_scene.bootstrap()["data_origin"] == "UNCONFIGURED"
    assert not wb.controlled_scene.scene_ids


@pytest.mark.parametrize("t,index,age", [(0, 0, 0), (.2, 1, 0), (.199999, 0, .199999),
                                       (12.47, 62, .07), (19.999, 99, .199), (20, None, None),
                                       (-.1, None, None)])
def test_exact_grid_no_epsilon_no_fallback(server, t, index, age):
    app, _, token, _ = server
    p = request("synced_frames", token)
    p["t_s"] = t
    code, raw, _ = http(app, "/api/synced_frames", p)
    assert code == 200
    result = json.loads(raw)
    assert result["expected_frame_index"] == index and result["sample_age_s"] == age
    assert result["media_tokens_issued"] == 0
    assert all(tile["status"] == ("OUT_OF_RANGE" if index is None else "MISSING")
               and tile["frame_ref"] is None for tile in result["tiles"])


def test_cursor_query_scope_and_session_binding(server):
    app, _, token, _ = server
    p = request("candidate_cameras", token)
    p["page_size"] = 2
    first = json.loads(http(app, "/api/candidate_cameras", p)[1])
    assert first["status"] != "READY"
    assert first["returned_count"] == 2 and first["candidates_total"] == 4
    p["cursor"] = first["next_cursor"]
    second = json.loads(http(app, "/api/candidate_cameras", p)[1])
    assert [c["camera_id"] for c in second["candidates"]] == list(CAMERAS[2:])
    p["query_intent"] = "ENTER_EXIT"
    assert http(app, "/api/candidate_cameras", p)[0] == 409


def test_evidence_pick_requires_result_pin(server):
    app, _, token, _ = server
    p = request("evidence_lookup", token)
    p["pick"]["result_sha256"] = "0" * 64
    code, raw, _ = http(app, "/api/evidence_lookup", p)
    assert code == 409 and json.loads(raw)["error"]["reason"] == "RESULT_PIN_MISMATCH"


@pytest.mark.parametrize("url", sorted(STATIC_FILES))
def test_exact_static_files_only(server, url):
    app, _, _, root = server
    path = root / STATIC_FILES[url]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"SYNTHETIC STATIC TEST TEXT")
    code, raw, headers = http(app, url, method="GET")
    assert code == 200 and raw == b"SYNTHETIC STATIC TEST TEXT"
    assert headers["X-Content-Type-Options"] == "nosniff"
    if url.endswith(".woff2"):
        assert headers["Content-Type"] == "font/woff2"


@pytest.mark.parametrize("url", sorted(LINE_FILES))
def test_exact_three_line_modules(server, url):
    app, _, _, root = server
    path = root / "vendor" / LINE_FILES[url]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("// SYNTHETIC TEST MODULE")
    assert http(app, url, method="GET")[0] == 200


@pytest.mark.parametrize("url", [
    "/workbench/app.mjs", "/workbench/scene.mjs", "/workbench/unknown.mjs",
    "/workbench-v2/../", "/workbench-v2/../workbench/app.mjs",
    "/workbench-v2/%2e%2e/app.mjs", "/workbench-v2/fixtures/unknown.json",
    "/workbench-v2/player-grid.test.mjs", "/workbench-v2/fonts/unknown.woff2",
    "/workbench-v2/fonts/", "/vendor/examples/jsm/lines/", "/vendor/examples/jsm/lines/Unknown.js",
    "/data/pilot/controlled_scene_v1/assets/controlled_scene_v1.blend",
    "/data/pilot/controlled_scene_v1/review_only/test",
    "/private_evaluation/production_manifest.json",
    "/docs/engineering/CONTROLLED_SCENE_B_DESIGN_20261018.md", "/derived/test",
])
def test_non_allowlisted_paths_denied(server, url):
    app, _, _, _ = server
    assert http(app, url, method="GET")[0] in {403, 404}


@pytest.mark.parametrize("ancestor", [False, True])
def test_allowlisted_symlink_denied(server, ancestor):
    app, _, _, root = server
    other = root / "outside"
    other.mkdir()
    (other / "index.html").write_text("secret test text")
    path = root / "frontend/workbench-v2"
    path.parent.mkdir(parents=True)
    if ancestor:
        path.symlink_to(other, target_is_directory=True)
    else:
        path.mkdir()
        (path / "index.html").symlink_to(other / "index.html")
    code, raw, _ = http(app, "/workbench-v2/", method="GET")
    assert code == 403 and b"secret" not in raw


def test_known_but_unmaterialized_frontend_is_404(server):
    app, _, _, _ = server
    assert http(app, "/workbench-v2/", method="GET")[0] == 404


@pytest.mark.parametrize("part", ["person", "curve"])
def test_missing_uncertainty_rejected_at_fixture_construction(part):
    layers = fixture_layers()
    row = layers["estimates"][0] if part == "person" else layers["curves"][0]["segments"][0]
    del row["uncertainty"]
    with pytest.raises(DataIntegrityError, match="UNCERTAINTY"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


def test_real_run_never_automatically_becomes_fixture(server):
    app, _, token, _ = server
    p = request("synced_frames", token)
    p["run_id"] = "ctrl-lcorr-s1-b1-5fps-v1-r001"
    code, raw, _ = http(app, "/api/synced_frames", p)
    assert code == 409 and "SYNTHETIC_FIXTURE" not in raw.decode()


@pytest.mark.parametrize("action", sorted(ACTIONS))
@pytest.mark.parametrize("reason", ["RGB_RECORD_HASH_MISMATCH", "SOURCE_RUN_PIN_MISMATCH",
                                   "PRIVATE/ABSOLUTE/LOCATOR"])
def test_public_integrity_reason_codes_and_sanitization(server, monkeypatch, action, reason):
    app, api, token, _ = server

    def reject(*args):
        raise DataIntegrityError(reason)

    monkeypatch.setattr(api, "call", reject)
    code, raw, _ = http(app, "/api/" + action, request(action, token))
    value = json.loads(raw)
    assert code == 409 and set(value) == {"schema_version", "error"}
    assert value["error"] == {"error_class": "DataIntegrityError", "reason":
                              "DATA_INTEGRITY_REJECTED" if "/" in reason else reason}


def test_office_factory_reuses_evidence_vendor_without_launcher_change(tmp_path):
    import importlib.util
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "controlled_factory_test", repo / "scripts/office_demo_backend.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path.resolve()
    evidence = root / "evidence"
    ui = root / "ui"
    app = module.application({}, root / "factory.sqlite3", ui, evidence)
    url, relative = next(iter(LINE_FILES.items()))
    path = evidence / "frontend/workbench/node_modules/three" / relative
    path.parent.mkdir(parents=True)
    path.write_text("// synthetic factory test module")
    assert http(app, url, method="GET")[0] == 200
    assert app.workbench.controlled_scene.fixture_mode is False
