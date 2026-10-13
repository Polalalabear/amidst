"""One fixed-source E0 inference job queue; no rendering, truth or evaluation.

HTTP role/session guards belong to Workbench. This manager accepts no caller
path, command, camera subset, model selection or input records. Source frames
remain registered immutable assets; every job owns a new output namespace.
"""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import math
import re
import sqlite3
import subprocess
import sys
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.association import (
    AssociationPolicy,
    InferenceBundle,
    SyntheticStaticContext,
)
from amidst.engineering.registry import LocationRegistry
from amidst.engineering.run import (
    EngineeringConfig,
    RunManifest,
    algorithm_hashes,
    effective_config_hash,
)
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.scenes import SceneAdapter

Json = dict[str, Any]
ACTIVE = ("QUEUED", "RUNNING", "CANCEL_REQUESTED")
TERMINAL = ("COMPLETED", "CANCELLED", "FAILED", "INTERRUPTED")
PARAMETERS = {
    "appearance_max_distance": {"default": 110.0, "min": 1.0, "max": 255.0},
    "max_speed_m_s": {"default": 3.0, "min": 0.1, "max": 20.0},
    "max_sample_gap_s": {"default": 0.6, "min": 0.01, "max": 5.0},
    "max_association_gap_s": {"default": 12.0, "min": 0.1, "max": 30.0},
    "max_overlap_separation_m": {"default": 2.0, "min": 0.01, "max": 10.0},
    "projection_uncertainty_m": {"default": 0.5, "min": 0.01, "max": 5.0},
}
SOURCE_FILES = ("run_manifest.json", "registry.json", "static_context.json",
                "engineering_config.json", "inference_photos_plus_observations.json")


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def encode(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def implementation_hashes() -> dict[str, str]:
    return algorithm_hashes() | {
        "workbench/" + name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ("run_jobs.py", "run_worker.py")
    }


def verified_file(path: Path, root: Path, expected: str | None = None) -> str:
    if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError("SOURCE_FILE_UNAVAILABLE")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected is not None and actual != expected:
        raise ValueError("SOURCE_CHANGED")
    return actual


def validate_source(spec: Json) -> None:
    root = Path(spec["source_root"])
    for relative, expected in spec["source_files"].items():
        verified_file(root / relative, root, expected)
    for frame in spec["frames"]:
        path = root / frame["relative_path"]
        verified_file(path, root, frame["sha256"])
        if path.stat().st_size != frame["size_bytes"]:
            raise ValueError("SOURCE_CHANGED")
    if implementation_hashes() != spec["producer_hashes"]:
        raise ValueError("PRODUCER_CHANGED")


def _rectangle(geometry: Json, z: float) -> tuple[float, float, float, float]:
    points = geometry.get("points", [])
    if geometry.get("type") != "polygon" or len(points) != 4:
        raise ValueError("UNSUPPORTED_OVERLAY_GEOMETRY")
    if any(len(p) != 3 or abs(p[2] - z) > 1e-9 for p in points):
        raise ValueError("UNSUPPORTED_OVERLAY_PLANE")
    xs, ys = sorted({p[0] for p in points}), sorted({p[1] for p in points})
    if len(xs) != 2 or len(ys) != 2 or set((p[0], p[1]) for p in points) != {
        (x, y) for x in xs for y in ys
    }:
        raise ValueError("UNSUPPORTED_OVERLAY_GEOMETRY")
    # Boundary order must describe the rectangle, rather than a self-crossing polygon.
    if any(a[0] != b[0] and a[1] != b[1]
           for a, b in zip(points, points[1:] + points[:1], strict=True)):
        raise ValueError("UNSUPPORTED_OVERLAY_GEOMETRY")
    return xs[0], ys[0], xs[1], ys[1]


def configured_context(original: SyntheticStaticContext, baseline: list[Json],
                       objects: list[Json]) -> tuple[SyntheticStaticContext, list[Json]]:
    """Translate every supported leaf; reject all other changes explicitly."""
    before = {row["object_id"]: row for row in baseline}
    after = {row["object_id"]: row for row in objects}
    if before.keys() != after.keys() or len(after) != len(objects):
        raise ValueError("UNSUPPORTED_OVERLAY_OBJECTS")
    context = original.model_dump(mode="json")
    changes: list[Json] = []
    for identity, row in after.items():
        old = before[identity]
        for field in row.keys() | old.keys():
            if row.get(field) == old.get(field):
                continue
            kind = old["kind"]
            if field == "label":
                changes.append({"object_id": identity, "field": field,
                                "effect": "PRESENTATION_ONLY", "value": row[field]})
            elif field == "geometry" and kind in {"WALKABLE", "REGION"}:
                bounds = _rectangle(row[field], original.ground_plane.point[2])
                if kind == "WALKABLE":
                    context["walkable_bounds_xy_m"] = bounds
                else:
                    target = next(r for r in context["regions"]
                                  if r["region_id"] == old["properties"]["region_id"])
                    target["bounds_xy_m"] = bounds
                changes.append({"object_id": identity, "field": field,
                                "effect": "CONFIGURED_STATIC_CONTEXT"})
            elif field == "properties" and kind == "CAMERA":
                keys = row[field].keys() | old[field].keys()
                if any(row[field].get(k) != old[field].get(k)
                       for k in keys - {"ground_to_pixel"}):
                    raise ValueError("UNSUPPORTED_OVERLAY_CAMERA_PROPERTIES")
                target = next(c for c in context["calibrations"]
                              if c["camera_id"] == identity.removeprefix("camera:"))
                if target["affine_ground_to_pixel"] is None:
                    raise ValueError("UNSUPPORTED_OVERLAY_CALIBRATION")
                target["affine_ground_to_pixel"] = row[field]["ground_to_pixel"]
                changes.append({"object_id": identity, "field": "properties.ground_to_pixel",
                                "effect": "CONFIGURED_STATIC_CONTEXT"})
            else:
                raise ValueError("UNSUPPORTED_OVERLAY_FIELD:" + kind + "." + field)
    # A derived configured-context hash keeps the original source hash unchanged.
    if context != original.model_dump(mode="json"):
        context["context_sha256"] = digest(context)
    return SyntheticStaticContext.model_validate(context), changes


def _parameters(supplied: Json) -> AssociationPolicy:
    if not isinstance(supplied, dict) or not supplied.keys() <= PARAMETERS.keys():
        raise ValueError("UNSUPPORTED_RUN_PARAMETERS")
    values = {name: limits["default"] for name, limits in PARAMETERS.items()}
    for name, value in supplied.items():
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not PARAMETERS[name]["min"] <= value <= PARAMETERS[name]["max"]):
            raise ValueError("INVALID_RUN_PARAMETER:" + name)
        values[name] = float(value)
    return AssociationPolicy.model_validate(values)


