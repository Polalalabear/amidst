# Recorded display estimates for the 3D model

Refs #612, #594 and Draft #623. The current response field is
`trackResponse.display_estimate`, with `schema_version: q-core.display-estimate.v1`.
It is optional, display-only, and separate from `blind.estimate`. Its compatible
contract is [Q_CORE_SEARCH_TRACK_V1.md](../contracts/Q_CORE_SEARCH_TRACK_V1.md)
section “相容新增：display_estimate”. Contract B is not edited.

## Source and failure behavior

Only selected single-view sightings' observation IDs and the pinned camera
calibration are read. The bbox bottom center is projected to z=0 through the
existing Projector. GT, renderer trajectories, visibility and depth are not
inputs. Source/run/clock bindings stay those of the index and response;
observations after `as_of_us` are ignored.

`FOOT_EDGE_MARGIN_PX = 4`: a selected box with
`y2 >= calibration["height"] - FOOT_EDGE_MARGIN_PX` is not projected.
Each selected observation retains either its point or an explicit reason.
A nonfinite bbox, undefined ground projection or nonfinite result retains
`GROUND_PROJECTION_UNDEFINED`; a clipped foot retains
`FOOT_TRUNCATED_AT_FRAME_BOTTOM`. If the latest selected timestamp contains
any reason, the display result is UNKNOWN, including when a peer at that
timestamp projects successfully. Clipping wins over undefined projection.
An earlier valid point is not reused to hide a newer failed projection.
Missing per-camera calibration is also retained as CALIBRATION_MISSING.
Only a complete absence of selected observations yields
NO_PROJECTABLE_SELECTED_OBSERVATION. Multiple valid latest observations
remain AMBIGUOUS_SELECTED_OBSERVATIONS. These are the five contract reasons.

Known results include est_xy, uncertainty_m, last_observed_us, method,
uncertainty_basis, max_speed_m_s, source_clock_id, source_index_sha256 and
calibration_sha256. The point stays at the last projected position during
a gap without a newer selected observation. `uncertainty_m` is the
**速度上限下的可達半徑**, elapsed source seconds times the existing proposed
display speed limit of 2 m/s. It excludes calibration and box error and is
not an error bound or a physical-clearance claim. Historical trail is omitted.

The callback runs after the tracking response is produced; no display point
feeds Agent, ranking or reconstruction. The display object is included in
output_sha256 before response saving. With no callback, the optional field
is absent and the original response/hash stays unchanged. The existing 3D
model reader consumes display_estimate; its internal view-model estimate
and the separate blind.estimate are unchanged. This does not establish that
the active main-screen UI renders a visible 3D estimate/radius.

| Run | Display estimate source |
|---|---|
| B-05 | UNKNOWN: no bound calibration for this synthetic run |
| A4-1 | Selected D124 detections and pinned r004 camera catalog |
| B4-1 | Selected D124 detections and pinned r004 camera catalog |
| r005 | UNKNOWN: no bound calibration for this static adapter |
| A4-1-8CAM | Selected index records and the bundle's pinned camera catalog |
| B4-1-8CAM | Selected index records and the same pinned catalog |

Both 8CAM runs retain the accepted RUN_SPECS extension. Default ambiguity
stays UNKNOWN; a legal manual selection can provide a concrete display point.
B-05/r005 8CAM sources are still absent from the approved bundle, not replaced.

## Current focused verification: 2026-11-24 Opus fixes

Use the existing Python environment, owned demo and approved 8CAM bundle.
Set PYTHON to the existing demo Python, DEMO_HOME to the existing
`local/data/demo-owned-v1`, ROOT_8CAM to
`local/data/r004-4actor-natural-walk-eightcam-20261114/bundle/safe`, OUT to
`local/evidence/cx623-review-20261124`, and UV_CACHE_DIR to `local/uv-cache`.
Resolve these paths for the scratch checkout; no new environment is installed.

