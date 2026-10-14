"""Server-bound local Agent contracts; model output never grants authority."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, model_validator

from amidst.domain.common import DomainModel, Timestamp
from amidst.engineering.access import Mode
from amidst.engineering.registry import ResourceRef, Sha256


class AgentDenied(ValueError):
    """Fixed public error codes, never rejected inputs or private exceptions."""


class AgentCamera(DomainModel):
    camera_id: str = Field(min_length=1, max_length=120)
    camera_ref: ResourceRef
    region_ids: tuple[str, ...] = ()


class AgentBinding(DomainModel):
    scene_id: str = Field(min_length=1, max_length=100)
    session_ref: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=200)
    run_ref: ResourceRef
    source_ref: str = Field(min_length=1, max_length=160)
    source_sha256: Sha256
    observation_mode: Mode
    decision_stage: Literal["RESULTS"] = "RESULTS"
    freeze_ref: str = Field(min_length=1, max_length=160)
    product_freeze_ref: str = Field(min_length=1, max_length=160)
    config_sha256: Sha256
    allowed_tools: tuple[str, ...] = Field(min_length=1, max_length=13)
    cameras: tuple[AgentCamera, ...] = Field(min_length=1, max_length=32)
    time_range: tuple[Timestamp, Timestamp]

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.time_range[1] < self.time_range[0]:
            raise ValueError("invalid source window")
        if len({c.camera_ref for c in self.cameras}) != len(self.cameras):
            raise ValueError("duplicate camera")
        return self


class AgentPolicy(DomainModel):
    max_model_calls: int = Field(default=12, ge=1, le=24, strict=True)
    max_tool_calls: int = Field(default=8, ge=1, le=16, strict=True)
    max_total_tokens: int = Field(default=24000, ge=128, le=48000, strict=True)
    max_elapsed_seconds: float = Field(default=300, gt=0, le=900)
    max_prompt_chars: int = Field(default=24000, ge=4000, le=24000, strict=True)
    max_result_chars: int = Field(default=6000, ge=512, le=16000, strict=True)
    max_output_tokens: int = Field(default=768, ge=128, le=1024, strict=True)
    max_window_seconds: float = Field(default=120, gt=0, le=120)


ResponseLanguage = Literal["zh-Hant", "en"]
RefusalReason = Literal[
    "UNSUPPORTED_TOOL", "PRIVATE_SOURCE", "EXTERNAL_EGRESS", "CONFIRMED_IDENTITY", "OUT_OF_SCOPE",
]
MissingSlot = Literal["target", "place_label", "requested_facts", "scope_change"]
FactField = Annotated[str, Field(pattern=r"^[a-z][a-z_]{0,59}$")]


class RequestGoal(DomainModel):
    topic: Literal["EVENTS", "OBSERVATIONS", "CAMERAS", "PLACES", "APPEARANCE", "STITCHES",
                   "TRAJECTORIES", "MEDIA", "REPLAY"]
    selection: Literal["PAGE", "FIRST", "ALL", "DETAIL"]
    requested_fields: tuple[FactField, ...] = Field(default=(), max_length=20)


class EvidenceSelection(DomainModel):
    receipt_ref: str = Field(pattern=r"^receipt:[A-Za-z0-9_-]{1,80}$")
    row_refs: tuple[ResourceRef, ...] = Field(default=(), max_length=128)


class EvidenceRow(DomainModel):
    row_ref: ResourceRef
    resource_ref: str | None = Field(default=None, max_length=200)
    receipt_ref: str
    fields: dict[str, JsonValue]
    json_locator: tuple[str | int, ...]
    source_payload_sha256: Sha256


class CoveragePage(DomainModel):
    receipt_ref: str
    source_truncated: bool | None
    source_returned_count: int | None = Field(ge=0, strict=True)
    visible_returned_count: int | None = Field(ge=0, strict=True)
    presentation_truncated: bool


class CoverageCollection(DomainModel):
    tool: str
    query_sha256: Sha256
    camera_ref: str | None
    time_range_seconds: tuple[Timestamp, Timestamp] | None
    matches_selected_scope: bool
    receipt_refs: tuple[str, ...]
    returned_count: int = Field(ge=0, strict=True)
    selected_count: int = Field(ge=0, strict=True)
    source_truncated: bool
    cursor_chain_prefix_valid: bool
    cursor_chain_complete: bool
    presentation_truncated: bool
    presentation_rows_complete: bool
    registered_total: int | None = Field(ge=0, strict=True)
    pages: tuple[CoveragePage, ...]


class AnswerCoverage(DomainModel):
    collections: tuple[CoverageCollection, ...]
    complete_for_selected_scope: bool
    scope_meaning: Literal["REGISTERED_DTO_COLLECTION_NOT_PERSON_OR_EVENT_TRUTH"]


class AnswerVerification(DomainModel):
    status: Literal["VERIFIED_DTO_FIELDS"]
    version: Literal["v2"]
    binding_sha256: Sha256


class AnswerScope(DomainModel):
    camera_refs: tuple[ResourceRef, ...]
    time_range_seconds: tuple[Timestamp, Timestamp]
    source_ref: str
    observation_mode: Mode
    freeze_ref: str
    product_freeze_ref: str


class VerifiedAnswer(DomainModel):
    schema_version: Literal["local.agent.answer.v2"]
    rows: tuple[EvidenceRow, ...]
    citations: tuple[str, ...]
    verification: AnswerVerification
    coverage: AnswerCoverage
    response_language: ResponseLanguage
    scope: AnswerScope
    semantic_factuality: Literal["LITERAL_FIELDS_VERIFIED_INTERPRETATION_NOT_CERTIFIED"]
    text: str
    requirement_verification: dict[str, JsonValue] | None = None


class ModelAction(DomainModel):
    kind: Literal["tool", "clarification", "answer", "refusal"]
    tool: str | None = Field(default=None, max_length=80)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    question: str | None = Field(default=None, min_length=1, max_length=1000)
    text: str | None = Field(default=None, min_length=1, max_length=3000)
    citations: tuple[str, ...] = Field(default=(), max_length=16)
    goal: RequestGoal | None = None
    selections: tuple[EvidenceSelection, ...] = Field(default=(), max_length=16)
    missing_slots: tuple[MissingSlot, ...] = Field(default=(), max_length=4)
    reason_code: RefusalReason | None = None

    @model_validator(mode="after")
    def disjoint(self) -> Self:
        if self.kind == "tool":
            valid = self.tool is not None and not self.question and not self.text
            valid = valid and not self.citations and not self.selections
            valid = valid and not self.missing_slots and not self.reason_code
        elif self.kind == "clarification":
            valid = bool(self.question) and not self.tool and not self.arguments
            valid = valid and not self.text and not self.citations
            valid = valid and not self.goal and not self.selections and not self.reason_code
        elif self.kind == "answer":
            valid = not self.tool and not self.arguments and not self.question
            valid = valid and not self.goal and not self.missing_slots and not self.reason_code
            valid = valid and (bool(self.selections) and not self.text and not self.citations
                              or bool(self.text) and bool(self.citations) and not self.selections)
        else:
            valid = bool(self.reason_code) and not self.tool and not self.arguments
            valid = valid and not self.question and not self.text and not self.citations
            valid = valid and not self.goal and not self.selections and not self.missing_slots
        if not valid:
            raise ValueError("disjoint action required")
        return self


AgentState = Literal[
    "READY", "RUNNING", "NEEDS_CLARIFICATION", "COMPLETED", "STOPPED", "FAILED",
    "BUDGET_EXHAUSTED", "RESUME_REQUIRED", "REFUSED",
]
