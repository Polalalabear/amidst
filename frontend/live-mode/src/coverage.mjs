// F2 (#656): wall-clipped camera coverage from static geometry + calibration only (no people, no GT).
// Pure module (no three.js) so it runs under node --test; the same algorithm is in
// src/amidst/q1q5/camera_projection.py (visibility_polygon) and both are checked against each other in tests.
//
// A ground point (x, y) is covered by a camera when a body point at height COVER_Z projects inside the image
// (pinhole, catalog intrinsics/extrinsics) and the 2D sight line camera->point crosses no wall segment.
// Rays are swept over the horizontal FOV every STEP_DEG; along each ray we march MARCH_M until the first wall.
// The polygon is the ring of the nearest and farthest covered point of every ray (camera blind spots under
// the lens are excluded). Walls = occluders_full_height (D346); vehicles (R004_ENV_*, 1.5 m) are not occluders.

export const COVER_Z = 0.9;
export const STEP_DEG = 1;
export const MARCH_M = 0.25;
export const MAX_RANGE_M = 14;
export const BLIND_CELL_M = 0.5;

// D346: only occluders_full_height (solid at every slice height up to 3.2 m) and door_openings may enter
// inference; walls are the occluders (doors are already gaps between them, vehicles are not occluders).
export function wallsOf(geometry) {
  return geometry.occluders_full_height.map(s => [s.a[0], s.a[1], s.b[0], s.b[1]]);
}

export function pose(spec) {
  const M = spec.camera_to_world, pos = [M[0][3], M[1][3], M[2][3]];
  const fwd = [-M[0][2], -M[1][2], -M[2][2]];
  return {pos, yaw: Math.atan2(fwd[1], fwd[0]), hfov: 2 * Math.atan(spec.width / 2 / spec.fx)};
}

export function seesPoint(spec, x, y, z) {
  const M = spec.camera_to_world, d = [x - M[0][3], y - M[1][3], z - M[2][3]];
  const c = [0, 1, 2].map(j => M[0][j] * d[0] + M[1][j] * d[1] + M[2][j] * d[2]);
  const depth = -c[2];
  if (depth <= (spec.clip_start ?? 0.05) || depth > (spec.clip_end ?? 100)) return false;
  const u = spec.width / 2 + spec.fx * c[0] / depth, v = spec.height / 2 - spec.fy * c[1] / depth;
  return u >= 0 && u <= spec.width && v >= 0 && v <= spec.height;
}

// distance along the ray (ox, oy, angle) to the first wall, or Infinity
export function rayHit(ox, oy, angle, walls) {
  const dx = Math.cos(angle), dy = Math.sin(angle);
  let best = Infinity;
  for (const [ax, ay, bx, by] of walls) {
    const ex = bx - ax, ey = by - ay, den = dx * ey - dy * ex;
    if (Math.abs(den) < 1e-12) continue;
    const t = ((ax - ox) * ey - (ay - oy) * ex) / den, s = ((ax - ox) * dy - (ay - oy) * dx) / den;
    if (t > 1e-9 && s >= -1e-9 && s <= 1 + 1e-9 && t < best) best = t;
  }
  return best;
}

export function visibilityPolygon(spec, walls, opts = {}) {
  const step = (opts.stepDeg ?? STEP_DEG) * Math.PI / 180, march = opts.march ?? MARCH_M, maxR = opts.maxRange ?? MAX_RANGE_M;
  const z = opts.z ?? COVER_Z, {pos, yaw, hfov} = pose(spec);
  const near = [], far = [], n = Math.max(1, Math.round(hfov / step));
  for (let i = 0; i <= n; i++) {
    const a = yaw - hfov / 2 + (hfov * i) / n, wall = Math.min(maxR, rayHit(pos[0], pos[1], a, walls));
    let first = null, last = null;
    for (let r = march; r < wall - 1e-9; r += march) {
      const x = pos[0] + r * Math.cos(a), y = pos[1] + r * Math.sin(a);
      if (seesPoint(spec, x, y, z)) { if (!first) first = [x, y]; last = [x, y]; }
    }
    if (first) { near.push(first); far.push(last); }
  }
  return {camera_id: spec.camera_id, polygon: far.length ? [...far, ...near.reverse()] : [], rays: far.length};
}

export function pointInPolygon(x, y, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export function polygonArea(poly) {
  let s = 0;
  for (let i = 0; i < poly.length; i++) { const [x0, y0] = poly[i], [x1, y1] = poly[(i + 1) % poly.length]; s += x0 * y1 - x1 * y0; }
  return Math.abs(s) / 2;
}

// floor cells (centres) that no camera covers: the blind zones drawn on the operator minimap
export function blindCells(floors, polygons, cell = BLIND_CELL_M) {
  const out = [];
  for (const f of floors) {
    for (let x = f.x_m[0] + cell / 2; x < f.x_m[1]; x += cell) {
      for (let y = f.y_m[0] + cell / 2; y < f.y_m[1]; y += cell) {
        if (!polygons.some(p => p.length >= 3 && pointInPolygon(x, y, p))) out.push([x, y]);
      }
    }
  }
  return out;
}

export function coverageOf(geometry, cameraIds = null) {
  const walls = wallsOf(geometry), ids = new Set(cameraIds || geometry.cameras.map(c => c.camera_id));
  const cams = geometry.cameras.filter(c => ids.has(c.camera_id)).map(c => ({...visibilityPolygon(c, walls), pose: pose(c)}));
  return {cameras: cams, blind: blindCells(geometry.floors, cams.map(c => c.polygon))};
}
