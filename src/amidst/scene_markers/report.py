"""Issue / rule-outcome / report model.  Reports are deterministic: no clock, no paths."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class Skip(Exception):
    """Raised by a rule that does not apply (e.g. preview run); recorded as SKIPPED."""


@dataclass(frozen=True)
class Issue:
    rule_id: str
    code: str
    severity: str  # "ERROR" | "WARN"
    scope: str  # file/section, e.g. "scene_static.walkable"
    field: str
    id: str | None
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "code": self.code,
            "severity": self.severity,
            "scope": self.scope,
            "field": self.field,
            "id": self.id,
            "message": self.message,
        }


@dataclass
class Collector:
    """Passed to a rule function; stamps the rule id on every issue."""

    rule_id: str
    issues: list[Issue] = field(default_factory=list)

    def err(self, code: str, scope: str, field_: str, message: str, id_: str | None = None) -> None:
        self.issues.append(Issue(self.rule_id, code, "ERROR", scope, field_, id_, message))

    def warn(
        self, code: str, scope: str, field_: str, message: str, id_: str | None = None
    ) -> None:
        self.issues.append(Issue(self.rule_id, code, "WARN", scope, field_, id_, message))


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    title: str
    spec_ref: str
    layer: str  # "contract" | "design" | "io"
    func: Callable[[Any, Collector], None]


@dataclass
class RuleOutcome:
    spec: RuleSpec
    result: str  # "PASS" | "FAIL" | "SKIPPED"
    issues: list[Issue]
    skip_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.spec.rule_id,
            "title": self.spec.title,
            "spec_ref": self.spec.spec_ref,
            "layer": self.spec.layer,
            "result": self.result,
            "error_count": sum(i.severity == "ERROR" for i in self.issues),
            "warn_count": sum(i.severity == "WARN" for i in self.issues),
            "skip_reason": self.skip_reason,
        }


RULES: list[RuleSpec] = []


def rule(
    rule_id: str, title: str, spec_ref: str, layer: str = "contract"
) -> Callable[[Callable[[Any, Collector], None]], Callable[[Any, Collector], None]]:
    def deco(func: Callable[[Any, Collector], None]) -> Callable[[Any, Collector], None]:
        if any(r.rule_id == rule_id for r in RULES):
            raise ValueError(f"duplicate rule id {rule_id}")
        RULES.append(RuleSpec(rule_id, title, spec_ref, layer, func))
        return func

    return deco
