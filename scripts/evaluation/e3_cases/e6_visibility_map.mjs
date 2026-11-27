// E6 design aid (#732): evaluation-only ASCII map of which cameras see each floor cell (same GT visibility function the
// LIVE A page logs). Not an input to inference. usage: e6_visibility_map.mjs ASSETS [step_m]
import {setup} from './generate.mjs';
import {groundTruthVisible} from '../../../frontend/live-mode/src/world.mjs';
import fs from 'node:fs';
import path from 'node:path';
import {ROOT} from './generate.mjs';
const [assets, stepArg] = process.argv.slice(2), step = Number(stepArg ?? .5);
const env = setup(assets), g = JSON.parse(fs.readFileSync(path.join(ROOT, 'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json')));
const L = {CAM_BRANCH: 'B', CAM_ENTRY: 'E', CAM_EXT_CAR: 'C', CAM_EXT_CLEAR: 'L', CAM_R101_IN: 'R', CAM_W1: '1', CAM_W2: '2', CAM_WIDE: 'W'};
console.log(Object.entries(L).map(([k, v]) => `${v}=${k}`).join(' '), '| * = 2+ cameras, . = blind, blank = no floor; columns step', step, 'm');
const inFloor = (x, y) => g.floors.some(f => x >= f.x_m[0] && x <= f.x_m[1] && y >= f.y_m[0] && y <= f.y_m[1]);
const xs = []; for (let x = -15; x <= 22.4; x += step) xs.push(+x.toFixed(3));
console.log('      x0=-15 ... ticks every 5 m: ' + xs.map(x => Number.isInteger(x / 5) ? '|' : ' ').join(''));
for (let y = 12; y >= -6; y -= step) {
 let s = y.toFixed(1).padStart(5) + ' ';
 for (const x of xs) {
  if (!inFloor(x, y)) { s += ' '; continue; }
  const c = groundTruthVisible(env.cams, env.world.blockers, env.world.root, x, y).map(id => L[id]);
  s += c.length === 0 ? '.' : c.length === 1 ? c[0] : '*';
 }
 console.log(s);
}
