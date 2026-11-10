# #417 cross-camera DEMO_DEFAULT replay before Claude review

Refs #417, #475, #410 and #445. The user explicitly requested a **new** follow-up Draft PR; the original #475 is preserved, and this PR does not close its formal acceptance gate. Base is `mainline/q1q5@796cc176cd40bedbfe701b95192d3c8679755aa9`. No PR histories, integration branch or merge commits are combined.

## Actual output

| Run | Association hypothesis | Declared source-clock time | As-of responses | Final state |
| --- | --- | --- | ---: | --- |
| A4-1 | CAM_EXT_CLEAR → CAM_W1; observed gap 1.2 s | 2026-11-01 14:00:10.200000+08:00 | 251 | LOST / UNKNOWN evidence |
| B4-1 | CAM_W2 → CAM_W1; observed gap 0.2 s | 2026-11-01 14:10:02.200000+08:00 | 211 | LOST / UNKNOWN evidence |

These are LOW-confidence association hypotheses, not confirmed same-person handoffs. A4's destination has only one qualifying sample, score approximately 0.40967 with WEAK red; it may be a false positive. The rule retains it as a hypothesis rather than relabelling it as identity truth. B4 does not switch to R101 at 3.4 s because the selected W1 local chain still has an observation at that instant. Later EXT_CAR (A4, 17 s gap) and WIDE (B4, 8.8 s gap) candidates exceed this demo's six-second association window and are rejected, not silently added.

`single-view.json` is the exact #410 §3.5 array: `{kind,camera_id,range_us,evidence_state}`. `track-response.json` is its final source-bound wire response. `responses.jsonl` contains a response at every 200,000 µs as-of boundary, including zero and the run end. `timeline.jsonl` records the corresponding current camera/state and declared Asia/Taipei clock time. `switch-events.json` identifies actual next-camera samples and the enabling static transition. `association-audit.json` records rejected candidates too. The full input/output sizes, hashes and executed source-file hashes are in the LOCAL receipts; curated results are committed in `D132_417_CROSS_CAMERA_RESULTS.json`.

## Evidence boundary and defaults

- The pure inference module receives only frozen observation/track value objects and a projection of static transition IDs. It has no filesystem, graph-loader, model, media, network, renderer or evaluation imports. Original #475 outputs, source clocks, frozen parameter files, graph bytes and RGB remain unchanged. No detector is rerun.
- The loader opens exactly the pinned index, records, local CX-8, receipt, configuration and declared clock for each run, plus the pinned camera graph and explicit job. The actual job pins were checked against the #475 published receipt before execution; the loader verifies those job-supplied byte pins, run/clock/local observation IDs, source sample times, graph content hash and shared catalog pin. Extra input roles, protected fields, symlinks, duplicate keys, nonfinite JSON and changed byte pins fail closed. Full records are never passed into inference; only person/score/time/color observation values are projected.
- The index uses scene ID `controlled-l-corridor`; the static graph uses `controlled_scene_v1_s001`. The job explicitly binds those names to revision r004 and common camera catalog `3eba8572…`. The original documents are not rewritten, and no general scene alias is installed. Graph byte SHA is `e250413a0d0a2aeb61bd98bb1763236b1e39127f919cee1ee3ca3bd906b78409`, from the pinned mainline base; its approval remains DRAFT.
- All cross-camera logic is DEMO_DEFAULT / formal_eligible=false. Source sample interval 200,000 µs, local score floor 0.4 and shared non-NONE color match the #475 local output. Handoff gap maximum is 6,000,000 µs, borrowing the #475 search-window value as a **new demo association rule**, not reusing its historical approval for another meaning. Seed policy: earliest available local seed; simultaneous ambiguous seeds/handoffs remain UNKNOWN, with no camera-name identity choice.
- A later seed needs a **direct** graph transition, no contemporaneous valid sample in the current selected local chain, a bounded gap and shared WEAK/STRONG color. Graph connectivity alone never supplies a detection, location, physical route or switch. An empty sample stays missing; only actual seed/LINKED samples produce OBSERVED intervals. Association events themselves remain INFERRED / LOW and identity UNCONFIRMED.
- Each as-of response uses observations with `timestamp_us < as_of_us`. A candidate's association uses only current-chain samples at or before that candidate's source time. No later sample determines an earlier switch. The reported `first_grid_as_of_us` is the next source sampling boundary at which that candidate can appear under #410's strict cutoff.

## LOST semantics raised by the user

The user asked whether all-camera absence should first be temporary loss and only become confirmed loss after a waiting period. That is a reasonable separate product state, but **current #410 defines trailing LOST without a timeout**: no later sighting is known before the requested as-of time. Thus an as-of response can currently end LOST, while the final retrospective single-view sequence later calls that earlier interval GAP. Neither state proves the person left the scene.

