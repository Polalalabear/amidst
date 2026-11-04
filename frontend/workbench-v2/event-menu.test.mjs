import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {EVENTS,B05B_RECORDING_ID,validPort,parseConfig,available,embedOrigin,embedSrc,pageUrl,acceptViewMessage,acceptLayoutMessage,modeOf,defaultMode,mountEventMenu} from './event-menu.mjs';
import {trackingStatus,NOT_PRODUCED_TEXT} from './tracking-source.mjs';

const BASE='http://127.0.0.1:8766/workbench-v2/';
const cfgOf=search=>parseConfig(search);
const byId=id=>EVENTS.find(e=>e.id===id);

test('EVENTS lists every demo event with a one-line note; ids are unique',()=>{
  assert.deepEqual(EVENTS.map(e=>e.id),['wall','q1','b05b','b05a','a41','b41']);
  assert.equal(new Set(EVENTS.map(e=>e.id)).size,EVENTS.length);
  for(const e of EVENTS){assert.ok(e.note.length>10&&!e.note.includes('\n'));}
  assert.match(byId('a41').note,/frame 62＝12\.40 s.*frame 100＝20\.00 s/);
  assert.match(byId('b05b').note,/5\.10 s.*A.*5\.15 s.*B/);
  assert.match(byId('b05a').note,/5\.20 s.*A＋GAP/);
});

test('validPort accepts only 1024–65535 integers',()=>{
  assert.equal(validPort('8780'),8780);
  for(const bad of [null,'','80','65536','8780x','-1','1e4','0x1F90',' 8780','8780.5'])assert.equal(validPort(bad),null,String(bad));
});

test('parseConfig: ports, ev, embed and view are validated; unknown values fall back',()=>{
  const c=cfgOf('?ev=a41&ev_live=8765&ev_cx=8780&view=simple');
  assert.deepEqual(c,{ev:'a41',embed:false,view:'simple',mode:null,layout:'single',evmode:null,ports:{live:8765,cx:8780}});
  assert.deepEqual(cfgOf('?ev=zzz&ev_cx=evil&embed=1&view=x'),{ev:null,embed:true,view:null,mode:null,layout:'single',evmode:null,ports:{live:null,cx:null}});
  assert.equal(cfgOf('').ev,null);
});

test('embed URLs are always loopback http on a validated port; run and view are carried; availability follows the ports',()=>{
  const c=cfgOf('?ev_live=8765&ev_cx=8780');
  assert.equal(embedOrigin(byId('a41'),c),'http://127.0.0.1:8780');
  assert.equal(embedSrc(byId('a41'),c,'simple','view'),'http://127.0.0.1:8780/?embed=1&view=simple&run=A4-1');
  assert.equal(embedSrc(byId('b41'),c,'bogus'),'http://127.0.0.1:8780/?embed=1&view=system&run=B4-1');
  assert.equal(embedSrc(byId('b05a'),c,'system'),'http://127.0.0.1:8765/workbench-v2/?embed=1&view=system&evmode=view');assert.equal(embedSrc(byId('b05a'),c,'simple','track'),'http://127.0.0.1:8765/workbench-v2/?embed=1&view=simple&evmode=track');
  const none=cfgOf('');
  assert.equal(embedSrc(byId('a41'),none,'system'),null);
  assert.deepEqual(EVENTS.filter(e=>!available(e,none)).map(e=>e.id),['b05a','a41','b41']);
  assert.deepEqual(EVENTS.filter(e=>!available(e,c)).map(e=>e.id),[]);
  const evil=cfgOf('?ev_cx=8780@evil.test');assert.equal(evil.ports.cx,null);
});

test('pageUrl: page events keep sibling ports and view; recording only for B-05b; no other query leaks through',()=>{
  const c=cfgOf('?ev_live=8765&ev_cx=8780&view=simple&junk=1&recording=other');
  assert.equal(pageUrl(byId('wall'),c,BASE+'?junk=1'),`${BASE}?ev=wall&ev_live=8765&ev_cx=8780&view=simple&mode=view`);
  assert.equal(pageUrl(byId('b05b'),c,BASE),`${BASE}?ev=b05b&recording=${B05B_RECORDING_ID}&ev_live=8765&ev_cx=8780&view=simple&mode=track&layout=single`);
  assert.equal(pageUrl(byId('b05b'),c,BASE,{mode:'view'}),`${BASE}?ev=b05b&ev_live=8765&ev_cx=8780&view=simple&mode=view`);
  assert.equal(pageUrl(byId('b05b'),c,BASE,{mode:'track',layout:'multi'}).endsWith('&mode=track&layout=multi'),true);
  assert.equal(pageUrl(byId('q1'),cfgOf(''),BASE),`${BASE}?ev=q1&mode=view`);
});

