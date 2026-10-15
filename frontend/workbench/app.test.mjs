import test from 'node:test';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {escapeHTML, normalizeRange, eventLabel, evidenceLabel, supportLabel, changesForObject, eventMediaFrames, frameTimeLabel, invalidateEventState, eventRequestIsCurrent,sourcePlaybackStep,nextPlaybackTimestamp,cameraTileLayout,cameraTilesHTML,frameLoadState,TILE_GAP,markerLegendItems,markerLegendHTML} from './app.mjs';

test('untrusted source fields cannot become HTML markup',()=>{
  assert.equal(escapeHTML('<img src=x onerror="bad()">'), '&lt;img src=x onerror=&quot;bad()&quot;&gt;');
});
test('v2 visible support and unresolved behavior remain distinct',()=>{
  assert.equal(supportLabel('UNKNOWN'),'證據不足／未定');
  assert.equal(supportLabel('SUPPORTED'),'可見證據支持此候選');
  assert.equal(supportLabel('GAP_ALTERNATIVES'),'保留盲區替代路徑');
  assert.equal(supportLabel(undefined),'');
});
test('both scene range contracts normalize and invalid ranges fail closed',()=>{
  assert.deepEqual(normalizeRange([2,14]),[2,14]);
  assert.deepEqual(normalizeRange({start:1,end:12}),[1,12]);
  assert.deepEqual(normalizeRange([9,2]),[0,0]);
  assert.deepEqual(normalizeRange([0,Infinity]),[0,0]);
});
test('provisional event wording preserves uncertainty',()=>{
  assert.equal(eventLabel('POSSIBLE_LOITERING'),'可能遊蕩');
  assert.equal(eventLabel('INFERRED_GAP_ALTERNATIVES'),'盲區路線候選');
});
test('draft changes retain original properties and only change edited values',()=>{
  const object={label:'西側門',semantic:'PORTAL',properties:{intrinsics:{fx:500,fy:500,cx:320,cy:240},source:'preserved'}};
  const changes=changesForObject(object,{label:'西側門',semantic:'ENTRY',intrinsic_fx:'510'});
  assert.deepEqual(changes,{semantic:'ENTRY',properties:{intrinsics:{fx:510,fy:500,cx:320,cy:240},source:'preserved'}});
  assert.equal(object.properties.intrinsics.fx,500);
});
test('malformed geometry cannot be submitted as a review draft',()=>{
  assert.throws(()=>changesForObject({}, {geometry:'{"type":"polygon","points":[[1,2]]}'}),/三個有效數字/);
  assert.throws(()=>changesForObject({}, {geometry:'not json'}),/JSON/);
  assert.deepEqual(changesForObject({label:'A'},{label:'A'}),{});
});
test('event media joins exact frame refs despite metadata order and repeated cameras',()=>{
  const frames=eventMediaFrames({
    media_refs:['a','b','c'],camera_ids:['WEST','DOOR'],
    source_frames:[
      {frame_ref:'c',camera_id:'DOOR',timestamp:9.2},
      {frame_ref:'a',camera_id:'DOOR',timestamp:8.4},
      {frame_ref:'b',camera_id:'WEST',timestamp:8.8},
    ],
  });
  assert.deepEqual(frames,[
    {media_ref:'a',camera_id:'DOOR',timestamp:8.4},
    {media_ref:'b',camera_id:'WEST',timestamp:8.8},
    {media_ref:'c',camera_id:'DOOR',timestamp:9.2},
  ]);
});
test('missing source metadata stays unknown instead of guessing camera or zero time',()=>{
  const frames=eventMediaFrames({media_refs:['a','missing','zero'],camera_ids:['WEST'],source_frames:[
    {frame_ref:'a',camera_id:'DOOR',timestamp:null},
    {frame_ref:'zero',camera_id:'WEST',timestamp:0},
  ]});
  assert.deepEqual(frames,[
    {media_ref:'a',camera_id:'DOOR',timestamp:null},
    {media_ref:'missing',camera_id:null,timestamp:null},
    {media_ref:'zero',camera_id:'WEST',timestamp:0},
  ]);
  assert.equal(frameTimeLabel(frames[0].timestamp),'時間未知');
  assert.equal(frameTimeLabel(frames[1].timestamp),'時間未知');
  assert.equal(frameTimeLabel(frames[2].timestamp),'0.0 s');
  assert.equal(frameTimeLabel(undefined),'時間未知');
});
test('management evidence status uses concise labels while research keeps diagnostics',()=>{
  assert.equal(evidenceLabel('INFERRED_GAP'),'盲區推論');
  assert.equal(evidenceLabel('PROJECTED'),'可見投影');
  assert.equal(evidenceLabel('INTERNAL_NEW_ENUM'),'候選事件 · 待檢視');
  assert.equal(evidenceLabel('INTERNAL_NEW_ENUM',true),'INTERNAL_NEW_ENUM');
});
test('late event and note responses cannot overwrite a newer selection in the same scene',async()=>{
  const target={sceneEpoch:3,eventEpoch:0,selectedEvent:null,event:null,notes:[]};
  const pending=[];
  const request=(ref,kind)=>{
    const ticket={sceneEpoch:target.sceneEpoch,eventEpoch:target.eventEpoch,eventRef:ref};
    return new Promise((resolve)=>pending.push(resolve)).then((data)=>{
      if(eventRequestIsCurrent(target,ticket)){
        if(kind==='note')target.notes.push(data);else target.event=data;
      }
    });
  };
  invalidateEventState(target);target.selectedEvent='A';
  const oldEvent=request('A','event'),oldNote=request('A','note');
  invalidateEventState(target);target.selectedEvent='B';
  const newEvent=request('B','event');
  pending[2]({event_ref:'B'});await newEvent;
  pending[0]({event_ref:'A'});pending[1]({note:'Only belongs to A'});
  await Promise.all([oldEvent,oldNote]);
  assert.deepEqual(target.event,{event_ref:'B'});assert.deepEqual(target.notes,[]);
});
test('object selection and query invalidation reject old responses even after selecting the same ref again',()=>{
  const target={sceneEpoch:4,eventEpoch:9,selectedEvent:'A',event:{event_ref:'A'},notes:[{note:'old'}]};
  const ticket={sceneEpoch:4,eventEpoch:9,eventRef:'A'};
  invalidateEventState(target);
  assert.equal(target.event,null);assert.deepEqual(target.notes,[]);assert.equal(target.selectedEvent,null);
  target.selectedEvent='A';
  assert.equal(eventRequestIsCurrent(target,ticket),false);
  assert.equal(eventRequestIsCurrent({...target,sceneEpoch:5},{...ticket,eventEpoch:target.eventEpoch}),false);
});