This PR preserves that contract. The six-second handoff eligibility window is **not** a six-second confirmed-loss timeout. It does not add a formal TEMP_LOST → SEARCHING → confirmed LOST policy. Claude/user review should decide that state/parameter change separately; the underlying #475 camera-local linker already has its own temporary-loss steps, which are not silently promoted to a new core API contract. Blind estimates remain UNAVAILABLE / PREDICTION_UNAVAILABLE; no position or curve is fabricated.

## Reproduction

All newly generated output is LOCAL under `$AMIDST_ARTIFACTS/d131-previews/cross-camera/` (15 files, including two receipts and summary). The exact job is `$AMIDST_ARTIFACTS/d131-previews/cross-camera-job.json`, SHA-256 `8586dce9a965193edc456e5a6bed48e331de874f678f85e5b5b20b7449dd71f7`. Its source locators are explicit; #475 input payloads remain at their original LOCAL locators and were not part of the preview-copy operation. The other preview assets are now persistent. The exact absolute paths are posted to #417/#445.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src "$EXISTING_PYTHON" -B scripts/run_cross_camera_demo.py --job "$AMIDST_ARTIFACTS/d131-previews/cross-camera-job.json" --job-sha256 8586dce9a965193edc456e5a6bed48e331de874f678f85e5b5b20b7449dd71f7 --out-dir "$NEW_CANONICAL_OUTPUT_DIRECTORY"
node scripts/check_cross_camera_demo.mjs --source="$AMIDST_ARTIFACTS/d131-previews/checkouts/pr452" --output="$NEW_CANONICAL_OUTPUT_DIRECTORY"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src "$EXISTING_PYTHON" -B -m pytest -o addopts= -q tests/q1q5/test_cross_camera_demo.py
```

The runner refuses an existing output directory and enforces at least 8 GiB before output creation/every file write. Actual execution was `cd87c5b16d49c9ca3ccbeb8e41502c746f46d747`; the later consumer checker/documentation commit is not misrepresented as the executed producer head. No original source file or previous result is overwritten.

## Focused verification

- Python: **46 passed**, including the 16 shared #410 vectors; no-file-open inference trap; AST import boundary; protected GT/script/renderer field rejection; closed role allowlist before any read; source hash/symlink failures; future-frame invariance and strict as-of; absent/current/ambiguous camera cases; missing samples and clock rollover.
- Independent consumer: **462/462 saved as-of responses** equal `singleViewSequence` from clean #452 head `088252833665a4bca9fcfbf31597b4bb296fb549`. The checker also verifies output hashes, per-file receipt hashes, evidence states and time bounds. This checks the actual outputs, not only synthetic vectors.
- No-allow architecture guard and base diff check are recorded at the final Draft head. Only the existing proposed `q-core.track-response.v1` literal is registered, without authority exceptions. Full backend/browser integration, identity accuracy, physical navigation and formal acceptance remain NOT_VERIFIED.

## Future #445 connection after review and explicit merge authorization

1. Register the exact #475 index/local-chain, job, declared clock and static graph pins as a **demo source**, preserving the explicit scene-name binding and DRAFT/UNKNOWN states. The automatic earliest-seed selection must be visible as a fixed demo preset; these outputs cannot answer arbitrary feature/region requests or imply a human-selected identity.
2. At the backend `q_core_track` adapter, use `response(..., as_of_us=resolved_request_time, ...)` on the pinned projected local tracks. For a recorded grid time, an exact matching `responses.jsonl` row may be replayed. Never send the final full-run response for an earlier `playback_now_us`, or round to a future row. Other feature/selection/time requests need recomputation or an explicit unavailable response.
3. Feed the returned `sightings`, `multi_view`, `single_view` and `blind` through the existing core API/store/views / tracking-source adapter. Bind RGB resolution separately to #442's actual run/clock/camera/frame pins. No GT/renderer timing, event script or synthetic media fallback is introduced by this data adapter.
4. #443 already owns the canonical backend sequence helper, while #452 owns its frontend counterpart. Reconcile this standalone helper to that canonical implementation during the future authorized integration, keeping the shared vectors. The schema registry will need one unioned entry for the same literal and both source paths, not duplicate entries or whole-file replacement.
5. Add this follow-up after #475/source graphs in the #445 plan and rerun merge-tree against the then-current real integration head. The earlier seven-head pairwise matrix does not cover this new PR. Run actual RGB/as-of single/multi acceptance and retain the LOST-policy decision as an open review item. **No integration merge is created here.**
