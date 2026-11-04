"""Port of LOCAL build_preview.py; creates a new derivative and static renders only.

No private preview poses, event answers or original media are bundled.
Use Python --help without Blender; execution requires explicit authorization.
"""
from __future__ import annotations
import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from r004_local_common import (argv_after_separator, authorize, canonical_hash, checked_path,
    disk as check_disk, execution_options, file_sha, new_output, parser, pinned, require, write_json)

SOURCE_SHA256 = '6e7de38dc069d330e0ffbb6c0051cdab304566fdbb7e3e8dfb429af863ae6d8e'


def parse_args(argv=None):
    p = parser(__doc__)
    p.add_argument('--source', type=Path, required=True, help='Read-only parent blend; never saved over.')
    p.add_argument('--source-sha256', default=SOURCE_SHA256, help='Pin of the selected parent; pass a new derivative pin when chaining builds.')
    p.add_argument('--output', type=Path, required=True, help='New output directory, outside the source.')
    execution_options(p)
    return p.parse_args(argv_after_separator(argv))


def main(argv=None):
    args = parse_args(argv)
    authorize(args)
    source = checked_path(args.source)
    pinned(source, args.source_sha256)
    source_before = file_sha(source)
    # No bpy import, source read, mkdir or render occurs on --help/import.
    import bpy
    from mathutils import Vector
    OUT = new_output(args.output)
    DEST = OUT / 'controlled_scene_v1_s001_r004.blend'
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    def disk(tag):
        free = check_disk(OUT, 32 * 1024**2)
        write_json(OUT / (tag + '-space.json'), {'available_bytes': free})
    sha = file_sha
    canon = canonical_hash
    def write(name, doc):
        write_json(OUT / name, doc)
    def mat(name, color):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.diffuse_color = (*color, 1)
        m.use_nodes = True
        n = m.node_tree.nodes.get('Principled BSDF')
        if n:
            n.inputs['Base Color'].default_value = (*color, 1)
            n.inputs['Roughness'].default_value = 0.8
        return m
    def cube(name, loc, scale, material):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        o = bpy.context.object
        o.name = name
        o.dimensions = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        o.data.materials.append(material)
        return o
    scene = bpy.context.scene
    disk('before-build')
    scene.frame_set(1)
    wall = mat('R004_ENV_WALL_NEUTRAL', (0.54, 0.53, 0.48))
    floor = mat('R004_ENV_FLOOR_NEUTRAL', (0.25, 0.26, 0.24))
    for o in bpy.data.objects:
        if o.type == 'MESH' and (o.name.startswith('WALL_') or o.name == 'CEILING_STATIC'):
            o.data = o.data.copy()
            o.data.materials.clear()
            o.data.materials.append(wall)
        if o.type == 'MESH' and o.name == 'FLOOR_GROUND':
            o.data = o.data.copy()
            o.data.materials.clear()
            o.data.materials.append(floor)
    cube('R004_EXTERIOR_FLOOR', (-9.2, 1, -0.12), (12, 14, 0.12), floor)
    cut = cube('R004_DOOR_BOOLEAN_TOOL', (-3.26, 0, 1.2), (0.8, 1.4, 2.4), wall)
    for name in ['WALL_VEST_W', 'WALL_JOINED_SHELL']:
        o = bpy.data.objects.get(name)
        if o and o.type == 'MESH':
            mod = o.modifiers.new('R004_ENTRY_APERTURE', 'BOOLEAN')
            mod.operation = 'DIFFERENCE'
            mod.object = cut
            mod.solver = 'EXACT'
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cut, do_unlink=True)
    body = mat('R004_ENV_VEHICLE_NEUTRAL', (0.19, 0.21, 0.18))
    glass = mat('R004_ENV_GLASS_NEUTRAL', (0.09, 0.11, 0.1))
    tire = mat('R004_ENV_TIRE', (0.025, 0.025, 0.025))
    cube('R004_ENV_VEHICLE_BODY', (-8, -3, 0.65), (3.8, 1.7, 0.7), body)
    cube('R004_ENV_VEHICLE_CABIN', (-8.2, -3, 1.22), (1.9, 1.5, 0.65), glass)
    for x in [-9.15, -6.85]:
        for y in [-3.85, -2.15]:
            bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.37, depth=0.2, location=(x, y, 0.37), rotation=(math.pi / 2, 0, 0))
            o = bpy.context.object
            o.name = 'R004_ENV_WHEEL'
            o.data.materials.append(tire)
    settings = {'CAM_EXT_CAR': ((-13, -6, 3), (-8, -3, 1), 70), 'CAM_EXT_CLEAR': ((-13, 7, 3), (-7, 5, 1), 70), 'CAM_ENTRY': ((-2.6, 1.8, 2.5), (-6, 0, 1), 75), 'CAM_W1': ((-2.6, -1.4, 2), (6, 1.2, 1), 75), 'CAM_W2': ((14.4, 2.1, 1.8), (8, 1.2, 1), 75), 'CAM_BRANCH': ((16.8, 6.5, 2.5), (16, 2.8, 1), 75), 'CAM_R101_IN': ((10.4, -4.5, 2.5), (8, -0.7, 1), 70), 'CAM_WIDE': ((17, 13.5, 2.7), (16, 5, 1), 90)}
    for o in list(bpy.data.objects):
        if o.type == 'CAMERA' and o.name not in settings:
            bpy.data.objects.remove(o, do_unlink=True)
    for name, (loc, target, hfov) in settings.items():
        o = bpy.data.objects.get(name)
        if o is None:
            o = bpy.data.objects.new(name, bpy.data.cameras.new(name))
            scene.collection.objects.link(o)
        o.animation_data_clear()
        o.location = loc
        o.rotation_euler = (Vector(target) - o.location).to_track_quat('-Z', 'Y').to_euler()
        c = o.data
        c.type = 'PERSP'
        c.sensor_fit = 'HORIZONTAL'
        c.sensor_width = 36
        c.sensor_height = 20.25
        c.lens = 36 / (2 * math.tan(math.radians(hfov) / 2))
        c.shift_x = c.shift_y = 0
        c.clip_start = 0.05
        c.clip_end = 100
    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.fps = 5
    scene.frame_start = 1
    scene.frame_end = 150
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.render.film_transparent = False
    actors = [o for o in bpy.data.objects if o.name.startswith('PRODUCTION_')]
    for o in actors:
        o.animation_data_clear()
    for prefix, rgb in [('PRODUCTION_P1', (0.7, 0.025, 0.018)), ('PRODUCTION_P2', (0.015, 0.04, 0.65))]:
        m = mat(prefix + '_R004_SHIRT', rgb)
        for o in actors:
            if o.type == 'MESH' and o.name.startswith(prefix) and any((x in o.name for x in ['TORSO', 'UPPER_ARM', 'FOREARM'])):
                o.data = o.data.copy()
                o.data.materials.clear()
                o.data.materials.append(m)
    scene.camera = bpy.data.objects['CAM_W1']
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(DEST), check_existing=True)
    sourcehash = sha(DEST)
    cams = []
    for name, (_, _, hfov) in settings.items():
        o = bpy.data.objects[name]
        fx = 960 * o.data.lens / o.data.sensor_width
        d = {'schema_version': 'controlled-scene.camera.v1', 'camera_id': name, 'camera_to_world': [list(r) for r in o.matrix_world], 'convention': 'BLENDER_NEG_Z_UP_Y', 'fx': fx, 'fy': fx, 'cx': 480.0, 'cy': 270.0, 'pixel_origin': 'TOP_LEFT_CONTINUOUS', 'width': 960, 'height': 540, 'pixel_aspect_xy': 1.0, 'render_resolution_percentage': 100, 'shift_x': 0.0, 'shift_y': 0.0, 'sensor_fit': 'HORIZONTAL', 'sensor_width_mm': o.data.sensor_width, 'sensor_height_mm': o.data.sensor_height, 'focal_length_mm': o.data.lens, 'clip_start': o.data.clip_start, 'clip_end': o.data.clip_end, 'distortion': None, 'camera_model': 'PINHOLE', 'floor_id': 'FLOOR_GROUND', 'zone_id': 'R004_STATIC_PROPOSED', 'meters_per_unit': 1.0, 'static_validity': {'status': 'NOT_EVALUATED', 'source_sha256': sourcehash}}
        d['calibration_sha256'] = canon(d)
        cams.append(d)
    write('safe_static/cameras.json', {'schema_version': 'controlled-scene.cameras.v1', 'cameras': cams, 'run_bindings': []})
    static = []
    for o in bpy.data.objects:
        if o.type != 'MESH' or o in actors:
            continue
        deps = bpy.context.evaluated_depsgraph_get()
        obj = o.evaluated_get(deps)
        mesh = obj.to_mesh()
        static.append({'object_ref': o.name, 'vertices_world_m': [list(obj.matrix_world @ v.co) for v in mesh.vertices], 'triangles_or_polygons': [list(poly.vertices) for poly in mesh.polygons]})
        obj.to_mesh_clear()
    write('safe_static/static_geometry.PROPOSED.json', {'schema_version': 'q-demo.static-geometry-proposal.v1', 'scene_revision': 'r004', 'source_sha256': sourcehash, 'approval_status': 'DRAFT', 'allowed_purposes': [], 'physical_traversal': 'UNKNOWN', 'collision': 'UNKNOWN', 'objects': static})
    for o in actors:
        o.hide_render = True
    (OUT / 'safe_static/frames').mkdir(exist_ok=True)
    for name in settings:
        disk('before-static-' + name)
        scene.camera = bpy.data.objects[name]
        scene.render.filepath = str(OUT / 'safe_static/frames' / f'{name}.png')
        bpy.ops.render.render(write_still=True)
        disk('after-static-' + name)
    write('static-export-receipt.json', {'source_sha256': sourcehash, 'source_parent_sha256': source_before, 'cameras_file_sha256': sha(OUT / 'safe_static/cameras.json'), 'geometry_file_sha256': sha(OUT / 'safe_static/static_geometry.PROPOSED.json'), 'static_frames': [{'camera_id': n, 'file_sha256': sha(OUT / 'safe_static/frames' / f'{n}.png')} for n in settings], 'approval_status': 'DRAFT', 'run_bindings': 'NONE', 'gt_read_for_inference': False})
    disk('after-build-static')
    print('R004_STATIC_DONE', sourcehash)
    require(file_sha(source) == source_before, 'SOURCE_CHANGED')


if __name__ == '__main__':
    main()
