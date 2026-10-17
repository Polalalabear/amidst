# C5 D21 strict visibility — 2026-10-17

Refs #18/#17/#26, D21 on #47, retrieval contract #45 @ed64070c58acd22ffab146edbcb293178c6ed9b2. Stacked on #50/cd6c854. Draft, no merge; CP2/CP3 unapproved. K1/K5 synchronization waits for the applied_frame_keys completion notice on #44. C6 remains paused under D14.

## Actual footprints

| Camera | suggestion ANY area m² | strict area m² | ANY cells | strict cells | cells_removed: visibility | cells_removed: detectability |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FRONT | 205.375 | **115.75** | 3286 | 1852 | **1434** | **0** |
| REAR | 202.5625 | **130.375** | 3241 | 2086 | **1155** | **0** |

Cells are0.25m squares,9 XY samples each on a0.125m subgrid. Foot+.002m and waist+.852m must both be VISIBLE at all9 points. UNKNOWN remains UNKNOWN. Admitted-cell minimum projected leg-box areas are301.608034875px FRONT and542.989010439px REAR, above112px=4×28: detectability excludes0 additional cells here. Tests prove one sample at111.999px excludes the cell while112px admits it. Every suggestion polygon is byte-for-byte the old index polygon. This is bounded sampled visibility, not continuous proof or detector recall.

Probe-visible counts cover all42510 ROI XY points per camera. Bits are **foot, waist, head**,1 iff that probe is VISIBLE;0 includes occlusion, UNKNOWN, FOV and clipping. These are point counts, not floor areas.

| Visible bits | FRONT | REAR |
| --- | ---: | ---: |
| 000 | 28502 | 28711 |
| 001 | 2396 | 2692 |
| 010 | 31 | 13 |
| 011 | 2627 | 1313 |
| 100 | 62 | 120 |
| 101 | 197 | 367 |
| 110 | 58 | 123 |
| 111 | 8637 | 9171 |

Export and index retain each point's three status codes: OCCLUDED0/VISIBLE1/UNKNOWN2/OUTSIDE_FOV3/CLIPPED4, in X_MAJOR_Y_MINOR order, with foot/waist/head order declared.

| Camera / rule | sampled visible | mixed UNKNOWN | sampled not-visible, not continuous blind proof | outside source support UNKNOWN |
| --- | ---: | ---: | ---: | ---: |
| FRONT / ANY | 3286 | 349 | 3487 | 3354 |
| FRONT / strict | 1852 | 689 | 4581 | 3354 |
| REAR / ANY | 3241 | 349 | 3532 | 3354 |
| REAR / strict | 2086 | 526 | 4510 | 3354 |

## D19 actual output under D21

| Version | 17-step sum cells | 17-step sum area m² | XY union cells | XY union area m² | representative paths |
| --- | ---: | ---: | ---: | ---: | ---: |
| NONE | **4498** | **281.125** | **592** | **37.0** | 1 |
| strict baseline applied | **4498** | **281.125** | **592** | **37.0** | 1 |
| baseline + retrieval feedback | **4498** | **281.125** | **592** | **37.0** | 1 |

**D21 removes0 reachable cells:0% summed and0% union reduction.** Baseline2 entries and feedback2 entries use the same34 real frames; neither removes a path. The receipt's region_comparison_by_origin compares baseline versus NONE and feedback additional to baseline, including all17 times. No region samples are truncated; area/count equality is checked. This is a frozen receipt field for OPEN FR-Q9, not an approved new K1 response field.

The old ANY freeze was independently recounted:4498→4092 summed cells (281.125→255.75m²),406 removed/−9.026233882%;592→499 union cells (37.0→31.1875m²),93 removed/−15.709459459%. The earlier−16.6% claim is superseded. The single representative also appears with NONE because #46 shortened the endpoint band; it is unrelated to negative evidence.

Demo wording: **「這段影格沒有提供足夠的排除證據」**. The frame wall still tells investigators which frames to review. No geometry, detector, speed or endpoint settings were tuned to force convergence. All33 original observations remain MISSING/null; identity UNCONFIRMED, physical authority UNKNOWN. **偵測器對比度與部分遮擋的漏判未驗證**; projected box area is a guard, not detector-recall or GT validation.

## Implementation and pending boundary

