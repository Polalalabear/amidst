# Workbench 2D/3D root-cause audit

保存日期：2026-10-16（Asia/Taipei）。目標：穩定、可重現的 **8 分鐘本機 demo**。
本文件保存同一 Codex 對話中的 Astra High 主稽核與追加兩檔窄驗證；不是修復完成、8 分鐘驗收、人物身分或物理安全認證。

## Evidence provenance and repository binding

- **CONFIRMED / documentation task**：開啟的 checkout `/Users/polalabear/Developer/amidst`，branch `phase1/physical-policy-approval`，HEAD `c5956dc825f669e28e2694578be0fed97432a786`；無 upstream，已有未追蹤的 `docs/history/`，本工作保留它。
- **CONFIRMED / documentation task**：runtime 報告所指 checkout `/Users/polalabear/Developer/amidst-claude`，branch `claude/office-demo-visualization`，HEAD `57eab7eae6ea27fb75a3bf7ad3e460e7caee3675`；tracked/untracked status 乾淨、無 upstream。兩者由 `git worktree list --porcelain` 證實屬同一 repository。
- **CONFIRMED / documentation task**：origin 為 `https://github.com/Polalalabear/amidst.git`；`git ls-remote origin refs/heads/main refs/heads/claude/office-demo-visualization refs/heads/docs/workbench-root-cause-audit` 回 main `f9b563fffcfeabeeb828ccff924a81420da6b88f`，另外兩個 refs 在核對時不存在。
- **CONFIRMED / documentation task**：main 與 inspected HEAD 的共同祖先為 `7d053543316d13272039402d33eb3c3bcab06ba8`；`git log --oneline <main>..<inspected>` 列出 25 個提交。文件分支以已核對的 main 為基底，使用暫存 index，只加入本文件與 `docs/README.md`，避免發布該 25 個既有提交或更動 runtime checkout。
- **CONFIRMED / Astra-reported, not rerun here**：PID `25413`、listener `127.0.0.1:65262`、cwd 為上述 Claude checkout；前輪比對 served `app.mjs`、`scene.mjs`、`motion.mjs`，追加驗證比對 `physical-review.mjs`、`scene.mjs`，bytes 均與 inspected checkout 相同。本文件工作未重新查詢 runtime、啟動服務或執行科學／應用測試。

以下所有 source 行號均綁定 **inspected HEAD `57eab7eae6ea27fb75a3bf7ad3e460e7caee3675`**，不是文件 commit 或目前 main 的行號。未發布的 inspected commit 不保證在 GitHub 可取；後續研究者須先核對本機該 commit，不能把 main 同名檔視為相同證據。

### Input fixture and hashes

此表為 **CONFIRMED / Astra-reported**；本文件工作沒有重新計算這些資產 hash。

| Input | Binding / reported SHA-256 |
| --- | --- |
| `configs/office_demo_fixture_v1.json` | `office-source-rgb-mvp-v1`; scene `blender-office`; FRONT/REAR; 0–9.8 s, 5 Hz; selected observation `observation:add9f687d311742321e80dff` at 4.4 s; next observation 8.6 s |
| Source `.blend` binding | `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e` |
| Dataset binding | `2367ecc30c05740e64320130237878315034f61b6b91ec92979fd2deba8619c4` |
| Office `safe_inputs.json` | `1ea62def6c843b3bae1c5e25584fa489915f08e678b28b6220dc88cc17b43163`; Astra reported matching fixture |
| Source geometry archive | `6d30e591d6210707f2b6175bf96dc2fe2395fe0202b24bd0a6df7ee87a5d997c` |
| Architectural scale binding | `7e3615a3b0b4485585da9c0f7beefb96955517f7a321910fc008c041f99a3eaf`; 0.0247 m/BU |
| Runtime binding | run `blender-pilot-office-baseline-v1`; model `SOURCE_SCENE_FRAME_220`; clock `BLENDER_PILOT_CONFIGURED_SECONDS_5HZ` |

Office bundle locator: `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/blender_camera_v1/office`.
These local paths are historical reproduction prerequisites, not assets included by this documentation publication. A missing/hash-mismatched input means BLOCKED; do not substitute a different run.

## A — 2D/3D projection mismatch

**Decision: NEEDS_OPUS_REVIEW.** Distinguish data quality from reproducible projection arithmetic.

