"""Transport fixtures are loopback-only; they are not model accuracy evaluations."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from amidst.local_agent import AgentDenied, ModelAction, OllamaProvider
from amidst.local_agent.tools import (
    action_schema,
    bounded_result,
    issued_references,
    sanitize_result,
)

from .test_manager import CAMERA, EVENT, OTHER_CAMERA, binding, evidence_page

SHA = "a" * 64


@pytest.mark.parametrize("url", [
    "https://127.0.0.1:11434", "http://example.com:11434", "http://127.0.0.1.evil.test",
    "http://user@127.0.0.1", "http://127.0.0.1/api/chat", "http://127.0.0.1?proxy=yes",
])
def test_no_arbitrary_or_redirecting_endpoint(url: str) -> None:
    with pytest.raises(AgentDenied, match="LOOPBACK_ENDPOINT_REQUIRED"):
        OllamaProvider(url, "qwen2.5:3b-instruct", model_digest=SHA)


def test_schema_disallows_mixed_actions_and_empty_unsupported_answers() -> None:
    for action in (
        {"kind": "tool", "tool": "list_cameras", "text": "answer"},
        {"kind": "answer", "text": "unsupported", "citations": []},
        {"kind": "clarification", "question": "which", "arguments": {"path": "private"}},
        {"kind": "shell", "tool": "exec"},
    ):
        with pytest.raises(ValueError):
            ModelAction.model_validate(action)


def test_dynamic_generation_schema_uses_exact_refs_scope_and_citations() -> None:
    schema = action_schema(binding(), [CAMERA], [8, 16], {CAMERA}, [])
    choices = schema["anyOf"]
    tools = {c["properties"]["tool"]["const"]: c for c in choices
             if "tool" in c["properties"]}
    assert "get_event_detail" not in tools
    query = tools["query_events"]["properties"]["arguments"]
    assert query["properties"]["camera_ref"]["enum"] == [CAMERA]
    assert query["properties"]["time_range"]["const"] == [8, 16]
    assert "camera_ref" in query["required"]
    assert all(c["properties"]["kind"].get("const") != "answer" for c in choices)
    ready = action_schema(binding(), [CAMERA], [8, 16], {CAMERA, EVENT}, ["receipt:valid"])
    detail = next(c for c in ready["anyOf"] if c["properties"].get("tool") == {
        "const": "get_event_detail"})
    assert detail["properties"]["arguments"]["properties"]["event_ref"]["enum"] == [EVENT]
    answer = next(c for c in ready["anyOf"] if c["properties"]["kind"]["const"] == "answer")
    assert answer["properties"]["citations"]["items"]["enum"] == ["receipt:valid"]


def test_optional_filters_never_offer_unregistered_regions_cursors_or_seed_references() -> None:
    track, observation = "track:" + "1" * 24, "observation:" + "2" * 24
    schema = action_schema(binding(), [CAMERA], [8, 16],
                           {CAMERA, EVENT, track, observation}, [],
                           issued_cursors={"query_events": ["signed-event-page"]})
    tools = {c["properties"]["tool"]["const"]: c["properties"]["arguments"]["properties"]
             for c in schema["anyOf"] if "tool" in c["properties"]}
    assert tools["query_events"]["region_id"]["anyOf"] == [
        {"type": "string", "enum": ["LOBBY"]}, {"type": "null"}]
    assert tools["query_events"]["cursor"]["anyOf"][0]["enum"] == ["signed-event-page"]
    assert "cursor" not in tools["query_observations"]
    seeds = tools["propose_feasible_trajectories"]["seed_refs"]["items"]["enum"]
    assert set(seeds) == {track, observation}
    assert tools["get_replay"]["timestamp"]["minimum"] == 8
    assert tools["get_replay"]["timestamp"]["maximum"] == 16
    no_regions = action_schema(binding(), [OTHER_CAMERA], [8, 16], {OTHER_CAMERA}, [])
    query = next(c["properties"]["arguments"]["properties"] for c in no_regions["anyOf"]
                 if c["properties"].get("tool") == {"const": "query_events"})
    assert "region_id" not in query
    proposal = next(c["properties"]["arguments"]["properties"] for c in no_regions["anyOf"]
                    if c["properties"].get("tool") == {"const": "propose_feasible_trajectories"})
    assert "seed_refs" not in proposal


def test_typed_schema_requires_goal_and_issued_rows_and_disjoint_refusal() -> None:
    first = action_schema(binding(), [CAMERA], [8, 16], {CAMERA}, [],
                          evidence_receipts=[], goal_required=True)
    query = next(c for c in first["anyOf"] if c["properties"].get("tool") == {
        "const": "query_events"})
    assert "goal" in query["required"]
    assert all(c["properties"]["kind"]["const"] != "answer" for c in first["anyOf"])
    clarification = next(c for c in first["anyOf"] if c["properties"]["kind"]["const"] ==
                         "clarification")
    assert "missing_slots" in clarification["required"]
    receipt = evidence_page()
    ready = action_schema(binding(), [CAMERA], [8, 16], {CAMERA, EVENT}, [],
                          evidence_receipts=[receipt])
    answer = next(c for c in ready["anyOf"] if c["properties"]["kind"]["const"] == "answer")
    assert answer["properties"]["selections"]["uniqueItems"] is True
    assert answer["properties"]["selections"]["maxItems"] == 1
    assert "text" not in answer["properties"] and "citations" not in answer["properties"]
    selector = answer["properties"]["selections"]["items"]["anyOf"][0]["properties"]
    assert selector["receipt_ref"]["const"] == receipt["receipt_ref"]
    assert selector["row_refs"]["items"]["enum"] == [receipt["evidence"]["rows"][0]["row_ref"]]
    second = evidence_page(1)
    ready_multi = action_schema(binding(), [CAMERA], [8, 16], {CAMERA, EVENT}, [],
                                evidence_receipts=[receipt, second])
    multi = next(c for c in ready_multi["anyOf"] if c["properties"]["kind"]["const"] == "answer")
    assert multi["properties"]["selections"]["maxItems"] == 2
    empty = evidence_page(empty=True)
    ready = action_schema(binding(), [CAMERA], [8, 16], {CAMERA}, [], evidence_receipts=[empty])
    answer = next(c for c in ready["anyOf"] if c["properties"]["kind"]["const"] == "answer")
    assert answer["properties"]["selections"]["items"]["anyOf"][0]["properties"][
        "row_refs"]["maxItems"] == 0
    for action in ({"kind": "refusal", "reason_code": "EXTERNAL_EGRESS", "text": "extra"},
                   {"kind": "answer", "selections": [{"receipt_ref": "receipt:valid"}],
                    "text": "invented"}):
        with pytest.raises(ValueError):
            ModelAction.model_validate(action)


def test_binary_removed_private_fields_fail_closed_and_public_refs_retained() -> None:
    safe = sanitize_result({"base64": "private pixels", "content_base64": "more pixels",
                            "session_ref": "private-session", "media_ref": "media:known",
                            "nested": {"source_frames": [{"frame_ref": "frame:known"}]}})
    assert safe["binary_media_omitted"] is True
    assert "private" not in json.dumps(safe)
    assert issued_references(safe) == {"media:known", "frame:known"}
    for private in ({"ground_truth": {}}, {"path": "/Users/private/source.blend"},
                    {"actor_id": "id"}, {"gt_path": []}, {"value": float("nan")}):
        with pytest.raises(AgentDenied):
            sanitize_result(private)


def test_truncation_keeps_exact_prefix_and_never_reorders_or_fakes_full_detail() -> None:
    rows = [{"event_ref": f"event:{i}", "payload": "x" * 140} for i in range(9)]
    limited = bounded_result({"items": rows}, 550)
    assert limited["presentation_truncated"]
    assert limited["original_item_count"] == 9
    assert limited["data"]["items"] == rows[:limited["visible_item_count"]]
    result = bounded_result({"candidates": [{"rank": 1, "path": "x" * 1000}]}, 512)
    assert result["detail_withheld"]
    assert result["data"] == {}


def test_event_metadata_retains_kind_counts_alternatives_and_original_order() -> None:
    rows = [{"event_ref": f"event:{i}", "kind": "INFERRED_GAP_ALTERNATIVES",
             "candidate_count": i + 2, "hypothesis_count": 3,
             "uncertainty": "PROVISIONAL UNKNOWN", "alternatives": ["first", "second"],
             "source_frames": [{"frame_ref": "large-frame", "padding": "x" * 1000}],
             "config_sha256": SHA} for i in range(3)]
    result = bounded_result({"items": rows}, 1800)
    assert result["presentation_truncated"]
    assert result["model_metadata_projection"]
    assert [r["event_ref"] for r in result["data"]["items"]] == [r["event_ref"] for r in rows]
    assert [r["candidate_count"] for r in result["data"]["items"]] == [2, 3, 4]
    assert all(r["alternatives"] == ["first", "second"] for r in result["data"]["items"])


def test_ollama_wire_contract_pins_digest_schema_options_and_real_counts() -> None:
    requests: list[dict[str, Any]] = []
    state = {"digest": SHA}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            pass

        def do_GET(self) -> None:
            data = {"models": [{"name": "qwen2.5:3b-instruct", "digest": state["digest"]}]}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({
                "model": "qwen2.5:3b-instruct", "done": True,
                "message": {"content": json.dumps({"kind": "clarification",
                                                   "question": "Which camera?"})},
                "prompt_eval_count": 123, "eval_count": 45,
            }).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        provider = OllamaProvider(f"http://127.0.0.1:{server.server_port}",
                                  "qwen2.5:3b-instruct", model_digest=SHA)
        completion = provider.complete([{"role": "user", "content": "free form"}],
                                       max_output_tokens=384)
        assert completion.prompt_tokens == 123
        assert completion.output_tokens == 45
        assert completion.provider == "OLLAMA_LOOPBACK"
        assert requests[0]["options"] == {"temperature": 0, "seed": 0, "num_ctx": 8192,
                                          "num_predict": 384}
        assert requests[0]["format"] == ModelAction.model_json_schema()
        assert requests[0]["stream"] is False
        assert "tools" not in requests[0]  # Tools only become actions after typed validation.
        state["digest"] = "b" * 64
        with pytest.raises(AgentDenied, match="MODEL_BINDING_CHANGED"):
            provider.identity()
    finally:
        server.shutdown()
        server.server_close()
