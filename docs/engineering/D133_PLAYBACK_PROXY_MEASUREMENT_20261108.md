# D133: LOCAL playback proxies and Mac switch baselines

This supplements Draft #444 / #413 and provides a LOCAL measurement receipt to
#479. It does not complete Argon's historical research document or integrate
#445. The earlier D127 review decision remains scoped to its original increment;
the new tools and measurements require Claude review.

## Source and measurement boundaries

- Runtime: clean, unmerged #408 head
  `eb10d4c62ce09a765488cdd0548cfdd3abfd5109`, used read-only.
- B-05b: P1 **SYNTHETIC**, 2 cameras, 160 frames/camera, 20 source fps.
  P1 manifest: `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`.
- A4-1 / B4-1: D124 **ACTUAL_BLENDER** RGB, respectively 4×250 and 5×210
  frames, 5 source fps. Safe-bundle manifest:
  `ad3c66f21ef6713a76b0bb6505a7e5eb3514fa346f9279c42d7b486479281f01`.
- Only pinned RGB files and safe run/clock/recording descriptors are read.
  No model execution, inference input changes, rendering or source asset writes.
  Proxies are playback-only, never detector/index inputs.
- JPEG90 uses Pillow subsampling=0, optimize=True. WebP90 uses method=4.
  These quality settings are not a claim of equal perceptual quality.
- Original PNGs retain their exact byte hashes. Public PNG playback and codec
  decoding remove ancillary metadata in memory, preserving pixel chunks. The
  manifest distinguishes original and served hashes.
- Mac installed Chrome, headless by default, isolated 1440×1000 contexts, DPR=1.
  HTTP cache disabled for playback cases. Run browser jobs sequentially.
  `--visible=true` is an explicit opt-in for the two original measurement tools;
  it is not used for the final full matrices or headless latency baseline.
- FPS means native ElementTiming **image render events**, with independent
  decoded-visible frame promotions sampled at rAF. Physical screen refresh,
  screen-to-photon latency and live detector latency remain **NOT_MEASURED**.
  `decode()` promise wait includes pending loading, not just decoder CPU work.
- The original 27-case receipt's ResourceTiming buffer retained only first
  entries. Its `http_*` values are partial samples, not total network traffic.
  A later source change increases that buffer; old data is not rewritten.

## Reproduction

Use existing dependencies (Pillow with WebP, Matplotlib, Playwright Core and
installed Chrome). Paths below are operator-supplied LOCAL paths. Each output
directory and P1 state directory must be new; keep existing results intact.
Every producer/measurement stops below 8 GiB free.

```sh
export AMIDST_ARTIFACTS="$HOME/amidst-artifacts"
export P1_BUNDLE='/absolute/path/to/pinned/P1/bundle'
export D124_SAFE='/absolute/path/to/pinned/D124/safe_bundle'
export VIEWER_CHECKOUT='/absolute/path/to/existing/clean/408/checkout'
export BENCH_CHECKOUT='/absolute/path/to/this/PR/checkout'
export PYTHON_UV='/absolute/path/to/existing/uv/python'
export PLAYWRIGHT_CORE='/absolute/path/to/playwright-core/index.mjs'
export CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
export PROXY_MANIFEST_SHA='48668dcfc5ca8282c1eeb8f057fd8d464cbd56db9232c7780f2f2e69202a6fab'

uv run --no-project --offline --python "$PYTHON_UV" python -B \
  scripts/media_bench/build_proxies.py plan --p1 "$P1_BUNDLE" \
  --d124 "$D124_SAFE" --out /private/tmp/new-proxy-plan.json
# Use the plan SHA printed above; never replace the existing D133 proxy folder.
uv run --no-project --offline --python "$PYTHON_UV" python -B \
  scripts/media_bench/build_proxies.py build --plan /private/tmp/new-proxy-plan.json \
  --plan-sha256 '<new-plan-SHA>' --out "$AMIDST_ARTIFACTS/new-proxies"

# For the preserved D133 outputs, use the manifest SHA pinned above.
node scripts/media_bench/viewer_server.mjs --checkout="$VIEWER_CHECKOUT" \
  --proxies="$AMIDST_ARTIFACTS/d133-playback-proxies-v2" \
  --manifest-sha256="$PROXY_MANIFEST_SHA" --port=8780
# In another terminal; this opens no visible Chrome window:
node scripts/media_bench/measure_playback.mjs --playwright="$PLAYWRIGHT_CORE" \
  --chrome="$CHROME" --manifest="$AMIDST_ARTIFACTS/d133-playback-proxies-v2/manifest.json" \
  --output="$AMIDST_ARTIFACTS/new-viewer-measurements"
```

The 8780 adapter serves the original event-viewer JS with a LOCAL format banner
and manifest-backed run/media routes. No tracking inference is supplied. B-05b
shows both cameras; A4-1/B4-1 show all 4/5 cameras. The viewer's 40 ms timer advances
at most one frame per tick, so B-05b high-speed results are capped near 25 fps per
camera. This is separate from the workbench's playback pipeline.

For the B-05b single-view workbench comparison:

