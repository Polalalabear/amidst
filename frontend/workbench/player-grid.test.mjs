import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  GRID_SIZES, layoutFor, createGridState, setSize, withPin, withPage, setCandidates, pageView, pageCount,
  expectedFrame, buildSyncedFramesRequest, toDisplayModel, renderGrid, EMPTY_SLOT_LABEL,
} from "./player-grid.mjs";

const fx = (name) => JSON.parse(readFileSync(new URL(`./fixtures/synced_frames_${name}.json`, import.meta.url), "utf8"));
const cams = (n) => Array.from({ length: n }, (_, i) => `FIX_CAM_${String(i + 1).padStart(2, "0")}`);
const cameraIds = (v) => v.slots.filter((s) => s.kind === "CAMERA").map((s) => s.camera_id);
const emptyCount = (v) => v.slots.filter((s) => s.kind === "EMPTY").length;

test("版面：1／2／4／8 格", () => {
  assert.deepEqual(GRID_SIZES, [1, 2, 4, 8]);
  assert.deepEqual(layoutFor(1), { size: 1, cols: 1, rows: 1 });
  assert.deepEqual(layoutFor(2), { size: 2, cols: 2, rows: 1 });
  assert.deepEqual(layoutFor(4), { size: 4, cols: 2, rows: 2 });
  assert.deepEqual(layoutFor(8), { size: 8, cols: 4, rows: 2 });
  assert.throws(() => layoutFor(3), RangeError);
  assert.throws(() => layoutFor(16), RangeError);
});

test("3 台：各格數都不複製鏡頭補位", () => {
  const c = cams(3);
  for (const [size, shown, empty, pages] of [[1, 1, 0, 3], [2, 2, 0, 2], [4, 3, 1, 1], [8, 3, 5, 1]]) {
    const v = pageView(createGridState({ candidates: c, size }));
    assert.equal(v.slots.length, size);
    assert.equal(cameraIds(v).length, shown, `size ${size}`);
    assert.equal(emptyCount(v), empty);
    assert.equal(v.page_count, pages);
    assert.equal(new Set(cameraIds(v)).size, cameraIds(v).length, "不重複");
  }
});

test("4 台 B1：8 格時後 4 格留空並標「無更多候選」", () => {
  const v = pageView(createGridState({ candidates: cams(4), size: 8 }));
  assert.deepEqual(cameraIds(v), cams(4));
  assert.equal(emptyCount(v), 4);
  assert.ok(v.slots.slice(4).every((s) => s.kind === "EMPTY" && s.label === EMPTY_SLOT_LABEL));
  assert.equal(v.page_label, "第 1／1 頁");
});

test("8 台：8 格剛好一頁；4 格兩頁", () => {
  const c = cams(8);
  const v8 = pageView(createGridState({ candidates: c, size: 8 }));
  assert.equal(v8.page_count, 1);
  assert.equal(emptyCount(v8), 0);
  const s4 = createGridState({ candidates: c, size: 4 });
  assert.equal(pageCount(s4), 2);
  assert.deepEqual(cameraIds(pageView(withPage(s4, 1))), c.slice(4, 8));
});

test(">8 台（11）：分頁保留全集合，每次請求不超過 8 台", () => {
  const c = cams(11);
  let s = createGridState({ candidates: c, size: 8 });
  assert.equal(pageCount(s), 2);
  const p1 = pageView(s);
  const p2 = pageView(withPage(s, 1));
  assert.equal(p1.page_label, "第 1／2 頁");
  assert.equal(p2.page_label, "第 2／2 頁");
  assert.deepEqual([...cameraIds(p1), ...cameraIds(p2)], c, "兩頁合起來是全集合、順序不變");
  assert.equal(emptyCount(p2), 5);
  assert.equal(p1.total_candidates, 11);
  assert.ok(p1.camera_ids.length <= 8);
  // 超出範圍的頁碼夾回
  assert.equal(withPage(s, 99).page, 1);
  assert.equal(withPage(s, -3).page, 0);
  // 切換格數回到第 1 頁，候選全集合不變
  s = setSize(withPage(s, 1), 2);
  assert.equal(s.page, 0);
  assert.equal(s.candidates.length, 11);
  assert.equal(pageCount(s), 6);
});

