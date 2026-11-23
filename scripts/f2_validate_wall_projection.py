"""F2 / D346 wall-projection gate: do the static occluders (R004_SCENE_GEOMETRY_2D_V1.json) line up with the walls in real frames?

For each camera, every visible occluder face is sampled every 5 cm, its wall-floor line (z = 0) is projected into source RGB frames
with the catalog calibration (scaled to the frame size), and the strongest image edge is searched within +-20 px (960-px equivalent)
along the line normal. Three numbers per camera, pooled over the given frames:

- standard (strict): offset of the strongest edge in the search window from the projected line;
- nearest edge: offset of the nearest local edge peak above the strength floor (a stronger parallel edge, e.g. a door jamb,
  can win the strict search);
- shifted control: the same strict measurement with the camera moved CONTROL_SHIFT_M sideways. A measure that cannot tell a
  0.3 m error from the real geometry proves nothing, so the gate requires the control to be clearly worse.

Gate (fixed in docs/operations/F2_LIVE_COVERAGE_20261122.md before the E3 run, after the r004 check in PR #664):
VALIDATED when scored samples >= 30, strict median <= 2 px and >= 80 % within 3 px (960-px equivalent), and the control median is
>= 3 px and >= 2x the strict median. Otherwise NOT_VALIDATED: scene_context does not clip that camera and marks it
SCENE_CONTEXT_INCOMPLETE. Inputs are static geometry, calibration and source RGB only (no GT, no depth).

    PYTHONPATH=src .venv/bin/python scripts/f2_validate_wall_projection.py --set r004=local/data/.../A4-1:000000.png,000100.png \
        --set live=local/evidence/e3-652-20261122/rgb/E3-A1:00000.png,00100.png --out local/evidence/f2-coverage-20261122/gate
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
REF_W = 960
SEARCH_PX = 20            # 960-px equivalent
STEP_M = 0.05
MIN_GRAD = 4.0            # |d grey| + 2|d (G-R)| per pixel; walls are warm grey (R > G), floors green-grey (G > R)
CONTROL_SHIFT_M = 0.3
GATE = {'min_samples': 30, 'max_median_px': 2.0, 'min_within_3px': 0.8, 'min_control_median_px': 3.0, 'control_ratio': 2.0}


def scaled(entry, w, h):
    s = w / entry['width']
    if abs(h / entry['height'] - s) > 1e-3:
        raise ValueError(f'ASPECT_MISMATCH {entry["camera_id"]} {w}x{h}')
    return {**entry, 'width': w, 'height': h, 'fx': entry['fx'] * s, 'fy': entry['fy'] * s}


def shifted(entry, metres):
    """Camera moved ``metres`` to its right (perpendicular to the viewing yaw), orientation unchanged: the control geometry."""
    (_, _, _), yaw, _ = cp.pose_of(entry)
    m = [row[:] for row in entry['camera_to_world']]
    m[0][3] += metres * math.sin(yaw)
    m[1][3] -= metres * math.cos(yaw)
    return {**entry, 'camera_to_world': m}


def project(entry, x, y, z):
    m = entry['camera_to_world']
    d = (x - m[0][3], y - m[1][3], z - m[2][3])
    c = [m[0][j] * d[0] + m[1][j] * d[1] + m[2][j] * d[2] for j in range(3)]
    depth = -c[2]
    if depth <= 0.05:
        return None
    return entry['width'] / 2 + entry['fx'] * c[0] / depth, entry['height'] / 2 - entry['fy'] * c[1] / depth, depth


VEHICLE_TOP_M = 1.5      # R004_ENV_* vehicles: not occluders for people, but they hide the wall foot line behind them


def vehicles_of(geom):
    return [(s['a'][0], s['a'][1], s['b'][0], s['b'][1]) for s in geom['clearance_segments'] if str(s['collider']).startswith('R004_ENV_')]


def hidden_by_vehicle(ox, oy, oz, x, y, vehicles):
    """The floor point (x, y, 0) is hidden when the sight line passes a vehicle edge below the vehicle top."""
    d = math.hypot(x - ox, y - oy)
    dx, dy = (x - ox) / d, (y - oy) / d
    for ax, ay, bx, by in vehicles:
        ex, ey = bx - ax, by - ay
        den = dx * ey - dy * ex
        if abs(den) < 1e-12:
            continue
        t = ((ax - ox) * ey - (ay - oy) * ex) / den
        u = ((ax - ox) * dy - (ay - oy) * dx) / den
        if 0 < t < d and 0 <= u <= 1 and oz * (1 - t / d) < VEHICLE_TOP_M:
            return True
    return False


def visible_samples(entry, walls, vehicles=()):
    (ox, oy, oz), _, _ = cp.pose_of(entry)
    out = []
    for ax, ay, bx, by in walls:
        n = max(1, int(math.hypot(bx - ax, by - ay) / STEP_M))
        for i in range(n + 1):
            x, y = ax + (bx - ax) * i / n, ay + (by - ay) * i / n
            if cp.ray_hit(ox, oy, math.atan2(y - oy, x - ox), walls) < math.hypot(x - ox, y - oy) - 0.02:
                continue                       # another face is in front
            if vehicles and hidden_by_vehicle(ox, oy, oz, x, y, vehicles):
                continue                       # wall foot hidden behind a vehicle (measurement only; vehicles never clip coverage)
            p = project(entry, x, y, 0.0)
            if p and 2 <= p[0] <= entry['width'] - 3 and 2 <= p[1] <= entry['height'] - 3:
                q = project(entry, x + (bx - ax) / n * .5, y + (by - ay) / n * .5, 0.0)
                out.append({'uv': p[:2], 'depth': p[2], 'dir': (q[0] - p[0], q[1] - p[1]) if q else (1.0, 0.0)})
    return out


def edge_offsets(sig, u, v, du, dv, search):
    norm = math.hypot(du, dv) or 1.0
    nx, ny = -dv / norm, du / norm
    h, w = sig.shape[:2]
    prof = []
    for s in range(-search - 1, search + 2):
        x, y = int(round(u + nx * s)), int(round(v + ny * s))
        prof.append(sig[y, x] if 0 <= x < w and 0 <= y < h else (np.nan, np.nan))
    prof = np.array(prof, dtype=float)
    d = np.abs(prof[2:] - prof[:-2]) / 2
    grad = d[:, 0] + 2 * d[:, 1]
    if np.all(np.isnan(grad)):
        return None, None
    i = int(np.nanargmax(grad))
    if grad[i] < MIN_GRAD:
        return None, None
    peaks = [j for j in range(1, len(grad) - 1) if grad[j] >= MIN_GRAD and grad[j] >= grad[j - 1] and grad[j] >= grad[j + 1]]
    return abs(i - search), min((abs(j - search) for j in peaks), default=abs(i - search))


def measure(entry, walls, frames, draw_to=None, vehicles=()):
    strict, near, metres = [], [], []
    for k, path in enumerate(frames):
        img = Image.open(path).convert('RGB')
        e = scaled(entry, *img.size)
        scale = img.size[0] / REF_W
        rgb = np.asarray(img, dtype=float)
        sig = np.stack([rgb.mean(axis=2), rgb[..., 1] - rgb[..., 0]], axis=2)
        search = max(3, round(SEARCH_PX * scale))
        draw = ImageDraw.Draw(img) if draw_to and k == 0 else None
        for s in visible_samples(e, walls, vehicles):
            off, nr = edge_offsets(sig, *s['uv'], *s['dir'], search)
            if off is not None:
                strict.append(off / scale)
                near.append(nr / scale)
                metres.append(off * s['depth'] / e['fx'])
            if draw:
                u, v, r = *s['uv'], max(1.0, 1.5 * scale)
                ok = off is not None and off / scale <= 3
                draw.ellipse([u - r, v - r, u + r, v + r], fill=(0, 200, 0) if ok else (255, 140, 0) if off is not None else (40, 90, 255))
        if draw:
            img.save(draw_to)
    return strict, near, metres


def stats_native(xs, scale):
    """The same offsets in the frame's own pixels (320-px LIVE frames: 1 px = 3 px at 960)."""
    if not xs:
        return {'n': 0, 'median_px': None, 'within_1px': None, 'within_2px': None}
    a = np.array(xs) * scale
    return {'n': len(xs), 'median_px': round(float(np.median(a)), 2), 'within_1px': round(float(np.mean(a <= 1 + 1e-9)), 3),
            'within_2px': round(float(np.mean(a <= 2 + 1e-9)), 3)}