test('acceptViewMessage: only the parent window on loopback with a known view',()=>{
  const parent={},other={};
  const msg=(o={})=>({source:parent,origin:'http://127.0.0.1:8766',data:{type:'amidst.view',view:'simple'},...o});
  assert.equal(acceptViewMessage(msg(),parent),'simple');
  assert.equal(acceptViewMessage(msg({source:other}),parent),null);
  assert.equal(acceptViewMessage(msg({origin:'http://evil.test'}),parent),null);
  assert.equal(acceptViewMessage(msg({origin:'http://127.0.0.1:8766.evil.test'}),parent),null);
  assert.equal(acceptViewMessage(msg({origin:'https://127.0.0.1:8766'}),parent),null);
  assert.equal(acceptViewMessage(msg({data:{type:'amidst.view',view:'x'}}),parent),null);
  assert.equal(acceptViewMessage(msg({data:{type:'other',view:'simple'}}),parent),null);
  assert.equal(acceptViewMessage(msg({data:null}),parent),null);
  assert.equal(acceptViewMessage(null,parent),null);
});

function fakeDoc(){
  const mk=tag=>{const n={tag,children:[],dataset:{},attrs:{},hidden:false,className:'',textContent:'',value:'',
    classList:{s:new Set(),add(...c){c.forEach(x=>this.s.add(x));},remove(...c){c.forEach(x=>this.s.delete(x));},toggle(c,on){on?this.s.add(c):this.s.delete(c);},contains(c){return this.s.has(c);}},
    append(...c){this.children.push(...c);},insertBefore(c){this.children.push(c);},setAttribute(k,v){this.attrs[k]=v;},getAttribute(k){return this.attrs[k]??null;},removeAttribute(k){delete this.attrs[k];},remove(){this.removed=true;}};
    n.contentWindow={posted:[],postMessage(m,o){this.posted.push([m,o]);}};return n;};
  const body=mk('body'),bar=mk('header'),main=mk('section');main.firstChild=null;
  bar.querySelector=()=>null;main.querySelector=()=>null;
  return {body,bar,createElement:mk,baseURI:BASE,querySelector:s=>({'.topbar':bar,'section.main':main}[s]??null)};
}
const findById=(doc,id)=>{const all=[...doc.bar.children,...(doc.querySelector('section.main').children)];const walk=n=>n.id===id?n:n.children.map(walk).find(Boolean);return all.map(walk).find(Boolean);};
function winOf(){return {parent:{},assigned:[],replaced:[],location:{assign(u){winOf.last.assigned.push(u);}},history:{replaceState(a,b,u){winOf.last.replaced.push(u);}},addEventListener(t,f){this.l=[t,f];},removeEventListener(){this.removed=true;}};}

test('mount: embedded events show the stage with the right iframe and pass the view; page events reload with params; unavailable ones cannot be chosen',()=>{
  const doc=fakeDoc(),win=winOf();winOf.last=win;win.location.assign=u=>win.assigned.push(u);
  const menu=mountEventMenu({doc,simple:null,url:`${BASE}?ev_live=8765&ev_cx=8780`,win});
  const select=findById(doc,'event-select'),stage=findById(doc,'event-stage'),frame=findById(doc,'event-frame');
  assert.equal(select.children.length,6);
  assert.equal(menu.current,'wall');assert.equal(stage.hidden,true);
  doc.body.dataset.view='simple';
  select.value='a41';select.onchange();
  assert.equal(stage.hidden,false);assert.equal(doc.body.classList.contains('ev-embed-active'),true);
  assert.equal(frame.getAttribute('src'),'http://127.0.0.1:8780/?embed=1&view=simple&run=A4-1');
  assert.equal(frame.attrs.sandbox,'allow-scripts allow-same-origin allow-forms');
  assert.match(win.replaced.at(-1),/ev=a41/);
  frame.onload();assert.deepEqual(frame.contentWindow.posted.at(-1),[{type:'amidst.view',view:'simple'},'http://127.0.0.1:8780']);
  select.value='b41';select.onchange();assert.match(frame.getAttribute('src'),/run=B4-1/);
  select.value='b05b';select.onchange();
  assert.equal(win.assigned.at(-1),`${BASE}?ev=b05b&recording=${B05B_RECORDING_ID}&ev_live=8765&ev_cx=8780&view=simple&mode=track&layout=single`);
});

