import test from 'node:test';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import zlib from 'node:zlib';
import { clampFrame, formatTime, frameName, mediaUrl, planTick, stepFrame } from './sync.mjs';
import { inspectPng, parseMediaPath, validateRun, resolveSafeFile } from './guard.mjs';
import { createServer } from './server.mjs';

const RUN = { key: 'T-1', label: 't', runId: 'r', frames: 4, cameras: ['CAM_A', 'CAM_B'] };

function chunk(type, data) {
  const head = Buffer.alloc(8);
  head.writeUInt32BE(data.length, 0);
  head.write(type, 4, 'latin1');
  return Buffer.concat([head, data, Buffer.alloc(4)]);
}
function png({ w = 960, h = 540, extra = null } = {}) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  const parts = [Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk('IHDR', ihdr)];
  if (extra) parts.push(chunk(extra, Buffer.from('x')));
  parts.push(chunk('IDAT', zlib.deflateSync(Buffer.from([0]))), chunk('IEND', Buffer.alloc(0)));
  return Buffer.concat(parts);
}
async function makeRoot(opts = {}) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ev-'));
  for (const cam of RUN.cameras) {
    const dir = path.join(root, RUN.key, 'safe', 'media', cam);
    await fs.mkdir(dir, { recursive: true });
    for (let i = 0; i < RUN.frames; i++) await fs.writeFile(path.join(dir, `${frameName(i)}.png`), png(opts.png));
  }
  await fs.mkdir(path.join(root, 'gt_private'));
  await fs.writeFile(path.join(root, 'gt_private', 'secret.txt'), 'SECRET');
  return await fs.realpath(root);
}

test('同步邏輯：frame、時間、步進皆夾在範圍內', () => {
  assert.equal(clampFrame(-3, 250), 0);
  assert.equal(clampFrame(999, 250), 249);
  assert.equal(stepFrame(249, 1, 250), 249);
  assert.equal(stepFrame(0, -1, 250), 0);
  assert.equal(formatTime(0, 5), '00:00.0');
  assert.equal(formatTime(249, 5), '00:49.8');
  assert.equal(formatTime(300, 5), '01:00.0');
  assert.equal(mediaUrl('A4-1', 'CAM_W1', 7), '/media/A4-1/CAM_W1/000007.png');
});

test('播放排程：逐格前進、未就緒停滯而不跳格、落後重新對齊', () => {
  const base = { total: 10, fps: 5 };
  assert.equal(planTick({ ...base, now: 100, nextDue: 200, frame: 3, ready: true }).action, 'wait');
  assert.equal(planTick({ ...base, now: 200, nextDue: 200, frame: 3, ready: false }).action, 'stall');
  const ok = planTick({ ...base, now: 210, nextDue: 200, frame: 3, ready: true });
  assert.deepEqual([ok.action, ok.frame, ok.nextDue, ok.late], ['advance', 4, 400, false]);
  const late = planTick({ ...base, now: 900, nextDue: 200, frame: 3, ready: true });
  assert.equal(late.frame, 4);
  assert.equal(late.late, true);
  assert.equal(late.nextDue, 1100);
  assert.equal(planTick({ ...base, now: 5000, nextDue: 0, frame: 9, ready: true }).action, 'end');
});

test('白名單：只接受已設定的 run／camera／範圍內 index', () => {
  const runs = [RUN];
  assert.deepEqual(parseMediaPath('/media/T-1/CAM_A/000003.png', runs).index, 3);
  for (const bad of [
    '/media/T-1/CAM_A/000004.png', '/media/T-1/CAM_Z/000000.png', '/media/X/CAM_A/000000.png',
    '/media/T-1/CAM_A/../CAM_B/000000.png', '/media/T-1/CAM_A/%2e%2e%2f000000.png',
    '/media/gt_private/CAM_A/000000.png', '/media/T-1/CAM_A/000000.png/x', '/gt_private/secret.txt',
    '/media/T-1/CAM_A/00000.png', '/media/T-1/CAM_A/000000.jpg',
  ]) assert.equal(parseMediaPath(bad, runs), null, bad);
});

