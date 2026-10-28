> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# Office Demo review follow-up — 2026-10-17

Refs #15/#17/#18/#23, reviews #46/#47, D19/D20 in #26. Stacked on #47 `6bafe041cad88121d14fdec671adbcc9e117b593`. Draft only; CP2/CP3 not approved. No merge.

Default launcher presets now include legacy Office backup and Office person (plus the existing control). `./start-office-demo.command --no-open` needs no OFFICE_PRESETS. Optional scene failures keep the default Office usable: `PRESET_READINESS=DEGRADED` plus scene reasons; the person has a distinct `PERSON_DEMO_READINESS` result. The human scene's nested hypothesis READY and D18 interval, and complete34-frame retrieval, are checked independently. HTTP/JSON exceptions and UNKNOWN results identify API/error type/reason. An observed target's expected UNKNOWN does not mask an inferred-layer failure or count as an inferred-layer failure.

D19 modes are NONE (omit all camera evidence), BASELINE, BASELINE_AND_FEEDBACK (unchanged default). Mode is sealed in both returned hashes. Feedback refs require the last mode and same-session issuance. K1/K5 files are byte-identical to the dependency ledger. D18 scope/interior-observation and missing/stale evidence reject before K1, proven with a test stub that fails if K1 executes. NONE avoids reading omitted evidence. K5 append-only rules still reject evidence removal; use a fresh request without a previous hash for standalone NONE.

**Measured v1.1 output: 1→1 representative; summed areas281.125→255.75m² over17 timestamps; mean16.536765→15.044118m²; −9.026233882%.** FRONT4.6 uses the0.738419173m foot band, REAR8.2 the2.492612215m head prior. The older3→1/−16.6% comparison cannot be reproduced with v1.1 by merely omitting evidence. No parameters were tuned to restore that count. Evidence acts before generation; the original paths were not pruned two-at-a-time. Baseline and feedback are the same34 frames; feedback adds0 prunes. **偵測器對比度與部分遮擋的漏判未驗證**. Identity remains UNCONFIRMED; physical authority UNKNOWN; original33 MISSING/null unchanged. C5 visibility rules remain unchanged pending Claude. K1 #48 synchronization/restricted_regions wiring and C6/D14 remain deferred.

Legacy REAR8.6 becomes READY/FOOT_RAY_PIXEL_BAND instead of SEGMENT_TOO_LONG; FRONT4.4 retains AMBIGUOUS_MERGE and HEAD_ANCHOR_UNRELIABLE. Legacy4.4→8.6 still lacks a legal starting endpoint; no D7 substitution or alternative route was performed. REAR22–24m approaches clip_end24.7m: v−2 rays beyond clipping fail UNKNOWN, with no shortening or head fallback. Missing foot_anchor_band_px is explicitly tested as FOOT_BAND_UNAVAILABLE. D20's8m cap is unchanged.

## 實際產出 / Actual output

- Model / effort: **gpt-6.1-sol / high**, verified in this session's turn_context. C4b's current regeneration is attributed explicitly; its historical UNKNOWN is not guessed retroactively.
- PR / commits: branch `codex/office-demo-review-followup`, base #47/6bafe04; exact publication SHA and Draft PR link posted on issues #15/#17/#18/#23/#26.
- Files changed: launcher; target API schema/dispatch; blind_hypothesis_integration; freeze/package scripts; focused hybrid/launcher/integration tests; C4a/C4b/C5 reports, C4b regenerated JSON, new D19 gzip/receipt, this record/index. No frontend/K1/K5/original assets.
- Commands run and results: below. Initial launcher18 passed in0.99s; intermediate focused70 passed in15.17s. Main focused run132 passed/1 failed in80.54s (test-only hand-calculated reduction constant typo9.026945309 vs measured9.026233882). Corrected affected integration file: **23 passed in11.82s**. Overlapping counts are not summed. Ruff/diff checks PASS.
- Artifacts: C4b JSON SHA-256 `91560790e8189637edfde5e21df57def5b9469c749a3f7ff39673c0adcd5148d`, canonical `bbbc40e7269bc087299588ebcbb5d12414c5dfe195bc116c3ae223647175b456`; D19 gzip `24ba202d2d33542e3dad6d0bf14e17026ce5149f7d39ef97591413918de8c8c1`, decoded `3b48a6f7fa324f07620c3c39158cbdf45f69c89c16d2f061fdfd2f880995321d`; small receipt `31d4138cb4473bd9d72ea1ab235dcf7f5ce1bd2b159fb4bd9c24393a26d26f1f`. All under docs/engineering. Full uncompressed C5 D19 output is LOCAL `/private/tmp/C5_PERSON_D19_20261017.json`. Historical C5 artifacts retained.
- Verified: sealed modes, default equality, actual endpoint/area/count comparison, same-session/append-only/freshness guards, no-K1 rejection, missing-band failure, observation preservation, pinned K1/K5 bytes, gzip losslessness. In-process34-frame retrieval75.690083ms (not HTTP/browser latency).
- Not verified: GT/RQ1/RQ2, detector contrast/partial-occlusion recall, continuous visibility, native K1 restriction labels, K4/K6 browser/full stage demo, full suite. No Blender render/export/save, source/media changes, install, new environment/worktree or external model call. Runtime verification recorded below if executed.
- Deviations/UNKNOWN/follow-ups: v1.1 changes the requested3→1/−16.6% demonstration to1→1/−9.0262%; frontend/demo narration must use current real output. C7 document conflict and C3b hardening are separate follow-ups. Initial sandbox uv run panicked in macOS system-configuration; approved execution using the same offline existing environment succeeded.

