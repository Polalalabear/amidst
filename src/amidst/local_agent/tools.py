"""Reuse existing typed read tools, with local-window and issued-reference checks."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from typing import Any

from amidst.engineering.facade import (
    EventRequest,
    MediaRequest,
    ReplayRequest,
    ResolveRequest,
    ToolRequest,
)
from amidst.product.service import (
    AppearanceRequest,
    ObservationRequest,
    PagedRequest,
    ProposeRequest,
    ReachRequest,
    StitchRequest,
)

from .contracts import AgentBinding, AgentDenied, RequestGoal

REQUEST_TYPES: dict[str, type[ToolRequest]] = {
    "resolve_place": ResolveRequest, "list_cameras": ToolRequest,
    "query_observations": PagedRequest, "query_events": PagedRequest,
    "get_event_summary": EventRequest, "get_event_detail": EventRequest,
    "get_media": MediaRequest, "get_replay": ReplayRequest,
    "get_observation_detail": ObservationRequest,
    "query_reachable_cameras": ReachRequest, "propose_feasible_trajectories": ProposeRequest,
    "search_person_appearance": AppearanceRequest, "get_stitch_hypotheses": StitchRequest,
}
DESCRIPTIONS = {
    "resolve_place": "Resolve a place label; ambiguous/missing labels need clarification.",
    "list_cameras": "List registered cameras and their opaque references in the bound scene.",
    "query_observations": "Read local tracks in an allowed camera and the selected window.",
    "query_events": "Read provisional event summaries, preserving UNKNOWN and alternatives.",
    "get_event_summary": "Read an already issued event reference without confirming behavior.",
    "get_event_detail": "Read original ranked candidates and uncertainty for an issued event.",
    "get_media": "Read metadata for issued media; image bytes are removed before model input.",
    "get_replay": "Read presentation metadata for an issued event at a selected timestamp.",
    "get_observation_detail": "Read an issued observation with its measured/projected evidence.",
    "query_reachable_cameras": "Read configured reachability; no real-world geometry authority.",
    "propose_feasible_trajectories": "Read deterministic alternatives; never reorder candidates.",
    "search_person_appearance": "Read provisional appearance ranking; not confirmed identity.",
    "get_stitch_hypotheses": "Read provisional/unmatched stitching and all alternatives.",
}


def tool_specs(binding: AgentBinding) -> list[dict[str, Any]]:
    specs = []
    for name in binding.allowed_tools:
        if name not in REQUEST_TYPES:
            raise AgentDenied("AGENT_TOOL_CONTRACT_UNAVAILABLE")
        schema = REQUEST_TYPES[name].model_json_schema()
        schema["properties"].pop("session_ref", None)
        schema["required"] = [k for k in schema.get("required", ()) if k != "session_ref"]
        schema.pop("title", None)
        for value in schema["properties"].values():
            value.pop("title", None)
        specs.append({"name": name, "description": DESCRIPTIONS[name], "parameters": schema})
    return specs


def action_schema(binding: AgentBinding, cameras: list[str], window: list[float],
                  issued_refs: set[str], citations: list[str], *,
                  issued_cursors: dict[str, list[str]] | None = None,
                  evidence_receipts: list[dict[str, Any]] | None = None,
                  goal_required: bool = False) -> dict[str, Any]:
    """Constrain generation to exact issued references, rather than repair guessed IDs."""
    regions = sorted({r for c in binding.cameras if c.camera_ref in cameras for r in c.region_ids})
    choices: list[dict[str, Any]] = []
    for spec in tool_specs(binding):
        parameters = deepcopy(spec["parameters"])
        unavailable = False
        for key, field in list(parameters["properties"].items()):
            if key == "camera_ref":
                parameters["properties"][key] = {"type": "string", "enum": cameras}
            elif key.endswith("_ref"):
                prefix = "track" if key == "local_track_ref" else key.removesuffix("_ref")
                refs = sorted(r for r in issued_refs if r.startswith(prefix + ":"))
                if key == "query_track_ref":
                    refs = sorted(r for r in issued_refs if r.startswith("track:"))
                if not refs and key in parameters.get("required", ()):
                    unavailable = True
                elif refs:
                    parameters["properties"][key] = {"type": "string", "enum": refs}
                else:
                    parameters["properties"].pop(key)
            elif key == "seed_refs":
                refs = sorted(r for r in issued_refs if r.startswith(("track:", "observation:")))
                if refs:
                    parameters["properties"][key] = {"type": "array", "default": [],
                        "maxItems": 12, "uniqueItems": True,
                        "items": {"type": "string", "enum": refs}}
                else:
                    parameters["properties"].pop(key)
            elif key in {"region_id", "cursor"}:
                values = regions if key == "region_id" else (issued_cursors or {}).get(
                    spec["name"], [])
                if values:
                    parameters["properties"][key] = {"anyOf": [
                        {"type": "string", "enum": sorted(set(values))}, {"type": "null"}],
                        "default": None}
                else:
                    parameters["properties"].pop(key)
            elif key == "time_range":
                parameters["properties"][key] = {
                    "type": "array", "minItems": 2, "maxItems": 2, "const": window}
            elif key == "timestamp":
                field.update(minimum=window[0], maximum=window[1])
            elif key == "limit":
                field.update(default=3, maximum=12)
            elif key == "top_k":
                field["maximum"] = 8
        if unavailable:
            continue
        if "time_range" in parameters["properties"]:
            parameters["required"] = list(dict.fromkeys(
                parameters.get("required", []) + ["camera_ref"]))
        properties: dict[str, Any] = {"kind": {"const": "tool"},
                                     "tool": {"const": spec["name"]}, "arguments": parameters}
        required = ["kind", "tool", "arguments"]
        if goal_required:
            properties["goal"] = RequestGoal.model_json_schema()
            required.append("goal")
        choices.append({"type": "object", "additionalProperties": False,
                        "properties": properties, "required": required})
    choices.append({"type": "object", "additionalProperties": False,
                    "properties": {"kind": {"const": "clarification"},
                                   "question": {"type": "string", "minLength": 1,
                                                "maxLength": 1000}},
                    "required": ["kind", "question"]})
    if evidence_receipts is not None:
        clarification = choices[-1]
        clarification["properties"]["missing_slots"] = {"type": "array", "minItems": 1,
            "maxItems": 4, "uniqueItems": True, "items": {"type": "string", "enum": [
                "target", "place_label", "requested_facts", "scope_change"]}}
        clarification["required"].append("missing_slots")
        choices.append({"type": "object", "additionalProperties": False,
            "properties": {"kind": {"const": "refusal"}, "reason_code": {"type": "string",
                "enum": ["UNSUPPORTED_TOOL", "PRIVATE_SOURCE", "EXTERNAL_EGRESS",
                         "CONFIRMED_IDENTITY", "OUT_OF_SCOPE"]}},
            "required": ["kind", "reason_code"]})
        selectors = []
        for receipt in evidence_receipts:
            if (receipt.get("status") != "OK" or not receipt.get("evidence")
                or receipt["result"].get("detail_withheld")):
                continue
            refs = [r["row_ref"] for r in receipt["evidence"]["rows"]]
            row_schema = ({"type": "array", "maxItems": len(refs), "uniqueItems": True,
                           "items": {"type": "string", "enum": refs}} if refs else
                          {"type": "array", "maxItems": 0})
            selectors.append({"type": "object", "additionalProperties": False,
                "properties": {"receipt_ref": {"const": receipt["receipt_ref"]},
                               "row_refs": row_schema}, "required": ["receipt_ref", "row_refs"]})
        if selectors and not goal_required:
            choices.append({"type": "object", "additionalProperties": False,
                "properties": {"kind": {"const": "answer"}, "selections": {
                    "type": "array", "minItems": 1, "maxItems": 16,
                    "items": {"anyOf": selectors}}}, "required": ["kind", "selections"]})
    elif citations:
        choices.append({"type": "object", "additionalProperties": False,
                        "properties": {"kind": {"const": "answer"},
                            "text": {"type": "string", "minLength": 1, "maxLength": 1200},
                            "citations": {"type": "array", "minItems": 1, "maxItems": 8,
                                          "items": {"type": "string", "enum": citations}}},
                        "required": ["kind", "text", "citations"]})
    return {"anyOf": choices}


def validate_tool_call(binding: AgentBinding, tool: str, params: object, *,
                       cameras: list[str], window: list[float], issued_refs: set[str],
                       region_ids: set[str], issued_cursors: set[str] | None = None
                       ) -> dict[str, Any]:
    if tool not in binding.allowed_tools or tool not in REQUEST_TYPES:
        raise AgentDenied("AGENT_TOOL_DENIED")
    if not isinstance(params, dict) or "session_ref" in params:
        raise AgentDenied("AGENT_INVALID_TOOL_ARGUMENTS")
    try:
        request = REQUEST_TYPES[tool].model_validate(params | {"session_ref": binding.session_ref})
    except (ValueError, TypeError):
        raise AgentDenied("AGENT_INVALID_TOOL_ARGUMENTS") from None
    values = request.model_dump(mode="json", exclude={"session_ref"}, exclude_none=True)
    if "time_range" in values:
        start, end = values["time_range"]
        if start < window[0] or end > window[1]:
            raise AgentDenied("AGENT_WINDOW_DENIED")
        if values.get("camera_ref") not in cameras:
            raise AgentDenied("AGENT_LOCAL_CAMERA_REQUIRED")
    if "timestamp" in values and not window[0] <= values["timestamp"] <= window[1]:
        raise AgentDenied("AGENT_WINDOW_DENIED")
    if values.get("region_id") and values["region_id"] not in region_ids:
        raise AgentDenied("AGENT_REGION_DENIED")
    if values.get("cursor") and (issued_cursors is None or values["cursor"] not in issued_cursors):
        raise AgentDenied("AGENT_CURSOR_NOT_ISSUED")
    for key, value in values.items():
        if key.endswith("_ref") and value not in issued_refs:
            raise AgentDenied("AGENT_REFERENCE_NOT_ISSUED")
        if key.endswith("_refs") and not set(value) <= issued_refs:
            raise AgentDenied("AGENT_REFERENCE_NOT_ISSUED")
    if "camera_ref" in values and values["camera_ref"] not in cameras:
        raise AgentDenied("AGENT_CAMERA_DENIED")
    if "limit" in values:
        values["limit"] = min(values["limit"], 12)
    if "top_k" in values:
        values["top_k"] = min(values["top_k"], 8)
    return values


_BINARY_KEYS = {"base64", "content_base64", "images", "image", "pixels"}
_PRIVATE_KEYS = {
    "ground_truth", "gt", "truth", "actor_id", "actor_identity", "gt_actor_id", "recipe",
    "relative_path", "absolute_path", "private_path", "media_root", "source_path", "secret",
    "recovery_token", "password", "api_key",
}


def sanitize_result(value: object) -> Any:
    """Fail closed on private fields; binary images never enter model messages."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise AgentDenied("AGENT_PRIVATE_TOOL_RESULT_DENIED")
            normalized = key.casefold().replace("-", "_")
            if normalized in _PRIVATE_KEYS or normalized.startswith("gt_"):
                raise AgentDenied("AGENT_PRIVATE_TOOL_RESULT_DENIED")
            if key in _BINARY_KEYS:
                result["binary_media_omitted"] = True
            elif key != "session_ref":
                result[key] = sanitize_result(child)
        return result
    if isinstance(value, (tuple, list)):
        return [sanitize_result(child) for child in value]
    if isinstance(value, str):
        if (value.startswith(("/", "\\\\", "file://")) or any(token in value for token in (
            "/Users/", "/private/", "/home/", "/tmp/", "file://", "../"))):
            raise AgentDenied("AGENT_PRIVATE_TOOL_RESULT_DENIED")
        return value
    if value is None or isinstance(value, (int, float, bool)):
        if isinstance(value, float) and not math.isfinite(value):
            raise AgentDenied("AGENT_INVALID_TOOL_RESULT")
        return value
    raise AgentDenied("AGENT_INVALID_TOOL_RESULT")