| ID / status | Source, function, inspected lines / minimal evidence | Reported result and falsification |
| --- | --- | --- |
| A1 CONFIRMED | `src/amidst/workbench/frame_baseline.py`, `BaselineFrameIndex.__init__`, 137–147: RGB path/hash → `RGBFrame` → `pixels = produce_perception(rgb, ...)` → `_project(measurement, ...)`; local tracks at 149–159 use `track.local_track_id`, observation IDs and missing timestamps, authority `CAMERA_LOCAL_PIXEL_COMPONENT_TRACK`. | Full visible chain: RGB → perception → Measurement bbox/contact/local_track → contact_pixel → projector → world_position. Producer-internal mask/bbox/tracklet logic remains UNKNOWN. Refute delegation by finding extraction code at these cited lines instead of the producer call. |
| A2 REFUTED | Same file/function 137–147; producer imported from `amidst.engineering.perception` at line 25. Hypothesis: this file itself implements foot/contact extraction. | This module delegates extraction. `src/amidst/engineering/perception.py` was outside the two-file extension and was not inspected. Do not infer its complete algorithm from four matching outputs. |
| A3 REFUTED, module scope only | Same file, `_project`, 219–244: `status=VisibilityStatus.OBSERVED, point_2d=row.contact_pixel`; `projector.project_frame(frame)`; catches `InverseProjectionError`; forwards `measurement_status`, `uncertainty`, `projection_quality`. | Hypothesis of a local occlusion/foot-quality gate before projection is refuted: no gate on `row.status` or uncertainty here. Upstream handling remains UNKNOWN. Counterevidence would be a reachable status/quality rejection in this path. |
| A4 REFUTED, four samples only | Same file `_project`, 219–244, API `/api/query`, independent ray–floor calculation in preserved script below. | Mathematical/unit/frontend-axis explanation for these four XYZ is unsupported: Astra reported residual **0 m** for all four, using existing calibration and floor. This does not validate calibration, real foot contact, or projection accuracy. Any nonzero residual above 1e-12 m falsifies the recorded consistency check. |
| A5 SUSPECTED | Same producer boundary; four RGBs `CAM_1F_AUDITORIUM_FRONT/frame_002.png`, `frame_003.png`, `frame_009.png`, `frame_010.png` at 0.4/0.6/1.8/2.0 s. | Astra visually reported lower-body occlusion by seats. All four contacts match `[(xmin+xmax-1)/2, ymax-1]`; visible-bottom motion projected onto the floor is a plausible source of large displacement. Neither the complete extraction formula nor true feet is independently established. Producer inspection or independent lawful contact evidence may refute this hypothesis. |
| A6 UNKNOWN | `_project`, 240–243 forwards `point.projection_quality`, authority `SOURCE_BOUND_FLOOR_INTERSECTION_ONLY`; quality implementation is outside inspected files. | `DETECTED`, same local track, successful projection and projection_quality are not demonstrated foot-accuracy evidence. No independent foot labels/error bounds were supplied. |

All four share `track:a7807f56197f0e8655944fed` and camera `CAM_1F_AUDITORIUM_FRONT`.

| Time s | bbox_xyxy | contact_pixel | measurement_status | uncertainty | projection_quality | Reported world_position m |
| --- | --- | --- | --- | --- | --- | --- |
| 0.4 | [765,11,799,136] | [781.5,135] | MERGED_OR_PARTIAL | 0.60 | 0.17854522364182726 | [34.285480667483995,48.18377357389123,0.4959475898742678] |
| 0.6 | [770,11,802,125] | [785.5,124] | DETECTED | 0.25 | 0.16364426249520367 | [32.78292744495016,47.38263825182045,0.4959475898742678] |
| 1.8 | [788,12,822,122] | [804.5,121] | MERGED_OR_PARTIAL | 0.60 | 0.15791299252284166 | [31.911247156041924,47.43246643901692,0.4959475898742678] |
| 2.0 | [792,12,825,135] | [808,134] | MERGED_OR_PARTIAL | 0.60 | 0.17444192848596846 | [33.607947205725665,48.503259117569954,0.4959475898742678] |

**CONFIRMED / Astra-reported**: 0.4→0.6 s displacement 1.7027871243394628 m; 1.8→2.0 s displacement 2.006336965477033 m. The earliest observed spatial discontinuity is already in API observation projections, before frontend rendering. The earliest defective producer operation is still UNKNOWN. Source observation is not measured 3D, and track identity remains UNCONFIRMED.

## B — Misleading 3D marker continuity

**Decision: READY_TO_FIX**, limited to presentation provenance/segment semantics; it does not fix original XYZ quality.

