# E7 Colab Upload Pack Specification v1 (`#727` / `#731`, D380 / D382 / D384 / D385 / D392)

## Purpose

Defines the exact directory layout, `MANIFEST.sha256` format, pre-upload enforcement gate, and GT-isolation rules for the private Google Drive upload pack consumed by [`notebooks/e7_colab_decider_eval.ipynb`](../../notebooks/e7_colab_decider_eval.ipynb).

- **Prepared by:** Codex on Mac (from `local/evidence/`), gated via `write_colab_answer_table` and `verify_colab_pack_pre_upload`.
- **Consumed by:** User running `notebooks/e7_colab_decider_eval.ipynb` on Colab Pro (Run All).
- **One-Click Run All Condition:** Out of the box, Run All completes end-to-end (including Cell 7 scoring and Cell 8 report export) for all audited models (`Qwen/Qwen2.5-VL-3B-Instruct`), while unaudited custom-code models (`convaiinnovations/laya`, `GSAI-ML/LLaDA-V`) are cleanly recorded as `SKIPPED_UNAUDITED` without aborting. Including `laya` or `LLaDA-V` requires auditing their HF custom `.py` files and setting `custom_code_audited = True` + pinned `audited_commit` in Cell 1. For formal `#732` runs, pin `PINNED_GIT_COMMIT` and every `hf_revision` to exact 40-char commit SHAs.
- **Identity status:** `UNCONFIRMED`.
- **No paid API calls** in Colab; Colab Pro compute cost is user-borne and recorded in hardware provenance.

## Directory Layout

```text
e7-colab-pack-<YYYYMMDD>/
├── MANIFEST.sha256                  # Required: `<64-hex>  <relative/path>` for every file below
├── PACK_INFO.json                   # Dataset scopes included, creation UTC, source git commit
├── requests/
│   ├── e3_16_segments.jsonl         # Frozen AO requests (no GT) for old 16 E3 segments (exploratory)
│   └── e6_12_segments.jsonl         # Optional: AO requests (no GT) for E6 12 segments (additional group)
├── frames/
│   └── <case_id>/<cam>/<tick>.png   # Frozen 320x180 synthetic frames referenced by requests/*.jsonl
├── baselines/
│   └── e5_report_frozen.json        # Frozen E5 report (B1, AO, AO-L metrics — decision outputs, not raw GT)
└── scoring_only/                    # READ ONLY BY CELL 7 (SCORING CELL); NEVER READ BY DECIDERS
    └── answer_table.json            # Derived label-only answer table (#717, D385 approved for Colab scoring cell only)
```

## Allowed vs Forbidden Files

- **Allowed:**
  - Frozen synthetic 320x180 frames (`frames/`)
  - Frozen detection indices and AO decision requests (`requests/*.jsonl`)
  - Frozen B1 / AO / AO-L report JSON (`baselines/e5_report_frozen.json`)
  - Derived **label-only** answer table under `scoring_only/answer_table.json` (D385: allowed for Colab scoring cell ONLY; decider code is tested to never read it; strictly bounded by the field allowlist below)
- **Strictly Forbidden (NEVER upload to Colab or Drive):**
  - Raw Ground Truth JSON/CSV (`gt/`, `a-log.json`)
  - Renderer actor trajectories, world coordinates, visibility tables, depth maps, `.blend` files
  - GT bounding boxes (`gt_boxes`, `gt_body_box`), per-camera visibility fields (`gt_visible`, `visibility`), or per-request visibility/occlusion regime labels (`gt_regime`, D392) inside `answer_table.json`
  - API keys or credentials

## Answer Table Schema (`scoring_only/answer_table.json`, D385 / D392 Label-Only Allowlist)

Per D385 and D392, raw GT, trajectories, visibility, depth, and `gt_regime` NEVER leave Mac. Before building the upload pack, Mac-side tooling pre-matches GT body boxes against each request's frozen candidate detections (via `e3_scoring.judge_box`) to produce **label-only** expected answers and `expected_detection_ids`. Any regime-stratified analysis is performed on Mac by joining on `request_id`.

`src/amidst/evaluation/e7_scoring_bridge.py` enforces hard invariants BOTH **before writing / pre-upload on Mac** (`write_colab_answer_table`, `verify_colab_pack_pre_upload`) and **at load/scoring time in Colab**:

1. **Strict Field Allowlist & Value Type/Enum Validation (`ALLOWED_ANSWER_ENTRY_FIELDS`):**
   - `expected_answer` (required `str`: one of `"SELECT"`, `"NOT_VISIBLE"`, `"STILL_HERE_OCCLUDED"`, or `"UNCERTAIN"`)
   - `expected_camera_ids` (`list[str]` of expected camera IDs; empty `[]` when `NOT_VISIBLE`)
   - `expected_detection_ids` (`dict[str, list[str]]` mapping `camera_id -> [pre-matched candidate detection_ids]` or `list[str]`; numeric boxes such as `[[x1, y1, x2, y2]]` are rejected with `ValueError("D385_INVALID_ANSWER_VALUE: ...")`)
   - Optional metadata labels only: `request_id` (`str`), `case_id` (`str`), `tick` (`int`, not `bool`)
   - Any other field (e.g. `box_xyxy`) raises `ValueError("D385_DISALLOWED_ANSWER_FIELD: ...")`.

2. **Hard-Rejected Forbidden GT Fields (`FORBIDDEN_GT_FIELDS`):**
   - `gt_visible`, `gt_boxes`, `actors`, `depth`, `visibility`, `trajectories`, `world_xy`, `gt_body_box`, `gt_regime`
   - Presence of ANY of these keys anywhere in `answer_table.json` (top-level or nested) immediately raises `ValueError("D385_FORBIDDEN_GT_FIELD: ...")`.

3. **Mac-Side Pre-Upload Enforcement Gate (`write_colab_answer_table` + `verify_colab_pack_pre_upload`):**
   - Mac-side pack creation (including `scripts/experiments/run_all.sh` Stage 4) MUST write `scoring_only/answer_table.json` through `write_colab_answer_table(path, table)` (validates BEFORE creating the file; on failure raises `ValueError` and creates no file).
   - Before uploading to Drive, run `python -m amidst.evaluation.e7_scoring_bridge verify-pack --pack-root <pack_root>`, which validates `scoring_only/answer_table.json`, rejects forbidden GT files/directories (`gt/`, `a-log.json`, `*.blend`) and forbidden keys in `requests/*.jsonl`, and verifies `MANIFEST.sha256` if present.

4. **`OWN_BOX` Handling (`NEEDS_MAC_SCORING`):**
   - Because Colab does not receive GT boxes, any decider output with `answer == "OWN_BOX"` on a visible target cannot be scored in Colab and is recorded with `outcome = "NEEDS_MAC_SCORING"` (`correct = False`, counted separately in `needs_mac_scoring_count` so accuracy is never inflated). Final `OWN_BOX` IoU scoring happens on Mac.

5. **Missing Answer Table Hard-Fail:**
   - Cell 7 of `notebooks/e7_colab_decider_eval.ipynb` raises `FileNotFoundError` immediately if `scoring_only/answer_table.json` is missing or unreadable (no silent `{}` / `GT_UNKNOWN` fallback).

Example valid `scoring_only/answer_table.json` entry:

```json
{
  "E3-A1|t0": {
    "request_id": "E3-A1|t0",
    "case_id": "E3-A1",
    "tick": 0,
    "expected_answer": "SELECT",
    "expected_camera_ids": ["CAM_EXT_CAR"],
    "expected_detection_ids": {
      "CAM_EXT_CAR": ["D1"]
    }
  }
}
```

## MANIFEST Verification Contract

1. Every file in the pack (except `MANIFEST.sha256` itself) MUST appear in `MANIFEST.sha256` with standard `sha256sum` format: `<64-lowercase-hex>  <relative-posix-path>`.
2. Cell 4 of `notebooks/e7_colab_decider_eval.ipynb` calls `amidst.evaluation.e7_decider_eval.verify_manifest_sha256(PACK_ROOT)` before loading any data.
3. On **any** missing file, path traversal, or SHA-256 mismatch, execution **stops immediately** with `ManifestVerificationError`.

## Request JSONL Schema (`requests/*.jsonl`)

Each line is a JSON object with inference-only fields:

```json
{
  "request_id": "E3-A1|t0",
  "case_id": "E3-A1",
  "dataset_group": "e3_16_segments",
  "tick": 0,
  "camera_ids": ["CAM_ENTRY", "CAM_EXT_CAR"],
  "variable_text": "DETECTIONS ...",
  "candidates": [
    {"detection_id": "D1", "camera_id": "CAM_EXT_CAR", "box": [17.9, 67.0, 46.6, 131.2], "score": 0.83}
  ],
  "image_paths": {
    "CAM_ENTRY": "frames/E3-A1/CAM_ENTRY/000000.png",
    "CAM_EXT_CAR": "frames/E3-A1/CAM_EXT_CAR/000000.png"
  }
}
```
