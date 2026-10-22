import {buildAudit,loadExpectations,exportRecord,validateRecord,judge,reviewerPreference,CONTRACT_COMMIT} from './review-model.mjs';
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
export function mount({root,getState,subscribe,getRequests,seek}){
  root.replaceChildren();root.className='rv-panel';const heading=el('h3','逐項審核（只讀）'),name=el('input'),nameLabel=el('label','審核人'),load=el('input'),clear=el('button','卸載預期清單'),opened=el('input'),message=el('p','未載入預期清單；自動檢查是提示，不代替人工判定。','rv-message'),progress=el('p',undefined,'rv-progress'),list=el('div',undefined,'rv-items'),download=el('button','匯出審核 JSON');
  name.type='text';name.maxLength=120;name.setAttribute('aria-label','審核人');nameLabel.append(name);load.type='file';load.accept='.json';load.setAttribute('aria-label','載入本機預期清單');opened.type='file';opened.accept='.json';opened.setAttribute('aria-label','核對已匯出的審核檔');
  try{name.value=localStorage.getItem(reviewerPreference('').key)??'';}catch{}
  name.onchange=()=>{const pref=reviewerPreference(name.value);try{localStorage.setItem(pref.key,pref.value);}catch{}};
  root.append(heading,nameLabel,el('p','本機預期清單（不傳送）'),load,clear,el('p','核對既有審核檔'),opened,message,progress,download,list);
  let loaded=null,audit=null,items=[],samples=[],seenHashes=new Set(),currentKey='',generation=0,destroyed=false,selectedId=null,lastExport=null;
  load.onchange=async()=>{try{const file=load.files[0];if(!file)return;if(file.size>2000000)throw new Error('EXPECTED_FILE_TOO_LARGE');loaded=await loadExpectations(await file.text());currentKey='';await refresh(getState());}catch(e){message.textContent=`無法套用 · ${e.message}`;}};
  clear.onclick=()=>{loaded=null;load.value='';currentKey='';refresh(getState());};
  opened.onchange=async()=>{try{const file=opened.files[0];if(!file)return;if(file.size>4000000)throw new Error('REVIEW_RECORD_TOO_LARGE');const r=await validateRecord(await file.text());message.textContent=`核對通過 · ${r.review_id} · ${r.summary.items} 項（僅 hash／結構，不是人工驗收）`;}catch(e){message.textContent=`核對失敗 · ${e.message}`;}};
  const active=()=>items.filter(x=>audit?.output_hashes.includes(x.target.response_output_sha256));
  function draw(){list.replaceChildren();const rows=active();progress.textContent=`${rows.length} 項 · 已判定 ${rows.filter(x=>x.verdict!=='UNREVIEWED').length} · 仍有未審項目 ${rows.filter(x=>x.verdict==='UNREVIEWED').length} · 過期 ${items.length-rows.length}`;
    if(loaded)message.textContent=audit?.expectations.applied?'預期清單已套用；只提供本機對照提示。':'預期清單不適用於目前來源／pins；沒有套用。';
    for(const row of rows){const card=el('details',undefined,'rv-item'),summary=el('summary',`${row.target.kind} · ${row.verdict}`),controls=el('div',undefined,'rv-controls'),verdict=el('select'),note=el('textarea');
      for(const v of ['UNREVIEWED','PASS','FAIL','UNSURE']){const o=el('option',v);o.value=v;verdict.append(o);}verdict.value=row.verdict;verdict.setAttribute('aria-label',`判定 ${row.item_id}`);note.value=row.note;note.placeholder='FAIL 必填備註；不要複製預期清單內容';note.setAttribute('aria-label',`備註 ${row.item_id}`);
      const update=()=>{items=judge(items,row.item_id,verdict.value,note.value,new Date().toISOString());selectedId=row.item_id;progress.textContent=`${active().length} 項 · 已判定 ${active().filter(x=>x.verdict!=='UNREVIEWED').length}`;summary.textContent=`${row.target.kind} · ${verdict.value}`;};verdict.onchange=update;note.oninput=update;card.onfocusin=()=>{selectedId=row.item_id;};
      const pre=el('pre',JSON.stringify({target:row.target,auto_checks:row.auto_checks,expectation_refs:row.expectation_refs},null,2));controls.append(verdict,note);card.append(summary,pre,controls);
      if(Number.isSafeInteger(row.target.ref.source_time_us)){const jump=el('button','跳至來源時間');jump.onclick=()=>seek(row.target.ref.source_time_us);card.append(jump);}list.append(card);
    }
  }
  async function refresh(s){
    const responses=[s.q1,s.q2,s.q3].filter(Boolean);for(const response of responses)if(!seenHashes.has(response.output_sha256)){seenHashes.add(response.output_sha256);const request=getRequests().findLast(q=>q.schema_version===response.schema_version.replace('-response.','-request.')||(response.schema_version==='q-demo.q3-parse-response.v1'&&q.schema_version==='q-demo.q3-parse-request.v1'));if(request)samples.push({request,response});}
    const key=JSON.stringify([responses.map(x=>x.output_sha256),s.artifacts.decisions?.length,Object.keys(s.artifacts.evidence??{}),loaded?.file_sha256]);if(key===currentKey)return;currentKey=key;const version=++generation;
    const result=await buildAudit({responses,artifacts:s.artifacts,parameters:s.activeRun?.parameter_set??null,samples,loaded});if(destroyed||version!==generation)return;audit=result;
    const prior=new Map(items.map(x=>[x.item_id,x]));for(const row of result.items){const old=prior.get(row.item_id);prior.set(row.item_id,old?{...row,verdict:old.verdict,note:old.note,reviewed_at:old.reviewed_at}:row);}items=[...prior.values()];draw();
  }
  download.onclick=async()=>{try{if(!audit?.responses.length)throw new Error('RESPONSE_REQUIRED');const s=getState();lastExport=await exportRecord({audit,allItems:items,reviewer:name.value,reviewedAt:new Date().toISOString(),source:{data_origin:s.bootstrap?.data_origin,source_kind:s.recordedKind??s.activeRun?.source_kind},parameterSet:s.activeRun??{},contractCommit:s.bootstrap?.contract_commit??CONTRACT_COMMIT,uiCommit:s.bootstrap?.ui_commit??'UNKNOWN',loaded});
      const url=URL.createObjectURL(new Blob([JSON.stringify(lastExport,null,2)],{type:'application/json'})),a=el('a');a.href=url;a.download=`q1q5-review-${lastExport.content_sha256.slice(0,16)}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);message.textContent=`已匯出 ${lastExport.review_id} · 仍有未審項目 ${lastExport.summary.unreviewed}`;
    }catch(e){message.textContent=`無法匯出 · ${e.message}`;}};
  const onKey=e=>{if(/^(INPUT|TEXTAREA|SELECT)$/.test(e.target?.tagName)||e.target?.isContentEditable||e.ctrlKey||e.metaKey||e.altKey)return;const verdict={p:'PASS',f:'FAIL',u:'UNSURE'}[e.key.toLowerCase()];if(verdict&&selectedId){const row=items.find(x=>x.item_id===selectedId);if(row){items=judge(items,selectedId,verdict,row.note,new Date().toISOString());draw();}}};document.addEventListener('keydown',onKey);
  const unsub=subscribe(refresh);refresh(getState());return {destroy(){destroyed=true;generation++;unsub();document.removeEventListener('keydown',onKey);root.replaceChildren();}};
}
