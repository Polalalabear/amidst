# C4a FOOT_RAY_PIXEL_BAND v1.1 — 2026-10-17

PR #45 `be646ca` confirmed in [clause-by-clause record](CONTRACT_V11_CONFIRMATION_20261017.md), including IO-Q9–Q12, BH-Q10–Q12 and FR-Q6/Q8. No Claude contract or K1/K5 source files changed. Parent C4b PR #44 @ `0942f5a`.

New producer uses the same v2 component contact_pixel, v±2 floor rays, far-end radius allowance, explicit NOT_APPLICABLE occlusion and 8-neighbour clipped endpoint sensitivity. Head prior is not read for this basis; there is no head fallback. Missing/invalid band/radius, projection failure, empty/disjoint/overlong clips and invalid sensitivity fail closed. D8 and CONTACT_OCCLUDED behavior remain separate. The opt-in runtime uses new `hybrid_contact_v1_1.json`; historical v1 config and all previous freezes remain byte-for-byte retained. Schema stays .v1; unsupported bases are unusable. Raw diagnostic coordinates remain forbidden as endpoints.

Actual person outputs: POINT0 / SEGMENT33 / UNKNOWN0; 29 FOOT_RAY_PIXEL_BAND, 4 HEAD_RAY_HEIGHT_PRIOR. C4a eligible33, original33 MISSING/null unchanged. FRONT4.6 band length0.7384191729883363m; REAR8.2 remains head-ray2.4926122151184877m. Full segment range0.7318733604641967–2.5718090841879455m. Original flags, projection, contact quality, camera/calibration and 8m cap unchanged. This is conditional projection evidence, not measured foot truth or an accuracy bound.

C4b using these endpoints remains READY but returns 1 representative (not the old 3); tests accept 1..K and do not tune settings to restore K=3. The [D18/K1 speed setting](../../configs/office_person_blind_hypothesis_v1.json) remains [0,2]m/s; READY establishes a feasible configured source-map path, not whole-building connectivity or physical acceptance. Real negative evidence is a later C5 milestone.

## 實際產出 / Actual output

- Model / effort: UNKNOWN (authoritative session metadata not exposed).
- PR / commits: feature branch codex/c4a-foot-ray-band, stacked on #44; publication records exact commit.
- Files changed: hybrid_contact.py; versioned hybrid config; freeze/report producers; backend/launcher config selection; focused hybrid/report/preset/launcher/C4b tests; clause confirmation, this report, new person prediction/summary/table, docs index and WORK_LOG.
- Commands run/results: final focused command/result recorded below. Intermediate 87-test run had one obsolete assertion expecting exactly3 K1 paths; changed assertion to contract1..K, no production parameter change. Subsequent C4a/C4b focused run59 passed in6.58s; not added to final count. Ruff checks and git diff --check PASS.
- Artifacts: three new frozen files below; old freezes not overwritten. Config k=2 is declared before these outputs and not tuned using GT.
- Verified: two-ray/radius arithmetic, UNKNOWN head-prior independence, no head fallback, invalid declarations/projections, supplied occluder skip, D8, same flags and observation preservation, runtime focused checks.
- Not verified: GT/RQ1 accuracy, real negative evidence, browser/full demo, K1 restricted-policy labels, full suite. No render/source write, dependency install, new environment or worktree.
- Deviations/UNKNOWN/follow-ups: IO-Q10 signed residual and IO-Q11 VISIBLE_BOTTOM_FAR_BOUND intentionally unimplemented. Historical D17 HEAD fallback snapshots retained as historical evidence; new producer rejects that basis for LOW_INCIDENCE-only. K1 policy work remains Claude-owned by user instruction.

Freeze command:

```sh
PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/freeze_person_hybrid_contact.py --bundle data/engineering/office_person_20261016_v1/office --fixture configs/office_demo_office_person_fixture_v1.json --contact-config configs/office_person_contact_v2.json --hybrid-config configs/hybrid_contact_v1_1.json --output docs/engineering/C4A_PERSON_FOOT_BAND_PREDICTIONS_20261017.json --summary docs/engineering/C4A_PERSON_FOOT_BAND_SUMMARY_20261017.json --table docs/engineering/C4A_PERSON_FOOT_BAND_TABLE_20261017.json
```

- `configs/hybrid_contact_v1_1.json` SHA-256 `7402f7d6af22c4bd54913d731ea0f29785607d630d6100b9651afca0c0d69bab`
- `docs/engineering/C4A_PERSON_FOOT_BAND_PREDICTIONS_20261017.json` SHA-256 `c1dfc1bd3baacca514f2066adcfc10036cbcfaf657e5636d8482b837d6dd4616`
- `docs/engineering/C4A_PERSON_FOOT_BAND_TABLE_20261017.json` SHA-256 `d44d86ad8c16b9f414472167678ba718be717b28e6644321322d0f99ecbb9a5f`
- `docs/engineering/C4A_PERSON_FOOT_BAND_SUMMARY_20261017.json` SHA-256 `792434654ad0505770a065adedf46d04c6b352217da0265a2e9ccddd43f78f6d`

Final verification:

```sh
PYTHONPATH=src:scripts OFFICE_TEST_ASSETS=/Users/polalabear/Developer/amidst UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -m pytest tests/unit/test_hybrid_contact.py tests/unit/test_hybrid_contact_report.py tests/workbench/test_office_demo_presets.py tests/workbench/test_office_launcher.py tests/workbench/test_blind_hypothesis_integration.py -o addopts='' -q
```

**87 passed in59.88s, 0failed/skipped.**