def issued_references(value: object) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith("_ref") and isinstance(child, str):
                refs.add(child)
            elif key.endswith("_refs") and isinstance(child, list):
                refs.update(v for v in child if isinstance(v, str))
            refs.update(issued_references(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(issued_references(child))
    return refs


def bounded_result(value: dict[str, Any], max_chars: int) -> dict[str, Any]:
    """Keep original prefixes and mark every presentation truncation explicitly."""
    exported = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    if len(json.dumps(exported, ensure_ascii=False)) <= max_chars:
        return {"data": exported, "presentation_truncated": False}
    exported = _metadata_projection(exported)
    if len(json.dumps(exported, ensure_ascii=False)) <= max_chars:
        return {"data": exported, "presentation_truncated": True,
                "model_metadata_projection": True, "geometry_computed_by_model": False}
    if isinstance(exported.get("candidates"), list) and all(
        isinstance(row, dict) and isinstance(row.get("candidate_id"), str)
        for row in exported["candidates"]
    ):
        exported = _detail_metadata(exported)
        if len(json.dumps(exported, ensure_ascii=False)) <= max_chars:
            return {"data": exported, "presentation_truncated": True,
                    "model_metadata_projection": True, "geometry_computed_by_model": False}
    # Summary pages are truncated only at complete item boundaries; no candidate reordering.
    if isinstance(exported.get("items"), list):
        original_count = len(exported["items"])
        while exported["items"] and len(json.dumps(exported, ensure_ascii=False)) > max_chars:
            exported["items"].pop()
        if len(json.dumps(exported, ensure_ascii=False)) <= max_chars:
            return {"data": exported, "presentation_truncated": True,
                    "original_item_count": original_count,
                    "visible_item_count": len(exported["items"])}
    # An indivisible detail is withheld rather than turning a partial path into evidence.
    return {"data": {}, "presentation_truncated": True,
            "detail_withheld": True, "reason": "MODEL_CONTEXT_BUDGET"}


def _metadata_projection(value: Any) -> Any:
    """Remove bulky coordinates/features, preserving IDs, counts and list order."""
    if isinstance(value, dict):
        if "event_ref" in value and "candidate_count" in value and "candidates" not in value:
            fields = {"event_ref", "kind", "time_range", "camera_ids", "camera_refs",
                      "local_track_refs", "candidate_count", "hypothesis_count", "uncertainty",
                      "evidence_state", "origin", "authority", "missing_evidence", "complete",
                      "termination_reason", "support_state", "detail_ref", "replay_ref",
                      "alternatives"}
            return {k: v for k, v in value.items() if k in fields} | {
                "additional_source_metadata_omitted_for_model_context": True}
        output: dict[str, Any] = {}
        for key, child in value.items():
            if key == "scope":
                continue  # The validated binding is supplied separately in every prompt.
            if (key in {"event_id", "canonical_event_id", "canonical_observation_id",
                        "config_version", "rule_version", "segment_refs", "association_refs"}
                or key.endswith("_sha256")):
                continue
            if key in {"media_refs", "camera_refs"} and isinstance(child, list):
                # Keep camera refs for next bounded lookups; media binary tools are not exposed.
                if key == "camera_refs":
                    output[key] = child
                else:
                    output[key + "_count"] = len(child)
                    output[key + "_omitted_for_model_context"] = True
                continue
            if key in {"projected_path", "polyline", "timed_points", "visible_features",
                       "measurements", "segments"} and isinstance(child, list):
                output[key + "_count"] = len(child)
                output[key + "_omitted_for_model_context"] = True
            elif key in {"trajectories", "hypotheses"} and isinstance(child, list):
                output[key + "_count"] = len(child)
                output[key + "_preview_original_order"] = [
                    _metadata_projection(row) for row in child[:4]]
                output[key + "_preview_complete"] = len(child) <= 4
            else:
                output[key] = _metadata_projection(child)
        return output
    if isinstance(value, list):
        return [_metadata_projection(child) for child in value]
    return value


def _detail_metadata(value: dict[str, Any]) -> dict[str, Any]:
    fields = {"event_ref", "kind", "time_range", "camera_ids", "candidate_count",
              "hypothesis_count", "uncertainty", "evidence_state", "origin", "authority",
              "missing_evidence", "supports", "conflicts", "complete", "termination_reason",
              "support_state", "detail_ref", "replay_ref", "local_track_refs", "region_ids"}
    output = {k: v for k, v in value.items() if k in fields}
    candidate_fields = {"candidate_id", "path_length", "minimum_travel_time",
                        "estimated_travel_time", "path_score", "feasibility_flags", "provenance"}
    output["candidates_metadata_original_order"] = [
        {k: v for k, v in row.items() if k in candidate_fields} for row in value["candidates"]]
    output["candidate_metadata_count"] = len(value["candidates"])
    output["geometry_and_hypothesis_details_omitted_for_model_context"] = True
    output["full_source_details_available_in_workbench"] = True
    return output