def bundle_counts(bundle: InferenceBundle, frame_count: int, measurements: int,
                  tracks: int) -> Json:
    return {"frames": frame_count, "measurements": measurements, "local_tracks": tracks,
            "observations": len(bundle.local_record_maps),
            "events": len(bundle.association_hypotheses), "gaps": len(bundle.snapshot.gaps),
            "candidates": sum(len(g.event.candidates) for g in bundle.snapshot.gaps)}


class SingleSyntheticRunManager:
    """Durable single-active-job manager bound to one server-registered source."""

    def __init__(self, source_scene: SceneAdapter, reviews: ReviewStore,
                 output_root: Path) -> None:
        if (source_scene.service.scope.source_id != "procedural-rgb-lab-v1"
                or source_scene.snapshot()["evidence_level"] != "E0_AFFINE_RGB_FIXTURE"):
            raise ValueError("UNSUPPORTED_RUN_SOURCE")
        self.scene, self.reviews = source_scene, reviews
        self.source_root = source_scene.service.store.media_root.resolve()
        output_root = Path(output_root)
        if output_root.is_symlink() or output_root.resolve().is_relative_to(self.source_root):
            raise ValueError("RUN_OUTPUT_SCOPE_DENIED")
        output_root.mkdir(parents=True, exist_ok=True)
        self.output_root = output_root.resolve()
        self.db_path = self.output_root / "jobs.sqlite3"
        lock_path = self.output_root / "owner.lock"
        if self.db_path.is_symlink() or lock_path.is_symlink():
            raise ValueError("RUN_OUTPUT_SCOPE_DENIED")
        self._owner = lock_path.open("a+b")
        try:
            fcntl.flock(self._owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._owner.close()
            raise ValueError("RUN_MANAGER_ALREADY_ACTIVE") from None
        self._lock = threading.RLock()
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._watchers: list[threading.Thread] = []
        self._closed = False
        try:
            self._source_files = {name: verified_file(self.source_root / name, self.source_root)
                                  for name in SOURCE_FILES}
            self._context = SyntheticStaticContext.model_validate_json(
                (self.source_root / "static_context.json").read_bytes())
            self._baseline_bundle = InferenceBundle.model_validate_json(
                (self.source_root / "inference_photos_plus_observations.json").read_bytes())
            manifest = RunManifest.model_validate_json(
                (self.source_root / "run_manifest.json").read_bytes())
            registry = LocationRegistry.model_validate_json(
                (self.source_root / "registry.json").read_bytes())
            engineering = EngineeringConfig.model_validate_json(
                (self.source_root / "engineering_config.json").read_bytes())
            receipt = next((r for r in manifest.receipts
                            if r.binding.observation_mode == "photos_plus_observations"), None)
            if (manifest.scope != self.scene.service.scope or receipt is None
                    or receipt.binding != self.scene.service.guard.binding
                    or "freeze-" + receipt.receipt_sha256 != self.scene.snapshot()["freeze_ref"]
                    or registry != self.scene.service.store.registry
                    or receipt.inference_sha256 != digest(self._baseline_bundle)
                    or self._baseline_bundle.static_context_sha256 != digest(self._context)
                    or self._context.source_sha256 != self.scene.source_hash
                    or self._context.context_sha256 != manifest.scope.spatial_context_sha256
                    or manifest.config_sha256 != effective_config_hash(
                        engineering, manifest.generator_config_sha256, self._context,
                        self._baseline_bundle.policy, manifest.algorithm_hashes)):
                raise ValueError("RUN_SOURCE_FREEZE_MISMATCH")
            source_binding = {"scene_id": self.scene.scene_id,
                              "snapshot_sha256": digest(self.scene.snapshot()),
                              "source_files": self._source_files}
            with self._db() as db:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY, payload TEXT);
                    CREATE TABLE IF NOT EXISTS jobs (
                        job_ref TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL,
                        request_hash TEXT NOT NULL, spec TEXT NOT NULL, spec_hash TEXT NOT NULL,
                        public TEXT NOT NULL, state TEXT NOT NULL, phase TEXT NOT NULL,
                        completed INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 4,
                        started_at TEXT, finished_at TEXT, cancel INTEGER NOT NULL DEFAULT 0,
                        failure_code TEXT, result_hash TEXT, receipt_hash TEXT);
                    CREATE UNIQUE INDEX IF NOT EXISTS jobs_single_active ON jobs((1))
                        WHERE state IN ('QUEUED','RUNNING','CANCEL_REQUESTED');
                """)
                stored = db.execute("SELECT payload FROM metadata WHERE id=1").fetchone()
                if stored is None:
                    db.execute("INSERT INTO metadata VALUES (1,?)", (encode(source_binding),))
                elif json.loads(stored[0]) != source_binding:
                    raise ValueError("RUN_SOURCE_REGISTRATION_MISMATCH")
                db.execute("""UPDATE jobs SET state='INTERRUPTED', phase='INTERRUPTED',
                    finished_at=?,failure_code='SERVER_RESTART_INTERRUPTED'
                    WHERE state IN ('QUEUED','RUNNING','CANCEL_REQUESTED')""", (now(),))
        except BaseException:
            self._owner.close()
            raise

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.db_path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def _scope(self, scene_id: str) -> None:
        if self._closed:
            raise ValueError("RUN_MANAGER_CLOSED")
        if scene_id != self.scene.scene_id:
            raise ValueError("RUN_SCENE_SCOPE_DENIED")

    @staticmethod
    def _public(row: sqlite3.Row) -> Json:
        public: Json = json.loads(row["public"])
        return public | {"state": row["state"], "phase": row["phase"],
                         "progress": {"completed": row["completed"], "total": row["total"]},
                         "started_at": row["started_at"], "finished_at": row["finished_at"],
                         "cancel_requested": bool(row["cancel"]),
                         "failure_code": row["failure_code"],
                         "result_available": row["state"] == "COMPLETED"}

    def context(self, scene_id: str) -> Json:
        self._scope(scene_id)
        return {"schema_version": "workbench.synthetic-jobs.v1", "available": True,
                "pipeline": "E0_RGB_ASSOCIATION", "scene_id": scene_id,
                "source_run_id": self.scene.run_id, "source_sha256": self.scene.source_hash,
                "current_annotation_version": self.reviews.state(scene_id)["current_version"],
                "supported_parameters": copy.deepcopy(PARAMETERS),
                "supported_overlay_fields": ["WALKABLE.geometry(rectangle, same plane)",
                    "REGION.geometry(rectangle, same plane)", "CAMERA.properties.ground_to_pixel",
                    "label(presentation-only)"], "max_active_jobs": 1,
                "limitations": ["Existing procedural RGB only; no render or truth input.",
                    "Configured synthetic association; no confirmed identity or formal acceptance.",
                    "Results are separate view-only runs; original frozen scenes remain unchanged.",
                    "Other overlay changes are rejected, rather than silently omitted."]}

    def start(self, scene_id: str, annotation_version: int, parameters: Json,
              idempotency_key: str) -> Json:
        self._scope(scene_id)
        if (not isinstance(annotation_version, int) or isinstance(annotation_version, bool)
                or annotation_version < 0):
            raise ValueError("ANNOTATION_VERSION_INVALID")
        if not isinstance(idempotency_key, str) or re.fullmatch(
            r"[A-Za-z0-9_-]{1,128}", idempotency_key
        ) is None:
            raise ValueError("IDEMPOTENCY_KEY_INVALID")
        policy = _parameters(parameters)
        request_hash = digest({"scene_id": scene_id, "annotation_version": annotation_version,
                               "policy": policy.model_dump(mode="json")})
        with self._lock:
            with self._db() as db:
                previous = db.execute("SELECT * FROM jobs WHERE idempotency_key=?",
                                      (idempotency_key,)).fetchone()
                if previous is not None:
                    if previous["request_hash"] != request_hash:
                        raise ValueError("IDEMPOTENCY_CONFLICT")
                    return self._public(previous)
                if db.execute("SELECT 1 FROM jobs WHERE state IN (?,?,?)", ACTIVE).fetchone():
                    raise ValueError("RUN_JOB_ALREADY_ACTIVE")
            state = self.reviews.state(scene_id)
            versions = state["versions"]
            if annotation_version >= len(versions):
                raise ValueError("ANNOTATION_VERSION_UNAVAILABLE")
            publication = versions[annotation_version]
            if publication["source_hash"] != self.scene.source_hash:
                raise ValueError("ANNOTATION_SOURCE_MISMATCH")
            effective_context, changes = configured_context(
                self._context, state["baseline_objects"], publication["objects"])
            frames = [f.model_dump(mode="json") for f in self.scene.service.frames.values()]
            if not frames or len(frames) > 2000:
                raise ValueError("RUN_FRAME_BUDGET_DENIED")
            spec: Json = {"source_root": str(self.source_root),
                          "source_files": self._source_files, "frames": frames,
                          "producer_hashes": implementation_hashes()}
            validate_source(spec)
            input_hash = digest([{k: f[k] for k in (
                "media_ref", "camera_id", "timestamp", "sha256", "width", "height")}
                for f in frames])
            config_hash = digest({"context": effective_context.model_dump(mode="json"),
                                  "policy": policy.model_dump(mode="json"),
                                  "producer_hashes": spec["producer_hashes"]})
            job_ref = "runjob-" + uuid.uuid4().hex
            run_id = "synthetic-job-" + uuid.uuid4().hex
            public = {"schema_version": "workbench.synthetic-job.v1", "job_ref": job_ref,
                      "new_run_id": run_id, "scene_id": scene_id,
                      "source_run_id": self.scene.run_id, "source_sha256": self.scene.source_hash,
                      "source_freeze_ref": self.scene.snapshot()["freeze_ref"],
                      "annotation_version": annotation_version,
                      "annotation_sha256": digest(publication), "input_sha256": input_hash,
                      "config_sha256": config_hash, "producer_hashes": spec["producer_hashes"],
                      "created_at": now()}
            spec |= {"public": public, "output_path": str(self.output_root / job_ref),
                     "scope": self.scene.service.scope.model_dump(mode="json"),
                     "effective_context": effective_context.model_dump(mode="json"),
                     "policy": policy.model_dump(mode="json"), "overlay_changes": changes,
                     "annotation_objects": publication["objects"],
                     "baseline_counts": bundle_counts(self._baseline_bundle, len(frames),
                         len(self._baseline_bundle.projected_measurements),
                         len({r.local_track_id for r in self._baseline_bundle.local_record_maps}))}
            with self._db() as db:
                db.execute("""INSERT INTO jobs (job_ref,idempotency_key,request_hash,spec,spec_hash,
                    public,state,phase) VALUES (?,?,?,?,?,?,'QUEUED','QUEUED')""",
                    (job_ref, idempotency_key, request_hash, encode(spec), digest(spec),
                     encode(public)))
            try:
                process = subprocess.Popen(
                    [sys.executable, "-m", "amidst.workbench.run_worker",
                     str(self.db_path), job_ref],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    cwd=Path(__file__).resolve().parents[3],
                )
            except OSError:
                self._terminal(job_ref, "FAILED", "WORKER_START_FAILED")
            else:
                self._processes[job_ref] = process
                watcher = threading.Thread(target=self._watch, args=(job_ref, process), daemon=True)
                self._watchers.append(watcher)
                watcher.start()
            return self.get(scene_id, job_ref)

    def _terminal(self, ref: str, state: str, failure: str | None = None) -> None:
        with self._db() as db:
            db.execute("""UPDATE jobs SET state=?,phase=?,finished_at=?,failure_code=?
                WHERE job_ref=? AND state IN ('QUEUED','RUNNING','CANCEL_REQUESTED')""",
                (state, state, now(), failure, ref))

    def _watch(self, ref: str, process: subprocess.Popen[bytes]) -> None:
        process.wait()
        with self._lock:
            with self._db() as db:
                row = db.execute("SELECT state,cancel FROM jobs WHERE job_ref=?", (ref,)).fetchone()
            if row is not None and row["state"] in ACTIVE:
                self._terminal(ref, "CANCELLED" if row["cancel"] else "FAILED",
                               None if row["cancel"] else "WORKER_EXIT_FAILED")
            self._processes.pop(ref, None)

    def list(self, scene_id: str) -> Json:
        self._scope(scene_id)
        with self._db() as db:
            rows = db.execute("SELECT * FROM jobs ORDER BY rowid DESC LIMIT 101").fetchall()
            return {"items": [self._public(row) for row in rows[:100]],
                    "truncated": len(rows) > 100, "limit": 100}

    def get(self, scene_id: str, job_ref: str) -> Json:
        self._scope(scene_id)
        if not isinstance(job_ref, str) or re.fullmatch(r"runjob-[0-9a-f]{32}", job_ref) is None:
            raise ValueError("RUN_JOB_SCOPE_DENIED")
        with self._db() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_ref=?", (job_ref,)).fetchone()
            if row is None:
                raise ValueError("RUN_JOB_SCOPE_DENIED")
            return self._public(row)

    def cancel(self, scene_id: str, job_ref: str) -> Json:
        with self._lock:
            job = self.get(scene_id, job_ref)
            if job["state"] in ACTIVE:
                with self._db() as db:
                    db.execute("""UPDATE jobs SET state='CANCEL_REQUESTED',phase='CANCEL_REQUESTED',
                        cancel=1 WHERE job_ref=? AND state IN ('QUEUED','RUNNING')""", (job_ref,))
                process = self._processes.get(job_ref)
                if process is not None and process.poll() is None:
                    process.terminate()
            return self.get(scene_id, job_ref)

    def result(self, scene_id: str, job_ref: str) -> Json:
        job = self.get(scene_id, job_ref)
        if job["state"] != "COMPLETED":
            raise ValueError("RUN_RESULT_UNAVAILABLE")
        with self._db() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_ref=?", (job_ref,)).fetchone()
        assert row is not None
        spec: Json = json.loads(row["spec"])
        if digest(spec) != row["spec_hash"]:
            raise ValueError("JOB_CONFIGURATION_CHANGED")
        validate_source(spec)
        path = self.output_root / job_ref / "result.json"
        verified_file(path, self.output_root, row["result_hash"])
        value: Json = json.loads(path.read_bytes())
        for key in ("job_ref", "new_run_id", "source_run_id", "source_sha256", "scene_id",
                    "annotation_version", "annotation_sha256", "input_sha256", "config_sha256"):
            if value[key] != job[key]:
                raise ValueError("RUN_RESULT_BINDING_MISMATCH")
        receipt_path = path.with_name("receipt.json")
        verified_file(receipt_path, self.output_root, row["receipt_hash"])
        receipt: Json = json.loads(receipt_path.read_bytes())
        if (receipt["binding"] != spec["public"]
                or receipt["deterministic_sha256"] != value["deterministic_sha256"]):
            raise ValueError("RUN_RESULT_BINDING_MISMATCH")
        for name, expected in receipt["artifacts"].items():
            if name not in {"result.json", "perception.json", "inference.json",
                            "configuration.json"}:
                raise ValueError("RUN_RESULT_ARTIFACT_MISMATCH")
            verified_file(path.parent / name, self.output_root, expected)
        return value

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for ref, process in tuple(self._processes.items()):
                self._terminal(ref, "INTERRUPTED", "SERVER_SHUTDOWN_INTERRUPTED")
                if process.poll() is None:
                    process.terminate()
        for watcher in self._watchers:
            watcher.join(timeout=10)
        self._owner.close()
