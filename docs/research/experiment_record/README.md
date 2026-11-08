# Amidst experiment record (LaTeX)

Paper-style record of the D134 integration stage: system design, RQ1–RQ5
(the user's Q1–Q5), functional acceptance, latency, screenshots, limits.
Chapter 4 of the project report cites this record.

v2 (2026-11-08) adds: reproducibility method (§4.4) and Appendix C table
(commit SHA, data SHA-256, model digest per result); RQ3 path (b) method
(§4.6, PR #490, D134); A1–A6 Agentic definition and status (§6.1, D137);
Appendix D workflow decisions D131–D137. Placeholders, not filled:
`TODO：待 #487 定版後換圖` (Fig. 5) and `NOT_RUN：量測 B` (§5.2).

- Source: `amidst_experiment_record.tex`
- Output: `amidst_experiment_record.pdf` (committed; LOCAL copy in
  `/Users/polalabear/amidst-artifacts/experiment-record-20261108/`)

## Build

Requires macOS TeX Live (`/Library/TeX/texbin/xelatex`, `latexmk`) and the
system fonts Songti TC, PingFang TC, Times New Roman, Helvetica Neue, Menlo.

```sh
docs/research/experiment_record/build.sh
```

The script runs `latexmk -xelatex`, fails on any undefined reference,
undefined citation or missing glyph, then removes auxiliary files.

## Rules used for numbers

Every number carries a source tag `[Sn]`; Appendix A of the PDF maps each tag
to a GitHub issue/PR/comment or a repo file at a named commit (`1fdc1a4`,
`a786bde`, `ebc6d3f`). Nothing is taken
from memory or estimated; missing items are written `NOT_RUN`, `UNKNOWN` or
待補. Extrapolations copied from #479 are labelled `EXTRAPOLATED`.

## Figure sources

| Figure | File | Source |
| --- | --- | --- |
| 圖 1 系統架構 | TikZ in `.tex` | `docs/contracts/Q_CORE_SEARCH_TRACK_V1.md`, `src/amidst/q1q5/q5_agent.py`, `configs/q1q5/r004_production_v1.json` @ `1fdc1a4` |
| 圖 2 功能架構 | TikZ in `.tex` | PR #487 description |
| 圖 3 使用流程 | TikZ in `.tex` | contract §3.5–3.6; PR #487 |
| 圖 4(a) A4-1 追蹤 | `figures/screen_a4_track_single.png` | LOCAL `/Users/polalabear/amidst-artifacts/d134-445-integration/screenshots/A4-1-track-single.png` (#445 comment 6717335520) |
| 圖 4(b) A4-1 盲區 | `figures/screen_a4_blind.png` | LOCAL `.../screenshots/A4-1-blind.png` |
| 圖 4(c) r005 查找結果牆 | `figures/screen_r005_search.png` | LOCAL `.../screenshots/r005-laptop.png` |
| 圖 5 新 UI | placeholder box (no image) | `TODO：待 #487 定版後換圖` |

Screenshots were opened and checked: no GT, renderer trajectory or script
information is visible. PNG ancillary chunks were stripped (keep only
IHDR/PLTE/tRNS/IDAT/IEND); the source files had none, so the copies are
byte-identical:

| File | SHA-256 |
| --- | --- |
| `screen_a4_track_single.png` | `a152c77f6aec7a93d1a53a9d71747f4023bd51fe4d12bf36bf75e2f400e6a98b` |
| `screen_a4_blind.png` | `4ac8ffd0b0c713495a2ac2e2f4b2c4b5a57a2df4c7be148df18193cccc8582a9` |
| `screen_r005_search.png` | `1e679662a538b86384895f3cd1d1b07fa6c8d142bf796cc2f0f58a40ec34dd36` |

All TikZ figures use black, white and gray only (line style carries meaning),
so they print in grayscale.
