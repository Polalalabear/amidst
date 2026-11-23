// A-private input recording. Only explicit public track requests and sanitized system messages leave A.
export const CASE_SCHEMA = 'live-ab.case.v1';
export const RECORD_DT = .05;
const clone = value => JSON.parse(JSON.stringify(value));
const keysAllowed = new Set(['w', 'a', 's', 'd', 'shift', 'view_yaw']);
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

export function inputKeys(input) {
  const keys = {};
  for (const [key, value] of Object.entries(input)) {
    if (!keysAllowed.has(key)) continue;
    if (key === 'view_yaw') {
      if (!Number.isFinite(value)) throw new Error('CASE_VIEW_YAW');
    } else if (typeof value !== 'boolean') throw new Error('CASE_KEY');
    keys[key] = value;
  }
  return keys;
}

export function captureStride(fps) {
  const stride = 1 / (fps * RECORD_DT);
  if (!Number.isInteger(stride) || stride < 1) throw new Error('CASE_FPS_MUST_DIVIDE_20');
  return stride;
}

export async function hashBinding(value) {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  const hash = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(hash)].map(byte => byte.toString(16).padStart(2, '0')).join('');
}

export function validateCase(data) {
  if (data?.schema_version !== CASE_SCHEMA || !/^[a-zA-Z0-9_-]{1,80}$/.test(data.case_id || '')
      || typeof data.run_id !== 'string' || !['T', 'A', 'B', 'C'].includes(data.actor_id)
      || !Number.isSafeInteger(data.seed) || data.seed < 0 || !data.config
      || !Array.isArray(data.inputs) || !data.bindings || !Array.isArray(data.actions)) {
    throw new Error('CASE_INVALID');
  }
  captureStride(data.config.fps);
  for (const [i, input] of data.inputs.entries()) {
    if (input.step !== i || input.dt !== RECORD_DT || !same(inputKeys(input.keys), input.keys)) {
      throw new Error(`CASE_INPUT_INVALID:${i}`);
    }
  }
  if (data.expected && data.expected.length !== data.inputs.length + 1) throw new Error('CASE_EXPECTED_LENGTH');
  let prior = -1;
  for (const action of data.actions) {
    if (!Number.isSafeInteger(action.tick) || action.tick < 0 || action.tick < prior
        || action.tick > Math.floor(data.inputs.length / captureStride(data.config.fps))
        || !['start', 'stop', 'reselect', 'pick'].includes(action.action)) throw new Error('CASE_ACTION_INVALID');
    if (['start', 'reselect'].includes(action.action) && !['red', 'blue'].includes(action.color)) throw new Error('CASE_ACTION_COLOR');
    if (action.action === 'pick' && (!Array.isArray(action.candidate?.est_xy)
        || action.candidate.est_xy.length !== 2 || !action.candidate.est_xy.every(Number.isFinite))) {
      throw new Error('CASE_ACTION_CANDIDATE');
    }
    prior = action.tick;
  }
  return clone(data);
}

export function createInputRecording(header, initial) {
  const data = {schema_version: CASE_SCHEMA, ...clone(header), inputs: [], expected: [clone(initial)], actions: []};
  validateCase(data);
  return {
    get length() { return data.inputs.length; },
    append(keys, snapshot) {
      data.inputs.push({step: data.inputs.length, dt: RECORD_DT, keys: inputKeys(keys)});
      data.expected.push(clone(snapshot));
    },
    export(actions = data.actions) { return validateCase({...data, actions}); },
  };
}

export function createPlayback(data, crowd, bindings) {
  const source = validateCase(data);
  if (!same(source.bindings, bindings)) throw new Error('CASE_SOURCE_MISMATCH');
  if (source.expected && !same(crowd.snapshot(), source.expected[0])) throw new Error('CASE_INITIAL_MISMATCH');
  let index = 0;
  return {
    get done() { return index === source.inputs.length; },
    step() {
      if (index === source.inputs.length) throw new Error('CASE_FINISHED');
      const input = source.inputs[index];
      const snapshot = crowd.step(input.keys, input.dt);
      index++;
      if (source.expected && !same(snapshot, source.expected[index])) throw new Error(`CASE_DIVERGED:${index}`);
      return snapshot;
    },
  };
}

export function importActions(bLog, aLog) {
  if (bLog.session_id !== aLog.session_id) throw new Error('CASE_ACTION_SESSION');
  return bLog.actions.map(action => {
    const capture = aLog.ticks.find(row => row.t_capture >= action.t_op);
    if (!capture) throw new Error('CASE_ACTION_AFTER_LAST_CAPTURE');
    const result = {tick: capture.tick, action: action.type};
    if (action.color) result.color = action.color;
    if (action.type === 'pick') result.candidate = {est_xy: action.est_xy, ...(action.cam ? {cam: action.cam} : {})};
    return result;
  });
}

export async function replayActions(actions, tick, sessionId, fetcher, clock) {
  const receipts = [];
  async function request(path, body) {
    const response = await fetcher(path, body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {});
    const data = await response.json();
    if (!response.ok) throw new Error(`CASE_ACTION_HTTP:${data.error || response.status}`);
    return data;
  }
  for (const action of actions.filter(a => a.tick === tick)) {
    const at = clock(), body = {session_id: sessionId};
    let endpoint = action.action;
    if (action.action === 'start' || action.action === 'reselect') {
      endpoint = 'start';
      body.color = action.color;
      if (action.action === 'reselect') body.reselect = true;
    } else if (action.action === 'pick') {
      const snapshot = await request('/track/candidates');
      const candidates = snapshot.candidates.filter(c => (!action.candidate.cam || c.cam === action.candidate.cam)
        && Math.hypot(c.est_xy[0] - action.candidate.est_xy[0], c.est_xy[1] - action.candidate.est_xy[1]) <= .001);
      if (candidates.length !== 1) throw new Error('CASE_PICK_NOT_UNIQUE');
      body.cand_id = candidates[0].cand_id;
    }
    const data = await request(`/track/${endpoint}`, body);
    const receipt = {type: action.action, t_op: at, mode: data.mode, color: data.color ?? null};
    const picked = data.picked || data.candidates?.[0];
    if (picked && (action.action === 'pick' || data.mode === 'TRACKING')) {
      Object.assign(receipt, {tick: picked.tick, cand_id: picked.cand_id, est_xy: picked.est_xy});
    }
    receipts.push(receipt);
  }
  return receipts;
}
