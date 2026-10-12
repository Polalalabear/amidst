"""Append-only local human checklist deltas, never source geometry authority.

Only a previously validated source-bound decision document enters this store.
No source meshes, media, model snapshots or algorithm results are persisted here.
"""

from __future__ import annotations

import copy
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from amidst.engineering.registry import content_hash

Json = dict[str, Any]
_DECISION_KEYS = frozenset({"schema_version", "status", "scope", "review_sha256", "item_ref",
                          "source_binding", "checks", "remaining_check_refs",
                          "source_authority_changed", "formal_approval", "rerun_authorized",
                          "prior_results_changed", "decision_sha256"})


class PhysicalReviewStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS physical_review_deltas (
                scene_id TEXT NOT NULL, review_sha256 TEXT NOT NULL,
                revision INTEGER NOT NULL, payload TEXT NOT NULL,
                document_hash TEXT NOT NULL,
                PRIMARY KEY(scene_id, review_sha256, revision))""")

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _records(db: sqlite3.Connection, scene_id: str, review_sha256: str) -> list[Json]:
        rows = db.execute(
            "SELECT * FROM physical_review_deltas WHERE scene_id=? AND review_sha256=? "
            "ORDER BY revision", (scene_id, review_sha256)).fetchall()
        records: list[Json] = []
        parent = None
        for revision, row in enumerate(rows, 1):
            value = json.loads(row["payload"])
            if (not isinstance(value, dict) or value.get("scene_id") != scene_id
                    or value.get("review_sha256") != review_sha256
                    or value.get("revision") != revision or row["revision"] != revision
                    or value.get("parent_document_hash") != parent
                    or value.get("formal_approval") is not False
                    or value.get("authority_changed") is not False
                    or value.get("rerun_authorized") is not False
                    or content_hash(value) != row["document_hash"]):
                raise ValueError("PHYSICAL_REVIEW_HISTORY_INVALID")
            parent = row["document_hash"]
            records.append({**value, "document_hash": parent})
        return records

    def state(self, scene_id: str, review_sha256: str) -> Json:
        with self._connection() as db:
            records = self._records(db, scene_id, review_sha256)
        return {"revision": len(records), "records": records,
                "review_sha256": review_sha256, "scene_id": scene_id,
                "authority": "LOCAL_HUMAN_CHECKLIST_DELTA_ONLY", "formal_approval": False,
                "authority_changed": False, "rerun_authorized": False,
                "rerun_status": "AWAITING_HUMAN_AND_SOURCE_AUTHORITY_CONFIRMATION"}

    def append(self, scene_id: str, review_sha256: str, decision: Json, *,
               expected_revision: int, reviewer: str, reason: str) -> Json:
        if (type(expected_revision) is not int or expected_revision < 0
                or not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 100
                or not isinstance(reason, str) or not reason.strip() or len(reason) > 2000
                or set(decision) != _DECISION_KEYS
                or decision.get("schema_version") != "workbench.blender-physical-review-decision.v1"
                or decision.get("review_sha256") != review_sha256
                or decision.get("source_authority_changed") is not False
                or decision.get("formal_approval") is not False
                or decision.get("prior_results_changed") is not False
                or decision.get("rerun_authorized") is not False
                or content_hash({k: v for k, v in decision.items() if k != "decision_sha256"})
                != decision.get("decision_sha256")):
            raise ValueError("PHYSICAL_REVIEW_DELTA_INVALID")
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            records = self._records(db, scene_id, review_sha256)
            if len(records) != expected_revision:
                raise ValueError("PHYSICAL_REVIEW_REVISION_CONFLICT")
            previous: dict[str, Json] = {}
            for record in records:
                if record["decision"]["item_ref"] == decision["item_ref"]:
                    for check in record["decision"]["checks"]:
                        previous[check["check_ref"]] = check
            changes: list[Json] = []
            for check in decision["checks"]:
                old = previous.get(check["check_ref"], {
                    "decision": "UNKNOWN", "evidence_refs": [], "comment": ""})
                if any(check[key] != old[key] for key in ("decision", "evidence_refs", "comment")):
                    changes.append({k: copy.deepcopy(v) for k, v in check.items()
                                    if k != "previous_decision"} | {
                        "baseline_previous_decision": check["previous_decision"],
                        "previous_local_decision": old["decision"],
                        "previous_local_evidence_refs": copy.deepcopy(old["evidence_refs"]),
                        "previous_local_comment": old["comment"]})
                previous[check["check_ref"]] = check
            remaining = sorted(ref for ref in set(decision["remaining_check_refs"]) | {
                check["check_ref"] for check in decision["checks"]}
                if previous.get(ref, {}).get("decision", "UNKNOWN") == "UNKNOWN")
            delta_decision = {k: copy.deepcopy(v) for k, v in decision.items()
                              if k not in {"checks", "decision_sha256", "remaining_check_refs"}}
            delta_decision.update({"checks": changes, "remaining_check_refs": remaining,
                                   "validated_input_sha256": decision["decision_sha256"],
                                   "status": "LOCALLY_REVIEWED" if any(
                                       check["decision"] != "UNKNOWN"
                                       for check in previous.values())
                                   else "UNKNOWN", "checks_are_changed_fields_only": True})
            delta_decision["decision_sha256"] = content_hash(delta_decision)
            value = {"schema_version": "workbench.physical-review-delta.v1",
                     "scene_id": scene_id, "review_sha256": review_sha256,
                     "revision": len(records) + 1,
                     "parent_document_hash": records[-1]["document_hash"] if records else None,
                     "decision": delta_decision, "reviewer": reviewer.strip(),
                     "reason": reason.strip(), "created_at": datetime.now(UTC).isoformat(),
                     "authority": "LOCAL_HUMAN_CHECKLIST_DELTA_ONLY", "formal_approval": False,
                     "authority_changed": False, "rerun_authorized": False}
            digest = content_hash(value)
            db.execute("INSERT INTO physical_review_deltas VALUES (?,?,?,?,?)",
                       (scene_id, review_sha256, value["revision"],
                        json.dumps(value, sort_keys=True, ensure_ascii=False,
                                   separators=(",", ":"), allow_nan=False), digest))
        return {**value, "document_hash": digest}

    def export_delta(self, scene_id: str, review_sha256: str, revision: int) -> Json:
        if type(revision) is not int or revision < 1:
            raise ValueError("PHYSICAL_REVIEW_REVISION_INVALID")
        with self._connection() as db:
            records = self._records(db, scene_id, review_sha256)
        if revision > len(records):
            raise ValueError("PHYSICAL_REVIEW_REVISION_UNAVAILABLE")
        return records[revision - 1]
