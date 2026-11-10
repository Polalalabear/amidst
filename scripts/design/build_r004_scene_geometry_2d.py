"""Build docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json from Codex's #516 feasibility export (D207).

Usage:
  python scripts/design/build_r004_scene_geometry_2d.py <codex_feasibility_dir> <cameras.json> --out <geometry.json>

Inputs (all LOCAL, never committed):
  <codex_feasibility_dir>/scene_export.json   read-only Blender export of the r004 .blend (Codex, #516)
  <codex_feasibility_dir>/geometry_2d.json    Codex's 260 XY cross-section segments over the 0..1.7 m body band
  <codex_feasibility_dir>/ARTIFACT_MANIFEST.json
  <cameras.json>                              r004 safe_static camera catalog

Output: a small, source-bound 2D design geometry for scripts/design/check_actor_clearance.py:
  clearance_segments     Codex's segments unchanged (walls, 5 screens, vehicle body/cabin/wheels)
  occluders_full_height  XY wall pieces that are solid at every topology interval from z=0 up to
                         z>=3.05 m (above every camera), so a 2D sight line that crosses one is
                         blocked in 3D. Door gaps and the low x=15 parapet (window above 0.5 m) are
                         excluded because they are not solid at every height.
  cameras                catalog matrices/intrinsics (camera_to_world, fx, fy, cx, cy, size, clip)
Standard library only. Reads no RGB, Ground Truth, visibility, depth or renderer trajectories.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

SLICE_HEIGHTS_M = (0.25, 1.45, 2.65, 3.05)   # one per shell topology interval (vertex z = 0, .5, 2.4, 2.9, 3.2)
RENDER_CAMERA_SETS = {
    'A4-1': ['CAM_EXT_CAR', 'CAM_EXT_CLEAR', 'CAM_ENTRY', 'CAM_W1'],
    'B4-1': ['CAM_W1', 'CAM_W2', 'CAM_BRANCH', 'CAM_R101_IN', 'CAM_WIDE'],
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def slice_object(obj, z):
    verts, out = obj['vertices_world_m'], set()
    for face in obj['polygons']:
        pts = []
        for ia, ib in zip(face, face[1:] + face[:1]):
            a, b = verts[ia], verts[ib]
            if (a[2] < z < b[2]) or (b[2] < z < a[2]):
                f = (z - a[2]) / (b[2] - a[2])
                pt = (round(a[0] + f * (b[0] - a[0]), 6), round(a[1] + f * (b[1] - a[1]), 6))
                if pt not in pts:
                    pts.append(pt)
        if len(pts) == 2 and math.dist(*pts) > 1e-7:
            out.add(tuple(sorted(pts)))
    return out


def axis_intervals(segments):
    lines = {}
    for a, b in segments:
        if abs(a[0] - b[0]) < 1e-5:
            key, lo, hi = ('x', round(a[0], 4)), *sorted((a[1], b[1]))
        elif abs(a[1] - b[1]) < 1e-5:
            key, lo, hi = ('y', round(a[1], 4)), *sorted((a[0], b[0]))
        else:
            raise ValueError(f'non axis-aligned occluder candidate {a}-{b}')
        lines.setdefault(key, []).append([lo, hi])
    for key, ivs in lines.items():
        ivs.sort()
        merged = [ivs[0]]
        for lo, hi in ivs[1:]:
            if lo <= merged[-1][1] + 1e-4:
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        lines[key] = merged
    return lines


def intersect(a_ivs, b_ivs):
    return [[max(a[0], b[0]), min(a[1], b[1])] for a in a_ivs for b in b_ivs
            if min(a[1], b[1]) - max(a[0], b[0]) > 1e-4]


def full_height_occluders(scene):
    out = []
    for obj in scene['objects']:
        name = obj['name']
        if obj['type'] != 'MESH' or obj['hide_render']:
            continue
        if name != 'WALL_JOINED_SHELL' and not name.startswith('OBSTACLE_SCREEN'):
            continue
        zs = [v[2] for v in obj['vertices_world_m']]
        if min(zs) > 1e-6 or max(zs) < max(SLICE_HEIGHTS_M):
            continue
        per_height = [axis_intervals(slice_object(obj, z)) for z in SLICE_HEIGHTS_M]
        for key in sorted(per_height[0]):
            ivs = per_height[0][key]
            for lines in per_height[1:]:
                ivs = intersect(ivs, lines.get(key, []))
            for lo, hi in ivs:
                lo, hi = round(lo, 6), round(hi, 6)
                a, b = ([key[1], lo], [key[1], hi]) if key[0] == 'x' else ([lo, key[1]], [hi, key[1]])
                out.append({'occluder_id': f'{name}:{key[0]}={key[1]}:{lo:g}..{hi:g}', 'a': a, 'b': b})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('codex_dir')
    ap.add_argument('cameras')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    d = Path(args.codex_dir)
    scene = json.loads((d / 'scene_export.json').read_text())
    geo = json.loads((d / 'geometry_2d.json').read_text())
    catalog = json.loads(Path(args.cameras).read_text())
    segments = [{'segment_id': s['segment_id'], 'collider': c['object_ref'],
                 'a': [round(v, 6) for v in s['a']], 'b': [round(v, 6) for v in s['b']]}
                for c in geo['colliders'] for s in c['segments']]
    floors = []
    for name, bounds in geo['floor']:
        floors.append({'floor_id': name, 'x_m': [round(v, 4) for v in bounds[0]],
                       'y_m': [round(v, 4) for v in bounds[1]], 'top_z_m': round(bounds[2][1], 4)})
    cams = []
    for c in sorted(catalog['cameras'], key=lambda c: c['camera_id']):
        cams.append({k: c[k] for k in ('camera_id', 'calibration_sha256', 'camera_model', 'convention',
                                        'camera_to_world', 'fx', 'fy', 'cx', 'cy', 'width', 'height',
                                        'clip_start', 'clip_end')}
                    | {'hfov_deg': round(2 * math.degrees(math.atan(c['width'] / 2 / c['fx'])), 4)})
    doc = {
        'schema': 'amidst.r004-scene-geometry-2d.v1',
        'status': 'DESIGN_FEASIBILITY_ONLY_NOT_RUNTIME_AUTHORITY',
        'decision_ref': 'D207 (issue #93); Codex #516 feasibility comment 6761965932',
        'must_not_enter': ['RUNTIME_INFERENCE', 'CANDIDATE_RANKING', 'DETECTION_INDEX', 'RECONSTRUCTION', 'SAFE_BUNDLE'],
        'provenance': {
            'source_blend': {'path': 'local/data/r004-build-v2-20261021/controlled_scene_v1_s001_r004.blend',
                             'sha256': scene['sha256'], 'storage': 'LOCAL'},
            'camera_catalog': {'path': 'local/data/r004-build-v2-20261021/safe_static/cameras.json',
                               'sha256': sha256(args.cameras), 'storage': 'LOCAL'},
            'codex_feasibility': {'path': 'local/evidence/codex-516-feasibility-20261110/',
                                  'artifact_manifest_sha256': sha256(d / 'ARTIFACT_MANIFEST.json'),
                                  'scene_export_sha256': sha256(d / 'scene_export.json'),
                                  'geometry_2d_sha256': sha256(d / 'geometry_2d.json'),
                                  'storage': 'LOCAL (copied from Codex 暫存目錄, SHA-256 checked 28/28)',
                                  'issue_comment': 'https://github.com/Polalalabear/amidst/issues/516#issuecomment-6761965932'},
            'builder': 'scripts/design/build_r004_scene_geometry_2d.py',
            'gt_read': False, 'rgb_read': False,
        },
        'units': 'meters; world frame of the r004 static scene (Blender, Z up)',
        'body_height_band_m': geo['body_height_band_m'],
        'clearance_method': geo['method'],
        'clearance_segments': segments,
        'occluder_method': ('XY intervals solid at every slice height ' + ', '.join(f'{z:g}' for z in SLICE_HEIGHTS_M)
                            + ' m (one per shell topology interval up to the 3.2 m top; every camera is at '
                              'z <= 3.0 m and every body point at z <= 1.85 m, so a 2D sight line crossing one '
                              'is blocked in 3D). Vehicle, door lintels and the x=15 parapet are not occluders.'),
        'occluders_full_height': full_height_occluders(scene),
        'door_openings': geo['door_openings'],
        'floors': floors,
        'cameras': cams,
        'render_camera_sets': RENDER_CAMERA_SETS,
        'render_camera_sets_basis': 'scenario card v1 section 2-3 and v2 section 1 (A4 renders CAM_ENTRY for lookup only; still rendered, so it counts for spawn/exit visibility)',
    }
    Path(args.out).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n')
    print(f"segments {len(segments)} occluders {len(doc['occluders_full_height'])} cameras {len(cams)}")


if __name__ == '__main__':
    main()
