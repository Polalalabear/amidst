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
    r"\bfirst(?:\s+(?:registered|returned|listed|matching|available|query|source[- ]ordered))*"
    r"\s+(?:event|record|entry|result|item|row|candidate)\b|\bhead\s+(?:entry|record|item)\b|"
    r"(?:第[一1]|首)(?:個|个|筆|笔|條|条|項|项)?"
    r"(?:回傳的?|返回的?|來源排序的?|来源排序的?|已註冊的?|已注册的?|候選|候选)?"
    r"(?:事件|記錄|紀錄|记录|項目|项目|結果|结果|資料|资料)", re.IGNORECASE)
_DETAIL = re.compile(r"get_event_detail|\b(?:details?|detailed)\b|詳情|详情|詳細|详细|細節|细节|"
                     r"\b(?:full|expanded|entire|complete)\s+(?:event|record|entry|payload)\b|"
                     r"\b(?:event|record|entry)\s+in\s+full\b|"
                     r"完整(?:事件|記錄|紀錄|记录)|展開(?:事件|記錄|紀錄|记录)|"
                     r"\b(?:explain|describe|expand)\s+(?:the\s+)?"
                     r"(?:first(?:\s+(?:returned|listed|registered|source[- ]ordered))*\s+)?"
                     r"(?:event|record|entry|result|item)\b|"
                     r"(?:說明|说明|解釋|解释)(?:第[一1]|首)?(?:筆|笔|個|个|項|项)?"
                     r"(?:回傳的?|返回的?)?(?:事件|記錄|紀錄|记录)", re.IGNORECASE)
_READ = re.compile(
    r"\b(?:read|get|inspect|check|show|list|query|retrieve|describe|explain|provide|give|"
    r"tell|present|open|view|display|expand|fetch|want|need|use)\b|"
    r"讀|读|查|列|顯示|显示|說明|说明|解釋|解释|提供|給|给|展示|展開|展开|檢視|检视|打開|打开",
    re.IGNORECASE)
_IMPLICIT_FIRST = re.compile(r"\bfirst\s+one\b|第一[筆笔個个](?!欄位|字段)|"
                             r"\b(?:earliest|oldest|top[- ]ranked)\s+(?:event|record|entry)\b",
                             re.IGNORECASE)
_FIELD_INTENT = re.compile(r"\b(?:read|show|list|include|keep|retain|preserve|omit|exclude)\b|"
                           r"讀|读|查|列|保留|欄位|字段", re.IGNORECASE)
_ALL = re.compile(r"\b(?:read|list|show|retrieve|query)\s+(?:all|every)\s+"
                  r"(?:registered\s+)?(?:events?|pages?)\b|"
                  r"(?:讀取|读取|查完|列出|顯示|显示)(?:全部|所有)(?:事件|頁|页)", re.IGNORECASE)
_NUMBER = (r"[0-9]+|(?:ninety|eighty|seventy|sixty|fifty|forty|thirty|twenty)"
           r"(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|nineteen|eighteen|"
           r"seventeen|sixteen|fifteen|fourteen|thirteen|twelve|eleven|ten|nine|eight|seven|"
           r"six|five|four|three|two|one|zero|[一二三四五六七八九]?十[一二三四五六七八九]?|"
           r"[零一兩两二三四五六七八九]")
_PAGES = re.compile(r"\b(" + _NUMBER + r")\s+pages?\b|"
                    r"(?<![第0-9一兩两二三四五六七八九十])(" + _NUMBER + r")\s*[頁页]",
                    re.IGNORECASE)
_PAGE_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "一": 1, "兩": 2, "两": 2,
                 "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8}
_PAGE_NUMBERS.update({"nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
                      "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
                      "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
                      "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
                      "ninety": 90, "zero": 0, "零": 0, "九": 9})
_FIELD_LIST = re.compile(r"(?:(?:fields?|attributes?|DTO\s*fields?)\b|欄位|字段)\s*[:：]?\s*"
                         r"(?!(?:from|for|to|of|are|were|should|with|that|which|and|or|like)\b)"
                         r"([a-z_][a-z_0-9]*(?:\s*[,，、]\s*[a-z_][a-z_0-9]*)*)",
                         re.IGNORECASE)
_IDENTIFIER = re.compile(r"(?<![A-Za-z0-9_])([a-z][a-z_]*_[a-z_]+)(?![A-Za-z0-9_])")
_CODE_FIELD = re.compile(r"`([a-z][a-z_]*)`")
_DIRECT_FIELD = re.compile(r"\b(?:include|omit|exclude|keep|retain|preserve)\s+"
                           r"(?:the\s+)?([a-z][a-z_]*)\b", re.IGNORECASE)