- sample_status retains ANY and adds FOOT_AND_TORSO_PROBES_VISIBLE. Export preserves old union codes and adds probe codes/combinations. Source BVH:299 meshes/638682 triangles,288 nonopaque triangles UNKNOWN,131 annotation instances excluded. No render/save, GT, target trajectory or renderer visibility/depth.
- Detectability uses a vertical camera-facing rectangle of width2r and foot-to-waist height. Its XY tangent is perpendicular to camera→sample. Four corners use calibrated pinhole intrinsics/extrinsics; shoelace quadrilateral area is measured, not bbox area. Invalid or clipped corners give0. Each cell retains the minimum over9 samples; the entry scalar is the minimum among admitted cells. This predicts the full unoccluded box, not visible pixel count.
- The versioned index binds source/run/clock/calibration/floor/body-size/producer hashes. polygons contains only strict, detectable cells. suggestion_polygons is the old ANY footprint, used solely for matching/ranking. ANY never emits negative polygons. Per-rule counts and visibility/detectability removals are separate.
- Retrieval guards the unchanged K5 converter: ineligible rules become UNKNOWN/VISIBILITY_RULE_NOT_ELIGIBLE; mismatched actual producer/version/difference_threshold/min_pixels become UNKNOWN/DETECTOR_PARAMETERS_MISMATCH. Raw frame_evaluations stay intact. Only guarded strict polygons reach evidence; baseline uses the same path. Freshness hashes each unique RGB once per K1 call.
- C4b collects server-held (camera_id, frame_ref, visibility_ref, producer, version) keys:34 unique with baseline,0 with NONE. Review says AWAITING_REVIEWED_K5_APPLIED_FRAME_KEYS_SYNC. K1/K5 files/pins remain unchanged. Native frame dedup has **not** been synchronized: current feedback still carries the same34 frames in2 further entries, with0 extra effect. Full dedup/restricted_regions wiring waits for #44's completion notice. No early copy of #48.

## 實際產出 / Actual output

- Model / effort: **gpt-6.1-sol / high**, current turn_context verified.
- PR / commits: codex/c5-d21-strict-visibility; base #50 cd6c854e05c87e6c3c45dac83c8c079121786c3a. Draft PR and SHA posted on #18/#17/#26/#47; no merge/rebase/force-push.
- Files changed: versioned config/index and person pin; exporter/builder/policy; retrieval actual-detector binding/guards; C4b frame-key collection; freeze/package producers; three focused test files; D21 report/receipt/gzip, history/index and current-result pointers. No frontend/K1/K5/source assets.
- Commands run and results: exact commands below. Three focused files **62 passed in19.08s**; after final one-read freshness optimization, affected two files **45 passed in17.73s** (overlap, not summed). Canonical Office/person pin and launcher **20 passed in32.36s**,0failed/skipped. Ruff and git diff --check PASS. Intermediate failures were a backwards synthetic camera and a missing ACTIVE field in a test hypothesis; corrected fixtures, final checks pass.
- Artifacts: index SHA7c464ec42d30afdd3489b53c8c0c2f6b866a4d542cc324ad8bd3aa89f8f0d83c; config SHA9baa3b3a9cd08589b3bce7c22aa9e59e110aa745791526ea4122db9f17596229; complete gzip SHAffa169e0adad3a74522f991961e49e456f2d468d8c272d20b25929f98ac4761f; decoded SHAf23e9dd9cc35aed74362126cba90d1f2cf041659559a71d079d84993aa6f3391; canonical SHAace13bf9cec17ae39d0f068b439a5e3eaabee715e145f0567efda17070d99887; receipt SHA93d016bcf461f5b719b5ef1fc89db19d5b90ae712a9c515139d6b562956ecba4. LOCAL rays /private/tmp/amidst-d21-20261017/static-rays-d21-v1.json SHA022d19549ce924ddc8b52ce518e05fc1eee0612848b8f8648167019b5f06b6f4; decoded API /private/tmp/amidst-d21-20261017/api-final-v2.json. Old freezes retained.
- Verified: source SHA/size/mtime unchanged before/after export; probe/status/count consistency, calibrated area and112px boundary/all-nine minimum; suggestion-only ranking; rule/detector/session/freshness guards; original observations/legacy canonical outputs; all seals/producer/dependency pins; complete counts/union; two API freezes byte-identical, gzip lossless, no private API locators.
- Not verified: native K5 frame dedup, K1 restriction sync, GT/RQ1/RQ2/recall/false-prune rates, continuous visibility/other scenes, browser/full demo/full suite. Existing services untouched; Claude's independent ongoing acceptance is not counted. No install/new environment/worktree.
- Deviations, UNKNOWN items and follow-ups:0 convergence reported honestly. FR-Q9 reporting location is the receipt pending API agreement. Frame-key collection prepared; K1/K5 sync pending. C6 paused. One preliminary index command ran before export finished and got FileNotFoundError; rerun only after successful export.

