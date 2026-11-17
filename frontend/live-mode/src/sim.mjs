// Operator-side simulation: WASD movement with wall clearance, scripted distractors (scenario v2.3).
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

// keys: {w,a,s,d,shift}. Camera-relative-free: W=+Y(north) A=-X S=-Y D=+X in the world frame (a
// third-person view is fixed behind the person looking +Y; documented simplification).
export function stepPlayer(p, keys, dt, segments) {
  let vx = 0, vy = 0;
  if (keys.w) vy += 1; if (keys.s) vy -= 1; if (keys.a) vx -= 1; if (keys.d) vx += 1;
  const n = Math.hypot(vx, vy);
  p.moving = n > 0; p.running = !!keys.shift && p.moving;
  if (!p.moving) return p;
  const v = p.running ? RUN : WALK;
  vx = vx / n * v * dt; vy = vy / n * v * dt;
  if (!blocked(p.x + vx, p.y + vy, segments)) { p.x += vx; p.y += vy; }
  else if (!blocked(p.x + vx, p.y, segments)) p.x += vx;
  else if (!blocked(p.x, p.y + vy, segments)) p.y += vy;
  p.heading = Math.atan2(vy, vx);
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
