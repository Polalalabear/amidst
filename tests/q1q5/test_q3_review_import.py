"""Explicit synthetic expected controls; the public eight answers remain blank."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from amidst.evaluation.q1_query_eval import PinnedSchemas
from amidst.evaluation.q3_review_import import import_review, read_csv, score_review

ROOT = Path(__file__).resolve().parents[2]


def inputs():
    freeze = json.loads((ROOT / "configs/q1q5/q3_minimum_v1.freeze.json").read_bytes())
    candidates = [
        json.loads(line)
        for line in (ROOT / "configs/q1q5/q3_minimum_v1.public.jsonl").read_bytes().splitlines()
    ]
    llm = dict(
        schema_version="q-demo.q3-llm-output.v1",
        intent="UNSUPPORTED",
        class_term=None,
        color_term=None,
        time_literal=None,
        camera_terms=[],
        region_terms=[],
        needs_clarification=False,
        clarification_question=None,
    )
    rows = [
        dict(
            id=q["id"],
            category=freeze["categories_by_id"][q["id"]],
            text=q["text"],
            keep_or_revise="KEEP",
            reviewed_text="",
            expected_status="UNSUPPORTED_CONDITION",
            expected_llm_output=json.dumps(llm),
            expected_structured_query="null",
            scope_ref="SYNTHETIC",
            scope_sha256="a" * 64,
            reviewer="Independent fixture reviewer",
            reviewed_at="2026-10-24T00:00:00+08:00",
            notes="SYNTHETIC ONLY NOT REAL ANSWERS",
        )
        for q in candidates
    ]
    scope = dict(
        schema_version="q-demo.q3-review-scope.v1",
        scope_id="SYNTHETIC",
        context_sha256="b" * 64,
        clocks=dict(schema_version="q-demo.eval-clock-catalog.v1", mappings=[]),
    )
    return rows, candidates, freeze, scope


def invoke(tmp_path, rows, candidates, freeze, scope):
    return import_review(
        rows,
        candidates,
        freeze,
        scope,
        version="synthetic-review-v2",
        schemas=PinnedSchemas(ROOT / "src/amidst/contracts/q_demo"),
        review_pin="c" * 64,
        candidate_pin=freeze["public_inputs_file_sha256"],
        scope_pin="a" * 64,
        output=tmp_path / "result",
    )


def test_validated_import_keeps_answers_out_of_public_inputs(tmp_path):
    result = invoke(tmp_path, *inputs())
    assert result["status"] == "VALIDATED_REVIEW_BYTES" and result["formal_rows"] == 0
    public = json.loads((tmp_path / "result/public.json").read_bytes())
    assert all(set(q) == {"id", "text"} for q in public["questions"])
    assert not result["formal_run_allowed"] and result["accuracy"] is None


def test_actual_blank_review_stays_blocked_and_emits_no_expected(tmp_path):
    path = ROOT / "docs/evaluation/Q3_MINIMUM_V1_REVIEW.csv"
    rows = read_csv(path, hashlib.sha256(path.read_bytes()).hexdigest())
    _, c, f, s = inputs()
    report = invoke(tmp_path, rows, c, f, s)
    assert report["status"] == "BLOCKED" and len(report["pending"]) == 8
    assert not (tmp_path / "result/expected.jsonl").exists()


@pytest.mark.parametrize("change", [None, "predictions", "permission"])
def test_scoring_is_separate_and_synthetic_never_enters_formal_denominator(tmp_path, change):
    values = inputs()
    report = invoke(tmp_path, *values)
    predictions = tmp_path / "predictions.jsonl"
    predictions.write_bytes(b"")
    pin = hashlib.sha256(b"").hexdigest()
    authority = dict(
        schema_version="q-demo.q3-evaluation-authority.v1",
        review_import_sha256=report["content_sha256"],
        predictions_file_sha256=pin,
        scope_file_sha256="a" * 64,
        decision="APPROVED",
        reviewer="Independent fixture reviewer",
        expected_independent=True,
        predictions_frozen=True,
        dataset_kind="SYNTHETIC",
    )
    if change == "predictions":
        authority["predictions_file_sha256"] = "0" * 64
    proof = tmp_path / "proof.json"
    proof.write_text(json.dumps(authority))
    args = dict(
        schemas=PinnedSchemas(ROOT / "src/amidst/contracts/q_demo"),
        scope_pin="a" * 64,
        predictions=predictions,
        predictions_pin=pin,
        authority=proof,
        authority_pin=hashlib.sha256(proof.read_bytes()).hexdigest(),
        permit=change != "permission",
    )
    if change:
        with pytest.raises(ValueError):
            score_review(tmp_path / "result", report, values[3], **args)
    else:
        result = score_review(tmp_path / "result", report, values[3], **args)
        assert result["formal_case_count"] == 0 and result["status_accuracy"]["value"] is None


@pytest.mark.parametrize(
    "change", ["expected", "exclude", "scope", "date", "duplicate", "text", "schema"]
)
def test_incomplete_invalid_or_changed_review_never_freezes(tmp_path, change):
    rows, c, f, s = deepcopy(inputs())
    if change == "expected":
        rows[0]["expected_llm_output"] = ""
    elif change == "exclude":
        rows[0]["keep_or_revise"] = "EXCLUDE"
    elif change == "scope":
        rows[0]["scope_sha256"] = "0" * 64
    elif change == "date":
        rows[0]["reviewed_at"] = "2026-10-24"
    elif change == "duplicate":
        rows[1]["id"] = rows[0]["id"]
    elif change == "text":
        rows[0]["text"] = "changed"
    else:
        rows[0]["expected_llm_output"] = "{}"
    try:
        result = invoke(tmp_path, rows, c, f, s)
    except ValueError:
        return
    assert result["status"] == "BLOCKED" and not (tmp_path / "result/public.json").exists()