## Executed reproduction commands

Use fresh output names: producers refuse existing outputs. Paths below are LOCAL.

    /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --disable-autoexec -b blender/school_v3.blend --python scripts/export_floor_visibility.py -- --config configs/c5_office_person_visibility_d21_v1.json --safe-inputs data/engineering/office_person_20261016_v1/office/safe_inputs.json --output /private/tmp/amidst-d21-20261017/static-rays-d21-v1.json
    PYTHONPATH=src UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/build_floor_visibility_index.py --rays /private/tmp/amidst-d21-20261017/static-rays-d21-v1.json --map docs/engineering/C7_OFFICE_SOURCE_MAP_20261017.json --safe-inputs data/engineering/office_person_20261016_v1/office/safe_inputs.json --hybrid-config configs/hybrid_contact_v1_1.json --output /private/tmp/amidst-d21-20261017/index-final-v1.json
    PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/freeze_person_blind_hypotheses.py --bundle data/engineering/office_person_20261016_v1/office --output /private/tmp/amidst-d21-20261017/api-final-v2.json
    PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/freeze_person_blind_hypotheses.py --bundle data/engineering/office_person_20261016_v1/office --output /private/tmp/amidst-d21-20261017/api-repeat-v2.json
    cmp /private/tmp/amidst-d21-20261017/api-final-v2.json /private/tmp/amidst-d21-20261017/api-repeat-v2.json
    PYTHONPATH=src UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/package_c5_receipt.py --input /private/tmp/amidst-d21-20261017/api-final-v2.json --output /private/tmp/amidst-d21-20261017/final/C5_PERSON_D21_20261017.json.gz --receipt /private/tmp/amidst-d21-20261017/final/C5_PERSON_D21_RECEIPT_20261017.json

    PYTHONPATH=src:scripts OFFICE_TEST_ASSETS=/Users/polalabear/Developer/amidst UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -m pytest tests/unit/test_floor_visibility_index.py tests/workbench/test_frame_retrieval.py tests/workbench/test_blind_hypothesis_integration.py -o addopts='' -q
    PYTHONPATH=src:scripts OFFICE_TEST_ASSETS=/Users/polalabear/Developer/amidst UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -m pytest tests/workbench/test_frame_retrieval.py tests/workbench/test_blind_hypothesis_integration.py -o addopts='' -q
    PYTHONPATH=src:scripts OFFICE_TEST_ASSETS=/Users/polalabear/Developer/amidst UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -m pytest tests/workbench/test_office_demo_presets.py::test_frozen_office_responses_equal_except_quality tests/workbench/test_office_demo_presets.py::test_person_split_preset_uses_pinned_config_and_d18_defaults tests/workbench/test_office_launcher.py -o addopts='' -q
    .local-worktrees/phase1-finalization/.venv/bin/ruff check scripts/freeze_person_blind_hypotheses.py scripts/package_c5_receipt.py scripts/export_floor_visibility.py scripts/build_floor_visibility_index.py src/amidst/geometry/visibility_policy.py src/amidst/geometry/floor_visibility_index.py src/amidst/workbench/frame_retrieval.py src/amidst/workbench/contact_scene.py src/amidst/workbench/blind_hypothesis_integration.py tests/unit/test_floor_visibility_index.py tests/workbench/test_frame_retrieval.py tests/workbench/test_blind_hypothesis_integration.py
    git diff --check

[Complete derived API gzip](C5_PERSON_D21_20261017.json.gz) · [small receipt](C5_PERSON_D21_RECEIPT_20261017.json) · [versioned index](C5_PERSON_VISIBILITY_INDEX_D21_20261017.json).

Post-commit read-only launcher preflight at5ed536c75059d535991746b5cfac2d20af0932eb passed: all3 scene registrations and dependency pins verified, fingerprint cdb88e4ddcfa6ea205039b3e0d3fd33a10eb9fd33d4ff8a217978b892d99ecf9. Command: PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -c 'import start_office_demo as l; print(l.preflight())'. No HTTP listener/service start or browser claim.
