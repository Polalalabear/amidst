// What may cross from the operator window to the system window (BroadcastChannel) and to the
// inference backend. D210: the system side must never receive the operator's person id or
// coordinates; it only gets camera pixels plus results the backend derived from those pixels.

const FRAME_KEYS = new Set(['cam', 'jpeg']);
const DET_KEYS = new Set(['bbox', 'score', 'color', 'red_ratio', 'blue_ratio', 'est_xy']);
const TRACK_KEYS = new Set(['state', 'active_cam', 'seen_cams', 'est_xy', 'events', 'lost_ticks',
  // image adjudication (src/amidst/live_mode/advisor.py): who decided, and the advisor's own status. Backend outputs only.
  'decision_source', 'fallback_reason', 'advisor']);
const ADVISOR_KEYS = new Set(['state', 'pending_ms', 'last']);
const ADVISOR_LAST_KEYS = new Set(['kind', 'cam', 'choice', 'reason', 'latency_ms', 'applied', 'cleared', 'model', 'source', 'fallback_reason']);
const EVENT_KEYS = new Set(['tick', 'type', 'cam', 'detail']);
const TOP_KEYS = new Set(['type', 'tick', 't_capture_ms', 'frames', 'dets', 'tracking', 'timing_ms']);
TOP_KEYS.add('schedule');
const SCHEDULE_KEYS = new Set(['mode','camera_ids','next_camera_ids','reason','lost_rounds','radius','graph_sha256']);

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
  const msg = {
    type: 'frame-batch', tick, t_capture_ms: tCaptureMs,
    frames: frames.map((f) => pick(f, FRAME_KEYS)),
    dets, tracking, timing_ms: result.timing_ms || {},
  };
  if (result.schedule) msg.schedule=pick(result.schedule,SCHEDULE_KEYS);
  return msg;
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
  if (msg.schedule) {
    chk(msg.schedule,SCHEDULE_KEYS,'schedule');
    if (!['adaptive','all'].includes(msg.schedule.mode)) bad.push('schedule.mode');
    if (!['ACTIVE_NEIGHBORS','ALL_CAMERAS','INITIAL_SEARCH','GRAPH_SCOPE_UNKNOWN','LOST_ALL','LOST_EXPAND','REQUEST_PLAN_MISS'].includes(msg.schedule.reason)) bad.push('schedule.reason');
    for (const key of ['lost_rounds','radius']) if (!Number.isInteger(msg.schedule[key]) || msg.schedule[key]<0) bad.push(`schedule.${key}`);
    if (msg.schedule.graph_sha256!=null && !/^[a-f0-9]{64}$/.test(msg.schedule.graph_sha256)) bad.push('schedule.graph_sha256');
    for (const key of ['camera_ids','next_camera_ids']) {
      if (!Array.isArray(msg.schedule[key]) || msg.schedule[key].some(id=>typeof id!=='string')) bad.push(`schedule.${key}`);
    }
  }
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
export function buildInferHeader({ tick, tCaptureMs, frames, availableCameras }) {
  const h = { tick, t_capture_ms: tCaptureMs, frames: frames.map((f) => ({ cam: f.cam, bytes: f.jpeg.byteLength })) };
  if (availableCameras) h.available_cameras=[...availableCameras];
  return h;
}
