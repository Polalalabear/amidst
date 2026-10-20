// Run: node --test tests/cs_b_review/test_app.test.js
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const { computeSummary, buildExport, filterFrames } = require("../../tools/cs_b_review/app.js");

const scr = JSON.parse(fs.readFileSync(path.join(__dirname,
  "fixtures/SYNTHETIC-ctrl-run/acceptance/d47_screening.json")));
const req = scr.frames.filter((f) => f.review_required);
const key = (f) => f.camera_id + "#" + f.frame_index;

test("summary counts unreviewed and model-screened", () => {
  const dec = { [key(req[0])]: { decision: "PASS" }, [key(req[1])]: { decision: "FAIL" },
                [key(req[2])]: { decision: "UNSURE" } };
  const s = computeSummary(scr.frames, dec);
  assert.strictEqual(s.required, req.length);
  assert.deepStrictEqual([s.pass, s.fail, s.unsure], [1, 1, 1]);
  assert.strictEqual(s.unreviewed, req.length - 3);
  assert.strictEqual(s.pass + s.fail + s.unsure + s.unreviewed, s.required);
  assert.strictEqual(s.model_screened_not_human_reviewed, scr.frames.length - req.length);
});

test("decision on non-required frame is not counted as required", () => {
  const nr = scr.frames.find((f) => !f.review_required);
  const s = computeSummary(scr.frames, { [key(nr)]: { decision: "PASS" } });
  assert.strictEqual(s.pass, 0);
  assert.strictEqual(s.unreviewed, req.length);
  assert.strictEqual(s.extra_non_required_decisions, 1);
});

test("export format", () => {
  const dec = { [key(req[0])]: { decision: "FAIL", note: "框偏" } };
  const o = buildExport(scr, "abc", dec, "2026-10-19T00:00:00Z");
  assert.strictEqual(o.schema_version, "d47_human_review_v1");
  assert.strictEqual(o.run_id, scr.run_id);
  assert.strictEqual(o.screening_sha256, "abc");
  assert.deepStrictEqual(o.decisions, [{ camera_id: req[0].camera_id, frame_index: req[0].frame_index, decision: "FAIL", note: "框偏" }]);
  assert.strictEqual(o.summary.fail, 1);
  assert.strictEqual(o.summary.unreviewed, req.length - 1);
  JSON.parse(JSON.stringify(o));
});

test("filters", () => {
  assert.strictEqual(filterFrames(scr.frames, "REQUIRED", "ALL", false, {}).length, req.length);
  assert.strictEqual(filterFrames(scr.frames, "ALL", "ALL", false, {}).length, scr.frames.length);
  const f = filterFrames(scr.frames, "FLAGGED", "CAM_W1", false, {});
  assert.ok(f.length && f.every((x) => x.camera_id === "CAM_W1" && x.review_reasons.includes("FLAGGED")));
  assert.strictEqual(filterFrames(scr.frames, "REQUIRED", "ALL", true, { [key(req[0])]: {} }).length, req.length - 1);
});
