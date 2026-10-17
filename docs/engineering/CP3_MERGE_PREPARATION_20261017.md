# CP3 / K8 merge preparation — 2026-10-17

Read-only simulation. No integration/main/Claude branch, index or checkout was merged or rewritten. PR heads below were queried live. Premise: CP2's 13 merges have completed in the documented order, with the proposed CP2 conflict resolutions. CP2 receipt: [report](CP2_MERGE_PREPARATION_20261017.md). Detailed merge-tree output, stage blobs, virtual trees and proposed resolution patches: [machine receipt](CP3_MERGE_PREPARATION_20261017.json).

CP2 virtual base: `298ce4696db22f8cc3d91945a67ec754841893a8`, starting integration `dcb89f475f14897e1b272da61d44a25acf8f1fb8`. CP2 uses #44 `86b9b24`, #46 `f10ea53`, #48 `74c6ace`, #45 `28479b4`. These virtual commits are LOCAL simulation objects, not published branch history.

| Step | PR / exact head | merge-tree | Conflicting paths / suggested resolution |
| --- | --- | --- | --- |
| 1 | #47 `0228ce270af2f0c98a63d1b6e822118045a33e2d` | CLEAN | None. |
| 2 | #50 `a4d5dac93c42fee64c031c5eb2953f9960a9e5c3` | CLEAN | None. |
| 3 | #53 `4019a44f1dc22130e7b6013179ac86c899ca1200` | CONFLICT | `docs/history/WORK_LOG.md`: keep both dated C7 records and K1/K5 sync record. Remove only markers. |
| 4 | #35 `7a7f93e3deac963d7c81fcb17d6e9ac9cd9ec67f` | CONFLICT | Five files, detailed below. |
| 5 | #38 `e82f94bc46afeac8cef087080356dbe159964f33` | CONFLICT | `src/amidst/workbench/service.py`: union whitelist entries for ground-estimate, demo-mode, observation-selection and demo-steps.office.json; keep blind-hypothesis. |
| 6 | #58 `131869d127798d3deba595dd9b5c533279f8fbc8` | CLEAN | None. |
| 7 | #57 `d2ee13674e769ea892a2f7c229dcc1c4fa04b585` | CLEAN | None. |
| 8 | #60 `1f53f0d189485694d55c37228591200e3209c830` | CLEAN | None. |

Step 4 suggested resolution, preserving both owners' features:

- `frontend/workbench/cross-camera.mjs`: keep the existing combined presentationData/contactQualityStyle import and groundEstimateOverlaySVG; add HYPOTHESIS_COLOR. Do not import contactQualityStyle twice.
- `frontend/workbench/scene.mjs`: keep ground-estimate helpers and K3 groundObservations plumbing; add K4 blind-hypothesis helpers, layer, constructor/setData argument. Keep the existing combined graphCaptionPlan/contactQualityStyle/contactQualityReadout import; do not redeclare bindings. Both groundObservations and blindHypothesis must reach setData.
- `frontend/workbench/frame-query.test.mjs` and `frontend/workbench/workbench-layout.test.mjs`: combine K4 blind-hypothesis environment helpers with existing sceneUsable/sceneOptionLabel preset guards. Neither side's helper set replaces the other.
- `src/amidst/workbench/service.py`: whitelist both ground-estimate.mjs and blind-hypothesis.mjs.

Only the proposed resolutions are used to build the next **virtual** merge parent. All four changed JS modules/tests pass `node --check`; both Python whitelist resolutions pass `ast.parse`. This verifies syntax, not browser behavior or combined feature acceptance. Auto-merged app.mjs/style.css were not accepted through a browser or test suite.

## Stack and pin observations

#38's live head is `e82f94b`, replacing the earlier `a39d2c2`; this report uses the new head. Actual GitHub bases: #38 → claude/k4-hypothesis-bands; #58 and #57 → claude/k1-restricted; #60 → claude/k8a-synthetic-method. Thus #57 is not actually based on #58, but it still merges cleanly in the requested order.

After step 8, K1/K5 source bytes are K8a while C4b's dependency ledger still names the older 74c6ace pins: CLEAN does not imply pins are synchronized. Draft [#63](https://github.com/Polalalabear/amidst/pull/63) supplies the already-checked C4b sync. An additional read-only `git merge-tree --write-tree --messages <step-8-virtual-commit> 28f050a` returns **CLEAN**, tree `91fe2f2747fbc39e0c83dd8ad55b81ddc29af0f2`. This optional probe is separate from the requested eight steps and does not authorize merging #63. Its three real HTTP modes, index and 34-key D19 checks passed before publication; see #63.

Contract review is separately recorded on [#45](https://github.com/Polalalabear/amidst/pull/45#issuecomment-6235792437). If Claude changes any head, rerun affected steps; current simulation does not cover later contract edits.

## Reproduction and limits

For each exact head in the receipt, run `git merge-tree --write-tree --messages <current> <head>`. Exit 0 means CLEAN; exit 1 means conflicts. Materialize only the result into a temporary GIT_INDEX_FILE; apply the receipt's proposed_resolution_diffs to its conflicted files; write-tree; then `git commit-tree <resolved-tree> -p <current> -p <head>` supplies the next virtual parent. Use a temporary GIT_OBJECT_DIRECTORY and original objects as alternates, so no ref or real index is changed. Repeat the preceding CP2 steps first; the receipt includes their pinned heads. A published CP2 merge will have a different commit identity, so rerun against the actual integration history when available.

This run used LOCAL `/private/tmp/cp3_merge_audit.py` with `step`, `finish`, and `show` operations; every resolution patch is in the committed JSON receipt rather than relying on those temporary helper files. Final virtual tree: `15c1808abdbe56e1072e0e2afd9e101d5cc1e5cd`. Temporary object availability is not promised as a published artifact. No full tests, inference, RGB reads, assets, GT, rendering or live service changes occurred in this report task.

## 實際產出 / Actual output
- Model / effort: UNKNOWN
- PR / commits: docs-only #54; commit identity is the Git commit containing this report. All simulated source SHAs are in the table/JSON.
- Files changed: this Markdown report and `CP3_MERGE_PREPARATION_20261017.json` only.
- Commands run and results: live `gh pr list --state open --limit 80 --json number,headRefOid,headRefName,baseRefName`; eight `git merge-tree --write-tree --messages` calls, 5 CLEAN / 3 CONFLICT (7 total conflicting paths across steps); proposed resolution syntax checks 4 JS PASS / 2 Python PASS; optional #63 probe CLEAN; `git diff --check` PASS.
- Artifacts: committed JSON contains exact heads, merge-tree messages, stage blobs, result/resolved trees and proposed resolution patches. It is a simulation receipt, not application output or raw data.
- Verified: every requested step evaluated in order after all CP2 steps; all conflict hunks inspected; both K3/K4 import/plumbing paths retained in suggested resolution; #58/57/60 and optional C4b sync merge cleanly.
- Not verified: actual integration merges, checkpoint approval, combined frontend runtime/browser, scientific/physical/identity acceptance, future head changes.
- Deviations, UNKNOWN items and follow-ups: updated #38 head used; actual base of #57 differs from an assumed linear stack; apply #63 through its own review/gate to update pins; no Claude branch was modified.

Refresh 2026-10-18: live final-head audit found #57 changed from `6db6eab` to `d2ee13674e769ea892a2f7c229dcc1c4fa04b585`. Steps 7 and 8 plus the optional #63 probe were rerun against that head, all CLEAN. Earlier six steps and their proposed resolutions are unchanged. The table, receipt and final/optional trees above now reflect this refresh.
