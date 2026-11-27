import test from 'node:test';
import assert from 'node:assert/strict';
import { candidateFrame, createBController, createBState, listCandidates, reduceB } from '../src/system.mjs';

const firstSession = '0123456789abcdef';
const secondSession = '0123456789abcde0';
const response = (body, status = 200) => ({ ok: status < 400, json: async () => body });
const state = (session_id, mode = 'IDLE', color = null) => ({ session_id, mode, color, tick: null });
const candidate = (cand_id, tick, x, color = 'red', cam = 'CAM_W1') => ({
  cand_id, tick, cam, color, bbox: [x, 0, x + 8, 40], score: 0.8, est_xy: [x / 10, 1],
});
const frame = (tick, mode, color = 'red', trackingState = mode, at = 1000 + tick) => ({
  tick, t_capture_ms: at, tracking: { state: trackingState, target: { mode, color } },
  frames: [{ cam: 'CAM_W1', jpeg: new ArrayBuffer(0) }],
});
const snapshot = (mode, candidates, color = 'red') => ({ mode, color, candidates, tick: candidates[0]?.tick ?? null });

test('B only lists finite projected same-color candidates, numbered from left to right', () => {
  const good = listCandidates([
    candidate('right', 1, 20), { ...candidate('left', 1, 2), extra: 'private' },
    candidate('wrong-color', 1, 1, 'blue'), { ...candidate('nan', 1, 0), est_xy: [NaN, 0] },
    { ...candidate('bad-box', 1, 0), bbox: [0, Infinity, 2, 3] },
  ], 'red');
  assert.deepEqual(good.map(c => [c.cand_id, c.number]), [['left', 1], ['right', 2]]);
  assert.ok(!('extra' in good[0]));
});

test('B route starts, presents candidates, retains old view during reselect and logs exact source ticks', async () => {
  const calls = [], actions = [];
  const one = candidate('one', 1, 0);
  const many = [candidate('right', 6, 24), candidate('left', 6, 1)];
  let expectation = state(firstSession);
  const controller = createBController({ clock: () => 1000, onAction: action => actions.push(action),
    fetcher: async (path, request) => {
      const body = request.body ? JSON.parse(request.body) : null;
      calls.push([path, body]);
      return response(expectation);
    },
  });
  await controller.sync();
  controller.intent('red', '查找藍衣');
  expectation = { ...snapshot('TRACKING', [one]), parse: { note: 'CHIP_OVERRIDES_SENTENCE', ignored: ['action'] } };
  assert.equal(await controller.act('start'), true);
  assert.equal(controller.state.mode, 'TRACKING');
  assert.match(controller.state.message, /採用所選顏色。已略過查找動作/);
  assert.deepEqual(calls.at(-1), ['/track/start', { session_id: firstSession, color: 'red', sentence: '查找藍衣' }]);
  assert.deepEqual(actions[0], { type: 'start', t_op: 1000, mode: 'TRACKING', color: 'red',
    cand_id: 'one', tick: 1, est_xy: [0, 1] });

  assert.equal(controller.frame(frame(5, 'TRACKING')), true);
  const cached = controller.state.frames;
  expectation = snapshot('NEEDS_PICK', many);
  await controller.act('reselect');
  assert.deepEqual(calls.at(-1)[1], { session_id: firstSession, color: 'red', reselect: true });
  assert.equal(controller.state.reselecting, true);
  assert.equal(controller.state.frames, cached);
  assert.deepEqual(controller.state.candidates.map(c => c.cand_id), ['left', 'right']);

  expectation = { mode: 'TRACKING', color: 'red', picked: many[1] };
  await controller.act('pick', controller.state.candidates[0]);
  assert.equal(controller.state.reselecting, false);
  assert.deepEqual(calls.at(-1), ['/track/pick', { session_id: firstSession, cand_id: 'left' }]);
  assert.equal(actions.at(-1).tick, 6);
  expectation = { mode: 'IDLE' };
  await controller.act('stop');
  assert.equal(controller.state.mode, 'IDLE');
  assert.deepEqual(calls.at(-1), ['/track/stop', { session_id: firstSession }]);
  assert.deepEqual(actions.map(a => a.type), ['start', 'reselect', 'pick', 'stop']);
  assert.ok(!JSON.stringify(actions).includes('查找藍衣'));
});

