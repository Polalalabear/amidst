// B 畫面（系統端）：單一跟隨視角＋HUD。
// 主區域只顯示後台判定的作用中鏡頭；切鏡有提示；失聯時有狀態和計時。HUD 的每個欄位都來自後台經
// protocol.mjs 白名單送出的訊息（validateSystemMessage 不過的訊息整則丟掉）和 /config（後台啟動參數）。
// 看不到也收不到操作者的座標、角色代號或 GT。8 鏡頭除錯格狀版：?role=system&view=grid。
import { CHANNEL, now } from './common.mjs';
import { TRACK_MODES, validateSystemMessage } from './protocol.mjs';
import { switchView, buildRequest, hudModeNote } from './llm_switch.mjs';
import { defaultModel, clampSideWidth, loadPanelPrefs, savePanelPrefs, lostHint, sameColorCount, sameColorNotice } from './ui_state.mjs';
import { createHudState, recordLatency, reduce, view as hudView, pickTarget } from './hud.mjs';

const TYPE_ZH = { ACQUIRE: '鎖定目標', SWITCH: '切鏡', TARGET_OUT_OF_VIEW: '目標離開視野', LOST: '失聯', REACQUIRE: '重新找到',
  ADJUDICATE_ASK: '問 LLM', ADJUDICATED: 'LLM 回答' };

const COLOR_LABEL = { red: '紅衣', blue: '藍衣' };
const validColor = color => color === 'red' || color === 'blue';
const positiveTick = tick => Number.isSafeInteger(tick) && tick >= 0;
const finiteVector = (value, size) => Array.isArray(value) && value.length === size && value.every(Number.isFinite);
const TEXT_ERRORS = {
  FEATURE_REQUIRED: '請選紅衣或藍衣，或輸入含顏色的句子。',
  FEATURE_AMBIGUOUS: '句子同時提到紅衣和藍衣。請選一個顏色。',
  COLOR_UNSUPPORTED: '即時追蹤支援紅衣和藍衣。',
  CANDIDATE_STALE: '候選已更新，請重新選擇。',
  CANDIDATE_UNKNOWN: '找不到這個候選，請重新選擇。',
  TRACK_MODE_CONFLICT: '追蹤狀態已變更，請重試。',
  SESSION_MISMATCH: '新的一局已開始，請重新選擇目標。',
  INVALID_SENTENCE: '句子最多 80 字。',
};

export const createBState = () => ({
  session: null, mode: 'IDLE', color: null, chip: null, sentence: '',
  reselecting: false, candidates: [], frames: [], candidateTick: null,
  lastTick: null, sessionAt: -Infinity, applyAt: -Infinity, message: '',
});

export function listCandidates(data, color) {
  if (!Array.isArray(data) || !validColor(color)) return [];
  const seen = new Set();
  const candidates = [];
  for (const candidate of data) {
    if (!candidate || candidate.color !== color || !positiveTick(candidate.tick)
        || typeof candidate.cand_id !== 'string' || !candidate.cand_id.length || candidate.cand_id.length > 64
        || typeof candidate.cam !== 'string' || !candidate.cam.length || candidate.cam.length > 64
        || !finiteVector(candidate.bbox, 4) || !finiteVector(candidate.est_xy, 2)
        || !Number.isFinite(candidate.score) || seen.has(candidate.cand_id)) continue;
    const { cand_id, tick, cam, bbox, est_xy, score } = candidate;
    seen.add(cand_id);
    candidates.push({ cand_id, tick, cam, bbox: [...bbox], est_xy: [...est_xy], color, score });
  }
  candidates.sort((a, b) => a.bbox[0] + a.bbox[2] - b.bbox[0] - b.bbox[2]
    || a.cam.localeCompare(b.cam) || a.cand_id.localeCompare(b.cand_id));
  return candidates.map((candidate, i) => ({ ...candidate, number: i + 1 }));
}

