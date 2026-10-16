import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {blindHypothesisFromResponse,blindHypothesisPlan,blindHypothesisRegionAt,blindHypothesisEnvelope,blindHypothesisStatusHTML,blindHypothesisLegendHTML,
  blindReasonText,insideBlindInterval,LEGEND_ITEMS,UNCONFIRMED_LABEL,HYPOTHESIS_COLOR} from './blind-hypothesis.mjs';
import {crossCameraCandidateHTML,crossCameraPanelHTML} from './cross-camera.mjs';

// MOCK, contract-shaped, not real data: K1 output on synthetic maps (fixtures/generate_blind_hypothesis_fixtures.py).
const fixture=JSON.parse(readFileSync(new URL('./fixtures/blind-hypothesis.fixture.json',import.meta.url),'utf8'));
const cases=()=>structuredClone(fixture.cases);
const projected=(timestamp,world_position,camera_id)=>({timestamp,world_position,state:'PROJECTED_OBSERVATION',camera_id,connect_from_previous:false});
// A candidate path with FRONT at 4.4 s and REAR at 8.6 s: the blind interval in between stays a MISSING gap.
const association=()=>({schema_version:'workbench.blender-association.v1',status:'READY',agent_used:false,selection:{camera_ids:['CAM_A','CAM_B'],time_range:[4,9],top_k:3},
  candidates:[{rank:1,score:1,selected_edge_refs:[],unassociated_node_refs:[],paths:[{camera_ids:['CAM_A','CAM_B'],canonical_time_range:[4,9],
    samples:[projected(4,[1.8,3,.5],'CAM_A'),projected(4.4,[2,3,.5],'CAM_A'),{timestamp:6,world_position:null,state:'MISSING'},projected(8.6,[8,3,.5],'CAM_B'),projected(9,[8.2,3,.5],'CAM_B')],
    gaps:[{time_range:[4.6,8.4],reason:'CROSS_CAMERA_LONG_GAP'}]}]}],baseline_candidate:null,graph:{nodes:[],edges:[]},camera_coverage:[]});

test('fixtures are labelled MOCK and contract-shaped',()=>{
  assert.match(fixture.fixture_note,/MOCK/);
  for(const response of Object.values(fixture.cases)){
    assert.equal(response.fixture_note,'MOCK, contract-shaped, not real data');
    assert.equal(response.schema_version,'workbench.blind-hypothesis.v1');
    assert.equal(response.evidence_state,'INFERRED_HYPOTHESIS');assert.equal(response.physical_authority,'UNKNOWN');assert.equal(response.identity_verdict,'UNCONFIRMED');
  }
});

test('READY response becomes a K>=3 path bundle with per-time regions and no target position',()=>{
  const plan=blindHypothesisPlan(cases().ready);
  assert.equal(plan.status,'READY');assert.ok(plan.paths.length>=3);
  assert.deepEqual(plan.interval,{start_s:4.4,end_s:8.6,duration_s:plan.interval.duration_s});
  assert.deepEqual(plan.paths.map(path=>path.rank),plan.paths.map((_,index)=>index+1));
  // Opacity is a rank cue: strictly decreasing, always translucent.
  for(const [index,path] of plan.paths.entries()){assert.ok(path.opacity>0&&path.opacity<1);if(index)assert.ok(path.opacity<plan.paths[index-1].opacity);}
  for(const path of plan.paths){assert.ok(path.points.length>0);assert.ok(path.samples.every(s=>s.timestamp_s>4.4&&s.timestamp_s<8.6));assert.equal(path.unconfirmed,false);}
  assert.ok(plan.regions.length>0&&plan.regions.every(r=>r.timestamp_s>4.4&&r.timestamp_s<8.6&&r.cells.length>0));
  assert.equal(plan.reason,null);assert.deepEqual(plan.substitutions,[]);
  // No field of the plan carries a single "current" target position.
  assert.equal('position' in plan,false);assert.equal('target' in plan,false);
  // The plan never fills the response and does not mutate the input.
  const response=cases().ready,before=JSON.stringify(response);blindHypothesisPlan(response);assert.equal(JSON.stringify(response),before);
});

