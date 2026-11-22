"""F2 / D346 pre-release check: do the static occluders (R004_SCENE_GEOMETRY_2D_V1.json) line up with the walls in real frames?

For each chosen camera, every visible occluder face is sampled every 5 cm, its wall-floor line (z = 0) is projected into the rendered
RGB frame with the catalog calibration, and the strongest image edge is searched within +-SEARCH_PX along the line normal. The offset
of that edge from the projected line is the alignment error (pixels; metres = px * depth / fx). The wall-clipped FOV far boundary
(camera_projection.visibility_polygon) is drawn too. Inputs are static geometry, calibration and source RGB only (no GT, no depth).

    PYTHONPATH=src .venv/bin/python scripts/f2_validate_wall_projection.py --frames <run dir with CAM_*/000000.png> --out local/evidence/...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from amidst.q1q5 import camera_projection as cp

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / 'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json'
SEARCH_PX = 20
STEP_M = 0.05
MIN_GRAD = 4.0    # edge strength |d grey| + 2|d (G-R)| per pixel; weaker peaks mean no visible edge and are not scored
# The r004 walls are warm grey (R > G) and the floor green-grey (G > R): the junction is a hue step more than a brightness step.


def project(entry, x, y, z):
    m = entry['camera_to_world']
    d = (x - m[0][3], y - m[1][3], z - m[2][3])
    c = [m[0][j] * d[0] + m[1][j] * d[1] + m[2][j] * d[2] for j in range(3)]
    depth = -c[2]
    if depth <= 0.05:
        return None
    return entry['width'] / 2 + entry['fx'] * c[0] / depth, entry['height'] / 2 - entry['fy'] * c[1] / depth, depth


def visible_samples(entry, walls):
    (ox, oy, _), _, _ = cp.pose_of(entry)
    out = []
    for k, (ax, ay, bx, by) in enumerate(walls):
        n = max(1, int(math.hypot(bx - ax, by - ay) / STEP_M))
        for i in range(n + 1):
            x, y = ax + (bx - ax) * i / n, ay + (by - ay) * i / n
            d = math.hypot(x - ox, y - oy)
            hit = cp.ray_hit(ox, oy, math.atan2(y - oy, x - ox), walls)
            if hit < d - 0.02:            # another face is in front
                continue
            p = project(entry, x, y, 0.0)
            if p and 2 <= p[0] <= entry['width'] - 3 and 2 <= p[1] <= entry['height'] - 3:
                q = project(entry, x + (bx - ax) / n * .5, y + (by - ay) / n * .5, 0.0)
                out.append({'wall': k, 'uv': p[:2], 'depth': p[2], 'dir': (q[0] - p[0], q[1] - p[1]) if q else (1.0, 0.0)})
    return out


def edge_offset(sig, u, v, du, dv):
    norm = math.hypot(du, dv) or 1.0
    nx, ny = -dv / norm, du / norm
    h, w = sig.shape[:2]
    prof = []
    for s in range(-SEARCH_PX - 1, SEARCH_PX + 2):
        x, y = int(round(u + nx * s)), int(round(v + ny * s))
        prof.append(sig[y, x] if 0 <= x < w and 0 <= y < h else (np.nan, np.nan))
    prof = np.array(prof, dtype=float)
    d = np.abs(prof[2:] - prof[:-2]) / 2
    grad = d[:, 0] + 2 * d[:, 1]
    if np.all(np.isnan(grad)):
        return None, 0.0, None
    i = int(np.nanargmax(grad))
    # secondary: nearest local peak above MIN_GRAD (a stronger parallel edge, e.g. a door jamb, can win the global search)
    peaks = [j for j in range(1, len(grad) - 1) if grad[j] >= MIN_GRAD and grad[j] >= grad[j - 1] and grad[j] >= grad[j + 1]]
    near = min((abs(j - SEARCH_PX) for j in peaks), default=None)
    return i - SEARCH_PX, float(grad[i]), near


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frames', type=Path, required=True)
    ap.add_argument('--frame', default='000000.png')
    ap.add_argument('--cameras', default='CAM_W1,CAM_ENTRY,CAM_BRANCH,CAM_WIDE')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    geom = json.loads(GEOM.read_text())
    walls = cp.walls_of(geom)
    cams = {c['camera_id']: c for c in geom['cameras']}
    a.out.mkdir(parents=True, exist_ok=True)
    report = {'schema': 'f2.wall-projection-check.v1', 'geometry_sha256': hashlib.sha256(GEOM.read_bytes()).hexdigest(),
              'frame': a.frame, 'search_px': SEARCH_PX, 'min_grad': MIN_GRAD, 'cameras': {}}
    for cid in a.cameras.split(','):
        e = cams[cid]
        src = a.frames / cid / a.frame
        img = Image.open(src).convert('RGB')
        rgb = np.asarray(img, dtype=float)
        sig = np.stack([rgb.mean(axis=2), rgb[..., 1] - rgb[..., 0]], axis=2)
        samples = visible_samples(e, walls)
        errs_px, errs_m, near_px, weak = [], [], [], 0
        draw = ImageDraw.Draw(img)
        for s in samples:
            off, g, near = edge_offset(sig, *s['uv'], *s['dir'])
            if near is not None:
                near_px.append(near)
            ok = off is not None and g >= MIN_GRAD
            if ok:
                errs_px.append(abs(off)); errs_m.append(abs(off) * s['depth'] / e['fx'])
            else:
                weak += 1
            u, v = s['uv']
            draw.ellipse([u - 1.5, v - 1.5, u + 1.5, v + 1.5], fill=(0, 200, 0) if ok and abs(off) <= 3 else (255, 140, 0) if ok else (40, 90, 255))
        for x, y in cp.visibility_polygon(e, walls):
            p = project(e, x, y, 0.0)
            if p:
                draw.rectangle([p[0] - 2, p[1] - 2, p[0] + 2, p[1] + 2], outline=(255, 0, 255))
        out_img = a.out / f'wallcheck_{cid}.png'
        img.save(out_img)
        ep = np.array(errs_px) if errs_px else np.array([np.nan])
        report['cameras'][cid] = {
            'frame_sha256': hashlib.sha256(src.read_bytes()).hexdigest(), 'overlay': out_img.name,
            'overlay_sha256': hashlib.sha256(out_img.read_bytes()).hexdigest(),
            'samples': len(samples), 'scored': len(errs_px), 'no_edge': weak,
            'median_px': round(float(np.nanmedian(ep)), 2), 'p90_px': round(float(np.nanpercentile(ep, 90)), 2),
            'within_3px': round(float(np.mean(ep <= 3)), 3) if errs_px else None,
            'median_m': round(float(np.median(errs_m)), 3) if errs_m else None,
            'p90_m': round(float(np.percentile(errs_m, 90)), 3) if errs_m else None,
            'nearest_edge_median_px': round(float(np.median(near_px)), 2) if near_px else None,
            'nearest_edge_p90_px': round(float(np.percentile(near_px, 90)), 2) if near_px else None,
            'nearest_edge_within_3px': round(float(np.mean(np.array(near_px) <= 3)), 3) if near_px else None}
    (a.out / 'wallcheck.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report['cameras'], indent=1))


if __name__ == '__main__':
    main()
