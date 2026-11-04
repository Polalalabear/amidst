import test from 'node:test';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import zlib from 'node:zlib';
import { clampFrame, formatTime, frameName, mediaUrl, planTick, stampText, stampParts, virtualTime, stepFrame } from './sync.mjs';
import { inspectPng, parseMediaPath, validateRun, resolveSafeFile, loadVerifiedFrame } from './guard.mjs';
import { RUNS } from './runs.mjs';
import { createServer } from './server.mjs';

const RUN = { key: 'T-1', label: 't', runId: 'r', frames: 4, cameras: ['CAM_A', 'CAM_B'] };

function chunk(type, data) {
  const head = Buffer.alloc(8);
  head.writeUInt32BE(data.length, 0);
  head.write(type, 4, 'latin1');
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(zlib.crc32(Buffer.concat([head.subarray(4), data])), 0);
  return Buffer.concat([head, data, crc]);
}
const EXTRA_OK = {
  sRGB: Buffer.from([0]),
  gAMA: Buffer.from([0, 0, 0xb1, 0x8f]),
  cHRM: Buffer.concat(Array.from({ length: 8 }, () => Buffer.from([0, 0, 0x75, 0x30]))),
  pHYs: Buffer.from([0, 0, 0x0b, 0x13, 0, 0, 0x0b, 0x13, 1]),
  oFFs: Buffer.alloc(9),
};
const PIXELS = zlib.deflateSync(Buffer.alloc(540 * (1 + 960 * 3)));
// opts：extra＝型別（合規內容）；extraData＝自訂 extra payload；ihdr／idat／iendData／tail 供反例改寫。
function png({ w = 960, h = 540, extra = null, extraData = null, ihdrLen = 13, idat = PIXELS, iendData = Buffer.alloc(0), tail = null } = {}) {
  const ihdr = Buffer.alloc(ihdrLen);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  const parts = [Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk('IHDR', ihdr)];
  if (extra) parts.push(chunk(extra, extraData ?? EXTRA_OK[extra] ?? Buffer.from('x')));
  parts.push(chunk('IDAT', idat), chunk('IEND', iendData));
  if (tail) parts.push(tail);
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
  assert.equal(formatTime(0, 5), '0.00 s');
  assert.equal(formatTime(249, 5), '49.80 s');
  assert.equal(formatTime(300, 5), '60.00 s');
  assert.equal(formatTime(1, 3), '0.33 s');
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
  assert.equal((await validateRun(root, RUN)).code, 'INTEGRITY_FAIL');
  await fs.writeFile(path.join(camA, '000000.png'), png({ w: 100, h: 100 }));
  assert.equal((await validateRun(root, RUN)).code, 'INTEGRITY_FAIL');
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
  const root = await makeRoot(); // 結構與 RUNS 不符 → 全部 UNAVAILABLE
  const { server, status } = await createServer(root);
  for (const s of status.values()) assert.equal(s.status, 'UNAVAILABLE');
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const base = `http://127.0.0.1:${server.address().port}`;
  const runs = await (await fetch(`${base}/api/runs`)).json();
  assert.equal(runs.length, RUNS.length);
  assert.ok(runs.every((r) => r.status === 'UNAVAILABLE' && r.code === 'UNAVAILABLE' && !('reason' in r)));
  for (const p of [`/media/${RUNS[0].key}/${RUNS[0].cameras[0]}/000000.png`, '/gt_private/secret.txt', '/../etc/passwd', '/media/../gt_private/secret.txt']) {
    const res = await fetch(`${base}${p}`);
    assert.equal(res.status, 404, p);
  }
  assert.equal((await fetch(`${base}/`, { method: 'POST' })).status, 405);
  server.close();
});

// ---- 以下為 P1 修補的反例（全為 SYNTHETIC，建在 tmp，不碰任何真實資料）----
const CANARY = 'SYNTHETIC_PRIVATE_CANARY';
const SYN = { key: 'S-1', label: 's', runId: 'syn', frames: 6, cameras: ['CAM_A', 'CAM_B'] };

