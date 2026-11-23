// F3 (#657): one playhead source for title / stage / plan; multi view = every run camera; manual re-selection candidates.
import test from 'node:test';
import assert from 'node:assert/strict';
import {blindReacquire, stagePlan, multiTiles, manualCandidates, manualSelectionSupported, agentSummaryText, TILE_BADGE} from './ui-model.mjs';

const SV = [
  {kind: 'ON_CAMERA', camera_id: 'CAM_A', range_us: [0, 10e6]},
  {kind: 'GAP', camera_id: null, range_us: [10e6, 12e6]},
  {kind: 'ON_CAMERA', camera_id: 'CAM_B', range_us: [12e6, 20e6]},
  {kind: 'LOST', camera_id: null, range_us: [20e6, 30e6]},
];
const SIGHT = [
  {camera_id: 'CAM_A', track_ref: 'a1', range_us: [0, 10e6], selected_for_single_view: true},
  {camera_id: 'CAM_C', track_ref: 'c1', range_us: [4e6, 8e6], selected_for_single_view: false},
  {camera_id: 'CAM_B', track_ref: 'b1', range_us: [12e6, 20e6], selected_for_single_view: true},
];

test('F3: the plan never says re-observed while the playhead is in a later LOST segment', () => {
  assert.equal(blindReacquire(SV, 15e6, null)?.cameraId, 'CAM_B');       // inside the re-acquired segment
  assert.equal(stagePlan(SV, 25e6).kind, 'LOST');
  assert.equal(blindReacquire(SV, 25e6, null), null);                     // same source as the title / stage: LOST
  const last = SV.slice(0, 3);
  assert.equal(blindReacquire(last, 25e6, null)?.cameraId, 'CAM_B');     // last segment: stays at the end of the window
});

test('F3: multi view lists every run camera with current / candidate roles from the playhead', () => {
  const ids = ['CAM_A', 'CAM_B', 'CAM_C', 'CAM_D', 'CAM_E', 'CAM_F', 'CAM_G', 'CAM_H'];
  const at5 = multiTiles(ids, SV, SIGHT, 5e6);
  assert.equal(at5.length, 8);
  assert.deepEqual(at5.slice(0, 4).map(x => x.role), ['current', 'none', 'candidate', 'none']);
  assert.equal(at5[0].badge, TILE_BADGE.current); assert.equal(at5[2].badge, '候選');
  assert.ok(multiTiles(ids, SV, SIGHT, 11e6).every(x => x.role !== 'current'));   // in the gap nobody is "目前追蹤"
});

test('F3: manual candidates are the other local tracks at the playhead', () => {
  assert.deepEqual(manualCandidates(SV, SIGHT, 5e6), [{trackRef: 'c1', cameraId: 'CAM_C', atUs: 5e6}]);
  assert.deepEqual(manualCandidates(SV, SIGHT, 9e6).map(c => c.trackRef), []);
  assert.deepEqual(manualCandidates(SV, SIGHT, 11e6), []);
});

test('F3: agent summary line', () => {
  assert.equal(agentSummaryText(null), null);
  assert.equal(agentSummaryText({switch_mode: 'AGENT_SEQUENTIAL', available: true, decisions: 3, adopted: 2, fallbacks: 1}), 'Agent 模式：決策 3 次、採用 2 次、退回規則 1 次');
  assert.match(agentSummaryText({switch_mode: 'AGENT_SEQUENTIAL', available: false, unavailable_reason: 'MAIN_SCREEN_AGENT_D124_RUNS_ONLY'}), /尚未接 Agent/);
});

test('CX-H6: registered core tracking supports manual selection, unavailable/generic responses do not', () => {
  for (const producer of ['demo-cross-camera-local-linker','demo-core-agent-track']) assert.equal(manualSelectionSupported({provenance:{producer}}),true);
  assert.equal(manualSelectionSupported({provenance:{producer:'q-core-track'}}),false);
  assert.equal(manualSelectionSupported(null),false);
});
