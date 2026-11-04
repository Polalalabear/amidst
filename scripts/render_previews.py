"""Render new static, actor-free camera previews; the old private 45-pose set is UNKNOWN.

This ports the LOCAL camera/render loop without importing private preview poses.
Blender --background --disable-autoexec --python THIS -- --source ... --output ...
--execute --authorization-ref ... ; Python THIS --help needs no Blender.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from r004_local_common import (argv_after_separator, authorize, checked_path, disk, execution_options,
    file_sha, new_output, parser, pinned, require, write_json)

SOURCE_SHA256 = '466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b'
CATALOG_SHA256 = '3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f'
DEFAULT_CATALOG = Path(__file__).resolve().parents[1] / 'configs/q1q5/authoring/r004_v2_static_cameras.json'


def parse_args(argv=None):
    p = parser(__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--catalog', type=Path, default=DEFAULT_CATALOG)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--camera-id', action='append', default=[])
    execution_options(p)
    return p.parse_args(argv_after_separator(argv))


def main(argv=None):
    args = parse_args(argv)
    authorize(args)
    source = checked_path(args.source)
    require(file_sha(source) == SOURCE_SHA256, 'INPUT_SHA256_MISMATCH')
    catalog = json.loads(pinned(args.catalog, CATALOG_SHA256))
    cameras = {c['camera_id']: c for c in catalog['cameras']}
    selected = args.camera_id or sorted(cameras)
    require(len(set(selected)) == len(selected) and set(selected) <= cameras.keys(), 'CAMERA_SCOPE_INVALID')
    import bpy
    from mathutils import Matrix
    out = new_output(args.output)
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    scene.frame_set(1)
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    for obj in bpy.data.objects:
        if obj.name.startswith('PRODUCTION_'):
            obj.hide_render = True
    records = []
    for camera_id in selected:
        c = cameras[camera_id]
        camera = bpy.data.objects[camera_id]
        camera.matrix_world = Matrix(c['camera_to_world'])
        camera.data.lens, camera.data.sensor_width = c['focal_length_mm'], c['sensor_width_mm']
        scene.camera = camera
        disk(out, 32 * 1024**2)
        folder = out / camera_id
        folder.mkdir()
        image = folder / 'frame_000000.png'
        scene.render.filepath = str(image)
        bpy.ops.render.render(write_still=True)
        disk(out)
        records.append({'camera_id': camera_id, 'preview_variant': camera_id, 'frame_index': 0,
                        'file_ref': image.relative_to(out).as_posix(), 'file_sha256': file_sha(image),
                        'calibration_sha256': c['calibration_sha256']})
    require(file_sha(source) == SOURCE_SHA256, 'SOURCE_CHANGED')
    write_json(out / 'rgb_index.json', {'schema_version': 'q-demo.preview-rgb.v1',
        'data_origin': 'ACTUAL_BLENDER', 'purpose': 'STATIC_ACTOR_FREE_PREVIEW_ONLY',
        'event_run': False, 'source_sha256': SOURCE_SHA256, 'records': records})


if __name__ == '__main__':
    main()