async function makeSyn() {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'evs-'));
  for (const cam of SYN.cameras) {
    const dir = path.join(root, SYN.key, 'safe', 'media', cam);
    await fs.mkdir(dir, { recursive: true });
    for (let i = 0; i < SYN.frames; i++) await fs.writeFile(path.join(dir, `${frameName(i)}.png`), png());
  }
  return await fs.realpath(root);
}
const frameFile = (root, cam, i) => path.join(root, SYN.key, 'safe', 'media', cam, `${frameName(i)}.png`);

test('inspectPng：白名單外區塊（含 tEXt/iTXt/zTXt/eXIf/iCCP/tIME/私有）、壞 CRC、尾端多餘 bytes 皆拒絕', () => {
  for (const extra of ['tEXt', 'iTXt', 'zTXt', 'eXIf', 'iCCP', 'tIME', 'sPLT', 'prVt']) {
    assert.equal(inspectPng(png({ extra })).ok, false, extra);
  }
  for (const extra of ['gAMA', 'sRGB', 'cHRM', 'pHYs', 'oFFs']) assert.equal(inspectPng(png({ extra })).ok, true, extra);
  const bad = png();
  bad[bad.length - 1] ^= 0xff; // IEND 的 CRC
  assert.equal(inspectPng(bad).ok, false);
  assert.equal(inspectPng(Buffer.concat([png(), Buffer.from(CANARY)])).ok, false);
});

test('未抽樣的影格帶 tEXt：啟動全量驗證即 INTEGRITY_FAIL', async () => {
  const root = await makeSyn();
  // 首／中／末（0、3、5）以外的格
  const text = Buffer.concat([Buffer.from('route\0'), Buffer.from(CANARY)]);
  const poisoned = png();
  const ihdrEnd = 8 + 25;
  const withText = Buffer.concat([poisoned.subarray(0, ihdrEnd), chunkOf('tEXt', text), poisoned.subarray(ihdrEnd)]);
  await fs.writeFile(frameFile(root, 'CAM_A', 1), withText);
  const v = await validateRun(root, SYN);
  assert.deepEqual([v.status, v.code], ['UNAVAILABLE', 'INTEGRITY_FAIL']);
  assert.ok(!JSON.stringify(v).includes(CANARY));
});
function chunkOf(type, data) {
  const head = Buffer.alloc(8);
  head.writeUInt32BE(data.length, 0);
  head.write(type, 4, 'latin1');
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(zlib.crc32(Buffer.concat([head.subarray(4), data])), 0);
  return Buffer.concat([head, data, crc]);
}

test('SHA 不符：驗證後被換掉的影格（即使仍是合法 PNG）不送出', async () => {
  const root = await makeSyn();
  const v = await validateRun(root, SYN);
  assert.equal(v.status, 'OK');
  assert.ok(await loadVerifiedFrame(root, SYN, v.digests, 'CAM_A', 2));
  // 換成另一個合法但 bytes 不同的 PNG（多一個白名單內的 gAMA 區塊）
  await fs.writeFile(frameFile(root, 'CAM_A', 2), png({ extra: 'gAMA', extraData: Buffer.from([0, 0, 0, 9]) }));
  assert.equal(await loadVerifiedFrame(root, SYN, v.digests, 'CAM_A', 2), null);
  // 換成帶 tEXt 的 bytes 同樣不送
  await fs.writeFile(frameFile(root, 'CAM_A', 4), png({ extra: 'tEXt' }));
  assert.equal(await loadVerifiedFrame(root, SYN, v.digests, 'CAM_A', 4), null);
  // 未登錄的 index／camera
  assert.equal(await loadVerifiedFrame(root, SYN, v.digests, 'CAM_A', 99), null);
  assert.equal(await loadVerifiedFrame(root, SYN, v.digests, 'CAM_Z', 0), null);
});