_PAGE_SIZE = re.compile(
    r"\b(?:limit|page[_ ]size)\s*(?:[=:]|of\b|to\b|is\b)?\s*(-?(?:" + _NUMBER + r"))\b|"
    r"每[頁页]\s*(?:最多|至多|上限|限|各)?\s*(" + _NUMBER + r")\s*(?:筆|笔|項|项|個|个|條|条)|"
    r"\b(" + _NUMBER + r")\s+(?:events?|records?|items?|rows?)\s+per\s+page\b",
    re.IGNORECASE)
_PAGE_CHOICE = re.compile(r"(?:" + _NUMBER + r")\s*(?:pages?|[頁页])?\s*"
                          r"(?:or\b|或|還是|还是)\s*(?:" + _NUMBER + r")\s*(?:pages?|[頁页])",
                          re.IGNORECASE)
_FIRST_PAGE_CHOICE = re.compile(r"(?:first\s+page|第一[頁页])\s*"
                                r"(?:or\b|或|還是|还是)\s*(?:" + _NUMBER + r")\s*"
                                r"(?:pages?|[頁页])", re.IGNORECASE)


class ExplicitRequirements(DomainModel):
    schema_version: Literal["local.agent.explicit-requirements.v2"] = (
        "local.agent.explicit-requirements.v2")
    request_sha256: Sha256
    requested_fields: tuple[str, ...] = ()
    first_event: bool = False
    event_detail: bool = False
    page_count: int | None = Field(default=None, ge=1, le=16)
    page_size: int | None = Field(default=None, ge=1, le=12)
    whole_collection: bool = False
    unsupported_literal_fields: tuple[str, ...] = ()
    ambiguous_dimensions: tuple[str, ...] = ()


class RequirementFeedback(ValueError):
    def __init__(self, unmet: list[str]) -> None:
        self.unmet = tuple(dict.fromkeys(unmet))
        super().__init__("AGENT_EXPLICIT_REQUIREMENTS_UNMET")


def _literal_slot(offset: int, lists: list[re.Match[str]], codes: list[re.Match[str]]) -> bool:
    return (any(m.start(1) <= offset < m.end(1) for m in lists) or
            any(m.start() <= offset < m.end() for m in codes))


def _page_number(token: str) -> int:
    token = token.lower()
    if token.startswith("-"):
        return -_page_number(token[1:])
    if token.lstrip("-").isdigit():
        return int(token)
    compound = re.split(r"[- ]", token)
    if len(compound) == 2:
        return _PAGE_NUMBERS[compound[0]] + _PAGE_NUMBERS[compound[1]]
    if "十" in token:
        before, after = token.split("十")
        return (1 if not before else _PAGE_NUMBERS[before]) * 10 + (
            0 if not after else _PAGE_NUMBERS[after])
    return _PAGE_NUMBERS[token]


