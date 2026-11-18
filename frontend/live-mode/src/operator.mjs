// A owns the renderer and its private evaluation log. Only camera pixels cross to B/backend.
import * as THREE from 'three';
import {groundTruthVisible} from './world.mjs';
import {setupWorld} from './setup.mjs';
import {createCrowd} from './crowd.mjs';
import {makePerson} from './person.mjs';
import {makeLoader, makeCharacter, VARIANTS} from './n6.mjs';
import {applyMouseDelta, DEFAULT_VIEW_CONFIG} from './view.mjs';
import {makeCapture, packInfer, chooseCaptureIds} from './capture.mjs';
import {buildSystemMessage, buildInferHeader} from './protocol.mjs';
import {CHANNEL, params, now} from './common.mjs';

const RUNS = ['A4-1-v2-4actor', 'B4-1-v2-4actor'];
function runId(value) {
  const id = RUNS.find(id => id === value || id.replace('-v2-4actor', '') === value);
  if (!id) throw new Error('RUN_UNKNOWN');
  return id;
}
export function menuOptions(q) {
  const skip = q.has('run') || q.has('actor') || q.has('auto');
  const actor_id = q.get('actor') || (skip ? 'T' : null);
  if (actor_id && !VARIANTS.includes(actor_id)) throw new Error('ACTOR_UNKNOWN');
  const run_id = runId(q.get('run') || (q.get('auto')?.startsWith('B4') ? 'B4-1' : 'A4-1'));
  return {run_id, actor_id, skip, mouse: q.has('auto') || q.get('mouse') === 'off' ? 'off' : q.get('mouse') === 'drag' ? 'drag' : 'lock'};
}
// Only the menu holds this gate. It is never exposed in window.__op or sent over the channel.
export function createSessionGate(scenario, options, fetcher) {
  let run_id = options.run_id, actor_id = options.actor_id, locked = false;
  const editable = () => { if (locked) throw new Error('SESSION_LOCKED'); };
  return Object.freeze({
    chooseRun(value) { editable(); run_id = runId(value); },
    chooseActor(value) { editable(); if (!VARIANTS.includes(value)) throw new Error('ACTOR_UNKNOWN'); actor_id = value; },
    snapshot: () => ({run_id, actor_id, locked}),
    async begin() {
      editable();
      if (!actor_id) throw new Error('ACTOR_REQUIRED');
      if (!scenario.runs.find(r => r.run_id === run_id)?.actors.find(a => a.actor_id === actor_id)) throw new Error('ACTOR_NOT_IN_RUN');
      locked = true;
      const response = await fetcher('/reset', {method: 'POST'});
      if (!response.ok) throw new Error('RESET_FAILED');
      const result = await response.json();
      if (!/^[a-f0-9]{16}$/.test(result.session_id || '')) throw new Error('RESET_SESSION_ID_MISSING');
      return Object.freeze({run_id, actor_id, session_id: result.session_id});
    },
  });
}

// Read base colors even when WebGL/preview rendering fails. glTF factors are linear RGB.
export function variantSwatches(buffer) {
  const data = new DataView(buffer);
  if (buffer.byteLength < 20 || data.getUint32(0, true) !== 0x46546c67 || data.getUint32(16, true) !== 0x4e4f534a) throw new Error('GLB_METADATA_INVALID');
  const json = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 20, data.getUint32(12, true))));
  const names = json.extensions?.KHR_materials_variants?.variants?.map(v => v.name) || [];
  const primitives = (json.meshes || []).flatMap(m => m.primitives);
  const primitive = primitives.find(p => /SHIRT/i.test(json.materials?.[p.material]?.name || ''));
  if (!primitive) throw new Error('GLB_SHIRT_MATERIAL_MISSING');
  return Object.fromEntries(VARIANTS.map(name => {
    const mapping = primitive.extensions?.KHR_materials_variants?.mappings?.find(m => m.variants.includes(names.indexOf(name)));
    const factor = json.materials?.[mapping?.material ?? primitive.material]?.pbrMetallicRoughness?.baseColorFactor;
    if (!factor) throw new Error(`GLB_VARIANT_COLOR_MISSING:${name}`);
    const color = new THREE.Color().setRGB(...factor.slice(0, 3), THREE.LinearSRGBColorSpace);
    return [name, `#${color.getHexString()}`];
  }));
}

