// B 畫面（系統端）：單一跟隨視角＋HUD。
// 主區域只顯示後台判定的作用中鏡頭；切鏡有提示；失聯時有狀態和計時。HUD 的每個欄位都來自後台經
// protocol.mjs 白名單送出的訊息（validateSystemMessage 不過的訊息整則丟掉）和 /config（後台啟動參數）。
// 看不到也收不到操作者的座標、角色代號或 GT。8 鏡頭除錯格狀版：?role=system&view=grid。
import { CHANNEL, now } from './common.mjs';
import { validateSystemMessage } from './protocol.mjs';
import { switchView, buildRequest, hudModeNote } from './llm_switch.mjs';
import { createHudState, reduce, view as hudView, pickTarget } from './hud.mjs';

const TYPE_ZH = { ACQUIRE: '鎖定目標', SWITCH: '切鏡', TARGET_OUT_OF_VIEW: '目標離開視野', LOST: '失聯', REACQUIRE: '重新找到',
  ADJUDICATE_ASK: '問 LLM', ADJUDICATED: 'LLM 回答' };

export async function start(body) {
  if (new URLSearchParams(location.search).get('view') === 'grid') return (await import('./system_grid.mjs')).start(body);
  const geometry = await fetch('/data/geometry.json').then((r) => r.json());
  const cfg = await fetch('/config').then((r) => r.json()).catch(() => ({}));
  body.insertAdjacentHTML('beforeend', `<div id="bs"><div id="bmain">
    <div id="hud">
      <div class="cell"><h4>目前鏡頭・追蹤</h4><div class="v" id="h1v"></div><div class="s" id="h1s"></div></div>
      <div class="cell"><h4>決策來源</h4><div class="v" id="h2v"></div><div class="s" id="h2s"></div></div>
      <div class="cell"><h4>最近一次裁決</h4><div class="v" id="h3v"></div><div class="s" id="h3s"></div></div>
      <div class="cell"><h4>模式・模型</h4><div class="v" id="h4v"></div><div class="s" id="h4s"></div></div>
    </div>
    <div id="stage"><canvas id="fcv"></canvas><div id="camname"></div><div id="banner"></div>
      <div id="center"><b id="cb"></b><span id="cs"></span></div></div>
    <div id="bar"></div></div>
    <div id="bside"><b>系統</b> <span class="kv">（只看鏡頭像素）</span><canvas id="map" width="320" height="288" style="width:320px;height:288px"></canvas>
      <div id="llmset"><b>設定</b> <span class="kv">（預設關閉）</span>
        <label><input type="checkbox" id="llmon"> LLM 決策</label>
        <select id="llmmode"><option value="review">LLM 覆核</option><option value="lead">LLM 主導</option></select>
        <select id="llmmodel"></select>
        <div id="llmstat" class="v"></div><div id="llmdet" class="s"></div></div>
      <div id="events"></div></div></div>`);
  const $ = (id) => document.getElementById(id);
  const stage = $('stage'), cv = $('fcv'), ctx = cv.getContext('2d');
  const log = { displays: [], violations: [] };
  window.__log = log;
  const st = createHudState();
  window.__hud = { st, cfg, view: null };

  // map (same drawing as the grid view, smaller)
  const mapCv = $('map'), mctx = mapCv.getContext('2d');
  const xs = geometry.floors.flatMap((f) => f.x_m), ys = geometry.floors.flatMap((f) => f.y_m);
  const minX = Math.min(...xs) - 1, maxX = Math.max(...xs) + 1, minY = Math.min(...ys) - 1, maxY = Math.max(...ys) + 1;
  const sc = Math.min(320 / (maxX - minX), 288 / (maxY - minY));
  const mx = (x) => (x - minX) * sc, my = (y) => 288 - (y - minY) * sc;
  const trail = [];
  function drawMap(tr) {
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
    if (tr && tr.est_xy) {
      trail.push(tr.est_xy); if (trail.length > 60) trail.shift();
      mctx.strokeStyle = '#e5484d'; mctx.beginPath();
      trail.forEach((p, i) => (i ? mctx.lineTo(mx(p[0]), my(p[1])) : mctx.moveTo(mx(p[0]), my(p[1])))); mctx.stroke();
      mctx.fillStyle = (tr.lost_ticks || 0) > 0 ? '#8b93a0' : '#e5484d'; mctx.beginPath(); mctx.arc(mx(tr.est_xy[0]), my(tr.est_xy[1]), 5, 0, 7); mctx.fill();
    }
  }
  drawMap(null);

  const events = [];
  const setCell = (id, text, sub, tone) => {
    const v = $(id + 'v'); v.textContent = text; v.className = `v tone-${tone || 'rule'}`; $(id + 's').textContent = sub || '';
  };
  function render() {
    const t = now();
    const v = hudView(st, t, cfg);
    window.__hud.view = v;
    setCell('h1', v.cam ? `${v.cam.replace('CAM_', '')}・${v.track.text}` : v.track.text, v.cam ? v.cam : '', v.track.kind);
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
      $('cb').textContent = kind === 'searching' ? v.track.text : v.track.text;
      $('cb').style.color = kind === 'lost' ? '#e5484d' : kind === 'searching' ? '#aab2bf' : '#f5a623';
      $('cs').textContent = kind === 'adjudicating' ? '畫面停在原鏡頭，等 LLM 回答' : kind === 'searching' ? '等候後台判定' : `最後鎖定的鏡頭：${v.cam}`;
    } else c.style.display = 'none';
    const bar = $('bar'); bar.textContent = v.status.text; bar.className = `tone-${v.status.tone}`;
  }
  // LLM 決策開關：只傳到後台的 /config；畫面一律以後台回報的實際狀態為準。
  const sync = (c) => {
    if (c !== cfg) { Object.keys(cfg).forEach((k) => delete cfg[k]); Object.assign(cfg, c); }
    const sv = switchView(cfg), models = (cfg.llm_switch && cfg.llm_switch.models) || [];
    $('llmon').checked = sv.checked; $('llmmode').value = sv.mode;
    const ms = $('llmmodel'); if (!ms.options.length) ms.innerHTML = models.map((m) => `<option>${m}</option>`).join('');
    if (cfg.llm_switch && cfg.llm_switch.model) ms.value = cfg.llm_switch.model;
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
  chan.onmessage = (ev) => { busy = busy.then(() => handle(ev.data)); };
  async function handle(msg) {
    const bad = validateSystemMessage(msg);
    if (bad.length) { log.violations.push({ tick: msg.tick, bad }); return; }
    const tr = msg.tracking;
    const t = now();
    const prevCam = st.cam;
    reduce(st, msg, t);
    // 只畫作用中鏡頭；沒有作用中鏡頭（還沒鎖定）時畫面維持空白
    const f = tr.active_cam && msg.frames.find((x) => x.cam === tr.active_cam);
    if (f) {
      const bmp = await createImageBitmap(new Blob([f.jpeg], { type: 'image/jpeg' }));
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
    }
    else ctx.clearRect(0, 0, cv.width, cv.height);   // no frame for the active camera: do not keep showing another camera
    drawMap(tr);
    for (const e of tr.events || []) events.unshift(`#${e.tick} ${TYPE_ZH[e.type] || e.type} ${e.cam || ''}`);
    $('events').textContent = events.slice(0, 40).join('\n'); $('events').style.whiteSpace = 'pre';
    render();
    log.displays.push({ tick: msg.tick, t_capture: msg.t_capture_ms, t_display: now(), active: tr.active_cam, state: tr.state,
      seen: tr.seen_cams, events: tr.events });
  }
  window.__ready = true;
}