def public_fact_refinement(original: str, replies: list[str]) -> dict[str, Any] | None:
    """Focus a clearly narrowed human reply; retain the whole original audit and safety context."""
    if not replies:
        return None
    reply = replies[-1]
    public_events = re.search(r"\b(?:registered|public|existing|frozen)"
                              r"(?:\s+(?:registered|public|existing|frozen))*\s+events?\b|"
                              r"(?:已註冊|已注册|註冊|注册|已登記|已登记|登記|登记|已有|現有|"
                              r"现有|公開|公开|凍結|冻结)事件",
                              reply, re.IGNORECASE)
    facts_only = re.search(r"\bfact[- ]only\b|\bonly\b.*\b(?:events?|fields?|facts?)\b|"
                           r"(?:只|僅|仅)(?:查|讀|读|列|要|保留).*?(?:事件|欄位|字段)",
                           reply, re.IGNORECASE)
    sensitive = {
        "identity": re.compile(r"\b(?:identify|identity|identification|real\s+name|"
            r"who\s+(?:is|are)|who\s+(?:they|he|she)\s+(?:are|is))\b|"
            r"確認.*?(?:身分|身份)|确认.*?(?:身分|身份)|真實姓名|真实姓名", re.IGNORECASE),
        "private": re.compile(r"\b(?:private|ground[_ ]truth|GT|credentials?|secrets?)\b|"
                              r"私有|私密", re.IGNORECASE)}
    identity_withdrawal = re.compile(
                           r"\b(?:drop|withdraw|cancel)\b.*?\b(?:identity|identification)\b|"
                           r"\b(?:no|without)\s+(?:identity|identification)\b|"
                           r"\bdo\s+not\s+identify\b|"
                           r"取消.*?(?:身分|身份)|(?:不|不要|不用|不需)"
                           r"(?:做|查|判定|確認|确认|推斷|推断).*?(?:身分|身份)",
                           re.IGNORECASE)
    private_withdrawal = re.compile(r"\b(?:drop|withdraw|cancel)\b.*?\b(?:private|GT|"
        r"ground[_ ]truth|credentials?|secrets?)\b|\b(?:no|without)\s+private\b|"
        r"\bdo\s+not\s+read\s+private\b|取消.*?(?:私有|私密)|"
        r"(?:不要|不用|不需|不讀|不读).*?(?:私有|私密|GT)", re.IGNORECASE)
    pending: set[str] = set()
    for text in [original, *replies]:
        clauses = re.split(r"[。；;!?！？\n]|\.(?=\s|$)|\bbut\b|但是|而是", text,
                           flags=re.IGNORECASE)
        for clause in clauses:
            events: list[tuple[int, str, str]] = []
            for kind, withdrawal in (("identity", identity_withdrawal),
                                     ("private", private_withdrawal)):
                withdrawals = list(withdrawal.finditer(clause))
                withdrawn = [w for w in withdrawals
                             if not _negative(clause, w.start(), literal=False)
                             and not any(_negative(clause, w.start() + cancel.start(),
                                                   literal=False)
                                 for cancel in re.finditer(r"\b(?:drop|withdraw|cancel)\b|取消",
                                     w.group(), re.IGNORECASE))]
                events.extend((w.end(), "retain", kind) for w in withdrawals if w not in withdrawn)
                events.extend((w.end(), "withdraw", kind) for w in withdrawn)
                events.extend((m.end(), "request", kind) for m in sensitive[kind].finditer(clause)
                    if not _negative(clause, m.start(), literal=False) and
                    not any(w.start() <= m.start() < w.end() for w in withdrawn))
            for _, event, kind in sorted(events):
                if event == "withdraw":
                    pending.discard(kind)
                else:
                    pending.add(kind)
    if not public_events or not facts_only or pending:
        return None
    return {"status": "HUMAN_NARROWED_PUBLIC_EVENT_FACTS", "request": reply,
            "reply_sha256": digest(reply), "original_retained_for_audit": True,
            "source_scope_changed": False}


