"""Server-bound local Agent contracts; model output never grants authority."""

from __future__ import annotations

from typing import Literal, Self

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
    max_prompt_chars: int = Field(default=18000, ge=4000, le=24000, strict=True)
    max_result_chars: int = Field(default=4500, ge=512, le=16000, strict=True)
    max_output_tokens: int = Field(default=768, ge=128, le=1024, strict=True)
    max_window_seconds: float = Field(default=120, gt=0, le=120)


class ModelAction(DomainModel):
    kind: Literal["tool", "clarification", "answer"]
    tool: str | None = Field(default=None, max_length=80)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    question: str | None = Field(default=None, min_length=1, max_length=1000)
    text: str | None = Field(default=None, min_length=1, max_length=3000)
    citations: tuple[str, ...] = Field(default=(), max_length=16)

    @model_validator(mode="after")
    def disjoint(self) -> Self:
        if self.kind == "tool":
            valid = self.tool is not None and not self.question and not self.text
            valid = valid and not self.citations
        elif self.kind == "clarification":
            valid = bool(self.question) and not self.tool and not self.arguments
            valid = valid and not self.text and not self.citations
        else:
            valid = bool(self.text) and not self.tool and not self.arguments and not self.question
            valid = valid and bool(self.citations)
        if not valid:
            raise ValueError("disjoint action required")
        return self


AgentState = Literal[
    "READY", "RUNNING", "NEEDS_CLARIFICATION", "COMPLETED", "STOPPED", "FAILED",
    "BUDGET_EXHAUSTED", "RESUME_REQUIRED",
]
