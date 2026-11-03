// 路徑白名單與 safe 結構驗證（node）。唯讀；不列出 root 或 run 目錄，
// 只存取預期的 <run>/safe/media/<camera>/<index>.png。
import { promises as fs } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import zlib from 'node:zlib';
import { FPS, FRAME_HEIGHT, FRAME_WIDTH } from './runs.mjs';
import { frameName } from './sync.mjs';

const MEDIA_RE = /^\/media\/([A-Za-z0-9-]+)\/([A-Z0-9_]+)\/(\d{6})\.png$/;
const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
// 白名單與固定結構：只收 CX-7 safe 影格實際使用的 8-bit RGB、非交錯子集（Blender 輸出）。
// 每個區塊的長度與欄位值都依 PNG 規格驗證，數值欄位另設合理上限，因此沒有任何區塊能帶自由文字：
// IHDR 13 bytes 且欄位全數固定；sRGB／gAMA／cHRM／pHYs／oFFs 為固定長度的小數值；
// IDAT 必須能完整解壓成恰好 540×(1+960×3) bytes 的像素資料（無多餘 zlib 資料）；IEND 長度必為 0。
// PLTE／tRNS／sBIT／bKGD（RGB 無 PLTE，其餘為選用輔助）以及 tEXt／iTXt／zTXt／eXIf／iCCP／sPLT／tIME
// 與一切未知或私有區塊都不在表內，出現即拒絕。
const ANCILLARY = new Map([
  ['sRGB', 1], ['gAMA', 4], ['cHRM', 32], ['pHYs', 9], ['oFFs', 9],
]);
const NUM_LIMIT = 10_000_000;
const ROW_BYTES = 1 + FRAME_WIDTH * 3;

function validAncillary(type, d) {
  const u = (i) => d.readUInt32BE(i);
  const s = (i) => d.readInt32BE(i);
  switch (type) {
    case 'sRGB': return d[0] <= 3;
    case 'gAMA': return u(0) >= 1 && u(0) <= NUM_LIMIT;
    case 'cHRM': for (let i = 0; i < 32; i += 4) if (u(i) > NUM_LIMIT) return false; return true;
    case 'pHYs': return u(0) <= NUM_LIMIT && u(4) <= NUM_LIMIT && d[8] <= 1;
    case 'oFFs': return Math.abs(s(0)) <= NUM_LIMIT && Math.abs(s(4)) <= NUM_LIMIT && d[8] <= 1;
    default: return false;
  }
}

function validIdat(parts) {
  const data = Buffer.concat(parts);
  let out;
  try { out = zlib.inflateSync(data, { info: true }); } catch { return false; }
  // bytesWritten＝zlib 實際消耗的輸入；必須等於全部 IDAT，否則 zlib 串流後面夾帶了資料。
  if (out.engine.bytesWritten !== data.length) return false;
  const raw = out.buffer;
  if (raw.length !== FRAME_HEIGHT * ROW_BYTES) return false;
  for (let r = 0; r < FRAME_HEIGHT; r++) if (raw[r * ROW_BYTES] > 4) return false;
  return true;
}

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

// 檢查「實際會送出的 bytes」：簽章；IHDR 在最前、唯一、長度 13 且為 960×540 8-bit RGB 非交錯；
// 其後只有各至多一次、長度與值合規的輔助區塊，然後連續的 IDAT（可解壓為恰好的像素量），
// 最後是長度 0 的 IEND，之後不得有任何 bytes。每個區塊 CRC 必須正確。
// reason 只供內部測試，不外送。
export function inspectPng(buf) {
  if (buf.length < 33 || !buf.subarray(0, 8).equals(PNG_SIGNATURE)) return { ok: false, reason: 'not-png' };
  let off = 8;
  let stage = 'ihdr'; // ihdr → pre（輔助區塊）→ idat → done
  const seen = new Set();
  const idat = [];
  while (off + 12 <= buf.length) {
    const len = buf.readUInt32BE(off);
    const type = buf.toString('latin1', off + 4, off + 8);
    if (len > buf.length || off + 12 + len > buf.length) return { ok: false, reason: 'truncated' };
    if (crc32(buf.subarray(off + 4, off + 8 + len)) !== buf.readUInt32BE(off + 8 + len)) return { ok: false, reason: 'crc' };
    const data = buf.subarray(off + 8, off + 8 + len);
    off += 12 + len;
    if (stage === 'ihdr') {
      if (type !== 'IHDR' || len !== 13) return { ok: false, reason: 'ihdr-first' };
      if (data.readUInt32BE(0) !== FRAME_WIDTH || data.readUInt32BE(4) !== FRAME_HEIGHT) return { ok: false, reason: 'size' };
      // 位元深度 8、色彩型態 2（RGB）、壓縮 0、過濾 0、非交錯
      if (!data.subarray(8, 13).equals(Buffer.from([8, 2, 0, 0, 0]))) return { ok: false, reason: 'ihdr-format' };
      stage = 'pre';
    } else if (type === 'IDAT') {
      if (stage === 'done') return { ok: false, reason: 'idat-after' };
      stage = 'idat';
      idat.push(data);
    } else if (type === 'IEND') {
      if (len !== 0) return { ok: false, reason: 'iend-length' };
      if (!idat.length || !validIdat(idat)) return { ok: false, reason: 'idat' };
      return off === buf.length ? { ok: true } : { ok: false, reason: 'trailing-bytes' };
    } else if (stage === 'pre' && ANCILLARY.has(type)) {
      if (seen.has(type)) return { ok: false, reason: 'duplicate' };
      seen.add(type);
      if (len !== ANCILLARY.get(type) || !validAncillary(type, data)) return { ok: false, reason: 'ancillary-shape' };
    } else {
      return { ok: false, reason: 'chunk-not-allowed' };
    }
    if (stage === 'idat' && type !== 'IDAT') return { ok: false, reason: 'idat-split' };
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
