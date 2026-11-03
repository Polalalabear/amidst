import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
import {wallLayout,stateAt,wallCells,summary,lanes,q1Clips,longestClips,WALL_MAX} from './monitor-wall-model.mjs';
import {createView} from './timeline-model.mjs';
const fx=JSON.parse(readFileSync(new URL('./fixtures/long_timeline_synthetic.json',import.meta.url),'utf8'));
test('fixture is marked synthetic with 8 cameras and no media/GT fields',()=>{assert.equal(fx.fixture_marker,'FIXTURE');assert.match(fx.SYNTHETIC,/合成/);assert.equal(fx.cameras.length,8);assert.doesNotMatch(JSON.stringify(fx),/media_url|file_sha256|gt_|trajectory/i);
  for(const c of fx.cameras){assert.equal(c.segments[0].range_us[0],0);assert.equal(c.segments.at(-1).range_us[1],fx.source_duration_us);c.segments.forEach((s,i)=>{if(i)assert.equal(s.range_us[0],c.segments[i-1].range_us[1]);});}});
test('wallLayout: 8 -> 4x2, every count 0..8 fits, >8 rejected',()=>{assert.deepEqual(wallLayout(8),{cols:4,rows:2});for(let n=0;n<=WALL_MAX;n++){const l=wallLayout(n);assert.ok(l.cols*l.rows>=n);}assert.throws(()=>wallLayout(9),/WALL_COUNT/);assert.throws(()=>wallLayout(-1),/WALL_COUNT/);});
test('stateAt is half-open and uncovered time is UNKNOWN, never OBSERVED',()=>{const s=[{range_us:[10,20],state:'OBSERVED'},{range_us:[20,30],state:'GAP'}];
  assert.equal(stateAt(s,10).state,'OBSERVED');assert.equal(stateAt(s,19).state,'OBSERVED');assert.equal(stateAt(s,20).state,'GAP');assert.equal(stateAt(s,30).state,'UNKNOWN');assert.equal(stateAt(s,5).state,'UNKNOWN');assert.equal(stateAt(undefined,5).state,'UNKNOWN');assert.equal(stateAt([{range_us:[0,9],state:'BOGUS'}],1).state,'UNKNOWN');});
test('wallCells covers all 8 cameras at any time, summary adds up',()=>{for(const t of [0,1234e6,fx.source_duration_us-1]){const cells=wallCells(fx.cameras,t);assert.equal(cells.length,8);assert.equal(Object.values(summary(cells)).reduce((a,b)=>a+b),8);assert.ok(cells.every(c=>c.segment_range_us));}
  assert.throws(()=>wallCells([...fx.cameras,{camera_id:'x'}],0),/WALL_COUNT/);assert.equal(wallCells(fx.cameras,fx.source_duration_us)[0].state,'UNKNOWN');});
test('fixture camera 7 is MISSING through 900-1500 s (designed blind stretch)',()=>{const c=fx.cameras[6];for(const t of [1000e6,1400e6])assert.equal(stateAt(c.segments,t).state,'MISSING');});
test('lanes clip states and Q1 clips to the same window',()=>{const v=createView(fx.source_duration_us,[0,600e6]);const l=lanes(fx.cameras,fx.q1_clips,v);assert.equal(l.length,8);
  assert.ok(l.every(x=>x.states.every(s=>s.left>=0&&s.left+s.width<=100+1e-9)));assert.deepEqual(l[7].q1,[]);assert.ok(l[0].q1.every(s=>s.range_us[0]<600e6));});
test('q1Clips keeps only declared fields; longestClips filters by duration and sorts',()=>{
  const r={results:[{camera_id:'B',matched_segments:[{range_us:[5e6,9e6],matched_frames:3,evaluated_frames:4,extra:1}]},{camera_id:'A',matched_segments:[{range_us:[0,2e6],matched_frames:1,evaluated_frames:1}]}]};
  const c=q1Clips(r);assert.deepEqual(c.B[0],{range_us:[5e6,9e6],matched_frames:3,evaluated_frames:4});assert.deepEqual(q1Clips(null),{});
  assert.deepEqual(longestClips(c,3e6),[{camera_id:'B',range_us:[5e6,9e6]}]);assert.equal(longestClips(c,0).length,2);assert.equal(longestClips(c,0)[0].camera_id,'A');});
