# D124 DEMO_DEFAULT index and RULE_ONLY trial

User authorization: 2026-11-07 chat, for an engineering preview before Sunday. These values are not formally approved research parameters. Frozen parameter_set_v1.json, source assets, original RGB and run clocks are unchanged. No integration merge was created.

## Actual output

| Run | Indexed / inferred frames | Detector candidates | Person candidates | QT-25 demo checks | Camera-local segments / steps |
| --- | --- | --- | --- | --- | --- |
| A4-1 | 1000/1000 | 1160 | 125 | 17 PASS | 3 / 25 |
| B4-1 | 1050/1050 | 2158 | 121 | 17 PASS | 4 / 65 |

Candidate counts are not independent people, accuracy or human labels. Model: official RT-DETR R18, CPU FP32, 640x640, seed 7, two threads, strict 80-class weights SHA-256 `3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0`. Every one of the 49 local official source-file pins was checked. The source folder has no Git repository; actual model Git HEAD is UNKNOWN. The adapter-reported historical code_source commit is REPORTED, not a newly verified Git checkout.

The source has 1000/1050 frames at 5 fps. All were inferred. Minimum free space observed during A4 inference: 14.5131 GiB; B4: 14.5559 GiB, above the 8 GiB hard floor. Forward-stage sums were 276.936741 s and 296.328899 s. These are actual stage measurements, not complete wall-clock or physical display performance.

## Scope and gate boundaries

- The QT-25-T DEMO profile runs the 14 named index checks from the existing source-pinned conformance checker, resulting in 17 per-document PASS results per run; it also verifies D124 source/config/output byte pins. It does not select the formal production receipt decoder or approve parameters.
- The CX-8-T DEMO profile replays the existing LocalLinker with explicit DEMO_DEFAULT LinkParameters, without forging an APPROVED document. Seed policy is the first frame with person candidates: exactly one qualifying observation or UNKNOWN; no best-looking-frame selection. Each camera is independent.
- The result is CAMERA_LOCAL_SELECTED_SEED, RULE_ONLY, identity UNCONFIRMED, physical navigation UNKNOWN. Cross-camera association/handoff and full-workbench tracking-source integration remain NOT_EVALUATED. A4 has 3 local segments across 4 cameras; B4 has 4 across 5. This is not the full #417/CX-8 formal acceptance.
- No Agent, Q3, external API, Windows, renderer, formal experiment, GT, visibility, depth or scenario timing was used as inference input. Source adapter preflight opens only manifest-listed safe metadata; pixel reads are exact pinned RGB.
- A4 executed source commit `5831cf5` (full source-file hashes in its LOCAL receipt); B4 executed `bf03add`. The later metadata-only provenance cleanup, checker and documentation do not change detector values or rerun the model. Do not call the final delivery head the executed predictor head.
- Changed parameter values require new outputs and a rerun. Sunday user approval is still pending; formal eligibility is false.

## Complete parameter table

APPROVED below quotes the historical frozen table only; the two new run-bound configurations as a whole remain DEMO_DEFAULT. Agent/Q3 and nonlocal-tracking fields are listed for review but not executed. NMS IoU null means not applicable: this official adapter does not apply NMS.

