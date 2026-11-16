// What may cross from the operator window to the system window (BroadcastChannel) and to the
// inference backend. D210: the system side must never receive the operator's person id or
// coordinates; it only gets camera pixels plus results the backend derived from those pixels.

const FRAME_KEYS = new Set(['cam', 'jpeg']);
const DET_KEYS = new Set(['bbox', 'score', 'color', 'red_ratio', 'blue_ratio', 'est_xy']);
const TRACK_KEYS = new Set(['state', 'active_cam', 'seen_cams', 'est_xy', 'events', 'lost_ticks',
  // image adjudication (src/amidst/live_mode/advisor.py): who decided, and the advisor's own status. Backend outputs only.
  'decision_source', 'fallback_reason', 'advisor']);
const ADVISOR_KEYS = new Set(['state', 'pending_ms', 'last']);
const ADVISOR_LAST_KEYS = new Set(['kind', 'cam', 'choice', 'reason', 'latency_ms', 'applied', 'model', 'source', 'fallback_reason']);
const EVENT_KEYS = new Set(['tick', 'type', 'cam', 'detail']);
const TOP_KEYS = new Set(['type', 'tick', 't_capture_ms', 'frames', 'dets', 'tracking', 'timing_ms']);

export function buildSystemMessage({ tick, tCaptureMs, frames, result }) {
  // Deliberately takes no operator/world state: only capture clock, pixels, backend result.
  const dets = {};
  for (const [cam, list] of Object.entries(result.dets || {})) {
    dets[cam] = list.map((d) => pick(d, DET_KEYS));
  }
  const tr = result.tracking || {};
  const tracking = pick(tr, TRACK_KEYS);
  if (tracking.events) tracking.events = tracking.events.map((e) => pick(e, EVENT_KEYS));
  if (tracking.advisor) {
    tracking.advisor = pick(tracking.advisor, ADVISOR_KEYS);
    if (tracking.advisor.last) tracking.advisor.last = pick(tracking.advisor.last, ADVISOR_LAST_KEYS);
  }
  return {
    type: 'frame-batch', tick, t_capture_ms: tCaptureMs,
    frames: frames.map((f) => pick(f, FRAME_KEYS)),
    dets, tracking, timing_ms: result.timing_ms || {},
  };
}

function pick(o, keys) {
  const r = {};
  for (const k of Object.keys(o)) if (keys.has(k)) r[k] = o[k];
  return r;
}

// Strict validator used by the system window on receive and by tests: any key outside the whitelist
// (e.g. operator_xy, person_id, gt) is a violation.
export function validateSystemMessage(msg) {
  const bad = [];
  const chk = (obj, keys, path) => {
    for (const k of Object.keys(obj)) if (!keys.has(k)) bad.push(`${path}.${k}`);
  };
  chk(msg, TOP_KEYS, 'msg');
  for (const [i, f] of (msg.frames || []).entries()) chk(f, FRAME_KEYS, `frames[${i}]`);
  for (const [cam, list] of Object.entries(msg.dets || {})) {
    for (const [i, d] of list.entries()) chk(d, DET_KEYS, `dets.${cam}[${i}]`);
  }
  if (msg.tracking) {
    chk(msg.tracking, TRACK_KEYS, 'tracking');
    for (const [i, e] of (msg.tracking.events || []).entries()) chk(e, EVENT_KEYS, `events[${i}]`);
    if (msg.tracking.advisor) {
      chk(msg.tracking.advisor, ADVISOR_KEYS, 'tracking.advisor');
      if (msg.tracking.advisor.last) chk(msg.tracking.advisor.last, ADVISOR_LAST_KEYS, 'tracking.advisor.last');
    }
  }
  return bad;
}

// request header sent to the backend: tick/clock/camera ids only
export function buildInferHeader({ tick, tCaptureMs, frames }) {
  return { tick, t_capture_ms: tCaptureMs, frames: frames.map((f) => ({ cam: f.cam, bytes: f.jpeg.byteLength })) };
}
