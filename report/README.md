# Amidst Q1–Q5 Research Report Package (`report/`)

> **Status:** Report skeleton & shared figure pipeline (#734 / #730, linked to #659 paper finalization).
> **Data status:** E3 and E5 frozen verdicts/metrics are populated from committed records; **E6 and E7 numbers are `PLACEHOLDER` (awaiting #732 execution and PR #726 merge for E6)**. AO-L zero-latency approximate results (`0.5741` follow rate, `+0.3260` vs actual AO-L, Mac-reproduced in PR `#737`) can be wired directly from `#737` once `#737` merges, without waiting for `#732`.

## Important Provenance & Scope Notices

1. **Identity is always `UNCONFIRMED`:** The system matches visual appearance against user-selected conditions only; it does not confirm person identity. Physical navigation and collision clearance remain `UNKNOWN` unless authorized geometry evidence establishes otherwise.
2. **E3 & E5 verdicts are preserved unchanged:**
   - **E3** (attached integration): **不成立 (not supported)**.
   - **E5** (open agent `AO` offline K=3 & `AO-L` simlive K=1 vs `B1` rule on 16 E3 segments, 68 decision points; source `docs/operations/E5_REPORT_20261123.md`):
     - **H8a (primary, AO vs B1):** **不成立 (not supported)**
     - **H8b (AO blind-lock vs B1):** **不成立 (not supported)**
     - **H8c (AO reappearance top-1 vs B1):** **無法判斷 (inconclusive)**
     - **H8d (AO-L simlive, K=1, vs B1):** **不成立 (not supported)**
3. **E7 is exploratory; Colab Pro latency != local demo latency:** E7 local model runs (`laya`, `Qwen-VL`, diffusion VLM) are executed on Colab Pro cloud GPUs and are explicitly exploratory. Colab GPU latency does **not** represent local demo hardware latency. Windows RTX 3060 runs are smoke-test only.
4. **Shared figure source & number provenance (#659 / #719 linkage):** `report/figures/` is the single source of truth for figures shared across the slide deck (`report/slides/`), A0 poster (`report/poster/`), and final paper (#659). Figures (`report/figures/fig*.svg`, `fig*.png`) are generated strictly from Track A's `unified_analysis_v1` JSON with no hand-copied numbers, without recalculating raw experiment metrics or modifying `scripts/evaluation/`. Narrative E5 numbers in `report/poster/poster_a0.html` and `report/slides/slides/amidst-q1q5/index.tsx` are sourced from `docs/operations/E5_REPORT_20261123.md` §1 / §9 (SHA-256 `4833adb7...28eb`; full SHA recorded in `report/figures/FIGURES.md`) and `local/evidence/e5-aol-20261124/report.json`.
5. **Datapack provenance:** Frozen datapack MANIFEST SHA-256: `4eee05ba92ac954d4916f3000bd0d7c011297a75253ffe860605e74bca881b98`.

## Directory Layout

```text
report/
├── README.md                              # This guide (structure, build & export commands)
├── figures/
│   ├── FIGURES.md                         # Figure catalog: data sources, SHA-256, commands
│   ├── build_figures.py                   # Headless matplotlib generator (reads unified_analysis_v1 JSON)
│   ├── sample_placeholder_input.json      # CI-safe sample unified_analysis_v1 JSON (E5 frozen + E6/E7 PLACEHOLDER)
│   ├── manifest.json                      # Generated figure hashes & input provenance
│   ├── fig1_e3_e5_summary.{svg,png}       # E3/E5 frozen verdicts & core metrics
│   ├── fig2_five_way_comparison.{svg,png} # Five-way comparison (E7 slots PLACEHOLDER awaiting #732)
│   └── fig3_latency_breakdown.{svg,png}   # Per-model latency & AO-L zero-latency approximation diagnostic
├── poster/
│   ├── README.md                          # A0 poster preview & PDF export instructions
│   └── poster_a0.html                     # A0 portrait (841mm × 1189mm) HTML/CSS poster using ../figures/
└── slides/
    ├── README.md                          # Open-slide setup, dev server & PDF/PPTX export
    ├── package.json                       # Pinned @open-slide/cli (2.0.0) & export scripts
    └── slides/
        └── amidst-q1q5/
            └── index.tsx                  # 8-slide deck with transitions, <Steps> reveals & speaker notes
```

## Build & Export Instructions

### 1. Regenerate Figures (`report/figures/`)

Generate all SVG and PNG figures from a `unified_analysis_v1` JSON file (no weights, videos, or external downloads required):

```bash
# Using the committed CI-safe placeholder input (E5 frozen + E6/E7 PLACEHOLDER):
python report/figures/build_figures.py \
  --input report/figures/sample_placeholder_input.json \
  --out-dir report/figures

# Once #732 produces the official unified_analysis_v1 JSON:
python report/figures/build_figures.py \
  --input local/evidence/unified-analysis/unified_analysis_v1.json \
  --out-dir report/figures
```

### 2. Build & Export Slides (`report/slides/`)

The slide deck uses [open-slide](https://github.com/open-slide/open-slide) (MIT) with `@open-slide/cli` pinned to exact version `2.0.0`.

```bash
cd report/slides
npm install

# Interactive presenter preview (1920x1080 canvas, transitions, progressive reveal, speaker notes)
npm run dev

# Build static bundle
npm run build

# Export to PDF and PPTX (writes to report/slides/dist/)
npm run export:pdf
npm run export:pptx
```

### 3. Build & Export A0 Portrait Poster (`report/poster/`)

The poster (`report/poster/poster_a0.html`) targets A0 portrait (`841mm × 1189mm`, `@page { size: 841mm 1189mm; margin: 0; }`) and embeds the shared SVG figures from `../figures/`.

Export to PDF using headless Chromium (via Playwright Python):

```bash
python -c "
from pathlib import Path
from playwright.sync_api import sync_playwright
src = Path('report/poster/poster_a0.html').resolve().as_uri()
out = Path('report/poster/poster_a0.pdf').resolve()
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page()
    page.goto(src, wait_until='networkidle')
    page.pdf(path=str(out), width='841mm', height='1189mm', print_background=True, margin={'top':'0','right':'0','bottom':'0','left':'0'})
    b.close()
print('Exported:', out)
"
```

Alternatively, open `report/poster/poster_a0.html` in Chrome/Edge → Print → Save as PDF → Paper size `A0` (841 × 1189 mm), Margins `None`, Background graphics `On`.

## CI Verification

CI validates only the report skeleton, pinned CLI version, speaker notes/transitions, and headless figure generation on `sample_placeholder_input.json` (no model weights or media downloads):

```bash
pytest tests/report/test_report_skeleton.py -q
```
