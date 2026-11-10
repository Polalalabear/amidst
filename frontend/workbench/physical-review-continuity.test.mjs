import test from 'node:test';
import assert from 'node:assert/strict';
import {physicalReviewScenePlan,physicalReviewEvidenceFrame,physicalReviewEvidenceAt,physicalReviewPanelHTML,validatePhysicalReviewResponse,REVIEW_MARKER_LIMIT} from './physical-review.mjs';
import {officeReviewResult,officeSamples,OFFICE_CAMERAS,OFFICE_CANDIDATES} from './physical-review-office.fixture.mjs';

const [FRONT,REAR]=OFFICE_CAMERAS;
const grid=(from,to,step)=>{const out=[];for(let i=0;from+i*step<=to+1e-9;i++)out.push(Math.round((from+i*step)*1000)/1000);return out;};
const frameAt=(plan,t)=>physicalReviewEvidenceFrame(plan,t);
const keys=frame=>frame.samples.map(sample=>sample.evidence_key);

test('B1 scene plan keeps observation_ref and camera ids, never invents track or identity fields, and leaves XYZ untouched',()=>{
  const result=officeReviewResult(),before=structuredClone(result),plan=physicalReviewScenePlan(result);
  assert.equal(plan.samples.length,61);
  assert.equal(plan.samples.filter(sample=>typeof sample.observation_ref==='string').length,59);
  assert.ok(plan.samples.filter(sample=>sample.observation_ref===null).every(sample=>sample.state==='MISSING'&&sample.world_position===null));
  result.synchronized_evidence.samples.forEach((source,index)=>{
    const sample=plan.samples[index];
    assert.equal(sample.observation_ref,source.observation_ref);assert.equal(sample.camera_id,source.camera_id);
    assert.deepEqual(sample.source_camera_ids,source.source_camera_ids);assert.deepEqual(sample.candidate_refs,source.candidate_refs);
    assert.equal(sample.connect_from_previous,source.connect_from_previous);assert.deepEqual(sample.world_position,source.world_position);
    assert.equal(Object.keys(sample).some(key=>/track|person|identity/.test(key)),false);
  });
  assert.deepEqual(result,before);
  assert.deepEqual(plan.sample_limits,{sample_count:61,received_samples:61,maximum_samples:400,truncated:false,marker_limit_per_timestamp:REVIEW_MARKER_LIMIT});
});

test('B1 observation_ref stays optional for older DTOs but must be a bounded string when present',()=>{
  const legacy=officeReviewResult();legacy.synchronized_evidence.samples.forEach(sample=>{delete sample.observation_ref;});
  assert.ok(physicalReviewScenePlan(legacy).samples.every(sample=>sample.observation_ref===null));
  for(const bad of [5,'',{},'x'.repeat(257)]){
    const invalid=officeReviewResult();invalid.synchronized_evidence.samples[0].observation_ref=bad;
    assert.throws(()=>validatePhysicalReviewResponse(invalid));
  }
});

test('B2 disconnected segments at 0.4→0.6 and 1.8→2.0 start new evidence records with their own marker keys',()=>{
  const plan=physicalReviewScenePlan(officeReviewResult());
  for(const [before,after] of [[0.4,0.6],[1.8,2]]){
    const last=frameAt(plan,before),first=frameAt(plan,after);
    assert.equal(last.samples.length,1);assert.equal(first.samples.length,1);
    assert.equal(last.samples[0].segment_start,false);assert.equal(first.samples[0].segment_start,true);
    assert.notEqual(last.samples[0].evidence_key,first.samples[0].evidence_key);
    assert.notDeepEqual(last.samples[0].world_position,first.samples[0].world_position);
  }
  // Connected samples inside a segment are marked as continuations, and every observation has a unique key across the whole run.
  assert.equal(frameAt(plan,0.2).samples[0].segment_start,false);assert.equal(frameAt(plan,0.8).samples[0].segment_start,false);
  const all=grid(0,9.8,0.2).flatMap(t=>keys(frameAt(plan,t)));assert.equal(new Set(all).size,all.length);
  assert.ok(all.every(key=>/^observation:/.test(key)));
});

test('B3 duplicate rows for one observation collapse by observation_ref and keep the union of candidate and camera provenance',()=>{
  const result=officeReviewResult(),raw=result.synchronized_evidence.samples.filter(sample=>sample.timestamp===0.6);
  assert.equal(raw.length,2);
  const frame=frameAt(physicalReviewScenePlan(result),0.6),sample=frame.samples[0];
  assert.equal(frame.samples.length,1);assert.equal(frame.total,1);assert.equal(frame.omitted,0);
  assert.deepEqual(sample.world_position,raw[0].world_position);assert.equal(sample.observation_ref,raw[0].observation_ref);
  assert.deepEqual(sample.candidate_refs,Object.values(OFFICE_CANDIDATES).sort());
  assert.deepEqual(sample.source_camera_ids,[FRONT,REAR].sort());
});

