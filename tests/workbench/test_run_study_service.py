"""New human-only workflows retain role, scene and strict HTTP request boundaries."""

import json
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from amidst.workbench.reviews import ReviewStore
from amidst.workbench.service import Application, Denied, Workbench


class Scene:
    scene_id = "synthetic-lab"
    label = "Isolated fixture"
    description = "Scope test"

    def media(self, ref):
        assert ref == "registered-frame"
        return "image/png", b"source-frame"

    def snapshot(self):
        return {"scene_id": self.scene_id, "source_hash": "a" * 64,
                "model_revision": "v1", "run_id": "test-run", "objects": [{
                    "object_id": "R1", "kind": "REGION", "label": "Region",
                    "semantic": "ROOM", "geometry": {"type": "polygon", "points":
                        [[0, 0, 0], [3, 0, 0], [3, 3, 0], [0, 3, 0]]},
                    "properties": {}, "editable_fields": ["label", "geometry", "semantic"],
                    "authority": "SYNTHETIC_CONFIG"}]}


class Jobs:
    def __init__(self):
        self.scene = SimpleNamespace(scene_id="synthetic-lab")
        self.calls = []

    def context(self, scene_id):
        self.calls.append(("context", scene_id))
        return {"available": True}

    def start(self, *args):
        self.calls.append(("start", *args))
        return {"state": "QUEUED"}

    def get(self, *args):
        self.calls.append(("get", *args))
        return {"state": "COMPLETED"}

    cancel = result = get

    def list(self, *args):
        self.calls.append(("list", *args))
        return {"items": []}


class Studies:
    def __init__(self):
        self.calls = []
        self.catalog = {"synthetic-lab": Scene()}

    def context(self, *args):
        self.calls.append(("context", *args))
        return {"status": "PREPARATION_REHEARSAL"}

    def start(self, *args):
        self.calls.append(("start", *args))
        return {"status": "RUNNING"}

    def resume(self, *args):
        self.calls.append(("resume", *args))
        return {"status": "RUNNING"}

    def view(self, *args):
        self.calls.append(("view", *args))
        return {"frame": {"media_ref": "registered-frame"}}

    def report(self, *args):
        self.calls.append(("report", *args))
        return {"status": "PREPARATION_REHEARSAL"}

    stop = record = submit = list = report

    def guard_external(self, *args):
        self.calls.append(("guard", *args))

    def authorize_media(self, *args):
        self.calls.append(("authorize_media", *args))
        if args[-1] != "registered-frame":
            raise ValueError("UNISSUED_MEDIA")


FIELDS = {
    "run_context": {}, "run_list": {},
    "run_start": {"annotation_version": 0, "parameters": {},
                  "idempotency_key": "isolated-request"},
    "run_get": {"job_ref": "runjob-" + "a" * 32},
    "run_cancel": {"job_ref": "runjob-" + "a" * 32},
    "run_result": {"job_ref": "runjob-" + "a" * 32},
    "operator_study_context": {}, "operator_study_list": {},
    "operator_study_start": {"task_ref": "task-reference", "mode": "manual"},
    "operator_study_view": {"study_ref": "study-reference", "camera_id": "C1",
                            "timestamp": 1.0},
    "operator_study_record": {"study_ref": "study-reference", "action": "correction"},
    "operator_study_submit": {"study_ref": "study-reference", "answer": {"unknown": True}},
    "operator_study_resume": {"study_ref": "study-reference", "recovery_token": "r" * 32},
    "operator_study_report": {"study_ref": "study-reference"},
    "operator_study_stop": {"study_ref": "study-reference"},
}


@pytest.fixture
def wired(tmp_path):
    scene = Scene()
    reviews = ReviewStore(tmp_path / "reviews.sqlite3", {scene.scene_id: scene.snapshot()})
    jobs, studies = Jobs(), Studies()
    workbench = Workbench({scene.scene_id: scene}, reviews,
                          run_jobs=jobs, operator_studies=studies)
    return workbench, jobs, studies


@pytest.mark.parametrize("action", FIELDS)
def test_new_actions_deny_management_before_any_backend(wired, action):
    workbench, jobs, studies = wired
    token = workbench.session({"role": "management"})["session_ref"]
    with pytest.raises(Denied, match="ROLE_DENIED"):
        workbench.call(action, {"session_ref": token, "scene_id": "synthetic-lab",
                                **FIELDS[action]})
    assert not jobs.calls and not studies.calls


@pytest.mark.parametrize("action", FIELDS)
def test_new_actions_validate_catalog_scope_before_any_backend(wired, action):
    workbench, jobs, studies = wired
    token = workbench.session({"role": "research"})["session_ref"]
    with pytest.raises(Denied, match="SCENE_DENIED"):
        workbench.call(action, {"session_ref": token, "scene_id": "unregistered",
                                **FIELDS[action]})
    assert not jobs.calls and not studies.calls


