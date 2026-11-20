import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {chromium} from '../core-preview/node_modules/playwright-core/index.mjs';
import {headlessMode} from '../../../scripts/browser_options.mjs';
import {checkEightCamWall} from './eightcam-check.mjs';

const root = process.env.AMIDST_ROOT_8CAM, out = process.env.AMIDST_TEST_EVIDENCE;
assert.ok(root && out, 'AMIDST_ROOT_8CAM and AMIDST_TEST_EVIDENCE required');
await mkdir(out, {recursive:true});
const backend = spawn('.venv/bin/python', ['-B','tests/browser/ui-redesign/eightcam_fixture.py',root],
  {env:process.env, stdio:['pipe','pipe','inherit']});
backend.stdin.on('error',()=>{});
const exited = once(backend,'exit'), lines = createInterface({input:backend.stdout});
let browser;
try {
  const first = await lines[Symbol.asyncIterator]().next();
  assert.equal(first.done,false,'backend must start');
  const {port,eightcam} = JSON.parse(first.value);
  assert.equal(eightcam.status,'READY');
  const base = 'http://127.0.0.1:'+port+'/workbench-v2/';
  browser = await chromium.launch({headless:headlessMode(),
    executablePath:process.env.CHROME_EXECUTABLE || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const results = [];
  for (const height of [900,1300]) {
    const page = await browser.newPage({viewport:{width:1440,height}});
    const errors = [], failed = [], checks = [];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('response',response=>{if(response.url().includes('/api/') && !response.ok()) failed.push(response.status());});
    for (const label of ['A4-1','B4-1']) {
      const sample = await checkEightCamWall(page,base,(ok,text)=>{assert.ok(ok,text);checks.push(text);},
        {required:true,label});
      await page.screenshot({path:resolve(out,label+'-8cam-'+height+'.png')});
      results.push({height,label,sample,checks:[...checks],errors:[...errors],failed:[...failed]});
      assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
    }
    await page.close();
  }
  await writeFile(resolve(out,'browser-receipt.json'),JSON.stringify(results,null,2)+'\n');
} finally {
  try { await browser?.close(); }
  finally {
    backend.stdin.end();
    const [code] = await exited;
    assert.equal(code,0,'owned fixture closes normally');
  }
}
