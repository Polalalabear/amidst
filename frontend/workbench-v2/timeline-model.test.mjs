import test from 'node:test';import assert from 'node:assert/strict';
import {createView,zoom,pan,fit,centerOn,timeToX,xToTime,ticks,formatTick,layoutMarkers,neighborEvent,clipSegments,followPlayhead,isVisible,span,zoomLevel,MIN_SPAN_US} from './timeline-model.mjs';
const D=3600e6;
test('createView validates range',()=>{assert.deepEqual(createView(D).range,[0,D]);assert.throws(()=>createView(D,[5,5]),/VIEW_RANGE_INVALID/);assert.throws(()=>createView(D,[0,D+1]),/VIEW_RANGE_INVALID/);assert.throws(()=>createView(0),/DURATION_INVALID/);});
test('zoom keeps anchor fraction and clamps to bounds and minimum span',()=>{
  let v=createView(D);v=zoom(v,4,1800e6);assert.deepEqual(v.range,[1350e6,2250e6]);assert.equal(zoomLevel(v),4);
  const a=900e6,v2=zoom(createView(D),2,a);assert.equal((a-v2.range[0])/span(v2),.25);
  assert.equal(span(zoom(v,1e9,1800e6)),MIN_SPAN_US);assert.deepEqual(zoom(v,.0001,1800e6).range,[0,D]);
  assert.throws(()=>zoom(v,0,0),/ZOOM_FACTOR_INVALID/);});
test('zoom at the left edge stays inside [0,duration]',()=>{const v=zoom(createView(D),8,0);assert.equal(v.range[0],0);assert.ok(v.range[1]<=D);const w=zoom(createView(D),8,D);assert.equal(w.range[1],D);});
test('pan clamps and preserves span',()=>{const v=createView(D,[100e6,200e6]);assert.deepEqual(pan(v,-500e6).range,[0,100e6]);assert.deepEqual(pan(v,1e12).range,[D-100e6,D]);assert.equal(span(pan(v,30e6)),100e6);});
test('fit pads and clamps; centerOn centres',()=>{const v=createView(D);assert.deepEqual(fit(v,[1000e6,1100e6]).range,[990e6,1110e6]);assert.deepEqual(fit(v,[0,50e6]).range,[0,60e6]);assert.throws(()=>fit(v,[5,5]),/FIT_RANGE_INVALID/);
  assert.deepEqual(centerOn(createView(D,[0,100e6]),1000e6).range,[950e6,1050e6]);});
test('time<->x round trip',()=>{const v=createView(D,[600e6,1200e6]);assert.equal(timeToX(v,900e6,1000),500);assert.equal(xToTime(v,500,1000),900e6);assert.equal(xToTime(v,timeToX(v,777e6,800),800),777e6);});
test('ticks use a nice step with labels >= minPx apart and in range',()=>{
  for(const [r,w] of [[[0,D],1000],[[0,60e6],1000],[[100e6,130e6],600]]){const v=createView(D,r),t=ticks(v,w,80);assert.ok(t.ticks.length>0);assert.ok(t.ticks.every(x=>x.t>=r[0]&&x.t<r[1]));if(t.ticks.length>1)assert.ok((t.ticks[1].left-t.ticks[0].left)/100*w>=80-1e-9);}
  assert.equal(ticks(createView(D),1000).step_us,300e6);});
test('formatTick: hh:mm:ss below one-minute steps, NhMMm above',()=>{assert.equal(formatTick(3725e6,10e6),'01:02:05');assert.equal(formatTick(3725e6,60e6),'1h02m');});
const ev=(id,t,kind='OBS_START')=>({id,t_us:t,kind,label:id});
test('layoutMarkers clusters near events and splits when zoomed in',()=>{
  const events=[ev('a',100e6),ev('b',101e6),ev('c',102e6,'GAP_START'),ev('d',900e6)];
  const wide=layoutMarkers(events,createView(D),1000,14);assert.equal(wide.length,2);assert.equal(wide[0].count,3);assert.equal(wide[0].kind,'CLUSTER');assert.deepEqual(wide[0].ids,['a','b','c']);assert.equal(wide[1].kind,'OBS_START');
  const zin=layoutMarkers(events,createView(D,[99e6,103e6]),1000,14);assert.equal(zin.length,3);assert.ok(zin.every(m=>m.count===1));});
test('layoutMarkers drops events outside window; ordering is deterministic; no event lost',()=>{
  const events=[ev('z',50e6),ev('y',50e6),ev('x',5000e6-1500e6)];const all=layoutMarkers(events,createView(D),1000,14);assert.equal(all.flatMap(m=>m.ids).length,3);
  assert.deepEqual(layoutMarkers(events,createView(D,[0,100e6]),1000,14)[0].ids,['y','z']);assert.deepEqual(layoutMarkers(events,createView(D,[100e6,200e6]),1000,14),[]);});
test('layoutMarkers clusters are anchored: a long chain does not collapse into one marker',()=>{const events=Array.from({length:10},(_,i)=>ev('e'+i,i*10e6));const m=layoutMarkers(events,createView(D,[0,100e6]),1000,30);assert.ok(m.length>1);assert.equal(m.flatMap(x=>x.ids).length,10);});
test('neighborEvent skips the current instant',()=>{const e=[ev('a',10),ev('b',20),ev('c',30)];assert.equal(neighborEvent(e,20,1).id,'c');assert.equal(neighborEvent(e,20,-1).id,'a');assert.equal(neighborEvent(e,30,1),null);assert.equal(neighborEvent(e,10,-1),null);});
test('clipSegments clips to window and drops invisible ones',()=>{const s=[{range_us:[0,100],state:'A'},{range_us:[100,300],state:'B'},{range_us:[300,400],state:'C'}];const out=clipSegments(s,createView(1000,[150,350]));assert.deepEqual(out.map(x=>[x.state,x.left,x.width]),[['B',0,75],['C',75,25]]);});
test('followPlayhead re-centers only when the playhead leaves the window',()=>{
  let v=zoom(createView(D),8,0);assert.equal(span(v),450e6);assert.deepEqual(v.range,[0,450e6]);
  assert.equal(followPlayhead(v,440e6),v);
  const t=440e6+60*2.5*1e6;assert.ok(!isVisible(v,t));
  const f=followPlayhead(v,t);assert.ok(isVisible(f,t));assert.equal(span(f),span(v));assert.equal((f.range[0]+f.range[1])/2,t);
  const e=followPlayhead(v,D-1);assert.ok(isVisible(e,D-1));assert.equal(e.range[1],D);
  assert.ok(isVisible(followPlayhead(f,0),0));
});
