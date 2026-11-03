import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {VIEW_KEY,INSUFFICIENT_TEXT,resolveView,readStoredView,writeStoredView,evidenceInsufficient,mountSimpleView,cellMissing,visibleFrameMissing} from './simple-view.mjs';
import {createStore,initialState} from './store.mjs';

const read=name=>readFileSync(new URL(name,import.meta.url),'utf8');
const memory=()=>{const m=new Map();return {getItem:k=>m.get(k)??null,setItem:(k,v)=>m.set(k,v),m};};
const broken={getItem(){throw new Error('denied');},setItem(){throw new Error('denied');}};
const q2={timeline:[
  {kind:'ON_CAMERA',range_us:[0,5150000],camera_id:'A',observation_ids:['o1']},
  {kind:'ON_CAMERA',range_us:[5150000,8000000],camera_id:'B',observation_ids:['o2']},
  {kind:'GAP',range_us:[8000000,9000000],camera_shown:'B',position:null},
]};
const at=(tUs,extra={})=>({...initialState(),task:'q2',q2,tUs,...extra});

test('resolveView: default is system; ?view= wins over storage; storage fills in; failures are swallowed',()=>{
  assert.equal(resolveView('',memory()),'system');
  assert.equal(resolveView('?view=simple',memory()),'simple');
  const st=memory();writeStoredView('simple',st);assert.equal(st.m.get(VIEW_KEY),'simple');
  assert.equal(resolveView('',st),'simple');
  assert.equal(resolveView('?view=system',st),'system');
  assert.equal(resolveView('?view=bogus',st),'simple');
  writeStoredView('bogus',st);assert.equal(readStoredView(st),'simple');
  assert.equal(resolveView('',broken),'system');assert.doesNotThrow(()=>writeStoredView('simple',broken));assert.equal(resolveView('',null),'system');
});

test('evidenceInsufficient: only GAP / UNKNOWN / error / MISSING frame; ON_CAMERA and non-q2 never',()=>{
  assert.equal(evidenceInsufficient(at(5100000)),false);   // A, on camera
  assert.equal(evidenceInsufficient(at(5150000)),false);   // switched to B on the system view's own segment boundary
  assert.equal(evidenceInsufficient(at(8500000)),true);    // GAP
  assert.equal(evidenceInsufficient(at(9500000)),true);    // outside every segment: UNKNOWN
  assert.equal(evidenceInsufficient(at(1000000,{error:{code:'FAIL_CLOSED'}})),true);
  assert.equal(evidenceInsufficient(at(1000000),{missingFrame:true}),true);
  assert.equal(evidenceInsufficient(at(1000000,{q2:null})),false);
  assert.equal(evidenceInsufficient({...initialState(),task:'q1'}),false);
  assert.equal(evidenceInsufficient(at(1000000,{q2:{timeline:null}})),true);   // malformed => fail closed
});

test('the notice reads the same segment the system view shows: it never moves the camera switch',()=>{
  // Insufficiency flips exactly where the system timeline flips, never earlier or later.
  const flips=[];let prev=null;for(let t=0;t<=9500000;t+=50000){const v=evidenceInsufficient(at(t));if(v!==prev)flips.push([t,v]);prev=v;}
  assert.deepEqual(flips,[[0,false],[8000000,true]]);
});

// Minimal DOM double for mountSimpleView. Cells are plain objects; `pending` models a q2 view still decoding inside a hidden [data-pending] wrapper.
function fakeDoc(){
  const mk=(tag)=>{const n={tag,children:[],dataset:{},attrs:{},hidden:false,classList:new Set(),className:'',textContent:'',
    append(...c){this.children.push(...c);},insertBefore(c){this.children.push(c);},setAttribute(k,v){this.attrs[k]=v;},remove(){this.removed=true;}};
    n.classList.toggle=(c,on)=>{on?n.classList.add(c):n.classList.delete(c);};n.classList.remove=c=>n.classList.delete(c);return n;};
  const body=mk('body'),bar=mk('header'),main=mk('div'),open=mk('button');
  const cells={q1:[],q2:[],wall:[]},slots={'#q2-slot':mk('div'),'#q1-slot':mk('div'),'#monitor-room-slot':mk('div')};
  const cell=(status,text='',pending=false)=>({dataset:{status},textContent:text,pending,querySelector:()=>null});
  return {body,main,bar,cells,cell,createElement:mk,baseURI:'http://localhost/workbench-v2/',
    querySelector:s=>({'.topbar':bar,'#q-main-view':main,'#search-open':open,...slots}[s]??null),
    querySelectorAll:s=>s.startsWith('#monitor-room-slot')?cells.wall:s.startsWith('#q1-slot')?cells.q1:s.startsWith('#q2-slot')?cells.q2.filter(c=>!s.includes(':not([data-pending])')||!c.pending):[]};
}
function fakeObserver(){const seen=[];const saved=globalThis.MutationObserver;globalThis.MutationObserver=class{constructor(cb){this.cb=cb;seen.push(this);}observe(){}disconnect(){}};return {seen,restore(){globalThis.MutationObserver=saved;}};}
test('mount: switch toggles body.view-simple without touching the store; notice only in simple view when evidence is insufficient',()=>{
  const doc=fakeDoc(),store=createStore(at(8500000)),st=memory(),before=store.getState();
  const v=mountSimpleView({doc,store,url:'http://localhost/workbench-v2/',storage:st});
  const notice=doc.main.children.find(c=>c.id==='simple-notice');
  assert.equal(v.view,'system');assert.equal(doc.body.classList.has('view-simple'),false);assert.equal(notice.hidden,true);
  v.set('simple');assert.equal(doc.body.classList.has('view-simple'),true);assert.equal(notice.hidden,false);assert.equal(notice.textContent,INSUFFICIENT_TEXT);assert.equal(st.m.get(VIEW_KEY),'simple');
  store.dispatch({type:'SET_T_US',tUs:5100000});assert.equal(notice.hidden,true);
  v.set('system');assert.equal(doc.body.classList.has('view-simple'),false);assert.equal(notice.hidden,true);
  assert.equal(store.getState().q2,before.q2);   // same data object: no reload
  v.destroy();
});
test('mount: ?view=simple opens simple view directly; toggling does not reset playback position',()=>{
  const doc=fakeDoc(),store=createStore(at(5150000));
  const v=mountSimpleView({doc,store,url:'http://localhost/workbench-v2/?view=simple',storage:memory()});
  assert.equal(v.view,'simple');assert.equal(doc.body.classList.has('view-simple'),true);
  v.set('system');v.set('simple');assert.equal(store.getState().tUs,5150000);
  v.destroy();
});

