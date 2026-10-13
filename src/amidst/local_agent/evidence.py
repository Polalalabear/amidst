"""Literal DTO evidence, independently verifiable selectors and honest source coverage."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from amidst.engineering.access import digest

from .contracts import (
    AgentBinding,
    AgentDenied,
    EvidenceRow,
    EvidenceSelection,
    RequestGoal,
    VerifiedAnswer,
)

EXECUTION_VERSION = "typed.evidence.v2"
FACT_FIELDS = frozenset({
    "event_ref", "observation_ref", "local_track_ref", "track_ref", "camera_ref", "camera_refs",
    "camera_id", "camera_ids", "resource_ref", "hypothesis_ref", "media_ref", "frame_ref",
    "association_ref", "kind", "candidate_count", "hypothesis_count", "time_range", "timestamp",
    "complete", "termination_reason", "evidence_state", "uncertainty", "missing_evidence",
    "alternatives", "supports", "conflicts", "support_state", "status", "reason", "origin",
    "authority", "region_ids", "track_refs", "score", "distance", "rank", "score_meaning",
    "hops", "place_id", "model_id", "requested_top_k", "candidate_tracks_read", "eligible_tracks",
    "unavailable_track_refs", "cutoff_tie_extension", "source_inputs_complete", "coverage",
    "local_pool_truncated", "query_track_ref", "candidate_id", "path_length",
    "minimum_travel_time", "estimated_travel_time", "path_score", "feasibility_flags",
    "provenance", "local_track_refs",
})
_RESOURCE_FIELDS = ("event_ref", "observation_ref", "hypothesis_ref", "track_ref",
                    "local_track_ref", "camera_ref", "resource_ref", "media_ref", "frame_ref",
                    "association_ref", "candidate_id")
_PAGED_TOOLS = {"query_events", "query_observations", "propose_feasible_trajectories"}
_TOPIC_TOOLS = {
    "EVENTS": {"query_events", "get_event_summary", "get_event_detail"},
    "OBSERVATIONS": {"query_observations", "get_observation_detail"},
    "CAMERAS": {"list_cameras", "query_reachable_cameras"},
    "PLACES": {"resolve_place"}, "APPEARANCE": {"search_person_appearance"},
    "STITCHES": {"get_stitch_hypotheses"},
    "TRAJECTORIES": {"propose_feasible_trajectories"},
    "MEDIA": {"get_media"}, "REPLAY": {"get_replay"},
}
_TOPIC_ROW_FIELDS = {"EVENTS": {"event_ref"},
                     "OBSERVATIONS": {"observation_ref", "local_track_ref", "track_ref"},
                     "CAMERAS": {"camera_ref"}}


def binding_digest(binding: AgentBinding) -> str:
    return digest(binding.model_dump(mode="json", exclude={"session_ref"}))


def at_locator(value: Any, locator: list[str | int] | tuple[str | int, ...]) -> Any:
    try:
        for part in locator:
            value = value[part]
        return value
    except (KeyError, IndexError, TypeError):
        raise AgentDenied("AGENT_EVIDENCE_LOCATOR_INVALID") from None


def build_evidence_receipt(receipt: dict[str, Any], original: dict[str, Any],
                           binding: AgentBinding) -> dict[str, Any]:
    """Keep only literal fields still visible after metadata/context projection."""
    data = receipt["result"]["data"]
    source_hash = digest(data)
    candidates: list[tuple[list[str | int], dict[str, Any]]] = []
    arrays = [key for key in ("items", "hits") if isinstance(data.get(key), list)]
    for key in arrays:
        candidates.extend(([key, i], row) for i, row in enumerate(data[key])
                          if isinstance(row, dict))
    if not arrays or any(key in data for key in _RESOURCE_FIELDS):
        candidates.insert(0, ([], data))
    rows = []
    for locator, row in candidates:
        source = at_locator(original, locator)
        fields = {k: deepcopy(v) for k, v in row.items() if k in FACT_FIELDS
                  and isinstance(source, dict) and k in source and digest(source[k]) == digest(v)
                  and len(json.dumps(v, ensure_ascii=False)) <= 12000}
        if not fields:
            continue
        resource = next((row[k] for k in _RESOURCE_FIELDS if isinstance(row.get(k), str)), None)
        row_ref = "factrow:" + digest({"receipt": receipt["receipt_ref"], "locator": locator})[:24]
        rows.append(EvidenceRow(row_ref=row_ref, resource_ref=resource,
            receipt_ref=receipt["receipt_ref"], fields=fields, json_locator=tuple(locator),
            source_payload_sha256=source_hash).model_dump(mode="json"))
    retrieval = data.get("retrieval")
    source_arrays = [key for key in ("items", "hits") if isinstance(original.get(key), list)]
    source_count = sum(len(original[k]) for k in source_arrays)
    visible_count = sum(len(data[k]) for k in arrays)
    evidenced_count = sum(bool(row["resource_ref"]) for row in rows if row["json_locator"])
    return {"schema_version": "local.agent.evidence.v2", "rows": rows,
            "source_payload_sha256": source_hash, "binding_sha256": binding_digest(binding),
            "rows_complete": (source_arrays == arrays and
                              source_count == visible_count == evidenced_count),
            "source_returned_count": source_count, "visible_returned_count": visible_count,
            "retrieval": deepcopy(retrieval) if isinstance(retrieval, dict) else None}


def validate_request_goal(goal: RequestGoal) -> None:
    if not set(goal.requested_fields) <= FACT_FIELDS:
        raise AgentDenied("AGENT_GOAL_FIELD_UNAVAILABLE")


def _verified_rows(receipt: dict[str, Any], binding: AgentBinding) -> list[dict[str, Any]]:
    if receipt.get("status") != "OK" or receipt["result"].get("detail_withheld"):
        raise AgentDenied("AGENT_UNGROUNDED_CITATION")
    evidence = receipt.get("evidence")
    if not isinstance(evidence, dict) or evidence.get("binding_sha256") != binding_digest(binding):
        raise AgentDenied("AGENT_EVIDENCE_BINDING_CHANGED")
    data = receipt["result"]["data"]
    if evidence.get("source_payload_sha256") != digest(data):
        raise AgentDenied("AGENT_EVIDENCE_PAYLOAD_CHANGED")
    rows = []
    for raw in evidence["rows"]:
        row = EvidenceRow.model_validate(raw).model_dump(mode="json")
        source = at_locator(data, row["json_locator"])
        if (row["receipt_ref"] != receipt["receipt_ref"]
            or row["source_payload_sha256"] != digest(data)
            or row["row_ref"] != "factrow:" + digest({"receipt": receipt["receipt_ref"],
                                                      "locator": row["json_locator"]})[:24]
            or not set(row["fields"]) <= FACT_FIELDS
            or not isinstance(source, dict)
            or any(k not in source or digest(source[k]) != digest(v)
                   for k, v in row["fields"].items())):
            raise AgentDenied("AGENT_FACT_FIELD_MISMATCH")
        expected_resource = next((source[k] for k in _RESOURCE_FIELDS
                                  if isinstance(source.get(k), str)), None)
        if row["resource_ref"] != expected_resource:
            raise AgentDenied("AGENT_FACT_FIELD_MISMATCH")
        rows.append(row)
    return rows


def derive_coverage(receipts: list[dict[str, Any]], rows: list[dict[str, Any]],
                    cameras: list[str], window: list[float] | None = None) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    selected = {row["resource_ref"] for row in rows if row["resource_ref"]}
    for receipt in receipts:
        if receipt.get("status") != "OK" or receipt["tool"] not in _PAGED_TOOLS:
            continue
        filters = {k: v for k, v in receipt["arguments"].items() if k not in {"cursor", "limit"}}
        key = digest({"tool": receipt["tool"], "filters": filters})
        groups.setdefault(key, []).append(receipt)
    collections = []
    for key, pages in groups.items():
        roots = [p for p in pages if not p["arguments"].get("cursor")]
        chain: list[dict[str, Any]] = []
        current = roots[0] if len(roots) == 1 else None
        exhausted = False
        while current and current not in chain:
            chain.append(current)
            retrieval = current.get("evidence", {}).get("retrieval")
            if not isinstance(retrieval, dict):
                break
            cursor = retrieval.get("next_cursor")
            if cursor is None:
                exhausted = retrieval.get("truncated") is False
                break
            matches = [p for p in pages if p["arguments"].get("cursor") == cursor]
            current = matches[0] if len(matches) == 1 else None
        chain_complete = exhausted and len(chain) == len(pages)
        visible_resources: list[str] = []
        duplicate_resources = False
        for page in pages:
            for row in page.get("evidence", {}).get("rows", []):
                resource = row["resource_ref"]
                if resource and resource not in visible_resources:
                    visible_resources.append(resource)
                elif resource:
                    duplicate_resources = True
        rows_complete = not duplicate_resources and all(
            p.get("evidence", {}).get("rows_complete") is True for p in pages)
        returned = len(visible_resources)
        collections.append({"tool": pages[0]["tool"], "query_sha256": key,
            "camera_ref": pages[0]["arguments"].get("camera_ref"),
            "time_range_seconds": pages[0]["arguments"].get("time_range"),
            "matches_selected_scope": (pages[0]["arguments"].get("time_range") == window
                and not pages[0]["arguments"].get("region_id")
                and not pages[0]["arguments"].get("seed_refs")),
            "receipt_refs": [p["receipt_ref"] for p in pages], "returned_count": returned,
            "selected_count": len(selected.intersection(visible_resources)),
            "source_truncated": not chain_complete, "cursor_chain_complete": chain_complete,
            "presentation_truncated": any(p["result"].get("presentation_truncated", False)
                                          for p in pages),
            "presentation_rows_complete": rows_complete,
            "registered_total": returned if chain_complete and rows_complete else None,
            "pages": [{"receipt_ref": p["receipt_ref"],
                       "source_truncated": (p.get("evidence", {}).get("retrieval") or {}).get(
                           "truncated"), "source_returned_count": p.get("evidence", {}).get(
                               "source_returned_count"), "visible_returned_count": p.get(
                                   "evidence", {}).get("visible_returned_count"),
                       "presentation_truncated": p["result"].get("presentation_truncated", False)}
                      for p in pages]})
    complete = bool(collections) and all(c["cursor_chain_complete"]
        and c["presentation_rows_complete"] and c["returned_count"] == c["selected_count"]
        and c["matches_selected_scope"]
        for c in collections) and set(cameras) <= {c["camera_ref"] for c in collections}
    return {"collections": collections, "complete_for_selected_scope": complete,
            "scope_meaning": "REGISTERED_DTO_COLLECTION_NOT_PERSON_OR_EVENT_TRUTH"}


def verified_answer(binding: AgentBinding, receipts: list[dict[str, Any]],
                    selections: tuple[EvidenceSelection, ...], goal: dict[str, Any],
                    cameras: list[str], window: list[float]) -> dict[str, Any]:
    if not selections:
        raise AgentDenied("AGENT_TYPED_ANSWER_REQUIRED")
    by_ref = {r["receipt_ref"]: r for r in receipts}
    if any(selection.receipt_ref not in by_ref for selection in selections):
        raise AgentDenied("AGENT_UNGROUNDED_CITATION")
    if goal.get("request_spec") is None:
        raise AgentDenied("AGENT_GOAL_REQUIRED")
    request = RequestGoal.model_validate(goal["request_spec"])
    for receipt in receipts:
        if receipt.get("status") == "OK" and not receipt["result"].get("detail_withheld"):
            _verified_rows(receipt, binding)
    requested: dict[str, set[str]] = {}
    available_rows: dict[str, list[dict[str, Any]]] = {}
    for selection in selections:
        receipt = by_ref[selection.receipt_ref]
        if receipt["tool"] not in _TOPIC_TOOLS[request.topic]:
            raise AgentDenied("AGENT_FACT_TOPIC_MISMATCH")
        available = _verified_rows(receipt, binding)
        available_rows[selection.receipt_ref] = available
        chosen_refs = (list(selection.row_refs) if selection.row_refs else
                       [row["row_ref"] for row in available])
        available_refs = {row["row_ref"] for row in available}
        if not set(chosen_refs) <= available_refs:
            raise AgentDenied("AGENT_FACT_ROW_NOT_ISSUED")
        prior = requested.setdefault(selection.receipt_ref, set())
        if len(chosen_refs) != len(set(chosen_refs)) or prior.intersection(chosen_refs):
            raise AgentDenied("AGENT_DUPLICATE_FACT_SELECTION")
        prior.update(chosen_refs)
    rows, cited = [], []
    resources: set[str] = set()
    # Receipt chronology and each DTO's original row order are server-owned.
    for receipt in receipts:
        reference = receipt["receipt_ref"]
        if reference not in requested:
            continue
        cited.append(reference)
        for row in available_rows[reference]:
            if row["row_ref"] not in requested[reference]:
                continue
            if row["resource_ref"] and row["resource_ref"] in resources:
                raise AgentDenied("AGENT_DUPLICATE_FACT_SELECTION")
            if row["resource_ref"]:
                resources.add(row["resource_ref"])
            rows.append(row)
    for row in rows:
        required_refs = _TOPIC_ROW_FIELDS.get(request.topic)
        if required_refs and not any(isinstance(row["fields"].get(key), str)
                                     for key in required_refs):
            raise AgentDenied("AGENT_FACT_TOPIC_MISMATCH")
        if not set(request.requested_fields) <= set(row["fields"]):
            raise AgentDenied("AGENT_REQUIRED_FACT_FIELDS_MISSING")
    if request.selection == "FIRST":
        topic_tool = {"EVENTS": "query_events", "OBSERVATIONS": "query_observations",
                      "TRAJECTORIES": "propose_feasible_trajectories"}.get(request.topic)
        first = next((r["resource_ref"] for p in receipts if p["tool"] == topic_tool
                      for r in p.get("evidence", {}).get("rows", [])), None)
        if len(rows) != 1 or first is None or rows[0]["resource_ref"] != first:
            raise AgentDenied("AGENT_FIRST_FACT_SELECTION_MISMATCH")
    coverage = derive_coverage(receipts, rows, cameras, window)
    if not rows and not coverage["complete_for_selected_scope"]:
        raise AgentDenied("AGENT_EMPTY_FACTUAL_ANSWER")
    answer = {"schema_version": "local.agent.answer.v2", "rows": rows, "citations": cited,
        "verification": {"status": "VERIFIED_DTO_FIELDS", "version": "v2",
                         "binding_sha256": binding_digest(binding)}, "coverage": coverage,
        "response_language": goal["response_language"],
        "scope": {"camera_refs": cameras, "time_range_seconds": window,
                  "source_ref": binding.source_ref, "observation_mode": binding.observation_mode,
                  "freeze_ref": binding.freeze_ref,
                  "product_freeze_ref": binding.product_freeze_ref},
        "semantic_factuality": "LITERAL_FIELDS_VERIFIED_INTERPRETATION_NOT_CERTIFIED"}
    answer["text"] = render_answer(answer)
    return VerifiedAnswer.model_validate(answer).model_dump(mode="json")


def render_answer(answer: dict[str, Any]) -> str:
    chinese = answer["response_language"] == "zh-Hant"
    text = ["已核對的登錄 DTO 欄位（合成／暫定）；不確認人物身分、行為或意圖。" if chinese
            else "Verified registered DTO fields (synthetic/provisional); identity, behavior and "
                 "intent are not confirmed."]
    for row in answer["rows"]:
        fields = "; ".join(f"{k}={json.dumps(v, ensure_ascii=False)}"
                           for k, v in row["fields"].items())
        text.append(f"{row['resource_ref'] or row['row_ref']}: {fields} [{row['receipt_ref']}]")
    for collection in answer["coverage"]["collections"]:
        total = collection["registered_total"]
        if chinese:
            total_label = total if total is not None else "UNKNOWN（來源尚有未讀頁或呈現遺漏）"
            text.append(f"此查詢已讀取 {collection['returned_count']} 筆；答案選取 "
                        f"{collection['selected_count']} 筆。登錄總數："
                        f"{total_label}。")
        else:
            text.append(f"Query rows read: {collection['returned_count']}; selected: "
                        f"{collection['selected_count']}. Registered total: "
                        f"{total if total is not None else 'UNKNOWN (unread or withheld rows)' }.")
        if collection["presentation_truncated"]:
            text.append("模型呈現曾截斷／省略內容；事件 complete 不代表全部查詢結果。" if chinese
                        else "Model presentation omitted content; event complete is separate "
                             "from collection completeness.")
    if not answer["rows"]:
        text.append("完整登錄查詢返回 0 筆；不代表沒有任何人物或行為。" if chinese else
                    "The exhausted registered query returned 0 rows; this is not proof of "
                    "absence of people or behavior.")
    return "\n".join(text)


def render_refusal(reason: str, language: str) -> dict[str, Any]:
    explanations = {
        "UNSUPPORTED_TOOL": ("此工作只支援已授權的本機 typed tools。", "Only authorized local "
                             "typed tools are supported."),
        "PRIVATE_SOURCE": ("不能讀取 GT、私有來源或憑證。", "GT, private sources and credentials "
                           "are unavailable."),
        "EXTERNAL_EGRESS": ("不能將影像或資料外送至外部 API。", "Images and data cannot be sent "
                             "to external APIs."),
        "CONFIRMED_IDENTITY": ("合成／暫定證據不能確認真實姓名或人物身分。",
                                 "Synthetic/provisional "
                                 "evidence cannot confirm real names or identity."),
        "OUT_OF_SCOPE": ("要求超出此案選定的來源、模式、鏡頭或時間窗。", "The request exceeds the "
                           "case's selected source, mode, cameras or time window."),
    }
    return {"schema_version": "local.agent.refusal.v2", "reason_code": reason,
            "response_language": language,
            "text": explanations[reason][0 if language == "zh-Hant" else 1],
            "origin": "MODEL_SELECTED_REASON_SERVER_RENDERED", "tools_dispatched_for_refusal": 0}