test('Office frame-query scenes step 0.2 s and other scenes keep 0.4 s',()=>{
  assert.equal(sourcePlaybackStep({capabilities:{frame_query:true}}),.2);
  assert.equal(sourcePlaybackStep({capabilities:{}}),.4);
  assert.equal(sourcePlaybackStep(undefined),.4);
});
test('0.2 s playback visits 50 timestamps from 0 to 9.8 without drift',()=>{
  const seen=[0];while(seen.at(-1)<9.8)seen.push(nextPlaybackTimestamp(seen.at(-1),[0,9.8],.2));
  assert.equal(seen.length,50);assert.equal(seen.at(-1),9.8);assert.ok(seen.every((v,i)=>v===Number((i*.2).toFixed(6))));
  assert.equal(nextPlaybackTimestamp(9.7,[0,9.8],.4),9.8);
  assert.equal(nextPlaybackTimestamp(0,[0,9.8],.4),.4);
});
const frames=[{camera_id:'CAM_A',timestamp:1.2,media_ref:'ref:a12'},{camera_id:'CAM_B',timestamp:1.2,status:'MISSING_FRAME'}];
const tiles=(timestamp,list,ids=['CAM_A','CAM_B'])=>cameraTilesHTML({cameraIds:ids,frames:list,timestamp,urlFor:ref=>'/m/'+ref});
test('one tile per selected camera, in order, each with its own frame',()=>{
  const html=tiles(1.2,[{camera_id:'CAM_A',timestamp:1.2,media_ref:'ref:a12'},{camera_id:'CAM_B',timestamp:1.2,media_ref:'ref:b12'}]);
  assert.deepEqual([...html.matchAll(/data-camera-tile="([^"]+)"/g)].map(m=>m[1]),['CAM_A','CAM_B']);
  assert.ok(html.indexOf('ref:a12')<html.indexOf('data-camera-tile="CAM_B"'));assert.match(html,/\/m\/ref:b12/);
  assert.equal((tiles(1.2,frames,['CAM_A']).match(/data-camera-tile=/g)??[]).length,1);
});
test('a camera without a frame is an explicit MISSING tile and never shows another camera image',()=>{
  const html=tiles(1.2,frames),b=html.slice(html.indexOf('data-camera-tile="CAM_B"'));
  assert.match(html,/data-camera-tile="CAM_A"[^>]*data-frame-availability="AVAILABLE"/);assert.match(b,/data-frame-availability="MISSING"/);
  assert.match(b,/MISSING · MISSING_FRAME/);assert.doesNotMatch(b,/<img/);
  const none=tiles(3,[{camera_id:'CAM_A',timestamp:3,media_ref:'ref:a3'}]),nb=none.slice(none.indexOf('data-camera-tile="CAM_B"'));
  assert.match(nb,/MISSING · 此時間沒有回傳來源影格/);assert.doesNotMatch(nb,/<img/);assert.doesNotMatch(nb,/ref:a3/);
  assert.match(cameraTilesHTML({}),/未選取鏡頭/);
});
test('a camera whose frame request is pending is LOADING, not MISSING; failures are ERROR; confirmed absence stays MISSING',()=>{
  const only=[{camera_id:'CAM_A',timestamp:1.2,media_ref:'ref:a12'}];
  const html=state=>cameraTilesHTML({cameraIds:['CAM_A','CAM_B'],frames:only,timestamp:1.2,urlFor:ref=>'/m/'+ref,loadState:state});
  const part=(h,id)=>h.slice(h.indexOf(`data-camera-tile="${id}"`));
  const loading=html('loading'),b=part(loading,'CAM_B');
  assert.match(b,/data-frame-availability="LOADING"/);assert.doesNotMatch(b,/MISSING/);assert.doesNotMatch(b,/<img/);
  assert.match(loading,/data-camera-tile="CAM_A"[^>]*data-frame-availability="AVAILABLE"/);
  assert.match(part(html('error'),'CAM_B'),/data-frame-availability="ERROR"/);
  assert.match(part(html('idle'),'CAM_B'),/data-frame-availability="MISSING"/);
  // A frame the backend returned without media is a confirmed MISSING even while another request is pending.
  const confirmed=cameraTilesHTML({cameraIds:['CAM_B'],frames:[{camera_id:'CAM_B',timestamp:1.2,status:'MISSING_FRAME'}],timestamp:1.2,loadState:'loading'});
  assert.match(confirmed,/data-frame-availability="MISSING"/);assert.match(confirmed,/MISSING · MISSING_FRAME/);
});
test('tiles follow the playback timestamp',()=>{
  const b=tiles(1.4,[{camera_id:'CAM_A',timestamp:1.4,media_ref:'ref:a14'}]);
  assert.match(b,/\/m\/ref:a14/);assert.doesNotMatch(b,/ref:a12/);assert.match(b,/1\.4/);
});
const layout=(o)=>cameraTileLayout({aspect:16/9,gap:8,chromeHeight:0,...o});
const dims=(l)=>[l.columns,l.rows];
test('cameraTileLayout follows the measured container, not a window breakpoint',()=>{
  assert.deepEqual(dims(layout({count:2,width:1400,height:600})),[2,1]);
  assert.deepEqual(dims(layout({count:2,width:600,height:600})),[1,2]);
  assert.deepEqual(dims(layout({count:2,width:645,height:600})),[1,2]);
  assert.deepEqual(dims(layout({count:2,width:660,height:600})),[2,1]);
  const short=layout({count:2,width:1400,height:150});assert.deepEqual(dims(short),[2,1]);assert.ok(short.tileHeight<=150+1e-9&&Math.abs(short.tileHeight-150)<1e-6);
  const chrome=layout({count:2,width:900,height:260,chromeHeight:40});assert.deepEqual(dims(chrome),[2,1]);assert.ok(Math.abs(chrome.tileHeight-220)<1e-6);
  const portrait=layout({count:2,width:700,height:600,aspect:9/16});assert.deepEqual(dims(portrait),[2,1]);assert.ok(Math.abs(portrait.tileWidth-337.5)<1e-6);
  assert.deepEqual(dims(layout({count:4,width:1000,height:700})),[2,2]);
  assert.deepEqual(dims(layout({count:3,width:1400,height:600})),[3,1]);
  assert.deepEqual(dims(layout({count:1,width:800,height:400})),[1,1]);
  assert.deepEqual(layout({count:0}),{columns:0,rows:0,tileWidth:0,tileHeight:0});
});
test('cameraTileLayout never overflows its container and keeps the aspect ratio',()=>{
  for(const o of [{count:2,width:1400,height:600},{count:2,width:600,height:600},{count:2,width:645,height:600},{count:2,width:1400,height:150},{count:2,width:900,height:260,chromeHeight:40},{count:2,width:700,height:600,aspect:9/16},{count:4,width:1000,height:700},{count:3,width:1400,height:600},{count:1,width:800,height:400}]){
    const a=o.aspect??16/9,c=o.chromeHeight??0,l=layout(o);
    assert.ok(l.columns*l.tileWidth+8*(l.columns-1)<=o.width+1e-6,JSON.stringify(o));
    assert.ok(l.rows*(l.tileHeight+c)+8*(l.rows-1)<=o.height+1e-6,JSON.stringify(o));
    assert.ok(Math.abs(l.tileWidth/l.tileHeight-a)<1e-9);
  }
});
test('the CSS tile gap and the layout helper share one constant; wall is diagnostic only',()=>{
  const src=readFileSync(new URL('./app.mjs',import.meta.url),'utf8');
  assert.match(src,/style="--tile-gap:\$\{TILE_GAP\}px"/);assert.match(src,/gap,chromeHeight:measured/);assert.equal(TILE_GAP,8);
  assert.match(src,/<details class="diagnostic-wall">/);assert.doesNotMatch(src,/<details class="diagnostic-wall" open/);
  assert.doesNotMatch(src,/data-viewer-camera|viewerCameraId/);assert.match(src,/data-aspect-source="DEFAULT"/);
});
test('marker legend reflects the true data sources and reports Candidate unavailable',()=>{
  const none=markerLegendItems({});
  assert.match(none.find(i=>i.key==='candidate').label,/Candidate unavailable/);
  assert.ok(none.every(i=>i.available===(i.key==='missing'?false:false)));
  assert.equal(none.some(i=>i.key==='historical'),false);
  const plan={selected_rank:1,paths:[{selected:true,samples:[{state:'PROJECTED_OBSERVATION'},{state:'MISSING'},{state:'INFERRED_CROSS_CAMERA'}]},{selected:false,samples:[{state:'PROJECTED_OBSERVATION'}]}]};
  const items=markerLegendItems({plan,historicalTrack:true});
  assert.deepEqual(items.map(i=>[i.key,i.available]),[['observed',true],['candidate',true],['missing',true],['historical',true]]);
  assert.match(items.find(i=>i.key==='historical').label,/非所選候選/);
  assert.match(markerLegendHTML(none),/目前無資料/);
  const only=markerLegendItems({plan:{selected_rank:2,paths:[{selected:true,samples:[{state:'PROJECTED_OBSERVATION'}]}]}});
  assert.deepEqual(only.map(i=>i.available),[true,false,false]);
});

test('LOADING and ERROR apply only to the live request epoch, so a superseded request cannot pin a tile in LOADING',()=>{
  assert.equal(frameLoadState({frameLoad:'loading',frameLoadEpoch:4,timelineEpoch:4}),'loading');
  assert.equal(frameLoadState({frameLoad:'error',frameLoadEpoch:4,timelineEpoch:4}),'error');
  assert.equal(frameLoadState({frameLoad:'loading',frameLoadEpoch:4,timelineEpoch:5}),'idle');
  assert.equal(frameLoadState({frameLoad:'error',frameLoadEpoch:4,timelineEpoch:6}),'idle');
  assert.equal(frameLoadState({frameLoad:'loading',frameLoadEpoch:null,timelineEpoch:9}),'loading');
  assert.equal(frameLoadState({frameLoad:'idle',frameLoadEpoch:4,timelineEpoch:4}),'idle');
});
