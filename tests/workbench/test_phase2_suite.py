"""Unified role, manual-study, frozen-source and mode guards for new local tools."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError
from test_service import FakeScene

from amidst.workbench.phase2_suite import Phase2Suite, SuiteRequest
from amidst.workbench.product_bridge import BridgeDenied
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.service import Denied, Workbench


@pytest.fixture
def suite(tmp_path: Any) -> tuple[Phase2Suite, Workbench, str]:
    scene = FakeScene()
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    reviews = ReviewStore(tmp_path / "state.sqlite3", {
        scene.scene_id: {key: scene.snapshot()[key] for key in keys}})
    workbench = Workbench({scene.scene_id: scene}, reviews)
    extension = Phase2Suite(workbench, tmp_path)
    token = workbench.session({"role": "research"})["session_ref"]
    return extension, workbench, token


def payload(token: str, **fields: Any) -> dict[str, Any]:
    return {"session_ref": token, "scene_id": "alpha", **fields}


def test_optional_runtime_is_explicit_and_agent_has_no_mock_fallback(suite: Any) -> None:
    extension, _, token = suite
    context = extension.call("context", payload(token))
    assert context["research"] is context["agent"] is context["storage"] is None
    with pytest.raises(RuntimeError, match="LOCAL_AGENT_UNAVAILABLE"):
        extension.call("agent_start", payload(token, message="查看事件",
            camera_refs=("camera:" + "1" * 24,), time_range=(0, 1)))


def test_roles_sources_unknown_actions_and_browser_configuration_fail_closed(suite: Any) -> None:
    extension, workbench, token = suite
    management = workbench.session({"role": "management"})["session_ref"]
    with pytest.raises(Denied, match="ROLE_DENIED"):
        extension.call("context", payload(management))
    with pytest.raises(Denied, match="SCENE_DENIED"):
        extension.call("context", payload(token, scene_id="other"))
    with pytest.raises(BridgeDenied, match="ACTION_DENIED"):
        extension.call("sql", payload(token))
    for field in ("dsn", "schema_name", "model", "endpoint", "source_locator", "owner_key"):
        with pytest.raises(ValidationError):
            SuiteRequest.model_validate(payload(token, **{field: "untrusted"}))


def test_manual_baseline_blocks_all_new_assistance(suite: Any) -> None:
    extension, workbench, token = suite
    def deny(*_: Any) -> None:
        raise Denied("STUDY_MANUAL_ASSISTANCE_DENIED")
    workbench.operator_studies = SimpleNamespace(guard_external=deny)
    for action, fields in (("context", {}), ("diagnostics", {}),
                           ("query", {"camera_id": "C1", "start": 0, "end": 1})):
        with pytest.raises(Denied, match="STUDY_MANUAL_ASSISTANCE_DENIED"):
            extension.call(action, payload(token, **fields))


def test_research_queries_reject_wrong_source_and_nonfinite_or_large_windows(suite: Any) -> None:
    extension, _, token = suite
    binding = {"scene_id": "alpha", "source_run_id": "alpha-run", "source_sha256": "a" * 64,
               "mode": "photos_plus_observations"}
    extension.research["photos_plus_observations"] = SimpleNamespace(
        context=lambda: {"binding": binding},
        query=lambda **kwargs: {"accepted": kwargs}, diagnostics=lambda: {"aggregate": True})
    result = extension.call("query", payload(token, camera_id="C1", start=0, end=3))
    assert result["accepted"]["run_id"] == "alpha-run"
    for start, end in ((4, 3), (0, 121)):
        with pytest.raises(BridgeDenied, match="FINITE_WINDOW_REQUIRED"):
            extension.call("query", payload(token, camera_id="C1", start=start, end=end))
    with pytest.raises(ValidationError):
        extension.call("query", payload(token, camera_id="C1", start=0, end=float("inf")))
    with pytest.raises(BridgeDenied, match="RESEARCH_SOURCE_WINDOW_DENIED"):
        extension.call("query", payload(token, camera_id="C1", start=0, end=6))
    binding["source_sha256"] = "b" * 64
    with pytest.raises(BridgeDenied, match="RESEARCH_SOURCE_BINDING_DENIED"):
        extension.call("diagnostics", payload(token))


def test_event_detail_issues_only_bound_original_media(suite: Any) -> None:
    extension, workbench, token = suite
    binding = {"scene_id": "alpha", "source_run_id": "alpha-run", "source_sha256": "a" * 64,
               "mode": "photos_plus_observations"}
    extension.research["photos_plus_observations"] = SimpleNamespace(
        context=lambda: {"binding": binding},
        event=lambda **_: {"event": {"media_refs": ["alpha-media"]}})
    extension.call("event", payload(token, event_ref="event-bound-ref"))
    assert workbench._session(token).media["alpha"] == {"alpha-media"}


def test_photos_only_uses_its_own_research_freeze_and_rejects_other_mode_refs(suite: Any) -> None:
    extension, _, token = suite
    for mode in ("photos_only", "photos_plus_observations"):
        binding = {"scene_id": "alpha", "source_run_id": "alpha-run", "source_sha256": "a" * 64,
                   "mode": mode, "freeze_ref": mode}
        extension.research[mode] = SimpleNamespace(
            context=lambda b=binding: {"binding": b},
            query=lambda b=binding, **_: {"binding": b})
    only = extension.call("query", payload(token, observation_mode="photos_only",
                                          camera_id="C1", start=0, end=3))
    plus = extension.call("query", payload(token, camera_id="C1", start=0, end=3))
    assert only["binding"]["freeze_ref"] != plus["binding"]["freeze_ref"]
    extension.research["photos_only"] = extension.research["photos_plus_observations"]
    with pytest.raises(BridgeDenied, match="RESEARCH_SOURCE_BINDING_DENIED"):
        extension.call("query", payload(token, observation_mode="photos_only",
                                        camera_id="C1", start=0, end=3))


def test_manual_preflight_stops_pending_owner_without_mode_specific_binding(suite: Any) -> None:
    extension, _, token = suite
    stopped = []
    extension.agent = SimpleNamespace(
        stop_all_pending_for_owner=lambda owner: stopped.append(owner))
    extension.before_manual_study(token)
    assert stopped == [token]
