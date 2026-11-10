#!/usr/bin/env python3
"""Render an isolated RGB-only dual-camera run; source .blend is never saved."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main():
    import bpy
    from amidst.simulation.blender_camera import extract_camera_dict
    from export_blender_pilot import configure_render

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    config = json.loads(args.config.read_text())
    source = Path(bpy.data.filepath)
    fingerprint = (sha(source), source.stat().st_size, source.stat().st_mtime_ns)
    assert fingerprint[0] == config["source_sha256"]
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("Experiment output already exists")
    # 34 RGB PNGs + two lossless previews; conservative 128 MiB allowance.
    required = 128 * 1024 * 1024
    if shutil.disk_usage(output.parent).free - required < 8 * 1024**3:
        raise RuntimeError("DISK_BELOW_8_GIB_AFTER_RENDER_BUDGET")
    print("RENDER_BUDGET_BYTES=" + str(required), flush=True)
    output.mkdir()
    try:
        scene = bpy.context.scene
        scene.frame_set(220, subframe=0)
        policy = configure_render(bpy, config["width"], config["height"])
        scale = config["metres_per_bu"]
        cameras = []
        for name in config["camera_ids"]:
            calibration = extract_camera_dict(scene, bpy.data.objects[name])
            for axis in range(3):
                calibration["camera_to_world"][axis][3] *= scale
            calibration["clip_start"] *= scale
            calibration["clip_end"] *= scale
            cameras.append({"camera_id": name, "calibration": calibration})
        bpy.ops.mesh.primitive_cylinder_add(vertices=96,
            radius=config["radius_m"] / scale, depth=config["height_m"] / scale)
        target = bpy.context.object
        target.name = "DUAL_CAMERA_VALIDATION_CYLINDER"
        target.color = (1.0, 0.18, 0.015, 1.0)
        for polygon in target.data.polygons:
            polygon.use_smooth = len(polygon.vertices) == 4
        frames, truth = [], []
        for index in range(config["frame_count"]):
            timestamp = index / config["sampling_hz"]
            position = [config["start_m"][axis] + config["velocity_m_s"][axis] * timestamp
                        for axis in range(3)]
            target.location = [p / scale for p in position]
            target.location.z += config["height_m"] / (2 * scale)
            bpy.context.view_layer.update()
            truth.append({"timestamp": timestamp, "target_id": target.name,
                          "foot_center_m": position})
            for camera in cameras:
                if shutil.disk_usage(output).free < 8 * 1024**3:
                    raise RuntimeError("DISK_BELOW_8_GIB")
                name = camera["camera_id"]
                relative = f"frames/{name}/{index:03d}.png"
                path = output / relative
                path.parent.mkdir(exist_ok=True, parents=True)
                scene.camera = bpy.data.objects[name]
                scene.render.filepath = str(path)
                bpy.ops.render.render(write_still=True)
                frames.append({"camera_id": name, "timestamp": timestamp,
                    "frame_index": index, "rgb_ref": relative, "sha256": sha(path),
                    "byte_count": path.stat().st_size, "width": config["width"],
                    "height": config["height"], "origin": "ACTUAL_BLENDER_RGB"})
        # Safe manifest contains no object identity, trajectory, visibility, depth or GT.
        calibration_hash = hashlib.sha256(json.dumps(cameras, sort_keys=True).encode()).hexdigest()
        write(output / "inputs.json", {"schema_version": "dual-camera.rgb-inputs.v1",
            "source_sha256": fingerprint[0], "scale_sha256": config["scale_sha256"],
            "metres_per_bu": scale, "run_id": config["run_id"],
            "clock_id": "DUAL_CAMERA_SHARED_SECONDS", "camera_time_offsets_s": {c["camera_id"]: 0 for c in cameras},
            "calibration_version": "SOURCE_FRAME_220_960x540_UNMODIFIED",
            "calibration_sha256": calibration_hash, "cameras": cameras,
            "floor_plane": {"point": [0, 0, config["floor_z_m"]], "normal": [0, 0, 1]},
            "frames": frames})
        write(output / "evaluation_only.json", {"evaluation_only": True, "samples": truth,
            "height_m": config["height_m"], "radius_m": config["radius_m"],
            "config_sha256": sha(args.config), "render_policy": policy})
        print("DUAL_CAMERA_RENDER_COMPLETE", flush=True)
    finally:
        assert fingerprint == (sha(source), source.stat().st_size, source.stat().st_mtime_ns)


if __name__ == "__main__":
    main()
