// 路徑白名單與 safe 結構驗證（node）。唯讀；不列出 root 或 run 目錄，
// 只存取預期的 <run>/safe/media/<camera>/<index>.png。
import { promises as fs } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { FPS, FRAME_HEIGHT, FRAME_WIDTH } from './runs.mjs';
import { frameName } from './sync.mjs';

const MEDIA_RE = /^\/media\/([A-Za-z0-9-]+)\/([A-Z0-9_]+)\/(\d{6})\.png$/;
const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
// 白名單：只放必要區塊與純數值的輔助區塊。tEXt／iTXt／zTXt／eXIf／iCCP／sPLT／tIME
// 與一切未知或私有區塊（可帶文字或自由資料）都不在表內，出現即拒絕。
const ALLOWED_CHUNKS = new Set([
  'IHDR', 'PLTE', 'IDAT', 'IEND',
  'tRNS', 'gAMA', 'cHRM', 'sRGB', 'sBIT', 'bKGD', 'pHYs', 'oFFs',
]);

// 對外只有這兩個固定碼；內部細節與檔案系統名稱一律不外洩。
export const CODE_UNAVAILABLE = 'UNAVAILABLE';
export const CODE_INTEGRITY_FAIL = 'INTEGRITY_FAIL';

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();
function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

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

// 檢查「實際會送出的 bytes」：簽章、IHDR 在最前且 960×540、每個區塊在白名單內且 CRC 正確、
// IEND 為最後且之後無任何多餘 bytes。reason 只供內部測試，不外送。
export function inspectPng(buf) {
  if (buf.length < 33 || !buf.subarray(0, 8).equals(PNG_SIGNATURE)) return { ok: false, reason: 'not-png' };
  let off = 8;
  let first = true;
  while (off + 12 <= buf.length) {
    const len = buf.readUInt32BE(off);
    const type = buf.toString('latin1', off + 4, off + 8);
    if (off + 12 + len > buf.length) return { ok: false, reason: 'truncated' };
    if (!ALLOWED_CHUNKS.has(type)) return { ok: false, reason: 'chunk-not-allowed' };
    if (first && (type !== 'IHDR' || len !== 13)) return { ok: false, reason: 'ihdr-first' };
    if (crc32(buf.subarray(off + 4, off + 8 + len)) !== buf.readUInt32BE(off + 8 + len)) return { ok: false, reason: 'crc' };
    if (first) {
      first = false;
      if (buf.readUInt32BE(off + 8) !== FRAME_WIDTH || buf.readUInt32BE(off + 12) !== FRAME_HEIGHT) return { ok: false, reason: 'size' };
    }
    off += 12 + len;
    if (type === 'IEND') return off === buf.length ? { ok: true } : { ok: false, reason: 'trailing-bytes' };
  }
  return { ok: false, reason: 'no-iend' };
}

const sha256 = (buf) => createHash('sha256').update(buf).digest('hex');

// 逐段 lstat：每一段都必須是真實目錄（或最後一段為一般檔），不可為 symlink；
// 之後 realpath 必須恰等於以 rootReal 串出的路徑，才算留在 root 內。
async function walkReal(rootReal, parts, wantFile) {
  let cur = rootReal;
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    if (part === '' || part === '.' || part === '..' || part.includes(path.sep)) return null;
    cur = path.join(cur, part);
    let st;
    try { st = await fs.lstat(cur); } catch { return null; }
    if (st.isSymbolicLink()) return null;
    const last = i === parts.length - 1;
    if (!(last && wantFile ? st.isFile() : st.isDirectory())) return null;
  }
  try { if ((await fs.realpath(cur)) !== cur) return null; } catch { return null; }
  return cur;
}

// 解析成 root 下的真實檔案；任何 symlink／越界／非一般檔一律回 null。
export async function resolveSafeFile(rootReal, run, camera, index) {
  return walkReal(rootReal, relativeMediaPath(run, camera, index).split(path.sep), true);
}

// 回傳 {status:'OK', fps, digests} 或 {status:'UNAVAILABLE', code}。
// 在任何 readdir／readFile 之前先逐段確認 run／safe／media／camera 都不是 symlink；
// 之後對「每一張」影格檢查 PNG 並記錄 SHA-256，供送出時比對。
export async function validateRun(rootReal, run) {
  const fail = (code) => ({ status: 'UNAVAILABLE', code });
  const mediaDirParts = [run.key, 'safe', 'media'];
  const mediaDir = await walkReal(rootReal, mediaDirParts, false);
  if (!mediaDir) return fail(CODE_UNAVAILABLE);
  for (const cam of run.cameras) {
    if (!(await walkReal(rootReal, [...mediaDirParts, cam], false))) return fail(CODE_UNAVAILABLE);
  }
  let cams;
  try { cams = (await fs.readdir(mediaDir)).sort(); } catch { return fail(CODE_UNAVAILABLE); }
  if (JSON.stringify(cams) !== JSON.stringify([...run.cameras].sort())) return fail(CODE_INTEGRITY_FAIL);
  const expectedFiles = Array.from({ length: run.frames }, (_, i) => `${frameName(i)}.png`);
  const digests = new Map();
  for (const cam of run.cameras) {
    let names;
    try { names = (await fs.readdir(path.join(mediaDir, cam))).sort(); } catch { return fail(CODE_UNAVAILABLE); }
    if (names.length !== expectedFiles.length || names.some((n, i) => n !== expectedFiles[i])) return fail(CODE_INTEGRITY_FAIL);
    const queue = Array.from({ length: run.frames }, (_, i) => i);
    let bad = null;
    const worker = async () => {
      for (let i = queue.shift(); i !== undefined && !bad; i = queue.shift()) {
        const file = await resolveSafeFile(rootReal, run, cam, i);
        if (!file) { bad = CODE_UNAVAILABLE; return; }
        let buf;
        try { buf = await fs.readFile(file); } catch { bad = CODE_UNAVAILABLE; return; }
        if (!inspectPng(buf).ok) { bad = CODE_INTEGRITY_FAIL; return; }
        digests.set(`${cam}/${i}`, sha256(buf));
      }
    };
    await Promise.all(Array.from({ length: 8 }, worker));
    if (bad) return fail(bad);
  }
  return { status: 'OK', fps: FPS, digests };
}

// 送出前的最後一關：重新讀檔，bytes 的 SHA-256 必須等於啟動驗證時記下的值，且仍通過 PNG 檢查。
// 回傳要送出的同一份 Buffer，或 null（呼叫端只回固定的 404）。
export async function loadVerifiedFrame(rootReal, run, digests, camera, index) {
  const expected = digests.get(`${camera}/${index}`);
  if (!expected) return null;
  const file = await resolveSafeFile(rootReal, run, camera, index);
  if (!file) return null;
  let buf;
  try { buf = await fs.readFile(file); } catch { return null; }
  if (sha256(buf) !== expected || !inspectPng(buf).ok) return null;
  return buf;
}
