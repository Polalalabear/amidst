// Scene -> SVG string. Solid = observed, dashed (orange) = physical prediction, dotted (teal) = external model guess.
// Styling lives in track-map.css; every dynamic string is escaped.
import {VIEW_W,VIEW_H,EXTERNAL_LABEL,EXTERNAL_UNAVAILABLE} from './track-map-model.mjs';
import {gapCaption} from './gap-state-model.mjs';
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
const pos=(scene,id)=>scene.nodes.find(n=>n.camera_id===id)?.xy;
function offset(a,b,k) {  // shift a parallel line sideways so observed / predicted / external between one pair stay distinguishable
  const dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy)||1;return [-dy/len*k,dx/len*k];
}
function line(a,b,cls,attrs,shift=0,title='') {
  const [ox,oy]=offset(a,b,shift);
  return `<line class="${cls}" x1="${a[0]+ox}" y1="${a[1]+oy}" x2="${b[0]+ox}" y2="${b[1]+oy}" ${attrs}>${title?`<title>${esc(title)}</title>`:''}</line>`;
}
function label(a,b,text,cls,shift) {
  const [ox,oy]=offset(a,b,shift);return `<text class="${cls}" x="${(a[0]+b[0])/2+ox}" y="${(a[1]+b[1])/2+oy-3}" text-anchor="middle">${esc(text)}</text>`;
}
export function renderSvg(scene) {
  const out=[`<svg class="tm-svg" viewBox="0 0 ${VIEW_W} ${VIEW_H}" role="img" aria-label="追蹤俯視圖（示意）" data-layout="${scene.layout}" data-origin="${esc(scene.origin)}">`];
  for(const e of scene.graphEdges)out.push(line(pos(scene,e.from),pos(scene,e.to),'tm-graph-edge','',0,e.title));
  for(const e of scene.observed)out.push(line(pos(scene,e.from),pos(scene,e.to),'tm-observed','',0,`已觀測 ${e.from}→${e.to}`));
  scene.predicted.forEach(p=>{const a=pos(scene,p.from),b=pos(scene,p.to);
    out.push(line(a,b,`tm-pred tm-conf-${p.confidence}`,`stroke-dasharray="${p.style.dash}" stroke-opacity="${p.style.opacity}" stroke-width="${p.style.width}" data-rank="${p.rank}"`,5,p.title));
    out.push(label(a,b,p.label,`tm-pred-label tm-conf-${p.confidence}`,5+((p.rank-1)%3)*7));});
  scene.externalLines.forEach((x,i)=>{const a=pos(scene,x.from),b=pos(scene,x.to);
    out.push(line(a,b,'tm-ext','stroke-dasharray="1 4"',-5,x.title));out.push(label(a,b,x.label,'tm-ext-label',-12-i*8));});
  for(const n of scene.nodes) {
    const off=n.role!=='TRACKING';
    out.push(`<g class="tm-node${n.current?' tm-current':''}${n.observed?' tm-seen':''}${off?' tm-off':''}" data-camera="${esc(n.camera_id)}"><circle cx="${n.xy[0]}" cy="${n.xy[1]}" r="${n.current?9:7}"/>`
      +`<text x="${n.xy[0]}" y="${n.xy[1]+3.5}" text-anchor="middle">${esc(n.camera_id)}</text>`
      +(off?`<text class="tm-off-note" x="${n.xy[0]}" y="${n.xy[1]+20}" text-anchor="middle">${n.role==='QUERY_ONLY'?'僅查詢':'不在圖內'}</text>`:'')+`</g>`);
  }
  out.push('</svg>');return out.join('');
}
export function renderPanelHtml(scene) {
  const parts=[];
  parts.push(`<div class="tm-head"><strong>俯視圖</strong><span class="tm-layout-note">${esc(scene.layoutNote)}</span></div>`);
  if(scene.notes.length)parts.push(`<div class="tm-synthetic" role="note">${scene.notes.map(esc).join(' · ')}</div>`);
  parts.push(scene.empty?'<p class="tm-empty">沒有可畫的鏡頭。</p>':renderSvg(scene));
  if(scene.inGap)parts.push(`<p class="tm-gap">目標暫不在任何鏡頭內（${esc(gapCaption(scene.gapNow??null))}）；位置未知，不補畫路線。</p>`);
  else if(scene.placeholderNote)parts.push(`<p class="tm-gap">${esc(scene.placeholderNote)}</p>`);
  if(scene.externalEnabled&&scene.externalUnavailable)parts.push(`<p class="tm-ext-unavailable" role="status">${EXTERNAL_UNAVAILABLE}</p>`);
  parts.push(`<div class="tm-legend"><span class="tm-key tm-key-obs">━ 已觀測</span><span class="tm-key tm-key-pred">${esc(scene.legend)}</span>${scene.externalEnabled?`<span class="tm-key tm-key-ext">┈ ${EXTERNAL_LABEL}</span>`:''}</div>`);
  parts.push(`<div class="tm-id">${esc(scene.identityLine)}</div>`);
  return parts.join('');
}
