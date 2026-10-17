# C4b Office person API integration — 2026-10-17

Refs #17, CP2 #26; depends on D17/D18 PR #37 and person preset split PR #43. CP2 remains unapproved. No integration merge.

The registered person preset now returns an additive `blind_hypotheses` object on `POST /api/target_reconstruction`, a sealed `review_evidence` object, and K5 `pruning_convergence`. This is the additive field already understood by K4. No frontend files were changed.

## Historical result at 1826dab (superseded by the v1.1 freeze below)

- K1 `READY`, 3 representative hypotheses, 17 reachable regions at 4.8–8.0 s (5 Hz).
- Exact D18 endpoints: FRONT 4.6 s `observation:218abc805d72fe39c4496da0` → REAR 8.2 s `observation:a012bc1b71556a46191bc68a`. No D7 substitution or snapping. Raw C4a segment lengths 2.161564727 m / 2.492612215 m; K1 intersects endpoint support with C7 without moving the observations.
- All 33 original person observations remain MISSING with null world positions. The existing target envelope therefore remains `UNKNOWN / SELECTED_PROJECTION_UNAVAILABLE`; the independent nested hypothesis layer is READY. This distinction is intentional: the inferred layer does not repair the observed layer.
- `checks.speed` and source-map `checks.walkable` PASS for these representatives. `checks.unseen` is UNKNOWN at all 17 steps: there is **no real negative evidence**; C5 has not registered it. No renderer visibility, trajectory, depth, GT or coarse annotations enter reconstruction.
- K5 same-session re-run without new evidence is READY, with no pruning and a verified chain. A separate **synthetic test fixture** exercises a newly registered negative-evidence entry and a pruned previous path; it is never attached to the real person run.
- Physical navigation/collision remains UNKNOWN; identity UNCONFIRMED; no formal research acceptance. C7/K7 map acceptance and browser demo remain separate.

## Dependency and source binding

Selected exact files are imported from K5 PR #36 `726e390d72acacc3138587e147dfb8b6f908cd5d` (includes K1 PR #33 `7c01522523d61c7c6453521b59478e6990ec241e`) and C7 PR #40 `7214ef7f2c1d6390a71ce1eb7872045addc8b6d2`. No owner module was modified; [dependency ledger](C4B_DEPENDENCIES_20261017.json) pins every imported file. These are reviewed dependency snapshots in the C4b feature branch, not a merge into the integration branch. Once dependency PRs are approved, retarget/reconcile through the normal merge-commit workflow; do not squash, rebase or merge this stack before checkpoint approval.

The map is `C7_OFFICE_SOURCE_MAP_20261017.json`, **person** variant (1.70 m, radius 0.25 m), SHA-256 `53c3771327ad71e26f0a5f1f4db580eaafb7bc7d028b9c250c9f401495bbcd61`. The legacy radius 0.1482 m map is not used. Its source hash, canonical output hash, floor Z and run parameters are checked. Source Blender hash remains the trusted run binding `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`; the existing loader checks live source/data integrity. No Blender process is invoked.

`office_person_blind_hypothesis_v1.json` is fixed before execution: inherited K1 speeds [0, 2] m/s, nominal 1.3 m/s, 0.25 m grid, 0.2 s clock and existing search limits/weights. Only scene registration, person body radius and C7 map binding differ from the K1 config. No route/result tuning. A 5 s cooperative deadline and 8 cached responses per scene/session bound API work; no hard process timeout is claimed.

C4a endpoints keep their original no-C7-clip estimate and flags. LOW_INCIDENCE-only marks OCCLUDER_BEHIND NOT_APPLICABLE; CONTACT_OCCLUDED still has no available source foot-hidden mask. K1 uses the C7 source floor map for support and paths; it does not invent such an occluder mask.

## API and review handoff

Use the existing research session and person scene; all paths, config, endpoints and source bindings resolve server-side:

