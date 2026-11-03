"""Recompute #343 planning arithmetic and pinned static evidence inventory only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'cards': ('b5302a0ad9a1895d728946d824854b6001b6b66a',
              'docs/evaluation/R004_COMPLEX_SCENARIO_CARDS_V2.md',
              '02d98c06ac93b5b1eec019d65415eada7b751b4c6e76d3982a28aa36d9efd88b'),
    'design': ('0b6e8004b3a9ae03ce5184466498dc22b727f8c4',
               'docs/evaluation/Q5_SWITCH_EVAL_V2_DESIGN.md',
               '0a4e579b0664ab663e44809ebc0d2670b434c17161d7c24f237b1be4d051cc4c'),
    'static_report': ('c5aa674ce772b7f49e813c89ab6fa415064e22ca',
                      'docs/engineering/R004_L2_STATIC_FEASIBILITY_20261027.json',
                      'ecf1ce4615da7faf6a908e1a98ec329ac62814b9f162af60b6085f945f1baeab'),
}
STATIC_PINS = {
    'cameras.json': '3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f',
    'static_geometry.PROPOSED.json': 'bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def need(value, message):
    if not value:
        raise ValueError(message)


def searching_bound(gap_us):
    if gap_us <= 5_200_000:
        return 1
    return max(1, -(-(gap_us - 6_600_000) // 1_000_000) + 1) + 1


def axis_in_frustum(camera, foot):
    matrix = camera['camera_to_world']
    for height in (0.0, 0.85, 1.7):
        point = [foot[0], foot[1], foot[2] + height]
        delta = [point[i] - matrix[i][3] for i in range(3)]
        x, y, z = [sum(matrix[j][i] * delta[j] for j in range(3)) for i in range(3)]
        depth = -z
        planes = [depth - camera['clip_start'], camera['clip_end'] - depth,
                  camera['fx'] * x + camera['cx'] * depth,
                  (camera['width'] - camera['cx']) * depth - camera['fx'] * x,
                  camera['cy'] * depth - camera['fy'] * y,
                  (camera['height'] - camera['cy']) * depth + camera['fy'] * y]
        if min(planes) < 0:
            return False
    return True


def static_audit(catalog, geometry):
    cameras = {row['camera_id']: row for row in catalog['cameras']}
    objects = {row['object_ref']: row for row in geometry['objects']}
    bounds = {}
    for name, obj in objects.items():
        if name.startswith(('WALK_', 'OBSTACLE_SCREEN_')):
            vertices = obj['vertices_world_m']
            bounds[name] = [[min(p[i] for p in vertices), max(p[i] for p in vertices)] for i in range(3)]
    box = bounds['WALK_CORNER']
    nx, ny = [round((box[i][1] - box[i][0]) / 0.1) for i in (0, 1)]
    need(nx > 0 and ny > 0, 'CORNER_BOUNDS_INVALID')
    corners = [[x, y, box[2][1]] for x in box[0] for y in box[1]]
    pair = [cameras[key] for key in ('CAM_BRANCH', 'CAM_WIDE')]
    counts = {'both': 0, 'from_only': 0, 'to_only': 0, 'neither': 0}
    for ix in range(nx + 1):
        for iy in range(ny + 1):
            point = [box[0][0] + ix / nx * (box[0][1] - box[0][0]),
                     box[1][0] + iy / ny * (box[1][1] - box[1][0]), box[2][1]]
            a, b = [axis_in_frustum(camera, point) for camera in pair]
            key = 'both' if a and b else 'from_only' if a else 'to_only' if b else 'neither'
            counts[key] += 1
    return {
        'camera_ids': sorted(cameras), 'camera_count': len(cameras),
        'camera_static_validity': {key: row['static_validity']['status'] for key, row in cameras.items()},
        'geometry_approval_status': geometry['approval_status'],
        'geometry_allowed_purposes': geometry['allowed_purposes'],
        'source_sha256_in_export': geometry['source_sha256'],
        'object_count': len(objects), 'proposed_object_bounds_xyz_m': bounds,
        'corner_bbox_axis_frustum_check': {
            'camera_ids': ['CAM_BRANCH', 'CAM_WIDE'], 'axis_heights_m': [0.0, 0.85, 1.7],
            'grid_shape': [nx + 1, ny + 1], 'counts': counts,
            'four_corner_axes_in_both_frusta': all(axis_in_frustum(c, p) for c in pair for p in corners),
            'support_bbox_only_not_continuous_surface_or_occlusion': True,
        },
        'obstacle_screen_count': sum(name.startswith('OBSTACLE_SCREEN_') for name in objects),
        'actual_occlusion_and_whole_body_visibility': 'UNKNOWN',
        'collision_and_physical_navigation': 'UNKNOWN',
        'new_camera_calibration_and_selected_routes': 'MISSING',
    }


def report(static_root=None):
    inputs, raw_sources = {}, {}
    for key, (commit, path, expected) in SOURCES.items():
        raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', commit + ':' + path])
        need(sha(raw) == expected, 'SOURCE_PIN_MISMATCH: ' + key)
        inputs[key] = {'commit': commit, 'path': path, 'sha256': expected}
        raw_sources[key] = raw
    static = json.loads(raw_sources['static_report'])
    need(static['render_performed'] is False and static['rgb_read'] is False
         and static['renderer_trajectory_visibility_depth_or_gt_read'] is False,
         'STATIC_EVIDENCE_SCOPE_MISMATCH')
    corner = next(p for p in static['frustum_pairs']
                  if p['from_camera_id'] == 'CAM_BRANCH' and p['to_camera_id'] == 'CAM_WIDE')
    direct = {'status': 'NOT_RUN', 'gate': 'LOCAL_STATIC_ROOT_UNKNOWN', 'input_pins': STATIC_PINS}
    if static_root is not None:
        root = Path(static_root).absolute()
        need(root.resolve() == root, 'STATIC_ROOT_ALIAS_REFUSED')
        checked, parsed = {}, {}
        for name, expected in STATIC_PINS.items():
            path = root / name
            need(path.is_file() and not path.is_symlink(), 'STATIC_FILE_REQUIRED: ' + name)
            raw = path.read_bytes()
            need(sha(raw) == expected, 'STATIC_PIN_MISMATCH: ' + name)
            parsed[name] = json.loads(raw)
            need(sha(path.read_bytes()) == expected, 'STATIC_CHANGED_DURING_READ: ' + name)
            checked[name] = {'sha256': expected, 'bytes': len(raw)}
        audit = static_audit(parsed['cameras.json'], parsed['static_geometry.PROPOSED.json'])
        for name, expected in STATIC_PINS.items():
            need(sha((root / name).read_bytes()) == expected, 'STATIC_CHANGED_AFTER_AUDIT: ' + name)
        direct = {'status': 'BOUNDED_STATIC_CHECKS_COMPLETED', 'inputs': checked,
                  'audit': audit, 'input_bytes_unchanged_after_audit': True,
                  'new_geometry_or_occlusion_claim': False}
    candidates = [
        ('B2-1', '門廳補盲鏡頭', ['NEW_CAMERA_AND_CALIBRATION', 'NEW_GRAPH_AND_G4', 'NEW_SCENE']),
        ('B2-2', 'CORR_N北段／R102路線', ['SCOPE_SELECTION', 'NEW_TRANSITIONS_AND_G4', 'ROUTE_AND_COVERAGE']),
        ('B2-3', '短暫遮擋型NO_SWITCH', ['OCCLUDER_AND_ROUTE_UNKNOWN', 'OBSERVATION_AND_COVERAGE']),
        ('B2-4', '超過G_max長空檔', ['U_D4_PENDING', 'PLANNED_BUDGET', 'PREFIX_EVIDENCE']),
        ('B2-5', '多人干擾', ['INTERFERER_ROUTE', 'NEW_SCENE', 'G4_AND_SELECTED_PARAMETERS']),
    ]
    return {
        'purpose': '#343 planning receipt; no runtime configuration or schema adoption',
        'status': 'PROPOSED_BLOCKED', 'source_inputs': inputs,
        'generator_sha256': sha(Path(__file__).read_bytes()),
        'direct_static_input_check': direct,
        'reused_static_evidence': {
            'source_sha256': static['static_source_sha256'],
            'branch_wide_corner_counts': corner['counts'],
            'corner_rectangle_axis_in_both_frusta': corner['both_frusta_contain_entire_support_rectangle_axis'],
            'occlusion': 'UNKNOWN', 'physical_traversal': 'UNKNOWN',
            'new_camera_or_obstacle_feasibility': 'UNKNOWN',
            'this_round': 'RECOMPUTED_BOUNDED_STATIC_CHECKS' if static_root is not None else 'NOT_RUN',
        },
        'arithmetic': {
            'units': 'microseconds', 'planned_budget': 4, 'session_budget': 6,
            'single_event_session_max_gap_us': 10_600_000,
            'single_event_planned_budget_max_gap_us': 8_600_000,
            'searching_bounds': {str(g): searching_bound(g) for g in (5_200_000, 6_600_000, 8_600_000, 10_600_000, 10_800_000)},
        },
        'candidates': [{'id': key, 'title': title, 'status': 'PROPOSED_BLOCKED',
                        'gates': gates, 'selected': False, 'render_authorized': False,
                        'allowed_purposes': []} for key, title, gates in candidates],
        'original_blender_video_or_dataset_read_or_copied': False, 'render_performed': False,
        'inference_or_model_execution': False, 'g4_effective': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--static-root', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = report(args.static_root)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    except (OSError, ValueError, KeyError, StopIteration, subprocess.CalledProcessError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
