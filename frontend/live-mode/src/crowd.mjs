// Operator-side circle proxy only. No DOM, renderer, network or inference imports.
import {scriptedPose, playerCandidates, blocked, DEFAULT_CROWD_CONFIG} from './sim.mjs';
export {DEFAULT_CROWD_CONFIG};
const ORDER=['T','A','B','C'];
const distance=(a,b)=>a&&b?Math.hypot(a.x-b.x,a.y-b.y):Infinity;
const key=(a,b)=>[a,b].sort().join('|');
const copy=value=>JSON.parse(JSON.stringify(value));
const priority=e=>e.is_player?-1:ORDER.indexOf(e.id);
const changed=(a,b)=>!!a!==!!b || (!!a&&distance(a,b)>1e-12);
function config(overrides={}){
 const cfg={...DEFAULT_CROWD_CONFIG,...overrides};
 for(const [k,v] of Object.entries(cfg))if(!Number.isFinite(v)||v<0||((k==='r_person'||k==='r_wall')&&v===0))throw new Error(`INVALID_CROWD_CONFIG:${k}`);
 if('wait_max_player_s' in cfg)throw new Error('PLAYER_WAIT_HAS_NO_TIMEOUT');
 return Object.freeze(cfg);
}

// Finite rejection: every change advances one candidate index; snapshots are never mutated.
export function resolveMoves(entities,overrides={},ignoredPairs=new Set()){
 const cfg=config(overrides),indices=Object.fromEntries(entities.map(e=>[e.id,0])),blockedBy={};
 const sorted=[...entities].sort((a,b)=>priority(a)-priority(b));
 const pose=e=>e.candidates[indices[e.id]];
 const moving=e=>changed(e.from,pose(e));
 let remaining=entities.reduce((n,e)=>n+e.candidates.length,0)+1;
 while(remaining-->0){
  let rejected=false;
  for(let i=0;i<sorted.length&&!rejected;i++)for(let j=i+1;j<sorted.length&&!rejected;j++){
   const a=sorted[i],b=sorted[j];if(ignoredPairs.has(key(a.id,b.id)))continue;
   const next=distance(pose(a),pose(b)),cur=distance(a.from,b.from);
   if(!(next<2*cfg.r_person-1e-12&&next<cur-1e-12))continue;
   const loser=[b,a].find(e=>moving(e)&&indices[e.id]+1<e.candidates.length);
   if(!loser)throw new Error('CROWD_UNRESOLVED_PAIR');
   indices[loser.id]++;blockedBy[loser.id]=loser===a?b.id:a.id;rejected=true;
  }
  if(!rejected)return {poses:Object.fromEntries(entities.map(e=>[e.id,copy(pose(e))])),blocked:blockedBy,indices};
 }
 throw new Error('CROWD_REJECTION_LIMIT');
}

export function validateScripts(run,overrides={}){
 const cfg=config(overrides),duration=run.duration_us/1e6,pairs=[];
 for(let a=0;a<run.actors.length;a++)for(let b=a+1;b<run.actors.length;b++){
  const x=run.actors[a],y=run.actors[b];let minimum=Infinity,at=null,open=null;const overlaps=[];
  for(let k=0;k<Math.ceil(duration*10);k++){
   const t=k/10,p=scriptedPose(x,t,duration),q=scriptedPose(y,t,duration),d=distance(p,q);
   if(d<minimum){minimum=d;at=t;}
   if(d<2*cfg.r_person){if(open===null)open=k;}
   else if(open!==null){overlaps.push({start_s:open/10,end_s:k/10,samples:k-open});open=null;}
  }
  if(open!==null)overlaps.push({start_s:open/10,end_s:duration,samples:Math.ceil(duration*10)-open});
  pairs.push({actors:[x.actor_id,y.actor_id],minimum_m:minimum,time_s:at,overlaps});
 }
 const choices=[null,...ORDER].map(actor_id=>({actor_id,pairs:copy(pairs),script_ids:run.actors.filter(a=>a.actor_id!==actor_id).map(a=>a.actor_id)}));
 return {run_id:run.run_id,r_person:cfg.r_person,dt_s:.1,choices,minimum_m:Math.min(...pairs.map(p=>p.minimum_m)),overlap_samples:pairs.reduce((n,p)=>n+p.overlaps.reduce((s,r)=>s+r.samples,0),0)};
}

