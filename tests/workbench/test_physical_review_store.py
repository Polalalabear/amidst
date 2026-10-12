"""SUBSTITUTE review-document fixtures verify delta history and concurrent writers."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_blender_physical_review import _payload
from test_blender_physical_review import inputs as inputs

from amidst.engineering.registry import content_hash
from amidst.workbench.blender_physical_review import (
    BlenderPhysicalReviewIndex,
    validate_review_decision,
)
from amidst.workbench.physical_review_store import PhysicalReviewStore

REVIEW = "a" * 64


def decision(value="UNKNOWN"):
    result = {"schema_version": "workbench.blender-physical-review-decision.v1",
            "review_sha256": REVIEW, "item_ref": "review-fixture:door",
            "checks": [{"check_ref": "review-fixture:height", "decision": value,
                        "evidence_refs": ["SUBSTITUTE_TEST_EVIDENCE"],
                        "comment": "SUBSTITUTE storage test; not a source approval",
                        "previous_decision": "UNKNOWN"}],
            "source_authority_changed": False, "rerun_authorized": False,
            "formal_approval": False, "prior_results_changed": False,
            "status": "UNKNOWN" if value == "UNKNOWN" else "LOCALLY_REVIEWED",
            "scope": "LOCAL_ENGINEERING_REVIEW_ONLY",
            "source_binding": {"source_sha256": "c" * 64, "site_id": "SUBSTITUTE"},
            "remaining_check_refs": ["review-fixture:height"] if value == "UNKNOWN" else []}
    result["decision_sha256"] = content_hash(result)
    return result


def append(store, expected=0, value="UNKNOWN"):
    return store.append("scene-a", REVIEW, decision(value), expected_revision=expected,
                        reviewer="substitute tester", reason="storage fixture only")


def test_local_review_reopens_and_exports_only_changed_check_document(tmp_path):
    path = tmp_path / "reviews.sqlite3"
    store = PhysicalReviewStore(path)
    first = append(store)
    second = append(store, 1, "CONFIRMED_LOCAL")
    reopened = PhysicalReviewStore(path)
    assert reopened.state("scene-a", REVIEW)["revision"] == 2
    assert reopened.export_delta("scene-a", REVIEW, 1) == first
    assert second["parent_document_hash"] == first["document_hash"]
    assert reopened.export_delta("scene-a", REVIEW, 2) == second
    assert all(row["formal_approval"] is False and row["rerun_authorized"] is False
               for row in reopened.state("scene-a", REVIEW)["records"])
    text = json.dumps(second)
    assert "vertices" not in text and "source_mesh" not in text and "media_bytes" not in text


def test_concurrent_same_revision_has_one_winner_without_overwrite(tmp_path):
    store = PhysicalReviewStore(tmp_path / "reviews.sqlite3")

    def write(_):
        try:
            return append(store)["revision"]
        except ValueError as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(write, range(8)))
    assert results.count(1) == 1
    assert results.count("PHYSICAL_REVIEW_REVISION_CONFLICT") == 7
    assert store.state("scene-a", REVIEW)["revision"] == 1


def test_source_revision_and_site_histories_do_not_carry_confirmation(tmp_path):
    store = PhysicalReviewStore(tmp_path / "reviews.sqlite3")
    append(store, value="CONFIRMED_LOCAL")
    assert store.state("scene-b", REVIEW)["revision"] == 0
    assert store.state("scene-a", "b" * 64)["revision"] == 0
    assert store.state("scene-a", REVIEW)["authority_changed"] is False
    assert store.state("scene-a", REVIEW)["rerun_authorized"] is False


def test_corrupted_delta_hash_is_rejected_before_replay_or_append(tmp_path):
    path = tmp_path / "reviews.sqlite3"
    store = PhysicalReviewStore(path)
    append(store)
    with sqlite3.connect(path) as db:
        raw = json.loads(db.execute("SELECT payload FROM physical_review_deltas").fetchone()[0])
        raw["reason"] = "tampered"
        db.execute("UPDATE physical_review_deltas SET payload=?", (json.dumps(raw),))
    for operation in (lambda: store.state("scene-a", REVIEW),
                      lambda: store.export_delta("scene-a", REVIEW, 1),
                      lambda: append(store, 1)):
        with pytest.raises(ValueError, match="PHYSICAL_REVIEW_HISTORY_INVALID"):
            operation()


def test_unvalidated_authority_and_non_integer_revision_cannot_be_stored(tmp_path):
    store = PhysicalReviewStore(tmp_path / "reviews.sqlite3")
    for fields in ({"source_authority_changed": True}, {"rerun_authorized": True},
                   {"review_sha256": "b" * 64}):
        with pytest.raises(ValueError, match="PHYSICAL_REVIEW_DELTA_INVALID"):
            store.append("scene-a", REVIEW, decision() | fields, expected_revision=0,
                         reviewer="tester", reason="SUBSTITUTE")
    with pytest.raises(ValueError, match="PHYSICAL_REVIEW_DELTA_INVALID"):
        append(store, True)
    assert store.state("scene-a", REVIEW)["revision"] == 0


def test_export_cannot_request_unavailable_or_boolean_revision(tmp_path):
    store = PhysicalReviewStore(tmp_path / "reviews.sqlite3")
    append(store)
    for revision in (True, 0, -1, 2):
        with pytest.raises(ValueError):
            store.export_delta("scene-a", REVIEW, revision)


def test_real_core_normalized_substitute_decision_can_enter_delta_store(inputs, tmp_path):
    source, baseline = inputs
    index = BlenderPhysicalReviewIndex(source, baseline)
    normalized = validate_review_decision(index, _payload(index))
    store = PhysicalReviewStore(tmp_path / "reviews.sqlite3")
    row = store.append("substitute-scene", index.review_sha256, normalized,
                       expected_revision=0, reviewer="SUBSTITUTE tester", reason="contract test")
    assert row["decision"]["validated_input_sha256"] == normalized["decision_sha256"]
    assert row["decision"]["source_authority_changed"] is False
    assert row["rerun_authorized"] is False and row["formal_approval"] is False


def test_local_previous_value_and_unchanged_fields_are_not_baseline_or_full_copy(tmp_path):
    store = PhysicalReviewStore(tmp_path / "reviews.sqlite3")
    append(store, value="CONFIRMED_LOCAL")
    identical = append(store, 1, "CONFIRMED_LOCAL")
    assert identical["decision"]["checks"] == []
    changed = append(store, 2, "UNKNOWN")["decision"]
    assert changed["checks_are_changed_fields_only"] is True
    assert changed["checks"][0]["previous_local_decision"] == "CONFIRMED_LOCAL"
    assert changed["checks"][0]["baseline_previous_decision"] == "UNKNOWN"
    assert changed["remaining_check_refs"] == ["review-fixture:height"]
