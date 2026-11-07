# #445 independent previews before Claude review

This is a partial engineering delivery, not an integrated workbench. The user explicitly requested no integration merge before Sunday. Issue #445 remains waiting. All three loopback services run from separate, pinned sources; no merge commit, worktree, original-media copy or render was made.

| Preview | URL | Source | Screenshot directory (LOCAL) |
| --- | --- | --- | --- |
| Two core screens, synthetic HTTP API fixture | http://127.0.0.1:8765/workbench-v2/ | #452 `088252833665a4bca9fcfbf31597b4bb296fb549` | `/private/tmp/d131-459-three-events-screenshots/` |
| Actual D124 new A4-1 RGB | http://127.0.0.1:8770/?run=A4-1 | #442 `62a8979632d800e9ac6d23fc29789e56a11550bc` | `/private/tmp/amidst-d131-442-viewer/screenshots/` |
| Actual D124 new B4-1 RGB | http://127.0.0.1:8770/?run=B4-1 | Same #442 source and pinned safe bundle | Same directory |
| r005 static RGB, model boxes and human review form | http://127.0.0.1:8769/ | #447 `39b9c4323288cae8c52532277cdd6dc75b63a965`; #473 helper `df493522fa10308a8712316a8881879cddd981ac` | `/private/tmp/amidst-d131-464-review/screenshots/` |

## Starting the delivered LOCAL previews

The machine-specific launcher is `/private/tmp/amidst-d131-control/start_previews.py`. Run it using the existing project Python (absolute path posted in #445). It probes the expected source pins, reuses only matching services and starts a missing service without stopping any process. It refuses startup below 8 GiB or if a port belongs to a different source. These `/private/tmp` locators are current local delivery locations, not permanent archives.

The source-controlled version takes an explicit Python executable:

```sh
"$EXISTING_PYTHON" scripts/local_pr_previews/start_previews.py --python "$EXISTING_PYTHON"
```

Separate commands for the delivered services:

```sh
node /private/tmp/amidst-d131-tooling/preview-server.mjs --source=/private/tmp/amidst-d128-419 --port=8765
node /private/tmp/amidst-d131-442-viewer/server.mjs
"$EXISTING_PYTHON" /private/tmp/amidst-d131-464-review/server.py --port 8769
```

The core preview is explicitly SYNTHETIC. Its normal controls call the actual #452 client/store/views against a synthetic HTTP adapter. To see search results, use class `person`, blank region, and time `13:00:00` to `13:00:02`, then click 查找結果牆. The same times work for 追蹤目前時間; single/multiple view and 1.5x synthetic-source-clock playback are available. This does not connect the core screens to actual RGB or the #471 Chinese alias branch.

The #442 adapter reads only the safe manifest-pinned D124 metadata and RGB. Startup verified all 2,050 frames, including byte hashes and PNG structure/CRC/pixels. Each RGB request rechecks its pin. The served UI is the clean #442 event-viewer; its LOCAL metadata adapter supplies the new run IDs instead of the historical hardcoded IDs. This is read-only viewing, not search/tracking integration. The portable adapter source requires explicit paths:

```sh
node scripts/local_pr_previews/d124_event_viewer.mjs --checkout="$EXACT_CLEAN_442_CHECKOUT" --bundle="$D124_SAFE_BUNDLE"
```

The r005 page reads the six original static RGB files in place, without copying them. The form places each original image beside region checkboxes, including UNKNOWN. It has no prefilled answer, keeps drafts in this browser, and exports DRAFT JSON only. Human coverage remains NOT_EVALUATED until the user returns and approves their answers. The 33 optional model boxes are unverified detections, including the original corridor false-positive labels. No human-return JSON or actual RGB screenshot is committed.

## Verification and remaining gates

- #452: 415 Node tests passed; final no-allow architecture guard and diff check passed.
- #459: real Mac Chrome/Playwright E2E passed 49 checks with zero page errors against exact #452 head. This includes source-menu selection and separate run/clock binding for SYNTHETIC_B05, SYNTHETIC_A4_1 and SYNTHETIC_B4_1 (two/three/two cameras). Sixteen synthetic screenshots remain LOCAL; a small synthetic-only contact sheet is attached to Draft #476. Windows/Linux/CI artifact upload and real-backend E2E remain NOT_RUN.
- #442 viewing: both runs passed browser playback/screenshot checks. No model or renderer was run by this viewer.
- r005 form: ten browser checks passed, including six images, no prefills, model-box toggle, UNKNOWN exclusion, draft persistence and DRAFT/NOT_EVALUATED export. QA-only answers are not a user approval.
- #417: Draft #475 contains DEMO_DEFAULT actual-RGB index and camera-local RULE_ONLY results. Cross-camera association, formal parameters and full tracking-source integration remain pending.

The [pairwise merge-tree report](../engineering/D131_445_MERGE_TREE.md) records all seven exact heads: **21 pairs, 17 clean, four conflicts, zero command errors**. Proposed future order after Claude review and explicit merge authorization is #442 → #447 → #470 (issue #457) → #473 → #443 → #408 → #452. Pairwise clean trees do not prove the seven-way integrated runtime. Recompute against the real integration head before any future authorized merge.

## Persistent LOCAL relocation (2026-11-07 follow-up)

The user authorized copying these preview checkouts, screenshots, manifests and review page to `~/amidst-artifacts/d131-previews/`. The current launcher is `~/amidst-artifacts/d131-previews/start_previews.py`; use the existing Python executable. The code version above now accepts `--root` and defaults to that persistent directory. It verifies both source head and source directory so an older `/private/tmp` service is not silently accepted. Only this task's exact old processes may be restarted during relocation.

The new `manifest.json` keeps original copy hashes and source paths alongside current paths/hashes; changed launcher/adapter/manifest bytes have separate new pins. Screenshot, HTML, model-result and checkout payload copies are byte checked. The original manifest is retained byte-for-byte under `receipts/`. No original RGB/model/Blender/dataset is copied or modified: services keep reading the previously pinned external originals. The user's submitted review JSON remains LOCAL DRAFT/NOT_EVALUATED and is not applied as coverage approval. New absolute paths and final manifest SHA are posted to #445 after verification.
