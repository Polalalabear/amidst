import test from 'node:test';import assert from 'node:assert/strict';
import {extractReappearances} from '../../scripts/evaluation/e3_cases/reappearance_events.mjs';
const policy={min_blind_s:3,max_blind_s:10,pre_visible_s:3,post_visible_s:3};
function rows(gaps=[[20,40]],length=90){return Array.from({length},(_,tick)=>({tick,actors:[{id:'T',present:true,
 gt_visible:gaps.some(([a,b])=>tick>=a&&tick<b)?[]:[tick<gaps[0][0]?'CAM_WEST':'CAM_EAST']}]}));}
test('one complete gap yields exactly one return point and a fixed three-second window',()=>{
 const result=extractReappearances(rows(),policy,{family:'C'});assert.equal(result.points.length,1);
 const p=result.points[0];assert.equal(p.tick,40);assert.equal(p.blind_duration_s,4);
 assert.deepEqual(p.evaluation_window_us,[8000000,11000000]);assert.deepEqual(p.from_cameras,['CAM_WEST']);
 assert.deepEqual(p.to_cameras,['CAM_EAST']);assert.equal(p.h4_reappearance,true);
});
test('visible continuation ticks do not increase return sample count',()=>{
 assert.equal(extractReappearances(rows([[20,40]],300),policy).points.length,1);
});
test('all qualifying gaps are retained once, without output-based selection',()=>{
 const r=extractReappearances(rows([[20,40],[65,85]],110),policy);
 assert.deepEqual(r.points.map(p=>p.tick),[40,85]);
});
test('longer than ten seconds and shorter than three seconds are diagnostic only',()=>{
 for(const gaps of [[[20,30]],[[20,75]]])assert.equal(extractReappearances(rows(gaps,110),policy).points.length,0);
});
test('missing pre/post observation time cannot manufacture eligible points',()=>{
 assert.equal(extractReappearances(rows([[5,25]],90),policy).points.length,0);
 assert.equal(extractReappearances(rows([[20,40]],50),policy).points.length,0);
});
test('C requires a change of visible camera set; B may return on the same camera',()=>{
 const same=rows().map(r=>({...r,actors:r.actors.map(a=>({...a,gt_visible:a.gt_visible.length?['CAM_SAME']:[]}))}));
 assert.equal(extractReappearances(same,policy,{family:'C'}).points.length,0);
 assert.equal(extractReappearances(same,policy,{family:'B'}).points.length,1);
});
test('missing or duplicate GT ticks fail closed',()=>{
 const bad=rows();bad[30].tick=29;assert.throws(()=>extractReappearances(bad,policy),/GT_GRID_REQUIRED/);
});
test('initially absent observations are not a lost-and-returned target',()=>{
 const initial=rows().map((r,i)=>({...r,actors:r.actors.map(a=>({...a,gt_visible:i<40?[]:['CAM_EAST']}))}));
 assert.equal(extractReappearances(initial,policy).points.length,0);
});
test('a target removed from the scene cannot count as a blind-gap return',()=>{
 const missing=rows();missing[30].actors[0].present=false;
 assert.equal(extractReappearances(missing,policy).points.length,0);
});
test('synthetic system output cannot substitute for the required private GT rows',()=>{
 assert.throws(()=>extractReappearances([{tick:0,tracking:{state:'TRACKING'}}],policy),/GT_GRID_REQUIRED/);
});
