// A-private production plans. No scored answers; never imported by inference or ranking.
import {HARDSET_ROUTES} from '../../../frontend/live-mode/src/hardset_routes.mjs';
const copy = id => structuredClone(HARDSET_ROUTES[id]);
const walk = (x,y) => ({mode:'walk',to_xy:[x,y]});
const run = (x,y) => ({mode:'run',to_xy:[x,y]});
const hold = seconds => ({mode:'hold',seconds});
const until = t_s => ({mode:'hold_until',t_s});
export const E3_ROUTES = {
 'E3-A1': {...copy('H2-1'), source_route:'H2-1', family:'A', tail_s:5},
 'E3-A2': {...copy('H2-2'), source_route:'H2-2', family:'A', tail_s:7},
 'E3-A3': {...copy('H2-3'), source_route:'H2-3', family:'A', tail_s:7},
 'E3-B1': {...copy('H3-1'), source_route:'H3-1', family:'B', tail_s:3},
 'E3-B2': {run_id:'A4-1',start_xy:[-10,-.4],family:'B',tail_s:3,
  steps:[hold(3),until(22),run(-3.35,-.25),run(3.4,.5),walk(2,-1.35),hold(7),walk(3.4,.5),hold(6)]},
 'E3-C1': {...copy('H4-3'), source_route:'H4-3', family:'C', tail_s:3},
 'E3-C2': {...copy('H4-2'), source_route:'H4-2', family:'C', tail_s:3},
 'E3-D1': {...copy('H3-2'), source_route:'H3-2', family:'D', tail_s:3},
 'E3-D2': {run_id:'B4-1',start_xy:[4,1],family:'D',tail_s:3,
  steps:[hold(.5),run(.35,1.7),run(-2.5,1.2),run(-3.35,.2),until(14),
   run(-2.5,1.2),run(.35,1.7),run(4,1),run(8,.6),run(11.4,1.3),until(26.6),
   walk(13,1.1),walk(14,1.1),walk(13.75,.5),hold(3),walk(14.1,1.1),
   run(16.7,1.8),run(16.7,13.5),hold(5)]},
};
