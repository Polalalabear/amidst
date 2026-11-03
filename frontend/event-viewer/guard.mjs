// 路徑白名單與 safe 結構驗證（node）。唯讀；不列出 root 或 run 目錄，
// 只存取預期的 <run>/safe/media/<camera>/<index>.png。
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { FPS, FRAME_HEIGHT, FRAME_WIDTH } from './runs.mjs';
import { frameName } from './sync.mjs';

const MEDIA_RE = /^\/media\/([A-Za-z0-9-]+)\/([A-Z0-9_]+)\/(\d{6})\.png$/;
const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const FORBIDDEN_CHUNKS = new Set(['tEXt', 'iTXt', 'zTXt', 'eXIf']);

// 回傳 {run, camera, index} 或 null。只接受原始 pathname，不解碼百分號。
export function parseMediaPath(pathname, runs) {
  const m = MEDIA_RE.exec(pathname);
  if (!m) return null;
  const run = runs.find((r) => r.key === m[1]);
  if (!run || !run.cameras.includes(m[2])) return null;
  const index = Number(m[3]);
  if (index >= run.frames) return null;
  return { run, camera: m[2], index };
}

export function relativeMediaPath(run, camera, index) {
  return path.join(run.key, 'safe', 'media', camera, `${frameName(index)}.png`);
}

// 解析成 root 下的真實檔案；任何 symlink／越界／非一般檔一律回 null。
export async function resolveSafeFile(rootReal, run, camera, index) {
  const rel = relativeMediaPath(run, camera, index);
  let cur = rootReal;
  for (const part of rel.split(path.sep)) {
    if (part === '' || part === '.' || part === '..') return null;
    cur = path.join(cur, part);
    let st;
    try { st = await fs.lstat(cur); } catch { return null; }
    if (st.isSymbolicLink()) return null;
  }
  const st = await fs.lstat(cur);
  if (!st.isFile()) return null;
  if (path.relative(rootReal, cur).startsWith('..')) return null;
  return cur;
}

export function inspectPng(buf) {
  if (buf.length < 33 || !buf.subarray(0, 8).equals(PNG_SIGNATURE)) return { ok: false, reason: '不是 PNG' };
  const width = buf.readUInt32BE(16);
  const height = buf.readUInt32BE(20);
  if (width !== FRAME_WIDTH || height !== FRAME_HEIGHT) return { ok: false, reason: `尺寸 ${width}×${height}` };
  let off = 8;
  while (off + 12 <= buf.length) {
    const len = buf.readUInt32BE(off);
    const type = buf.toString('latin1', off + 4, off + 8);
    if (FORBIDDEN_CHUNKS.has(type)) return { ok: false, reason: `含中繼資料區塊 ${type}` };
    if (type === 'IEND') return { ok: true };
    off += 12 + len;
  }
  return { ok: false, reason: '缺少 IEND' };
}

function sampleIndices(total) {
  return [...new Set([0, Math.floor(total / 2), total - 1])];
}

// 回傳 {status:'OK'} 或 {status:'UNAVAILABLE', reason}。
export async function validateRun(rootReal, run) {
  const fail = (reason) => ({ status: 'UNAVAILABLE', reason });
  const mediaDir = path.join(rootReal, run.key, 'safe', 'media');
  let cams;
  try {
    const st = await fs.lstat(mediaDir);
    if (!st.isDirectory() || st.isSymbolicLink()) return fail('media 不是一般目錄');
    cams = await fs.readdir(mediaDir);
  } catch {
    return fail('找不到 safe/media');
  }
  const expectedCams = [...run.cameras].sort();
  if (JSON.stringify([...cams].sort()) !== JSON.stringify(expectedCams)) {
    return fail(`攝影機不符：預期 ${expectedCams.join(',')}，實際 ${[...cams].sort().join(',')}`);
  }
  const expectedFiles = Array.from({ length: run.frames }, (_, i) => `${frameName(i)}.png`);
  for (const cam of run.cameras) {
    const dir = path.join(mediaDir, cam);
    let names;
    try {
      const st = await fs.lstat(dir);
      if (!st.isDirectory() || st.isSymbolicLink()) return fail(`${cam} 不是一般目錄`);
      names = (await fs.readdir(dir)).sort();
    } catch {
      return fail(`${cam} 無法讀取`);
    }
    if (names.length !== expectedFiles.length || names.some((n, i) => n !== expectedFiles[i])) {
      return fail(`${cam} 影格不符：預期 ${run.frames} 張連續編號，實際 ${names.length} 張`);
    }
    for (const i of sampleIndices(run.frames)) {
      const file = await resolveSafeFile(rootReal, run, cam, i);
      if (!file) return fail(`${cam}/${frameName(i)}.png 不是一般檔`);
      const info = inspectPng(await fs.readFile(file));
      if (!info.ok) return fail(`${cam}/${frameName(i)}.png ${info.reason}`);
    }
  }
  return { status: 'OK', fps: FPS };
}
