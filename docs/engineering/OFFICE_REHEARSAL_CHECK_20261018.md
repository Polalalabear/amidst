> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# Office rehearsal readiness command — 2026-10-18

`./start-office-demo.command rehearsal-check --output <new external JSON path>` runs the launcher's existing readiness checks against its current managed service and records each result as PASS, FAIL or UNKNOWN. It never starts or stops a service. Missing service, unexecuted stages, unavailable optional presets or unavailable artifacts remain UNKNOWN; known failures remain FAIL even if later checks pass. Exit codes: PASS 0, FAIL 1, UNKNOWN 2.

It checks process identity/cwd/listener, source fingerprint, launcher metadata, served frontend/vendor hashes, preset catalog, per-scene source/clock binding, dual-camera timelines and PNG availability, and the person target/retrieval APIs. Contact-quality degradation is recorded separately. It measures manifest/safe-input/index/frozen-response SHA-256; safe-input/index hashes are also compared to configured pins. A measured manifest or frozen response hash without an expected pin is **not** a claim that it was independently validated against a known freeze.

Output is exclusive-create, mode 600; an existing file is never overwritten. Paths in the application checkout, asset/evidence repositories, configured bundle or a GT directory are rejected, including resolved directory aliases. Reports contain local paths/provenance; do not publish raw receipts blindly. This committed [curated receipt](OFFICE_REHEARSAL_CHECK_20261018.json) contains only the bounded verification summary and hashes. No original assets, RGB or GT were copied.

## Reproduce

Use this PR's branch, with existing assets/dependencies and a clean tracked checkout:

```sh
./start-office-demo.command start --no-open
./start-office-demo.command rehearsal-check --output /private/tmp/office-rehearsal-user-check.json
./start-office-demo.command stop
```

Choose a new existing-parent output path each time. The launcher discovers its PID and ephemeral port; it does not assume a URL. It overwrites PYTHONPATH with its own src and uses the existing offline uv environment. `OFFICE_ASSETS_REPO` / `OFFICE_EVIDENCE_REPO` may point to existing sources. Do not use stop unless the service is yours to stop. This test's service was created solely for this authorized test and then stopped.

Focused tests:

```sh
PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache \
  uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python \
  -m pytest tests/workbench/test_office_launcher.py \
  tests/workbench/test_rehearsal_check.py -o addopts='' -q --tb=short
```

Result: **23 passed in 0.92s**. Scoped Ruff and `git diff --check`: PASS. Initial test failures exposed an audit label assuming camera_id in mocked frames and an absent new fingerprint dependency in test setup; both corrected before the final run. No original readiness gate was removed.

## Live result

Claude rehearsal base `3fb485730d295e7b977da92c8477cff60067940a`; independent Codex implementation commit `ba1ffe1cdd895eb66639dc65245dc73c5b2aeadf` is based directly on it. Claude's branch/checkout were not modified. This uses the existing checkout/environment, with no new worktree, clone, venv or asset copy.

Actual commands were the three reproduction commands above, with output `/private/tmp/office-rehearsal-check-20261018.json`. **59 PASS, 0 FAIL, 0 UNKNOWN**, exit 0. Full LOCAL receipt SHA-256: `ab014883383824ce5865fd1871edd90f924f132a1b1e6c826d1232a343112455`.

Key hashes:

| Artifact | SHA-256 |
| --- | --- |
| Person bundle manifest | `e49eec2cbe3df5ba98cbda2d6659cb03b80c1a1d4cdf9a57dec50e90491e8d71` |
| Person bundle safe_inputs | `e9aff43f08955222348407a3435baff05c8a38f6638226a1bd43dc544836c998` |
| Bound C5 D21 index | `7c464ec42d30afdd3489b53c8c0c2f6b866a4d542cc324ad8bd3aa89f8f0d83c` |
| Original C5 K1-sync frozen response gzip | `d7dbc907d0c04a12928ee3a92f783ba56148e118684fafd603ee33091371f6e8` |

The test created managed PID 86508 on dynamically discovered port 53148. Explicit launcher stop sent SIGTERM only to that owned process; subsequent PID-specific lsof found no listener. Existing unknown-owner Demo PID 97774, PostgreSQL 68475 and Ollama 97769 were preserved. No inference changes, rendering, Agent replay, P1 scale experiment or GT evaluation were performed here. HTTP readiness is bounded service evidence, not browser, identity, physical or scientific acceptance.

## 實際產出 / Actual output
- Model / effort: UNKNOWN
- PR / commits: independent `codex/rehearsal-readiness`, based on Claude rehearsal `3fb4857`; implementation `ba1ffe1cdd895eb66639dc65245dc73c5b2aeadf`; report/curated receipt are in the following documentation commit of the same Draft PR.
- Files changed: `scripts/start_office_demo.py`, `scripts/office_rehearsal_check.py`, `tests/workbench/test_office_launcher.py`, `tests/workbench/test_rehearsal_check.py`, this report and its JSON receipt.
- Commands run and results: focused pytest 23 passed; scoped Ruff PASS; diff check PASS; actual start → rehearsal-check → stop, 59 PASS / 0 FAIL / 0 UNKNOWN; PID-specific lsof verified test listener gone.
- Artifacts: full LOCAL receipt `/private/tmp/office-rehearsal-check-20261018.json` SHA above; committed curated receipt with per-check status and artifact hashes; LOCAL start/check/stop logs under `/private/tmp/office-rehearsal-check-*20261018*`.
- Verified: actual managed service on requested rehearsal base; individual checks/statuses, source and runtime binding, bundle/index/freeze hashes; protected/exclusive output and fail/unknown behavior in tests; other services preserved.
- Not verified: visual/browser rehearsal acceptance, full eight-minute narrative, physical/identity/research claims, checkpoint approval or actual integration merges.
- Deviations, UNKNOWN items and follow-ups: Draft is stacked on the rehearsal branch to make the tested base exact; coordinate its eventual integration separately. The original frozen response file and estimator/prediction files remain unchanged.
