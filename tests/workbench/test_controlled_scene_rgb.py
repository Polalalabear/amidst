"""2a in-process WSGI with generated RGB bytes; no renderer, model, GT or listener."""

import hashlib
import json
import struct
import zlib
from dataclasses import replace
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from amidst.engineering.registry import content_hash
from amidst.workbench.controlled_scene_api import ACTIONS, ControlledSceneAPI
from amidst.workbench.controlled_scene_data import RunRegistration, load_safe_run
from amidst.workbench.controlled_scene_rgb_api import MEDIA_PATH, ControlledRGBAPI
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.scene_errors import DataIntegrityError
from amidst.workbench.service import Application, Workbench


def png():
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data)))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 960, 540, 8, 2, 0, 0, 0))
            + chunk(b"tEXt", b"Source\0TEST PRIVATE LOCATOR MUST NOT BE SERVED")
            + chunk(b"IDAT", zlib.compress((b"\0" + b"\x80" * (960 * 3)) * 540))
            + chunk(b"IEND", b""))


def http(app, url, payload=None, **extra):
    parts = urlsplit(url)
    raw = json.dumps(payload).encode() if payload is not None else b""
    env = {"HTTP_HOST": "127.0.0.1:12345", "SERVER_PORT": "12345",
           "REQUEST_METHOD": "POST" if payload is not None else "GET",
           "PATH_INFO": parts.path, "QUERY_STRING": parts.query, "wsgi.input": BytesIO(raw),
           "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(raw)), **extra}
    result = {}

    def start(status, headers):
        result.update(code=int(status.split()[0]), headers=dict(headers))

    result["raw"] = b"".join(app(env, start))
    if result["headers"]["Content-Type"].startswith("application/json"):
        result["json"] = json.loads(result["raw"])
    return SimpleNamespace(**result)


@pytest.fixture
def server(tmp_path):
    root = tmp_path.resolve()
    now = [1000.0]
    states = []
    for run_id in ("test-a", "test-b1"):
        run_root = root / run_id
        safe = run_root / "safe_bundle"
        safe.mkdir(parents=True)
        sampling = {"fps": 5, "duration_s": .6, "sample_count_per_camera": 3,
                    "last_timestamp_s": .4, "sampling_version": "5fps-v1",
                    "image_size_px": [960, 540], "format": "PNG_RGB8"}
        common = {"scene_id": "test-scene", "scene_version": 1, "run_id": run_id,
                  "clock_id": "clock:" + run_id, "source_sha256": "a" * 64,
                  "sampling": sampling, "data_origin": "ACTUAL_BLENDER"}
        camera_ids = ["CAM_1", "CAM_2"]
        cameras, bindings = [], []
        for camera in [*camera_ids, "CAM_UNBOUND"]:
            c = {"camera_id": camera, "width": 960, "height": 540}
            c["calibration_sha256"] = content_hash(c)
            cameras.append(c)
            if camera in camera_ids:
                b = {"camera_id": camera, "run_id": run_id, "clock_id": common["clock_id"],
                     "valid_time_range_s": [0, .6], "visibility_index_ref": None}
                b["binding_sha256"] = content_hash(b)
                bindings.append(b)
        records, missing = [], []
        for camera in camera_ids:
            for i in range(3):
                sample = {"camera_id": camera, "frame_index": i, "timestamp_s": i / 5}
                if i == 1:
                    missing.append(sample | {"reason": "RGB_RECORD_ABSENT"})
                else:
                    ref = f"rgb/{camera}/frame_{i:06d}.png"
                    p = run_root / ref
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(png())
                    records.append(sample | {"rgb_ref": ref,
                                             "file_sha256": hashlib.sha256(png()).hexdigest()})
        files = {
            "scene_static": {"schema_version": "controlled-scene.static.v1",
                             "scene_id": common["scene_id"], "scene_version": 1,
                             "source_static_sha256": common["source_sha256"]},
            "cameras": {"schema_version": "controlled-scene.cameras.v1",
                        "cameras": cameras, "run_bindings": bindings},
            "rgb_index": common | {"schema_version": "controlled-scene.rgb-index.v1",
                                   "rgb_ref_base": "RUN_ROOT", "expected_grid": {
                                       "camera_ids": list(reversed(camera_ids)),
                                       "frame_index_start": 0, "frame_index_end_exclusive": 3,
                                       "timestamp_rule": "frame_index / fps"},
                                   "records": records, "missing": missing},
            "runtime_profile": common | {
                "schema_version": "controlled-scene.runtime-profile.v1", "camera_ids": camera_ids,
                "rgb_index_schema_version": "controlled-scene.rgb-index.v1",
                "runtime_readiness": "NOT_READY", "complete_runtime_bundle": False,
                "required_inputs": ["rgb_perception_index"],
                "unavailable_inputs": ["rgb_perception_index"],
                "missing_inputs_policy": "FAIL_CLOSED"},
        }
        manifest = common | {"schema_version": "controlled-scene.manifest.v1",
                             "allowlist": [], "geometry_files": [],
                             "runtime_readiness": "NOT_READY"}
        state = SimpleNamespace(root=run_root, files=files, manifest=manifest, reg=None)
        states.append(state)

    def persist(state):
        entries = []
        for name, value in state.files.items():
            raw = json.dumps(value).encode()
            (state.root / "safe_bundle" / (name + ".json")).write_bytes(raw)
            entries.append({"role": name, "filename": name + ".json",
                            "file_sha256": hashlib.sha256(raw).hexdigest()})
        state.manifest["allowlist"] = entries
        raw = json.dumps(state.manifest).encode()
        (state.root / "safe_bundle/manifest.json").write_bytes(raw)
        state.reg = RunRegistration(state.root, hashlib.sha256(raw).hexdigest(), "test-scene",
                                    state.manifest["run_id"], "a" * 64)

    for state in states:
        persist(state)
    api = ControlledRGBAPI(tuple(s.reg for s in states), clock=lambda: now[0])
    wb = Workbench({}, ReviewStore(root / "reviews.db", {}), controlled_scene=api)
    app = Application(wb, root)
    session = wb.session({"role": "management"})["session_ref"]
    return SimpleNamespace(app=app, api=api, wb=wb, session=session, states=states,
                           now=now, persist=persist)


def request(server, t=0, *, run="test-a", cameras=None, action="synced_frames"):
    return {"schema_version": "controlled-scene." + action.replace("_", "-") + "-request.v1",
            "session_ref": server.session, "scene_id": "test-scene", "run_id": run,
            "t_s": t, "camera_ids": cameras or ["CAM_1", "CAM_2"]}


def test_bootstrap_registers_distinct_real_runs_and_partial_readiness(server):
    r = http(server.app, "/api/bootstrap?surface=workbench-v2")
    assert r.code == 200 and r.json["data_origin"] == "ACTUAL_BLENDER"
    assert r.json["status"] == "PARTIAL" and r.json["fixture_marker"] is None
    scene = r.json["scenes"][0]
    assert scene["run_ids"] == ["test-a", "test-b1"]
    assert scene["camera_ids"] == ["CAM_1", "CAM_2"]
    for run in scene["runs"]:
        assert run["runtime_readiness"] == "NOT_READY"
        assert run["capabilities"]["synced_frames"] == "AVAILABLE"
        assert run["capabilities"]["person_layer"] == "NOT_MATERIALIZED"
    assert http(server.app, "/api/bootstrap").json["data_origin"] == "LEGACY_RUNTIME"


@pytest.mark.parametrize("t,index,age", [(0, 0, 0), (.199999, 0, .199999), (.2, 1, 0),
                                        (.399999, 1, .199999), (.4, 2, 0), (.599999, 2, .199999),
                                        (.6, None, None), (-.000001, None, None)])
def test_real_grid_missing_does_not_fall_back(server, t, index, age):
    r = http(server.app, "/api/synced_frames", request(server, t))
    assert r.code == 200
    assert r.json["expected_frame_index"] == index and r.json["sample_age_s"] == age
    state = "OUT_OF_RANGE" if index is None else "MISSING" if index == 1 else "READY"
    assert all(tile["status"] == state for tile in r.json["tiles"])
    assert r.json["media_tokens_issued"] == (2 if state == "READY" else 0)


def test_media_url_scoped_and_text_metadata_removed_with_source_and_served_hashes(server):
    r = http(server.app, "/api/synced_frames", request(server))
    assert r.code == 200
    assert server.session not in r.raw.decode() and "rgb/CAM_" not in r.raw.decode()
    digest = r.json.pop("output_sha256")
    assert content_hash(r.json) == digest
    for tile in r.json["tiles"]:
        media = http(server.app, tile["frame_ref"])
        assert media.code == 200 and media.headers["Content-Type"] == "image/png"
        assert b"PRIVATE LOCATOR" not in media.raw and b"tEXt" not in media.raw
        assert hashlib.sha256(media.raw).hexdigest() == tile["served_sha256"]
        assert hashlib.sha256(png()).hexdigest() == tile["file_sha256"]
        assert tile["file_sha256"] != tile["served_sha256"]
        for header, expected in [("Cache-Control", "no-store"),
                                 ("Referrer-Policy", "no-referrer"),
                                 ("X-Content-Type-Options", "nosniff")]:
            assert media.headers[header] == expected


def test_loader_only_opens_manifest_listed_safe_files_and_requested_rgb(server, monkeypatch):
    import amidst.workbench.controlled_scene_data as module
    import amidst.workbench.controlled_scene_rgb_data as scoped
    original = module.read_regular
    opened = []

    def guard(root, relative, **kwargs):
        assert relative in {"safe_bundle/manifest.json", "safe_bundle/scene_static.json",
                            "safe_bundle/cameras.json", "safe_bundle/runtime_profile.json",
                            "safe_bundle/rgb_index.json", "rgb/CAM_1/frame_000000.png",
                            "rgb/CAM_2/frame_000000.png"}
        opened.append(relative)
        return original(root, relative, **kwargs)

    monkeypatch.setattr(module, "read_regular", guard)
    monkeypatch.setattr(scoped, "read_regular", guard)
    r = http(server.app, "/api/synced_frames", request(server))
    assert r.code == 200 and opened
    assert http(server.app, r.json["tiles"][0]["frame_ref"]).code == 200
    loaded = load_safe_run(server.states[0].reg, purpose="RGB_PLAYBACK")
    assert not loaded.calibrations
    assert loaded.files["runtime_profile"]["runtime_readiness"] == "NOT_READY"
    with pytest.raises(DataIntegrityError):
        load_safe_run(server.states[0].reg)  # RGB scope never weakens FULL_RUNTIME.


@pytest.mark.parametrize("action", sorted(ACTIONS - {"synced_frames"}))
def test_other_real_layers_fail_unavailable_without_fixture_fallback(server, action):
    r = http(server.app, "/api/" + action, request(server, action=action))
    assert r.code == 503 and r.json["error"]["reason"] == "CONTROLLED_LAYER_NOT_MATERIALIZED"
    assert "SYNTHETIC_FIXTURE" not in r.raw.decode()


@pytest.mark.parametrize("case", ["unknown_run", "fixture_run", "unbound_camera", "bad_session",
                                 "sub_microsecond", "bool_time", "huge_time", "private", "pin"])
def test_invalid_scope_never_issues_token(server, case):
    p = request(server)
    if case == "unknown_run":
        p["run_id"] = "other"
    elif case == "fixture_run":
        p["run_id"] = "fixture-controlled-5fps-v1-r001"
    elif case == "unbound_camera":
        p["camera_ids"] = ["CAM_UNBOUND"]
    elif case == "bad_session":
        p["session_ref"] = "invalid"
    elif case == "sub_microsecond":
        p["t_s"] = .0000001
    elif case == "bool_time":
        p["t_s"] = True
    elif case == "huge_time":
        p["t_s"] = 10 ** 400
    elif case == "private":
        p["actor_id"] = "bad"
    else:
        p["source_sha256"] = "0" * 64
    assert http(server.app, "/api/synced_frames", p).code in {400, 403, 409}
    assert not server.api._media_grants


@pytest.mark.parametrize("case,reason", [
    ("absent", "PINNED_RGB_RECORD_MISSING"), ("hash", "RGB_RECORD_HASH_MISMATCH"),
    ("symlink", "PATH_REJECTED"), ("png", "RGB_PNG_INVALID"),
    ("manifest", "SAFE_FILE_HASH_MISMATCH"), ("index", "SAFE_FILE_HASH_MISMATCH"),
    ("grid", "RGB_INDEX_INCOMPLETE"), ("source", "RGB_PLAYBACK_MANIFEST_MISMATCH"),
])
def test_integrity_failure_is_atomic_and_not_missing(server, case, reason):
    state = server.states[0]
    path = state.root / "rgb/CAM_2/frame_000000.png"
    if case == "absent":
        path.unlink()
    elif case == "hash":
        path.write_bytes(b"corrupted")
    elif case == "symlink":
        path.unlink()
        path.symlink_to(state.root / "rgb/CAM_1/frame_000000.png")
    elif case == "png":
        path.write_bytes(b"invalid png")
        state.files["rgb_index"]["records"][2]["file_sha256"] = (
            hashlib.sha256(b"invalid png").hexdigest())
        server.persist(state)
    elif case == "manifest":
        (state.root / "safe_bundle/manifest.json").write_text("{}")
    elif case == "index":
        (state.root / "safe_bundle/rgb_index.json").write_text("{}")
    elif case == "grid":
        state.files["rgb_index"]["records"].pop()
        server.persist(state)
    else:
        state.manifest["source_sha256"] = "b" * 64
        server.persist(state)
    if case in {"png", "grid", "source"}:
        server.api._runs[state.reg.run_id] = state.reg
    r = http(server.app, "/api/synced_frames", request(server))
    assert r.code == 409 and r.json["error"] == {
        "error_class": "DataIntegrityError", "reason": reason}
    assert "tiles" not in r.json and not server.api._media_grants


@pytest.mark.parametrize("case,code", [("invalid", 403), ("expired", 410), ("revoked", 403),
                                     ("scope", 403), ("extra_query", 400), ("duplicate", 400),
                                     ("cross_origin", 403), ("cross_site", 403),
                                     ("stale", 409), ("rgb_hash", 409), ("gone", 409)])
def test_media_token_failure_paths(server, case, code):
    response = http(server.app, "/api/synced_frames", request(server))
    url = response.json["tiles"][0]["frame_ref"]
    extra = {}
    if case == "invalid":
        url = MEDIA_PATH + "?token=" + "x" * 43
    elif case == "expired":
        server.now[0] += 120
    elif case == "revoked":
        del server.wb.sessions[server.session]
    elif case == "scope":
        server.wb.sessions[server.session].scene_ids = frozenset()
    elif case == "extra_query":
        url += "&run_id=test-b1"
    elif case == "duplicate":
        url += "&token=bad"
    elif case == "cross_origin":
        extra["HTTP_ORIGIN"] = "http://evil.invalid"
    elif case == "cross_site":
        extra["HTTP_SEC_FETCH_SITE"] = "cross-site"
    elif case == "stale":
        old = server.states[0].reg
        server.api._runs[old.run_id] = replace(old, manifest_sha256="0" * 64)
    elif case == "rgb_hash":
        (server.states[0].root / "rgb/CAM_1/frame_000000.png").write_bytes(b"changed")
    else:
        (server.states[0].root / "rgb/CAM_1/frame_000000.png").unlink()
    r = http(server.app, url, **extra)
    assert r.code == code and r.json["schema_version"] == "controlled-scene.error.v1"
    assert "tiles" not in r.json and b"PRIVATE LOCATOR" not in r.raw


def test_bootstrap_safe_file_integrity_and_missing_metadata(server):
    path = server.states[0].root / "safe_bundle/runtime_profile.json"
    path.write_text("{}")
    assert http(server.app, "/api/bootstrap?surface=workbench-v2").code == 409
    path.unlink()
    # Integrity failures stay closed for this process; missing inputs are not substituted.
    assert http(server.app, "/api/bootstrap?surface=workbench-v2").code == 409
    assert http(server.app, "/api/bootstrap").code == 200


def test_missing_metadata_is_503_without_ready_or_fixture(server):
    (server.states[0].root / "safe_bundle/runtime_profile.json").unlink()
    r = http(server.app, "/api/bootstrap?surface=workbench-v2")
    assert r.code == 503
    assert r.json["error"]["error_class"] == "RequiredInputUnavailable"
    assert "scenes" not in r.json


def test_observed_integrity_failure_closes_existing_grants_for_whole_run(server):
    response = http(server.app, "/api/synced_frames", request(server))
    url = response.json["tiles"][0]["frame_ref"]
    damaged = server.states[0].root / "rgb/CAM_2/frame_000000.png"
    damaged.write_bytes(b"corrupted")
    assert http(server.app, "/api/synced_frames", request(server)).code == 409
    # CAM_1 is unchanged, but a known integrity failure closes its run as well.
    assert http(server.app, url).code == 409
    # The separately pinned other run can still serve its own records.
    assert http(server.app, "/api/synced_frames", request(server, run="test-b1")).code == 200


def test_fixture_surface_never_serves_real_media(server):
    server.wb.controlled_scene = ControlledSceneAPI(fixture_mode=True)
    r = http(server.app, MEDIA_PATH + "?token=" + "x" * 43)
    assert r.code == 403
    assert r.json["error"]["reason"] == "REAL_RGB_NOT_CONFIGURED"


def test_office_factory_uses_canonical_asset_root_not_phase1_evidence(server, monkeypatch):
    import office_demo_backend as backend

    canonical = server.states[0].root.parent
    monkeypatch.setattr(backend, "assets_repo", lambda: canonical)
    app = backend.application({}, canonical / "factory.db", canonical,
                              canonical / ".local-worktrees/phase1-finalization")
    assert isinstance(app.workbench.controlled_scene, ControlledRGBAPI)
    runs = app.workbench.controlled_scene._runs
    assert set(runs) == {"ctrl-lcorr-s1-a-5fps-v1-r001", "ctrl-lcorr-s1-b1-5fps-v1-r001"}
    assert all(reg.run_root.parent == canonical / "data/pilot/controlled_scene_v1/runs"
               for reg in runs.values())
    assert http(app, "/api/bootstrap").code == 200


def test_grant_bound_to_record_and_run_even_with_same_png_bytes(server):
    a = http(server.app, "/api/synced_frames", request(server)).json
    b = http(server.app, "/api/synced_frames", request(server, run="test-b1")).json
    a_url, b_url = a["tiles"][0]["frame_ref"], b["tiles"][0]["frame_ref"]
    assert a_url != b_url
    a_grant = server.api._media_grants[urlsplit(a_url).query.split("=")[1]]
    b_grant = server.api._media_grants[urlsplit(b_url).query.split("=")[1]]
    assert a_grant.registration.run_id == "test-a"
    assert b_grant.registration.run_id == "test-b1"
    assert http(server.app, b_url + "&camera_id=CAM_2").code == 400


def test_token_store_bounded_and_retired_tokens_fail_closed(server, monkeypatch):
    import amidst.workbench.controlled_scene_rgb_api as module

    monkeypatch.setattr(module, "MAX_MEDIA_GRANTS", 2)
    first = http(server.app, "/api/synced_frames", request(server)).json
    http(server.app, "/api/synced_frames", request(server, .4))
    assert len(server.api._media_grants) == 2
    assert http(server.app, first["tiles"][0]["frame_ref"]).code == 403
