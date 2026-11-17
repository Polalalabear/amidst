// 2026-11-17: readable place / camera names, one table for the front desk and the admin; codes stay available.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {PLACE_NAMES, CAMERA_NAMES, placeName, cameraName, placeLabel, cameraLabel, nameTitle, namesToConfirm} from './place-names.mjs';
import {cameraName as presentCamera} from './ui-present.mjs';
import {chipsFromParse} from './nl-spotlight-model.mjs';
import {buildOverview, trackingCard} from './admin-overview-model.mjs';

const graph = JSON.parse(readFileSync(new URL('../../configs/q1q5/graphs/r004/region_graph_v3.json', import.meta.url)));
const cams = JSON.parse(readFileSync(new URL('../../configs/q1q5/graphs/r004/camera_graph_v3.json', import.meta.url)));
const alias = JSON.parse(readFileSync(new URL('../../configs/q1q5/query_alias_v1.json', import.meta.url)));

test('every graph v3 region and camera has a row; no extra ids', () => {
  assert.deepEqual(Object.keys(PLACE_NAMES).sort(), graph.regions.map(r => r.region_id).sort());
  for (const c of cams.cameras) assert.ok(Object.hasOwn(CAMERA_NAMES, c.camera_id), c.camera_id);
  assert.ok(Object.hasOwn(CAMERA_NAMES, 'CAM_ENTRY'));   // search-only camera (D74), not in the tracking graph
});

test('PROPOSED names match the alias config; every row cites a source; UNKNOWN rows show the code', () => {
  for (const [id, e] of Object.entries(PLACE_NAMES)) if (e.status === 'PROPOSED') assert.equal(alias.region_aliases[e.name.replace(' ', '')], id);
  for (const e of [...Object.values(PLACE_NAMES), ...Object.values(CAMERA_NAMES)]) { assert.ok(['PROPOSED', 'DERIVED', 'UNKNOWN'].includes(e.status)); assert.ok(e.source.length > 10); }
  assert.equal(cameraName('CAM_WIDE'), 'CAM_WIDE'); assert.equal(cameraLabel('CAM_WIDE').known, false);
  assert.match(nameTitle('CAM_WIDE'), /UNKNOWN/);
  assert.ok(namesToConfirm().length >= 15);
});

test('readable names with the code kept for tooltips; a real catalog label wins; unknown ids pass through', () => {
  assert.equal(cameraName('CAM_W2'), '走廊（轉角端）');
  assert.deepEqual(placeLabel('VEST_W'), {name: '門廳', code: 'VEST_W', known: true});
  assert.equal(placeName('R101', 'R101'), '101 教室');      // catalog label that only repeats the code
  assert.equal(placeName('R101', '一〇一室'), '一〇一室');   // a run's own label wins
  assert.equal(placeName('XYZ'), 'XYZ'); assert.equal(cameraName('CAM_OTHER'), 'CAM_OTHER');
  assert.match(nameTitle('CAM_W2'), /CAM_W2/);
  assert.equal(presentCamera('CAM_W1'), '走廊（門廳端）'); assert.equal(presentCamera('CAM_A'), 'A');
});

test('search bar location chips and admin coverage use the readable names', () => {
  const run = {region_catalog: {regions: [{region_id: 'CORR_W', label: 'CORR_W'}]}, supported_classes: {class_labels: []}};
  assert.equal(chipsFromParse({location: ['CORR_W']}, run)[0].text, '走廊');
  const boot = {data_origin: 'LIVE', status: 'AVAILABLE', runs: [{scene_id: 's', run_id: 'r', camera_ids: ['CAM_W2'], region_graph: {regions: [{region_id: 'OUT_W'}, {region_id: 'CORNER'}]}}]};
  assert.deepEqual(buildOverview({bootstrap: boot}).regions.map(r => r.name), ['西入口外', '轉角']);
});

test('tracking card: readable camera, plain state and reasons, codes still listed', () => {
  const t = trackingCard({classLabel: 'person', cameraId: 'CAM_W2', state: 'OBSERVED', autoSeed: true, reasons: ['DEMO_DEFAULT', 'GRAPH_NOT_APPROVED', 'ASSOCIATION_IDENTITY_UNCONFIRMED', 'ASSOCIATION_AMBIGUOUS', 'NEW_CODE']}, null);
  assert.equal(t.camera.name, '走廊（轉角端）'); assert.equal(t.camera.code, 'CAM_W2');
  assert.equal(t.stateText, '鏡頭中看到'); assert.equal(t.stateCode, 'OBSERVED');
  assert.deepEqual(t.reasonChips.map(r => r.text), ['示範預設參數', '場景圖未核准', '跨鏡頭身分未確認', '跨鏡頭有多個候選']);
  assert.ok(t.reasons.includes('NEW_CODE'));   // unknown codes are never dropped
  assert.equal(trackingCard(null), null);
});
