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
import {RECORD_DT, captureStride, hashBinding, validateCase, createInputRecording,
  createPlayback, importActions, replayActions} from './recording.mjs';

import {createScriptOperator, createFixedStepper, SCRIPT_DT} from './script_operator.mjs';
import {HARDSET_ROUTES} from './hardset_routes.mjs';
import {coverageOf, wallsOf} from './coverage.mjs';
import {drawCoverageMap, cameraColors} from './coverage_map.mjs';
import {buildCoverageOverlay} from './coverage_overlay.mjs';
import {backUrl, isBackKey} from './ui_state.mjs';

const RUNS = ['A4-1-v2-4actor', 'B4-1-v2-4actor'];
function runId(value) {
  const id = RUNS.find(id => id === value || id.replace('-v2-4actor', '') === value);
  if (!id) throw new Error('RUN_UNKNOWN');
  return id;
}
export function menuOptions(q) {
  const script = q.has('script') ? HARDSET_ROUTES[q.get('script')] : null;
  if (q.has('script') && !script) throw new Error('SCRIPT_UNKNOWN');
  if (script && q.has('actor') && q.get('actor') !== 'T') throw new Error('SCRIPT_ACTOR_MUST_BE_T');
  const skip = q.has('run') || q.has('actor') || q.has('auto') || !!script;
  const actor_id = q.get('actor') || (skip ? 'T' : null);
  if (actor_id && !VARIANTS.includes(actor_id)) throw new Error('ACTOR_UNKNOWN');
  const run_id = runId(script?.run_id || q.get('run') || (q.get('auto')?.startsWith('B4') ? 'B4-1' : 'A4-1'));
  return {run_id, actor_id, skip, mouse: q.has('auto') || script || q.get('mouse') === 'off' ? 'off' : q.get('mouse') === 'drag' ? 'drag' : 'lock'};
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
  let recordedCase = null;
  if (q.get('auto') === 'recorded') {
    body.innerHTML = '<main style="padding:5vw"><h1>A · 載入重播劇本</h1><input id="case-file" type="file" accept=".json"><p id="case-status" role="status"></p></main>';
    recordedCase = await new Promise(resolve => {
      body.querySelector('#case-file').onchange = async event => {
        try { resolve(validateCase(JSON.parse(await event.target.files[0].text()))); }
        catch (error) { body.querySelector('#case-status').textContent = error.message; }
      };
    });
    Object.assign(P, recordedCase.config, {auto: recordedCase.config.auto || null});
    Object.assign(options, {run_id: recordedCase.run_id, actor_id: recordedCase.actor_id, mouse: 'off'});
    body.replaceChildren();
  }
  P.record = q.get('record') === '1' || !!recordedCase;
  const response = await fetcher('/data/scenario.json');
  if (!response.ok) throw new Error('SCENARIO_LOAD_FAILED');
  const scenario = await response.json(), gate = createSessionGate(scenario, options, fetcher);
  let gltf = null, cleanup = () => {};
  async function begin() {
    const session = await gate.begin();
    cleanup(); body.querySelector('#ab-menu')?.remove();
    return enter(body, P, session, {fetcher, mouse: options.mouse, gltf, recordedCase});
  }
  if (options.skip) return begin();
  body.insertAdjacentHTML('beforeend', `<main id="ab-menu" class="ab-menu">
    <h1>A · 選擇場景與角色</h1><h2>1 · 場景</h2><div id="ab-runs" class="ab-runs"></div>
    <h2>2 · 角色</h2><div id="ab-actors" class="ab-actors"></div>
    <p>WASD 移動 · Shift 跑 · 滑鼠轉視角。開始後只能重新載入來換場景或角色。</p>
    <button id="ab-begin" disabled>開始</button> <span id="ab-status" role="status">載入外觀…</span></main>`);
  const doc = body.ownerDocument, runButtons = [], cards = [];
  let menuReady = false;
  const beginButton = body.querySelector('#ab-begin'), status = body.querySelector('#ab-status');
  function update() {
    const selected = gate.snapshot(), run = scenario.runs.find(r => r.run_id === selected.run_id);
    for (const b of runButtons) { const active = b.dataset.run === selected.run_id; b.setAttribute('aria-pressed', active); }
    for (const card of cards) {
      const id = card.dataset.actor, a = run.actors.find(a => a.actor_id === id);
      card.querySelector('small').textContent = `${(a.waypoints[0].t_us / 1e6).toFixed(1)}–${(a.waypoints.at(-1).t_us / 1e6).toFixed(1)} s`;
      const active = id === selected.actor_id; card.setAttribute('aria-pressed', active);
    }
    beginButton.disabled = !menuReady || !selected.actor_id;
  }
  for (const id of RUNS) {
    const b = doc.createElement('button'); b.dataset.run = id; b.textContent = `${id.replace('-v2-4actor', '')} · ${scenario.runs.find(r => r.run_id === id).duration_us / 1e6} s`;
    b.className = 'ab-run'; b.onclick = () => { gate.chooseRun(id); update(); }; body.querySelector('#ab-runs').append(b); runButtons.push(b);
  }
  try {
    const asset = await fetcher('/data/character.glb'); if (!asset.ok) throw new Error('CHARACTER_LOAD_FAILED');
    const buffer = await asset.arrayBuffer(), colors = variantSwatches(buffer);
    for (const id of VARIANTS) {
      const card = doc.createElement('button'); card.dataset.actor = id; card.className = 'ab-actor'; card.style.setProperty('--actor-swatch', colors[id]);
      card.innerHTML = `<canvas data-preview="${id}" width="160" height="170" hidden></canvas><p><span class="actor-swatch"></span> <b>角色 ${id}</b></p><small></small>`;
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

export const XRAY_NOTICE = '操作者透視視角，鏡頭看不到';
// N6 shares one baked material across floor/walls. Clone only the wall assignment in memory.
// Default (#656): the operator sees opaque walls, exactly like the virtual cameras. X-ray is an explicit operator
// toggle; when on, walls turn 18% opaque and the ceiling hides for that one render only. The coverage overlay
// (camera icons, FOV, blind cells) is shown only inside the operator render. Everything is restored synchronously
// in finally, before any virtual camera capture can run.
export function makeOperatorView(world, {overlay = null, xray = false} = {}) {
  const materials = [...world.wallMats], ceiling = world.scene.getObjectByName('CEILING_STATIC_LIVE');
  world.scene.getObjectByName('WALL_JOINED_SHELL_LIVE')?.traverse(object => {
    if (!object.isMesh) return;
    const cloned = (Array.isArray(object.material) ? object.material : [object.material]).map(material => material.clone());
    object.material = Array.isArray(object.material) ? cloned : cloned[0]; materials.push(...cloned);
  });
  if (overlay) { overlay.visible = false; world.scene.add(overlay); }
  const draw = render => {
    const previous = materials.map(m => ({transparent: m.transparent, opacity: m.opacity, depthWrite: m.depthWrite}));
    const visible = ceiling?.visible;
    try {
      if (overlay) overlay.visible = true;
      if (xray) {
        if (ceiling) ceiling.visible = false;
        for (const m of materials) { m.transparent = true; m.opacity = .18; m.depthWrite = false; }
      }
      render();
    } finally {
      if (overlay) overlay.visible = false;
      if (ceiling) ceiling.visible = visible;
      materials.forEach((m, i) => Object.assign(m, previous[i]));
    }
  };
  draw.setXray = on => { xray = !!on; return xray; };
  Object.defineProperty(draw, 'xray', {get: () => xray});
  return draw;
}

async function runOperator(body, P, session, {fetcher, mouse, gltf, recordedCase}) {
  body.insertAdjacentHTML('beforeend', `<div id="op"><div id="view-wrap"><canvas id="view"></canvas><div id="xray-notice" role="status" hidden>${XRAY_NOTICE}</div></div>
    <div id="hud-tl"><button id="op-back" type="button" title="回到場景選單（Esc）">← 返回</button>
      <div id="hud-card" class="hud-card"><dl id="hud-info"><dt>場景</dt><dd id="hud-run"></dd><dt>角色</dt><dd id="hud-actor"></dd><dt>追蹤鏡頭</dt><dd id="hud-cam">—</dd>
        <dt>模式</dt><dd id="hud-mode"></dd><dt>延遲</dt><dd id="hud-lat">—</dd></dl><p id="hud-status" class="kv"></p></div>
      <details id="hud-tools" class="hud-card" open><summary>工具</summary><div class="tools-body">
        <p>WASD 移動 · Shift 跑 · 點畫面鎖定滑鼠（Esc 釋放，再按 Esc 返回）</p>
        <button id="ab-download">下載 A 紀錄</button><button id="xray-toggle" aria-pressed="false">透視：關</button>
        <p id="crowd-warning" role="status" hidden>人群模擬錯誤（已跳過該步）</p></div></details></div>
    <div id="hud-tr"><button id="map-toggle" type="button" aria-pressed="true" class="hud-card map-toggle">小地圖：開</button>
      <div id="map-wrap"><canvas id="cover-map" width="320" height="320" aria-label="鏡頭位置、可視範圍與盲區小地圖"></canvas></div></div></div>`);
  const stats = body.querySelector('#stats') || body.querySelector('#hud-status');
  body.querySelector('#op-back').onclick = () => { location.assign(backUrl()); };
  addEventListener('keydown', e => { if (isBackKey(e, body.ownerDocument)) location.assign(backUrl()); });
  const mapToggle = body.querySelector('#map-toggle'), mapWrap = body.querySelector('#map-wrap');
  mapToggle.onclick = () => { const on = mapWrap.hidden; mapWrap.hidden = !on; mapToggle.setAttribute('aria-pressed', String(on)); mapToggle.textContent = on ? '小地圖：開' : '小地圖：關'; mapToggle.blur(); };
  body.querySelector('#hud-run').textContent = session.run_id.replace('-v2-4actor', '');
  body.querySelector('#hud-actor').textContent = session.actor_id;
  body.querySelector('#hud-mode').textContent = P.record ? '錄製' : P.script ? `劇本 ${P.script}` : P.auto ? '自動' : '手動';
  if (P.record) body.querySelector('#hud-tools .tools-body').insertAdjacentHTML('beforeend',
    '<button id="record-stop">結束錄製</button> <button id="case-download">下載重播劇本</button><p><label>附加同局 B 紀錄 <input id="case-actions" type="file" accept=".json"></label></p><button id="replay-system-download">下載重播系統紀錄</button>');
  const {scenario, world, cams, n6, config, geometry} = await setupWorld(P, {scenario: true});
  if (gltf) world.characterGltf = gltf;
  const run = scenario.runs.find(r => r.run_id === session.run_id), camIds = P.cams || Object.keys(cams);
  const crowd = createCrowd(run, {actorId: session.actor_id, segments: world.segments, auto: !!P.auto,
    cfg: recordedCase?.config.crowd || {}, strict: false});
  const route = P.script ? HARDSET_ROUTES[P.script] : null;
  if (P.script && (!route || runId(route.run_id) !== session.run_id || P.auto)) throw new Error('SCRIPT_SESSION_MISMATCH');
  const scripted = route ? createScriptOperator(route) : null;
  const stepper = scripted && !P.record ? createFixedStepper(crowd, scripted) : null;
  let snapshot = crowd.snapshot(), viewState = {view_yaw: 0, view_pitch: 0};
  const stride = P.record ? captureStride(P.fps) : null;
  const bindings = P.record ? {scene_sha256: await hashBinding({run, segments: world.segments}),
    cameras_sha256: await hashBinding(Object.fromEntries(Object.entries(cams).map(([id, c]) =>
      [id, {world: c.camera.matrixWorld.toArray(), projection: c.camera.projectionMatrix.toArray()}])))} : null;
  const recording = P.record ? createInputRecording({case_id: recordedCase?.case_id || P.script || 'case-' + Date.now(),
    script_id: recordedCase?.script_id || P.script || null,
    run_id: session.run_id, actor_id: session.actor_id, seed: recordedCase?.seed ?? 0, bindings,
    config: {w:P.w,h:P.h,fps:P.fps,cams:camIds,model:P.model,scene:P.scene,quality:P.quality,
      auto:P.auto,crowd:snapshot.config}}, snapshot) : null;
  const playback = recordedCase ? createPlayback(recordedCase, crowd, bindings) : null;
  const people = new Map();
  for (const actor of run.actors) people.set(actor.actor_id, await makePerson(P.model, world, actor.actor_id === 'C' ? 'blue' : actor.actor_id === 'B' ? 'orange' : 'red', actor.actor_id));
  const view = body.querySelector('#view');
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
  if (scripted) { log.config.script = {case_id: P.script, dt: SCRIPT_DT, steps: route.steps.length}; log.script_events = scripted.events; }
  window.__log = log;
  let caseActions = recordedCase?.actions || [], finished = false, stopped = false, carry = 0;
  const replayLog = {schema_version: 'live-ab.b-log.v1', session_id: session.session_id,
    ticks: [], actions: [], hud_latency: [], displays: [], violations: [], capture_source: 'A_REPLAY_RESPONSE'};
  function download(value, name) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {type: 'application/json'}));
    const link = Object.assign(body.ownerDocument.createElement('a'), {href: url, download: name});
    link.click(); URL.revokeObjectURL(url);
  }
  if (P.record) {
    window.__case = () => recording.export(caseActions);
    window.__replayLog = replayLog;
    body.querySelector('#record-stop').onclick = () => { stopped = true; };
    body.querySelector('#case-download').onclick = () => download(recording.export(caseActions), recording.export().case_id + '.case.json');
    body.querySelector('#replay-system-download').onclick = () => download(replayLog, 'live-ab-b-' + session.session_id + '.json');
    body.querySelector('#case-actions').onchange = async event => {
      try { caseActions = importActions(JSON.parse(await event.target.files[0].text()), log); stats.textContent = '已附加 B 操作'; }
      catch (error) { stats.textContent = error.message; }
    };
  }
  window.__setKeys = k => Object.assign(keys, k);
  // Read-only coordinates preserve the legacy measurement hook; no object/variant/session setter.
  Object.defineProperty(window, '__op', {configurable: false, value: Object.freeze({get P0() { const a = snapshot.actors.find(a => a.is_player); return Object.freeze({x: a.x, y: a.y, heading: a.heading}); }})});
  body.querySelector('#ab-download').onclick = () => {
    const blob = new Blob([JSON.stringify(log, null, 2)], {type: 'application/json'}), url = URL.createObjectURL(blob), link = body.ownerDocument.createElement('a');
    link.href = url; link.download = `live-ab-a-${session.session_id}.json`; link.click(); URL.revokeObjectURL(url);
  };
  const cap = makeCapture(world, cams, P.w, P.h, P.quality), chan = new BroadcastChannel(CHANNEL);
  // #656: wall-clipped coverage of the run's cameras (static geometry + calibration only), on the 3D view and the minimap.
  const coverage = coverageOf(geometry, camIds), colors = cameraColors(camIds), walls = wallsOf(geometry);
  const drawOperator = makeOperatorView(world, {overlay: buildCoverageOverlay(coverage, colors), xray: false}); let last = performance.now();
  const coverMap = body.querySelector('#cover-map'), coverCtx = coverMap.getContext('2d'), xrayNotice = body.querySelector('#xray-notice');
  const xrayButton = body.querySelector('#xray-toggle');
  xrayButton.onclick = () => {
    const on = drawOperator.setXray(!drawOperator.xray);
    xrayButton.textContent = on ? '透視：開' : '透視：關'; xrayButton.setAttribute('aria-pressed', String(on)); xrayNotice.hidden = !on; xrayButton.blur();
  };
  window.__opView = Object.freeze({get xray() { return drawOperator.xray; }, setXray: on => { if (!!on !== drawOperator.xray) xrayButton.onclick(); return drawOperator.xray; },
    coverage: Object.freeze({cameras: coverage.cameras.map(c => ({camera_id: c.camera_id, vertices: c.polygon.length})), blind_cells: coverage.blind.length})});
  const crowdWarning = body.querySelector('#crowd-warning');
  let recordedEvents = 0, capturedEvents = 0;
  function frame(tn) {
    const dt = Math.min(.1, Math.max(0, (tn - last) / 1000)); last = tn;
    let advanced = dt;
    if (P.record) {
      advanced = 0;
      carry = Math.min(.2, carry + dt);
      while (!inflight && !finished && !stopped && carry >= RECORD_DT
          && snapshot.tick < tick * stride && !playback?.done) {
        const player = snapshot.actors.find(a => a.is_player);
        const input = playback ? recordedCase.inputs[recording.length].keys
          : scripted ? scripted.keys({x: player.x, y: player.y}, snapshot.t_sim)
          : {...keys, view_yaw: viewState.view_yaw};
        try { snapshot = playback ? playback.step() : crowd.step(input, RECORD_DT); }
        catch (error) { finished = true; window.__recordingError = error.message; stats.textContent = error.message; break; }
        recording.append(input, snapshot);
        updatePeople(RECORD_DT);
        carry -= RECORD_DT;
        advanced += RECORD_DT;
      }
    } else if (dt > 0) snapshot = stepper ? stepper.advance(dt) : crowd.step({...keys, view_yaw: viewState.view_yaw}, dt);
    if (advanced > 0) {
      for (const event of snapshot.events.slice(recordedEvents)) {
        if (eventTypes.includes(event.type) && event.type !== 'crowd_error') log[event.type].push(event);
      }
      recordedEvents = snapshot.events.length;
      log.crowd_error = snapshot.events.filter(event => event.type === 'crowd_error');
      if (log.crowd_error.length) crowdWarning.hidden = false;
    }
    if (!P.record) updatePeople(dt);
    else if (snapshot.tick === 0) updatePeople(0);
    function updatePeople(stepDt) {
     for (const a of snapshot.actors) {
      const h = people.get(a.actor_id); h.setVisible(a.present);
      if (a.present) { h.setPose(a.x, a.y, a.heading); h.setSpeed(a.speed < .05 ? 0 : a.speed, a.is_player && !P.auto ? a.running : undefined); } h.update(stepDt);
     }
    }
    const p = snapshot.actors.find(a => a.is_player), yaw = viewState.view_yaw * Math.PI / 180, pitch = viewState.view_pitch * Math.PI / 180;
    // Independent orbit follows the player at 4.5 m, eye height 2.1 m; body heading stays movement-derived.
    vcam.position.set(p.x - 4.5 * Math.sin(yaw), 2.1, -p.y + 4.5 * Math.cos(yaw));
    vcam.lookAt(vcam.position.x + Math.sin(yaw) * Math.cos(pitch), vcam.position.y + Math.sin(pitch), vcam.position.z - Math.cos(yaw) * Math.cos(pitch));
    drawOperator(() => renderer.render(world.scene, vcam));
    drawCoverageMap(coverCtx, {geometry, walls, coverage, colors, player: p, w: coverMap.width, h: coverMap.height});
    if (P.record && !inflight && !finished && !stopped && snapshot.tick === tick * stride) void captureTick();
    if (P.record && (stopped || playback?.done) && !inflight) {
      finished = true; window.__recordingDone = true;
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  let tick = 0, inflight = false, schedule = null;
  async function captureTick() {
    if (inflight) { log.dropped++; return; }
    inflight = true;
    try {
      const tCap = now(), snap = snapshot;
      if (recordedCase) replayLog.actions.push(...await replayActions(caseActions, tick, session.session_id, fetcher, now));
      const row = privateTick(snap, tick, tCap, a => groundTruthVisible(cams, world.blockers, world.root, a.x, a.y));
      if (scripted) row.script_step = scripted.step;
      // Start every shoot synchronously in this task, before the next animation frame changes poses.
      const frames = await Promise.all((P.record ? camIds : chooseCaptureIds(camIds, schedule)).map(async id => ({cam: id, jpeg: await cap.shoot(id)})));
      const header = buildInferHeader({tick, tCaptureMs: P.record ? tick * 1000 / P.fps : tCap, frames, availableCameras: camIds});
      const tSend = now(), response = await fetcher('/infer', {method: 'POST', body: packInfer(header, frames.map(f => f.jpeg))});
      if (!response.ok) {
        if (!P.record && response.status === 409) {
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
      const message = buildSystemMessage({tick, tCaptureMs: tCap, frames, result: res});
      chan.postMessage(message);
      if (P.record) replayLog.ticks.push({tick, t_capture: tCap, t_resp: tResp, t_display: null, tracking: message.tracking});
      const newEvents = snap.events.slice(capturedEvents);
      for (const type of eventTypes) {
        row[type] = [...(row[type] || []), ...newEvents.filter(event => event.type === type)];
      }
      row.spawn_adjusted = log.ticks.length ? [] : snap.spawn_adjusted;
      capturedEvents = snap.events.length;
      log.ticks.push({...row, t_infer_capture_ms: header.t_capture_ms, t_send: tSend, t_resp: tResp, t_post: now(), timing: res.timing_ms,
        active: res.tracking?.active_cam, state: res.tracking?.state, schedule: res.schedule});
      body.querySelector('#hud-cam').textContent = res.tracking?.active_cam?.replace('CAM_', '') || '—';
      body.querySelector('#hud-lat').textContent = `${(tResp - tSend).toFixed(0)} ms`;
      log.sent++; stats.textContent = `tick ${tick} · sent ${log.sent} · dropped ${log.dropped} · round-trip ${(tResp - tSend).toFixed(0)} ms`; tick++;
    } catch (error) { if (P.record) { finished = true; window.__recordingError = error.message; } stats.textContent = `擷取失敗：${error.message}`; log.errors ||= []; log.errors.push({tick, error: error.message}); }
    finally { inflight = false; }
  }
  if (!P.record) setInterval(captureTick, 1000 / P.fps);
  window.__ready = true;
}
