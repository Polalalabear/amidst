// F3 (#657) headless screenshots: Agent mode on the 8785 main tracking screen, playhead-consistent status, all-camera multi view,
// manual re-selection. Only visible UI controls. UI_QA_BASE_URL (default 8785) and UI_QA_OUTPUT choose server and output folder.
import {headlessMode} from '../../../scripts/browser_options.mjs';
import {ownedRuntime} from '../core-preview/owned-runtime.mjs';
import {pathToFileURL} from 'node:url';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const owned = ownedRuntime();
const {chromium} = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_MODULE ?? owned.playwrightModule).href);
const out = process.env.UI_QA_OUTPUT ?? owned.evidenceRoot + '/f3-screens'; await mkdir(out + '/screenshots', {recursive: true});
const base = new URL('/workbench-v2/', process.env.UI_QA_BASE_URL ?? 'http://127.0.0.1:8785').href;
const b = await chromium.launch({headless: headlessMode(), executablePath: process.env.CHROME_EXECUTABLE ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const results = [];
const capture = async (p, name, data = {}) => {
  const file = out + '/screenshots/' + name + '.png'; await p.screenshot({path: file, fullPage: true});
  const raw = await readFile(file);
  const r = {name, bytes: raw.length, sha256: createHash('sha256').update(raw).digest('hex'),
    title: await p.locator('.ui-track-title').innerText().catch(() => null), planNote: await p.locator('#ui-blind-end').innerText().catch(() => null),
    tiles: await p.locator('.ui-multi-tile').evaluateAll(ts => ts.map(t => [t.querySelector('.ui-cam-name')?.textContent, t.dataset.role])),
    journalAgent: await p.locator('#ui-journal-agent').innerText().catch(() => null), manual: await p.locator('#ui-manual-note').innerText().catch(() => null), ...data};
  results.push(r); console.log(JSON.stringify(r));
};
const seek = async (p, t) => { await p.locator('#ui-scrub').evaluate((el, t) => { el.value = String(t); el.dispatchEvent(new Event('input', {bubbles: true})); }, t); await p.waitForTimeout(1800); };
const SHOTS = {'A4-1': [3.5e6, 20e6, 45e6], 'B4-1': [16e6, 22e6, 35e6]};
try {
  for (const [run, times] of Object.entries(SHOTS)) {
    const ctx = await b.newContext({viewport: {width: 1440, height: 900}}), p = await ctx.newPage();
    await p.goto(base + '?run=' + run + '&screen=case2', {waitUntil: 'domcontentloaded'});
    await p.locator('#ui-track-mode').waitFor();
    if (await p.locator('#ui-track-mode').getAttribute('aria-checked') !== 'true') await p.locator('#ui-track-mode').click();
    await p.locator('#ui-q-track [data-role=classes] [data-value=person]').click();
    const tr = p.waitForResponse(r => r.url().endsWith('/api/q_core_track') && r.request().method() === 'POST', {timeout: 600000});
    await p.locator('#ui-track-submit').click(); const track = await (await tr).json();
    await writeFile(out + '/' + run + '-agent-track-response.json', JSON.stringify(track, null, 1));
    if (await p.locator('#ui-q-track').getAttribute('data-open') === 'true') await p.locator('#ui-q-track [aria-label=收起查詢窗]').click().catch(() => {});
    await p.locator('#ui-play').waitFor(); if ((await p.locator('#ui-play').innerText()).includes('❚❚')) await p.locator('#ui-play').click();
    for (const t of times) { await seek(p, t); await capture(p, `${run}-agent-single-${t / 1e6}s`, {agent: track.agent, t}); }
    await p.locator('[data-layout=multi]').click(); await p.waitForTimeout(800);
    for (const t of times.slice(0, 2)) { await seek(p, t); await capture(p, `${run}-agent-multi-${t / 1e6}s`, {t}); }
    await p.locator('[data-layout=single]').click(); await p.waitForTimeout(800);
    for (const t of times) {     // manual re-selection: the first candidate at a playhead that offers one
      await seek(p, t); const btn = p.locator('#ui-manual-list button').first();
      if (await btn.count() === 0) continue;
      const ref = await btn.getAttribute('data-track-ref');
      const mr = p.waitForResponse(r => r.url().endsWith('/api/q_core_track') && r.request().method() === 'POST', {timeout: 600000});
      await btn.click(); const manual = await (await mr).json(); await p.waitForTimeout(1500);
      await capture(p, `${run}-manual-${t / 1e6}s`, {manual_seed: manual.manual_seed ?? null, chosen: ref, t});
      break;
    }
    await ctx.close();
  }
  { // 8CAM: multi view shows all eight cameras
    const ctx = await b.newContext({viewport: {width: 1440, height: 900}}), p = await ctx.newPage();
    await p.goto(base + '?run=A4-1-8CAM&screen=case2', {waitUntil: 'domcontentloaded'});
    await p.locator('#ui-q-track [data-role=classes] [data-value=person]').click();
    const tr = p.waitForResponse(r => r.url().endsWith('/api/q_core_track') && r.request().method() === 'POST', {timeout: 600000});
    await p.locator('#ui-track-submit').click(); const track = await (await tr).json();
    await p.locator('[data-layout=multi]').click(); await p.waitForTimeout(2500);
    await capture(p, 'A4-1-8CAM-multi', {status: track.status});
    await ctx.close();
  }
} finally {
  await writeFile(out + '/f3-screens-results.json', JSON.stringify(results, null, 1)); await b.close();
}
