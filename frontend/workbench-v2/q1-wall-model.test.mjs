import test from 'node:test';import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';
import {wallModel,seedRequest,overlayBoxes,coverageText} from './q1-wall-model.mjs';import {parseRaw,checkRequest} from './q-validate.mjs';
const pack=async n=>JSON.parse(await readFile(new URL(`./fixtures/${n}.json`,import.meta.url),'utf8'));
const response=async n=>parseRaw((await pack(n)).cases[0].response_json);
const ready=await response('q1-ready');const run=parseRaw((await pack('q-bootstrap')).bootstrap_json).runs[0];
test('three groups preserve source order and remain disjoint',()=>{const r=structuredClone(ready);r.not_evaluated_cameras=[{camera_id:'UNSEEN',coverage:{not_inferred_frames:1}}];const m=wallModel(r);assert.deepEqual(m.groups.matches.map(x=>x.rank),[1,2]);assert.deepEqual(m.groups.noMatch.map(x=>x.camera_id),['E']);assert.equal(m.groups.notEvaluated[0].camera_id,'UNSEEN');assert.equal(m.groups.matches,r.results);});
for(const size of [1,2,4,8])test(`${size}-tile layout never duplicates or renumbers ranks`,()=>{const m=wallModel(ready,{size,page:1});assert.equal(m.tiles.length,size);assert.equal(new Set(m.tiles.filter(Boolean).map(x=>x.camera_id)).size,m.tiles.filter(Boolean).length);assert.deepEqual(m.tiles.filter(Boolean).map(x=>x.rank),size===1?[2]:[1,2]);});
for(const [file,phrase] of [['q1-no-match','在已推論的影格中沒有找到'],['q1-out-of-range','沒有交集，沒有查詢'],['q1-partial','未涵蓋部分沒有資料']])test(`${file} distinct uncertainty wording`,async()=>assert.match(wallModel(await response(file)).message,new RegExp(phrase)));
test('timeout partial does not imply absence',()=>assert.match(wallModel({...ready,status:'PARTIAL',reason:'TIME_BUDGET'}).message,/僅顯示已評估部分/));
test('Q2 observation seed is exactly a returned representative with original requested time',()=>{const result=ready.results[0],segment=result.matched_segments[0];const q=seedRequest(ready,result,segment,run,'SYNTHETIC');assert.equal(checkRequest('q2',q),q);assert.equal(q.seed.observation_id,segment.representative.observation_ids[0]);assert.deepEqual(q.time,ready.resolved_scope.requested_time);assert.equal(q.switch_mode,'RULE_ONLY');assert.throws(()=>seedRequest(ready,result,{...segment},run,'SYNTHETIC'),/UNBOUND_SEGMENT/);});
test('multiple observation choices cannot be silently auto-selected',()=>{const r=structuredClone(ready),a=r.results[0],s=a.matched_segments[0];s.representative.observation_ids.push('obs:FICT_OTHER');assert.throws(()=>seedRequest(r,a,s,run,'SYNTHETIC'),/SELECTION_REQUIRED/);assert.equal(seedRequest(r,a,s,run,'SYNTHETIC','RULE_ONLY','obs:FICT_OTHER').seed.observation_id,'obs:FICT_OTHER');});
test('last backend page preserves total separate from returned and original ranks',()=>{const last={...ready,results:[ready.results[1]],returned_count:1,next_cursor:null};const m=wallModel(last);assert.equal(m.total,2);assert.equal(m.returned,1);assert.equal(m.tiles[0].rank,2);});
test('raw boxes are clipped only for presentation and require matching frame/camera',()=>{const raw={observation_id:'obs:FICT',frame_ref:'frame:FICT',camera_id:'CAM_FICT',bbox_xyxy_px:[-5,5,12,20]};const box=overlayBoxes([raw],{width:10,height:10,frameRef:raw.frame_ref,cameraId:raw.camera_id})[0];assert.deepEqual(raw.bbox_xyxy_px,[-5,5,12,20]);assert.deepEqual([box.left,box.top,box.right,box.bottom],[0,50,100,100]);assert.deepEqual(overlayBoxes([raw],{width:10,height:10,frameRef:'other',cameraId:raw.camera_id}),[]);});
test('coverage keeps missing separate from not-inferred',()=>assert.equal(coverageText({evaluated_frames:2,missing_frames:3,not_sampled_frames:4,not_inferred_frames:5}),'已推論 2 · 未取樣 4 · 未推論 5 · MISSING 3'));