def test_study_owner_comes_from_server_session_and_media_is_issued(wired):
    workbench, _, studies = wired
    token = workbench.session({"role": "research"})["session_ref"]
    for action in ("operator_study_start", "operator_study_view", "operator_study_submit"):
        workbench.call(action, {"session_ref": token, "scene_id": "synthetic-lab",
                                **FIELDS[action]})
    assert all(call[2] == token for call in studies.calls)
    assert workbench.sessions[token].media["synthetic-lab"] == {"registered-frame"}


def test_study_media_authorizes_owner_and_issued_ref_before_original_bytes(wired):
    workbench, _, studies = wired
    token = workbench.session({"role": "research"})["session_ref"]
    assert workbench.study_media(token, "synthetic-lab", "study-reference",
                                 "registered-frame") == ("image/png", b"source-frame")
    assert studies.calls == [("authorize_media", "synthetic-lab", token,
                              "study-reference", "registered-frame")]
    with pytest.raises(ValueError, match="UNISSUED_MEDIA"):
        workbench.study_media(token, "synthetic-lab", "study-reference", "unissued")
    studies.calls.clear()
    management = workbench.session({"role": "management"})["session_ref"]
    with pytest.raises(Denied, match="ROLE_DENIED"):
        workbench.study_media(management, "synthetic-lab", "study-reference",
                              "registered-frame")
    assert studies.calls == []


@pytest.mark.parametrize("suffix", ["&owner_key=caller", "&ref=duplicate"])
def test_study_media_http_rejects_extra_or_duplicate_fields(wired, tmp_path, suffix):
    workbench, _, studies = wired
    token = workbench.session({"role": "research"})["session_ref"]
    query = urlencode({"session_ref": token, "scene_id": "synthetic-lab",
                       "study_ref": "study-reference", "ref": "registered-frame"}) + suffix
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/api/operator_study_media",
               "QUERY_STRING": query, "HTTP_HOST": "127.0.0.1:8016", "SERVER_PORT": "8016"}
    response = {}
    b"".join(Application(workbench, tmp_path)(
        environ, lambda status, headers: response.update(status=status)))
    assert response["status"] == "400 Bad Request"
    assert studies.calls == []


@pytest.mark.parametrize("method,args", [
    ("presentation_media", ("registered-frame",)),
    ("gallery_media", ("registered-frame",)),
    ("motion_media", ("synthetic-lab", "registered-frame")),
    ("cross_camera_media", ("synthetic-lab", "registered-frame")),
    ("physical_cross_camera_media", ("synthetic-lab", "registered-frame")),
])
def test_other_media_surfaces_enforce_manual_protocol_before_provider(wired, method, args):
    workbench, _, studies = wired
    token = workbench.session({"role": "research"})["session_ref"]

    def refuse(*values):
        studies.calls.append(("guard", *values))
        raise ValueError("MANUAL_BASELINE_EXTERNAL_ASSISTANCE_DENIED")

    studies.guard_external = refuse
    with pytest.raises(ValueError, match="MANUAL_BASELINE_EXTERNAL_ASSISTANCE_DENIED"):
        getattr(workbench, method)(token, *args)
    assert len(studies.calls) == 1


@pytest.mark.parametrize("extra", [
    {"path": "/private/source"}, {"producer": "arbitrary.module"},
    {"command": "shell"}, {"owner_key": "override"}, {"elapsed_seconds": 1},
    {"parameters": {"max_speed_m_s": True}},
    {"parameters": {"max_speed_m_s": "3"}},
    {"parameters": {"max_speed_m_s": float("nan")}},
])
def test_http_rejects_caller_paths_owners_and_non_numeric_parameters(wired, tmp_path, extra):
    workbench, jobs, studies = wired
    token = workbench.session({"role": "research"})["session_ref"]
    data = json.dumps({"session_ref": token, "scene_id": "synthetic-lab",
                       **FIELDS["run_start"], **extra}).encode()
    environ = {"REQUEST_METHOD": "POST", "PATH_INFO": "/api/run_start",
               "QUERY_STRING": "", "HTTP_HOST": "127.0.0.1:8016", "SERVER_PORT": "8016",
               "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(data)),
               "wsgi.input": BytesIO(data)}
    response = {}
    body = b"".join(Application(workbench, tmp_path)(
        environ, lambda status, headers: response.update(status=status)))
    assert response["status"] == "400 Bad Request"
    assert b"/private/source" not in body
    assert not jobs.calls and not studies.calls