export function createCrowd(run,{actorId='T',cfg:overrides={},segments=[],auto=false}={}){
 const cfg=config(overrides),duration=run.duration_us/1e6;
 if(actorId!==null&&!ORDER.includes(actorId))throw new Error('ACTOR_UNKNOWN');
 const selected=run.actors.find(a=>a.actor_id===actorId);
 if(actorId!==null&&!selected)throw new Error('ACTOR_NOT_IN_RUN');
 const scripts=run.actors.filter(a=>a.actor_id!==actorId).map(actor=>({
  actor, s_i:0, pause_total_i:0, playerPauseSeconds:0,
  pose:scriptedPose(actor,0,duration), waited_s:0, blocker:null, block_wait:0,
 }));
 const player=selected?{x:selected.waypoints[0].xy[0],y:selected.waypoints[0].xy[1],heading:0,moving:false,running:false}:null;
 const events=[],spawn_adjusted=[],passes=new Map();let tick=0,t_sim=0,playerPresent=!!player;
 if(player&&!auto){
  const clear=q=>!blocked(q.x,q.y,segments,cfg.r_wall)&&scripts.every(s=>distance(q,s.pose)>=2*cfg.r_person);
  if(!clear(player)){
   const from={x:player.x,y:player.y};let found=null;
   for(let radius=.05;radius<=5&&!found;radius+=.05)for(let k=0;k<64&&!found;k++){
    const q={x:from.x+radius*Math.cos(2*Math.PI*k/64),y:from.y+radius*Math.sin(2*Math.PI*k/64)};if(clear(q))found=q;
   }
   if(!found)throw new Error('SPAWN_NO_FREE_POINT');Object.assign(player,found);
   spawn_adjusted.push({type:'spawn_adjusted',tick:0,t_sim:0,i:actorId,from,to:found,dist_m:distance(from,found)});
  }
 }
 function snapshot(){
  const actors=scripts.map(s=>({actor_id:s.actor.actor_id,variant:s.actor.actor_id,is_player:false,present:!!s.pose,x:s.pose?.x??null,y:s.pose?.y??null,heading:s.pose?.heading??0,speed:s.speed||0,s_i:s.s_i,pause_total_i:s.pause_total_i,block_wait:s.block_wait,blocked_by:s.blocker}));
  if(player)actors.unshift({actor_id:actorId,variant:actorId,is_player:true,present:playerPresent,...player,speed:player.speed||0});
  return copy({tick,t_sim,actors,events,spawn_adjusted,forced_pairs:[...passes.values()].map(p=>[p.i,p.j]),config:cfg});
 }
 function step(keys={},dt=.1){
  if(!Number.isFinite(dt)||dt<=0||dt>.1+1e-9)throw new Error('CROWD_DT_MUST_BE_0_TO_0_1');
  const entities=[];
  if(player){
   const candidates=auto?[scriptedPose(selected,t_sim+dt,duration),playerPresent?{...player}:null]:playerCandidates(player,keys,dt,segments,cfg);
   entities.push({id:actorId,is_player:true,from:playerPresent?{...player}:null,candidates});
  }
  for(const s of scripts)entities.push({id:s.actor.actor_id,is_player:false,from:s.pose,candidates:[scriptedPose(s.actor,s.s_i+dt,duration),s.pose]});
  // Resolve first: a timer alone must not manufacture a pass when the pair is no longer blocked.
  let resolved=resolveMoves(entities,cfg,new Set(passes.keys()));
  for(let round=0;round<scripts.length;round++){
   let added=false;
   for(const s of scripts){
    const id=s.actor.actor_id,why=resolved.blocked[id],peer=scripts.find(p=>p.actor.actor_id===why);
    if(!peer||resolved.indices[id]===0||s.blocker!==why||s.waited_s<cfg.wait_max_mutual_s-1e-9||ORDER.indexOf(id)<ORDER.indexOf(why))continue;
    const pair=key(id,why);if(passes.has(pair))continue;
    const chain=!!player&&resolved.blocked[why]===actorId;
    const e={type:'forced_overlap',tick:tick+1,t_sim:t_sim+dt,i:id,j:why,kind:'script',waited_s:s.waited_s,dist_m:distance(s.pose,peer.pose),chain};
    // A direct player wait leaves a persistent delay in this actor's script clock.
    if (s.playerPauseSeconds > 0 || peer.playerPauseSeconds > 0) e.cause = 'player_phase_shift';
    events.push(e);passes.set(pair,{...e,entered:false});added=true;
   }
   if(!added)break;
   resolved=resolveMoves(entities,cfg,new Set(passes.keys()));
  }
  if(player){
   const p=resolved.poses[actorId],old={...player};playerPresent=!!p;
   if(p)Object.assign(player,p,{speed:distance(old,p)/dt});else player.speed=0;
  }
  for(const s of scripts){
   const id=s.actor.actor_id,rejected=resolved.indices[id]>0,why=resolved.blocked[id]??null;
   if(rejected){s.pause_total_i+=dt;s.speed=0;s.waited_s=s.blocker===why?s.waited_s+dt:dt;}
   else{s.s_i+=dt;s.speed=s.pose&&resolved.poses[id]?distance(s.pose,resolved.poses[id])/dt:0;s.waited_s=0;}
   const waitedOnPlayer=rejected&&player&&why===actorId;
   if (waitedOnPlayer) {
    s.block_wait += dt;
    s.playerPauseSeconds += dt;
   }
   else if(s.block_wait){events.push({type:'block_wait',tick:tick+1,t_sim:t_sim+dt,i:id,j:'player',waited_s:s.block_wait});s.block_wait=0;}
   s.blocker=rejected?why:null;s.pose=resolved.poses[id];
  }
  for(const [pair,p] of passes){
   const a=scripts.find(s=>s.actor.actor_id===p.i)?.pose,b=scripts.find(s=>s.actor.actor_id===p.j)?.pose;
   const d=distance(a,b);if(d<2*cfg.r_person)p.entered=true;
   if(!a||!b||(d>=2*cfg.r_person&&(p.entered||d>p.dist_m+1e-9)))passes.delete(pair);
  }
  tick++;t_sim+=dt;return snapshot();
 }
 return Object.freeze({session:Object.freeze({actor_id:actorId,run_id:run.run_id}),step,snapshot});
}