async function makeLinked(linkLevel) {
  const root = await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), 'evl-')));
  // 測試用 private 目錄，只放帶 canary 名稱的空目錄，沒有任何真實 GT
  const priv = path.join(root, 'gt_private');
  await fs.mkdir(path.join(priv, 'media', `${CANARY}_DIR`), { recursive: true });
  await fs.mkdir(path.join(root, SYN.key), { recursive: true });
  if (linkLevel === 'safe') await fs.symlink(priv, path.join(root, SYN.key, 'safe'));
  if (linkLevel === 'media') {
    await fs.mkdir(path.join(root, SYN.key, 'safe'));
    await fs.symlink(path.join(priv, 'media'), path.join(root, SYN.key, 'safe', 'media'));
  }
  if (linkLevel === 'run') {
    await fs.rm(path.join(root, SYN.key), { recursive: true });
    await fs.symlink(priv, path.join(root, SYN.key));
  }
  return root;
}

test('上層 symlink（run／safe／media）指向 private：fail-closed，且錯誤碼不含名稱', async () => {
  for (const level of ['run', 'safe', 'media']) {
    const root = await makeLinked(level);
    const v = await validateRun(root, SYN);
    assert.deepEqual([v.status, v.code], ['UNAVAILABLE', 'UNAVAILABLE'], level);
    assert.ok(!JSON.stringify(v).includes(CANARY), level);
  }
});

test('API／頁面：symlink 與錯誤情境下回應只含固定碼，不含路徑或目錄名稱；根目錄 symlink 亦 fail-closed', async () => {
  const real = RUNS[0];
  // run 的 safe 為 symlink，指向放有 canary 目錄名的 test private
  const root = await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), 'evr-')));
  const priv = path.join(root, 'gt_private');
  await fs.mkdir(path.join(priv, 'media', CANARY), { recursive: true });
  await fs.mkdir(path.join(root, real.key));
  await fs.symlink(priv, path.join(root, real.key, 'safe'));
  const link = path.join(os.tmpdir(), `evroot-${process.pid}`);
  await fs.symlink(root, link);
  try {
    for (const arg of [root, link]) {
      const { server, status } = await createServer(arg);
      await new Promise((r) => server.listen(0, '127.0.0.1', r));
      const base = `http://127.0.0.1:${server.address().port}`;
      const text = await (await fetch(`${base}/api/runs`)).text();
      const runs = JSON.parse(text);
      assert.deepEqual(runs.map((r) => r.key), RUNS.map((r) => r.key)); // 只列宣告的 run
      assert.ok(runs.every((r) => r.status === 'UNAVAILABLE' && ['UNAVAILABLE', 'INTEGRITY_FAIL'].includes(r.code)));
      for (const bad of [CANARY, 'gt_private', root, os.tmpdir(), 'evr-', 'evroot']) assert.ok(!text.includes(bad), bad);
      const res = await fetch(`${base}/media/${real.key}/${real.cameras[0]}/000000.png`);
      assert.equal(res.status, 404);
      assert.ok(![...status.values()].some((s) => JSON.stringify(s).includes(CANARY)));
      server.close();
    }
  } finally {
    await fs.rm(link, { force: true });
  }
});

test('頁面不回顯 reason：app.mjs 只讀 run.code', async () => {
  const src = await fs.readFile(new URL('./app.mjs', import.meta.url), 'utf8');
  assert.ok(!/run\.reason|\.reason/.test(src));
  assert.match(src, /run\.code/);
});

// ---- 增量複審 P1：chunk 長度／結構（全為 SYNTHETIC；canary 為合成字串）----
const IEND_CANARY = Buffer.from('route\0SYNTHETIC_PRIVATE_IEND_METADATA_CANARY');
const reason = (b) => inspectPng(b).reason;

