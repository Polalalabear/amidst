# Measurement B — workbench-v2 latency (switch, first lock, search)

Read-only, in-page measurement of the new workbench (`/workbench-v2/`, D139+). No product code is changed.
Definitions below were **not** found in #479/#93 (only "P50/P90, target < 0.3 s, 30 each" in D130), so this README is the definition.

| metric | start (`t0`) | end | notes |
|---|---|---|---|
| `switch` — camera-switch latency | tracking playing at 1x; the camera timeline marks the next camera's ON_CAMERA segment `.current` | that camera's `.ui-stage-img` is visible, loaded **and `img.decode()` resolved** | setup (start tracking, park playhead 200 ms before the switch) is untimed |
| `lock` — first-lock time | click `#ui-track-submit` | stage image of the first ON_CAMERA segment decoded (playhead inside it, stamp = that camera) | `seeked:true` if the app did not park the playhead in the first sighting itself and the tool had to seek (includes that) |
| `search` — search time | click `#ui-search-submit` | every `#ui-case1 .ui-shot img` decoded | |

Scenarios: `B-05` (13:00:00–13:00:08), `A4-1` (14:00:00–14:00:50), `B4-1` (14:10:00–14:10:42), class `person`; same operations/windows as `tests/browser/ui-redesign/real-e2e.mjs`.
Columns per row: `ms` (the metric above, via `performance.now()` + `decode()`), `raf_ms` (same, plus two animation frames after decode ≈ presented, 16.7 ms granularity), `paint_ms` (native Element Timing `renderTime`; **null in the built-in browser/Chrome 152 inside iframes**, no entries are delivered — treat as UNKNOWN unless present).
Query answers come from stored data (no model inference); numbers are UI/decoding latency, not detector latency.

## Files
- `inject.js` — defines `window.__mb` (`run({metric,event,n})`, `results`, `export()`, `reset()`, `env()`).
- `stats.mjs` — P50/P90/min/max/mean per metric × event (+`ALL`); P90 = nearest rank, median of even n = mean of middle two. CLI prints a Markdown table.
- `stats.test.mjs` — `node --test tests/perf/measurement-b/stats.test.mjs`.
- `playwright-selfcheck.mjs` — headless quick check with the same `inject.js` (needs `npm ci` in `tests/browser/core-preview`). Not for official numbers.

**Reused from D133** (`scripts/media_bench/`): the `img.decode()` completion criterion, ElementTiming probe idea, `performance.now()` clock, nearest-rank P90 / even-median conventions. **New:** everything else — D133's `browser_probe.mjs` is bound to the old #408 viewer selectors (`#grid img`, `.q2-*`) and to headless Playwright; here selectors target `workbench-v2`'s `.ui-*`. **Why old numbers are not comparable:** old = #408 legacy viewer/PNG-proxy replay, headless, "decoded-visible" of the matching PNG for the *recorded* switch observation; new = workbench-v2 UI state change → decode, in the visible built-in browser, including the app's own frame loader.

## Official run (built-in browser, 30 samples each)
1. The Browser pane **must be visible** (hidden pane ⇒ rAF/paint unreliable; `paneVisible:false` is recorded per row and `stats.mjs` warns). Keep it visible and don't touch it during the run. Disk ≥ 8 GiB free.
2. Open `http://127.0.0.1:8785/workbench-v2/` (any page of that origin; samples load `/workbench-v2/?run=…` in a **fresh same-origin iframe each** — the reset point; iframe is 1440×900, scaled down if the pane is smaller).
3. Load the injector. `<script src>` from a local port works in the built-in browser (verified; `connect-src 'self'` stops fetch to other origins); either serve the file (`cd tests/perf/measurement-b && python3 -m http.server 8822`) and run in `javascript_tool`:
   ```js
   await new Promise((res,rej)=>{const s=document.createElement('script');s.src='http://127.0.0.1:8822/inject.js?'+Date.now();s.onload=res;s.onerror=rej;document.head.appendChild(s);}); __mb.reset(); 'ok'
   ```
   or paste the whole of `inject.js` into the tool.
4. Run (one call per scenario; ~10 s each for 30 samples; do a 3-sample warm-up first and `reset()` after it):
   ```js
   for (const ev of ['B-05','A4-1','B4-1']) for (const m of ['search','lock','switch']) await __mb.run({metric:m,event:ev,n:30});
   JSON.stringify(__mb.results.filter(r=>r.error).length)   // number of failed samples
   ```
5. Export: `__mb.export()` returns the JSON string (`{tool, env, rows}`); save it, e.g. `javascript_tool` return value → file, then
   `node tests/perf/measurement-b/stats.mjs export.json --out summary.json` (add `--field raf_ms` for the presented-time variant).
6. Report: n/attempts and error count (failed samples are never dropped silently), P50/P90, Chrome/Claude version (`env.ua`), pane size (`env.innerWidth×innerHeight`), 8785 head SHA. Target in D130: switch P50/P90 < 300 ms.

## Caveats
- Samples after the first hit the browser's HTTP cache for frames (all run in one browser profile) ⇒ "warm" numbers; the first sample of each scenario is the coldest. Report that; don't mix with D133's fresh-context numbers.
- Segment times for `switch`/`lock` come from the visible timeline (flex weights × `#ui-scrub` max), resolution 0.2 s; the tracking API response is not readable from outside the app.
- `switch`: if the camera changes before the 1x playback starts, the sample errors (`ALREADY_IN_NEXT_SEGMENT`) rather than returning a number.
- Timings use the iframe's own `performance.now()` clock; background tabs/windows, screen-sharing or heavy CPU load change results.
- Dry-run numbers (3 per cell, local 8821 server) are in `/Users/polalabear/amidst-artifacts/coordinator-20261109/measurement-b-dryrun/` and are **not** official.