test('B3 reordered and duplicated input yields identical frames at every tick',()=>{
  const result=officeReviewResult(),base=physicalReviewScenePlan(result),rows=base.samples;
  const reversed={...base,samples:[...rows].reverse()};
  const rotated={...base,samples:[...rows.slice(23),...rows.slice(0,23)]};
  const doubled={...base,samples:[...rows,...rows]};
  const interleaved={...base,samples:rows.map((_,index)=>rows[(index*7)%rows.length]).filter((row,index,all)=>all.indexOf(row)===index)};
  assert.equal(interleaved.samples.length,rows.length);
  for(const t of grid(0,9.8,0.1)){
    const expected=frameAt(base,t);
    for(const variant of [reversed,rotated,doubled,interleaved])assert.deepEqual(frameAt(variant,t),expected,`t=${t}`);
  }
});

test('B3 two observations at 4.4 s stay separate, ordered deterministically and distinguish the new segment',()=>{
  const plan=physicalReviewScenePlan(officeReviewResult()),frame=frameAt(plan,4.4);
  assert.equal(frame.samples.length,2);assert.equal(frame.omitted,0);
  const [first,second]=frame.samples;assert.notDeepEqual(first.world_position,second.world_position);assert.notEqual(first.evidence_key,second.evidence_key);
  assert.deepEqual(frame.samples.map(sample=>sample.segment_start).sort(),[false,true]);
  const restart=frame.samples.find(sample=>sample.segment_start),continuing=frame.samples.find(sample=>!sample.segment_start);
  assert.equal(restart.observation_ref,'observation:fe656e1bf939570f51f9ca73');assert.equal(continuing.observation_ref,'observation:add9f687d311742321e80dff');
  assert.deepEqual(physicalReviewEvidenceAt(plan,4.4),frame.samples);
});

test('B3 simultaneous FRONT and REAR evidence is never merged because XYZ or timestamp match',()=>{
  const result=officeReviewResult(),same=[2,3,.5];
  result.synchronized_evidence.samples=[
    {timestamp:5,world_position:[...same],state:'PROJECTED_OBSERVATION',camera_id:FRONT,observation_ref:'observation:front-1',connect_from_previous:false,source_camera_ids:[FRONT],candidate_refs:[OFFICE_CANDIDATES.a]},
    {timestamp:5,world_position:[...same],state:'PROJECTED_OBSERVATION',camera_id:REAR,observation_ref:'observation:rear-1',connect_from_previous:false,source_camera_ids:[REAR],candidate_refs:[OFFICE_CANDIDATES.a]},
    {timestamp:5,world_position:[...same],state:'PROJECTED_OBSERVATION',camera_id:FRONT,observation_ref:null,connect_from_previous:false,source_camera_ids:[FRONT],candidate_refs:[OFFICE_CANDIDATES.a]},
    {timestamp:5,world_position:[...same],state:'PROJECTED_OBSERVATION',camera_id:FRONT,observation_ref:null,connect_from_previous:false,source_camera_ids:[FRONT],candidate_refs:[OFFICE_CANDIDATES.b]}];
  result.synchronized_evidence.missing_intervals=[];
  const frame=frameAt(physicalReviewScenePlan(result),5);
  assert.equal(frame.samples.length,4);assert.equal(new Set(keys(frame)).size,4);
  assert.deepEqual(frame.samples.map(sample=>sample.camera_id).sort(),[FRONT,FRONT,FRONT,REAR].sort());
  // An exact repeat of an anonymous row is the same record and collapses; a conflicting row under one observation_ref keeps its own key.
  const repeat=officeReviewResult();repeat.synchronized_evidence.missing_intervals=[];
  const row={timestamp:5,world_position:[...same],state:'PROJECTED_OBSERVATION',camera_id:FRONT,observation_ref:null,connect_from_previous:false,source_camera_ids:[FRONT],candidate_refs:[OFFICE_CANDIDATES.a]};
  const conflict={...row,observation_ref:'observation:shared',world_position:[9,9,.5]};
  repeat.synchronized_evidence.samples=[row,structuredClone(row),conflict,{...conflict,world_position:[8,8,.5]}];
  const repeated=frameAt(physicalReviewScenePlan(repeat),5);
  assert.equal(repeated.samples.length,3);assert.equal(new Set(keys(repeated)).size,3);
});

test('B3 display limit is reported instead of silently dropping markers',()=>{
  const result=officeReviewResult();result.synchronized_evidence.missing_intervals=[];
  result.synchronized_evidence.samples=Array.from({length:REVIEW_MARKER_LIMIT+6},(_,index)=>({timestamp:5,world_position:[index,0,.5],state:'PROJECTED_OBSERVATION',camera_id:FRONT,
    observation_ref:`observation:many-${String(index).padStart(2,'0')}`,connect_from_previous:false,source_camera_ids:[FRONT],candidate_refs:[]}));
  const frame=frameAt(physicalReviewScenePlan(result),5);
  assert.equal(frame.samples.length,REVIEW_MARKER_LIMIT);assert.equal(frame.total,REVIEW_MARKER_LIMIT+6);assert.equal(frame.omitted,6);
  assert.deepEqual(frame.samples.map(sample=>sample.world_position[0]),Array.from({length:REVIEW_MARKER_LIMIT},(_,index)=>index));
  const truncated=officeReviewResult();Object.assign(truncated.synchronized_evidence,{truncated:true,sample_count:500,maximum_samples:400});
  const plan=physicalReviewScenePlan(truncated);assert.equal(plan.sample_limits.truncated,true);assert.equal(plan.sample_limits.sample_count,500);
  assert.match(physicalReviewPanelHTML(truncated),/來源取樣已截斷（500 筆中僅收 61 筆）/);
});

