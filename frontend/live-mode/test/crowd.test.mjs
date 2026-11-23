import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { performance } from 'node:perf_hooks';
import { createCrowd, resolveMoves, validateScripts, DEFAULT_CROWD_CONFIG } from '../src/crowd.mjs';
import { stepPlayer, scriptedPose } from '../src/sim.mjs';
const source = new URL('../../../docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json', import.meta.url);
const runs = JSON.parse(fs.readFileSync(source)).runs.filter(r=>['A4-1-v2-4actor','B4-1-v2-4actor'].includes(r.run_id));
const actor=(id,points)=>({actor_id:id,waypoints:points.map(([t,x,y])=>({t_us:t*1e6,xy:[x,y]}))});
const run=(actors,duration=100)=>({run_id:'fixture',duration_us:duration*1e6,actors});
const close=(a,b,eps=1e-8)=>assert.ok(Math.abs(a-b)<eps,`${a} != ${b}`);
const checkedResolve = (entities, cfg, ignored) => {
 for (const entity of entities) assert.deepEqual(entity.candidates.at(-1), entity.from, entity.id);
 return resolveMoves(entities, cfg, ignored);
};
const checkPhase = (snap, dt) => {
 for (const actor of snap.actors.filter(a => !a.is_player)) {
  assert.equal(actor.tainted, actor.pause_total_i > 0, JSON.stringify({tick: snap.tick, actor}));
 }
 for (const event of snap.events.filter(e => e.type === 'forced_overlap' && e.tick === snap.tick)) {
  assert.ok(Math.abs(event.phase_offset_s) >= dt / 2, JSON.stringify(event));
 }
};

