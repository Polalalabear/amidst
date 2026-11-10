"""Independent CSV annotations -> versioned public text and evaluation-only answers.

No query parser, provider or prediction imports. The existing scorer validates
answers and clocks; an import never proves reviewer identity or grants runtime authority.
"""

import csv
import hashlib
import io
import json
import os
import re
import stat
from datetime import datetime
from pathlib import Path

from amidst.evaluation.q3_parse_eval import STATUSES, clock_catalog, evaluate
from amidst.q1q5.production_preflight import read_pinned, strict_json
from amidst.q1q5.store import canonical_hash


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def save(path, value):
    raw = (
        value
        if isinstance(value, bytes)
        else json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
    return hashlib.sha256(raw).hexdigest()


def read_csv(path, pin):
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path and path.suffix == ".csv", "CANONICAL_CSV")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_size <= 2_097_152, "CSV_SIZE_TYPE")
        raw = stream.read(2_097_153)
    need(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == pin, "CSV_PIN")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    columns = [
        "id",
        "category",
        "text",
        "keep_or_revise",
        "reviewed_text",
        "expected_status",
        "expected_llm_output",
        "expected_structured_query",
        "scope_ref",
        "scope_sha256",
        "reviewer",
        "reviewed_at",
        "notes",
    ]
    need(reader.fieldnames == columns, "CSV_COLUMNS")
    rows = list(reader)
    need(
        len(rows) == 8
        and all(None not in row and all(v is not None for v in row.values()) for row in rows),
        "EIGHT_REVIEW_ROWS_REQUIRED",
    )
    return rows


def import_review(
    rows,
    candidates,
    freeze,
    scope,
    *,
    version,
    schemas,
    review_pin,
    candidate_pin,
    scope_pin,
    output,
):
    need(
        isinstance(version, str)
        and re.fullmatch("[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}", version)
        and version != freeze["version"],
        "NEW_REVIEW_VERSION_REQUIRED",
    )
    need(
        freeze["public_inputs_file_sha256"] == candidate_pin
        and [r["id"] for r in candidates] == freeze["ordered_ids"] == [r["id"] for r in rows]
        and len({r["id"] for r in rows}) == 8,
        "CANDIDATE_ORDER_OR_PIN",
    )
    need(
        scope.get("schema_version") == "q-demo.q3-review-scope.v1"
        and set(scope) == {"schema_version", "scope_id", "clocks", "context_sha256"},
        "REVIEW_SCOPE",
    )
    clocks = clock_catalog(scope["clocks"])
    need(re.fullmatch("[0-9a-f]{64}", scope["context_sha256"]) is not None, "CONTEXT_PIN")
    answers, pending, selection = [], [], []
    for row, candidate in zip(rows, candidates, strict=True):
        cid = row["id"]
        need(
            row["text"] == candidate["text"] and row["category"] == freeze["categories_by_id"][cid],
            "CANDIDATE_TEXT_CATEGORY",
        )
        action = row["keep_or_revise"]
        if action not in {"KEEP", "REVISE", "EXCLUDE"}:
            pending.append(dict(id=cid, reason="REVIEW_ACTION_MISSING"))
            continue
        if (
            not row["reviewer"].strip()
            or not row["reviewed_at"]
            or row["scope_ref"] != scope["scope_id"]
            or row["scope_sha256"] != scope_pin
        ):
            pending.append(dict(id=cid, reason="REVIEWER_OR_SCOPE_MISSING"))
            continue
        need(
            row["reviewer"].casefold() not in {"codex", "qwen", "claude", "synthetic", "ai"},
            "INDEPENDENT_REVIEWER_REQUIRED",
        )
        need(datetime.fromisoformat(row["reviewed_at"]).tzinfo is not None, "REVIEW_TIMEZONE")
        if action == "EXCLUDE":
            pending.append(dict(id=cid, reason="MINIMUM_CATEGORY_NEEDS_REPLACEMENT"))
            continue
        text = candidate["text"] if action == "KEEP" else row["reviewed_text"].strip()
        need(
            bool(text)
            and len(text) <= 4096
            and (action != "KEEP" or not row["reviewed_text"] or row["reviewed_text"] == text),
            "REVIEW_TEXT_REQUIRED",
        )
        if not (
            row["expected_status"] in STATUSES
            and row["expected_llm_output"]
            and row["expected_structured_query"]
        ):
            pending.append(dict(id=cid, reason="INDEPENDENT_EXPECTED_MISSING"))
            continue
        answer = dict(
            id=cid,
            text=text,
            category=row["category"],
            expected_status=row["expected_status"],
            expected_llm_output=strict_json(row["expected_llm_output"]),
            expected_structured_query=strict_json(row["expected_structured_query"]),
        )
        answers.append(answer)
        selection.append(
            dict(id=cid, action=action, reviewer=row["reviewer"], reviewed_at=row["reviewed_at"])
        )
    # Use the existing evaluator's answer/schema/clock checks with zero predictions.
    validation = evaluate(
        answers,
        [],
        cases_sha256=review_pin,
        predictions_sha256=hashlib.sha256(b"").hexdigest(),
        schemas=schemas,
        clocks=clocks,
        clocks_sha256=scope_pin,
        evaluation_eligible=False,
        authority_sha256=None,
    )
    pending.extend(validation["invalid_cases"])
    ready = not pending and len(answers) == 8
    output = Path(output)
    need(
        output.is_absolute()
        and output.resolve() == output
        and not output.exists()
        and output.parent.is_dir(),
        "NEW_REVIEW_OUTPUT_REQUIRED",
    )
    output.mkdir(mode=0o700)
    report = dict(
        schema_version="q-demo.q3-review-import.v1",
        version=version,
        status="VALIDATED_REVIEW_BYTES" if ready else "BLOCKED",
        pending=pending,
        valid_rows=validation["valid_case_count"],
        formal_rows=0,
        formal_run_allowed=False,
        reviewer_identity_authenticated=False,
        accuracy=None,
        review_file_sha256=review_pin,
        candidate_file_sha256=candidate_pin,
        scope_file_sha256=scope_pin,
        context_sha256=scope["context_sha256"],
        selection=selection,
        files={},
    )
    if ready:
        report["files"]["public.json"] = save(
            output / "public.json",
            dict(
                schema_version="q-demo.reviewed-q3-public.v1",
                questions=[dict(id=r["id"], text=r["text"]) for r in answers],
            ),
        )
        report["files"]["expected.jsonl"] = save(
            output / "expected.jsonl",
            b"".join(
                json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
                + b"\n"
                for row in answers
            ),
        )
    report["content_sha256"] = canonical_hash(report)
    save(output / "IMPORT.json", report)
    return report