def _negative(fragment: str, offset: int, *, literal: bool = True) -> bool:
    prefix = fragment[:offset]
    last_clause = re.split(r"[,，]", prefix)[-1]
    if _FIELD_INTENT.search(last_clause) or _READ.search(last_clause):
        prefix = last_clause
    matches = list(_NEGATION.finditer(prefix))
    if not matches:
        return False
    tail = prefix[matches[-1].end():]
    # A prohibition on interpretation/translation does not forbid reading a literal field.
    if literal and re.match(
                r"\s*(?:infer|claim|confirm|identify|translat\w*|推斷|推断|確認|确认|翻譯|翻译)",
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
    unsupported_fields: set[str] = set()
    for text in [original, *replies]:
        positive: dict[str, set[Any]] = {key: set() for key in values}
        negative: dict[str, set[Any]] = {key: set() for key in values}
        positive_fields: set[str] = set()
        negative_fields: set[str] = set()
        invalid_dimensions: set[str] = set()
        known_first = False
        unresolved_first = False
        first_page_positive = False
        first_page_negative = False
        for fragment in re.split(r"[。；;!?！？\n]|\.(?=\s|$)|\bbut\b|但是|而是", text,
                                  flags=re.IGNORECASE):
            lists = list(_FIELD_LIST.finditer(fragment))
            codes = list(_CODE_FIELD.finditer(fragment))

            first_matches = [m for m in _FIRST_EVENT.finditer(fragment)
                             if not _literal_slot(m.start(), lists, codes)]
            for match in first_matches:
                known_first = True
                (negative if _negative(fragment, match.start(), literal=False) else positive)[
                    "first_event"].add(True)
            if any(not _negative(fragment, m.start(), literal=False)
                   and not _literal_slot(m.start(), lists, codes)
                   and not any(first.start() <= m.start() < first.end() for first in first_matches)
                   for m in _IMPLICIT_FIRST.finditer(fragment)):
                unresolved_first = True
            for match in _DETAIL.finditer(fragment):
                exact_tool = match.group().lower() == "get_event_detail"
                if _literal_slot(match.start(), lists, codes) and not exact_tool:
                    continue
                polite_noun_request = re.search(r"\bdetails?\s*(?:please|for|of|about)\b|"
                                                 r"請.*(?:詳情|详情|細節|细节)", fragment,
                                                 re.IGNORECASE)
                if not (_READ.search(fragment) or exact_tool or polite_noun_request):
                    if not _negative(fragment, match.start(), literal=False):
                        ambiguous.add("detail_intent")
                    continue
                ambiguous.discard("detail_intent")
                (negative if _negative(fragment, match.start(), literal=False) else positive)[
                    "event_detail"].add(True)
            for match in _ALL.finditer(fragment):
                (negative if _negative(fragment, match.start()) else positive)[
                    "whole_collection"].add(True)
            for match in _PAGES.finditer(fragment):
                token = (match.group(1) or match.group(2)).lower()
                if re.search(r"第\s*$", fragment[:match.start()]):
                    continue
                count = _page_number(token)
                if not 1 <= count <= 16:
                    invalid_dimensions.add("page_count")
                else:
                    (negative if _negative(fragment, match.start()) else positive)[
                        "page_count"].add(count)
            for match in re.finditer(r"first\s+page|第一[頁页]", fragment, re.IGNORECASE):
                if _negative(fragment, match.start()):
                    first_page_negative = True
                else:
                    first_page_positive = True
            if _PAGE_CHOICE.search(fragment) or _FIRST_PAGE_CHOICE.search(fragment):
                invalid_dimensions.add("page_count")
            for match in _PAGE_SIZE.finditer(fragment):
                size = _page_number(match.group(1) or match.group(2) or match.group(3))
                if not 1 <= size <= 12:
                    invalid_dimensions.add("page_size")
                else:
                    (negative if _negative(fragment, match.start()) else positive)[
                        "page_size"].add(size)
            identifiers = list(_CODE_FIELD.finditer(fragment))
            identifiers += [m for m in _DIRECT_FIELD.finditer(fragment)
                            if m.group(1).lower() in FACT_FIELDS]
            if _FIELD_INTENT.search(fragment) or _READ.search(fragment):
                identifiers += list(_IDENTIFIER.finditer(fragment))
            for match in identifiers:
                if any(field_list.start(1) <= match.start() < field_list.end(1)
                       for field_list in lists):
                    continue
                name = match.group(1).lower()
                if name in FACT_FIELDS:
                    (negative_fields if _negative(fragment, match.start(1))
                     else positive_fields).add(name)
                elif name not in {"get_event_detail", "page_size"}:
                    if _negative(fragment, match.start()):
                        unsupported_fields.discard(name)
                    else:
                        unsupported_fields.add(name)
            for match in lists:
                names = {name.strip().lower() for name in re.split(r"[,，、]", match.group(1))}
                unknown = names - FACT_FIELDS
                if _negative(fragment, match.start()):
                    unsupported_fields.difference_update(unknown)
                else:
                    unsupported_fields.update(unknown)
                names.intersection_update(FACT_FIELDS)
                (negative_fields if _negative(fragment, match.start())
                 else positive_fields).update(names)
        conflicts = positive_fields.intersection(negative_fields)
        # A root-page instruction is a step, not a conflicting total cardinality.
        if first_page_positive and not positive["page_count"]:
            positive["page_count"].add(1)
        if first_page_negative and not negative["page_count"] and not positive["page_count"]:
            negative["page_count"].add(1)
        if unresolved_first:
            ambiguous.add("first_resource_or_order")
        elif known_first:
            ambiguous.discard("first_resource_or_order")
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
            elif key == "page_count" and len(yes) > 1:
                ambiguous.add(key)
            elif yes:
                values[key] = max(yes) if key in {"page_count", "page_size"} else True
                ambiguous.discard(key)
            elif no:
                values[key] = None if key in {"page_count", "page_size"} else False
                ambiguous.discard(key)
    if field_conflicts:
        ambiguous.add("requested_fields")
    if unsupported_fields:
        ambiguous.add("unsupported_literal_fields")
    return ExplicitRequirements(request_sha256=digest({"original": original, "replies": replies}),
        requested_fields=tuple(sorted(fields)), ambiguous_dimensions=tuple(sorted(ambiguous)),
        unsupported_literal_fields=tuple(sorted(unsupported_fields)),
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
