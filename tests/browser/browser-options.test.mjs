import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {headlessMode} from '../../scripts/browser_options.mjs';

test('only --headful or AMIDST_HEADFUL=1 enables a visible browser', () => {
  for (const env of [{}, {AMIDST_HEADFUL: '0'}, {AMIDST_HEADFUL: 'true'}, {HEADLESS: '0'}]) {
    assert.equal(headlessMode({argv: [], env}), true);
  }
  assert.equal(headlessMode({argv: ['--visible=true'], env: {}}), true);
  assert.equal(headlessMode({argv: ['--headful'], env: {}}), false);
  assert.equal(headlessMode({argv: [], env: {AMIDST_HEADFUL: '1'}}), false);
});

test('hardset smoke uses the shared launcher and two pages with failure cleanup', async () => {
  const source = await readFile(new URL('../../frontend/live-mode/measure/hardset_smoke.mjs', import.meta.url), 'utf8');
  assert.match(source, /const browser = await launch\(\)/);
  assert.equal(source.match(/await browser\.newPage\(\)/g)?.length, 2);
  assert.doesNotMatch(source, /newWindow|openWindow|HEADLESS|headless:\s*false|bringToFront/);
  assert.match(source, /finally\s*\{\s*await browser\.close\(\)/);
});

test('one headless browser owns A/B pages and closes on failure', {
  skip: process.env.AMIDST_BROWSER_TEST !== '1', timeout: 30000,
}, async () => {
  const output = process.env.AMIDST_BROWSER_EVIDENCE;
  assert.ok(output);
  assert.equal(headlessMode(), true);
  const {launch} = await import('../../frontend/live-mode/measure/lib.mjs');
  await mkdir(output, {recursive: true});
  const browser = await launch();
  let receipt;
  await assert.rejects(async () => {
    try {
      const a = await browser.newPage(), b = await browser.newPage();
      assert.equal(a.browser(), b.browser());
      assert.ok(browser.process().spawnargs.includes('--headless=new'));
      const session = await browser.target().createCDPSession();
      const version = await session.send('Browser.getVersion');
      assert.match(version.userAgent, /HeadlessChrome/);
      await a.setContent('<title>A test</title><main>A · 操作端測試</main>');
      await b.setContent('<title>B test</title><main>B · 系統端測試</main>');
      assert.equal(await a.title(), 'A test');
      assert.equal(await b.title(), 'B test');
      await a.screenshot({path: join(output, 'a.png')});
      await b.screenshot({path: join(output, 'b.png')});
      receipt = {headless: true, headless_switch: '--headless=new',
        user_agent: version.userAgent, same_browser: a.browser() === b.browser(),
        page_titles: [await a.title(), await b.title()]};
      throw new Error('EXPECTED_TEST_FAILURE');
    } finally {
      await browser.close();
    }
  }, /EXPECTED_TEST_FAILURE/);
  assert.equal(browser.connected, false);
  await writeFile(join(output, 'failure-cleanup.json'),
    JSON.stringify({...receipt, closed_after_failure: !browser.connected}, null, 2));
});
