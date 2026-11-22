// #652 extension: authored A-private controls, fixed before any experiment output.
const walk=(x,y)=>({mode:'walk',to_xy:[x,y]});
const run=(x,y)=>({mode:'run',to_xy:[x,y]});
const hold=seconds=>({mode:'hold',seconds});
const until=t_s=>({mode:'hold_until',t_s});
const westStart=wait=>[hold(3),until(wait),run(-3.35,-.25),run(3.4,.5)];
const eastStart=wait=>[hold(.5),run(.35,1.7),run(-2.5,1.2),run(-3.35,.2),until(wait),
 run(-2.5,1.2),run(.35,1.7),run(4,1),run(8,.6),run(11.4,1.3),walk(11.4,.6)];
function blindCycles(start,holds,visible){
 const steps=[...start,hold(3.2)];
 for(const seconds of holds)steps.push(walk(3.4,.5),walk(2,-1.35),hold(seconds),walk(3.4,.5),walk(...visible),hold(3.2));
 return steps;
}
function branches(start,holds){
 const steps=[...start,hold(3.2)];
 for(const [i,seconds]of holds.entries()){
  if(i%2===0)steps.push(walk(13,.5),walk(13.75,.5),hold(seconds),walk(14.6,.5),walk(15.5,1.1),walk(16.7,1.8));
  else steps.push(walk(15.5,1.1),walk(14.6,.5),walk(13.75,.5),hold(seconds),walk(13,.5),walk(11.4,.6));
  steps.push(hold(3.2));
 }
 return steps;
}
export const REAPPEARANCE_ROUTES={
 'E3-B3':{run_id:'A4-1',start_xy:[-10,-.4],family:'B',tail_s:1,
  steps:blindCycles(westStart(22),[3,4,5,4,3],[3.4,.5])},
 'E3-B4':{run_id:'A4-1',start_xy:[-10,-.4],family:'B',tail_s:1,
  steps:blindCycles(westStart(25),[4,3,5,3,4],[4.35,1.1])},
 'E3-B5':{run_id:'A4-1',start_xy:[-10,-.4],family:'B',tail_s:1,
  steps:blindCycles(westStart(28),[5,3,4,5,3],[3.4,.5])},
 'E3-C3':{run_id:'B4-1',start_xy:[4,1],family:'C',tail_s:1,
  steps:branches(eastStart(14),[3,4,3,4,3])},
 'E3-C4':{run_id:'B4-1',start_xy:[4,1],family:'C',tail_s:1,
  steps:branches(eastStart(22),[4,3,4,3,4])},
 'E3-C5':{run_id:'B4-1',start_xy:[4,1],family:'C',tail_s:1,
  steps:branches(eastStart(21),[3,5,4,3,4])},
};
export const REAPPEARANCE_POLICY=Object.freeze({
 min_blind_s:3,max_blind_s:10,pre_visible_s:3,post_visible_s:3,
 points_per_gap:1,window_s:3,minimum_new_points:27,
 base_declared_reappearance_points:3,base_declared_primary_points:38,
 selection:'SCRIPT_AND_GT_ONLY_NO_AGENT_OR_RULE_OUTPUTS',
 c_requirement:'different visible camera sets before and after gap; no claim about top3 without experiment outputs',
});