export function bindMouseView(canvas, doc, {mode = 'lock', update}) {
  if (mode === 'off') return () => {};
  const canLock = mode !== 'drag' && typeof canvas.requestPointerLock === 'function';
  // clientX/clientY already use CSS pixels, independent of devicePixelRatio.
  const retryClickTravelCssPx = 3;
  let dragMode = !canLock, dragging = false, previous = null, travel = 0, pending = null;
  const listeners = [];
  const on = (target, type, fn) => { target.addEventListener(type, fn); listeners.push(() => target.removeEventListener(type, fn)); };
  const fallback = ticket => {
    if (ticket !== pending) return;
    pending = null;
    dragMode = true;
  };
  on(canvas, 'click', () => {
    if (!canLock || pending || doc.pointerLockElement === canvas || travel > retryClickTravelCssPx) return;
    const ticket = pending = Symbol();
    try { Promise.resolve(canvas.requestPointerLock()).catch(() => fallback(ticket)); }
    catch { fallback(ticket); }
  });
  on(doc, 'pointerlockerror', () => { if (pending) fallback(pending); });
  on(doc, 'pointerlockchange', () => {
    if (doc.pointerLockElement === canvas && canLock) {
      dragMode = false;
      pending = null;
    }
    dragging = false;
    previous = null;
  });
  on(canvas, 'mousedown', e => {
    travel = 0;
    if (dragMode && e.button === 0) {
      dragging = true;
      previous = [e.clientX, e.clientY];
      e.preventDefault();
    }
  });
  on(doc, 'mouseup', () => { dragging = false; previous = null; });
  on(doc, 'mousemove', e => {
    if (doc.pointerLockElement === canvas) update(e.movementX, e.movementY);
    else if (dragging && previous) {
      const dx = e.clientX - previous[0], dy = e.clientY - previous[1];
      travel += Math.abs(dx) + Math.abs(dy);
      update(dx, dy);
      previous = [e.clientX, e.clientY];
    }
  });
  on(doc.defaultView || doc, 'blur', () => { dragging = false; previous = null; });
  return () => listeners.forEach(remove => remove());
}

export function privateTick(snapshot, tick, t_capture, visible) {
  const scripted = snapshot.actors.filter(actor => !actor.is_player);
  const pauses = key => Object.fromEntries(scripted.map(actor => [actor.actor_id, actor[key]]));
  return {tick, t_capture, t_sim: snapshot.t_sim,
    actors: snapshot.actors.map(a => ({id: a.actor_id, present: a.present, xy: a.present ? [a.x, a.y] : null, gt_visible: a.present ? visible(a) : []})),
    pause_total_i: pauses('pause_total_i'),
    pause_player_i: pauses('pause_player_i'),
    pause_script_i: pauses('pause_script_i'),
    block_wait: snapshot.actors.filter(a => a.block_wait > 0).map(a => ({i: a.actor_id, j: 'player', waited_s: a.block_wait})),
    forced_pairs: snapshot.forced_pairs,
    active_passes: snapshot.active_passes,
  };
}

function previews(body, gltf) {
  const disposers = [];
  for (const id of VARIANTS) {
    let renderer;
    try {
      const canvas = body.querySelector(`[data-preview="${id}"]`);
      renderer = new THREE.WebGLRenderer({canvas, alpha: true, antialias: true});
      renderer.setSize(160, 170, false);
      const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(32, 160 / 170, .1, 20);
      scene.add(new THREE.HemisphereLight(0xffffff, 0x888888, 3));
      const character = makeCharacter(gltf, id); scene.add(character.object); character.update(0);
      camera.position.set(3.4, 1.8, 2.5); camera.lookAt(0, .9, 0);
      renderer.render(scene, camera); canvas.hidden = false;
      disposers.push(() => renderer.dispose());
    } catch { renderer?.dispose(); /* Swatch remains visible; no guessed color. */ }
  }
  return () => disposers.forEach(dispose => dispose());
}