export function reduceB(state, event) {
  if (event.type === 'INTENT') return { ...state, chip: event.chip, sentence: event.sentence };
  if (event.type === 'MESSAGE') return { ...state, message: event.message };
  if (event.type === 'SESSION') {
    const data = event.data;
    if (!data || typeof data.session_id !== 'string' || !/^[a-f0-9]{16}$/i.test(data.session_id)
        || !TRACK_MODES.includes(data.mode) || (data.color !== null && !validColor(data.color))) return state;
    if (data.session_id !== state.session) {
      return { ...createBState(), session: data.session_id,
        sessionAt: event.at ?? -Infinity,
        mode: state.session ? 'IDLE' : data.mode, color: state.session ? null : data.color };
    }
    if (data.mode === state.mode && data.color === state.color) return state;
    return { ...state, mode: data.mode, color: data.color, reselecting: false, candidates: [], candidateTick: null };
  }
  if (event.type === 'DISCONNECT') return { ...createBState(), message: event.message };
  if (!state.session || event.session !== state.session) return state;
  if (event.type === 'FRAME') {
    const msg = event.msg;
    if (msg.t_capture_ms < state.sessionAt || (state.lastTick !== null && msg.tick <= state.lastTick)) return state;
    const next = { ...state, frames: [...state.frames, msg].slice(-5), lastTick: msg.tick };
    if (!msg.tracking.target || !event.adoptMode || msg.t_capture_ms < state.applyAt) return next;
    const { color, mode } = msg.tracking.target;
    const reselecting = mode === 'NEEDS_PICK' && msg.tracking.state === 'TRACKING';
    if (mode === state.mode && color === state.color) return { ...next, reselecting };
    return { ...next, color, mode, reselecting, candidates: [], candidateTick: null };
  }
  if (event.type === 'CANDIDATES') {
    const { data } = event;
    if (state.mode !== 'NEEDS_PICK' || data?.color !== state.color
        || !positiveTick(data.tick) || (state.candidateTick !== null && data.tick < state.candidateTick)) return state;
    return { ...state, candidates: listCandidates(data.candidates, data.color), candidateTick: data.tick };
  }
  if (event.type === 'APPLIED') {
    const { kind, data, at } = event;
    const color = kind === 'stop' ? null : data.color;
    const mode = data.mode;
    return { ...state, color, mode, reselecting: kind === 'reselect',
      candidates: mode === 'NEEDS_PICK' ? listCandidates(data.candidates, color) : [],
      candidateTick: mode === 'NEEDS_PICK' ? data.tick : null,
      applyAt: at, message: parseFeedback(data.parse) };
  }
  return state;
}

export function candidateFrame(groups, candidate) {
  return groups.find(row => row.tick === candidate.tick)?.frames.find(frame => frame.cam === candidate.cam);
}

function parseFeedback(parse) {
  if (!parse) return '';
  const result = [];
  if (parse.note === 'CHIP_OVERRIDES_SENTENCE') result.push('採用所選顏色');
  const excluded = { action: '查找動作', location: '地點', time: '時間' };
  const ignored = Array.isArray(parse.ignored)
    ? parse.ignored.filter(field => Object.hasOwn(excluded, field)).map(field => excluded[field]) : [];
  if (ignored.length) result.push(`已略過${ignored.join('、')}`);
  if (Number.isSafeInteger(parse.unrecognized_count) && parse.unrecognized_count > 0) {
    result.push(`${parse.unrecognized_count} 段未辨識`);
  }
  return result.join('。');
}

