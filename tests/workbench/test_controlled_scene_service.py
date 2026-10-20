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
    assert json.loads(raw)["error"]["reason"] == "UNCERTAINTY_FIELDS_MISSING"


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


def declared_uncertainty(kind="AREA_M2", extent=18.5):
    limits = {"AREA_M2": (.25, 4), "LENGTH_M": (.25, 1), "ANGLE_DEG": (15, 45)}
    high, medium = limits[kind]
    grade = "HIGH" if extent <= high else "MEDIUM" if extent <= medium else "LOW"
    return {"extent_kind": kind, "extent_value": extent,
            "constraints_used": ["speed"], "quality_grade": grade,
            "quality_rule_ref": "SYNTHETIC-quality-rule-D56", "quality_rule_sha256": "a" * 64}


def ready_segment(layers):
    row = layers["curves"][0]["segments"][0]
    row.update(status="READY", geometry={"type": "SYNTHETIC_REGION"},
               uncertainty=declared_uncertainty())
    row.pop("reason", None)
    return row


def test_contract_uncertainty_accepted_and_observations_exempt():
    layers = fixture_layers()
    ready_segment(layers)
    segments = layers["curves"][0]["segments"]
    segments.extend([
        {"kind": "OBSERVED", "evidence_state": "PROJECTED_OBSERVATION",
         "sample_timestamps_s": [12.4], "geometry": {"type": "INTERVAL_SERIES"}},
        {"kind": "MISSING_GAP", "evidence_state": "MISSING", "geometry": None},
    ])
    assert "uncertainty" not in layers["estimates"][0]
    api = ControlledSceneAPI(fixture_mode=True, layers=layers)
    assert api.fixture_mode is True