| ID / status | Source, function, inspected lines / minimal evidence | Reported result and falsification |
| --- | --- | --- |
| B1 CONFIRMED | `frontend/workbench/physical-review.mjs`, `physicalReviewScenePlan`, 173–179: maps samples to timestamp, world_position, state, camera_id, source_camera_ids, candidate_refs and connect_from_previous. | Input 61 samples, 59 with observation_ref; output 61 samples, **0 observation_ref**. Input and output both have 0 track_ref. XYZ/order preserved. Fix should preserve existing observation provenance; do not invent missing track IDs. Countertest: output retains the 59 observation refs. |
| B2 CONFIRMED | Same file, `physicalReviewEvidenceAt`, 181–191: timestamp `Set`, numeric sort, nearest timestamp (earlier wins a tie), tolerance at most 0.100001 s; filter input samples, then `slice(0,24)`. | Only timestamps deduplicate/sort; sample identity does not. No selected-person/candidate filter in this function. 0.6 s: 2 samples/1 position; 4.4 s: 4 samples/2 positions. Countertest: matching identities are deduplicated or sample output does not preserve input order. |
| B3 CONFIRMED | `frontend/workbench/scene.mjs`, `setPhysicalReview`, 288–297 creates 24 reusable marker slots; `setPhysicalReviewTime`, 302–309: `sample=points[index]`, `marker.position.copy(...)`. | No connect/camera/observation/track comparison in slot assignment. Astra executed the exact method with substitute marker objects: marker[0] reused across 0.4→0.6 and 1.8→2.0 discontinuities (connect=false), and FRONT→REAR at 8.6 s. Countertest: identity-sensitive slot assignment or different object identity across these transitions. This is not a WebGL/browser acceptance test. |
| B4 REFUTED, this fixture's sampled long gap | `physicalReviewEvidenceAt`, 181–191 and `setPhysicalReviewTime`, 302–309. | Hypothesis: continuous movement/interpolation through missing 4.6–8.4 s. All 20 sampled timestamps returned []; marker hidden at 5.0 s, same object reappeared at 8.6 s. No new middle XYZ. Countertest: any valid position at those 20 times. Unrelated fixtures/arbitrary timestamps not exhaustively tested. |
| B5 SUSPECTED / actual cross-track case unproven | Scene slot assignment above; track_ref absent in evidence input and plan. | Renderer cannot distinguish tracks, but actual crossing of different track_refs is not proven by this DTO. Distinct observation rows/segments and camera transitions are sufficient to prove anonymous slot reuse, not confirmed person identity. |

**CONFIRMED / Astra-reported**: `/api/physical_review.synchronized_evidence.samples` already contains original XYZ jumps with `connect_from_previous=false`; display slot reuse does not create those numbers. It can make disconnected anonymous projections look like one continuous person. A/B common underlying pixel/contact cause remains **SUSPECTED**.

**REFUTED, current runtime only / Astra-reported**: historical presentation-track override as the direct source of this Office runtime. `src/amidst/workbench/blender_scene.py`, constructor 491–527 supplies safe-input presentation; runtime had no `presentation.frames`; `scene.mjs:updateBodies`, 389–395 historical override was therefore inactive. Six checked timeline times (0,4.4,4.6,8.4,8.6,9.8) were EXACT for both cameras. Other clock/selection states were not exhaustively ruled out.

## C — Missing Auditorium geometry

**Decision: CONDITIONALLY_READY** for bounded display completeness verification; not approval of whole-scene geometry or furniture restoration.

| ID / status | Source, function, inspected lines / minimal evidence | Reported result and falsification |
| --- | --- | --- |
| C1 CONFIRMED | `src/amidst/workbench/blender_scene.py`, `_source_meshes`, 148–177: Office approved support-derived crop, selects only `group_0`, `group_0.002`; 178–213 clips source triangles without caps; 224–233 declares PARTIAL_DISPLAY_CONTEXT, archive_is_whole_scene=false. | Reported Office 1,662 triangles; bounds m [[27.7815,41.737,0.47594758987426755],[37.4265,57.557,3.295947589874267]]. FRONT position [50.02349409179688,57.16834296875,3.784387042236328], REAR [50.012678796386716,39.042655615234374,3.784830267333984], outside crop. Countertest: complete Auditorium mesh already present inside API payload. |
| C2 CONFIRMED | Same file constructor 491–527 copies presentation into snapshot; `scene.mjs:setData`, 83–86 → `addSourceMeshes`, 364–374 renders supplied vertices/triangles. | First observed loss is partial export/crop, not a demonstrated frontend omission of a complete model. Trace: source Blender binding → evaluated archive → _source_meshes → safe_inputs.presentation → backend snapshot → Three.js. Direct full Blender/exporter inspection was not performed. |
| C3 CONFIRMED, availability/metadata only | Existing sibling `auditorium/safe_inputs.json`, presentation metadata; same _source_meshes schema. No invented JSON line numbers: Astra supplied parsed JSON fields, not line-addressed evidence. | Existing 318-triangle asset; bounds [[37.044,38.4025,0.47594758987426755],[50.641,57.6805,3.295947589874267]]. Same reported source archive binding, still PARTIAL_DISPLAY_CONTEXT. Compare with Office via test C below. It may restore some display context, not necessarily furniture. |
| C4 UNKNOWN, complete inventory; CONFIRMED, reported image appearance | Four A5 source PNGs show seats and lectern-like furniture; source object mapping/full inventory uninspected. | Complete furniture export availability is UNKNOWN. No large .blend parsing or full archive inventory was performed. Do not claim named objects, room ownership or complete source geometry certification from RGB appearance or camera names. |

