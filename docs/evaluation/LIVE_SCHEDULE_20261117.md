# CX-L2 graph scheduling acceptance — 2026-11-17

Issue #553; baseline main `21aacc8e` includes B screen #551. Tested runtime code
`12e58b50c88cefb9b5e1b57bf3fb9a6f97846ec4`, tree
`dc1405c03c5f895b31af3e3d85ce3931a37822a8`. Later receipt/doc commits do not change
runtime. Runtime and reproduction contract:
[handoff](../operations/LIVE_SCHEDULE_HANDOFF_20261117.md).
Machine-readable results: [receipt](live_schedule_20261117/receipt.json).

## Test-first and quality

The initial scheduler test failed collection because the module did not exist; initial
Node tests likewise failed on the missing capture-plan module. Final focused runs:
`python -m pytest tests/live_mode -q`: 44 passed;
`node --test frontend/live-mode/test/*.test.mjs`: 36 passed;
`git diff --check`: passed. Tests cover selected model batch, no empty observations
for skipped cameras, active neighbors, lost expansion, switching, unknown topology,
source binding and protocol isolation. No changes to existing tracker/people/advisor
or system.mjs. No full suite was authorized or run for this task.

Replayed all 38 frozen detection recordings from LOCAL
`evidence/live-mode-advisor-20261116/sol2` (18) and
`evidence/live-mode-tracker-20261116/gate` (20), A4/B4 19 each. Their RGB-derived bbox,
score and HSV observations, clock and registered camera ids are sanitized before a new
rule-only Tracker and scheduler execute. Old est_xy, old tracking decisions and GT are
excluded. GT is reattached only afterward for the unchanged t1 scorer. Source file
hashes and all per-record results are in `quality.json`. This is deterministic replay
of the earlier model outputs, not a new model benchmark or 38 fresh browser runs.

| Policy | Mean on target | Wrong person | Lost |
| --- | ---: | ---: | ---: |
| all-camera, same code | 0.640842 | 0.213850 | 0.145308 |
| adaptive, N=3 (rejected) | 0.608614 | 0.147426 | 0.243960 |
| adaptive, N=1 (default) | **0.657261** | 0.179602 | 0.163137 |

N=3 failed the original replay threshold; its evidence remains in `replay-n3`.
N=1 expands after the first lost observation and searches all cameras after the
second. It meets the issue's replay criterion without changing the scorer or tracker.
N was selected on this same cohort; there is no held-out statistical/generalization
claim. Lost fraction rises 0.017829 absolute despite less wrong-person time.
A4 on-target mean is 0.401048 → 0.433886, B4 0.880636 → 0.880636. The weak A4
baseline remains weak; this is engineering acceptance, not confirmed identity.

## Real latency

Four serial MPS/browser runs, advisor off, same detector and source scene, all eight
registered cameras available, 320×180 captures, requested 5 fps. The same-code baseline
uses `--schedule all`; candidate uses `--schedule adaptive --expand-every 1`.
A4 route is 50 seconds (58-second measurement); B4 is 42 seconds (50-second
measurement). Warm-up discards the first four displayed ticks. Recorded p50/p95
are capture-to-B-screen display, not only model forward time. Achieved fps counts
displayed rounds per capture-clock span; skipped busy intervals are recorded drops.
Each route/mode was run once on a shared, non-exclusive GPU. Resource utilization
and camera visibility logs are diagnostic; active-camera visibility is not the
person-following metric above. No live-following 0.65 claim is made from these logs.

| Route / mode | Rounds/s | p50 ms | p95 ms | Mean inferred cameras |
| --- | ---: | ---: | ---: | ---: |
| all-A4 | 0.875 | 933.9 | 1527.2 | 8.000 |
| adaptive-A4 | 1.164 | 822.1 | 922.3 | 6.328 |
| all-B4 | 0.897 | 938.7 | 1288.7 | 8.000 |
| adaptive-B4 | 1.246 | 764.0 | 1026.8 | 6.155 |

All four runs had zero protocol violations. Scheduling improves throughput by 33.0% (A4) and 38.9% (B4), but does not reach the requested 5 fps. Busy-interval drop ratios remain 76.8% / 75.4% in adaptive A4/B4.

The graph and safe camera catalog are byte-hash bound at startup. Graph v3 has seven
nodes, lacks ENTRY, and has dense W1/W2 neighborhoods. ENTRY selects all registered
cameras (`GRAPH_SCOPE_UNKNOWN`), hubs select seven; unknown topology is never filled
from GT. This limits speed gains. Graph is an observation hint, not physical-route
or collision authority. Files with runtime-forbidden metadata are rejected.

## Evidence and limits

LOCAL artifact root `$AMIDST_ARTIFACTS/cx553-20261117`: test-first logs, final focused
logs, both N strategies' full replays, four real latency JSON/logs, and server logs.
`ARTIFACTS_MANIFEST.json` records every retained result's size and SHA-256; its own
hash, file count and bytes are in the committed receipt. Rebuild with the handoff
commands and `scripts/live_mode/schedule_receipt.py`; new real timings need not match
exactly. The original input files and hashes are immutable external prerequisites.

No paid calls or key reads; no original Blender, scene, calibration or GT asset changes;
no primary checkout/pin/service changes. #559 detector and launcher are still a separate
unmerged feature: this branch's measured detector is the main baseline. Joint detector
plus scheduler behavior requires integration verification after review. No merge or
deployment has been performed. B screen receives whitelisted schedule data; adding a
new schedule visualization to system.mjs is outside this task's permitted file scope.
