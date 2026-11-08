'use strict';

const $ = id => document.getElementById(id);
const svgNS = 'http://www.w3.org/2000/svg';
let data;
let state;
let storageKey;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function switchTab(tab) {
  for (const name of ['preview', 'confirm']) {
    const selected = name === tab;
    $(name).hidden = !selected;
    $(`tab-${name}`).classList.toggle('active', selected);
    $(`tab-${name}`).setAttribute('aria-selected', String(selected));
  }
}

function save() {
  state.reviewer = $('reviewer').value;
  state.date = $('review-date').value;
  try { localStorage.setItem(storageKey, JSON.stringify(state)); }
  catch (_) { $('validation').textContent = 'localStorage 不可用；仍可下載目前表單。'; }
}

function rowState(camera) {
  const current = state.rows[camera];
  if (!current || !Array.isArray(current.regions) || typeof current.unknown !== 'boolean') {
    state.rows[camera] = {regions: [], unknown: false};
  }
  return state.rows[camera];
}

function renderPreview(camera) {
  const card = element('article', undefined, 'card');
  const head = element('div', undefined, 'card-head');
  head.append(element('h3', camera.camera_id), element('span', `${camera.detections.length} 候選`, 'badge'));
  const stage = element('div', undefined, 'stage');
  const image = element('img');
  image.src = camera.image_url;
  image.alt = `${camera.camera_id} 原始靜態 RGB`;
  image.width = 960;
  image.height = 540;
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('viewBox', '0 0 960 540');
  svg.setAttribute('preserveAspectRatio', 'none');
  svg.style.display = $('show-boxes').checked ? '' : 'none';
  svg.classList.add('overlay');
  for (const [index, det] of camera.detections.entries()) {
    const [x1, y1, x2, y2] = det.bbox_xyxy_px;
    const rect = document.createElementNS(svgNS, 'rect');
    for (const [key, value] of Object.entries({x: x1, y: y1, width: x2 - x1,
      height: y2 - y1, fill: 'none', stroke: '#f9a01b', 'stroke-width': 2})) {
      rect.setAttribute(key, String(value));
    }
    const label = document.createElementNS(svgNS, 'text');
    label.setAttribute('x', String(Math.max(2, x1 + 3)));
    label.setAttribute('y', String(Math.max(16, y1 - 5)));
    label.setAttribute('fill', '#fff');
    label.setAttribute('stroke', '#16262c');
    label.setAttribute('stroke-width', '3');
    label.setAttribute('paint-order', 'stroke');
    label.setAttribute('font-size', '13');
    label.setAttribute('font-weight', '700');
    label.textContent = `${index + 1} ${det.class_label} ${det.score.toFixed(2)}`;
    svg.append(rect, label);
  }
  stage.append(image, svg);
  const details = element('details', undefined, 'candidate-list');
  details.append(element('summary', '候選明細：原 class label／score'));
  const list = element('ul');
  for (const [index, det] of camera.detections.entries()) {
    list.append(element('li', `${index + 1}. ${det.class_label} · ${det.score.toFixed(3)} · [${det.bbox_xyxy_px.map(n => n.toFixed(1)).join(', ')}]`));
  }
  details.append(list);
  if (camera.camera_id.startsWith('CAM_CORR_')) {
    details.append(element('p', '走廊候選可能為誤檢；本頁不更名、不標真值。', 'caution'));
  }
  const hash = element('div', `原圖 SHA-256：${camera.frame_sha256}`, 'framehash');
  card.append(head, stage, details, hash);
  $('preview-grid').append(card);
}

function updateBadge(camera, badge) {
  const selected = rowState(camera);
  const status = selected.unknown ? 'PROPOSED_UNKNOWN' :
    selected.regions.length ? 'PROPOSED_KNOWN' : 'NOT_EVALUATED';
  badge.textContent = status;
  badge.classList.toggle('pending', status === 'NOT_EVALUATED');
}

