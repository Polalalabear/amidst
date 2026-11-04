// Q_CORE_SEARCH_TRACK_V1 §5 acceptance tests (D126, #93). Codex implements core-search-track-model.mjs.
// Until it exists every test skips with CORE_FRONTEND_MODEL_MISSING; AMIDST_REQUIRE_IMPL=1 turns the skip into a failure.
// Inputs: pinned r004 region graph, hand-written SYNTHETIC fixtures and the SYNTHETIC bootstrap run. No GT, trajectories or scripts.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const CODE='CORE_FRONTEND_MODEL_MISSING';
const json=async rel=>JSON.parse(await readFile(new URL(rel,import.meta.url),'utf8'));
const R004=await json('../../configs/q1q5/graphs/r004/region_graph_v3_1.json');
const SYN=await json('../../tests/q1q5/fixtures/core_multi_room.synthetic.json');
const VECTORS=(await json('../../tests/q1q5/fixtures/core_single_view_vectors.synthetic.json')).vectors;
const RUN=JSON.parse((await json('./fixtures/q-bootstrap.json')).bootstrap_json).runs[0];
const SESSION='SYNTHETIC_SESSION_A';

let loaded;
async function model(t) {
  if(loaded===undefined){try{loaded=await import('./core-search-track-model.mjs');}catch(error){if(error?.code!=='ERR_MODULE_NOT_FOUND')throw error;loaded=null;}}
  if(loaded)return loaded;
  if(process.env.AMIDST_REQUIRE_IMPL==='1')assert.fail(CODE);
  t.skip(CODE);return null;
}
const codeOf=fn=>{try{fn();}catch(error){return error.message;}return 'NO_ERROR';};
function menus(m,graph=SYN.region_graph){return {regions:m.regionOptions(graph),...m.featureOptions(SYN.class_labels,SYN.color_labels)};}
const origin=RUN.clock_mapping.wall_origin,day=origin.slice(0,10),offset=origin.slice(-6);
const search=(over={})=>({start:'13:00',end:'13:30',regionIds:['SYN_ROOM_1'],classLabel:'person',colorLabel:'',...over});
const track=(over={})=>({start:'',end:'',regionIds:[],classLabel:'person',colorLabel:'red',...over});

