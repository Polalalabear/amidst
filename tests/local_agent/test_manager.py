"""Lifecycle tests are scripted fixtures, explicitly distinct from true-model receipts."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from amidst.engineering.access import digest
from amidst.local_agent import (
    AgentBinding,
    AgentDenied,
    AgentPolicy,
    LocalAgentManager,
    ModelAction,
    ModelCompletion,
)
from amidst.local_agent.contracts import EvidenceSelection, RequestGoal
from amidst.local_agent.evaluation import summarize_cases
from amidst.local_agent.evidence import build_evidence_receipt, verified_answer
from amidst.local_agent.requirements import (
    RequirementFeedback,
    derive_requirements,
    public_fact_refinement,
    validate_completion,
    validate_proposal,
)
from amidst.local_agent.tools import REQUEST_TYPES

CAMERA = "camera:" + "a" * 24
OTHER_CAMERA = "camera:" + "b" * 24
EVENT = "event:" + "c" * 24
SCENE, OWNER, SHA = "local-camera", "authorized-server-owner", "d" * 64


def binding(mode: str = "photos_plus_observations") -> AgentBinding:
    return AgentBinding.model_validate({
        "scene_id": SCENE, "session_ref": "server-product-session", "run_id": "frozen-run",
        "run_ref": "run:" + "e" * 24, "source_ref": "source:" + "f" * 24,
        "source_sha256": SHA, "observation_mode": mode, "freeze_ref": "freeze-" + SHA,
        "product_freeze_ref": "product-freeze-" + SHA, "config_sha256": SHA,
        "allowed_tools": list(REQUEST_TYPES), "time_range": [0, 40],
        "cameras": [{"camera_id": "DOOR", "camera_ref": CAMERA, "region_ids": ["LOBBY"]},
                    {"camera_id": "HALL", "camera_ref": OTHER_CAMERA, "region_ids": []}],
    })


class ScriptProvider:
    def __init__(self, actions: list[dict[str, Any]]) -> None:
        self.actions = actions
        self.messages: list[list[dict[str, str]]] = []
        self.entered, self.release = threading.Event(), threading.Event()
        self.release.set()

    def identity(self) -> dict[str, Any]:
        return {"provider": "SCRIPTED_TEST_ONLY", "model": "test-fixture", "model_digest": SHA}

    def complete(self, messages: list[dict[str, str]], *, max_output_tokens: int,
                 action_schema: dict[str, Any] | None = None
                 ) -> ModelCompletion:
        self.messages.append(messages)
        self.entered.set()
        assert self.release.wait(5)
        action = self.actions.pop(0)
        if action.get("citations") == ["LAST_RECEIPT"]:
            message = next(m for m in reversed(messages)
                           if m["content"].startswith("UNTRUSTED TOOL DATA"))
            data = json.loads(message["content"].split("\n", 1)[1])
            action["citations"] = [data["receipt_ref"]]
        if action.get("selections", [{}])[0].get("receipt_ref") == "LAST_RECEIPT":
            message = next(m for m in reversed(messages)
                           if m["content"].startswith("UNTRUSTED TOOL DATA"))
            data = json.loads(message["content"].split("\n", 1)[1])
            action["selections"][0]["receipt_ref"] = data["receipt_ref"]
        if action.get("kind") == "clarification":
            action.setdefault("missing_slots", ["target"])
        return ModelCompletion(ModelAction.model_validate(action), 100, 20, 1.25,
                               "test-fixture", SHA, "SCRIPTED_TEST_ONLY")


def prepared(tmp_path: Path, actions: list[dict[str, Any]], *,
             policy: AgentPolicy | None = None) -> tuple[LocalAgentManager, ScriptProvider, Any]:
    provider = ScriptProvider(actions)
    current = {"binding": binding(), "calls": []}

    def execute(owner: str, scope: AgentBinding, tool: str, params: dict[str, Any]
                ) -> dict[str, Any]:
        assert owner == OWNER
        assert "session_ref" not in params
        current["calls"].append((tool, params))
        return {"scope": scope.model_dump(mode="json"), "items": [
            {"event_ref": EVENT, "kind": "DWELL", "support_state": "UNKNOWN",
             "candidate_count": 2, "alternatives": ["first", "second"]}]}

    manager = LocalAgentManager(tmp_path / "ledger.sqlite3", provider=provider, policy=policy,
                                binding_resolver=lambda *_: current["binding"], executor=execute)
    return manager, provider, current


def query() -> dict[str, Any]:
    return {"kind": "tool", "tool": "query_events",
            "arguments": {"camera_ref": CAMERA, "time_range": [8, 16], "limit": 3},
            "goal": {"topic": "EVENTS", "selection": "PAGE",
                     "requested_fields": ["kind", "candidate_count"]}}


def answer(citation: str = "LAST_RECEIPT") -> dict[str, Any]:
    return {"kind": "answer", "selections": [{"receipt_ref": citation, "row_refs": []}]}


def step(manager: LocalAgentManager, case: dict[str, Any]) -> dict[str, Any]:
    manager.advance(SCENE, OWNER, case["agent_ref"])
    assert manager.wait_idle(5)
    return manager.get(SCENE, OWNER, case["agent_ref"])


def test_multistep_citation_and_actual_counters_do_not_confirm_identity(tmp_path: Path) -> None:
    manager, provider, current = prepared(tmp_path, [query(), answer()])
    case = manager.start(SCENE, OWNER, "請查門口八到十六秒的停留與替代解",
                         camera_refs=[CAMERA], time_range=[8, 16])
    assert case["state"] == "READY"
    assert "recovery_token" in case
    assert "session_ref" not in case["binding"]
    case = step(manager, case)
    assert case["state"] == "READY"
    case = step(manager, case)
    assert case["state"] == "COMPLETED"
    assert case["metrics"]["model_call_count"] == 2
    assert case["metrics"]["prompt_tokens"] == 200
    assert case["metrics"]["output_tokens"] == 40
    assert case["metrics"]["tool_call_count"] == 1
    assert len(current["calls"]) == 1
    assert case["tool_receipts"][0]["result"]["data"]["items"][0]["alternatives"] == [
        "first", "second"]
    assert case["answer"]["citations"] == [case["tool_receipts"][0]["receipt_ref"]]
    assert not case["confirmed_identity_or_behavior"]
    assert not case["candidate_order_changed"]
    assert len(provider.messages) == 2
    evaluation = summarize_cases([case])
    assert evaluation["duration_ms"] == {"p50": 1.25, "p95": 1.25}
    assert not evaluation["true_model_execution"]
    assert "recovery_token" not in json.dumps(evaluation)
    assert "recovery_token" not in json.dumps(manager.list(SCENE, OWNER))


def test_clarification_reply_and_stop_resume_are_persistent(tmp_path: Path) -> None:
    manager, provider, current = prepared(tmp_path, [
        {"kind": "clarification", "question": "你指哪個局部目標？"}, query()])
    case = manager.start(SCENE, OWNER, "查那個人的停留", time_range=[8, 16])
    case = step(manager, case)
    assert case["state"] == "NEEDS_CLARIFICATION"
    manager.stop(SCENE, OWNER, case["agent_ref"])
    manager = LocalAgentManager(tmp_path / "ledger.sqlite3", provider=provider,
                                binding_resolver=lambda *_: current["binding"],
                                executor=manager.executor)
    assert manager.resume(SCENE, OWNER, case["agent_ref"])["state"] == "NEEDS_CLARIFICATION"
    manager.reply(SCENE, OWNER, case["agent_ref"], "只查這個鏡頭的候選事件")
    case = step(manager, case)
    assert case["state"] == "READY"
    assert case["metrics"]["model_call_count"] == 2


@pytest.mark.parametrize(("patch", "code"), [
    ({"tool": "shell"}, "AGENT_TOOL_DENIED"),
    ({"arguments": {"camera_ref": CAMERA, "time_range": [0, 40]}}, "AGENT_WINDOW_DENIED"),
    ({"arguments": {"time_range": [8, 16]}}, "AGENT_LOCAL_CAMERA_REQUIRED"),
    ({"arguments": {"camera_ref": OTHER_CAMERA, "time_range": [8, 16]}},
     "AGENT_LOCAL_CAMERA_REQUIRED"),
    ({"arguments": {"session_ref": "fake", "time_range": [8, 16]}},
     "AGENT_INVALID_TOOL_ARGUMENTS"),
    ({"tool": "get_event_detail", "arguments": {"event_ref": EVENT}},
     "AGENT_REFERENCE_NOT_ISSUED"),
])
def test_unknown_tools_out_of_scope_and_unissued_refs_never_execute(
    tmp_path: Path, patch: dict[str, Any], code: str,
) -> None:
    manager, _, current = prepared(tmp_path, [query() | patch])
    case = manager.start(SCENE, OWNER, "query", camera_refs=[CAMERA], time_range=[8, 16])
    case = step(manager, case)
    assert case["state"] == "FAILED"
    assert case["error_code"] == code
    assert not current["calls"]
    assert case["metrics"]["model_call_count"] == 1


def test_unissued_final_citation_is_rejected_and_usage_remains_counted(tmp_path: Path) -> None:
    manager, _, _ = prepared(tmp_path, [answer("receipt:fake")])
    case = step(manager, manager.start(SCENE, OWNER, "查詢"))
    assert case["state"] == "FAILED"
    assert case["error_code"] == "AGENT_UNGROUNDED_CITATION"
    assert case["metrics"]["prompt_tokens"] == 100
    assert case["metrics"]["invalid_action_count"] == 1


def test_async_advance_stop_ignores_late_model_result(tmp_path: Path) -> None:
    manager, provider, current = prepared(tmp_path, [query()])
    provider.release.clear()
    case = manager.start(SCENE, OWNER, "查詢", time_range=[8, 16])
    running = manager.advance(SCENE, OWNER, case["agent_ref"])
    assert running["state"] == "RUNNING"
    assert provider.entered.wait(2)
    assert manager.stop(SCENE, OWNER, case["agent_ref"])["state"] == "STOPPED"
    provider.release.set()
    assert manager.wait_idle(5)
    stopped = manager.get(SCENE, OWNER, case["agent_ref"])
    assert stopped["state"] == "STOPPED"
    assert not current["calls"]
    assert not stopped["tool_receipts"]


def test_mode_or_freeze_change_during_model_cannot_commit_or_execute(tmp_path: Path) -> None:
    manager, provider, current = prepared(tmp_path, [query()])
    provider.release.clear()
    case = manager.start(SCENE, OWNER, "查詢", time_range=[8, 16])
    manager.advance(SCENE, OWNER, case["agent_ref"])
    assert provider.entered.wait(2)
    current["binding"] = binding().model_copy(update={"config_sha256": "a" * 64})
    provider.release.set()
    assert manager.wait_idle(5)
    assert not current["calls"]
    with pytest.raises(AgentDenied, match="BINDING_CHANGED"):
        manager.get(SCENE, OWNER, case["agent_ref"])
    raw = manager.ledger.load(manager._owner(OWNER), SCENE, case["agent_ref"])
    assert raw["state"] == "FAILED"
    assert raw["error_code"] == "AGENT_BINDING_CHANGED"


def test_model_budget_persists_across_stop_resume(tmp_path: Path) -> None:
    manager, _, _ = prepared(tmp_path, [query()], policy=AgentPolicy(max_model_calls=1))
    case = step(manager, manager.start(SCENE, OWNER, "query", time_range=[8, 16]))
    manager.stop(SCENE, OWNER, case["agent_ref"])
    manager.resume(SCENE, OWNER, case["agent_ref"])
    case = step(manager, case)
    assert case["state"] == "BUDGET_EXHAUSTED"
    assert case["metrics"]["model_call_count"] == 1
    with pytest.raises(AgentDenied, match="NOT_RESUMABLE"):
        manager.resume(SCENE, OWNER, case["agent_ref"])


def test_recovery_requires_secret_same_freeze_and_moves_owner(tmp_path: Path) -> None:
    manager, _, current = prepared(tmp_path, [])
    case = manager.start(SCENE, OWNER, "查詢")
    ref, token = case["agent_ref"], case["recovery_token"]
    with pytest.raises(AgentDenied, match="CASE_UNAVAILABLE"):
        manager.get(SCENE, "new-owner", ref)
    with pytest.raises(AgentDenied, match="RECOVERY_DENIED"):
        manager.recover(SCENE, "new-owner", ref, "z" * 43)
    current["binding"] = binding().model_copy(update={"session_ref": "new-product-session"})
    recovered = manager.recover(SCENE, "new-owner", ref, token)
    assert recovered["state"] == "READY"
    assert recovered["agent_ref"] == ref
    with pytest.raises(AgentDenied, match="CASE_UNAVAILABLE"):
        manager.get(SCENE, OWNER, ref)
    current["binding"] = binding().model_copy(update={"config_sha256": "a" * 64})
    with pytest.raises(AgentDenied, match="RECOVERY_BINDING_DENIED"):
        manager.recover(SCENE, "third-owner", ref, token)


def test_process_restart_requires_explicit_resume(tmp_path: Path) -> None:
    manager, provider, current = prepared(tmp_path, [])
    case = manager.start(SCENE, OWNER, "查詢")
    raw = manager.ledger.load(manager._owner(OWNER), SCENE, case["agent_ref"])
    raw["state"] = "RUNNING"
    manager.ledger.save(manager._owner(OWNER), raw, raw["revision"])
    restarted = LocalAgentManager(tmp_path / "ledger.sqlite3", provider=provider,
                                 binding_resolver=lambda *_: current["binding"],
                                 executor=manager.executor)
    assert restarted.get(SCENE, OWNER, case["agent_ref"])["state"] == "RESUME_REQUIRED"
    assert restarted.resume(SCENE, OWNER, case["agent_ref"])["state"] == "READY"


@pytest.mark.parametrize("selection", [
    {"time_range": [float("nan"), 20]}, {"time_range": [8, True]},
    {"time_range": [-1, 20]}, {"time_range": [8, 41]}, {"camera_refs": ["fake"]},
])
def test_invalid_initial_selection_is_rejected(tmp_path: Path, selection: dict[str, Any]) -> None:
    manager, _, _ = prepared(tmp_path, [])
    with pytest.raises(AgentDenied, match="INVALID_SELECTION"):
        manager.start(SCENE, OWNER, "query", **selection)


def test_tuple_selection_matches_workbench_dto_and_close_ignores_late_model(tmp_path: Path) -> None:
    manager, provider, current = prepared(tmp_path, [query()])
    provider.release.clear()
    case = manager.start(SCENE, OWNER, "query", camera_refs=(CAMERA,), time_range=(8, 16))
    manager.advance(SCENE, OWNER, case["agent_ref"])
    assert provider.entered.wait(2)
    manager.close()
    manager.close()
    provider.release.set()
    assert manager.wait_idle(5)
    raw = manager.ledger.load(manager._owner(OWNER), SCENE, case["agent_ref"])
    assert raw["state"] == "STOPPED"
    assert not raw["tool_receipts"]
    assert not current["calls"]
    with pytest.raises(AgentDenied, match="AGENT_CLOSED"):
        manager.context(SCENE, OWNER)


def test_manual_barrier_stops_old_modes_and_checks_generation_before_resolver(
    tmp_path: Path,
) -> None:
    manager, provider, _ = prepared(tmp_path, [query()])
    calls, forbidden = [], {"now": False}

    def resolve(_: str, scene: str, mode: str) -> AgentBinding:
        calls.append((scene, mode))
        if forbidden["now"]:
            raise ValueError("manual protocol would be contaminated")
        return binding(mode).model_copy(update={"scene_id": scene})

    manager.resolve = resolve
    provider.release.clear()
    running = manager.start(SCENE, OWNER, "query", time_range=[8, 16])
    other_mode = manager.start(SCENE, OWNER, "query", mode="photos_only")
    other_scene = manager.start("second-scene", OWNER, "query")
    foreign = manager.start(SCENE, "different-owner", "query")
    manager.advance(SCENE, OWNER, running["agent_ref"])
    assert provider.entered.wait(2)
    result = manager.stop_all_pending_for_owner(OWNER)
    assert set(result["stopped_agent_refs"]) == {
        running["agent_ref"], other_mode["agent_ref"], other_scene["agent_ref"]}
    before = len(calls)
    forbidden["now"] = True
    provider.release.set()
    assert manager.wait_idle(5)
    assert len(calls) == before
    assert manager.ledger.load(manager._owner("different-owner"), SCENE,
                               foreign["agent_ref"])["state"] == "READY"


def test_manual_barrier_drains_dispatched_tool_before_trial_start(tmp_path: Path) -> None:
    manager, _, _ = prepared(tmp_path, [query()])
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    def execute(*_: Any) -> dict[str, Any]:
        entered.set()
        assert release.wait(5)
        return {"items": [{"event_ref": EVENT}]}

    manager.executor = execute
    case = manager.start(SCENE, OWNER, "query", time_range=[8, 16])
    manager.advance(SCENE, OWNER, case["agent_ref"])
    assert entered.wait(2)

    def barrier() -> None:
        manager.stop_all_pending_for_owner(OWNER)
        finished.set()

    waiter = threading.Thread(target=barrier)
    waiter.start()
    assert not finished.wait(.05)
    release.set()
    assert finished.wait(2)
    assert manager.wait_idle(5)
    waiter.join(2)
    raw = manager.ledger.load(manager._owner(OWNER), SCENE, case["agent_ref"])
    assert raw["state"] == "STOPPED"
    assert not raw["tool_receipts"]


def test_invalid_model_json_still_accounts_reported_tokens_and_request_budget(
    tmp_path: Path,
) -> None:
    manager, provider, _ = prepared(tmp_path, [], policy=AgentPolicy(max_model_calls=1))
    provider.complete = lambda *_args, **_kwargs: ModelCompletion(  # type: ignore[method-assign]
        None, 101, 33, 2.0, "test-fixture", SHA, "SCRIPTED_TEST_ONLY",
        error_code="AGENT_INVALID_MODEL_RESPONSE")
    case = step(manager, manager.start(SCENE, OWNER, "query"))
    assert case["state"] == "FAILED"
    assert case["metrics"]["prompt_tokens"] == 101
    assert case["metrics"]["output_tokens"] == 33
    assert case["metrics"]["model_request_attempt_count"] == 1
    assert case["metrics"]["usage_unknown_request_count"] == 0
    assert case["model_receipts"][0]["action_kind"] == "INVALID"
    manager.resume(SCENE, OWNER, case["agent_ref"])
    assert step(manager, case)["state"] == "BUDGET_EXHAUSTED"


def test_stopped_model_retains_unknown_attempt_then_accounts_discarded_actual_usage(
    tmp_path: Path,
) -> None:
    manager, provider, _ = prepared(tmp_path, [query()])
    provider.release.clear()
    case = manager.start(SCENE, OWNER, "query", time_range=[8, 16])
    manager.advance(SCENE, OWNER, case["agent_ref"])
    assert provider.entered.wait(2)
    stopped = manager.stop(SCENE, OWNER, case["agent_ref"])
    assert stopped["metrics"]["usage_unknown_request_count"] == 1
    provider.release.set()
    assert manager.wait_idle(5)
    stopped = manager.get(SCENE, OWNER, case["agent_ref"])
    assert stopped["metrics"]["model_request_attempt_count"] == 1
    assert stopped["metrics"]["usage_unknown_request_count"] == 0
    assert stopped["metrics"]["model_call_count"] == 1
    assert stopped["metrics"]["prompt_tokens"] == 100
    assert stopped["metrics"]["output_tokens"] == 20
    assert stopped["model_receipts"][0]["result_discarded"] is True
    assert stopped["answer"] is None and not stopped["tool_receipts"]


@pytest.mark.parametrize("budget", ["elapsed", "tokens"])
def test_stop_resume_cannot_reset_consumed_runtime_or_actual_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, budget: str,
) -> None:
    from amidst.local_agent import manager as module

    clock = {"now": 0.0}
    monkeypatch.setattr(module, "time", SimpleNamespace(
        time=lambda: 1000 + clock["now"], monotonic=lambda: clock["now"]))
    policy = (AgentPolicy(max_elapsed_seconds=.01) if budget == "elapsed"
              else AgentPolicy(max_total_tokens=128))
    manager, provider, current = prepared(tmp_path, [query(), query()], policy=policy)
    original_complete = provider.complete

    def complete(*args: Any, **kwargs: Any) -> ModelCompletion:
        return replace(original_complete(*args, **kwargs), prompt_tokens=200)

    monkeypatch.setattr(provider, "complete", complete)
    provider.release.clear()
    case = manager.start(SCENE, OWNER, "query", time_range=[8, 16])
    manager.advance(SCENE, OWNER, case["agent_ref"])
    assert provider.entered.wait(2)
    clock["now"] = .05
    stopped = manager.stop(SCENE, OWNER, case["agent_ref"])
    assert stopped["metrics"]["elapsed_ms"] >= 49
    provider.release.set()
    assert manager.wait_idle(5)
    stopped = manager.get(SCENE, OWNER, case["agent_ref"])
    assert stopped["state"] == "STOPPED"
    assert stopped["metrics"]["prompt_tokens"] == 200
    assert not stopped["tool_receipts"] and stopped["answer"] is None
    manager.resume(SCENE, OWNER, case["agent_ref"])
    exhausted = step(manager, case)
    assert exhausted["state"] == "BUDGET_EXHAUSTED"
    assert len(provider.messages) == 1 and not current["calls"]


def test_old_model_cases_remain_readable_but_cannot_advance_resume_or_reply(tmp_path: Path) -> None:
    manager, provider, _ = prepared(tmp_path, [
        {"kind": "clarification", "question": "Which local target?"}])
    ready = manager.start(SCENE, OWNER, "query")
    question = step(manager, manager.start(SCENE, OWNER, "that person"))
    stopped = manager.stop(SCENE, OWNER, ready["agent_ref"])
    provider.identity = lambda: {  # type: ignore[method-assign]
        "provider": "SCRIPTED_TEST_ONLY", "model": "new-model", "model_digest": "e" * 64}
    assert not manager.get(SCENE, OWNER, ready["agent_ref"])["model_version_current"]
    for method, ref in ((manager.advance, stopped["agent_ref"]),
                        (manager.resume, stopped["agent_ref"])):
        with pytest.raises(AgentDenied, match="CASE_MODEL_VERSION_CHANGED"):
            method(SCENE, OWNER, ref)
    with pytest.raises(AgentDenied, match="CASE_MODEL_VERSION_CHANGED"):
        manager.reply(SCENE, OWNER, question["agent_ref"], "now continue")
    assert manager.get(SCENE, OWNER, question["agent_ref"])["state"] == "NEEDS_CLARIFICATION"
    assert manager.get(SCENE, OWNER, stopped["agent_ref"])["state"] == "STOPPED"


@pytest.mark.parametrize(("text", "clarification", "code"), [
    ("Do you want to upload images to an external API?", True,
     "AGENT_UNSUPPORTED_CLARIFICATION"),
    ("Please specify your API key and password", True, "AGENT_UNSUPPORTED_CLARIFICATION"),
    ("請提供外部 API 的金鑰以便上傳影像", True, "AGENT_UNSUPPORTED_CLARIFICATION"),
    ("That is definitely the same person", False, "AGENT_UNSUPPORTED_CLAIM"),
    ("人物身分已確認，姓名是小王。", False, "AGENT_UNSUPPORTED_CLAIM"),
])
def test_unsafe_model_outputs_fail_closed(text: str, clarification: bool, code: str) -> None:
    with pytest.raises(AgentDenied, match=code):
        LocalAgentManager._guard_output(text, clarification=clarification)
    LocalAgentManager._guard_output("The data does not mean identity is confirmed.",
                                   clarification=False)


def test_identical_successful_query_is_paid_feedback_without_reexecution(tmp_path: Path) -> None:
    manager, _, current = prepared(tmp_path, [query(), query()])
    case = manager.start(SCENE, OWNER, "query", time_range=[8, 16])
    case = step(manager, case)
    case = step(manager, case)
    assert case["state"] == "READY" and case["answer"] is None
    assert case["goal"]["requirement_feedback"]["unmet"] == ["QUERY_ALREADY_SUCCEEDED"]
    assert len(current["calls"]) == 1
    assert case["metrics"]["model_call_count"] == 2
    assert case["metrics"]["tool_request_attempt_count"] == 2
    assert case["metrics"]["invalid_action_count"] == 1


def evidence_page(index: int = 0, *, cursor: str | None = None,
                  next_cursor: str | None = None, window: list[float] | None = None,
                  empty: bool = False) -> dict[str, Any]:
    rows = [] if empty else [{"event_ref": "event:" + f"{index + 1:024x}", "kind": "DWELL",
        "candidate_count": index + 2, "complete": True, "uncertainty": "UNKNOWN"}]
    original = {"items": rows, "retrieval": {"truncated": next_cursor is not None,
                                            "next_cursor": next_cursor}}
    receipt = {"receipt_ref": "receipt:" + f"{index + 1:024x}", "tool": "query_events",
        "arguments": {"camera_ref": CAMERA, "time_range": window or [8, 16], "limit": 3},
        "status": "OK", "result": {"data": deepcopy(original),
                                  "presentation_truncated": False},
        "result_sha256": digest(original)}
    if cursor:
        receipt["arguments"]["cursor"] = cursor
    receipt["evidence"] = build_evidence_receipt(receipt, original, binding())
    return receipt


def literal_answer(receipts: list[dict[str, Any]], *, selection: str = "PAGE",
                   requested_fields: list[str] | None = None,
                   selected: list[EvidenceSelection] | None = None) -> dict[str, Any]:
    return verified_answer(binding(), receipts,
        tuple(selected or [EvidenceSelection(receipt_ref=r["receipt_ref"]) for r in receipts]),
        {"request_spec": {"topic": "EVENTS", "selection": selection,
                          "requested_fields": (["kind", "candidate_count"]
                                               if requested_fields is None else requested_fields)},
         "response_language": "en"}, [CAMERA], [8, 16])


@pytest.mark.parametrize("tamper", ["field", "bool_value", "locator", "resource", "data", "mode"])
def test_verified_answer_rejects_every_broken_field_or_receipt_binding(tamper: str) -> None:
    receipt = evidence_page()
    row = receipt["evidence"]["rows"][0]
    if tamper == "field":
        row["fields"]["candidate_count"] = 999
    elif tamper == "bool_value":
        row["fields"]["complete"] = 1
    elif tamper == "locator":
        row["json_locator"] = ["items", 10]
    elif tamper == "resource":
        row["resource_ref"] = EVENT
    elif tamper == "data":
        receipt["result"]["data"]["items"][0]["kind"] = "CONFIRMED"
    else:
        receipt["evidence"]["binding_sha256"] = "0" * 64
    with pytest.raises(AgentDenied, match="AGENT_(?:FACT|EVIDENCE)"):
        literal_answer([receipt])


def test_page_unknown_total_and_exhausted_chain_are_separate_from_event_complete() -> None:
    first = evidence_page(next_cursor="page-two")
    partial = literal_answer([first])
    collection = partial["coverage"]["collections"][0]
    assert partial["rows"][0]["fields"]["complete"] is True
    assert collection["registered_total"] is None and collection["source_truncated"] is True
    assert partial["coverage"]["complete_for_selected_scope"] is False
    assert "UNKNOWN" in partial["text"]
    second = evidence_page(1, cursor="page-two")
    complete = literal_answer([first, second])
    collection = complete["coverage"]["collections"][0]
    assert collection["registered_total"] == 2 and collection["source_truncated"] is False
    assert collection["pages"][0]["source_truncated"] is True
    assert complete["coverage"]["complete_for_selected_scope"] is True
    assert literal_answer([second])["coverage"]["complete_for_selected_scope"] is False


@pytest.mark.parametrize("windows", [[[8, 9]], [[8, 12], [12, 16]], [[8, 11], [12, 16]]])
def test_narrow_disjoint_or_multiple_query_windows_never_claim_locked_scope_complete(
    windows: list[list[float]],
) -> None:
    receipts = [evidence_page(i, window=window) for i, window in enumerate(windows)]
    answer = literal_answer(receipts)
    assert answer["coverage"]["complete_for_selected_scope"] is False
    assert all(c["registered_total"] == 1 for c in answer["coverage"]["collections"])


def test_presentation_row_loss_prevents_registered_total_even_after_cursor_exhaustion() -> None:
    receipt = evidence_page()
    original = deepcopy(receipt["result"]["data"])
    original["items"].append({"event_ref": EVENT, "kind": "DWELL", "candidate_count": 3})
    receipt["result"]["presentation_truncated"] = True
    receipt["evidence"] = build_evidence_receipt(receipt, original, binding())
    answer = literal_answer([receipt])
    assert answer["coverage"]["collections"][0]["cursor_chain_complete"] is True
    assert answer["coverage"]["collections"][0]["presentation_rows_complete"] is False
    assert answer["coverage"]["collections"][0]["registered_total"] is None
    assert answer["coverage"]["complete_for_selected_scope"] is False


def test_empty_exhausted_query_is_verified_zero_and_does_not_claim_person_absence() -> None:
    answer = literal_answer([evidence_page(empty=True)])
    assert answer["rows"] == []
    assert answer["coverage"]["collections"][0]["registered_total"] == 0
    assert answer["coverage"]["complete_for_selected_scope"] is True
    assert "not proof of absence" in answer["text"]
    with pytest.raises(AgentDenied, match="EMPTY_FACTUAL_ANSWER"):
        literal_answer([evidence_page(empty=True, next_cursor="unread")])


def test_unrepresentable_source_row_cannot_be_misreported_as_exhausted_zero() -> None:
    receipt = evidence_page(empty=True)
    original = {"items": [{"unsupported": "not an event"}],
                "retrieval": {"truncated": False, "next_cursor": None}}
    receipt["result"]["data"] = deepcopy(original)
    receipt["evidence"] = build_evidence_receipt(receipt, original, binding())
    with pytest.raises(AgentDenied, match="EMPTY_FACTUAL_ANSWER"):
        literal_answer([receipt])


def test_wrong_topic_missing_fields_and_nonfirst_selection_fail_closed() -> None:
    receipt = evidence_page()
    wrong = deepcopy(receipt)
    wrong["tool"] = "list_cameras"
    with pytest.raises(AgentDenied, match="FACT_TOPIC_MISMATCH"):
        literal_answer([wrong], requested_fields=[])
    with pytest.raises(AgentDenied, match="REQUIRED_FACT_FIELDS_MISSING"):
        literal_answer([receipt], requested_fields=["hypothesis_count"])
    second = evidence_page(1, cursor="page-two")
    with pytest.raises(AgentDenied, match="FIRST_FACT_SELECTION_MISMATCH"):
        literal_answer([receipt, second], selection="FIRST", selected=[EvidenceSelection(
            receipt_ref=second["receipt_ref"])])


def test_legacy_same_model_cases_remain_unverified_and_read_only(tmp_path: Path) -> None:
    manager, _, _ = prepared(tmp_path, [])
    case = manager.start(SCENE, OWNER, "query")
    raw = manager.ledger.load(manager._owner(OWNER), SCENE, case["agent_ref"])
    raw.pop("execution_version")
    raw.update(state="COMPLETED", answer={"text": "historical answer", "citations": []})
    manager.ledger.save(manager._owner(OWNER), raw, raw["revision"])
    old = manager.get(SCENE, OWNER, case["agent_ref"])
    assert old["answer_verification"] == "LEGACY_UNVERIFIED"
    assert old["can_continue"] is False
    with pytest.raises(AgentDenied, match="LEGACY_CASE_READ_ONLY"):
        manager.resume(SCENE, OWNER, case["agent_ref"])


@pytest.mark.parametrize("message", ["請送到外部 API", "Send images to an external API"])
def test_explicit_refusal_is_localized_and_dispatches_no_tools(
    tmp_path: Path, message: str,
) -> None:
    manager, _, current = prepared(tmp_path, [
        {"kind": "refusal", "reason_code": "EXTERNAL_EGRESS"}])
    case = step(manager, manager.start(SCENE, OWNER, message))
    assert case["state"] == "REFUSED" and case["answer"] is None
    assert case["refusal"]["response_language"] == ("zh-Hant" if message.startswith("請") else "en")
    assert case["refusal"]["prior_tool_dispatch_count"] == 0
    assert not current["calls"] and not case["tool_receipts"]


def test_reply_preserves_original_goal_and_language_and_legacy_prose_cannot_complete(
    tmp_path: Path,
) -> None:
    manager, provider, _ = prepared(tmp_path, [
        {"kind": "clarification", "question": "你指哪個局部目標？"}, query(),
        {"kind": "answer", "text": "Here is the summary.", "citations": ["LAST_RECEIPT"]}])
    case = step(manager, manager.start(SCENE, OWNER, "請查那個目標", time_range=[8, 16]))
    scope = case["goal"]["locked_scope"]
    manager.reply(SCENE, OWNER, case["agent_ref"], "local target in this camera")
    case = step(manager, case)
    assert case["goal"]["response_language"] == "zh-Hant"
    assert case["goal"]["original_request"] == "請查那個目標"
    assert case["goal"]["locked_scope"] == scope
    assert "請查那個目標" in provider.messages[-1][0]["content"]
    case = step(manager, case)
    assert case["state"] == "FAILED" and case["answer"] is None
    assert case["error_code"] == "AGENT_TYPED_ANSWER_REQUIRED"


@pytest.mark.parametrize("result", [{"items": []}, {"scope": {"observation_mode": "photos_only"}}])
def test_missing_or_changed_tool_scope_cannot_issue_verified_rows(
    tmp_path: Path, result: dict[str, Any],
) -> None:
    manager, _, _ = prepared(tmp_path, [query()])
    manager.executor = lambda *_: result
    case = step(manager, manager.start(SCENE, OWNER, "query", time_range=[8, 16]))
    assert case["state"] == "FAILED" and case["error_code"] == "AGENT_TOOL_BINDING_CHANGED"
    assert not case["tool_receipts"] and case["answer"] is None


def test_unissued_paging_cursor_is_rejected_before_dispatch(tmp_path: Path) -> None:
    action = query()
    action["arguments"]["cursor"] = "unissued-signed-cursor"
    manager, _, current = prepared(tmp_path, [action])
    case = step(manager, manager.start(SCENE, OWNER, "query", time_range=[8, 16]))
    assert case["error_code"] == "AGENT_CURSOR_NOT_ISSUED" and not current["calls"]


def three_row_receipt() -> dict[str, Any]:
    receipt = evidence_page(next_cursor="unread")
    data = receipt["result"]["data"]
    data["items"].extend(evidence_page(index)["result"]["data"]["items"][0]
                         for index in (1, 2))
    receipt["result_sha256"] = digest(data)
    receipt["evidence"] = build_evidence_receipt(receipt, deepcopy(data), binding())
    return receipt


def test_disjoint_selectors_share_receipt_and_preserve_all_three_original_rows() -> None:
    receipt = three_row_receipt()
    rows = receipt["evidence"]["rows"]
    selections = [EvidenceSelection(receipt_ref=receipt["receipt_ref"],
                                   row_refs=(rows[index]["row_ref"],)) for index in (2, 0, 1)]
    answer = literal_answer([receipt], selected=selections)
    assert answer["rows"] == rows
    assert answer["citations"] == [receipt["receipt_ref"]]
    collection = answer["coverage"]["collections"][0]
    assert collection["returned_count"] == collection["selected_count"] == 3
    assert collection["registered_total"] is None
    assert answer["coverage"]["complete_for_selected_scope"] is False
    assert answer["rows"] == literal_answer([receipt])["rows"]


@pytest.mark.parametrize("indices", [[[0], [0]], [[0, 0]], [[], [1]]])
def test_same_receipt_repeated_or_overlapping_rows_remain_rejected(
    indices: list[list[int]],
) -> None:
    receipt = three_row_receipt()
    rows = receipt["evidence"]["rows"]
    selections = [EvidenceSelection(receipt_ref=receipt["receipt_ref"],
        row_refs=tuple(rows[index]["row_ref"] for index in group)) for group in indices]
    with pytest.raises(AgentDenied, match="DUPLICATE_FACT_SELECTION"):
        literal_answer([receipt], selected=selections)


def test_summary_detail_duplicate_resource_remains_rejected() -> None:
    summary = evidence_page()
    detail = {"receipt_ref": "receipt:detail", "tool": "get_event_detail",
        "arguments": {"event_ref": summary["result"]["data"]["items"][0]["event_ref"]},
        "status": "OK", "result": {"data": deepcopy(summary["result"]["data"]["items"][0]),
                                  "presentation_truncated": False}}
    detail["evidence"] = build_evidence_receipt(detail, detail["result"]["data"], binding())
    with pytest.raises(AgentDenied, match="DUPLICATE_FACT_SELECTION"):
        literal_answer([summary, detail])


def test_selector_order_cannot_reverse_original_page_receipt_order() -> None:
    first = evidence_page(next_cursor="page-two")
    second = evidence_page(1, cursor="page-two")
    answer = literal_answer([first, second], selected=[
        EvidenceSelection(receipt_ref=second["receipt_ref"]),
        EvidenceSelection(receipt_ref=first["receipt_ref"])])
    assert answer["citations"] == [first["receipt_ref"], second["receipt_ref"]]
    assert [row["resource_ref"] for row in answer["rows"]] == [
        receipt["evidence"]["rows"][0]["resource_ref"] for receipt in (first, second)]


@pytest.mark.parametrize(("message", "first", "detail", "pages", "all_rows"), [
    ("Read the first page.", False, False, 1, False),
    ("Read the first event detail.", True, True, None, False),
    ("讀第一頁，再讀第一個事件的詳細。", True, True, 1, False),
    ("Read first page, not first event.", False, False, 1, False),
    ("Do not read detail; read first page.", False, False, 1, False),
    ("不要讀詳細，查第一頁。", False, False, 1, False),
    ("Do not claim all events are known; read one page.", False, False, 1, False),
    ("Do not read all pages.", False, False, None, False),
    ("List all registered events.", False, False, None, True),
    ("Read two pages, keep UNKNOWN.", False, False, 2, False),
    ("查兩頁並保留 UNKNOWN。", False, False, 2, False),
    ("Do not read the first page.", False, False, None, False),
])
def test_explicit_requirements_separate_target_evidence_page_and_negation(
    message: str, first: bool, detail: bool, pages: int | None, all_rows: bool,
) -> None:
    requirement = derive_requirements(message, [])
    assert requirement.first_event is first
    assert requirement.event_detail is detail
    assert requirement.page_count == pages
    assert requirement.whole_collection is all_rows


def test_literal_field_lists_not_ordinary_words_and_trusted_reply_resolution() -> None:
    assert derive_requirements("Be kind and complete the task.", []).requested_fields == ()
    requirement = derive_requirements("Read fields: kind, candidate_count, complete.", [])
    assert set(requirement.requested_fields) == {"kind", "candidate_count", "complete"}
    assert derive_requirements("Explain `uncertainty`.", []).requested_fields == ("uncertainty",)
    conflict = derive_requirements("Read detail; do not read detail.", [])
    assert conflict.ambiguous_dimensions == ("event_detail",)
    clarified = derive_requirements("Read detail; do not read detail.", ["Read event detail."])
    assert clarified.ambiguous_dimensions == () and clarified.event_detail is True
    assert clarified.request_sha256 != conflict.request_sha256


def test_initial_weak_goal_is_unlocked_and_charged_then_model_can_correct(tmp_path: Path) -> None:
    corrected = query()
    corrected["goal"]["selection"] = "FIRST"
    manager, _, current = prepared(tmp_path, [query(), corrected])
    case = step(manager, manager.start(SCENE, OWNER, "Read first event detail.",
                                       time_range=[8, 16]))
    assert case["state"] == "READY" and case["answer"] is None
    assert case["goal"]["request_spec"] is None and not current["calls"]
    assert case["metrics"]["invalid_action_count"] == 1
    assert (case["metrics"]["model_call_count"] ==
            case["metrics"]["model_request_attempt_count"] == 1)
    assert case["metrics"]["prompt_tokens"] == 100
    assert case["goal"]["requirement_feedback"]["unmet"] == ["FIRST_EVENT_FINAL_GOAL_REQUIRED"]
    case = step(manager, case)
    assert case["goal"]["request_spec"]["selection"] == "FIRST"
    assert len(current["calls"]) == 1


def test_explicit_field_downgrade_is_recoverable_before_any_dispatch(tmp_path: Path) -> None:
    manager, _, current = prepared(tmp_path, [query()])
    case = step(manager, manager.start(SCENE, OWNER, "Read `uncertainty`.", time_range=[8, 16]))
    assert case["state"] == "READY" and not current["calls"]
    assert case["goal"]["request_spec"] is None
    assert case["goal"]["requirement_feedback"]["unmet"] == ["REQUESTED_LITERAL_FIELDS_REQUIRED"]


def test_correct_scalar_summary_needs_detail_and_model_selects_recovery_tool(
    tmp_path: Path,
) -> None:
    first = query()
    first["goal"]["selection"] = "FIRST"
    detail = {"kind": "tool", "tool": "get_event_detail", "arguments": {"event_ref": EVENT}}
    manager, _, current = prepared(tmp_path, [first, answer(), detail, answer()])
    original = manager.executor

    def execute(owner: str, scope: AgentBinding, tool: str,
                params: dict[str, Any]) -> dict[str, Any]:
        result = original(owner, scope, tool, params)
        if tool == "get_event_detail":
            return {"scope": result["scope"], **result["items"][0]}
        return result

    manager.executor = execute
    case = manager.start(SCENE, OWNER, "Read first event detail with candidate_count.",
                         time_range=[8, 16])
    case = step(manager, case)
    case = step(manager, case)
    assert case["state"] == "READY" and case["answer"] is None
    assert case["goal"]["requirement_feedback"]["unmet"] == ["DETAIL_EVIDENCE_RECEIPT_REQUIRED"]
    assert case["metrics"]["invalid_action_count"] == 1
    case = step(manager, step(manager, case))
    assert case["state"] == "COMPLETED" and len(case["answer"]["rows"]) == 1
    assert [tool for tool, _ in current["calls"]] == ["query_events", "get_event_detail"]
    assert case["answer"]["rows"][0]["json_locator"] == []
    assert case["goal_completion_verification"] == "EXPLICIT_REQUEST_CONSTRAINTS_VERIFIED"
    assert case["metrics"]["model_call_count"] == 4
    assert case["metrics"]["prompt_tokens"] == 400


def test_feedback_cannot_reset_model_budget_through_stop_resume(tmp_path: Path) -> None:
    manager, _, current = prepared(tmp_path, [query(), query()],
                                   policy=AgentPolicy(max_model_calls=2))
    case = step(manager, manager.start(SCENE, OWNER, "Read first event detail.",
                                       time_range=[8, 16]))
    manager.stop(SCENE, OWNER, case["agent_ref"])
    manager.resume(SCENE, OWNER, case["agent_ref"])
    case = step(manager, case)
    assert case["state"] == "BUDGET_EXHAUSTED"
    assert case["metrics"]["invalid_action_count"] == 2
    assert case["metrics"]["model_request_attempt_count"] == 2
    assert case["metrics"]["prompt_tokens"] == 200 and not current["calls"]


def test_security_failure_is_terminal_even_with_unsatisfied_goal(tmp_path: Path) -> None:
    bad = query() | {"tool": "shell"}
    manager, _, _ = prepared(tmp_path, [bad])
    case = step(manager, manager.start(SCENE, OWNER, "Read first event detail.",
                                       time_range=[8, 16]))
    assert case["state"] == "FAILED" and case["error_code"] == "AGENT_TOOL_DENIED"
    assert case["goal"]["requirement_feedback"] is None


def test_v2_literal_verified_history_is_read_only_and_goal_not_checked(tmp_path: Path) -> None:
    manager, _, _ = prepared(tmp_path, [query(), answer()])
    case = step(manager, step(manager, manager.start(SCENE, OWNER, "query", time_range=[8, 16])))
    raw = manager.ledger.load(manager._owner(OWNER), SCENE, case["agent_ref"])
    raw["execution_version"] = "typed.evidence.v2"
    manager.ledger.save(manager._owner(OWNER), raw, raw["revision"])
    old = manager.get(SCENE, OWNER, case["agent_ref"])
    assert old["answer_verification"] == "VERIFIED_DTO_FIELDS"
    assert old["goal_completion_verification"] == "NOT_CHECKED" and old["can_continue"] is False
    assert old["execution_compatibility"] == "READ_ONLY_PRIOR_EXECUTION_VERSION"
    with pytest.raises(AgentDenied, match="LEGACY_CASE_READ_ONLY"):
        manager.resume(SCENE, OWNER, case["agent_ref"])


def test_explicit_two_pages_requires_both_chains_and_all_read_rows() -> None:
    requirements = derive_requirements("Read two pages with fields: kind, candidate_count.", [])
    first = evidence_page(next_cursor="page-two")
    partial = literal_answer([first])
    with pytest.raises(RequirementFeedback, match="EXPLICIT_REQUIREMENTS_UNMET"):
        validate_completion(requirements, partial, [first])
    second = evidence_page(1, cursor="page-two", next_cursor="page-three")
    full_requested = literal_answer([first, second])
    proof = validate_completion(requirements, full_requested, [first, second])
    assert proof["status"] == "EXPLICIT_REQUEST_CONSTRAINTS_VERIFIED"
    assert full_requested["coverage"]["complete_for_selected_scope"] is False
    assert full_requested["coverage"]["collections"][0]["registered_total"] is None
    subset = literal_answer([first, second], selected=[
        EvidenceSelection(receipt_ref=first["receipt_ref"])])
    with pytest.raises(RequirementFeedback):
        validate_completion(requirements, subset, [first, second])


def test_empty_exhausted_query_and_positive_all_do_not_create_detail_reference() -> None:
    zero = literal_answer([evidence_page(empty=True)])
    assert validate_completion(derive_requirements("Read first event detail.", []), zero,
                               [evidence_page(empty=True)])["status"]
    partial_receipt = evidence_page(next_cursor="unread")
    with pytest.raises(RequirementFeedback):
        validate_completion(derive_requirements("Read all events.", []),
                            literal_answer([partial_receipt]), [partial_receipt])


def test_conflicting_original_request_requires_human_clarification() -> None:
    requirements = derive_requirements("Read detail; do not read detail.", [])
    with pytest.raises(RequirementFeedback):
        validate_proposal(requirements, RequestGoal(topic="EVENTS", selection="PAGE"))


def test_unrelated_negation_and_sentence_boundary_preserve_positive_read() -> None:
    requirements = derive_requirements(
        "Do not infer identities. Read first event detail without translating candidate_count; "
        "list fields: kind, candidate_count, complete.", [])
    assert requirements.first_event and requirements.event_detail
    assert set(requirements.requested_fields) == {"kind", "candidate_count", "complete"}
    assert not requirements.ambiguous_dimensions
    assert derive_requirements("candidate_count is a source label.", []).requested_fields == ()
    negative = derive_requirements("Do not include candidate_count, hypothesis_count.", [])
    assert not negative.requested_fields and not negative.ambiguous_dimensions


def test_conflicting_fields_are_not_silently_dropped_or_resolved_by_unrelated_reply() -> None:
    original = "Read fields: kind, candidate_count; do not include candidate_count."
    conflict = derive_requirements(original, [])
    assert conflict.ambiguous_dimensions == ("requested_fields",)
    assert set(conflict.requested_fields) == {"kind", "candidate_count"}
    unrelated = derive_requirements(original, ["Keep fields: complete."])
    assert unrelated.ambiguous_dimensions == ("requested_fields",)
    resolved = derive_requirements(original, ["Include candidate_count."])
    assert not resolved.ambiguous_dimensions
    assert set(resolved.requested_fields) == {"kind", "candidate_count"}


@pytest.mark.parametrize(("message", "size", "ambiguous"), [
    ("Read first page (limit=3).", 3, False),
    ("Read two pages, page_size: 5.", 5, False),
    ("讀第一頁，每頁 4 筆。", 4, False),
    ("Read first page limit=0.", None, True),
    ("Read first page limit=13.", None, True),
    ("Read first page limit=-1.", None, True),
    ("Read first page limit=3 or limit=5.", None, True),
    ("Read first page limit=13, then limit=3.", None, True),
])
def test_explicit_page_size_is_bounded_and_conflicts_require_clarification(
    message: str, size: int | None, ambiguous: bool,
) -> None:
    requirements = derive_requirements(message, [])
    assert requirements.page_size == size
    assert ("page_size" in requirements.ambiguous_dimensions) is ambiguous
    if ambiguous:
        resolved = derive_requirements(message, ["Use limit=4."])
        assert resolved.page_size == 4 and "page_size" not in resolved.ambiguous_dimensions


def test_wrong_explicit_limit_is_recoverable_before_dispatch(tmp_path: Path) -> None:
    wrong = query()
    wrong["arguments"]["limit"] = 2
    manager, _, current = prepared(tmp_path, [wrong, query()])
    case = step(manager, manager.start(SCENE, OWNER, "Read first page limit=3.",
                                       time_range=[8, 16]))
    assert case["state"] == "READY" and case["goal"]["request_spec"] is None
    assert not current["calls"] and case["metrics"]["prompt_tokens"] == 100
    assert case["goal"]["requirement_feedback"]["unmet"] == ["REQUESTED_PAGE_SIZE_REQUIRED"]
    case = step(manager, case)
    assert len(current["calls"]) == 1 and current["calls"][0][1]["limit"] == 3


@pytest.mark.parametrize("fault", ["orphan", "gap", "out_of_order", "wrong_limit"])
def test_requested_page_prefix_rejects_disjoint_or_changed_pages(fault: str) -> None:
    first = evidence_page(next_cursor="page-two")
    second = evidence_page(1, cursor="page-two", next_cursor="page-three")
    receipts = [first, second]
    if fault == "orphan":
        first["arguments"]["cursor"] = "orphan-root"
    elif fault == "gap":
        second["arguments"]["cursor"] = "another-issued-cursor"
    elif fault == "out_of_order":
        receipts.reverse()
    else:
        second["arguments"]["limit"] = 2
    result = literal_answer(receipts)
    with pytest.raises(RequirementFeedback):
        validate_completion(derive_requirements("Read two pages limit=3.", []), result, receipts)


def test_first_selection_uses_exact_scope_root_not_previous_narrow_query() -> None:
    narrow = evidence_page(window=[8, 9])
    scoped = evidence_page(1, next_cursor="unread")
    result = literal_answer([narrow, scoped], selection="FIRST", selected=[
        EvidenceSelection(receipt_ref=scoped["receipt_ref"])])
    assert validate_completion(derive_requirements("Read first event.", []), result,
                               [narrow, scoped])["status"]
    orphan = evidence_page(cursor="orphan")
    with pytest.raises(AgentDenied, match="FIRST_FACT_SELECTION_MISMATCH"):
        literal_answer([orphan], selection="FIRST")


def test_exhausted_empty_first_request_can_complete_without_inventing_target() -> None:
    receipt = evidence_page(empty=True)
    result = literal_answer([receipt], selection="FIRST")
    assert not result["rows"]
    requirements = derive_requirements("Read first page limit=3 then first event detail.", [])
    assert validate_completion(requirements, result, [receipt])["status"]


def test_trusted_clarification_amends_minimum_but_keeps_locked_scope_and_accounting(
    tmp_path: Path,
) -> None:
    manager, _, current = prepared(tmp_path, [query(),
        {"kind": "clarification", "question": "Should I read event detail?"}, query(), answer()])
    original = "Read event detail; do not read event detail."
    case = manager.start(SCENE, OWNER, original, time_range=[8, 16])
    locked = deepcopy(case["goal"]["locked_scope"])
    case = step(manager, case)
    assert case["state"] == "READY" and not current["calls"]
    case = step(manager, case)
    assert case["state"] == "NEEDS_CLARIFICATION"
    reply = "Do not read event detail; read first page limit=3."
    case = manager.reply(SCENE, OWNER, case["agent_ref"], reply)
    assert case["goal"]["original_request"] == original
    assert case["goal"]["clarification_replies"] == [reply]
    assert case["goal"]["locked_scope"] == locked and case["goal"]["response_language"] == "en"
    assert case["metrics"]["model_call_count"] == 2
    assert case["goal"]["request_spec"] is None
    case = step(manager, step(manager, case))
    assert case["state"] == "COMPLETED"
    assert case["answer"]["coverage"]["complete_for_selected_scope"] is False
    assert case["answer"]["coverage"]["collections"][0]["registered_total"] is None
    assert case["metrics"]["model_call_count"] == 4
    assert case["metrics"]["prompt_tokens"] == 400
    assert len(current["calls"]) == 1


@pytest.mark.parametrize("message", [
    "Explain the first returned record in full.",
    "Provide details for the first listed item.",
    "Give the first matching result's details.",
    "Tell me the details of the head entry.",
    "Open the full record for the first source-ordered event.",
    "Show the first entry's expanded record.",
    "Explain the first returned record.",
    "Give a detailed explanation of the first item.",
    "Expand the first event.",
    "請說明第一筆回傳的事件詳細。",
    "提供首筆記錄的細節。",
    "查第一項結果的完整記錄。",
    "說明第一筆事件。",
])
def test_general_first_resource_detail_phrase_variants_have_independent_obligations(
    message: str,
) -> None:
    req = derive_requirements(message, [])
    assert req.first_event and req.event_detail and not req.ambiguous_dimensions
    with pytest.raises(RequirementFeedback):
        validate_proposal(req, RequestGoal(topic="EVENTS", selection="PAGE"))
    validate_proposal(req, RequestGoal(topic="EVENTS", selection="FIRST"))


@pytest.mark.parametrize("message", [
    "Read first page, do not open event details.",
    "Show first page without event details.",
    "不要開事件細節，查第一頁。",
    "Read fields: kind, candidate_count, complete; do not read details.",
])
def test_first_page_and_negative_detail_are_not_first_resource_detail(message: str) -> None:
    req = derive_requirements(message, [])
    assert not req.first_event and not req.event_detail and not req.ambiguous_dimensions


def test_field_identifiers_and_unrelated_negation_do_not_change_target_contract() -> None:
    req = derive_requirements(
        "Do not infer identities. Describe first record details "
        "without translating candidate_count.",
        [])
    assert req.first_event and req.event_detail and req.requested_fields == ("candidate_count",)
    req = derive_requirements("Read fields: event_ref, complete; keep `kind`.", [])
    assert not req.first_event and not req.event_detail
    assert set(req.requested_fields) == {"event_ref", "complete", "kind"}
    assert not derive_requirements("Read the fields from the source.", []).ambiguous_dimensions


@pytest.mark.parametrize("message", [
    "Read the first one's details.", "Read earliest event details.",
    "Show top-ranked entry details.", "請展開第一筆的細節。",
])
def test_unclear_resource_or_order_requires_clarification_without_guessing(message: str) -> None:
    req = derive_requirements(message, [])
    assert "first_resource_or_order" in req.ambiguous_dimensions
    with pytest.raises(RequirementFeedback):
        validate_proposal(req, RequestGoal(topic="EVENTS", selection="PAGE"))
    amended = derive_requirements(message, ["Read the first returned event detail."])
    assert amended.first_event and amended.event_detail and not amended.ambiguous_dimensions


def test_contradictory_general_detail_phrases_and_unsupported_literals_fail_closed() -> None:
    req = derive_requirements("Describe the full record; do not open the full record.", [])
    assert "event_detail" in req.ambiguous_dimensions
    amended = derive_requirements("Describe the full record; do not open the full record.",
                                   ["Please provide event details."])
    assert amended.event_detail and not amended.ambiguous_dimensions
    req = derive_requirements("Read fields: kind, unavailable_field.", [])
    assert req.unsupported_literal_fields == ("unavailable_field",)
    with pytest.raises(RequirementFeedback):
        validate_proposal(req, RequestGoal(topic="EVENTS", selection="PAGE"))
    amended = derive_requirements("Read fields: kind, unavailable_field.",
                                   ["Do not include unavailable_field."])
    assert not amended.ambiguous_dimensions and amended.requested_fields == ("kind",)


def detail_receipt(summary: dict[str, Any]) -> dict[str, Any]:
    row = deepcopy(summary["result"]["data"]["items"][0])
    receipt = {"receipt_ref": "receipt:detail", "tool": "get_event_detail", "status": "OK",
        "arguments": {"event_ref": row["event_ref"]},
        "result": {"data": row, "presentation_truncated": False}, "result_sha256": digest(row)}
    receipt["evidence"] = build_evidence_receipt(receipt, row, binding())
    return receipt


def test_read_detail_tool_is_not_enough_final_fields_must_use_detail_receipt() -> None:
    summary = evidence_page(next_cursor="unread")
    detail = detail_receipt(summary)
    receipts = [summary, detail]
    query_selected = literal_answer(receipts, selection="FIRST", selected=[
        EvidenceSelection(receipt_ref=summary["receipt_ref"])])
    req = derive_requirements("Explain first returned record in full.", [])
    with pytest.raises(RequirementFeedback) as error:
        validate_completion(req, query_selected, receipts)
    assert error.value.unmet == ("DETAIL_EVIDENCE_RECEIPT_REQUIRED",)
    selected = literal_answer(receipts, selection="FIRST", selected=[
        EvidenceSelection(receipt_ref=detail["receipt_ref"])])
    assert validate_completion(req, selected, receipts)["status"]
    assert selected["rows"][0]["source_payload_sha256"] == digest(detail["result"]["data"])
    with pytest.raises(AgentDenied, match="DETAIL_FACT_SOURCE_REQUIRED"):
        literal_answer(receipts, selection="DETAIL", selected=[
            EvidenceSelection(receipt_ref=summary["receipt_ref"])])


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(("fault", "expected"), [
    ("row", "FACT_ROW_NOT_ISSUED"), ("receipt", "UNGROUNDED_CITATION"),
    ("status", "UNGROUNDED_CITATION"), ("topic", "FACT_TOPIC_MISMATCH"),
    ("binding", "EVIDENCE_BINDING_CHANGED"), ("field", "FACT_FIELD_MISMATCH"),
    ("private_payload", "EVIDENCE_PAYLOAD_CHANGED"),
])
def test_duplicate_never_masks_any_later_security_or_authority_failure(
    fault: str, expected: str, reverse: bool,
) -> None:
    first, bad = evidence_page(), evidence_page(1)
    duplicate = [EvidenceSelection(receipt_ref=first["receipt_ref"])] * 2
    unsafe = EvidenceSelection(receipt_ref=bad["receipt_ref"])
    if fault == "row":
        unsafe = EvidenceSelection(receipt_ref=bad["receipt_ref"],
                                   row_refs=("factrow:" + "0" * 24,))
    elif fault == "receipt":
        unsafe = EvidenceSelection(receipt_ref="receipt:unissued")
    elif fault == "status":
        bad["status"] = "ERROR"
    elif fault == "topic":
        bad["tool"] = "list_cameras"
    elif fault == "binding":
        bad["evidence"]["binding_sha256"] = "0" * 64
    elif fault == "field":
        bad["evidence"]["rows"][0]["fields"]["candidate_count"] = 987
    else:
        bad["result"]["data"]["ground_truth"] = "PRIVATE_TEST_ONLY"
    selections = [unsafe, *duplicate] if reverse else [*duplicate, unsafe]
    with pytest.raises(AgentDenied, match=expected):
        literal_answer([first, bad], selected=selections)


def duplicate_first_answer(provider: ScriptProvider) -> None:
    original = provider.complete
    used = False

    def complete(*args: Any, **kwargs: Any) -> ModelCompletion:
        nonlocal used
        result = original(*args, **kwargs)
        if result.action and result.action.kind == "answer" and not used:
            used = True
            action = result.action.model_dump(mode="json")
            action["selections"] *= 2
            return replace(result, action=ModelAction.model_validate(action))
        return result

    provider.complete = complete  # type: ignore[method-assign]


def test_validated_duplicate_is_rejected_with_charged_feedback_then_model_reselects(
    tmp_path: Path,
) -> None:
    manager, provider, _ = prepared(tmp_path, [query(), answer(), answer()])
    duplicate_first_answer(provider)
    case = manager.start(SCENE, OWNER, "Read first page.", time_range=[8, 16])
    case = step(manager, step(manager, case))
    assert case["state"] == "READY" and case["answer"] is None
    assert case["goal"]["requirement_feedback"]["unmet"] == ["AGENT_DUPLICATE_FACT_SELECTION"]
    assert case["metrics"]["invalid_action_count"] == 1
    assert case["metrics"]["prompt_tokens"] == 200 and case["metrics"]["tool_call_count"] == 1
    case = step(manager, case)
    assert case["state"] == "COMPLETED" and case["metrics"]["prompt_tokens"] == 300
    assert len(case["answer"]["rows"]) == 1


def test_duplicate_feedback_cannot_reset_budget_by_stop_resume(tmp_path: Path) -> None:
    manager, provider, _ = prepared(tmp_path, [query(), answer(), answer()],
                                   policy=AgentPolicy(max_model_calls=2))
    duplicate_first_answer(provider)
    case = step(manager, step(manager,
        manager.start(SCENE, OWNER, "Read first page.", time_range=[8, 16])))
    assert case["state"] == "BUDGET_EXHAUSTED" and case["answer"] is None
    assert case["metrics"]["prompt_tokens"] == 200
    manager.stop(SCENE, OWNER, case["agent_ref"])
    with pytest.raises(AgentDenied):
        manager.resume(SCENE, OWNER, case["agent_ref"])


def test_old_v3_literal_and_explicit_proof_remain_read_only_under_new_guard(tmp_path: Path) -> None:
    manager, _, _ = prepared(tmp_path, [query(), answer()])
    case = step(manager, step(manager, manager.start(SCENE, OWNER, "query", time_range=[8, 16])))
    raw = manager.ledger.load(manager._owner(OWNER), SCENE, case["agent_ref"])
    answer_hash = digest(raw["answer"])
    raw["execution_version"] = "typed.evidence.v3"
    manager.ledger.save(manager._owner(OWNER), raw, raw["revision"])
    old = manager.get(SCENE, OWNER, case["agent_ref"])
    assert old["answer_verification"] == "VERIFIED_DTO_FIELDS"
    assert digest(old["answer"]) == answer_hash
    assert old["goal_completion_verification"] == "NOT_CHECKED" and not old["can_continue"]
    for method in (manager.advance, manager.resume):
        with pytest.raises(AgentDenied, match="LEGACY_CASE_READ_ONLY"):
            method(SCENE, OWNER, case["agent_ref"])


@pytest.mark.parametrize(("message", "pages", "size"), [
    ("Read first page, continue its cursor, list both two pages; 4 items per page.", 2, 4),
    ("Read first page, then read two pages total; keep UNKNOWN or alternatives.", 2, None),
    ("先讀第一頁，接續游標，再列出這兩頁；每頁 5 筆。", 2, 5),
    ("先讀第一頁，再列出前兩頁；保留 UNKNOWN 或替代解，每頁最多四筆。", 2, 4),
    ("Read first page only, page size is five.", 1, 5),
    ("Read two pages total, do not claim all events are known.", 2, None),
    ("Read sixteen pages.", 16, None),
    ("讀十六頁。", 16, None),
    ("Read first page, limit of twelve.", 1, 12),
])
def test_overall_page_cardinality_overrides_ordinal_root_step_without_global_or_conflict(
    message: str, pages: int, size: int | None,
) -> None:
    req = derive_requirements(message, [])
    assert req.page_count == pages and req.page_size == size
    assert not req.ambiguous_dimensions and not req.first_event and not req.whole_collection


@pytest.mark.parametrize("message", [
    "Read two or three pages.", "Read two pages; read three pages total.",
    "Read first page or two pages.", "讀兩頁或三頁。", "讀兩頁；總共讀三頁。",
    "Read seventeen pages.", "讀十七頁。", "Read first page limit thirteen.",
])
def test_genuine_cardinality_choices_conflicts_or_unsupported_counts_need_clarification(
    message: str,
) -> None:
    req = derive_requirements(message, [])
    assert req.ambiguous_dimensions
    with pytest.raises(RequirementFeedback):
        validate_proposal(req, RequestGoal(topic="EVENTS", selection="PAGE"))


def test_default_live_budgets_remain_unchanged() -> None:
    policy = AgentPolicy()
    assert (policy.max_model_calls, policy.max_tool_calls, policy.max_total_tokens,
            policy.max_elapsed_seconds) == (12, 8, 24000, 300)


def test_ambiguous_person_reply_can_narrow_to_public_events_without_losing_audit_or_locale(
    tmp_path: Path,
) -> None:
    original = "請查那個人剛才的活動。"
    reply = "Only registered public events, first page, fields: kind, candidate_count. No identity."
    manager, provider, _ = prepared(tmp_path, [
        {"kind": "clarification", "question": "你要哪種局部資料？"}, query(), answer()])
    case = step(manager, manager.start(SCENE, OWNER, original, time_range=[8, 16]))
    scope = deepcopy(case["goal"]["locked_scope"])
    case = manager.reply(SCENE, OWNER, case["agent_ref"], reply)
    refinement = case["goal"]["public_fact_refinement"]
    assert refinement["status"] == "HUMAN_NARROWED_PUBLIC_EVENT_FACTS"
    assert refinement["request"] == reply and refinement["reply_sha256"] == digest(reply)
    assert refinement["source_scope_changed"] is False
    assert case["goal"]["original_request"] == original
    assert case["goal"]["clarification_replies"] == [reply]
    assert case["goal"]["response_language"] == "zh-Hant" and case["goal"]["locked_scope"] == scope
    case = step(manager, step(manager, case))
    assert case["state"] == "COMPLETED"
    assert case["metrics"]["model_call_count"] == 3
    reminder = provider.messages[-1][-1]["content"]
    assert reply in reminder and original in reminder
    assert "authorized_clarification_replies" in reminder
    assert case["goal"]["explicit_requirements"]["request_sha256"] == digest({
        "original": original, "replies": [reply]})


@pytest.mark.parametrize(("original", "reply"), [
    ("Who is this person?", "Only registered event facts; confirm identity too."),
    ("Read private sources.", "Only registered event facts."),
    ("Who is this person?",
     "Only registered event facts. Do not read private data. Identify them."),
    ("請確認這個人的身分。", "只列已註冊事件，仍要確認身分。"),
])
def test_public_narrowing_never_hides_persisting_private_or_identity_request(
    original: str, reply: str,
) -> None:
    assert public_fact_refinement(original, [reply]) is None


def test_explicit_human_withdrawal_can_resolve_identity_intent_audit_remains() -> None:
    reply = "Drop identity request; only registered event facts, fields: kind."
    result = public_fact_refinement("Who is this person?", [reply])
    assert result and result["original_retained_for_audit"]
    assert result["request"] == reply and result["reply_sha256"] == digest(reply)


def test_full_reply_history_sensitive_intent_cannot_be_hidden_by_later_fact_only_reply() -> None:
    assert public_fact_refinement("Read source events.", ["Read private sources.",
        "Only registered event facts."]) is None
    assert public_fact_refinement("Read source events.", ["Identify them.",
        "Only registered event facts."]) is None
    assert public_fact_refinement("Read source events.", ["Read private sources.",
        "Drop private request; only registered event facts."])
    for phrase in ("tell me who they are", "who are they", "confirm identity too"):
        assert public_fact_refinement("Who is this person?", [
            "Cancel identity request; only registered public events, " + phrase + "."]) is None
    assert public_fact_refinement("Read private sources and identify them.", [
        "Drop identity request; only registered event facts."]) is None
    assert public_fact_refinement("Read source events.", [
        "Read private sources; cancel private request; only registered event facts."])
    assert public_fact_refinement("Read source events.", [
        "Cancel private request; read private sources; only registered event facts."]) is None
    assert public_fact_refinement("Read private sources.", [
        "Do not cancel private request; only registered event facts."]) is None
    assert public_fact_refinement("讀私有來源。", [
        "不要取消私有要求，只列公開事件。 "]) is None
    assert public_fact_refinement("Identify them.", [
        "Do not withdraw identity request; only registered event facts."]) is None


def test_known_target_after_reply_gets_bounded_feedback_then_model_chooses_tools(
    tmp_path: Path,
) -> None:
    manager, provider, _ = prepared(tmp_path, [
        {"kind": "clarification", "question": "Which local target?", "missing_slots": ["target"]},
        {"kind": "clarification", "question": "Which target?", "missing_slots": ["target"]},
        query(), answer()])
    case = step(manager, manager.start(SCENE, OWNER, "Read that person's activity.",
                                       time_range=[8, 16]))
    case = manager.reply(SCENE, OWNER, case["agent_ref"],
        "Only registered event facts, first page, fields: kind, candidate_count. No identity.")
    case = step(manager, case)
    assert case["state"] == "READY" and case["question"] is None and case["answer"] is None
    assert case["goal"]["requirement_feedback"]["unmet"] == [
        "CLARIFICATION_NOT_REQUIRED", "KNOWN_SLOT_TARGET"]
    assert case["metrics"]["prompt_tokens"] == 200
    assert case["metrics"]["invalid_action_count"] == 1
    case = step(manager, step(manager, case))
    assert case["state"] == "COMPLETED" and case["metrics"]["model_call_count"] == 4
    assert len(provider.messages) == 4 and case["metrics"]["tool_call_count"] == 1


def test_redundant_clarification_feedback_cannot_bypass_model_budget(tmp_path: Path) -> None:
    actions = [{"kind": "clarification", "question": "Which target?", "missing_slots": ["target"]}]
    manager, _, _ = prepared(tmp_path, actions, policy=AgentPolicy(max_model_calls=1))
    case = step(manager, manager.start(SCENE, OWNER, "Read first event detail.",
                                       time_range=[8, 16]))
    assert case["state"] == "BUDGET_EXHAUSTED" and case["question"] is None
    assert case["metrics"]["model_call_count"] == 1 and case["metrics"]["prompt_tokens"] == 100


@pytest.mark.parametrize(("message", "slot"), [
    ("Read fields: kind; do not include kind.", "requested_facts"),
    ("Read first event details or top-ranked entry details.", "target"),
    ("Read fields: kind, unavailable_field.", "requested_facts"),
])
def test_necessary_clarification_is_not_blocked_by_partly_known_ambiguous_requirements(
    tmp_path: Path, message: str, slot: str,
) -> None:
    manager, _, _ = prepared(tmp_path, [{"kind": "clarification", "question": "Please clarify?",
                                       "missing_slots": [slot]}])
    case = step(manager, manager.start(SCENE, OWNER, message, time_range=[8, 16]))
    assert case["state"] == "NEEDS_CLARIFICATION" and case["question"] == "Please clarify?"
    assert case["goal"]["requirement_feedback"] is None
    assert case["metrics"]["model_call_count"] == 1



def continuation_query() -> dict[str, Any]:
    action = query()
    action.pop("goal")
    action["arguments"]["cursor"] = "NEXT_ISSUED_CURSOR"
    return action


def paging_prepared(tmp_path: Path, actions: list[dict[str, Any]], *,
                    policy: AgentPolicy | None = None
                    ) -> tuple[LocalAgentManager, ScriptProvider, Any]:
    manager, provider, current = prepared(tmp_path, actions, policy=policy)
    original_complete = provider.complete

    def complete(messages: list[dict[str, str]], **kwargs: Any) -> ModelCompletion:
        receipts = [json.loads(m["content"].split("\n", 1)[1]) for m in messages
                    if m["content"].startswith("UNTRUSTED TOOL DATA")]
        action = provider.actions[0]
        if action.get("arguments", {}).get("cursor") == "NEXT_ISSUED_CURSOR":
            action["arguments"]["cursor"] = receipts[-1]["result"]["data"][
                "retrieval"]["next_cursor"]
        if action.get("selections", [{}])[0].get("receipt_ref") == "ALL_QUERY_RECEIPTS":
            action["selections"] = [{"receipt_ref": r["receipt_ref"], "row_refs": []}
                                    for r in receipts if r["tool"] == "query_events"]
        return original_complete(messages, **kwargs)

    def execute(owner: str, scope: AgentBinding, tool: str, params: dict[str, Any]
                ) -> dict[str, Any]:
        assert owner == OWNER
        current["calls"].append((tool, deepcopy(params)))
        index = 1 if params.get("cursor") else 0
        data = evidence_page(index, next_cursor=None if index else "fixture-signed-next")[
            "result"]["data"]
        return {"scope": scope.model_dump(mode="json"), **data}

    provider.complete = complete  # type: ignore[method-assign]
    manager.executor = execute
    return manager, provider, current


def test_query_feedback_then_fixture_chooses_issued_continuation_and_all_literal_pages(
    tmp_path: Path,
) -> None:
    manager, _, current = paging_prepared(tmp_path, [query(), query(), continuation_query(),
                                                    answer("ALL_QUERY_RECEIPTS")])
    case = manager.start(SCENE, OWNER, "Read two pages limit=3.", time_range=[8, 16])
    case = step(manager, step(manager, case))
    assert case["state"] == "READY" and case["answer"] is None
    assert len(case["tool_receipts"]) == len(current["calls"]) == 1
    assert case["metrics"]["tool_request_attempt_count"] == 2
    assert case["metrics"]["invalid_action_count"] == 1
    assert case["metrics"]["prompt_tokens"] == 200
    case = step(manager, step(manager, case))
    assert case["state"] == "COMPLETED" and len(case["answer"]["rows"]) == 2
    assert len(current["calls"]) == len(case["tool_receipts"]) == 2
    assert current["calls"][1][1]["cursor"] == "fixture-signed-next"
    assert case["metrics"]["model_call_count"] == 4
    assert case["metrics"]["tool_request_attempt_count"] == 3
    assert case["metrics"]["invalid_action_count"] == 1
    assert case["answer"]["coverage"]["complete_for_selected_scope"] is True


@pytest.mark.parametrize("tool", ["query_events", "query_observations"])
def test_last_tool_attempt_duplicate_still_allows_answer_and_stop_resume_preserves_usage(
    tmp_path: Path, tool: str,
) -> None:
    action = query()
    action["tool"] = tool
    if tool == "query_observations":
        action["goal"]["topic"] = "OBSERVATIONS"
    manager, _, current = prepared(tmp_path, [action, deepcopy(action), answer()],
                                   policy=AgentPolicy(max_tool_calls=2))
    if tool == "query_observations":
        executor = manager.executor
        manager.executor = lambda *args: executor(*args) | {"items": [
            {"observation_ref": "observation:" + "1" * 24, "kind": "UNKNOWN",
             "candidate_count": 1}]}
    case = step(manager, step(manager, manager.start(SCENE, OWNER, "Read source facts.",
                                                     time_range=[8, 16])))
    assert case["state"] == "READY" and case["metrics"]["tool_request_attempt_count"] == 2
    before = deepcopy(case["metrics"])
    manager.stop(SCENE, OWNER, case["agent_ref"])
    resumed = manager.resume(SCENE, OWNER, case["agent_ref"])
    assert resumed["metrics"] == before
    case = step(manager, resumed)
    assert case["state"] == "COMPLETED" and len(current["calls"]) == 1
    assert case["metrics"]["tool_request_attempt_count"] == 2
    assert case["metrics"]["invalid_action_count"] == 1
    assert case["metrics"]["model_call_count"] == 3
    assert case["metrics"]["prompt_tokens"] == 300


def test_duplicate_attempt_consumes_tool_budget_without_dispatching_next_page(
    tmp_path: Path,
) -> None:
    manager, _, current = paging_prepared(tmp_path, [query(), query(), continuation_query()],
                                         policy=AgentPolicy(max_tool_calls=2))
    case = step(manager, step(manager, manager.start(SCENE, OWNER, "Read source facts.",
                                                     time_range=[8, 16])))
    case = step(manager, case)
    assert case["state"] == "BUDGET_EXHAUSTED"
    assert case["error_code"] == "AGENT_TOOL_BUDGET_EXHAUSTED"
    assert len(current["calls"]) == len(case["tool_receipts"]) == 1
    assert case["metrics"]["tool_request_attempt_count"] == 2
    assert case["metrics"]["model_call_count"] == 3
    manager.stop(SCENE, OWNER, case["agent_ref"])
    with pytest.raises(AgentDenied):
        manager.resume(SCENE, OWNER, case["agent_ref"])


@pytest.mark.parametrize(("unsafe", "code"), [
    ("cursor", "AGENT_CURSOR_NOT_ISSUED"), ("camera", "AGENT_LOCAL_CAMERA_REQUIRED"),
    ("window", "AGENT_WINDOW_DENIED"), ("region", "AGENT_REGION_DENIED"),
])
def test_repeat_query_unsafe_arguments_remain_terminal_before_feedback(
    tmp_path: Path, unsafe: str, code: str,
) -> None:
    repeated = query()
    repeated["arguments"].update({"cursor": "unissued"} if unsafe == "cursor" else
        {"camera_ref": OTHER_CAMERA} if unsafe == "camera" else
        {"time_range": [8, 17]} if unsafe == "window" else {"region_id": "unregistered"})
    manager, _, current = prepared(tmp_path, [query(), repeated])
    case = step(manager, manager.start(SCENE, OWNER, "Read source facts.",
                                       camera_refs=[CAMERA], time_range=[8, 16]))
    case = step(manager, case)
    assert case["state"] == "FAILED" and case["error_code"] == code
    assert case["goal"]["requirement_feedback"] is None and len(current["calls"]) == 1
    assert case["metrics"]["tool_request_attempt_count"] == 1


@pytest.mark.parametrize(("tamper", "code"), [
    ("binding", "AGENT_EVIDENCE_BINDING_CHANGED"),
    ("payload", "AGENT_EVIDENCE_PAYLOAD_CHANGED"),
    ("row", "AGENT_FACT_FIELD_MISMATCH"),
    ("scope", "AGENT_TOOL_BINDING_CHANGED"),
    ("retrieval", "AGENT_EVIDENCE_CONTINUATION_CHANGED"),
    ("issued_message", "AGENT_EVIDENCE_RECEIPT_CHANGED"),
])
def test_repeat_query_tampered_matching_receipt_is_terminal_not_feedback(
    tmp_path: Path, tamper: str, code: str,
) -> None:
    manager, _, current = paging_prepared(tmp_path, [query(), query()])
    case = step(manager, manager.start(SCENE, OWNER, "Read source facts.", time_range=[8, 16]))
    raw = manager.ledger.load(manager._owner(OWNER), SCENE, case["agent_ref"])
    receipt = raw["tool_receipts"][0]
    if tamper == "binding":
        receipt["evidence"]["binding_sha256"] = "0" * 64
    elif tamper == "payload":
        receipt["result"]["data"]["items"][0]["candidate_count"] = 999
    elif tamper == "row":
        receipt["evidence"]["rows"][0]["fields"]["candidate_count"] = 999
    elif tamper == "scope":
        receipt["result"]["data"]["scope"]["observation_mode"] = "photos_only"
        new_sha = digest(receipt["result"]["data"])
        receipt["evidence"]["source_payload_sha256"] = new_sha
        for row in receipt["evidence"]["rows"]:
            row["source_payload_sha256"] = new_sha
    elif tamper == "retrieval":
        receipt["evidence"]["retrieval"]["next_cursor"] = "unissued"
    else:
        message = next(m for m in raw["messages"] if m["content"].startswith("UNTRUSTED TOOL DATA"))
        message["content"] = message["content"].replace("fixture-signed-next", "unissued")
    manager.ledger.save(manager._owner(OWNER), raw, raw["revision"])
    case = step(manager, case)
    assert case["state"] == "FAILED" and case["error_code"] == code
    assert case["goal"]["requirement_feedback"] is None and len(current["calls"]) == 1
    assert case["metrics"]["tool_request_attempt_count"] == 1


def test_nonpaging_duplicate_retains_terminal_guard(tmp_path: Path) -> None:
    action = {"kind": "tool", "tool": "list_cameras", "arguments": {},
              "goal": {"topic": "CAMERAS", "selection": "PAGE", "requested_fields": []}}
    manager, _, current = prepared(tmp_path, [action, deepcopy(action)])
    case = step(manager, step(manager, manager.start(SCENE, OWNER, "Read camera facts.")))
    assert case["state"] == "FAILED" and case["error_code"] == "AGENT_DUPLICATE_TOOL_LOOP"
    assert len(current["calls"]) == 1


def test_stopped_generation_cannot_commit_query_feedback_or_new_receipt(tmp_path: Path) -> None:
    manager, provider, current = prepared(tmp_path, [query(), query()])
    case = step(manager, manager.start(SCENE, OWNER, "Read source facts.", time_range=[8, 16]))
    provider.entered.clear()
    provider.release.clear()
    manager.advance(SCENE, OWNER, case["agent_ref"])
    assert provider.entered.wait(5)
    manager.stop(SCENE, OWNER, case["agent_ref"])
    provider.release.set()
    assert manager.wait_idle(5)
    case = manager.get(SCENE, OWNER, case["agent_ref"])
    assert case["state"] == "STOPPED" and case["goal"]["requirement_feedback"] is None
    assert case["metrics"]["tool_request_attempt_count"] == 1
    assert case["metrics"]["invalid_action_count"] == 0
    assert len(current["calls"]) == len(case["tool_receipts"]) == 1
    assert case["metrics"]["model_request_attempt_count"] == 2



def test_exhausted_no_cursor_query_repeat_can_select_existing_literal_evidence(
    tmp_path: Path,
) -> None:
    manager, _, current = prepared(tmp_path, [query(), query(), answer()])
    executor = manager.executor
    manager.executor = lambda *args: executor(*args) | {
        "retrieval": {"truncated": False, "next_cursor": None}}
    case = step(manager, step(manager, manager.start(SCENE, OWNER, "Read first page.",
                                                     time_range=[8, 16])))
    assert case["state"] == "READY" and case["answer"] is None
    case = step(manager, case)
    assert case["state"] == "COMPLETED" and len(current["calls"]) == 1
    assert case["answer"]["coverage"]["complete_for_selected_scope"] is True
    assert case["metrics"]["tool_request_attempt_count"] == 2
    assert case["metrics"]["invalid_action_count"] == 1


def test_query_feedback_obeys_consumed_model_budget_and_cannot_resume(tmp_path: Path) -> None:
    manager, _, current = prepared(tmp_path, [query(), query(), answer()],
                                   policy=AgentPolicy(max_model_calls=2))
    case = step(manager, step(manager, manager.start(SCENE, OWNER, "Read source facts.",
                                                     time_range=[8, 16])))
    assert case["state"] == "BUDGET_EXHAUSTED" and case["answer"] is None
    assert case["metrics"]["model_call_count"] == 2
    assert case["metrics"]["tool_request_attempt_count"] == 2
    assert case["metrics"]["invalid_action_count"] == 1
    assert case["metrics"]["prompt_tokens"] == 200
    assert len(current["calls"]) == len(case["tool_receipts"]) == 1
    manager.stop(SCENE, OWNER, case["agent_ref"])
    with pytest.raises(AgentDenied):
        manager.resume(SCENE, OWNER, case["agent_ref"])


def test_original_scope_projection_is_preserved_and_still_verifiable_for_query_feedback(
    tmp_path: Path,
) -> None:
    manager, _, current = prepared(tmp_path, [query(), query(), answer()],
                                   policy=AgentPolicy(max_result_chars=512))
    case = step(manager, manager.start(SCENE, OWNER, "Read source facts.", time_range=[8, 16]))
    assert case["tool_receipts"][0]["result"]["presentation_truncated"] is True
    assert "scope" not in case["tool_receipts"][0]["result"]["data"]
    case = step(manager, case)
    assert case["state"] == "READY" and case["answer"] is None
    assert case["goal"]["requirement_feedback"]["unmet"] == ["QUERY_ALREADY_SUCCEEDED"]
    case = step(manager, case)
    assert case["state"] == "COMPLETED" and len(current["calls"]) == 1
    assert case["answer"]["coverage"]["complete_for_selected_scope"] is False
    assert case["metrics"]["tool_request_attempt_count"] == 2



def test_paid_literal_field_feedback_uses_human_names_then_fixture_declares_its_own_goal(
    tmp_path: Path,
) -> None:
    required = ["kind", "candidate_count", "uncertainty"]
    corrected = query()
    corrected["goal"]["requested_fields"] = required
    manager, provider, current = prepared(tmp_path, [
        {"kind": "clarification", "question": "Which literal fields do you want?",
         "missing_slots": ["requested_facts"]}, query(), corrected, answer()])
    executor = manager.executor

    def execute(*args: Any) -> dict[str, Any]:
        result = executor(*args)
        result["items"][0]["uncertainty"] = "UNKNOWN"
        return result

    manager.executor = execute
    original = "Read registered event facts."
    reply = "Keep fields: kind, candidate_count, uncertainty."
    case = step(manager, manager.start(SCENE, OWNER, original, time_range=[8, 16]))
    case = manager.reply(SCENE, OWNER, case["agent_ref"], reply)
    case = step(manager, case)
    report = case["goal"]["requirement_feedback"]
    assert case["state"] == "READY" and case["answer"] is None
    assert report["required_literal_field_names"] == sorted(required)
    assert report["field_names_source"] == "TRUSTED_HUMAN_REQUEST_REQUIREMENTS"
    assert case["goal"]["request_spec"] is None and not current["calls"]
    assert case["metrics"]["model_call_count"] == 2
    assert case["metrics"]["invalid_action_count"] == 1
    assert case["metrics"]["tool_request_attempt_count"] == 0
    case = step(manager, step(manager, case))
    assert case["state"] == "COMPLETED" and len(current["calls"]) == 1
    assert case["goal"]["request_spec"]["requested_fields"] == required
    assert case["goal"]["original_request"] == original
    assert case["goal"]["clarification_replies"] == [reply]
    assert case["answer"]["rows"][0]["fields"]["uncertainty"] == "UNKNOWN"
    assert case["metrics"]["model_call_count"] == 4
    assert case["metrics"]["prompt_tokens"] == 400
    assert case["metrics"]["output_tokens"] == 80
    assert case["metrics"]["invalid_action_count"] == 1
    assert "required_literal_field_names" in provider.messages[2][-1]["content"]


@pytest.mark.parametrize("unsupported", [False, True])
def test_literal_feedback_never_derives_names_or_values_from_source_or_unsupported_identifiers(
    tmp_path: Path, unsupported: bool,
) -> None:
    manager, _, current = prepared(tmp_path, [query()])
    text = "Read fields: uncertainty" + (", unavailable_field." if unsupported else ".")
    case = step(manager, manager.start(SCENE, OWNER, text, time_range=[8, 16]))
    report = case["goal"]["requirement_feedback"]
    assert report["required_literal_field_names"] == ["uncertainty"]
    assert "unavailable_field" not in json.dumps(report)
    assert "kind" not in json.dumps(report) and "candidate_count" not in json.dumps(report)
    assert case["goal"]["request_spec"] is None and not current["calls"]
    assert case["metrics"]["tool_request_attempt_count"] == 0
    assert case["metrics"]["prompt_tokens"] == 100
