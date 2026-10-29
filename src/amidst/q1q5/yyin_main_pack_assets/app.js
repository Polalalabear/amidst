"use strict";
(() => {
  const resultReasons = globalThis.PACK_DATA.keywords;
  const blank = id => ({id, text:"", cls:"", target:"", color:"", start:"", end:"", camera:"", ask:"", result:"", reason:"", explanation:"", unknown:false, evidence:{}});
  function csvEncode(rows) {
    return "\ufeff" + rows.map(row => row.map(value => {
      const s = String(value ?? "");
      return /[",\r\n]/.test(s) ? '"' + s.replaceAll('"', '""') + '"' : s;
    }).join(",")).join("\r\n") + "\r\n";
  }
  function csvDecode(raw) {
    raw = raw.replace(/^\ufeff/, "");
    const rows = []; let row=[], cell="", quoted=false, afterQuote=false;
    for (let i=0;i<raw.length;i++) {
      const c=raw[i];
      if (quoted) {
        if (c === '"') { if (raw[i+1] === '"') {cell+='"';i++;} else {quoted=false;afterQuote=true;} }
        else cell+=c;
      } else if (c === '"') {
        if (cell || afterQuote) throw Error("CSV引號格式不正確");
        quoted=true;
      } else if (c === ',' || c === '\n' || c === '\r') {
        row.push(cell); cell="";afterQuote=false;
        if (c !== ',') { if (c==='\r' && raw[i+1]==='\n') i++;rows.push(row);row=[]; }
      } else {
        if (afterQuote) throw Error("CSV引號後有多餘字元");
        cell+=c;
      }
    }
    if (quoted) throw Error("CSV引號未關閉");
    if (cell || row.length || afterQuote) {row.push(cell);rows.push(row);}
    return rows;
  }
  function scopedCameras(row,data) {
    const explicit = data.cameras.filter(c => row.camera.includes(c.camera_id));
    return explicit.length ? explicit : data.cameras;
  }
  function notes(row,data) {
    const fields=["關鍵字="+row.reason, "目標="+row.target];
    if (["相機","車"].includes(row.cls) && ["找得到","找不到"].includes(row.result)) {
      fields.push("鏡頭="+scopedCameras(row,data).map(c => c.camera_id+":"+(row.evidence[c.camera_id]||"看不清")).join(","));
    }
    fields.push("說明="+(row.unknown?"UNKNOWN：":"")+row.explanation);
    return fields.join("｜");
  }
  function cells(row,data) {
    if (!row.text.trim()) return [row.id,"","","","","","","","",""];
    return [row.id,row.text,row.cls,row.color,row.start,row.end,row.camera,row.ask,row.result,notes(row,data)].map(v=>v.trim());
  }
  function rowErrors(row,index,data) {
    const errors=[], values=[row.text,row.cls,row.target,row.color,row.start,row.end,row.camera,row.ask,row.result,row.reason,row.explanation,...Object.values(row.evidence)];
    if (values.some(v => /^[\t\r]/.test(v) || /^[=+\-@]/.test(v.trimStart()))) errors.push("欄位不能以公式字元或Tab開頭");
    if (/[\r\n]/.test(row.text)) errors.push("句子不能換行");
    if (row.text.length>200) errors.push("句子上限200字");
    if (!row.text.trim()) { if(!data.row_groups.OPTIONAL.includes(row.id)) errors.push("句子尚未填寫");return errors; }
    if (!row.cls || !row.ask || !row.reason || !row.target) errors.push("必填選項尚未完成");
    if (!["人","車","相機"].includes(row.cls) || !["是","否"].includes(row.ask)) errors.push("選項不在清單中");
    if (!(resultReasons[row.result]||[]).includes(row.reason)) errors.push("結果與原因不一致");
    if ((row.cls==="人" && !["追人","只問鏡頭"].includes(row.target)) || (row.cls!=="人" && row.target!=="不適用")) errors.push("目標與類別不一致");
    if (row.result==="反問" && row.ask!=="是") errors.push("反問題請選系統該反問");
    const scoped=scopedCameras(row,data);
    const needsEvidence=["相機","車"].includes(row.cls) && ["找得到","找不到"].includes(row.result);
    if (needsEvidence && scoped.some(c=>!["看得到","看不到","看不清"].includes(row.evidence[c.camera_id]))) errors.push("請逐台填畫面判斷");
    if (row.cls==="車" && (!data.cameras.some(c=>row.camera.includes(c.camera_id)) || scoped.some(c=>!c.car_question_eligible))) errors.push("車題須明寫允許出車題的鏡頭代號");
    const needsExplanation=!row.start.trim() || !row.end.trim() || ["不支援","反問",""].includes(row.result) || row.unknown || (needsEvidence&&scoped.some(c=>row.evidence[c.camera_id]==="看不清")) || (row.ask==="是"&&row.result!=="反問");
    if (needsExplanation&&!row.explanation.trim()) errors.push("此列需要說明");
    if (data.row_groups.Q1_EXTRA.includes(row.id)&&row.cls!=="相機") errors.push("第9–12列只填相機類的椅子或桌子題");
    if (row.cls!=="人"&&row.color&&!row.explanation.trim()) errors.push("非人物的顏色條件請說明不支援原因");
    return errors;
  }
  function progress(rows,data) {
    const counts={A:0,A_person:0,B:0,B_color:0,C:0,D:0,E:0,Q1:0,found:0,absent:0,outside:0,partial:0,dated:0,camera:0,whole:0};
    const cReasons=new Set();
    rows.forEach((r,i)=>{
      if(data.row_groups.OPTIONAL.includes(r.id))return;
      const evidencePending=["相機","車"].includes(r.cls)&&["找得到","找不到"].includes(r.result)
        &&scopedCameras(r,data).some(c=>r.evidence[c.camera_id]==="看不清");
      if (!r.text.trim()||rowErrors(r,i,data).length||r.unknown||evidencePending) return;
      const explicit=!!r.start.trim()&&!!r.end.trim();
      const parsed=["完整找到","完整未找到","完全超時","部分涵蓋","只測解析"].includes(r.reason);
      if (parsed&&!explicit) counts.whole++;
      if (data.row_groups.Q3_MIN.includes(r.id)) {
        if (parsed&&explicit&&["相機","車"].includes(r.cls)) counts.A++;
        if (parsed&&explicit&&r.cls==="人"&&r.target==="只問鏡頭") counts.A_person++;
        if (parsed&&explicit&&r.cls==="人"&&r.target==="追人") {counts.B++;if(r.color.trim())counts.B_color++;}
        if (r.result==="反問") {counts.C++;cReasons.add(r.reason+":"+r.explanation);}
        if (r.reason==="類別不支援") counts.D++;
        if (r.reason==="條件不支援") counts.E++;
      }
      if (explicit&&["相機","車"].includes(r.cls)&&["完整找到","完整未找到","完全超時","部分涵蓋"].includes(r.reason)) {
        counts.Q1++;
        if(r.reason==="完整找到")counts.found++;
        if(r.reason==="完整未找到")counts.absent++;
        if(r.reason==="完全超時")counts.outside++;
        if(r.reason==="部分涵蓋")counts.partial++;
      }
      if (/\d{4}-\d{2}-\d{2}/.test(r.text)&&/(?:[+-]\d{2}:\d{2}|Asia\/Taipei|台北|臺北|UTC)/.test(r.text)) counts.dated++;
      if (data.cameras.some(c=>r.text.includes(c.camera_id))) counts.camera++;
    });
    const requirements=data.quotas;
    return {counts,requirements,complete:Object.entries(requirements).every(([k,v])=>counts[k]>=v)&&cReasons.size>=2};
  }
  function restore(raw,data) {
    const parsed=csvDecode(raw);
    if (JSON.stringify(parsed[0])!==JSON.stringify(data.columns)||parsed.length!==data.row_ids.length+1) throw Error("表頭或列數不符");
    return parsed.slice(1).map((v,i)=>{
      if (v.length!==10||v[0]!==data.row_ids[i]) throw Error("欄數或固定編號不符");
      if(v.slice(1).every(x=>x===""))return blank(v[0]);
      const r={...blank(v[0]),text:v[1],cls:v[2],color:v[3],start:v[4],end:v[5],camera:v[6],ask:v[7],result:v[8]};
      const split=v[9].indexOf("｜說明=");
      if(split<0)throw Error("備註缺說明段");
      const head=v[9].slice(0,split).split("｜");
      if(head.length<2||head.length>3||!head[0].startsWith("關鍵字=")||!head[1].startsWith("目標="))throw Error("備註格式不符");
      r.reason=head[0].slice(4);r.target=head[1].slice(3);r.explanation=v[9].slice(split+4);
      if(r.explanation.startsWith("UNKNOWN：")){r.unknown=true;r.explanation=r.explanation.slice(8);}
      if(head.length===3){
        if(!head[2].startsWith("鏡頭="))throw Error("備註有未知段");
        for(const pair of head[2].slice(3).split(",")){
          const [id,value,...extra]=pair.split(":");
          if(extra.length||!data.cameras.some(c=>c.camera_id===id)||!['看得到','看不到','看不清'].includes(value)||Object.hasOwn(r.evidence,id))throw Error("鏡頭判斷格式不符");
          r.evidence[id]=value;
        }
      }
      const errors=rowErrors(r,i,data);
      if(errors.some(e=>e.includes("公式")||e.includes("換行")||e.includes("清單")||e.includes("目標")))throw Error(errors.join("；"));
      return r;
    });
  }
  globalThis.Authoring={blank,csvEncode,csvDecode,cells,notes,rowErrors,progress,restore};
  if(typeof document==="undefined")return;
  const data=window.PACK_DATA;
  let rows=data.row_ids.map(blank),dirty=false;
  const byId=id=>document.getElementById(id);
  function el(tag,text,attrs={}){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);return e;}
  byId("scope").textContent=`目前已選定：${data.run_id}。展示時間 ${data.time_window.start} 至 ${data.time_window.end_exclusive}（結束不含），${data.time_window.timezone}。`;
  for(const c of data.cameras){const f=el("figure");f.append(el("img",undefined,{src:c.image,alt:c.camera_id+"空場景畫面"}),el("figcaption",c.camera_id+" — "+c.instruction));byId("cameras").append(f);byId("camera-list").append(el("option",c.camera_id,{value:c.camera_id}));}
  function drawProgress(){
    const p=progress(rows,data);byId("progress").replaceChildren();
    for(const[k,n]of Object.entries(p.counts)){const need=p.requirements[k];const label=el("span",`${k}: ${n}${need?" / "+need:""}`,{class:"badge "+(need?(n>=need?"ok":"pending"):"")});byId("progress").append(label);}
  }
  function drawRows(){
    byId("rows").replaceChildren();
    rows.forEach((r,i)=>{
      const field=el("fieldset"),legend=el("legend",r.id+(data.row_groups.OPTIONAL.includes(r.id)?"（選填）":"")),grid=el("div",undefined,{class:"grid"}),locked=[];
      field.append(legend,grid);
      function control(key,label,options,help="",wide=false){
        const l=el("label",label,{class:wide?"wide":""});let input;
        if(options){input=el("select");for(const v of options)input.append(el("option",v===""?"（留空）":v,{value:v}));}
        else{input=el(key==="text"||key==="explanation"?"textarea":"input",undefined,key==="text"||key==="explanation"?{}:{type:"text"});}
        input.value=r[key];if(key==="camera")input.setAttribute("list","camera-list");
        if(key!=="text"){input.disabled=!r.text.trim();locked.push(input);}
        const error=el("p",undefined,{class:"error"});
        input.addEventListener(options?"change":"input",()=>{
          r[key]=input.value;dirty=true;
          if(key==="cls"){r.target=r.cls==="人"?"":"不適用";drawRows();}
          else if(key==="result"){r.reason="";drawRows();}
          else if(key==="text"){for(const c of locked)c.disabled=!r.text.trim();}
          drawProgress();error.textContent=rowErrors(r,i,data).join("；");
        });
        if(key==="camera")input.addEventListener("change",drawRows);
        l.append(input);if(help)l.append(el("small",help));l.append(error);grid.append(l);return input;
      }
      control("text","使用者會說的話",null,data.help_texts.sentence,true);
      control("cls","想找什麼",data.row_groups.Q1_EXTRA.includes(r.id)?["","相機"]:["",...data.dropdowns.classes]);
      if(r.cls!=="人")r.target="不適用";
      control("target","人物題的目標",r.cls==="人"?["",...data.dropdowns.targets]:["不適用"]);
      control("color","顏色（照原話，可留白）");
      control("camera","鏡頭或區域（照原話）",null,"直接查詢用畫面代號；含糊說法只作反問。車題只用標示允許的鏡頭。");
      control("start","開始時間（照原話）",null,data.help_texts.time);
      control("end","結束時間（照原話）");
      control("ask","系統該反問嗎",["",...data.dropdowns.ask]);
      control("result","預期結果",["",...data.dropdowns.results]);
      control("reason","原因",["",...(resultReasons[r.result]||[])]);
      control("explanation","說明（留白、不支援、反問或不確定時必填）",null,data.help_texts.explanation,true);
      const label=el("label","我不確定",{class:"wide"}),check=el("input",undefined,{type:"checkbox"});check.checked=r.unknown;check.disabled=!r.text.trim();locked.push(check);label.prepend(check);check.onchange=()=>{r.unknown=check.checked;dirty=true;drawProgress();};grid.append(label);
      if(["相機","車"].includes(r.cls)&&["找得到","找不到"].includes(r.result)){
        const evidence=el("div",undefined,{class:"wide evidence"});
        for(const c of scopedCameras(r,data)){const l=el("label",c.camera_id),s=el("select");for(const v of["","看得到","看不到","看不清"])s.append(el("option",v||"（請選）",{value:v}));s.value=r.evidence[c.camera_id]||"";s.disabled=!r.text.trim();locked.push(s);s.onchange=()=>{r.evidence[c.camera_id]=s.value;dirty=true;drawProgress();};l.append(s);evidence.append(l);}grid.append(evidence);
      }
      byId("rows").append(field);
    });drawProgress();
  }
  byId("export").onclick=()=>{
    const all=rows.flatMap((r,i)=>rowErrors(r,i,data).map(e=>r.id+"："+e));
    const fatal=all.filter(e=>e.includes("公式")||e.includes("換行")||e.includes("上限")||e.includes("反問題"));
    if(fatal.length){byId("notice").textContent=fatal.join("；");return;}
    const incomplete=all.length>0||!progress(rows,data).complete;
    const raw=csvEncode([data.columns,...rows.map(r=>cells(r,data))]);
    const link=el("a",undefined,{download:`情境_yyin_${new Date().toISOString().slice(0,10)}${incomplete?"_INCOMPLETE":""}.csv`});
    const url=URL.createObjectURL(new Blob([raw],{type:"text/csv;charset=utf-8"}));link.href=url;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);dirty=false;
    byId("notice").textContent=incomplete?"已匯出未完成回覆。"+all.slice(0,6).join("；"):"已匯出。請放進RETURN並保留原本檔案。";
  };
  byId("import").onchange=async event=>{try{const file=event.target.files[0];if(!file)return;rows=restore(await file.text(),data);drawRows();dirty=false;byId("notice").textContent="已載入；配額與缺漏仍會逐列檢查。";}catch(e){byId("notice").textContent="無法載入："+e.message;}finally{event.target.value="";}};
  addEventListener("beforeunload",event=>{if(dirty){event.preventDefault();event.returnValue="";}});
  drawRows();
})();
