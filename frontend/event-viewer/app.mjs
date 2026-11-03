import { clampFrame, formatTime, mediaUrl, planTick, stampText, stepFrame } from './sync.mjs';

const $ = (id) => document.getElementById(id);
const cache = new Map();
const state = { run: null, frame: 0, playing: false, nextDue: 0, skipped: 0, stalls: 0, shown: -1, target: 0 };

function load(runKey, camera, index) {
  const url = mediaUrl(runKey, camera, index);
  if (!cache.has(url)) {
    // 用 load 事件而非 decode()：隱藏分頁中 decode() 可能永不結束。
    const img = new Image();
    const done = new Promise((resolve) => { img.onload = () => resolve(true); img.onerror = () => resolve(false); });
    img.src = url;
    cache.set(url, { img, done, ok: null });
    cache.get(url).done.then((ok) => { cache.get(url).ok = ok; });
  }
  return cache.get(url);
}

function framesReady(index) {
  const run = state.run;
  return run.cameras.every((cam) => load(run.key, cam, index).ok === true);
}

function prefetch(from) {
  const run = state.run;
  for (let i = from; i < Math.min(from + 15, run.frames); i++) run.cameras.forEach((c) => load(run.key, c, i));
  if (cache.size > run.cameras.length * 60) {
    for (const key of [...cache.keys()].slice(0, run.cameras.length * 20)) cache.delete(key);
  }
}

function show(index) {
  const run = state.run;
  run.cameras.forEach((cam) => {
    $(`img-${cam}`).src = mediaUrl(run.key, cam, index);
    $(`cap-${cam}`).textContent = stampText(cam, index, run.fps);
  });
  state.frame = index;
  state.shown = index;
  state.target = index;
  $('scrub').value = index;
  $('clock').textContent = formatTime(index, run.fps);
  $('frameno').textContent = `frame ${index} / ${run.frames - 1}`;
  $('stats').textContent = `跳格 ${state.skipped}｜停滯 ${state.stalls}`;
  prefetch(index + 1);
}

// 跳到任意格：等所有鏡頭的同一格都解碼完才一起換，避免畫面錯位。
async function seek(index) {
  const run = state.run;
  const target = clampFrame(index, run.frames);
  state.target = target;
  await Promise.all(run.cameras.map((c) => load(run.key, c, target).done));
  if (state.run === run && state.target === target && framesReady(target)) show(target);
}

function setPlaying(on) {
  state.playing = on;
  $('play').textContent = on ? '暫停' : '播放';
  if (on) state.nextDue = performance.now();
}

function tick(now) {
  if (state.playing) {
    const run = state.run;
    const next = Math.min(state.frame + 1, run.frames - 1);
    prefetch(next);
    const plan = planTick({ now, nextDue: state.nextDue, frame: state.frame, total: run.frames, fps: run.fps, ready: framesReady(next) });
    if (plan.action === 'end') setPlaying(false);
    else if (plan.action === 'stall') { state.stalls++; $('stats').textContent = `跳格 ${state.skipped}｜停滯 ${state.stalls}`; }
    else if (plan.action === 'advance') { state.nextDue = plan.nextDue; show(plan.frame); }
  }
}

function buildGrid(run) {
  const grid = $('grid');
  grid.className = run.cameras.length > 4 ? 'cols3' : '';
  grid.replaceChildren(...run.cameras.map((cam) => {
    const fig = document.createElement('figure');
    const img = document.createElement('img');
    img.id = `img-${cam}`;
    img.alt = cam;
    const cap = document.createElement('figcaption');
    cap.id = `cap-${cam}`;
    cap.textContent = stampText(cam, null, run.fps);
    fig.append(img, cap);
    return fig;
  }));
}

async function selectRun(run) {
  setPlaying(false);
  cache.clear();
  state.run = run;
  state.skipped = 0; state.stalls = 0; state.shown = -1;
  const bad = run.status !== 'OK';
  $('unavailable').hidden = !bad;
  $('grid').hidden = bad;
  $('runinfo').textContent = `${run.label}｜run ${run.runId}｜${run.fps} fps｜${run.frames} 格｜${run.cameras.join('、')}`;
  for (const id of ['prev', 'next', 'play', 'scrub']) $(id).disabled = bad;
  if (bad) {
    $('unavailable').textContent = `UNAVAILABLE：${run.label} 的 safe 影像驗證未通過（${run.code}）。不顯示任何畫面。`;
    return;
  }
  buildGrid(run);
  $('scrub').max = run.frames - 1;
  await seek(0);
}

async function main() {
  let runs;
  try {
    runs = await (await fetch('/api/runs')).json();
  } catch {
    $('unavailable').hidden = false;
    $('unavailable').textContent = 'UNAVAILABLE：無法連線到本機 server。';
    return;
  }
  const sel = $('run');
  runs.forEach((r, i) => sel.add(new Option(`${r.key}${r.status === 'OK' ? '' : '（UNAVAILABLE）'}`, i)));
  sel.onchange = () => selectRun(runs[Number(sel.value)]);
  $('play').onclick = () => {
    if (state.playing) return setPlaying(false);
    if (state.frame >= state.run.frames - 1) seek(0).then(() => setPlaying(true));
    else setPlaying(true);
  };
  $('prev').onclick = () => { setPlaying(false); seek(stepFrame(state.target, -1, state.run.frames)); };
  $('next').onclick = () => { setPlaying(false); seek(stepFrame(state.target, 1, state.run.frames)); };
  $('scrub').oninput = (e) => { setPlaying(false); seek(Number(e.target.value)); };
  window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'SELECT' || !state.run || state.run.status !== 'OK') return;
    if (e.code === 'Space') { e.preventDefault(); $('play').click(); }
    else if (e.key === 'ArrowLeft') $('prev').click();
    else if (e.key === 'ArrowRight') $('next').click();
  });
  await selectRun(runs[0]);
  setInterval(() => tick(performance.now()), 40);
}

main();
