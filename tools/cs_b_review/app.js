"use strict";
// CS-B D47 human review page. Pure helpers are exported for node tests.

const REASONS = ["FLAGGED", "D27_TARGET", "BLIND_BOUNDARY", "SWITCH_BOUNDARY", "RANDOM_SAMPLE"];

function frameKey(f) { return f.camera_id + "#" + f.frame_index; }

function computeSummary(frames, decisions) {
  const s = { required: 0, pass: 0, fail: 0, unsure: 0, unreviewed: 0,
              extra_non_required_decisions: 0, model_screened_not_human_reviewed: 0 };
  for (const f of frames) {
    const d = decisions[frameKey(f)];
    if (f.review_required) {
      s.required++;
      if (!d) s.unreviewed++;
      else if (d.decision === "PASS") s.pass++;
      else if (d.decision === "FAIL") s.fail++;
      else if (d.decision === "UNSURE") s.unsure++;
      else s.unreviewed++;
    } else {
      s.model_screened_not_human_reviewed++;
      if (d) s.extra_non_required_decisions++;
    }
  }
  return s;
}

function buildExport(screening, screeningSha, decisions, nowIso) {
  const out = [];
  for (const f of screening.frames) {
    const d = decisions[frameKey(f)];
    if (d) out.push({ camera_id: f.camera_id, frame_index: f.frame_index,
                      decision: d.decision, note: d.note || "" });
  }
  return {
    schema_version: "d47_human_review_v1",
    run_id: screening.run_id,
    screening_sha256: screeningSha,
    reviewed_at: nowIso,
    decisions: out,
    summary: computeSummary(screening.frames, decisions),
  };
}

function filterFrames(frames, reason, camera, onlyUnreviewed, decisions) {
  return frames.filter((f) =>
    (reason === "ALL" || (reason === "REQUIRED" ? f.review_required : (f.review_reasons || []).includes(reason))) &&
    (camera === "ALL" || f.camera_id === camera) &&
    (!onlyUnreviewed || !decisions[frameKey(f)]));
}

if (typeof module !== "undefined") {
  module.exports = { computeSummary, buildExport, filterFrames, frameKey };
}

