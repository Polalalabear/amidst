import test from 'node:test';
import assert from 'node:assert/strict';
import {presentationData,presentationJSON,prepareFrames,retainElements,relationGraph,guidanceGraph,requestIsCurrent,updateGuidanceInputs,graphCaptionPlan} from './presentation-data.mjs';
import {guidanceSelection,guidanceRelationsHTML,portFlowHTML,resultStatus} from './app.mjs';

test('event IDs and embedded references disappear from technical presentation, while canonical records stay intact',()=>{
  const record={event:{event_id:'event_123',event_ref:'event:abc',canonical_event_id:'canonical-secret',summary:'use event:abc and canonical-secret',candidates:[{candidate_ref:'candidate:2'}]},
    evidence:[{kind:'EVENT',record_ref:'arbitrary-event-id'}],features:[{record_kind:'EVENT',record_ref:'another-arbitrary-id'}],
    actions:[{tool:'get_event_detail',record_ref:'event:abc'}],label:'event_456'};
  const original=structuredClone(record),display=presentationJSON(record);
  for(const id of ['event:abc','event_123','event_456','canonical-secret','arbitrary-event-id','another-arbitrary-id'])assert.equal(display.includes(id),false);
  assert.equal(display.includes('event_ref'),false);assert.equal(display.includes('event_id'),false);
  assert.match(display,/candidate:2/);assert.match(display,/get_event_detail/);
  assert.deepEqual(record,original);assert.deepEqual(presentationData({event:{kind:'GAP',time_range:[1,3]}}),{event:{kind:'GAP',time_range:[1,3]}});
  // Dedicated logs serialize the original data and retain its canonical references.
  assert.match(JSON.stringify(record),/event:abc/);
});

test('decoded frames commit only after all images are ready and a current response still owns the scope',async()=>{
  const pending=[];let current=true,settled=false;
  const result=prepareFrames([{media_ref:'a'},{media_ref:'b'},{status:'MISSING'}],ref=>'/media/'+ref,
    {decode:url=>new Promise(resolve=>pending.push({url,resolve})),current:()=>current}).then(value=>{settled=true;return value;});
  assert.deepEqual(pending.map(item=>item.url),['/media/a','/media/b']);
  pending[1].resolve();await Promise.resolve();assert.equal(settled,false);
  current=false;pending[0].resolve();assert.equal(await result,false);
  assert.equal(await prepareFrames([{media_ref:'current'}],ref=>ref,{decode:async()=>{},current:()=>true}),true);
});

test('routine DOM updates retain the exact canvas, decoded frame and panel nodes',()=>{
  const stage={name:'original canvas'},frame={name:'decoded image'},panel={name:'live panel'};
  const prior=new Map([['stage',stage],['frame',frame],['panel',panel]]),replacements=new Map();
  const root={querySelector:selector=>prior.get(selector),set innerHTML(markup){assert.equal(markup,'updated controls');
    for(const key of prior.keys())replacements.set(key,{replaceWith(node){this.retained=node;}});
    this.querySelector=selector=>replacements.get(selector);}};
  retainElements(root,'updated controls',['stage','frame','panel']);
  assert.equal(replacements.get('stage').retained,stage);assert.equal(replacements.get('frame').retained,frame);
  assert.equal(replacements.get('panel').retained,panel);
});

test('navigation display anchors use only matching source objects and explicit source edges',()=>{
  const snapshot={objects:[{object_id:'camera',kind:'CAMERA',label:'東鏡頭',geometry:{points:[[2,4,3]]}},
    {object_id:'region-object',kind:'REGION',label:'走廊',properties:{region_id:'R'},geometry:{points:[[0,0,0],[4,0,0],[4,4,0],[0,4,0]]}}]};
  const input={navigation_nodes:[{node_ref:'c',kind:'CAMERA',resource_id:'camera'},{node_ref:'r',kind:'REGION',resource_id:'R'},
    {node_ref:'missing',kind:'REGION',resource_id:'UNKNOWN'}],navigation_edges:[{from_ref:'c',to_ref:'r',relation:'REGISTERED_COVERAGE'},
    {from_ref:'c',to_ref:'missing',relation:'CONFIGURED_REGION_LINK'}]};
  const original=structuredClone(snapshot),graph=guidanceGraph(input,snapshot);
  assert.deepEqual(graph.nodes.map(node=>[node.label,node.position]),[['東鏡頭',[2,4,3]],['走廊',[2,2,0]]]);
  assert.equal(graph.edges.length,1);assert.equal(graph.edges[0].label,'登錄涵蓋關聯');
  assert.equal(graph.presentation_only,true);assert.deepEqual(snapshot,original);
  assert.deepEqual(guidanceGraph({...input,navigation_edges:[]},snapshot).edges,[],'nearby geometry must not imply a relationship');
  assert.equal(relationGraph({nodes:[{id:'x',position:[NaN,0,0]}],edges:[{from:'x',to:'x'}]}).nodes.length,0);
});

