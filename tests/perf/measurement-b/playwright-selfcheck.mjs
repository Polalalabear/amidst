// Quick headless self-check of the injector (NOT the official measurement: the official runs use the built-in
// browser with its pane visible). Usage:
//   node playwright-selfcheck.mjs [--base http://127.0.0.1:8785] [--n 3] [--out /path/export.json] [--events B-05,A4-1,B4-1]
import {pathToFileURL, fileURLToPath} from 'node:url';
import {readFileSync, writeFileSync} from 'node:fs';
import {ownedRuntime} from '../../browser/core-preview/owned-runtime.mjs';
import {summarizeRows, toMarkdown} from './stats.mjs';

const argv = process.argv.slice(2), opt = (k, d) => { const i = argv.indexOf('--' + k); return i >= 0 ? argv[i + 1] : d; };
const base = opt('base', 'http://127.0.0.1:8785'), n = Number(opt('n', 3)), events = opt('events', 'B-05,A4-1,B4-1').split(',');
const owned = ownedRuntime();
const {chromium} = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_MODULE ?? owned.playwrightModule).href);
const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_EXECUTABLE ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
try {
  const page = await (await browser.newContext({viewport: {width: 1440, height: 900}, deviceScaleFactor: 1})).newPage();
  await page.goto(new URL('/workbench-v2/', base).href, {waitUntil: 'domcontentloaded'});
  await page.addScriptTag({content: readFileSync(fileURLToPath(new URL('./inject.js', import.meta.url)), 'utf8')});
  for (const event of events) for (const metric of ['search', 'lock', 'switch']) await page.evaluate(a => window.__mb.run(a), {metric, event, n});
  const json = await page.evaluate(() => window.__mb.export());
  if (opt('out')) writeFileSync(opt('out'), json);
  console.log(toMarkdown(summarizeRows(JSON.parse(json).rows)));
} finally { await browser.close(); }
