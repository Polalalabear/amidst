"""Executable Blender RGB boundaries and explicitly separate substitute ports.

No Agent, renderer, stream, source modification or source copy is used. Actual
RGB measurements and camera-local kinematic curves are rerun from sanitized
inputs. Graph/history retain separate fixtures; materialized replay is verified.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol, cast

from amidst.engineering.registry import content_hash
from amidst.engineering.run import load_facades, materialize_run
from amidst.workbench.blender_association import BaselineAssociationIndex
from amidst.workbench.blender_association_media import AssociationScene
from amidst.workbench.blender_motion import BaselineMotionIndex
from amidst.workbench.blender_motion_media import MotionScene
from amidst.workbench.frame_baseline import BaselineFrameIndex
from amidst.workbench.reviews import ReviewStore, replay_review_delta
from amidst.workbench.scenes import SceneAdapter, load_synthetic_lab

Json = dict[str, Any]


class _BlenderProbeScene(Protocol):
    scene_id: str
    index: BaselineFrameIndex

    def export_safe_inputs(self) -> Json: ...
    def live_scope(self) -> Json: ...
    def snapshot(self) -> Json: ...
    def frames(self, camera_ids: Sequence[str], timestamp: float) -> Json: ...
    def media(self, ref: str) -> tuple[str, bytes]: ...


class _MotionProbeArtifacts(Protocol):
    def manifest(self, scene: MotionScene) -> Json: ...
    def media(self, scene: MotionScene, ref: str) -> tuple[str, bytes]: ...


class _AssociationProbeArtifacts(Protocol):
    def manifest(self, scene: AssociationScene) -> Json: ...
    def media(self, scene: AssociationScene, ref: str) -> tuple[str, bytes]: ...


def _image_chunks(raw: bytes) -> tuple[str, bool]:
    """Digest retained IDAT bytes without returning PNG metadata or image bytes."""
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("INVALID_PROBE_MEDIA")
    offset, image, text, ended = 8, bytearray(), False, False
    while offset < len(raw):
        if offset + 12 > len(raw):
            raise ValueError("INVALID_PROBE_MEDIA")
        size = int.from_bytes(raw[offset:offset + 4], "big")
        end = offset + size + 12
        if end > len(raw):
            raise ValueError("INVALID_PROBE_MEDIA")
        kind = raw[offset + 4:offset + 8]
        if kind == b"IDAT":
            image.extend(raw[offset:end])
        text |= kind in {b"tEXt", b"iTXt", b"zTXt"}
        offset = end
        if kind == b"IEND":
            ended = end == len(raw)
            break
    if not image or not ended:
        raise ValueError("INVALID_PROBE_MEDIA")
    return hashlib.sha256(image).hexdigest(), text


def _substitute_ports(root: Path) -> tuple[list[Json], Json]:
    """Actually run configured Graph/history, independently of Blender pixels."""
    config = {
        "schema_version": "simulation.engineering.config.v1", "model_id": "synthetic-lab-v1",
        "frame_count": 51, "fps": 5.0, "input_modes": ["photos_plus_observations"],
        "receiver": "LOCAL_DETERMINISTIC_IMAGE_ASSOCIATION",
        "decision_stage": "PIXEL_MEASUREMENT_THEN_PROVISIONAL_ASSOCIATION",
        "external_model_calls": False, "formal_phase1_acceptance": False,
    }
    config_path = root / "substitute-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    fixture = root / "substitute"
    manifest = materialize_run(fixture, config_path, run_id="blender-port-substitute-v1")
    facade = load_facades(fixture)[0]
    scene = load_synthetic_lab(fixture)
    scope = {
        "source_sha256": manifest.source_sha256, "model_id": manifest.scope.model_id,
        "model_revision": manifest.scope.model_revision, "run_id": manifest.scope.run_id,
        "clock_id": manifest.scope.clock_id, "config_sha256": manifest.config_sha256,
        "registry_sha256": manifest.registry_sha256,
        "snapshot_sha256": content_hash(facade.snapshot.model_dump(mode="json")),
    }
    gap = next((row for row in facade.snapshot.gaps if row.event.trajectories), None)
    graph = {
        "port": "graph.gaps", "from_layer": "isolated.procedural_RGB_observations",
        "to_layer": "configured.Graph_and_reconstruction", "data_kind": "SUBSTITUTE",
        "source_binding": scope,
        "input": {"observations": len(facade.snapshot.observations),
                  "rgb_frames": len(manifest.frame_links),
                  "constraints": ["configured_navigation", "clock", "speed", "bounded_search"],
                  "blender_pixels_used": False},
        "output": {"gaps": len(facade.snapshot.gaps),
                   "sample_candidate_count": len(gap.event.candidates) if gap else 0,
                   "sample_hypothesis_count": len(gap.event.trajectories) if gap else 0,
                   "termination_reason": gap.event.termination_reason.value if gap else None,
                   "blender_events_generated": False, "substitute_run_independent": True},
        "status": "PASS" if gap is not None else "FAIL",
    }
    snapshot = scene.snapshot()
    baseline = {key: snapshot[key] for key in
                ("scene_id", "source_hash", "model_revision", "run_id", "objects")}
    store = ReviewStore(root / "substitute-review.sqlite3", {scene.scene_id: baseline})
    obj = next(o for o in snapshot["objects"] if "label" in o["editable_fields"])
    draft = store.save_draft(scene.scene_id, obj["object_id"], {"label": "替代端口文件修改"},
                             0, "synthetic-test", "isolated substitute delta")
    store.validate_draft(draft["draft_id"])
    publication = store.publish_draft(draft["draft_id"], "synthetic-test",
                                      "isolated substitute delta", 0)
    delta = store.export_delta(scene.scene_id, 1)
    restored = replay_review_delta(store.state(scene.scene_id)["versions"][0], delta)
    current = publication["overlay"]
    history = {
        "port": "history.delta", "from_layer": "isolated.review_document_changes",
        "to_layer": "source_bound_delta_document", "data_kind": "SUBSTITUTE",
        "source_binding": scope,
        "input": {"base_version": 0, "changed_objects": 1, "changed_fields": ["label"],
                  "blender_scene_reviewed": False},
        "output": {"delta": delta, "restored_sha256": content_hash(restored),
                   "published_sha256": content_hash(current),
                   "replay_matches": restored == current,
                   "needs_rerun": any(row.get("status") == "NEEDS_RERUN"
                                      for row in publication.get("affected_runs", [])),
                   "source_assets_copied": False},
        "status": "PASS" if restored == current else "FAIL",
    }
    return [graph, history], scope


def run_blender_port_probe(scene: SceneAdapter,
                           motion_artifacts: _MotionProbeArtifacts | None = None,
                           association_artifacts: _AssociationProbeArtifacts | None = None) -> Json:
    """Rerun one Blender site's pixels, preserving every actual/substitute boundary."""
    adapter = cast(_BlenderProbeScene, scene)
    scope_before = adapter.live_scope()
    original = adapter.index.snapshot()
    original_sha256 = content_hash(original)
    inputs = adapter.export_safe_inputs()
    index = BaselineFrameIndex(inputs)
    rerun = index.snapshot()
    binding = rerun["source_binding"]
    cameras = sorted(row["camera_id"] for row in inputs["cameras"])
    times = sorted(row["timestamp"] for row in inputs["frames"])
    start, end = float(times[0]), min(float(times[-1]), float(times[0]) + 10.0)
    target = (start + end) / 2
    query = index.query(cameras, start, end, target, 3)
    motion = BaselineMotionIndex(rerun).reconstruct(cameras, start, end)
    operator_motion = BaselineMotionIndex(original).reconstruct(cameras, start, end)
    association = BaselineAssociationIndex(rerun).reconstruct(cameras, start, end, 3)
    operator_association = BaselineAssociationIndex(original).reconstruct(cameras, start, end, 3)
    repeated = index.query(cameras, start, end, target, 3)
    timeline = adapter.frames(cameras, target)
    media_rows = {row["frame_ref"]: row for row in inputs["frames"]}
    samples = []
    for frame in timeline["frames"]:
        if frame["frame_ref"] is None:
            continue
        row = media_rows[frame["frame_ref"]]
        raw = Path(row["local_path"]).read_bytes()
        mime, served = adapter.media(frame["frame_ref"])
        original_idat, _ = _image_chunks(raw)
        served_idat, served_text = _image_chunks(served)
        original_hash = hashlib.sha256(raw).hexdigest()
        served_hash = hashlib.sha256(served).hexdigest()
        samples.append({
            "frame_ref": frame["frame_ref"], "camera_id": row["camera_id"],
            "timestamp": row["timestamp"], "mime": mime,
            "original_sha256": original_hash, "served_sha256": served_hash,
            "original_bytes": len(raw), "served_bytes": len(served),
            "idat_sha256": original_idat, "pixels_unchanged": original_idat == served_idat,
            "public_text_metadata_removed": not served_text,
            "manifest_hashes_match": (original_hash == row["sha256"]
                                      and served_hash == row["served_sha256"]),
        })
        if len(samples) == 2:
            break
    ports: list[Json] = []

    def actual(name: str, source: str, target_layer: str,
               input_data: Json, output_data: Json, passed: bool) -> None:
        ports.append({"port": name, "from_layer": source, "to_layer": target_layer,
                      "data_kind": "ACTUAL_BLENDER", "source_binding": copy.deepcopy(binding),
                      "input": input_data, "output": output_data,
                      "status": "PASS" if passed else "FAIL"})

    actual("source.rgb", "source.Blender_camera_render", "RGB_pixel_producer",
           {"cameras": len(cameras), "rgb_frames": len(inputs["frames"]),
            "time_range": [start, end], "target_and_motion": "SUBSTITUTE_SYNTHETIC",
            "renderer_annotations_used": False},
           {"rgb_frames": len(index.frame_records), "public_media_samples": samples,
            "original_images_copied": False},
           len(index.frame_records) == len(inputs["frames"]) and bool(samples)
           and all(row["manifest_hashes_match"] and row["pixels_unchanged"]
                   and row["public_text_metadata_removed"] for row in samples))
    presentation = adapter.snapshot().get("presentation", {})
    model_summary = {key: presentation.get(key) for key in (
        "authority", "default_material", "source_archive_sha256", "evaluated_scene",
        "archive_is_whole_scene", "selected_object_count", "selected_objects_complete",
        "display_triangle_count", "truncated", "whole_scene_occlusion_proof",
        "physical_authority_changed", "source_geometry_modified",
    )}
    actual("source.model", "original.evaluated_source_mesh_archive", "workbench.smooth_3D_context",
           {"source_sha256": binding["source_sha256"], "source_asset_opened": False,
            "source_saved": False, "source_copied": False},
           {"materialization_status": "PARTIAL", "model": model_summary},
           bool(presentation.get("meshes")) and presentation.get("display_triangle_count", 0) > 0
           and presentation.get("physical_authority_changed") is False
           and presentation.get("source_geometry_modified") is False)
    measurements = rerun["measurements"]
    projected = rerun["projected_measurements"]
    sample = measurements[0] if measurements else None
    sample_projected = projected[0] if projected else None
    actual("perception.measurements", "actual.Blender_RGB_pixels", "camera_local_pixel_components",
           {"rgb_frames": len(index.frame_records), "measurement_source": "RGB_PIXELS",
            "input_manifest_sha256": index.telemetry["input_manifest_sha256"]},
           {"measurements": len(measurements), "local_tracks": len(rerun["local_tracks"]),
            "sample": sample, "frame_status_counts": index.telemetry["frame_status_counts"],
            "producer_sha256": rerun["producer_sha256"], "identity_verdict": "UNCONFIRMED"},
           len(measurements) == index.telemetry["pixel_measurements"])
    sample_camera = next((row["calibration"] for row in inputs["cameras"]
                          if sample is not None and row["camera_id"] == sample["camera_id"]), None)
    floor = {key: rerun["floor_plane"][key] for key in
             ("point", "normal", "source_sha256", "authority", "floor_id")}
    actual("geometry.projected", "camera_pixel_contact_and_source_calibration",
           "approved_floor_intersection",
           {"contact_pixel": sample["contact_pixel"] if sample else None,
            "calibration": sample_camera, "floor_plane": floor, "units": "METRES"},
           {"projected_measurements": index.telemetry["projected_measurements"],
            "projection_attempts": len(projected), "sample": sample_projected,
            "walkability_proven": False, "whole_scene_visibility_proven": False},
           len(projected) == len(measurements)
           and floor["source_sha256"] == binding["source_sha256"])
    with TemporaryDirectory(prefix="amidst-blender-ports-") as directory:
        root = Path(directory)
        safe_file = root / "pixel-snapshot.json"
        safe_file.write_text(json.dumps(rerun, ensure_ascii=False, allow_nan=False),
                             encoding="utf-8")
        reopened = json.loads(safe_file.read_bytes())
        rerun_sha256 = content_hash(rerun)
        actual("repository.snapshot", "rerun.safe_pixel_projection_snapshot", "LOCAL_JSON.reopen",
               {"snapshot_sha256": rerun_sha256, "frames": len(index.frame_records),
                "measurements": len(measurements)},
               {"reopened_sha256": content_hash(reopened), "canonical_refs_and_order_preserved":
                reopened == rerun, "operator_snapshot_sha256": original_sha256,
                "rerun_matches_operator_index": rerun_sha256 == original_sha256},
               reopened == rerun and rerun_sha256 == original_sha256)
        actual("retrieval.features", "import_built.camera_time_pixel_index",
               "scoped_frame_features",
               {"camera_ids": cameras, "time_range": [start, end],
                "target_timestamp": target, "top_k": 3},
               {"retrieval": query["retrieval"], "status": query["status"],
                "source_features": query["source_features"]},
               query["retrieval"]["global_scan"] is False
               and query["retrieval"]["bytes_read"] == 0
               and query["retrieval"]["frames_read"] == 0)
        actual("baseline.top_k", "scoped_pixel_features", "deterministic_frame_ranking",
               {"behavior_intent": "walking", "intent_authority": "USER_SELECTED_INTENT",
                "top_k": 3, "agent_used": False},
               {"items": query["items"], "status": query["status"], "ranking": query["ranking"],
                "deterministic_repeat_matches": repeated == query,
                "query_sha256": content_hash(query), "behavior_verdict": query["behavior_verdict"]},
               query == repeated and len(query["items"]) <= 3 and query["agent_used"] is False)
        actual("presentation.frames", "source.camera_time_and_authorized_media",
               "workbench.camera_images_and_3D_context",
               {"camera_ids": cameras, "timestamp": target, "top_k_media_refs":
                [row["media_ref"] for row in query["items"]]},
               {"timeline": timeline, "public_media_samples": samples,
                "new_video_generated": False, "display_only": True},
               len(timeline["frames"]) == len(cameras) and bool(samples)
               and all(row["pixels_unchanged"] for row in samples))
        substitute, substitute_scope = _substitute_ports(root)
        ports.extend(substitute)
    contaminated = copy.deepcopy(inputs)
    contaminated["ground_truth"] = {"forbidden_position": [999, 999, 999]}
    contaminated["trajectory"] = {"forbidden_recipe": "MUST_NOT_BE_READ"}
    for row in contaminated["frames"]:
        row["visibility"] = "FAKE_CONFIRMED"
        row["ground_truth"] = {"forbidden_pixel": [999, 999]}
    poisoned = BaselineFrameIndex(contaminated)
    unchanged = content_hash(poisoned.snapshot()) == content_hash(rerun)
    actual("truth.isolation", "extra_truth_recipe_and_visibility_fields",
           "explicit_camera_time_RGB_allowlist",
           {"poisoned_private_copy_only": True, "source_files_changed": False,
            "pixels_and_calibration": "UNCHANGED"},
           {"safe_snapshot_unchanged": unchanged, "features_unchanged":
            poisoned.source_features == index.source_features,
            "query_unchanged": poisoned.query(cameras, start, end, target, 3) == query,
            "motion_unchanged": BaselineMotionIndex(poisoned.snapshot()).reconstruct(
                cameras, start, end) == motion,
            "association_unchanged": BaselineAssociationIndex(poisoned.snapshot()).reconstruct(
                cameras, start, end, 3) == association, "evaluation": "NOT_RUN"},
           unchanged and poisoned.query(cameras, start, end, target, 3) == query
           and BaselineMotionIndex(poisoned.snapshot()).reconstruct(cameras, start, end) == motion
           and BaselineAssociationIndex(poisoned.snapshot()).reconstruct(
               cameras, start, end, 3) == association)
    actual("physics.curves", "camera_local_projected_pixel_tracks",
           "bounded_position_time_velocity_and_provisional_events",
           {"source_features": index.source_features, "units": "METRES",
            "policy": motion["policy"], "camera_ids": cameras, "time_range": [start, end]},
           {"summary": motion["summary"], "reconstruction_sha256": motion["reconstruction_sha256"],
            "sample_track": motion["tracks"][0] if motion["tracks"] else None,
            "camera_coverage": motion["camera_coverage"], "retrieval": motion["retrieval"],
            "agent_used": False, "collision_and_navigation_checked": False,
            "rerun_matches_operator": motion == operator_motion,
            "deterministic_repeat": BaselineMotionIndex(rerun).reconstruct(
                cameras, start, end) == motion},
           motion == operator_motion and motion["retrieval"]["bytes_read"] == 0
           and motion["agent_used"] is False)
    motion_scene = cast(MotionScene, scene)
    artifact_state: Json = (motion_artifacts.manifest(motion_scene)
                           if motion_artifacts is not None else {
        "status": "UNAVAILABLE", "items": [], "reason": "NOT_MATERIALIZED"})
    if artifact_state["status"] == "AVAILABLE":
        assert motion_artifacts is not None
        artifact_checks = []
        for item in artifact_state["items"]:
            mime, data = motion_artifacts.media(motion_scene, item["media_ref"])
            sha256 = hashlib.sha256(data).hexdigest()
            artifact_checks.append({"media_ref": item["media_ref"], "kind": item["kind"],
                                    "mime_type": mime, "byte_count": len(data),
                                    "sha256": sha256,
                                    "hash_matches": sha256 == item["sha256"]
                                    and len(data) == item["byte_count"]})
        actual("reconstruction.video", "actual_pixel_kinematic_curves_and_source_RGB",
               "materialized_diagnostic_reconstruction_replay",
               {"reconstruction_sha256": motion["reconstruction_sha256"],
                "source_features": index.source_features, "agent_used": False},
               {"materialization_status": "MATERIALIZED", "artifacts": artifact_state,
                "binary_checks": artifact_checks, "source_blend_opened_or_copied": False,
                "semantic_event_confirmed": False},
               artifact_state["reconstruction_sha256"] == motion["reconstruction_sha256"]
               and len(artifact_checks) == 2
               and all(row["hash_matches"] for row in artifact_checks))
    else:
        ports.append({"port": "reconstruction.video", "data_kind": "DEFERRED",
                      "from_layer": "actual_pixel_kinematic_curves", "to_layer": "replay_media",
                      "status": "DEFERRED", "input": {"reconstruction_sha256":
                                                        motion["reconstruction_sha256"]},
                      "output": {"materialization_status": "NOT_MATERIALIZED",
                                 "reason": artifact_state["reason"]}})
    actual("association.cross_camera", "camera_local_connected_floor_segments",
           "time_speed_floor_compatibility_graph",
           {"source_features": index.source_features, "camera_ids": cameras,
            "time_range": [start, end], "policy": association["policy"]},
           {"association_status": association["status"], "summary": association["summary"],
            "association_sha256": association["association_sha256"],
            "camera_coverage": association["camera_coverage"],
            "sample_edges": association["graph"]["edges"][:2],
            "rejected_edge_reason_counts": {
                reason: sum(row["reason"] == reason
                            for row in association["graph"]["rejected_edges"])
                for reason in sorted({row["reason"]
                                      for row in association["graph"]["rejected_edges"]})},
            "identity_confirmed": False, "geometry_authority": "SOURCE_BOUND_FLOOR_ONLY",
            "rerun_matches_operator": association == operator_association},
           association == operator_association and association["agent_used"] is False)
    actual("association.top_k", "source_bound_cross_camera_graph",
           "bounded_distinct_global_hypotheses_and_unassociated_baseline",
           {"top_k": 3, "canonical_search_scope": "SELECTED_CAMERAS_FULL_SOURCE_TIME",
            "agent_used": False},
           {"association_status": association["status"], "search": association["search"],
            "retrieval": association["retrieval"],
            "candidate_summaries": [{"rank": row["rank"], "score": row["score"],
                "candidate_ref": row["candidate_ref"], "paths": len(row["paths"]),
                "selected_edges": len(row["selected_edge_refs"]),
                "unassociated_nodes": len(row["unassociated_node_refs"]),
                "identity_verdict": row["identity_verdict"]}
                for row in association["candidates"]],
            "unassociated_baseline_retained": association["baseline_candidate"][
                "is_unassociated_baseline"],
            "deterministic_repeat": association == BaselineAssociationIndex(rerun).reconstruct(
                cameras, start, end, 3), "probability_or_accuracy_claim": False},
           len(association["candidates"]) <= 3
           and len({row["candidate_ref"] for row in association["candidates"]})
           == len(association["candidates"])
           and association["baseline_candidate"]["is_unassociated_baseline"]
           and association["retrieval"]["frames_read"] == 0
           and association["retrieval"]["bytes_read"] == 0)
    association_scene = cast(AssociationScene, scene)
    cross_artifact_state: Json = (association_artifacts.manifest(association_scene)
                                 if association_artifacts is not None else {
        "status": "UNAVAILABLE", "items": [], "reason": "NOT_MATERIALIZED"})
    if cross_artifact_state["status"] == "AVAILABLE":
        assert association_artifacts is not None
        cross_checks = []
        for item in cross_artifact_state["items"]:
            mime, data = association_artifacts.media(association_scene, item["media_ref"])
            digest = hashlib.sha256(data).hexdigest()
            cross_checks.append({"media_ref": item["media_ref"], "kind": item["kind"],
                                 "mime_type": mime, "byte_count": len(data), "sha256": digest,
                                 "hash_matches": digest == item["sha256"]
                                 and len(data) == item["byte_count"]})
        actual("association.video", "actual_source_RGB_and_provisional_top_k_paths",
               "pre_materialized_synchronized_3D_curves_and_replay",
               {"association_sha256": association["association_sha256"],
                "source_features": index.source_features, "agent_used": False},
               {"materialization_status": "MATERIALIZED", "artifacts": cross_artifact_state,
                "binary_checks": cross_checks, "identity_or_semantic_event_confirmed": False,
                "source_blend_opened_or_copied": False},
               cross_artifact_state["association_sha256"] == association["association_sha256"]
               and len(cross_checks) == 2 and all(row["hash_matches"] for row in cross_checks))
    else:
        ports.append({"port": "association.video", "data_kind": "DEFERRED",
                      "from_layer": "source_bound_provisional_top_k_paths",
                      "to_layer": "synchronized_replay_media", "status": "DEFERRED",
                      "input": {"association_sha256": association["association_sha256"]},
                      "output": {"materialization_status": "NOT_MATERIALIZED",
                                 "reason": cross_artifact_state["reason"]}})
    operator_unchanged = (adapter.live_scope() == scope_before
                          and content_hash(adapter.index.snapshot()) == original_sha256)
    completed = [row for row in ports if row["status"] != "DEFERRED"]
    passed = all(row["status"] == "PASS" for row in completed) and operator_unchanged
    return {
        "schema_version": "workbench.blender-system-ports.v1",
        "status": "PASS" if passed else "FAIL", "data_kind": "BLENDER_WITH_EXPLICIT_SUBSTITUTES",
        "selected_scene_id": adapter.scene_id, "selected_scene_used_as_input": True,
        "source_binding": binding, "ports": ports,
        "source_types": {"actual_blender": {
            "binding": binding, "rgb": "SOURCE_CAMERA_RENDER_WITH_SYNTHETIC_TARGET",
            "model": "PARTIAL_SOURCE_EVALUATED_GEOMETRY",
            "measurements": "RERUN_FROM_RGB_PIXELS",
            "projection": "APPROVED_FLOOR_INTERSECTION_WITH_UNCERTAINTY",
        }, "substitute": {"binding": substitute_scope,
                          "ports": ["graph.gaps", "history.delta"],
                          "blender_pixels_used": False},
            "deferred": (["reconstruction.video"] if artifact_state["status"] != "AVAILABLE"
                         else []) + (["association.video"]
                                     if cross_artifact_state["status"] != "AVAILABLE" else [])
            + ["real_camera_stream", "accounts_and_deployment"],
            "physical_inference": "FLOOR_KINEMATICS_AND_PROVISIONAL_CROSS_CAMERA_HYPOTHESES"},
        "summary": {"passed": sum(row["status"] == "PASS" for row in completed),
                    "total": len(completed), "deferred": len(ports) - len(completed),
                    "ports_total": len(ports),
                    "actual_blender_ports": sum(row["data_kind"] == "ACTUAL_BLENDER"
                                                for row in completed), "substitute_ports": 2,
                    "selected_scene_used_as_input": True,
                    "source_rgb_frames": len(index.frame_records),
                    "rerun_matches_operator_index": content_hash(rerun) == original_sha256,
                    "operator_run_modified": not operator_unchanged,
                    "isolated_substitute_fixture": True, "formal_acceptance": False,
                    "agent_calls": 0, "external_model_calls": 0, "blend_copies": 0,
                    "new_video_generated": False,
                    "video_materialized": artifact_state["status"] == "AVAILABLE",
                    "association_video_materialized": cross_artifact_state["status"] == "AVAILABLE",
                    "cross_camera_status": association["status"],
                    "real_stream": "FUTURE",
                    "accounts_and_deployment": "DEFERRED"},
    }