```json
{
  "session_ref": "<research session>",
  "scene_id": "blender-office-person",
  "camera_ids": ["CAM_1F_AUDITORIUM_FRONT", "CAM_1F_AUDITORIUM_REAR"],
  "start": 0.0,
  "end": 9.8,
  "top_k": 3,
  "observation_ref": "observation:218abc805d72fe39c4496da0"
}
```

`negative_evidence_refs` defaults to `[]`; clients cannot send evidence geometry, endpoints, speed/config, paths or GT. Unknown refs return UNKNOWN / NEGATIVE_EVIDENCE_UNAVAILABLE. `previous_response_sha256` resolves only a server-held sealed response from the same scene and session. K5 validates its hash, request fingerprint and append-only evidence. A missing/evicted/cross-session predecessor fails closed. No C5 retrieval registry is wired in this task.

`review_evidence` includes the original MISSING source observations, resolved ground estimates and their hashes, D17 usage checks, D18 frame range, run parameters, and the returned hypothesis response hash. Response annotation explicitly skips sealed nested artifacts so their hashes survive API serialization. Management-role access and cross-scene access remain denied. No Agent tool was added.

Missing config/map yields a K1 UNKNOWN result; existing file hash, source, floor or body-size mismatches remain fatal DataIntegrityError. Launcher fingerprints the hypothesis binding/config/map and imported implementation. The opted-in person catalog retains legacy Office as the default.

## Reproduction

```sh
PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/freeze_person_blind_hypotheses.py --bundle data/engineering/office_person_20261016_v1/office --output /private/tmp/C4B_PERSON_REPRO.json
```

Use a fresh output path. The producer refuses existing outputs and outputs inside the input bundle. It uses a fixed offline session for reproducible fingerprints and a temporary review DB; no HTTP listener or runtime is started. It verifies imported dependency bytes and source observation preservation.

For a later human browser run (not executed here):

```sh
OFFICE_PRESETS="$PWD/configs/office_demo_presets_person_v1.json" ./start-office-demo.command
```

K4/K6 UI integration and demo script ownership remain with Claude. This was the historical v1 status. v1.1 is now implemented in #46; see the current result below.

## Original implementation record / 原始實作紀錄

- Model / effort: **gpt-6.1-sol / high** for the 2026-10-17 v1.1 regeneration and review follow-up (current session turn_context verified). The original implementation recorded UNKNOWN; this does not infer its historical runtime settings.
- PR / commits: local feature branch `codex/c4b-person-hypothesis`, stacked on PR #43 / `78367659f048`; D17 commit `099513e`. PR/commit links recorded on issue #17 after publication. No integration merge.
- Files changed: dependency ledger and 9 exact dependency files; 2 person hypothesis configs; person opt-in preset binding; backend preset registration and launcher fingerprint; `src/amidst/workbench/blind_hypothesis_integration.py`, service request/dispatch/session cache, sealed annotation boundary; freeze script and response artifact; focused integration tests; this report/index/WORK_LOG.
- Commands run/results: focused final command/result recorded below; Ruff check for new integration/script/test plus exact dependency modules PASS; Ruff F checks for existing backend/service/launcher PASS; git diff --check PASS.
- Artifacts: frozen response and all producer/dependency/config hashes below/in the artifact; raw person bundle is LOCAL and not published.
- Verified: real person READY hypotheses; exact D17/D18 usage, no substitution, MISSING preservation; WSGI JSON dispatch preserves output hashes; K5 same-session chain and synthetic new evidence pruning; role/scene/override guards; missing estimates/map/config and invalid D17/D8/provenance/hash fail closed.
- Not verified: live socket/browser, K4/K6 human walkthrough, full demo, real C5 raycast negative-evidence pruning, GT/RQ1/RQ2 accuracy, K7 acceptance, full suite. No Blender render/export/source write, dependency installation, venv or worktree creation, or live service changes.
- Deviations, UNKNOWN items and follow-ups: nested READY while observed target remains UNKNOWN as described; C5 registry unavailable; K7 acceptance separate; v1.1 deferred. Preliminary test invocation omitted OFFICE_TEST_ASSETS (16 skipped, not counted as PASS); later actual-asset tests corrected two test assumptions (baseline selected row has no `state`; synthetic visible region must exceed body-radius erosion). No real-data constraints were relaxed.

