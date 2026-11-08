// DOM-level checks of mountUi (ui-shell.mjs) in a real browser against the synthetic preview server (P3-4 of #487 review).
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {startPreview} from '../core-preview/preview-server.mjs';
const source=process.env.CORE_SOURCE;if(!source)throw Error('CORE_SOURCE_REQUIRED');
const {chromium}=await import(process.env.PLAYWRIGHT_CORE_MODULE?pathToFileURL(process.env.PLAYWRIGHT_CORE_MODULE).href:'playwright-core');
const preview=await startPreview({source,port:0}),browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];let checks=0;page.on('pageerror',e=>errors.push(String(e)));
const check=(ok,msg)=>{assert.ok(ok,msg);checks++;console.log(JSON.stringify({check:checks,message:msg}));};
try{
 await page.goto(preview.url,{waitUntil:'domcontentloaded'});await page.locator('#ui-enter').waitFor();
 check(await page.locator('#ui-v1').count()===1&&await page.locator('body[data-ui=v1]').count()===1,'ui root mounted and body marked data-ui=v1');
 check(await page.locator('#ui-cover').getAttribute('data-on')==='true','cover layer is on at start');
 await page.locator('#ui-enter').click();await page.waitForTimeout(400);check(await page.locator('#ui-cover').getAttribute('data-on')==='false','cover layer off after enter');
 for(const c of ['case1','case2','case3'])check(await page.locator(`[data-case=${c}]`).isVisible(),'chooser offers '+c);
 await page.locator('[data-case=case1]').click();await page.locator('#ui-case1').waitFor();
 check(await page.locator('#ui-case1').isVisible()&&!(await page.locator('#ui-case2').isVisible()),'case1 visible, case2 hidden');
 const isOpen=()=>page.locator('#ui-q-search').getAttribute('data-open').then(v=>v==='true');if(await isOpen()){await page.locator('.ui-burger').click();check(!(await isOpen()),'burger closes open query window');}
 await page.locator('.ui-burger').click();check(await isOpen(),'burger opens query window');
 await page.keyboard.press('Escape');check(await page.locator('#ui-q-search').getAttribute('data-open')!=='true','Escape closes query window');
 const html=await page.locator('#ui-v1').innerHTML();check(!/ground_truth|gt_private|visibility_ref/.test(html),'no GT field names in rendered DOM');
 await page.goto(preview.url+'?ui=legacy',{waitUntil:'domcontentloaded'});await page.waitForTimeout(500);
 check(await page.locator('#ui-v1').count()===0&&await page.locator('body[data-ui=v1]').count()===0,'?ui=legacy removes the new UI root');
 check(errors.length===0,'no page errors');console.log(JSON.stringify({status:'PASS',checks}));
}finally{await browser.close();await new Promise((d,r)=>preview.server.close(e=>e?r(e):d()));}
