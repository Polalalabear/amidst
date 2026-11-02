"""Read-only D89 static lower bounds. Never opens renderer/time-dependent data."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def rectangle_distance(a, b):
    # All frozen patches used here are axis-aligned rectangles. Check that before
    # using their bounding boxes; a bound remains optimistic about obstructions.
    for polygon in (a, b):
        assert len(polygon) == 4
        assert len({p[2] for p in polygon}) == 1
        assert len({p[0] for p in polygon}) == len({p[1] for p in polygon}) == 2
    return math.sqrt(sum(max(0, min(p[i] for p in a) - max(p[i] for p in b),
                                 min(p[i] for p in b) - max(p[i] for p in a)) ** 2
                         for i in range(3)))


def audit(root, patches_path):
    catalog_path = root / 'safe_static/cameras.json'
    geometry_path = root / 'safe_static/static_geometry.PROPOSED.json'
    source = root / 'controlled_scene_v1_s001_r004.blend'
    expected = {
        'catalog': '3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f',
        'geometry': 'bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a',
        'blend': '466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b',
        'patches': '17dbae08de96a65b8cc9710b5a8cb4a945d466362f17d41a7e6a0b3108285151',
    }
    paths = dict(catalog=catalog_path, geometry=geometry_path, blend=source, patches=patches_path)
    actual = {key: sha(path) for key, path in paths.items()}
    assert actual == expected, actual
    geometry = json.loads(geometry_path.read_bytes())
    cameras = json.loads(catalog_path.read_bytes())
    patches = json.loads(patches_path.read_bytes())
    assert geometry['source_sha256'] == expected['blend']
    assert all(c['static_validity']['status'] == 'NOT_EVALUATED' for c in cameras['cameras'])
    names = [(f'EXT_CAR_{side}_to_W1', f'CAM_EXT_CAR:EXIT_V3:{side}_APPROACH', 'CAM_W1:ENTRY_V3:E_VEST_CORR', 3.0)
             for side in ('NORTH', 'SOUTH')]
    names += [('EXT_CLEAR_to_W1', 'CAM_EXT_CLEAR:EXIT_V3:E_OUT_VEST', 'CAM_W1:ENTRY_V3:E_VEST_CORR', 3.0),
              ('W2_to_BRANCH', 'CAM_W2:EXIT_V3:E_W_CORNER', 'CAM_BRANCH:ENTRY_V3:E_W_CORNER', 3.0),
              ('W2_to_WIDE', 'CAM_W2:EXIT_V3:E_W_CORNER', 'CAM_WIDE:ENTRY_V3:E_W_CORNER', 3.0),
              ('W1_to_R101', 'CAM_W1:EXIT_V3:E_PORTAL_R101', 'CAM_R101_IN:ENTRY_V3:E_PORTAL_R101', 2.0),
              ('W2_to_R101', 'CAM_W2:EXIT_V3:E_PORTAL_R101', 'CAM_R101_IN:ENTRY_V3:E_PORTAL_R101', 2.0),
              ('EXT_destination_entry_separation_NORTH', 'CAM_EXT_CAR:ENTRY_V3:NORTH_APPROACH', 'CAM_EXT_CLEAR:ENTRY_V3:E_OUT_VEST', 0.8),
              ('EXT_destination_entry_separation_SOUTH', 'CAM_EXT_CAR:ENTRY_V3:SOUTH_APPROACH', 'CAM_EXT_CLEAR:ENTRY_V3:E_OUT_VEST', 0.8),
              ('CORR_destination_entry_separation', 'CAM_W1:ENTRY_V3:E_W_CORNER', 'CAM_W2:ENTRY_V3:E_W_CORNER', 0.8)]
    bounds = []
    for label, a, b, seconds in names:
        distance = rectangle_distance(patches[a]['polygon_world_m'], patches[b]['polygon_world_m'])
        bounds.append(dict(measurement=label, from_patch=a, to_patch=b, euclidean_lower_bound_m=distance,
                           planned_delta_s=seconds, minimum_mean_speed_m_s=distance / seconds,
                           minimum_seconds_at_1_5_m_s=distance / 1.5,
                           within_1_5_m_s_lower_bound=distance <= 1.5 * seconds))
    supports = []
    for obj in geometry['objects']:
        if obj['object_ref'] in {'R004_EXTERIOR_FLOOR', 'WALK_VEST_W', 'WALK_CORR_W', 'WALK_CORNER', 'WALK_R101'}:
            vertices = obj['vertices_world_m']
            supports.append(dict(object_ref=obj['object_ref'], vertex_count=len(vertices),
                                 bounds_world_m=[[min(p[i] for p in vertices), max(p[i] for p in vertices)] for i in range(3)]))
    assert actual == {key: sha(path) for key, path in paths.items()}
    return dict(schema_version='q-demo.r004-d89-static-feasibility.v1', input_sha256=actual,
                source_unchanged=True, method='STATIC_RECTANGLE_DISTANCE_LOWER_BOUND',
                bounds=bounds, support_bounds=supports,
                route_or_actor_time_samples_read=False, renderer_visibility_or_depth_read=False,
                render_performed=False, source_saved=False,
                whole_body_visibility='UNKNOWN', collision='UNKNOWN', physical_traversal='UNKNOWN',
                total_frames={'A4': 1000, 'B4': 1050},
                scope='A4-1 50 s; B4-1 42 s; D89 NO_SWITCH yields; no script creation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--static-root', type=Path, required=True)
    parser.add_argument('--patches', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.static_root, args.patches)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
