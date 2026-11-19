// Scripted operator for the #597 hard-case set (D321/D322). It plays the A-side player like a person at the
// keyboard: each fixed step it turns the view toward the next waypoint and presses W (and Shift to run), and the
// crowd simulation applies the same wall clearance and person avoidance as for a human player.
// Inputs are only the route plan, the player's own pose and the simulation clock. It never reads the B window,
// the backend, the tracker, camera visibility or scored answers. No DOM, network or renderer imports.
import {WALK, RUN} from './sim.mjs';

export const SCRIPT_DT = 0.05; // fixed simulation step (s); replays depend only on t_sim, not on frame timing
export const DEFAULT_SCRIPT_CONFIG = Object.freeze({dt: SCRIPT_DT, stall_s: 2.0, stall_eps_m: 0.01});

// Validate a route plan ({start_xy, steps}) and return frozen instructions.
export function compileRoute(plan) {
  if (!plan || !Array.isArray(plan.start_xy) || plan.start_xy.length !== 2 || !plan.start_xy.every(Number.isFinite)) throw new Error('ROUTE_START_INVALID');
  if (!Array.isArray(plan.steps) || !plan.steps.length) throw new Error('ROUTE_STEPS_EMPTY');
  return Object.freeze(plan.steps.map((step, i) => {
    if (step.mode === 'walk' || step.mode === 'run') {
      if (!Array.isArray(step.to_xy) || step.to_xy.length !== 2 || !step.to_xy.every(Number.isFinite)) throw new Error(`ROUTE_STEP_${i}_TARGET`);
      return Object.freeze({i, mode: step.mode, to: Object.freeze([...step.to_xy]), speed: step.mode === 'run' ? RUN : WALK});
    }
    if (step.mode === 'hold') {
      if (!Number.isFinite(step.seconds) || step.seconds < 0) throw new Error(`ROUTE_STEP_${i}_SECONDS`);
      return Object.freeze({i, mode: 'hold', seconds: step.seconds});
    }
    if (step.mode === 'hold_until') {
      if (!Number.isFinite(step.t_s) || step.t_s < 0) throw new Error(`ROUTE_STEP_${i}_UNTIL`);
      return Object.freeze({i, mode: 'hold_until', t_s: step.t_s});
    }
    throw new Error(`ROUTE_STEP_${i}_MODE`);
  }));
}

// view_yaw convention (view.mjs): degrees clockwise from world +Y; W moves along it.
export function yawToward(from, to) {
  return ((Math.atan2(to[0] - from.x, to[1] - from.y) * 180 / Math.PI) % 360 + 360) % 360;
}

export function createScriptOperator(plan, overrides = {}) {
  const cfg = Object.freeze({...DEFAULT_SCRIPT_CONFIG, ...overrides});
  const steps = compileRoute(plan);
  let index = 0, holdEnd = null, stall = null, lastYaw = 0;
  const events = [];
  const current = () => steps[index] ?? null;
  function advance(t_sim) {
    events.push({type: 'script_step_done', step: index, t_sim});
    index++; holdEnd = null; stall = null;
  }
  // Keys for the step that starts at t_sim with the player at pose {x, y}.
  function keys(pose, t_sim) {
    for (let guard = 0; guard <= steps.length; guard++) {
      const step = current();
      if (!step) return {view_yaw: lastYaw};
      if (step.mode === 'hold' || step.mode === 'hold_until') {
        if (holdEnd === null) holdEnd = step.mode === 'hold' ? t_sim + step.seconds : step.t_s;
        if (t_sim + 1e-9 < holdEnd) return {view_yaw: lastYaw};
        advance(t_sim); continue;
      }
      const d = Math.hypot(step.to[0] - pose.x, step.to[1] - pose.y);
      if (d <= step.speed * cfg.dt / 2 + 1e-9) { advance(t_sim); continue; }
      // Person or wall in the way: keep pressing toward the waypoint (the crowd decides), log the wait once.
      if (stall && Math.hypot(pose.x - stall.x, pose.y - stall.y) <= cfg.stall_eps_m) {
        if (!stall.logged && t_sim - stall.t >= cfg.stall_s - 1e-9) { stall.logged = true; events.push({type: 'script_stall', step: index, t_sim, xy: [pose.x, pose.y]}); }
      } else stall = {x: pose.x, y: pose.y, t: t_sim, logged: false};
      lastYaw = yawToward(pose, step.to);
      return {w: true, shift: step.mode === 'run', view_yaw: lastYaw};
    }
    throw new Error('SCRIPT_LOOP_GUARD');
  }
  return Object.freeze({
    keys,
    get done() { return index >= steps.length; },
    get step() { return index; },
    events,
    config: cfg,
  });
}

// Runs the crowd in fixed steps driven by the scripted operator. advance(wallDt) is called once per frame;
// leftover time is carried, so the trajectory is a function of t_sim only.
export function createFixedStepper(crowd, operator, {dt = operator.config.dt, maxSteps = 8} = {}) {
  let carry = 0, snapshot = crowd.snapshot();
  const player = s => s.actors.find(a => a.is_player);
  function stepOnce() {
    const p = player(snapshot);
    snapshot = crowd.step(operator.keys({x: p.x, y: p.y}, snapshot.t_sim), dt);
    return snapshot;
  }
  return Object.freeze({
    advance(wallDt) {
      carry += Math.max(0, wallDt);
      let n = 0;
      while (carry + 1e-9 >= dt && n < maxSteps) { carry -= dt; stepOnce(); n++; }
      if (n === maxSteps) carry = 0; // a stalled frame slows the run down instead of jumping
      return snapshot;
    },
    stepOnce,
    get snapshot() { return snapshot; },
  });
}
