// Bind a fixed evaluation recording to immutable LOCAL sources, without copying assets.
// node scripts/live_mode/detection_manifest.mjs <recording> <shared-local>
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
const [recording, shared] = process.argv.slice(2);
if (!recording || !shared) throw new Error('recording and shared-local required');
const entry = (root, relative) => {
  const bytes = fs.readFileSync(path.join(root, relative));
  return { path: relative, bytes: bytes.length, sha256: crypto.createHash('sha256').update(bytes).digest('hex') };
};
const files = ['evaluation_labels.json', ...fs.readdirSync(path.join(recording, 'rgb')).sort().map(f => `rgb/${f}`)]
  .map(f => entry(recording, f));
const inputs = ['data/live-assets-20261115/character.glb', 'data/live-assets-20261115/scene.glb',
  'data/live-assets-20261115/cameras.three.json', 'data/r004-build-v2-20261021/safe_static/cameras.json',
  'data/demo-owned-v1/models/rtdetr/rtdetr_r18vd_dec3_6x_coco_from_paddle.pth',
  'evidence/live-mode-n6-20261115/glb_n6scene_320x180_r1.rows.json'].map(f => entry(shared, f));
fs.writeFileSync(path.join(recording, 'MANIFEST.json'), JSON.stringify({
  schema: 'amidst.live-detection-recording.v1', run_id: 'cx552-fixed-grid-20261117',
  clock_id: 'cx552-static-grid-tick-v1', source: 'N6_WEBGL_RENDER_FROM_PINNED_GLBS',
  recorder_commit: 'b74bc723', sample_policy: { step_m: 1, headings_deg: [0,90,180,270],
    rgb_resolutions: [[320,180],[640,360]], jpeg_quality: 0.85, animation_idle_update_s: 0.5 },
  evaluation_only: ['evaluation_labels.json'], inference_inputs: 'rgb/*.jpg only',
  file_count: files.length, total_bytes: files.reduce((n,f)=>n+f.bytes,0), inputs, files,
  regeneration: 'record_detection_bench.mjs with the same pinned N6 inputs; new capture is a new recording; latency cannot be rebuilt exactly',
}, null, 2));
console.log(JSON.stringify({ file_count: files.length, total_bytes: files.reduce((n,f)=>n+f.bytes,0) }));
