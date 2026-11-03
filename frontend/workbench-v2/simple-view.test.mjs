import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {VIEW_KEY,INSUFFICIENT_TEXT,resolveView,readStoredView,writeStoredView,evidenceInsufficient,mountSimpleView} from './simple-view.mjs';
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

// Minimal DOM double for mountSimpleView.
function fakeDoc(){
  const mk=(tag)=>{const n={tag,children:[],dataset:{},attrs:{},hidden:false,classList:new Set(),className:'',textContent:'',
    append(...c){this.children.push(...c);},insertBefore(c){this.children.push(c);},setAttribute(k,v){this.attrs[k]=v;},remove(){this.removed=true;}};
    n.classList.toggle=(c,on)=>{on?n.classList.add(c):n.classList.delete(c);};n.classList.remove=c=>n.classList.delete(c);return n;};
  const body=mk('body'),bar=mk('header'),main=mk('div'),open=mk('button');
  return {body,main,bar,createElement:mk,baseURI:'http://localhost/workbench-v2/',querySelector:s=>({'.topbar':bar,'#q-main-view':main,'#search-open':open}[s]??null)};
}
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
  for(const keep of ['#q-play','#q-scrub','#search-open','#view-seg','.q1-segment button','.q2-media','.q1-media'])assert.ok(!css.includes(`${keep}{display:none`)&&!css.split('\n').some(l=>l.split('{')[0].split(',').some(x=>x.trim()===`body.view-simple ${keep}`)),`must stay visible: ${keep}`);
});

test('wiring: stylesheet linked, toggle mounted from app.mjs, class names exist in the sources they hide',()=>{
  assert.match(read('index.html'),/href="simple-view\.css"/);
  assert.match(read('app.mjs'),/mountSimpleView\(\{doc:root,store,url\}\)/);
  const sources=['q2-view.mjs','q1-wall-view.mjs','monitor-room-view.mjs','track-map-view.mjs','q2-box-redraw.mjs','cam-stamp.mjs','style.css'].map(read).join('\n')+read('index.html');
  for(const name of ['q2-box','q1-box','q2-state','q2-candidates','q1-flag','q1-provenance','q1-coverage','mr-label','mr-state','mr-clock','tm-float','data-stamp','track-map-slot','q-timeline-slot','q5-slot','q-notice','legend'])assert.ok(sources.includes(name),`class/id vanished from sources: ${name}`);
});

test('isolation: simple-view.mjs imports no ground-truth, renderer, visibility or depth source',()=>{
  const src=read('simple-view.mjs');
  assert.deepEqual([...src.matchAll(/from '([^']+)'/g)].map(m=>m[1]),['./q2-session-model.mjs','./q-playback.mjs']);
  assert.doesNotMatch(src.replace(/^\/\/.*$/gm,''),/ground_truth|gt_private|renderer_trajectory|visibility|depth/i);
});
