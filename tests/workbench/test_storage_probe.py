"""Real overlapping synthetic connections and isolation of staged probes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from amidst.workbench.reviews import ReviewStore
from amidst.workbench.storage_probe import PROBE_STAGES, _synthetic_scene, run_probe


def test_all_stages_measure_concurrency_conflict_rollback_and_delta_replay() -> None:
    report = run_probe()
    assert report["passed"] and not report["production_certification"]
    assert report["barrier_synchronized"]
    assert report["isolated_temporary_database"]
    assert report["worker_model"] == "THREADS_WITH_INDEPENDENT_SQLITE_CONNECTIONS"
    assert report["totals"] == {
        "phases": 4, "passed_phases": 4, "expected_conflicts": 1, "integrity_failures": 0,
    }
    phases = {phase["stage"]: phase for phase in report["phases"]}
    assert tuple(phases) == PROBE_STAGES
    readers = phases["readers"]["output"]
    assert readers["successful_reads"] == 12
    assert readers["simultaneously_open_read_transactions"] == 4
    assert readers["observed_versions"] == [0] and readers["hash_mismatches"] == 0
    appends = phases["appends"]["output"]
    assert appends["successful_appends"] == 8 and appends["lost_appends"] == 0
    assert appends["unique_notes"] == 4 and appends["unique_reviews"] == 4
    assert appends["rejected_writes"] == 5 and appends["rollback_verified"]
    conflict = phases["publish_conflict"]["output"]
    assert conflict["successful_publications"] == 1 and conflict["version_conflicts"] == 1
    assert conflict["committed_version"] == 1 and conflict["version_rows"] == 2
    assert conflict["lost_updates"] == 0 and conflict["winner_preserved"]
    assert conflict["retry_rollback_verified"]
    replay = phases["reopen_replay"]["output"]
    assert replay["delta_replay_matches"] and replay["wrong_base_rejected"]
    assert replay["patch_operations"] == 1 and replay["unchanged_objects_exported"] == 0
    for phase in phases.values():
        integrity = phase["integrity"]
        assert integrity["sqlite_integrity_ok"] and integrity["foreign_key_errors"] == 0
        assert integrity["source_snapshot_unchanged"] and integrity["baseline_unchanged"]
        assert integrity["caller_fixture_unchanged"] and integrity["reopen_verified"]
    serialized = json.dumps(report, allow_nan=False)
    assert "/Users/" not in serialized and "sqlite3" not in serialized
    assert ".blend" not in serialized and "ground_truth" not in serialized


@pytest.mark.parametrize("stage", PROBE_STAGES)
def test_stages_are_independently_runnable(stage: str) -> None:
    report = run_probe(stage)
    assert report["passed"]
    assert report["stage"] == stage
    assert [phase["stage"] for phase in report["phases"]] == [stage]
    assert report["totals"]["phases"] == 1


@pytest.mark.parametrize("stage", ["production", "", "ALL", "../database", 1, None, {}])
def test_unbounded_or_invalid_stage_rejected(stage: Any) -> None:
    with pytest.raises(ValueError, match="STORAGE_PROBE_STAGE_INVALID"):
        run_probe(stage)


def test_probe_cannot_mutate_or_open_an_existing_user_database(tmp_path: Path) -> None:
    scene = _synthetic_scene()
    database = tmp_path / "existing.sqlite3"
    existing = ReviewStore(database, {scene["scene_id"]: scene})
    existing.record_note(scene["scene_id"], "existing-event", "OPEN", "Keep this", "User",
                         scene["run_id"])
    original_bytes = database.read_bytes()
    state = existing.state(scene["scene_id"])
    assert run_probe("all")["passed"]
    assert database.read_bytes() == original_bytes
    assert existing.state(scene["scene_id"]) == state
    with pytest.raises(TypeError):
        run_probe(db_path=database)  # type: ignore[call-arg]