test('defaults have no timeout for player; baseline scripts validate for all five role selections',()=>{
 assert.equal('wait_max_player_s' in DEFAULT_CROWD_CONFIG,false);
 for(const r of runs){const v=validateScripts(r);assert.equal(v.choices.length,5);assert.equal(v.overlap_samples,0);assert.ok(v.minimum_m>=0.6);}
});
test('selected variant is the sole player, other variants remain unique; session cannot change',()=>{
 for(const r of runs)for(const id of ['T','A','B','C']){
  const c=createCrowd(r,{actorId:id});assert.equal(c.session.actor_id,id);
  assert.throws(()=>{c.session.actor_id='Z';});
  const s=c.snapshot();assert.equal(s.actors.length,4);assert.equal(s.actors.filter(x=>!x.is_player).length,3);
  assert.equal(new Set(s.actors.map(x=>x.variant)).size,4);
 }
});
test('C-8 simultaneous inward proposals reject lower priority; moving/stationary player cases',()=>{
 const e=(id,player,x,next)=>({id,is_player:player,from:{x,y:0},candidates:[{x:next,y:0},{x,y:0}]});
 let r=resolveMoves([e('T',true,0,.12),e('A',false,.8,.68)]);
 close(r.poses.T.x,.12);close(r.poses.A.x,.8);assert.equal(r.blocked.A,'T');
 r=resolveMoves([e('T',true,0,.25),e('A',false,.65,.65)]);
 close(r.poses.T.x,0);close(r.poses.A.x,.65);
 const three=[e('T',false,-.7,0),e('A',false,.7,0),{id:'C',is_player:false,from:{x:0,y:.7},candidates:[{x:0,y:0},{x:0,y:.7}]}];
 r=resolveMoves(three);for(let i=0;i<three.length;i++)for(let j=i+1;j<three.length;j++)assert.ok(Math.hypot(r.poses[three[i].id].x-r.poses[three[j].id].x,r.poses[three[i].id].y-r.poses[three[j].id].y)>=.6);
});
test('A-1 legacy movement speeds, diagonal normalization, walls/sliding and overlap escape',()=>{
 for(const shift of [false,true]){const p={x:0,y:0};stepPlayer(p,{w:true,d:true,shift},.1,[]);close(Math.hypot(p.x,p.y),(shift?2.5:1.2)*.1);}
 const p={x:0,y:0};stepPlayer(p,{d:true,w:true},.1,[{a:[.28,-1],b:[.28,1]}]);close(p.x,0);assert.ok(p.y>0);
 const q={x:0,y:0};stepPlayer(q,{a:true},.1,[],[{x:.1,y:0,present:true}]);assert.ok(q.x<0);
 const b={x:0,y:0};stepPlayer(b,{d:true},.1,[],[{x:.65,y:0,present:true}]);close(b.x,0);
});
test('C-6 player waits beyond 60s, never forced; other clocks advance; leave resumes one step',()=>{
 const r=run([actor('T',[[0,0,0],[100,0,0]]),actor('A',[[0,-2,0],[100,98,0]]),actor('B',[[0,0,5],[100,100,5]])]);
 const c=createCrowd(r,{actorId:'T'});
 for(let i=0;i<600;i++)c.step({},.1);
 const s=c.snapshot(),a=s.actors.find(x=>x.actor_id==='A'),b=s.actors.find(x=>x.actor_id==='B');
 assert.ok(a.block_wait>50);close(a.s_i+s.actors.find(x=>x.actor_id==='A').pause_total_i,60,1e-7);close(b.s_i,60,1e-7);
 assert.equal(s.events.filter(e=>e.type==='forced_overlap'&&e.kind==='player').length,0);
 c.step({w:true,shift:true},.1);c.step({w:true,shift:true},.1);c.step({w:true,shift:true},.1);
 const prev=c.snapshot().actors.find(x=>x.actor_id==='A').s_i;
 c.step({w:true,shift:true},.1);
 const released=c.snapshot().actors.find(x=>x.actor_id==='A');
 assert.ok(released.s_i>prev);
 assert.equal(released.tainted,true);
});
test('C-6 real A4/B4 60s stationary player; unaffected actors match baseline; one-step release',()=>{
 for(const [runId,playerId,blockedId] of [['A4-1-v2-4actor','A','B'],['B4-1-v2-4actor','T','A']]){
  const r=runs.find(x=>x.run_id===runId),c=createCrowd(r,{actorId:playerId}),baseline=createCrowd(r,{actorId:null});
  for(let k=0;k<600;k++){
   const s=c.step({},.1),b=baseline.step({},.1);close(s.t_sim,(k+1)*.1,1e-7);
   for(const a of s.actors.filter(x=>!x.is_player)){
    close(a.s_i+a.pause_total_i,s.t_sim,1e-7);
    close(a.pause_player_i + a.pause_script_i, a.pause_total_i, 1e-7);
    const other=b.actors.find(x=>x.actor_id===a.actor_id);
    if(a.pause_total_i===0&&other.pause_total_i===0&&a.present&&other.present){close(a.x,other.x);close(a.y,other.y);}
   }
  }
  const s=c.snapshot(),target=s.actors.find(x=>x.actor_id===blockedId);
  assert.ok(target.block_wait>8);assert.equal(s.events.filter(e=>e.type==='forced_overlap'&&e.kind==='player').length,0);
  let released=false;
  for(let k=0;k<20;k++){
   const before=c.snapshot(),p=before.actors.find(x=>x.is_player),a=before.actors.find(x=>x.actor_id===blockedId);
   const keys={d:p.x>a.x,a:p.x<a.x,w:p.y>a.y,s:p.y<a.y,shift:true};
   const after=c.step(keys,.1).actors.find(x=>x.actor_id===blockedId);
   if(after.blocked_by!==playerId&&after.s_i>a.s_i){released=true;break;}
  }
  assert.ok(released,runId);
 }
});
test('script mutual timeout only allows the later-priority script through; logs chain separately',()=>{
 const r=run([actor('T',[[0,0,0],[100,0,0]]),actor('A',[[0,-1.2,0],[100,98.8,0]]),actor('C',[[0,-2.4,0],[100,97.6,0]])]);
 const c=createCrowd(r,{actorId:'T'});
 for(let i=0;i<120;i++)c.step({},.1);
 const s=c.snapshot();assert.equal(s.events.filter(e=>e.kind==='player'&&e.type==='forced_overlap').length,0);
 assert.ok(s.events.some(e=>e.type==='forced_overlap'&&e.chain));
 for(const e of s.events.filter(e=>e.type==='forced_overlap')){assert.equal(e.i,'C');assert.equal(e.chain,true);
  assert.equal(e.cause, 'player_phase_shift');
  assert.equal(e.pause_player_i, 0); // C was delayed by A, not directly by the player.
  assert.deepEqual(e.tainted, {i: true, j: true});}
});
test('B4 T keeps the entered C→A pass at 13.1s and releases A in one step', () => {
 const r = runs.find(r => r.run_id === 'B4-1-v2-4actor');
 const crowd = createCrowd(r, {actorId: 'T'});
 for (let i = 0; i < 600; i++) {
  const snap = crowd.step({}, .1);
  if (snap.tick === 131) {
   const pass = snap.active_passes.find(p => p.i === 'C' && p.j === 'A');
   assert.ok(pass?.entered && pass.lingering);
   assert.equal(snap.events.some(e => e.type === 'pass_end' && e.i === 'C' && e.j === 'A'), false);
  }
 }
 const before = crowd.snapshot().actors.find(a => a.actor_id === 'A');
 const after = crowd.step({w: true, d: true, shift: true}, .1);
 const a = after.actors.find(a => a.actor_id === 'A');
 close(a.s_i, before.s_i + .1);
 assert.equal(a.blocked_by, null);
 const t = after.actors.find(a => a.is_player);
 const receipt = {tick: after.tick, t_sim: after.t_sim, A_script_s: a.s_i,
  T_A_m: Math.hypot(t.x-a.x, t.y-a.y), A_blocked_by: a.blocked_by, active_passes: after.active_passes};
 if (process.env.AMIDST_TEST_EVIDENCE) fs.writeFileSync(
  `${process.env.AMIDST_TEST_EVIDENCE}/b4-release.json`, JSON.stringify(receipt, null, 2));
});
test('C-5 a script conflict without direct player delay remains a failure event', () => {
 const routes = run([
  actor('T', [[0, 0, 10], [100, 0, 10]]),
  actor('A', [[0, 0, 0], [100, 0, 0]]),
  actor('C', [[0, -2, 0], [100, 98, 0]]),
 ]);
 for (const actorId of [null, 'T']) {
  const crowd = createCrowd(routes, {actorId});
  for (let tick = 0; tick < 80; tick++) crowd.step({}, .1);
  const events = crowd.snapshot().events;
  assert.equal(events.some(event => event.type === 'block_wait'), false);
  const forced = events.filter(event => event.type === 'forced_overlap');
  assert.ok(forced.length > 0);
  assert.ok(forced.every(event => event.kind === 'script' && event.cause === 'script' && !event.tainted.i && !event.tainted.j));
 }
});
test('C-1..5 fixed-seed 100s crowd stress, source line fidelity, independent clocks and C-7 timing',()=>{
 let seed=0x568;const random=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/2**32);
 const report=[];
 let phaseShiftCounterexample;
 for(const r of runs)for(const id of ['T','A','B','C']){
  const c=createCrowd(r,{actorId:id,resolve:checkedResolve}),baseline=createCrowd(r,{actorId:null,resolve:checkedResolve});
  let raw=0,penetrations=0,total=0,separated=0,excluded=0,compute=0,rawTotal=0,rawSeparated=0;
  for(let k=0;k<1000;k++){
   const before=c.snapshot(),p=before.actors.find(a=>a.is_player),others=before.actors.filter(a=>!a.is_player&&a.present);
   const nearest=others.sort((a,b)=>Math.hypot(a.x-p.x,a.y-p.y)-Math.hypot(b.x-p.x,b.y-p.y))[0];
   let keys={};if(k%80<55&&nearest){keys={w:nearest.y>p.y,s:nearest.y<p.y,d:nearest.x>p.x,a:nearest.x<p.x,shift:k%3===0};}else keys={w:random()>.5,s:random()>.5,a:random()>.5,d:random()>.5};
   const start=performance.now(),s=c.step(keys,.1);compute+=performance.now()-start;const base=baseline.step({},.1);
   checkPhase(s, .1);
   checkPhase(base, .1);
   if (r.run_id === 'A4-1-v2-4actor' && id === 'T' && s.tick === 787) {
    phaseShiftCounterexample = s.events.find(event => event.type === 'forced_overlap'
      && event.tick === 787 && event.i === 'C' && event.j === 'B');
    const completedPlayerWait = before.events
      .filter(event => event.type === 'block_wait' && event.i === 'B')
      .reduce((seconds, event) => seconds + event.waited_s, 0);
    const blocker = before.actors.find(a => a.actor_id === 'B');
    close(completedPlayerWait, 19);
    close(blocker.pause_total_i, 21.9);
    assert.equal(blocker.block_wait, 0);
   }
   for(const a of s.actors.filter(a=>!a.is_player)){
    close(a.s_i+a.pause_total_i,s.t_sim,1e-7);
    close(a.pause_player_i + a.pause_script_i, a.pause_total_i, 1e-7);
    const expected=scriptedPose(r.actors.find(x=>x.actor_id===a.actor_id),a.s_i,r.duration_us/1e6);
    const peer=base.actors.find(x=>x.actor_id===a.actor_id);if(a.pause_total_i===0&&peer.pause_total_i===0&&a.present&&peer.present){close(a.x,peer.x);close(a.y,peer.y);}
    assert.equal(a.present,!!expected);if(expected){close(a.x,expected.x,.001);close(a.y,expected.y,.001);}
   }
   const visible=s.actors.filter(x=>x.present);
   for(let i=0;i<visible.length;i++)for(let j=i+1;j<visible.length;j++){
    const a=visible[i],b=visible[j],d=Math.hypot(a.x-b.x,a.y-b.y),forced=s.forced_pairs.some(pair=>pair.includes(a.actor_id)&&pair.includes(b.actor_id));
    if((a.is_player||b.is_player)&&d<.58){raw++;if(!forced)penetrations++;}
    rawTotal++;if(d>=.58)rawSeparated++;
    if(forced){excluded++;continue;}total++;if(d>=.58)separated++;
   }
  }
  const s=c.snapshot(),forced=s.events.filter(e=>e.type==='forced_overlap');
  const ended = s.events.filter(e => e.type === 'pass_end');
  assert.equal(ended.length + s.active_passes.length, forced.length, JSON.stringify(s.events));
  const active = new Set();
  for (const event of s.events) {
   const pair = [event.i, event.j].sort().join('|');
   if (event.type === 'forced_overlap') active.add(pair);
   if (event.type === 'pass_end') {
    assert.ok(active.delete(pair), JSON.stringify(event));
    if (event.reason === 'timeout') assert.ok(event.duration_s <= s.config.pass_max_s + .1, JSON.stringify(event));
   }
  }
  assert.equal(active.size, s.active_passes.length);
  const allPasses = [...ended, ...s.active_passes];
  const metrics = {
   run: r.run_id,
   actor: id,
   raw_player_penetrations: raw,
   player_penetrations: penetrations,
   separation: separated / total,
   raw_separation: rawSeparated / rawTotal,
   pair_samples: rawTotal,
   nonseparated_excluding_passes: total - separated,
   excluded_pairs: excluded,
   exempt_steps: allPasses.reduce((sum, e) => sum + e.exempt_steps, 0),
   lingering_passes: allPasses.filter(e => e.lingering).length,
   lingering_steps: allPasses.reduce((sum, e) => sum + e.lingering_steps, 0),
   active_passes: s.active_passes,
   pass_ends: ended,
   baseline_forced_overlap: baseline.snapshot().events.filter(e => e.type === 'forced_overlap').length,
   forced_player_phase_shift: forced.filter(e => e.kind === 'script' && e.cause === 'player_phase_shift').length,
   forced_script_other: forced.filter(e => e.kind === 'script' && e.cause !== 'player_phase_shift').length,
   forced_player: forced.filter(e => e.kind === 'player').length,
   forced_nonchain: forced.filter(e => !e.chain).length,
   forced_chain: forced.filter(e => e.chain).length,
   mean_step_ms: compute / 1000,
   forced_events: forced,
  };
  report.push(metrics);
 }
 if(process.env.AMIDST_TEST_EVIDENCE)fs.writeFileSync(`${process.env.AMIDST_TEST_EVIDENCE}/crowd-stress.json`,JSON.stringify(report,null,2));
 console.log('CROWD_STRESS '+JSON.stringify(report));
 assert.ok(phaseShiftCounterexample, 'A4 player T emits C→B forced overlap at tick 787');
 close(phaseShiftCounterexample.t_sim, 78.7);
 assert.equal(phaseShiftCounterexample.chain, false);
 assert.equal(phaseShiftCounterexample.kind, 'script');
 assert.equal(phaseShiftCounterexample.cause, 'player_phase_shift');
 assert.equal(phaseShiftCounterexample.tainted.j, true);
 close(phaseShiftCounterexample.pause_player_j, 19);
 for (const metrics of report) {
  const receipt = JSON.stringify(metrics);
  assert.equal(metrics.player_penetrations, 0, receipt);
  assert.ok(metrics.separation >= .99, receipt);
  assert.equal(metrics.baseline_forced_overlap, 0, receipt);
  assert.equal(metrics.forced_player, 0, receipt);
  assert.equal(metrics.forced_script_other, 0, receipt);
 }
});