Office and Auditorium use separate site/run image sequences even when camera names match. Reusing source-bound display geometry must never substitute Auditorium observations/media into the Office inference path. Geometry remains display-only; no navigation, aperture, visibility, collision or body-clearance authority upgrade.

## Read-only reproduction and reported results

All application/scientific test outcomes below are **Astra-reported**, not independently rerun by this documentation task. No standalone original execution log/receipt was supplied for publication; the conversation's actual outputs and report are the evidence source. Missing output is not invented. The script below is preserved verbatim from Astra's final reply, including absolute prerequisites. It uses session creation plus read/query APIs; runs no model inference or image regeneration, and saves no fixture/data files.

### Tests A/B — preserved executable script

Prerequisites: inspected source bytes, existing Node, existing source-bound bundle and original service URL. Missing assets/service are BLOCKED. Validate the binding table first. Passing asserts arithmetic/data/display-method behavior only; this script contains no independent true-foot oracle.

```bash
/opt/homebrew/bin/node --input-type=module <<'JS'
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {physicalReviewScenePlan,physicalReviewEvidenceAt}
  from '/Users/polalabear/Developer/amidst-claude/frontend/workbench/physical-review.mjs';

const post=async(a,p)=>{
  const r=await fetch(`http://127.0.0.1:65262/api/${a}`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(p)});
  assert(r.ok); return r.json();
};
const session=await post('session',{role:'research'});
const scope={session_ref:session.session_ref,scene_id:'blender-office'};
const cameras=['CAM_1F_AUDITORIUM_FRONT','CAM_1F_AUDITORIUM_REAR'];
const query=await post('query',{...scope,camera_id:cameras[0],start:0,end:2});
const inputs=JSON.parse(readFileSync(
 '/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/blender_camera_v1/office/safe_inputs.json'));
const c=inputs.cameras.find(x=>x.camera_id===cameras[0]).calibration;
const m=c.camera_to_world,o=m.slice(0,3).map(row=>row[3]);
for(const t of [.4,.6,1.8,2]){
  const s=query.observations.find(x=>x.timestamp===t);
  const [u,v]=s.contact_pixel;
  const ray=[(u-c.cx)/c.fx,-(v-c.cy)/c.fy,-1];
  const d=m.slice(0,3).map(row=>ray.reduce((n,x,i)=>n+x*row[i],0));
  const k=(inputs.floor_plane.point[2]-o[2])/d[2];
  assert(Math.hypot(...o.map((x,i)=>x+k*d[i]-s.world_position[i]))<1e-12);
}
const result=await post('physical_review',{
  ...scope,camera_ids:cameras,start:0,end:9.8});
const plan=physicalReviewScenePlan(result);
const at=t=>physicalReviewEvidenceAt(plan,t);
assert.equal(plan.samples.length,61);
assert.equal(plan.samples.filter(s=>s.observation_ref).length,0);
assert.equal(at(.6).length,2);
assert(at(.6).every(s=>s.connect_from_previous===false));
for(let tick=23;tick<=42;tick++)assert.equal(at(tick/5).length,0);

const source=readFileSync(
 '/Users/polalabear/Developer/amidst-claude/frontend/workbench/scene.mjs','utf8');
