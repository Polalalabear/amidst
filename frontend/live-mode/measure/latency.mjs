// End-to-end latency run. node measure/latency.mjs <label> "<operator query>" [seconds]
// Two windows (operator + system) in one browser; the operator auto-walks the scenario v2.3 target route.
// Joins operator ground-truth logs (evaluation only) with the system window's display log.
import fs from 'node:fs';
import { execSync } from 'node:child_process';
import { launch, BASE, sleep, pct } from './lib.mjs';
const [label, query = 'auto=B4&duration=42', secs = '50'] = process.argv.slice(2);
const out = process.env.OUT || 'out'; fs.mkdirSync(out, { recursive: true });

const sh = (c) => { try { return execSync(c, { encoding: 'utf8' }); } catch { return ''; } };
function usage() {
  const pids = sh("pgrep -f amidst.live_mode.server").trim().split('\n').filter(Boolean);
  const server = pids.length ? Number(sh(`ps -o pcpu= -p ${pids.join(',')}`).trim().split('\n')[0]) : null;
  const chrome = sh("ps -Ao pcpu,command | grep 'Google Chrome' | grep -v grep | awk '{s+=$1} END {print s}'");
  const gpu = sh("ioreg -r -d 1 -w0 -c IOAccelerator | grep -o '\"Device Utilization %\"=[0-9]*' | head -1").match(/=(\d+)/);
  const blender = sh("ps -Ao pcpu,command | grep Blender | grep -v grep | awk '{s+=$1} END {print s}'");
  return { server_cpu: server, chrome_cpu: Number(chrome) || 0, gpu_util: gpu ? Number(gpu[1]) : null, blender_cpu: Number(blender) || 0,
    load1: Number(sh('sysctl -n vm.loadavg').trim().split(' ')[1]) };
}

const b = await launch();
const sys = await b.newPage(); sys.on('pageerror', (e) => console.log('[sys err]', e.message));
await sys.goto(`${BASE}/?role=system`);
await sys.waitForFunction('window.__ready === true');
const op = await b.newPage(); op.on('pageerror', (e) => console.log('[op err]', e.message));
await op.goto(`${BASE}/?${query}`);
await op.waitForFunction('window.__ready === true', { timeout: 60000 });
const samples = [];
const tStart = Date.now();
while (Date.now() - tStart < Number(secs) * 1000) { await sleep(1000); samples.push(usage()); }
const o = await op.evaluate(() => {
  const {config: cfg, sent, dropped, fpsStart: t0, actor_id, ticks} = __log;
  // The latency measurement scores the scripted actor. The A download itself stores one
  // visibility list per actor. Older operators supplied a flat list to this tool.
  return {cfg, sent, dropped, t0, ticks: ticks.map(tick => ({
    ...tick, gt_visible: tick.actors?.find(actor => actor.id === actor_id)?.gt_visible ?? tick.gt_visible ?? [],
  }))};
});
const s = await sys.evaluate(() => ({ displays: __log.displays, viol: __log.violations }));
if (process.env.SHOT) {
  await sys.screenshot({ path: `${process.env.SHOT}_system.png` });
  await op.screenshot({ path: `${process.env.SHOT}_operator.png` });
}
await b.close();

const WARM = 4; // drop first ticks (MPS/JIT warm-up)
const disp = new Map(s.displays.map((d) => [d.tick, d]));
const rows = o.ticks.filter((t) => disp.has(t.tick)).map((t) => ({ ...t, ...disp.get(t.tick), t_capture: t.t_capture }));
const steady = rows.slice(WARM);
const lat = steady.map((r) => r.t_display - r.t_capture);
const period = 1000 / o.cfg.fps;

// first lock: first tick where the target is ground-truth visible -> first system display TRACKING
const firstVis = rows.find((r) => r.gt_visible.length);
const firstLock = rows.find((r) => r.state === 'TRACKING');
const first_lock_ms = firstVis && firstLock ? firstLock.t_display - firstVis.t_capture : null;

// switch latency: active camera loses ground-truth visibility while another camera has it; time until
// the system's active camera is one that really sees the target.
const switches = [];
for (let i = WARM + 1; i < rows.length; i++) {
  const prev = rows[i - 1], cur = rows[i];
  const prevActive = prev.active;
  if (prevActive && prev.gt_visible.includes(prevActive) && !cur.gt_visible.includes(prevActive) && cur.gt_visible.length) {
    let j = i;
    while (j < rows.length && !(rows[j].active && rows[j].gt_visible.includes(rows[j].active))) j++;
    if (j < rows.length) switches.push({ leave_tick: cur.tick, from: prevActive, to: rows[j].active, ms: rows[j].t_display - cur.t_capture,
      ticks: rows[j].tick - cur.tick });
  }
}
const correct = steady.filter((r) => r.gt_visible.length);
const correctRate = correct.length ? correct.filter((r) => r.active && r.gt_visible.includes(r.active)).length / correct.length : null;
const wall = (rows.at(-1).t_capture - rows[0].t_capture) / 1000;
const med = (k) => pct(steady.map((r) => r.timing[k]).filter((v) => v != null), 0.5);
const res = {
  label, query, secs: Number(secs), config: o.cfg, tick_period_ms: period,
  ticks_displayed: rows.length, sent: o.sent, dropped: o.dropped,
  achieved_fps: (rows.length - 1) / wall, drop_ratio: o.dropped / (o.dropped + o.sent),
  frame_latency_ms: { p50: pct(lat, 0.5), p95: pct(lat, 0.95), max: Math.max(...lat), n: lat.length },
  stage_ms_p50: { render_capture: pct(steady.map((r) => r.t_send - r.t_capture), 0.5), http_roundtrip: pct(steady.map((r) => r.t_resp - r.t_send), 0.5),
    server_total: med('server_total'), forward: med('forward'), color: med('color'), channel_to_display: pct(steady.map((r) => r.t_display - r.t_post), 0.5) },
  first_lock_ms, switch_events: switches, switch_ms: { p50: pct(switches.map((x) => x.ms), 0.5), p95: pct(switches.map((x) => x.ms), 0.95), n: switches.length },
  correct_active_rate: correctRate, protocol_violations: s.viol.length,
  schedule: {
    inferred_camera_count: { p50: pct(steady.map((r) => r.schedule?.camera_ids.length).filter(Number.isFinite), 0.5),
      mean: steady.reduce((a, r) => a + (r.schedule?.camera_ids.length || 0), 0) / steady.length },
    reasons: Object.fromEntries([...new Set(steady.map((r) => r.schedule?.reason).filter(Boolean))]
      .map((reason) => [reason, steady.filter((r) => r.schedule?.reason === reason).length])),
  },
  usage_mean: Object.fromEntries(['server_cpu', 'chrome_cpu', 'gpu_util', 'blender_cpu', 'load1'].map((k) => [k, samples.reduce((a, x) => a + (x[k] || 0), 0) / samples.length])),
};
fs.writeFileSync(`${out}/${label}.latency.json`, JSON.stringify({ ...res, rows: rows.map((r) => ({ tick: r.tick, lat: r.t_display - r.t_capture, active: r.active, gt: r.gt_visible, state: r.state, schedule: r.schedule })) }));
console.log(JSON.stringify(res));
