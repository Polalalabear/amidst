// DOM View for Core Tracking Screen: Single-view auto-switching, Multi-view candidates, and Topdown integration.
// Connects to buildCoreTrackingViewModel output. Pure DOM view; no inference inputs.

import {
  AUTO_SEED_LABEL,
  reasonChips,
  buildCoreTrackingViewModel,
  SUPPORTED_SPEEDS,
  CORE_NAVIGATION_BADGE,
} from './core-search-track-model.mjs';
import { resolveFrameImageSrc } from './core-media.mjs';
import { buildScene3dModel } from './scene3d-model.mjs';
import { mountScene3dView } from './scene3d-view.mjs';

const el = (tag, text, cls) => {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (cls) node.className = cls;
  return node;
};

const SVG_NS = 'http://www.w3.org/2000/svg';

export function mountCoreTrackingView({
  container,
  store = null,
  onModeChange = null,
  onSpeedChange = null,
  onSeek = null,
  api = null,
  mediaResolver = null,
  synthetic = false,
  onFrameReady = () => {},
  scene3dFactory = mountScene3dView,
} = {}) {
  if (!container) throw new Error('CONTAINER_REQUIRED');

  let currentModel = null;
  let destroyed = false;
  let generation = 0;

  let lastRenderKey=null;
  // Topdown 2D/3D toggle (#605). 2D is the default; the 3D view is created on demand and kept across re-renders
  // (the 34 MB scene loads once). Missing assets -> note + back to 2D, the page never breaks.
  let topdownMode = '2d', scene3d = null, scene3dHost = null, scene3dReady = false, scene3dNote = '';
  function setTopdownMode(mode) {
    if (destroyed || mode === topdownMode) return;
    if (mode === '2d') { topdownMode = '2d'; scene3dNote = ''; lastRenderKey = null; render(currentModel); return; }
    topdownMode = '3d'; scene3dNote = scene3dReady ? '' : '載入 3D 場景…';
    if (!scene3d) {
      scene3dHost = el('div', undefined, 'q-scene3d-host');
      try { scene3d = scene3dFactory({ host: scene3dHost }); } catch { scene3d = null; }
      if (!scene3d) { failScene3d(); return; }
      scene3d.ready.then(() => { if (destroyed) return; scene3dReady = true; scene3dNote = ''; lastRenderKey = null; render(currentModel); }, failScene3d);
    }
    lastRenderKey = null; render(currentModel);
  }
  function failScene3d() {
    if (destroyed) return;
    try { scene3d?.destroy(); } catch { /* ignore */ }
    scene3d = null; scene3dHost = null; scene3dReady = false; topdownMode = '2d'; scene3dNote = '3D 資產不存在';
    lastRenderKey = null; render(currentModel);
  }
  function syncScene3d(model) {
    if (topdownMode !== '3d' || !scene3dReady || !scene3d) return;
    scene3d.update(buildScene3dModel({ view: model, cameraAsset: scene3d.cameraAsset() }));
  }
  function render(model) {
    if(store&&model){
      const state=store.getState(),intervals=state.activeRun?.sampling?.per_camera?.map(c=>c.source_frame_interval_us).filter(x=>Number.isSafeInteger(x)&&x>0)??[];
      const interval=intervals.length?Math.min(...intervals):1;
      const key=JSON.stringify([state.coreTrackResponse?.output_sha256,model.playbackMode,model.speed,model.status,
        model.singleView?.segmentKind,model.singleView?.activeCameraId,Math.floor(model.currentTUs/interval),model.asOfUs]);
      if(key===lastRenderKey)return;lastRenderKey=key;
    }else lastRenderKey=null;
    if (destroyed) return;
    currentModel = model;
    const renderGeneration=++generation;
    container.replaceChildren();

    const root = el('div', undefined, 'q-core-tracking');
    root.setAttribute('role', 'region');
    root.setAttribute('aria-label', '事件追蹤畫面');

    // Header
    const head = el('div', undefined, 'q-core-tracking-head');
    const titleGroup = el('div', undefined, 'q-core-title-group');
    const title = el('h2', '事件追蹤', 'q-core-title');
    const navBadge = el('span', model?.identityBadge ?? CORE_NAVIGATION_BADGE, 'q-core-identity-badge');
    titleGroup.append(title, navBadge);
    head.append(titleGroup);

    const statusBadge = el('span', model?.statusText ?? '尚未載入追蹤結果。', 'q-core-track-status');
    head.append(statusBadge);
    root.append(head);
    if (model && model.status !== 'UNLOADED') {
      const tags = el('div', undefined, 'q-core-tags');
      tags.append(el('span', AUTO_SEED_LABEL, 'q-core-auto-seed'));
      for (const chip of reasonChips(model.reasons)) tags.append(el('span', chip.text, 'q-core-reason'));
      root.append(tags);
    }

    if (!model || model.status === 'UNLOADED') {
      const emptyBox = el('div', undefined, 'q-core-empty');
      emptyBox.append(el('p', model?.statusText ?? '尚未載入追蹤結果。', 'q-core-empty-message'));
      root.append(emptyBox);
      container.append(root);
      return;
    }

    // Controls Bar: Mode Toggle + Speed Multiplier + Time
    const controls = el('div', undefined, 'q-core-controls-bar');

    // Mode Toggle
    const modeGroup = el('div', undefined, 'q-core-mode-toggle');
    modeGroup.setAttribute('role', 'radiogroup');
    modeGroup.setAttribute('aria-label', '播放模式');

    const singleBtn = el('button', '單畫面自動切鏡', 'q-core-btn');
    singleBtn.type = 'button';
    singleBtn.dataset.mode = 'single';
    singleBtn.setAttribute('aria-pressed', String(model.playbackMode === 'single'));
    if (model.playbackMode === 'single') singleBtn.classList.add('active');
    singleBtn.addEventListener('click', () => {
      if (onModeChange) onModeChange('single');
      else if (store?.dispatch) store.dispatch({ type: 'SET_PLAYBACK_MODE', value: 'single' });
    });

    const multiBtn = el('button', '多鏡頭候選網格', 'q-core-btn');
    multiBtn.type = 'button';
    multiBtn.dataset.mode = 'multi';
    multiBtn.setAttribute('aria-pressed', String(model.playbackMode === 'multi'));
    if (model.playbackMode === 'multi') multiBtn.classList.add('active');
    multiBtn.addEventListener('click', () => {
      if (onModeChange) onModeChange('multi');
      else if (store?.dispatch) store.dispatch({ type: 'SET_PLAYBACK_MODE', value: 'multi' });
    });

    modeGroup.append(singleBtn, multiBtn);
    controls.append(modeGroup);

    // Speed multiplier buttons
    const speedGroup = el('div', undefined, 'q-core-speed-group');
    speedGroup.setAttribute('role', 'radiogroup');
    speedGroup.setAttribute('aria-label', '播放速度');

    for (const sp of SUPPORTED_SPEEDS) {
      const spBtn = el('button', `${sp}×`, 'q-core-btn q-core-speed-btn');
      spBtn.type = 'button';
      spBtn.dataset.speed = String(sp);
      spBtn.setAttribute('aria-pressed', String(model.speed === sp));
      if (model.speed === sp) spBtn.classList.add('active');
      spBtn.addEventListener('click', () => {
        if (onSpeedChange) onSpeedChange(sp);
        else if (store?.dispatch) store.dispatch({ type: 'SET_SPEED', speed: sp });
      });
      speedGroup.append(spBtn);
    }
    controls.append(speedGroup);

    // Time readout
    const timeDisplay = el('span', `${(model.currentTUs / 1000000).toFixed(2)} s / ${(model.asOfUs / 1000000).toFixed(2)} s`, 'q-core-time-readout');
    controls.append(timeDisplay);

    root.append(controls);

    // Main Content: Single-view vs Multi-view
    if (model.playbackMode === 'single') {
      const singleViewBox = el('div', undefined, 'q-core-single-view');

      // Active Camera Tile
      const activeTile = el('article', undefined, 'q-core-active-camera');
      const tileHead = el('div', undefined, 'q-core-tile-head');
      const camName = el('h3', model.singleView.activeCameraId ?? '無畫面（盲區／遺失）', 'q-core-active-cam-id');
      const segBadge = el('span', model.singleView.badge, 'q-core-segment-badge');
      segBadge.dataset.kind = model.singleView.segmentKind;
      tileHead.append(camName, segBadge);
      activeTile.append(tileHead);

      // Frame / Video slot (renders actual <img> frame with synthetic frame data URI / media resolver)
      const frameSlot = el('div', undefined, 'q-core-card-media q-core-frame-display');
      frameSlot.dataset.cameraId = model.singleView.activeCameraId ?? '';
      frameSlot.dataset.kind = model.singleView.segmentKind;

      let captionText = '';
      if (model.singleView.segmentKind === 'ON_CAMERA') {
        captionText = `[${model.singleView.activeCameraId}] ${synthetic?'SYNTHETIC · 影像示意':'MISSING · 來源 RGB 未取得'} · OBSERVED 證據`;
      } else if (model.singleView.segmentKind === 'GAP') {
        captionText = `盲區間隔 · 前次鏡頭: ${model.singleView.lastObservedCameraId ?? '無'}`;
      } else if (model.singleView.segmentKind === 'LOST') {
        captionText = '目標遺失（LOST）';
      } else {
        captionText = '狀態未知';
      }

      const img = el('img', undefined, 'q-core-tracking-frame-img');
      img.addEventListener('load',()=>{if(!destroyed&&generation===renderGeneration)onFrameReady();});
      img.alt = captionText;
      img.dataset.cameraId = model.singleView.activeCameraId ?? '';
      img.dataset.kind = model.singleView.segmentKind;

      const frameSrc = resolveFrameImageSrc({
        cameraId: model.singleView.activeCameraId,
        currentTUs: model.currentTUs,
        segmentKind: model.singleView.segmentKind,
        lastObservedCameraId: model.singleView.lastObservedCameraId,
        mediaResolver,
        synthetic,
        onResolved: (url) => {
          if (!destroyed && generation===renderGeneration && /^\/api\/controlled_scene_media\?token=[A-Za-z0-9_-]{43}$/.test(url??'')) { img.src = url; img.hidden = false; frameCaption.textContent=`[${model.singleView.activeCameraId}] 來源綁定 RGB · OBSERVED 證據`; }
        },
      });
      if(frameSrc)img.src = frameSrc;else img.hidden=true;
      frameSlot.append(img);

      const frameCaption = el('div', captionText, 'q-core-frame-caption');
      frameSlot.append(frameCaption);
      activeTile.append(frameSlot);

      // Next switch countdown / indicator
      if (model.singleView.nextSwitchUs !== null) {
        const switchNotice = el('div', `下次切鏡時間: ${(model.singleView.nextSwitchUs / 1000000).toFixed(2)} s`, 'q-core-next-switch');
        activeTile.append(switchNotice);
      }
      singleViewBox.append(activeTile);

      // Transitions history list
      if (model.singleView.transitions && model.singleView.transitions.length > 0) {
        const transBox = el('details', undefined, 'q-core-transitions');
        const summary = el('summary', `自動切鏡歷程 (${model.singleView.transitions.length})`, 'q-core-trans-summary');
        transBox.append(summary);

        const list = el('ul', undefined, 'q-core-trans-list');
        for (const t of model.singleView.transitions) {
          const fromLabel = t.from_camera ? `${t.from_camera} (${t.from_kind})` : t.from_kind;
          const toLabel = t.to_camera ? `${t.to_camera} (${t.to_kind})` : t.to_kind;
          const item = el('li', `切鏡 @ ${(t.switch_at_us / 1000000).toFixed(2)}s: ${fromLabel} → ${toLabel}`, 'q-core-trans-item');
          list.append(item);
        }
        transBox.append(list);
        singleViewBox.append(transBox);
      }

      root.append(singleViewBox);
    } else {
      // Multi-view Grid
      const multiBox = el('div', undefined, 'q-core-multi-view');
      const grid = el('div', undefined, 'q-core-multi-grid');

      for (const cam of model.multiView.cameras) {
        const camTile = el('article', undefined, 'q-core-multi-cam-tile');
        camTile.dataset.cameraId = cam.cameraId;
        camTile.dataset.active = String(cam.isActive);

        const tileHead = el('div', undefined, 'q-core-tile-head');
        tileHead.append(el('h3', cam.cameraId, 'q-core-multi-cam-id'));
        const badge = el('span', cam.badge, 'q-core-cam-badge');
        badge.dataset.active = String(cam.isActive);
        tileHead.append(badge);
        camTile.append(tileHead);

        // Frame slot with actual <img> element and time window caption
        const frameSlot = el('div', undefined, 'q-core-card-media');
        frameSlot.dataset.cameraId = cam.cameraId;
        frameSlot.dataset.active = String(cam.isActive);

        const img = el('img', undefined, 'q-core-multi-cam-img');
        img.addEventListener('load',()=>{if(!destroyed&&generation===renderGeneration)onFrameReady();});
        img.alt = `${cam.cameraId} 畫面`;
        img.dataset.cameraId = cam.cameraId;
        img.dataset.active = String(cam.isActive);
        const timeLabel = `時間窗: [${(cam.firstUs / 1000000).toFixed(1)}s, ${(cam.lastUs / 1000000).toFixed(1)}s]`;

        const initialSrc = resolveFrameImageSrc({
          cameraId: cam.cameraId,
          currentTUs: model.currentTUs,
          segmentKind: cam.isActive ? 'ON_CAMERA' : 'CANDIDATE',
          includeCandidate: true,
          mediaResolver,
          synthetic,
          onResolved: (url) => {
            if (!destroyed && generation===renderGeneration && /^\/api\/controlled_scene_media\?token=[A-Za-z0-9_-]{43}$/.test(url??'')) { img.src = url; img.hidden = false; timeCaption.textContent=`${timeLabel} · 來源綁定 RGB`; }
          },
        });
        if(initialSrc)img.src = initialSrc;else img.hidden=true;
        frameSlot.append(img);

        const timeCaption = el('div', `${timeLabel} · ${synthetic?'SYNTHETIC · 影像示意':'MISSING · 來源 RGB 未取得'}`, 'q-core-frame-caption');
        frameSlot.append(timeCaption);
        camTile.append(frameSlot);

        grid.append(camTile);
      }
      multiBox.append(grid);
      root.append(multiBox);
    }

    // Topdown Map Panel
    const topdownBox = el('section', undefined, 'q-core-topdown-panel');
    topdownBox.setAttribute('aria-label', '俯視圖');

    const tdHead = el('div', undefined, 'q-core-topdown-head');
    const tdTitle = el('strong', '俯視圖', 'q-core-topdown-title');
    tdHead.append(tdTitle);

    const blindStatus = model?.topdown?.blind_status ?? 'UNAVAILABLE';
    const isEstimated = blindStatus === 'ESTIMATED' && model?.topdown?.blind?.usable;
    const blindBadge = el('span', isEstimated ? `INFERRED · 信心 ${model.topdown.blind.confidence??'UNKNOWN'}` : '預測不可用', 'q-core-blind-status');
    blindBadge.classList.add(isEstimated ? 'estimated' : 'unavailable');
    tdHead.append(blindBadge);

    const navLine = el('p', model?.topdown?.identity_line ?? CORE_NAVIGATION_BADGE, 'q-core-identity-note');
    tdHead.append(navLine);
    const modeSeg = el('div', undefined, 'q-topdown-mode');
    modeSeg.setAttribute('role', 'group');
    modeSeg.setAttribute('aria-label', '俯視圖顯示方式');
    for (const [mode, text] of [['2d', '2D 示意'], ['3d', '3D 場景']]) {
      const b = el('button', text, 'q-core-btn q-topdown-mode-btn');
      b.type = 'button'; b.dataset.mode = mode;
      b.setAttribute('aria-pressed', String(topdownMode === mode));
      if (topdownMode === mode) b.classList.add('active');
      b.addEventListener('click', () => setTopdownMode(mode));
      modeSeg.append(b);
    }
    tdHead.append(modeSeg);
    topdownBox.append(tdHead);
    if (scene3dNote) { const n = el('p', scene3dNote, 'q-scene3d-note'); n.setAttribute('role', 'status'); topdownBox.append(n); }

    if (topdownMode === '3d' && scene3dHost) {
      topdownBox.append(scene3dHost);
      if (scene3dReady) {
        const m3 = buildScene3dModel({ view: model, cameraAsset: scene3d?.cameraAsset() });
        const hud = el('div', undefined, 'q-scene3d-hud');
        const blindNow = m3.segmentKind === 'GAP' || m3.segmentKind === 'LOST';
        hud.append(el('span', `t = ${(m3.currentTUs / 1e6).toFixed(1)} s`), el('span', m3.stateText, blindNow ? 'q-scene3d-blind' : ''), el('span', `作用中鏡頭：${m3.activeCameraId ?? '—'}`), el('span', `估計位置：${m3.estimate.status}`), el('span', m3.estimateText));
        topdownBox.append(hud);
        const legend = el('ul', undefined, 'q-scene3d-legend');
        for (const t of m3.legend) legend.append(el('li', t));
        topdownBox.append(legend);
      }
      root.append(topdownBox);
      container.append(root);
      syncScene3d(model);
      return;
    }

    // SVG Map Rendering
    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('class', 'q-core-topdown-svg');
    svg.setAttribute('viewBox', '0 0 100 100');

    // Observed Path (solid line)
    const observedCams = model?.topdown?.observed_cameras ?? [];
    if (observedCams.length > 1) {
      const poly = document.createElementNS(SVG_NS, 'polyline');
      poly.setAttribute('class', 'q-core-observed-path');
      const at = new Map((model?.topdown?.nodes ?? []).map(n => [n.cameraId, n]));
      poly.setAttribute('points', observedCams.map(c => at.get(typeof c === 'string' ? c : c?.camera_id ?? c?.cameraId)).filter(Boolean).map(n => `${n.x},${n.y}`).join(' '));
      poly.setAttribute('stroke', '#50fa7b');
      poly.setAttribute('stroke-width', '2');
      poly.setAttribute('fill', 'none');
      svg.append(poly);
    }

    // Blind curve (dashed line)
    if (model?.topdown?.blind_curve?.visible && model.topdown.blind_curve.points?.length > 1) {
      const blindPath = document.createElementNS(SVG_NS, 'polyline');
      blindPath.setAttribute('class', 'q-core-blind-curve');
      blindPath.setAttribute('stroke', '#ffb86c');
      blindPath.setAttribute('stroke-width', '2');
      blindPath.setAttribute('stroke-dasharray', model.topdown.blind_curve.stroke_dasharray ?? '4 3');
      blindPath.setAttribute('points', model.topdown.blind_curve.svgPoints.map(pt => pt.join(',')).join(' '));
      blindPath.setAttribute('fill', 'none');
      svg.append(blindPath);
    }

    // Camera nodes
    const nodes = model?.topdown?.nodes ?? [];
    for (const node of nodes) {
      const circle = document.createElementNS(SVG_NS, 'circle');
      circle.setAttribute('class', `q-core-cam-node ${node.isActive ? 'active' : ''}`);
      circle.setAttribute('cx', String(node.x));
      circle.setAttribute('cy', String(node.y));
      circle.setAttribute('r', node.isActive ? '4' : '2.5');
      circle.setAttribute('fill', node.isActive ? '#50fa7b' : '#6272a4');
      svg.append(circle);

      const label = document.createElementNS(SVG_NS, 'text');
      label.setAttribute('class', 'q-core-node-label');
      label.setAttribute('x', String(node.x));
      label.setAttribute('y', String(node.y - 4));
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('fill', '#f8f8f2');
      label.setAttribute('font-size', '3.5');
      label.textContent = node.cameraId;
      svg.append(label);
    }

    topdownBox.append(svg);
    root.append(topdownBox);

    container.append(root);
  }

  // Initial render
  if (store) {
    const s = store.getState();
    const model = s.coreTrackingView ?? (s.coreTrackResponse ? buildCoreTrackingViewModel(s.coreTrackResponse, {
      tUs: s.tUs,
      playbackMode: s.playbackMode,
      speed: s.speed,
      cameraGraph: s.cameraGraph,
      displayPositions: s.displayPositions,
      runClockId: s.activeRun?.clock_mapping?.clock_id ?? s.activeRun?.clock_id ?? null,
    }) : null);
    render(model);

    const unsub = store.subscribe(() => {
      if (destroyed) return;
      const state = store.getState();
      const nextModel = state.coreTrackingView ?? (state.coreTrackResponse ? buildCoreTrackingViewModel(state.coreTrackResponse, {
        tUs: state.tUs,
        playbackMode: state.playbackMode,
        speed: state.speed,
        cameraGraph: state.cameraGraph,
        displayPositions: state.displayPositions,
        runClockId: state.activeRun?.clock_mapping?.clock_id ?? state.activeRun?.clock_id ?? null,
      }) : null);
      render(nextModel);
    });

    return {
      update(m) { render(m); },
      destroy() {
        destroyed = true;
        try { scene3d?.destroy(); } catch { /* ignore */ }
        unsub();
        container.replaceChildren();
      },
    };
  }

  return {
    update(m) { render(m); },
    destroy() {
      destroyed = true;
      try { scene3d?.destroy(); } catch { /* ignore */ }
      container.replaceChildren();
    },
  };
}