test('IEND 帶 payload（CRC 重算正確）被拒；IEND 之後有尾巴被拒', () => {
  assert.equal(reason(png({ iendData: IEND_CANARY })), 'iend-length');
  assert.equal(reason(png({ tail: Buffer.from('x') })), 'trailing-bytes');
  assert.equal(reason(png({ tail: chunk('IEND', Buffer.alloc(0)) })), 'trailing-bytes');
  assert.equal(reason(png({ tail: chunk('tEXt', IEND_CANARY) })), 'trailing-bytes');
});

test('IHDR 長度不符、格式不符被拒', () => {
  assert.equal(reason(png({ ihdrLen: 14 })), 'ihdr-first');
  assert.equal(reason(png({ ihdrLen: 12 })), 'ihdr-first');
  assert.equal(reason(png({ w: 959 })), 'size');
});

test('輔助區塊：長度錯、值超界、重複、型別在白名單外一律拒絕', () => {
  assert.equal(reason(png({ extra: 'sRGB', extraData: IEND_CANARY })), 'ancillary-shape');
  assert.equal(reason(png({ extra: 'gAMA', extraData: Buffer.from('ROUTE') })), 'ancillary-shape');
  assert.equal(reason(png({ extra: 'cHRM', extraData: Buffer.from('route\0SYNTHETIC_PRIVATE_CANARY_32BYTES!!').subarray(0, 32) })), 'ancillary-shape');
  assert.equal(reason(png({ extra: 'pHYs', extraData: Buffer.from('SYNTHETIC') })), 'ancillary-shape');
  assert.equal(reason(png({ extra: 'oFFs', extraData: Buffer.from('SYNTHETIC') })), 'ancillary-shape');
  for (const extra of ['PLTE', 'tRNS', 'sBIT', 'bKGD']) assert.equal(reason(png({ extra, extraData: Buffer.alloc(3) })), 'chunk-not-allowed', extra);
  const dup = png();
  const g = chunk('sRGB', Buffer.from([0]));
  const at = 8 + 25;
  assert.equal(reason(Buffer.concat([dup.subarray(0, at), g, g, dup.subarray(at)])), 'duplicate');
});

test('IDAT：必須完整解壓為恰好的像素量；zlib 尾巴、過短、壞過濾位元組被拒；IDAT 不可被打斷', () => {
  assert.equal(reason(png({ idat: zlib.deflateSync(Buffer.from([0])) })), 'idat');
  assert.equal(reason(png({ idat: Buffer.concat([PIXELS, IEND_CANARY]) })), 'idat');
  const bad = Buffer.alloc(540 * (1 + 960 * 3)); bad[0] = 9;
  assert.equal(reason(png({ idat: zlib.deflateSync(bad) })), 'idat');
  const base = png();
  const at = 8 + 25;
  const half = Math.floor(PIXELS.length / 2);
  const split = Buffer.concat([base.subarray(0, at), chunk('IDAT', PIXELS.subarray(0, half)), chunk('sRGB', Buffer.from([0])), chunk('IDAT', PIXELS.subarray(half)), chunk('IEND', Buffer.alloc(0))]);
  assert.equal(inspectPng(split).ok, false);
  const ok = Buffer.concat([base.subarray(0, at), chunk('IDAT', PIXELS.subarray(0, half)), chunk('IDAT', PIXELS.subarray(half)), chunk('IEND', Buffer.alloc(0))]);
  assert.equal(inspectPng(ok).ok, true);
});

test('Codex 反例：未抽樣的影格 IEND 帶 canary → 啟動 INTEGRITY_FAIL、HTTP 404 且 body 不含 canary', async () => {
  const root = await makeSyn();
  await fs.writeFile(frameFile(root, 'CAM_A', 1), png({ iendData: IEND_CANARY }));
  const v = await validateRun(root, SYN);
  assert.deepEqual([v.status, v.code], ['UNAVAILABLE', 'INTEGRITY_FAIL']);
  assert.ok(!JSON.stringify(v).includes('CANARY'));
  // 啟動後才換（模擬 SHA 比對）：換成 IEND 帶 payload 的檔案，不送出
  const root2 = await makeSyn();
  const ok = await validateRun(root2, SYN);
  assert.equal(ok.status, 'OK');
  await fs.writeFile(frameFile(root2, 'CAM_B', 2), png({ iendData: IEND_CANARY }));
  assert.equal(await loadVerifiedFrame(root2, SYN, ok.digests, 'CAM_B', 2), null);
});

