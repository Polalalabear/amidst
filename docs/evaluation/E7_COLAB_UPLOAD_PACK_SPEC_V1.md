# E7 Colab Upload Pack Specification v1 (`#727` / `#731`, D380 / D382 / D384 / D385)

## Purpose

Defines the exact directory layout, `MANIFEST.sha256` format, and GT-isolation rules for the private Google Drive upload pack consumed by [`notebooks/e7_colab_decider_eval.ipynb`](../../notebooks/e7_colab_decider_eval.ipynb).

- **Prepared by:** Codex on Mac (from `local/evidence/`).
- **Consumed by:** User running `notebooks/e7_colab_decider_eval.ipynb` on Colab Pro (Run All).
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
    └── answer_table.json            # Derived answer table (#717, D385 approved for Colab scoring cell only)
```

## Allowed vs Forbidden Files

- **Allowed:**
  - Frozen synthetic 320x180 frames (`frames/`)
  - Frozen detection indices and AO decision requests (`requests/*.jsonl`)
  - Frozen B1 / AO / AO-L report JSON (`baselines/e5_report_frozen.json`)
  - Derived answer table under `scoring_only/answer_table.json` (D385: allowed for Colab scoring cell ONLY; decider code is tested to never read it)
- **Strictly Forbidden (NEVER upload to Colab or Drive):**
  - Raw Ground Truth JSON/CSV (`gt/`, `a-log.json`)
  - Renderer actor trajectories, world coordinates, visibility tables, depth maps, `.blend` files
  - API keys or credentials

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