export function createBController({ fetcher = fetch, clock = now, onChange = () => {}, onAction = () => {} } = {}) {
  let state = createBState();
  let revision = 0;
  let operation = null;
  let poll = null;
  let candidateRequest = null;
  let outdatedSession = null;
  function dispatch(event) {
    const next = reduceB(state, event);
    if (next === state) return false;
    const previous = state;
    state = next;
    onChange(state, previous, event);
    return true;
  }
  const request = async (path, body) => {
    const response = await fetcher(`/track/${path}`, body ? {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    } : { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw new Error(data?.error || 'REQUEST_FAILED');
    return data;
  };
  function refreshCandidates() {
    if (operation || state.mode !== 'NEEDS_PICK' || !state.session) return Promise.resolve();
    if (candidateRequest) return candidateRequest;
    const session = state.session, ticket = revision;
    const inflight = request(`candidates?color=${state.color}`)
      .then(data => {
        if (ticket === revision) dispatch({ type: 'CANDIDATES', data, session });
      })
      .catch(() => {
        if (ticket === revision) dispatch({ type: 'MESSAGE', message: '候選讀取失敗，正在重試。' });
      })
      .finally(() => { if (candidateRequest === inflight) candidateRequest = null; });
    candidateRequest = inflight;
    return inflight;
  }
  function sync() {
    if (poll) return poll;
    const ticket = revision;
    poll = request('state').then(data => {
      if (!data || data.session_id === outdatedSession) return;
      if (data.session_id !== state.session || (!operation && revision === ticket)) {
        const session = state.session;
        if (dispatch({ type: 'SESSION', data, at: clock() }) && state.session !== session) {
          revision++;
          operation = null;
          candidateRequest = null;
          outdatedSession = null;
        }
      }
      void refreshCandidates();
    }).catch(() => {
      if (!state.session) dispatch({ type: 'MESSAGE', message: '正在連線到追蹤後台。' });
    }).finally(() => { poll = null; });
    return poll;
  }
  async function act(kind, candidate) {
    const session = state.session;
    if (operation || !session) return false;
    const args = { session_id: session };
    const endpoint = kind === 'reselect' ? 'start' : kind;
    if (kind === 'start') {
      if (state.chip) args.color = state.chip;
      if (state.sentence.trim()) args.sentence = state.sentence.trim();
      if (!args.color && !args.sentence) {
        dispatch({ type: 'MESSAGE', message: TEXT_ERRORS.FEATURE_REQUIRED });
        return false;
      }
    } else if (kind === 'reselect') {
      if (state.mode !== 'TRACKING') return false;
      Object.assign(args, { color: state.color, reselect: true });
    } else if (kind === 'pick') {
      if (state.mode !== 'NEEDS_PICK' || !state.candidates.some(item => item.cand_id === candidate?.cand_id)) return false;
      args.cand_id = candidate.cand_id;
    } else if (kind !== 'stop') return false;

    const at = clock();
    const ticket = ++revision;
    operation = ticket;
    candidateRequest = null;
    dispatch({ type: 'MESSAGE', message: '' });
    let refresh = false, syncState = false;
    try {
      const data = await request(endpoint, args);
      if (revision !== ticket || state.session !== session) return false;
      if (!TRACK_MODES.includes(data?.mode) || (kind !== 'stop' && !validColor(data.color))) {
        throw new Error('REQUEST_FAILED');
      }
      dispatch({ type: 'APPLIED', kind, data, session, at });
      const picked = kind === 'pick' ? data.picked : kind === 'start' && data.mode === 'TRACKING'
        ? listCandidates(data.candidates, data.color)[0] : null;
      const action = { type: kind, t_op: at, mode: data.mode, color: state.color };
      if (picked && positiveTick(picked.tick) && finiteVector(picked.est_xy, 2)
          && typeof picked.cand_id === 'string' && picked.cand_id.length <= 64) {
        Object.assign(action, { cand_id: picked.cand_id, tick: picked.tick, est_xy: [...picked.est_xy] });
      }
      onAction(action);
      return true;
    } catch (error) {
      if (revision !== ticket || state.session !== session) return false;
      const code = error.message;
      const message = TEXT_ERRORS[code] || '追蹤請求失敗，請重試。';
      if (code === 'SESSION_MISMATCH') {
        outdatedSession = session;
        dispatch({ type: 'DISCONNECT', message });
        syncState = true;
      } else {
        dispatch({ type: 'MESSAGE', message });
        refresh = ['CANDIDATE_STALE', 'CANDIDATE_UNKNOWN'].includes(code);
        syncState = code === 'TRACK_MODE_CONFLICT';
      }
      return false;
    } finally {
      if (operation === ticket) {
        operation = null;
        onChange(state, state, { type: 'SETTLED' });
        if (refresh && candidateRequest) await candidateRequest;
        if (refresh) await refreshCandidates();
        if (syncState && poll) await poll;
        if (syncState) await sync();
      }
    }
  }
  return {
    get state() { return state; },
    get busy() { return operation !== null; },
    sync, act,
    intent: (chip, sentence) => dispatch({ type: 'INTENT', chip, sentence }),
    frame(msg) {
      const accepted = dispatch({ type: 'FRAME', msg, session: state.session, adoptMode: !operation });
      if (accepted && state.mode === 'NEEDS_PICK' && state.candidateTick !== msg.tick) void refreshCandidates();
      return accepted;
    },
  };
}

export async function start(body) {
  if (new URLSearchParams(location.search).get('view') === 'grid') return (await import('./system_grid.mjs')).start(body);
  const geometry = await fetch('/data/geometry.json').then((r) => r.json());
  const cfg = await fetch('/config').then((r) => r.json()).catch(() => ({}));
  body.insertAdjacentHTML('beforeend', `<div id="bs"><button type="button" id="side-toggle" aria-expanded="true" aria-controls="bside" title="收合／展開系統面板">系統 ▸</button><div id="bmain">
    <div id="hud">
      <div class="cell"><h4>目前鏡頭・追蹤</h4><div class="v" id="h1v"></div><div class="s" id="h1s"></div></div>
      <div class="cell"><h4>決策來源</h4><div class="v" id="h2v"></div><div class="s" id="h2s"></div></div>
      <div class="cell"><h4>最近一次裁決</h4><div class="v" id="h3v"></div><div class="s" id="h3s"></div></div>
      <div class="cell"><h4>模式・模型</h4><div class="v" id="h4v"></div><div class="s" id="h4s"></div></div>
    </div>
    <details id="target-controls" open>
      <summary>選擇追蹤目標</summary>
      <form id="target-form">
        <div class="target-chips" role="group" aria-label="衣服顏色">
          <button type="button" data-target-color="red" aria-pressed="false">紅衣</button>
          <button type="button" data-target-color="blue" aria-pressed="false">藍衣</button>
        </div>
        <input type="text" id="target-sentence" maxlength="80" aria-label="追蹤句子" placeholder="例如：追蹤穿紅衣的人">
        <button type="submit" id="target-start">開始追蹤</button>
        <button type="button" id="target-reselect">改選目標</button>
        <button type="button" id="target-stop">停止追蹤</button>
        <span id="target-feedback" role="status" aria-live="polite"></span>
      </form>
    </details>
    <div id="stage"><canvas id="fcv"></canvas><div id="camname"></div><div id="banner"></div>
      <div id="same-color" role="status" hidden></div>
      <div id="center"><b id="cb"></b><span id="cs"></span><div id="lost-hint" hidden></div></div>
      <div id="candidate-frames" hidden></div></div>
    <div id="bar"></div></div>
    <div id="bside"><div id="side-resize" role="separator" aria-orientation="vertical" aria-label="拖拉調整系統面板寬度" tabindex="0"></div><b>系統</b> <span class="kv">（只看鏡頭像素）</span>
      <canvas id="map" width="320" height="288"></canvas>
      <ol id="target-candidates" aria-label="追蹤候選" hidden></ol>
      <button type="button" id="system-download">下載 B 記錄</button>
      <div id="llmset"><b>設定</b> <span class="kv">（預設關閉）</span>
        <label><input type="checkbox" id="llmon"> LLM 決策</label>
        <select id="llmmode"><option value="review">LLM 覆核</option><option value="lead">LLM 主導</option><option value="agent">Agent 決策</option></select>
        <select id="llmmodel"></select>
        <div id="llmstat" class="v"></div><div id="llmdet" class="s"></div></div>
      <div id="events"></div></div></div>`);
  const $ = (id) => document.getElementById(id);
  const stage = $('stage'), cv = $('fcv'), ctx = cv.getContext('2d');
  // #677 後台面板：可收合、可拖拉寬度，狀態存 localStorage（讀寫都包 try/catch，壞掉就用預設）。
  const prefs = loadPanelPrefs();
  const bs = $('bs');
  const applyPrefs = () => {
    bs.style.setProperty('--side-w', `${clampSideWidth(prefs.width, Math.floor(innerWidth * .6))}px`);
    bs.classList.toggle('side-collapsed', prefs.collapsed);
    $('side-toggle').setAttribute('aria-expanded', String(!prefs.collapsed));
    $('side-toggle').textContent = prefs.collapsed ? '◂ 系統' : '系統 ▸';
    window.dispatchEvent(new Event('resize'));
  };
  $('side-toggle').onclick = () => { prefs.collapsed = !prefs.collapsed; savePanelPrefs(prefs); applyPrefs(); };
  $('side-resize').addEventListener('pointerdown', event => {
    event.preventDefault();
    const move = e => { prefs.width = clampSideWidth(innerWidth - e.clientX, Math.floor(innerWidth * .6)); applyPrefs(); };
    const up = () => { removeEventListener('pointermove', move); removeEventListener('pointerup', up); savePanelPrefs(prefs); };
    addEventListener('pointermove', move); addEventListener('pointerup', up);
  });
  $('side-resize').addEventListener('keydown', event => {
    const step = event.key === 'ArrowLeft' ? 20 : event.key === 'ArrowRight' ? -20 : 0;
    if (!step) return;
    prefs.width = clampSideWidth(prefs.width + step, Math.floor(innerWidth * .6)); savePanelPrefs(prefs); applyPrefs();
  });
  addEventListener('resize', () => { if (!prefs.collapsed) bs.style.setProperty('--side-w', `${clampSideWidth(prefs.width, Math.floor(innerWidth * .6))}px`); });
  applyPrefs();
  let lastDets = {};
  const newLog = session_id => ({ schema_version: 'live-ab.b-log.v1', session_id,
    ticks: [], actions: [], hud_latency: [], displays: [], violations: [] });
  let log = newLog(null);
  window.__log = log;
  const st = createHudState();
  window.__hud = { st, cfg, view: null };
  window.__hud.setDets = d => { lastDets = d || {}; drawMap(st.tr, controller.state.candidates, ghostCandidates()); };   // screenshot/test hook: replaces the detections the hints read (display only)

  // map (same drawing as the grid view, smaller)
  const mapCv = $('map'), mctx = mapCv.getContext('2d');
  const xs = geometry.floors.flatMap((f) => f.x_m), ys = geometry.floors.flatMap((f) => f.y_m);
  const minX = Math.min(...xs) - 1, maxX = Math.max(...xs) + 1, minY = Math.min(...ys) - 1, maxY = Math.max(...ys) + 1;
  const sc = Math.min(320 / (maxX - minX), 288 / (maxY - minY));
  const mx = (x) => (x - minX) * sc, my = (y) => 288 - (y - minY) * sc;
  const trail = [];
  let mapHits = [];
  function drawMap(tr, candidates = [], ghosts = []) {
    mctx.clearRect(0, 0, 320, 288);
    mctx.fillStyle = '#2a303a';
    for (const f of geometry.floors) mctx.fillRect(mx(f.x_m[0]), my(f.y_m[1]), (f.x_m[1] - f.x_m[0]) * sc, (f.y_m[1] - f.y_m[0]) * sc);
    mctx.strokeStyle = '#6b7482'; mctx.beginPath();
    for (const s of geometry.clearance_segments) { mctx.moveTo(mx(s.a[0]), my(s.a[1])); mctx.lineTo(mx(s.b[0]), my(s.b[1])); }
    mctx.stroke();
    for (const c of geometry.cameras) {
      const p = c.camera_to_world;
      mctx.fillStyle = tr && tr.active_cam === c.camera_id ? '#f5a623' : '#8b93a0';
      mctx.fillRect(mx(p[0][3]) - 3, my(p[1][3]) - 3, 6, 6);
      mctx.fillStyle = '#8b93a0'; mctx.font = '9px sans-serif'; mctx.fillText(c.camera_id.replace('CAM_', ''), mx(p[0][3]) + 5, my(p[1][3]) - 4);
    }
    if (tr?.est_xy && trail.length) {
      mctx.strokeStyle = '#e5484d'; mctx.beginPath();
      trail.forEach((p, i) => (i ? mctx.lineTo(mx(p[0]), my(p[1])) : mctx.moveTo(mx(p[0]), my(p[1])))); mctx.stroke();
      mctx.fillStyle = (tr.lost_ticks || 0) > 0 ? '#8b93a0' : '#e5484d'; mctx.beginPath(); mctx.arc(mx(tr.est_xy[0]), my(tr.est_xy[1]), 5, 0, 7); mctx.fill();
    }
    for (const g of ghosts) {   // 失聯時的候選：空心圈，不可點（改選請用「改選目標」）
      mctx.strokeStyle = g.same ? '#ffd370' : '#8b93a0'; mctx.lineWidth = 2; mctx.beginPath();
      mctx.arc(mx(g.est_xy[0]), my(g.est_xy[1]), 8, 0, 2 * Math.PI); mctx.stroke();
    }
    mctx.lineWidth = 1;
    mapHits = candidates.map(candidate => {
      const x = mx(candidate.est_xy[0]), y = my(candidate.est_xy[1]);
      mctx.fillStyle = '#ffd370'; mctx.beginPath(); mctx.arc(x, y, 10, 0, 2 * Math.PI); mctx.fill();
      mctx.fillStyle = '#171a20'; mctx.font = 'bold 11px sans-serif';
      mctx.textAlign = 'center'; mctx.fillText(String(candidate.number), x, y + 4); mctx.textAlign = 'start';
      return { x, y, candidate };
    });
  }
  drawMap(null);

  const events = [];
  let viewRevision = 0, candidateRevision = 0, candidateKey = null;
  function resetFollow() {
    viewRevision++;
    trail.length = 0;
    ctx.clearRect(0, 0, cv.width, cv.height);
    // Latency is scoped to the session and stays continuous across target changes.
    Object.assign(st, createHudState(), { delays: st.delays, medianMs: st.medianMs });
  }
  const controller = createBController({
    onChange(state, previous, event) {
      if (state.session !== previous.session) {
        window.__log = log = newLog(state.session);
        events.length = 0;
        $('events').textContent = '';
        resetFollow();
        Object.assign(st, createHudState());
      } else if ((event.type === 'APPLIED' && event.kind !== 'reselect')
          || (state.mode === 'IDLE' && previous.mode !== 'IDLE')) {
        resetFollow();
      }
      if (event.type !== 'FRAME') {
        render();
        renderCandidates();
        drawMap(st.tr, state.candidates, ghostCandidates());
      }
    },
    onAction(action) { log.actions.push(action); },
  });
  const ghostCandidates = () => {
    const h = lostHint(st.tr, lastDets, cfg);
    return h ? h.candidates.map(c => ({ est_xy: c.est_xy, same: c.color === h.color })) : [];
  };
  const setCell = (id, text, sub, tone) => {
    const v = $(id + 'v'); v.textContent = text; v.className = `v tone-${tone || 'rule'}`; $(id + 's').textContent = sub || '';
  };
  const sentence = $('target-sentence');
  const chips = [...document.querySelectorAll('[data-target-color]')];
  for (const chip of chips) chip.addEventListener('click', () => {
    const color = chip.dataset.targetColor;
    controller.intent(controller.state.chip === color ? null : color, sentence.value);
  });
  sentence.addEventListener('input', () => controller.intent(controller.state.chip, sentence.value));
  $('target-form').addEventListener('submit', event => { event.preventDefault(); void controller.act('start'); });
  $('target-reselect').onclick = () => controller.act('reselect');
  $('target-stop').onclick = () => controller.act('stop');
  $('system-download').onclick = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(log, null, 2)], { type: 'application/json' }));
    const link = Object.assign(document.createElement('a'), { href: url, download: `live-ab-b-${log.session_id}.json` });
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  function canvasPoint(canvas, event) {
    const rect = canvas.getBoundingClientRect();
    return [(event.clientX - rect.left) * canvas.width / rect.width,
      (event.clientY - rect.top) * canvas.height / rect.height];
  }
  mapCv.onclick = event => {
    const [x, y] = canvasPoint(mapCv, event);
    const hit = mapHits.map(item => ({ ...item, distance: Math.hypot(item.x - x, item.y - y) }))
      .sort((a, b) => a.distance - b.distance)[0];
    if (hit?.distance <= 11) void controller.act('pick', hit.candidate);
  };
  function renderCandidates() {
    const { session, candidates, frames } = controller.state;
    const displayed = candidates.map(candidate => [candidate, candidateFrame(frames, candidate)]);
    const key = JSON.stringify([session, controller.busy, displayed.map(([candidate, frame]) => [candidate.cand_id, !!frame])]);
    if (key === candidateKey) return;
    candidateKey = key;
    const revision = ++candidateRevision;
    const list = $('target-candidates'), pane = $('candidate-frames');
    list.hidden = !candidates.length;
    list.replaceChildren(...candidates.map(candidate => {
      const li = document.createElement('li'), button = document.createElement('button');
      button.type = 'button';
      button.disabled = controller.busy;
      button.textContent = `${candidate.number}・${candidate.cam}・${candidate.est_xy.map(value => value.toFixed(1)).join(', ')} m`;
      button.onclick = () => controller.act('pick', candidate);
      li.append(button);
      return li;
    }));
    pane.replaceChildren();
    pane.hidden = true;
    const byFrame = new Map();
    for (const [candidate, frame] of displayed) {
      if (!frame) continue;
      if (!byFrame.has(frame)) byFrame.set(frame, []);
      byFrame.get(frame).push(candidate);
    }
    void Promise.all([...byFrame].map(async ([frame, boxes]) => {
      const figure = document.createElement('figure'), caption = document.createElement('figcaption');
      const canvas = document.createElement('canvas');
      try {
        const image = await createImageBitmap(new Blob([frame.jpeg], { type: 'image/jpeg' }));
        canvas.width = image.width;
        canvas.height = image.height;
        const overlay = canvas.getContext('2d');
        overlay.drawImage(image, 0, 0);
        image.close();
        for (const { bbox: [x0, y0, x1, y1], number } of boxes) {
          overlay.lineWidth = 2;
          overlay.strokeStyle = '#ffd370';
          overlay.strokeRect(x0, y0, x1 - x0, y1 - y0);
          overlay.fillStyle = '#ffd370';
          overlay.fillRect(x0, y0, 20, 18);
          overlay.fillStyle = '#171a20';
          overlay.font = 'bold 13px sans-serif';
          overlay.fillText(String(number), x0 + 4, y0 + 14);
        }
      } catch {
        return null;
      }
      caption.textContent = frame.cam;
      canvas.dataset.candidateCam = frame.cam;
      canvas.onclick = event => {
        const [x, y] = canvasPoint(canvas, event);
        const hit = boxes.find(({ bbox: [x0, y0, x1, y1] }) => x >= x0 && x <= x1 && y >= y0 && y <= y1);
        if (hit) void controller.act('pick', hit);
      };
      figure.append(canvas, caption);
      return figure;
    })).then(tiles => {
      if (candidateRevision !== revision) return;
      const visible = tiles.filter(Boolean);
      pane.replaceChildren(...visible);
      pane.hidden = !visible.length;
    });
  }
  function render() {
    const t = now();
    const state = controller.state;
    const waitingForFrame = !st.tr || st.tr.target?.color !== state.color;
    const through = state.session && (state.mode === 'IDLE' || state.mode === 'ACQUIRING'
      || (state.mode === 'NEEDS_PICK' && !state.reselecting) || waitingForFrame);
    const shown = through ? { ...st, tr: {
      state: state.mode === 'ACQUIRING' || state.mode === 'TRACKING' ? 'SEARCHING' : state.mode,
      target: { color: state.color, mode: state.mode },
    }, switchInfo: null, pending: null, decision: null } : st;
    const v = hudView(shown, t, cfg, state.candidates.length);
    window.__hud.view = v;
    setCell('h1', v.cam ? `${v.cam.replace('CAM_', '')}・${v.track.text}` : v.track.text,
      [v.target, v.cam].filter(Boolean).join(' · '), v.track.kind);
    if (sentence.value !== state.sentence) sentence.value = state.sentence;
    for (const chip of chips) chip.setAttribute('aria-pressed', String(chip.dataset.targetColor === state.chip));
    const unavailable = !state.session || controller.busy;
    $('target-start').disabled = unavailable;
    $('target-reselect').disabled = unavailable || state.mode !== 'TRACKING';
    $('target-stop').disabled = unavailable || state.mode === 'IDLE';
    $('system-download').disabled = !state.session;
    mapCv.style.cursor = state.candidates.length ? 'pointer' : '';
    $('target-feedback').textContent = [
      state.mode === 'ACQUIRING' ? '畫面中沒有符合的人' : '',
      state.mode === 'NEEDS_PICK' && state.reselecting ? `改選目標（${state.candidates.length} 位）` : '',
      state.message,
    ].filter(Boolean).join('。');
    setCell('h2', v.source.label, v.source.reason ? `原因：${v.source.reason}` : '', v.source.tone);
    const d = v.decision;
    if (d) {
      setCell('h3', `${d.candidates == null ? '?' : d.candidates} 人 → ${d.pick}`, `${d.reason ? `「${d.reason}」` : ''}${d.latencyMs} ms・${d.outcome}`,
        d.applied ? 'llm' : d.fallback ? 'fallback' : 'rule');
    } else setCell('h3', '尚無裁決', '', 'searching');
    setCell('h4', v.mode.text, v.mode.model || hudModeNote(cfg) || (v.mode.mode === 'off' ? '後台沒有開 advisor' : ''), v.mode.mode === 'off' ? 'rule' : 'llm');
    stage.className = v.track.kind === 'tracking' ? '' : v.track.kind;
    $('camname').textContent = v.cam || '';
    $('camname').style.display = v.cam ? '' : 'none';
    const bn = $('banner');
    if (v.switch) { bn.style.display = 'block'; bn.textContent = `切鏡 ${v.switch.from.replace('CAM_', '')} → ${v.switch.to.replace('CAM_', '')}（${v.switch.by}）`; }
    else bn.style.display = 'none';
    const c = $('center'), kind = v.track.kind;
    if (kind === 'lost' || kind === 'brief' || kind === 'searching' || kind === 'adjudicating') {
      c.style.display = 'flex';
      $('cb').textContent = v.track.text;
      $('cb').style.color = kind === 'lost' ? '#e5484d' : kind === 'searching' ? 'var(--muted)' : 'var(--accent)';
      $('cs').textContent = kind === 'adjudicating' ? '畫面停在原鏡頭，等 LLM 回答' : kind === 'searching' ? '' : `最後鎖定的鏡頭：${v.cam}`;
    } else c.style.display = 'none';
    const hint = lostHint(shown.tr, lastDets, cfg), hintBox = $('lost-hint');
    hintBox.hidden = !hint;
    if (hint) {
      const lines = hint.candidates.length ? hint.candidates.map(c => `候選 ${c.number}（${c.color}）：${c.reason}`) : [`原因：${hint.reason}`];
      const key = lines.join('\n');
      if (hintBox.dataset.key !== key) { hintBox.dataset.key = key; hintBox.replaceChildren(...lines.map(l => Object.assign(document.createElement('div'), { textContent: l }))); }
    }
    const n = sameColorCount(lastDets, state.color), notice = state.session && (state.mode === 'TRACKING') ? sameColorNotice(n) : '';
    const sc = $('same-color');
    sc.hidden = !notice;
    if (notice && sc.dataset.n !== String(n)) {
      sc.dataset.n = String(n); sc.replaceChildren(document.createTextNode(notice + ' '));
      const b = document.createElement('button'); b.type = 'button'; b.textContent = '改選目標'; b.onclick = () => controller.act('reselect'); sc.append(b);
    } else if (!notice) delete sc.dataset.n;
    const bar = $('bar');
    bar.textContent = v.status.text;
    bar.className = `tone-${v.status.tone}`;
    if (v.latency) {
      const delay = document.createElement('span');
      delay.className = `tone-${v.latency.tone}`;
      delay.textContent = ` · 目前延遲 ${(v.latency.ms / 1000).toFixed(2)} s`;
      bar.append(delay);
    }
  }
  // LLM 決策開關：只傳到後台的 /config；畫面一律以後台回報的實際狀態為準。
  const sync = (c) => {
    if (c !== cfg) { Object.keys(cfg).forEach((k) => delete cfg[k]); Object.assign(cfg, c); }
    const sv = switchView(cfg), models = (cfg.llm_switch && cfg.llm_switch.models) || [];
    $('llmon').checked = sv.checked; $('llmmode').value = sv.mode;
    const ms = $('llmmodel'); if (!ms.options.length) ms.innerHTML = models.map((m) => `<option>${m}</option>`).join('');
    // D237：關閉時預設選 terra6.1；開啟後以後台回報的實際模型為準。
    ms.value = defaultModel(models, sv.checked && !sv.fake ? (cfg.llm_switch && cfg.llm_switch.model) : null) || ms.value;
    $('llmmodel').disabled = $('llmmode').disabled = sv.fake;
    const stat = $('llmstat'); stat.textContent = sv.text; stat.className = `v tone-${sv.tone}`; $('llmdet').textContent = sv.detail;
  };
  const push = async () => {
    const body = buildRequest($('llmon').checked, $('llmmode').value, $('llmmodel').value);
    try {
      await fetch('/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      sync(await fetch('/config').then((r) => r.json()));
    } catch (e) { $('llmstat').textContent = 'LLM 決策：後台沒有回應'; $('llmstat').className = 'v tone-fallback'; }
  };
  ['llmon', 'llmmode', 'llmmodel'].forEach((id) => $(id).addEventListener('change', push));
  sync(cfg);
  setInterval(render, 100);
  render();

  const chan = new BroadcastChannel(CHANNEL);
  let busy = Promise.resolve();
  chan.onmessage = event => {
    const received = now(), session = controller.state.session;
    busy = busy.then(() => handle(event.data, received, session)).catch(() => {
      log.violations.push({ reason: 'FRAME_DISPLAY_FAILED' });
    });
  };
  async function handle(msg, received, session) {
    if (!session || session !== controller.state.session) return;
    const bad = validateSystemMessage(msg);
    if (bad.length) { log.violations.push({ tick: msg?.tick, bad }); return; }
    if (!controller.frame(msg)) return;
    const tr = msg.tracking;
    const state = controller.state;
    const revision = viewRevision;
    const stillCurrent = () => session === controller.state.session && revision === viewRevision;
    const medianMs = recordLatency(st, received, msg.t_capture_ms);
    function recordDisplay(displayed) {
      if (session !== controller.state.session) return;
      const receipt = { tick: msg.tick, t_capture: msg.t_capture_ms, t_resp: received,
        t_display: displayed ? now() : null };
      log.ticks.push({ ...receipt, tracking: { state: tr.state, target: tr.target,
        active_cam: tr.active_cam, est_xy: tr.est_xy, lost_ticks: tr.lost_ticks, events: tr.events } });
      log.hud_latency.push({ tick: msg.tick, t_resp: received, median_ms: medianMs });
      if (displayed) log.displays.push({
        ...receipt, active: tr.active_cam, state: tr.state, seen: tr.seen_cams, events: tr.events,
      });
    }
    const isCurrent = msg.t_capture_ms >= state.applyAt && tr.target?.mode === state.mode && tr.target?.color === state.color;
    const prevCam = st.cam;
    if (isCurrent) { reduce(st, msg, received); lastDets = msg.dets || {}; }
    const showTrack = isCurrent && (state.mode === 'TRACKING' || state.reselecting);
    const f = showTrack && tr.active_cam && msg.frames.find(x => x.cam === tr.active_cam);
    if (f) {
      let bmp;
      try { bmp = await createImageBitmap(new Blob([f.jpeg], { type: 'image/jpeg' })); }
      catch (error) { recordDisplay(false); throw error; }
      if (!stillCurrent()) { bmp.close(); recordDisplay(false); return; }
      if (cv.width !== bmp.width || cv.height !== bmp.height) { cv.width = bmp.width; cv.height = bmp.height; }
      ctx.drawImage(bmp, 0, 0);
      const dets = msg.dets[tr.active_cam] || [];
      const ti = pickTarget(dets, tr);
      dets.forEach((d, i) => {
        const [x0, y0, x1, y1] = d.bbox;
        const isT = i === ti;
        ctx.lineWidth = Math.max(1.5, bmp.width / (isT ? 160 : 320));
        ctx.strokeStyle = isT ? '#f5a623' : d.color === 'red' ? '#e5484d' : d.color === 'blue' ? '#3b82f6' : '#cfd6e0';
        ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
        if (isT) {
          ctx.font = `600 ${Math.max(11, Math.round(bmp.width / 50))}px sans-serif`; ctx.fillStyle = '#f5a623';
          const ly = Math.max(12, y0 - 4); ctx.lineWidth = 3; ctx.strokeStyle = '#000'; ctx.strokeText('目標', x0, ly); ctx.fillText('目標', x0, ly);
        }
      });
      if (prevCam && prevCam !== tr.active_cam) { cv.classList.remove('fade'); void cv.offsetWidth; cv.classList.add('fade'); }
      bmp.close();
    }
    else if (isCurrent) ctx.clearRect(0, 0, cv.width, cv.height);
    if (!stillCurrent()) { recordDisplay(false); return; }
    if (showTrack && tr.est_xy) {
      trail.push(tr.est_xy);
      if (trail.length > 60) trail.shift();
    }
    renderCandidates();
    drawMap(st.tr, controller.state.candidates, ghostCandidates());
    if (isCurrent) {
      for (const e of tr.events || []) events.unshift(`#${e.tick} ${TYPE_ZH[e.type] || e.type} ${e.cam || ''}`);
    }
    $('events').textContent = events.slice(0, 40).join('\n'); $('events').style.whiteSpace = 'pre';
    render();
    recordDisplay(isCurrent);
  }
  void controller.sync();
  setInterval(controller.sync, 1000);
  window.__ready = true;
}
