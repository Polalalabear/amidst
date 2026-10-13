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
from amidst.local_agent.contracts import EvidenceSelection
from amidst.local_agent.evaluation import summarize_cases
from amidst.local_agent.evidence import build_evidence_receipt, verified_answer
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


def test_identical_completed_read_is_not_reexecuted_until_budget(tmp_path: Path) -> None:
    manager, _, current = prepared(tmp_path, [query(), query()])
    case = manager.start(SCENE, OWNER, "query", time_range=[8, 16])
    case = step(manager, case)
    case = step(manager, case)
    assert case["state"] == "FAILED"
    assert case["error_code"] == "AGENT_DUPLICATE_TOOL_LOOP"
    assert len(current["calls"]) == 1
    assert case["metrics"]["model_call_count"] == 2


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