test('UNKNOWN draws no path, no region and no position, and says why in Chinese',()=>{
  const plan=blindHypothesisPlan(cases().unknown);
  assert.equal(plan.status,'UNKNOWN');assert.equal(plan.reason,'ENDPOINTS_UNREACHABLE');assert.match(plan.reasonText,/無法連通/);
  assert.deepEqual(plan.paths,[]);assert.deepEqual(plan.regions,[]);
  for(const t of [4.4,4.6,6,8.4,8.6])assert.equal(blindHypothesisRegionAt(plan,t),null);
  assert.deepEqual(blindHypothesisEnvelope(plan),[]);assert.equal(insideBlindInterval(plan,6),false);
  const html=blindHypothesisStatusHTML(plan);
  assert.match(html,/data-status="UNKNOWN"/);assert.match(html,/data-blind-reason="ENDPOINTS_UNREACHABLE"/);assert.match(html,/位置 UNKNOWN/);assert.match(html,/不畫路徑與範圍/);
});

test('every contract fail-closed reason has a Chinese explanation, unknown codes are shown as unlisted',()=>{
  const codes=['ENDPOINT_UNUSABLE','ENDPOINT_SUBSTITUTION_INVALID','INTERVAL_INVALID','INTERVAL_TOO_LONG','WALKABLE_ANNOTATION_UNAVAILABLE','SPEED_CONFIG_UNAVAILABLE',
    'ENDPOINT_OUTSIDE_WALKABLE','ENDPOINTS_UNREACHABLE','REACHABLE_SET_EMPTY','NEGATIVE_EVIDENCE_INVALID','NEGATIVE_EVIDENCE_NOT_APPEND_ONLY','NO_HYPOTHESIS_PASSED_CHECKS',
    'PRUNING_RERUN_NOT_IMPLEMENTED','SEARCH_BUDGET_EXHAUSTED','PROVENANCE_MISMATCH'];
  for(const code of codes){assert.match(blindReasonText(code),/[一-鿿]/,code);assert.ok(!blindReasonText(code).includes(code));}
  assert.match(blindReasonText('SOMETHING_NEW'),/SOMETHING_NEW/);assert.match(blindReasonText(null),/原因未提供/);
  const unknown={...cases().unknown,reason:'NO_HYPOTHESIS_PASSED_CHECKS'};
  assert.match(blindHypothesisPlan(unknown).reasonText,/沒有路徑通過/);
});

test('D7 endpoint substitution is shown with the original reference, time, UNKNOWN reason, substitute and signed offset',()=>{
  const plan=blindHypothesisPlan(cases().substituted_unconfirmed);
  assert.equal(plan.interval.start_s,4.2);assert.equal(plan.substitutions.length,1);
  const [notice]=plan.substitutions;
  assert.equal(notice.endpoint,'START');assert.equal(notice.original_observation_ref,'obs:front-4.4');assert.equal(notice.substitute_observation_ref,'obs:front-4.2');
  assert.match(notice.text,/起點已替代/);assert.match(notice.text,/obs:front-4\.4/);assert.match(notice.text,/4\.4 s/);assert.match(notice.text,/UNKNOWN/);assert.match(notice.text,/頭部錨點不可靠/);
  assert.match(notice.text,/obs:front-4\.2/);assert.match(notice.text,/4\.2 s/);assert.match(notice.text,/−0\.2 s/);
  const html=blindHypothesisStatusHTML(plan);assert.match(html,/data-blind-notice/);assert.match(html,/起點已替代/);
  // The substituted interval is the interval used; no sample sits at the substitute or original time.
  assert.ok(plan.paths.every(path=>path.samples.every(s=>s.timestamp_s>4.2)));
  assert.equal(blindHypothesisRegionAt(plan,4.2),null);assert.equal(blindHypothesisRegionAt(plan,4.4).timestamp_s,4.4);
  const later=cases().substituted_unconfirmed;later.endpoint_substitutions=[{...later.endpoint_substitutions[0],endpoint:'END',time_offset_s:0.3}];
  assert.match(blindHypothesisPlan(later).substitutions[0].text,/終點已替代.*\+0\.3 s/);
});

test('D11 paths through an unconfirmed area keep their rank but are labelled and styled apart from verified paths',()=>{
  const plan=blindHypothesisPlan(cases().substituted_unconfirmed);
  const flagged=plan.paths.filter(path=>path.unconfirmed),verified=plan.paths.filter(path=>!path.unconfirmed);
  assert.ok(flagged.length>=1&&verified.length>=1);
  for(const path of flagged){assert.equal(path.unconfirmedLabel,UNCONFIRMED_LABEL);assert.ok(path.unconfirmedLinks.length>0);}
  for(const path of verified)assert.equal(path.unconfirmedLabel,null);
  assert.deepEqual(plan.paths.map(path=>path.rank),[1,2,3]);
  assert.ok(plan.regions.some(region=>region.cells.some(cell=>cell.unconfirmed)));
  assert.ok(plan.notices.some(text=>text.includes(UNCONFIRMED_LABEL)&&text.includes('未確認')));
  assert.ok([...UNCONFIRMED_LABEL].length<=6);
});

