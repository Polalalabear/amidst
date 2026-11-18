// Operator-side simulation: view-relative WASD, wall clearance and scenario v2.3 scripts.
import {moveVector} from './view.mjs';
export const WALK = 1.2, RUN = 2.5; // m/s, matching the N6 clip speeds

export function segDist(px, py, s) {
  const [ax, ay] = s.a, [bx, by] = s.b;
  const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy || 1e-9;
  let t = ((px - ax) * dx + (py - ay) * dy) / l2; t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}
export function blocked(x, y, segments, r = 0.25) {
  for (const s of segments) if (segDist(x, y, s) < r) return true;
  return false;
}

// keys: {w,a,s,d,shift,view_yaw?}. Missing yaw preserves legacy W=+Y, D=+X.
export const DEFAULT_CROWD_CONFIG = Object.freeze({r_person: 0.30, r_wall: 0.25, wait_max_mutual_s: 3, eps_m: 0.02});

// All candidates use the same step-start position; no entity is pushed by another.
export function playerCandidates(p, keys, dt, segments, cfg = DEFAULT_CROWD_CONFIG) {
  const {vx, vy} = moveVector(keys, keys.view_yaw ?? 0, (keys.shift ? RUN : WALK) * dt);
  const result = [], seen = new Set();
  for (const [dx, dy] of [[vx, vy], [vx, 0], [0, vy], [0, 0]]) {
    const x = p.x + dx, y = p.y + dy, key = `${x},${y}`;
    if (seen.has(key) || ((dx || dy) && blocked(x, y, segments, cfg.r_wall))) continue;
    seen.add(key); result.push({x, y, heading: dx || dy ? Math.atan2(dy, dx) : (p.heading || 0), moving: !!(dx || dy), running: !!keys.shift && !!(dx || dy)});
  }
  return result;
}

export function stepPlayer(p, keys, dt, segments, people = [], cfg = DEFAULT_CROWD_CONFIG) {
  const choice = playerCandidates(p, keys, dt, segments, cfg).find(q => people.every(other => {
    if (other.present === false) return true;
    const next = Math.hypot(q.x-other.x, q.y-other.y), current = Math.hypot(p.x-other.x, p.y-other.y);
    return !(next < 2*cfg.r_person && next < current-1e-12);
  }));
  if (choice) Object.assign(p, choice);
  return p;
}

// scripted actor: linear interpolation of waypoints [{t_us, xy}], looping at duration
export function scriptedPose(actor, tSec, durationSec) {
  const t = tSec % durationSec;
  const w = actor.waypoints;
  if (t < w[0].t_us / 1e6 || t > w[w.length - 1].t_us / 1e6) return null; // not present
  for (let i = 0; i < w.length - 1; i++) {
    const a = w[i], b = w[i + 1], ta = a.t_us / 1e6, tb = b.t_us / 1e6;
    if (t >= ta && t <= tb) {
      const k = tb > ta ? (t - ta) / (tb - ta) : 0;
      const x = a.xy[0] + (b.xy[0] - a.xy[0]) * k, y = a.xy[1] + (b.xy[1] - a.xy[1]) * k;
      return { x, y, heading: Math.atan2(b.xy[1] - a.xy[1], b.xy[0] - a.xy[0]) };
    }
  }
  return null;
}
