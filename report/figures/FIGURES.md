# Report Figures Catalog (`report/figures/FIGURES.md`)

> **Shared Asset Policy (#734 / #730 / #659):** Every figure in `report/figures/` is shared across the slide deck (`report/slides/`), the A0 portrait poster (`report/poster/poster_a0.html`), and paper finalization (#659 / #719).
> **No hand-copied numbers:** All figures are rendered exclusively by `report/figures/build_figures.py` from Track A's `unified_analysis_v1` JSON without recalculating raw experiment metrics or modifying `scripts/evaluation/`.

## Mandatory Caveats

- **Identity status:** `UNCONFIRMED` across all figures and evaluations (visual appearance matching only).
- **E3 & E5 verdicts (preserved unchanged):**
  - E3 (attached integration): **不成立 (not supported)**.
  - E5 (`AO` offline K=3 / `AO-L` simlive K=1 vs `B1` rule): **H8a 不成立 (not supported)**, **H8b 不成立 (not supported)**, **H8c 無法判斷 (inconclusive)**, **H8d (AO-L, K=1) 不成立 (not supported)**.
- **E6 & E7 status:** Currently **`PLACEHOLDER` (awaiting #732 execution and PR #726 merge for E6)**.
- **Hardware caveat:** E7 local models run on Colab Pro cloud GPUs as an exploratory benchmark; **Colab Pro GPU latency != local demo latency**. Windows RTX 3060 is smoke-test only.
- **Frozen datapack MANIFEST SHA-256:** `4eee05ba92ac954d4916f3000bd0d7c011297a75253ffe860605e74bca881b98`

## Data Sources

| Source ID | Path | SHA-256 | Status |
|---|---|---|---|
| `e5_report_md` | `docs/operations/E5_REPORT_20261123.md` (main `10a1384c`) | `4833adb7f608973194f24da9e54ea20742f3b6be31c208cf8bec024c638828eb` | `LOADED` (frozen) |
| `e5_aol_report_json` | `local/evidence/e5-aol-20261124/report.json` (LOCAL) | `edf988df08ac48c421086fa1c37394b285a4c34335e2aa23c0091a0e5439f3ad` | `LOADED` (frozen) |
| `sample_placeholder_input` | `report/figures/sample_placeholder_input.json` | Recorded in `report/figures/manifest.json` | `CI-SAFE SAMPLE` |
| `e7_analysis_pending` | `local/evidence/e7-pending/analysis.json` (LOCAL) | `UNKNOWN` | `PLACEHOLDER (awaiting #732)` |
| `e6_verdict_pending` | `local/evidence/e6-pending/verdict.json` (LOCAL) | `UNKNOWN` | `PLACEHOLDER (awaiting #726 + #732)` |
| `aol_zero_latency_pending` | `local/evidence/e5-aol-zero-latency-pending/diagnostic.json` (LOCAL) | `UNKNOWN` | `PLACEHOLDER (awaiting #732)` |

## Figure Inventory

| Figure ID | Files | Status | Data Source | Generation Command | Used In |
|---|---|---|---|---|---|
| **Fig 1** | `fig1_e3_e5_summary.svg`<br>`fig1_e3_e5_summary.png` | `AVAILABLE` (E5 frozen verdicts & core metrics) | `e5_report_md`, `e5_aol_report_json` via `unified_analysis_v1` JSON | `python report/figures/build_figures.py --input report/figures/sample_placeholder_input.json --out-dir report/figures` | Slide 3, Poster §3, Paper Ch. 4 |
| **Fig 2** | `fig2_five_way_comparison.svg`<br>`fig2_five_way_comparison.png` | `PARTIAL / PLACEHOLDER` (B1/AO/AO-L frozen; Script Answer, AO-L Zero-Latency, `laya`, `Qwen-VL`, Diffusion VLM are `PLACEHOLDER` awaiting #732) | `unified_analysis_v1` JSON (`five_way_comparison`) | `python report/figures/build_figures.py --input report/figures/sample_placeholder_input.json --out-dir report/figures` | Slide 5, Poster §4, Paper Ch. 4 |
| **Fig 3** | `fig3_latency_breakdown.svg`<br>`fig3_latency_breakdown.png` | `PARTIAL / PLACEHOLDER` (AO/AO-L p50/p95 & 52.7% EXPIRED frozen; E7 local latency & zero-latency approximation score are `PLACEHOLDER` awaiting #732) | `unified_analysis_v1` JSON (`latency_breakdown`) | `python report/figures/build_figures.py --input report/figures/sample_placeholder_input.json --out-dir report/figures` | Slide 4, Poster §3–§4, Paper Ch. 4 |

## Regenerating With Final #732 Analysis Output

Once Track A (#731) and #732 produce the official `unified_analysis_v1` JSON file, re-run:

```bash
python report/figures/build_figures.py \
  --input <path/to/unified_analysis_v1.json> \
  --out-dir report/figures
```

`report/figures/manifest.json` is automatically updated with the exact input SHA-256 and output figure SHA-256 hashes.