test('an absent actor advances its script clock while entry is obstructed', () => {
 const fixture = run([
  actor('T', [[0, 0, 0], [100, 0, 0]]),
  actor('A', [[0.2, 0.1, 0], [0.6, 1.2, 0], [100, 1.2, 0]]),
 ]);
 const crowd = createCrowd(fixture, { actorId: 'T' });
 const get = snap => snap.actors.find(a => a.actor_id === 'A');
 assert.equal(get(crowd.step({}, .1)).present, false);
 const obstructed = get(crowd.step({}, .1));
 assert.equal(obstructed.present, false);
 close(obstructed.s_i, .2);
 assert.equal(obstructed.pause_total_i, 0);
 assert.equal(obstructed.tainted, false);
 let latest;
 for (let i = 0; i < 5; i++) latest = get(crowd.step({}, .1));
 assert.equal(latest.present, true);
 assert.ok(latest.x >= .6);
 assert.equal(latest.pause_player_i, 0);
 assert.equal(latest.pause_script_i, 0);
 close(latest.s_i, .7);
});

test('an exempt script pair still checks collisions with a third actor', () => {
 const proposal = (id, x, next) => ({
  id, is_player: false, from: { x, y: 0 }, candidates: [{ x: next, y: 0 }, { x, y: 0 }],
 });
 const pair = new Set(['A|C']);
 const a = proposal('A', 0, 0), c = proposal('C', -.7, .15), b = proposal('B', .8, .65);
 assert.equal(resolveMoves([a, c], {}, pair).indices.C, 0);
 const result = resolveMoves([a, b, c], {}, pair);
 assert.equal(result.indices.C, 1);
 assert.equal(result.blocked.C, 'B');
 close(result.poses.C.x, -.7);
});