```sh
AMIDST_DEMO_HOME="$DEMO_HOME" AMIDST_ROOT_8CAM="$ROOT_8CAM" AMIDST_TEST_EVIDENCE="$OUT" PYTHONPATH=src:scripts uv run --offline --no-project --python "$PYTHON" python -B -m pytest tests/q1q5/test_demo_estimate.py tests/q1q5/test_demo_eightcam.py tests/q1q5/test_service_core_track.py tests/q1q5/test_service_agent_track.py tests/q1q5/test_api.py -o addopts= -q -p no:cacheprovider --basetemp="$OUT/tmp-pytest-final"
node --test frontend/workbench-v2/event-names.test.mjs frontend/workbench-v2/monitor-room-model.test.mjs frontend/workbench-v2/scene3d-model.test.mjs frontend/workbench-v2/core-screens.test.mjs
uv run --offline --no-project --python "$PYTHON" python -B scripts/check_architecture_guard.py --repo . --base origin/main
git diff --check
```

- Python: **116 passed, 0 skipped**. Existing LOCAL input opt-ins are both set.
  API/Demo objects are exercised in process: no HTTP server is started.
- Node: **54 passed, 0 skipped**. Model/unit tests only, no browser or screenshots.
- Tests cover height-3 clipping, above-horizon latest observations after an
  earlier valid point, one invalid latest peer, nonfinite bbox/result, undefined
  ground, clipping priority, source isolation, optional schema attachment, all
  five reason codes, saved response hashes, callback-off byte-equivalent output,
  and display_estimate versus blind.estimate separation. The schema tests reuse
  the existing core-contract subset checker; no jsonschema dependency is added.
- The requested nested schema literal is registered in schema_registry_v1.json;
  no authority pin or outer track-response version changes. Architecture guard,
  focused Ruff and diff check pass. The initial sandbox uv panic is an environment
  startup failure; offline uv outside the sandbox ran the final tests.
- No service/browser startup, screenshot, paid call, detector inference or render
  was run for these review fixes. The existing 8785/8791 services and demo pin
  were not changed. This is not a new pin gate or visible 3D acceptance.

LOCAL `local/evidence/cx623-review-20261124/MANIFEST.json`, SHA-256 `02454c08de07ef0f54bbbdbc7fd1ecf01691d131fccc1562e38f74a7f2d12547`, 11 receipt files / 400,793 bytes (manifest itself excluded). Temporary pytest state was removed.
The same commands regenerate the tests and selected-observation receipts from
existing inputs; byte-identical timings are not promised.

## Historical checkpoints: do not add these counts to the current run

| Date / head | Environment and focused set | Historical result |
|---|---|---|
| 2026-11-18 D326, before main 8290f190 | Existing demo environment, both LOCAL input opt-ins set; demo_eightcam + demo_estimate + d147_acceptance + demo_launcher + api | 76 passed, 0 skipped |
| 2026-11-20 d380d4ff, main 8290f190 merged | Same LOCAL-enabled set plus agent_service | 90 passed, 0 skipped |
| 2026-11-24 9f3871f9 | Existing Python, AMIDST_ROOT_8CAM set, AMIDST_DEMO_HOME omitted; demo_estimate + demo_eightcam + service_core_track | 25 passed, 7 skipped (owned-demo fixtures not enabled) |

These were different heads, environments and file sets, not three results
for one run. The old 1 px clipping/replay counts do not describe the new 4 px
and undefined-projection behavior. The 2026-11-24 wider startup attempt at
about 5.5 GiB failed the unchanged 8 GiB gate; it is historical evidence,
not current service verification. Current review fixes use only focused tests.

Historical LOCAL manifests (retain their original scope):

- `local/evidence/cx612-d326-20261118/MANIFEST.json`, SHA-256 `1f1ee80459a4eeb407c72d944b2e45e7e999edb42a3971213ce2194b021a6b0f`, 5 files / 292,776 bytes.
- `local/evidence/cx594-d326-20261118/MANIFEST.json`, SHA-256 `95b30841b20777f92cf1d55b057c2e6846a3cd823673e5e777aa9b4c96c01db0`, 14 files / 2,308,983 bytes.
- `local/evidence/cx623-main-20261120/MANIFEST.json`, SHA-256 `280ba887a7cf432c4fe3f1ce54ba9b984002bfc39d065f0aff8f45d6bcb8f9a2`, 12 files / 2,306,108 bytes.
- `local/evidence/codex-w-20261124/a1/MANIFEST.json`, SHA-256 `2cbf881c0dc0d6cfb6f65cef1cc1ab443a52fb3b0429653d2081ec6dba8f26fd`, 12 files / 437,796 bytes.

The historical test/model receipts can be regenerated with their committed
head and corresponding opt-ins. Historical screenshot receipt hashes remain
historical; no screenshots were regenerated in the review-fix task.
