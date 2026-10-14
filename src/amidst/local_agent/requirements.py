"""Trusted explicit request constraints; never an answer, oracle or tool router."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import Field

from amidst.domain.common import DomainModel
from amidst.engineering.access import digest
from amidst.engineering.registry import Sha256

from .contracts import RequestGoal
from .evidence import FACT_FIELDS

_NEGATION = re.compile(
    r"\b(?:do not|don't|must not|never|without|no need to|not)\b|"
    r"不要|不需|無需|无需|不用|不必|別|别|不讀|不读|不查|不列|不是|不只|不僅|不仅", re.IGNORECASE)
_FIRST_EVENT = re.compile(
    r"\bfirst(?:\s+(?:registered|source[- ]ordered))?\s+event\b|"
    r"(?:第[一1]個|第一个|首個|首个)(?:候選|候选)?事件", re.IGNORECASE)
_DETAIL = re.compile(r"get_event_detail|\bdetails?\b|詳情|详情|詳細|详细", re.IGNORECASE)
_READ = re.compile(r"\b(?:read|get|inspect|check|show|list|query|retrieve)\b|"
                   r"讀|读|查|列|顯示|显示", re.IGNORECASE)
_FIELD_INTENT = re.compile(r"\b(?:read|show|list|include|keep|retain|preserve|omit|exclude)\b|"
                           r"讀|读|查|列|保留|欄位|字段", re.IGNORECASE)
_ALL = re.compile(r"\b(?:read|list|show|retrieve|query)\s+(?:all|every)\s+"
                  r"(?:registered\s+)?(?:events?|pages?)\b|"
                  r"(?:讀取|读取|查完|列出|顯示|显示)(?:全部|所有)(?:事件|頁|页)", re.IGNORECASE)
_PAGES = re.compile(r"\b([0-9]+|one|two|three|four|five|six|seven|eight)\s+pages?\b|"
                    r"(?<!第)([0-9]+|一|兩|两|二|三|四|五|六|七|八)\s*[頁页]", re.IGNORECASE)
_PAGE_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "一": 1, "兩": 2, "两": 2,
                 "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8}
_FIELD_LIST = re.compile(r"(?:fields?|attributes?|DTO\s*fields?|欄位|字段)\s*[:：]?\s*"
                         r"([a-z_][a-z_0-9]*(?:\s*[,，、]\s*[a-z_][a-z_0-9]*)*)",
                         re.IGNORECASE)
_IDENTIFIER = re.compile(r"(?<![A-Za-z0-9_])([a-z][a-z_]*_[a-z_]+)(?![A-Za-z0-9_])")
_CODE_FIELD = re.compile(r"`([a-z][a-z_]*)`")
_PAGE_SIZE = re.compile(r"\b(?:limit|page[_ ]size)\s*[=:]\s*(-?[0-9]+)\b|"
                        r"每[頁页]\s*([0-9]+)\s*(?:筆|笔|項|项|個|个|rows?\b)",
                        re.IGNORECASE)


class ExplicitRequirements(DomainModel):
    schema_version: Literal["local.agent.explicit-requirements.v1"] = (
        "local.agent.explicit-requirements.v1")
    request_sha256: Sha256
    requested_fields: tuple[str, ...] = ()
    first_event: bool = False
    event_detail: bool = False
    page_count: int | None = Field(default=None, ge=1, le=16)
    page_size: int | None = Field(default=None, ge=1, le=12)
    whole_collection: bool = False
    ambiguous_dimensions: tuple[str, ...] = ()


class RequirementFeedback(ValueError):
    def __init__(self, unmet: list[str]) -> None:
        self.unmet = tuple(dict.fromkeys(unmet))
        super().__init__("AGENT_EXPLICIT_REQUIREMENTS_UNMET")


def _negative(fragment: str, offset: int) -> bool:
    prefix = fragment[:offset]
    last_clause = re.split(r"[,，]", prefix)[-1]
    if _FIELD_INTENT.search(last_clause):
        prefix = last_clause
    matches = list(_NEGATION.finditer(prefix))
    if not matches:
        return False
    tail = prefix[matches[-1].end():]
    # A prohibition on interpretation/translation does not forbid reading a literal field.
    if re.match(r"\s*(?:infer|claim|confirm|identify|translat\w*|推斷|推断|確認|确认|翻譯|翻译)",
                tail, re.IGNORECASE):
        return False
    return True


def derive_requirements(original: str, replies: list[str]) -> ExplicitRequirements:
    """Parse explicit constraints only from human text, never receipt/source text.

    Later clear human clarification can resolve or amend the same dimension. Unclear
    negation is retained as a clarification obligation, not silently guessed.
    """
    fields: set[str] = set()
    values: dict[str, Any] = {"first_event": False, "event_detail": False,
                              "whole_collection": False, "page_count": None, "page_size": None}
    ambiguous: set[str] = set()
    field_conflicts: set[str] = set()
    for text in [original, *replies]:
        positive: dict[str, set[Any]] = {key: set() for key in values}
        negative: dict[str, set[Any]] = {key: set() for key in values}
        positive_fields: set[str] = set()
        negative_fields: set[str] = set()
        invalid_dimensions: set[str] = set()
        for fragment in re.split(r"[。；;!?！？\n]|\.(?=\s|$)|\bbut\b|但是|而是", text,
                                  flags=re.IGNORECASE):
            for match in _FIRST_EVENT.finditer(fragment):
                (negative if _negative(fragment, match.start()) else positive)[
                    "first_event"].add(True)
            for match in _DETAIL.finditer(fragment):
                # Require an affirmative read instruction or the exact public tool name.
                if not (_READ.search(fragment) or match.group().lower() == "get_event_detail"):
                    continue
                (negative if _negative(fragment, match.start()) else positive)[
                    "event_detail"].add(True)
            for match in _ALL.finditer(fragment):
                (negative if _negative(fragment, match.start()) else positive)[
                    "whole_collection"].add(True)
            for match in _PAGES.finditer(fragment):
                token = (match.group(1) or match.group(2)).lower()
                count = int(token) if token.isdigit() else _PAGE_NUMBERS[token]
                if not 1 <= count <= 16:
                    invalid_dimensions.add("page_count")
                else:
                    (negative if _negative(fragment, match.start()) else positive)[
                        "page_count"].add(count)
            for match in re.finditer(r"first\s+page|第一[頁页]", fragment, re.IGNORECASE):
                (negative if _negative(fragment, match.start()) else positive)["page_count"].add(1)
            for match in _PAGE_SIZE.finditer(fragment):
                size = int(match.group(1) or match.group(2))
                if not 1 <= size <= 12:
                    invalid_dimensions.add("page_size")
                else:
                    (negative if _negative(fragment, match.start()) else positive)[
                        "page_size"].add(size)
            lists = list(_FIELD_LIST.finditer(fragment))
            identifiers = list(_CODE_FIELD.finditer(fragment))
            if _FIELD_INTENT.search(fragment):
                identifiers += list(_IDENTIFIER.finditer(fragment))
            for match in identifiers:
                if any(field_list.start(1) <= match.start() < field_list.end(1)
                       for field_list in lists):
                    continue
                name = match.group(1).lower()
                if name in FACT_FIELDS:
                    (negative_fields if _negative(fragment, match.start())
                     else positive_fields).add(name)
            for match in lists:
                names = {name.strip().lower() for name in re.split(r"[,，、]", match.group(1))}
                names.intersection_update(FACT_FIELDS)
                (negative_fields if _negative(fragment, match.start())
                 else positive_fields).update(names)
        conflicts = positive_fields.intersection(negative_fields)
        field_conflicts.difference_update((positive_fields | negative_fields) - conflicts)
        field_conflicts.update(conflicts)
        fields.update(positive_fields)
        fields.difference_update(negative_fields - conflicts)
        for key in values:
            yes, no = positive[key], negative[key]
            if key in invalid_dimensions or yes.intersection(no):
                ambiguous.add(key)
            elif key == "page_size" and len(yes) > 1:
                ambiguous.add(key)
            elif key == "page_count" and len(yes) > 1 and (
                len(yes - {1}) > 1 or re.search(r"\bor\b|或|還是|还是", text, re.IGNORECASE)):
                ambiguous.add(key)
            elif yes:
                values[key] = max(yes) if key in {"page_count", "page_size"} else True
                ambiguous.discard(key)
            elif no:
                values[key] = None if key in {"page_count", "page_size"} else False
                ambiguous.discard(key)
    if field_conflicts:
        ambiguous.add("requested_fields")
    return ExplicitRequirements(request_sha256=digest({"original": original, "replies": replies}),
        requested_fields=tuple(sorted(fields)), ambiguous_dimensions=tuple(sorted(ambiguous)),
        **values)


def validate_proposal(requirements: ExplicitRequirements, proposal: RequestGoal) -> None:
    unmet = []
    if requirements.ambiguous_dimensions:
        unmet.append("CLARIFY_CONTRADICTORY_REQUIREMENTS")
    if not set(requirements.requested_fields) <= set(proposal.requested_fields):
        unmet.append("REQUESTED_LITERAL_FIELDS_REQUIRED")
    if requirements.first_event and (proposal.topic != "EVENTS" or proposal.selection != "FIRST"):
        unmet.append("FIRST_EVENT_FINAL_GOAL_REQUIRED")
    if requirements.event_detail and proposal.topic != "EVENTS":
        unmet.append("EVENT_DETAIL_FINAL_GOAL_REQUIRED")
    if requirements.whole_collection and proposal.selection != "ALL":
        unmet.append("WHOLE_COLLECTION_FINAL_GOAL_REQUIRED")
    if unmet:
        raise RequirementFeedback(unmet)


def validate_query_parameters(requirements: ExplicitRequirements, tool: str,
                              arguments: dict[str, Any]) -> None:
    if (tool == "query_events" and requirements.page_size is not None
        and arguments.get("limit") != requirements.page_size):
        raise RequirementFeedback(["REQUESTED_PAGE_SIZE_REQUIRED"])


def validate_completion(requirements: ExplicitRequirements, answer: dict[str, Any],
                        receipts: list[dict[str, Any]]) -> dict[str, Any]:
    """Call after literal/source verification; derive targets only from actual receipts."""
    rows = answer["rows"]
    coverage = answer["coverage"]
    by_ref = {receipt["receipt_ref"]: receipt for receipt in receipts
              if receipt["status"] == "OK"}
    empty_exhausted = not rows and coverage["complete_for_selected_scope"] is True
    unmet = []
    if requirements.ambiguous_dimensions:
        unmet.append("CLARIFY_CONTRADICTORY_REQUIREMENTS")
    if any(not set(requirements.requested_fields) <= set(row["fields"]) for row in rows):
        unmet.append("REQUESTED_LITERAL_FIELDS_REQUIRED")
    collections = [c for c in coverage["collections"] if c["tool"] == "query_events"]
    matching_refs = {collection["receipt_refs"][0] for collection in collections
                     if collection["matches_selected_scope"]
                     and collection["cursor_chain_prefix_valid"]}
    queries = [receipt for receipt in receipts if receipt["status"] == "OK"
               and receipt["tool"] == "query_events" and receipt["receipt_ref"] in matching_refs]
    first = next((item.get("event_ref") for receipt in queries
                  for item in receipt["result"]["data"].get("items", [])), None)
    if requirements.first_event and not empty_exhausted:
        if len(rows) != 1 or first is None or rows[0]["resource_ref"] != first:
            unmet.append("FIRST_EVENT_SELECTION_REQUIRED")
    if requirements.event_detail and not empty_exhausted:
        if not rows or any(by_ref[row["receipt_ref"]]["tool"] != "get_event_detail"
               or row["json_locator"] != [] for row in rows):
            unmet.append("DETAIL_EVIDENCE_RECEIPT_REQUIRED")
    if requirements.page_count is not None:
        for camera in answer["scope"]["camera_refs"]:
            matching = [c for c in collections if c["camera_ref"] == camera
                        and c["matches_selected_scope"]]
            if not matching or any(len(c["pages"]) > requirements.page_count or
                len(c["pages"]) < requirements.page_count and not c["cursor_chain_complete"]
                for c in matching):
                unmet.append("REQUESTED_PAGE_CHAIN_REQUIRED")
            if any(not c["cursor_chain_prefix_valid"] for c in matching):
                unmet.append("REQUESTED_PAGE_CHAIN_REQUIRED")
            if (not requirements.first_event and not requirements.event_detail
                and any(not c["presentation_rows_complete"] for c in matching)):
                unmet.append("REQUESTED_PAGE_ROWS_REQUIRED")
            if (not requirements.first_event and not requirements.event_detail
                and any(c["returned_count"] != c["selected_count"] for c in matching)):
                unmet.append("REQUESTED_PAGE_ROWS_REQUIRED")
    if requirements.page_size is not None:
        scoped = [c for c in collections if c["matches_selected_scope"]]
        if not scoped or any(by_ref[ref]["arguments"].get("limit") != requirements.page_size
                             for collection in scoped for ref in collection["receipt_refs"]):
            unmet.append("REQUESTED_PAGE_SIZE_REQUIRED")
    if requirements.whole_collection and not coverage["complete_for_selected_scope"]:
        unmet.append("WHOLE_COLLECTION_EXHAUSTION_REQUIRED")
    if unmet:
        raise RequirementFeedback(unmet)
    return {"status": "EXPLICIT_REQUEST_CONSTRAINTS_VERIFIED",
            "version": requirements.schema_version, "request_sha256": requirements.request_sha256,
            "semantic_goal_understanding": "REQUIRES_INDEPENDENT_ORACLE"}
