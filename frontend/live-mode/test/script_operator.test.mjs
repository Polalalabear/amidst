// #597 scripted operator (D321/D322): route -> keys, real-wall walkability, determinism, input isolation.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createCrowd} from '../src/crowd.mjs';
import {moveVector} from '../src/view.mjs';
import {compileRoute, createScriptOperator, createFixedStepper, yawToward, SCRIPT_DT} from '../src/script_operator.mjs';
import {HARDSET_ROUTES} from '../src/hardset_routes.mjs';

const read = rel => JSON.parse(fs.readFileSync(new URL(rel, import.meta.url)));
const scenario = read('../../../docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json');
const geometry = read('../../../docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json');
const table = read('../../../configs/evaluation/live_hardset_v1.json');
const runOf = id => scenario.runs.find(r => r.run_id === `${id}-v2-4actor`);
const emptyRun = {run_id: 'fixture', duration_us: 100e6, actors: [{actor_id: 'T', waypoints: [{t_us: 0, xy: [0, 0]}, {t_us: 100e6, xy: [0, 0]}]}]};
const player = s => s.actors.find(a => a.is_player);

function play(caseId, frames = null) {
  const route = HARDSET_ROUTES[caseId], run = runOf(route.run_id);
  const crowd = createCrowd(run, {actorId: 'T', segments: geometry.clearance_segments});
  const op = createScriptOperator(route), stepper = createFixedStepper(crowd, op);
  const plan = table.cases.find(c => c.case_id === caseId).route_plan, samples = new Map();
  const record = s => samples.set(Math.round(s.t_sim / SCRIPT_DT), [player(s).x, player(s).y]);
  let guard = 0;
  while (!op.done && stepper.snapshot.t_sim < plan.length_s + 5 && guard++ < 1e5) {
    if (frames) { stepper.advance(frames()); } else stepper.stepOnce();
    record(stepper.snapshot);
  }
  return {op, snapshot: stepper.snapshot, samples, plan};
}

test('the frontend route copy equals route_plan in configs/evaluation/live_hardset_v1.json and holds no answers', () => {
  const generated = table.cases.filter(c => c.source === 'GENERATED');
  assert.deepEqual(Object.keys(HARDSET_ROUTES).sort(), generated.map(c => c.case_id).sort());
  for (const c of generated) {
    assert.deepEqual(HARDSET_ROUTES[c.case_id], {run_id: c.run_id, start_xy: c.route_plan.start_xy, steps: c.route_plan.steps});
    const start = runOf(c.run_id).actors.find(a => a.actor_id === 'T').waypoints[0].xy;
    assert.deepEqual(c.route_plan.start_xy, start, `${c.case_id} starts where the player spawns`);
  }
  const text = fs.readFileSync(new URL('../src/hardset_routes.mjs', import.meta.url), 'utf8').split('\n').filter(l => !l.startsWith('//')).join('\n');
  for (const word of ['answer', 'target_gt', 'expected_action', 'gt_visible', 'events']) assert.ok(!text.includes(word), word);
});

test('compileRoute rejects malformed plans', () => {
  assert.throws(() => compileRoute({start_xy: [0], steps: [{mode: 'hold', seconds: 1}]}), /ROUTE_START_INVALID/);
  assert.throws(() => compileRoute({start_xy: [0, 0], steps: []}), /ROUTE_STEPS_EMPTY/);
  assert.throws(() => compileRoute({start_xy: [0, 0], steps: [{mode: 'fly'}]}), /ROUTE_STEP_0_MODE/);
  assert.throws(() => compileRoute({start_xy: [0, 0], steps: [{mode: 'walk', to_xy: [1, NaN]}]}), /ROUTE_STEP_0_TARGET/);
  assert.throws(() => compileRoute({start_xy: [0, 0], steps: [{mode: 'hold', seconds: -1}]}), /ROUTE_STEP_0_SECONDS/);
});

test('route steps become W/Shift keys whose view_yaw points W at the waypoint', () => {
  for (const to of [[3, 0], [0, 3], [-2, -2], [1, -4]]) {
    const yaw = yawToward({x: 0, y: 0}, to), v = moveVector({w: true}, yaw, 1), n = Math.hypot(...to);
    assert.ok(Math.abs(v.vx - to[0] / n) < 1e-9 && Math.abs(v.vy - to[1] / n) < 1e-9, `${to}`);
  }
  const op = createScriptOperator({start_xy: [0, 0], steps: [{mode: 'walk', to_xy: [2, 0]}, {mode: 'run', to_xy: [2, 5]}, {mode: 'hold', seconds: 1}]});
  assert.deepEqual(op.keys({x: 0, y: 0}, 0), {w: true, shift: false, view_yaw: 90});
  assert.deepEqual(op.keys({x: 2, y: 0}, 1.7), {w: true, shift: true, view_yaw: 0});
  assert.deepEqual(op.keys({x: 2, y: 5}, 3.7), {view_yaw: 0}); // hold: no movement key
});

