"""Read-only Blender source export from an independently validated frozen lock.

Run freeze_export in the locked project environment first. This Blender producer
uses the original camera/raycaster functions, never renders or saves the source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def export(lock_path: Path, expected_lock_sha256: str, output: Path) -> dict[str, Any]:
    import bpy  # type: ignore[import-not-found]
    from mathutils import Matrix  # type: ignore[import-not-found]

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(root / "scripts"))
    from export_blender_pilot import annotation_objects, project
    from export_phase1_reviewed_inputs import inclusive_timestamps, sample_waypoints

    from amidst.finalization.reviewed_reference_movement import (
        ReferenceMovementApproval,
        build_reference_annotation_document,
    )
    from amidst.simulation.blender_camera import extract_camera_dict
    from amidst.simulation.blender_visibility import BlenderMeshRaycaster

    if digest(lock_path) != expected_lock_sha256:
        raise ValueError("frozen preflight export lock changed")
    lock = json.loads(lock_path.read_bytes())
    if lock.get("status") != "FROZEN_BEFORE_SOURCE_SIMULATION":
        raise ValueError("independently validated frozen export lock required")
    config = lock["config"]
    movement = ReferenceMovementApproval(**lock["reference_movement_approval"])
    movement.validate()
    source = Path(bpy.data.filepath).resolve()
    before = digest(source), source.stat().st_size, source.stat().st_mtime_ns
    if before != (lock["source_sha256"], lock["source_size_bytes"], lock["source_mtime_ns"]):
        raise ValueError("actual source changed after frozen preflight")
    if output.exists():
        raise FileExistsError("new versioned dataset directory required")
    bindings = {b["camera"]["camera_id"]: b for b in lock["camera_bindings"]}
    scene = bpy.context.scene
    scene.render.resolution_x = config["width"]
    scene.render.resolution_y = config["height"]
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.use_border = scene.render.use_crop_to_border = False
    cameras = {name: extract_camera_dict(scene, bpy.data.objects[name]) for name in bindings}
    if any(cameras[name] != bindings[name]["camera"] for name in bindings):
        raise ValueError("fresh source calibration differs from approved exact binding")
    raycaster = BlenderMeshRaycaster(scene, excluded_objects=annotation_objects(bpy, scene))
    summaries = []
    for case in config["cases"]:
        identity = case["case_id"]
        target = "scoped_" + identity
        version = config["dataset_version"]
        context_id = "SCOPED_CORRIDOR_" + version.upper() + ":" + identity.upper()
        trajectory_id = "SCOPED_CORRIDOR_TRAJECTORY_" + version + ":" + identity
        waypoints = case["waypoints"]
        timestamps = inclusive_timestamps(waypoints[0]["timestamp"], waypoints[-1]["timestamp"], 5)
        frames, truth = [], []
        for index, timestamp in enumerate(timestamps):
            foot = sample_waypoints(waypoints, timestamp)
            truth.append(
                {"timestamp": timestamp, "position": foot, "floor_id": lock["floor"]["floor_id"]}
            )
            for camera_id in sorted(case["camera_ids"]):
                camera = cameras[camera_id]
                offset = bindings[camera_id]["landmark_offset_bu"]
                landmark = [p + o for p, o in zip(foot, offset, strict=True)]
                projection = project(camera, landmark, Matrix)
                reason, occluder = projection["reason"], None
                if reason == "IN_FRUSTUM":
                    matrix = camera["camera_to_world"]
                    ray = raycaster(tuple(matrix[a][3] for a in range(3)), tuple(landmark))
                    reason, occluder = ray.reason, ray.occluder_id
                observed = reason == "CLEAR"
                frames.append(
                    {
                        "frame_id": index,
                        "timestamp": timestamp,
                        "target_id": target,
                        "camera_id": camera_id,
                        "status": "OBSERVED" if observed else "GAP",
                        "point_2d": projection["pixel"] if observed else None,
                        "provenance": "OBSERVED" if observed else None,
                        "gap_reason": None if observed else reason,
                        "occluder_id": occluder,
                        "data_kind": "SYNTHETIC",
                    }
                )
        observations = {
            "label": "PILOT / SYNTHETIC SAMPLE",
            "data_kind": "SYNTHETIC",
            "site_id": "approved-corridor",
            "source_asset_sha256": before[0],
            "frames": frames,
        }
        write(output / "inference" / identity / "observations.json", observations)
        write(
            output / "inference" / identity / "context.json",
            {
                "schema_version": "phase1-scoped-source-context-v1",
                "source_id": "scoped_export:" + version + ":" + identity,
                "source_sha256": before[0],
                "spatial_context_id": context_id,
                "scope_id": lock["scope_id"],
                "authority": lock["authority"],
                "camera_bindings": [bindings[c] for c in sorted(case["camera_ids"])],
                "coordinate_units": "BLENDER_NATIVE_UNITS",
                "metres_per_blender_unit": 0.0247,
                "observations_sha256": digest(
                    output / "inference" / identity / "observations.json"
                ),
                "config_file_sha256": lock["config_file_sha256"],
                "export_lock_file_sha256": expected_lock_sha256,
                "ground_truth_available_to_inference": False,
            },
        )
        write(
            output / "evaluation" / identity / "ground_truth.json",
            {
                "provenance": "GROUND_TRUTH",
                "source_sha256": before[0],
                "trajectory_id": trajectory_id,
                "spatial_context_id": context_id,
                "target_id": target,
                "coordinate_units": "BLENDER_NATIVE_UNITS",
                "samples": truth,
            },
        )
        write(
            output / "evaluation" / identity / "reference_movement_annotations.json",
            build_reference_annotation_document(
                waypoints,
                movement,
                target_id=target,
                trajectory_id=trajectory_id,
                dataset_version=config["dataset_version"],
            ),
        )
        write(output / "simulation" / identity / "recipe.json", case)
        summaries.append(
            {
                "case_id": identity,
                "timestamp_count": len(timestamps),
                "observed_records": sum(f["status"] == "OBSERVED" for f in frames),
                "gap_records": sum(f["status"] == "GAP" for f in frames),
                "formal_case_readiness": False,
            }
        )
    after = digest(source), source.stat().st_size, source.stat().st_mtime_ns
    if before != after:
        raise RuntimeError("source changed during unsaved source export")
    manifest = {
        "schema_version": "phase1-scoped-source-dataset-v1",
        "status": "SOURCE_EXPORTED_FORMAL_READINESS_PENDING",
        "dataset_version": config["dataset_version"],
        "source_sha256": before[0],
        "config_file_sha256": lock["config_file_sha256"],
        "export_lock_file_sha256": expected_lock_sha256,
        "full_experiment_config_file_sha256": lock["full_experiment_config_file_sha256"],
        "reference_movement_approval_receipt_content_sha256": movement.receipt_content_sha256,
        "reference_movement_policy_content_sha256": movement.proposal_content_sha256,
        "sampling_fps": 5,
        "blender_version": bpy.app.version_string,
        "blender_build": bpy.app.build_hash.decode(),
        "source_size_bytes": before[1],
        "source_mtime_ns": before[2],
        "export_seed": config["export_seed"],
        "inference_seed": config["inference_seed"],
        "source_saved": False,
        "source_rendered": False,
        "formal_case_readiness": False,
        "ground_truth_partition": "evaluation",
        "recipe_partition": "simulation",
        "cases": summaries,
        "producer_hashes": {
            str(p.relative_to(root)): digest(p)
            for p in (
                Path(__file__),
                root / "scripts/export_blender_pilot.py",
                root / "scripts/export_phase1_reviewed_inputs.py",
                root / "src/amidst/finalization/reviewed_reference_movement.py",
                root / "src/amidst/simulation/blender_camera.py",
                root / "src/amidst/simulation/blender_visibility.py",
            )
        },
        "artifacts": {
            str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*.json"))
        },
    }
    write(output / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--expected-lock-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    result = export(args.lock, args.expected_lock_sha256, args.output)
    print(json.dumps({"status": result["status"], "cases": result["cases"]}), flush=True)