| Parameter | Value | Source-table status |
| --- | --- | --- |
| top_k | `3` | APPROVED |
| agent_max_rounds | `3` | APPROVED |
| agent_total_budget_ms | `5000` | APPROVED |
| agent_call_timeout_ms | `2000` | APPROVED |
| link_iou_min | `0.3` | APPROVED |
| link_center_dist_max_diag_ratio | `0.5` | APPROVED |
| link_max_gap_us | `600000` | APPROVED |
| link_max_gap_samples | `2` | APPROVED |
| agent_max_illegal_submissions | `2` | APPROVED |
| search_window_us | `6000000` | APPROVED |
| research_interval_us | `1000000` | APPROVED |
| session_max_research_rounds | `6` | APPROVED |
| fallback_budget_ms | `1000` | APPROVED |
| session_max_agent_rounds | `12` | APPROVED |
| stride_samples | `1` | APPROVED |
| switch_min_presence | `"MATCH_STRONG"` | DEMO_DEFAULT |
| q3_llm_timeout_ms | `2000` | DEMO_DEFAULT |
| exit_rule | `"BBOX_BOTTOM_MIDPOINT_IN_ROI"` | DEMO_DEFAULT |
| index_score_floor | `0.3` | DEMO_DEFAULT |
| nms.iou | `null` | DEMO_DEFAULT |
| query_min_score | `0.4` | DEMO_DEFAULT |
| segment_merge_gap_us | `200000` | DEMO_DEFAULT |
| link_min_score | `0.4` | DEMO_DEFAULT |
| link_color_rule | `"NOT_NONE"` | DEMO_DEFAULT |
| link_ambiguity_margin | `0.05` | DEMO_DEFAULT |
| exit_boundary_inclusive | `true` | DEMO_DEFAULT |
| evidence_max_observations | `64` | DEMO_DEFAULT |
| q3_max_llm_attempts | `1` | DEMO_DEFAULT |
| llm_temperature | `0.0` | DEMO_DEFAULT |
| llm_seed | `7` | DEMO_DEFAULT |
| color_method_sha256 | `"2af90afce923c837a61cd3e507a54cfb0e14dee959d76c79bc641385b7810368"` | DEMO_DEFAULT |
| index_grid_origin_frame | `0` | DEMO_DEFAULT |
| hsv_config | `{"bands":{"blue":[[0.5,0.72]],"green":[[0.19,0.45]],"orange":[[0.05,0.12]],"purple":[[0.72,0.85]],"red":[[0.95,0.05]],"yellow":[[0.12,0.19]]},"crop_ratio":0.5,"histogram_bins":18,"min_pixels":64,"saturation_min":0.2,"strong_ratio":0.6,"truncation_max_ratio":0.2,"value_min":0.2,"version":"D131-DEMO-HSV-v1","weak_ratio":0.3}` | DEMO_DEFAULT |

## Reproduction and LOCAL artifacts

The exact executed configuration byte pins and all output byte pins are in `D131_417_DEMO_DEFAULT_RESULTS.json`. Actual absolute locators are posted to issue #417 as requested. Keep index JSONL, observations, RGB, model weights and source assets LOCAL. `$DEMO_LOCAL_ROOT` refers to that posted output directory.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:$EXISTING_RUNTIME_DEPS "$EXISTING_PYTHON" -B scripts/run_d124_demo_default.py --permit-real-rgb --demo-default --config "$RUN_CONFIG" --config-sha256 "$RUN_CONFIG_SHA256" --safe-bundle "$SAFE_BUNDLE" --model-source "$MODEL_SOURCE" --source-hashes "$MODEL_HASHES" --weights "$WEIGHTS" --out-dir "$NEW_RUN_OUTPUT" --seed 7 --threads 2
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src "$EXISTING_PYTHON" -B scripts/check_d124_demo_default.py --index-dir "$NEW_RUN_OUTPUT" --config "$RUN_CONFIG" --config-sha256 "$RUN_CONFIG_SHA256" --safe-bundle "$SAFE_BUNDLE" --produce-local-tracks
```

The first command refuses an existing output directory, requires both explicit demo/real-RGB flags, pins source metadata/model files and enforces 8 GiB before each frame/operation/write. The checker refuses existing output receipts when producing them. Use a fresh batch after any value change; do not overwrite prior evidence.

## Verification

`tests/q1q5/test_d124_demo_default.py`, `test_detection_index.py`, `test_hsv_color.py`, `test_linker.py`: 75 passed in 0.23 s. Source/hash/symlink/low-disk/authority/ambiguous-seed negative cases are synthetic. No-allow architecture guard and diff-check are rerun at the final delivery head. Both real output demo checkers PASS as above. Production/formal gates remain NOT_RUN.
