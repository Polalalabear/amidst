// #771: the selected-detection box on the main tracking picture. Source observation only (detection index, never GT):
// the box is drawn only when the picture on screen is exactly the frame the box was detected on (no interpolation, no extrapolation).
import {placeBox} from './q2-session-model.mjs';

// Observation ids of the sightings the system selected for the single view on `cameraId` at source time `t`.
export function selectedObservationIds(sightings, cameraId, t) {
  const ids = [];
  for (const s of Array.isArray(sightings) ? sightings : []) {
    if (s?.camera_id !== cameraId || s.selected_for_single_view === false || !Array.isArray(s.range_us) || !Array.isArray(s.observation_ids)) continue;
    if (s.range_us[0] <= t && t < s.range_us[1]) ids.push(...s.observation_ids);
  }
  return ids;
}

// Pure pick: the cached box detected exactly at frame time `t` on `cameraId`, among the selected sightings. null when there is none.
export function pickBox(sightings, cache, cameraId, t) {
  for (const id of selectedObservationIds(sightings, cameraId, t)) {
    const b = cache.get(id);
    if (b && b.camera_id === cameraId && b.timestamp_us === t && Array.isArray(b.bbox_xyxy_px)) return b;
  }
  return null;
}

// Fetches boxes lazily (one request per chunk of ids the response named) and keeps them per response.
export function createTargetBoxSource({api, onUpdate = () => {}}) {
  let cache = new Map(), forResponse = null, pending = new Set(), dead = false;
  const reset = response => { if (forResponse !== response) { forResponse = response; cache = new Map(); pending = new Set(); } };
  return {
    cache: () => cache,
    box(state, cameraId, t) {
      const resp = state.coreTrackResponse, run = state.activeRun;
      if (!resp || !run || typeof api?.trackBoxes !== 'function') return null;
      reset(resp);
      const want = selectedObservationIds(resp.sightings, cameraId, t).filter(id => !cache.has(id) && !pending.has(id));
      for (let i = 0; i < want.length; i += 128) {
        const chunk = want.slice(i, i + 128); chunk.forEach(id => pending.add(id));
        const mine = forResponse;
        Promise.resolve(api.trackBoxes(run, chunk)).then(r => {
          if (dead || mine !== forResponse) return;
          if (r?.ok) for (const [id, b] of Object.entries(r.data.observations ?? {})) cache.set(id, b);
          else chunk.forEach(id => cache.set(id, null));   // unavailable: remember so it is not asked again
          onUpdate();
        }).catch(() => { chunk.forEach(id => cache.set(id, null)); });
      }
      return pickBox(resp.sightings, cache, cameraId, t);
    },
    destroy() { dead = true; },
  };
}

// Overlay on one picture: absolutely positioned inside the picture's container, laid out like the letterboxed <img>.
export function createBoxLayer({doc, container, img}) {
  const node = doc.createElement('span'); node.className = 'ui-target-box'; node.hidden = true; container.append(node);
  let last = null, detail = false;
  const layout = () => {
    if (!last) { node.hidden = true; return; }
    const p = placeBox(last.bbox_xyxy_px, img.naturalWidth, img.naturalHeight, container.clientWidth, container.clientHeight);
    if (!p) { node.hidden = true; return; }
    Object.assign(node.style, {left: p.left + '%', top: p.top + '%', width: (p.right - p.left) + '%', height: (p.bottom - p.top) + '%'});
    node.hidden = false;
  };
  img.addEventListener('load', layout);
  return {
    paint(box, {showDetail = false} = {}) {
      last = box; detail = showDetail;
      node.dataset.obs = box ? box.observation_id : '';
      node.textContent = '';
      if (box && detail) { const tag = doc.createElement('span'); tag.className = 'ui-target-box-tag ui-mono'; tag.textContent = `OBS · ${box.observation_id} · ${box.score}`; node.append(tag); }
      node.title = box ? '已選偵測框（身分未確認）' : '';
      layout();
    },
    layout,
    node,
  };
}
