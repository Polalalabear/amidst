#!/usr/bin/env node
// 唯讀多鏡頭播放頁的本機 server。用法：
//   node frontend/event-viewer/server.mjs --root <safe 根目錄> [--root-8cam <8 鏡頭 bundle/safe>] [--port 8765]
// 只綁 127.0.0.1，只服務白名單內的靜態檔與 safe PNG。
import http from 'node:http';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { RUNS, FPS } from './runs.mjs';
import { parseMediaPath, loadVerifiedFrame, validateRun, rootKeyOf, CODE_UNAVAILABLE } from './guard.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const STATIC = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/app.mjs', ['app.mjs', 'text/javascript; charset=utf-8']],
  ['/sync.mjs', ['sync.mjs', 'text/javascript; charset=utf-8']],
  ['/style.css', ['style.css', 'text/css; charset=utf-8']],
]);

// roots：舊 run 的 root（字串，向下相容）或 { legacy, eightcam }（各 root 的 run 來源見 runs.mjs 的 source 欄位）。
// 某個 root 未提供或是 symlink 就 fail-closed：只有使用該 root 的 run 回 UNAVAILABLE。
async function resolveRoot(arg) {
  try {
    if (arg && !(await fs.lstat(path.resolve(arg))).isSymbolicLink()) return await fs.realpath(arg);
  } catch { /* null */ }
  return null;
}

export async function createServer(rootsArg) {
  const rootsIn = typeof rootsArg === 'string' || rootsArg == null ? { legacy: rootsArg } : rootsArg;
  const roots = { legacy: await resolveRoot(rootsIn.legacy), eightcam: await resolveRoot(rootsIn.eightcam) };
  const rootOf = (run) => roots[rootKeyOf(run)] ?? null;
  // 啟動時全量驗證一次（每張 PNG 區塊白名單＋CRC，並記 SHA-256），結果快取；送出時再比對。
  const status = new Map();
  for (const run of RUNS) {
    status.set(run.key, rootOf(run) ? await validateRun(rootOf(run), run) : { status: 'UNAVAILABLE', code: CODE_UNAVAILABLE });
  }

  const send = (res, code, type, body) => {
    // 只允許 loopback 頁面以 iframe 內嵌（workbench-v2 事件選單）；不放寬任何路徑或 authority 檢查。
    res.writeHead(code, { 'content-type': type, 'cache-control': 'no-store', 'x-content-type-options': 'nosniff', 'content-security-policy': "frame-ancestors http://127.0.0.1:*" });
    res.end(body);
  };

  const server = http.createServer(async (req, res) => {
    try {
      if (req.method !== 'GET' && req.method !== 'HEAD') return send(res, 405, 'text/plain', 'method not allowed');
      const pathname = (req.url || '').split('?')[0];
      if (STATIC.has(pathname)) {
        const [name, type] = STATIC.get(pathname);
        return send(res, 200, type, await fs.readFile(path.join(HERE, name)));
      }
      if (pathname === '/api/runs') {
        // 只列 runs.mjs 宣告的 run；只回固定欄位與固定錯誤碼，不含任何檔案系統名稱。
        const body = RUNS.map((r) => {
          const s = status.get(r.key);
          return {
            key: r.key, label: r.label, runId: r.runId, frames: r.frames, cameras: r.cameras, fps: FPS, clock: r.clock,
            status: s.status, ...(s.status === 'OK' ? {} : { code: s.code }),
          };
        });
        return send(res, 200, 'application/json; charset=utf-8', JSON.stringify(body));
      }
      const media = parseMediaPath(pathname, RUNS);
      if (!media || status.get(media.run.key).status !== 'OK') return send(res, 404, 'text/plain', 'not found');
      const buf = await loadVerifiedFrame(rootOf(media.run), media.run, status.get(media.run.key).digests, media.camera, media.index);
      if (!buf) return send(res, 404, 'text/plain', 'not found');
      return send(res, 200, 'image/png', buf);
    } catch {
      return send(res, 500, 'text/plain', 'error');
    }
  });
  return { server, status };
}

function parseArgs(argv) {
  const out = { port: 8765, root: null, root8: null };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--root') out.root = argv[++i];
    else if (argv[i] === '--root-8cam') out.root8 = argv[++i];
    else if (argv[i] === '--port') out.port = Number(argv[++i]);
  }
  return out;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const { root, root8, port } = parseArgs(process.argv.slice(2));
  if ((!root && !root8) || !Number.isInteger(port)) {
    console.error('用法：node frontend/event-viewer/server.mjs --root <safe 根目錄> [--root-8cam <8 鏡頭 bundle/safe>] [--port 8765]');
    process.exit(2);
  }
  const t0 = Date.now();
  const { server, status } = await createServer({ legacy: root, eightcam: root8 });
  console.log(`啟動全量驗證 ${((Date.now() - t0) / 1000).toFixed(1)} s`);
  for (const [key, s] of status) console.log(`${key}: ${s.status}${s.code ? `（${s.code}）` : ''}`);
  server.listen(port, '127.0.0.1', () => console.log(`http://127.0.0.1:${port}/`));
}