export async function start(body, {fetcher = globalThis.fetch, query = location.search, enter = runOperator, preview = previews} = {}) {
  const q = new URLSearchParams(query), options = menuOptions(q);
  const P = {...params(), model: q.get('model') || 'glb'};
  const response = await fetcher('/data/scenario.json');
  if (!response.ok) throw new Error('SCENARIO_LOAD_FAILED');
  const scenario = await response.json(), gate = createSessionGate(scenario, options, fetcher);
  let gltf = null, cleanup = () => {};
  async function begin() {
    const session = await gate.begin();
    cleanup(); body.querySelector('#ab-menu')?.remove();
    return enter(body, P, session, {fetcher, mouse: options.mouse, gltf});
  }
  if (options.skip) return begin();
  body.insertAdjacentHTML('beforeend', `<main id="ab-menu" style="box-sizing:border-box;min-height:100%;padding:4vh 5vw;max-width:1200px;margin:auto">
    <h1>A · 選擇場景與角色</h1><h2>1 · 場景</h2><div id="ab-runs" style="display:flex;gap:16px"></div>
    <h2>2 · 角色</h2><div id="ab-actors" style="display:flex;gap:16px;flex-wrap:wrap"></div>
    <p>WASD 移動 · Shift 跑 · 滑鼠轉視角。開始後只能重新載入來換場景或角色。</p>
    <button id="ab-begin" disabled style="padding:12px 36px">開始</button> <span id="ab-status" role="status">載入外觀…</span></main>`);
  const doc = body.ownerDocument, runButtons = [], cards = [];
  let menuReady = false;
  const beginButton = body.querySelector('#ab-begin'), status = body.querySelector('#ab-status');
  function update() {
    const selected = gate.snapshot(), run = scenario.runs.find(r => r.run_id === selected.run_id);
    for (const b of runButtons) { const active = b.dataset.run === selected.run_id; b.setAttribute('aria-pressed', active); b.style.outline = active ? '3px solid #f5a623' : ''; }
    for (const card of cards) {
      const id = card.dataset.actor, a = run.actors.find(a => a.actor_id === id);
      card.querySelector('small').textContent = `${(a.waypoints[0].t_us / 1e6).toFixed(1)}–${(a.waypoints.at(-1).t_us / 1e6).toFixed(1)} s`;
      const active = id === selected.actor_id; card.setAttribute('aria-pressed', active); card.style.outline = active ? '3px solid #f5a623' : '';
    }
    beginButton.disabled = !menuReady || !selected.actor_id;
  }
  for (const id of RUNS) {
    const b = doc.createElement('button'); b.dataset.run = id; b.textContent = `${id.replace('-v2-4actor', '')} · ${scenario.runs.find(r => r.run_id === id).duration_us / 1e6} s`;
    b.style.cssText = 'padding:18px 36px'; b.onclick = () => { gate.chooseRun(id); update(); }; body.querySelector('#ab-runs').append(b); runButtons.push(b);
  }
  try {
    const asset = await fetcher('/data/character.glb'); if (!asset.ok) throw new Error('CHARACTER_LOAD_FAILED');
    const buffer = await asset.arrayBuffer(), colors = variantSwatches(buffer);
    for (const id of VARIANTS) {
      const card = doc.createElement('button'); card.dataset.actor = id; card.style.cssText = 'width:180px;padding:10px;background:#242b35;color:inherit;border:1px solid #687380;border-radius:8px';
      card.innerHTML = `<canvas data-preview="${id}" width="160" height="170" hidden></canvas><p><span style="display:inline-block;width:18px;height:18px;background:${colors[id]}"></span> <b>角色 ${id}</b></p><small></small>`;
      card.onclick = () => { gate.chooseActor(id); update(); }; body.querySelector('#ab-actors').append(card); cards.push(card);
    }
    update(); status.textContent = '請選角色';
    // GLB parse/render failure keeps the metadata-derived swatches and usable selection.
    try { gltf = await makeLoader().parseAsync(buffer, '/data/'); cleanup = preview(body, gltf); } catch { status.textContent = '預覽無法顯示；可依色塊選角色'; }
    menuReady = true; update();
    beginButton.onclick = async () => {
      beginButton.disabled = true; runButtons.forEach(b => { b.disabled = true; }); cards.forEach(b => { b.disabled = true; }); status.textContent = '開始…';
      try { await begin(); } catch (error) { status.textContent = `開始失敗：${error.message}。請重新載入。`; }
    };
  } catch (error) { status.textContent = `載入失敗：${error.message}。請重新載入。`; }
}