function renderConfirmation(camera) {
  const card = element('article', undefined, 'card confirm-card');
  const head = element('div', undefined, 'card-head');
  const badge = element('span', '', 'badge');
  head.append(element('h3', camera.camera_id), badge);
  card.append(head);
  const body = element('div', undefined, 'confirm-body');
  const imagePanel = element('div', undefined, 'confirm-image');
  const image = element('img');
  image.src = camera.image_url;
  image.alt = `${camera.camera_id} 原始靜態 RGB，供 coverage 人工確認`;
  image.width = 960;
  image.height = 540;
  imagePanel.append(image);
  const controls = element('div', undefined, 'confirm-controls');
  controls.append(element('p', '依旁邊原圖選擇可確認的已知區域；若無法判定，勾選 UNKNOWN。'));
  const choices = element('div', undefined, 'region-list');
  const known = [];
  const selected = rowState(camera.camera_id);
  for (const region of data.regions) {
    const label = element('label');
    const box = element('input');
    box.type = 'checkbox';
    box.checked = selected.regions.includes(region);
    box.setAttribute('aria-label', `${camera.camera_id} ${region}`);
    box.addEventListener('change', () => {
      if (box.checked) {
        unknown.checked = false;
        selected.unknown = false;
      }
      selected.regions = known.filter(item => item.box.checked).map(item => item.region);
      updateBadge(camera.camera_id, badge);
      save();
    });
    known.push({region, box});
    label.append(box, document.createTextNode(region));
    choices.append(label);
  }
  const unknownLabel = element('label', undefined, 'unknown');
  const unknown = element('input');
  unknown.type = 'checkbox';
  unknown.checked = selected.unknown;
  unknown.setAttribute('aria-label', `${camera.camera_id} UNKNOWN`);
  unknown.addEventListener('change', () => {
    selected.unknown = unknown.checked;
    if (unknown.checked) {
      for (const item of known) item.box.checked = false;
      selected.regions = [];
    }
    updateBadge(camera.camera_id, badge);
    save();
  });
  unknownLabel.append(unknown, document.createTextNode('UNKNOWN'));
  choices.append(unknownLabel);
  controls.append(choices, element('div', `frame SHA-256：${camera.frame_sha256}`, 'framehash'));
  body.append(imagePanel, controls);
  card.append(body);
  updateBadge(camera.camera_id, badge);
  $('confirm-grid').append(card);
}

function exportDraft() {
  save();
  const reviewer = state.reviewer.trim();
  const date = state.date;
  if (!reviewer || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    $('validation').textContent = '請填寫審閱者與有效日期。';
    return;
  }
  const rows = [];
  for (const camera of data.cameras) {
    const selected = rowState(camera.camera_id);
    const regions = [...new Set(selected.regions)];
    if (regions.some(region => !data.regions.includes(region)) || (selected.unknown && regions.length)) {
      $('validation').textContent = `${camera.camera_id} 的已知區域與 UNKNOWN 不可同時選擇。`;
      return;
    }
    rows.push({camera_id: camera.camera_id, frame_sha256: camera.frame_sha256,
      selection_state: selected.unknown ? 'PROPOSED_UNKNOWN' : regions.length ? 'PROPOSED_KNOWN' : 'NOT_EVALUATED',
      proposed_covered_regions: regions, proposed_unknown: !!selected.unknown});
  }
  const draft = {schema_version: 'local-r005-coverage-review-draft.v1',
    approval_status: 'DRAFT', coverage_basis: 'NOT_EVALUATED',
    reviewer, review_date: date, exported_at: new Date().toISOString(),
    scene_id: data.scene_id, source_pr_heads: data.source_pr_heads,
    source_report_sha256: data.report_sha256,
    source_region_graph_sha256: data.region_graph_sha256,
    candidate_threshold: data.threshold, rows};
  const blob = new Blob([JSON.stringify(draft, null, 2) + '\n'], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const link = element('a');
  link.href = url;
  link.download = `r005-coverage-review-DRAFT-${date}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  $('validation').textContent = '已下載本機 DRAFT JSON；尚未核定或寫入 graph。';
}

async function start() {
  const response = await fetch('/data.json', {cache: 'no-store'});
  if (!response.ok) throw new Error('資料載入失敗');
  data = await response.json();
  if (data.cameras.length !== 6 || data.regions.length !== 6 ||
      data.cameras.reduce((sum, c) => sum + c.detections.length, 0) !== 33) {
    throw new Error('資料範圍不符');
  }
  storageKey = `r005-review:${data.report_sha256}:${data.region_graph_sha256}`;
  try { state = JSON.parse(localStorage.getItem(storageKey) || 'null'); } catch (_) { state = null; }
  if (!state || typeof state !== 'object' || !state.rows) state = {reviewer: '', date: '', rows: {}};
  $('reviewer').value = state.reviewer || '';
  $('review-date').value = state.date || '';
  $('reviewer').addEventListener('input', save);
  $('review-date').addEventListener('change', save);
  $('meta').append(element('span', `PR #473 ${data.source_pr_heads['473'].slice(0, 12)}`),
    element('span', `PR #447 ${data.source_pr_heads['447'].slice(0, 12)}`),
    element('span', `threshold ${data.threshold.toFixed(2)} · 33 候選`),
    element('span', 'coverage NOT_EVALUATED'));
  for (const camera of data.cameras) {
    renderPreview(camera);
    renderConfirmation(camera);
  }
  $('show-boxes').addEventListener('change', () => {
    for (const svg of document.querySelectorAll('.overlay')) svg.style.display = $('show-boxes').checked ? '' : 'none';
  });
  $('tab-preview').addEventListener('click', () => switchTab('preview'));
  $('tab-confirm').addEventListener('click', () => switchTab('confirm'));
  $('download').addEventListener('click', exportDraft);
}

start().catch(error => { $('validation').textContent = `預覽無法載入：${error.message}`; switchTab('confirm'); });
