# K8a C4b pre-sync — 2026-10-17

Refs #17/#18, #58 @131869d127798d3deba595dd9b5c533279f8fbc8. Draft stacked on #53 @4019a44f1dc22130e7b6013179ac86c899ca1200; do not merge. No integration/main or upstream Claude branch changed. K8a is not registered in a real preset, ReviewStore or C4b cache.

## Six required checks

1. **PASS — full real HTTP responses.** Before and after replacing the two modules, actual POST `/api/target_reconstruction` in NONE, BASELINE and BASELINE_AND_FEEDBACK returned byte-identical complete JSON and native seals. Actual TIME_RANGE retrieval and append-only feedback also compare byte-identical, excluding only retrieval.stats.latency_ms. LOCAL captures `/private/tmp/k8a-http-before.json` and `k8a-http-after.json` have identical SHA-256 `d98d515a6e592d4c503f782b8d2532a6834ef02bad4a3272aa5317110046ce78`. Capture-only fixed session, dynamic loopback HTTP server, closed after each run.
2. **PASS — 34-key D19.** All four target stages READY; NONE/BASELINE/BASELINE_AND_FEEDBACK/feedback each281.125m², 4498 summed cells, union592 cells/37m², reduction0%. 34 unchanged five-field keys. All duplicate feedback frames ALREADY_APPLIED_FRAME, no added evidence/log.
3. **PASS — negative controls.** Upstream synthetic/golden tests verify REAL K1 rejects synthetic method with NEGATIVE_EVIDENCE_INVALID / VISIBILITY_METHOD_NOT_SOURCE_MESH_RAYCAST. Added real C5 wrapper control remains VISIBILITY_RULE_NOT_ELIGIBLE; wrapper source unchanged.
4. **PASS — chain/isolation.** Actual retrieval→K5→K1 chain verified; REAL calls omit data_origin and returned payloads contain no data_origin anywhere. Existing real presets/configs unchanged; new config is separate and never registered. Upstream tests verify origin default/REAL equality, spoofing rejection, strict D21/detector type comparisons, mixed-origin previous-response rejection.
5. **PASS — package/pins.** C5 index SHA `7c464ec42d30afdd3489b53c8c0c2f6b866a4d542cc324ad8bd3aa89f8f0d83c` unchanged. Old freezes retained. All existing native API sections in the new package exactly equal the prior freeze; wrapper dependency pins and wrapper hash honestly differ. New gzip `C5_K8A_PRESYNC_REAL_20261017.json.gz` SHA `e2d2594d5f9adce3504fe06790896819b4f0701fb6954c1e2b4a74ffc4f91cc9`; decoded SHA `2d9027dfe5822b6e4f2b4f158d6622c0a923de95a831566046cd3c70abd73b81`. Gzip is lossless/mtime0. No real settings/footprints were rebuilt or tuned.
6. **PASS — focused/regression.** Twelve requested/relevant files **404 passed in107.76s, 0failed/skipped**. All checks used OFFICE_TEST_ASSETS so real integration tests did not skip. Ruff and git diff --check PASS.

## Scope and reproduction

Exact upstream copies: engine.py, retrieval_evidence.py, tests/unit/test_blind_hypothesis_synthetic.py and separate configs/k8_synthetic_blind_hypothesis_v1.json from131869d. Only the first two are runtime K1/K5 changes. Dependency ledger pins #58 and the actual file hashes; other module bytes and real configuration/presets remain unchanged. FrameRetrievalIndex wrapper is not modified. Additional files are verification helper, one wrapper negative test, six-check receipt and a new safe derived package/report.

```sh
PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/verify_k8a_real_http.py /private/tmp/k8a-real-new.json
shasum -a 256 /private/tmp/k8a-real-new.json
PYTHONPATH=src:scripts OFFICE_TEST_ASSETS=/Users/polalabear/Developer/amidst UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -m pytest tests/unit/test_blind_hypothesis.py tests/unit/test_blind_hypothesis_office.py tests/unit/test_blind_hypothesis_pruning.py tests/unit/test_blind_hypothesis_restricted.py tests/unit/test_blind_hypothesis_synthetic.py tests/workbench/test_frame_retrieval.py tests/workbench/test_blind_hypothesis_integration.py tests/unit/test_hybrid_contact.py tests/unit/test_hybrid_contact_report.py tests/workbench/test_office_demo_presets.py tests/workbench/test_office_launcher.py tests/workbench/test_target_reconstruction.py -o addopts='' -q
PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/freeze_person_blind_hypotheses.py --bundle data/engineering/office_person_20261016_v1/office --output /private/tmp/C5_K8A_PRESYNC_NEW.json
PYTHONPATH=src UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/package_c5_receipt.py --input /private/tmp/C5_K8A_PRESYNC_NEW.json --output /private/tmp/C5_K8A_PRESYNC_NEW.json.gz --receipt /private/tmp/C5_K8A_PRESYNC_NEW_RECEIPT.json
.local-worktrees/phase1-finalization/.venv/bin/ruff check src/amidst/blind_hypothesis scripts/verify_k8a_real_http.py tests/unit/test_blind_hypothesis_synthetic.py tests/workbench/test_frame_retrieval.py
git diff --check
```

All output paths must be fresh. Before capture used the same helper while source was4019a44; after capture used the copied131869d modules. The branch's helper is the same logic with import/format cleanup; no volatile dynamic port or session issuance timestamp enters captures. Native output hashes per mode are recorded in `K8A_C4B_PRESYNC_CHECKS_20261017.json`.

## 實際產出 / Actual output
- Model / effort: UNKNOWN.
- PR / commits: independent Draft on #53 @4019a44, exact commit posted on #17/#58.
- Files changed: two exact runtime modules, their ledger pins, upstream separate config/test, wrapper negative test, HTTP verifier, six-check report/receipt, new package/receipt. No source asset/real config/preset/wrapper changes.
- Commands run and results: commands above; six checks PASS,404passed/107.76s, no failed/skipped; native HTTP full responses equal; Ruff/diff PASS. Initial verifier import-format lint corrected before commit.
- Artifacts: new safe package SHAs above, LOCAL HTTP captures and producer-bound package; old freezes remain original.
- Verified: all six #58 synchronization checks against actual person data; source exact bytes; new honest pins; strict fail-closed and REAL hashes preserved.
- Not verified: frontend/browser, GT/RQ1/RQ2/recall, full suite, K8 synthetic demo acceptance; no rendering or source writes.
- Deviations, UNKNOWN items and follow-ups: NONE. Source head checked131869d before and after checks; if it changes, re-sync/re-check required. Draft remains unmerged; #58 itself not merged by this task.
