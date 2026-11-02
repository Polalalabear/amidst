"""Reproduce L2 static planning checks; no renderer, actor tracks or RGB reads."""
import argparse
import hashlib
import json
import math
from pathlib import Path

EXPECTED = {
    'catalog': '3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f',
    'geometry': 'bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a',
    'patches': '17dbae08de96a65b8cc9710b5a8cb4a945d466362f17d41a7e6a0b3108285151',
    'cards': '131fcbcde58899101880e3c968cd18b8fa65c96aa19c049b953b9dd36ec12a82',
}
SOURCE = '466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b'
SPEED = 1.2
HEIGHTS = (0.0, 0.85, 1.7)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def camera_coordinates(camera, point):
    matrix = camera['camera_to_world']
    delta = [point[i] - matrix[i][3] for i in range(3)]
    return [sum(matrix[j][i] * delta[j] for j in range(3)) for i in range(3)]


def planes(camera, point):
    x, y, z = camera_coordinates(camera, point)
    depth = -z
    return [depth - camera['clip_start'], camera['clip_end'] - depth,
            camera['fx'] * x + camera['cx'] * depth,
            (camera['width'] - camera['cx']) * depth - camera['fx'] * x,
            camera['cy'] * depth - camera['fy'] * y,
            (camera['height'] - camera['cy']) * depth + camera['fy'] * y]


def in_frustum(camera, point, axis=False):
    heights = HEIGHTS if axis else (0.0,)
    return all(min(planes(camera, [point[0], point[1], point[2] + h])) >= 0 for h in heights)


def project(camera, point):
    x, y, z = camera_coordinates(camera, point)
    return [camera['cx'] + camera['fx'] * x / -z,
            camera['cy'] - camera['fy'] * y / -z, -z]


def segment_interval(values_a, values_b):
    lo, hi = 0.0, 1.0
    for a, b in zip(values_a, values_b, strict=True):
        if a < 0 and b < 0:
            return None
        if a < 0:
            lo = max(lo, -a / (b - a))
        elif b < 0:
            hi = min(hi, a / (a - b))
    return (lo, hi) if lo <= hi else None


def frustum_intervals(camera, points):
    result = []
    distance = 0.0
    for a, b in zip(points, points[1:], strict=False):
        va, vb = [], []
        for h in HEIGHTS:
            va += planes(camera, [a[0], a[1], a[2] + h])
            vb += planes(camera, [b[0], b[1], b[2] + h])
        interval = segment_interval(va, vb)
        length = math.dist(a, b)
        if interval:
            result.append([(distance + fraction * length) / SPEED for fraction in interval])
        distance += length
    return result


def rectangle_values(polygon, point):
    return [point[0] - min(v[0] for v in polygon), max(v[0] for v in polygon) - point[0],
            point[1] - min(v[1] for v in polygon), max(v[1] for v in polygon) - point[1]]


def first_patch_entry(points, polygon):
    distance = 0.0
    for a, b in zip(points, points[1:], strict=False):
        interval = segment_interval(rectangle_values(polygon, a), rectangle_values(polygon, b))
        length = math.dist(a, b)
        if interval:
            return (distance + interval[0] * length) / SPEED
        distance += length
    return None


def support_cells(geometry):
    result = []
    for obj in geometry['objects']:
        if obj['object_ref'] not in {'R004_EXTERIOR_FLOOR', 'WALK_VEST_W', 'WALK_CORR_W',
                                     'WALK_CORNER', 'WALK_CORR_N', 'WALK_R101'}:
            continue
        vertices = obj['vertices_world_m']
        for face in obj['triangles_or_polygons']:
            polygon = [vertices[i] for i in face]
            if len({round(p[2], 6) for p in polygon}) != 1:
                continue
            top = max(v[2] for v in vertices)
            if abs(polygon[0][2] - top) > 1e-6:
                continue
            xs, ys = {round(p[0], 6) for p in polygon}, {round(p[1], 6) for p in polygon}
            if len(polygon) == 4 and len(xs) == len(ys) == 2:
                result.append((obj['object_ref'], polygon))
    return result


def supported(point, cells):
    return any(min(rectangle_values(polygon, point)) >= -1e-6
               and abs(point[2] - polygon[0][2]) < 1e-6 for _, polygon in cells)


