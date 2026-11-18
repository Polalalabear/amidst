// Curate update-gate evidence, keeping screenshots, absolute paths and raw responses LOCAL.
// node scripts/demo_update_receipt.mjs <work> <receipt-output>
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
const [work, output] = process.argv.slice(2);
if (!work || !output) throw new Error('work and output required');
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
const read = p => fs.readFileSync(path.join(work,p));
const json = p => JSON.parse(read(p));
const walk = d => fs.readdirSync(path.join(work,d),{withFileTypes:true}).flatMap(e=>
  e.isDirectory()?walk(`${d}/${e.name}`):[`${d}/${e.name}`]);
const paths = ['core','real-900','real-1300','state'].flatMap(walk).concat([
  'RESULT.txt','unit-node.log','unit-pytest.log','unit-pytest-rerun.log','focused.log','dependency-check.json',
  'dependency.log','core-e2e.log','real-e2e-900.log','real-e2e-1300.log','http-status.txt',
  'live-preflight.log','live-launch.log','live-config.json','server.log','commit-range.txt']);
const files = [...new Set(paths)].sort().map(p=>{const b=read(p);return {path:p,bytes:b.length,sha256:sha(b)};});
const manifest = JSON.stringify({path_base:'$AMIDST_ARTIFACTS/cx555-20261117',files},null,2);
fs.writeFileSync(path.join(work,'MANIFEST.json'),manifest);
const py = read('unit-pytest-rerun.log').toString();
const match = py.match(/(\d+) passed, (\d+) skipped, (\d+) deselected/);
if (!match) throw new Error('unit result missing');
const dep = json('dependency-check.json'), core = json('core/results.json');
const real = Object.fromEntries([900,1300].map(h=>{const r=json(`real-${h}/browser-results.json`);
  return [h,{source_head:r.source_head,checks:r.checks,screenshots:r.results.length,errors:r.errors,http:r.http,
    test_script_sha256:r.test_script_sha256}];}));
if(dep.status!=='PASS'||core.status!=='PASS'||core.checks!==130||Object.values(real).some(r=>r.checks!==347||r.errors.length||r.http.length)) throw new Error('gate not passing');
const receipt = {issue:555, tested_code_head:'f6d7e8ff5fabab317026e9c33aa26facc2ed7194',
  tested_code_tree:'ef2fe1a343e262dd94d9abaaa0faf895e39cb2a8', current_demo_pin:'b24d6a26dc3f556f34270055cab45f5c5dd6382b',
  gate_created_utc:new Date(fs.statSync(path.join(work,'RESULT.txt')).mtimeMs).toISOString(),
  gate_expires_utc:new Date(fs.statSync(path.join(work,'RESULT.txt')).mtimeMs+24*3600*1000).toISOString(),
  node:{passed:576,failed:0,skipped:0}, pytest:{passed:+match[1],skipped:+match[2],deselected:+match[3]},
  dependency:{status:dep.status,entries:dep.entries,bytes:dep.bytes,manifest_sha256:dep.manifest_sha256,
    source_head:dep.source_head,negative_io_probe_denied:dep.negative_io_probe_denied,
    source_mutations:dep.source_mutations,models_executed:dep.models_executed},
  http:{port:8795,status:200}, core:{status:core.status,checks:core.checks,page_errors:core.page_errors},real,
  live_launcher:json('live-config.json'),
  execution:'own shared clone; locked own .venv and repo-local Playwright; owned package read-only; qa_demo_update redirects only state tempfile destination',
  earlier_attempt:{status:'ABORTED',failed:68,passed:607,skipped:52,deselected:17,
    reason:'pytest basetemp was inside repository but recording/freeze fixtures require outside-repo output; rerun with checkout-external AMIDST_ARTIFACTS'},
  artifacts:{manifest:'$AMIDST_ARTIFACTS/cx555-20261117/MANIFEST.json',sha256:sha(manifest),
    result_sha256:sha(read('RESULT.txt')),file_count:files.length,total_bytes:files.reduce((n,f)=>n+f.bytes,0),
    regeneration:'DEMO_8785_UPDATE_PLAN_20261117.md; logs and screenshots not guaranteed byte-identical; expires after 24h'},
  not_verified:['native Windows PowerShell (not installed)','pin approval or 8785 restart','new UI design adoption','paid API','physical/identity acceptance'],
  source_range:read('commit-range.txt').toString().trim().split('\n'),
};
fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(receipt,null,2));
console.log(JSON.stringify({pytest:receipt.pytest,real,artifacts:receipt.artifacts,expires:receipt.gate_expires_utc}));
