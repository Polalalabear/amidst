// Live-mode game design v2: two minimap styles for the operator screen (design mockup code).
// Needs window.SCENE from ../live-mode-game-v1/scene-data.js. World frame: Blender XY metres.
// o: { player:{x,y,headingDeg}, seeing:[camera ids that actually see the player — operator side only] }
(function () {
  const rad = (d) => d * Math.PI / 180;

  function playerMarker(ctx, size) {
    // high-contrast marker: dark halo, white arrow, thick dark outline, bright ring
    ctx.beginPath(); ctx.arc(0, 0, size * 1.55, 0, 7); ctx.fillStyle = 'rgba(0,0,0,.55)'; ctx.fill();
    ctx.beginPath(); ctx.arc(0, 0, size * 1.55, 0, 7); ctx.strokeStyle = '#ffd60a'; ctx.lineWidth = 3; ctx.stroke();
    ctx.beginPath(); ctx.moveTo(size, 0); ctx.lineTo(-size * 0.75, -size * 0.75); ctx.lineTo(-size * 0.3, 0); ctx.lineTo(-size * 0.75, size * 0.75); ctx.closePath();
    ctx.lineJoin = 'round'; ctx.strokeStyle = '#0b0e13'; ctx.lineWidth = 5; ctx.stroke();
    ctx.fillStyle = '#ffffff'; ctx.fill();
  }

  // A — "you are the centre": heading-up, zoomed in, player fixed at the centre. No view wedges;
  // a camera only lights up (dot + beam to you) while it actually sees you.
  window.drawMinimapA = function (cv, o) {
    const S = window.SCENE, ctx = cv.getContext('2d'), W = cv.width, H = cv.height, ppm = o.ppm || 15;
    const rot = rad(o.player.headingDeg - 90);
    ctx.save(); ctx.clearRect(0, 0, W, H);
    ctx.beginPath(); ctx.arc(W / 2, H / 2, W / 2 - 2, 0, 7); ctx.clip();
    ctx.fillStyle = '#0b0e13'; ctx.fillRect(0, 0, W, H);
    ctx.translate(W / 2, H / 2); ctx.rotate(rot);
    const T = (x, y) => [(x - o.player.x) * ppm, -(y - o.player.y) * ppm];
    ctx.fillStyle = '#566173';
    for (const f of S.floors) { const [x0, y0] = T(f.x[0], f.y[1]), [x1, y1] = T(f.x[1], f.y[0]); ctx.fillRect(x0, y0, x1 - x0, y1 - y0); }
    ctx.strokeStyle = 'rgba(11,14,19,.55)'; ctx.lineWidth = 2; ctx.beginPath();
    for (const [ax, ay, bx, by] of S.walls) { ctx.moveTo(...T(ax, ay)); ctx.lineTo(...T(bx, by)); }
    ctx.stroke();
    for (const c of S.cameras) {
      const on = (o.seeing || []).includes(c.id), [px, py] = T(c.x, c.y);
      if (on) {
        ctx.strokeStyle = 'rgba(255,214,10,.75)'; ctx.lineWidth = 3; ctx.setLineDash([2, 6]); ctx.lineCap = 'round';
        ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(0, 0); ctx.stroke(); ctx.setLineDash([]);
      }
      ctx.beginPath(); ctx.arc(px, py, on ? 8 : 4.5, 0, 7);
      ctx.fillStyle = on ? '#ffd60a' : '#aab3c0'; ctx.fill();
      ctx.strokeStyle = '#0b0e13'; ctx.lineWidth = 2; ctx.stroke();
      if (on) {
        ctx.save(); ctx.translate(px, py); ctx.rotate(-rot);
        ctx.font = '700 13px -apple-system,"PingFang TC",sans-serif'; ctx.lineWidth = 4; ctx.strokeStyle = '#0b0e13'; ctx.fillStyle = '#ffd60a';
        const t = c.id.replace('CAM_', ''); ctx.strokeText(t, 11, 5); ctx.fillText(t, 11, 5); ctx.restore();
      }
    }
    ctx.rotate(-rad(o.player.headingDeg)); // marker points along the heading => up on screen
    playerMarker(ctx, o.marker || 13);
    ctx.restore();
    ctx.beginPath(); ctx.arc(W / 2, H / 2, W / 2 - 2, 0, 7); ctx.strokeStyle = 'rgba(255,255,255,.35)'; ctx.lineWidth = 2; ctx.stroke();
  };

  // B — "whole floor": north-up, the whole site, fixed. Low-alpha wedge only for cameras that see
  // you; cross-hair lines lead the eye to the player.
  window.drawMinimapB = function (cv, o) {
    const S = window.SCENE, ctx = cv.getContext('2d'), W = cv.width, H = cv.height;
    const x0w = -15.8, x1w = 23, y0w = -6.6, y1w = 14.2, ppm = Math.min(W / (x1w - x0w), H / (y1w - y0w));
    const T = (x, y) => [(x - x0w) * ppm + (W - (x1w - x0w) * ppm) / 2, H - (y - y0w) * ppm - (H - (y1w - y0w) * ppm) / 2];
    ctx.save(); ctx.clearRect(0, 0, W, H); ctx.fillStyle = '#0b0e13'; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#566173';
    for (const f of S.floors) { const [ax, ay] = T(f.x[0], f.y[1]), [bx, by] = T(f.x[1], f.y[0]); ctx.fillRect(ax, ay, bx - ax, by - ay); }
    ctx.strokeStyle = 'rgba(11,14,19,.55)'; ctx.lineWidth = 1.5; ctx.beginPath();
    for (const [ax, ay, bx, by] of S.walls) { ctx.moveTo(...T(ax, ay)); ctx.lineTo(...T(bx, by)); }
    ctx.stroke();
    const [px, py] = T(o.player.x, o.player.y);
    for (const c of S.cameras) {
      const on = (o.seeing || []).includes(c.id), [cx, cy] = T(c.x, c.y);
      if (on) {
        const len = (Math.hypot(o.player.x - c.x, o.player.y - c.y) + 1.5) * ppm;
        const a0 = -rad(c.yaw_deg + c.hfov_deg / 2), a1 = -rad(c.yaw_deg - c.hfov_deg / 2);
        ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, len, a0, a1); ctx.closePath();
        ctx.fillStyle = 'rgba(255,214,10,.20)'; ctx.fill();
      }
      ctx.beginPath(); ctx.arc(cx, cy, on ? 6 : 3.5, 0, 7); ctx.fillStyle = on ? '#ffd60a' : '#aab3c0'; ctx.fill();
      ctx.strokeStyle = '#0b0e13'; ctx.lineWidth = 1.5; ctx.stroke();
      if (on) {
        ctx.font = '700 12px -apple-system,"PingFang TC",sans-serif'; ctx.lineWidth = 4; ctx.strokeStyle = '#0b0e13'; ctx.fillStyle = '#ffd60a';
        const t = c.id.replace('CAM_', ''); ctx.strokeText(t, cx + 9, cy - 7); ctx.fillText(t, cx + 9, cy - 7);
      }
    }
    ctx.strokeStyle = 'rgba(255,255,255,.28)'; ctx.lineWidth = 1; ctx.beginPath();
    ctx.moveTo(px, 0); ctx.lineTo(px, H); ctx.moveTo(0, py); ctx.lineTo(W, py); ctx.stroke();
    ctx.translate(px, py); ctx.rotate(-rad(o.player.headingDeg)); playerMarker(ctx, o.marker || 9);
    ctx.restore();
  };
})();
