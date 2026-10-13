"""Small durable revision ledger, separate from immutable source/read models."""

from __future__ import annotations

import builtins
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .contracts import AgentDenied


class AgentLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS agent_cases ("
                       "agent_ref TEXT PRIMARY KEY, owner_hash TEXT NOT NULL, "
                       "scene_id TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS agent_owner_scene "
                       "ON agent_cases(owner_hash, scene_id)")
            # A process cannot silently continue an unfinished model/tool request after restart.
            for ref, revision, raw in db.execute(
                "SELECT agent_ref,revision,payload FROM agent_cases"
            ).fetchall():
                payload = json.loads(raw)
                if payload["state"] == "RUNNING":
                    clock = payload.get("operation_clock")
                    if clock:
                        payload["metrics"]["elapsed_ms"] = max(
                            payload["metrics"]["elapsed_ms"], clock["baseline_elapsed_ms"]
                            + max(0.0, time.time() * 1000 - clock["started_at_ms"]))
                        payload["metrics"]["interrupted_elapsed_upper_bound"] = True
                    payload.update(state="RESUME_REQUIRED", error_code="AGENT_PROCESS_INTERRUPTED",
                                   generation=payload["generation"] + 1, revision=revision + 1)
                    db.execute("UPDATE agent_cases SET revision=?,payload=? WHERE agent_ref=?",
                               (revision + 1, self._encode(payload), ref))

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _encode(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)

    def create(self, owner_hash: str, case: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO agent_cases VALUES (?,?,?,?,?)",
                       (case["agent_ref"], owner_hash, case["binding"]["scene_id"],
                        case["revision"], self._encode(case)))

    def load(self, owner_hash: str, scene_id: str, agent_ref: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT payload FROM agent_cases "
                             "WHERE agent_ref=? AND owner_hash=? AND scene_id=?",
                             (agent_ref, owner_hash, scene_id)).fetchone()
        if row is None:
            raise AgentDenied("AGENT_CASE_UNAVAILABLE")
        payload: dict[str, Any] = json.loads(row[0])
        return payload

    def save(self, owner_hash: str, case: dict[str, Any], expected_revision: int) -> None:
        updated = case | {"revision": expected_revision + 1}
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE agent_cases SET revision=?,payload=? "
                "WHERE agent_ref=? AND owner_hash=? AND revision=?",
                (expected_revision + 1, self._encode(updated), case["agent_ref"],
                 owner_hash, expected_revision),
            )
            if cursor.rowcount != 1:
                raise AgentDenied("AGENT_STALE_REVISION")
        case["revision"] = expected_revision + 1

    def list(self, owner_hash: str, scene_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM agent_cases WHERE owner_hash=? AND scene_id=? "
                              "ORDER BY rowid DESC LIMIT 100", (owner_hash, scene_id)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def all_for_owner(self, owner_hash: str) -> builtins.list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM agent_cases WHERE owner_hash=?",
                              (owner_hash,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def recovery_case(self, agent_ref: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT payload FROM agent_cases WHERE agent_ref=?",
                             (agent_ref,)).fetchone()
        if row is None:
            raise AgentDenied("AGENT_RECOVERY_DENIED")
        result: dict[str, Any] = json.loads(row[0])
        return result

    def transfer(self, owner_hash: str, case: dict[str, Any], expected_revision: int) -> None:
        updated = case | {"revision": expected_revision + 1}
        with self._connect() as db:
            cursor = db.execute("UPDATE agent_cases SET owner_hash=?,revision=?,payload=? "
                                "WHERE agent_ref=? AND revision=?",
                                (owner_hash, expected_revision + 1, self._encode(updated),
                                 case["agent_ref"], expected_revision))
            if cursor.rowcount != 1:
                raise AgentDenied("AGENT_STALE_REVISION")
        case["revision"] = expected_revision + 1
