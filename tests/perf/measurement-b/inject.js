// Measurement B injector. Paste/evaluate this whole file in a page on the same origin as the workbench
// (e.g. http://127.0.0.1:8785/workbench-v2/). It defines window.__mb. Read-only: it only drives visible UI
// controls inside a fresh same-origin iframe per sample and reads the DOM. No product code is changed.
(() => {
  const VERSION = 'measurement-b/1';
  const EVENTS = {
    'B-05': {start: '13:00:00', end: '13:00:08'},
    'A4-1': {start: '14:00:00', end: '14:00:50'},
    'B4-1': {start: '14:10:00', end: '14:10:42'},
  };
  const TIMEOUT_MS = 20000;
  const results = [];
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // Poll with both rAF and a timer so a throttled/hidden pane still makes progress (timings are then unreliable;
  // env.paneVisible is recorded for that reason).
  function waitFor(win, fn, what, timeout = TIMEOUT_MS) {
    return new Promise((resolve, reject) => {
      const t0 = performance.now();
      let done = false;
      const step = () => {
        if (done) return;
        let v;
        try { v = fn(); } catch (e) { v = null; }
        if (v) { done = true; return resolve(v); }
        if (performance.now() - t0 > timeout) { done = true; return reject(new Error('TIMEOUT: ' + what)); }
        win.requestAnimationFrame(step);
        setTimeout(step, 8);
      };
      step();
    });
  }

  function env() {
    return {
      version: VERSION, href: location.href, ua: navigator.userAgent, dpr: devicePixelRatio,
      innerWidth, innerHeight, visibilityState: document.visibilityState,
      paneVisible: document.visibilityState === 'visible' && innerWidth > 0 && innerHeight > 0,
      elementTiming: !!(window.PerformanceObserver && PerformanceObserver.supportedEntryTypes.includes('element')),
    };
  }

  // Fresh iframe = reset point for every sample. Fixed 1440x900 layout, scaled down if the pane is smaller.
  async function openFrame(query) {
    const f = document.createElement('iframe');
    const scale = innerWidth > 0 && innerHeight > 0 ? Math.min(1, innerWidth / 1440, innerHeight / 900) : 1;
    f.style.cssText = `position:fixed;left:0;top:0;width:1440px;height:900px;border:0;z-index:2147483647;background:#000;transform-origin:0 0;transform:scale(${scale})`;
    f.src = '/workbench-v2/?' + query;
    document.body.appendChild(f);
    await new Promise((res, rej) => { f.onload = res; f.onerror = rej; setTimeout(() => rej(new Error('TIMEOUT: iframe load')), TIMEOUT_MS); });
    const win = f.contentWindow, doc = f.contentDocument;
    await waitFor(win, () => doc.querySelector('#ui-v1'), 'app shell');
    // Element Timing only reports images that carry the attribute when they load: tag every <img> as it appears.
    const tag = n => { if (n.nodeType === 1) { if (n.tagName === 'IMG') n.setAttribute('elementtiming', 'mb'); n.querySelectorAll?.('img').forEach(i => i.setAttribute('elementtiming', 'mb')); } };
    tag(doc.documentElement);
    new win.MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(tag))).observe(doc.documentElement, {childList: true, subtree: true});
    return {f, win, doc, close: () => f.remove()};
  }

  const setVal = (win, el, v) => { el.value = v; el.dispatchEvent(new win.Event('input', {bubbles: true})); el.dispatchEvent(new win.Event('change', {bubbles: true})); };
  const imgReady = i => i && !i.hidden && i.complete && i.naturalWidth > 0;
  // Approximate presentation time: two animation frames after decode (rAF granularity ~16.7 ms; needs a visible pane).
  const afterPaint = win => new Promise(r => { const t = setTimeout(() => r(win.performance.now()), 250); win.requestAnimationFrame(() => win.requestAnimationFrame(() => { clearTimeout(t); r(win.performance.now()); })); });
  async function decoded(imgs) { await Promise.all(imgs.map(i => i.decode().catch(() => {}))); }

  // Element-timing helper: native image-paint renderTime (ms on the frame's own timeline) for given image URLs.
  function paintObserver(win) {
    const seen = [];
    try {
      new win.PerformanceObserver(l => { for (const e of l.getEntries()) if (e.name === 'image-paint' && e.renderTime) seen.push({url: e.url, t: e.renderTime}); })
        .observe({type: 'element', buffered: true});
    } catch (e) { /* unsupported */ }
    return seen;
  }
  const mark = (doc, sel) => doc.querySelectorAll(sel).forEach(i => i.setAttribute('elementtiming', 'mb'));

  async function pickPerson(fr, panel) {
    const el = await waitFor(fr.win, () => fr.doc.querySelector(`${panel} [data-role=classes] [data-value=person]`), 'person class chip');
    el.click();
  }

  // ---- metric: search time -------------------------------------------------------------------------------
  // Fresh page -> enter -> case1 (query window open) -> person + times -> submit click -> all result-card
  // images decoded. Same operations as tests/browser/ui-redesign/real-e2e.mjs.
  async function sampleSearch(event) {
    const cfg = EVENTS[event], fr = await openFrame('run=' + event);
    try {
      const paints = paintObserver(fr.win);
      (await waitFor(fr.win, () => fr.doc.querySelector('#ui-enter'), 'enter button')).click();
      (await waitFor(fr.win, () => fr.doc.querySelector('[data-case=case1]'), 'case1 button')).click();
      await pickPerson(fr, '#ui-q-search');
      setVal(fr.win, fr.doc.querySelector('#ui-search-start'), cfg.start);
      setVal(fr.win, fr.doc.querySelector('#ui-search-end'), cfg.end);
      const sel = '#ui-case1 .ui-shot img';
      if (fr.doc.querySelectorAll(sel).length) throw new Error('RESULTS_ALREADY_PRESENT');
      const t0 = fr.win.performance.now();
      fr.doc.querySelector('#ui-search-submit').click();
      let n = 0;
      const imgs = await waitFor(fr.win, () => {
        const xs = [...fr.doc.querySelectorAll(sel)];
        if (!n && xs.length) { n = xs.length; mark(fr.doc, sel); }
        return n && xs.length === n && xs.every(imgReady) ? xs : null;
      }, 'result images');
      await decoded(imgs);
      const t1 = fr.win.performance.now(), t2 = await afterPaint(fr.win);
      await sleep(150);
      const urls = new Set(imgs.map(i => i.currentSrc));
      const rt = paints.filter(p => urls.has(p.url)).map(p => p.t);
      return {ms: t1 - t0, hits: n, raf_ms: t2 - t0, paint_ms: rt.length >= n ? Math.max(...rt) - t0 : null};
    } finally { fr.close(); }
  }

  // ---- shared: tracking helpers ---------------------------------------------------------------------------
  // The tracking response is not readable from outside the app (it keeps its own fetch reference), so segment
  // times come from the visible camera timeline: flex weights are fractions of the recording, #ui-scrub max is
  // its length in microseconds. Resolution is the 0.2 s source frame step.
  const scrubVal = fr => Number(fr.doc.querySelector('#ui-scrub')?.value);
  function seek(fr, t) { const el = fr.doc.querySelector('#ui-scrub'); el.value = String(t); el.dispatchEvent(new fr.win.Event('input', {bubbles: true})); }
  function segments(fr) {
    const els = [...fr.doc.querySelectorAll('#ui-camera-timeline .ui-tl-seg')];
    const max = Number(fr.doc.querySelector('#ui-scrub')?.max) || 0;
    const w = els.map(e => parseFloat(e.style.flexGrow || e.style.flex) || 0), sum = w.reduce((a, b) => a + b, 0) || 1;
    let acc = 0;
    return els.map((e, i) => { const a = acc / sum * max; acc += w[i]; return {el: e, kind: e.dataset.kind, cam: e.textContent.trim(), a, b: acc / sum * max, current: e.classList.contains('current')}; });
  }
  async function startTrack(fr, cfg) {
    await pickPerson(fr, '#ui-q-track');
    setVal(fr.win, fr.doc.querySelector('#ui-track-start'), cfg.start);
    if (segments(fr).some(s => s.kind === 'ON_CAMERA')) throw new Error('TIMELINE_ALREADY_PRESENT');
    const t0 = fr.win.performance.now();
    fr.doc.querySelector('#ui-track-submit').click();
    return t0;
  }
  const stampCam = fr => (fr.doc.querySelector('#ui-case2 .ui-stamp')?.textContent ?? '').split(' ·')[0].replace(/^CAM_/, '');
  const stage = fr => fr.doc.querySelector('#ui-case2 .ui-stage-img');

  // ---- metric: first-lock time ---------------------------------------------------------------------------
  // Track submit click -> first sighting's frame decoded on the stage (playhead inside the first ON_CAMERA segment).
  async function sampleLock(event) {
    const cfg = EVENTS[event], fr = await openFrame('run=' + event + '&screen=case2');
    try {
      const paints = paintObserver(fr.win);
      const t0 = await startTrack(fr, cfg);
      const first = await waitFor(fr.win, () => segments(fr).find(s => s.kind === 'ON_CAMERA'), 'tracking timeline');
      mark(fr.doc, '#ui-case2 .ui-stage-img');
      let seeked = false;
      const inFirst = () => { const v = scrubVal(fr); return v >= first.a - 1 && v < first.b + 1; };
      // The app normally parks the playhead inside the first sighting by itself; if it does not, seek (and say so).
      await sleep(0);
      if (!inFirst()) { seek(fr, Math.floor((first.a + first.b) / 2)); seeked = true; }
      const el = await waitFor(fr.win, () => inFirst() && stampCam(fr) === first.cam && imgReady(stage(fr)) && stage(fr), 'first sighting image');
      await decoded([el]);
      const t1 = fr.win.performance.now(), t2 = await afterPaint(fr.win);
      await sleep(150);
      const rt = paints.filter(p => p.url === el.currentSrc).map(p => p.t);
      return {ms: t1 - t0, seeked, camera: first.cam, raf_ms: t2 - t0, paint_ms: rt.length ? Math.max(...rt) - t0 : null};
    } finally { fr.close(); }
  }

  // ---- metric: camera-switch latency --------------------------------------------------------------------
  // 1x playback: the camera timeline marks the next camera's ON_CAMERA segment as current (t_cross) -> that
  // camera's stage image decoded. Untimed setup: start tracking, park the playhead 200 ms before the switch.
  async function sampleSwitch(event) {
    const cfg = EVENTS[event], fr = await openFrame('run=' + event + '&screen=case2');
    try {
      const paints = paintObserver(fr.win);
      await startTrack(fr, cfg);
      const segs = await waitFor(fr.win, () => { const s = segments(fr); return s.some(x => x.kind === 'ON_CAMERA') ? s : null; }, 'tracking timeline');
      const on = segs.map((s, i) => ({...s, i})).filter(s => s.kind === 'ON_CAMERA');
      const next = on.find(s => s.cam !== on[0].cam);
      if (!next) throw new Error('NO_CAMERA_SWITCH');
      const prev = on.filter(s => s.i < next.i).at(-1);
      await sleep(300);
      seek(fr, Math.max(prev.a, next.a - 200000));
      mark(fr.doc, '#ui-case2 .ui-stage-img');
      await waitFor(fr.win, () => stampCam(fr) === prev.cam && imgReady(stage(fr)), 'parked frame');
      const sp = fr.doc.querySelector('#ui-speed'); if (sp) setVal(fr.win, sp, '1');
      await sleep(200);
      const isCurrent = () => segments(fr).findIndex(s => s.current) === next.i;
      if (isCurrent()) throw new Error('ALREADY_IN_NEXT_SEGMENT');
      fr.doc.querySelector('#ui-play').click();
      let tCross = null;
      const el = await waitFor(fr.win, () => {
        if (tCross === null && isCurrent()) tCross = fr.win.performance.now();
        return tCross !== null && stampCam(fr) === next.cam && imgReady(stage(fr)) && stage(fr);
      }, 'next-camera image');
      await decoded([el]);
      const t1 = fr.win.performance.now(), t2 = await afterPaint(fr.win);
      const playBtn = fr.doc.querySelector('#ui-play'); if (playBtn.innerText.includes('❚')) playBtn.click();
      await sleep(150);
      const rt = paints.filter(p => p.url === el.currentSrc).map(p => p.t);
      return {ms: t1 - tCross, camera_from: prev.cam, camera_to: next.cam, switch_at_us: Math.round(next.a), raf_ms: t2 - tCross, paint_ms: rt.length ? Math.max(...rt) - tCross : null};
    } finally { fr.close(); }
  }

  const SAMPLERS = {search: sampleSearch, lock: sampleLock, switch: sampleSwitch};

  async function run({metric, event, n = 1, onProgress} = {}) {
    if (!SAMPLERS[metric]) throw new Error('metric must be one of ' + Object.keys(SAMPLERS));
    if (!EVENTS[event]) throw new Error('event must be one of ' + Object.keys(EVENTS));
    const e = env();
    for (let i = 0; i < n; i++) {
      const row = {metric, event, i: results.filter(r => r.metric === metric && r.event === event).length + 1, paneVisible: e.paneVisible, wallClock: new Date().toISOString()};
      try { Object.assign(row, await SAMPLERS[metric](event)); } catch (err) { row.error = String(err.message ?? err); }
      results.push(row);
      if (onProgress) onProgress(row);
    }
    return results.filter(r => r.metric === metric && r.event === event).slice(-n);
  }

  window.__mb = {
    VERSION, EVENTS, env, run, results,
    reset: () => { results.length = 0; },
    export: () => JSON.stringify({tool: VERSION, exportedAt: new Date().toISOString(), env: env(), rows: results}, null, 1),
  };
})();
