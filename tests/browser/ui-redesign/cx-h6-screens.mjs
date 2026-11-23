// CX-H6: scoped headless smoke through visible controls. Names/metadata mark mock runs.
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {headlessMode} from '../../../scripts/browser_options.mjs';
const {chromium} = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_MODULE).href);
const output = process.env.UI_QA_OUTPUT;
assert(output && process.env.UI_QA_BASE_URL);
await mkdir(output, {recursive:true});
const mock = process.env.CX_H6_MOCK === '1', replay = process.env.CX_H6_REPLAY === '1';
const browser = await chromium.launch({headless:headlessMode(),executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const results = [], failures=[];
async function capture(page, name, doc) {
  const file = `${output}/${mock?'mock-':replay?'replay-':''}${name}.png`;
  await page.screenshot({path:file,fullPage:true});
  const data=await readFile(file);
  results.push({name,mock,replay,file:file.split('/').at(-1),bytes:data.length,sha256:createHash('sha256').update(data).digest('hex'),
    status:doc.status,agent:doc.agent??null,manual_seed:doc.manual_seed??null,
    title:await page.locator('.ui-track-title').innerText(),
    tiles:await page.locator('.ui-multi-tile').count(),
    agentText:await page.locator('#ui-journal-agent').innerText().catch(()=>null)});
}
async function seek(page,t) {
  await page.locator('#ui-scrub').evaluate((el,t)=>{el.value=String(t);el.dispatchEvent(new Event('input',{bubbles:true}));},t);
  await page.waitForTimeout(1000);
}
try {
  for (const [label,cameras] of [['A4-1-8CAM',8],['B-05',2]]) {
    const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
    page.on('pageerror',e=>failures.push(String(e)));
    await page.goto(`${process.env.UI_QA_BASE_URL}/workbench-v2/?run=${label}&screen=case2`,{waitUntil:'domcontentloaded'});
    await page.locator('#ui-q-track [data-role=classes] [data-value=person]').click();
    const submit=async()=>{const response=page.waitForResponse(r=>r.url().endsWith('/api/q_core_track')&&r.request().method()==='POST',{timeout:600000});await page.locator('#ui-track-submit').click();return (await response).json();};
    const rule=await submit();
    assert.notEqual(rule.status,'UNKNOWN');assert(rule.sightings.length>0);
    await writeFile(`${output}/${label}-rule.json`,JSON.stringify(rule,null,2));
    await page.locator('[data-layout=multi]').click();
    await seek(page,label==='A4-1-8CAM'?20e6:3.2e6);
    await capture(page,`${label}-rule-multi`,rule);
    assert.equal(await page.locator('.ui-multi-tile').count(),cameras);
    if(await page.locator('#ui-q-track').getAttribute('data-open')!=='true')await page.locator('[aria-label="開關查詢窗"]').click();
    if(await page.locator('#ui-track-mode').getAttribute('aria-checked')!=='true')await page.locator('#ui-track-mode').click();
    const agent=await submit();
    assert.equal(agent.agent.available,true);assert(agent.agent.decisions>0);
    await writeFile(`${output}/${label}-agent.json`,JSON.stringify(agent,null,2));
    await seek(page,label==='A4-1-8CAM'?20e6:3.2e6);
    await capture(page,`${label}-agent-multi`,agent);
    const alternate=agent.sightings.find(s=>s.selected_for_single_view===false);
    assert(alternate,`${label}: expected manual target candidate`);
    await page.locator('[data-layout=single]').click();
    await seek(page,alternate.range_us[0]);
    const btn=page.locator('#ui-manual-list button').first();
    assert(await btn.count(),`${label}: expected manual target button`);
    // Re-selection retains the selected mode. The server's per-run call cap remains in force.
    const response=page.waitForResponse(r=>r.url().endsWith('/api/q_core_track')&&r.request().method()==='POST',{timeout:600000});
    await btn.click();const manual=await(await response).json();
    assert.equal(manual.manual_seed.applied,true);
    await writeFile(`${output}/${label}-manual.json`,JSON.stringify(manual,null,2));
    await page.waitForTimeout(1000);await capture(page,`${label}-manual`,manual);
    await context.close();
  }
  assert.deepEqual(failures,[]);
} finally {
  await writeFile(`${output}/RESULTS.json`,JSON.stringify({mock,replay,validation_mode:replay?'EXACT_REQUEST_SHA_REPLAY':mock?'MOCK':'LIVE_OPENAI',paid_calls:replay||mock?0:null,source_receipts:replay?['../A4-1-8CAM-agent.json','../B-05-agent.json','../usage/usage.jsonl']:[],results,failures},null,2));
  await browser.close();
}
console.log(JSON.stringify({mock,replay,screenshots:results.length,failures}));
