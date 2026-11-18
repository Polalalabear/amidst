// Curated acceptance receipt + full LOCAL artifact manifest; no raw media is published.
// node scripts/live_mode/detection_receipt.mjs <work> <receipt-directory>
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
const [work, output] = process.argv.slice(2);
if (!work || !output) throw new Error('work and receipt-directory required');
const json = (p) => JSON.parse(fs.readFileSync(path.join(work, p)));
const sha = (data) => crypto.createHash('sha256').update(data).digest('hex');
const walk = (dir) => fs.readdirSync(path.join(work,dir),{withFileTypes:true}).flatMap(e =>
  e.isDirectory() ? walk(`${dir}/${e.name}`) : [`${dir}/${e.name}`]);
const groups = ['recording','diagnosis','routes','replay','paired_replay','latency'];
const files = groups.flatMap(walk).sort().map(p => { const b=fs.readFileSync(path.join(work,p));
  return { path:p, bytes:b.length, sha256:sha(b) }; });
const manifest = JSON.stringify({ path_base:'$AMIDST_ARTIFACTS/cx552-20261117', files },null,2);
fs.writeFileSync(path.join(work,'ARTIFACTS_MANIFEST.json'),manifest);
const lat = ['baseline_r1','baseline_r2','candidate_r1_retry','candidate_r2'].map(name => {
  const { rows, ...summary } = json(`latency/${name}.latency.json`); return summary;
});
const paired = Object.fromEntries(['baseline','redetected'].map(s => [s,
  json(`paired_replay/gate4_off/${s}/t1_summary.json`).runs.map(r=>({label:r.label,
    visible_ticks:r.evaluation_only.target_visible_ticks,on_target:r.evaluation_only.on_target,
    wrong_person:r.evaluation_only.wrong_person,lost:r.evaluation_only.lost}))]));
const pytest = fs.readFileSync(path.join(work,'pytest.txt'),'utf8');
const receipt = { issue:552, baseline:'31a69177', metric:json('diagnosis/deployed.summary.json').metric,
  source_recording_manifest_sha256:sha(fs.readFileSync(path.join(work,'recording/MANIFEST.json'))),
  source_inputs:json('recording/MANIFEST.json').inputs,
  baseline_detection:json('diagnosis/stretch.summary.json').thresholds['0.35'],
  final_detection:json('diagnosis/deployed.summary.json').calibrated_profile,
  diagnostic_controls:Object.fromEntries(['stretch','letterbox','bright','highres'].map(v=>
    [v,json(`diagnosis/${v}.summary.json`).thresholds['0.35'].by_camera])),
  latency:lat, existing_replay:json('replay/bench.json'), paired_rgb_replay:paired,
  focused_pytest:{command:'PYTHONPATH=src:<runtime-deps> uv run --offline --no-project --python "$PYTHON" python -m pytest tests/live_mode -q',
    passed:(pytest.match(/^\.+/m)||[''])[0].length,output:pytest.trim()},
  artifacts:{manifest:'$AMIDST_ARTIFACTS/cx552-20261117/ARTIFACTS_MANIFEST.json',sha256:sha(manifest),
    groups:Object.fromEntries(groups.map(g=>{const a=files.filter(f=>f.path.startsWith(g+'/'));
      return [g,{file_count:a.length,total_bytes:a.reduce((n,f)=>n+f.bytes,0)}]})),
    regeneration:'Commands in docs/operations/LIVE_DETECTION_HANDOFF_20261117.md; latency and capture clock not exactly reproducible'},
  not_verified:['human-operated routes','new scenes or characters','confirmed identity','physical safety',
    'paid advisor','8785 deployment','pixel-level occlusion attribution'],
  limitations:['One paired A4 recording: correct falls 0.737 to 0.705 and wrong-person rises 0.126 to 0.253',
    'Settings calibrated on this fixed grid and A4/B4; no independent held-out set',
    'First candidate latency attempt aborted with detached Frame; no usable values, retry retained',
    'Latency measured on shared GPU, two valid runs per setting; no confidence intervals'],
};
fs.mkdirSync(output,{recursive:true});
fs.writeFileSync(path.join(output,'acceptance.json'),JSON.stringify(receipt,null,2));
console.log(JSON.stringify({latency_p50:lat.map(r=>r.frame_latency_ms.p50),artifacts:receipt.artifacts}));
