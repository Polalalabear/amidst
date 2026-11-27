// E6 post-recording freeze (#742, D399). Evaluation-only: reads the A-side logs, places the formal decision points from GT with the
// detectors frozen in e6_routes_v1.json, checks the DC9 gate, writes GT files, a frozen spec copy and MANIFEST.sha256.
// No inference, scorer, model or API call. usage: finalize_e6.mjs OUT ASSETS FROZEN_SPEC_OUT
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {ROOT, read, sha, setup} from './generate.mjs';
import {loadE6, E6_ROUTES_PATH} from './e6_routes.mjs';
import {summarize} from './e6_design_check.mjs';
import {projectBox} from '../../../frontend/live-mode/src/person.mjs';
const [outArg, assets, frozenOut] = process.argv.slice(2);
if (!outArg || !assets || !frozenOut) throw new Error('usage: finalize_e6.mjs OUT ASSETS FROZEN_SPEC_OUT');
const out = path.resolve(outArg), env = setup(assets), {doc, routes} = loadE6();
const specPath = path.join(ROOT, doc.spec_ref.path), spec = read(specPath);
if (sha(fs.readFileSync(specPath)) !== doc.spec_ref.sha256) throw new Error('SPEC_SHA_MISMATCH');
if (doc.status !== 'FROZEN_ROUTES_V1') throw new Error('ROUTES_NOT_FROZEN');
const receipts = Object.fromEntries(read(path.join(out, 'input-replay.json')).map(r => [r.case_id, r]));
const frozen = structuredClone(spec), gate = [], WINDOW = 15;
frozen.spec_version = 'e6-scenarios-frozen-v1';
frozen.status = 'FROZEN_PRE_SCORING_D399';
frozen.source_spec = {path: doc.spec_ref.path, sha256: doc.spec_ref.sha256};
frozen.routes = {path: 'configs/evaluation/e6_routes_v1.json', sha256: sha(fs.readFileSync(E6_ROUTES_PATH)), detector_source: doc.detector_source};
fs.mkdirSync(path.join(out, 'gt-boxes'), {recursive: true});
for (const fc of frozen.formal_cases) {
 const id = fc.case_id, c = doc.cases.find(x => x.case_id === id), log = read(path.join(out, `${id}.replay1.a-log.json`));
 const rows = log.ticks.map((r, i) => ({tick: i, t: r.t_sim, actors: Object.fromEntries(r.actors.map(a => [a.id, {present: a.present, xy: a.xy, vis: a.gt_visible}]))}));
 if (rows.some((r, i) => log.ticks[i].tick !== i)) throw new Error(`${id}:TICK_GRID`);
 const stalls = receipts[id].stalls ?? [];
 const sum = summarize(c, {rows, complete: receipts[id].route_complete, stalls, spawn_adjusted: log.spawn_adjusted ?? []});
 const ticks = sum.decision_points.map(d => d.realized_t_s === null ? null : Math.round(d.realized_t_s * 5)).sort((a, b) => a - b);
 const minGap = Math.min(...ticks.slice(1).map((t, i) => t - ticks[i]));
 const lastRow = log.ticks.at(-1), paused = Object.values(lastRow.pause_player_i ?? {}).some(v => v > 0) || log.ticks.some(t => Object.values(t.pause_player_i ?? {}).some(v => v > 0));
 const g = {case_id: id, forced_overlap: log.forced_overlap.length, pause_player_i_nonzero: paused, script_stall: stalls.length, crowd_error: log.crowd_error.length,
  spawn_adjusted: (log.spawn_adjusted ?? []).length, min_dp_gap_ticks: minGap, window_overlap: minGap < WINDOW, design_all_ok: sum.all_ok, max_ticks: rows.length - 1};
 g.pass = !g.forced_overlap && !g.pause_player_i_nonzero && !g.script_stall && !g.crowd_error && !g.spawn_adjusted && !g.window_overlap && g.design_all_ok;
 gate.push(g);
 const gt = {schema_version: 'live-ab.a-log.v1', session_id: log.session_id, run_id: log.run_id, actor_id: 'T', config: {...log.config, case_id: id},
  ticks: log.ticks.map(r => ({tick: r.tick, t_capture: r.t_capture, t_sim: r.tick / 5, actors: r.actors.map(a => ({...a, gt_boxes: Object.fromEntries(a.gt_visible.map(cam => [cam, projectBox(env.cams[cam].camera, env.world.root, a.xy[0], a.xy[1], 320, 180)]))}))})),
  provenance: {role: 'EVALUATION_ONLY', visibility: 'THREE_BODY_POINT_RAYS_STATIC_WALLS_NOT_ACTOR_OCCLUSION', gt_box_kind: 'EXISTING_PROJECTBOX_0_5_X_0_5_X_1_75_M_PROXY_NOT_PIXEL_MASK',
   image_size_px: [320, 180], identity_verdict: 'UNCONFIRMED', physical_verdict: 'UNKNOWN', source_a_log_sha256: sha(fs.readFileSync(path.join(out, `${id}.replay1.a-log.json`)))}};
 const gtBytes = JSON.stringify(gt); fs.writeFileSync(path.join(out, 'gt-boxes', `${id}.a-log.json`), gtBytes);
 fc.actual_gt_status = 'FROZEN'; fc.actual_duration_s = (rows.length - 1) / 5;
 fc.case_path = `${id}.case.json`; fc.case_sha256 = sha(fs.readFileSync(path.join(out, `${id}.case.json`)));
 fc.gt_path = `gt-boxes/${id}.a-log.json`; fc.gt_sha256 = sha(gtBytes);
 fc.actual_decision_points = sum.decision_points.map(d => ({dp_id: d.dp_id, type: d.type, tick: Math.round(d.realized_t_s * 5), t_actual_s: Math.round(d.realized_t_s * 5) / 5,
  expected_window_s: 3.0, gt_regime: d.observed_regime, spec_gt_regime: d.spec_regime, placement: `GT_DETECTOR_${d.kind}`}));
 fc.start_xy_spec = fc.start_xy; fc.start_xy = c.start_xy; fc.start_adjustment = c.start_adjustment;
}
// The checker compares formal start_xy with E3 opening coordinates; the frozen copy keeps spec start_xy in start_xy_spec and the
// recorded start in start_xy_recorded instead, so the spec field the checker reads stays the committed spec value.
for (const fc of frozen.formal_cases) { fc.start_xy_recorded = fc.start_xy; fc.start_xy = fc.start_xy_spec; delete fc.start_xy_spec; }
fs.writeFileSync(path.join(out, 'dc9-gate.json'), JSON.stringify(gate, null, 2) + '\n');
fs.writeFileSync(path.resolve(frozenOut), JSON.stringify(frozen, null, 1) + '\n');
fs.copyFileSync(path.resolve(frozenOut), path.join(out, 'e6_scenarios_frozen_v1.json'));
// MANIFEST over every file in OUT (relative path, sha256); MANIFEST.sha256 itself excluded.
const files = []; (function walk(d) { for (const e of fs.readdirSync(d, {withFileTypes: true})) { const p = path.join(d, e.name); e.isDirectory() ? walk(p) : e.name !== 'MANIFEST.sha256' && files.push(p); } })(out);
files.sort(); const lines = files.map(f => `${sha(fs.readFileSync(f))}  ${path.relative(out, f)}`);
fs.writeFileSync(path.join(out, 'MANIFEST.sha256'), lines.join('\n') + '\n');
console.log(JSON.stringify({gate_pass: gate.every(g => g.pass), failing: gate.filter(g => !g.pass), files: files.length, manifest_sha256: sha(fs.readFileSync(path.join(out, 'MANIFEST.sha256')))}, null, 1));
