// Deterministic SYNTHETIC fixture generator for workbench v2 (design §6.6 V2-2).
// Ported from the design mockup v3 generator, adapted to contract v1.1 (#65 @ 98451bd) field names.
// The invented scene and the two walkers exist only to produce payloads; no UI code may import this file.
// Usage: node generate_v2_fixtures.mjs          write fixtures next to this file
//        node generate_v2_fixtures.mjs --check  fail if any committed file differs from a fresh run
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { COMPOSED_EVIDENCE_STATE, QUALITY_LIMITS, QUALITY_RULE_REF, gradeFor, humanoidRangeAllowed } from '../uncertainty.mjs';

const HERE = fileURLToPath(new URL('.', import.meta.url));

// ---------- canonical JSON and hashes (contract §2.1) ----------
export function canonicalJson(v) {
  if (v === null || typeof v === 'boolean') return JSON.stringify(v);
  if (typeof v === 'number') { if (!Number.isFinite(v)) throw new Error('non-finite number'); return JSON.stringify(v); }
  if (typeof v === 'string') return JSON.stringify(v).replace(/[\u007f-￿]/g, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`);
  if (Array.isArray(v)) return `[${v.map(canonicalJson).join(',')}]`;
  return `{${Object.keys(v).sort().map((k) => `${JSON.stringify(k)}:${canonicalJson(v[k])}`).join(',')}}`;
}
export const sha = (v) => createHash('sha256').update(typeof v === 'string' ? v : canonicalJson(v)).digest('hex');
const hashField = (obj, field) => { const { [field]: _drop, ...rest } = obj; return { ...rest, [field]: sha(rest) }; };
const r2 = (n) => Math.round(n * 100) / 100;
const r3 = (n) => Math.round(n * 1000) / 1000;
const pad6 = (n) => String(n).padStart(6, '0');
const jit = (i) => { const s = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return s - Math.floor(s) - 0.5; };

const NOTE = 'SYNTHETIC: 所有數值、影格、候選與估計都是設計用的示意資料，不是任何真實 run 的結果；形狀照受控場景契約 v1.1（#65 @ 98451bd）。';
const SCENE_ID = 'controlled-l-corridor';
const FPS = 5;
const QUALITY_RULE_SHA = sha({ ref: QUALITY_RULE_REF, limits: QUALITY_LIMITS });
const POSE_MODEL = 'NOT_USED';

// ---------- invented scene (generator only) ----------
const IMG_W = 960, IMG_H = 540, HFOV = (75 * Math.PI) / 180, FX_PX = IMG_W / 2 / Math.tan(HFOV / 2);
const SCENE = {
  floors: [
    { id: 'WALK_CORR_W', poly: [[0, 0], [17.4, 0], [17.4, 2.4], [0, 2.4]] },
    { id: 'WALK_CORR_N', poly: [[15, 2.4], [17.4, 2.4], [17.4, 12], [15, 12]] },
    { id: 'WALK_R101', poly: [[5, -5], [11, -5], [11, 0], [5, 0]] },
    { id: 'WALK_R102', poly: [[17.4, 7], [22.4, 7], [22.4, 11], [17.4, 11]] },
  ],
  walls: [[0, 0, 7.4, 0], [8.6, 0, 17.4, 0], [0, 2.4, 15, 2.4], [0, 0, 0, 2.4], [15, 2.4, 15, 12], [17.4, 0, 17.4, 8.4], [17.4, 9.6, 17.4, 12], [15, 12, 17.4, 12],
    [5, -5, 5, 0], [11, -5, 11, 0], [5, -5, 11, -5], [17.4, 7, 22.4, 7], [17.4, 11, 22.4, 11], [22.4, 7, 22.4, 11]],
  areas: { AREA_R101_FRONT: [[6.5, 0], [9.5, 0], [9.5, 2.4], [6.5, 2.4]] },
};
const CAMS = {
  CAM_W1: { pos: [0.3, 1.2, 2.8], yaw: 0, pitch: -0.45, far: 8.7, room: 'WALK_CORR_W', foot: [[1, 0], [9, 0], [9, 2.4], [1, 2.4]] },
  CAM_W2: { pos: [15.0, 1.2, 2.8], yaw: Math.PI, pitch: -0.45, far: 9.0, room: 'WALK_CORR_W', foot: [[6, 0], [14.5, 0], [14.5, 2.4], [6, 2.4]] },
  CAM_N1: { pos: [16.2, 11.8, 2.8], yaw: -Math.PI / 2, pitch: -0.45, far: 8.3, room: 'WALK_CORR_N', foot: [[15, 3.5], [17.4, 3.5], [17.4, 11], [15, 11]] },
  CAM_R102_CTRL: { pos: [22.1, 10.7, 2.8], yaw: Math.atan2(9 - 10.7, 19.9 - 22.1), pitch: -0.6, far: 7, room: 'WALK_R102', foot: [[17.4, 7], [22.4, 7], [22.4, 11], [17.4, 11]] },
};
for (const c of Object.values(CAMS)) {
  const cp = Math.cos(c.pitch), sp = Math.sin(c.pitch), cy = Math.cos(c.yaw), sy = Math.sin(c.yaw);
  c.f = [cy * cp, sy * cp, sp]; c.r = [sy, -cy, 0];
  c.u = [c.r[1] * c.f[2] - c.r[2] * c.f[1], c.r[2] * c.f[0] - c.r[0] * c.f[2], c.r[0] * c.f[1] - c.r[1] * c.f[0]];
  c.h = [cy, sy];
}
const camSpace = (c, p) => { const d = [p[0] - c.pos[0], p[1] - c.pos[1], p[2] - c.pos[2]]; return [d[0] * c.r[0] + d[1] * c.r[1] + d[2] * c.r[2], d[0] * c.u[0] + d[1] * c.u[1] + d[2] * c.u[2], d[0] * c.f[0] + d[1] * c.f[1] + d[2] * c.f[2]]; };
const projC = (q) => [IMG_W / 2 + (FX_PX * q[0]) / q[2], IMG_H / 2 - (FX_PX * q[1]) / q[2]];
const fwd = (c, p) => (p[0] - c.pos[0]) * c.h[0] + (p[1] - c.pos[1]) * c.h[1];
const inPoly = (pt, poly) => { let o = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const [xi, yi] = poly[i], [xj, yj] = poly[j]; if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi) + xi) o = !o; } return o; };
const floorPoly = (id) => SCENE.floors.find((f) => f.id === id).poly;

const P_A = (t) => ({ x: 1 + 1.3 * t, y: 1.2 });
const P1_B = (t) => { const t1 = (16.2 - 1) / 1.3; if (t <= t1) return { x: 1 + 1.3 * t, y: 1.2 }; return { x: 16.2, y: Math.min(1.2 + 1.3 * (t - t1), 11.5) }; };
const P2_B = (t) => { if (t < 8) return null; const t1 = 8 + 7 / 1.3; if (t <= t1) return { x: 1 + 1.3 * (t - 8), y: 1.2 }; return { x: 8, y: Math.max(1.2 - 1.3 * (t - t1), -2.5) }; };

function imageOf(cam, p) {
  const c = CAMS[cam];
  if (!inPoly([p.x, p.y], floorPoly(c.room))) return null;
  const fd = fwd(c, [p.x, p.y, 0]); if (fd < 0.3 || fd > c.far) return null;
  const qf = camSpace(c, [p.x, p.y, 0]), qh = camSpace(c, [p.x, p.y, 1.75]); if (qf[2] < 0.1 || qh[2] < 0.1) return null;
  const pf = projC(qf), ph = projC(qh), w = (FX_PX * 0.52) / qf[2];
  const full = [pf[0] - w / 2, ph[1], pf[0] + w / 2, pf[1]];
  const cl = [Math.max(0, full[0]), Math.max(0, full[1]), Math.min(IMG_W, full[2]), Math.min(IMG_H, full[3])];
  if (cl[2] <= cl[0] || cl[3] <= cl[1]) return null;
  if ((cl[3] - cl[1]) / (full[3] - full[1]) < 0.35) return null;
  return { bbox: cl.map(Math.round), footIn: pf[1] <= IMG_H && pf[0] >= 0 && pf[0] <= IMG_W, dist: Math.hypot(p.x - c.pos[0], p.y - c.pos[1]) };
}

const EVENTS = {
  A: { key: 'A', run_id: 'fixture-ctrl-a-5fps-v1-r001', duration_s: 10, cams: ['CAM_R102_CTRL', 'CAM_W1', 'CAM_W2'], people: [P_A], missing: { CAM_W2: [31] } },
  B1: { key: 'B1', run_id: 'fixture-ctrl-b1-5fps-v1-r001', duration_s: 20, cams: ['CAM_R102_CTRL', 'CAM_N1', 'CAM_W1', 'CAM_W2'], people: [P1_B, P2_B], missing: { CAM_N1: [76] } },
};
const ruleUncertainty = (kind, value, used, extra = {}) => ({
  extent_kind: kind, extent_value: value, constraints_used: used, quality_grade: gradeFor(kind, value),
  quality_rule_ref: QUALITY_RULE_REF, quality_rule_sha256: QUALITY_RULE_SHA, ...extra,
});
const mid2 = (g) => [(g.near_m[0] + g.far_m[0]) / 2, (g.near_m[1] + g.far_m[1]) / 2];

// ---------- per-event simulation ----------
function simulate(ev) {
  const N = ev.duration_s * FPS;
  const frames = {}, render = {};
  for (const cam of ev.cams) {
    frames[cam] = []; render[cam] = [];
    for (let k = 0; k < N; k++) {
      const miss = (ev.missing[cam] || []).includes(k);
      frames[cam].push({ k, miss, frame_ref: miss ? null : `fr-${ev.key}-${cam}-${pad6(k)}` });
      render[cam].push(ev.people.map((fn, pi) => { const p = fn(k / FPS); return p ? { ...p, pi } : null; }).filter(Boolean));
    }
  }
  const estimates = [], tracks = [], gen = new Map(), seq = {};
  for (const cam of ev.cams) {
    const open = new Map();
    for (let k = 0; k < N; k++) {
      const fr = frames[cam][k];
      if (fr.miss) { for (const tr of open.values()) { tr.gaps.push(k); tr.samples.push({ k, missing: true }); } continue; }
      const seen = new Set();
      for (const p of render[cam][k]) {
        const im = imageOf(cam, p); if (!im) continue;
        seen.add(p.pi);
        let tr = open.get(p.pi);
        if (!tr) { seq[cam] = (seq[cam] || 0) + 1; tr = { ref: `lt-${ev.key}-${cam.replace('CAM_', '')}-${String(seq[cam]).padStart(2, '0')}`, camera_id: cam, samples: [], gaps: [], end: null }; open.set(p.pi, tr); tracks.push(tr); }
        const c = CAMS[cam], u = [(p.x - c.pos[0]) / im.dist, (p.y - c.pos[1]) / im.dist];
        const L = 0.12 + 0.04 * im.dist, cx = p.x + jit(k * 7 + cam.length) * 0.12, cy = p.y + jit(k * 13 + cam.length) * 0.08;
        const near = [r3(cx - (u[0] * L) / 2), r3(cy - (u[1] * L) / 2), 0], far = [r3(cx + (u[0] * L) / 2), r3(cy + (u[1] * L) / 2), 0];
        const obs = `obs-${ev.key}-${cam}-${pad6(k)}-c0`;
        const flagged = im.dist > 8.2;
        const ground = im.footIn
          ? { status: 'READY', estimate_kind: 'SEGMENT', basis: 'FOOT_RAY_PIXEL_BAND',
              segment: { near_m: near, far_m: far, raw_near_m: near, raw_far_m: far, length_m: r2(L) }, constraints_applied: [],
              contact_quality: { status: flagged ? 'FLAGGED' : 'PASS', reasons: flagged ? ['LOW_INCIDENCE'] : [] }, evidence_state: 'PROJECTED_OBSERVATION' }
          : { status: 'UNKNOWN', estimate_kind: 'UNKNOWN', basis: 'FOOT_RAY_PIXEL_BAND', reason: 'FOOT_OUT_OF_FRAME', segment: null, evidence_state: 'UNKNOWN' };
        const est = { estimate_ref: `pe-${ev.key}-${cam}-${pad6(k)}-c0`, observation_ref: obs, camera_id: cam, frame_ref: fr.frame_ref,
          rgb_file_sha256: sha(`rgb:${fr.frame_ref}`), calibration_sha256: sha(`calibration:${cam}`), floor_id: 'FLOOR_1F', timestamp_s: k / FPS,
          local_track_ref: tr.ref, ground_estimate: hashField(ground, 'output_sha256'), bbox_px: im.bbox, bbox_height_px: im.bbox[3] - im.bbox[1] };
        estimates.push(est);
        gen.set(obs, { u, dist: im.dist, cam, k });
        tr.samples.push({ k, obs, est, ready: ground.status === 'READY', flagged });
      }
      for (const [pi, tr] of [...open.entries()]) if (!seen.has(pi)) { tr.end = 'NO_DETECTION_IN_VIEW'; open.delete(pi); }
    }
    for (const tr of open.values()) tr.end = 'RUN_END';
  }
  composeGround(estimates, tracks, gen);
  headings(tracks);
  for (const e of estimates) {
    e.display = { humanoid_range_allowed: humanoidRangeAllowed(e.composed_ground), display_config_sha256: sha('display-config-v1') };
    e.identity_verdict = 'UNCONFIRMED'; e.physical_verdict = 'UNKNOWN';
  }
  return { ev, N, frames, render, estimates, tracks, gen };
}

// §6.3.1: height range -> along-ray floor segment; foot visible uses the foot pixel band; speed only tightens out-of-frame feet.
function composeGround(estimates, tracks, gen) {
  for (const tr of tracks) {
    const nReady = tr.samples.filter((s) => s.ready && !s.flagged).length;
    const heightOk = nReady >= 5; // contract §3.12: at least 5 high-confidence frames; whole-track use
    const lo = heightOk ? 1.68 : 1.65, hi = heightOk ? 1.74 : 1.75;
    tr.heightOk = heightOk;
    for (let i = 0; i < tr.samples.length; i++) {
      const s = tr.samples[i]; if (s.missing) continue;
      const e = s.est, g = gen.get(s.obs), c = CAMS[g.cam], ge = e.ground_estimate;
      const used = [], unavail = []; let near, far, foot;
      if (ge.status === 'READY') {
        foot = 'VISIBLE'; near = ge.segment.near_m.slice(0, 2); far = ge.segment.far_m.slice(0, 2);
        unavail.push({ kind: 'prior', reason: 'FOOT_VISIBLE' }, { kind: 'track_height', reason: 'FOOT_VISIBLE' }, { kind: 'lowest_visible_far', reason: 'FOOT_VISIBLE' });
      } else {
        foot = 'OUT_OF_FRAME';
        const at = (h) => [c.pos[0] + (g.u[0] * g.dist * (2.8 - h)) / 1.05, c.pos[1] + (g.u[1] * g.dist * (2.8 - h)) / 1.05];
        near = at(hi); far = at(lo);
        if (heightOk) { used.push({ kind: 'track_height', source_ref: `${tr.ref}#track_height_estimate`, source_sha256: sha(`track-height:${tr.ref}`), values: { lower_m: lo, upper_m: hi } }); unavail.push({ kind: 'prior', reason: 'SUPERSEDED_BY_TRACK_HEIGHT' }); }
        else { used.push({ kind: 'prior', source_ref: 'body-prior-v1', source_sha256: sha('body-prior-v1'), values: { lower_m: lo, upper_m: hi } }); unavail.push({ kind: 'track_height', reason: 'INSUFFICIENT_FRAMES' }); }
        const lv = at(-0.6);
        used.push({ kind: 'lowest_visible_far', source_ref: s.obs, source_sha256: e.rgb_file_sha256, values: { bound_m: [r3(lv[0]), r3(lv[1]), 0] } });
        // speed: latest earlier foot-visible sample of the same track, <= 1.0 s back, no missing sample between; anchors never use speed
        let anchor = null;
        for (let j = i - 1; j >= 0 && s.k - tr.samples[j].k <= FPS; j--) {
          const a = tr.samples[j]; if (a.missing) break;
          if (a.ready && !a.flagged) { anchor = a; break; }
        }
        if (anchor) {
          const am = mid2(anchor.est.composed_ground.geometry), dt = (s.k - anchor.k) / FPS, rad = 2.0 * dt + anchor.est.composed_ground.geometry.length_m / 2;
          const clip = [];
          for (let q = 0; q <= 40; q++) { const pt = [near[0] + ((far[0] - near[0]) * q) / 40, near[1] + ((far[1] - near[1]) * q) / 40]; if (Math.hypot(pt[0] - am[0], pt[1] - am[1]) <= rad) clip.push(pt); }
          used.push({ kind: 'speed', source_ref: anchor.obs, source_sha256: anchor.est.composed_ground.output_sha256, values: { anchor_timestamp_s: anchor.k / FPS, dt_s: dt, v_max_mps: 2.0, speed_config_sha256: sha('speed-config-v1') } });
          if (!clip.length) { e.composed_ground = unknownComposed('CONSTRAINTS_INCONSISTENT', used, unavail); continue; }
          near = clip[0]; far = clip[clip.length - 1];
        } else unavail.push({ kind: 'speed', reason: 'NO_ANCHOR' });
      }
      unavail.push({ kind: 'occlusion_near', reason: 'NOT_OCCLUDED_BY_STATIC' });
      const len = r2(Math.hypot(far[0] - near[0], far[1] - near[1]));
      e.composed_ground = hashField({
        schema_version: 'controlled-scene.composed-ground.v1', status: 'READY', reason: null, evidence_state: COMPOSED_EVIDENCE_STATE,
        foot_status: foot, pose_model: POSE_MODEL,
        geometry: { kind: 'SEGMENT', floor_id: 'FLOOR_1F', near_m: [r3(near[0]), r3(near[1]), 0], far_m: [r3(far[0]), r3(far[1]), 0], length_m: len, polygon_m: null, polygon_area_m2: null, view_ray_ref: `${s.obs}#head_ray` },
        constraints_used: used, constraints_unavailable: unavail,
        uncertainty: ruleUncertainty('LENGTH_M', len, used.map((x) => x.kind)),
      }, 'output_sha256');
    }
  }
}
function unknownComposed(reason, used, unavail) {
  return hashField({ schema_version: 'controlled-scene.composed-ground.v1', status: 'UNKNOWN', reason, evidence_state: 'UNKNOWN', foot_status: 'UNKNOWN', pose_model: POSE_MODEL, geometry: null,
    constraints_used: used, constraints_unavailable: unavail, uncertainty: { extent_value: null, quality_grade: 'UNKNOWN', reason } }, 'output_sha256');
}

