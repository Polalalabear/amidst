# Persistent independent preview delivery (2026-11-07)

Refs #445, #417, #478. The user requested a persistent copy before Claude review and explicitly prohibited integration merges. #445 remains waiting.

The persistent root is `$AMIDST_ARTIFACTS/d131-previews/`. It contains four copied clean checkouts (pr452, pr442, pr473, pr477), 16 core screenshots, two D124 screenshots, two r005 screenshots, the six-camera review HTML/CSS/JS/data/server, original receipt manifests and a new launcher. The copy operation used an exact reviewed file plan: **8,325 entries / 213,458,583 source bytes**, including ten preserved relative documentation symlinks. No original Blender, RGB, model, calibration, dataset or GT assets were copied. The page's six original images remain served read-only from the pinned external artifact directory. The 33 displayed-box JSON is part of the authorized existing preview; raw_top300, #475 inference payloads, the QA-only return and the user's actual return were excluded from the copy list.

The new `manifest.json` records every new absolute locator, original source locator, original SHA-256 and current SHA-256. The original 26-file delivery manifest is retained byte-for-byte as `receipts/delivery_manifest.original.json`, SHA-256 `e2f89cb2f22a78e2a7dbd8ead9acf8b021635ef97ce91e9c5b3a8f2b1e5ccea2`. Working-tree payloads/screenshots/HTML retain their copy hashes. New location/health fields change three local adapters and the r005 locator manifest; the launcher uses the persistent paths and a safe log basename. Git may refresh copied `.git/index` stat caches when verifying cleanliness; both original and current cache hashes are retained separately. This is not a source-code change or a merge.

To reproduce those four adapter/locator edits on a fresh byte-verified copy, use `scripts/local_pr_previews/rebind_previews.py --root <copy-root>`. It preflights all four exact original pins before changing any file; do not apply it again to an already rebound copy. Copy `start_previews.py` from this PR to the root. That script's default root is `~/amidst-artifacts/d131-previews`; optional `--root` and `--python` are explicit. No dependency/browser install is needed to launch.

```sh
PYTHONDONTWRITEBYTECODE=1 "$EXISTING_PYTHON" "$AMIDST_ARTIFACTS/d131-previews/start_previews.py"
```

| View | URL | Persistent location below root |
| --- | --- | --- |
| Synthetic two core screens | http://127.0.0.1:8765/workbench-v2/ | `checkouts/pr452`, `tooling/preview-server.mjs`, `screenshots/core/` |
| Actual D124 A4-1 | http://127.0.0.1:8770/?run=A4-1 | `checkouts/pr442`, `tooling/d124_event_viewer.mjs`, `d124-viewer/screenshots/` |
| Actual D124 B4-1 | http://127.0.0.1:8770/?run=B4-1 | same |
| r005 static boxes and six-camera form | http://127.0.0.1:8769/ | `checkouts/pr473`, `r005-review/index.html`, `r005-review/screenshots/` |

Services now verify both head/report pin **and persistent source directory**. Only the three exact old task-owned processes were stopped/restarted; unrelated services and browser localStorage were untouched. Origins, page HTML and data bytes are unchanged, so existing form drafts remain attached to the same origin and source pins. The user's supplied six-camera DRAFT matched six frame pins and the report/graph pins; it is still DRAFT/NOT_EVALUATED and was not applied as formal coverage or copied into this preview package.

The new #478 cross-camera outputs are generated independently under `cross-camera/` with a metadata-only `cross-camera-job.json`. They are not copied #475 payloads. See #478's handoff for 46 Python tests, 462 real response comparisons, input/output pins and the future #445 adapter. The earlier seven-head merge-tree report remains a historical pairwise preview; it does not claim to cover #475/#478 or a completed integration. `q-core.track-response.v1` registry additions must be unioned with #443/#452 at future authorized integration.

The user's new LOST question is recorded in #478: current #410 trailing LOST is not timeout-based confirmed loss. Claude/user review of that distinction, formal parameters, identity validity and complete real-RGB core integration is still pending. This delivery adds no merge commit, source-asset write, external upload or coverage approval. Final absolute locators, byte totals and the final top-level manifest hash are posted in #445; the top-level manifest also lists newly generated cross-camera output pins.
