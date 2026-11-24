// Front-desk floor panel. Only shared system view models enter; no legacy DOM access.
import {buildScene3dModel, estimateUnknownText} from './scene3d-model.mjs';
import {mountScene3dView} from './scene3d-view.mjs';

export function mountUiScene3dPanel({host, scene3dFactory = mountScene3dView} = {}) {
  if (!host) throw new Error('HOST_REQUIRED');
  const doc = host.ownerDocument;
  const el = (tag, text, cls) => { const n = doc.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; };
  const head = el('div', null, 'ui-card-head ui-plan-head'), toggle = el('div', null, 'ui-plan-toggle');
  toggle.setAttribute('role', 'group'); toggle.setAttribute('aria-label', '俯視圖顯示方式');
  head.append(el('span', '樓層俯視圖'), toggle);
  const buttons = new Map();
  for (const [mode, label] of [['2d', '2D 示意'], ['3d', '3D 場景']]) {
    const button = el('button', label, 'ui-btn ui-btn-ghost ui-small'); button.type = 'button'; button.dataset.mode = mode;
    button.addEventListener('click', () => select(mode)); toggle.append(button); buttons.set(mode, button);
  }
  const note = el('p', '', 'ui-note ui-scene3d-note'); note.setAttribute('role', 'status');
  const hud = el('div', null, 'ui-scene3d-hud');
  const summary = el('p', '', 'ui-note ui-estimate-summary');
  const flat = el('div', null, 'ui-plan-flat'), spatial = el('div', null, 'q-scene3d-host ui-scene3d-host');
  const legend = el('ul', null, 'q-scene3d-legend');
  host.append(head, note, hud, summary, flat, spatial, legend);
  let mode = '2d', current = null, runKey, scene = null, ready = false, message = '', epoch = 0, destroyed = false, sceneKey = null;

  function release() {
    epoch++;
    try { scene?.destroy(); } catch { /* Still detach a failed renderer. */ } finally { scene = null; ready = false; sceneKey = null; spatial.replaceChildren(); }
  }
  function missing() { release(); mode = '2d'; message = '3D 資產不存在'; paint(); }
  function paint() {
    if (destroyed || !current) return;
    let model;
    try { model = buildScene3dModel({view: current.view, cameraAsset: ready ? scene.cameraAsset() : null}); }
    catch { missing(); return; }
    host.dataset.mode = mode;
    for (const [key, button] of buttons) button.setAttribute('aria-pressed', String(key === mode));
    note.textContent = message; note.hidden = !message;
    hud.replaceChildren(el('span', `t = ${(model.currentTUs / 1e6).toFixed(1)} s`), el('span', model.stateText),
      el('span', `作用中鏡頭：${model.activeCameraId ?? '—'}`));
    const estimate = model.estimate;
    summary.textContent = estimate.status === 'INFERRED'
      ? `系統估計（推論） · 不確定範圍 ${Number.isFinite(estimate.uncertaintyM) ? `${estimate.uncertaintyM} m` : 'UNKNOWN'} · 身分未確認`
      : estimateUnknownText(estimate.reason);
    flat.hidden = mode !== '2d'; spatial.hidden = mode !== '3d'; legend.hidden = mode !== '3d';
    if (mode === '2d') current.render2d(flat, model);
    if (mode === '3d' && ready) {
      const key = JSON.stringify([model.cameras, model.segmentKind, model.estimate, model.switchMarker]);
      if (key !== sceneKey) {
        try { scene.update(model); sceneKey = key; } catch { missing(); return; }
      }
      legend.replaceChildren(...model.legend.map(text => el('li', text)));
    }
  }
  function select(next) {
    if (destroyed || !current || next === mode) return;
    mode = next; message = '';
    if (mode === '3d' && !scene) {
      const ticket = ++epoch;
      message = '載入 3D 場景…';
      try {
        const instance = scene = scene3dFactory({host: spatial});
        Promise.resolve(instance.ready).then(() => {
          if (destroyed || ticket !== epoch || scene !== instance) return;
          // Never show a different scene's static assets for an unsupported run.
          let ids;
          try { ids = new Set((instance.cameraAsset()?.cameras ?? []).map(c => c.camera_id)); }
          catch { missing(); return; }
          if (!ids.size || (current.cameraIds ?? []).some(id => !ids.has(id))) { missing(); return; }
          ready = true; message = ''; paint();
        }, () => { if (!destroyed && ticket === epoch) missing(); });
      } catch { missing(); return; }
    }
    paint();
  }
  return {
    update(next) {
      if (destroyed) return;
      if (current && next.runKey !== runKey) { release(); mode = '2d'; message = ''; }
      current = next; runKey = next.runKey; paint();
    },
    destroy() { if (destroyed) return; destroyed = true; release(); host.replaceChildren(); },
  };
}
