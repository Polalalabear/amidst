"""Blender-only independent engineering producer. Never loads an existing asset.

Run Blender --background --factory-startup --disable-autoexec --python THIS --
--config ABS --output NEW_ABS [--pilot]. Producer config/source remain private;
only safe/rgb.json + PNGs + static.json are inference-eligible.
"""

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def write(path, doc):
    path.write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def material(name, color, roughness=0.7):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def cube(name, loc, scale, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.scale = scale
    ob.data.materials.append(mat)
    bevel = ob.modifiers.new("edges", "BEVEL")
    bevel.width = 0.025
    bevel.segments = 2
    ob.modifiers.new("normals", "WEIGHTED_NORMAL")
    return ob


def sphere(name, loc, scale, mat, parent):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, location=(0, 0, 0))
    ob = bpy.context.object
    ob.name = name
    ob.parent = parent
    ob.location = loc
    ob.scale = scale
    ob.data.materials.append(mat)
    for face in ob.data.polygons:
        face.use_smooth = True
    return ob


def pivot(name, loc, parent):
    ob = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    return ob


def tube(name, loc, rings, mat, parent):
    """Connected cloth/limb surface rather than disconnected toy-like ellipsoids."""
    vertices = []
    for z, rx, ry in rings:
        vertices.extend(
            (rx * math.cos(i * math.tau / 24), ry * math.sin(i * math.tau / 24), z)
            for i in range(24)
        )
    faces = [tuple(range(23, -1, -1))]
    for ring in range(len(rings) - 1):
        faces.extend(
            (
                ring * 24 + i,
                ring * 24 + (i + 1) % 24,
                (ring + 1) * 24 + (i + 1) % 24,
                (ring + 1) * 24 + i,
            )
            for i in range(24)
        )
    faces.append(tuple(range((len(rings) - 1) * 24, len(rings) * 24)))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(mat)
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent, ob.location = parent, loc
    for face in mesh.polygons:
        face.use_smooth = True
    return ob


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--pilot", action="store_true")
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    producer_pin, config_pin = sha(Path(__file__)), sha(args.config)
    config = json.loads(args.config.read_bytes())
    out = args.output
    assert config["schema_version"] == "q-demo.dynamic-producer.v1"
    assert config["formal_dataset"] is False and not out.exists()
    assert out.is_absolute() and out.resolve() == out and out.parent.is_dir()
    assert shutil.disk_usage(out.parent).free >= 8 * 1024**3
    out.mkdir(mode=0o700)
    private, safe = out / "private_producer", out / "safe"
    private.mkdir(mode=0o700)
    safe.mkdir()
    (safe / "media").mkdir()
    (private / "df-before.txt").write_text(
        subprocess.check_output(["df", "-k", str(out)], text=True)
    )
    # Construct everything from scratch. No .blend, media or dataset is opened.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = config["image_size_px"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.fps = config["fps"]
    scene.frame_start = 1
    count = config["duration_s"] * config["fps"]
    scene.frame_end = count
    scene.render.film_transparent = False
    scene.world.color = (0.5, 0.5, 0.5)
    scene.view_settings.view_transform = "Standard"
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = config["render_samples"]
    floor = material("floor", (0.36, 0.39, 0.42))
    wall = material("wall", (0.72, 0.76, 0.78))
    wood = material("doors", (0.26, 0.16, 0.09))
    metal = material("trim", (0.10, 0.14, 0.16))
    cube("floor", (9, 0, -0.08), (22, 9, 0.16), floor)
    cube("back_wall", (9, 2.5, 1.6), (22, 0.15, 3.2), wall)
    for x in [1, 5, 9, 13, 17]:
        cube("door", (x, 2.39, 1.05), (0.95, 0.08, 2.1), wood)
        cube("handle", (x + 0.32, 2.3, 1.0), (0.06, 0.07, 0.12), metal)
    for x in [2, 9, 16]:
        bpy.ops.object.light_add(type="AREA", location=(x, -1, 5))
        light = bpy.context.object
        light.data.energy = 600
        light.data.shape = "DISK"
        light.data.size = 6
    cameras = {}
    for name, row in config["cameras"].items():
        bpy.ops.object.camera_add(location=row["position"])
        camera = bpy.context.object
        camera.name = "camera_" + name
        camera.rotation_euler = (
            (Vector(row["look_at"]) - camera.location).to_track_quat("-Z", "Y").to_euler()
        )
        camera.data.lens = row["lens_mm"]
        camera.data.sensor_width = 36
        cameras[name] = camera
    # Authored articulated humanoid: local forward +X; both cameras see side/front.
    skin = material("skin", (0.64, 0.39, 0.24))
    red = material("shirt", (0.66, 0.025, 0.018))
    dark = material("trousers", (0.035, 0.055, 0.075))
    hair = material("hair", (0.035, 0.025, 0.018))
    shoe = material("shoes", (0.018, 0.018, 0.021))
    actor = pivot("private_actor", (0, 0, 0), None)
    tube(
        "shirt",
        (0, 0, 0),
        [
            (0.95, 0.14, 0.19),
            (1.06, 0.15, 0.20),
            (1.30, 0.17, 0.25),
            (1.45, 0.14, 0.26),
            (1.52, 0.085, 0.11),
        ],
        red,
        actor,
    )
    sphere("pelvis", (0, 0, 0.92), (0.17, 0.24, 0.17), dark, actor)
    sphere("neck", (0, 0, 1.56), (0.075, 0.075, 0.09), skin, actor)
    sphere("head", (0, 0, 1.72), (0.105, 0.095, 0.14), skin, actor)
    sphere("hair", (-0.018, 0, 1.81), (0.10, 0.097, 0.065), hair, actor)
    sphere("nose", (0.103, 0, 1.72), (0.027, 0.022, 0.025), skin, actor)
    white = material("eyes", (0.80, 0.80, 0.76))
    for side in [-1, 1]:
        sphere("eye", (0.095, side * 0.045, 1.755), (0.012, 0.017, 0.009), white, actor)
        sphere("pupil", (0.107, side * 0.045, 1.755), (0.005, 0.006, 0.006), hair, actor)
        sphere("ear", (-0.015, side * 0.095, 1.725), (0.021, 0.015, 0.031), skin, actor)
    sphere("mouth", (0.10, 0, 1.672), (0.006, 0.028, 0.004), hair, actor)
    limbs = []
    for side in [-1, 1]:
        hip = pivot("hip", (0, side * 0.13, 0.89), actor)
        tube(
            "thigh",
            (0, 0, 0),
            [(0.04, 0.10, 0.11), (-0.20, 0.09, 0.095), (-0.41, 0.075, 0.075)],
            dark,
            hip,
        )
        knee = pivot("knee", (0, 0, -0.4), hip)
        tube(
            "shin",
            (0, 0, 0),
            [(0.02, 0.076, 0.075), (-0.18, 0.075, 0.07), (-0.38, 0.055, 0.06)],
            dark,
            knee,
        )
        sphere("shoe", (0.055, 0, -0.38), (0.12, 0.065, 0.055), shoe, knee)
        shoulder = pivot("shoulder", (0, side * 0.29, 1.43), actor)
        tube(
            "sleeve",
            (0, 0, 0),
            [(0.03, 0.09, 0.09), (-0.14, 0.082, 0.082), (-0.19, 0.075, 0.075)],
            red,
            shoulder,
        )
        tube("upper_arm", (0, 0, 0), [(-0.17, 0.065, 0.066), (-0.34, 0.057, 0.055)], skin, shoulder)
        elbow = pivot("elbow", (0, 0, -0.35), shoulder)
        tube(
            "forearm",
            (0, 0, 0),
            [(0.015, 0.057, 0.055), (-0.17, 0.05, 0.048), (-0.29, 0.033, 0.035)],
            skin,
            elbow,
        )
        sphere("hand", (0, 0, -0.32), (0.065, 0.055, 0.085), skin, elbow)
        limbs.append((side, hip, knee, shoulder, elbow))
    motion = config["private_motion"]
    for frame in range(count):
        t = frame / config["fps"]
        phase = 2 * math.pi * motion["gait_hz"] * t
        actor.location = (
            motion["start_x"] + (motion["end_x"] - motion["start_x"]) * frame / (count - 1),
            motion["y"],
            0.035 + 0.025 * math.cos(phase * 2),
        )
        actor.keyframe_insert("location", frame=frame + 1)
        for side, hip, knee, shoulder, elbow in limbs:
            wave = math.sin(phase + (0 if side == 1 else math.pi))
            for ob, angle in [
                (hip, 0.48 * wave),
                (knee, -0.65 * max(0, -wave)),
                (shoulder, -0.42 * wave),
                (elbow, -0.3 - 0.15 * wave),
            ]:
                ob.rotation_euler.y = angle
                ob.keyframe_insert("rotation_euler", frame=frame + 1)
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(private / "source.blend"), check_existing=True)
    write(private / "producer-config.json", config)
    static = dict(
        schema_version="q-demo.dynamic-static.v1",
        scene_id=config["scene_id"],
        revision="rSYN",
        engineering_only=True,
        cameras={
            name: dict(
                position=list(cam.location),
                matrix_world=[list(r) for r in cam.matrix_world],
                lens_mm=cam.data.lens,
                sensor_width_mm=cam.data.sensor_width,
            )
            for name, cam in cameras.items()
        },
        image_size_px=config["image_size_px"],
        source_blend_file_sha256=sha(private / "source.blend"),
        gt_read=False,
    )
    write(safe / "static.json", static)
    frames = [0, 20, 40, 60, 80, 100, 120, 140, 159] if args.pilot else range(count)
    records = []
    for name, camera in cameras.items():
        scene.camera = camera
        for frame in frames:
            assert shutil.disk_usage(out).free >= 8 * 1024**3
            scene.frame_set(frame + 1)
            target = safe / "media" / (name + "-" + str(frame).zfill(4) + ".png")
            scene.render.filepath = str(target)
            bpy.ops.render.render(write_still=True)
            records.append(
                dict(
                    camera_id=name,
                    frame_index=frame,
                    timestamp_s=frame / config["fps"],
                    rgb_ref=str(target.relative_to(safe)),
                    file_sha256=sha(target),
                )
            )
    write(
        safe / ("pilot.json" if args.pilot else "rgb.json"),
        dict(
            schema_version="q-demo.dynamic-rgb-run.v1",
            source_kind="SYNTHETIC",
            scene_id=config["scene_id"],
            run_id=config["run_id"],
            clock_id=config["clock_id"],
            sampling=dict(
                fps=config["fps"],
                duration_s=config["duration_s"],
                sample_count_per_camera=count,
                image_size_px=config["image_size_px"],
            ),
            motion_kind="ARTICULATED_RENDERED_MOTION",
            static_ref="static.json",
            static_file_sha256=sha(safe / "static.json"),
            records=records,
            identity_verdict="UNCONFIRMED",
            gt_read=False,
        ),
    )
    write(
        private / "RECEIPT.json",
        dict(
            producer_script_sha256=producer_pin,
            config_file_sha256=config_pin,
            blender_version=bpy.app.version_string,
            source_sha256=sha(private / "source.blend"),
            frames_rendered=len(records),
            pilot=args.pilot,
            original_assets_opened=False,
        ),
    )
    assert sha(Path(__file__)) == producer_pin and sha(args.config) == config_pin
    (private / "df-after.txt").write_text(
        subprocess.check_output(["df", "-k", str(out)], text=True)
    )


if __name__ == "__main__":
    main()
