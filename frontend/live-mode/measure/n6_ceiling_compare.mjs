// Capture the actual operator canvas and system grid at a fixed A4-1 script time.
// The fixture HTTP server serves unchanged LOCAL N6 assets and returns empty detections.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { launch } from './lib.mjs';

const [output, baselineRef] = process.argv.slice(2);
const assets = process.env.AMIDST_LIVE_ASSETS;
if (!output || !assets) {
  throw new Error('Usage: AMIDST_LIVE_ASSETS=<assets> node measure/n6_ceiling_compare.mjs <out> [baseline-ref]');
}
const frontend = fileURLToPath(new URL('../', import.meta.url));
const repo = path.resolve(frontend, '../..');
const data = new Map([
  ['scene.glb', path.join(assets, 'scene.glb')],
  ['character.glb', path.join(assets, 'character.glb')],
  ['cameras.three.json', path.join(assets, 'cameras.three.json')],
  ['scenario.json', path.join(repo, 'docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json')],
  ['geometry.json', path.join(repo, 'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json')],
]);
const baselineSetup = baselineRef
  ? execFileSync('git', ['show', `${baselineRef}:frontend/live-mode/src/setup.mjs`], {cwd: repo})
  : null;
const sha = buffer => createHash('sha256').update(buffer).digest('hex');
const scenarioSecond = 12;
const query = 'auto=A4&run=A4-1-v2-4actor&model=glb&w=640&h=360&fps=2&q=0.95';
const operatorFile = path.join(frontend, 'src/operator.mjs');
const operatorSource = await readFile(operatorFile, 'utf8');
const clockLine = 'const tSec = (tn - t0) / 1000;';
const deltaLine = 'const dt = Math.min(0.1, (tn - last) / 1000); last = tn;';
assert.ok(operatorSource.includes(clockLine) && operatorSource.includes(deltaLine));
const frozenOperator = operatorSource
  .replace(clockLine, `const tSec = ${scenarioSecond};`)
  .replace(deltaLine, 'const dt = 0; last = tn;');

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost').pathname;
    if (req.method === 'POST' && (url === '/reset' || url === '/infer')) {
      for await (const _ of req) { /* Drain the real capture packet. */ }
      return res.end(url === '/reset' ? '{}' : JSON.stringify({
        tracking: {state: 'SEARCHING', seen_cams: [], lost_ticks: 0, events: []},
        dets: {}, timing_ms: {},
      }));
    }
    if (url === '/config') return res.end(JSON.stringify({n6: true, schedule_mode: 'all'}));
    const file = url === '/' ? path.join(frontend, 'index.html')
      : url.startsWith('/data/') ? data.get(url.slice(6))
      : url === '/src/tokens.css' ? path.join(frontend, '../workbench-v2/tokens.css')
      : url.startsWith('/src/') ? path.join(frontend, url)
      : url.startsWith('/vendor/three/') ? path.join(frontend, 'node_modules/three', url.slice('/vendor/three/'.length))
      : null;
    if (!file || !(await stat(file)).isFile()) {
      res.writeHead(404);
      return res.end();
    }
    const types = {'.mjs': 'text/javascript', '.js': 'text/javascript', '.html': 'text/html',
      '.json': 'application/json', '.glb': 'model/gltf-binary'};
    res.setHeader('Content-Type', types[path.extname(file)]);
    if (baselineSetup && url === '/src/setup.mjs') return res.end(baselineSetup);
    if (url === '/src/operator.mjs') return res.end(frozenOperator);
    createReadStream(file).pipe(res);
  } catch {
    res.writeHead(404);
    res.end();
  }
});

await mkdir(output, {recursive: true});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const inputHashes = Object.fromEntries(await Promise.all([...data].map(async ([name, file]) =>
  [name, sha(await readFile(file))])));
let browser;
try {
  browser = await launch();
  const system = await browser.newPage();
  const operator = await browser.newPage();
  const errors = [];
  for (const page of [system, operator]) {
    page.on('pageerror', error => { errors.push(error.message); console.error(error); });
    page.on('response', response => {
      if (response.status() >= 400 && !response.url().endsWith('/favicon.ico')) {
        console.error(response.status(), new URL(response.url()).pathname);
      }
    });
  }
  await system.bringToFront();
  await system.goto(`${base}/?role=system&view=grid`);
  await system.waitForFunction(() => window.__ready === true, {polling: 100, timeout: 15000});
  await operator.bringToFront();
  await operator.goto(`${base}/?${query}`);
  await operator.waitForFunction(() => window.__ready === true, {polling: 100, timeout: 15000});
  try {
    await system.waitForFunction(() => window.__log?.displays.length >= 1, {polling: 100, timeout: 15000});
  } catch (error) {
    console.error('operator', await operator.evaluate(() => ({sent: __log?.sent, dropped: __log?.dropped})));
    console.error('system', await system.evaluate(() => ({displays: __log?.displays.length, violations: __log?.violations.slice(0, 1)})));
    throw error;
  }
  const pose = await operator.evaluate(() => {
    const {x, y, heading} = window.__op.P0;
    return {x, y, heading};
  });
  assert.deepEqual(errors, []);
  assert.equal(await system.evaluate(() => window.__log.violations.length), 0);
  await operator.bringToFront();
  await operator.locator('#view').wait();
  await (await operator.$('#view')).screenshot({path: path.join(output, 'operator.png')});
  await system.bringToFront();
  await (await system.$('#sys')).screenshot({path: path.join(output, 'system.png')});
  for (const tile of await system.$$('.tile')) {
    const cam = await tile.$eval('span', span => span.textContent);
    assert.match(cam, /^CAM_[A-Z0-9_]+$/);
    const png = await tile.$eval('canvas', canvas => canvas.toDataURL('image/png').split(',')[1]);
    await writeFile(path.join(output, `${cam}.png`), Buffer.from(png, 'base64'));
  }
  const afterHashes = Object.fromEntries(await Promise.all([...data].map(async ([name, file]) =>
    [name, sha(await readFile(file))])));
  assert.deepEqual(afterHashes, inputHashes);
  const receipt = {
    baselineRef: baselineRef ?? null, scenarioSecond, query, pose,
    inputHashes, protocolViolations: 0, pageErrors: errors, detector: 'fixture',
    operatorSha256: sha(operatorSource),
    setupSha256: sha(baselineSetup ?? await readFile(path.join(frontend, 'src/setup.mjs'))),
  };
  await writeFile(path.join(output, 'receipt.json'), JSON.stringify(receipt, null, 2) + '\n');
  console.log(JSON.stringify(receipt));
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}