test('HTTP 反例（完整 A4-1 SYNTHETIC，只毒化一格 IEND）：UNAVAILABLE／404 且 body 不含 canary；未毒化對照為 OK／200', async () => {
  const run = RUNS[0];
  const build = async (poison) => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'evh-'));
    const good = png();
    for (const cam of run.cameras) {
      const dir = path.join(root, run.key, 'safe', 'media', cam);
      await fs.mkdir(dir, { recursive: true });
      for (let i = 0; i < run.frames; i++) await fs.writeFile(path.join(dir, `${frameName(i)}.png`), good);
    }
    if (poison) await fs.writeFile(path.join(root, run.key, 'safe', 'media', run.cameras[0], `${frameName(1)}.png`), png({ iendData: IEND_CANARY }));
    return await fs.realpath(root);
  };
  for (const poison of [false, true]) {
    const root = await build(poison);
    const { server, status } = await createServer(root);
    await new Promise((r) => server.listen(0, '127.0.0.1', r));
    const base = `http://127.0.0.1:${server.address().port}`;
    const res = await fetch(`${base}/media/${run.key}/${run.cameras[0]}/000001.png`);
    const body = Buffer.from(await res.arrayBuffer());
    if (poison) {
      assert.deepEqual([status.get(run.key).status, status.get(run.key).code], ['UNAVAILABLE', 'INTEGRITY_FAIL']);
      assert.equal(res.status, 404);
      assert.ok(!body.includes('CANARY'));
    } else {
      assert.equal(status.get(run.key).status, 'OK');
      assert.equal(res.status, 200);
    }
    server.close();
    await fs.rm(root, { recursive: true, force: true });
  }
});

test('畫格標籤：<鏡頭> · <虛擬世界時間>（UTC+8）＋次要行 +<經過秒數> s · DECLARED_DEMO_CLOCK；時鐘缺失則 UNKNOWN、不假設日期', () => {
  const [a4, b4] = [RUNS[0].clock, RUNS[1].clock];
  assert.equal(stampText('CAM_ENTRY', 62, 5, a4), 'CAM_ENTRY · 2026-11-01 14:00:12.40（UTC+8）\n+12.40 s · DECLARED_DEMO_CLOCK');
  assert.equal(stampParts('CAM_W1', 0, 5, a4).main, 'CAM_W1 · 2026-11-01 14:00:00.00（UTC+8）');
  assert.equal(stampParts('CAM_W1', 100, 5, a4).main, 'CAM_W1 · 2026-11-01 14:00:20.00（UTC+8）');
  assert.equal(stampParts('CAM_W1', 249, 5, a4).main, 'CAM_W1 · 2026-11-01 14:00:49.80（UTC+8）');
  assert.equal(stampParts('CAM_W1', 105, 5, b4).main, 'CAM_W1 · 2026-11-01 14:10:21.00（UTC+8）');
  assert.equal(virtualTime(0, 5, a4).declared, true);
  // 時鐘缺失或無效：虛擬時間 UNKNOWN，經過秒數仍保留為次要資訊
  assert.equal(stampText('CAM_W1', 62, 5, null), 'CAM_W1 · UNKNOWN\n+12.40 s · CLOCK_MAPPING_MISSING');
  assert.equal(stampParts('X', 1, 5, { ...a4, timezone: 'Not/AZone' }).main, 'X · UNKNOWN');
  assert.equal(stampParts('X', 1, 5, { ...a4, wall_origin: 'bad' }).main, 'X · UNKNOWN');
  for (const bad of [null, undefined, NaN, -1, 1.5]) assert.equal(stampText('CAM_W1', bad, 5, a4), 'CAM_W1 · UNKNOWN');
  assert.equal(stampText('CAM_W1', 3, 0, a4), 'CAM_W1 · UNKNOWN');
  assert.notEqual(stampText('A', 5, 5, a4), stampText('B', 5, 5, a4));
});