test("釘選：固定在每頁第 1 格，其餘依排序遞補，不改排序", () => {
  const c = cams(11);
  const s = withPin(createGridState({ candidates: c, size: 4 }), "FIX_CAM_07");
  assert.equal(pageCount(s), 4); // 其餘 10 台，每頁 3 台
  const v1 = pageView(s);
  assert.equal(v1.slots[0].camera_id, "FIX_CAM_07");
  assert.equal(v1.slots[0].pinned, true);
  assert.equal(v1.slots[0].rank, 7, "rank 仍是原排序");
  assert.deepEqual(cameraIds(v1).slice(1), ["FIX_CAM_01", "FIX_CAM_02", "FIX_CAM_03"]);
  const v4 = pageView(withPage(s, 3));
  assert.equal(v4.slots[0].camera_id, "FIX_CAM_07");
  assert.equal(emptyCount(v4), 2);
  assert.deepEqual(s.candidates, c, "候選順序不被釘選改動");
  // 全部鏡頭出現一次（釘選的那台每頁重複出現是版面設計，不算補位）
  const seen = new Set();
  for (let p = 0; p < 4; p++) cameraIds(pageView(withPage(s, p))).forEach((id) => seen.add(id));
  assert.equal(seen.size, 11);
  // 取消釘選
  assert.equal(pageView(withPin(s, null)).slots[0].camera_id, "FIX_CAM_01");
});

test("釘選：1 格時釘選鏡頭排第 1 頁；不在候選內的釘選被忽略", () => {
  const c = cams(3);
  const s1 = withPin(createGridState({ candidates: c, size: 1 }), "FIX_CAM_03");
  assert.equal(pageView(s1).slots[0].camera_id, "FIX_CAM_03");
  assert.equal(pageCount(s1), 3);
  const bad = withPin(createGridState({ candidates: c, size: 4 }), "NOPE");
  assert.equal(bad.pinned, null);
  // 候選更新後，釘選的鏡頭不存在則解除
  const s = setCandidates(withPin(createGridState({ candidates: c, size: 4 }), "FIX_CAM_02"), ["FIX_CAM_01"]);
  assert.equal(s.pinned, null);
  // 只剩被釘選那一台時不複製補位
  const only = withPin(createGridState({ candidates: ["FIX_CAM_01"], size: 4 }), "FIX_CAM_01");
  assert.deepEqual(cameraIds(pageView(only)), ["FIX_CAM_01"]);
  assert.equal(emptyCount(pageView(only)), 3);
});

test("沒有候選：全空格，不送請求", () => {
  const v = pageView(createGridState({ candidates: [], size: 2 }));
  assert.equal(emptyCount(v), 2);
  assert.throws(() => buildSyncedFramesRequest(v, { session_ref: "s", scene_id: "x", run_id: "r", t_s: 1 }), RangeError);
});

test("時間游標：落在影格之間取 LATEST_AT_OR_BEFORE（5 fps）", () => {
  const run = { fps: 5, duration_s: 20 };
  const a = expectedFrame(12.47, run);
  assert.equal(a.expected_frame_index, 62);
  assert.equal(a.expected_timestamp_s, 12.4);
  assert.ok(Math.abs(a.sample_age_s - 0.07) < 1e-9);
  // 剛好在 sample 上：不因浮點誤差退一格
  for (const [t, i] of [[0.6, 3], [1.4, 7], [12.4, 62], [0.2, 1], [0.0, 0], [19.8, 99]]) {
    assert.equal(expectedFrame(t, run).expected_frame_index, i, `t=${t}`);
    assert.equal(expectedFrame(t, run).sample_age_s, 0);
  }
  // 差一點點到下一格仍用前一格，不加 epsilon
  assert.equal(expectedFrame(0.5999999, run).expected_frame_index, 2);
  assert.equal(expectedFrame(19.99, run).expected_frame_index, 99);
});

test("時間游標：run 是半開區間 [0, duration_s)", () => {
  const run = { fps: 5, duration_s: 20 };
  assert.equal(expectedFrame(20, run).in_range, false);
  assert.equal(expectedFrame(-0.1, run).in_range, false);
  assert.equal(expectedFrame(-0.1, run).expected_frame_index, null);
  assert.throws(() => expectedFrame(Number.NaN, run), RangeError);
  assert.throws(() => expectedFrame(1, { fps: 0, duration_s: 1 }), RangeError);
});

test("請求：單一 run／clock／時間點，camera_ids 取自當頁", () => {
  const s = createGridState({ candidates: cams(11), size: 8 });
  const r = buildSyncedFramesRequest(pageView(withPage(s, 1)), { session_ref: "sess-x", scene_id: "sc", run_id: "run", t_s: 12.47 });
  assert.deepEqual(r.camera_ids, ["FIX_CAM_09", "FIX_CAM_10", "FIX_CAM_11"]);
  assert.equal(r.t_s, 12.47);
  assert.equal(r.schema_version, "controlled-scene.synced-frames-request.v1");
});

