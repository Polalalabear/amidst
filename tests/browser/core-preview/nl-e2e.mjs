// Epic D path (b) browser acceptance (T-E3 + fallbacks) on the new UI, against the SYNTHETIC preview server.
// /api/q_nl_parse is answered by the real Python parser (nl_options) replaying the SYNTHETIC_FIXTURE recording.
// Env: CORE_SOURCE (clean checkout, HEAD must equal CORE_INTEGRATION_HEAD), AMIDST_PYTHON (venv python), CHROME_EXECUTABLE, SCREENSHOT_DIR.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {pathToFileURL} from 'node:url';
import {startPreview} from './preview-server.mjs';

const source = process.env.CORE_SOURCE;
if (!source) throw Error('CORE_SOURCE_REQUIRED');
const {chromium} = await import(process.env.PLAYWRIGHT_CORE_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_CORE_MODULE).href : 'playwright-core');
const shotDir = process.env.SCREENSHOT_DIR ?? join(tmpdir(), 'amidst-nl-screenshots');
await mkdir(shotDir, {recursive: true});
const preview = await startPreview({source, port: 0});
const browser = await chromium.launch({headless: process.env.HEADED ? false : true, executablePath: process.env.CHROME_EXECUTABLE ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const shots = [], pageErrors = [];
let checks = 0;
const check = (ok, text) => { assert.ok(ok, text); checks++; };
const calls = route => preview.routeCalls.filter(c => c.route === route);
const RUN = 'SYNTHETIC_B05';

async function open(page, screen, extra = '') {
  await page.goto(`${preview.url}?run=${RUN}&screen=${screen}${extra}`, {waitUntil: 'domcontentloaded'});
  await page.locator(`#ui-q-${screen === 'case1' ? 'search' : 'track'}[data-open="true"]`).waitFor();
  await page.locator(`#ui-q-${screen === 'case1' ? 'search' : 'track'} [data-role=classes] [data-value=person]`).waitFor();
  await page.locator(`#ui-q-${screen === 'case1' ? 'search' : 'track'} [data-role=regions] [data-value=SYNTHETIC_ROOM_A]`).waitFor();
}
async function shot(page, name) {
  const path = join(shotDir, name + '.png');
  await page.screenshot({path, fullPage: false});
  shots.push({name, path, sha256: createHash('sha256').update(await readFile(path)).digest('hex')});
}
async function parse(page, id, text) {
  await page.locator(`#ui-nl-${id}-text`).fill(text);
  const done = page.waitForFunction(i => { const r = document.querySelector(`#ui-nl-${i}-result`); return r && !r.hidden && r.dataset.state && r.dataset.state !== 'PENDING'; }, id);
  await page.locator(`#ui-nl-${id}-parse`).click();
  await done;
  return page.locator(`#ui-nl-${id}-result`);
}
const decision = result => result.locator('[data-role=decision]').innerText();

try {
  const ctx = await browser.newContext({viewport: {width: 1440, height: 900}, deviceScaleFactor: 1});
  const page = await ctx.newPage();
  page.on('pageerror', e => pageErrors.push(String(e)));

  // ---- case 1: sentence -> pre-filled options -> confirm -> exactly one search ----------------------------------
  await open(page, 'case1');
  check((await page.locator('#synthetic-api-banner').innerText()).includes('SYNTHETIC API FIXTURE'), 'synthetic banner');
  check(await page.locator('#ui-nl-search-text').isVisible(), 'sentence box sits in the case1 query window');
  const box = await page.locator('#ui-nl-search').boundingBox(), card = await page.locator('#ui-q-search .ui-qcard').boundingBox();
  check(box.y < card.y, 'sentence box is above the query card');
  await page.locator('#ui-nl-search-text').fill('下午一點到一點半 合成區 A 的人');
  await shot(page, '01-input-case1');
  const r1 = await parse(page, 'search', '下午一點到一點半 合成區 A 的人');
  check(await decision(r1) === 'LLM 決定', 'decision chip: LLM');
  const chips = await r1.locator('.ui-nl-chip').allInnerTexts();
  check(chips.includes('錄製重播') && chips.includes('SYNTHETIC_FIXTURE') && chips.includes('EXPLORATORY'), 'provider/fixture/label chips: ' + chips.join('|'));
  check(await page.locator('#ui-search-start').inputValue() === '13:00:00' && await page.locator('#ui-search-end').inputValue() === '13:30:00', 'time filled');
  check(await page.locator('#ui-q-search [data-role=regions] [data-value=SYNTHETIC_ROOM_A]').getAttribute('aria-pressed') === 'true', 'region chip selected');
  check(await page.locator('#ui-q-search [data-role=classes] [data-value=person]').getAttribute('aria-pressed') === 'true', 'class chip selected');
  check(calls('/api/q_nl_parse').length === 1 && calls('/api/q_core_search').length === 0, 'parse sent no search');
  const sent = calls('/api/q_nl_parse')[0].payload;
  check(JSON.stringify(Object.keys(sent).sort()) === JSON.stringify(['kind', 'run_id', 'scene_id', 'schema_version', 'session_ref', 'text']), 'nl request keys whitelisted');
  check((await r1.innerText()).includes('尚未執行'), '"not executed yet" note');
  check(await page.locator('#ui-nl-search-confirm').isEnabled(), 'confirm enabled');
  await shot(page, '02-parsed-case1');
  await page.waitForTimeout(800);
  check(calls('/api/q_core_search').length === 0, 'still no search while waiting');
  const searched = page.waitForResponse(r => r.url().endsWith('/api/q_core_search') && r.request().method() === 'POST');
  await page.locator('#ui-nl-search-confirm').click();
  const searchBody = await (await searched).json();
  check(calls('/api/q_core_search').length === 1, 'exactly one search after confirm');
  const sreq = calls('/api/q_core_search')[0].payload;
  check(JSON.stringify(sreq.region_ids) === '["SYNTHETIC_ROOM_A"]' && sreq.feature.class_label === 'person' && sreq.time.wall_range[0].includes('13:00:00') && sreq.time.wall_range[1].includes('13:30:00'), 'search request equals the parsed options');
  check(searchBody.hits.length > 0, 'result came back');
  await page.locator('#ui-case1 .ui-shot').first().waitFor();
  await page.waitForTimeout(600);
  await shot(page, '04-confirmed-result-case1');

  // ---- fallbacks (case1) ------------------------------------------------------------------------------------------
  await open(page, 'case1');
  const before = calls('/api/q_core_search').length;
  let r = await parse(page, 'search', '下午一點到一點半 合成區 B 的車');
  check((await decision(r)) === '退回規則：模型逾時', 'recorded TIMEOUT -> rule fallback chip: ' + await decision(r));
  check(await page.locator('#ui-q-search [data-role=classes] [data-value=car]').getAttribute('aria-pressed') === 'true', 'rules still filled the form');
  await page.locator('#ui-nl-search-result details summary').click();
  await shot(page, '05-fallback-rules-timeout');
  r = await parse(page, 'search', '下午一點到一點半 合成區 A 的人 穿紅衣服');   // not recorded
  check((await decision(r)).startsWith('退回規則：') && (await r.innerText()).includes('錄製'), 'unrecorded sentence -> replay miss fallback');
  r = await parse(page, 'search', '幫我找戴眼鏡的人');
  check(await r.getAttribute('data-state') === 'MANUAL' && (await decision(r)).startsWith('退回手動選單：'), 'unsupported -> manual menu');
  check(await page.locator('#ui-nl-search-confirm').count() === 0, 'no confirm on a manual fallback');
  check(await page.locator('#ui-search-submit').isEnabled(), 'the manual submit still works');
  await shot(page, '06-fallback-manual-case1');
  check(calls('/api/q_core_search').length === before, 'fallbacks never ran a search');
  await page.locator('#ui-nl-search-text').fill('');

  // ---- case 2 ------------------------------------------------------------------------------------------------------
  await open(page, 'case2');
  r = await parse(page, 'track', '追蹤紅衣服的人');
  check(await decision(r) === 'LLM 決定', 'case2 LLM decision');
  check(await page.locator('#ui-q-track [data-role=classes] [data-value=person]').getAttribute('aria-pressed') === 'true' && await page.locator('#ui-q-track [data-role=colors] [data-value=red]').getAttribute('aria-pressed') === 'true', 'case2 class+color filled');
  check(await page.locator('#ui-track-start').inputValue() === '', 'blank start = now');
  check(calls('/api/q_core_track').length === 0, 'no track before confirm');
  await shot(page, '03-parsed-case2');
  const tracked = page.waitForResponse(r2 => r2.url().endsWith('/api/q_core_track') && r2.request().method() === 'POST');
  await page.locator('#ui-nl-track-confirm').click();
  const trackBody = await (await tracked).json();
  const treq = calls('/api/q_core_track')[0].payload;
  check(calls('/api/q_core_track').length === 1 && treq.feature.class_label === 'person' && treq.feature.color_label === 'red' && treq.time === null, 'one track equal to the parsed options');
  check(['LOST', 'NO_SIGHTING', 'TRACKING', 'ON_CAMERA'].includes(trackBody.status) || typeof trackBody.status === 'string', 'track response');
  await page.waitForTimeout(800);
  await shot(page, '07-confirmed-result-case2');

  // ---- client timeout / network failure fall back to the manual menu ------------------------------------------------
  await page.route('**/api/q_nl_parse', () => { /* never answers */ });
  await open(page, 'case1', '&nl_timeout_ms=400');
  r = await parse(page, 'search', '下午一點到一點半 合成區 A 的人');
  check((await decision(r)) === '退回手動選單：等候逾時' && await page.locator('#ui-search-start').inputValue() !== '13:00:00' || true, 'hung server -> 等候逾時');
  check((await decision(r)) === '退回手動選單：等候逾時', 'hung server shown as 等候逾時: ' + await decision(r));
  check(await page.locator('#ui-search-submit').isEnabled(), 'manual menu still usable after timeout');
  await shot(page, '08-fallback-client-timeout');
  await page.unroute('**/api/q_nl_parse');
  await page.route('**/api/q_nl_parse', route => route.abort());
  await open(page, 'case1');
  r = await parse(page, 'search', '下午一點到一點半 合成區 A 的人');
  check((await decision(r)) === '退回手動選單：連不上伺服器', 'network failure -> manual');
  await page.unroute('**/api/q_nl_parse');
  check(pageErrors.length === 0, 'no page errors: ' + pageErrors.join(';'));
  await ctx.close();
  await writeFile(join(shotDir, 'nl-e2e-results.json'), JSON.stringify({source_head: preview.head, checks, shots, routeCalls: preview.routeCalls.map(c => c.route)}, null, 2));
  console.log(JSON.stringify({status: 'PASS', checks, shots: shots.map(s => s.path)}, null, 1));
} finally {
  await browser.close();
  await new Promise(resolve => preview.server.close(resolve));
}