// D56 Q16: heading from a 5-sample window inside one local track; otherwise UNKNOWN. Angle range from the interval lengths.
function headings(tracks) {
  for (const tr of tracks) {
    const S = tr.samples;
    for (let i = 0; i < S.length; i++) {
      if (S[i].missing) continue;
      const e = S[i].est;
      const win = S.slice(i - 2, i + 3);
      const okWin = i >= 2 && win.length === 5 && win.every((s, j) => !s.missing && s.k === S[i].k - 2 + j && s.est.composed_ground.status === 'READY');
      if (!okWin) { e.heading = { state: 'UNKNOWN', reason: i < 2 || i + 2 >= S.length ? 'LOCAL_TRACK_EDGE' : 'WINDOW_INCOMPLETE', direction_xy: null }; continue; }
      const a = mid2(win[0].est.composed_ground.geometry), b = mid2(win[4].est.composed_ground.geometry);
      const d = [b[0] - a[0], b[1] - a[1]], base = Math.hypot(...d);
      if (base < 0.3) { e.heading = { state: 'UNKNOWN', reason: 'DIRECTION_AMBIGUOUS', direction_xy: null }; continue; }
      const maxL = Math.max(...win.map((s) => s.est.composed_ground.geometry.length_m));
      const deg = Math.min(180, Math.ceil((2 * Math.atan(maxL / 2 / base) * 180) / Math.PI * 10) / 10);
      e.heading = { state: 'INFERRED', status: 'READY', direction_xy: [r3(d[0] / base), r3(d[1] / base)], uncertainty: ruleUncertainty('ANGLE_DEG', deg, ['endpoint_estimates']) };
    }
  }
}

