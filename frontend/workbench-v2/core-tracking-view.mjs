// DOM View for Core Tracking Screen: Single-view auto-switching, Multi-view candidates, and Topdown integration.
// Connects to buildCoreTrackingViewModel output. Pure DOM view; no inference inputs.

import {
  buildCoreTrackingViewModel,
  SUPPORTED_SPEEDS,
  CORE_NAVIGATION_BADGE,
} from './core-search-track-model.mjs';

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
} = {}) {
  if (!container) throw new Error('CONTAINER_REQUIRED');

  let currentModel = null;
  let destroyed = false;

  function render(model) {
    if (destroyed) return;
    currentModel = model;
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
    singleBtn.addEventListener('click', () => {
      if (onModeChange) onModeChange('single');
      else if (store?.dispatch) store.dispatch({ type: 'SET_PLAYBACK_MODE', value: 'single' });
    });

    const multiBtn = el('button', '多畫面', 'q-core-btn');
    multiBtn.type = 'button';
    multiBtn.dataset.mode = 'multi';
    multiBtn.setAttribute('aria-pressed', String(model.playbackMode === 'multi'));
    multiBtn.addEventListener('click', () => {
      if (onModeChange) onModeChange('multi');
      else if (store?.dispatch) store.dispatch({ type: 'SET_PLAYBACK_MODE', value: 'multi' });
    });

    modeGroup.append(singleBtn, multiBtn);
    controls.append(modeGroup);

    // Speed Controls
    const speedGroup = el('div', undefined, 'q-core-speed-controls');
    speedGroup.setAttribute('aria-label', '播放倍速');
    for (const sp of SUPPORTED_SPEEDS) {
      const spBtn = el('button', `${sp}×`, 'q-core-btn');
      spBtn.type = 'button';
      spBtn.dataset.speed = String(sp);
      spBtn.setAttribute('aria-pressed', String(model.speed === sp));
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

      // Frame / Video slot
      const frameSlot = el('div', undefined, 'q-core-card-media q-core-frame-display');
      if (model.singleView.segmentKind === 'ON_CAMERA') {
        frameSlot.textContent = `[${model.singleView.activeCameraId}] 影格播放中 · OBSERVED`;
      } else if (model.singleView.segmentKind === 'GAP') {
        frameSlot.textContent = `盲區間隔 · 前次鏡頭: ${model.singleView.lastObservedCameraId ?? '無'}`;
      } else if (model.singleView.segmentKind === 'LOST') {
        frameSlot.textContent = '目標遺失（LOST）';
      } else {
        frameSlot.textContent = '狀態未知';
      }
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

        const frameSlot = el('div', undefined, 'q-core-card-media');
        frameSlot.textContent = `時間窗: [${(cam.firstUs / 1000000).toFixed(1)}s, ${(cam.lastUs / 1000000).toFixed(1)}s]`;
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

    // Blind Curve (dashed line) — Rendered ONLY if isEstimated is true
    if (isEstimated) {
      const curveSegments = model?.topdown?.blind_curves ?? [];
      const curvePoints = model?.topdown?.blind?.curve?.points ?? [];
      if (curvePoints.length > 0 || curveSegments.length > 0) {
        const pathEl = document.createElementNS(SVG_NS, 'path');
        pathEl.setAttribute('class', 'q-core-blind-curve');
        pathEl.setAttribute('stroke', '#8be9fd');
        pathEl.setAttribute('stroke-width', '2');
        pathEl.setAttribute('stroke-dasharray', '6 4');
        pathEl.setAttribute('fill', 'none');
        svg.append(pathEl);
      }
    }

    // Camera nodes
    for (const camId of (model?.topdown?.observed_cameras ?? [])) {
      const circle = document.createElementNS(SVG_NS, 'circle');
      circle.setAttribute('class', 'q-core-camera-node');
      circle.setAttribute('r', '4');
      circle.setAttribute('fill', camId === model.singleView.activeCameraId ? '#50fa7b' : '#888');
      circle.dataset.camera = camId;
      svg.append(circle);
    }

    topdownBox.append(svg);
    root.append(topdownBox);

    container.append(root);
  }

  // Initial render & subscription
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
