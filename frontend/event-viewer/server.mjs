#!/usr/bin/env node
// 唯讀多鏡頭播放頁的本機 server。用法：
//   node frontend/event-viewer/server.mjs --root <safe 根目錄> [--port 8765]
// 只綁 127.0.0.1，只服務白名單內的靜態檔與 safe PNG。
import http from 'node:http';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { RUNS, FPS } from './runs.mjs';
import { parseMediaPath, resolveSafeFile, validateRun } from './guard.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const STATIC = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/app.mjs', ['app.mjs', 'text/javascript; charset=utf-8']],
  ['/sync.mjs', ['sync.mjs', 'text/javascript; charset=utf-8']],
  ['/style.css', ['style.css', 'text/css; charset=utf-8']],
]);

export async function createServer(rootArg) {
  const rootReal = await fs.realpath(rootArg);
  const status = new Map();
  for (const run of RUNS) status.set(run.key, await validateRun(rootReal, run));

  const send = (res, code, type, body) => {
    res.writeHead(code, { 'content-type': type, 'cache-control': 'no-store', 'x-content-type-options': 'nosniff' });
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
        const body = RUNS.map((r) => ({
          key: r.key, label: r.label, runId: r.runId, frames: r.frames, cameras: r.cameras, fps: FPS,
          ...status.get(r.key),
        }));
        return send(res, 200, 'application/json; charset=utf-8', JSON.stringify(body));
      }
      const media = parseMediaPath(pathname, RUNS);
      if (!media || status.get(media.run.key).status !== 'OK') return send(res, 404, 'text/plain', 'not found');
      const file = await resolveSafeFile(rootReal, media.run, media.camera, media.index);
      if (!file) return send(res, 404, 'text/plain', 'not found');
      return send(res, 200, 'image/png', await fs.readFile(file));
    } catch {
      return send(res, 500, 'text/plain', 'error');
    }
  });
  return { server, status };
}

function parseArgs(argv) {
  const out = { port: 8765, root: null };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--root') out.root = argv[++i];
    else if (argv[i] === '--port') out.port = Number(argv[++i]);
  }
  return out;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const { root, port } = parseArgs(process.argv.slice(2));
  if (!root || !Number.isInteger(port)) {
    console.error('用法：node frontend/event-viewer/server.mjs --root <safe 根目錄> [--port 8765]');
    process.exit(2);
  }
  const { server, status } = await createServer(root);
  for (const [key, s] of status) console.log(`${key}: ${s.status}${s.reason ? `（${s.reason}）` : ''}`);
  server.listen(port, '127.0.0.1', () => console.log(`http://127.0.0.1:${port}/`));
}