// ---------- blind hypothesis (K1-like; SYNTHETIC) ----------
function segX(p1, p2, p3, p4) {
  const d = (a, b, c) => (c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0]);
  const d1 = d(p3, p4, p1), d2 = d(p3, p4, p2), d3 = d(p1, p2, p3), d4 = d(p1, p2, p4);
  return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0));
}
function blindHypothesis(sim) {
  const { N, frames, estimates, tracks } = sim;
  const endTr = tracks.find((t) => t.camera_id === 'CAM_W2' && t.samples.find((s) => s.est)?.est.timestamp_s < 5);
  const nTr = tracks.find((t) => t.camera_id === 'CAM_N1');
  const lastReady = [...endTr.samples].reverse().find((s) => s.ready), firstReady = nTr.samples.find((s) => s.ready);
  const e0 = lastReady.est, e1 = firstReady.est;
  const t0 = e0.timestamp_s, t1 = e1.timestamp_s, V = 2.0, G = 0.25;
  const xs = -0.5, ys = -5.5, nx = Math.round(23.5 / G), ny = Math.round(18 / G);
  const walk = new Uint8Array(nx * ny), cen = (i) => [xs + ((i % nx) + 0.5) * G, ys + (Math.floor(i / nx) + 0.5) * G];
  for (let i = 0; i < nx * ny; i++) walk[i] = SCENE.floors.some((f) => inPoly(cen(i), f.poly)) ? 1 : 0;
  const cross = (a, b) => SCENE.walls.some((w) => segX(a, b, [w[0], w[1]], [w[2], w[3]]));
  const cellOf = (p) => Math.floor((p[1] - ys) / G) * nx + Math.floor((p[0] - xs) / G);
  const dijk = (src) => {
    const d = new Float32Array(nx * ny).fill(Infinity), s = cellOf(src); d[s] = 0; const q = [s];
    while (q.length) {
      let bi = 0; for (let j = 1; j < q.length; j++) if (d[q[j]] < d[q[bi]]) bi = j;
      const c = q.splice(bi, 1)[0], cx = c % nx, cy = Math.floor(c / nx), pc = cen(c);
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        if (!dx && !dy) continue; const x = cx + dx, y = cy + dy; if (x < 0 || y < 0 || x >= nx || y >= ny) continue;
        const n = y * nx + x; if (!walk[n]) continue;
        const nd = d[c] + Math.hypot(dx, dy) * G;
        if (nd < d[n] && !cross(pc, cen(n))) { if (d[n] === Infinity) q.push(n); d[n] = nd; }
      }
    }
    return d;
  };
  const a = mid2(e0.composed_ground.status === 'READY' ? e0.composed_ground.geometry : e0.ground_estimate.segment), b = mid2(e1.composed_ground.status === 'READY' ? e1.composed_ground.geometry : e1.ground_estimate.segment);
  const dS = dijk(a), dE = dijk(b);
  const detCache = {};
  const detectable = (cam, i) => { const m = (detCache[cam] ??= {}); if (m[i] === undefined) { const p = cen(i); m[i] = !!imageOf(cam, { x: p[0], y: p[1] }); } return m[i]; };
  const neg = [];
  for (const cam of sim.ev.cams) {
    if (cam === 'CAM_R102_CTRL') continue;
    for (let k = Math.round(t0 * FPS) + 1; k < Math.round(t1 * FPS); k++) {
      const fr = frames[cam][k];
      if (fr.miss) { neg.push({ camera_id: cam, frame_index: k, timestamp_s: k / FPS, frame_ref: null, state: 'MISSING' }); continue; }
      const det = estimates.some((e) => e.camera_id === cam && e.timestamp_s === k / FPS);
      neg.push({ camera_id: cam, frame_index: k, timestamp_s: k / FPS, frame_ref: fr.frame_ref, state: det ? 'DETECTION_PRESENT' : 'NO_DETECTION' });
    }
  }
  const regions = [];
  for (let k = Math.round(t0 * FPS); k <= Math.round(t1 * FPS); k++) {
    const tau = k / FPS, cells = [];
    const prune = neg.filter((n) => n.frame_index === k && n.state === 'NO_DETECTION').map((n) => n.camera_id);
    for (let i = 0; i < nx * ny; i++) {
      if (!walk[i]) continue;
      if (dS[i] > V * (tau - t0) + 1e-9 || dE[i] > V * (t1 - tau) + 1e-9) continue;
      if (prune.some((cam) => detectable(cam, i))) continue;
      cells.push(i);
    }
    const rows = []; // run-length by row: [iy, ix0, ix1]
    for (const i of cells) { const iy = Math.floor(i / nx), ix = i % nx, last = rows.at(-1); if (last && last[0] === iy && last[2] === ix - 1) last[2] = ix; else rows.push([iy, ix, ix]); }
    regions.push({ t_s: tau, area_m2: r2(cells.length * G * G), cell_count: cells.length, rows });
  }
  const paths = [[a, [16.2, 1.2], b], [a, [15.6, 0.7], [15.6, 2.9], b], [a, [16.9, 1.7], [16.9, 3.1], b]].map((pts, i) => ({
    hypothesis_ref: `hyp-${i + 1}`, rank: i + 1, points: pts.map((p) => [r3(p[0]), r3(p[1])]), checks: { speed: 'PASS', walkable: 'PASS', negative_evidence: 'PASS' } }));
  return { e0, e1, endTr, nTr, t0, t1, regions, paths, neg, grid: { x0: xs, y0: ys, cell_m: G, nx, ny }, V };
}

