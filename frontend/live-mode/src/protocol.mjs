// The same schema strips backend extras on send and rejects malformed messages on receive.
// These messages carry pixel observations and their downstream results.
export const TRACK_MODES = ['IDLE', 'ACQUIRING', 'NEEDS_PICK', 'TRACKING'];

const enumOf = (...values) => value => values.includes(value);
const text = value => typeof value === 'string' && Array.from(value).length <= 64;
const number = Number.isFinite;
const integer = value => Number.isSafeInteger(value) && value >= 0;
const boolean = value => typeof value === 'boolean';
const jpeg = value => value instanceof ArrayBuffer && !Object.keys(value).length;
const nullable = rule => ({ nullable: rule });
const list = (rule, size) => ({ list: rule, size });
const shape = (fields, required = []) => ({ fields, required });
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value)
  && [Object.prototype, null].includes(Object.getPrototypeOf(value));

const FORBIDDEN = new Set([
  'actor_id', 'role', 'variant', 'person_id', 'operator_xy', 'player_xy', 'gt', 'gt_visible',
  'waypoints', 's_i', 'forced_overlap', 'phase_offset_s', 'pass_end', 'crowd_error', 'active_passes',
  'spawn_adjusted', 'run_id', 'view_yaw', 'view_pitch',
  'session', 'session_id', '__proto__', 'prototype', 'constructor',
]);
const forbidden = key => FORBIDDEN.has(key) || /^(?:gt_|script_|pause_|session\.)/.test(key);
const source = enumOf('RULE_ONLY', 'RULE_FALLBACK', 'AGENT');
const questionKind = enumOf('SILENT_PICK', 'LOST_WITH_CANDIDATES');
const point = nullable(list(number, 2));
const color = enumOf('red', 'blue', 'none');
const TARGET_RULE = shape({
  color: nullable(enumOf('red', 'blue')),
  mode: enumOf(...TRACK_MODES),
}, ['color', 'mode']);

const EVENT_DETAILS = {
  ACQUIRE: shape({ by: enumOf('USER_PICK', 'AUTO_SINGLE') }, ['by']),
  SWITCH: shape({ from: text, gap_ticks: integer, by: enumOf('AGENT') }, ['from']),
  TARGET_OUT_OF_VIEW: enumOf(null),
  LOST: enumOf(null),
  REACQUIRE: enumOf(null),
  ADJUDICATE_ASK: shape({ kind: questionKind, candidates: integer }),
  ADJUDICATED: shape({
    choice: nullable(integer), applied: boolean, cleared: boolean, source, latency_ms: number,
  }),
};
const EVENT_RULE = (event) => shape({
  tick: integer, type: enumOf(...Object.keys(EVENT_DETAILS)), cam: nullable(text),
  detail: nullable(Object.hasOwn(EVENT_DETAILS, event?.type) ? EVENT_DETAILS[event.type] : enumOf(null)),
}, ['tick', 'type']);

