// Synthetic fixture; not the missing original 23.5-second recording.
import fs from 'node:fs';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {createCrowd} from '../../frontend/live-mode/src/crowd.mjs';
import {RECORD_DT, createInputRecording, createPlayback, replayActions} from '../../frontend/live-mode/src/recording.mjs';
const raw = fs.readFileSync(new URL('../../docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json', import.meta.url));
const run = JSON.parse(raw).runs.find(r => r.run_id === 'A4-1-v2-4actor');
const bindings = {scenario_sha256: crypto.createHash('sha256').update(raw).digest('hex'), scope: 'SYNTHETIC_TEST_ONLY'};
const crowd = createCrowd(run, {actorId: 'C'});
const recorder = createInputRecording({case_id: 'CX676_SYNTHETIC_BLUE', run_id: run.run_id, actor_id: 'C',
  seed: 676, config: {fps: 5, crowd: crowd.snapshot().config}, bindings}, crowd.snapshot());
for (let step = 0; step < 80; step++) recorder.append({w: step < 20}, crowd.step({w: step < 20}, RECORD_DT));
const recording = recorder.export([{tick: 0, action: 'start', color: 'blue'},
  {tick: 10, action: 'reselect', color: 'blue'}, {tick: 10, action: 'pick', candidate: {cam: 'CAM_W2', est_xy: [5, 0]}}]);
for (let repeat = 0; repeat < 2; repeat++) {
  const playback = createPlayback(recording, createCrowd(run, {actorId: 'C'}), bindings);
  while (!playback.done) playback.step();
}
const requests = [], receipts = [];
const fetcher = async (path, options) => {
  requests.push({path, body: options?.body ? JSON.parse(options.body) : null});
  return {ok: true, json: async () => path === '/track/candidates'
    ? {candidates: [{cand_id: 'fresh', tick: 9, cam: 'CAM_W2', est_xy: [5, 0]}]}
    : {mode: path === '/track/pick' ? 'TRACKING' : 'ACQUIRING', color: 'blue'}};
};
for (let tick = 0; tick <= 20; tick++) receipts.push(...await replayActions(recording.actions, tick, 'synthetic-session', fetcher, () => tick * 200));
assert.deepEqual(requests.map(r => r.path), ['/track/start', '/track/start', '/track/candidates', '/track/pick']);
assert(!JSON.stringify(requests).match(/actor_id|scenario|expected|gt_visible/));
process.stdout.write(JSON.stringify({scope: 'SYNTHETIC_FIXTURE_NOT_ORIGINAL_EVENT', playback_repeats: 2,
  recording, public_requests: requests, receipts}, null, 2) + '\n');