test('region menu is read from the graph, in order, for r004 and the synthetic multi-room graph',async t=>{
  const m=await model(t);if(!m)return;
  for(const graph of [R004,SYN.region_graph]){
    const options=m.regionOptions(graph);
    assert.deepEqual(options.map(o=>o.value),graph.regions.map(r=>r.region_id));
    graph.regions.forEach((r,i)=>assert.equal(options[i].label,r.display_name??r.region_id));
  }
});
test('feature menu passes class and color vocabularies through without hardcoding',async t=>{
  const m=await model(t);if(!m)return;
  assert.deepEqual(m.featureOptions(SYN.class_labels,SYN.color_labels),{classes:SYN.class_labels,colors:SYN.color_labels});
  assert.deepEqual(m.featureOptions(['person'],[]),{classes:['person'],colors:[]});
});
test('search request: HH:MM in the declared clock becomes a full ISO wall range',async t=>{
  const m=await model(t);if(!m)return;
  const q=m.buildCoreSearchRequest(RUN,SESSION,search(),menus(m));
  assert.deepEqual(Object.keys(q).sort(),['feature','region_ids','run_id','scene_id','schema_version','session_ref','time']);
  assert.equal(q.schema_version,'q-core.search-request.v1');
  assert.deepEqual([q.session_ref,q.scene_id,q.run_id],[SESSION,RUN.scene_id,RUN.run_id]);
  assert.deepEqual(q.time,{kind:'WALL',timezone:RUN.clock_mapping.timezone,wall_range:[`${day}T13:00:00${offset}`,`${day}T13:30:00${offset}`]});
  assert.deepEqual(q.region_ids,['SYN_ROOM_1']);
  assert.deepEqual(q.feature,{class_label:'person',color_label:null});
  const full=m.buildCoreSearchRequest(RUN,SESSION,search({start:`${day}T13:00:05${offset}`,end:'13:00:30'}),menus(m));
  assert.deepEqual(full.time.wall_range,[`${day}T13:00:05${offset}`,`${day}T13:00:30${offset}`]);
});
test('search request: location only, feature only and both are accepted',async t=>{
  const m=await model(t);if(!m)return;
  assert.equal(m.buildCoreSearchRequest(RUN,SESSION,search({classLabel:''}),menus(m)).feature,null);
  assert.deepEqual(m.buildCoreSearchRequest(RUN,SESSION,search({regionIds:[]}),menus(m)).region_ids,[]);
  const both=m.buildCoreSearchRequest(RUN,SESSION,search({regionIds:['SYN_ROOM_2','SYN_HALL'],classLabel:'chair'}),menus(m));
  assert.deepEqual([both.region_ids,both.feature],[['SYN_ROOM_2','SYN_HALL'],{class_label:'chair',color_label:null}]);
});
test('search request: field rules reject with the contract error codes',async t=>{
  const m=await model(t);if(!m)return;
  const cases=[
    [{start:''},'TIME_REQUIRED'],[{end:''},'TIME_REQUIRED'],
    [{start:'13:30',end:'13:00'},'TIME_ORDER'],[{start:'13:00',end:'13:00'},'TIME_ORDER'],
    [{start:'1pm'},'TIME_INVALID'],[{start:'25:00'},'TIME_INVALID'],
    [{regionIds:[],classLabel:''},'LOCATION_OR_FEATURE_REQUIRED'],
    [{regionIds:['NOT_A_REGION']},'REGION_UNKNOWN'],
    [{classLabel:'unicorn'},'UNSUPPORTED_CLASS'],
    [{colorLabel:'purple'},'COLOR_UNKNOWN'],
    [{classLabel:'chair',colorLabel:'red'},'UNSUPPORTED_CONDITION'],
  ];
  for(const [over,code] of cases)assert.equal(codeOf(()=>m.buildCoreSearchRequest(RUN,SESSION,search(over),menus(m))),code,JSON.stringify(over));
  for(const code of new Set(cases.map(c=>c[1])))assert.ok(typeof m.ERROR_TEXT[code]==='string'&&m.ERROR_TEXT[code],code);
});
test('track request: feature required, empty time means playback now',async t=>{
  const m=await model(t);if(!m)return;
  const q=m.buildCoreTrackRequest(RUN,SESSION,track(),menus(m),42000000);
  assert.equal(q.schema_version,'q-core.track-request.v1');
  assert.deepEqual([q.time,q.playback_now_us,q.region_ids],[null,42000000,[]]);
  assert.deepEqual(q.feature,{class_label:'person',color_label:'red'});
  const windowed=m.buildCoreTrackRequest(RUN,SESSION,track({start:'13:00',end:'13:30',regionIds:['SYN_ROOM_3']}),menus(m),42000000);
  assert.equal(windowed.time.kind,'WALL');assert.deepEqual(windowed.region_ids,['SYN_ROOM_3']);
  assert.equal(codeOf(()=>m.buildCoreTrackRequest(RUN,SESSION,track({classLabel:''}),menus(m),0)),'FEATURE_REQUIRED');
  for(const now of [-1,1.5,null,undefined,'0'])assert.equal(codeOf(()=>m.buildCoreTrackRequest(RUN,SESSION,track(),menus(m),now)),'NOW_REQUIRED',String(now));
  assert.equal(codeOf(()=>m.buildCoreTrackRequest(RUN,SESSION,track({regionIds:['NOT_A_REGION']}),menus(m),0)),'REGION_UNKNOWN');
  assert.ok(m.ERROR_TEXT.FEATURE_REQUIRED&&m.ERROR_TEXT.NOW_REQUIRED);
});
test('track class support: only person is supported by the current linker',async t=>{
  const m=await model(t);if(!m)return;
  assert.equal(m.trackClassSupport('person'),'SUPPORTED');
  for(const label of SYN.class_labels.filter(x=>x!=='person'))assert.equal(m.trackClassSupport(label),'UNSUPPORTED',label);
});
for(const vector of VECTORS){
  test(`single view sequence: ${vector.id}`,async t=>{
    const m=await model(t);if(!m)return;
    const input=structuredClone(vector.sightings);
    assert.deepEqual(m.singleViewSequence(input,{asOfUs:vector.as_of_us}),vector.single_view);
    assert.deepEqual(input,vector.sightings,'input must not be mutated');
    assert.deepEqual(m.multiViewCameras(structuredClone(vector.sightings),{asOfUs:vector.as_of_us}),vector.multi_view);
  });
}
test('single view sequence invariants hold on generated SYNTHETIC sightings',async t=>{
  const m=await model(t);if(!m)return;
  let seed=7;const rnd=n=>{seed=(seed*1103515245+12345)%2147483648;return seed%n;};
  for(let round=0;round<300;round++){
    const sightings=Array.from({length:rnd(6)},()=>{const a=rnd(50)*1000000;return {camera_id:`CAM_${'ABCD'[rnd(4)]}`,range_us:[a,a+(1+rnd(20))*1000000]};});
    const asOfUs=(1+rnd(70))*1000000,out=m.singleViewSequence(sightings,{asOfUs});
    const live=sightings.filter(s=>s.range_us[0]<asOfUs);
    if(!live.length){assert.deepEqual(out,[]);continue;}
    assert.equal(out.at(-1).range_us[1],asOfUs);assert.notEqual(out.at(-1).kind,'GAP');
    out.forEach((seg,i)=>{
      assert.ok(seg.range_us[0]<seg.range_us[1]);
      if(i)assert.equal(out[i-1].range_us[1],seg.range_us[0]);
      if(seg.kind==='ON_CAMERA'){
        assert.equal(seg.evidence_state,'OBSERVED');
        // the shown camera really saw the target for the whole segment (union of its own sightings)
        for(let t=seg.range_us[0];t<seg.range_us[1];t+=500000)assert.ok(live.some(s=>s.camera_id===seg.camera_id&&s.range_us[0]<=t&&t<s.range_us[1]),JSON.stringify({sightings,asOfUs,seg}));
      }else{
        assert.deepEqual([seg.camera_id,seg.evidence_state],[null,'UNKNOWN']);
        for(let t=seg.range_us[0];t<seg.range_us[1];t+=500000)assert.ok(!live.some(s=>s.range_us[0]<=t&&t<s.range_us[1]));
      }
    });
  }
});
