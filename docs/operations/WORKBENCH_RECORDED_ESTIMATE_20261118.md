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

The full integration-service startup and dependency smoke remain pending.
The existing P1 startup requires 8 GiB free, and the disk check reported
approximately 6.8 GiB. Startup returned DISK_BELOW_8_GIB. The existing
threshold was retained. The 8785 service and pin were not changed.

LOCAL `local/evidence/cx612-d326-20261118/MANIFEST.json` SHA-256 `1f1ee80459a4eeb407c72d944b2e45e7e999edb42a3971213ce2194b021a6b0f`, 5 files / 292,776 bytes. The commands regenerate the model and observation replay receipts.