const body=source.split('  setPhysicalReviewTime(timestamp) {')[1].split('\n  }')[0];
const update=new Function('physicalReviewEvidenceAt','vector','timestamp',body);
const marker={userData:{},position:{copy(v){this.xyz=[...v]}},traverse(){}};
const ctx={physicalReviewPlan:plan,reviewEvidenceMarkers:[marker]};
for(const t of [.4,.6,1.8,2,5,8.6]){
  update.call(ctx,physicalReviewEvidenceAt,p=>p,t);
  assert.equal(ctx.reviewEvidenceMarkers[0],marker);
  assert.equal(marker.visible,t!==5);
}
console.log('PASS: projection consistency, identity loss, slot reuse, missing gap');
JS
```

Expected baseline: all assertions pass; Astra reported equivalent executed probes passed, four residuals 0, input unchanged. This exact final assembled script was supplied for replay, not separately claimed as executed verbatim. FAIL: binding-correct assertions contradict baseline. BLOCKED: service/source/bundle unavailable or changed. After fixes, assertions for identity loss/slot reuse intentionally must change; they are defect detectors, not permanent desired behavior tests.

### Test C — minimal metadata/API comparison

```bash
python3 -B - <<'PY'
import json
from pathlib import Path
root=Path('/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/blender_camera_v1')
for site in ('office','auditorium'):
    p=json.loads((root/site/'safe_inputs.json').read_text())['presentation']
    print(site, {k:p[k] for k in ('display_triangle_count','bounds_metres','authority','archive_is_whole_scene','source_archive_sha256')})
PY
```

Then inspect `/api/scene` using the existing research session and `scene_id=blender-office`; compare `snapshot.presentation` with Office metadata. Expected/reported: Office 1,662; Auditorium 318; both partial; Office API retains Office crop. This documentation task did not execute this metadata command. PASS: binding-consistent metadata matches; FAIL: full geometry exists in payload but is absent in renderer, requiring a narrower frontend test; BLOCKED: required source asset/binding missing. Full seats/lectern restoration remains unverified until an independent source mesh inventory exists.

## Demo repair handoff — future tasks, no repair authorized by this publication

| Task / owner | Authorized scope for proposed follow-up | Acceptance and stop conditions |
| --- | --- | --- |
| A — Opus High, read-only | Inspect `src/amidst/engineering/perception.py` contact extraction, bbox/mask, local track assignment and occlusion flags; use existing `frame_baseline.py` boundary and the same four PNGs. Inspect only named producer functions; request approval before expanding dependencies. | Explain formula/quality flags and whether true contact has independent support. Replay existing four observations without GT corrections. Stop if required evidence is absent or a data contract/scientific assumption must change. Keep unresolved portions UNKNOWN; no whole-repository audit. |
| B — Sonnet, frontend patch | `frontend/workbench/physical-review.mjs`, `frontend/workbench/scene.mjs`; focused tests to be named/approved before adding files. Preserve existing observation_ref and candidate/camera provenance; explicitly represent disconnected anonymous samples. | Regress duplicate samples/order changes, 0.4→0.6, 1.8→2.0, 4.4 multiple observations, 20 gap samples, FRONT→REAR 8.6. Browser: provenance inspectable, break/transition visible, no implied person identity, gap has no position, original XYZ unchanged. Stop before changing backend DTO or inventing track_ref; preserving observation_ref changes internal ScenePlan shape and must be reviewed in the patch. |
| C — geometry completeness before display edits | Read existing Office/Auditorium safe_inputs metadata, named `_source_meshes` function and existing source-bound geometry receipts. Do not parse large Blender/archive inventories without scoped approval. Only after verification propose `src/amidst/workbench/blender_scene.py` and `frontend/workbench/scene.mjs` display changes. | Confirm source/scale binding and inventory before claiming seats/lectern completeness. Regression: original Office fixture, candidate ranks and physical results unchanged; added geometry labeled PARTIAL/display-only. Browser: missing region explicitly identified and supported region visible. Stop on missing assets, run mixing or authority expansion. |

All follow-ups prohibit GT leakage into inference, calibration changes, interpolation/invented positions, original .blend edits, source media/dataset edits and unauthorized geometry-authority expansion. This publication does not authorize those repairs or installation/render/inference runs.

Eight-minute acceptance is **UNKNOWN / not tested**. A future rehearsal must time the complete local flow with the fixed inputs, reproducible startup/clock selection, explicit missing/unknown states and no unexplained marker identity changes; engineering probes alone do not establish demo stability or scientific accuracy.

## Documentation-task validation and publication scope

This task independently verifies Git checkout/branch/HEAD/status, remote/main identity, existing documentation conventions, changed-file scope, Markdown paths and `git diff --check`. Application tests, API probes, browser playback, source/fixture hashes and geometry checks are not rerun. Their historical results above remain Astra-reported.

Only this audit and the required navigation entry in [documentation index](../README.md) belong in the documentation commit. No application code, fixture, calibration, GT, generated assets or original source geometry belong in it. Publication is confirmed only by a matching remote branch commit; push does not authorize a merge.
