"use strict";
(() => {
  const encode = rows => "\ufeff" + rows.map(r=>r.map(v=>/[",\r\n]/.test(v)?'"'+v.replaceAll('"','""')+'"':v).join(",")).join("\r\n")+"\r\n";
  function decode(raw) {
    raw=raw.replace(/^\ufeff/,"");let rows=[],row=[],cell="",quoted=false,closed=false;
    for(let i=0;i<raw.length;i++){const c=raw[i];if(quoted){if(c==='"'){if(raw[i+1]==='"'){cell+='"';i++;}else{quoted=false;closed=true;}}else cell+=c;}
      else if(c==='"'){if(cell||closed)throw Error("引號格式錯誤");quoted=true;}
      else if(",\r\n".includes(c)){row.push(cell);cell="";closed=false;if(c!==','){if(c==='\r'&&raw[i+1]==='\n')i++;rows.push(row);row=[];}}
      else{if(closed)throw Error("引號後有多餘文字");cell+=c;}}
    if(quoted)throw Error("引號未結束");if(cell||row.length||closed){row.push(cell);rows.push(row);}return rows;
  }
  function validate(rows,data) {
    if(JSON.stringify(rows[0])!==JSON.stringify(data.columns)||rows.length!==4)throw Error("表頭或列數不符");
    rows.slice(1).forEach((r,i)=>{if(r.length!==3||r[0]!==data.row_ids[i])throw Error("固定題號不符");if(r[1]&&!data.allowed_answers.includes(r[1]))throw Error("選項不在清單");if(r.some(v=>/^[\t\r]/.test(v)||/^[=+@-]/.test(v.trimStart())))throw Error("不允許公式字元");});
    return rows.slice(1).map(r=>({id:r[0],answer:r[1],notes:r[2]}));
  }
  const complete = rows => rows.every(r=>r.answer&&(!["都不是","看不出來"].includes(r.answer)||r.notes.trim()));
  globalThis.ReviewForm={encode,decode,validate,complete};
  if(typeof document==="undefined")return;
  const data=window.REVIEW_DATA;let rows=data.row_ids.map(id=>({id,answer:"",notes:""})),dirty=false;
  const get=id=>document.getElementById(id);const el=(tag,text)=>{const n=document.createElement(tag);if(text)n.textContent=text;return n;};
  get("role").textContent=data.fixture_role==="SYNTHETIC"?"SYNTHETIC 自測圖，不可作正式確認。":"僅使用附圖判斷；不確定請照實保留。";
  function draw(){get("questions").replaceChildren();rows.forEach((r,i)=>{const q=data.questions[i],f=el("fieldset"),l=el("legend",r.id+"："+q.prompt),img=el("img"),link=el("a","開啟完整疊圖"),answer=el("label","你的選擇"),select=el("select"),notes=el("label","備註（都不是／看不出來時請填）"),ta=el("textarea");img.src=q.image;img.alt=r.id+" A／B／C靜態候選";img.style.width="100%";img.style.maxWidth="1000px";link.href=q.image;link.target="_blank";link.rel="noopener";
    for(const v of["",...data.allowed_answers]){const o=el("option",v||"（尚未選擇）");o.value=v;select.append(o);}select.value=r.answer;select.onchange=()=>{r.answer=select.value;dirty=true;};ta.value=r.notes;ta.oninput=()=>{r.notes=ta.value;dirty=true;};answer.append(select);notes.append(ta);f.append(l,img,link,answer,notes);get("questions").append(f);});}
  get("export").onclick=()=>{try{const table=[data.columns,...rows.map(r=>[r.id,r.answer,r.notes])];validate(table,data);const done=complete(rows);const link=el("a"),url=URL.createObjectURL(new Blob([encode(table)],{type:"text/csv;charset=utf-8"}));link.href=url;link.download=`審圖_yyin_${new Date().toISOString().slice(0,10)}${done?"":"_INCOMPLETE"}.csv`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);dirty=false;get("notice").textContent=done?"已匯出，請放進RETURN交回。":"已匯出未完成回覆，請保留_INCOMPLETE。";}catch(e){get("notice").textContent="不能匯出："+e.message;}};
  get("import").onchange=async e=>{try{const file=e.target.files[0];if(!file)return;rows=validate(decode(await file.text()),data);draw();dirty=false;get("notice").textContent="已載入審圖回覆；尚未送出。";}catch(err){get("notice").textContent="無法載入："+err.message;}finally{e.target.value="";}};
  addEventListener("beforeunload",e=>{if(dirty){e.preventDefault();e.returnValue="";}});draw();
})();
