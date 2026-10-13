"""Fixed subprocess entry point for existing E0 RGB inference only."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.association import (
    AssociationPolicy,
    InferenceBundle,
    InferenceScope,
    SyntheticStaticContext,
    build_inference,
)
from amidst.engineering.perception import PerceptionResult, RGBFrame, produce_perception
from amidst.engineering.registry import opaque_ref
from amidst.workbench.run_jobs import ACTIVE, bundle_counts, encode, now, validate_source

Json = dict[str, Any]


class Cancelled(Exception):
    pass


def _progress(db_path: Path, ref: str, parent_pid: int, phase: str, completed: int) -> None:
    if os.getppid() != parent_pid:
        raise Cancelled
    with sqlite3.connect(db_path, timeout=15) as db:
        row = db.execute("SELECT state,cancel FROM jobs WHERE job_ref=?", (ref,)).fetchone()
        if row is None or row[1] or row[0] not in ACTIVE:
            raise Cancelled
        db.execute("UPDATE jobs SET state='RUNNING',phase=?,completed=?,started_at=COALESCE("
                   "started_at,?) WHERE job_ref=?", (phase, completed, now(), ref))


def _write(path: Path, value: object) -> str:
    data = (encode(value) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(data)
    path.chmod(0o444)
    return hashlib.sha256(data).hexdigest()


def _candidate(row: Json, run_id: str, event_ref: str, rank: int) -> Json:
    keys = ("polyline", "path_length", "minimum_travel_time", "estimated_travel_time",
            "spatial_cost", "temporal_cost", "semantic_regions", "feasibility_flags",
            "path_score", "provenance")
    return {"candidate_ref": opaque_ref("candidate", run_id, event_ref, str(rank)),
            "rank": rank, **{k: row[k] for k in keys}}


def result_payload(spec: Json, perception: PerceptionResult, bundle: InferenceBundle) -> Json:
    public = spec["public"]
    run_id = public["new_run_id"]
    pixels = {m.observation_id: m for m in perception.measurements}
    projected = {p.observation_id: p for p in bundle.projected_measurements}
    frames = {f["media_ref"]: f for f in spec["frames"]}
    observations: list[Json] = []
    observation_refs: dict[str, str] = {}
    for rank, mapping in enumerate(bundle.local_record_maps):
        selected = [pixels[p] for p in mapping.original_pixel_observation_ids]
        ref = opaque_ref("observation", run_id, str(rank))
        observation_refs[mapping.canonical_observation_id] = ref
        observations.append({"observation_ref": ref,
            "camera_ids": [selected[0].camera_id],
            "time_range": [selected[0].timestamp, selected[-1].timestamp],
            "media_refs": list(dict.fromkeys(m.frame_ref for m in selected)),
            "projected_path": [{k: v for k, v in point.model_dump(mode="json").items()
                                if k not in {"point_id", "observation_id"}}
                               for m in selected
                               if (point := projected[m.observation_id].point) is not None],
            "region_ids": list(dict.fromkeys(r for m in selected
                                             for r in projected[m.observation_id].region_ids)),
            "measurement_count": len(selected), "evidence_state": "PROJECTED",
            "uncertainty": "Class-agnostic RGB components; local identities are provisional."})
    gaps = {g.event.event_id: g.event for g in bundle.snapshot.gaps}
    events: list[Json] = []
    semantic_events: list[Json] = []
    for rank, hypothesis in enumerate(bundle.association_hypotheses):
        ref = opaque_ref("event", run_id, str(rank))
        gap = gaps.get(hypothesis.event_id or "")
        candidates = [] if gap is None else [_candidate(c.model_dump(mode="json"), run_id, ref, i)
                                           for i, c in enumerate(gap.candidates, 1)]
        candidate_links = {} if gap is None else {
            c.candidate_id: candidates[i]["candidate_ref"] for i, c in enumerate(gap.candidates)}
        trajectories: list[Json] = []
        if gap is not None:
            for i, trajectory in enumerate(gap.trajectories):
                row = trajectory.model_dump(mode="json")
                trajectories.append({
                    "trajectory_ref": opaque_ref("trajectory", run_id, ref, str(i)),
                    "candidate_ref": candidate_links[row["candidate_id"]],
                    **{k: row[k] for k in ("kind", "timed_points", "segments",
                        "minimum_travel_time", "temporal_slack", "movement_duration",
                        "dwell_duration", "uncertainty", "provenance")}})
        source_frames = [{"frame_ref": media_ref, "camera_id": frames[media_ref]["camera_id"],
                          "timestamp": frames[media_ref]["timestamp"]}
                         for media_ref in dict.fromkeys(hypothesis.frame_refs)]
        event = {"event_ref": ref, "kind": hypothesis.kind, "status": hypothesis.status,
                 "camera_ids": list(hypothesis.camera_ids),
                 "time_range": list(hypothesis.time_range),
                 "observation_refs": [observation_refs[o]
                     for o in hypothesis.original_observation_ids if o in observation_refs],
                 "region_ids": list(hypothesis.region_ids), "source_frames": source_frames,
                 "media_refs": list(dict.fromkeys(hypothesis.frame_refs)),
                 "candidate_count": len(candidates), "hypothesis_count": len(trajectories),
                 "candidates": candidates, "trajectories": trajectories,
                 "termination_reason": hypothesis.termination_reason,
                 "complete": hypothesis.complete, "uncertainty": hypothesis.uncertainty,
                 "reason": hypothesis.reason, "alternatives": [hypothesis.uncertainty],
                 "evidence_state": "INFERRED_GAP" if gap else "PROJECTED"}
        events.append(event)
        semantic_events.append({k: v for k, v in event.items() if k not in {
            "event_ref", "observation_refs", "candidates", "trajectories"}} | {
            "observation_indices": [list(observation_refs).index(o)
                for o in hypothesis.original_observation_ids if o in observation_refs],
            "candidates": [{k: v for k, v in c.items() if k != "candidate_ref"}
                           for c in candidates],
            "trajectories": [{k: v for k, v in t.items()
                if k not in {"trajectory_ref", "candidate_ref"}} | {
                    "candidate_rank": next(c["rank"] for c in candidates
                                           if c["candidate_ref"] == t["candidate_ref"])}
                for t in trajectories]})
    counts = bundle_counts(bundle, len(spec["frames"]), len(perception.measurements),
                           len(perception.tracks))
    semantic = {"input_sha256": public["input_sha256"],
                "config_sha256": public["config_sha256"],
                "annotation_sha256": public["annotation_sha256"], "counts": counts,
                "measurements": [{k: v for k, v in m.model_dump(mode="json").items()
                    if k not in {"observation_id", "local_track_id", "run_id", "evidence_refs"}}
                    for m in perception.measurements],
                "observations": [{k: v for k, v in o.items() if k != "observation_ref"}
                                 for o in observations], "events": semantic_events}
    return {"schema_version": "workbench.synthetic-run-result.v1",
            **{k: public[k] for k in ("scene_id", "job_ref", "new_run_id", "source_run_id",
                "source_sha256", "annotation_version", "annotation_sha256", "input_sha256",
                "config_sha256")}, "deterministic_sha256": digest(semantic),
            "comparison": {"baseline": spec["baseline_counts"], "new": counts,
                "delta": {k: counts[k] - spec["baseline_counts"][k] for k in counts}},
            "observations": observations, "events": events,
            "annotation_labels": {r["object_id"]: r["label"] for r in spec["annotation_objects"]},
            "overlay_changes": spec["overlay_changes"], "producer_hashes": spec["producer_hashes"],
            "authority": "SYNTHETIC_CONFIGURED_PROVISIONAL", "formal_phase1_acceptance": False,
            "view_only": True, "external_model_calls": False,
            "limitations": list(bundle.limitations)}


def execute(db_path: Path, ref: str) -> None:
    parent_pid = os.getppid()
    with sqlite3.connect(db_path, timeout=15) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM jobs WHERE job_ref=?", (ref,)).fetchone()
    if row is None:
        raise ValueError("RUN_JOB_SCOPE_DENIED")
    spec: Json = json.loads(row["spec"])
    if digest(spec) != row["spec_hash"] or spec["public"]["job_ref"] != ref:
        raise ValueError("JOB_CONFIGURATION_CHANGED")
    _progress(db_path, ref, parent_pid, "VALIDATING_INPUTS", 0)
    validate_source(spec)
    frames = tuple(RGBFrame(media_ref=f["media_ref"], camera_id=f["camera_id"],
        timestamp=f["timestamp"], path=Path(spec["source_root"]) / f["relative_path"],
        sha256=f["sha256"], width=f["width"], height=f["height"]) for f in spec["frames"])
    _progress(db_path, ref, parent_pid, "RGB_MEASUREMENT", 1)
    perception = produce_perception(frames, model_id=spec["scope"]["model_id"],
                                    run_id=spec["public"]["new_run_id"])
    if not perception.complete:
        raise ValueError("RGB_MEASUREMENT_INCOMPLETE")
    _progress(db_path, ref, parent_pid, "ASSOCIATION", 2)
    context = SyntheticStaticContext.model_validate(spec["effective_context"])
    raw_scope = spec["scope"]
    scope = InferenceScope(
        place_id=raw_scope["place_id"], model_id=raw_scope["model_id"],
        model_revision=raw_scope["model_revision"], run_id=spec["public"]["new_run_id"],
        clock_id=raw_scope["clock_id"], source_ref=opaque_ref("source", raw_scope["source_id"],
            raw_scope["source_sha256"]), source_sha256=raw_scope["source_sha256"],
        spatial_context_id=context.spatial_context_id, context_sha256=context.context_sha256)
    bundle = build_inference(perception, scope=scope, context=context,
                             policy=AssociationPolicy.model_validate(spec["policy"]))
    _progress(db_path, ref, parent_pid, "FREEZING_RESULT", 3)
    validate_source(spec)
    result = result_payload(spec, perception, bundle)
    output = Path(spec["output_path"])
    if output.parent != db_path.parent or output.name != ref or output.is_symlink():
        raise ValueError("RUN_OUTPUT_SCOPE_DENIED")
    output.mkdir()
    artifacts = {
        "configuration.json": _write(output / "configuration.json", {
            "public": spec["public"], "effective_context": spec["effective_context"],
            "policy": spec["policy"], "annotation_objects": spec["annotation_objects"],
            "overlay_changes": spec["overlay_changes"],
            "producer_hashes": spec["producer_hashes"]}),
        "perception.json": _write(output / "perception.json", perception.model_dump(mode="json")),
        "inference.json": _write(output / "inference.json", bundle.model_dump(mode="json")),
        "result.json": _write(output / "result.json", result),
    }
    receipt_hash = _write(output / "receipt.json", {
        "schema_version": "workbench.synthetic-run-receipt.v1",
        "binding": spec["public"], "artifacts": artifacts,
        "deterministic_sha256": result["deterministic_sha256"],
        "rgb_regenerated": False, "truth_read": False, "evaluation_run": False,
        "formal_phase1_acceptance": False})
    _progress(db_path, ref, parent_pid, "FREEZING_RESULT", 3)
    validate_source(spec)
    with sqlite3.connect(db_path, timeout=15) as db:
        db.execute("""UPDATE jobs SET state='COMPLETED',phase='COMPLETED',completed=4,
            finished_at=?,result_hash=?,receipt_hash=?
            WHERE job_ref=? AND state='RUNNING' AND cancel=0""",
            (now(), artifacts["result.json"], receipt_hash, ref))


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(2)
    db_path, ref = Path(sys.argv[1]), sys.argv[2]
    try:
        execute(db_path, ref)
    except Exception as exc:
        # Only a finite public failure code is stored; no exception/path/token transcript.
        safe = {"SOURCE_CHANGED", "SOURCE_FILE_UNAVAILABLE", "PRODUCER_CHANGED",
                "JOB_CONFIGURATION_CHANGED", "RGB_MEASUREMENT_INCOMPLETE",
                "RUN_OUTPUT_SCOPE_DENIED"}
        code = str(exc) if isinstance(exc, ValueError) and str(exc) in safe else "PIPELINE_FAILED"
        with sqlite3.connect(db_path, timeout=15) as db:
            db.execute("""UPDATE jobs SET
                state=CASE WHEN cancel=1 THEN 'CANCELLED' ELSE 'FAILED' END,
                phase=CASE WHEN cancel=1 THEN 'CANCELLED' ELSE 'FAILED' END,finished_at=?,
                failure_code=CASE WHEN cancel=1 THEN NULL ELSE ? END
                WHERE job_ref=? AND state IN ('QUEUED','RUNNING','CANCEL_REQUESTED')""",
                (now(), code, ref))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
