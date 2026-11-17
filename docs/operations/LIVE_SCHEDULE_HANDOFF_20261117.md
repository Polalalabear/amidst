# CX-L2 live camera scheduling — 2026-11-17

Issue #553; branch `codex/feat-live-schedule`, base `main@21aacc8e` (#551 B screen).
This branch is independent of unmerged #559 (CX-L1 detector/launcher). Combining their
changes and rerunning joint inference is pending review/integration, not verified here.

## Runtime contract

The backend selects the active camera and graph-v3 neighbors using only its tracker
state and the registered safe camera catalog. After one lost round it expands to two
hops; after two lost rounds it searches all available registered cameras. Reacquisition
or camera switching recalculates the neighborhood. First search and uncovered topology
search all cameras. Unprocessed cameras are absent observations, never fabricated empty
detections. The operator renders only `next_camera_ids` from the backend, intersected
with its registered cameras; it does not use GT to choose captures. `/detect` stays
unscheduled. `/infer` adds a schedule record, whitelisted into the B-screen channel.

Graph: `configs/q1q5/graphs/r004/camera_graph_v3.json`, SHA-256
`9896be113bf6e2b5f2d9344f1227484674fda2c2bb983d32a70d8ffcc4adfc7e`.
Camera catalog SHA-256
`3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`.
A hash or catalog mismatch fails before model loading. Graph remains DRAFT advisory
capture topology, with no physical-navigation authority. CAM_ENTRY has no v3 node:
`GRAPH_SCOPE_UNKNOWN` explicitly falls back to all cameras. W1/W2 each have six
neighbors, so their active neighborhood still costs seven cameras. No edges invented.
Files marked `must_not_enter: RUNTIME_INFERENCE` are rejected. No GT input to scheduler.

## Reproduce

From the isolated checkout, use the already provisioned runtime dependencies; no API
key or paid advisor is needed. Set the following to existing LOCAL read-only inputs:
`AMIDST_RUNTIME_DEPS=local/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps`,
`AMIDST_MODELS=local/data/demo-owned-v1/models/rtdetr`,
`AMIDST_LIVE_ASSETS=local/data/live-assets-20261115`,
`AMIDST_CAMERAS=local/data/r004-build-v2-20261021/safe_static/cameras.json`.
Resolve these against the shared artifact root if the scratch checkout has no data.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="src:$AMIDST_RUNTIME_DEPS" python -B -m amidst.live_mode.server \
  --port 8797 --device mps --models "$AMIDST_MODELS" --assets "$AMIDST_LIVE_ASSETS" \
  --cameras "$AMIDST_CAMERAS" --advisor off --schedule adaptive --expand-every 1
```

Use `--schedule all` for the same-code baseline. 8785 is rejected; do not change its pin.
Open `?role=system` and an operator route, e.g.
`?auto=A4&run=A4-1-v2-4actor&duration=50&model=glb&w=320&h=180&fps=5`.
Measurement (from `frontend/live-mode`):

```sh
LIVE_BASE=http://127.0.0.1:8797 OUT="$AMIDST_ARTIFACTS/cx553-20261117/latency" \
  node measure/latency.mjs adaptive-A4 \
  'auto=A4&run=A4-1-v2-4actor&duration=50&model=glb&w=320&h=180&fps=5' 58
```

For B4 use `auto=B4&run=B4-1-v2-4actor&duration=42` and measure 50 seconds.
GT in latency/t1 logs is evaluation-only, never sent to inference or scheduling.

Quality replay: invoke `scripts/live_mode/replay_schedule.py` with `PYTHONPATH=src`,
`--src sol2=<LOCAL evidence/live-mode-advisor-20261116/sol2>`,
`--src gate=<LOCAL evidence/live-mode-tracker-20261116/gate>`, `--cameras` as above,
`--out <LOCAL output> --expand-every 1`. The script strips GT, old projected positions,
and old tracker answers before policy execution; only after replay it attaches the GT
scoring envelope and runs `t1_analyze.mjs`. Input hashes are in `quality.json`.

Focused verification: `python -m pytest tests/live_mode -q` (44 passed),
`node --test frontend/live-mode/test/*.test.mjs` (36 passed), `git diff --check`.
Final measured results and artifact manifest are recorded in the evaluation receipt.
No full suite, paid model, API key read, source asset change, tracker/advisor/people or
system.mjs edit, primary checkout edit, deployment, or merge was performed.