test('absent or foreign fields give no plan, so no layer appears',()=>{
  for(const value of [undefined,null,{},{status:'READY'},{schema_version:'workbench.target-reconstruction.v1'},{schema_version:'workbench.target-reconstruction.v1',blind_hypotheses:null},'x',3])
    assert.equal(blindHypothesisPlan(value),null,JSON.stringify(value));
  assert.equal(blindHypothesisFromResponse({blind_hypotheses:{schema_version:'other'}}),null);
  // Both candidate locations for the field (BH-Q1) are accepted; no other key is read.
  const response=cases().ready;
  assert.equal(blindHypothesisFromResponse(response),response);
  assert.equal(blindHypothesisFromResponse({schema_version:'workbench.target-reconstruction.v1',blind_hypotheses:response}),response);
  assert.equal(blindHypothesisFromResponse({schema_version:'workbench.target-reconstruction.v1',hypotheses:response}),null);
  assert.equal(blindHypothesisStatusHTML(null),'');assert.deepEqual(blindHypothesisEnvelope(null),[]);assert.equal(blindHypothesisRegionAt(null,6),null);
});

test('malformed READY responses fail closed instead of drawing partial hypotheses',()=>{
  const mutate=change=>{const response=cases().ready;change(response);return blindHypothesisPlan(response);};
  for(const [name,change] of Object.entries({
    badEvidenceState:r=>{r.evidence_state='PROJECTED_OBSERVATION';},
    probabilityBasis:r=>{r.ranking_basis='PROBABILITY';},
    nonHypothesisSample:r=>{r.hypotheses[0].samples[2].evidence_state='PROJECTED_OBSERVATION';},
    nonFinitePosition:r=>{r.hypotheses[0].samples[0].position_m=[1,NaN,0];},
    polygonKind:r=>{r.reachable_regions[0].kind='POLYGON';},
    noRegions:r=>{r.reachable_regions=[];},
    noActivePaths:r=>{r.hypotheses=[];},
    badInterval:r=>{r.interval.end_s=r.interval.start_s;}})){
    const plan=mutate(change);
    assert.equal(plan.status,'UNKNOWN',name);assert.equal(plan.reason,'INVALID_RESPONSE',name);assert.deepEqual(plan.paths,[],name);assert.deepEqual(plan.regions,[],name);
  }
  const pruned=cases().ready;pruned.hypotheses[0].status='PRUNED';
  assert.equal(blindHypothesisPlan(pruned).paths.length,pruned.hypotheses.length-1);
});

test('reachable region follows the clock: shown only strictly inside the interval and within half a step of a region',()=>{
  const plan=blindHypothesisPlan(cases().ready);
  assert.equal(blindHypothesisRegionAt(plan,4.4),null);assert.equal(blindHypothesisRegionAt(plan,8.6),null);
  assert.equal(blindHypothesisRegionAt(plan,3),null);assert.equal(blindHypothesisRegionAt(plan,12),null);assert.equal(blindHypothesisRegionAt(plan,NaN),null);
  assert.equal(blindHypothesisRegionAt(plan,4.6).timestamp_s,4.6);assert.equal(blindHypothesisRegionAt(plan,6.04).timestamp_s,6);
  assert.equal(blindHypothesisRegionAt(plan,8.4).timestamp_s,8.4);
  const shown=[4.6,6,8.4].map(t=>blindHypothesisRegionAt(plan,t));
  assert.notDeepEqual(shown[0].cells,shown[1].cells);
  assert.equal(insideBlindInterval(plan,6),true);assert.equal(insideBlindInterval(plan,8.6),false);
});

