// D214：#529 八鏡頭 run 的註冊與驗證。合成資料測結構；真實 LOCAL 資料只在存在時驗證（不存在就略過）。
import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { promises as fs, existsSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import zlib from 'node:zlib';
import { RUNS } from './runs.mjs';
import { validateRun, parseMediaPath, relativeMediaPath } from './guard.mjs';
import { createServer } from './server.mjs';
import { frameName } from './sync.mjs';

const CAMS = ['CAM_BRANCH', 'CAM_ENTRY', 'CAM_EXT_CAR', 'CAM_EXT_CLEAR', 'CAM_R101_IN', 'CAM_W1', 'CAM_W2', 'CAM_WIDE'];
const sha = (b) => createHash('sha256').update(b).digest('hex');
function chunk(type, data) {
  const head = Buffer.alloc(8); head.writeUInt32BE(data.length, 0); head.write(type, 4, 'latin1');
  const crc = Buffer.alloc(4); crc.writeUInt32BE(zlib.crc32(Buffer.concat([head.subarray(4), data])), 0);
  return Buffer.concat([head, data, crc]);
}
const PIXELS = zlib.deflateSync(Buffer.alloc(540 * (1 + 960 * 3)));
function png() {
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(960, 0); ihdr.writeUInt32BE(540, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk('IHDR', ihdr), chunk('IDAT', PIXELS), chunk('IEND', Buffer.alloc(0))]);
}

const FRAMES = 3;
// 合成 run：與 runs.mjs 的結構相同（mediaDir／manifest），manifest 的 SHA 在建立後才知道。
async function makeBundle({ dropFrame = false, badSha = false, extraFrame = false } = {}) {
  const root = await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), 'ev8-')));
  const runId = 'r-test-a4-1';
  const frames = [];
  for (const cam of CAMS) {
    const dir = path.join(root, 'rgb', runId, cam);
    await fs.mkdir(dir, { recursive: true });
    for (let i = 0; i < FRAMES; i++) {
      const buf = png();
      if (!(dropFrame && cam === 'CAM_ENTRY' && i === 1)) await fs.writeFile(path.join(dir, `${frameName(i)}.png`), buf);
      frames.push({ camera_id: cam, frame_index: i, relative_path: `rgb/${runId}/${cam}/${frameName(i)}.png`, sha256: badSha && cam === 'CAM_W2' && i === 2 ? '0'.repeat(64) : sha(buf), source_time_us: i * 200000 });
    }
  }
  if (extraFrame) await fs.writeFile(path.join(root, 'rgb', runId, 'CAM_W1', `${frameName(FRAMES)}.png`), png());
  await fs.mkdir(path.join(root, 'runs'));
  const raw = Buffer.from(JSON.stringify({ run_id: runId, fps: 5, camera_ids: CAMS, frames }));
  await fs.writeFile(path.join(root, 'runs', 'A4-1.json'), raw);
  const run = { key: 'T-8CAM', label: 't', runId, frames: FRAMES, source: 'eightcam', mediaDir: ['rgb', runId], manifest: { path: ['runs', 'A4-1.json'], sha256: sha(raw) }, cameras: CAMS };
  return { root, run };
}

test('註冊：兩個新 run 各 8 台相機、固定 frame 數、來源為 eightcam；舊 run 原封不動', () => {
  const [a, b, a8, b8] = RUNS;
  assert.deepEqual(RUNS.map((r) => r.key), ['A4-1', 'B4-1', 'A4-1-8CAM', 'B4-1-8CAM']);
  assert.equal(a.cameras.length, 4); assert.equal(b.cameras.length, 5);
  assert.equal(a.frames, 250); assert.equal(b.frames, 210);
  assert.equal(a.source, undefined); assert.equal(a.mediaDir, undefined);
  for (const [r, frames] of [[a8, 250], [b8, 210]]) {
    assert.deepEqual(r.cameras, CAMS); assert.equal(r.frames, frames); assert.equal(r.source, 'eightcam');
    assert.match(r.manifest.sha256, /^[0-9a-f]{64}$/);
    assert.ok(r.cameras.includes('CAM_ENTRY'));
    // 路徑一律相對，不含絕對路徑
    assert.ok(!r.mediaDir.some((p) => path.isAbsolute(p) || p.includes('..')) && !path.isAbsolute(relativeMediaPath(r, 'CAM_W1', 0)));
  }
  assert.equal(a8.clock.wall_origin, '2026-11-01T14:00:00+08:00'); assert.equal(b8.clock.wall_origin, '2026-11-01T14:10:00+08:00');
  assert.equal(parseMediaPath('/media/A4-1-8CAM/CAM_ENTRY/000249.png', RUNS).camera, 'CAM_ENTRY');
  assert.equal(parseMediaPath('/media/A4-1-8CAM/CAM_ENTRY/000250.png', RUNS), null);
  assert.equal(parseMediaPath('/media/A4-1/CAM_WIDE/000000.png', RUNS), null); // 舊 run 沒有 WIDE
});