test('preset selection produces a finite label/camera/time/behavior/Top-K payload without semantic authority',()=>{
  const presets={time_range:[2,30],cameras:[{camera_id:'A'}],behaviors:['walking','running','enter_exit'].map(value=>({value}))};
  const values={place:'ignored UI label',camera_id:'A',label:' navigation ',start:'3',end:'12',behavior:'running',top_k:'3'};
  assert.deepEqual(guidanceSelection(values,presets),{label:'navigation',camera_id:'A',start:3,end:12,behavior:'running',top_k:3});
  for(const override of [{camera_id:'OTHER'},{start:'0'},{end:'31'},{behavior:'confirmed_running'},{top_k:'9'},{top_k:'1.5'}])
    assert.throws(()=>guidanceSelection({...values,...override},presets));
});

test('late guidance and decisions cannot repaint after scene, query or label selection changes',()=>{
  const state={sceneEpoch:1,queryEpoch:4,guideEpoch:2},ticket={...state};
  assert.equal(requestIsCurrent(state,ticket),true);
  for(const key of ['sceneEpoch','queryEpoch','guideEpoch'])assert.equal(requestIsCurrent({...state,[key]:state[key]+1},ticket),false);
});

test('unsaved form edits reject in-flight guide and decision replies without replacing user inputs',async()=>{
  const state={sceneEpoch:1,queryEpoch:4,guideEpoch:2,guide:{guide_ref:'server-issued'},
    guideSelection:{label:'navigation',behavior:'walking',start:'2',end:'12'}};
  const originalGuide=state.guide,ticket={sceneEpoch:1,queryEpoch:4,guideEpoch:2};
  let resolveGuide,resolveDecision;
  const guideReply=new Promise(resolve=>{resolveGuide=resolve;}).then(result=>{
    if(requestIsCurrent(state,ticket))state.guide=result;
  });
  const decisionReply=new Promise(resolve=>{resolveDecision=resolve;}).then(result=>{
    if(requestIsCurrent(state,ticket)&&state.guide===originalGuide)state.guide={...originalGuide,...result};
  });
  const edits={label:'CAM_B',camera_id:'B',behavior:'enter_exit',start:'',end:'19.4',top_k:'4'};
  updateGuidanceInputs(state,edits);
  assert.equal(state.guide,null);assert.deepEqual(state.guideSelection,edits);
  resolveGuide({guide_ref:'old-guide',agent_input:{selection:{behavior:'walking'}}});
  resolveDecision({agent_output:{status:'old-decision'}});await Promise.all([guideReply,decisionReply]);
  assert.equal(state.guide,null);assert.deepEqual(state.guideSelection,edits);
  assert.equal(state.guideEpoch,3);
});

test('system port view reports actual IO and failure states without exposing event references',()=>{
  const html=portFlowHTML({ports:[{port:'event.query',from_layer:'repository',to_layer:'retrieval',status:'FAIL',
    input:{camera_id:'A',time_range:[0,4]},output:{event_ref:'event:hidden',canonical_event_id:'event_opaque',candidate_count:3,complete:false}}]});
  assert.match(html,/repository → retrieval/);assert.match(html,/FAIL/);assert.match(html,/candidate_count/);assert.match(html,/complete/);
  assert.equal(html.includes('event:hidden'),false);assert.equal(html.includes('event_opaque'),false);
  assert.equal(resultStatus({passed:true}),'PASS');assert.equal(resultStatus({passed:false}),'FAIL');assert.equal(resultStatus({}),'UNKNOWN');
});


test('unlocated camera nodes keep explicit relationships in human text without made-up 3D positions',()=>{
  const html=guidanceRelationsHTML({navigation_nodes:[{node_ref:'opaque:a',kind:'CAMERA',resource_id:'CAM_A'},
    {node_ref:'opaque:b',kind:'REGION',resource_id:'ROOM'}],navigation_edges:[{from_ref:'opaque:a',to_ref:'opaque:b',relation:'REGISTERED_COVERAGE'}]},
    {objects:[{object_id:'r',kind:'REGION',properties:{region_id:'ROOM'},geometry:{points:[[1,2,0]]}}]});
  assert.match(html,/CAM_A → ROOM/);assert.match(html,/登錄涵蓋關聯/);assert.match(html,/3D 可定位 1/);
  assert.equal(html.includes('opaque:a'),false);assert.equal(html.includes('opaque:b'),false);
});


test('graph caption budget preserves every source edge and captions only selected-camera relationships on demand',()=>{
  const nodes=Array.from({length:7},(_,i)=>({id:'n'+i,position:[i,0,0],label:'Camera '+i}));
  const edges=[...Array.from({length:6},(_,i)=>({from:'n0',to:'n'+(i+1),label:'registered coverage'})),
    ...Array.from({length:5},(_,i)=>({from:'n'+(i+1),to:'n'+(i+2),label:'configured link'}))];
  const graph={nodes,edges,focus_node_id:'n0',show_relation_captions:false},original=structuredClone(graph);
  const compact=graphCaptionPlan(graph);
  assert.equal(compact.nodes.length,7);assert.equal(compact.edges.length,11);
  assert.deepEqual(compact.nodeCaptions.map(node=>node.id),['n0']);assert.deepEqual(compact.edgeCaptions,[]);
  const expanded=graphCaptionPlan({...graph,show_relation_captions:true});
  assert.equal(expanded.edges.length,11);assert.equal(expanded.edgeCaptions.length,2);
  assert.ok(expanded.nodeCaptions.length<=3);assert.ok(expanded.edgeCaptions.every(edge=>edge.from==='n0'||edge.to==='n0'));
  assert.deepEqual(graph,original,'caption controls never mutate topology');
});
