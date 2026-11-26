# Amidst Q1–Q5 Presentation Slides (`report/slides/`)

Built with [open-slide](https://github.com/open-slide/open-slide) (MIT) on a 1920×1080 canvas.
`@open-slide/cli` is pinned to exact version `2.0.0` (no `^` or `~`).

## Deck Outline (`slides/amidst-q1q5/index.tsx`)

1. **Problem & Motivation** — Multi-camera tracking & decision switching
2. **Q1–Q5 System Architecture & Provenance / GT Isolation**
3. **E3 & E5 Results** — Exact preserved verdicts (E3 not supported; E5 H8a/H8b/H8d not supported, H8c inconclusive)
4. **Latency Bottleneck & AO-L Zero-Latency Diagnostic** — 52.7% EXPIRED calls & approximation clearly labeled
5. **E7 Local Models & Hardware Constraints** — Colab Pro exploratory benchmark != local demo latency (`PLACEHOLDER` awaiting #732)
6. **E6 Pre-registered Follow-up** — De-anchoring, history, summary (`PLACEHOLDER` awaiting #726 + #732)
7. **Live Demo Showcase** — Ports `8785` / `8791` workbench, identity `UNCONFIRMED`
8. **Limitations, Reproducibility & Future Work**

All slides use open-slide page transitions, `<Steps>` / `<Step>` progressive reveals, and per-slide speaker notes. Figures are imported from the shared `../figures/` directory.

## Install, Preview & Export

```bash
cd report/slides
npm install

# Live presenter view (includes speaker notes & timer)
npm run dev

# Build static HTML deck
npm run build

# Export PDF & PPTX
npm run export:pdf
npm run export:pptx
```