```sh
uv run --no-project --offline --python "$PYTHON_UV" python -B \
  scripts/media_bench/legacy_proxy_server.py --checkout="$VIEWER_CHECKOUT" \
  --proxies="$AMIDST_ARTIFACTS/d133-playback-proxies-v2" \
  --manifest-sha256="$PROXY_MANIFEST_SHA" --bundle="$P1_BUNDLE" \
  --state=/private/tmp/new-proxy-workbench-state --port=8782
node scripts/media_bench/measure_legacy_playback.mjs --playwright="$PLAYWRIGHT_CORE" \
  --chrome="$CHROME" --output="$AMIDST_ARTIFACTS/new-workbench-measurements"
```

This LOCAL adapter delegates original session/media authorization and original
source-byte checks before returning mapped proxy bytes and served hashes. The
served JS response changes only Blob MIME from fixed PNG to the response content
type; original checkout JS remains unchanged. Startup prints both JS hashes.
It is a benchmark adapter, not a shipped proxy feature in #408.

## Switch baseline definition

The legacy profile uses the unmodified P1 launcher on port 8781:

```sh
cd "$VIEWER_CHECKOUT"
uv run --no-project --offline --python "$PYTHON_UV" python -B \
  scripts/start_q1q5_p1.py --bundle "$P1_BUNDLE" \
  --manifest-sha256 6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7 \
  --state-root /private/tmp/new-switch-state --current-ui --no-open --port 8781
# Run the measurement from this PR's checkout, not VIEWER_CHECKOUT:
cd "$BENCH_CHECKOUT"
node scripts/media_bench/measure_switch_latency.mjs --playwright="$PLAYWRIGHT_CORE" \
  --chrome="$CHROME" --recording="$P1_BUNDLE/data/recordings/2777741d96ac9aff5bffb2f61a4d2938.json" \
  --profiles=legacy --repeats=30 --output="$AMIDST_ARTIFACTS/new-switch-baseline"
```

Start = replay clock reaches **5.15 s**, the first matching observation referenced
by the recorded A→B switch (B frame 103). End = the matching new-camera image is
decoded/visible, and separately its native ElementTiming render timestamp. This
does not establish the first physical pixel appearance of the target; that is
**UNKNOWN** without independent human annotation. No detector is executed.
At the declared replay instant, clock/DOM sampling has rAF granularity.

The optional `core` profile uses the existing unmerged #452 synthetic preview on
port 8765. It measures fixture state→schematic readiness only. It has no actual
camera PNG/native image-paint sample and must not be pooled with the legacy data.
Foreground results (30 legacy + 11 core saved before user-requested popup stop)
and the complete headless results stay separate. The missing foreground trials
are not imputed. Median uses the average middle pair for even n; P90 is nearest rank.

## Result receipts

The accompanying curated JSON and table contain the actual measured numbers,
tool/source pins and focused validation. Raw samples, screenshots and all RGB /
proxies remain LOCAL under `amidst-artifacts/d133-*`. No integration merge exists;
#478 remains the separate cross-camera delivery and #445 still awaits review and
explicit merge authorization.

- [Measured tables and recommendation](D133_PLAYBACK_MEASURED_RESULTS_20261108.md)
- [Curated source-pinned receipt](d133_playback_latency_20261108.json)
- [Latency ECDF](d133_latency_ecdf_20261108.svg)

Recompute the chart using only the published curated receipt (no RGB required):

```sh
MPLCONFIGDIR=/private/tmp/amidst-d133-mpl uv run --no-project --offline \
  --python "$PYTHON_UV" python -B scripts/media_bench/report_results.py \
  --curated docs/engineering/d133_playback_latency_20261108.json \
  --out /private/tmp/new-d133-chart
```

The recomputed PNG matched the original LOCAL byte hash:
`c7409c7f7b4aefd9eef94aa8deef7fae952f52301097f64483954b9d6699a798`.
The published SVG removes only generated trailing whitespace to satisfy the diff
gate: `83cb618f1897d635e8369298fbcc446680182e50bedb08ccb88c27b28d90ddcb`.
The original LOCAL SVG is retained unchanged at
`7c5cec70fd4716c4ac659eaec47a168a5c96ae50725ec6464657dec52f2e6ab2`;
its whitespace-normalized bytes equal the published SVG. The plotting script now
applies that normalization to future SVG output.
Focused proxy tests: **8 passed in 0.11 s** using the existing offline uv Python.
Initial sandbox cache access / macOS system-configuration failures were environment
errors; the same focused command passed in normal local execution without code or
dependency changes. Five JS syntax checks and `git diff --check` passed. The
27 event-viewer and 9 workbench cases all reached the final native painted frame
with **0 page errors**; all 9 workbench buffer error counts were 0. Both latency
sessions' saved samples had **0 timeouts / 0 page errors** (101 samples total,
kept in four separate mode/profile groups). After measurement, all **2,370 original
PNG / 4,740 proxy** hashes matched and the #408 runtime checkout remained clean.

One full-duration playback trial per combination does not establish long-run or
cross-machine performance. The recorded switch baseline does not include model
execution or independently annotated physical first appearance. Complete research
acceptance, real A4/B4 integrated workbench switching, Windows and full suites are
not verified. The previous D127 410-test result is historical and was not rerun here.