// ---------------------------------------------------------------- browser
if (typeof document !== "undefined") {
  const $ = (id) => document.getElementById(id);
  const st = { run: null, screening: null, sha: null, decisions: {}, list: [], pos: 0,
               storageOk: true, mem: {} };

  const storeKey = () => `csb-d47:${st.screening.run_id}:${st.sha}`;
  function loadDecisions() {
    try { return JSON.parse(localStorage.getItem(storeKey()) || "{}") || {}; }
    catch (e) { st.storageOk = false; return st.mem[storeKey()] || {}; }
  }
  function saveDecisions() {
    st.mem[storeKey()] = st.decisions;
    try { localStorage.setItem(storeKey(), JSON.stringify(st.decisions)); }
    catch (e) { st.storageOk = false; }
    $("storage-warn").hidden = st.storageOk;
  }

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  async function init() {
    const runs = await (await fetch("/api/runs")).json();
    const sel = $("run");
    for (const r of runs) sel.append(new Option(r.run_id, r.run_id));
    sel.onchange = () => loadRun(sel.value, runs);
    $("reason").append(new Option("全部必審格", "REQUIRED"), new Option("全部影格（含非必審）", "ALL"));
    for (const r of REASONS) $("reason").append(new Option(r, r));
    $("reason").onchange = $("camera").onchange = $("unrev").onchange = refilter;
    $("export").onclick = doExport;
    $("note").addEventListener("input", () => {
      const f = cur(); if (!f) return;
      const d = st.decisions[frameKey(f)];
      if (d) { d.note = $("note").value; saveDecisions(); }
    });
    $("note").addEventListener("keydown", (e) => {
      if (e.key === "Escape" || (e.key === "Enter" && !e.shiftKey)) { e.preventDefault(); $("note").blur(); }
      e.stopPropagation();
    });
    document.addEventListener("keydown", onKey);
    await loadRun(runs[0] && runs[0].run_id, runs);
  }

  async function loadRun(runId, runs) {
    if (!runId) { $("fatal").textContent = "沒有 run"; return; }
    const meta = runs.find((r) => r.run_id === runId);
    $("fatal").textContent = meta.index_error || "";
    const resp = await fetch(`/api/runs/${encodeURIComponent(runId)}/screening`);
    if (!resp.ok) { $("fatal").textContent = "讀取 d47_screening.json 失敗：" + (await resp.text()); return; }
    st.sha = resp.headers.get("X-Screening-SHA256");
    st.screening = await resp.json();
    st.run = runId;
    const sc = st.screening;
    const idxOk = !sc.rgb_index_sha256 || sc.rgb_index_sha256 === meta.rgb_index_sha256;
    if (!idxOk) $("fatal").textContent = "警告：screening.rgb_index_sha256 與 rgb_index.json 實際雜湊不符";
    $("meta").textContent = `${sc.run_id} · detector ${sc.detector && sc.detector.name} ${sc.detector && sc.detector.version} · screening sha ${String(st.sha).slice(0, 12)}`;
    st.decisions = loadDecisions();
    const cams = [...new Set(sc.frames.map((f) => f.camera_id))].sort();
    $("camera").replaceChildren(new Option("全部鏡頭", "ALL"), ...cams.map((c) => new Option(c, c)));
    $("unrev").checked = false;
    $("reason").value = "REQUIRED";
    refilter();
  }

  function cur() { return st.list[st.pos]; }

  function refilter() {
    const keepKey = cur() ? frameKey(cur()) : null;
    st.list = filterFrames(st.screening.frames, $("reason").value, $("camera").value, $("unrev").checked, st.decisions);
    const i = keepKey ? st.list.findIndex((f) => frameKey(f) === keepKey) : -1;
    st.pos = i >= 0 ? i : 0;
    render();
  }

  function drawBox(svg, box, cls, label) {
    if (!box) return;
    const [x0, y0, x1, y1] = box;
    const r = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    r.setAttribute("x", x0); r.setAttribute("y", y0);
    r.setAttribute("width", x1 - x0); r.setAttribute("height", y1 - y0);
    r.setAttribute("class", cls);
    svg.append(r);
    if (label) {
      const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
      t.setAttribute("x", x0 + 2); t.setAttribute("y", Math.max(12, y0 - 3));
      t.setAttribute("class", "lbl " + cls); t.textContent = label;
      svg.append(t);
    }
  }

  function imgUrl(f) { return `/rgb/${encodeURIComponent(st.run)}/${f.rgb_ref.split("/").map(encodeURIComponent).join("/")}`; }

  function setImg(img, f, errBox) {
    img.onerror = async () => {
      let msg = "影像載入失敗";
      try { const r = await fetch(img.src); msg = (await r.json()).error || msg; } catch (e) { /* keep */ }
      if (errBox) errBox.textContent = "影像被拒絕：" + msg;
    };
    img.onload = () => {
      if (errBox) { errBox.textContent = ""; $("overlay").setAttribute("viewBox", `0 0 ${img.naturalWidth} ${img.naturalHeight}`); }
    };
    img.src = imgUrl(f);
  }

  function render() {
    const f = cur();
    const sum = computeSummary(st.screening.frames, st.decisions);
    const done = sum.required - sum.unreviewed;
    $("progress").textContent = `必審 ${done}/${sum.required} · PASS ${sum.pass} · FAIL ${sum.fail} · UNSURE ${sum.unsure} · 未審 ${sum.unreviewed}`;
    $("bar").style.width = sum.required ? (100 * done / sum.required) + "%" : "0%";
    $("pos").textContent = st.list.length ? `${st.pos + 1} / ${st.list.length}` : "0 / 0";
    $("storage-warn").hidden = st.storageOk;
    const svg = $("overlay");
    svg.replaceChildren();
    $("flags").replaceChildren(); $("reasons").replaceChildren(); $("dets").replaceChildren();
    $("thumbs").replaceChildren();
    if (!f) { $("title").textContent = "沒有符合篩選的格子"; $("img").removeAttribute("src"); return; }
    $("title").textContent = `${f.camera_id} · frame ${f.frame_index} · t=${f.timestamp_s}s`;
    $("model-only").hidden = !!f.review_required;
    setImg($("img"), f, $("imgerr"));
    svg.setAttribute("viewBox", "0 0 960 540");
    (f.detections || []).forEach((d, i) =>
      drawBox(svg, d.bbox_xyxy_px, "det", `${(d.labels || []).join(",")} ${d.score !== undefined ? Number(d.score).toFixed(2) : ""}`));
    const p = f.projection || {};
    drawBox(svg, p.expected_present ? p.expected_bbox_xyxy_px : null, "prj", "投影(製作路線)");
    for (const x of f.flags || []) $("flags").append(el("span", "chip flag", x));
    for (const x of f.review_reasons || []) $("reasons").append(el("span", "chip", x));
    if (!(f.flags || []).length) $("flags").append(el("span", "dim", "（無）"));
    for (const d of f.detections || [])
      $("dets").append(el("li", null, `[${(d.bbox_xyxy_px || []).join(", ")}] score ${d.score} ${(d.labels || []).join(",")}`));
    if (!(f.detections || []).length) $("dets").append(el("li", "dim", "無偵測"));
    $("proj").textContent = p.expected_present ? `預期出現 [${(p.expected_bbox_xyxy_px || []).join(", ")}]` : "投影：預期不在畫面";
    const same = st.screening.frames.filter((g) => g.camera_id === f.camera_id).sort((a, b) => a.frame_index - b.frame_index);
    const i = same.findIndex((g) => g.frame_index === f.frame_index);
    for (const [lab, g] of [["前一格", same[i - 1]], ["後一格", same[i + 1]]]) {
      const box = el("figure", "thumb");
      if (g) {
        const im = new Image(); setImg(im, g, null);
        box.append(im, el("figcaption", null, `${lab} · #${g.frame_index}`));
      } else box.append(el("figcaption", "dim", `${lab}：無`));
      $("thumbs").append(box);
    }
    const d = st.decisions[frameKey(f)];
    $("verdict").textContent = d ? d.decision : (f.review_required ? "未審" : "MODEL_SCREENED_NOT_HUMAN_REVIEWED");
    $("verdict").className = "verdict " + (d ? d.decision : "NONE");
    $("note").value = d ? d.note || "" : "";
  }

  function decide(kind) {
    const f = cur(); if (!f) return;
    const key = frameKey(f);
    st.decisions[key] = { decision: kind, note: $("note").value || (st.decisions[key] && st.decisions[key].note) || "" };
    saveDecisions();
    if (st.pos < st.list.length - 1 && !$("unrev").checked) st.pos++;
    else if ($("unrev").checked) { refilter(); return; }
    render();
  }

  function onKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key.toLowerCase();
    if (k === "p") decide("PASS");
    else if (k === "f") decide("FAIL");
    else if (k === "u") decide("UNSURE");
    else if (k === "arrowright") { if (st.pos < st.list.length - 1) { st.pos++; render(); } e.preventDefault(); }
    else if (k === "arrowleft") { if (st.pos > 0) { st.pos--; render(); } e.preventDefault(); }
    else if (k === "n") { e.preventDefault(); $("note").focus(); }
  }

  function doExport() {
    const obj = buildExport(st.screening, st.sha, st.decisions, new Date().toISOString());
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" }));
    a.download = "d47_human_review.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    const s = obj.summary;
    $("exported").textContent = `已匯出：必審 ${s.required}，未審 ${s.unreviewed}` + (s.unreviewed ? "（仍有未審格）" : "");
  }

  init().catch((e) => { $("fatal").textContent = "初始化失敗：" + e; });
}
