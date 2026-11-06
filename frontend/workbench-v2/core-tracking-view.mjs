// DOM View for Core Tracking Screen: Single-view auto-switching, Multi-view candidates, and Topdown integration.
// Connects to buildCoreTrackingViewModel output. Pure DOM view; no inference inputs.

import {
  buildCoreTrackingViewModel,
  SUPPORTED_SPEEDS,
  CORE_NAVIGATION_BADGE,
} from './core-search-track-model.mjs';
import { resolveFrameImageSrc } from './core-media.mjs';

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
} = {}) {
  if (!container) throw new Error('CONTAINER_REQUIRED');

  let currentModel = null;
  let destroyed = false;
  let generation = 0;

  function render(model) {
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
        img.alt = `${cam.cameraId} 畫面`;
        img.dataset.cameraId = cam.cameraId;
        img.dataset.active = String(cam.isActive);

        const initialSrc = resolveFrameImageSrc({
          cameraId: cam.cameraId,
          currentTUs: model.currentTUs,
          segmentKind: cam.isActive ? 'ON_CAMERA' : 'CANDIDATE',
          mediaResolver,
          synthetic,
          onResolved: (url) => {
            if (!destroyed && generation===renderGeneration && /^\/api\/controlled_scene_media\?token=[A-Za-z0-9_-]{43}$/.test(url??'')) { img.src = url; img.hidden = false; timeCaption.textContent+=` · 來源綁定 RGB`; }
          },
        });
        if(initialSrc)img.src = initialSrc;else img.hidden=true;
        frameSlot.append(img);

        const timeCaption = el('div', `時間窗: [${(cam.firstUs / 1000000).toFixed(1)}s, ${(cam.lastUs / 1000000).toFixed(1)}s] · ${synthetic?'SYNTHETIC · 影像示意':'MISSING · 來源 RGB 未取得'}`, 'q-core-frame-caption');
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
    const blindBadge = el('span', isEstimated ? '物理預測（示意，非實際路徑）· 低信心' : '預測不可用', 'q-core-blind-status');
    blindBadge.classList.add(isEstimated ? 'estimated' : 'unavailable');
    tdHead.append(blindBadge);

    const navLine = el('p', model?.topdown?.identity_line ?? CORE_NAVIGATION_BADGE, 'q-core-identity-note');
    tdHead.append(navLine);
    topdownBox.append(tdHead);

    // SVG Map Rendering
    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('class', 'q-core-topdown-svg');
    svg.setAttribute('viewBox', '0 0 100 100');

    // Observed Path (solid line)
    const observedCams = model?.topdown?.observed_cameras ?? [];
    if (observedCams.length > 1) {
      const poly = document.createElementNS(SVG_NS, 'polyline');
      poly.setAttribute('class', 'q-core-observed-path');
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
      blindPath.setAttribute('stroke-dasharray', '4 3');
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
      }) : null);
      render(nextModel);
    });

    return {
      update(m) { render(m); },
      destroy() {
        destroyed = true;
        unsub();
        container.replaceChildren();
      },
    };
  }

  return {
    update(m) { render(m); },
    destroy() {
      destroyed = true;
      container.replaceChildren();
    },
  };
}