test('candidate 409 refreshes choices rather than applying old candidate', async () => {
  const old = candidate('old', 2, 11), fresh = candidate('fresh', 9, 30);
  const routes = {
    '/track/state': response(state(firstSession)),
    '/track/start': response(snapshot('NEEDS_PICK', [old])),
    '/track/pick': response({ error: 'CANDIDATE_STALE' }, 409),
    '/track/candidates?color=red': response(snapshot('NEEDS_PICK', [fresh])),
  };
  const controller = createBController({ fetcher: async path => routes[path] });
  await controller.sync();
  controller.intent('red', '');
  await controller.act('start');
  assert.equal(await controller.act('pick', controller.state.candidates[0]), false);
  assert.match(controller.state.message, /候選已更新/);
  assert.deepEqual(controller.state.candidates.map(c => c.cand_id), ['fresh']);
});

test('session rollover forgets intent, frames and an old request that completes afterward', async () => {
  let session = firstSession, release;
  let now = 1000;
  const actions = [];
  const controller = createBController({ clock: () => now, onAction: a => actions.push(a),
    fetcher: async path => path === '/track/state' ? response(state(session))
      : new Promise(resolve => { release = resolve; }),
  });
  await controller.sync();
  controller.intent('red', '追蹤紅衣');
  controller.frame(frame(1, 'IDLE', null, 'IDLE'));
  const old = controller.act('start');
  now = 2000;
  session = secondSession;
  await controller.sync();
  release(response(snapshot('TRACKING', [candidate('old', 1, 0)])));
  assert.equal(await old, false);
  assert.equal(controller.state.session, secondSession);
  assert.equal(controller.state.mode, 'IDLE');
  assert.equal(controller.state.chip, null);
  assert.equal(controller.state.sentence, '');
  assert.deepEqual(controller.state.frames, []);
  assert.deepEqual(controller.state.candidates, []);
  assert.deepEqual(actions, []);
  assert.equal(controller.frame(frame(42, 'TRACKING')), false);
  assert.equal(controller.frame(frame(0, 'IDLE', null, 'IDLE', 2001)), true);
});

test('a session mismatch invalidates old intent and polls the server again', async () => {
  let calls = 0;
  const controller = createBController({ fetcher: async path => {
    if (path === '/track/state') return response(state(++calls === 1 ? firstSession : secondSession));
    return response({ error: 'SESSION_MISMATCH' }, 409);
  } });
  await controller.sync();
  controller.intent(null, '紅衣');
  assert.equal(await controller.act('start'), false);
  assert.equal(controller.state.session, secondSession);
  assert.equal(controller.state.sentence, '');
  assert.equal(controller.state.mode, 'IDLE');
});

test('an old candidate request cannot delay fetching candidates for the new session', async () => {
  let session = firstSession, finishOld, lookups = 0;
  let clock = 1000;
  const controller = createBController({ clock: () => clock, fetcher: async path => {
    if (path === '/track/state') return response(state(session));
    if (path === '/track/start') return response(snapshot('NEEDS_PICK', []));
    if (++lookups === 1) return new Promise(resolve => { finishOld = resolve; });
    return response(snapshot('NEEDS_PICK', [candidate('new', 1, 3)]));
  } });
  await controller.sync();
  controller.intent('red', '');
  await controller.act('start');
  controller.frame(frame(1, 'NEEDS_PICK'));
  assert.equal(lookups, 1);
  session = secondSession;
  clock = 2000;
  await controller.sync();
  controller.intent('red', '');
  await controller.act('start');
  controller.frame(frame(1, 'NEEDS_PICK', 'red', 'NEEDS_PICK', 2001));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(lookups, 2);
  assert.equal(controller.state.candidates[0].cand_id, 'new');
  finishOld(response(snapshot('NEEDS_PICK', [candidate('old', 5, 6)])));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(controller.state.candidates[0].cand_id, 'new');
});

test('cache keeps only the newest five frames and matches a candidate by tick and camera', () => {
  let st = reduceB(createBState(), { type: 'SESSION', data: state(firstSession) });
  for (let tick = 0; tick < 7; tick++) {
    st = reduceB(st, { type: 'FRAME', session: firstSession, msg: frame(tick, 'IDLE'), adoptMode: true });
  }
  assert.deepEqual(st.frames.map(msg => msg.tick), [2, 3, 4, 5, 6]);
  assert.ok(candidateFrame(st.frames, candidate('cached', 2, 0)));
  assert.equal(candidateFrame(st.frames, candidate('evicted', 1, 0)), undefined);
  assert.equal(candidateFrame(st.frames, candidate('other', 2, 0, 'red', 'CAM_W2')), undefined);
});