test('B4 no marker exists anywhere in the 4.4–8.6 s blind interval, including 4.6–8.4 s, and nothing is held or interpolated',()=>{
  const result=officeReviewResult(),plan=physicalReviewScenePlan(result);
  assert.ok(frameAt(plan,4.4).samples.length>0);
  for(const t of [...grid(4.45,8.55,0.05),5.2,6.5,5.0,7.0])assert.deepEqual(frameAt(plan,t),{samples:[],total:0,omitted:0},`t=${t}`);
  for(const t of grid(4.6,8.4,0.2))assert.equal(physicalReviewEvidenceAt(plan,t).length,0);
  // Rows before and after the gap hold the only positions; MISSING rows carry none.
  const timestamps=new Set(plan.samples.filter(sample=>sample.world_position).map(sample=>sample.timestamp));
  assert.ok(grid(4.6,8.4,0.2).every(t=>!timestamps.has(t)));
  assert.ok(plan.samples.filter(sample=>sample.state==='MISSING').every(sample=>sample.world_position===null));
});

test('B4 reappearance at 8.6 s is a new FRONT→REAR observation with its own key and no link to the last FRONT sample',()=>{
  const plan=physicalReviewScenePlan(officeReviewResult()),before=frameAt(plan,4.4),after=frameAt(plan,8.6);
  assert.equal(after.samples.length,1);const [sample]=after.samples;
  assert.equal(sample.camera_id,REAR);assert.equal(sample.segment_start,true);assert.equal(sample.observation_ref,'observation:997166541f223b4f923d8bff');
  assert.ok(before.samples.every(prior=>prior.camera_id===FRONT&&prior.evidence_key!==sample.evidence_key));
  assert.deepEqual(frameAt(plan,8.5),{samples:[],total:0,omitted:0});assert.equal(frameAt(plan,8.8).samples[0].segment_start,false);
});

test('B2 candidate switching and item switching never change observation marker identity or XYZ',()=>{
  const result=officeReviewResult(),base=frameAt(physicalReviewScenePlan(result),2);
  const swapped=structuredClone(result);
  for(const sample of swapped.synchronized_evidence.samples)sample.candidate_refs=[...sample.candidate_refs].reverse();
  swapped.synchronized_evidence.samples.reverse();
  const next=frameAt(physicalReviewScenePlan(swapped),2);
  assert.deepEqual(keys(next),keys(base));assert.deepEqual(next.samples.map(sample=>sample.world_position),base.samples.map(sample=>sample.world_position));
  const another=structuredClone(result),second=structuredClone(result.items[0]);second.item_ref='review-item:'+'2'.repeat(24);second.checklist[0].check_ref='review-check:'+'2'.repeat(24);another.items.push(second);
  assert.deepEqual(keys(frameAt(physicalReviewScenePlan(another,'review-item:'+'2'.repeat(24)),2)),keys(base));
});

test('B1/B4 original XYZ values are unchanged by plan building, framing and repeated ticks',()=>{
  const result=officeReviewResult(),original=officeSamples().filter(sample=>sample.world_position).map(sample=>JSON.stringify(sample.world_position));
  const plan=physicalReviewScenePlan(result),planBefore=structuredClone(plan);
  for(const t of grid(0,9.8,0.05))frameAt(plan,t);
  assert.deepEqual(plan,planBefore);
  assert.deepEqual(plan.samples.filter(sample=>sample.world_position).map(sample=>JSON.stringify(sample.world_position)),original);
  const shown=new Set(grid(0,9.8,0.2).flatMap(t=>frameAt(plan,t).samples.map(sample=>JSON.stringify(sample.world_position))));
  assert.ok([...shown].every(position=>original.includes(position)));
});

test('B5 legend separates projected observations, inferred points, segment starts and missing intervals without claiming confirmed positions',()=>{
  const html=physicalReviewPanelHTML(officeReviewResult());
  assert.match(html,/青綠＝影像投影觀測（來源取樣，非已確認的人員位置）/);assert.match(html,/外環＝新片段起點/);assert.match(html,/共 5 處/);
  assert.match(html,/缺失區間不顯示任何位置/);assert.match(html,/每個時間點最多顯示 24 個標記/);assert.doesNotMatch(html,/已確認(?:的)?人員位置(?!）)|同一人連續移動(?!）)/);
});
