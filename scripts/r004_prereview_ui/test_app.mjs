// Focused offline CSV boundary tests; no browser, network, media, or inference.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const context = { window: {} };
vm.createContext(context);
vm.runInContext(fs.readFileSync(new URL("./app.js", import.meta.url), "utf8"), context);
const u = context.window.R004_REVIEW_UTILS;
const item = {
  item_id: "CAM-01", category: "EXIT_ROI", object_id: "相機A",
  image_refs: ["one.png", "two.png"], statement: '固定敘述，含"引號"\n換行'
};
let passed = 0;
function test(name, run) { run(); passed += 1; console.log("PASS " + name); }
function row(decision = "T", reason = "", reviewer = "組員", date = "2026-10-23") {
  return [...u.fixedValues(item), decision, reason, reviewer, date];
}

test("CSV BOM, quotes, commas, multiline", () => {
  const rows = [u.COLUMNS, row("F", '逗號,雙引號"\n換行')];
  const csv = u.toCSV(rows);
  assert.equal(csv.charCodeAt(0), 0xfeff);
  assert.deepEqual(JSON.parse(JSON.stringify(u.parseCSV(csv))), JSON.parse(JSON.stringify(rows)));
  assert.equal(u.validateImport(u.parseCSV(csv), [item]).answers.get("CAM-01").reason, '逗號,雙引號"\n換行');
});
test("formula neutralize and restore", () => {
  for (const text of ["=SUM(1,2)", " +abc", "-3", "@cmd", "\tx"]) assert.equal(u.decodeEditable(u.encodeEditable(text)), text);
});
test("leading apostrophe restore", () => {
  for (const text of ["'=abc", "'ordinary", "''=abc", "''ordinary"]) assert.equal(u.decodeEditable(u.encodeEditable(text)), text);
});
test("unescaped formula rejected", () => assert.throws(() => u.decodeEditable("=SUM(1,2)")));
test("fixed content tamper rejected", () => {
  const altered = row(); altered[4] += "改";
  assert.throws(() => u.validateImport([u.COLUMNS, altered], [item]));
});
test("unknown ID rejected", () => {
  const altered = row(); altered[0] = "UNKNOWN";
  assert.throws(() => u.validateImport([u.COLUMNS, altered], [item]));
});
test("duplicate ID rejected", () => {
  const item2 = { ...item, item_id: "CAM-02" };
  assert.throws(() => u.validateImport([u.COLUMNS, row(), row()], [item, item2]));
});
test("missing F reason rejected", () => assert.throws(() => u.validateImport([u.COLUMNS, row("F")], [item])));
test("uncertain literal accepted", () => {
  assert.equal(u.validateImport([u.COLUMNS, row("不確定", "缺證據")], [item]).answers.get("CAM-01").decision, "不確定");
});
test("missing reviewer rejected", () => assert.throws(() => u.validateImport([u.COLUMNS, row("T", "", "")], [item])));
test("incomplete blank answer accepted", () => {
  assert.equal(u.validateImport([u.COLUMNS, row("", "", "", "")], [item]).answers.get("CAM-01").decision, "");
});
test("invalid calendar rejected", () => assert.equal(u.validDate("2026-02-30"), false));
test("unclosed CSV quote rejected", () => assert.throws(() => u.parseCSV('"a')));
test("remote and traversal image rejected", () => {
  for (const path of ["https://x/y.png", "../x.png", "images/%2e%2e/y.png", "/root.png", "file:///x"]) assert.equal(u.safeImagePath(path), false);
  assert.equal(u.safeImagePath("images/相機.png"), true);
});
test("header order rejected", () => {
  const columns = [...u.COLUMNS]; [columns[0], columns[1]] = [columns[1], columns[0]];
  assert.throws(() => u.validateImport([columns, row("", "", "", "")], [item]));
});
test("context and details are both retained", () => {
  const example = { ...item, context: "審查說明", details: { edge_path: ["EDGE-1"] }, system_verdict: "WEAK" };
  const details = u.contextDetails(example);
  assert.equal(details.context, "審查說明");
  assert.equal(details.details.edge_path[0], "EDGE-1");
  assert.equal(details.system_verdict, "WEAK");
  assert.equal(details.statement, undefined);
});
test("HSV verdict explanation distinguishes weak and unknown", () => {
  assert.match(u.verdictDescription("WEAK"), /弱候選.*尚不能確定/);
  assert.match(u.verdictDescription("NONE"), /不等於.*不存在/);
  assert.match(u.verdictDescription("UNKNOWN"), /無法形成有效/);
  assert.match(u.verdictDescription("STRONG"), /不代表/);
});
test("every unresolved decision requires a reason", () => {
  const gap = { ...item, category: "UNRESOLVED" };
  for (const decision of ["T", "F", "不確定"]) {
    assert.equal(u.needsReason(gap, decision), true);
    const values = [...u.fixedValues(gap), decision, "", "組員", "2026-10-23"];
    assert.throws(() => u.validateImport([u.COLUMNS, values], [gap]));
  }
});
test("unresolved T with rationale imports", () => {
  const gap = { ...item, category: "UNRESOLVED" };
  const values = [...u.fixedValues(gap), "T", "資料不足，請補入口圖。", "組員", "2026-10-23"];
  assert.equal(u.validateImport([u.COLUMNS, values], [gap]).answers.get(item.item_id).decision, "T");
});
test("ordinary T may omit reason", () => {
  assert.equal(u.needsReason(item, "T"), false);
  assert.equal(u.sufficientAnswer(item, { decision: "T", reason: "" }), true);
});
test("unresolved progress excludes missing or whitespace rationale", () => {
  const gap = { ...item, category: "UNRESOLVED" };
  assert.equal(u.sufficientAnswer(gap, { decision: "T", reason: "  " }), false);
  assert.equal(u.sufficientAnswer(gap, { decision: "T", reason: "已核對，需補入口。" }), true);
  assert.equal(u.needsReason(gap, ""), false);
  assert.equal(u.sufficientAnswer(gap, { decision: "", reason: "先記錄" }), false);
});
console.log(passed + " focused UI utility tests PASS");