const passFixture = (path = [[0, 0, 0], [100, 0, 0]], player = false) => run([
 ...(player ? [actor('T', [[0, 0, 3], [100, 0, 3]])] : []),
 actor('A', path),
 actor('C', [[0, -2, 0], [100, 98, 0]]),
]);

test('a completed script crossing emits separated before the time cap', () => {
 const crowd = createCrowd(passFixture(), {actorId: null});
 for (let i = 0; i < 80; i++) crowd.step({}, .1);
 const end = crowd.snapshot().events.find(e => e.type === 'pass_end');
 assert.equal(end.reason, 'separated');
 assert.ok(end.duration_s > 0 && end.duration_s < 3);
 assert.ok(end.exempt_steps > 0);
});

test('a pass ends as receded when the second resolution moves apart before entry', () => {
 const crowd = createCrowd(passFixture(), {actorId: null, resolve(entities, cfg, ignored) {
  const result = resolveMoves(entities, cfg, ignored);
  if (ignored.has('A|C')) result.poses.C.x = entities.find(e => e.id === 'C').from.x - .2;
  return result;
 }});
 for (let i = 0; i < 50; i++) crowd.step({}, .1);
 const end = crowd.snapshot().events.find(e => e.type === 'pass_end');
 assert.equal(end.reason, 'receded');
 assert.equal(end.exempt_steps, 1);
});

