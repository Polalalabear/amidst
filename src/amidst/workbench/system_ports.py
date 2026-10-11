"""Executable, isolated synthetic port probe using the real deterministic modules.

The temporary fixture is deliberately separate from the operator's frozen scene.
It runs no Blender render, external model, evaluation or production deployment.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from amidst.engineering.registry import content_hash
from amidst.engineering.run import load_facades, materialize_run
from amidst.workbench.navigation_guidance import GuidanceIndex, mock_decide
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.scenes import load_synthetic_lab


def _read(root: Path, name: str) -> dict[str, Any]:
    result: dict[str, Any] = json.loads((root / name).read_bytes())
    return result


def run_port_probe() -> dict[str, Any]:
    """Exercise every engineering boundary with fresh pixels and frozen outputs."""
    with TemporaryDirectory(prefix="amidst-system-ports-") as directory:
        root = Path(directory)
        config = {
            "schema_version": "simulation.engineering.config.v1",
            "model_id": "synthetic-lab-v1", "frame_count": 51, "fps": 5.0,
            "input_modes": ["photos_only", "photos_plus_observations"],
            "receiver": "LOCAL_DETERMINISTIC_IMAGE_ASSOCIATION",
            "decision_stage": "PIXEL_MEASUREMENT_THEN_PROVISIONAL_ASSOCIATION",
            "external_model_calls": False, "formal_phase1_acceptance": False,
        }
        config_path = root / "probe-config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        manifest = materialize_run(root / "fixture", config_path, run_id="system-port-fixture-v1")
        fixture = root / "fixture"
        scene = load_synthetic_lab(fixture)
        snapshot = scene.snapshot()
        perception = _read(fixture, "perception_photos_plus_observations.json")
        inference = _read(fixture, "inference_photos_plus_observations.json")
        facades = load_facades(fixture)
        facade = next(f for f in facades
                      if f.guard.binding.observation_mode == "photos_plus_observations")
        camera_id = str(snapshot["cameras"][0]["camera_id"])
        index = GuidanceIndex(scene)
        guide = index.guide("navigation", camera_id, 0.0, 10.0, "walking", 3)
        agent_input = guide["agent_input"]
        agent_output = mock_decide(agent_input)
        query = scene.query(camera_id, 0.0, 10.0)
        gap = next(g for g in facade.snapshot.gaps if g.event.trajectories)
        event = next(e for e in facade.events if e.canonical_event_id == gap.event.event_id)
        replay = facade.invoke("get_replay", {
            "session_ref": facade.guard.session_ref, "event_ref": event.event_ref,
            "timestamp": sum(event.time_range) / 2,
        })
        media_ref = next(iter(manifest.frame_links.values()))
        mime, pixels = scene.media(media_ref)
        measurement = perception["measurements"][0]
        projected = inference["projected_measurements"][0]
        ports: list[dict[str, Any]] = []

        def port(name: str, source: str, target: str, input_data: dict[str, Any],
                 output_data: dict[str, Any], passed: bool) -> None:
            ports.append({"port": name, "from_layer": source, "to_layer": target,
                          "input": input_data, "output": output_data,
                          "status": "PASS" if passed else "FAIL"})

        port("source.rgb", "synthetic.generate_sequence", "perception.produce_perception",
             {"cameras": 2, "frames_per_camera": 51, "fps": 5.0,
              "time_range": [0.0, 10.0], "annotations": "NONE"},
             {"rgb_frames": len(manifest.frame_links), "media_ref": media_ref,
              "mime": mime, "image_sha256": hashlib.sha256(pixels).hexdigest(),
              "source_sha256": manifest.source_sha256},
             len(manifest.frame_links) == 102 and mime == "image/png" and bool(pixels))
        port("perception.measurements", "perception.produce_perception",
             "association.build_inference",
             {"rgb_frames": len(manifest.frame_links), "measurement_source": "RGB_PIXELS"},
             {"measurements": len(perception["measurements"]),
              "local_tracks": len(perception["tracks"]), "sample": {
                  key: measurement[key] for key in
                  ("camera_id", "timestamp", "bbox_xyxy", "contact_pixel", "status")}},
             bool(perception["measurements"]) and bool(perception["tracks"]))
        port("geometry.projected", "association._project", "observation.aggregation",
             {"contact_pixel": measurement["contact_pixel"], "camera_id": camera_id,
              "calibration": "CONFIGURED_AFFINE_GROUND_PLANE", "units": "metres"},
             {"projected_measurements": len(inference["projected_measurements"]),
              "sample": {key: projected[key] for key in
                         ("camera_id", "timestamp", "status") if key in projected},
              "world_position": (projected.get("point") or {}).get("world_position")},
             bool(inference["projected_measurements"]))
        port("graph.gaps", "observation.aggregation", "graph+reconstruction",
             {"observations": len(facade.snapshot.observations),
              "hard_constraints": ["configured_navigation", "clock", "speed", "bounded_search"]},
             {"gaps": len(facade.snapshot.gaps),
              "candidate_count": len(gap.event.candidates),
              "hypothesis_count": len(gap.event.trajectories),
              "termination_reason": gap.event.termination_reason.value,
              "complete": event.complete},
             bool(gap.event.candidates) and bool(gap.event.trajectories))
        frozen_hash = content_hash(facade.snapshot.model_dump(mode="json"))
        reopened = next(f for f in load_facades(fixture)
                        if f.guard.binding.observation_mode == "photos_plus_observations")
        port("repository.snapshot", "graph+reconstruction", "LOCAL_JSON.repository",
             {"snapshot_sha256": frozen_hash, "observations": len(facade.snapshot.observations),
              "events": len(facade.snapshot.gaps)},
             {"reopened_sha256": content_hash(reopened.snapshot.model_dump(mode="json")),
              "canonical_ids_and_order_preserved": reopened.snapshot == facade.snapshot},
             reopened.snapshot == facade.snapshot)
        port("retrieval.features", "LOCAL_JSON.repository", "scoped.camera_time_index",
             {"camera_id": camera_id, "time_range": [0.0, 10.0], "label": "navigation"},
             {"observations": len(query["observations"]), "events": len(query["events"]),
              "retrieval": query["retrieval"], "guide_status": guide["status"]},
             bool(query["observations"]) and guide["status"] == "READY")
        port("agent.navigation", "label.graph_preprocessor", "MockAgent",
             {"label": "navigation", "behavior": "walking", "top_k": 3,
              "input_sha256": content_hash(agent_input)},
             {"output_sha256": content_hash(agent_output), "output": agent_output,
              "external_model_calls": 0},
             bool(agent_input) and bool(agent_output))
        port("presentation.replay", "frozen.event", "workbench.3D_timeline",
             {"event_ref": event.event_ref, "timestamp": sum(event.time_range) / 2,
              "hypothesis_count": len(gap.event.trajectories)},
             {"replay": replay, "presentation_only": True,
              "inference_sha256": frozen_hash},
             bool(replay) and content_hash(facade.snapshot.model_dump(mode="json")) == frozen_hash)

        review_keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
        reviews = ReviewStore(root / "review.sqlite3", {
            scene.scene_id: {key: snapshot[key] for key in review_keys}})
        obj = next(o for o in snapshot["objects"] if "label" in o["editable_fields"])
        draft = reviews.save_draft(scene.scene_id, obj["object_id"], {"label": "端口測試修改"},
                                   0, "synthetic-test", "isolated delta probe")
        reviews.validate_draft(draft["draft_id"])
        publication = reviews.publish_draft(draft["draft_id"], "synthetic-test",
                                            "isolated delta probe", 0)
        delta = reviews.export_delta(scene.scene_id, 1)
        port("history.delta", "human_review.document_changes", "Git_reviewable_delta_document",
             {"base_version": 0, "changed_fields": ["label"], "changed_objects": 1},
             {"schema_version": delta["schema_version"], "version": 1, "delta": delta,
              "needs_rerun": any(item.get("status") == "NEEDS_RERUN"
                                 for item in publication.get("affected_runs", [])),
              "blend_copied": False},
             delta["schema_version"] == "workbench.scene-review-delta.v1")

        # Only the isolated simulation sidecar is poisoned; no operator artifact changes.
        (fixture / "simulation/export/ground_truth.json").write_bytes(b"GT_POISON_NOT_JSON")
        poisoned = next(f for f in load_facades(fixture)
                        if f.guard.binding.observation_mode == "photos_plus_observations")
        unchanged = poisoned.snapshot == facade.snapshot
        port("truth.isolation", "simulation.export.GT", "inference_boundary",
             {"gt_sidecar": "POISONED_AFTER_FREEZE", "rgb_and_calibration": "UNCHANGED"},
             {"snapshot_unchanged": unchanged, "evaluation": "NOT_RUN"}, unchanged)
        passed = all(item["status"] == "PASS" for item in ports)
        return {
            "schema_version": "workbench.system-ports.v1",
            "status": "PASS" if passed else "FAIL", "data_kind": "SYNTHETIC_PORT_TEST",
            "ports": ports, "agent_input": agent_input, "agent_output": agent_output,
            "summary": {"passed": sum(p["status"] == "PASS" for p in ports),
                        "total": len(ports), "isolated_fixture": True,
                        "operator_run_modified": False, "formal_acceptance": False,
                        "real_stream": "FUTURE", "accounts_and_deployment": "DEFERRED",
                        "external_model_calls": 0, "blend_copies": 0},
        }