test('symlink 一律拒絕（檔案、目錄）', async () => {
  const root = await makeRoot();
  const cam = path.join(root, RUN.key, 'safe', 'media', 'CAM_A');
  await fs.rm(path.join(cam, '000001.png'));
  await fs.symlink(path.join(root, 'gt_private', 'secret.txt'), path.join(cam, '000001.png'));
  assert.equal(await resolveSafeFile(root, RUN, 'CAM_A', 1), null);
  assert.ok(await resolveSafeFile(root, RUN, 'CAM_A', 0));
  const moved = path.join(root, RUN.key, 'safe', 'media', 'CAM_B');
  await fs.rename(moved, `${moved}_real`);
  await fs.symlink(`${moved}_real`, moved);
  assert.equal(await resolveSafeFile(root, RUN, 'CAM_B', 0), null);
});

test('manifest 驗證：完整通過；缺檔、多檔、缺鏡頭、壞 PNG、含 metadata 皆 UNAVAILABLE', async () => {
  const root = await makeRoot();
  assert.equal((await validateRun(root, RUN)).status, 'OK');
  const camA = path.join(root, RUN.key, 'safe', 'media', 'CAM_A');

  await fs.rm(path.join(camA, '000002.png'));
  assert.equal((await validateRun(root, RUN)).status, 'UNAVAILABLE');
  await fs.writeFile(path.join(camA, '000002.png'), png());
  await fs.writeFile(path.join(camA, '000009.png'), png());
  assert.equal((await validateRun(root, RUN)).status, 'UNAVAILABLE');
  await fs.rm(path.join(camA, '000009.png'));
  assert.equal((await validateRun(root, RUN)).status, 'OK');

  await fs.writeFile(path.join(camA, '000000.png'), png({ extra: 'tEXt' }));
  assert.match((await validateRun(root, RUN)).reason, /tEXt/);
  await fs.writeFile(path.join(camA, '000000.png'), png({ w: 100, h: 100 }));
  assert.match((await validateRun(root, RUN)).reason, /尺寸/);
  await fs.writeFile(path.join(camA, '000000.png'), Buffer.from('not png at all, just text padding......'));
  assert.equal((await validateRun(root, RUN)).status, 'UNAVAILABLE');
  await fs.writeFile(path.join(camA, '000000.png'), png());

  await fs.rename(path.join(root, RUN.key, 'safe', 'media', 'CAM_B'), path.join(root, 'moved'));
  assert.equal((await validateRun(root, RUN)).status, 'UNAVAILABLE');
  assert.equal((await validateRun(root, { ...RUN, key: 'NOPE' })).status, 'UNAVAILABLE');
});

test('inspectPng 拒絕缺 IEND 與非 PNG', () => {
  assert.equal(inspectPng(png()).ok, true);
  assert.equal(inspectPng(png().subarray(0, 60)).ok, false);
  assert.equal(inspectPng(Buffer.alloc(40)).ok, false);
});

test('server：不符時不提供影像；gt_private 與穿越路徑回 404', async () => {
  const { RUNS } = await import('./runs.mjs');
  const root = await makeRoot(); // 結構與 RUNS 不符 → 全部 UNAVAILABLE
  const { server, status } = await createServer(root);
  for (const s of status.values()) assert.equal(s.status, 'UNAVAILABLE');
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const base = `http://127.0.0.1:${server.address().port}`;
  const runs = await (await fetch(`${base}/api/runs`)).json();
  assert.equal(runs.length, RUNS.length);
  assert.ok(runs.every((r) => r.status === 'UNAVAILABLE' && r.reason));
  for (const p of [`/media/${RUNS[0].key}/${RUNS[0].cameras[0]}/000000.png`, '/gt_private/secret.txt', '/../etc/passwd', '/media/../gt_private/secret.txt']) {
    const res = await fetch(`${base}${p}`);
    assert.equal(res.status, 404, p);
  }
  assert.equal((await fetch(`${base}/`, { method: 'POST' })).status, 405);
  server.close();
});