// ---------- envelopes ----------
function envelope(ev, schemaName, body, timeRange) {
  const clock = `clock:${ev.run_id}`;
  return hashField({
    schema_version: `controlled-scene.${schemaName}.v1`,
    SYNTHETIC: NOTE, data_origin: 'SYNTHETIC_FIXTURE', fixture_marker: 'FIXTURE',
    resolved_scope: { scene_id: SCENE_ID, scene_version: 1, run_id: ev.run_id, clock_id: clock, sampling_version: '5fps-v1', time_range_s: timeRange ?? [0, ev.duration_s], length_unit: 'm', data_origin: 'SYNTHETIC_FIXTURE',
      scene_static_sha256: sha('scene-static'), camera_catalog_sha256: sha('camera-catalog'), rgb_index_sha256: sha(`rgb-index:${ev.run_id}`) },
    ...body,
    identity_verdict: 'UNCONFIRMED', agent_used: false,
    provenance: { producer: 'v2-fixture-generator', gt_read: false },
  }, 'output_sha256');
}

function personLayer(sim) {
  return envelope(sim.ev, 'person-layer', { status: 'READY', time_range_s: [0, sim.ev.duration_s], estimates: sim.estimates }, [0, sim.ev.duration_s]);
}

function curveLayer(sim, hyp) {
  const ev = sim.ev;
  const policy = { body_policy_sha256: sha('body-policy-v1'), speed_config_sha256: sha('speed-config-v1') };
  const curves = sim.tracks.map((tr) => {
    const segs = [], S = tr.samples; let run = [];
    const flush = () => { if (run.length) { segs.push({ kind: 'OBSERVED', evidence_state: 'PROJECTED_OBSERVATION', sample_timestamps_s: run.map((x) => x.k / FPS), support_refs: run.map((x) => x.obs), geometry: { type: 'INTERVAL_SERIES' } }); run = []; } };
    for (let i = 0; i < S.length; i++) {
      if (S[i].missing) { flush(); segs.push({ kind: 'MISSING_GAP', evidence_state: 'MISSING', t_s: [S[i].k / FPS, (S[i].k + 1) / FPS], reason: 'RGB_RECORD_ABSENT', geometry: null }); continue; }
      if (S[i].ready) run.push(S[i]); else flush();
      const n = S[i + 1];
      if (n && !n.missing && n.k === S[i].k + 1 && S[i].est.composed_ground.status === 'READY' && n.est.composed_ground.status === 'READY') {
        const ga = S[i].est.composed_ground.geometry, gb = n.est.composed_ground.geometry;
        const dist = Math.hypot(...[0, 1].map((j) => mid2(gb)[j] - mid2(ga)[j])), area = r2(((ga.length_m + gb.length_m) / 2) * Math.max(dist, 0.01));
        segs.push({ kind: 'INFERRED_CONNECTOR', evidence_state: 'INFERRED_INTERPOLATION', t_s: [S[i].k / FPS, n.k / FPS], support_refs: [S[i].obs, n.obs], local_track_ref: tr.ref, geometry: { type: 'RIBBON' },
          uncertainty: ruleUncertainty('AREA_M2', area, ['endpoint_estimates']) });
      }
    }
    flush();
    return hashField({ curve_ref: `cv-${tr.ref.slice(3)}`, candidate_ref: null, local_track_refs: [tr.ref], camera_id: tr.camera_id, segments: segs, result_sha256: '', map_sha256: sha('walkable-map-v1'), policy_pins: policy,
      association: { state: 'NONE', identity_verdict: 'UNCONFIRMED' }, termination_reason: tr.end }, 'result_sha256');
  });
  if (hyp) {
    const peak = Math.max(...hyp.regions.map((r) => r.area_m2));
    const seg = { kind: 'BLIND_HYPOTHESIS', evidence_state: 'INFERRED_HYPOTHESIS', t_s: [hyp.t0, hyp.t1], hypothesis_response_sha256: hyp.doc_sha, hypothesis_refs: hyp.paths.map((p) => p.hypothesis_ref),
      unassociated_baseline: true, region_band: true, support_refs: [hyp.e0.observation_ref, hyp.e1.observation_ref],
      uncertainty: ruleUncertainty('AREA_M2', peak, ['endpoint_estimates', 'k1_reachability', 'speed'], { per_sample_ref: 'blind_hypothesis_B1.json#reachable_regions[].area_m2' }) };
    curves.push(hashField({ curve_ref: 'cv-B1-blind-01', candidate_ref: 'cand-01', local_track_refs: [hyp.endTr.ref, hyp.nTr.ref], segments: [seg], result_sha256: '', map_sha256: sha('walkable-map-v1'), policy_pins: policy,
      association: { state: 'INFERRED_HYPOTHESIS', identity_verdict: 'UNCONFIRMED' } }, 'result_sha256'));
  }
  return envelope(ev, 'curve-layer', { status: 'READY', time_range_s: [0, ev.duration_s], curves, time_highlight: { t_s: 0, window_s: 1 }, kinds_reserved: ['PREDICTION'] }, [0, ev.duration_s]);
}