test('B browser selects via frame, map and list, downloads receipts and clears on reset', {
  skip: process.env.LIVE_AB_BROWSER !== '1', timeout: 60000,
}, async () => {
  const { createServer } = await import('node:http');
  const { readFile, mkdir, writeFile } = await import('node:fs/promises');
  const { resolve } = await import('node:path');
  const { launch } = await import('../measure/lib.mjs');
  const geom = { floors: [{ x_m: [0, 20], y_m: [0, 20] }], clearance_segments: [], cameras: [] };
  let track = state(firstSession), offered = [], selected = null;
  const requests = [];
  const server = createServer(async (req, res) => {
    const send = (data, status = 200) => {
      res.writeHead(status, { 'Content-Type': 'application/json' }).end(JSON.stringify(data));
    };
    if (req.url === '/config') return send({ advisor: 'off' });
    if (req.url === '/data/geometry.json') return send(geom);
    if (req.url === '/track/state') return send(track);
    if (req.url.startsWith('/track/candidates?')) return send(snapshot(track.mode, offered, track.color));
    if (req.method === 'POST' && req.url.startsWith('/track/')) {
      const buffers = [];
      for await (const chunk of req) buffers.push(chunk);
      const body = JSON.parse(Buffer.concat(buffers).toString());
      requests.push({ path: req.url, body });
      if (body.session_id !== track.session_id) return send({ error: 'SESSION_MISMATCH' }, 409);
      if (req.url === '/track/start') {
        track = state(firstSession, body.reselect ? 'NEEDS_PICK' : offered.length ? 'NEEDS_PICK' : 'ACQUIRING',
          body.color ?? 'blue');
        return send({ ...snapshot(track.mode, offered, track.color), parse: { parser: 'RULES', ignored: ['action'] } });
      }
      if (req.url === '/track/pick') {
        selected = offered.find(item => item.cand_id === body.cand_id);
        if (!selected) return send({ error: 'CANDIDATE_STALE' }, 409);
        track = state(firstSession, 'TRACKING', track.color);
        return send({ mode: 'TRACKING', color: track.color, picked: selected });
      }
      if (req.url === '/track/stop') {
        offered = [];
        track = state(firstSession);
        return send({ mode: 'IDLE' });
      }
    }
    if (req.url === '/?role=system') {
      return res.writeHead(200, { 'Content-Type': 'text/html' }).end(await readFile(new URL('../index.html', import.meta.url)));
    }
    const match = req.url.match(/^\/src\/([a-z_-]+\.(?:mjs|css))$/);
    if (match) return res.writeHead(200, { 'Content-Type': match[1].endsWith('.css') ? 'text/css' : 'text/javascript' })
      .end(await readFile(new URL(match[1] === 'tokens.css' ? '../../workbench-v2/tokens.css' : `../src/${match[1]}`, import.meta.url)));
    res.writeHead(404).end();
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await launch();
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const waitText = (selector, text) => page.waitForFunction((selector, text) =>
      document.querySelector(selector).textContent.includes(text), { timeout: 5000 }, selector, text);
    const click = selector => page.click(selector);
    await page.goto(`http://127.0.0.1:${server.address().port}/?role=system`);
    await waitText('#h1v', '尚未開始追蹤');
    assert.equal(await page.$eval('#bs',el=>getComputedStyle(el).display),'grid','shared LIVE styles load in fixture');
    await page.type('#target-sentence', '查找藍衣的人');
    await click('#target-start');
    await waitText('#target-feedback', '畫面中沒有符合的人');
    assert.deepEqual(requests[0].body, { session_id: firstSession, sentence: '查找藍衣的人' });
    offered = [candidate('right', 2, 42, 'blue'), candidate('left', 2, 12, 'blue')];
    track = state(firstSession, 'NEEDS_PICK', 'blue');
    const sendFrame = async (tick, mode, color, active_cam = null) => page.evaluate(async data => {
      const channel = new BroadcastChannel('amidst-live-mode');
      const cv = Object.assign(document.createElement('canvas'), { width: 96, height: 60 });
      const context = cv.getContext('2d'); context.fillStyle = '#183c78'; context.fillRect(0, 0, 96, 60);
      const image = await new Promise(resolve => cv.toBlob(resolve, 'image/jpeg'));
      channel.postMessage({
        type: 'frame-batch', tick: data.tick, t_capture_ms: Date.now() - 5,
        frames: [{ cam: 'CAM_W1', jpeg: await image.arrayBuffer() }], dets: {}, timing_ms: { forward: 4 },
        tracking: { state: data.mode, target: { color: data.color, mode: data.mode }, active_cam: data.active_cam,
          seen_cams: [], est_xy: data.active_cam ? [1.2, 1] : null, lost_ticks: 0, events: [] },
      });
      channel.close();
    }, { tick, mode, color, active_cam });
    await sendFrame(2, 'NEEDS_PICK', 'blue');
    await waitText('#h1v', '（2 位）');
    await waitText('#h1s', '目標：藍衣');
    await page.waitForSelector('[data-candidate-cam="CAM_W1"]', { visible: true });
    const output = process.env.LIVE_AB_B_OUTPUT;
    if (output) {
      await mkdir(output, { recursive: true });
      await page.screenshot({ path: resolve(output, 'b-candidates.png') });
    }
    const box = await (await page.$('[data-candidate-cam="CAM_W1"]')).boundingBox();
    await page.mouse.click(box.x + box.width * 16 / 96, box.y + box.height * 20 / 60);
    await page.waitForFunction(() => __log.actions.some(action => action.cand_id === 'left'));
    assert.equal(selected.cand_id, 'left');

    await sendFrame(3, 'TRACKING', 'blue', 'CAM_W1');
    await waitText('#h1v', '跟蹤中');
    offered = [candidate('map', 3, 20, 'blue', 'CAM_W2')]; // No cached image for this camera.
    await click('#target-reselect');
    await waitText('#target-feedback', '改選目標');
    await waitText('#target-candidates', 'CAM_W2');
    assert.equal(await page.$eval('#candidate-frames', element => element.hidden), true);
    assert.match(await page.$eval('#h1v', element => element.textContent), /跟蹤中/);
    const map = await (await page.$('#map')).boundingBox();
    await page.mouse.click(map.x + (2 + 1) * (288 / 22), map.y + 288 - (1 + 1) * (288 / 22));
    await page.waitForFunction(() => __log.actions.some(action => action.cand_id === 'map'));
    assert.equal(selected.cand_id, 'map');

    offered = [candidate('list', 3, 30, 'blue', 'CAM_W2')];
    await page.waitForFunction(() => !document.querySelector('#target-reselect').disabled);
    await click('#target-reselect');
    await page.waitForSelector('#target-candidates button:not([disabled])', { visible: true });
    await click('#target-candidates button');
    await page.waitForFunction(() => __log.actions.some(action => action.cand_id === 'list'));
    await click('#target-stop');
    await waitText('#h1v', '尚未開始追蹤');
    const report = await page.evaluate(() => window.__log);
    assert.equal(report.schema_version, 'live-ab.b-log.v1');
    assert.deepEqual(report.actions.map(action => action.type), ['start', 'pick', 'reselect', 'pick', 'reselect', 'pick', 'stop']);
    assert.equal(report.violations.length, 0);
    assert.ok(report.ticks.every(tick => tick.t_display >= tick.t_resp && tick.t_resp >= tick.t_capture));
    assert.equal(report.hud_latency.length, report.ticks.length);
    assert.doesNotMatch(JSON.stringify(report), /查找藍衣的人|actor_id|gt_visible|run_id/);
    if (output) {
      const downloads = resolve(output, 'downloads');
      await mkdir(downloads, { recursive: true });
      const cdp = await page.createCDPSession();
      await cdp.send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: downloads });
      await click('#system-download');
      const filename = resolve(downloads, `live-ab-b-${firstSession}.json`);
      let content;
      for (let round = 0; round < 30 && !content; round++) {
        content = await readFile(filename, 'utf8').catch(() => null);
        if (!content) await new Promise(resolve => setTimeout(resolve, 100));
      }
      assert.deepEqual(JSON.parse(content), report);
      await writeFile(resolve(output, 'browser-receipt.json'), JSON.stringify({ requests, errors, report }, null, 2));
    }

    track = state(secondSession);
    await page.waitForFunction(expected => __log.session_id === expected, { timeout: 4000 }, secondSession);
    assert.equal(await page.$eval('#target-sentence', input => input.value), '');
    assert.deepEqual(await page.evaluate(() => __log.actions), []);
    assert.deepEqual(errors, []);
  } finally {
    await browser?.close();
    await new Promise(resolve => server.close(resolve));
  }
});