- Historical `docs/engineering/C4B_OFFICE_PERSON_RESPONSE_20261017.json` at 1826dab SHA-256: `fb50b24681c732bd14e4ab0dbd4995467fe6d4b33f76b3c1ed083b07beabdca8`
- `docs/engineering/C4B_DEPENDENCIES_20261017.json` SHA-256: `29e6a7c18d13d3a30a94b8882c09be0e5f4fbf6d62ec63652e44311ba6688ac2`
- `configs/office_person_blind_hypothesis_v1.json` SHA-256: `7de91282921888f929e1ebdbc8ef8a5bfbc68ede7f1e28c6d730de86b15f693c`
- `configs/office_person_hypothesis_binding_v1.json` SHA-256: `2c71bc4afd5de9daadc4a66c032a01ca090f5b8efd826a5b55c08a575b1da687`

Historical nested K1 output SHA-256: `63d9080be8910c88f3c743d1e03691333d5559a7fe71aabf17c5afd9bfa387f6`. Frozen result canonical SHA-256: `19bd3921c193880e173cd54e358cd102c0847c4fc725b5d5da866a87ec832c44`.

Focused final verification (includes D17 and preset regression; earlier overlapping runs are not added):

```sh
PYTHONPATH=src:scripts OFFICE_TEST_ASSETS=/Users/polalabear/Developer/amidst UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -m pytest tests/unit/test_hybrid_contact.py tests/unit/test_hybrid_contact_report.py tests/workbench/test_blind_hypothesis_integration.py tests/workbench/test_office_demo_presets.py tests/workbench/test_office_launcher.py tests/workbench/test_target_reconstruction.py -o addopts='' -q
```

**94 passed in 67.09 s, 0 failed/skipped.**

```sh
.local-worktrees/phase1-finalization/.venv/bin/ruff check scripts/freeze_person_blind_hypotheses.py tests/workbench/test_blind_hypothesis_integration.py src/amidst/workbench/blind_hypothesis_integration.py src/amidst/workbench/contact_scene.py src/amidst/blind_hypothesis src/amidst/geometry/source_floor_map.py
.local-worktrees/phase1-finalization/.venv/bin/ruff check --select F src/amidst/workbench/service.py scripts/start_office_demo.py scripts/office_demo_backend.py
git diff --check
```

All PASS. New/changed focused integration modules formatted with the existing Ruff; existing service/launcher/backend formatting preserved.

Reproduction rerun with output `/private/tmp/C4B_PERSON_REPRO_20261017.json` (LOCAL) returned the identical artifact SHA-256 `fb50b24681c732bd14e4ab0dbd4995467fe6d4b33f76b3c1ed083b07beabdca8`. Producer/dependency pins and absence of private asset locators in the frozen response were also checked.

Post-commit launcher preflight at implementation commit `1826dab582b8` PASS:

```sh
PYTHONPATH=src:scripts OFFICE_PRESETS="$PWD/configs/office_demo_presets_person_v1.json" UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -c 'import start_office_demo; print(start_office_demo.preflight())'
```

Three registered scene IDs: blender-office / blender-contact-control / blender-office-person; default blender-office. Dependency fingerprint `9ec66c1cad571c79467b7577219615c8095cb82d5fb39b9854efbd6ea7207b54`. Existing unrelated untracked assets/history remain retained. This is a read-only preflight PASS, not an HTTP/browser readiness result; no service was started. The launcher's `commit` field denotes the existing APPLICATION_BASE; its separate HEAD printed `1826dab582b8`.