def score_review(
    output,
    report,
    scope,
    *,
    schemas,
    scope_pin,
    predictions,
    predictions_pin,
    authority,
    authority_pin,
    permit,
):
    """Explicit evaluation-only entry, after predictions and independent answers freeze."""
    need(
        permit is True and report["status"] == "VALIDATED_REVIEW_BYTES",
        "EXPLICIT_EVALUATION_PERMISSION_AND_REVIEW_REQUIRED",
    )
    proof = strict_json(read_pinned(Path(authority), authority_pin))
    need(
        set(proof)
        == {
            "schema_version",
            "review_import_sha256",
            "predictions_file_sha256",
            "scope_file_sha256",
            "decision",
            "reviewer",
            "expected_independent",
            "predictions_frozen",
            "dataset_kind",
        }
        and proof["schema_version"] == "q-demo.q3-evaluation-authority.v1",
        "EVALUATION_AUTHORITY_FIELDS",
    )
    need(
        proof["review_import_sha256"] == report["content_sha256"]
        and proof["predictions_file_sha256"] == predictions_pin
        and proof["scope_file_sha256"] == scope_pin
        and proof["decision"] == "APPROVED"
        and isinstance(proof["reviewer"], str)
        and bool(proof["reviewer"].strip())
        and proof["reviewer"].casefold() not in {"codex", "claude", "qwen", "ai", "synthetic"}
        and proof["expected_independent"] is True
        and proof["predictions_frozen"] is True
        and proof["dataset_kind"] in {"SYNTHETIC", "FORMAL_R004"},
        "EVALUATION_AUTHORITY_SCOPE",
    )
    raw = read_pinned(Path(predictions), predictions_pin, maximum=16_777_216)
    expected = read_pinned(
        Path(output) / "expected.jsonl", report["files"]["expected.jsonl"], maximum=16_777_216
    )
    result = evaluate(
        [strict_json(line) for line in expected.splitlines()],
        [strict_json(line) for line in raw.splitlines()],
        cases_sha256=report["files"]["expected.jsonl"],
        predictions_sha256=predictions_pin,
        schemas=schemas,
        clocks=clock_catalog(scope["clocks"]),
        clocks_sha256=scope_pin,
        evaluation_eligible=proof["dataset_kind"] == "FORMAL_R004",
        authority_sha256=authority_pin,
    )
    save(Path(output) / "SCORE.json", result)
    return result
