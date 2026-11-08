"""D124 Blender producer: frozen route, tangent yaw, minimal front/back features.

Only this producer reads the frozen authored plan. Never import this module from
inference or pass its config, pose journal, or original plan to the safe bundle.
Blender opens the explicitly pinned source; this script never saves a blend.

Blender --background --disable-autoexec SOURCE.blend --python THIS --
  --repo REPO --catalog CATALOG --config CONFIG --output NEW_ROOT
  --scenario A4-1 --authorization-ref D124_URL
  [--camera CAM_ID ...] [--frame-indices 0,40-55] [--max-new-frames 4] [--resume]

Only PNGs are written below safe/media. Everything else is in gt_private.
No real rendering occurs when importing the pure helpers for focused tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import time
import zlib

AUTHORIZATION = "https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620431061"
MINIMUM_BYTES = 8 * 1024**3
FULL_START_BYTES = 19 * 1024**3 // 2
AXIS_YAW = {"+X": 0.0, "+Y": math.pi / 2, "-X": math.pi, "-Y": -math.pi / 2}


class ProducerError(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise ProducerError(code)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_space(path, reserve_bytes=0, *, disk_usage=shutil.disk_usage):
    """Check before every write; never write a low-space progress record."""
    path = Path(path)
    while not path.exists():
        require(path != path.parent, "OUTPUT_FILESYSTEM_MISSING")
        path = path.parent
    free = disk_usage(path).free
    require(free >= MINIMUM_BYTES + reserve_bytes, "STOP_BELOW_8_GIB_OR_FRAME_RESERVE")
    return free


def exact_resume_lock(expected, actual):
    require(expected == actual, "RESUME_LOCK_MISMATCH")


def require_start_space(path, limited, reserve_bytes, *, disk_usage=shutil.disk_usage):
    """A full invocation needs 9.5 GiB; bounded previews retain the 8 GiB floor."""
    extra = reserve_bytes if limited else FULL_START_BYTES - MINIMUM_BYTES
    return require_space(path, extra, disk_usage=disk_usage)


def no_symlink_components(path):
    path = Path(path).absolute()
    for component in (path, *path.parents):
        require(not component.is_symlink(), "OUTPUT_SYMLINK")


def validate_output_resume(root, expected, resume):
    """Reject another/old run before creating or changing anything in its tree."""
    root = Path(root)
    no_symlink_components(root / "gt_private")
    no_symlink_components(root / "safe" / "media")
    if root.exists():
        require(resume, "EXISTING_OUTPUT_REQUIRES_RESUME")
        lock_path = root / "gt_private" / "LOCK.json"
        require(lock_path.is_file() and not lock_path.is_symlink(), "RESUME_LOCK_MISSING")
        exact_resume_lock(expected, json.loads(lock_path.read_bytes()))
    else:
        require(not resume, "RESUME_LOCK_MISSING")


def validate_waypoints(waypoints):
    require(isinstance(waypoints, list) and len(waypoints) >= 2, "ROUTE_POINTS_MISSING")
    previous = -1
    for point in waypoints:
        t = point["planned_source_time_us"]
        xyz = point["foot_anchor_world_m"]
        require(type(t) is int and t > previous, "ROUTE_TIME_NOT_STRICT")
        require(len(xyz) == 3 and all(type(v) in (int, float) and math.isfinite(v) for v in xyz),
                "ROUTE_COORDINATES_INVALID")
        previous = t


def route_pose(waypoints, source_time_us, front_axis="+X", initial_yaw=0.0, epsilon=1e-9):
    """Same piecewise-linear position; half-open segment tangent, stops hold yaw."""
    validate_waypoints(waypoints)
    require(front_axis in AXIS_YAW, "FRONT_AXIS_UNRESOLVED")
    require(waypoints[0]["planned_source_time_us"] <= source_time_us
            <= waypoints[-1]["planned_source_time_us"], "NO_ROUTE_EXTRAPOLATION")
    yaw = initial_yaw
    position = None
    for index, (a, b) in enumerate(zip(waypoints, waypoints[1:])):
        ta, tb = a["planned_source_time_us"], b["planned_source_time_us"]
        if source_time_us < ta:
            break
        dx = b["foot_anchor_world_m"][0] - a["foot_anchor_world_m"][0]
        dy = b["foot_anchor_world_m"][1] - a["foot_anchor_world_m"][1]
        if math.hypot(dx, dy) > epsilon:
            yaw = math.atan2(dy, dx) - AXIS_YAW[front_axis]
        if source_time_us < tb or index == len(waypoints) - 2:
            fraction = (source_time_us - ta) / (tb - ta)
            position = [a["foot_anchor_world_m"][i] + fraction *
                        (b["foot_anchor_world_m"][i] - a["foot_anchor_world_m"][i])
                        for i in range(3)]
            break
    require(position is not None, "ROUTE_INTERVAL_MISSING")
    return position, yaw


def parse_frame_indices(specification, count):
    if specification is None:
        return list(range(count))
    selected = set()
    try:
        for token in specification.split(","):
            ends = token.strip().split("-")
            require(1 <= len(ends) <= 2 and all(x.isdigit() for x in ends), "FRAME_SELECTOR_INVALID")
            first, last = int(ends[0]), int(ends[-1])
            require(0 <= first <= last < count, "FRAME_SELECTOR_OUTSIDE_SOURCE_GRID")
            selected.update(range(first, last + 1))
    except (AttributeError, ValueError) as error:
        raise ProducerError("FRAME_SELECTOR_INVALID") from error
    require(selected, "FRAME_SELECTOR_EMPTY")
    return sorted(selected)


def png_safe(raw, expected_size=(960, 540)):
    """Strip text/EXIF, validate RGB8 PNG/CRC/zlib, preserve IDAT bytes exactly."""
    require(raw[:8] == b"\x89PNG\r\n\x1a\n", "PNG_REQUIRED")
    safe = bytearray(raw[:8])
    cursor, kinds, idat, safe_idat = 8, [], bytearray(), bytearray()
    allowed = {b"IHDR", b"IDAT", b"IEND", b"cHRM", b"gAMA", b"oFFs", b"pHYs", b"sRGB"}
    removed = {b"tEXt", b"zTXt", b"iTXt", b"eXIf"}
    while cursor < len(raw):
        require(cursor + 12 <= len(raw), "PNG_TRUNCATED")
        length = struct.unpack_from(">I", raw, cursor)[0]
        kind = raw[cursor + 4:cursor + 8]
        end = cursor + length + 12
        require(end <= len(raw) and kind in allowed | removed, "PNG_CHUNK_REJECTED")
        data = raw[cursor + 8:cursor + 8 + length]
        require(zlib.crc32(kind + data) & 0xffffffff == struct.unpack_from(">I", raw, end - 4)[0], "PNG_CRC")
        if kind == b"IHDR":
            require(not kinds and length == 13, "PNG_IHDR")
            width, height, bits, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", data)
            require((width, height) == tuple(expected_size)
                    and (bits, color, compression, filtering, interlace) == (8, 2, 0, 0, 0), "PNG_FORMAT")
        elif kind == b"IDAT":
            require(kinds and (b"IDAT" not in kinds or kinds[-1] in {b"IDAT"} | removed), "PNG_IDAT_ORDER")
            idat.extend(data)
        elif kind == b"IEND":
            require(length == 0 and idat and end == len(raw), "PNG_IEND")
        if kind not in removed:
            safe.extend(raw[cursor:end])
            if kind == b"IDAT":
                safe_idat.extend(data)
        kinds.append(kind)
        cursor = end
    require(kinds and kinds[0] == b"IHDR" and kinds[-1] == b"IEND" and idat == safe_idat, "PNG_PIXEL_BINDING")
    stride, expected = expected_size[0] * 3 + 1, (expected_size[0] * 3 + 1) * expected_size[1]
    try:
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(bytes(idat), expected + 1)
    except zlib.error as error:
        raise ProducerError("PNG_ZLIB") from error
    require(len(pixels) == expected and decoder.eof and not decoder.unused_data
            and not decoder.unconsumed_tail and all(pixels[i] <= 4 for i in range(0, expected, stride)), "PNG_PIXELS")
    return bytes(safe), hashlib.sha256(idat).hexdigest()


def read_pinned(path, pin):
    require(path.is_file() and not path.is_symlink() and sha(path) == pin, "INPUT_PIN_MISMATCH:" + path.name)
    return path.read_bytes()


def private_write(path, raw, *, exclusive=False):
    no_symlink_components(path)
    require_space(path.parent, len(raw) + 16384)
    with path.open("xb" if exclusive else "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def snapshot(path, raw):
    if path.exists():
        require(path.is_file() and not path.is_symlink() and path.read_bytes() == raw, "PRIVATE_SNAPSHOT_CHANGED")
    else:
        private_write(path, raw, exclusive=True)


def make_appearance(bpy, target, appearance, front_axis):
    from mathutils import Vector

    require(appearance["preserve_source_materials"] is True, "SOURCE_MATERIALS_MUST_STAY")
    for key in ("head", "torso"):
        obj = bpy.data.objects.get(appearance[key + "_object"])
        require(obj is not None and obj.type == "MESH", "SOURCE_BODY_MESH_MISSING")
        points = [target.matrix_world.inverted() @ obj.matrix_world @ Vector(p) for p in obj.bound_box]
        center = [(min(p[i] for p in points) + max(p[i] for p in points)) / 2 for i in range(3)]
        dimensions = [max(p[i] for p in points) - min(p[i] for p in points) for i in range(3)]
        tolerance = appearance["bounds_tolerance_m"]
        require(all(abs(a - b) <= tolerance for a, b in zip(center, appearance[key + "_center_local_m"]))
                and all(abs(a - b) <= tolerance for a, b in zip(dimensions, appearance[key + "_dimensions_m"])),
                "SOURCE_BODY_BOUNDS_CHANGED")
    alpha = AXIS_YAW[front_axis]

    def local(f, lateral, z):
        return (f * math.cos(alpha) - lateral * math.sin(alpha),
                f * math.sin(alpha) + lateral * math.cos(alpha), z)

    materials = {}
    for name in ("face", "eye", "dark", "badge", "backpack"):
        mat = bpy.data.materials.new("D124_" + name)
        color = appearance[name + "_color_rgb"]
        mat.diffuse_color = (*color, 1)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (*color, 1)
        bsdf.inputs["Roughness"].default_value = 0.75
        materials[name] = mat

    def feature(name, position, size, material, sphere=False):
        require(bpy.data.objects.get("D124_" + name) is None, "FEATURE_ALREADY_PRESENT")
        if sphere:
            bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=(0, 0, 0))
        else:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
        obj = bpy.context.object
        obj.name = "D124_" + name
        obj.parent = target
        obj.location = local(*position)
        obj.rotation_euler[2] = alpha
        obj.scale = tuple(v / 2 if sphere else v for v in size)
        obj.data.materials.append(materials[material])
        if sphere:
            for face in obj.data.polygons:
                face.use_smooth = True
        return obj

    for side in (-1, 1):
        feature("eye_" + str(side), (0.103, side * 0.043, 1.632), (0.018, 0.034, 0.021), "eye", True)
        feature("pupil_" + str(side), (0.113, side * 0.043, 1.632), (0.008, 0.015, 0.015), "dark", True)
    feature("nose", (0.117, 0, 1.604), (0.040, 0.030, 0.030), "face", True)
    feature("front_badge", (0.136, 0, 1.302), (0.010, 0.110, 0.085), "badge")
    feature("front_badge_mark", (0.143, 0, 1.302), (0.006, 0.020, 0.055), "dark")
    feature("backpack", (-0.165, 0, 1.210), (0.085, 0.230, 0.290), "backpack")
    feature("backpack_stripe", (-0.210, 0, 1.255), (0.008, 0.150, 0.018), "badge")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenario", choices=("A4-1", "B4-1"), required=True)
    parser.add_argument("--authorization-ref", required=True)
    parser.add_argument("--camera", action="append")
    parser.add_argument("--frame-indices")
    parser.add_argument("--max-new-frames", type=int)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv if argv is not None else sys.argv[sys.argv.index("--") + 1:])
    require(args.authorization_ref == AUTHORIZATION, "EXPLICIT_D124_AUTHORIZATION_REQUIRED")
    require(args.max_new_frames is None or args.max_new_frames > 0, "FRAME_LIMIT_INVALID")
    from mathutils import Vector
    import bpy

    no_symlink_components(args.output)
    repo, output = args.repo.resolve(), args.output.resolve()
    config_raw = args.config.read_bytes()
    config = json.loads(config_raw)
    require(config["authorization_ref"] == AUTHORIZATION
            and config["status"] == "AUTHORIZED_RENDER_ONLY", "CONFIG_AUTHORIZATION_MISMATCH")
    settings, orientation = config["render"], config["orientation"]
    require(settings["minimum_available_bytes"] == MINIMUM_BYTES, "DISK_FLOOR_CHANGED")
    require(settings["full_render_start_available_bytes"] == FULL_START_BYTES
            and settings["frame_reserve_bytes"] == 32 * 1024**2, "START_OR_RESERVE_CHANGED")
    limited = args.frame_indices is not None or args.max_new_frames is not None
    require_start_space(output, limited, settings["frame_reserve_bytes"])
    require(settings["fps"] == 5 and settings["sample_interval_us"] == 200000
            and settings["image_size_px"] == [960, 540] and settings["samples"] == 16, "RENDER_PROFILE_CHANGED")
    require(orientation["front_axis"] in AXIS_YAW and orientation["turn_smoothing"] == "NONE", "ORIENTATION_UNSELECTED")
    source = Path(bpy.data.filepath).resolve()
    require(source.is_file() and sha(source) == config["source_sha256"], "SOURCE_PIN_MISMATCH")
    freeze_path = repo / config["freeze"]["path"]
    freeze_raw = read_pinned(freeze_path, config["freeze"]["sha256"])
    frozen = json.loads(freeze_raw)
    frozen_run = next(row for row in frozen["runs"] if row["scenario"] == args.scenario)
    run = config["runs"][args.scenario]
    require(frozen_run["fps"] == 5 and frozen_run["sample_interval_us"] == 200000
            and frozen_run["source_duration_us"] == run["source_duration_us"]
            and run["sample_count_per_camera"] * 200000 == run["source_duration_us"], "FROZEN_GRID_CHANGED")
    pinned = {name: read_pinned(repo / frozen_run[name]["path"], frozen_run[name]["sha256"])
              for name in ("producer_script", "adapter_plan", "clock", "run_declaration")}
    producer, clock, declaration = (json.loads(pinned[name]) for name in ("producer_script", "clock", "run_declaration"))
    require(run["new_run_id"] != declaration["run_id"] and run["new_clock_id"] != clock["clock_id"], "NEW_RUN_AND_CLOCK_REQUIRED")
    catalog_raw = read_pinned(args.catalog.resolve(), config["catalog_sha256"])
    cameras = {row["camera_id"]: row for row in json.loads(catalog_raw)["cameras"]}
    camera_ids = producer["render_camera_ids"]
    require(len(camera_ids) == len(set(camera_ids)) and set(camera_ids) <= set(cameras), "CAMERA_SCOPE_INVALID")
    selected_cameras = args.camera or camera_ids
    require(set(selected_cameras) <= set(camera_ids) and len(selected_cameras) == len(set(selected_cameras)), "CAMERA_NOT_IN_FROZEN_SCOPE")
    indices = parse_frame_indices(args.frame_indices, run["sample_count_per_camera"])
    route = producer["planning_waypoints"]
    validate_waypoints(route)

    scene = bpy.context.scene
    scene.frame_set(1)
    actors = [obj for obj in bpy.data.objects if obj.name.startswith("PRODUCTION_")]
    target = bpy.data.objects.get("PRODUCTION_P1_ROOT")
    require(target is not None and target.parent is None and len(actors) == 34, "SOURCE_ACTORS_CHANGED")
    require(all(abs(v) < 1e-8 for v in target.rotation_euler[:2])
            and all(abs(v - 1) < 1e-8 for v in target.scale), "SOURCE_ROOT_TRANSFORM_CHANGED")
    initial_yaw = float(target.rotation_euler.z)
    for actor in actors:
        actor.animation_data_clear()
        actor.hide_render = not actor.name.startswith("PRODUCTION_P1_")
    bounds = [target.matrix_world.inverted() @ actor.matrix_world @ Vector(corner)
              for actor in actors if actor.type == "MESH" and actor.name.startswith("PRODUCTION_P1_")
              for corner in actor.bound_box]
    require(bounds and abs(min(p.z for p in bounds)) < 0.01, "SOURCE_FOOT_ANCHOR_UNKNOWN")
    for camera_id in camera_ids:
        camera = bpy.data.objects.get(camera_id)
        expected = cameras[camera_id]
        require(camera is not None and camera.type == "CAMERA", "CAMERA_MISSING")
        require(all(abs(camera.matrix_world[i][j] - expected["camera_to_world"][i][j]) < 1e-5
                    for i in range(4) for j in range(4)), "CAMERA_POSE_CHANGED")
        require(abs(960 * camera.data.lens / camera.data.sensor_width - expected["fx"]) < 1e-5, "CAMERA_INTRINSICS_CHANGED")
    make_appearance(bpy, target, config["appearance"], orientation["front_axis"])
    scene.render.resolution_x, scene.render.resolution_y = settings["image_size_px"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.use_stamp = False
    scene.render.fps = 5
    require(hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"), "RENDER_SAMPLES_SETTING_UNAVAILABLE")
    scene.eevee.taa_render_samples = settings["samples"]

    root = output / args.scenario
    private, safe = root / "gt_private", root / "safe" / "media"
    lock = {"authorization_ref": AUTHORIZATION, "producer_id": config["producer_id"],
            "driver_sha256": sha(Path(__file__)), "config_sha256": hashlib.sha256(config_raw).hexdigest(),
            "source_sha256": config["source_sha256"], "freeze_sha256": config["freeze"]["sha256"],
            "catalog_sha256": config["catalog_sha256"], "frozen_input_pins": {name: frozen_run[name]["sha256"] for name in pinned},
            "run_id": run["new_run_id"], "clock_id": run["new_clock_id"],
            "original_run_id": declaration["run_id"], "original_clock_id": clock["clock_id"],
            "source_duration_us": run["source_duration_us"], "camera_ids": camera_ids,
            "render": settings, "orientation": orientation, "appearance": config["appearance"],
            "source_initial_yaw_rad": initial_yaw, "engine": scene.render.engine,
            "source_file_saved_or_copied": False, "new_gait_authored": False}
    validate_output_resume(root, lock, args.resume)
    new_root = not root.exists()
    require_space(root)
    for directory in (root, private, safe):
        require_space(directory.parent)
        directory.mkdir(parents=True, exist_ok=not (directory == root and new_root),
                        mode=0o700 if directory == private else 0o755)
    import fcntl
    require_space(private)
    process_lock_path = private / ".render-process.lock"
    no_symlink_components(process_lock_path)
    process_lock = process_lock_path.open("a+b")
    try:
        fcntl.flock(process_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        process_lock.close()
        raise ProducerError("ANOTHER_RENDER_PROCESS_OWNS_OUTPUT") from error
    try:
        lock_path = private / "LOCK.json"
        if lock_path.exists():
            exact_resume_lock(lock, json.loads(lock_path.read_bytes()))
        else:
            private_write(lock_path, json_bytes(lock), exclusive=True)
        snapshot(private / "render_r004_d124.py", Path(__file__).read_bytes())
        snapshot(private / "producer_config.json", config_raw)
        snapshot(private / "frozen_producer_plan.json", pinned["producer_script"])
        snapshot(private / "original_clock.json", pinned["clock"])
        journal = private / "frame_journal.jsonl"
        require(not journal.is_symlink(), "JOURNAL_SYMLINK")
        records = [json.loads(line) for line in journal.read_text().splitlines()] if journal.exists() else []
        done = {(row["camera_id"], row["frame_index"]): row for row in records}
        require(len(done) == len(records), "DUPLICATE_JOURNAL_ENTRY")
        for (camera_id, index), row in done.items():
            require(camera_id in camera_ids and type(index) is int and 0 <= index < run["sample_count_per_camera"]
                    and row["source_time_us"] == index * 200000, "RESUME_GRID_CHANGED")
            frame_path = safe / camera_id / f"{index:06d}.png"
            require(frame_path.is_file() and not frame_path.is_symlink() and sha(frame_path) == row["safe_sha256"], "RESUME_FRAME_CHANGED")
            sanitized, pixel_sha = png_safe(frame_path.read_bytes())
            require(sanitized == frame_path.read_bytes() and pixel_sha == row["pixel_chunks_sha256"], "RESUME_PIXEL_CHANGED")
        for path in safe.rglob("*"):
            require(not path.is_symlink(), "SAFE_OUTPUT_SYMLINK")
            if path.is_file():
                require(path.suffix == ".png" and path.stem.isdigit()
                        and (path.parent.name, int(path.stem)) in done, "UNJOURNALED_OUTPUT_EXISTS")
        new_count, expected_frames = 0, run["sample_count_per_camera"] * len(camera_ids)
        def progress(status):
            private_write(private / "progress.json", json_bytes({"scenario": args.scenario,
                          "run_id": run["new_run_id"], "completed_frames": len(done), "expected_frames": expected_frames,
                          "status": status, "available_bytes": require_space(private), "new_frames_this_invocation": new_count}))
        progress("RENDERING")
        temporary = private / "render_temp"
        no_symlink_components(temporary)
        require_space(temporary.parent)
        temporary.mkdir(exist_ok=True, mode=0o700)
        for camera_id in selected_cameras:
            scene.camera = bpy.data.objects[camera_id]
            safe_dir = safe / camera_id
            require_space(safe_dir.parent)
            safe_dir.mkdir(exist_ok=True)
            for index in indices:
                if (camera_id, index) in done:
                    continue
                safe_path = safe_dir / f"{index:06d}.png"
                require(not safe_path.exists(), "UNJOURNALED_OUTPUT_EXISTS")
                require_space(private, settings["frame_reserve_bytes"])
                descriptor, raw_name = tempfile.mkstemp(prefix="d124-owned-", suffix=".png", dir=temporary)
                os.close(descriptor)
                raw_path = Path(raw_name)
                try:
                    position, yaw = route_pose(route, index * 200000, orientation["front_axis"], initial_yaw,
                                               orientation["zero_speed_epsilon_m"])
                    target.location = position
                    target.rotation_euler.z = yaw
                    bpy.context.view_layer.update()
                    scene.render.filepath = str(raw_path)
                    require_space(private, settings["frame_reserve_bytes"])
                    started = time.monotonic()
                    bpy.ops.render.render(write_still=True)
                    require(raw_path.stat().st_size <= settings["maximum_png_bytes"], "RENDER_PNG_TOO_LARGE")
                    raw = raw_path.read_bytes()
                    sanitized, pixel_sha = png_safe(raw)
                    private_write(safe_path, sanitized, exclusive=True)
                    row = {"camera_id": camera_id, "frame_index": index, "source_time_us": index * 200000,
                           "foot_position_world_m": position, "root_yaw_rad": yaw,
                           "raw_sha256": hashlib.sha256(raw).hexdigest(), "safe_sha256": hashlib.sha256(sanitized).hexdigest(),
                           "pixel_chunks_sha256": pixel_sha, "raw_bytes": len(raw), "safe_bytes": len(sanitized),
                           "raw_retained": False, "elapsed_s": time.monotonic() - started}
                    record = (json.dumps(row, sort_keys=True) + "\n").encode()
                    require_space(private, len(record) + 16384)
                    with journal.open("ab") as stream:
                        stream.write(record)
                        stream.flush()
                        os.fsync(stream.fileno())
                    done[(camera_id, index)] = row
                    new_count += 1
                    print("D124_FRAME_DONE", args.scenario, camera_id, index, len(done), expected_frames, flush=True)
                finally:
                    # Only the unique temporary file created by this invocation.
                    raw_path.unlink(missing_ok=True)
                if args.max_new_frames is not None and new_count >= args.max_new_frames:
                    progress("PAUSED_FRAME_LIMIT")
                    require(sha(source) == config["source_sha256"]
                            and sha(freeze_path) == config["freeze"]["sha256"], "SOURCE_OR_FREEZE_CHANGED")
                    return 0
            require(sha(source) == config["source_sha256"], "SOURCE_CHANGED_AFTER_CAMERA")
        complete = len(done) == expected_frames
        progress("RENDER_COMPLETE" if complete else "PAUSED_SELECTED_PREVIEW_COMPLETE")
        private_write(private / "completion.json", json_bytes({"scenario": args.scenario,
                      "run_id": run["new_run_id"], "clock_id": run["new_clock_id"], "render_complete": complete,
                      "completed_frames": len(done), "expected_frames": expected_frames,
                      "source_sha256_after": sha(source), "freeze_sha256_after": sha(freeze_path),
                      "safe_bundle_validation": "NOT_RUN", "source_file_saved_or_copied": False}))
        require(sha(source) == config["source_sha256"] and sha(freeze_path) == config["freeze"]["sha256"], "SOURCE_OR_FREEZE_CHANGED")
        return 0
    finally:
        process_lock.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProducerError as error:
        print("D124_STOP", str(error), flush=True)
        raise SystemExit(2) from error