// candidate_cameras (§6.1, D28): relation tier -> overlap area desc -> camera_id
function clipPoly(subject, clip) {
  let out = subject;
  for (let i = 0; i < clip.length; i++) {
    const A = clip[i], B = clip[(i + 1) % clip.length], inp = out; out = []; if (!inp.length) break;
    const side = (p) => (B[0] - A[0]) * (p[1] - A[1]) - (B[1] - A[1]) * (p[0] - A[0]);
    for (let j = 0; j < inp.length; j++) {
      const P = inp[j], Q = inp[(j + 1) % inp.length], sp = side(P), sq = side(Q);
      if (sp >= 0) out.push(P);
      if (sp >= 0 !== sq >= 0) { const t = sp / (sp - sq); out.push([P[0] + t * (Q[0] - P[0]), P[1] + t * (Q[1] - P[1])]); }
    }
  }
  return out;
}
const polyArea = (p) => { let s = 0; for (let i = 0; i < p.length; i++) { const a = p[i], b = p[(i + 1) % p.length]; s += a[0] * b[1] - b[0] * a[1]; } return s / 2; };
const ccw = (p) => (polyArea(p) < 0 ? [...p].reverse() : p);
function candidateCameras(ev, q) {
  const target = ccw(SCENE.areas[q.target]);
  const access = q.intent === 'ENTER_EXIT' ? ccw([[7.4, 0], [8.6, 0], [8.6, 1.2], [7.4, 1.2]]) : null;
  const rows = ev.cams.map((id) => {
    if (ev.key === 'B1' && id === 'CAM_R102_CTRL') return { camera_id: id, relation: 'UNKNOWN', reason_codes: ['VISIBILITY_INDEX_UNAVAILABLE'], tier: 4, overlap: null, availability: 'PARTIAL', unavailable_reason: 'VISIBILITY_INDEX_UNAVAILABLE' };
    const ov = Math.abs(polyArea(clipPoly(ccw(CAMS[id].foot), target)));
    if (ov > 1e-6) return { camera_id: id, relation: 'TARGET_FOOTPRINT_INTERSECT', reason_codes: ['TARGET_FOOTPRINT_INTERSECT', 'OVERLAP_AREA'], tier: 1, overlap: r2(ov), availability: 'AVAILABLE', unavailable_reason: null };
    if (access && Math.abs(polyArea(clipPoly(ccw(CAMS[id].foot), access))) > 1e-6) return { camera_id: id, relation: 'ACCESS_PATH_INTERSECT', reason_codes: ['ACCESS_PATH_INTERSECT'], tier: 2, overlap: 0, availability: 'AVAILABLE', unavailable_reason: null };
    return { camera_id: id, relation: 'NO_INTERSECTION', reason_codes: ['NO_INTERSECTION'], tier: 3, overlap: 0, availability: 'AVAILABLE', unavailable_reason: null };
  });
  rows.sort((a, b) => a.tier - b.tier || (b.overlap ?? -1) - (a.overlap ?? -1) || (a.camera_id < b.camera_id ? -1 : 1));
  const candidates = rows.map((r, i) => ({
    camera_id: r.camera_id, rank: i + 1, relation: r.relation, reason_codes: r.reason_codes,
    related_region_refs: r.tier <= 2 ? [q.target] : [], suggested_time_windows_s: r.tier <= 2 ? [[q.t0, q.t1]] : [],
    geometry_basis: r.tier === 4 ? null : { footprint_method: 'SYNTHETIC_FOOTPRINT', visibility_ref: `vis-${r.camera_id}`, footprint_sha256: sha(`footprint:${r.camera_id}`), overlap_area_m2: r.overlap, detectability: 'NOT_EVALUATED' },
    image_evidence: { perception_status: 'NOT_EVALUATED', evaluated_frames: 0, frame_records_read: 0, frames_with_detection: null, count_complete: false, sample_frame_refs: [] },
    availability: r.availability, unavailable_reason: r.unavailable_reason,
  }));
  const unknown = rows.filter((r) => r.relation === 'UNKNOWN').map((r) => r.camera_id);
  const querySha = sha({ ev: ev.run_id, ...q });
  return envelope(ev, 'candidate-cameras', {
    status: unknown.length ? 'PARTIAL' : 'READY', reason: unknown.length ? 'VISIBILITY_INDEX_UNAVAILABLE' : null,
    query_id: `cq-${querySha}`, query_sha256: querySha, candidate_snapshot_sha256: sha(candidates),
    query: { target_region_ref: q.target, time_range_s: [q.t0, q.t1], query_intent: q.intent },
    candidates, candidates_total: candidates.length, returned_count: candidates.length, next_cursor: null,
    candidate_set_complete: unknown.length === 0, truncated: false, unknown_camera_ids: unknown, recommended_camera_ids: candidates.map((c) => c.camera_id),
    ranking_basis: ['relation_tier', 'overlap_area_m2_desc', 'camera_id'],
    stats: { catalog_records_read: candidates.length, index_records_read: candidates.length - unknown.length, frame_records_read: 0 },
  }, [q.t0, q.t1]);
}

