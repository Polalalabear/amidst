import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createCrowd} from '../src/crowd.mjs';
import {RECORD_DT, createInputRecording, createPlayback, validateCase, replayActions,
  captureStride, importActions} from '../src/recording.mjs';
import {buildInferHeader, buildSystemMessage, validateSystemMessage} from '../src/protocol.mjs';

const runs = JSON.parse(fs.readFileSync(new URL(
  '../../../docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json', import.meta.url))).runs;
const bindings = {scene_sha256: 's', cameras_sha256: 'c'};
function recorded(run) {
  const crowd = createCrowd(run, {actorId: 'T'});
  const recorder = createInputRecording({case_id: 'fixture', run_id: run.run_id, actor_id: 'T',
    seed: 596, config: {fps: 5, crowd: crowd.snapshot().config}, bindings}, crowd.snapshot());
  for (let i = 0; i < 1600; i++) {
    const keys = {w: i % 100 < 50, d: i % 60 < 25, shift: i % 3 === 0, view_yaw: i % 360};
    recorder.append(keys, crowd.step(keys, RECORD_DT));
  }
  return recorder.export();
}

test('A4/B4 recorded inputs reproduce every private pose and clock twice', () => {
  for (const run of runs.filter(r => ['A4-1-v2-4actor', 'B4-1-v2-4actor'].includes(r.run_id))) {
    const data = recorded(run);
    const replay = () => {
      const crowd = createCrowd(run, {actorId: 'T'}), playback = createPlayback(data, crowd, bindings);
      const frames = [crowd.snapshot()];
      while (!playback.done) frames.push(playback.step());
      return frames;
    };
    assert.deepEqual(replay(), data.expected);
    assert.deepEqual(replay(), data.expected);
    assert.throws(() => createPlayback(data, createCrowd(run, {actorId: 'T'}), {}), /SOURCE_MISMATCH/);
    data.expected[2].actors[0].x += 1;
    const playback = createPlayback(data, createCrowd(run, {actorId: 'T'}), bindings);
    playback.step();
    assert.throws(() => playback.step(), /CASE_DIVERGED:2/);
  }
});

test('generated cases need only inputs and bindings, and reject invalid clocks/actions', () => {
  const data = recorded(runs[0]);
  delete data.expected;
  const playback = createPlayback(data, createCrowd(runs[0], {actorId: 'T'}), bindings);
  while (!playback.done) playback.step();
  assert.throws(() => playback.step(), /FINISHED/);
  assert.throws(() => captureStride(3), /FPS_MUST_DIVIDE_20/);
  data.inputs[0].dt = .1;
  assert.throws(() => validateCase(data), /INPUT_INVALID/);
});

test('replayed track actions resolve a fresh candidate and send only public fields', async () => {
  const sent = [];
  const actions = [
    {tick: 0, action: 'start', color: 'red', gt: 'private'},
    {tick: 1, action: 'pick', candidate: {est_xy: [1, 2]}, actor_id: 'private'},
    {tick: 2, action: 'stop'},
  ];
  const fetcher = async (path, options) => {
    sent.push({path, body: options?.body ? JSON.parse(options.body) : null});
    return {ok: true, json: async () => path === '/track/candidates'
      ? {candidates: [{cand_id: 'fresh', tick: 0, cam: 'CAM_W1', est_xy: [1, 2]}]}
      : {mode: path === '/track/stop' ? 'IDLE' : 'TRACKING', color: 'red'}};
  };
  for (let tick = 0; tick < 3; tick++) await replayActions(actions, tick, 'fresh-session', fetcher, () => tick * 1000);
  assert.equal(sent.find(row => row.path === '/track/pick').body.cand_id, 'fresh');
  assert.doesNotMatch(JSON.stringify(sent), /private|actor_id|gt/);
  assert.deepEqual(importActions({session_id: 's', actions: [{type: 'start', t_op: 40, color: 'red'}]},
    {session_id: 's', ticks: [{tick: 0, t_capture: 0}, {tick: 1, t_capture: 200}]}),
  [{tick: 1, action: 'start', color: 'red'}]);
  const ambiguous = async () => ({ok: true, json: async () => ({candidates: [
    {est_xy: [1, 2]}, {est_xy: [1, 2]}]})});
  await assert.rejects(() => replayActions(actions, 1, 's', ambiguous, () => 0), /PICK_NOT_UNIQUE/);
  const data = recorded(runs[0]);
  const header = buildInferHeader({tick: 0, tCaptureMs: 0, frames: [], availableCameras: ['CAM_W1'], ...data});
  const wire = buildSystemMessage({tick: 0, tCaptureMs: 0, frames: [], result: {
    ...data, tracking: {state: 'IDLE', events: []}, dets: {}, timing_ms: {}}});
  assert.deepEqual(validateSystemMessage(wire), []);
  assert.doesNotMatch(JSON.stringify({header, wire}), /expected|bindings|actor_id|seed|pause_|gt_visible/);
});
