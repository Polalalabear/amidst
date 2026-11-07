import test from 'node:test';
import assert from 'node:assert/strict';
import {buildCoreSearchRequest, buildCoreTrackRequest, singleViewSequence} from './core-search-track-model.mjs';
import {buildSearchRequest} from './search-dialog-model.mjs';

const run = {scene_id:'SYNTHETIC_SCENE',run_id:'SYNTHETIC_RUN',
  clock_mapping:{wall_origin:'2026-11-01T13:00:00+08:00',timezone:'Asia/Taipei',source_duration_us:2000000}};
const menus = {regions:['SYN_ROOM'],classes:['person'],colors:[]};
const form = {start:'13:00:00',end:'13:00:01',classLabel:'person',colorLabel:'',regionIds:[]};

test('core wall ranges retain source microseconds and compare equivalent ISO forms', () => {
  for (const [start,end] of [['13:00:00.000001','13:00:00.000002'],
    ['13:00:00.9','13:00:01'],['13:00:00','13:00:00.000001']]) {
    assert.equal(buildCoreSearchRequest(run,'SYN_SESSION',{...form,start,end},menus).time.kind,'WALL');
  }
  assert.throws(() => buildCoreSearchRequest(run,'SYN_SESSION',{...form,start:'13:00:00.000002',end:'13:00:00.000001'},menus),/TIME_ORDER/);
  assert.throws(() => buildCoreSearchRequest(run,'SYN_SESSION',{...form,start:'13:00:00.0000001'},menus),/TIME_INVALID/);
});

test('core wall ranges reject impossible calendar days instead of normalizing them', () => {
  assert.throws(() => buildCoreSearchRequest(run,'SYN_SESSION',{...form,
    start:'2026-02-30T13:00:00+08:00',end:'2026-02-30T13:00:01+08:00'},menus),/TIME_INVALID/);
});

test('zero playback now remains an empty past window and legacy form cannot query the future', () => {
  const blank = {...form,start:'',end:'',mode:'track'};
  const q = buildCoreTrackRequest(run,'SYN_SESSION',blank,menus,0);
  assert.equal(q.time,null);
  assert.equal(q.playback_now_us,0);
  assert.throws(() => buildSearchRequest(run,'SYN_SESSION',{...blank,allowNowTime:true,playbackNowUs:0}),/TIME_INVALID/);
});

test('overlapping sightings on the current camera keep it selected while visible', () => {
  assert.deepEqual(singleViewSequence([
    {camera_id:'SYN_A',range_us:[0,5]}, {camera_id:'SYN_A',range_us:[4,10]},
    {camera_id:'SYN_B',range_us:[3,20]},
  ],{asOfUs:20}),[
    {kind:'ON_CAMERA',camera_id:'SYN_A',range_us:[0,10],evidence_state:'OBSERVED'},
    {kind:'ON_CAMERA',camera_id:'SYN_B',range_us:[10,20],evidence_state:'OBSERVED'},
  ]);
});