function evidenceLookups(simB, curves, hyp) {
  const ev = simB.ev;
  const body = (relation, extra) => envelope(ev, 'evidence-lookup', { status: 'READY', relation, fixture_canned: true, ...extra });
  const nearest = (e, tClick) => ({ observation_ref: e.observation_ref, camera_id: e.camera_id, frame_ref: e.frame_ref, timestamp_s: e.timestamp_s, support_offset_s: r2(e.timestamp_s - tClick), bbox_px: e.bbox_px });
  const byObs = new Map(simB.estimates.map((e) => [e.observation_ref, e]));
  const curve = curves.curves.find((c) => c.segments.some((s) => s.kind === 'INFERRED_CONNECTOR') && c.segments.some((s) => s.kind === 'OBSERVED'));
  const obsSeg = curve.segments.findIndex((s) => s.kind === 'OBSERVED'), conSeg = curve.segments.findIndex((s) => s.kind === 'INFERRED_CONNECTOR');
  const firstObs = byObs.get(curve.segments[obsSeg].support_refs[0]);
  const con = curve.segments[conSeg], ce = [byObs.get(con.support_refs[0]), byObs.get(con.support_refs[1])];
  const tClick = r2((con.t_s[0] + con.t_s[1]) / 2);
  const pick = (layer, ref, seg, hash, t) => ({ layer, ref, result_sha256: hash, segment_index: seg, t_click_s: t });
  const out = {};
  out.IS_OBSERVATION = body('IS_OBSERVATION', { pick_echo: pick('observation', firstObs.observation_ref, 0, curve.result_sha256, firstObs.timestamp_s),
    nearest_support: nearest(firstObs, firstObs.timestamp_s), other_supports: [], jump: { t_s: firstObs.timestamp_s, camera_ids: [firstObs.camera_id] } });
  const t2 = curve.segments[obsSeg].sample_timestamps_s[1] ?? firstObs.timestamp_s;
  out.SUPPORTS_OBSERVED_SEGMENT = body('SUPPORTS_OBSERVED_SEGMENT', { pick_echo: pick('curve', curve.curve_ref, obsSeg, curve.result_sha256, r2(t2 + 0.03)),
    nearest_support: nearest(byObs.get(curve.segments[obsSeg].support_refs[1] ?? firstObs.observation_ref), r2(t2 + 0.03)), other_supports: curve.segments[obsSeg].support_refs.slice(0, 3),
    jump: { t_s: t2, camera_ids: [firstObs.camera_id] } });
  const near = Math.abs(ce[0].timestamp_s - tClick) <= Math.abs(ce[1].timestamp_s - tClick) ? ce[0] : ce[1], other = near === ce[0] ? ce[1] : ce[0];
  out.ENDPOINTS_OF_CONNECTOR = body('ENDPOINTS_OF_CONNECTOR', { pick_echo: pick('curve', curve.curve_ref, conSeg, curve.result_sha256, tClick), nearest_support: nearest(near, tClick),
    other_supports: [other.observation_ref], jump: { t_s: near.timestamp_s, camera_ids: [near.camera_id] } });
  const blind = curves.curves.find((c) => c.curve_ref === 'cv-B1-blind-01');
  out.HYPOTHESIS_ENDPOINTS_AND_NEGATIVE_EVIDENCE = body('HYPOTHESIS_ENDPOINTS_AND_NEGATIVE_EVIDENCE', { pick_echo: pick('curve', blind.curve_ref, 0, blind.result_sha256, r2((hyp.t0 + hyp.t1) / 2)),
    nearest_support: null, other_supports: [hyp.e0.observation_ref, hyp.e1.observation_ref], negative_evidence_frames: hyp.neg, jump: null });
  const gapCurve = curves.curves.find((c) => c.segments.some((s) => s.kind === 'MISSING_GAP')), gi = gapCurve.segments.findIndex((s) => s.kind === 'MISSING_GAP');
  out.NO_SUPPORT = body('NO_SUPPORT', { pick_echo: pick('curve', gapCurve.curve_ref, gi, gapCurve.result_sha256, gapCurve.segments[gi].t_s[0]), nearest_support: null, other_supports: [], jump: null, reason: 'RGB_RECORD_ABSENT' });
  return out;
}