test('envelope gives per-time XYZ extents covering every cell, clipped to a requested time range',()=>{
  const plan=blindHypothesisPlan(cases().ready),all=blindHypothesisEnvelope(plan);
  assert.equal(all.length,plan.regions.length);
  for(const [index,row] of all.entries()){
    const region=plan.regions[index],half=region.cell_size_m/2;
    assert.equal(row.timestamp_s,region.timestamp_s);assert.equal(row.bounds.length,3);
    for(const [lo,hi] of row.bounds)assert.ok(lo<=hi);
    for(const cell of region.cells){assert.ok(cell.x-half>=row.bounds[0][0]-1e-9&&cell.x+half<=row.bounds[0][1]+1e-9);assert.ok(cell.y-half>=row.bounds[1][0]-1e-9&&cell.y+half<=row.bounds[1][1]+1e-9);}
  }
  const clipped=blindHypothesisEnvelope(plan,[5,6]);assert.ok(clipped.length>0&&clipped.every(row=>row.timestamp_s>=5&&row.timestamp_s<=6));
  assert.deepEqual(blindHypothesisEnvelope(plan,[0,1]),[]);
});

test('legend is resident, uses the five-colour language and labels of at most six characters',()=>{
  assert.deepEqual(LEGEND_ITEMS.map(item=>item.label),['觀測','推論','缺失','假設','範圍']);
  for(const item of LEGEND_ITEMS)assert.ok([...item.label].length<=6);
  assert.equal(LEGEND_ITEMS.find(item=>item.key==='missing').style,'dashed');assert.equal(LEGEND_ITEMS.find(item=>item.key==='hypothesis').color,HYPOTHESIS_COLOR);
  for(const name of ['ready','unknown','substituted_unconfirmed']){
    const html=blindHypothesisStatusHTML(blindHypothesisPlan(cases()[name]));
    assert.match(html,/data-blind-hypothesis-legend/);for(const item of LEGEND_ITEMS)assert.match(html,new RegExp(`data-legend="${item.key}"`));
  }
  assert.match(blindHypothesisLegendHTML(),/觀測/);
});

test('READY status block states position UNKNOWN and that order is not probability',()=>{
  const html=blindHypothesisStatusHTML(blindHypothesisPlan(cases().ready));
  assert.match(html,/data-status="READY"/);assert.match(html,/位置 UNKNOWN/);assert.match(html,/不是機率/);assert.match(html,/4\.4 s–8\.6 s/);assert.doesNotMatch(html,/data-blind-notice/);
});

test('2D XYZ curve gets a hypothesis band only when a band is supplied, inside the blind interval, and never replaces observed or MISSING points',()=>{
  const without=crossCameraCandidateHTML(association(),1);
  assert.doesNotMatch(without,/data-hypothesis-band/);assert.equal(crossCameraCandidateHTML(association(),1,{hypothesisBand:[]}),without);
  const band=blindHypothesisEnvelope(blindHypothesisPlan(cases().ready));
  const html=crossCameraCandidateHTML(association(),1,{hypothesisBand:band});
  for(const axis of 'xyz')assert.match(html,new RegExp(`data-hypothesis-band="${axis}"`));
  assert.equal((html.match(/<path data-hypothesis-band=/g)??[]).length,3);
  assert.match(html,new RegExp(`fill="${HYPOTHESIS_COLOR}"`));assert.match(html,/推論，不是觀測/);
  // The band's x extent stays inside the blind interval.
  const chartLeft=Number(html.match(/data-chart-left="([\d.]+)"/)[1]),chartRight=Number(html.match(/data-chart-right="([\d.]+)"/)[1]);
  const xs=[...html.matchAll(/<path data-hypothesis-band="x" d="([^"]+)"/g)][0][1].match(/[ML]?(-?[\d.]+),/g).map(item=>Number(item.replace(/[ML,]/g,'')));
  const timeOf=px=>4+(px-chartLeft)/(chartRight-chartLeft)*5;
  assert.ok(Math.min(...xs)>=chartLeft&&Math.max(...xs)<=chartRight);
  assert.ok(timeOf(Math.min(...xs))>=4.4&&timeOf(Math.max(...xs))<=8.6);
  // Observed markers are still drawn exactly as before (4 projected samples), the MISSING sample is not turned into a circle.
  assert.equal((html.match(/<circle/g)??[]).length,(without.match(/<circle/g)??[]).length);
  // A band outside the chart's time range is not drawn.
  assert.doesNotMatch(crossCameraCandidateHTML(association(),1,{hypothesisBand:blindHypothesisEnvelope(blindHypothesisPlan(cases().ready),[20,30])}),/data-hypothesis-band/);
  // The panel passes the band through to the same curve.
  assert.match(crossCameraPanelHTML(association(),{rank:1,hypothesisBand:band}),/data-hypothesis-band="z"/);
  assert.doesNotMatch(crossCameraPanelHTML(association(),{rank:1}),/data-hypothesis-band/);
});
