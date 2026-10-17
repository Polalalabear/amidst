# Independent Office person preset / fixture — 2026-10-17

Extracted only the person fixture, person contact settings and opt-in preset catalog from C6 @ `9937135f69da3e768c1d2714ee416dc3a780f04c`. Fixture endpoints updated by D18; C6 route planning, rendering and benchmark changes are outside this split. Stacked on C4a D17 `099513e`.

The opt-in `configs/office_demo_presets_person_v1.json` registers legacy Office, auditorium control and Office person, preserving legacy Office as the default. Backend resolves each run's pinned contact configuration; launcher fingerprints that configuration. Missing optional inputs degrade independently; hash/path integrity errors remain fatal. Person observations remain 33 MISSING/null with a separate C4a ground_estimate.

Reproduce (existing assets/environment only):

```sh
OFFICE_PRESETS="$PWD/configs/office_demo_presets_person_v1.json" ./start-office-demo.command
```

This command is a handoff recipe; no service was started in this task. Person default observation is FRONT 4.6 s (`observation:218abc805d72fe39c4496da0`); end is REAR 8.2 s (`observation:a012bc1b71556a46191bc68a`); blind frames 4.8–8.0 s, no substitution. Legacy fixture is unchanged.

## Actual output

- Model / effort: UNKNOWN (not exposed authoritatively).
- PR / commits: local split branch `codex/office-person-preset`, parent C4a D17 `099513e`; no merge into integration.
- Files changed: three person configs, scripts/office_demo_backend.py, scripts/start_office_demo.py, tests/workbench/test_office_demo_presets.py, this report, docs index and WORK_LOG.
- Commands run/results: `PYTHONPATH=src:scripts OFFICE_TEST_ASSETS=/Users/polalabear/Developer/amidst UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -m pytest tests/workbench/test_office_demo_presets.py tests/workbench/test_office_launcher.py -o addopts='' -q` → 28 passed in 55.08 s, 0 failed/skipped; Ruff F checks and git diff --check PASS.
- Artifacts: config SHA-256 below. The existing person bundle is LOCAL, not copied or published; safe_inputs `e9aff43f08955222348407a3435baff05c8a38f6638226a1bd43dc544836c998`.
- Verified: D18 explicit endpoint refs/times/cameras and zero observations in the open interval; config hash/path rejection; unchanged legacy canonical responses via focused regression.
- Not verified: browser, full demo, C4b at this milestone, full suite. No render, inference experiment, GT evaluation or source mutation.
- Deviations/UNKNOWN: opt-in catalog deliberately preserves existing default catalog behavior; later C4b work uses this catalog. Physical/identity acceptance stays UNKNOWN/UNCONFIRMED.

- `configs/office_demo_office_person_fixture_v1.json`: `19d4939d47dd9ee92f145de6849ae336962cd1951b31fa40432183f36f540dec`
- `configs/office_demo_presets_person_v1.json`: `0da96de94f8287adbfeade57bc0cd7ec146bee424d88aa14092850f3c605ebe7`
- `configs/office_person_contact_v2.json`: `b84a2d328159e9c12ffe59dfef015cce65ebd2bd966551a731c7bf2df2bac3d5`