test('mount: ports missing => embedded entries are disabled and cannot be selected',()=>{
  const doc=fakeDoc(),win=winOf();winOf.last=win;
  const menu=mountEventMenu({doc,simple:null,url:BASE,win});
  const select=findById(doc,'event-select');
  assert.deepEqual(select.children.filter(o=>o.disabled).map(o=>o.value),['b05a','a41','b41']);
  select.value='a41';select.onchange();
  assert.equal(menu.current,'wall');assert.equal(findById(doc,'event-stage').hidden,true);
});

test('mount: ?ev= restores the embedded event after a reload; ?embed=1 mounts no menu and obeys parent view messages only',()=>{
  const doc=fakeDoc(),win=winOf();winOf.last=win;
  const menu=mountEventMenu({doc,simple:null,url:`${BASE}?ev=a41&ev_cx=8780`,win});
  assert.equal(menu.current,'a41');assert.equal(findById(doc,'event-frame').getAttribute('src'),'http://127.0.0.1:8780/?embed=1&view=system&run=A4-1');
  const doc2=fakeDoc(),win2=winOf();winOf.last=win2;const set=[];
  mountEventMenu({doc:doc2,simple:{set:v=>set.push(v)},url:`${BASE}?embed=1&view=simple`,win:win2});
  assert.equal(findById(doc2,'event-select'),undefined);assert.equal(doc2.body.classList.contains('ev-embedded'),true);
  const [type,fn]=win2.l;assert.equal(type,'message');
  fn({source:win2.parent,origin:'http://127.0.0.1:8766',data:{type:'amidst.view',view:'simple'}});
  fn({source:{},origin:'http://127.0.0.1:8766',data:{type:'amidst.view',view:'system'}});
  assert.deepEqual(set,['simple']);
});