test('an entered pass lingers through the cap and ends on separation', () => {
 const path = [[0, 0, 0], [4.5, 0, 0], [8.3, 3.8, 0], [100, 3.8, 0]];
 const crowd = createCrowd(passFixture(path), {actorId: null});
 let lingering;
 for (let i = 0; i < 125; i++) {
  const snap = crowd.step({}, .1);
  const last = snap.events.at(-1);
  if (snap.t_sim >= 8 && snap.t_sim <= 8.2) {
   assert.equal(snap.forced_pairs.length, 1);
   const a = snap.actors.find(a => a.actor_id === 'A'), c = snap.actors.find(a => a.actor_id === 'C');
   assert.ok(Math.hypot(a.x-c.x, a.y-c.y) < .6);
   assert.equal(a.blocked_by, null);
   assert.equal(c.blocked_by, null);
  }
  if (last?.type === 'pass_end') lingering = last;
 }
 assert.ok(lingering);
 assert.equal(lingering.reason, 'separated');
 assert.equal(lingering.lingering, true);
 assert.ok(lingering.duration_s > 3 && lingering.lingering_steps > 0);
 const forces = crowd.snapshot().events.filter(e => e.type === 'forced_overlap');
 assert.equal(forces.length, 1);
});

test('a pass that never enters while the player blocks the passer still times out', () => {
 const fixture = passFixture(undefined, true);
 // Keep the injected stop strictly outside 2r, away from floating-point boundary noise.
 for (const point of fixture.actors.find(a => a.actor_id === 'C').waypoints) point.xy[0] -= .05;
 const crowd = createCrowd(fixture, {actorId: 'T', resolve(entities, cfg, ignored) {
  const result = resolveMoves(entities, cfg, ignored);
  if (ignored.has('A|C')) {
   const mover = entities.find(e => e.id === 'C');
   result.poses.C = {...mover.from};
   result.blocked.C = 'T';
   result.indices.C = mover.candidates.length - 1;
  }
  return result;
 }});
 for (let i = 0; i < 80; i++) {
  const snap = crowd.step({}, .1);
  if (snap.forced_pairs.length) {
   const a = snap.actors.find(a => a.actor_id === 'A'), c = snap.actors.find(a => a.actor_id === 'C');
   assert.ok(Math.hypot(a.x-c.x, a.y-c.y) >= .6 - 1e-9);
   assert.equal(c.blocked_by, 'T');
  }
 }
 const end = crowd.snapshot().events.find(e => e.type === 'pass_end');
 assert.equal(end.reason, 'timeout');
 assert.equal(end.lingering, false);
 close(end.duration_s, 3);
});