def route_audit(name, points, patches, cameras, cells):
    length = sum(math.dist(a, b) for a, b in zip(points, points[1:], strict=False))
    unsupported = 0
    for a, b in zip(points, points[1:], strict=False):
        steps = max(1, math.ceil(math.dist(a, b) / 0.02))
        for i in range(steps + 1):
            p = [a[k] + (b[k] - a[k]) * i / steps for k in range(3)]
            # The 6 cm exterior/interior step has no support at intermediate z.
            if abs(a[2] - b[2]) > 1e-6:
                continue
            unsupported += not supported(p, cells)
    return dict(route_id=name, role='PROPOSED_PLANNING_POLYLINE_NOT_RENDERER_TRACK',
                points_world_m=points, length_m=length, duration_at_1_2_m_s=length / SPEED,
                sampled_support_failures_2cm=unsupported,
                support_only_not_collision_or_navigation=True,
                first_entry_s={key: first_patch_entry(points, patch['polygon_world_m'])
                               for key, patch in patches.items() if ':ENTRY_' in key},
                axis_frustum_intervals_s={key: frustum_intervals(camera, points)
                                          for key, camera in cameras.items()},
                actual_last_visible_time_s=None, occlusion='UNKNOWN')


def grid_pair(a, b, box, z, cameras, cells):
    groups = dict(both=[], from_only=[], to_only=[])
    for ix in range(round((box[1] - box[0]) * 10) + 1):
        for iy in range(round((box[3] - box[2]) * 10) + 1):
            point = [round(box[0] + ix * 0.1, 6), round(box[2] + iy * 0.1, 6), z]
            if not supported(point, cells):
                continue
            pa, pb = in_frustum(cameras[a], point, True), in_frustum(cameras[b], point, True)
            key = 'both' if pa and pb else 'from_only' if pa else 'to_only' if pb else None
            if key:
                groups[key].append(point)
    examples = {}
    for key, points in groups.items():
        if points:
            centroid = [sum(p[i] for p in points) / len(points) for i in range(3)]
            point = min(points, key=lambda p: math.dist(p, centroid))
            examples[key] = dict(point_world_m=point,
                                 foot_projection_uv_depth_m={c: project(cameras[c], point) for c in [a, b]})
    corners = [[x, y, z] for x in box[:2] for y in box[2:]]
    return dict(from_camera_id=a, to_camera_id=b, grid_spacing_m=0.1,
                vertical_axis_heights_m=list(HEIGHTS), support_box_xy_m=box,
                counts={k: len(v) for k, v in groups.items()}, examples=examples,
                both_frusta_contain_entire_support_rectangle_axis=all(
                    in_frustum(cameras[c], p, True) for c in [a, b] for p in corners),
                interpretation='CALIBRATION_FRUSTUM_ONLY; excludes occlusion and person extent',
                actual_exclusive_visibility='UNKNOWN')


