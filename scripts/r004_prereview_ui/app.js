/* Offline review: no network, persistence, inference, or approval mutation. */
"use strict";
(function () {
  const COLUMNS = ["item_id", "category", "object_id", "image_refs", "statement", "decision", "reason", "reviewer", "date"];
  const DECISIONS = ["", "T", "F", "不確定"];
  const FIXED_COLUMNS = COLUMNS.slice(0, 5);
  const CATEGORY_NAMES = {
    CAMERA_IDENTITY: "相機與畫面對應", EXIT_ROI: "出口區域", REGION_EDGE: "區域連通",
    CAMERA_TRANSITION: "相機轉移", UNRESOLVED: "待決缺口", HSV_RED: "紅色 preview", HSV_BLUE: "藍色 preview"
  };
  function dangerous(value) { return /^[\s]*[=+\-@]|^[\t\r]/.test(String(value)); }
  function encodeEditable(value) { const text = String(value || ""); return dangerous(text) || text.startsWith("'") ? "'" + text : text; }
  function decodeEditable(value) {
    const text = String(value || "");
    if (text.startsWith("''")) return text.slice(1);
    if (text.startsWith("'") && dangerous(text.slice(1))) return text.slice(1);
    if (dangerous(text)) throw new Error("可填欄位含未中和的試算表公式起始字元，請使用本頁匯出的 CSV。");
    return text;
  }
  function escapeCSV(value) { return '"' + String(value == null ? "" : value).replace(/"/g, '""') + '"'; }
  function toCSV(rows) { return "\ufeff" + rows.map(row => row.map(escapeCSV).join(",")).join("\r\n") + "\r\n"; }
  function parseCSV(source) {
    const text = String(source).replace(/^\ufeff/, "");
    const rows = []; let row = [], value = "", quoted = false, closed = false, atStart = true;
    function field() { row.push(value); value = ""; closed = false; atStart = true; }
    function line() { field(); rows.push(row); row = []; }
    for (let i = 0; i < text.length; i += 1) {
      const ch = text[i];
      if (quoted) {
        if (ch === '"') { if (text[i + 1] === '"') { value += '"'; i += 1; } else { quoted = false; closed = true; } }
        else value += ch;
      } else if (ch === ",") field();
      else if (ch === "\r" || ch === "\n") { if (ch === "\r" && text[i + 1] === "\n") i += 1; line(); }
      else if (ch === '"') { if (!atStart || closed) throw new Error("CSV 引號格式錯誤。"); quoted = true; atStart = false; }
      else { if (closed) throw new Error("CSV 引號結束後有多餘字元。"); value += ch; atStart = false; }
    }
    if (quoted) throw new Error("CSV 有未關閉的引號。");
    if (value !== "" || row.length || closed || !atStart) line();
    return rows;
  }
  function validDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const [year, month, day] = value.split("-").map(Number);
    const date = new Date(Date.UTC(year, month - 1, day));
    return year >= 1000 && date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
  }
  function fixedValues(item) { return [item.item_id, item.category, item.object_id, item.image_refs.join("|"), item.statement]; }
  function needsReason(item, decision) { return decision === "F" || decision === "不確定" || (item.category === "UNRESOLVED" && Boolean(decision)); }
  function sufficientAnswer(item, answer) { return Boolean(answer.decision && (!needsReason(item, answer.decision) || answer.reason.trim())); }
  function contextDetails(item) { return Object.fromEntries(Object.entries(item).filter(([key]) => !FIXED_COLUMNS.includes(key))); }
  function verdictDescription(verdict) {
    return ({ STRONG: "顏色證據達強候選門檻；不代表已有人工作為正確答案。", WEAK: "顏色證據僅達弱候選門檻，尚不能確定有該色衣物。", NONE: "未達此顏色候選門檻；不等於已證明物件不存在。", UNKNOWN: "本次無法形成有效顏色判定；請依圖片判斷是否有足夠證據。" })[verdict] || "未提供可解釋的系統判定；不能當作人工答案。";
  }
  function validateImport(rows, items) {
    if (!rows.length || rows[0].length !== COLUMNS.length || !COLUMNS.every((name, i) => rows[0][i] === name)) throw new Error("CSV 欄位名稱或順序不符。");
    if (rows.length - 1 !== items.length) throw new Error("CSV 必須保留本包全部項目；尚未填答的列也要保留。");
    const byID = new Map(items.map(item => [item.item_id, item])); const answers = new Map(); const identities = new Set();
    rows.slice(1).forEach((row, index) => {
      if (row.length !== COLUMNS.length) throw new Error("第 " + (index + 2) + " 列欄位數不符。");
      const item = byID.get(row[0]);
      if (!item || answers.has(row[0])) throw new Error("CSV 有未知或重複的 item_id：" + row[0]);
      const expected = fixedValues(item);
      FIXED_COLUMNS.forEach((name, i) => { if (row[i] !== expected[i]) throw new Error(item.item_id + " 的固定欄位被修改：" + name); });
      const [decision, reason, reviewer, date] = row.slice(5).map(decodeEditable);
      if (!DECISIONS.includes(decision)) throw new Error(item.item_id + " 的 decision 只能是 T、F、不確定或空白。");
      if (reason.length > 10000 || reviewer.length > 120) throw new Error(item.item_id + " 的文字過長。");
      if (date && !validDate(date)) throw new Error(item.item_id + " 的日期須為有效的 YYYY-MM-DD。");
      if (decision && (!reviewer.trim() || !date)) throw new Error(item.item_id + " 已填判斷但缺少審查者或日期。");
      if (needsReason(item, decision) && !reason.trim()) throw new Error(item.item_id + " 必須附理由（F／不確定，以及缺口項的所有判斷）。");
      if (reviewer || date) { if (!reviewer.trim() || !validDate(date)) throw new Error("審查者與日期必須一起填寫。"); identities.add(JSON.stringify([reviewer, date])); }
      answers.set(item.item_id, { decision, reason });
    });
    if (identities.size > 1) throw new Error("本頁一次接續一位審查者／一個日期；請分開不同審查者的 CSV。");
    return { answers, identity: identities.size ? JSON.parse(Array.from(identities)[0]) : ["", ""] };
  }
  function safeImagePath(value) {
    if (typeof value !== "string" || !value || /^[\\/]|^[a-z][a-z0-9+.-]*:/i.test(value) || /[\\\u0000?#]/.test(value)) return false;
    try { return !decodeURIComponent(value).split("/").some(part => part === ".." || part === "." || /[:\\\u0000]/.test(part)); }
    catch (_) { return false; }
  }
  window.R004_REVIEW_UTILS = { COLUMNS, parseCSV, toCSV, encodeEditable, decodeEditable, fixedValues, validateImport, validDate, safeImagePath, needsReason, sufficientAnswer, contextDetails, verdictDescription };
  if (typeof document === "undefined") return;
  const $ = id => document.getElementById(id);
  const data = window.R004_REVIEW_DATA;
  function message(text, error) { $("message").textContent = text; $("message").classList.toggle("error", Boolean(error)); }
  if (!data || !Array.isArray(data.items) || !data.items.length) { message("無法讀取 data.js 或項目清單為空。請保留完整資料夾並直接開啟 index.html。", true); $("export").disabled = true; return; }
  const items = data.items; const ids = new Set();
  try {
    items.forEach(item => {
      if (!["item_id", "category", "object_id", "statement"].every(key => typeof item[key] === "string") || !item.item_id || ids.has(item.item_id) || !Array.isArray(item.image_refs) || !item.image_refs.every(safeImagePath) || item.image_refs.some(ref => ref.includes("|"))) throw new Error("項目資料無效：" + String(item.item_id));
      ids.add(item.item_id);
    });
  } catch (error) { message(error.message, true); $("export").disabled = true; return; }
  const answers = new Map(items.map(item => [item.item_id, { decision: "", reason: "" }]));
  let currentID = items[0].item_id; let filtered = items.slice(); let dirty = false;
  $("title").textContent = data.title || "r004 前置審查"; document.title = $("title").textContent;
  if (data.notice) $("notice").textContent = data.notice;
  $("scope").textContent = typeof data.scope === "string" ? data.scope : JSON.stringify(data.scope || {});
  Array.from(new Set(items.map(item => item.category))).forEach(category => { const option = document.createElement("option"); option.value = category; option.textContent = CATEGORY_NAMES[category] || category; $("category").append(option); });
  const report = data.report || data.summary || {};
  ["status", "counts", "engineering_checks"].forEach(key => {
    if (report[key] == null) return;
    const paragraph = document.createElement("p"); paragraph.className = "summary-row";
    paragraph.textContent = key + "：" + (typeof report[key] === "string" ? report[key] : JSON.stringify(report[key], null, 2)); $("summary").append(paragraph);
  });
  (report.unresolved || data.known_gaps || []).forEach(gap => { const li = document.createElement("li"); li.textContent = [gap.id, gap.severity, gap.summary || JSON.stringify(gap)].filter(Boolean).join(" · "); $("known-gaps").append(li); });
  function answerState(item, answer) { return !answer.decision ? "尚未填答" : sufficientAnswer(item, answer) ? "已填 " + answer.decision : "待補理由 · " + answer.decision; }
  function updateProgress() {
    const counts = { T: 0, F: 0, 不確定: 0 }; let done = 0;
    answers.forEach((answer, id) => { if (answer.decision) counts[answer.decision] += 1; if (sufficientAnswer(items.find(item => item.item_id === id), answer)) done += 1; });
    $("progress").max = items.length; $("progress").value = done;
    $("progress-label").textContent = "填答 " + done + "／" + items.length + " 項";
    $("decision-counts").textContent = "T " + counts.T + " · F " + counts.F + " · 不確定 " + counts.不確定 + " · 待補／未填 " + (items.length - done);
  }
  function matches(item) {
    const category = $("category").value, status = $("status-filter").value, search = $("search").value.trim().toLocaleLowerCase(); const answer = answers.get(item.item_id);
    return (!category || item.category === category) && (!search || [item.item_id, item.object_id, item.statement].join(" ").toLocaleLowerCase().includes(search)) && (status === "all" || (status === "pending" && !sufficientAnswer(item, answer)) || (status === "complete" && sufficientAnswer(item, answer)) || answer.decision === status);
  }
  function renderList() {
    filtered = items.filter(matches); $("filter-count").textContent = "顯示 " + filtered.length + "／" + items.length + " 項"; $("item-list").replaceChildren();
    filtered.forEach(item => { const li = document.createElement("li"), button = document.createElement("button"), state = document.createElement("small"); button.type = "button"; button.textContent = item.item_id; button.setAttribute("aria-current", String(item.item_id === currentID)); state.className = "state"; state.textContent = answerState(item, answers.get(item.item_id)); button.append(state); button.addEventListener("click", () => { currentID = item.item_id; render(); }); li.append(button); $("item-list").append(li); });
  }
  function updateNavigation() {
    const position = items.findIndex(row => row.item_id === currentID), index = filtered.findIndex(row => row.item_id === currentID);
    $("previous").disabled = !filtered.some(row => items.indexOf(row) < position); $("next").disabled = !filtered.some(row => items.indexOf(row) > position);
    $("item-position").textContent = index >= 0 ? "篩選中第 " + (index + 1) + "／" + filtered.length + " 項" : "目前項目已不符合篩選條件；可繼續前後切換";
  }
  function renderItem() {
    const item = items.find(row => row.item_id === currentID);
    $("item").hidden = !item; $("empty").hidden = Boolean(item); updateNavigation();
    if (!item) return;
    $("item-category").textContent = CATEGORY_NAMES[item.category] || item.category;
    $("item-id").textContent = item.item_id; $("object-id").textContent = "對象：" + item.object_id; $("statement").textContent = item.statement; $("images").replaceChildren();
    const isHSV = item.category === "HSV_RED" || item.category === "HSV_BLUE";
    $("system-verdict").hidden = !isHSV;
    $("system-verdict").textContent = isHSV ? "系統判定：" + (item.system_verdict || "UNKNOWN") + " · " + (item.color === "red" ? "紅色" : item.color === "blue" ? "藍色" : item.color || "顏色") + "\n" + verdictDescription(item.system_verdict || "UNKNOWN") + " 請依可見衣物判斷上面的敘述，這是 PREVIEW 審查。" : "";
    item.image_refs.forEach((ref, i) => {
      const figure = document.createElement("figure"), link = document.createElement("a"), img = document.createElement("img"), caption = document.createElement("figcaption"), title = document.createElement("span"), zoom = document.createElement("a");
      const label = /(?:EXIT_PROPOSED|overlay|\/exits\/|標記|標示)/i.test(ref) ? "標記圖" : /(?:crop|裁切)/i.test(ref) ? "裁切圖" : "原圖／參考圖";
      img.src = ref; img.alt = item.object_id + " · " + label + " " + (i + 1); img.loading = "lazy"; link.href = ref; link.target = "_blank"; link.rel = "noopener"; link.title = "開啟原尺寸圖片"; link.append(img);
      title.className = "image-title"; title.textContent = label + " " + (i + 1); zoom.href = ref; zoom.target = "_blank"; zoom.rel = "noopener"; zoom.textContent = "開啟原尺寸／放大"; caption.append(title, zoom, document.createElement("br"), document.createTextNode(ref)); figure.append(link, caption);
      img.addEventListener("error", () => { figure.classList.add("error-image"); caption.append(document.createElement("br"), document.createTextNode("圖片無法讀取：請確認資料夾完整，不應據此填 T。")); }); $("images").append(figure);
    });
    const context = contextDetails(item);
    $("context").textContent = JSON.stringify(context, null, 2); $("context-wrapper").hidden = !Object.keys(context).length;
    const answer = answers.get(item.item_id); document.querySelectorAll('input[name="decision"]').forEach(radio => { radio.checked = radio.value === answer.decision; }); $("reason").value = answer.reason; updateItemState();
  }
  function updateItemState() {
    if (!currentID) return; const item = items.find(row => row.item_id === currentID), answer = answers.get(currentID); const required = needsReason(item, answer.decision);
    $("reason").required = required; $("reason").setAttribute("aria-required", String(required)); $("reason-required").textContent = item.category === "UNRESOLVED" ? "（缺口項所有判斷都必填：可接受／需修改／資料不足及原因）" : "（F 與不確定必填）"; $("item-state").textContent = answerState(item, answer) + "。目前分頁內暫存；請匯出後保留檔案。";
  }
  function render() { renderList(); renderItem(); updateProgress(); }
  function record() { if (!currentID) return; dirty = true; updateItemState(); updateProgress(); renderList(); updateNavigation(); }
  document.querySelectorAll('input[name="decision"]').forEach(radio => radio.addEventListener("change", () => { if (!currentID) return; answers.get(currentID).decision = radio.value; record(); }));
  $("reason").addEventListener("input", () => { if (!currentID) return; answers.get(currentID).reason = $("reason").value; record(); });
  $("clear").addEventListener("click", () => { if (!currentID) return; answers.get(currentID).decision = ""; dirty = true; render(); });
  ["category", "status-filter", "search"].forEach(id => $(id).addEventListener(id === "search" ? "input" : "change", () => { filtered = items.filter(matches); if (!filtered.some(item => item.item_id === currentID)) currentID = filtered.length ? filtered[0].item_id : null; render(); }));
  ["reviewer", "review-date"].forEach(id => $(id).addEventListener("input", () => { dirty = true; }));
  function step(delta) { const position = items.findIndex(item => item.item_id === currentID); const choices = filtered.filter(item => delta < 0 ? items.indexOf(item) < position : items.indexOf(item) > position); if (choices.length) currentID = (delta < 0 ? choices[choices.length - 1] : choices[0]).item_id; render(); $("item-id").scrollIntoView({ block: "nearest" }); }
  $("previous").addEventListener("click", () => step(-1)); $("next").addEventListener("click", () => step(1));
  $("export").addEventListener("click", () => {
    const reviewer = $("reviewer").value, date = $("review-date").value;
    if (!reviewer.trim() || !validDate(date)) { message("匯出前請填審查者姓名與有效日期。", true); (!reviewer.trim() ? $("reviewer") : $("review-date")).focus(); return; }
    const invalid = items.filter(item => { const answer = answers.get(item.item_id); return needsReason(item, answer.decision) && !answer.reason.trim(); });
    if (invalid.length) { currentID = invalid[0].item_id; $("category").value = ""; $("status-filter").value = "all"; $("search").value = ""; render(); message("請先補上 " + invalid.length + " 項必填理由（F／不確定，以及缺口項所有判斷），再匯出。未判斷的項目可保留空白。", true); $("reason").focus(); return; }
    const pending = items.filter(item => !sufficientAnswer(item, answers.get(item.item_id))).length;
    const rows = [COLUMNS, ...items.map(item => { const answer = answers.get(item.item_id); return [...fixedValues(item), ...[answer.decision, answer.reason, reviewer, date].map(encodeEditable)]; })];
    const blob = new Blob([toCSV(rows)], { type: "text/csv;charset=utf-8" }), url = URL.createObjectURL(blob), a = document.createElement("a");
    a.href = url; a.download = "r004_review_" + (pending ? "INCOMPLETE_" : "FILLED_") + date + ".csv"; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 10000); dirty = false;
    message(pending ? "已匯出 INCOMPLETE：仍有 " + pending + " 項未填，尚不能作為完整回收。可稍後匯入接續。" : "已匯出 FILLED：所有項目已有審查意見，仍須由 Owner／獨立審查者另行核定。");
  });
  $("import-button").addEventListener("click", () => $("import").click());
  $("import").addEventListener("change", async event => {
    const file = event.target.files[0]; if (!file) return;
    try {
      if (file.size > 20 * 1024 * 1024) throw new Error("CSV 超過 20 MiB，請確認檔案。");
      const text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer()); const result = validateImport(parseCSV(text), items);
      if (dirty && !window.confirm("匯入會取代目前分頁內尚未匯出的內容。確定要繼續？")) return;
      result.answers.forEach((answer, id) => answers.set(id, answer)); [$("reviewer").value, $("review-date").value] = result.identity; dirty = false; render();
      message("CSV 已通過欄位、項目 ID 與固定內容檢查，填答已載入。尚未自動核准任何項目。");
    } catch (error) { message("匯入拒絕（INVALID）：" + error.message + " 原有填答保持不變。", true); }
    finally { event.target.value = ""; }
  });
  window.addEventListener("beforeunload", event => { if (dirty) { event.preventDefault(); event.returnValue = ""; } });
  render(); message("資料已讀取。請先填姓名／日期，再逐項判斷；可隨時匯出未完成 CSV。");
}());