const DETECTION = shape({
  bbox: list(number, 4), score: number, color, red_ratio: number, blue_ratio: number, est_xy: point,
}, ['bbox']);
const SCHEDULE = shape({
  mode: enumOf('adaptive', 'all'),
  camera_ids: list(text), next_camera_ids: list(text),
  reason: enumOf('ACTIVE_NEIGHBORS', 'ALL_CAMERAS', 'INITIAL_SEARCH', 'GRAPH_SCOPE_UNKNOWN',
    'LOST_ALL', 'LOST_EXPAND', 'REQUEST_PLAN_MISS'),
  lost_rounds: integer, radius: integer,
  graph_sha256: nullable(value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)),
}, ['mode', 'camera_ids', 'next_camera_ids', 'reason', 'lost_rounds', 'radius']);
const TIMINGS = ['decode', 'preprocess', 'forward', 'post', 'detect_total', 'color', 'track', 'server_total'];
const TRACKING = shape({
  state: enumOf('IDLE', 'SEARCHING', 'NEEDS_PICK', 'TRACKING', 'LOST', 'ADJUDICATING',
    'TARGET_OUT_OF_VIEW'),
  active_cam: nullable(text), seen_cams: list(text), est_xy: point,
  events: list({ event: true }), lost_ticks: integer, target: TARGET_RULE,
  decision_source: source, fallback_reason: nullable(text),
  advisor: nullable(shape({
    state: enumOf('IDLE', 'ASKING'), pending_ms: nullable(number),
    last: nullable(shape({
      kind: questionKind, cam: text, choice: nullable(integer), reason: nullable(text),
      latency_ms: number, applied: boolean, cleared: boolean, model: nullable(text), source,
      fallback_reason: nullable(text),
    })),
  })),
});
const MESSAGE = shape({
  type: enumOf('frame-batch'), tick: integer, t_capture_ms: number,
  frames: list(shape({ cam: text, jpeg }, ['cam', 'jpeg'])),
  dets: { map: list(DETECTION) }, tracking: TRACKING,
  timing_ms: shape(Object.fromEntries(TIMINGS.map(key => [key, number]))),
  schedule: SCHEDULE,
}, ['type', 'tick', 't_capture_ms', 'frames', 'dets', 'tracking', 'timing_ms']);

function checked(value, rule, path, bad) {
  const reject = () => { bad.push(path); return undefined; };
  if (typeof rule === 'function') return rule(value) ? value : reject();
  if (rule.event) return checked(value, EVENT_RULE(value), path, bad);
  if (rule.nullable) return value === null ? null : (checked(value, rule.nullable, path, bad) ?? null);
  if (rule.list) {
    if (!Array.isArray(value) || (rule.size !== undefined && value.length !== rule.size)) return reject();
    for (const key of Object.keys(value)) {
      if (!/^(?:0|[1-9]\d*)$/.test(key) || Number(key) >= value.length) bad.push(`${path}.${key}`);
    }
    const result = Array.from(value, (item, i) => checked(item, rule.list, `${path}[${i}]`, bad));
    if (rule.size !== undefined && result.includes(undefined)) return undefined;
    return result.filter(item => item !== undefined);
  }
  if (!record(value)) return reject();
  const fields = [];
  for (const [key, item] of Object.entries(value)) {
    const type = rule.map ?? (Object.hasOwn(rule.fields, key) ? rule.fields[key] : null);
    const at = `${path}.${key}`;
    if (forbidden(key) || !type || (rule.map && !text(key))) {
      bad.push(at);
      continue;
    }
    const converted = checked(item, type, at, bad);
    if (converted !== undefined) fields.push([key, converted]);
  }
  const result = Object.fromEntries(fields);
  let missing = false;
  for (const key of rule.required ?? []) {
    if (!Object.hasOwn(result, key)) { bad.push(`${path}.${key}`); missing = true; }
  }
  return missing ? undefined : result;
}

export function buildSystemMessage({ tick, tCaptureMs, frames, result }) {
  const msg = {
    type: 'frame-batch', tick, t_capture_ms: tCaptureMs, frames,
    dets: result.dets || {}, tracking: result.tracking || {}, timing_ms: result.timing_ms || {},
  };
  if (result.schedule) msg.schedule = result.schedule;
  const clean = checked(msg, MESSAGE, 'msg', []);
  if (!clean) throw new TypeError('INVALID_FRAME_ENVELOPE');
  return clean;
}

export function validateSystemMessage(msg) {
  const bad = [];
  checked(msg, MESSAGE, 'msg', bad);
  return [...new Set(bad.map(path => path === 'msg' ? path : path.slice(4)))].map(
    path => path.includes('.') || path === 'msg' ? path : `msg.${path}`,
  );
}

// The inference header accepts only the capture clock and registered camera IDs.
export function buildInferHeader({ tick, tCaptureMs, frames, availableCameras }) {
  const h = { tick, t_capture_ms: tCaptureMs, frames: frames.map(f => ({ cam: f.cam, bytes: f.jpeg.byteLength })) };
  if (availableCameras) h.available_cameras = [...availableCameras];
  return h;
}
