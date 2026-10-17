# C5 Office person visibility / retrieval / real negative evidence — 2026-10-17

Current synchronized K1/K5 (`74c6ace`) result: [sync report](C5_K1_K5_SYNC_20261017.md), [complete API freeze](C5_PERSON_K1_SYNC_D19_20261017.json.gz), [small receipt](C5_PERSON_K1_SYNC_D19_RECEIPT_20261017.json). NONE / BASELINE / feedback remain 281.125 m² and 0% convergence; 34 repeated frames are now excluded natively. C6 remains paused. Earlier frozen outputs below are historical and retained.

## Historical record before the K1/K5 sync

Refs #18 / #17; K0 v1.1 PR #45 @ be646ca confirmed on PR #46. Parent C4a a6ce40c; C7 policy inputs from PR #40 a69e63f. **K1/K5 remain unchanged and Claude-owned**, as explicitly selected by the user. No checkpoint approval or integration merge is claimed.

## D19 current review result

Mode NONE / BASELINE / BASELINE_AND_FEEDBACK is now explicit and sealed in the response hash; the last remains the default. With the current v1.1 foot-ray endpoint the measured output is **1→1 representative and −9.026233882% summed/mean reachable-region area**, not3→1/−16.6%. The latter was the historical head-ray comparison cited in D19. Both runs apply evidence before generation, not "剪掉2條". Baseline and feedback are the same34 frames, and feedback prunes0 further paths. **偵測器對比度與部分遮擋的漏判未驗證**; this remains an RQ2 evaluation question. Visibility union rules are unchanged pending Claude's decision. [Current complete gzip](C5_PERSON_D19_20261017.json.gz), [small receipt](C5_PERSON_D19_RECEIPT_20261017.json), and [commands/result record](OFFICE_DEMO_REVIEW_FOLLOWUP_20261017.md).