test("fixture 3 台：READY 與 UNKNOWN 各自分開，空格留空", () => {
  const f = fx("3cams");
  const v = pageView(createGridState({ candidates: f.candidates, size: 4, fixtureIds: f.candidates }));
  const m = toDisplayModel(v, f.pages[0].response, { requestedTimeS: 12.47 });
  assert.equal(m.ok, true);
  assert.equal(m.watermark, "FIXTURE");
  const real = toDisplayModel(pageView(createGridState({ candidates: f.candidates, size: 4 })), f.pages[0].response);
  assert.equal(real.watermark, null, "非 fixture 鏡頭不加浮水印");
  assert.equal(m.identity_verdict, "UNCONFIRMED");
  assert.equal(m.time_matches_request, true);
  assert.deepEqual(m.tiles.map((t) => t.status ?? t.kind), ["READY", "READY", "UNKNOWN", "EMPTY"]);
  const unknown = m.tiles[2];
  assert.equal(unknown.mark, "?");
  assert.equal(unknown.show_image, false);
  assert.equal(unknown.reason, "RUN_BINDING_UNAVAILABLE");
  assert.equal(m.tiles[0].show_image, true);
  assert.equal(m.tiles[0].timestamp_s, 12.4);
  // 本地算出的 expected index 與 server 一致
  assert.equal(expectedFrame(12.47, f.run).expected_frame_index, m.expected_frame_index);
});

test("fixture 4 台：MISSING 不顯示成 READY，也不用其他影格補", () => {
  const f = fx("4cams");
  const v = pageView(createGridState({ candidates: f.candidates, size: 8 }));
  const m = toDisplayModel(v, f.pages[0].response);
  const missing = m.tiles[2];
  assert.equal(missing.status, "MISSING");
  assert.equal(missing.badge, "MISSING");
  assert.equal(missing.hatched, true);
  assert.equal(missing.show_image, false);
  assert.equal(missing.frame_ref, null);
  assert.equal(missing.timestamp_s, null);
  assert.equal(missing.reason, "RGB_RECORD_ABSENT");
  assert.equal(m.tiles.filter((t) => t.kind === "EMPTY").length, 4);
});

test("OUT_OF_RANGE 是獨立狀態", () => {
  const ids = ["FIX_CAM_01", "FIX_CAM_02"];
  const v = pageView(createGridState({ candidates: ids, size: 2 }));
  const resp = {
    schema_version: "controlled-scene.synced-frames.v1", t_s: 25, clock_id: "c", sampling_version: "5fps-v1",
    tiles: ids.map((id) => ({ camera_id: id, status: "OUT_OF_RANGE", frame_ref: null, reason: "TIME_OUTSIDE_RUN" })),
  };
  const m = toDisplayModel(v, resp);
  assert.ok(m.ok);
  assert.ok(m.tiles.every((t) => t.status === "OUT_OF_RANGE" && !t.show_image && !t.hatched && t.mark === null));
  assert.equal(expectedFrame(25, { fps: 5, duration_s: 20 }).in_range, false);
});

test("四種 tile 狀態徽章各不相同", () => {
  const f = fx("8cams");
  const v = pageView(createGridState({ candidates: f.candidates, size: 8 }));
  const m = toDisplayModel(v, f.pages[0].response);
  assert.equal(m.tiles.length, 8);
  const byStatus = Object.groupBy(m.tiles, (t) => t.status);
  assert.equal(byStatus.READY.length, 6);
  assert.equal(byStatus.MISSING.length, 1);
  assert.equal(byStatus.UNKNOWN.length, 1);
  assert.equal(new Set(m.tiles.map((t) => t.css)).size, 3);
});

test("fixture 11 台：兩頁都能轉成顯示模型，頁尾空格", () => {
  const f = fx("11cams");
  assert.equal(f.pages.length, 2);
  let s = createGridState({ candidates: f.candidates, size: 8 });
  const m1 = toDisplayModel(pageView(s), f.pages[0].response);
  s = withPage(s, 1);
  const m2 = toDisplayModel(pageView(s), f.pages[1].response);
  assert.ok(m1.ok && m2.ok);
  assert.equal(m1.page_label, "第 1／2 頁");
  assert.equal(m2.tiles.filter((t) => t.kind === "EMPTY").length, 5);
  assert.equal(m2.tiles.find((t) => t.camera_id === "FIX_CAM_09").status, "MISSING");
  assert.ok(f.pages.every((p) => p.request.camera_ids.length <= 8));
});

