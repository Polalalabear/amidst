// #772: read-only step-by-step decision view for ?mode=review on the v1 front desk.
// Every value is copied from the tracking response the screen already holds (association_audit, sightings, agent, provenance);
// nothing is inferred, no request is made, and a field the response does not carry is shown as UNKNOWN. Never mounted in presentation mode.

const HIDDEN_KEY = /^(gt_|ground_truth|actor|renderer|trajectory|visibility|depth|event_script|private)/i;
const FIELDS = [
  ['reason', '決策／原因'], ['decision_source', '決策來源'], ['decided_by', '決定者'], ['link_kind', '連結種類'],
  ['evidence_state', '證據狀態'], ['confidence', '信心'], ['gap_us', '空檔 (µs)'], ['candidate_tracks', '候選'],
  ['adopted_track_ref', '採用'], ['rule_answer', '規則答案'], ['fallback_reason', 'fallback 原因'], ['rule_override', '規則覆寫'],
  ['model', '模型'], ['detections', '偵測數'], ['frames_attached', '附影格數'], ['identity_verdict', '身分'],
];
const val = v => v === null || v === undefined ? 'UNKNOWN' : typeof v === 'object' ? JSON.stringify(v) : String(v);

// One row per association_audit entry, oldest first. `fields` keeps only the response's own values, in a fixed order.
export function decisionRows(response) {
  const audit = Array.isArray(response?.association_audit) ? response.association_audit : [];
  const sightings = Array.isArray(response?.sightings) ? response.sightings : [];
  return audit.map(a => {
    const fields = FIELDS.filter(([k]) => Object.hasOwn(a, k) && !HIDDEN_KEY.test(k)).map(([k, label]) => ({key: k, label, value: val(a[k])}));
    if (a.answer && typeof a.answer === 'object') {
      const {answer, camera_id, reason_codes} = a.answer;
      fields.push({key: 'answer', label: 'Agent 答案', value: val(answer)}, {key: 'answer.camera_id', label: 'Agent 選鏡頭', value: val(camera_id)}, {key: 'answer.reason_codes', label: 'Agent 理由碼', value: val(reason_codes)});
    }
    const evidence = sightings.filter(s => a.to_track_ref && s.track_ref === a.to_track_ref).flatMap(s => s.observation_ids ?? []);
    return {
      timestamp_us: a.timestamp_us ?? null,
      from: a.from_camera_id ?? null, to: a.to_camera_id ?? null,
      title: `${a.from_camera_id ?? '—'} → ${a.to_camera_id ?? '—'} · ${val(a.reason)}`,
      fields,
      evidence: {count: evidence.length, first: evidence[0] ?? null, last: evidence.at(-1) ?? null},
      hasMissing: !Object.hasOwn(a, 'decision_source') && !Object.hasOwn(a, 'decided_by'),
    };
  }).sort((x, y) => (x.timestamp_us ?? 0) - (y.timestamp_us ?? 0));
}

export function reviewSummary(response) {
  const p = response?.provenance ?? {}, ag = response?.agent ?? null;
  return {
    producer: val(p.producer), gt_read: val(p.gt_read), parameter_mode: val(p.parameter_mode), formal_eligible: val(p.formal_eligible),
    agent: ag ? {switch_mode: val(ag.switch_mode), available: val(ag.available), decisions: val(ag.decisions), adopted: val(ag.adopted), fallbacks: val(ag.fallbacks), agent_used: val(ag.agent_used), unavailable_reason: val(ag.unavailable_reason)} : null,
    output_sha256: val(response?.output_sha256),
  };
}

export function mountReviewPanel({doc, host, store, onSeek}) {
  const state0 = store.getState();
  if (!state0.reviewMode) return {destroy() {}};   // presentation / normal mode: no DOM at all
  const el = (tag, text, cls) => { const n = doc.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
  const panel = el('aside', undefined, 'ui-review-panel'); panel.id = 'ui-review-panel'; panel.setAttribute('aria-label', '審核模式 · 逐步決策');
  host.append(panel);
  let key = '';
  const render = s => {
    const resp = s.coreTrackResponse, t = s.tUs;
    const k = JSON.stringify([resp?.output_sha256 ?? null, Math.floor(t / 1000)]);
    if (k === key) return; key = k;
    panel.replaceChildren(el('h3', '審核模式 · 逐步決策（只讀）'));
    if (!resp) { panel.append(el('p', '尚未載入追蹤結果。', 'ui-muted')); return; }
    const sum = reviewSummary(resp), head = el('div', undefined, 'ui-review-head');
    head.append(el('p', `來源 ${sum.producer} · GT 讀取 ${sum.gt_read} · 參數 ${sum.parameter_mode} · 正式資格 ${sum.formal_eligible}`, 'ui-mono ui-small'));
    if (sum.agent) head.append(el('p', `Agent ${sum.agent.switch_mode} · 可用 ${sum.agent.available} · 決策 ${sum.agent.decisions} · 採用 ${sum.agent.adopted} · fallback ${sum.agent.fallbacks} · 實際使用 ${sum.agent.agent_used}${sum.agent.unavailable_reason !== 'UNKNOWN' ? ' · ' + sum.agent.unavailable_reason : ''}`, 'ui-mono ui-small'));
    head.append(el('p', '身分未確認 · 物理通行與碰撞 UNKNOWN', 'ui-mono ui-small'));
    panel.append(head);
    const rows = decisionRows(resp).filter(r => r.timestamp_us === null || r.timestamp_us <= t);
    panel.append(el('p', `播放時間 ${(t / 1e6).toFixed(2)} s 之前的決策：${rows.length} 筆`, 'ui-small ui-muted'));
    for (const r of rows) {
      const d = el('details', undefined, 'ui-review-row'), sm = el('summary', `${r.timestamp_us === null ? '—' : (r.timestamp_us / 1e6).toFixed(2) + ' s'} · ${r.title}`);
      d.append(sm);
      const dl = el('dl', undefined, 'ui-review-fields');
      for (const f of r.fields) { dl.append(el('dt', f.label), el('dd', f.value, 'ui-mono')); }
      if (r.hasMissing) { dl.append(el('dt', '決策來源'), el('dd', 'UNKNOWN（回應未帶 decision_source／decided_by）', 'ui-mono')); }
      dl.append(el('dt', '證據'), el('dd', r.evidence.count ? `${r.evidence.count} 筆觀測 · ${r.evidence.first} … ${r.evidence.last}` : 'UNKNOWN（沒有對應 sighting）', 'ui-mono'));
      d.append(dl);
      if (r.timestamp_us !== null) { const b = el('button', '跳至來源時間', 'ui-link'); b.type = 'button'; b.addEventListener('click', () => onSeek(r.timestamp_us)); d.append(b); }
      panel.append(d);
    }
  };
  const un = store.subscribe(render); render(store.getState());
  return {destroy() { un(); panel.remove(); }};
}
