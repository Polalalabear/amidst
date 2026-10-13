"""Hermetic registration-fact rehearsals preserve study isolation and denominators."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from test_scenes import fixture_scene

from amidst.workbench import operator_study
from amidst.workbench.operator_study import OperatorStudyStore

Json = dict[str, Any]
SCENE = "synthetic-lab"
OWNER = "server-research-session"


@pytest.fixture
def prepared(tmp_path: Path) -> tuple[OperatorStudyStore, Any]:
    source = tmp_path / "source"
    source.mkdir()
    scene = fixture_scene(source).with_display_identity(SCENE, "Source", "Rehearsal fixture")
    return OperatorStudyStore({SCENE: scene}, tmp_path / "study" / "ledger.sqlite3"), scene


def task(store: OperatorStudyStore, family: str) -> Json:
    return next(row for row in store.context(SCENE)["tasks"] if row["family"] == family)


def start(store: OperatorStudyStore, family: str, mode: str = "manual") -> Json:
    return store.start(SCENE, OWNER, task(store, family)["task_ref"], mode)


def view(store: OperatorStudyStore, study: Json, timestamp: float = 0) -> Json:
    return store.view(SCENE, OWNER, study["study_ref"], camera_id="A", timestamp=timestamp)


def test_library_and_ledger_are_source_bound_preparation_without_answer_or_truth_exports(
    prepared: tuple[OperatorStudyStore, Any],
) -> None:
    store, scene = prepared
    context = store.context(SCENE)
    assert context["status"] == "PREPARATION_REHEARSAL"
    assert context["reference_kind"] == "CANONICAL_SOURCE_REFERENCE"
    assert not context["actual_operator_acceptance"]
    assert len(context["tasks"]) == 4
    assert {row["answer_type"] for row in context["tasks"]} == {
        "timestamp", "count", "presence", "order"}
    assert context["binding"]["run_id"] == scene.run_id
    assert context["binding"]["registry_sha256"] == scene.service.store.registry.sha256
    exported = json.dumps(context)
    for prohibited in ("expected", "answer_key", "actor_identity", "recipe", "ground_truth",
                       "relative_path", str(scene.service.store.media_root)):
        assert prohibited not in exported
    assert store.context("local-camera")["available"] is False
    with pytest.raises(ValueError, match="SOURCE_UNAVAILABLE"):
        store.start("local-camera", OWNER, context["tasks"][0]["task_ref"], "manual")
    with pytest.raises(ValueError, match="MUST_BE_SEPARATE_FROM_SOURCE"):
        OperatorStudyStore({SCENE: scene}, scene.service.store.media_root / "study.sqlite3")


@pytest.mark.parametrize(("family", "answer", "correctness"), [
    ("earliest_registered_frame", {"timestamp": 0.0}, "CORRECT"),
    ("registered_frame_count", {"count": 3}, "CORRECT"),
    ("exact_registration_presence", {"presence": "MISSING"}, "CORRECT"),
    ("source_frame_order", {"order": ["B", "A"]}, "CORRECT"),
    ("registered_frame_count", {"count": 2}, "INCORRECT"),
    ("registered_frame_count", {"unknown": True}, "UNKNOWN"),
])
def test_reference_scoring_keeps_completed_and_unresolved_denominators(
    prepared: tuple[OperatorStudyStore, Any], family: str, answer: Json, correctness: str,
) -> None:
    store, _ = prepared
    study = start(store, family)
    result = store.submit(SCENE, OWNER, study["study_ref"], answer)
    assert result["status"] == "COMPLETED"
    assert result["metrics"]["correctness"] == correctness
    assert result["metrics"]["completed_denominator"] == 1
    assert result["metrics"]["eligible_completed_denominator"] == 1
    assert result["metrics"]["unresolved_count"] == int(correctness == "UNKNOWN")
    assert not result["comparison"]["eligible_for_duration_comparison"]
    assert "recovery_token" not in result
    assert "expected" not in json.dumps(result)
    with pytest.raises(ValueError, match="NOT_RUNNING"):
        store.submit(SCENE, OWNER, study["study_ref"], answer)


@pytest.mark.parametrize("answer", [
    {"count": True}, {"count": "3"}, {"count": -1}, {"count": 65},
    {"count": 3, "elapsed_ms": 1}, {"unknown": 1}, {}, [3], {"count": float("nan")},
])
def test_invalid_answers_never_complete_or_spoof_metrics(
    prepared: tuple[OperatorStudyStore, Any], answer: object,
) -> None:
    store, _ = prepared
    study = start(store, "registered_frame_count")
    with pytest.raises(ValueError, match="INVALID_STUDY"):
        store.submit(SCENE, OWNER, study["study_ref"], answer)
    report = store.report(SCENE, OWNER, study["study_ref"])
    assert report["status"] == "RUNNING"
    assert report["metrics"]["completed_denominator"] == 0


def test_manual_original_view_counts_are_server_issued_and_assisted_tools_are_scoped(
    prepared: tuple[OperatorStudyStore, Any],
) -> None:
    store, _ = prepared
    manual = start(store, "registered_frame_count")
    assert manual["issued_frames"] == []
    original = view(store, manual)
    assert original["assistance"] is None
    assert original["frame"]["timestamp"] == 0
    assert original["measurement_scope"] == "SERVER_ACCEPTED_SOURCE_VIEW_REQUESTS"
    with pytest.raises(ValueError, match="REQUIRES_SERVER_VIEW"):
        store.record(SCENE, OWNER, manual["study_ref"], "camera_view", camera_id="A")
    with pytest.raises(ValueError, match="EVIDENCE_SCOPE_DENIED"):
        store.record(SCENE, OWNER, manual["study_ref"], "evidence_open", evidence_ref="foreign")
    with pytest.raises(ValueError, match="REQUIRES_VIEWED_FRAME"):
        store.record(SCENE, OWNER, manual["study_ref"], "correction", frame_ref="foreign")
    corrected = store.record(SCENE, OWNER, manual["study_ref"], "correction",
                             frame_ref=original["frame"]["frame_ref"])
    assert corrected["metrics"]["camera_view_count"] == 1
    assert corrected["metrics"]["frame_open_count"] == 1
    assert corrected["metrics"]["distinct_camera_count"] == 1
    assert corrected["metrics"]["correction_count"] == 1
    store.stop(SCENE, OWNER, manual["study_ref"])
    assisted = start(store, "registered_frame_count", "assisted")
    annotated = view(store, assisted)
    evidence = annotated["assistance"]
    assert evidence["kind"] == "REGISTERED_FRAME_METADATA"
    assert evidence["registered_timestamps"] == [0.0, 1.0, 100.0]
    assert "expected" not in json.dumps(annotated)
    report = store.record(SCENE, OWNER, assisted["study_ref"], "evidence_open",
                          evidence_ref=evidence["evidence_ref"])
    assert report["metrics"]["evidence_open_count"] == 1


def test_view_rejects_foreign_task_time_camera_frame_and_missing_media_without_logging(
    prepared: tuple[OperatorStudyStore, Any],
) -> None:
    store, scene = prepared
    study = start(store, "earliest_registered_frame")
    for payload in ({"camera_id": "foreign", "timestamp": 0},
                    {"camera_id": "A", "timestamp": 100}, {"frame_ref": "foreign"},
                    {"camera_id": "A", "timestamp": float("nan")},
                    {"camera_id": "A", "timestamp": 0, "frame_ref": "foreign"}):
        with pytest.raises(ValueError):
            store.view(SCENE, OWNER, study["study_ref"], **payload)
    scene.service.store.media_root.joinpath("rgb.png").write_bytes(b"tampered")
    with pytest.raises(ValueError):
        view(store, study)
    assert store.report(SCENE, OWNER, study["study_ref"])["metrics"]["frame_open_count"] == 0


def test_owner_binding_recovery_and_source_changes_fail_closed(
    prepared: tuple[OperatorStudyStore, Any],
) -> None:
    store, scene = prepared
    study = start(store, "registered_frame_count")
    for method in (store.report, store.stop):
        with pytest.raises(ValueError, match="SCOPE_DENIED"):
            method(SCENE, "different-session", study["study_ref"])
    assert store.list(SCENE, "different-session")["items"] == []
    with pytest.raises(ValueError, match="RECOVERY_DENIED"):
        store.resume(SCENE, study["study_ref"], "wrong-recovery", "different-session")
    recovered = store.resume(SCENE, study["study_ref"], study["recovery_token"],
                             "different-session")
    assert "recovery_token" not in recovered
    assert store.list(SCENE, OWNER)["items"] == []
    assert len(store.list(SCENE, "different-session")["items"]) == 1
    with pytest.raises(ValueError, match="SCOPE_DENIED"):
        store.report(SCENE, OWNER, study["study_ref"])
    scene.source_hash = "9" * 64
    with pytest.raises(ValueError, match="BINDING_CHANGED"):
        store.report(SCENE, "different-session", study["study_ref"])
    with pytest.raises(ValueError, match="BINDING_CHANGED"):
        store.resume(SCENE, study["study_ref"], study["recovery_token"], OWNER)


def test_persisted_timer_uses_active_monotonic_segments_and_excludes_restart_gap(
    prepared: tuple[OperatorStudyStore, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, scene = prepared
    ticks = {"mono": 1_000_000_000, "wall": 100.0}
    monkeypatch.setattr(operator_study.time, "monotonic_ns", lambda: ticks["mono"])
    monkeypatch.setattr(operator_study.time, "time", lambda: ticks["wall"])
    study = start(store, "registered_frame_count")
    ticks.update(mono=3_000_000_000, wall=102.0)
    assert view(store, study)["frame"]["timestamp"] == 0
    assert store.report(SCENE, OWNER, study["study_ref"])["metrics"]["duration_ms"] == 2000
    restarted = OperatorStudyStore({SCENE: scene}, store.db_path)
    ticks.update(mono=100_000_000_000, wall=160.0)
    paused = restarted.report(SCENE, OWNER, study["study_ref"])
    assert paused["status"] == "RESUME_REQUIRED"
    assert paused["metrics"]["duration_ms"] == 2000
    with pytest.raises(ValueError, match="RESUME_REQUIRED"):
        restarted.submit(SCENE, OWNER, study["study_ref"], {"count": 3})
    resumed = restarted.resume(SCENE, study["study_ref"], study["recovery_token"], "new-session")
    assert resumed["metrics"]["excluded_resume_gap_ms"] == 58_000
    ticks.update(mono=104_000_000_000, wall=164.0)
    completed = restarted.submit(SCENE, "new-session", study["study_ref"], {"count": 3})
    assert completed["metrics"]["duration_ms"] == 6000
    assert completed["metrics"]["excluded_resume_gap_ms"] == 58_000
    assert completed["timing_basis"] == "SERVER_MONOTONIC_ACTIVE_SEGMENTS"
    assert "EXCLUDED_FROM_ACTIVE_DURATION" in completed["resume_gap_basis"]
    with pytest.raises(ValueError, match="SCOPE_DENIED"):
        store.report(SCENE, OWNER, study["study_ref"])


def test_manual_external_assistance_denial_is_durable_and_excluded_from_comparison(
    prepared: tuple[OperatorStudyStore, Any],
) -> None:
    store, _ = prepared
    store.guard_external("unsupported", OWNER, "query")  # No active study: no side effects.
    manual = start(store, "registered_frame_count")
    with pytest.raises(ValueError, match="EXTERNAL_ASSISTANCE_DENIED"):
        store.guard_external("another-scene", OWNER, "run_result")
    contaminated = store.submit(SCENE, OWNER, manual["study_ref"], {"count": 3})
    assert contaminated["metrics"]["completed_denominator"] == 1
    assert contaminated["metrics"]["eligible_completed_denominator"] == 0
    assert contaminated["metrics"]["correctness"] == "CORRECT"
    assert contaminated["metrics"]["protocol_excluded_count"] == 1
    assisted = start(store, "registered_frame_count", "assisted")
    store.guard_external(SCENE, OWNER, "query")
    report = store.submit(SCENE, OWNER, assisted["study_ref"], {"count": 3})
    comparison = report["comparison"]
    assert not comparison["eligible_for_duration_comparison"]
    assert comparison["modes"]["manual"]["completed_denominator"] == 1
    assert comparison["modes"]["manual"]["eligible_completed_denominator"] == 0
    assert comparison["modes"]["manual"]["protocol_excluded_count"] == 1
    assert comparison["modes"]["assisted"]["eligible_completed_denominator"] == 1
    with sqlite3.connect(store.db_path) as connection:
        persisted = json.loads(connection.execute("SELECT state FROM operator_studies "
                                                 "WHERE study_ref=?",
                                                 (manual["study_ref"],)).fetchone()[0])
    assert not persisted["protocol_valid"]
    assert "external_assistance_denied" in [event["action"] for event in persisted["events"]]


def test_paired_comparison_requires_same_correct_task_and_preserves_repeated_attempt_counts(
    prepared: tuple[OperatorStudyStore, Any],
) -> None:
    store, _ = prepared
    manual = start(store, "registered_frame_count")
    view(store, manual)
    store.submit(SCENE, OWNER, manual["study_ref"], {"count": 3})
    assisted = start(store, "registered_frame_count", "assisted")
    view(store, assisted)
    paired = store.submit(SCENE, OWNER, assisted["study_ref"], {"count": 3})
    assert paired["comparison"]["eligible_for_duration_comparison"]
    assert paired["comparison"]["same_binding"] and paired["comparison"]["same_task"]
    assert not paired["comparison"]["learning_effect_controlled"]
    assert not paired["efficiency_gain_claim"]
    other_task = start(store, "exact_registration_presence", "assisted")
    unpaired = store.submit(SCENE, OWNER, other_task["study_ref"], {"presence": "MISSING"})
    assert unpaired["comparison"]["modes"]["manual"]["attempt_count"] == 0
    assert not unpaired["comparison"]["eligible_for_duration_comparison"]
    repeated = start(store, "registered_frame_count")
    repeated_report = store.submit(SCENE, OWNER, repeated["study_ref"], {"unknown": True})
    assert repeated_report["comparison"]["modes"]["manual"]["completed_denominator"] == 2
    assert repeated_report["comparison"]["modes"]["manual"]["unresolved_count"] == 1
    assert not repeated_report["comparison"]["eligible_for_duration_comparison"]


def test_stopped_attempt_retains_time_but_has_no_completed_denominator(
    prepared: tuple[OperatorStudyStore, Any],
) -> None:
    store, _ = prepared
    active = start(store, "registered_frame_count")
    with pytest.raises(ValueError, match="ACTIVE_STOP_OR_RESUME_FIRST"):
        start(store, "registered_frame_count", "assisted")
    stopped = store.stop(SCENE, OWNER, active["study_ref"])
    assert stopped["status"] == "STOPPED"
    assert stopped["metrics"]["completed_denominator"] == 0
    assert stopped["comparison"]["modes"]["manual"]["stopped_count"] == 1
    assert "recovery_token" not in json.dumps(store.list(SCENE, OWNER))


def test_unregistered_frame_metadata_is_rejected_before_task_pack_generation(
    prepared: tuple[OperatorStudyStore, Any],
) -> None:
    store, scene = prepared
    frame = next(iter(scene.service.frames.values()))
    scene.service.frames[frame.media_ref] = frame.model_copy(update={"timestamp": 50.0})
    with pytest.raises(ValueError, match="BINDING_CHANGED"):
        store.context(SCENE)


def test_study_media_grants_require_this_owner_bound_issued_frame_and_preserve_counters(
    prepared: tuple[OperatorStudyStore, Any],
) -> None:
    store, scene = prepared
    study = start(store, "registered_frame_count")
    original_ref = next(iter(scene.service.frames))
    with pytest.raises(ValueError, match="MEDIA_SCOPE_DENIED"):
        store.authorize_media(SCENE, OWNER, study["study_ref"], original_ref)
    opened = view(store, study)
    granted_ref = opened["frame"]["media_ref"]
    store.authorize_media(SCENE, OWNER, study["study_ref"], granted_ref)
    store.authorize_media(SCENE, OWNER, study["study_ref"], granted_ref)
    assert store.report(SCENE, OWNER, study["study_ref"])["metrics"]["frame_open_count"] == 1
    with pytest.raises(ValueError, match="SCOPE_DENIED"):
        store.authorize_media(SCENE, "different-owner", study["study_ref"], granted_ref)
    store.stop(SCENE, OWNER, study["study_ref"])
    store.authorize_media(SCENE, OWNER, study["study_ref"], granted_ref)
    with pytest.raises(ValueError, match="MEDIA_SCOPE_DENIED"):
        store.authorize_media(SCENE, OWNER, study["study_ref"], "media:foreign")


def test_guessed_correct_answers_without_source_views_do_not_qualify_for_duration_comparison(
    prepared: tuple[OperatorStudyStore, Any],
) -> None:
    store, _ = prepared
    manual = start(store, "registered_frame_count")
    store.submit(SCENE, OWNER, manual["study_ref"], {"count": 3})
    assisted = start(store, "registered_frame_count", "assisted")
    result = store.submit(SCENE, OWNER, assisted["study_ref"], {"count": 3})
    assert result["comparison"]["modes"]["manual"]["correct_count"] == 1
    assert result["comparison"]["modes"]["manual"]["viewed_correct_count"] == 0
    assert not result["comparison"]["eligible_for_duration_comparison"]


def test_explicit_recovery_preserves_pair_group_but_never_exposes_owner_or_recovery_hashes(
    prepared: tuple[OperatorStudyStore, Any],
) -> None:
    store, _ = prepared
    manual = start(store, "registered_frame_count")
    view(store, manual)
    store.resume(SCENE, manual["study_ref"], manual["recovery_token"], "recovered-session")
    store.submit(SCENE, "recovered-session", manual["study_ref"], {"count": 3})
    assisted = store.start(SCENE, "recovered-session",
                           task(store, "registered_frame_count")["task_ref"], "assisted")
    store.view(SCENE, "recovered-session", assisted["study_ref"], camera_id="A", timestamp=0)
    result = store.submit(SCENE, "recovered-session", assisted["study_ref"], {"count": 3})
    assert result["comparison"]["eligible_for_duration_comparison"]
    for private_field in ("owner_hash", "comparison_owner_hash", "recovery_hash", "clock_ref"):
        assert private_field not in json.dumps(result)


@pytest.mark.parametrize("terminal", ["COMPLETED", "STOPPED"])
def test_terminal_recovery_after_restart_restores_inspection_without_reopening_execution(
    prepared: tuple[OperatorStudyStore, Any], monkeypatch: pytest.MonkeyPatch, terminal: str,
) -> None:
    store, scene = prepared
    ticks = {"mono": 1_000_000_000, "wall": 100.0}
    monkeypatch.setattr(operator_study.time, "monotonic_ns", lambda: ticks["mono"])
    monkeypatch.setattr(operator_study.time, "time", lambda: ticks["wall"])
    study = start(store, "registered_frame_count")
    opened = view(store, study)
    ticks.update(mono=3_000_000_000, wall=102.0)
    finished = (store.submit(SCENE, OWNER, study["study_ref"], {"count": 3})
                if terminal == "COMPLETED" else store.stop(SCENE, OWNER, study["study_ref"]))
    restarted = OperatorStudyStore({SCENE: scene}, store.db_path)
    ticks.update(mono=900_000_000_000, wall=1000.0)
    with pytest.raises(ValueError, match="RECOVERY_DENIED"):
        restarted.resume(SCENE, study["study_ref"], "wrong-token", "new-session")
    recovered = restarted.resume(SCENE, study["study_ref"], study["recovery_token"], "new-session")
    assert recovered["status"] == terminal
    assert recovered["metrics"] == finished["metrics"]
    assert recovered["submitted_answer"] == finished["submitted_answer"]
    assert recovered["issued_frames"] == [opened["frame"]]
    assert "recovery_token" not in recovered
    assert recovered["comparison"] == finished["comparison"]
    assert restarted.list(SCENE, "new-session")["items"][0]["status"] == terminal
    inspected = restarted.report(SCENE, "new-session", study["study_ref"])
    assert inspected["metrics"]["duration_ms"] == 2000
    restarted.authorize_media(SCENE, "new-session", study["study_ref"],
                              opened["frame"]["media_ref"])
    with pytest.raises(ValueError, match="SCOPE_DENIED"):
        restarted.report(SCENE, OWNER, study["study_ref"])
    for operation in (
        lambda: restarted.view(SCENE, "new-session", study["study_ref"],
                               camera_id="A", timestamp=1),
        lambda: restarted.record(SCENE, "new-session", study["study_ref"], "correction",
                                 frame_ref=opened["frame"]["frame_ref"]),
        lambda: restarted.submit(SCENE, "new-session", study["study_ref"], {"count": 3}),
    ):
        with pytest.raises(ValueError, match="NOT_RUNNING"):
            operation()
    with pytest.raises(ValueError, match="ALREADY_TERMINAL"):
        restarted.stop(SCENE, "new-session", study["study_ref"])
    if terminal == "COMPLETED":
        assisted = restarted.start(SCENE, "new-session",
                                   task(restarted, "registered_frame_count")["task_ref"],
                                   "assisted")
        restarted.view(SCENE, "new-session", assisted["study_ref"], camera_id="A", timestamp=0)
        pair = restarted.submit(SCENE, "new-session", assisted["study_ref"], {"count": 3})
        assert pair["comparison"]["eligible_for_duration_comparison"]


@pytest.mark.parametrize("access", ["report", "media", "resume"])
@pytest.mark.parametrize("finish", ["stop", "submit"])
def test_historical_assisted_study_access_contaminates_and_denies_active_manual_only(
    prepared: tuple[OperatorStudyStore, Any], access: str, finish: str,
) -> None:
    store, scene = prepared
    previous = start(store, "registered_frame_count", "assisted")
    previous_frame = view(store, previous)["frame"]
    store.submit(SCENE, OWNER, previous["study_ref"], {"count": 3})
    manual = start(store, "registered_frame_count")
    current_frame = view(store, manual)["frame"]
    # Current manual study inspection/recovery is valid and does not add media counters.
    safe = store.report(SCENE, OWNER, manual["study_ref"])
    assert safe["submitted_answer"] is None
    assert "submitted_answer" not in json.dumps(safe["comparison"])
    store.authorize_media(SCENE, OWNER, manual["study_ref"], current_frame["media_ref"])
    store.resume(SCENE, manual["study_ref"], manual["recovery_token"], OWNER)
    inspect = {
        "report": lambda: store.report(SCENE, OWNER, previous["study_ref"]),
        "media": lambda: store.authorize_media(SCENE, OWNER, previous["study_ref"],
                                               previous_frame["media_ref"]),
        "resume": lambda: store.resume(SCENE, previous["study_ref"],
                                       previous["recovery_token"], OWNER),
    }[access]
    with pytest.raises(ValueError, match="OTHER_STUDY_ACCESS_DENIED"):
        inspect()
    invalid = store.report(SCENE, OWNER, manual["study_ref"])
    assert not invalid["protocol_valid"]
    assert invalid["protocol_violations"] == ["OTHER_STUDY_ACCESS"]
    assert invalid["metrics"]["frame_open_count"] == 1
    reopened = OperatorStudyStore({SCENE: scene}, store.db_path)
    assert not reopened.report(SCENE, OWNER, manual["study_ref"])["protocol_valid"]
    # Complete through the original server clock; historical grants are then readable.
    final = (store.stop(SCENE, OWNER, manual["study_ref"]) if finish == "stop"
             else store.submit(SCENE, OWNER, manual["study_ref"], {"count": 3}))
    assert final["metrics"]["protocol_excluded_count"] == 1
    assert final["metrics"]["eligible_completed_denominator"] == 0
    inspect()
