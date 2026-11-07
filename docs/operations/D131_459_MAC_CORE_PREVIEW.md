# Mac synthetic core preview and browser E2E

This is an independent preview of PR #452, not #445 integration. It uses the exact clean source head `088252833665a4bca9fcfbf31597b4bb296fb549`. The HTTP adapter provides explicit SYNTHETIC responses and SVG cards; no actual RGB, model, key, renderer, original dataset or GT is used. Unavailable routes remain errors. The source checkout is read-only and no merge commit is created.

## Reproduction

Reuse a clean checkout at the specified PR #452 head and set `CORE_SOURCE` to its absolute directory. Keep this PR's tools separately; do not add their files to the preview checkout. Node 20+ and an existing Google Chrome installation are required. Install only the locked Playwright Core package (`npm ci --prefix tests/browser/core-preview`); this does not download a browser.

```sh
CORE_SOURCE=<clean-452-checkout> CHROME_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' SCREENSHOT_DIR=<new-local-screenshot-directory> node tests/browser/core-preview/core-e2e.mjs
node tests/browser/core-preview/preview-server.mjs --source=<clean-452-checkout> --port=8765
```

Open `http://127.0.0.1:8765/workbench-v2/`. In the left core controls, search with class `person`, blank location and time `13:00:00` to `13:00:02`. Location-only uses the explicit synthetic region menu and blank class. For tracking, either use that time range or clear both times to use the displayed source clock. Single/multi controls and the shared play/scrub controls are visible. Source camera sequence A → GAP → B → LOST is synthetic. The measured multiplier is the synthetic source clock; it is not physical display fps or actual RGB playback throughput.

## Actual output

- Sol prepared the original fixture/Playwright scaffolding; root finished browser failures and source-bound publication. Exact root model/effort UNKNOWN.
- Mac Google Chrome E2E: 49 checks PASS on the above #452 head, 16 PNG screenshots. Explicit visible-state assertions supplement DOM counts. The older DOM-only gate missed monitor-wall occlusion and unsupported 1.5x timing; those bugs were repaired on original PR #452 and the browser test rerun.
- Coverage: real source-menu selection for three independent SYNTHETIC_B05 / SYNTHETIC_A4_1 / SYNTHETIC_B4_1 scopes (two/three/two cameras), cleared old results and request/run/clock binding for each; normal control validation, location/feature/both requests, visible results, unavailable route, different overlapping requests/stale response, source-clock now, A/GAP/B/LOST, real automatic synthetic timeline advancement, single/multi, 1.5x configuration, shared speed agreement, simple/system view and no page errors.
- Screenshot hashes: `docs/engineering/D131_459_MAC_E2E_RECEIPT.json`. Full PNGs are LOCAL; the small JPEG contact sheet is a curated synthetic review receipt, not original media. No large PNG set is committed.
- Windows, Linux, CI artifact upload, actual RGB, actual backend runtime and physical screen fps: NOT_RUN/NOT_VERIFIED. This delivery follows the user's narrowed Mac-only instruction; it does not claim the original cross-platform gate complete.
- The fake source can demonstrate a missing media card. This is labelled MISSING; no synthetic fallback is used by the real API client outside the explicit fixture server.