test('static: the page loads event-menu.css; the menu module makes no network request of its own',()=>{
  const html=readFileSync(new URL('index.html',import.meta.url),'utf8');
  assert.ok(html.includes('event-menu.css'));
  const src=readFileSync(new URL('event-menu.mjs',import.meta.url),'utf8');
  assert.ok(!/fetch\(|XMLHttpRequest|WebSocket/.test(src));
});

test('tracking source: only b05a / b05b have system tracking; A4-1 / B4-1 are NOT_PRODUCED and nothing is invented',()=>{
  assert.equal(trackingStatus('b05b').status,'AVAILABLE');assert.equal(trackingStatus('b05a').status,'AVAILABLE');
  for(const id of ['a41','b41']){assert.equal(trackingStatus(id).status,'NOT_PRODUCED');assert.equal(trackingStatus(id).reason,NOT_PRODUCED_TEXT);}
  assert.match(NOT_PRODUCED_TEXT,/#118.*CX-8/);
  assert.equal(trackingStatus('wall').status,'NONE');assert.equal(trackingStatus('q1').status,'NONE');
  assert.equal(defaultMode(byId('b05b')),'track');assert.equal(defaultMode(byId('a41')),'view');
  assert.equal(modeOf(byId('wall'),{mode:'track'}),'view');assert.equal(modeOf(byId('a41'),{mode:'track'}),'track');
  const c=cfgOf('?ev_cx=8780');
  assert.equal(embedSrc(byId('a41'),c,'system','track'),null);   // no frames are loaded for a tracking view that does not exist
  assert.match(embedSrc(byId('a41'),c,'system','view'),/run=A4-1/);
});

test('layout messages: parent loopback window only, known layouts only',()=>{
  const parent={},m=(o={})=>({source:parent,origin:'http://127.0.0.1:8766',data:{type:'amidst.layout',layout:'multi'},...o});
  assert.equal(acceptLayoutMessage(m(),parent),'multi');
  assert.equal(acceptLayoutMessage(m({source:{}}),parent),null);
  assert.equal(acceptLayoutMessage(m({origin:'http://evil.test'}),parent),null);
  assert.equal(acceptLayoutMessage(m({data:{type:'amidst.layout',layout:'x'}}),parent),null);
  assert.equal(acceptLayoutMessage(m({data:{type:'amidst.view',view:'simple'}}),parent),null);
});

function fakeStore(q2=null){const dispatched=[],subs=[];return {dispatched,subs,dispatch:a=>dispatched.push(a),getState:()=>({q2}),subscribe:f=>{subs.push(f);return()=>{};},setQ2(v){q2=v;subs.forEach(f=>f());}};}
const btn=(doc,id,key,val)=>findById(doc,id).children.find(b=>b.dataset[key]===val);

test('mount: complex event — 查看 shows the viewer; 追蹤 shows 尚未產生 and loads no frames; layout buttons are hidden',()=>{
  const doc=fakeDoc(),win=winOf();winOf.last=win;
  const menu=mountEventMenu({doc,simple:null,url:`${BASE}?ev=a41&ev_cx=8780&mode=view`,win});
  const frame=findById(doc,'event-frame'),notice=findById(doc,'ev-notice'),layout=findById(doc,'ev-layout');
  assert.equal(menu.mode,'view');assert.match(frame.getAttribute('src'),/run=A4-1/);assert.equal(notice.hidden,true);assert.equal(layout.hidden,true);
  btn(doc,'ev-mode','mode','track').onclick();
  assert.equal(menu.mode,'track');assert.equal(frame.getAttribute('src'),null);assert.equal(notice.hidden,false);
  assert.equal(notice.children[0].textContent,NOT_PRODUCED_TEXT);assert.equal(notice.children[1].textContent,'證據不足');
  assert.equal(layout.hidden,true);
  btn(doc,'ev-mode','mode','view').onclick();assert.match(frame.getAttribute('src'),/run=A4-1/);assert.equal(notice.hidden,true);
});

test('mount: B-05b — 追蹤 offers the single / multi layout through the store; 查看 reloads without the recording; wall has no 追蹤',()=>{
  const doc=fakeDoc(),win=winOf();winOf.last=win;const store=fakeStore({});
  const menu=mountEventMenu({doc,simple:null,store,url:`${BASE}?ev=b05b&recording=${B05B_RECORDING_ID}&mode=track&layout=multi`,win});
  assert.equal(menu.mode,'track');assert.equal(findById(doc,'ev-layout').hidden,false);
  assert.deepEqual(store.dispatched.at(-1),{type:'SET_PLAYBACK_MODE',value:'multi'});   // the chosen layout is applied once the recorded response is there
  btn(doc,'ev-layout','layout','single').onclick();assert.deepEqual(store.dispatched.at(-1),{type:'SET_PLAYBACK_MODE',value:'single'});
  btn(doc,'ev-mode','mode','view').onclick();assert.equal(win.assigned.at(-1),`${BASE}?ev=b05b&view=system&mode=view`);
  const doc2=fakeDoc(),win2=winOf();winOf.last=win2;
  mountEventMenu({doc:doc2,simple:null,store:fakeStore(),url:`${BASE}?ev=wall`,win:win2});
  assert.equal(btn(doc2,'ev-mode','mode','track').disabled,true);assert.equal(findById(doc2,'ev-layout').hidden,true);
});

test('mount: B-05a embed — mode and layout reach the iframe only as messages to the validated origin; embedded workbench applies them',()=>{
  const doc=fakeDoc(),win=winOf();winOf.last=win;
  const menu=mountEventMenu({doc,simple:null,store:fakeStore(),url:`${BASE}?ev=b05a&ev_live=8765&mode=track`,win});
  const frame=findById(doc,'event-frame');assert.match(frame.getAttribute('src'),/evmode=track/);
  btn(doc,'ev-layout','layout','multi').onclick();
  assert.deepEqual(frame.contentWindow.posted.at(-1),[{type:'amidst.layout',layout:'multi'},'http://127.0.0.1:8765']);
  btn(doc,'ev-mode','mode','view').onclick();assert.match(frame.getAttribute('src'),/evmode=view/);assert.equal(menu.mode,'view');
  const doc2=fakeDoc(),win2=winOf();winOf.last=win2;const st=fakeStore();
  mountEventMenu({doc:doc2,simple:null,store:st,url:`${BASE}?embed=1&evmode=view`,win:win2});
  assert.equal(doc2.body.classList.contains('ev-mode-view'),true);
  const fn=win2.l[1];
  fn({source:win2.parent,origin:'http://127.0.0.1:8766',data:{type:'amidst.layout',layout:'multi'}});
  fn({source:{},origin:'http://127.0.0.1:8766',data:{type:'amidst.layout',layout:'single'}});
  assert.deepEqual(st.dispatched,[{type:'SET_PLAYBACK_MODE',value:'multi'}]);
});
