# Browser automation defaults

All browser launchers use scripts/browser_options.mjs. It returns
headless=true unless the command line contains --headful or the caller
sets AMIDST_HEADFUL=1. Headful operation is reserved for explicit human
review. The historical HEADLESS=0 and --visible=true switches now keep
the browser headless.

The audit covered codex/feat-live-ab at 50164136, codex/feat-live-relock at
533b4e99 and the local historical codex/feat-live-detection at 11a3eace.
Their LIVE launchers already defaulted to headless. Two media benchmarks
had conditional headful paths through --visible=true. Main 7393bf62 also
introduced hardset_smoke.mjs with a HEADLESS=0 headful path and a CDP
newWindow target for B. The merged branch now uses two browser.newPage()
calls in that script and the shared launcher.

The audit found no open -a, open http or window.open launch in the scoped
runnable sources. The origin of the user's observed desktop windows is
UNKNOWN. The historical hardset document records HEADLESS=0 runs.

| Entry points changed | Default | Cleanup |
|---|---|---|
| frontend/live-mode/measure/lib.mjs | headless=true | callers own browser |
| frontend/live-mode/test/ab_menu.test.mjs | headless=true | try/finally |
| frontend/live-mode/measure/smoke.mjs | shared headless launcher | try/finally |
| frontend/live-mode/measure/hardset_smoke.mjs | shared headless launcher, A/B pages in one context | try/finally |
| frontend/live-mode/measure/t1_record.mjs, adj_record.mjs | shared headless launcher | try/finally |
| frontend/live-mode/measure/adj_build.mjs, detect_sweep.mjs | shared headless launcher | try/finally |
| frontend/live-mode/measure/latency.mjs, shots.mjs | shared headless launcher | try/finally |
| frontend/live-mode/measure/bscreen_shots.mjs, exterior_shots.mjs | shared headless launcher | try/finally |
| tests/browser/core-preview/core-e2e.mjs, core-legacy-e2e.mjs, real-e2e.mjs | headless=true | browser and preview cleanup |
| tests/browser/ui-redesign/dom-e2e.mjs, real-e2e.mjs | headless=true | try/finally |
| tests/perf/measurement-b/playwright-selfcheck.mjs | headless=true | try/finally |
| scripts/capture_n6_viewer.mjs | headless=true | browser and server cleanup |
| scripts/media_bench/measure_playback.mjs, measure_switch_latency.mjs, measure_legacy_playback.mjs | headless=true | try/finally |

Other LIVE consumers inherit the same launcher. These include
ab_flow.test.mjs, n6_ceiling_compare.mjs and the detection bench/route
recorders. Their existing browser.close calls remain in finally blocks.
The A/B simulations use pages in one browser and storage partition.
Evidence uses script assertions and screenshots under LOCAL evidence.

## Verification

The actual Puppeteer launch contained --headless=new and CDP reported
HeadlessChrome. The two pages had the same browser. An injected exception
still closed the browser, which reported connected=false afterwards.
The browser-options suite passed three tests with zero skips.

The focused A/B suite passed 16 tests including both browser fixtures.
After merging main and integrating scripted recording, the complete LIVE
Node suite passed 128 tests with zero skips. The Playwright synthetic
preview completed 130 assertions with no page errors and a PASS receipt.
All modified scripts passed node --check. Diff and architecture checks pass.

Run with OUT pointing at a LOCAL evidence directory and the existing N6
assets configured through AMIDST_LIVE_ASSETS.

```sh
env -u AMIDST_HEADFUL AMIDST_BROWSER_TEST=1 AMIDST_BROWSER_EVIDENCE="$OUT" node --test tests/browser/browser-options.test.mjs
env -u AMIDST_HEADFUL LIVE_AB_BROWSER=1 LIVE_AB_TEST_OUTPUT="$OUT/a" LIVE_AB_B_OUTPUT="$OUT/b" node --test frontend/live-mode/test/ab_menu.test.mjs frontend/live-mode/test/ab_flow.test.mjs
AMIDST_DEMO_HOME="$DEMO_HOME" CORE_SOURCE="$CHECKOUT" CORE_INTEGRATION_HEAD="$HEAD" SCREENSHOT_DIR="$OUT/synthetic" node tests/browser/core-preview/core-e2e.mjs
git diff --check
```

The synthetic source must be a clean checkout at the full SHA passed as
HEAD. Its required Playwright dependency must resolve inside the checkout.
This run used a copy of the existing dependency in scratch.

Production LIVE inference, the full media benchmarks, the legacy RGB gate
and the 8785 gate were not run in this checkpoint. Real headful behavior
was not exercised.

The first synthetic preview finished its assertions while cleanup took
longer. A scoped diagnostic found that Chrome had already exited. Automatic
approval rejected enabling the remaining Node inspector because it would
expose an additional local diagnostic interface. The Node later exited
normally with code zero. The corrected cleanup closes the browser before
the preview server, and its independent rerun completed normally.

LOCAL `local/evidence/codex-headless-20261118/MANIFEST.json` SHA-256 `bdd6bcd856cfb146045c6afcca649df6a6d215fa2f74fb1c1a24464f974a12d6`, 62 files / 3,738,380 bytes. The commands regenerate the screenshots and receipts, with variable wall-clock values.
