// Live-mode game design v1 mockups: shared drawing helpers (design only, not runtime code).
// Assets: camera stills from N6 (#539) are LOCAL; pass ?assets=<dir> (defaults to the repo-root
// local/ path). Missing images fall back to a flat placeholder so the page still renders.
(function () {
  const q = new URLSearchParams(location.search);
  const ASSETS = q.get('assets') || '../../../../local/data/live-assets-20261115/verification';
  window.camImg = (id) => `${ASSETS}/${id}.png`;
  window.imgFallback = (el) => { el.onerror = null; el.style.display = 'none'; el.parentElement.classList.add('noimg'); };

  // Person silhouette (stand-in for the N6 rig). view: 'back' | 'front'. Returns SVG markup.
  window.personSVG = function (top, w, h, view, stride = 0.6) {
    const skin = '#c9b8a6', pants = '#3a3f4a', shoe = '#22252b';
    const s = stride; // 0 idle .. 1 full stride
    const legL = `rotate(${-18 * s} 50 118)`, legR = `rotate(${18 * s} 50 118)`;
    const armL = `rotate(${16 * s} 50 58)`, armR = `rotate(${-16 * s} 50 58)`;
    return `<svg viewBox="0 0 100 230" width="${w}" height="${h}" xmlns="http://www.w3.org/2000/svg">
      <ellipse cx="50" cy="224" rx="30" ry="6" fill="rgba(0,0,0,.28)"/>
      <g transform="${legL}"><rect x="34" y="112" width="15" height="100" rx="7" fill="${pants}"/><ellipse cx="41" cy="214" rx="10" ry="6" fill="${shoe}"/></g>
      <g transform="${legR}"><rect x="51" y="112" width="15" height="100" rx="7" fill="${pants}"/><ellipse cx="59" cy="214" rx="10" ry="6" fill="${shoe}"/></g>
      <g transform="${armL}"><rect x="18" y="54" width="12" height="62" rx="6" fill="${top}"/><circle cx="24" cy="118" r="6" fill="${skin}"/></g>
      <g transform="${armR}"><rect x="70" y="54" width="12" height="62" rx="6" fill="${top}"/><circle cx="76" cy="118" r="6" fill="${skin}"/></g>
      <rect x="28" y="48" width="44" height="72" rx="14" fill="${top}"/>
      ${view === 'back' ? `<rect x="34" y="58" width="32" height="40" rx="6" fill="#39424d"/>` : `<rect x="56" y="62" width="9" height="11" fill="#e8e2d4"/>`}
      <rect x="44" y="36" width="12" height="14" rx="5" fill="${skin}"/>
      <circle cx="50" cy="24" r="16" fill="${skin}"/>
    </svg>`;
  };

  // Minimap on a canvas. opts:
  //  center:[x,y] world m; ppm px per metre; rotateDeg (heading-up = 90 - heading); size [w,h]
  //  cams: { id: 'active'|'neighbor'|'idle'|'seen' }  wedgeLen m
  //  player:{x,y,headingDeg} (operator only)  est:{x,y,sigma} (system only)  trail:[[x,y]...]
  window.drawMinimap = function (cv, o) {
    const S = window.SCENE, ctx = cv.getContext('2d');
    const [W, H] = [cv.width, cv.height];
    ctx.save();
    ctx.clearRect(0, 0, W, H);
    ctx.translate(W / 2, H / 2);
    ctx.rotate((o.rotateDeg || 0) * Math.PI / 180);
    const T = (x, y) => [(x - o.center[0]) * o.ppm, -(y - o.center[1]) * o.ppm];
    // floors
    ctx.fillStyle = o.floor || '#2b313b';
    for (const f of S.floors) {
      const [x0, y0] = T(f.x[0], f.y[1]); const [x1, y1] = T(f.x[1], f.y[0]);
      ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
    }
    // FOV wedges
    const wl = o.wedgeLen || 9;
    for (const c of S.cameras) {
      const st = (o.cams || {})[c.id] || 'idle';
      const col = { active: 'rgba(245,166,35,.34)', neighbor: 'rgba(56,189,248,.20)', seen: 'rgba(74,222,128,.22)', idle: 'rgba(160,170,185,.08)' }[st];
      const a0 = (c.yaw_deg - c.hfov_deg / 2) * Math.PI / 180, a1 = (c.yaw_deg + c.hfov_deg / 2) * Math.PI / 180;
      ctx.beginPath(); ctx.moveTo(...T(c.x, c.y));
      for (let k = 0; k <= 16; k++) { const a = a0 + (a1 - a0) * k / 16; ctx.lineTo(...T(c.x + wl * Math.cos(a), c.y + wl * Math.sin(a))); }
      ctx.closePath(); ctx.fillStyle = col; ctx.fill();
      if (st === 'active') { ctx.strokeStyle = 'rgba(245,166,35,.8)'; ctx.lineWidth = 1.5; ctx.stroke(); }
    }
    // walls
    ctx.strokeStyle = o.wall || '#c9d1dc'; ctx.lineWidth = o.wallW || 1.6; ctx.lineCap = 'round';
    ctx.beginPath();
    for (const [ax, ay, bx, by] of S.walls) { ctx.moveTo(...T(ax, ay)); ctx.lineTo(...T(bx, by)); }
    ctx.stroke();
    ctx.strokeStyle = '#6b7482'; ctx.lineWidth = 1; ctx.beginPath();
    for (const [ax, ay, bx, by] of S.vehicle) { ctx.moveTo(...T(ax, ay)); ctx.lineTo(...T(bx, by)); }
    ctx.stroke();
    // trail
    if (o.trail && o.trail.length) {
      ctx.strokeStyle = o.trailColor || 'rgba(229,72,77,.7)'; ctx.setLineDash([4, 4]); ctx.lineWidth = 2;
      ctx.beginPath(); o.trail.forEach((p, i) => (i ? ctx.lineTo(...T(...p)) : ctx.moveTo(...T(...p)))); ctx.stroke(); ctx.setLineDash([]);
    }
    // camera icons
    for (const c of S.cameras) {
      const st = (o.cams || {})[c.id] || 'idle';
      const [px, py] = T(c.x, c.y);
      ctx.save(); ctx.translate(px, py); ctx.rotate(-c.yaw_deg * Math.PI / 180);
      ctx.fillStyle = { active: '#f5a623', neighbor: '#38bdf8', seen: '#4ade80', idle: '#8b93a0' }[st];
      ctx.fillRect(-6, -4.5, 10, 9); ctx.beginPath(); ctx.moveTo(4, -2.5); ctx.lineTo(9, -5); ctx.lineTo(9, 5); ctx.lineTo(4, 2.5); ctx.fill();
      ctx.restore();
      if (o.labels !== false) {
        ctx.save(); ctx.translate(px, py); ctx.rotate(-(o.rotateDeg || 0) * Math.PI / 180);
        ctx.font = `600 ${o.labelSize || 11}px -apple-system, "PingFang TC", sans-serif`;
        ctx.fillStyle = st === 'idle' ? '#9aa3b0' : '#eef2f7'; ctx.textAlign = 'left';
        ctx.fillText(c.id.replace('CAM_', ''), 9, -7); ctx.restore();
      }
    }
    // system estimate (system side only)
    if (o.est) {
      const [px, py] = T(o.est.x, o.est.y);
      ctx.fillStyle = 'rgba(229,72,77,.18)'; ctx.strokeStyle = 'rgba(229,72,77,.7)'; ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.arc(px, py, o.est.sigma * o.ppm, 0, 7); ctx.fill(); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = '#e5484d'; ctx.beginPath(); ctx.arc(px, py, 6, 0, 7); ctx.fill();
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke();
    }
    // operator player (operator side only)
    if (o.player) {
      const [px, py] = T(o.player.x, o.player.y);
      ctx.save(); ctx.translate(px, py); ctx.rotate(-o.player.headingDeg * Math.PI / 180);
      ctx.fillStyle = 'rgba(255,255,255,.16)';
      ctx.beginPath(); ctx.moveTo(0, 0); ctx.arc(0, 0, 34, -0.5, 0.5); ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#ffffff'; ctx.strokeStyle = '#111'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(13, 0); ctx.lineTo(-8, -9); ctx.lineTo(-4, 0); ctx.lineTo(-8, 9); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.restore();
    }
    ctx.restore();
  };
})();
