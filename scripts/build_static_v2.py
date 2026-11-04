"""Port of LOCAL build_static_v2.py; creates a new derivative and static renders only.

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

SOURCE_SHA256 = 'f079c8b055c0030445b088d50fa4e7866a7ed4553fefc4cf8af8dd4ab899aea8'


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
    settings = {}
    for c in bpy.data.objects:
        if c.type == 'CAMERA':
            settings[c.name] = (list(c.location), None, math.degrees(c.data.angle_x))
    c = bpy.data.objects['CAM_ENTRY']
    c.location = (-2.5, 0.4, 2.5)
    c.rotation_euler = (Vector((-6, 0, 1)) - c.location).to_track_quat('-Z', 'Y').to_euler()
    for name, color in [('R004_ENV_WALL_NEUTRAL', (0.36, 0.33, 0.27)), ('R004_ENV_FLOOR_NEUTRAL', (0.09, 0.11, 0.085))]:
        mat(name, color)
    light = bpy.data.lights.new('R004_EXTERIOR_FILL', 'AREA')
    light.energy = 1800
    light.shape = 'DISK'
    light.size = 8
    obj = bpy.data.objects.new('R004_EXTERIOR_FILL', light)
    scene.collection.objects.link(obj)
    obj.location = (-9, 0, 6)
    scene.render.engine = 'BLENDER_EEVEE'
    actors = [o for o in bpy.data.objects if o.name.startswith('PRODUCTION_')]
    for o in actors:
        o.hide_render = False
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
