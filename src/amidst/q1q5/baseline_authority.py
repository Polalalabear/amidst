"""Operator-supplied freeze receipts. Integrity/scope verification, not authentication."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from amidst.q1q5.production_preflight import read_pinned, strict_json
from amidst.q1q5.store import canonical_hash

FORMAL = "FORMAL_R004"


def need(ok, code):
    if not ok:
        raise ValueError(code)


@dataclass(frozen=True)
class ReviewedAuthority:
    file_sha256: str
    scope_sha256: str
    public_questions: tuple
    input_pins: tuple
    source_kind: str = FORMAL


def load_authority(path, pin, *, permit, input_pins):
    need(permit is True, "EXPLICIT_REVIEWED_RUN_PERMISSION_REQUIRED")
    doc = strict_json(read_pinned(path, pin))
    need(
        set(doc) == {"schema_version", "scope", "receipts"}
        and doc["schema_version"] == "q-demo.baseline-freeze-authority.v1",
        "AUTHORITY_FIELDS",
    )
    scope = doc["scope"]
    need(
        set(scope) == {"source_kind", "input_pins", "public_questions"}
        and scope["source_kind"] == FORMAL,
        "FORMAL_SCOPE_REQUIRED",
    )
    need(
        set(input_pins) == {"protocol", "cases", "composition", "registry", "runtime"}
        and all(isinstance(p, str) and re.fullmatch("[0-9a-f]{64}", p) for p in input_pins.values())
        and scope["input_pins"] == input_pins,
        "FREEZE_INPUT_PIN_MISMATCH",
    )
    questions = strict_json(
        read_pinned(
            Path(scope["public_questions"]["path"]),
            scope["public_questions"]["file_sha256"],
            maximum=16_777_216,
        )
    )
    need(
        questions.get("schema_version") == "q-demo.reviewed-q3-public.v1"
        and len(questions.get("questions", [])) == 8,
        "FROZEN_EIGHT_Q3_REQUIRED",
    )
    public = questions["questions"]
    need(
        all(
            set(q) == {"id", "text"} and all(isinstance(v, str) and v for v in q.values())
            for q in public
        )
        and len({q["id"] for q in public}) == 8,
        "PUBLIC_QUESTIONS_ONLY",
    )
    scope_hash = canonical_hash(scope)
    # Gate names match #192; a declaration alone never supplies missing receipts.
    gates = {
        "AUTHORIZED_RUN_CAMERA_TIME_SCOPE",
        "YYIN_REVIEW_RETURNED",
        "CLAUDE_GRAPH_ROI_CHECK_AND_G4",
        "NECESSARY_HSV_APPROVAL",
        "SOURCE_SETTINGS_FREEZE_RECEIPT",
        "FORMAL_RGB_PINS",
        "FORMAL_INDEX_PINS",
        "RUN_BOUND_CLOCK_GRAPH_PARAMETER_CATALOG_PINS",
        "Q3_MINIMUM_SET_AND_INDEPENDENT_EXPECTED_FROZEN",
        "MODEL_RUNTIME_GENERATION_BUDGET_APPROVAL",
        "ENVIRONMENT_AND_RESOURCE_PLAN_FROZEN",
        "PRODUCT_API_UI_REPLAY_PREREQUISITES",
        "ISSUE_145_CONFORMANCE_RESOLVED",
    }
    receipts = doc["receipts"]
    need(isinstance(receipts, list) and len(receipts) == len(gates), "ALL_GATE_RECEIPTS_REQUIRED")
    seen = set()
    for ref in receipts:
        need(set(ref) == {"path", "file_sha256"}, "RECEIPT_PIN_REQUIRED")
        receipt = strict_json(read_pinned(Path(ref["path"]), ref["file_sha256"]))
        need(
            set(receipt)
            == {
                "gate",
                "decision",
                "scope_sha256",
                "reviewer",
                "reviewed_at",
                "review_kind",
                "predictions_seen",
            },
            "RECEIPT_FIELDS",
        )
        reviewer = receipt["reviewer"]
        need(
            receipt["gate"] in gates
            and receipt["gate"] not in seen
            and receipt["decision"] == "APPROVED"
            and receipt["scope_sha256"] == scope_hash
            and isinstance(reviewer, str)
            and bool(reviewer.strip())
            and reviewer.casefold() not in {"codex", "qwen", "claude", "synthetic", "ai"}
            and receipt["review_kind"] == "INDEPENDENT_HUMAN"
            and receipt["predictions_seen"] is False,
            "REVIEW_SCOPE_OR_INDEPENDENCE_REQUIRED",
        )
        stamp = datetime.fromisoformat(receipt["reviewed_at"])
        need(stamp.tzinfo is not None, "REVIEW_TIMEZONE_REQUIRED")
        seen.add(receipt["gate"])
    return ReviewedAuthority(
        pin,
        scope_hash,
        tuple((q["id"], q["text"]) for q in public),
        tuple(sorted(input_pins.items())),
    )


def check_input(authority, name, pin):
    if authority is not None:
        need(
            isinstance(authority, ReviewedAuthority)
            and dict(authority.input_pins).get(name) == pin,
            "AUTHORITY_INPUT_PIN_MISMATCH",
        )


def verify_questions(cases, authority):
    if authority is None:
        return
    need(isinstance(authority, ReviewedAuthority), "VERIFIED_AUTHORITY_REQUIRED")
    public = dict(authority.public_questions)
    texts = [c["query"] for c in cases if c["query"]["kind"] == "TEXT"]
    need(
        {q["question_id"] for q in texts} == set(public)
        and all(public.get(q["question_id"]) == q["text"] for q in texts),
        "CASE_QUESTION_FREEZE_MISMATCH",
    )