// True when some simple-view rule removes `sel` itself (display:none / visibility:hidden), ignoring pseudo-element rules.
const removes=sel=>read('simple-view.css').replace(/\/\*[\s\S]*?\*\//g,'').split('}').some(rule=>rule.split('{')[0].split(',').some(x=>x.trim()===`body.view-simple ${sel}`)&&/display:none|visibility:hidden/.test(rule.split('{')[1]??''));
test('simple view CSS hides every annotation the system view draws',()=>{
  const css=read('simple-view.css').split('\n').filter(l=>l.startsWith('body.view-simple')).join('\n');
  const hidden=sel=>css.split('}').some(rule=>rule.split('{')[0].split(',').some(x=>x.trim()===`body.view-simple ${sel}`)&&/display:none|content:none/.test(rule));
  const annotations=[ // OBS boxes, source-time labels, candidate/evidence column, state badges, 俯視圖, bands/curves, log, legend, text marks
    '.q2-box','.q1-box','.q2-state','.q2-candidates','.q2-camera>h3','.q1-card>h3','.q1-flag','.q1-provenance','.q1-coverage','.q1-segment>span',
    '#track-map-slot','.tm-float','#track-map-toggle','#q-timeline-slot','#q5-slot','#q-notice','.legend','.synth','aside.panel','#q3-slot',
    '.mr-label','.mr-state','.mr-clock','.mr-head','.mr-meta','.mr-stats','#q-time','#q-wall','#q-stop','#q-manual-controls','.icons','.vhead',
    '[data-stamp]::before',
  ];
  for(const sel of annotations)assert.ok(hidden(sel),`not hidden in simple view: ${sel}`);
  // The controls needed to pick a target and to play must stay visible.
  for(const keep of ['#q-play','#q-scrub','#search-open','#view-seg','.q1-segment button','.q2-media','.q1-media','.mr-media'])assert.ok(!removes(keep),`must stay visible: ${keep}`);
});

test('wiring: stylesheet linked, toggle mounted from app.mjs, class names exist in the sources they hide',()=>{
  assert.match(read('index.html'),/href="simple-view\.css"/);
  assert.match(read('app.mjs'),/mountSimpleView\(\{doc:root,store,url\}\)/);
  const sources=['q2-view.mjs','q1-wall-view.mjs','monitor-room-view.mjs','track-map-view.mjs','q2-box-redraw.mjs','cam-stamp.mjs','style.css'].map(read).join('\n')+read('index.html');
  for(const name of ['q2-box','q1-box','q2-state','q2-candidates','q1-flag','q1-provenance','q1-coverage','mr-label','mr-state','mr-clock','tm-float','data-stamp','track-map-slot','q-timeline-slot','q5-slot','q-notice','legend'])assert.ok(sources.includes(name),`class/id vanished from sources: ${name}`);
});

test('isolation: simple-view.mjs imports only the two system-view modules the q2 view itself uses',()=>{
  const src=read('simple-view.mjs');
  assert.deepEqual([...src.matchAll(/from '([^']+)'/g)].map(m=>m[1]),['./q2-session-model.mjs','./q-playback.mjs']);
});

test('cellMissing: MISSING status or fallback text without a picture; loading placeholders and pictures never',()=>{
  const c=(status,text,img=false)=>({dataset:{status},textContent:text,querySelector:()=>img?{}:null});
  assert.equal(cellMissing(c('MISSING','')),true);
  assert.equal(cellMissing(c(undefined,'MISSING · 沒有可用的 RGB')),true);
  assert.equal(cellMissing(c(undefined,'UNKNOWN · 無代表畫面')),true);
  assert.equal(cellMissing(c(undefined,'MISSING · 代表畫面尚未取得')),false);
  assert.equal(cellMissing(c(undefined,'等待畫面…')),false);
  assert.equal(cellMissing(c('READY','',true)),false);
  assert.equal(cellMissing(c(undefined,'MISSING',true)),false);
});

test('Q1 and the wall: a MISSING cell shows the notice; no stale q2 GAP is read once the wall is on or the task is q1',()=>{
  const q1={...initialState(),task:'q1'};
  assert.equal(evidenceInsufficient(q1),false);
  assert.equal(evidenceInsufficient(q1,{missingFrame:true}),true);
  assert.equal(evidenceInsufficient({...q1,error:{code:'X'}}),true);
  const staleGap=at(8500000);                       // q2 state sitting in the store at a GAP time
  assert.equal(evidenceInsufficient(staleGap),true);
  assert.equal(evidenceInsufficient(staleGap,{wallVisible:true}),false);             // wall on: the old q2 state is ignored
  assert.equal(evidenceInsufficient(staleGap,{wallVisible:true,missingFrame:true}),true);
  assert.equal(evidenceInsufficient({...staleGap,task:'q1'}),false);                 // back on q1: ignored too
  const doc=fakeDoc();doc.cells.q1.push(doc.cell('MISSING'));doc.cells.wall.push(doc.cell('READY'));
  assert.equal(visibleFrameMissing(doc,{task:'q1',wallVisible:false}),true);
  assert.equal(visibleFrameMissing(doc,{task:'q1',wallVisible:true}),false);         // only the visible screen is read
  assert.equal(visibleFrameMissing(doc,{task:'q2',wallVisible:false}),false);
});

test('mount: Q1 MISSING cell and wall MISSING tile raise the notice; leaving the wall does not keep a stale q2 GAP notice',()=>{
  const obs=fakeObserver();
  try{
    const doc=fakeDoc(),store=createStore({...at(8500000),task:'q1'});
    const v=mountSimpleView({doc,store,url:'http://localhost/?view=simple',storage:memory()});
    const notice=doc.main.children.find(c=>c.id==='simple-notice');
    assert.equal(notice.hidden,true);
    doc.cells.q1.push(doc.cell('MISSING','MISSING · 沒有可用的 RGB'));v.refresh();assert.equal(notice.hidden,false);
    doc.cells.q1.length=0;v.refresh();assert.equal(notice.hidden,true);
    store.dispatch({type:'SET_TASK',task:'q2'});assert.equal(notice.hidden,false);   // q2 GAP at 8.5 s
    doc.body.dataset.monitorWall='on';obs.seen[0].cb();assert.equal(notice.hidden,true);   // wall on: stale GAP ignored
    doc.cells.wall.push(doc.cell('MISSING'));obs.seen[0].cb();assert.equal(notice.hidden,false);
    v.destroy();
  }finally{obs.restore();}
});

test('mount: paused q2 view swaps a MISSING cell for a READY one -> notice clears on the commit mutation alone; pending cells are ignored',()=>{
  const obs=fakeObserver();
  try{
    const doc=fakeDoc(),store=createStore(at(1000000));        // on camera: only a MISSING frame can raise the notice
    const v=mountSimpleView({doc,store,url:'http://localhost/?view=simple',storage:memory()});
    const notice=doc.main.children.find(c=>c.id==='simple-notice');
    const old=doc.cell('MISSING','MISSING · 沒有可用的 RGB');doc.cells.q2.push(old);obs.seen[0].cb();assert.equal(notice.hidden,false);
    const next=doc.cell('READY','',true);doc.cells.q2.push(next);obs.seen[0].cb();assert.equal(notice.hidden,false);   // replacement still hidden/pending: the old frame is what is visible
    doc.cells.q2.splice(0,1);next.pending=false;obs.seen[0].cb();                                                         // commit: old removed, [data-pending] cleared, no store dispatch
    assert.equal(notice.hidden,true);
    const hiddenMissing=doc.cell('MISSING','',true);doc.cells.q2.length=0;doc.cells.q2.push(doc.cell('READY'),hiddenMissing);obs.seen[0].cb();
    assert.equal(notice.hidden,true);                                                                                     // a still-pending MISSING cell is not visible
    v.destroy();
  }finally{obs.restore();}
});

test('simple view CSS also hides raw fallback text in frame cells and q2 message paragraphs',()=>{
  const css=read('simple-view.css');
  assert.match(css,/body\.view-simple \.q2-media,body\.view-simple \.q1-media,body\.view-simple \.mr-media\{font-size:0;color:transparent\}/);
  assert.match(css,/body\.view-simple \.q2-session>p[^{]*\{display:none\}/);
  for(const cell of ['.q2-media','.q1-media','.mr-media'])assert.ok(!removes(cell),`the picture cell itself must stay: ${cell}`);
});