test("完整性錯誤：整頁 fail closed，沒有任何 tile，也不是 MISSING", () => {
  const f = fx("integrity_error");
  const v = pageView(createGridState({ candidates: f.candidates, size: 4 }));
  const m = toDisplayModel(v, f.pages[0].response);
  assert.equal(m.ok, false);
  assert.deepEqual(m.tiles, []);
  assert.equal(m.error.code, "DataIntegrityError");
  assert.match(m.error.message, /RGB_RECORD_HASH_MISMATCH/);
  assert.ok(!JSON.stringify(m).includes("MISSING\""));
});

test("協定違規一律 fail closed（不降格、不補 tile）", () => {
  const f = fx("4cams");
  const v = pageView(createGridState({ candidates: f.candidates, size: 4 }));
  const good = f.pages[0].response;
  const clone = () => structuredClone(good);
  const cases = {
    "schema 不符": (r) => { r.schema_version = "x"; },
    "缺 tiles": (r) => { delete r.tiles; },
    "少一台": (r) => { r.tiles.pop(); },
    "多一台": (r) => { r.tiles.push({ camera_id: "OTHER", status: "UNKNOWN", frame_ref: null, reason: "x" }); },
    "重複": (r) => { r.tiles[1] = { ...r.tiles[0] }; },
    "未定義狀態": (r) => { r.tiles[0].status = "HASH_MISMATCH"; },
    "READY 無 hash": (r) => { delete r.tiles[0].file_sha256; },
    "MISSING 帶 frame_ref": (r) => { r.tiles[2].frame_ref = "fr-other"; },
  };
  for (const [name, mutate] of Object.entries(cases)) {
    const r = clone(); mutate(r);
    const m = toDisplayModel(v, r);
    assert.equal(m.ok, false, name);
    assert.deepEqual(m.tiles, [], name);
  }
  assert.equal(toDisplayModel(v, null).ok, false);
  assert.equal(toDisplayModel(v, "oops").ok, false);
});

test("回應的 t_s 與請求不同時回報（不當成同一個時間）", () => {
  const f = fx("3cams");
  const v = pageView(createGridState({ candidates: f.candidates, size: 4 }));
  assert.equal(toDisplayModel(v, f.pages[0].response, { requestedTimeS: 13 }).time_matches_request, false);
});

test("renderGrid：用最小 DOM stub 驗證輸出，fail closed 不輸出影格", () => {
  const mk = () => {
    const el = { children: [], dataset: {}, style: {}, className: "", textContent: "", attrs: {}, listeners: {} };
    el.append = (...c) => el.children.push(...c);
    el.replaceChildren = () => { el.children = []; };
    el.setAttribute = (k, v) => { el.attrs[k] = v; };
    el.addEventListener = (k, fn) => { el.listeners[k] = fn; };
    el.ownerDocument = { createElement: mk };
    return el;
  };
  const f = fx("4cams");
  const v = pageView(withPin(createGridState({ candidates: f.candidates, size: 8 }), "FIX_CAM_02"));
  const box = mk();
  const pinned = [];
  renderGrid(box, toDisplayModel(v, structuredClone(f.pages[0].response), {}) , {});
  // 釘選改了 slot 順序，但 response 的 tile 以 camera_id 對應，所以仍成功
  assert.equal(box.children.length, 8);
  assert.equal(box.children.filter((c) => c.className.includes("tile-empty")).length, 4);
  assert.ok(box.children.some((c) => c.className.includes("tile-hatched")));
  const urls = [];
  const box2 = mk();
  renderGrid(box2, toDisplayModel(pageView(createGridState({ candidates: f.candidates, size: 8 })), f.pages[0].response), {
    frameUrl: (t) => { urls.push(t.camera_id); return "x"; }, onPin: (id) => pinned.push(id),
  });
  assert.deepEqual(urls, ["FIX_CAM_01", "FIX_CAM_02", "FIX_CAM_04"], "MISSING 不要求圖片");
  box2.children[0].listeners.click();
  assert.deepEqual(pinned, ["FIX_CAM_01"]);
  const err = mk();
  renderGrid(err, toDisplayModel(v, fx("integrity_error").pages[0].response));
  assert.equal(err.children.length, 1);
  assert.equal(err.children[0].attrs.role, "alert");
});
