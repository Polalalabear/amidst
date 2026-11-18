// Angles are degrees: yaw clockwise from world +Y, pitch positive upward. No DOM or GT.
export const DEFAULT_VIEW_CONFIG = Object.freeze({
  mouse_sens_deg_per_px: 0.15, pitch_min_deg: -15, pitch_max_deg: 50, max_delta_px: 200,
});
export function applyMouseDelta(view, dx, dy, overrides = {}) {
  const cfg = {...DEFAULT_VIEW_CONFIG, ...overrides};
  const clamp = v => Math.max(-cfg.max_delta_px, Math.min(cfg.max_delta_px, v));
  return {...view,
    view_yaw: ((view.view_yaw + clamp(dx) * cfg.mouse_sens_deg_per_px) % 360 + 360) % 360,
    view_pitch: Math.max(cfg.pitch_min_deg, Math.min(cfg.pitch_max_deg, view.view_pitch - clamp(dy) * cfg.mouse_sens_deg_per_px)),
  };
}
export function moveVector(keys, view_yaw = 0, speed = 1) {
  const forward = Number(!!keys.w) - Number(!!keys.s), right = Number(!!keys.d) - Number(!!keys.a);
  const n = Math.hypot(forward, right);
  if (!n) return {vx: 0, vy: 0};
  const yaw = view_yaw * Math.PI / 180;
  return {vx: (forward * Math.sin(yaw) + right * Math.cos(yaw)) / n * speed,
    vy: (forward * Math.cos(yaw) - right * Math.sin(yaw)) / n * speed};
}