## Current v1.1 / D19 freeze (2026-10-17 review follow-up)

The same response path is now regenerated with `hybrid_contact_v1_1.json` (SHA-256 `7402f7d6af22c4bd54913d731ea0f29785607d630d6100b9651afca0c0d69bab`). FRONT4.6 is FOOT_RAY_PIXEL_BAND **0.7384191729883363m**; REAR8.2 remains HEAD_RAY_HEIGHT_PRIOR **2.4926122151184877m**. READY,17 regions; original33 MISSING/null unchanged. The freeze includes explicit NONE and the default BASELINE_AND_FEEDBACK comparison, with no retrieval payload (`--skip-retrieval`); complete retrieval evidence is in the D19 gzip/receipt.

**v1.1 actually produces 1 → 1 representative, with summed per-time region areas 281.125 → 255.75m² (mean16.536765 → 15.044118m²), a 9.026233882% reduction.** The requested3 → 1 / −16.6% comparison belongs to the older head-ray endpoints; it cannot be presented as a current v1.1 result. No endpoint, speed, diversity or visibility setting was changed to obtain a demonstration count. Evidence is applied before hypothesis generation; K5 does not prune two previous paths. Baseline and feedback use the same34 source frames; feedback adds0 pruned paths. 偵測器對比度與部分遮擋的漏判未驗證 (pending RQ2/GT evaluation, outside inference).

D19 API: `negative_evidence_mode` accepts NONE (no baseline/feedback), BASELINE (server baseline only), BASELINE_AND_FEEDBACK (baseline plus session-issued refs; unchanged default). The mode is in both sealed blind_hypotheses and review_evidence hashes. Feedback refs with NONE/BASELINE are rejected. A NONE→BASELINE chain is append-only; removing previously applied evidence fails closed, so a new standalone NONE request omits previous_response_sha256. D18 scope, interior-observation and evidence-freshness guards now return a sealed integration-preflight UNKNOWN **before calling K1**. K1/K5 snapshots remain unchanged.

Legacy run stays FRONT4.4→REAR8.6 under D18. Its REAR8.6 LOW_INCIDENCE-only estimate changes from v1 head-ray SEGMENT_TOO_LONG (10.237160757m) to a v1.1 READY foot-ray band. FRONT4.4 still has AMBIGUOUS_MERGE and remains HEAD_ANCHOR_UNRELIABLE / ineligible. Thus the original pair still cannot provide two legal K1 endpoints. D7 is neither invoked nor implicitly satisfied: no alternate observation, timestamp, endpoint or legacy K1 route was selected; any D7 substitution requires a separate caller-side record. Person4.6→8.2 needs no D7.

REAR's roughly22–24m range approaches clip_end24.7m. A v−2 pixel ray beyond the far clip yields UNKNOWN/PROJECTION_FAILED; the producer does not clamp/shorten it or fall back to a head ray. This is a geometric/depth-of-view limitation, not a measured target-distance or detector-recall claim. Missing foot_anchor_band_px with LOW_INCIDENCE-only is now explicitly tested as FOOT_BAND_UNAVAILABLE.

Launch from this checkout using `./start-office-demo.command --no-open`; OFFICE_PRESETS is no longer required. Legacy Office remains the default backup and person is loaded in the same catalog. PERSON_DEMO_READINESS checks nested K1 READY at4.6→8.2 and the34-frame4.8→8.0 retrieval. API failures list endpoint/error type/reason; optional person failure leaves the backup workbench usable with DEGRADED and does not claim person readiness. WORKBENCH_READY alone is not person/full-demo acceptance.

Current artifact SHA-256: `91560790e8189637edfde5e21df57def5b9469c749a3f7ff39673c0adcd5148d`. Historical snapshots remain accessible at their cited commits; original source assets are untouched. See [review result record](OFFICE_DEMO_REVIEW_FOLLOWUP_20261017.md) for commands, hashes and current verification.