test('walk, run, hold and hold_until timings follow 1.2 / 2.5 m/s in an empty world', () => {
  const route = {start_xy: [0, 0], steps: [{mode: 'hold', seconds: 1}, {mode: 'walk', to_xy: [3.6, 0]}, {mode: 'run', to_xy: [3.6, 5]}, {mode: 'hold_until', t_s: 10}]};
  const crowd = createCrowd(emptyRun, {actorId: 'T'}), op = createScriptOperator(route), stepper = createFixedStepper(crowd, op);
  while (!op.done) stepper.stepOnce();
  const done = op.events.filter(e => e.type === 'script_step_done').map(e => e.t_sim);
  const near = (a, b, eps) => assert.ok(Math.abs(a - b) <= eps, `${a} vs ${b}`);
  near(done[0], 1, 1e-6);
  near(done[1], 1 + 3.6 / 1.2, SCRIPT_DT + 1e-6);
  near(done[2], 1 + 3 + 5 / 2.5, 2 * SCRIPT_DT + 1e-6);
  near(done[3], 10, SCRIPT_DT + 1e-6);
  const p = player(stepper.snapshot);
  assert.ok(Math.hypot(p.x - 3.6, p.y - 5) <= 2.5 * SCRIPT_DT / 2 + 1e-9);
});

test('a person in the way is waited for (no pushing through) and the wait is logged', () => {
  const blocker = {actor_id: 'A', waypoints: [{t_us: 0, xy: [1, 0]}, {t_us: 100e6, xy: [1, 0]}]};
  const run = {...emptyRun, actors: [...emptyRun.actors, blocker]};
  const crowd = createCrowd(run, {actorId: 'T'}), op = createScriptOperator({start_xy: [0, 0], steps: [{mode: 'walk', to_xy: [2, 0]}]});
  const stepper = createFixedStepper(crowd, op);
  for (let i = 0; i < 100; i++) stepper.stepOnce();
  const p = player(stepper.snapshot);
  assert.ok(Math.hypot(p.x - 1, p.y) >= 0.6 - 1e-9, 'kept the 0.60 m person clearance');
  assert.equal(op.done, false);
  assert.ok(op.events.some(e => e.type === 'script_stall'));
});

test('all nine generated routes are walkable with real walls and never block a scripted person', () => {
  for (const id of Object.keys(HARDSET_ROUTES)) {
    const {op, snapshot, plan} = play(id);
    assert.equal(op.done, true, `${id} finished`);
    assert.ok(Math.abs(snapshot.t_sim - plan.length_s) <= 0.5, `${id} length ${snapshot.t_sim} vs plan ${plan.length_s}`);
    assert.deepEqual(op.events.filter(e => e.type === 'script_stall'), [], `${id} no stall`);
    for (const a of snapshot.actors.filter(a => !a.is_player)) assert.equal(a.pause_player_i, 0, `${id} ${a.actor_id} not blocked`);
    assert.deepEqual(snapshot.events.filter(e => e.type === 'forced_overlap'), [], `${id} no forced overlap`);
    const last = player(snapshot), end = plan.timeline.at(-1).xy;
    assert.ok(Math.hypot(last.x - end[0], last.y - end[1]) <= 0.1, `${id} ends at the planned point`);
  }
});

test('fixed seed and start: two runs with different frame timing give the same trajectory (bound 0.01 m)', () => {
  let seed = 7;
  const jitter = () => { seed = (seed * 1103515245 + 12345) % 2 ** 31; return 0.008 + (seed / 2 ** 31) * 0.05; };
  for (const id of ['H1-1', 'H4-2', 'H5-1']) {
    const a = play(id, () => 1 / 60), b = play(id, jitter);
    let worst = 0, shared = 0;
    for (const [k, xy] of a.samples) { const other = b.samples.get(k); if (!other) continue; shared++; worst = Math.max(worst, Math.hypot(xy[0] - other[0], xy[1] - other[1])); }
    assert.ok(shared > 0.9 * a.samples.size, `${id} compared ${shared} steps`);
    assert.ok(worst <= 0.01, `${id} max difference ${worst} m`);
  }
});

test('the scripted operator reads only the route, its own pose and t_sim (no B window, backend, tracker or GT)', () => {
  const src = fs.readFileSync(new URL('../src/script_operator.mjs', import.meta.url), 'utf8');
  const code = src.split('\n').filter(line => !line.trim().startsWith('//')).join('\n');
  assert.deepEqual([...code.matchAll(/from\s+'([^']+)'/g)].map(m => m[1]), ['./sim.mjs']);
  for (const word of ['fetch', 'BroadcastChannel', 'XMLHttpRequest', 'WebSocket', 'window', 'document', 'tracking', 'gt_visible',
    'groundTruth', 'active_cam', 'state', '/infer', '/track', 'protocol', 'system', 'answer', 'live_hardset']) {
    assert.ok(!new RegExp(`\\b${word.replace('/', '\\/')}`).test(code), `forbidden reference: ${word}`);
  }
  // The keys function sees only {x, y} and t_sim.
  const seen = [];
  const op = createScriptOperator(HARDSET_ROUTES['H5-1']);
  op.keys(new Proxy({x: -10, y: -0.4}, {get: (t, k) => { seen.push(k); return t[k]; }}), 0);
  assert.ok(seen.every(k => k === 'x' || k === 'y'), `read ${seen}`);
});