test('合成 8 台 bundle：影格數、SHA 與 manifest 一致才 OK', async () => {
  const { root, run } = await makeBundle();
  const r = await validateRun(root, run);
  assert.equal(r.status, 'OK'); assert.equal(r.digests.size, 8 * FRAMES);
});

test('缺影格 → 不可用（INTEGRITY_FAIL，不補、不顯示）；SHA 與 manifest 不符、多一格也是 INTEGRITY_FAIL', async () => {
  for (const opts of [{ dropFrame: true }, { badSha: true }, { extraFrame: true }]) {
    const { root, run } = await makeBundle(opts);
    const r = await validateRun(root, run);
    assert.equal(r.status, 'UNAVAILABLE', JSON.stringify(opts));
    assert.equal(r.code, 'INTEGRITY_FAIL', JSON.stringify(opts));
  }
});

test('manifest 內容被改（SHA 不等於 runs.mjs 釘住的值）→ INTEGRITY_FAIL；manifest 缺 → UNAVAILABLE', async () => {
  const { root, run } = await makeBundle();
  await fs.appendFile(path.join(root, 'runs', 'A4-1.json'), ' ');
  assert.equal((await validateRun(root, run)).code, 'INTEGRITY_FAIL');
  await fs.rm(path.join(root, 'runs', 'A4-1.json'));
  assert.equal((await validateRun(root, run)).code, 'UNAVAILABLE');
});

test('server：沒給 --root-8cam 時只有新 run 顯示 UNAVAILABLE，舊 run 由自己的 root 決定；影格 API 對 UNAVAILABLE 回 404', async () => {
  const { server, status } = await createServer({ legacy: null, eightcam: null });
  assert.deepEqual([...status.keys()], RUNS.map((r) => r.key));
  assert.ok([...status.values()].every((s) => s.status === 'UNAVAILABLE'));
  await new Promise((ok) => server.listen(0, '127.0.0.1', ok));
  try {
    const base = `http://127.0.0.1:${server.address().port}`;
    const runs = await (await fetch(`${base}/api/runs`)).json();
    assert.equal(runs.length, 4); assert.deepEqual(runs[2].cameras, CAMS);
    assert.equal((await fetch(`${base}/media/A4-1-8CAM/CAM_ENTRY/000000.png`)).status, 404);
  } finally { server.close(); }
});

// 真實 #529 LOCAL 資料：只在 AMIDST_ARTIFACTS（預設 ~/amidst/local）下存在時驗證。
const ART = process.env.AMIDST_ARTIFACTS || path.join(os.homedir(), 'amidst', 'local');
const REAL = path.join(ART, 'data', 'r004-4actor-natural-walk-eightcam-20261114', 'bundle', 'safe');
test('真實 #529 safe bundle：兩個新 run 全量驗證 OK，8 台 × 影格數；root-8cam 缺時不影響舊 run 的狀態判定', { skip: !existsSync(REAL) && 'LOCAL #529 資料不存在' }, async () => {
  const { server, status } = await createServer({ legacy: null, eightcam: REAL });
  server.close();
  for (const key of ['A4-1-8CAM', 'B4-1-8CAM']) {
    const run = RUNS.find((r) => r.key === key);
    assert.equal(status.get(key).status, 'OK', key);
    assert.equal(status.get(key).digests.size, 8 * run.frames);
  }
  assert.equal(status.get('A4-1').status, 'UNAVAILABLE'); // legacy root 未提供
});
