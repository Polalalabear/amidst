// Screen 2 (system), debug grid view: 8 camera tiles, detection boxes, map, event timeline (?role=system&view=grid).
// The default system view is the follow view (system.mjs + hud.mjs).
// Receives only camera JPEGs and backend results via BroadcastChannel; every message is validated
// against the whitelist so an operator id or coordinate would be rejected.
import { CHANNEL, now } from './common.mjs';
import { validateSystemMessage } from './protocol.mjs';

export async function start(body) {
  const geometry = await fetch('/data/geometry.json').then((r) => r.json());
  body.insertAdjacentHTML('beforeend', `<div id="sys"><div class="tiles" id="tiles"></div><div id="side">
    <b>System</b> <span class="kv">(sees camera pixels only)</span>
    <canvas id="map" width="400" height="360"></canvas>
    <div id="status" class="kv"></div><div id="events"></div></div></div>`);
  const tiles = {};
  const tilesEl = document.getElementById('tiles');
  for (const c of geometry.cameras) {
    const d = document.createElement('div'); d.className = 'tile';
    d.innerHTML = `<span>${c.camera_id}</span><canvas></canvas>`;
    tilesEl.appendChild(d); tiles[c.camera_id] = { el: d, cv: d.querySelector('canvas') };
  }
  const log = { displays: [], violations: [] };
  window.__log = log;
  const mapCv = document.getElementById('map'), mctx = mapCv.getContext('2d');
  const xs = geometry.floors.flatMap((f) => f.x_m), ys = geometry.floors.flatMap((f) => f.y_m);
  const minX = Math.min(...xs) - 1, maxX = Math.max(...xs) + 1, minY = Math.min(...ys) - 1, maxY = Math.max(...ys) + 1;
  const sc = Math.min(400 / (maxX - minX), 360 / (maxY - minY));
  const mx = (x) => (x - minX) * sc, my = (y) => 360 - (y - minY) * sc;
  const trail = [];
  const events = [];
  function drawMap(tr) {
    mctx.clearRect(0, 0, 400, 360);
    mctx.fillStyle = '#2a303a';
    for (const f of geometry.floors) mctx.fillRect(mx(f.x_m[0]), my(f.y_m[1]), (f.x_m[1] - f.x_m[0]) * sc, (f.y_m[1] - f.y_m[0]) * sc);
    mctx.strokeStyle = '#6b7482'; mctx.beginPath();
    for (const s of geometry.clearance_segments) { mctx.moveTo(mx(s.a[0]), my(s.a[1])); mctx.lineTo(mx(s.b[0]), my(s.b[1])); }
    mctx.stroke();
    for (const c of geometry.cameras) {
      const p = c.camera_to_world; const x = p[0][3], y = p[1][3];
      mctx.fillStyle = tr && tr.active_cam === c.camera_id ? '#f5a623' : (tr && tr.seen_cams.includes(c.camera_id) ? '#4cc38a' : '#8b93a0');
      mctx.fillRect(mx(x) - 3, my(y) - 3, 6, 6);
      mctx.fillStyle = '#8b93a0'; mctx.font = '9px sans-serif'; mctx.fillText(c.camera_id.replace('CAM_', ''), mx(x) + 5, my(y) - 4);
    }
    if (tr && tr.est_xy) {
      trail.push(tr.est_xy); if (trail.length > 60) trail.shift();
      mctx.strokeStyle = '#e5484d'; mctx.beginPath();
      trail.forEach((p, i) => (i ? mctx.lineTo(mx(p[0]), my(p[1])) : mctx.moveTo(mx(p[0]), my(p[1])))); mctx.stroke();
      mctx.fillStyle = '#e5484d'; mctx.beginPath(); mctx.arc(mx(tr.est_xy[0]), my(tr.est_xy[1]), 5, 0, 7); mctx.fill();
    }
  }
  drawMap(null);
  const chan = new BroadcastChannel(CHANNEL);
  chan.onmessage = async (ev) => {
    const msg = ev.data;
    const bad = validateSystemMessage(msg);
    if (bad.length) { log.violations.push({ tick: msg.tick, bad }); return; }
    for (const f of msg.frames) {
      const t = tiles[f.cam]; if (!t) continue;
      const bmp = await createImageBitmap(new Blob([f.jpeg], { type: 'image/jpeg' }));
      t.cv.width = bmp.width; t.cv.height = bmp.height;
      const ctx = t.cv.getContext('2d'); ctx.drawImage(bmp, 0, 0);
      for (const d of msg.dets[f.cam] || []) {
        const [x0, y0, x1, y1] = d.bbox;
        ctx.strokeStyle = d.color === 'red' ? '#e5484d' : d.color === 'blue' ? '#3b82f6' : '#cfd6e0';
        ctx.lineWidth = Math.max(1, bmp.width / 320); ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
      }
      t.el.classList.toggle('active', msg.tracking.active_cam === f.cam);
    }
    const tr = msg.tracking;
    drawMap(tr);
    for (const e of tr.events || []) events.unshift(`#${e.tick} ${e.type} ${e.cam || ''}`);
    document.getElementById('events').textContent = events.slice(0, 40).join('\n');
    document.getElementById('events').style.whiteSpace = 'pre';
    document.getElementById('status').textContent = `state ${tr.state} · active ${tr.active_cam} · tick ${msg.tick}`;
    const tDisplay = now();
    log.displays.push({ tick: msg.tick, t_capture: msg.t_capture_ms, t_display: tDisplay, active: tr.active_cam, state: tr.state,
      seen: tr.seen_cams, events: tr.events });
  };
  window.__ready = true;
}