// N6 shares one baked material across floor/walls. Clone only the wall assignment in memory,
// then restore all view-only properties synchronously before any virtual camera capture.
export function makeOperatorView(world) {
  const materials = [...world.wallMats], ceiling = world.scene.getObjectByName('CEILING_STATIC_LIVE');
  world.scene.getObjectByName('WALL_JOINED_SHELL_LIVE')?.traverse(object => {
    if (!object.isMesh) return;
    const cloned = (Array.isArray(object.material) ? object.material : [object.material]).map(material => material.clone());
    object.material = Array.isArray(object.material) ? cloned : cloned[0]; materials.push(...cloned);
  });
  return render => {
    const previous = materials.map(m => ({transparent: m.transparent, opacity: m.opacity, depthWrite: m.depthWrite}));
    const visible = ceiling?.visible;
    try {
      if (ceiling) ceiling.visible = false;
      for (const m of materials) { m.transparent = true; m.opacity = .18; m.depthWrite = false; }
      render();
    } finally {
      if (ceiling) ceiling.visible = visible;
      materials.forEach((m, i) => Object.assign(m, previous[i]));
    }
  };
}

async function runOperator(body, P, session, {fetcher, mouse, gltf}) {
  body.insertAdjacentHTML('beforeend', `<div id="op"><canvas id="view"></canvas><div id="panel"><h2>A · 操作端</h2>
    <p>WASD 移動 · Shift 跑 · 點畫布鎖定滑鼠（Esc 釋放）；不支援鎖定時按住左鍵拖曳。</p>
    <p>換場景或角色請重新載入。</p><button id="ab-download">下載 A 紀錄</button><p id="stats" class="kv"></p>
    <p id="crowd-warning" role="status" hidden>人群模擬錯誤（已跳過該步）</p></div></div>`);
  const {scenario, world, cams, n6, config} = await setupWorld(P, {scenario: true});
  if (gltf) world.characterGltf = gltf;
  const run = scenario.runs.find(r => r.run_id === session.run_id), camIds = P.cams || Object.keys(cams);
  const crowd = createCrowd(run, {actorId: session.actor_id, segments: world.segments, auto: !!P.auto, strict: false});
  let snapshot = crowd.snapshot(), viewState = {view_yaw: 0, view_pitch: 0};
  const people = new Map();
  for (const actor of run.actors) people.set(actor.actor_id, await makePerson(P.model, world, actor.actor_id === 'C' ? 'blue' : actor.actor_id === 'B' ? 'orange' : 'red', actor.actor_id));
  const view = body.querySelector('#view'), stats = body.querySelector('#stats');
  const renderer = new THREE.WebGLRenderer({canvas: view, antialias: true}), vcam = new THREE.PerspectiveCamera(55, 1, .1, 200);
  function resize() { renderer.setSize(view.clientWidth, view.clientHeight, false); vcam.aspect = view.clientWidth / view.clientHeight; vcam.updateProjectionMatrix(); }
  resize(); addEventListener('resize', resize);
  bindMouseView(view, body.ownerDocument, {mode: mouse, update: (dx, dy) => { viewState = applyMouseDelta(viewState, dx, dy); }});
  const keys = {};
  addEventListener('keydown', e => { keys[e.key.toLowerCase()] = true; });
  addEventListener('keyup', e => { keys[e.key.toLowerCase()] = false; });
  addEventListener('blur', () => { for (const k of Object.keys(keys)) delete keys[k]; });
  const eventTypes = ['forced_overlap', 'block_wait', 'pass_end', 'crowd_error'];
  const log = {schema_version: 'live-ab.a-log.v1', ...session, ticks: [], forced_overlap: [], block_wait: [],
    pass_end: [], crowd_error: [], spawn_adjusted: snapshot.spawn_adjusted,
    config: {...P, run: session.run_id, cams: camIds, n6, crowd: snapshot.config, ...snapshot.config, view: {...DEFAULT_VIEW_CONFIG, mouse}, schedule_mode: config.schedule_mode},
    sent: 0, dropped: 0, fpsStart: now()};
  window.__log = log;
  window.__setKeys = k => Object.assign(keys, k);
  // Read-only coordinates preserve the legacy measurement hook; no object/variant/session setter.
  Object.defineProperty(window, '__op', {configurable: false, value: Object.freeze({get P0() { const a = snapshot.actors.find(a => a.is_player); return Object.freeze({x: a.x, y: a.y, heading: a.heading}); }})});
  body.querySelector('#ab-download').onclick = () => {
    const blob = new Blob([JSON.stringify(log, null, 2)], {type: 'application/json'}), url = URL.createObjectURL(blob), link = body.ownerDocument.createElement('a');
    link.href = url; link.download = `live-ab-a-${session.session_id}.json`; link.click(); URL.revokeObjectURL(url);
  };
  const cap = makeCapture(world, cams, P.w, P.h, P.quality), chan = new BroadcastChannel(CHANNEL);
  const drawOperator = makeOperatorView(world); let last = performance.now();
  const crowdWarning = body.querySelector('#crowd-warning');
  let recordedEvents = 0, capturedEvents = 0;
  function frame(tn) {
    const dt = Math.min(.1, Math.max(0, (tn - last) / 1000)); last = tn;
    if (dt > 0) {
      snapshot = crowd.step({...keys, view_yaw: viewState.view_yaw}, dt);
      for (const event of snapshot.events.slice(recordedEvents)) {
        if (eventTypes.includes(event.type) && event.type !== 'crowd_error') log[event.type].push(event);
      }
      recordedEvents = snapshot.events.length;
      log.crowd_error = snapshot.events.filter(event => event.type === 'crowd_error');
      if (log.crowd_error.length) crowdWarning.hidden = false;
    }
    for (const a of snapshot.actors) {
      const h = people.get(a.actor_id); h.setVisible(a.present);
      if (a.present) { h.setPose(a.x, a.y, a.heading); h.setSpeed(a.speed < .05 ? 0 : a.speed, a.is_player && !P.auto ? a.running : undefined); } h.update(dt);
    }
    const p = snapshot.actors.find(a => a.is_player), yaw = viewState.view_yaw * Math.PI / 180, pitch = viewState.view_pitch * Math.PI / 180;
    // Independent orbit follows the player at 4.5 m, eye height 2.1 m; body heading stays movement-derived.
    vcam.position.set(p.x - 4.5 * Math.sin(yaw), 2.1, -p.y + 4.5 * Math.cos(yaw));
    vcam.lookAt(vcam.position.x + Math.sin(yaw) * Math.cos(pitch), vcam.position.y + Math.sin(pitch), vcam.position.z - Math.cos(yaw) * Math.cos(pitch));
    drawOperator(() => renderer.render(world.scene, vcam));
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  let tick = 0, inflight = false, schedule = null;
  async function captureTick() {
    if (inflight) { log.dropped++; return; }
    inflight = true;
    try {
      const tCap = now(), snap = snapshot;
      const row = privateTick(snap, tick, tCap, a => groundTruthVisible(cams, world.blockers, world.root, a.x, a.y));
      // Start every shoot synchronously in this task, before the next animation frame changes poses.
      const frames = await Promise.all(chooseCaptureIds(camIds, schedule).map(async id => ({cam: id, jpeg: await cap.shoot(id)})));
      const header = buildInferHeader({tick, tCaptureMs: tCap, frames, availableCameras: camIds});
      const tSend = now(), response = await fetcher('/infer', {method: 'POST', body: packInfer(header, frames.map(f => f.jpeg))});
      if (!response.ok) {
        if (response.status === 409) {
          const error = await response.json();
          if (error?.error === 'NON_MONOTONIC_TICK' && Number.isSafeInteger(error.next_tick) && error.next_tick > tick) {
            log.dropped++;
            log.errors ||= [];
            log.errors.push({tick, error: 'NON_MONOTONIC_TICK'});
            tick = error.next_tick;
            return;
          }
        }
        throw new Error(`INFER_HTTP_${response.status}`);
      }
      const res = await response.json(), tResp = now(); schedule = res.schedule || null;
      chan.postMessage(buildSystemMessage({tick, tCaptureMs: tCap, frames, result: res}));
      const newEvents = snap.events.slice(capturedEvents);
      for (const type of eventTypes) {
        row[type] = [...(row[type] || []), ...newEvents.filter(event => event.type === type)];
      }
      row.spawn_adjusted = log.ticks.length ? [] : snap.spawn_adjusted;
      capturedEvents = snap.events.length;
      log.ticks.push({...row, t_send: tSend, t_resp: tResp, t_post: now(), timing: res.timing_ms,
        active: res.tracking?.active_cam, state: res.tracking?.state, schedule: res.schedule});
      log.sent++; stats.textContent = `tick ${tick} · sent ${log.sent} · dropped ${log.dropped} · round-trip ${(tResp - tSend).toFixed(0)} ms`; tick++;
    } catch (error) { stats.textContent = `擷取失敗：${error.message}`; log.errors ||= []; log.errors.push({tick, error: error.message}); }
    finally { inflight = false; }
  }
  setInterval(captureTick, 1000 / P.fps); window.__ready = true;
}
