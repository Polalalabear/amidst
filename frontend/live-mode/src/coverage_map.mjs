// F2 (#656): operator minimap of camera coverage (A side). Pure 2D canvas drawing, no three.js, no GT:
// floors, walls, each camera's wall-clipped FOV polygon (coverage.mjs), blind floor cells, camera icons + labels,
// and the operator's own avatar position (which A controls; it never crosses to B).
export const CAM_COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#ec4899', '#8b5cf6', '#14b8a6', '#ef4444', '#84cc16'];
export const BLIND_FILL = 'rgba(220,38,38,.28)';

export function cameraColors(ids) { return Object.fromEntries([...ids].sort().map((id, i) => [id, CAM_COLORS[i % CAM_COLORS.length]])); }

// world (x, y) metres -> canvas pixels; y grows up in the world and down on the canvas
export function mapTransform(floors, w, h, pad = 8) {
  const x0 = Math.min(...floors.map(f => f.x_m[0])), x1 = Math.max(...floors.map(f => f.x_m[1]));
  const y0 = Math.min(...floors.map(f => f.y_m[0])), y1 = Math.max(...floors.map(f => f.y_m[1]));
  const s = Math.min((w - 2 * pad) / (x1 - x0), (h - 2 * pad) / (y1 - y0));
  const ox = pad + ((w - 2 * pad) - s * (x1 - x0)) / 2, oy = pad + ((h - 2 * pad) - s * (y1 - y0)) / 2;
  return {scale: s, map: (x, y) => [ox + (x - x0) * s, oy + (y1 - y) * s]};
}

export function drawCoverageMap(ctx, {geometry, walls, coverage, colors, player = null, w, h, blindCell = .5}) {
  const {scale, map} = mapTransform(geometry.floors, w, h);
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = '#e8e4dc';
  for (const f of geometry.floors) { const [a, b] = map(f.x_m[0], f.y_m[1]); ctx.fillRect(a, b, (f.x_m[1] - f.x_m[0]) * scale, (f.y_m[1] - f.y_m[0]) * scale); }
  ctx.fillStyle = BLIND_FILL;
  const cell = blindCell * scale;
  for (const [x, y] of coverage.blind) { const [a, b] = map(x, y); ctx.fillRect(a - cell / 2, b - cell / 2, cell, cell); }
  for (const c of coverage.cameras) {
    if (c.polygon.length < 3) continue;
    ctx.beginPath(); c.polygon.forEach(([x, y], i) => { const [a, b] = map(x, y); i ? ctx.lineTo(a, b) : ctx.moveTo(a, b); }); ctx.closePath();
    ctx.globalAlpha = .22; ctx.fillStyle = colors[c.camera_id]; ctx.fill(); ctx.globalAlpha = .9; ctx.strokeStyle = colors[c.camera_id]; ctx.lineWidth = 1; ctx.stroke(); ctx.globalAlpha = 1;
  }
  ctx.strokeStyle = '#33302b'; ctx.lineWidth = 2; ctx.beginPath();
  for (const [ax, ay, bx, by] of walls) { const [a, b] = map(ax, ay), [c, d] = map(bx, by); ctx.moveTo(a, b); ctx.lineTo(c, d); }
  ctx.stroke();
  ctx.font = '10px sans-serif';
  for (const c of coverage.cameras) {
    const {pos: [x, y], yaw} = c.pose, [a, b] = map(x, y);
    ctx.save(); ctx.translate(a, b); ctx.rotate(-yaw);
    ctx.fillStyle = colors[c.camera_id]; ctx.strokeStyle = '#111'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(7, 0); ctx.lineTo(-5, -5); ctx.lineTo(-5, 5); ctx.closePath(); ctx.fill(); ctx.stroke(); ctx.restore();
    ctx.fillStyle = '#111'; ctx.fillText(c.camera_id.replace('CAM_', ''), a + 6, b - 6);
  }
  if (player) {
    const [a, b] = map(player.x, player.y);
    ctx.fillStyle = '#dc2626'; ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(a, b, 5, 0, 2 * Math.PI); ctx.fill(); ctx.stroke();
  }
  return {scale};
}