test('已宣告的展示時鐘逐欄等於 configs/q1q5/clocks（不自行假設日期），並由 /api/runs 提供', async () => {
  const dir = new URL('../../configs/q1q5/clocks/', import.meta.url);
  for (const [run, file] of [[RUNS[0], 'r004_a4_v1.json'], [RUNS[1], 'r004_b4_v1.json']]) {
    const c = JSON.parse(await fs.readFile(new URL(file, dir), 'utf8'));
    assert.equal(c.run_id, run.runId);
    for (const k of ['clock_id', 'mapping_kind', 'timezone', 'wall_origin', 't0_us', 'rate']) assert.equal(run.clock[k], c[k], `${run.key}.${k}`);
    assert.equal(c.mapping_kind, 'DECLARED_DEMO_CLOCK');
  }
  const dir2 = await fs.mkdtemp(path.join(os.tmpdir(), 'ev-clock-'));
  const { server } = await createServer(path.join(dir2, 'missing'));
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  try {
    const runs = await (await fetch(`http://127.0.0.1:${server.address().port}/api/runs`)).json();
    assert.equal(runs[0].clock.wall_origin, '2026-11-01T14:00:00+08:00');
    assert.equal(runs[1].clock.wall_origin, '2026-11-01T14:10:00+08:00');
  } finally { server.close(); await fs.rm(dir2, { recursive: true, force: true }); }
});

import { parseEmbed, acceptViewMessage as acceptViewMsg, INSUFFICIENT_TEXT as VIEWER_INSUFFICIENT } from './sync.mjs';

test('embed: params are validated; simple view shows the fixed 證據不足 notice; only the parent loopback window may switch the view', () => {
  const keys = ['A4-1', 'B4-1'];
  assert.deepEqual(parseEmbed('?embed=1&view=simple&run=B4-1', keys), { embed: true, view: 'simple', run: 'B4-1' });
  assert.deepEqual(parseEmbed('?embed=1&view=x&run=../gt_private', keys), { embed: true, view: 'system', run: null });
  assert.deepEqual(parseEmbed('', keys), { embed: false, view: 'system', run: null });
  assert.equal(VIEWER_INSUFFICIENT, '證據不足');
  const parent = {};
  const ok = { source: parent, origin: 'http://127.0.0.1:8766', data: { type: 'amidst.view', view: 'simple' } };
  assert.equal(acceptViewMsg(ok, parent), 'simple');
  assert.equal(acceptViewMsg({ ...ok, source: {} }, parent), null);
  assert.equal(acceptViewMsg({ ...ok, origin: 'http://evil.test' }, parent), null);
  assert.equal(acceptViewMsg({ ...ok, data: { type: 'amidst.view', view: 'x' } }, parent), null);
});

test('embed: server allows only loopback framing and still 404s every non-safe path', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'ev-embed-'));
  const { server } = await createServer(path.join(dir, 'missing'));
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const port = server.address().port;
  try {
    const res = await fetch(`http://127.0.0.1:${port}/`);
    assert.equal(res.headers.get('content-security-policy'), 'frame-ancestors http://127.0.0.1:*');
    assert.equal((await fetch(`http://127.0.0.1:${port}/gt_private/x`)).status, 404);
    assert.equal((await fetch(`http://127.0.0.1:${port}/media/A4-1/../gt_private/a`)).status, 404);
  } finally { server.close(); await fs.rm(dir, { recursive: true, force: true }); }
});