The final pre-follow-up review count is **122 passed** per [#47 review](https://github.com/Polalalabear/amidst/pull/47#issuecomment-6232257803). The120/75.70s below is the earlier author run before the two final tests, retained with its original timing; it is not the final count. Current changed-code focused results are recorded separately.

## Historical C5 behavior at 6bafe04

`POST /api/frame_retrieval` now serves the v1.1 contract: TIME_RANGE and HYPOTHESIS (PATHS / REACHABLE_REGIONS), range-indexed frame references, window ordering/truncation, `frame_evaluations`, resolved `visibility_entries`, `frame_outcomes` and K5 `negative_evidence_candidates`. Camera/time/config/visibility overrides and GT are not accepted. Research role and same-session hypothesis references remain required. Limits:4 cameras,20s window,64 result frames,512 frame records/query,5s cooperative deadline; expiry or missing inputs yields UNKNOWN. No hard process deadline is claimed.

C4b automatically starts with **2 BLIND_INTERVAL_BASELINE entries**, each containing17 real no-detection frames on its camera at4.8–8.0s. The exact D18 endpoints remain FRONT4.6→REAR8.2, without D7 or snapping. K1 is **READY,1 hypothesis,17 reachable regions; unseen PASS with0 steps without negative evidence**. Max/mean step speed is0.352376m/s under unchanged[0,2]m/s configuration. This demonstrates configured source-map feasibility for these endpoints, not whole-building connectivity.

A real TIME_RANGE retrieval of4.8–8.0s returns34 frames,34 frame_evaluations with count0, and2 RETRIEVAL_FEEDBACK entries. Appending them through the same-session previous-response hash yields READY, a verified K5 chain and2 pruning-log steps. It prunes0 additional paths in this run because the same visible footprints were already covered by baseline evidence. No artificial evidence was added to force a pruning result. The original33 observations remain MISSING/null; identity UNCONFIRMED and physical navigation/collision UNKNOWN.

C7's separate restricted_ref/restricted_regions input is available in review_evidence, with status **AWAITING_CLAUDE_K1_NATIVE_SUPPORT**. It is not inserted into walkable/unknown regions or used to change the lattice/score. Native K1 policy labels remain Claude's dependency; this PR does not pretend they exist.

## Independent static source visibility

The C5 exporter runs a read-only Blender process against the pinned original source at frame220, verifies source SHA/size/mtime before/after, checks the bundle camera matrices, and builds its own inference-side BVH. It reads no C6 planning rays, GT, renderer target visibility/trajectory/depth, or coarse annotation geometry. Annotation collections/prefixes are excluded from occluders (131 excluded instances); physical source obstacles remain. The source snapshot is299 mesh instances /638682 triangles;288 nonopaque-material triangles are retained as UNKNOWN hits rather than opaque or clear rays. No Blender render/save occurs.

Per-run probes are floor+.002/.852/1.702m (height1.70m,radius.25m), after calibrated FOV/clip checks. Any foot/torso/head probe visible means that XY sample is visible, matching C6's union definition. The exporter tested42510 XY samples per camera,76139/76199 actual rays after FOV/clip;5054/4018 samples were visible through torso/head while the foot was not. These are raw-ROI sample counts, not physical-area or identity claims.

The0.25m raster uses9 XY locations per cell on a0.125m subgrid. Only cells with all9 union samples VISIBLE and whose entire square lies within the C7 source-floor support enter the positive footprint. Mixed/unknown cells stay UNKNOWN; cells with all sampled points not visible are explicitly named SAMPLED_NOT_VISIBLE_NOT_CONTINUOUS_BLIND_PROOF. Unsampled continuous visibility remains UNKNOWN. Cell codes, grid resolution, source/calibration/floor/run/config/producer hashes and UNKNOWN domain are retained. Polygons are individual supported cells, so holes are never filled by an exterior-ring shortcut. K1 retains its body-radius/cell erosion rules.

| Camera | Sampled positive footprint area m² | UNKNOWN mixed cells | Outside source floor support cells |
| --- | --- | --- | --- |
| FRONT |205.375|349|3354|
| REAR |202.5625|349|3354|

The footprints are bounded sampled static-source visibility, **not continuous or global blind-area proof**. They do not certify detector recall. An unflagged/truncated target or detector miss can cause false pruning; GT/RQ2 evaluation must check that after freeze. Evidence applies only at the actual5Hz frame times, never to intervals between frames. No C6 planning classification was substituted for an RGB no-detection.

## Frame evaluations / integrity / counters

A frame gets NO_DETECTION only when all four flags are exactly true (`frame_available`, `rgb_hash_verified`, `provenance_ok`, `perception_evaluated`) and the **whole frame** measurement_count is integer0. Rejected components still count as detections: a null projected point is not no-detection. Missing/malformed/unevaluated flags produce UNKNOWN; any component produces DETECTION_PRESENT. Source RGB hashes are checked at index startup, on retrieved frames and again on the union of frames used by baseline/feedback before each K1 call. Hash mismatch/symlink is fatal; unavailable evidence cannot keep a cached PASS.

The index is prebuilt into per-camera sorted time arrays with bisect range lookup; HYPOTHESIS matching checks only bounded time-window records and the cached footprint geometry. Startup verifies all100 source RGBs; that startup cost is separate from query counters. The actual34-frame query read34 frame records and2 visibility entries. Last freeze's warm query took121.436583ms total (index lookup.056666ms; frame/perception lookup and conversion121.379917ms). This includes selected RGB hashing, not startup perception or offline rays, and is an in-process API measurement, not browser/socket latency. latency_ms is excluded from the retrieval output hash and from deterministic freeze payloads; measured values remain in the console/result record.

`C5_INDEX_SCALE_20261017.json` is a separate SYNTHETIC metadata-only benchmark, excluded from demo/evidence. It creates10⁵/10⁶ indexed records without images/rendering;100 queries each read exactly17 records. At10⁶: build.415144s, p50.508333ms /p95.517625ms. It does **not** measure RGB I/O, geometry, detection, full UI latency or research accuracy.

## Reproduce

Read-only ray export (uses the existing Blender/environment/assets; no install):

```sh
/Applications/Blender.app/Contents/MacOS/Blender --factory-startup --disable-autoexec -b blender/school_v3.blend --python scripts/export_floor_visibility.py -- --config configs/c5_office_person_visibility_v1.json --safe-inputs data/engineering/office_person_20261016_v1/office/safe_inputs.json --output /private/tmp/C5_STATIC_RAYS_REPRO.json
PYTHONPATH=src UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/build_floor_visibility_index.py --rays /private/tmp/C5_STATIC_RAYS_REPRO.json --map docs/engineering/C7_OFFICE_SOURCE_MAP_20261017.json --safe-inputs data/engineering/office_person_20261016_v1/office/safe_inputs.json --hybrid-config configs/hybrid_contact_v1_1.json --output /private/tmp/C5_INDEX_REPRO.json
PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/freeze_person_blind_hypotheses.py --bundle data/engineering/office_person_20261016_v1/office --output /private/tmp/C5_API_REPRO.json
```

Use new output names; producers refuse existing outputs. The API producer uses the committed index pin, not a caller path override. Two independent API freezes matched byte-for-byte at decoded SHA6492e349c86ec243e2fb571d9a523d5d801a32c629dbc187163b50bbc8ce3db5. The complete response is losslessly packaged as .json.gz (empty gzip filename,mtime0), with a small review receipt. This avoids a large repeated JSON diff while retaining every API field.

```sh
PYTHONPATH=src UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/package_c5_receipt.py --input /private/tmp/C5_API_REPRO.json --output /private/tmp/C5_API_REPRO.json.gz --receipt /private/tmp/C5_RECEIPT_REPRO.json
PYTHONPATH=src UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/benchmark_frame_retrieval_index.py --output /private/tmp/C5_SCALE_REPRO.json
```

## 實際產出 / Actual output

- Model / effort: UNKNOWN (authoritative session metadata not exposed).
- PR / commits: codex/c5-visibility-retrieval, stacked on PR #46/a6ce40c; selected C7 inputs copied exactly from a69e63f. Exact C5 SHA recorded on publication. K1 #33/K5 #36 untouched; no merge/rebase/force-push.
- Files changed: C5 static exporter/policy/index builder and runtime retrieval; versioned C5 config and hypothesis binding; C4b baseline/feedback/source freshness and sealed response annotations; research-only API schemas/dispatch/session refs; launcher dependency fingerprint; deterministic freeze/packaging and scale scripts; focused tests, selected C7 policy inputs, index/artifact/receipts, this report/index/WORK_LOG. Full file list in PR.
- Commands/results: exact focused command below **120 passed in75.70s**. After the last missing-index/freshness refinements, focused C5/C4b checks34 passed in17.65s and final C5 API checks12 passed in7.67s (overlapping, not summed). Ruff full checks on new modules/tests and Ruff F on existing service/launcher PASS; git diff --check PASS. Export/build/freeze/package/scale commands above executed with task output paths; source export log/RAW rays stay LOCAL. No live service was launched.
- Artifacts: repository hashes below. LOCAL static-rays-v1.json SHA9831e299e35842ef568ac0390f97f7f5915fa710ad5d6def010ad0cfe05e337d; raw ray output and full decoded API files stay under /private/tmp/amidst-c5-20261017/. No RGB/raw DB/GT/.blend uploaded.
- Verified: independent static source rays and unchanged source identity; three-probe/FOV/clip/UNKNOWN semantics and C6 policy-case consistency; actual NO_DETECTION versus rejected components; baseline2 / feedback2 and K5 append-only/session validation; original33 MISSING preserved; exact response/dependency/source pins; WSGI JSON dispatch, role/override guards; sorted range counters, query budgets, synthetic scale, lossless artifact and independent API reproduction.
- Not verified: GT coverage/false prunes/RQ1/RQ2, exact continuous visibility between samples/frames, corridor or whole-school coverage, live socket/browser/K4/K6 demo, native K1 D15 labels, full suite. No render, source mutation, installation, venv/worktree creation, external model call or live service changes.
- Deviations/UNKNOWN/follow-ups: index is bounded to Office person run/source support; no other camera/run borrows it. K1 policy support remains Claude's explicit dependency. The source index's finite raster resolution is exposed rather than treated as global blindness. Feedback prunes0 additional paths in this run; no false demonstration of convergence. Missing index returns a sealed UNKNOWN response with unmeasured totals null. CP2/CP3 approvals remain separate.

Focused main command:

```sh
PYTHONPATH=src:scripts OFFICE_TEST_ASSETS=/Users/polalabear/Developer/amidst UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -m pytest tests/unit/test_hybrid_contact.py tests/unit/test_hybrid_contact_report.py tests/unit/test_floor_visibility_index.py tests/unit/test_restricted_policy.py tests/workbench/test_blind_hypothesis_integration.py tests/workbench/test_frame_retrieval.py tests/workbench/test_office_demo_presets.py tests/workbench/test_office_launcher.py tests/workbench/test_target_reconstruction.py -o addopts='' -q
```

Final refinement commands use the same environment with `-m pytest tests/unit/test_floor_visibility_index.py tests/workbench/test_frame_retrieval.py tests/workbench/test_blind_hypothesis_integration.py -o addopts='' -q` (34 passed) and `-m pytest tests/workbench/test_frame_retrieval.py -o addopts='' -q` (12 passed).

- `docs/engineering/C5_PERSON_VISIBILITY_INDEX_FINAL_20261017.json` SHA-256 `e128a79c107c8333b9c6e9d83145e1cb4787c90ff1c2684fb38d9e76717ad62e`
- `docs/engineering/C5_PERSON_C4B_REAL_EVIDENCE_VERIFIED_20261017.json.gz` SHA-256 `f0142a103344920e20bcfb98209d16d08895e2e2ab43f13f9c9aeae645ede998`
- `docs/engineering/C5_PERSON_RESULT_RECEIPT_20261017.json` SHA-256 `fd5b23949eab925febc6259df7a5bf54dad46eeb6fb406531b89267230e69095`
- `docs/engineering/C5_INDEX_SCALE_20261017.json` SHA-256 `09c35d0347392c0c9664ec666e351c0f3072d8a0a7a3656f4f13bf4ba70d3cf3`
- `docs/engineering/C5_DEPENDENCIES_20261017.json` SHA-256 `553388b73ff62ef75bd58210e600d02a1017930475bc5edee43adc1d756e65ee`

Post-commit preflight at `148e1a0cd65a` PASS (three scene IDs; fingerprint b360fd526d859cb40648a8229eb583e83ded93d63bf7b6894b0e366012f40d5f):

```sh
PYTHONPATH=src:scripts OFFICE_PRESETS="$PWD/configs/office_demo_presets_person_v1.json" UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -c 'import start_office_demo; print(start_office_demo.preflight())'
```

This validates the clean-checkout dependency pins only; no HTTP listener/browser readiness is claimed. Existing unrelated untracked assets/history remain unchanged.
