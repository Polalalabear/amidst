# #445 / #487 Mac real-data UI acceptance (2026-11-08)

D131/D132: fix acceptance failures in `claude/ui-redesign-v1`, report on #445.
The initial `53953a81` diagnosis is superseded by the fixed-run evidence below.
No PR is merged. No source RGB, GT, render, model inference or identity acceptance is produced.

## Changed behavior

- ACTUAL_BLENDER uses the shared playback eligibility rule. The player waits for the **visible new UI** RGB instead of a legacy slot that the new UI does not mount.
- Scrub reads its value before PAUSE causes synchronous rendering. Source timestamps survive dragging.
- Multi-view requests source-bound candidate RGB; old frames are cleared before a new timestamp is requested. Candidate pixels do not become identity evidence.
- Integrated bootstrap runs can be selected in the header and case3 event buttons. They use the same backend, without requiring retired sibling ports or missing recording IDs.
- The visible “追蹤新目標” entry reopens its query window.

## Reproduce

From the demo checkout (existing service uses port 8785):

```sh
AMIDST_DEMO_PYTHON="$PWD/.venv/bin/python" ./start_445_demo.command --port 8785
AMIDST_REQUIRE_IMPL=1 node --test frontend/workbench-v2/*.test.mjs frontend/event-viewer/*.test.mjs
PLAYWRIGHT_CORE_MODULE="$AMIDST_ARTIFACTS/demo-owned-v1/tooling/playwright-core/index.mjs" \
UI_QA_OUTPUT="$AMIDST_ARTIFACTS/d135-487-mac-ui/accepted" \
node tests/browser/ui-redesign/real-e2e.mjs
```

The real E2E requires the selected source packages served by the integration backend. It drives visible UI only, without injected API fixtures, direct store changes or deep-link workarounds for tracking/blind results. Initial `?run=` selects the source, as the visible source selector does. A saved-run input package is not live inference.

## Actual output

- Model / effort: GPT-6 family / UNKNOWN.
- PR / commits: existing Draft #487; exact tested source head is in the LOCAL result ledger and #445 comment.
- Files changed: `frontend/workbench-v2/ui-shell.mjs`, `frontend/workbench-v2/q-playback.mjs`, `tests/browser/ui-redesign/real-e2e.mjs`, this document. Claude's parallel P2/P3 changes are preserved by merge, with final results recorded on #445.
- Commands/results: Node focused command above: 493 PASS. New UI synthetic gate: 49 PASS / 16 PNGs. Real UI command: 86 checks PASS; 24 PNGs; no page errors or failed API responses. Final head, receipts and manifest hash are recorded on #445.
- Artifacts (LOCAL, relative to `$AMIDST_ARTIFACTS`): `d135-487-mac-ui/accepted/browser-results.json` records per-PNG bytes/SHA-256, source head, checks and API/browser errors; `screenshots/` contains three events × cover/search/single/multi/view/admin-overview/admin-settings plus three blind-state screenshots. `MANIFEST.json` binds retained receipts/logs; manifest SHA and total sizes are on #445. Raw screenshots are not committed.
- Verified: real package RGB decoded for B-05 (P1 SYNTHETIC source), A4-1/B4-1 (D124 ACTUAL_BLENDER); wall counts 2/4/5; three speeds; automatic source camera switching; all multi tiles decoded; source event switching; A4 LOW and B4 UNKNOWN confidence dashed blind sketches. B-05 has no calibrated display positions and correctly remains UNKNOWN without a drawn physical curve.
- Not verified: physical display timing and research/identity/physical-navigation acceptance have no authorized measurement or annotation; they remain UNKNOWN and are outside engineering UI acceptance. Mac does not execute PowerShell.
- Deviations: none of the four diagnosed UI failures is deferred. Source uncertainties (DRAFT graph, DEMO_DEFAULT parameters, identity UNCONFIRMED, physical navigation UNKNOWN) remain visible and are not upgraded by this UI test.

## Review corrections included

The bottom bar fills short viewports while retaining flow space for long content. Result selection preserves decoded image nodes. UI variables/links are scoped so legacy colors remain unchanged. Admin tabs expose cleanup. Existing stop/manual controls keep their original listeners, availability checks and backend semantics through the single legacy bridge. The spec now matches the requested 300 px result image height. `core-e2e.mjs` drives the new visible UI (49 checks / 16 synthetic PNGs); the former driver is retained as `core-legacy-e2e.mjs`. Synthetic preview warnings remain visible above the new front desk. No P2/P3 is deferred as an untested note.

The real-data gate verifies the transport bottom equals viewport bottom (within 2 px) in single and multi layouts for all three events. Long query panels scroll within their own height limit; the fixed UI root uses `overflow:clip` so focus cannot scroll the header and transport away. The concurrency test holds the first response until the newer response finishes, instead of depending on an arbitrary delay.

Synthetic gate command (clean source/head guard stays enabled):

```sh
CORE_SOURCE="$PWD" CORE_INTEGRATION_HEAD="$(git rev-parse HEAD)" \
PLAYWRIGHT_CORE_MODULE="$AMIDST_ARTIFACTS/demo-owned-v1/tooling/playwright-core/index.mjs" \
CHROME_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
SCREENSHOT_DIR="$AMIDST_ARTIFACTS/d135-487-mac-ui/accepted-synthetic" \
node tests/browser/core-preview/core-e2e.mjs
```
