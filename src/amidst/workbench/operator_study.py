"""Source-bound operator-study preparation, without person/behavior truth or trial claims.

Reference answers come only from registered original-frame metadata. The SQLite ledger
is separate from source registries, evaluation outputs, and product case records.
"""

from __future__ import annotations

import copy
import hmac
import json
import math
import secrets
import sqlite3
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.registry import MediaFrame, opaque_ref
from amidst.workbench.scenes import SceneAdapter

Json = dict[str, Any]
_PHASE = "PREPARATION_REHEARSAL"
_REFERENCE = "CANONICAL_SOURCE_REFERENCE"
_MAX_FRAME_METADATA = 64
_MAX_EVENTS = 2048


def _private_hash(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise ValueError("INVALID_STUDY_CREDENTIAL")
    return sha256(value.encode()).hexdigest()


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("INVALID_STUDY_TIMESTAMP")
    return float(value)


@dataclass(frozen=True)
class _Task:
    public: Json
    expected: object


class OperatorStudyStore:
    """Bounded preparation task library and durable owner-bound execution ledger.

    The hosting service must authorize research role and current scene first, and call
    ``guard_external`` before exposing assisted tools outside this study protocol.
    Recovery tokens are credentials; only ``start`` returns one, never reports/exports.
    """

    def __init__(self, catalog: dict[str, SceneAdapter], db_path: Path):
        self.catalog = catalog
        self.db_path = Path(db_path)
        if any(part.is_symlink() for part in (self.db_path, *self.db_path.parents)):
            raise ValueError("STUDY_LEDGER_PATH_DENIED")
        resolved = self.db_path.resolve()
        if any(resolved.is_relative_to(scene.service.store.media_root)
               for scene in catalog.values()):
            raise ValueError("STUDY_LEDGER_MUST_BE_SEPARATE_FROM_SOURCE")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.clock_ref = secrets.token_hex(16)
        with self._connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS operator_studies "
                               "(study_ref TEXT PRIMARY KEY, state TEXT NOT NULL)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=15)

    def _source(self, scene_id: str) -> tuple[SceneAdapter, Json, tuple[MediaFrame, ...]]:
        scene = self.catalog.get(scene_id)
        if scene_id != "synthetic-lab" or scene is None:
            raise ValueError("OPERATOR_STUDY_SOURCE_UNAVAILABLE")
        snapshot = scene.summary()
        if (not str(snapshot.get("evidence_level", "")).startswith("E0")
                or scene.service.guard.stage != "RESULTS"
                or not snapshot.get("freeze_ref")):
            raise ValueError("OPERATOR_STUDY_REQUIRES_FROZEN_E0_SOURCE")
        frames = tuple(sorted((frame for frame in scene.service.frames.values()
                               if frame.purpose == "RGB_SEQUENCE" and frame.annotations == "NONE"),
                              key=lambda frame: (frame.camera_id, frame.timestamp, frame.frame_id)))
        if not frames or any(frame.scope != scene.service.scope for frame in frames):
            raise ValueError("OPERATOR_STUDY_FRAME_SCOPE_INVALID")
        frozen = scene.service.guard.binding
        if (frozen.run_id != scene.run_id or frozen.registry_sha256 != snapshot["registry_sha256"]
                or frozen.registry_sha256 != scene.service.store.registry.sha256
                or scene.service.context().get("freeze_ref") != snapshot["freeze_ref"]
                or frames != tuple(sorted((frame for frame in scene.service.store.registry.frames
                                           if frame.scope == scene.service.scope
                                           and frame.purpose == "RGB_SEQUENCE"
                                           and frame.annotations == "NONE"),
                                          key=lambda frame: (frame.camera_id, frame.timestamp,
                                                             frame.frame_id)))):
            raise ValueError("OPERATOR_STUDY_SOURCE_BINDING_CHANGED")
        binding: Json = {
            "scene_id": scene_id, "run_id": scene.run_id,
            "source_sha256": scene.source_hash, "dataset_sha256": frozen.dataset_sha256,
            "config_sha256": frozen.config_sha256, "freeze_ref": snapshot["freeze_ref"],
            "clock_id": frozen.clock_id, "registry_sha256": frozen.registry_sha256,
            "media_sha256": frozen.media_sha256,
            "frame_metadata_sha256": digest([
                {"camera_id": frame.camera_id, "timestamp": frame.timestamp,
                 "frame_id": frame.frame_id, "media_ref": frame.media_ref,
                 "sha256": frame.sha256} for frame in frames
            ]),
        }
        return scene, binding, frames

    @staticmethod
    def _frame_ref(binding: Json, frame: MediaFrame) -> str:
        return opaque_ref("studyframe", digest(binding), frame.media_ref)

    def _tasks(self, binding: Json, frames: tuple[MediaFrame, ...]) -> dict[str, _Task]:
        """Deterministic tasks ask only registration facts, never model output as truth."""
        tasks: dict[str, _Task] = {}
        cameras = sorted({frame.camera_id for frame in frames})
        for variant, camera in enumerate(cameras[:2]):
            bucket = [frame for frame in frames if frame.camera_id == camera]
            selected = bucket[:6]
            if len(selected) < 2:
                continue
            first, second, last = selected[0], selected[1], selected[-1]
            step = second.timestamp - first.timestamp
            if step <= 0:
                continue
            low = max(0.0, first.timestamp - step / 3)
            next_gap = (bucket[len(selected)].timestamp - last.timestamp
                        if len(bucket) > len(selected) else step)
            high = last.timestamp + min(step, next_gap) / 3

            def add(family: str, answer_type: str, prompt: str, expected: object,
                    *, interval: tuple[float, float] = (low, high),
                    targets: list[Json] | None = None, variant: int = variant,
                    camera: str = camera) -> None:
                ref = opaque_ref("studytask", digest(binding), "preparation-v1", family,
                                 str(variant))
                tasks[ref] = _Task({"task_ref": ref, "family": family, "prompt": prompt,
                                    "answer_type": answer_type, "camera_ids": [camera],
                                    "time_range": list(interval), "targets": targets or [],
                                    "reference_kind": _REFERENCE}, expected)

            middle = first.timestamp + step / 2
            add("earliest_registered_frame", "timestamp",
                "Read the source viewer and enter the earliest registered frame timestamp "
                "inside the stated inclusive interval. This is a registration fact.",
                first.timestamp, interval=(low, middle))
            add("registered_frame_count", "count",
                "Count registered original frames in the stated inclusive interval. "
                "Do not count people, observations, or inferred events.", len(selected))
            exact = second.timestamp if variant % 2 else middle
            add("exact_registration_presence", "presence",
                f"Does this camera have an original frame registered at exactly {exact:g} "
                "seconds? PRESENT/MISSING concerns exact registration, not scene visibility.",
                "PRESENT" if any(frame.timestamp == exact for frame in bucket) else "MISSING",
                interval=(low, min(high, second.timestamp + step / 3)))
            add("source_frame_order", "order",
                "Open the two source-frame targets and order labels A/B from earlier to later. "
                "Use the source timestamps; this does not identify a person.", ["B", "A"],
                targets=[{"label": "A", "camera_id": camera,
                          "frame_ref": self._frame_ref(binding, last)},
                         {"label": "B", "camera_id": camera,
                          "frame_ref": self._frame_ref(binding, first)}])
        if not tasks:
            raise ValueError("OPERATOR_STUDY_TASK_SOURCE_TOO_SMALL")
        return tasks

    def context(self, scene_id: str) -> Json:
        if scene_id != "synthetic-lab" or scene_id not in self.catalog:
            return {"schema_version": "operator.study.context.v1", "available": False,
                    "status": "UNAVAILABLE", "reason": "NO_REGISTERED_TASK_PACK",
                    "phase": _PHASE, "actual_operator_acceptance": False}
        _, binding, frames = self._source(scene_id)
        return {"schema_version": "operator.study.context.v1", "available": True,
                "status": _PHASE, "reference_kind": _REFERENCE, "binding": binding,
                "tasks": [copy.deepcopy(task.public)
                          for task in self._tasks(binding, frames).values()],
                "modes": ["manual", "assisted"], "actual_operator_acceptance": False,
                "limitations": ["Source registration tasks only; no person/behavior truth.",
                                "Actual operator recruitment and trials remain deferred.",
                                "Repeated tasks disclose order and may have learning effects."]}

    @staticmethod
    def _read(connection: sqlite3.Connection, study_ref: str) -> Json:
        if not isinstance(study_ref, str) or len(study_ref) > 128:
            raise ValueError("STUDY_SCOPE_DENIED")
        result = connection.execute("SELECT state FROM operator_studies WHERE study_ref = ?",
                                    (study_ref,)).fetchone()
        if result is None:
            raise ValueError("STUDY_SCOPE_DENIED")
        state: Json = json.loads(result[0])
        return state

    @staticmethod
    def _all(connection: sqlite3.Connection) -> list[Json]:
        return [json.loads(row[0]) for row in connection.execute(
            "SELECT state FROM operator_studies ORDER BY rowid")]

    @staticmethod
    def _save(connection: sqlite3.Connection, state: Json) -> None:
        connection.execute("INSERT INTO operator_studies(study_ref,state) VALUES (?,?) "
                           "ON CONFLICT(study_ref) DO UPDATE SET state=excluded.state",
                           (state["study_ref"], json.dumps(state, allow_nan=False,
                                                        separators=(",", ":"))))

    def _authorize(self, state: Json, scene_id: str, owner_key: str,
                   *, require_running: bool = False) -> tuple[SceneAdapter, Json, _Task,
                                                             tuple[MediaFrame, ...]]:
        if (state["owner_hash"] != _private_hash(owner_key)
                or state["binding"]["scene_id"] != scene_id):
            raise ValueError("STUDY_SCOPE_DENIED")
        scene, binding, frames = self._source(scene_id)
        if binding != state["binding"]:
            raise ValueError("OPERATOR_STUDY_SOURCE_BINDING_CHANGED")
        task = self._tasks(binding, frames).get(state["task_ref"])
        if task is None:
            raise ValueError("STUDY_TASK_SCOPE_DENIED")
        if require_running and (state["status"] != "RUNNING"
                                or state["clock_ref"] != self.clock_ref):
            raise ValueError("STUDY_NOT_RUNNING_RESUME_REQUIRED")
        return scene, binding, task, frames

    def _tick(self, state: Json) -> None:
        if state["status"] == "RUNNING" and state["clock_ref"] == self.clock_ref:
            now = time.monotonic_ns()
            state["elapsed_ns"] += max(0, now - state["last_monotonic_ns"])
            state["last_monotonic_ns"] = now
            state["last_wall_s"] = time.time()

    def _event(self, state: Json, action: str, **references: str) -> None:
        if len(state["events"]) >= _MAX_EVENTS:
            raise ValueError("STUDY_ACTION_LIMIT_REACHED")
        state["events"].append({"action": action, "elapsed_ms": state["elapsed_ns"] // 1_000_000,
                                **references})

    def start(self, scene_id: str, owner_key: str, task_ref: str, mode: str) -> Json:
        if mode not in {"manual", "assisted"}:
            raise ValueError("INVALID_STUDY_MODE")
        _, binding, frames = self._source(scene_id)
        tasks = self._tasks(binding, frames)
        task = tasks.get(task_ref)
        if task is None:
            raise ValueError("STUDY_TASK_SCOPE_DENIED")
        owner_hash = _private_hash(owner_key)
        token = secrets.token_urlsafe(32)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = [state for state in self._all(connection)
                        if state["owner_hash"] == owner_hash]
            if any(state["status"] == "RUNNING" for state in previous):
                raise ValueError("STUDY_ACTIVE_STOP_OR_RESUME_FIRST")
            state: Json = {
                "study_ref": opaque_ref("study", secrets.token_hex(32)),
                "owner_hash": owner_hash,
                "comparison_owner_hash": (previous[-1]["comparison_owner_hash"]
                                          if previous else owner_hash),
                "recovery_hash": _private_hash(token), "binding": binding, "task_ref": task_ref,
                "mode": mode, "status": "RUNNING", "protocol_valid": True,
                "protocol_violations": [], "clock_ref": self.clock_ref,
                "last_monotonic_ns": time.monotonic_ns(), "last_wall_s": time.time(),
                "elapsed_ns": 0, "excluded_resume_gap_ms": 0, "resume_count": 0,
                "events": [], "issued_frames": [], "issued_evidence": [],
                "submitted_answer": None, "correctness": "NOT_SUBMITTED",
                "task_sequence": 1 + len([row for row in previous if row["binding"] == binding]),
            }
            self._event(state, "start")
            self._save(connection, state)
            result = self._dto(state, task)
            result["recovery_token"] = token
            return result

    def view(self, scene_id: str, owner_key: str, study_ref: str,
             camera_id: str | None = None, timestamp: float | None = None,
             frame_ref: str | None = None) -> Json:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = self._read(connection, study_ref)
            scene, binding, task, frames = self._authorize(state, scene_id, owner_key,
                                                         require_running=True)
            low, high = task.public["time_range"]
            eligible = [frame for frame in frames if frame.camera_id in task.public["camera_ids"]
                        and low <= frame.timestamp <= high]
            if frame_ref is not None:
                if camera_id is not None or timestamp is not None:
                    raise ValueError("STUDY_VIEW_TARGET_CONFLICT")
                candidates = [frame for frame in eligible
                              if self._frame_ref(binding, frame) == frame_ref]
            else:
                if camera_id not in task.public["camera_ids"]:
                    raise ValueError("STUDY_CAMERA_SCOPE_DENIED")
                requested = _number(timestamp)
                if not low <= requested <= high:
                    raise ValueError("STUDY_TIME_SCOPE_DENIED")
                candidates = sorted((frame for frame in eligible if frame.camera_id == camera_id),
                                    key=lambda frame: (abs(frame.timestamp - requested),
                                                       frame.timestamp, frame.frame_id))
            if not candidates:
                raise ValueError("STUDY_FRAME_SCOPE_DENIED")
            frame = candidates[0]
            # Verify original registered bytes before granting/logging this source-view request.
            scene.media(frame.media_ref)
            source_ref = self._frame_ref(binding, frame)
            self._tick(state)
            if source_ref not in state["issued_frames"]:
                state["issued_frames"].append(source_ref)
            self._event(state, "camera_view", camera_id=frame.camera_id)
            self._event(state, "frame_open", frame_ref=source_ref, camera_id=frame.camera_id)
            assistance = None
            if state["mode"] == "assisted":
                evidence_ref = opaque_ref("studyevidence", digest(binding), task.public["task_ref"],
                                          frame.camera_id)
                timestamps = [item.timestamp for item in eligible
                              if item.camera_id == frame.camera_id]
                if len(timestamps) > _MAX_FRAME_METADATA:
                    raise ValueError("STUDY_METADATA_LIMIT_REACHED")
                if evidence_ref not in state["issued_evidence"]:
                    state["issued_evidence"].append(evidence_ref)
                assistance = {"evidence_ref": evidence_ref, "kind": "REGISTERED_FRAME_METADATA",
                              "camera_id": frame.camera_id, "time_range": [low, high],
                              "registered_timestamps": timestamps}
            self._save(connection, state)
            return {"schema_version": "operator.study.view.v1", "study_ref": study_ref,
                    "phase": _PHASE, "mode": state["mode"], "binding": binding,
                    "frame": {"frame_ref": source_ref, "camera_id": frame.camera_id,
                              "timestamp": frame.timestamp, "media_ref": frame.media_ref},
                    "assistance": assistance,
                    "measurement_scope": "SERVER_ACCEPTED_SOURCE_VIEW_REQUESTS"}

    def record(self, scene_id: str, owner_key: str, study_ref: str, action: str,
               camera_id: str | None = None, frame_ref: str | None = None,
               evidence_ref: str | None = None) -> Json:
        if action not in {"correction", "evidence_open"}:
            raise ValueError("STUDY_ACTION_REQUIRES_SERVER_VIEW")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = self._read(connection, study_ref)
            _, binding, task, frames = self._authorize(state, scene_id, owner_key,
                                                     require_running=True)
            refs: dict[str, str] = {}
            if action == "correction":
                matched = next((frame for frame in frames
                                if self._frame_ref(binding, frame) == frame_ref), None)
                if (frame_ref not in state["issued_frames"] or matched is None
                        or camera_id not in (None, matched.camera_id) or evidence_ref is not None):
                    raise ValueError("STUDY_CORRECTION_REQUIRES_VIEWED_FRAME")
                refs = {"frame_ref": str(frame_ref), "camera_id": matched.camera_id}
            else:
                if (state["mode"] != "assisted" or evidence_ref not in state["issued_evidence"]
                        or camera_id is not None or frame_ref is not None):
                    raise ValueError("STUDY_EVIDENCE_SCOPE_DENIED")
                refs = {"evidence_ref": str(evidence_ref)}
            self._tick(state)
            self._event(state, action, **refs)
            self._save(connection, state)
            return self._dto(state, task)

    def authorize_media(self, scene_id: str, owner_key: str, study_ref: str,
                        media_ref: str) -> None:
        """Authorize only original frames already issued by this owner-bound study view.

        Serving these bytes does not increment counters again. Terminal attempts retain
        their issued-source grants for inspection; they cannot issue additional frames.
        """
        self._guard_other_study(owner_key, study_ref)
        with self._connect() as connection:
            state = self._read(connection, study_ref)
            _, binding, _, frames = self._authorize(state, scene_id, owner_key)
            issued = {frame.media_ref for frame in frames
                      if self._frame_ref(binding, frame) in state["issued_frames"]}
            if media_ref not in issued:
                raise ValueError("STUDY_MEDIA_SCOPE_DENIED")

    @staticmethod
    def _answer(task: _Task, answer: object) -> tuple[Json, str]:
        if not isinstance(answer, dict):
            raise ValueError("INVALID_STUDY_ANSWER")
        if answer == {"unknown": True} and type(answer.get("unknown")) is bool:
            return {"unknown": True}, "UNKNOWN"
        answer_type = task.public["answer_type"]
        if set(answer) != {answer_type}:
            raise ValueError("INVALID_STUDY_ANSWER")
        value = answer[answer_type]
        if answer_type == "timestamp":
            value = _number(value)
            if value < 0:
                raise ValueError("INVALID_STUDY_ANSWER")
        elif answer_type == "presence":
            if value not in ("PRESENT", "MISSING"):
                raise ValueError("INVALID_STUDY_ANSWER")
        elif answer_type == "count":
            if type(value) is not int or value < 0 or value > _MAX_FRAME_METADATA:
                raise ValueError("INVALID_STUDY_ANSWER")
        elif answer_type == "order":
            if not isinstance(value, list) or value not in (["A", "B"], ["B", "A"]):
                raise ValueError("INVALID_STUDY_ANSWER")
        correct = value == task.expected
        return {answer_type: value}, "CORRECT" if correct else "INCORRECT"

    def submit(self, scene_id: str, owner_key: str, study_ref: str, answer: object) -> Json:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = self._read(connection, study_ref)
            _, _, task, _ = self._authorize(state, scene_id, owner_key, require_running=True)
            submitted, correctness = self._answer(task, answer)
            self._tick(state)
            self._event(state, "submit")
            state.update(status="COMPLETED", submitted_answer=submitted, correctness=correctness)
            self._save(connection, state)
            return self._report(connection, state, task)

    def stop(self, scene_id: str, owner_key: str, study_ref: str) -> Json:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = self._read(connection, study_ref)
            _, _, task, _ = self._authorize(state, scene_id, owner_key)
            if state["status"] != "RUNNING":
                raise ValueError("STUDY_ALREADY_TERMINAL")
            self._tick(state)
            self._event(state, "stop")
            state["status"] = "STOPPED"
            self._save(connection, state)
            return self._report(connection, state, task)

    def resume(self, scene_id: str, study_ref: str, recovery_token: str,
               new_owner_key: str) -> Json:
        owner_hash = _private_hash(new_owner_key)
        self._guard_other_study(new_owner_key, study_ref)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = self._read(connection, study_ref)
            if (state["binding"]["scene_id"] != scene_id
                    or not hmac.compare_digest(state["recovery_hash"],
                                               _private_hash(recovery_token))):
                raise ValueError("STUDY_RECOVERY_DENIED")
            _, binding, frames = self._source(scene_id)
            if binding != state["binding"]:
                raise ValueError("OPERATOR_STUDY_SOURCE_BINDING_CHANGED")
            if state["status"] in {"COMPLETED", "STOPPED"}:
                # Credential recovery restores inspection ownership, not execution.
                # Preserve all terminal timing, correctness and source grants exactly.
                state.update(owner_hash=owner_hash, resume_count=state["resume_count"] + 1)
                if len(state["events"]) < _MAX_EVENTS:
                    self._event(state, "terminal_ownership_recovery")
                self._save(connection, state)
                return self._report(connection, state,
                                    self._tasks(binding, frames)[state["task_ref"]])
            if any(row["owner_hash"] == owner_hash and row["status"] == "RUNNING"
                   and row["study_ref"] != study_ref for row in self._all(connection)):
                raise ValueError("STUDY_ACTIVE_STOP_OR_RESUME_FIRST")
            if state["clock_ref"] == self.clock_ref:
                self._tick(state)
            else:
                gap = max(0.0, time.time() - state["last_wall_s"])
                state["excluded_resume_gap_ms"] += int(gap * 1000)
            state.update(owner_hash=owner_hash, clock_ref=self.clock_ref,
                         last_monotonic_ns=time.monotonic_ns(), last_wall_s=time.time(),
                         resume_count=state["resume_count"] + 1)
            self._event(state, "resume")
            self._save(connection, state)
            return self._dto(state, self._tasks(binding, frames)[state["task_ref"]])

    def _guard_other_study(self, owner_key: str, requested_study_ref: str) -> None:
        """Commit the baseline audit before denying historical study assistance.

        Public callers invoke this before opening their own ledger transaction, so the
        denial cannot roll back the contamination record or nest SQLite write locks.
        """
        owner_hash = _private_hash(owner_key)
        denied = False
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for state in self._all(connection):
                if (state["owner_hash"] == owner_hash and state["mode"] == "manual"
                        and state["status"] == "RUNNING"
                        and state["study_ref"] != requested_study_ref):
                    self._tick(state)
                    state["protocol_valid"] = False
                    if "OTHER_STUDY_ACCESS" not in state["protocol_violations"]:
                        state["protocol_violations"].append("OTHER_STUDY_ACCESS")
                    if len(state["events"]) < _MAX_EVENTS:
                        self._event(state, "other_study_access_denied")
                    self._save(connection, state)
                    denied = True
        if denied:
            raise ValueError("MANUAL_BASELINE_OTHER_STUDY_ACCESS_DENIED")

    def guard_external(self, scene_id: str, owner_key: str, action: str) -> None:
        """Log contamination and deny assisted surfaces for any active manual owner.

        Checks all scenes so changing a dropdown cannot evade baseline isolation. Reads
        of study context/list/report and original granted media remain separate routes.
        """
        owner_hash = _private_hash(owner_key)
        denied = False
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for state in self._all(connection):
                if (state["owner_hash"] == owner_hash and state["mode"] == "manual"
                        and state["status"] == "RUNNING"):
                    self._tick(state)
                    state["protocol_valid"] = False
                    if "EXTERNAL_ASSISTED_ACCESS" not in state["protocol_violations"]:
                        state["protocol_violations"].append("EXTERNAL_ASSISTED_ACCESS")
                    # Caller-supplied action/scene are not exported or trusted references.
                    if len(state["events"]) < _MAX_EVENTS:
                        self._event(state, "external_assistance_denied")
                    self._save(connection, state)
                    denied = True
        if denied:
            raise ValueError("MANUAL_BASELINE_EXTERNAL_ASSISTANCE_DENIED")

    def _dto(self, state: Json, task: _Task) -> Json:
        elapsed = state["elapsed_ns"]
        if state["status"] == "RUNNING" and state["clock_ref"] == self.clock_ref:
            elapsed += max(0, time.monotonic_ns() - state["last_monotonic_ns"])
        events = state["events"]
        completed = state["status"] == "COMPLETED"
        valid = state["protocol_valid"]
        scene = self.catalog[state["binding"]["scene_id"]]
        issued_frames = [{"frame_ref": self._frame_ref(state["binding"], frame),
                          "camera_id": frame.camera_id, "timestamp": frame.timestamp,
                          "media_ref": frame.media_ref}
                         for frame in scene.service.frames.values()
                         if self._frame_ref(state["binding"], frame) in state["issued_frames"]]
        return {
            "schema_version": "operator.study.report.v1", "study_ref": state["study_ref"],
            "task": copy.deepcopy(task.public), "mode": state["mode"],
            "status": ("RESUME_REQUIRED" if state["status"] == "RUNNING"
                       and state["clock_ref"] != self.clock_ref else state["status"]),
            "phase": _PHASE, "reference_kind": _REFERENCE,
            "binding": copy.deepcopy(state["binding"]), "protocol_valid": valid,
            "protocol_violations": list(state["protocol_violations"]),
            "task_sequence": state["task_sequence"], "resume_count": state["resume_count"],
            "timing_basis": "SERVER_MONOTONIC_ACTIVE_SEGMENTS",
            "resume_gap_basis": "SERVER_WALL_APPROXIMATION_EXCLUDED_FROM_ACTIVE_DURATION",
            "measurement_scope": "SERVER_ACCEPTED_SOURCE_VIEW_REQUESTS",
            "actual_operator_acceptance": False, "efficiency_gain_claim": False,
            "submitted_answer": copy.deepcopy(state["submitted_answer"]),
            "issued_frames": sorted(issued_frames,
                                    key=lambda frame: (frame["camera_id"], frame["timestamp"])),
            "metrics": {
                "duration_ms": elapsed // 1_000_000,
                "excluded_resume_gap_ms": state["excluded_resume_gap_ms"],
                "camera_view_count": sum(event["action"] == "camera_view" for event in events),
                "frame_open_count": sum(event["action"] == "frame_open" for event in events),
                "distinct_camera_count": len({event["camera_id"] for event in events
                                               if event["action"] == "camera_view"}),
                "correction_count": sum(event["action"] == "correction" for event in events),
                "evidence_open_count": sum(event["action"] == "evidence_open" for event in events),
                "correctness": state["correctness"], "completed_denominator": int(completed),
                "eligible_completed_denominator": int(completed and valid),
                "correct_count": int(completed and state["correctness"] == "CORRECT"),
                "unresolved_count": int(completed and state["correctness"] == "UNKNOWN"),
                "protocol_excluded_count": int(not valid),
            },
        }

    def _report(self, connection: sqlite3.Connection, state: Json, task: _Task) -> Json:
        result = self._dto(state, task)
        matching = [row for row in self._all(connection)
                    if row["comparison_owner_hash"] == state["comparison_owner_hash"]
                    and row["binding"] == state["binding"] and row["task_ref"] == state["task_ref"]]
        modes: Json = {}
        for mode in ("manual", "assisted"):
            rows = [row for row in matching if row["mode"] == mode]
            completed = [row for row in rows if row["status"] == "COMPLETED"]
            eligible = [row for row in completed if row["protocol_valid"]]
            correct = [row for row in eligible if row["correctness"] == "CORRECT"]
            viewed_correct = [row for row in correct
                              if any(event["action"] == "frame_open" for event in row["events"])]
            modes[mode] = {"attempt_count": len(rows), "completed_denominator": len(completed),
                           "eligible_completed_denominator": len(eligible),
                           "correct_count": len(correct),
                           "incorrect_count": sum(row["correctness"] == "INCORRECT"
                                                  for row in eligible),
                           "unresolved_count": sum(row["correctness"] == "UNKNOWN"
                                                   for row in eligible),
                           "protocol_excluded_count": sum(not row["protocol_valid"]
                                                          for row in rows),
                           "stopped_count": sum(row["status"] == "STOPPED" for row in rows),
                           "viewed_correct_count": len(viewed_correct),
                           "correct_duration_ms": [row["elapsed_ns"] // 1_000_000
                                                   for row in correct]}
        paired = all(modes[mode]["correct_count"] == 1
                     and modes[mode]["viewed_correct_count"] == 1
                     and modes[mode]["eligible_completed_denominator"] == 1
                     and modes[mode]["attempt_count"] == 1 for mode in modes)
        result["comparison"] = {
            "status": "PAIRED_PREPARATION_REHEARSAL" if paired else "UNPAIRED_PREPARATION",
            "task_ref": state["task_ref"], "same_binding": True, "same_task": True,
            "same_operator_session_or_explicit_recovery": True,
            "modes": modes, "eligible_for_duration_comparison": paired,
            "order": [{"mode": row["mode"], "task_sequence": row["task_sequence"],
                       "status": row["status"]} for row in matching],
            "learning_effect_controlled": False, "efficiency_gain_claim": False,
        }
        return result

    def report(self, scene_id: str, owner_key: str, study_ref: str) -> Json:
        self._guard_other_study(owner_key, study_ref)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = self._read(connection, study_ref)
            _, _, task, _ = self._authorize(state, scene_id, owner_key)
            self._tick(state)
            self._save(connection, state)
            return self._report(connection, state, task)

    def list(self, scene_id: str, owner_key: str) -> Json:
        _, binding, frames = self._source(scene_id)
        tasks = self._tasks(binding, frames)
        owner_hash = _private_hash(owner_key)
        with self._connect() as connection:
            items = []
            for state in self._all(connection):
                if state["owner_hash"] != owner_hash or state["binding"] != binding:
                    continue
                dto = self._dto(state, tasks[state["task_ref"]])
                items.append({"study_ref": state["study_ref"], "task_ref": state["task_ref"],
                              "mode": state["mode"], "status": dto["status"], "phase": _PHASE,
                              "protocol_valid": state["protocol_valid"],
                              "duration_ms": dto["metrics"]["duration_ms"],
                              "correctness": state["correctness"]})
            return {"schema_version": "operator.study.list.v1", "phase": _PHASE,
                    "binding": binding, "items": items, "actual_operator_acceptance": False}
