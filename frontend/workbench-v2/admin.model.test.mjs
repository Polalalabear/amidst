import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runCatalog,recordingCatalog,filterRuns,filterRecordings,parseTimecode,formatDuration,selectionFor,isSelected} from './admin.model.mjs';

const mk=(id,scene,cams,dur)=>({scene_id:scene,run_id:id,camera_ids:cams,source_kind:'SYNTHETIC',sampling:{per_camera:[{source_frame_interval_us:50000}]},clock_mapping:{source_duration_us:dur}});
const bootstrap={runs:[mk('r1','P1',['A','B'],8000000),mk('r2','R004',['C1','C2','C3'],50000000)],
  recordings:[{recording_id:'a'.repeat(32),recorded_at:'2026-10-30T10:00:00Z',source_kind:'ENGINEERING',response_kind:'q2',switch_mode:'RULE_ONLY'},
    {recording_id:'b'.repeat(32),recorded_at:'2026-11-01T09:00:00Z',source_kind:'SYNTHETIC',response_kind:'q1',title:'A4-1 追蹤'},
    {recording_id:'c'.repeat(32),source_kind:'SYNTHETIC',response_kind:'q1'}]};

test('catalog lists runs with cameras/duration/fps and falls back to IDs when no title exists', () => {
  const runs=runCatalog(bootstrap);
  assert.equal(runs.length,2);assert.equal(runs[0].fps,20);assert.equal(runs[0].duration_us,8000000);assert.equal(runs[0].title,'P1 · r1');assert.equal(runs[0].titleMissing,true);
  const recs=recordingCatalog(bootstrap);
  assert.equal(recs[0].title,'a'.repeat(32));assert.equal(recs[0].titleMissing,true);
  assert.equal(recs[1].title,'A4-1 追蹤');assert.equal(recs[1].titleMissing,false);
  assert.deepEqual(runCatalog(null),[]);
});

test('filter runs by scene, camera, source kind and source time', () => {
  const runs=runCatalog(bootstrap);
  assert.deepEqual(filterRuns(runs,{scene:'r004'}).map(x=>x.run_id),['r2']);
  assert.deepEqual(filterRuns(runs,{camera:'b'}).map(x=>x.run_id),['r1']);
  assert.deepEqual(filterRuns(runs,{camera:'c2'}).map(x=>x.run_id),['r2']);
  assert.deepEqual(filterRuns(runs,{from_us:10000000}).map(x=>x.run_id),['r2'],'8 s run has nothing after 10 s');
  assert.equal(filterRuns(runs,{source_kind:'FORMAL'}).length,0);
  assert.equal(filterRuns(runs,{}).length,2);
});

test('filter recordings by text, source kind and recorded time; undated ones never match a time filter', () => {
  const recs=recordingCatalog(bootstrap);
  assert.equal(filterRecordings(recs,{text:'A4-1'}).length,1);
  assert.equal(filterRecordings(recs,{source_kind:'SYNTHETIC'}).length,2);
  assert.equal(filterRecordings(recs,{from:'2026-11-01'}).length,1);
  assert.equal(filterRecordings(recs,{to:'2026-10-31'}).length,1);
  assert.equal(filterRecordings(recs,{from:'2026-10-01',to:'2026-12-01'}).length,2);
  assert.equal(filterRecordings(recs,{}).length,3);
});

test('timecodes parse to integer microseconds; garbage is null', () => {
  assert.equal(parseTimecode('0:05'),5000000);assert.equal(parseTimecode('1:02:03'),3723000000);assert.equal(parseTimecode('2.5'),2500000);
  assert.equal(parseTimecode(''),null);assert.equal(parseTimecode('a:b'),null);assert.equal(parseTimecode('1:2:3:4'),null);
  assert.equal(formatDuration(8000000),'0:08');assert.equal(formatDuration(50000000),'0:50');
});

test('picking an item produces the selection the wall reads', () => {
  const [run]=runCatalog(bootstrap),[rec]=recordingCatalog(bootstrap);
  assert.deepEqual(selectionFor(run),{kind:'run',scene_id:'P1',run_id:'r1'});
  assert.deepEqual(selectionFor(rec),{kind:'recording',recording_id:'a'.repeat(32)});
  assert.equal(isSelected(run,selectionFor(run)),true);assert.equal(isSelected(rec,selectionFor(run)),false);assert.equal(isSelected(run,null),false);
});

test('shipped pages wire the wall and the admin link; wall stays out of UI-A and demo-mode files', () => {
  const index=readFileSync(new URL('./index.html',import.meta.url),'utf8');
  assert.match(index,/id="monitor-room-slot"/);assert.match(index,/href="admin\.html"/);assert.match(index,/monitor-room\.css/);
  const admin=readFileSync(new URL('./admin.html',import.meta.url),'utf8');
  for(const id of ['admin-event-rows','admin-play','admin-speed','admin-start','admin-restart','admin-record-rows','admin-preview'])assert.match(admin,new RegExp(`id="${id}"`));
  for(const f of ['monitor-room-view.mjs','monitor-room-model.mjs','admin.model.mjs','admin.mjs']){
    const src=readFileSync(new URL('./'+f,import.meta.url),'utf8');
    assert.doesNotMatch(src,/\bgt_|ground_truth|visibility|depth/i,`${f} must not read GT/depth/visibility`);
  }
});
