// Screen 1 (operator): sentence + person, WASD third-person control, distractors on the v2.3 routes,
// 8 virtual cameras captured offscreen, frames sent to the backend, results relayed to the system window.
import * as THREE from 'three';
import { buildWorld, buildCameras, groundTruthVisible } from './world.mjs';
import { stepPlayer, scriptedPose } from './sim.mjs';
import { makePerson, projectBox } from './person.mjs';
import { makeCapture, packInfer } from './capture.mjs';
import { buildSystemMessage, buildInferHeader } from './protocol.mjs';
import { CHANNEL, params, now } from './common.mjs';

export async function start(body) {
  const P = params();
  body.insertAdjacentHTML('beforeend', `<div id="op"><canvas id="view"></canvas><div id="panel">
    <b>Operator</b> <span class="kv">(live mode spike)</span><br><br>
    <label>Sentence<br><input id="sentence" value="${P.sentence}"></label>
    <label>Person <select id="who"><option>red top</option><option>blue top</option></select></label>
    <p class="kv">WASD move · Shift run · The system window (<code>?role=system</code>) sees only camera pixels.</p>
    <div id="stats" class="kv"></div></div></div>`);
  const [geometry, scenario] = await Promise.all([
    fetch('/data/geometry.json').then((r) => r.json()), fetch('/data/scenario.json').then((r) => r.json())]);
  const world = buildWorld(geometry);
  const cams = buildCameras(geometry, world.root, P.w, P.h);
  const camIds = P.cams || Object.keys(cams);
  const run = scenario.runs.find((r) => r.run_id === P.run);
  const durSec = run.duration_us / 1e6;
  const player = await makePerson(P.model, world, 'red');
  const distract = [];
  for (const a of run.actors.filter((x) => x.actor_id !== 'T')) {
    const col = a.actor_id === 'A' ? 'red' : a.actor_id === 'B' ? 'orange' : 'blue';
    distract.push({ a, h: await makePerson('capsule', world, col) });
  }
  const T = run.actors.find((a) => a.actor_id === 'T');
  const P0 = { x: T.waypoints[0].xy[0], y: T.waypoints[0].xy[1], heading: 0, moving: false, running: false };

  // main view
  const view = document.getElementById('view');
  const renderer = new THREE.WebGLRenderer({ canvas: view, antialias: true });
  const vcam = new THREE.PerspectiveCamera(55, 1, 0.1, 200);
  scene_resize();
  addEventListener('resize', scene_resize);
  function scene_resize() { renderer.setSize(view.clientWidth, view.clientHeight, false); vcam.aspect = view.clientWidth / view.clientHeight; vcam.updateProjectionMatrix(); }

  const keys = {};
  addEventListener('keydown', (e) => { const k = e.key.toLowerCase(); if (k === 'shift') keys.shift = true; else keys[k] = true; });
  addEventListener('keyup', (e) => { const k = e.key.toLowerCase(); if (k === 'shift') keys.shift = false; else keys[k] = false; });

  const log = { ticks: [], dropped: 0, sent: 0, fpsStart: now(), config: { ...P, cams: camIds, tris: player.tris } };
  window.__log = log;
  window.__setKeys = (k) => Object.assign(keys, k);
  const cap = makeCapture(world, cams, P.w, P.h, P.quality);
  const chan = new BroadcastChannel(CHANNEL);
  await fetch('/reset', { method: 'POST' });

  const t0 = performance.now();
  let last = t0;
  function frame(tn) {
    const dt = Math.min(0.1, (tn - last) / 1000); last = tn;
    const tSec = (tn - t0) / 1000;
    if (P.auto) {
      const pose = scriptedPose(T, tSec, durSec);
      if (pose) { P0.x = pose.x; P0.y = pose.y; P0.heading = pose.heading; }
      player.setVisible(!!pose);
      log.autoPresent = !!pose;
    } else stepPlayer(P0, keys, dt, world.segments);
    player.setPose(P0.x, P0.y, P0.heading);
    for (const d of distract) {
      const pose = scriptedPose(d.a, tSec, durSec);
      d.h.setVisible(!!pose);
      if (pose) d.h.setPose(pose.x, pose.y, pose.heading);
    }
    vcam.position.set(P0.x, 3.5, -(P0.y - 4.5)); vcam.lookAt(P0.x, 1, -P0.y);
    // walls are see-through only in the operator's own view; the virtual cameras render them opaque
    for (const m of world.wallMats) { m.transparent = true; m.opacity = 0.18; m.depthWrite = false; }
    renderer.render(world.scene, vcam);
    for (const m of world.wallMats) { m.transparent = false; m.opacity = 1; m.depthWrite = true; }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  let tick = 0, inflight = false;
  async function captureTick() {
    if (inflight) { log.dropped++; return; }
    inflight = true;
    try {
      const tCap = now();
      const present = player.object.visible !== false;
      const gt = present ? groundTruthVisible(cams, world.blockers, world.root, P0.x, P0.y) : [];
      const frames = [];
      for (const id of camIds) frames.push({ cam: id, jpeg: await cap.shoot(id) });
      const header = buildInferHeader({ tick, tCaptureMs: tCap, frames });
      const tSend = now();
      const res = await fetch('/infer', { method: 'POST', body: packInfer(header, frames.map((f) => f.jpeg)) }).then((r) => r.json());
      const tResp = now();
      const msg = buildSystemMessage({ tick, tCaptureMs: tCap, frames, result: res });
      chan.postMessage(msg);
      log.sent++;
      // evaluation-only log (stays in this window; never part of the channel message)
      log.ticks.push({ tick, t_capture: tCap, t_send: tSend, t_resp: tResp, t_post: now(), gt_visible: gt, timing: res.timing_ms,
        active: res.tracking && res.tracking.active_cam, state: res.tracking && res.tracking.state });
      document.getElementById('stats').textContent = `tick ${tick} · sent ${log.sent} · dropped ${log.dropped} · round-trip ${(tResp - tSend).toFixed(0)} ms`;
      tick++;
    } finally { inflight = false; }
  }
  setInterval(captureTick, 1000 / P.fps);
  window.__ready = true;
}
