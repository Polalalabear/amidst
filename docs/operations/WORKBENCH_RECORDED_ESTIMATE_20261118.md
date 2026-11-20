# Recorded ground estimates for the 3D view

Issue #612 adds trackResponse.estimate to the recorded integration service.
The estimate uses the selected single-view sightings' observation IDs.
Each selected detection's box foot is projected with the pinned calibration
onto z=0 through the existing Projector. Source/run/clock bindings remain
those of the index and response.

The response includes est_xy, uncertainty_m, last_observed_us, method,
source_clock_id, source_index_sha256 and calibration_sha256. The point stays
at the last projected position during a gap. The radius is elapsed source
seconds times the existing proposed display speed limit, 2 m/s, from
PredictionParams.speed_range_m_s. It is labeled SPEED_ONLY_REACHABLE_RADIUS.
It excludes calibration and detector-box error, so it is a nominal display
envelope. It does not establish a measured error bound or physical clearance.

Missing calibration, missing selected projections or multiple selected
observations at the latest time produce UNKNOWN with a reason. No camera
or actor is substituted. The optional historical trail is omitted.
Records after as_of_us are ignored, and source observations are unmodified.
The API adds the estimate before hashing and saving its response.

| Run | Estimate source |
|---|---|
| B-05 | UNKNOWN, no bound calibration registered for this synthetic run |
| A4-1 | Existing D124 selected detections and pinned r004 camera catalog |
| B4-1 | Existing D124 selected detections and pinned r004 camera catalog |
| r005 | UNKNOWN, no bound calibration registered for this static demo adapter |
| A4-1-8CAM | Existing selected index records and the bundle's pinned camera catalog |
| B4-1-8CAM | Existing selected index records and the same bundle's pinned camera catalog |

The two real observation replays queried every 200 ms. A4-1 produced 240
INFERRED and 10 UNKNOWN samples out of 250. B4-1 produced 209 INFERRED and
one UNKNOWN sample out of 210. The index records and calibrations alone
produce these samples. No RGB was rendered and no new detector ran.

## Verification

Set AMIDST_DEMO_HOME to the owned demo and OUT to a LOCAL evidence
directory. Existing Python and Node dependencies are used.

```sh
AMIDST_TEST_EVIDENCE="$OUT" python -B -m pytest tests/q1q5/test_demo_estimate.py tests/q1q5/test_api.py -o addopts= -q -p no:cacheprovider
node --test frontend/workbench-v2/scene3d-model.test.mjs frontend/workbench-v2/core-screens.test.mjs
python -B scripts/check_architecture_guard.py --repo . --base origin/main
git diff --check
```

The focused Python run passed 49 tests with zero skips. The frontend model
tests passed 36. Isolation fixtures restrict all input-field access and
check future observations, source preservation, ambiguity, missing
calibration and saved-response hash consistency. New Python files pass Ruff.
Architecture guard and diff check pass.

The initial startup attempt returned DISK_BELOW_8_GIB at approximately
6.8 GiB free. At the final D326 check approximately 9 GiB was available;
the unchanged 8 GiB startup threshold passed. The normal Demo entry point
then loaded all four original runs and both available 8CAM runs. The final
focused Python set passed 76 tests with zero skips, including normal-entry
estimates for B-05/A4-1/B4-1/r005 and both 8CAM responses. Dependency smoke
passed with six runs and 20 first frames. The headless browser verified
both 8CAM walls at 900 and 1300 px heights. See the reproduction commands
in WORKBENCH_8CAM_D302_20261118.md. The full 3D visual gate and 8785 pin
remain with their assigned reviewer; the service and pin were not changed.

LOCAL `local/evidence/cx612-d326-20261118/MANIFEST.json` SHA-256 `1f1ee80459a4eeb407c72d944b2e45e7e999edb42a3971213ce2194b021a6b0f`, 5 files / 292,776 bytes. The commands regenerate the model and observation replay receipts.

Final integration evidence is LOCAL `local/evidence/cx594-d326-20261118/MANIFEST.json`, SHA-256 `95b30841b20777f92cf1d55b057c2e6846a3cd823673e5e777aa9b4c96c01db0`, 14 files / 2,308,983 bytes. It includes the normal-entry receipts, source-only projection replay, dependency smoke and four headless screenshots. The same commands regenerate the checks; screenshot clocks and tokens can differ.

## 2026-11-20 main integration

Merge commit `dc2d5373` includes main `8290f190`. The service initialization
keeps main's NotApplicableAgent for B-05 and the recorded track_estimator
hook. W2's camera projection relocation and Agent service are retained;
q1q5/api.py introduces no evaluation import. The focused Python set above,
plus tests/q1q5/test_agent_service.py, passes 90 tests with zero skips.
The workbench model/name tests pass 53. Six-run dependency smoke and the
A4/B4 eight-camera browser smoke pass after merge (20 decoded first
frames, two heights, 20 unique browser assertions, no page/API errors).
No new detector, Agent call or asset render is performed. Full 3D visual
acceptance and the 8785 pin remain with Claude and the user.

LOCAL `local/evidence/cx623-main-20261120/MANIFEST.json` SHA-256 `280ba887a7cf432c4fe3f1ce54ba9b984002bfc39d065f0aff8f45d6bcb8f9a2`, 12 files / 2,306,108 bytes. Contains the final tests, main pin audit, smoke receipts and four screenshots. Rebuild with WORKBENCH_8CAM_D302_20261118.md's focused commands, adding test_agent_service.py to pytest. Screenshot clocks and tokens vary.