test('overlay follows letterboxed RGB plane, not the outer tile',()=>{const b=overlayBoxes([{observation_id:'obs:FICT',frame_ref:'frame:FICT',camera_id:'FICT',bbox_xyxy_px:[0,0,100,100]}],{width:100,height:100,containerWidth:200,containerHeight:100,frameRef:'frame:FICT',cameraId:'FICT'})[0];assert.deepEqual([b.left,b.top,b.right,b.bottom],[25,0,75,100]);});
import {wallSelection,wallStamps,groupByStamp,cameraRange} from './q1-wall-model.mjs';
test('wall playback spans every hit camera and freezes a camera outside its own range on a legal frame',()=>{
  const seg=r=>({range_us:r}),a={camera_id:'A',matched_segments:[seg([1000000,2000000])]},b={camera_id:'B',matched_segments:[seg([1500000,3000000]),seg([3500000,4000000])]},none={camera_id:'C',matched_segments:[]};
  assert.deepEqual(cameraRange(b),[1500000,4000000]);assert.equal(cameraRange(none),null);
  assert.deepEqual(wallSelection([a,b,none]),{kind:'Q1_SEGMENT',camera_id:null,range_us:[1000000,4000000]});assert.equal(wallSelection([none]),null);
  const at=t=>wallStamps([a,b,none],t,()=>50000);
  assert.deepEqual(at(1200000),[{camera_id:'A',stamp:1200000,outside:false},{camera_id:'B',stamp:1500000,outside:true}]);
  assert.deepEqual(at(3000000),[{camera_id:'A',stamp:1950000,outside:true},{camera_id:'B',stamp:2950000,outside:true}]);// 3000000 is B's gap start (end-exclusive)
  assert.deepEqual(at(3500000)[1],{camera_id:'B',stamp:3500000,outside:false});
  assert.deepEqual([...groupByStamp(at(1500000))],[[1500000,['A','B']]]);
});
test('wallStamps uses the half-open union: gaps are outside, nearest legal frame, ties go to the earlier point',()=>{
  const cam=(...r)=>({camera_id:'G',matched_segments:r.map(range_us=>({range_us}))}),at=(c,t)=>wallStamps([c],t,()=>1)[0];
  const gap=cam([0,1000000],[3000000,4000000]);
  assert.deepEqual(at(gap,2000000),{camera_id:'G',stamp:3000000,outside:true});// Codex repro: gap midpoint is not a hit; 3000000 is nearer than 999999
  assert.deepEqual(at(gap,1000000),{camera_id:'G',stamp:999999,outside:true});// end is exclusive
  assert.equal(at(gap,999999).outside,false);assert.equal(at(gap,3000000).outside,false);assert.equal(at(gap,3999999).outside,false);
  assert.deepEqual(at(gap,4000000),{camera_id:'G',stamp:3999999,outside:true});assert.deepEqual(at(gap,-5),{camera_id:'G',stamp:0,outside:true});
  const tie=cam([0,1000000],[3000001,4000000]);// 999999 and 3000001 are both 1000001 from 2000000
  assert.deepEqual(at(tie,2000000),{camera_id:'G',stamp:999999,outside:true});
  assert.equal(at(tie,3000001).outside,false);assert.equal(at(tie,3000000).outside,true);
  assert.deepEqual(wallSelection([gap]).range_us,[0,4000000]);// envelope still drives the wall's play range
});