test('malformed proposal still fails the strict resolver', () => {
 const a = {id: 'A', from: {x: 0, y: 0}, candidates: [{x: .2, y: 0}]};
 const b = {id: 'B', from: {x: .7, y: 0}, candidates: [{x: .5, y: 0}]};
 assert.throws(() => resolveMoves([a, b]), /CROWD_UNRESOLVED_PAIR/);
});

for (const strict of [undefined, false]) {
 test(`a second-round resolver error ${strict === false ? 'rolls back the step' : 'throws by default'}`, () => {
  let fail = true;
  const crowd = createCrowd(passFixture(), {actorId: null, strict, resolve(entities, cfg, ignored) {
   if (fail && ignored.size) throw new Error('CROWD_REJECTION_LIMIT');
   return resolveMoves(entities, cfg, ignored);
  }});
  for (let i = 0; i < 70; i++) {
   const before = crowd.snapshot();
   if (strict !== false) {
    try { crowd.step({}, .1); } catch (error) {
     assert.equal(error.message, 'CROWD_REJECTION_LIMIT');
     assert.deepEqual(crowd.snapshot(), before);
     return;
    }
    continue;
   }
   const after = crowd.step({}, .1);
   if (after.tick !== before.tick) continue;
   assert.deepEqual(after, {...before, events: [...before.events,
    {type: 'crowd_error', code: 'CROWD_REJECTION_LIMIT', tick: before.tick, t_sim: before.t_sim, count: 1}]});
   const repeated = crowd.step({}, .1);
   assert.deepEqual(repeated, {...after, events: [...before.events,
    {...after.events.at(-1), count: 2}]});
   fail = false;
   const resumed = crowd.step({}, .1);
   assert.equal(resumed.tick, before.tick + 1);
   assert.ok(resumed.events.some(e => e.type === 'forced_overlap'));
   assert.ok(resumed.forced_pairs.length);
   assert.throws(() => crowd.step({}, -1), /CROWD_DT_MUST_BE_0_TO_0_1/);
   return;
  }
  assert.fail('second resolver round was not reached');
 });
}
