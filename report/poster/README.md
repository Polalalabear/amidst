# Amidst Q1–Q5 A0 Portrait Poster (`report/poster/`)

- **Source:** `poster_a0.html` (semantic HTML5 + CSS with `@page { size: 841mm 1189mm; margin: 0; }`).
- **Shared Figures:** References `../figures/fig1_e3_e5_summary.svg`, `../figures/fig2_five_way_comparison.svg`, and `../figures/fig3_latency_breakdown.svg` (identical figures used by `report/slides/` and #659 paper finalization).

## Export to A0 Portrait PDF

### Option 1: Headless Chromium via Playwright (recommended)

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

### Option 2: Browser Print-to-PDF

1. Open `report/poster/poster_a0.html` in Chromium / Chrome / Edge.
2. Press `Ctrl+P` (or `Cmd+P`) → **Save as PDF**.
3. Set **Paper size** = `A0` (`841 mm × 1189 mm`), **Margins** = `None`, **Background graphics** = `On`.
4. Save to `report/poster/poster_a0.pdf`.
