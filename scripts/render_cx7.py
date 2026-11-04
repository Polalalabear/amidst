"""New #415 CX-7 producer, written from the repo freeze/receipt and safe cameras.

Replaces the unavailable LOCAL legacy producer; this is not a copy of it.
Python THIS --help or --check-only needs no Blender. Actual rendering requires
--execute, a new run ID, explicit authorization and static model front-axis input.
No previous run, private journal, keyframe file or measured track is read.
Authoring records stay outside safe/. Only sanitized RGB and source-grid metadata
are written under safe/. No source blend is saved or copied.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import struct
import zlib
from r004_local_common import (argv_after_separator, authorize, checked_path,
    digest, disk, execution_options, file_sha, new_output, parser, pinned, read_bytes,
    require, write_bytes, write_json)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = 'docs/engineering/R004_A4B4_SCRIPT_FREEZE_20261029.json'
FREEZE_SHA256 = 'ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb'
AXES = {'+X': 0., '+Y': math.pi / 2, '-X': math.pi, '-Y': -math.pi / 2}


def relative_file(root, name):
    require(isinstance(name, str) and name and '\\' not in name, 'UNSAFE_RELATIVE_FILE')
    relative = Path(name)
    require(not relative.is_absolute() and '..' not in relative.parts, 'UNSAFE_RELATIVE_FILE')
    return checked_path(root / relative)


def load_inputs(repo, scenario, catalog):
    repo = checked_path(repo)
    freeze = json.loads(pinned(repo / FREEZE, FREEZE_SHA256))
    matches = [r for r in freeze['runs'] if r['scenario'] == scenario]
    require(len(matches) == 1, 'SCENARIO_UNKNOWN')
    scope = matches[0]
    ref = scope['producer_script']
    plan = json.loads(pinned(relative_file(repo, ref['path']), ref['sha256']))
    cameras = json.loads(pinned(catalog, freeze['source_pins']['catalog_sha256']))
    catalog_by_id = {c['camera_id']: c for c in cameras['cameras']}
    require(plan['scenario'] == scenario and set(plan['render_camera_ids']) <= catalog_by_id.keys(),
            'SCENARIO_CAMERA_MISMATCH')
    require(scope['fps'] == 5 and scope['sample_interval_us'] == 200_000, 'SOURCE_GRID_MISMATCH')
    points = plan['planning_waypoints']
    validate_points(points, scope['source_duration_us'])
    clock_ref = scope['clock']
    clock = json.loads(pinned(relative_file(repo, clock_ref['path']), clock_ref['sha256']))
    return freeze, scope, plan, catalog_by_id, clock


def validate_points(points, duration):
    require(isinstance(points, list) and len(points) >= 2, 'CONTROL_POINTS_MISSING')
    previous = -1
    for point in points:
        t, xyz = point['planned_source_time_us'], point['foot_anchor_world_m']
        require(type(t) is int and previous < t <= duration, 'CONTROL_TIME_INVALID')
        require(isinstance(xyz, list) and len(xyz) == 3
                and all(type(v) in (int, float) and math.isfinite(v) for v in xyz), 'CONTROL_POINT_INVALID')
        previous = t
    require(points[0]['planned_source_time_us'] == 0 and previous == duration, 'CONTROL_SPAN_INVALID')


def sample_pose(points, time_us, front_axis):
    """Authored interpolation, half-open tangents, stationary intervals hold yaw."""
    require(front_axis in AXES, 'STATIC_FRONT_AXIS_REQUIRED')
    require(type(time_us) is int and 0 <= time_us < points[-1]['planned_source_time_us'], 'NO_EXTRAPOLATION')
    heading = None
    for a, b in zip(points, points[1:]):
        ta, tb = a['planned_source_time_us'], b['planned_source_time_us']
        delta = [y - x for x, y in zip(a['foot_anchor_world_m'], b['foot_anchor_world_m'])]
        if math.hypot(*delta[:2]) > 1e-9:
            heading = math.atan2(delta[1], delta[0]) - AXES[front_axis]
        if time_us < tb:
            require(heading is not None, 'INITIAL_HEADING_UNKNOWN')
            fraction = (time_us - ta) / (tb - ta)
            return [x + fraction * d for x, d in zip(a['foot_anchor_world_m'], delta)], heading
    raise ValueError('CONTROL_INTERVAL_MISSING')


def sanitize_png(raw):
    require(raw[:8] == b'\x89PNG\r\n\x1a\n', 'PNG_INVALID')
    kept = bytearray(raw[:8])
    offset = 8
    while offset < len(raw):
        require(offset + 12 <= len(raw), 'PNG_INVALID')
        length = struct.unpack('>I', raw[offset:offset + 4])[0]
        end = offset + length + 12
        require(end <= len(raw), 'PNG_INVALID')
        kind = raw[offset + 4:offset + 8]
        data = raw[offset + 8:end - 4]
        require(zlib.crc32(kind + data) == struct.unpack('>I', raw[end - 4:end])[0], 'PNG_CRC_INVALID')
        if kind not in {b'tEXt', b'zTXt', b'iTXt', b'eXIf'}:
            kept.extend(raw[offset:end])
        offset = end
    from check_event_run_bundle import inspect_png
    inspect_png(bytes(kept))
    return bytes(kept)


def parse_args(argv=None):
    p = parser(__doc__)
    p.add_argument('--repo', type=Path, default=ROOT)
    p.add_argument('--catalog', type=Path, default=ROOT / 'configs/q1q5/authoring/r004_v2_static_cameras.json')
    p.add_argument('--scenario', choices=['A4-1', 'B4-1'], required=True)
    p.add_argument('--source', type=Path, help='Pinned r004 v2 source; never written.')
    p.add_argument('--output', type=Path, help='New directory; resume/overwrite are unsupported.')
    p.add_argument('--run-id', help='New run ID; old declared run IDs are rejected.')
    p.add_argument('--clock', type=Path, help='Explicit new run clock declaration under repo configs/q1q5/clocks/.')
    p.add_argument('--clock-sha256', help='Byte pin of that new declaration; never fabricate clock provenance.')
    p.add_argument('--actor-prefix', help='Static source model prefix, selected from the source asset.')
    p.add_argument('--front-axis', choices=sorted(AXES), help='Static model front direction, explicitly checked by an owner.')
    p.add_argument('--front-axis-ref', help='Reference to that static model authoring decision.')
    p.add_argument('--check-only', action='store_true', help='Verify only allowed repo plans and safe camera pins; no bpy.')
    p.add_argument('--frame-limit', type=int, help='Optional bounded preview; never label it a full run.')
    execution_options(p)
    return p.parse_args(argv_after_separator(argv))


def main(argv=None):
    args = parse_args(argv)
    freeze, scope, plan, cameras, clock = load_inputs(args.repo, args.scenario, args.catalog)
    if args.check_only:
        print(json.dumps({'status': 'INPUT_PINS_VERIFIED', 'scenario': args.scenario,
                          'rendered': False, 'model_static_front': 'NOT_CHECKED'}))
        return
    authorize(args)
    require(args.source and args.output and args.actor_prefix and args.front_axis and args.front_axis_ref,
            'STATIC_MODEL_INPUT_REQUIRED')
    require(args.run_id and args.run_id != plan['declared_run_context']['run_id'], 'NEW_RUN_ID_REQUIRED')
    require(args.clock and args.clock_sha256, 'NEW_CLOCK_DECLARATION_REQUIRED')
    new_clock_path = checked_path(args.clock)
    require(new_clock_path.is_relative_to(checked_path(args.repo) / 'configs/q1q5/clocks'), 'CLOCK_MUST_BE_REPO_DECLARATION')
    new_clock_raw = pinned(new_clock_path, args.clock_sha256)
    new_clock = json.loads(new_clock_raw)
    require(new_clock.get('run_id') == args.run_id and new_clock.get('clock_id') != clock['clock_id'], 'NEW_CLOCK_SCOPE_MISMATCH')
    require(all(new_clock.get(k) == clock.get(k) for k in ('mapping_kind', 'timezone', 'wall_origin', 't0_us', 'rate', 'source_duration_us')), 'CLOCK_MAPPING_CHANGED')
    from check_event_run_bundle import ClockMapping
    ClockMapping.from_document(new_clock, expected_run_id=args.run_id)
    require(args.frame_limit is None or args.frame_limit > 0, 'FRAME_LIMIT_INVALID')
    source = checked_path(args.source)
    expected_source = freeze['source_pins']['source_sha256']
    require(file_sha(source) == expected_source, 'SOURCE_SHA256_MISMATCH')
    count = scope['source_duration_us'] // scope['sample_interval_us']
    selected_count = min(count, args.frame_limit) if args.frame_limit else count
    # A full run starts with 9.5 GiB; every frame retains 8 GiB plus a write reserve.
    disk(args.output, 32 * 1024**2 if args.frame_limit else 3 * 1024**3 // 2)
    import bpy
    from mathutils import Matrix, Vector
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    scene.frame_set(1)
    actor = [o for o in bpy.data.objects if o.name.startswith(args.actor_prefix)]
    require(actor and any(o.type == 'MESH' for o in actor), 'STATIC_MODEL_NOT_FOUND')
    actor_set = set(actor)
    roots = [o for o in actor if o.parent not in actor_set]
    bounds = [o.matrix_world @ Vector(corner) for o in actor if o.type == 'MESH' for corner in o.bound_box]
    anchor = Vector(((min(v.x for v in bounds) + max(v.x for v in bounds)) / 2,
                     (min(v.y for v in bounds) + max(v.y for v in bounds)) / 2, min(v.z for v in bounds)))
    for o in actor:
        o.animation_data_clear()
    for o in bpy.data.objects:
        if o.name.startswith('PRODUCTION_'):
            o.hide_render = o not in actor_set
    # Explicitly authored visual markers establish a visible front/back convention.
    # They do not claim anatomical, detector or identity correctness.
    axis = Vector((math.cos(AXES[args.front_axis]), math.sin(AXES[args.front_axis]), 0))
    lateral = Vector((-axis.y, axis.x, 0))
    height = max(v.z for v in bounds) - anchor.z
    width = max(max(v.x for v in bounds) - min(v.x for v in bounds),
                max(v.y for v in bounds) - min(v.y for v in bounds))
    for label, forward, z, color in [('FRONT_BADGE', .55, .70, (1., .8, .02, 1.)),
                                    ('BACKPACK', -.55, .62, (.06, .08, .12, 1.)),
                                    ('EYE_L', .38, .92, (.02, .02, .02, 1.)),
                                    ('EYE_R', .38, .92, (.02, .02, .02, 1.))]:
        side = (-.12 if label == 'EYE_L' else .12 if label == 'EYE_R' else 0.)
        bpy.ops.mesh.primitive_cube_add(size=1, location=anchor + axis * width * forward
                                        + lateral * width * side + Vector((0, 0, height * z)))
        o = bpy.context.object
        o.name = 'CX7_AUTHORED_' + label
        o.scale = (width * .10, width * .10, height * (.12 if label == 'BACKPACK' else .035))
        material = bpy.data.materials.new(o.name)
        material.diffuse_color = color
        o.data.materials.append(material)
        roots.append(o)
    original = {o: o.matrix_world.copy() for o in roots}
    out = new_output(args.output)
    scene.render.engine = 'BLENDER_EEVEE'
    if hasattr(scene, 'eevee'):
        scene.eevee.taa_render_samples = 16
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode, scene.render.image_settings.color_depth = 'RGB', '8'
    scene.render.film_transparent = False
    records = []
    for camera_id in plan['render_camera_ids']:
        calibration = cameras[camera_id]
        camera = bpy.data.objects.get(camera_id)
        require(camera is not None and camera.type == 'CAMERA', 'SOURCE_CAMERA_MISSING')
        camera.animation_data_clear()
        camera.matrix_world = Matrix(calibration['camera_to_world'])
        for attr, key in [('lens', 'focal_length_mm'), ('sensor_width', 'sensor_width_mm'),
                          ('sensor_height', 'sensor_height_mm'), ('clip_start', 'clip_start'),
                          ('clip_end', 'clip_end'), ('shift_x', 'shift_x'), ('shift_y', 'shift_y')]:
            setattr(camera.data, attr, calibration[key])
        camera.data.type, camera.data.sensor_fit = 'PERSP', 'HORIZONTAL'
        scene.camera = camera
        for index in range(selected_count):
            disk(out, 32 * 1024**2)
            time_us = index * scope['sample_interval_us']
            position, yaw = sample_pose(plan['planning_waypoints'], time_us, args.front_axis)
            transform = Matrix.Translation(Vector(position)) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Translation(-anchor)
            for obj, matrix in original.items():
                obj.matrix_world = transform @ matrix
            bpy.context.view_layer.update()
            # New temporary render only; no old raw image or private file is read.
            scratch = out / f'{camera_id}-{index:06d}.png'
            scene.render.filepath = str(scratch)
            bpy.ops.render.render(write_still=True)
            raw = sanitize_png(read_bytes(scratch))
            name = f'media/{camera_id}/{index:06d}.png'
            write_bytes(out / 'safe' / name, raw)
            scratch.unlink()
            records.append({'camera_id': camera_id, 'frame_index': index,
                            'source_time_us': time_us, 'filename': name, 'file_sha256': digest(raw)})
    require(file_sha(source) == expected_source, 'SOURCE_CHANGED')
    # Preserve an explicitly supplied declaration byte-for-byte; never invent provenance.
    clock = new_clock
    write_bytes(out / 'safe/clock.json', new_clock_raw)
    write_json(out / 'safe/rgb.json', {'run_id': args.run_id, 'clock_id': clock['clock_id'],
        'source_sha256': expected_source, 'catalog_sha256': freeze['source_pins']['catalog_sha256'],
        'data_origin': 'ACTUAL_BLENDER', 'full_run': selected_count == count, 'fps': 5, 'frames': records})
    write_json(out / 'authoring-receipt.json', {'authorization_ref': args.authorization_ref,
        'producer_sha256': file_sha(Path(__file__)), 'freeze_sha256': FREEZE_SHA256,
        'front_axis_ref': args.front_axis_ref, 'frame_count': len(records),
        'source_before_sha256': expected_source, 'source_after_sha256': file_sha(source),
        'model_visual_acceptance': 'UNKNOWN', 'identity': 'UNCONFIRMED', 'physical_traversal': 'UNKNOWN'})


if __name__ == '__main__':
    main()