// ---------- build everything ----------
export function buildAll() {
  const files = {};
  const simA = simulate(EVENTS.A), simB = simulate(EVENTS.B1);
  const hyp = blindHypothesis(simB);
  const hypDoc = envelope(simB.ev, 'blind-hypothesis-fixture', {
    status: 'READY', SHAPE_NOTE: '契約 v1.1 沒有定義 K1 假設回應的形狀（UNKNOWN）；這份只是 fixture 用的暫定形狀，不是契約的一部分。',
    interval_s: [hyp.t0, hyp.t1], endpoint_observation_refs: [hyp.e0.observation_ref, hyp.e1.observation_ref], speed_cap_mps: hyp.V, unassociated_baseline: true,
    grid: hyp.grid, reachable_regions: hyp.regions, paths: hyp.paths, negative_evidence: hyp.neg,
  }, [hyp.t0, hyp.t1]);
  hyp.doc_sha = hypDoc.output_sha256;
  const personA = personLayer(simA), personB = personLayer(simB);
  const curvesA = curveLayer(simA, null), curvesB = curveLayer(simB, hyp);
  files['bootstrap_fixture.json'] = hashField({
    schema_version: 'controlled-scene.bootstrap.v1', SYNTHETIC: NOTE, data_origin: 'SYNTHETIC_FIXTURE', fixture_marker: 'FIXTURE',
    scenes: [{ scene_id: SCENE_ID, run_ids: [EVENTS.A.run_id, EVENTS.B1.run_id], camera_ids: Object.keys(CAMS), sampling: { fps: FPS, duration_s: 20, sampling_version: '5fps-v1' } }],
    real_run_support: 'NOT_IMPLEMENTED', gt_read: false, requires_session: true,
  }, 'output_sha256');
  files['candidate_cameras_A.json'] = candidateCameras(EVENTS.A, { target: 'AREA_R101_FRONT', t0: 0, t1: 10, intent: 'PASS_THROUGH' });
  files['candidate_cameras_B1.json'] = candidateCameras(EVENTS.B1, { target: 'AREA_R101_FRONT', t0: 8, t1: 20, intent: 'ENTER_EXIT' });
  files['person_layer_A.json'] = personA;
  files['person_layer_B1.json'] = personB;
  files['curve_layer_A.json'] = curvesA;
  files['curve_layer_B1.json'] = curvesB;
  files['blind_hypothesis_B1.json'] = hypDoc;
  const lookups = evidenceLookups(simB, curvesB, hyp);
  for (const [relation, doc] of Object.entries(lookups)) files[`evidence_lookup_B1_${relation.toLowerCase()}.json`] = doc;
  // Deliberately broken payloads: the api must refuse them.
  const sub = personB.estimates.slice(0, 6);
  const missing = structuredClone(sub);
  const victim = missing.find((e) => e.composed_ground.status === 'READY');
  delete victim.composed_ground.uncertainty;
  files['person_layer_missing_uncertainty.json'] = hashField({ ...personB, estimates: missing, output_sha256: '' }, 'output_sha256');
  files['person_layer_gt_read_true.json'] = hashField({ ...personB, estimates: sub, provenance: { producer: 'v2-fixture-generator', gt_read: true }, output_sha256: '' }, 'output_sha256');
  return Object.fromEntries(Object.entries(files).sort(([a], [b]) => (a < b ? -1 : 1)).map(([k, v]) => [k, `${JSON.stringify(v)}\n`]));
}

// ---------- CLI ----------
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const files = buildAll();
  if (process.argv.includes('--check')) {
    let bad = 0;
    for (const [name, text] of Object.entries(files)) {
      const p = HERE + name;
      if (!existsSync(p) || readFileSync(p, 'utf8') !== text) { console.error(`DIFFERS: ${name}`); bad++; }
    }
    const extra = readdirSync(HERE).filter((n) => n.endsWith('.json') && !(n in files) && !n.startsWith('synced_frames_'));
    for (const n of extra) { console.error(`UNEXPECTED: ${n}`); bad++; }
    if (bad) process.exit(1);
    console.log(`ok: ${Object.keys(files).length} fixture files match`);
  } else {
    for (const [name, text] of Object.entries(files)) writeFileSync(HERE + name, text);
    console.log(`wrote ${Object.keys(files).length} files`);
  }
}