@pytest.mark.parametrize("kind", [None, "INFERRED_CONSTRAINED", "UNKNOWN_KIND", {}, 1])
def test_unknown_or_missing_curve_kind_fails_closed(kind):
    layers = fixture_layers()
    row = layers["curves"][0]["segments"][0]
    if kind is None:
        row.pop("kind")
        row.pop("evidence_state")
    else:
        row["kind"] = kind
    with pytest.raises(DataIntegrityError, match="CURVE_KIND_INVALID"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


@pytest.mark.parametrize("field", ["extent_kind", "extent_value", "constraints_used",
                                  "quality_grade", "quality_rule_ref", "quality_rule_sha256"])
def test_each_contract_uncertainty_field_is_required(field):
    layers = fixture_layers()
    row = ready_segment(layers)
    row["uncertainty"].pop(field)
    with pytest.raises(DataIntegrityError, match="UNCERTAINTY_FIELDS_MISSING"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


@pytest.mark.parametrize("value", ["anything", {}, True, -1, float("inf"), float("nan"),
                                  10**400, None])
def test_uncertainty_extent_must_be_finite_nonnegative_number(value):
    layers = fixture_layers()
    ready_segment(layers)["uncertainty"]["extent_value"] = value
    with pytest.raises(DataIntegrityError, match="UNCERTAINTY_FIELDS_INVALID"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


@pytest.mark.parametrize("case", ["constraints_type", "constraints_item", "rule_ref", "hash",
                                 "grade", "legacy_bounds", "old_schema"])
def test_uncertainty_metadata_and_legacy_schema_rejected(case):
    layers = fixture_layers()
    row = ready_segment(layers)
    u = row["uncertainty"]
    if case == "constraints_type":
        u["constraints_used"] = "speed"
    elif case == "constraints_item":
        u["constraints_used"] = [{}]
    elif case == "rule_ref":
        u["quality_rule_ref"] = ""
    elif case == "hash":
        u["quality_rule_sha256"] = "no-pin"
    elif case == "grade":
        u["quality_grade"] = "HIGH"
    elif case == "legacy_bounds":
        u["bounds"] = {}
    else:
        row["uncertainty"] = {"status": "BOUNDED_HEURISTIC", "bounds": "anything",
                              "method": "old", "units": "m", "reason": None,
                              "limitations": ["test"]}
    with pytest.raises(DataIntegrityError, match="UNCERTAINTY_FIELDS"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


@pytest.mark.parametrize("part", ["heading", "composed_ground"])
def test_nonunknown_person_subfield_requires_own_uncertainty(part):
    layers = fixture_layers()
    estimate = layers["estimates"][0]
    estimate[part] = ({"state": "INFERRED", "direction_xy": [1, 0]} if part == "heading"
                      else {"status": "READY", "geometry": {"type": "SEGMENT"}})
    with pytest.raises(DataIntegrityError, match="UNCERTAINTY_FIELDS_MISSING"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


def test_heading_uses_angle_uncertainty_and_height_range_is_separate():
    layers = fixture_layers()
    estimate = layers["estimates"][0]
    estimate["heading"] = {"state": "INFERRED", "direction_xy": [1, 0],
                           "uncertainty": declared_uncertainty("ANGLE_DEG", 15)}
    estimate["track_height_estimate"] = {
        "status": "READY", "height_m": 1.71,
        "uncertainty": {"method": "RANGE_OF_SUPPORT_HEIGHTS", "lower_m": 1.68, "upper_m": 1.74}}
    ControlledSceneAPI(fixture_mode=True, layers=layers)
    estimate["heading"]["uncertainty"] = declared_uncertainty("LENGTH_M", .25)
    with pytest.raises(DataIntegrityError, match="UNCERTAINTY_FIELDS_INVALID"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


@pytest.mark.parametrize("part", ["curve", "composed_ground"])
def test_position_inference_cannot_use_angle_extent(part):
    layers = fixture_layers()
    row = (ready_segment(layers) if part == "curve" else
           layers["estimates"][0]["composed_ground"])
    row.update(status="READY", geometry={"type": "SEGMENT"},
               uncertainty=declared_uncertainty("ANGLE_DEG", 15))
    with pytest.raises(DataIntegrityError, match="UNCERTAINTY_FIELDS_INVALID"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


def test_unknown_inference_must_not_publish_geometry():
    layers = fixture_layers()
    layers["curves"][0]["segments"][0]["geometry"] = {"type": "REGION"}
    with pytest.raises(DataIntegrityError, match="UNCERTAINTY_FIELDS_INVALID"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


@pytest.mark.parametrize("status", [{}, [], 1, "BOUNDED_HEURISTIC"])
def test_malformed_inference_status_is_integrity_error(status):
    layers = fixture_layers()
    ready_segment(layers)["status"] = status
    with pytest.raises(DataIntegrityError, match="UNCERTAINTY_FIELDS_INVALID"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


def test_unknown_inference_must_explicitly_have_null_geometry():
    layers = fixture_layers()
    layers["curves"][0]["segments"][0].pop("geometry")
    with pytest.raises(DataIntegrityError, match="UNCERTAINTY_FIELDS_INVALID"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


def test_d56_grade_uses_normative_table_not_stale_example():
    layers = fixture_layers()
    u = ready_segment(layers)["uncertainty"]
    u.update(declared_uncertainty("AREA_M2", .11))
    ControlledSceneAPI(fixture_mode=True, layers=layers)
    u["quality_grade"] = "MEDIUM"
    with pytest.raises(DataIntegrityError, match="UNCERTAINTY_FIELDS_INVALID"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


@pytest.mark.parametrize("action", sorted(ACTIONS))
def test_huge_integer_requests_return_json_400(server, action):
    app, _, token, _ = server
    p = request(action, token)
    huge = 10**400
    if action in {"candidate_cameras", "person_layer", "curve_layer"}:
        p["time_range_s"] = [0, huge]
    elif action == "synced_frames":
        p["t_s"] = huge
    else:
        p["pick"]["t_click_s"] = huge
    code, raw, headers = http(app, "/api/" + action, p)
    assert code == 400 and "application/json" in headers["Content-Type"]
    assert json.loads(raw)["error"]["code"] == "INVALID_OR_STALE_REQUEST"


def test_huge_integer_polygon_coordinate_returns_json_400(server):
    app, _, token, _ = server
    p = request("candidate_cameras", token)
    p.update(target_region_ref=None, target_polygon={
        "floor_id": "FLOOR_FIXTURE", "frame_id": "fixture-world", "length_unit": "m",
        "polygon_m": [[0, 0], [1, 0], [10**400, 1]]})
    code, raw, _ = http(app, "/api/candidate_cameras", p)
    assert code == 400 and "error" in json.loads(raw)


@pytest.mark.parametrize("link_vendor", [False, True])
def test_server_configured_symlink_roots_preserve_legacy_vendor(server, tmp_path, link_vendor):
    original, _, _, root = server
    vendor = root / "vendor"
    target = vendor / "build/three.module.js"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"SYNTHETIC VENDOR MODULE")
    alias = root.parent / (root.name + "-alias")
    alias.symlink_to(root, target_is_directory=True)
    app = Application(original.workbench, alias,
                      vendor_root=alias / "vendor" if link_vendor else vendor)
    code, raw, _ = http(app, "/vendor/three.module.js", method="GET")
    assert code == 200 and raw == b"SYNTHETIC VENDOR MODULE"
    assert app.repo == root.resolve() and app.vendor_root == vendor.resolve()


@pytest.mark.parametrize("name", ["layout.mjs", "shell-view.mjs", "uncertainty.mjs"])
def test_v2_shell_imports_are_explicitly_allowlisted(server, name):
    app, _, _, root = server
    path = root / "frontend/workbench-v2" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"// SYNTHETIC SHELL MODULE")
    assert STATIC_FILES["/workbench-v2/" + name] == "frontend/workbench-v2/" + name
    code, raw, _ = http(app, "/workbench-v2/" + name, method="GET")
    assert code == 200 and raw == b"// SYNTHETIC SHELL MODULE"


@pytest.mark.parametrize("part", ["person", "curve"])
def test_missing_uncertainty_rejected_at_fixture_construction(part):
    layers = fixture_layers()
    row = (layers["estimates"][0]["composed_ground"] if part == "person"
           else layers["curves"][0]["segments"][0])
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


@pytest.mark.parametrize("missing", [True, False])
def test_every_estimate_requires_composed_ground(missing):
    layers = fixture_layers()
    if missing:
        layers["estimates"][0].pop("composed_ground")
        with pytest.raises(DataIntegrityError, match="COMPOSED_GROUND_MISSING"):
            ControlledSceneAPI(fixture_mode=True, layers=layers)
    else:
        ControlledSceneAPI(fixture_mode=True, layers=layers)


@pytest.mark.parametrize("part", ["curve", "composed_ground"])
@pytest.mark.parametrize("geometry,kind,extent", [
    (None, "LENGTH_M", .1), ({}, "LENGTH_M", .1),
    ({"length_m": 3}, "LENGTH_M", .1),
    ({"length_m": 3}, "AREA_M2", 3),
    ({"polygon_area_m2": 3}, "AREA_M2", .1),
    ({"polygon_area_m2": 3}, "LENGTH_M", 3),
    ({"length_m": -1}, "LENGTH_M", .1),
    ({"polygon_area_m2": True}, "AREA_M2", .1),
    ({"length_m": 10**400}, "LENGTH_M", .1),
])
def test_ready_geometry_cannot_be_absent_or_underreported(part, geometry, kind, extent):
    layers = fixture_layers()
    row = ready_segment(layers) if part == "curve" else layers["estimates"][0][part]
    row.update(status="READY", geometry=geometry, uncertainty=declared_uncertainty(kind, extent))
    with pytest.raises(DataIntegrityError, match="INFERENCE_GEOMETRY_INVALID"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


@pytest.mark.parametrize("field,kind", [("length_m", "LENGTH_M"),
                                        ("polygon_area_m2", "AREA_M2")])
def test_geometry_extent_equal_or_conservative_is_accepted(field, kind):
    for extent in (.25, .5):
        layers = fixture_layers()
        ready_segment(layers).update(geometry={field: .25},
                                     uncertainty=declared_uncertainty(kind, extent))
        ControlledSceneAPI(fixture_mode=True, layers=layers)


@pytest.mark.parametrize("kind,state", [
    ("OBSERVED", "PROJECTED_OBSERVATION"),
    ("INFERRED_CONNECTOR", "INFERRED_INTERPOLATION"),
    ("BLIND_HYPOTHESIS", "INFERRED_HYPOTHESIS"),
    ("MISSING_GAP", "MISSING"), ("UNKNOWN_GAP", "UNKNOWN"),
])
def test_curve_kind_state_mapping_is_closed(kind, state):
    layers = fixture_layers()
    row = ready_segment(layers)
    row.update(kind=kind, evidence_state=state)
    if kind == "UNKNOWN_GAP":
        row.update(geometry=None, reason="GROUND_UNAVAILABLE")
    ControlledSceneAPI(fixture_mode=True, layers=layers)
    for wrong in ["PROJECTED_OBSERVATION", "INFERRED_INTERPOLATION", "INFERRED_HYPOTHESIS",
                  "MISSING", "UNKNOWN", None, {}]:
        if wrong == state:
            continue
        row["evidence_state"] = wrong
        with pytest.raises(DataIntegrityError, match="CURVE_KIND_INVALID"):
            ControlledSceneAPI(fixture_mode=True, layers=layers)


def test_prediction_is_reserved_and_rejected():
    layers = fixture_layers()
    ready_segment(layers).update(kind="PREDICTION", evidence_state="INFERRED_PREDICTION")
    with pytest.raises(DataIntegrityError, match="CURVE_KIND_INVALID"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


@pytest.mark.parametrize("state", [None, "", "PROJECTED_OBSERVATION", "OBSERVED", "MISSING",
                                  "UNKNOWN", "made_up", {}])
def test_composed_ground_evidence_is_inferred_constrained(state):
    layers = fixture_layers()
    layers["estimates"][0]["composed_ground"]["evidence_state"] = state
    with pytest.raises(DataIntegrityError, match="COMPOSED_GROUND_EVIDENCE_INVALID"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


@pytest.mark.parametrize("part", ["curve", "composed_ground", "heading"])
@pytest.mark.parametrize("constraints", [[], ["made_up"], [""], [True],
                                         ["endpoint_estimates"], ["k1_reachability"],
                                         ["prior", "track_height", "occlusion_near",
                                          "lowest_visible_far", "speed"]])
def test_ready_constraint_names_are_closed(part, constraints):
    layers = fixture_layers()
    if part == "curve":
        row = ready_segment(layers)
    elif part == "heading":
        row = {"state": "INFERRED", "direction_xy": [1, 0],
               "uncertainty": declared_uncertainty("ANGLE_DEG", 15)}
        layers["estimates"][0][part] = row
    else:
        row = layers["estimates"][0][part]
        row.update(status="READY", geometry={"length_m": .1},
                   uncertainty=declared_uncertainty("LENGTH_M", .1))
    row["uncertainty"]["constraints_used"] = constraints
    if constraints == ["prior", "track_height", "occlusion_near",
                       "lowest_visible_far", "speed"] or (
            part == "curve" and constraints in [["endpoint_estimates"], ["k1_reachability"]]):
        ControlledSceneAPI(fixture_mode=True, layers=layers)
    else:
        with pytest.raises(DataIntegrityError, match="UNCERTAINTY_FIELDS_INVALID"):
            ControlledSceneAPI(fixture_mode=True, layers=layers)


@pytest.mark.parametrize("case", ["absent_geometry", "geometry", "reason"])
def test_unknown_gap_requires_null_geometry_and_reason(case):
    layers = fixture_layers()
    row = layers["curves"][0]["segments"][0]
    row.update(kind="UNKNOWN_GAP", evidence_state="UNKNOWN", geometry=None, reason="NO_GROUND")
    if case == "absent_geometry":
        row.pop("geometry")
    elif case == "geometry":
        row["geometry"] = {"length_m": .1}
    else:
        row.pop("reason")
    with pytest.raises(DataIntegrityError, match="INFERENCE_ITEM_INVALID"):
        ControlledSceneAPI(fixture_mode=True, layers=layers)


@pytest.mark.parametrize("kind,state", [("UNKNOWN_GAP", "UNKNOWN"), ("MISSING_GAP", "MISSING")])
def test_gap_click_returns_no_support_relation(server, kind, state):
    app, _, token, _ = server
    layers = fixture_layers()
    layers["curves"][0]["segments"][0].update(kind=kind, evidence_state=state)
    app.workbench.controlled_scene = ControlledSceneAPI(fixture_mode=True, layers=layers)
    code, raw, _ = http(app, "/api/evidence_lookup", request("evidence_lookup", token))
    value = json.loads(raw)
    assert code == 200 and value["relation"] == "NO_SUPPORT"
    assert value["status"] == "NO_SUPPORT" and value["reason"] == kind
    assert value["nearest_support"] is None and value["other_supports"] == []
    assert value["jump"] is None


@pytest.mark.parametrize("kind,state,relation", [
    ("BLIND_HYPOTHESIS", "INFERRED_HYPOTHESIS", "HYPOTHESIS_ENDPOINTS_AND_NEGATIVE_EVIDENCE"),
    ("OBSERVED", "PROJECTED_OBSERVATION", None),
    ("INFERRED_CONNECTOR", "INFERRED_INTERPOLATION", None),
])
def test_evidence_relation_does_not_borrow_hypothesis_support(server, kind, state, relation):
    app, _, token, _ = server
    layers = fixture_layers()
    layers["curves"][0]["segments"][0].update(kind=kind, evidence_state=state)
    app.workbench.controlled_scene = ControlledSceneAPI(fixture_mode=True, layers=layers)
    code, raw, _ = http(app, "/api/evidence_lookup", request("evidence_lookup", token))
    value = json.loads(raw)
    assert code == 200 and value["status"] == "UNKNOWN"
    assert value["relation"] == relation
    assert value["nearest_support"] is None and value["other_supports"] == []
    assert value["jump"] is None