def audit(static_root, graph_root, cards):
    paths = dict(catalog=static_root / 'safe_static/cameras.json',
                 geometry=static_root / 'safe_static/static_geometry.PROPOSED.json',
                 patches=graph_root / 'static_patches_v3.json', cards=cards,
                 region_graph=graph_root / 'region_graph_v3.json',
                 camera_graph=graph_root / 'camera_graph_v3.json',
                 tracking_scope=graph_root / 'tracking_scope_v3.json')
    before = {k: sha(p) for k, p in paths.items()}
    for key, expected in EXPECTED.items():
        if before[key] != expected:
            raise ValueError(f'INPUT_PIN_MISMATCH:{key}')
    catalog = json.loads(paths['catalog'].read_bytes())
    geometry = json.loads(paths['geometry'].read_bytes())
    patches = json.loads(paths['patches'].read_bytes())
    cameras = {c['camera_id']: c for c in catalog['cameras']}
    if geometry['source_sha256'] != SOURCE:
        raise ValueError('SOURCE_PIN_MISMATCH')
    if not all(c['static_validity']['status'] == 'NOT_EVALUATED' for c in cameras.values()):
        raise ValueError('STATIC_VALIDITY_CHANGED')
    cells = support_cells(geometry)
    south = [[-6.2, -4.1, -0.06], [-3.2, 0.0, -0.06], [-3.2, 0.0, 0.0], [0.35, 1.1, 0.0]]
    clear = [[-3.35, 0.4, -0.06], [-3.2, 0.0, -0.06], [-3.2, 0.0, 0.0], [0.35, 1.1, 0.0]]
    routes = {
        'SOUTH_VIA_WEST_PORTAL_TO_W1': south,
        'NORTH_VIA_WEST_PORTAL_TO_W1': [[-10.0, -0.9, -0.06], *south[1:]],
        'CLEAR_VIA_WEST_PORTAL_TO_W1': clear,
        'W1_VIA_WEST_PORTAL_TO_SOUTH': list(reversed(south)),
        'BRANCH_TO_W1_THEN_W2_DETOUR': [[15.0, 1.4, 0.0], [13.9, 0.2, 0.0],
                                      [12.85, 1.6, 0.0], [12.6, 1.85, 0.0], [11.4, 1.15, 0.0]],
        'W2_TO_BRANCH_THEN_WIDE': [[11.4, 1.15, 0.0], [15.0, 1.4, 0.0], [15.5, 1.4, 0.0]],
        'R101_TO_W2_THEN_W1': [[8.0, -0.1, 0.0], [8.0, 0.1, 0.0], [7.9, 0.6, 0.0]],
        'R101_PORTAL_TO_DEEP': [[8.0, -0.1, 0.0], [8.0, -4.0, 0.0]],
        'R101_TO_FRUSTUM_OUTSIDE_CORNER': [[8.0, -0.5, 0.0], [5.2, -4.8, 0.0]],
    }
    route_results = [route_audit(k, p, patches, cameras, cells) for k, p in routes.items()]
    pairs = [grid_pair('CAM_EXT_CAR', 'CAM_EXT_CLEAR', [-15.2, -3.2, -6.0, 8.0], -0.06, cameras, cells),
             grid_pair('CAM_BRANCH', 'CAM_WIDE', [15.0, 17.4, 0.0, 2.4], 0.0, cameras, cells),
             grid_pair('CAM_W1', 'CAM_W2', [0.0, 15.0, 0.0, 2.4], 0.0, cameras, cells)]
    probes = [[8.0, -1.0, 0.0], [8.0, -4.0, 0.0], [5.2, -4.8, 0.0], [0.1, 1.2, 0.0]]
    cards_plan = {'V2-RR': (4, 30), 'V2-LG': (4, 24), 'V2-LL': (4, 24), 'V2-LT': (4, 20),
                  'V2-PE1': (5, 22), 'V2-PE2': (4, 24), 'V2-OV1': (4, 26), 'V2-OV2': (5, 16),
                  'V2-OV3': (5, 16), 'V2-A4-2': (4, 77), 'V2-B4-2': (5, 80)}
    estimate = {}
    for key, (count, seconds) in cards_plan.items():
        frames = count * seconds * 5
        estimate[key] = dict(camera_count=count, duration_s=seconds, frames=frames,
                             historical_rgb_estimate_gib=frames * 63976 * 1024 / 150 / 2**30,
                             historical_forward_estimate_min=frames * 1.108406209 / 60,
                             actual_r004_rgb_or_forward_measurement=False)
    after = {k: sha(p) for k, p in paths.items()}
    if after != before:
        raise ValueError('INPUT_CHANGED_DURING_AUDIT')
    return dict(schema_version='q-demo.r004-l2-static-feasibility.v1', status='PLANNING_ONLY_NOT_ACCEPTANCE',
                inputs_sha256=before, static_source_sha256=SOURCE, input_bytes_unchanged=True,
                source_blend_bytes_read=False, source_blend_bytes_verified=False,
                cards_commit='d6e22e60eb56cc5ccd863e4f73e595d82f4b0e7b',
                base_commit='680ca357a31b664bed3feb6a5284dcd7c5c0d94d',
                route_role='NEW_EXPLICIT_PLANNING_POLYLINES; not frozen or executed actor routes',
                route_audits=route_results, frustum_pairs=pairs,
                probes=[dict(point_world_m=p, supported=supported(p, cells),
                             axis_in_frustum={key: in_frustum(c, p, True) for key, c in cameras.items()},
                             foot_uv_depth_m={key: project(c, p) for key, c in cameras.items()}) for p in probes],
                estimates=estimate, renderer_trajectory_visibility_depth_or_gt_read=False,
                rgb_read=False, render_performed=False, source_saved=False,
                whole_body_visibility='UNKNOWN', physical_traversal='UNKNOWN', collision='UNKNOWN',
                G4_approved=False, line_1_changed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--static-root', type=Path, required=True)
    parser.add_argument('--graph-root', type=Path, required=True)
    parser.add_argument('--cards', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.static_root, args.graph_root, args.cards)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