Exact focused command:

```sh
PYTHONPATH=src:scripts OFFICE_TEST_ASSETS=/Users/polalabear/Developer/amidst UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -m pytest tests/unit/test_hybrid_contact.py tests/unit/test_hybrid_contact_report.py tests/unit/test_floor_visibility_index.py tests/unit/test_restricted_policy.py tests/workbench/test_blind_hypothesis_integration.py tests/workbench/test_frame_retrieval.py tests/workbench/test_office_demo_presets.py tests/workbench/test_office_launcher.py tests/workbench/test_target_reconstruction.py -o addopts='' -q
```

Corrected focused rerun uses the same environment and `-m pytest tests/workbench/test_blind_hypothesis_integration.py -o addopts='' -q`.

```sh
PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/freeze_person_blind_hypotheses.py --bundle data/engineering/office_person_20261016_v1/office --skip-retrieval --output /private/tmp/C4B_PERSON_V11_REVIEW_FINAL_20261017.json
cp /private/tmp/C4B_PERSON_V11_REVIEW_FINAL_20261017.json docs/engineering/C4B_OFFICE_PERSON_RESPONSE_20261017.json
PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/freeze_person_blind_hypotheses.py --bundle data/engineering/office_person_20261016_v1/office --output /private/tmp/C5_PERSON_D19_20261017.json
PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/package_c5_receipt.py --input /private/tmp/C5_PERSON_D19_20261017.json --output docs/engineering/C5_PERSON_D19_20261017.json.gz --receipt docs/engineering/C5_PERSON_D19_RECEIPT_20261017.json
```

All exit0. Producers reject existing outputs/outputs inside source bundles. No GT read.

```sh
.local-worktrees/phase1-finalization/.venv/bin/ruff check src/amidst/workbench/blind_hypothesis_integration.py tests/workbench/test_blind_hypothesis_integration.py tests/workbench/test_office_launcher.py scripts/freeze_person_blind_hypotheses.py scripts/package_c5_receipt.py tests/unit/test_hybrid_contact.py
.local-worktrees/phase1-finalization/.venv/bin/ruff check --select F scripts/start_office_demo.py src/amidst/workbench/service.py
git diff --check
```

## Final verification and live launcher result

The exact nine-file focused command above was rerun after the test constant correction: **133 passed in78.83s, 0failed/skipped**. Earlier runs overlap and are not added.

At implementation `ad0be6d5b73e9cadee39a9d8cdc11bea739b3fed`, `./start-office-demo.command --no-open` exited0. Dynamic port61858, PID47309; owned cwd/listener and HTTP frontend hashes MATCH; all three scene timelines/PNG probes passed. `PERSON_DEMO_API=target_reconstruction READY`, `PERSON_DEMO_API=frame_retrieval READY`, `PERSON_DEMO_READINESS=READY`, `PRESET_READINESS=READY`, `HTTP_HEALTH=PASS`, `FRONTEND_MATCH=PASS`. This is bounded HTTP/API readiness, not browser/full stage acceptance.

`./start-office-demo.command stop` exited0 and SIGTERM stopped only owned PID47309. Pre-existing Workbench PID97774/port57597, PostgreSQL68475 and Ollama97769 were preserved. This test service is no longer running. Low-priority camera foot-hidden-mask ownership/interface tracking is [#49](https://github.com/Polalalabear/amidst/issues/49); no mask implementation started.
