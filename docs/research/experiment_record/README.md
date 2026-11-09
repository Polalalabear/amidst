# Amidst experiment record (LaTeX)

Paper-style record of the D134 integration stage: system design, RQ1–RQ5
(the user's Q1–Q5), functional acceptance, latency, screenshots, limits.
Chapter 4 of the project report cites this record.

v2 (2026-11-08) adds: reproducibility method (§4.4) and Appendix C table
(commit SHA, data SHA-256, model digest per result); RQ3 path (b) method
(§4.6, PR #490, D134); A1–A6 Agentic definition and status (§6.1, D137);
Appendix D workflow decisions D131–D137. Placeholders, not filled:
`TODO：待 #487 定版後換圖` (Fig. 5) and `NOT_RUN：量測 B` (§5.2).

v2.1 (2026-11-09) adds §6.2 major issues I1–I7 (person detected as other
classes, no car detections, tracking rules too conservative, flicker,
scrub snap-back, test environment) and Table 10, recall against the user's
human reference (evaluation only; `data/d147_recall_eval.json`, produced by
`scripts/eval_d147_recall.py` at `dceeb7c` on `claude/ui-d139`).

v2.2 (2026-11-09) adds §6.3 切鏡規則與俯視圖現況（sticky-camera handoff
rule from `associate()` @ `9fade4a` / PR #498, overhead-map layouts, Agent and
OpenAI status; sources S20–S28) and updates the §6.2 status column (I1–I7
against D147–D150 and #498: per-camera recall min 77.78%, single-view
switching A4 96.47% / B4 91.58%, vehicles via scene annotation). PR #498 is
Draft and **not merged**; these results are "verified on that branch" only.
v3 (e2e screenshots, measurement B) is separate.

v3 (2026-11-09) adds: measurement B formal results (§5.2, Table 8; 8785 @
`89a73e6`, 3 metrics × 3 events × 30 samples, 270 samples, 0 errors; source
LOCAL `coordinator-20261109/measurement-b-formal-89a73e6/summary.md` and
#479 comment 6737298718), environment, limits (`paint_ms` null, warm cache,
B-05 lock ≈83 ms cause UNKNOWN, UI/decode not detection latency) and why it
is not comparable with the 8821 trial or D133; new UI screenshots (Fig. 5–6,
replacing the placeholder); §6.2 status: #498 merged (`42fc0a8`), I1/I4/I5
now "merged and verified", new I8 (Table 11, `Q_RESPONSE_LIMIT`, D153, fixed
by #500); §7.1 order of work after acceptance A (D151, D152); sources S29–S36.

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
| 圖 5(a) B4-1 查找結果牆 | `figures/v3_b4_search.jpg` | headless Chrome capture of 8785 @ `89a73e6`, LOCAL `/Users/polalabear/amidst-artifacts/experiment-record-20261108/v3-sources/b4_search.png` |
| 圖 5(b) A4-1 車輛場景標註 | `figures/v3_a4_car.jpg` (cropped) | same, `v3-sources/a4_car.png` |
| 圖 5(c) B4-1 追蹤切鏡 | `figures/v3_b4_track.jpg` | LOCAL `/Users/polalabear/amidst-artifacts/demo-owned-v1/evidence/8785-eceed45-20261109/height-1300/screenshots/B4-1-case2-single.png` (#93 comment 6732444642) |
| 圖 6(a) A4-1 追蹤 | `figures/v3_a4_track.jpg` | same folder, `A4-1-case2-single.png` |
| 圖 6(b) B-05 追蹤 | `figures/v3_b05_track.jpg` | same folder, `B-05-case2-single.png` |
| 圖 6(c) 後台概況 | `figures/v3_admin.jpg` | same folder, `B4-1-admin-overview.png` |

Screenshots were opened and checked: no GT, renderer trajectory or script
information is visible. PNG ancillary chunks were stripped (keep only
IHDR/PLTE/tRNS/IDAT/IEND); the source files had none, so the copies are
byte-identical:

| File | SHA-256 |
| --- | --- |
| `screen_a4_track_single.png` | `a152c77f6aec7a93d1a53a9d71747f4023bd51fe4d12bf36bf75e2f400e6a98b` |
| `screen_a4_blind.png` | `4ac8ffd0b0c713495a2ac2e2f4b2c4b5a57a2df4c7be148df18193cccc8582a9` |
| `screen_r005_search.png` | `1e679662a538b86384895f3cd1d1b07fa6c8d142bf796cc2f0f58a40ec34dd36` |

v3 figures are JPEG (quality 80–85, width ≤ 1200 px) re-encoded with `sips`
from the PNGs above, so they are not byte-identical; source SHA-256 are in
Appendix A (S33, S34) and the e2e `MANIFEST.json`. All were opened and checked:
no GT, renderer trajectory or script information is visible.

All TikZ figures use black, white and gray only (line style carries meaning),
so they print in grayscale.
