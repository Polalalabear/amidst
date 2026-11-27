# E7 Colab Upload Pack Specification v1 (`#727` / `#731`, D380 / D382 / D384 / D385 / D392)

## Purpose

Defines the exact directory layout, `MANIFEST.sha256` format, pre-upload enforcement gate, and GT-isolation rules for the private Google Drive upload pack consumed by [`notebooks/e7_colab_decider_eval.ipynb`](../../notebooks/e7_colab_decider_eval.ipynb).

- **Prepared by:** Codex on Mac (from `local/evidence/`), gated via `write_colab_answer_table` and `verify_colab_pack_pre_upload`.
- **Consumed by:** User running `notebooks/e7_colab_decider_eval.ipynb` on Colab Pro (Run All).
- **One-Click Run All Condition:** Run All completes end-to-end from CELL 1 on a fresh Colab runtime (Python 3.13, L4; accepted for the per-tick laya run, #766). Audited parties run: `qwen_vl` (`Qwen/Qwen2.5-VL-3B-Instruct`, `image_text` and `text_only`), and `laya_text` / `laya_typed` (`convaiinnovations/laya`, audited commit `246177e5…`, native `RLAgent` path). The unaudited custom-code model `GSAI-ML/LLaDA-V` is recorded as `SKIPPED_UNAUDITED` without aborting; including it requires auditing its HF custom `.py` files and setting `custom_code_audited = True` + pinned `audited_commit` in Cell 1. For formal `#732` runs, pin `PINNED_GIT_COMMIT` and every `hf_revision` to exact 40-char commit SHAs.
- **Identity status:** `UNCONFIRMED`.
- **No paid API calls** in Colab; Colab Pro compute cost is user-borne and recorded in hardware provenance.

## Delivery format and Colab runtime (#766, notebook `2026-11-27-r2`)

- **One zip.** Mac builds `e7-colab-pack.zip` from the pack folder with `python -m amidst.evaluation.e7_colab_runtime make-zip --pack-root <pack_root> --zip <zip>` (runs `verify-pack` first; stored without compression). The zip's SHA-256 goes to the sidecar `e7-colab-pack.zip.sha256` (`<hex>  <name>`) next to it, because `PACK_INFO.json` is inside the zip and cannot contain the zip's own digest. Upload both to `MyDrive/amidst/`.
- **Colab side (CELL 4):** the zip is checked against the sidecar, extracted to local `/content/e7-colab-pack` (path traversal refused), then `MANIFEST.sha256` is verified on local disk (replaces reading 4252 small files from Drive). A pre-extracted pack at `PACK_ROOT` is still accepted. The zip SHA-256 is written to `RUN_NOTES.json`.
- **Pinned runtime (Python 3.13):** `torch==2.7.1`, `torchvision==0.22.1` (matching pair, both with cp313 manylinux wheels on PyPI; torch ≥ 2.6 has Dynamo on 3.13), `transformers==4.53.3`, `huggingface_hub==0.33.4`, `safetensors==0.5.3`, `accelerate==1.8.1`. numpy / Pillow / matplotlib are **not** installed or downgraded; CELL 2 only checks minimums (numpy 2.0, Pillow 10, matplotlib 3.8). CELL 2 compares the on-disk version of each pin with the version already imported in memory and stops with "重啟 runtime 後再 Run All" if they differ.
- **Resume (CELL 6):** after each (party, mode) group a checkpoint `OUTPUT_DIR/checkpoints/<party>__<mode>.json` is written atomically, with a fingerprint (git commit, scope, request count, smoke flag, CPU cap, pins). A rerun skips groups whose fingerprint matches and does not load a model whose modes are all done.
- **Packaging (CELL 9):** `OUTPUT_DIR/e7-run-<date>/` and `.zip` with `e7_analysis_*`, PNG, checkpoints, `RUN_NOTES.json` (versions, deviations from `RUN_DEVIATIONS`, pack zip SHA-256, per-party HF provenance) and its own `MANIFEST.sha256`.
- **Provenance (#768):** weights are hashed AFTER warmup (the first model of a repo has an empty cache before it loads) and keyed by path relative to the snapshot root; a model's `weight_files_sha256` lists every weight shard; if none can be hashed, `weights_sha256` is `"UNKNOWN"` with `weights_unknown_reason` (never `RECORD_AT_RUNTIME`). Qwen's `hf_revision` is the commit `66285546d2b821cf421d4f5eb2576359d3770cd3`.
- Not verified until the user runs the notebook on a fresh L4 runtime (`SMOKE_MODE=True` and `False`, one Run All).

## Per-tick requests-only pack and real-latency replay (#767)

- **Why:** E7 snapshots are every 10 ticks (2 s); E5 scores every tick. Qwen (~6 s/answer) is replayed on the Mac through the unchanged E5 AO-L machinery (`src/amidst/evaluation/e7_replay.py`, `scripts/evaluation/e7_replay_run.py`): the request starting at tick t uses the latest snapshot at or before t and its answer is delivered after that request's measured latency (`AOpenDecider` simlive `_poll`, `chain_box` IoU ≥ 0.3, `NeutralTracker`). Primary chain start = the snapshot tick (stricter); the ask-tick variant is a sensitivity column. Format fallbacks are "no answer" (they still occupy their latency). laya (~40 ms) is rerun on Colab GPU with one text_only request per tick, then replayed the same way (latency < 0.2 s: effective on the next tick).
- **Pack (fixed structure):** `python scripts/evaluation/build_e7_colab_pack.py --pertick --roots <E3 roots> --out <pack>` writes only `requests/e3_16_segments.jsonl` (one text_only request per tick, no `image_paths`), `PACK_INFO.json`, `MANIFEST.sha256`. It reads NO GT, has NO `scoring_only/`, NO frames, NO baselines; `verify_requests_only_pack` rejects any answer table or GT file/key, **rejects a pack with 0 requests, and requires exactly these three files** (`MANIFEST.sha256`, `PACK_INFO.json`, `requests/e3_16_segments.jsonl`): any extra or missing file is rejected (the gate scans only those files' keys, so the structure is fixed rather than inferred). Zip it with `python -m amidst.evaluation.e7_colab_runtime make-zip --requests-only ...`.
- **Notebook settings for that run (CELL 1):** `PACK_ZIP` = the per-tick zip, `RUN_PARTIES = ["laya_text", "laya_typed"]`, `RUN_UNACCELERATED = False` (skips the CPU pass), `SCORE_ON_COLAB = False` (CELL 7 skipped; CELL 8 writes `e7_raw_comparisons.json`). Scoring stays on the Mac.

## Limitations of E7 (D416 / #767 note; read before quoting any E7 number)

E7 is **not** a fair comparison between an Agent and the rule (B1). Its requests are stateless detection snapshots, and for the laya parties:

1. **No target conditions:** the request has no "target is red" colour condition, no reference crop and no previous position (B1 uses colour and a 4 m gate; the E5 API Agent gets `AO_STATE`, the reference crop and scene context).
2. **Option text carries no colour:** the candidate option text laya sees does not contain colours.
3. **Ranking fallback:** when the answer is not a SELECT, the next-camera ranking is filled with `camera_ids[:3]` (request camera order), not a model ranking (`e7_decider_eval.py`).

So E7 only shows what a model does with a flat list of detections and no target information; it cannot answer "is the Agent better than the rule". Fair comparison is E8 (#780). Replay-vs-AOL numbers (#767) share these confounds: E7 prompts have no reference crop, history or `AO_STATE`, and GPU/CPU agreement is 0.95 (answers are not bit-exact).

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
