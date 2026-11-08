// Admin page: pick the event the wall plays, tune playback, search the recorded footage. Uses the existing API only.
import {createQApi,FIXTURE_ORIGIN} from './q-api.mjs';
import {createSettingsStore,resolveRun,wallCameras,SETTINGS_KEY} from './monitor-room-model.mjs';
import {mountMonitorRoom} from './monitor-room-view.mjs';
import {mountTabs,mountOverview,mountSettings} from './admin-ui.mjs';
import {runCatalog,recordingCatalog,filterRuns,filterRecordings,parseTimecode,formatDuration,selectionFor,isSelected} from './admin.model.mjs';

const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
export async function bootstrap(root=document,{api:provided=null,storage=globalThis.localStorage}={}){
  const $=s=>root.querySelector(s),source=new URL(root.baseURI??'http://localhost/').searchParams.get('source')==='fixture'?FIXTURE_ORIGIN:'SERVER';
  const api=provided??createQApi({source}),settings=createSettingsStore(storage,{key:SETTINGS_KEY});
  const preview=createSettingsStore(null),wall=mountMonitorRoom($('#admin-preview'),{api,settings:preview});
  let boot=null;mountTabs(root);const overview=mountOverview($('#admin-overview'),{getBootstrap:()=>boot,storage});const settingsPane=mountSettings($('#admin-settings'),{getBootstrap:()=>boot,storage});
  const loaded=await api.bootstrap();await api.createSession();
  if(loaded.ok){boot=loaded.data;settingsPane.draw();overview.draw();}
  if(!loaded.ok){$('#admin-origin').textContent=`UNKNOWN · ${loaded.error?.code??'BOOTSTRAP'}`;return {settings,wall};}
  const data=loaded.data;$('#admin-origin').textContent=`${data.data_origin} · ${data.status}`;wall.setBootstrap(data);
  const runs=runCatalog(data),recs=recordingCatalog(data),kinds=[...new Set([...runs,...recs].map(x=>x.source_kind))];
  for(const k of kinds)$('#f-kind').append(Object.assign(el('option',k),{value:k}));
  const scopes=new Map();
  async function runOf(sel){
    if(sel?.kind==='recording'&&!scopes.has(sel.recording_id)){const r=await api.replay(sel.recording_id);const sc=r.ok?r.data?.resolved_scope:null;scopes.set(sel.recording_id,sc?{scene_id:sc.scene_id,run_id:sc.run_ids?.[0]}:null);}
    return resolveRun(data,sel,id=>scopes.get(id)??null);
  }
  function row(item){
    const tr=el('tr');tr.dataset.key=item.key;tr.setAttribute('aria-selected',String(isSelected(item,settings.get().selection)));
    const name=el('td');name.append(el('div',item.title));if(item.titleMissing)name.append(el('div','（尚無可讀名稱，顯示 ID）','note'));
    const kind=el('td',item.kind==='run'?'場景':'錄製回應'),src=el('td'),act=el('td'),pick=el('button','播放','ibtn primary'),see=el('button','預覽','ibtn');
    src.append(el('span',item.source_kind,'badge'));
    pick.onclick=()=>settings.set({selection:selectionFor(item),cameras:null,restart:settings.get().restart+1});
    see.onclick=()=>preview.set({selection:selectionFor(item),playing:true,restart:preview.get().restart+1});
    act.append(pick,' ',see);
    tr.append(name,kind,src,el('td',item.kind==='run'?String(item.camera_ids.length):'—'),
      el('td',item.kind==='run'?`${formatDuration(item.duration_us)} · ${item.fps??'?'} fps`:(item.recorded_at??'UNKNOWN')),act);
    return tr;
  }
  function drawRecords(){
    const from=parseTimecode($('#f-from').value);
    const items=[...filterRuns(runs,{scene:$('#f-scene').value,camera:$('#f-camera').value,source_kind:$('#f-kind').value,from_us:from}),
      ...($('#f-camera').value||$('#f-from').value?[]:filterRecordings(recs,{text:$('#f-scene').value,source_kind:$('#f-kind').value,from:$('#f-rec-from').value||null,to:$('#f-rec-to').value?$('#f-rec-to').value+'T23:59:59Z':null}))];
    $('#admin-record-rows').replaceChildren(...items.map(row));$('#f-count').textContent=`${items.length} 筆`;
    if(!items.length){const tr=el('tr'),td=el('td','沒有符合的紀錄');td.colSpan=6;tr.append(td);$('#admin-record-rows').append(tr);}
  }
  async function draw(){
    const s=settings.get(),sel=s.selection;
    $('#admin-event-rows').replaceChildren(...[...runs,...recs].map(row));
    $('#admin-current').textContent=!sel?'自動（鏡頭最多的來源）':sel.kind==='run'?`場景 ${sel.scene_id} · ${sel.run_id}`:`錄製 ${sel.recording_id}`;
    $('#admin-play').textContent=s.playing?'Ⅱ 暫停':'▶ 播放';$('#admin-speed').value=String(s.speed);$('#admin-loop').checked=s.loop;
    const run=await runOf(sel),box=$('#admin-cameras');box.replaceChildren();
    for(const c of run?.camera_ids??[]){const lab=el('label'),cb=el('input');cb.type='checkbox';cb.checked=!s.cameras||s.cameras.includes(c);
      cb.onchange=()=>{const now=new Set(wallCameras(run,settings.get().cameras));cb.checked?now.add(c):now.delete(c);const all=run.camera_ids.filter(x=>now.has(x));settings.set({cameras:all.length===run.camera_ids.length?null:all});};
      lab.append(cb,' '+c);box.append(lab);}
    drawRecords();
  }
  $('#admin-play').onclick=()=>settings.set({playing:!settings.get().playing});
  $('#admin-speed').onchange=e=>settings.set({speed:Number(e.target.value)});
  $('#admin-loop').onchange=e=>settings.set({loop:e.target.checked});
  $('#admin-restart').onclick=()=>settings.restart();
  $('#admin-auto').onclick=()=>settings.set({selection:null,cameras:null,restart:settings.get().restart+1});
  $('#admin-start').onchange=e=>{const us=parseTimecode(e.target.value);$('#admin-start-note').textContent=us===null&&e.target.value?'格式：m:ss 或秒數':'';if(us!==null||!e.target.value)settings.set({startUs:us??0,restart:settings.get().restart+1});};
  for(const id of ['#f-scene','#f-camera','#f-from','#f-rec-from','#f-rec-to','#f-kind'])$(id).addEventListener('input',drawRecords);
  settings.subscribe(draw);await draw();
  return {settings,wall,preview};
}
if(typeof document!=='undefined'&&document.getElementById('admin-root'))bootstrap();
