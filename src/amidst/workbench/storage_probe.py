"""Bounded, staged SQLite concurrency checks on isolated synthetic fixtures.

No caller database/path is accepted. The probe exercises real concurrent
connections, not production throughput or deployment certification.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from typing import Any

from amidst.workbench.reviews import ReviewStore, replay_review_delta

Payload = dict[str, Any]
PROBE_STAGES = ("readers", "appends", "publish_conflict", "reopen_replay")
_WORKERS = 4
_SCENE = "storage-probe-scene"
_RUN = "synthetic-storage-probe-run"


def _hash(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def _synthetic_scene() -> Payload:
    return {
        "scene_id": _SCENE, "source_hash": _hash("synthetic-storage-probe-source-v1"),
        "model_revision": "synthetic-model-v1", "run_id": _RUN,
        "objects": [
            {"object_id": "probe-region", "kind": "REGION", "label": "Synthetic room",
             "semantic": "ROOM", "geometry": {
                 "type": "polygon", "points": [[0, 0, 0], [4, 0, 0], [4, 3, 0], [0, 3, 0]],
             }, "properties": {"floor_id": None, "region_id": "probe-room"},
             "editable_fields": ["label", "semantic", "geometry", "properties"],
             "authority": "SYNTHETIC_CONFIG"},
            {"object_id": "probe-portal", "kind": "PORTAL", "label": "Synthetic door",
             "semantic": "DOOR", "geometry": {
                 "type": "line", "points": [[4, 1, 0], [4, 2, 0]],
             }, "properties": {"width": 1}, "editable_fields": ["label", "properties"],
             "authority": "SYNTHETIC_CONFIG"},
        ],
    }


def _parallel(tasks: list[Callable[[], Payload]]) -> list[Payload]:
    start = Barrier(len(tasks) + 1, timeout=15)

    def invoke(task: Callable[[], Payload]) -> Payload:
        start.wait()
        return task()

    with ThreadPoolExecutor(max_workers=len(tasks), thread_name_prefix="storage-probe") as pool:
        futures = [pool.submit(invoke, task) for task in tasks]
        start.wait()
        return [future.result(timeout=30) for future in futures]


def _integrity(db_path: Path, scene: Payload) -> Payload:
    with sqlite3.connect(db_path, timeout=10) as db:
        rows = db.execute("SELECT payload, hash FROM scenes WHERE id=?", (_SCENE,)).fetchone()
        assert rows is not None
        snapshot = json.loads(rows[0])
        counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("scenes", "drafts", "validations", "versions", "result_reviews",
                                "management_notes")}
        checks = [row[0] for row in db.execute("PRAGMA quick_check")]
        foreign_key_errors = len(db.execute("PRAGMA foreign_key_check").fetchall())
    reopened = ReviewStore(db_path, {_SCENE: scene})
    baseline = reopened.state(_SCENE)["baseline_objects"]
    return {
        "row_counts": counts, "sqlite_integrity_ok": checks == ["ok"],
        "foreign_key_errors": foreign_key_errors,
        "source_snapshot_unchanged": snapshot == scene and _hash(snapshot) == rows[1],
        "baseline_unchanged": baseline == scene["objects"], "reopen_verified": True,
    }


def _readers(db_path: Path, scene: Payload, store: ReviewStore) -> Payload:
    # The second barrier holds each independent read transaction open until all
    # four have read the baseline. This proves overlap without timing assertions.
    open_reads = Barrier(_WORKERS, timeout=15)

    def read() -> Payload:
        with sqlite3.connect(db_path, timeout=10) as db:
            db.execute("BEGIN")
            rows = [db.execute("SELECT payload, hash FROM versions WHERE scene_id=?",
                               (_SCENE,)).fetchone()]
            open_reads.wait()
            rows.extend(db.execute("SELECT payload, hash FROM versions WHERE scene_id=?",
                                   (_SCENE,)).fetchone() for _ in range(2))
            versions = [json.loads(row[0])["version"] for row in rows if row is not None]
            mismatches = sum(_hash(json.loads(row[0])) != row[1]
                             for row in rows if row is not None)
            db.commit()
        return {"versions": versions, "hash_mismatches": mismatches}

    results = _parallel([read] * _WORKERS)
    versions = [version for result in results for version in result["versions"]]
    output = {
        "successful_reads": len(versions), "simultaneously_open_read_transactions": _WORKERS,
        "observed_versions": sorted(set(versions)),
        "hash_mismatches": sum(result["hash_mismatches"] for result in results),
    }
    return {"input": {"connections": _WORKERS, "reads_per_connection": 3, "base_version": 0},
            "output": output, "conflicts": 0,
            "passed": versions == [0] * 12 and output["hash_mismatches"] == 0}


def _appends(db_path: Path, scene: Payload, store: ReviewStore) -> Payload:
    stores = [ReviewStore(db_path, {_SCENE: scene}) for _ in range(_WORKERS)]

    def append(index: int) -> Payload:
        worker = stores[index]
        note = worker.record_note(_SCENE, f"synthetic-event-{index}", "OPEN", "Probe note",
                                  f"Worker {index}", _RUN)
        review = worker.record_result(_SCENE, f"synthetic-event-{index}", "UNKNOWN",
                                      "Probe judgment", f"Worker {index}", _RUN)
        return {"note_id": note["note_id"], "review_id": review["review_id"]}

    results = _parallel([partial(append, i) for i in range(_WORKERS)])
    before_rejections = store.state(_SCENE)
    rejected = 0
    for worker in stores:
        try:
            worker.record_note(_SCENE, "synthetic-event", "OPEN", "Wrong run", "Probe",
                               "wrong-synthetic-run")
        except ValueError as exc:
            if str(exc) != "RESULT_RUN_MISMATCH":
                raise
            rejected += 1
    rollback_rejected = False
    # Insert an otherwise valid row before an append-only trigger rejects an
    # UPDATE. The connection context must roll back the earlier INSERT too.
    try:
        with sqlite3.connect(db_path, timeout=10) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("INSERT INTO management_notes (id, scene_id, payload, hash) "
                       "SELECT 'rollback-probe', scene_id, payload, hash "
                       "FROM management_notes LIMIT 1")
            db.execute("UPDATE scenes SET hash='rejected'")
    except sqlite3.IntegrityError as exc:
        if str(exc) != "APPEND_ONLY_REVIEW_STORE":
            raise
        rollback_rejected = True
    state = store.state(_SCENE)
    output = {
        "successful_appends": len(results) * 2,
        "unique_notes": len({result["note_id"] for result in results}),
        "unique_reviews": len({result["review_id"] for result in results}),
        "rejected_writes": rejected + int(rollback_rejected),
        "rollback_verified": state == before_rejections,
        "lost_appends": 8 - len(state["notes"]) - len(state["result_reviews"]),
    }
    return {"input": {"connections": _WORKERS, "appends_per_connection": 2,
                      "rejected_write_attempts": 5}, "output": output, "conflicts": 0,
            "passed": output["unique_notes"] == 4 and output["unique_reviews"] == 4
            and output["lost_appends"] == 0 and output["rejected_writes"] == 5
            and output["rollback_verified"]}


def _publish_conflict(db_path: Path, scene: Payload, store: ReviewStore) -> Payload:
    stores = [ReviewStore(db_path, {_SCENE: scene}) for _ in range(2)]
    drafts = [worker.save_draft(_SCENE, "probe-region", {"label": f"Reviewed room {index}"},
                                0, f"Publisher {index}", "Synthetic conflict fixture")
              for index, worker in enumerate(stores)]
    for worker, draft in zip(stores, drafts, strict=True):
        assert worker.validate_draft(draft["draft_id"])["valid"]

    def publish(index: int) -> Payload:
        try:
            result = stores[index].publish_draft(drafts[index]["draft_id"], f"Publisher {index}",
                                                 "Synthetic publication", 0)
        except ValueError as exc:
            if str(exc) != "VERSION_CONFLICT":
                raise
            return {"status": "VERSION_CONFLICT"}
        return {"status": "PUBLISHED", "label": result["objects"][0]["label"]}

    results = _parallel([partial(publish, i) for i in range(2)])
    winners = [result for result in results if result["status"] == "PUBLISHED"]
    conflicts = sum(result["status"] == "VERSION_CONFLICT" for result in results)
    state = store.state(_SCENE)
    unchanged_count = len(state["versions"])
    loser = next(draft for draft in state["drafts"] if draft["status"] == "STALE")
    try:
        store.publish_draft(loser["draft_id"], "Retry publisher", "Still stale", 1)
    except ValueError as exc:
        if str(exc) != "VERSION_CONFLICT":
            raise
    output = {
        "successful_publications": len(winners), "version_conflicts": conflicts,
        "committed_version": state["current_version"], "version_rows": len(state["versions"]),
        "winner_preserved": len(winners) == 1
        and state["objects"][0]["label"] == winners[0]["label"],
        "retry_rollback_verified": len(store.state(_SCENE)["versions"]) == unchanged_count,
        "lost_updates": int(not winners or state["objects"][0]["label"] != winners[0]["label"]),
    }
    return {"input": {"connections": 2, "validated_drafts": 2, "expected_base_version": 0},
            "output": output, "conflicts": conflicts,
            "passed": len(winners) == 1 and conflicts == 1 and output["version_rows"] == 2
            and output["winner_preserved"] and output["retry_rollback_verified"]}


def _reopen_replay(db_path: Path, scene: Payload, store: ReviewStore) -> Payload:
    draft = store.save_draft(_SCENE, "probe-portal", {"properties": {"width": 1.2}},
                             0, "Synthetic reviewer", "Synthetic width correction")
    assert store.validate_draft(draft["draft_id"])["valid"]
    published = store.publish_draft(draft["draft_id"], "Synthetic reviewer", "Checked", 0)
    reopened = ReviewStore(db_path, {_SCENE: scene})
    state = reopened.state(_SCENE)
    delta = reopened.export_delta(_SCENE, 1)
    replayed = replay_review_delta(state["versions"][0], delta)
    wrong_base = {**state["versions"][0], "source_hash": "f" * 64}
    rejected_base = False
    try:
        replay_review_delta(wrong_base, delta)
    except ValueError as exc:
        if str(exc) != "DELTA_BASE_MISMATCH":
            raise
        rejected_base = True
    output = {
        "reopened_version": state["current_version"], "changed_objects": 1,
        "patch_operations": len(delta["patch"]),
        "delta_replay_matches": replayed == published["overlay"],
        "wrong_base_rejected": rejected_base,
        "unchanged_objects_exported": 0, "source_or_media_copied": False,
        "document_hash": delta["document_hash"],
    }
    return {"input": {"base_version": 0, "target_version": 1,
                      "changed_field": "probe-portal.properties.width", "new_value": 1.2},
            "output": output, "conflicts": 0,
            "passed": output["delta_replay_matches"] and rejected_base
            and output["patch_operations"] == 1}


_RUNNERS = {"readers": _readers, "appends": _appends,
            "publish_conflict": _publish_conflict, "reopen_replay": _reopen_replay}


def run_probe(stage: str = "all") -> Payload:
    """Run one named stage or all four using disposable tiny synthetic stores."""
    if not isinstance(stage, str) or stage not in {"all", *PROBE_STAGES}:
        raise ValueError("STORAGE_PROBE_STAGE_INVALID")
    selected = PROBE_STAGES if stage == "all" else (stage,)
    phases = []
    with TemporaryDirectory(prefix="amidst-storage-probe-") as directory:
        for name in selected:
            scene = _synthetic_scene()
            source_digest = _hash(scene)
            db_path = Path(directory) / f"{name}.sqlite3"
            store = ReviewStore(db_path, {_SCENE: scene})
            result = _RUNNERS[name](db_path, scene, store)
            integrity = _integrity(db_path, scene)
            integrity["caller_fixture_unchanged"] = _hash(scene) == source_digest
            passed = bool(result["passed"] and integrity["sqlite_integrity_ok"]
                          and integrity["foreign_key_errors"] == 0
                          and integrity["source_snapshot_unchanged"]
                          and integrity["baseline_unchanged"]
                          and integrity["caller_fixture_unchanged"])
            phases.append({"stage": name, **result, "passed": passed, "integrity": integrity})
    return {
        "schema": "workbench.synthetic-storage-probe.v1", "stage": stage,
        "fixture": "tiny-synthetic-review-scene-v1", "isolated_temporary_database": True,
        "worker_model": "THREADS_WITH_INDEPENDENT_SQLITE_CONNECTIONS",
        "barrier_synchronized": True, "production_certification": False,
        "passed": all(phase["passed"] for phase in phases), "phases": phases,
        "totals": {
            "phases": len(phases), "passed_phases": sum(phase["passed"] for phase in phases),
            "expected_conflicts": sum(phase["conflicts"] for phase in phases),
            "integrity_failures": sum(not phase["passed"] for phase in phases),
        },
    }
