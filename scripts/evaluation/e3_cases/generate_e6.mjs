// E6 input recordings (#732 G1+G2). Same production path as generate.mjs; only the route/run source differs.
// usage: generate_e6.mjs OUT ASSETS [CASE_IDS...]   (A-side only: no detector, model or API call)
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {ROOT, read, sha, setup, generate} from './generate.mjs';
import {loadE6} from './e6_routes.mjs';
if (process.argv[1] === fileURLToPath(import.meta.url)) {
 const [out, assets, ...ids] = process.argv.slice(2);
 if (!out || !assets) throw new Error('usage: generate_e6.mjs OUT ASSETS [CASE_IDS...]');
 fs.mkdirSync(out, {recursive: true});
 const {routes, runs} = loadE6(), env = setup(assets), receipts = [];
 const scenario = read(path.join(ROOT, 'docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json'));
 const chosen = ids.length ? ids : Object.keys(routes);
 for (const id of chosen) {
  if (!routes[id]) throw new Error(`E6_CASE_UNKNOWN:${id}`);
  const {data, receipt} = await generate(routes[id], id, env), bytes = JSON.stringify(data);
  fs.writeFileSync(path.join(out, `${id}.case.json`), bytes);
  receipts.push({...receipt, case_sha256: sha(bytes), bytes: Buffer.byteLength(bytes)});
  console.log(id, receipt.duration_s, receipt.capture_ticks, receipt.replay_state_sha256[0]);
 }
 // Scenario document served to the LIVE page by record.mjs via E3_SCENARIO_JSON (E6 runs replace the A4/B4 runs).
 fs.writeFileSync(path.join(out, 'e6-scenario.json'), JSON.stringify({...scenario, document: 'E6 routes scenario (generated, #732)', runs: runs.filter(r => chosen.includes(r.run_id))}));
 fs.writeFileSync(path.join(out, 'input-replay.json'), JSON.stringify(receipts, null, 2) + '\n');
}