def stats(xs):
    if not xs:
        return {'n': 0, 'median_px': None, 'p90_px': None, 'within_3px': None}
    a = np.array(xs)
    return {'n': len(xs), 'median_px': round(float(np.median(a)), 2), 'p90_px': round(float(np.percentile(a, 90)), 2),
            'within_3px': round(float(np.mean(a <= 3)), 3)}


def gate(std, ctrl):
    if std['n'] < GATE['min_samples']:
        return 'NOT_VALIDATED', 'TOO_FEW_SAMPLES'
    if std['median_px'] > GATE['max_median_px'] or std['within_3px'] < GATE['min_within_3px']:
        return 'NOT_VALIDATED', 'MISALIGNED'
    if ctrl['n'] == 0 or ctrl['median_px'] < GATE['min_control_median_px'] or ctrl['median_px'] < GATE['control_ratio'] * std['median_px']:
        return 'NOT_VALIDATED', 'CONTROL_NOT_DISCRIMINATING'
    return 'VALIDATED', None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', action='append', required=True, metavar='NAME=DIR:frame,frame',
                    help='frames DIR/<camera>/<frame> for every camera of the geometry file')
    ap.add_argument('--cameras', default=None)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    geom = json.loads(GEOM.read_text())
    walls, vehicles = cp.walls_of(geom), vehicles_of(geom)
    cams = {c['camera_id']: c for c in geom['cameras']}
    ids = a.cameras.split(',') if a.cameras else sorted(cams)
    a.out.mkdir(parents=True, exist_ok=True)
    report = {'schema': 'f2.wall-projection-gate.v1', 'geometry_sha256': hashlib.sha256(GEOM.read_bytes()).hexdigest(),
              'search_px_960': SEARCH_PX, 'min_grad': MIN_GRAD, 'control_shift_m': CONTROL_SHIFT_M, 'gate': GATE, 'sets': {}}
    for spec in a.set:
        name, rest = spec.split('=', 1)
        root, names = rest.rsplit(':', 1)
        root = Path(root)
        out = {}
        for cid in ids:
            frames = [root / cid / f for f in names.split(',') if (root / cid / f).is_file()]
            if not frames:
                out[cid] = {'verdict': 'NOT_VALIDATED', 'reason': 'NO_FRAMES'}
                continue
            overlay = a.out / f'{name}_{cid}.png'
            s, nr, m = measure(cams[cid], walls, frames, overlay, vehicles)
            c, _, _ = measure(shifted(cams[cid], CONTROL_SHIFT_M), walls, frames, vehicles=vehicles)
            st, ct = stats(s), stats(c)
            verdict, reason = gate(st, ct)
            out[cid] = {'verdict': verdict, 'reason': reason, 'frames': [str(f.name) for f in frames],
                        'frame_sha256': [hashlib.sha256(f.read_bytes()).hexdigest() for f in frames],
                        'frame_width': Image.open(frames[0]).size[0],
                        'standard': st, 'nearest_edge': stats(nr), 'control_shift': ct,
                        'standard_native': stats_native(s, Image.open(frames[0]).size[0] / REF_W),
                        'control_native': stats_native(c, Image.open(frames[0]).size[0] / REF_W),
                        'standard_median_m': round(float(np.median(m)), 3) if m else None,
                        'overlay': overlay.name, 'overlay_sha256': hashlib.sha256(overlay.read_bytes()).hexdigest()}
        report['sets'][name] = out
    (a.out / 'gate.json').write_text(json.dumps(report, indent=1, ensure_ascii=False) + '\n')
    for name, out in report['sets'].items():
        for cid, r in out.items():
            st, ct, nr = r.get('standard', {}), r.get('control_shift', {}), r.get('nearest_edge', {})
            print(f"{name:5} {cid:14} {r['verdict']:14} {str(r['reason']):28} std n={st.get('n')} med={st.get('median_px')} "
                  f"p90={st.get('p90_px')} w3={st.get('within_3px')} | near w3={nr.get('within_3px')} | ctrl med={ct.get('median_px')} "
                  f"w3={ct.get('within_3px')}")


if __name__ == '__main__':
    main()
