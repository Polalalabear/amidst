// #675: headless configuration controls only; model responses are verified separately.
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {writeFile} from 'node:fs/promises';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_MODULE).href);
const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const out=process.env.LIVE_QA_OUT, errors=[];
try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 page.on('pageerror',e=>errors.push(String(e)));
 await page.request.post('http://127.0.0.1:8791/config',{data:{advisor:'agent',advisor_model:'terra6.1'}});
 await page.goto('http://127.0.0.1:8791/?role=system',{waitUntil:'networkidle'});
 await page.locator('#llmon').waitFor();
 assert(await page.locator('#llmon').isChecked());
 assert.equal(await page.locator('#llmmode').inputValue(),'agent');
 assert.equal(await page.locator('#llmmodel').inputValue(),'terra6.1');
 await page.locator('#llmon').uncheck();
 await page.waitForTimeout(500);
 assert.equal((await (await page.request.get('http://127.0.0.1:8791/config')).json()).advisor,'off');
 await page.locator('#llmon').check();
 await page.waitForTimeout(500);
 await page.locator('#llmmode').selectOption('agent');
 await page.waitForTimeout(500);
 const config=await (await page.request.get('http://127.0.0.1:8791/config')).json();
 assert.equal(config.advisor,'agent');assert.equal(config.advisor_model,'terra6.1');
 assert(config.llm_switch.available);assert.equal(errors.length,0);
 await page.screenshot({path:`${out}/agent-enabled.png`,fullPage:true});
 await writeFile(`${out}/headless-switch.json`,JSON.stringify({headless:true,errors,config,checked:true},null,2));
 console.log('Agent switch off/on, terra6.1, 0 page errors: PASS');
} finally {await browser.close();}
