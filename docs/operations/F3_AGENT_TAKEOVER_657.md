# F3 (#657): Agent takes over in 8785 and LIVE

Status: engineering record for the F3 PR on `claude/feat-e3` (2026-11-22). Identity stays `UNCONFIRMED` throughout. Ground Truth, renderer
trajectories, visibility and depth are not read by any path below.

## What changed

| Area | Path | Behaviour in Agent mode | Rule mode |
| --- | --- | --- | --- |
| 8785 Q2/Q5 controller | `src/amidst/q1q5/service_agent_q5.py`, `openai_gateway.py` (v2 request) | `agent_service.decide` sees every detection (score ≥ 0.3, all classes), all frames, the reference crop and the D340 scene context. SELECT / OWN_BOX is adopted even when the colour gate, score, top-k or graph would block it (`submitted.linked_without_rule_gates`, `RULE_OVERRIDE:` reason codes). NOT_VISIBLE / STILL_HERE → stay (decided_by AGENT). A failed call → RULE_FALLBACK with the contract `fallback_reason`. | Byte-identical to `RuleController` (test). |
| 8785 main tracking screen | `service_agent_track.py`, `cross_camera_demo.associate(decider=, manual=)`, `serve_demo_integration.py` | The track request carries `switch_mode: AGENT_SEQUENTIAL`. At every loss the model is asked with zero, one or many candidates (C3), including colour-incompatible candidates (C2) and still-observed ones (C4). A SELECT adopts that local track (`AGENT_ASSOCIATION_HYPOTHESIS`, `rule_override` kept). WAIT keeps the target lost, so the rule cannot cut on its own. A failure lets the rule decide. Answers are cached per run, so a replay costs nothing. `doc.agent` summarises decisions, adoptions and fallbacks. | `decider=None`: unchanged (existing golden tests). |
| LIVE | `src/amidst/live_mode/service_decider.py`, `server.py` (`--advisor agent`), switch / HUD / admin | People of any colour are candidates. The model is asked on LOST (any count), on AMBIGUOUS (≥ 2 near) and on a periodic recheck. SELECT reseeds the tracker; NOT_VISIBLE records `next_camera_hint`. | The `rule` / `llm` modes are unchanged. |
| 8785 UI | `frontend/workbench-v2/ui-shell.mjs`, `ui-model.mjs`, `q-api.mjs`, `app.mjs` | The title, state chip, stage, multi-view tiles and floor-plan note all use one source (`stagePlan` at the playhead). The "observed again" note shows only while the playhead is inside that segment. The multi view shows every camera of the run (8 tiles for 8CAM), labelled 目前追蹤 / 候選 / 未見目標. Manual re-selection: candidates are the other local tracks at the playhead, and `manual_seed {track_ref, at_us}` makes that track the target from there (`OPERATOR_SELECTION`, decided_by USER). The journal shows the Agent summary and each Agent or operator decision. | Rule requests carry no `switch_mode` (unchanged). |

## Evidence (LOCAL)

`local/evidence/f3-657-20261122/` (MANIFEST.sha256 SHA-256 `4c329e6f8c2332bd3aacf3285bc51a04eec68c269539a84e1e3fc3a6c0926588`) has 27 files (6.8 MB). It cannot be rebuilt byte for byte, because the model answers vary.

- `track/{A4-1,B4-1,A4-1-8CAM}-{rule,agent,agent-replay}.json` are the q_core_track responses from the clone server (port 8795). `track/summary.json` summarises them.
- `screens/screenshots/*.png` are headless screenshots (1440×900). `screens/f3-screens-results.json` lists each screenshot's title, plan note, tiles and manual note, with its SHA-256.
- `usage/usage.jsonl` is the ApiGuard log: 21 calls, all `OK`, 187,493 input and 3,188 output tokens, estimated USD 0.2034 (`gpt-6.1-terra`).

### Agent adoption on real data (D124 runs, whole window)

| Run | Decisions | Adopted | Fallbacks | First request | Replay | Est. USD |
| --- | --- | --- | --- | --- | --- | --- |
| A4-1 | 8 | 7 | 0 | 40.2 s | 0.01 s, 0 calls | 0.066 |
| B4-1 | 13 | 3 | 0 | 55.6 s | 0.01 s, 0 calls | 0.137 |

A sample adopted row (A4-1, t = 5.0 s) reads: `AGENT_SERVICE_DECISION`, decision_source `AGENT`, answer SELECT `CAM_EXT_CLEAR D1`, reason
codes `RULE_OVERRIDE:SCORE_BELOW_0.4`, `adopted_track_ref` set, 4 detections, 4 frames, and a reference crop attached. The matching
`AGENT_ASSOCIATION_HYPOTHESIS` event switches the chain at 5.0 s. Under the rule, the target had cut to EXT_CLEAR at 3.0 s instead.

In B4-1 the model gave ten SELECT answers, but only three picked a detection that belongs to a local track. The others are WAIT
(`not_adoptable: NO_LOCAL_TRACK_FOR_DETECTION`), so B4-1 in Agent mode leaves CAM_WIDE (14.0–20.8 s under the rule) as a blind interval.
This is an observation for F4/E3, not a scored result: no accuracy claim is made here.

## How to reproduce

1. Gateway, in its own terminal: `AMIDST_API_ENABLED=1 AMIDST_API_MAX_USD_TOTAL=3 AMIDST_API_MAX_TOKENS_PER_CALL=24000 python -B scripts/openai_agent_gateway.py --queue-dir <owned>/state-f3/agent-gateway`.
2. Server: `AMIDST_RECORDED_AGENT=openai python -B scripts/serve_demo_integration.py --config <copy with state_root=state-f3> --auto-root-8cam <8cam bundle> --port 8795`. This needs the checkout's `.venv` on the owned runtime python, so the owned IO guard stays on.
3. Screenshots: `UI_QA_BASE_URL=http://127.0.0.1:8795 UI_QA_OUTPUT=<out> node tests/browser/ui-redesign/f3-screens.mjs`.

## Deviations and limits

- **Contract B.** "Agent only within legal top-k" predates D340. In Agent mode, rule gates are information, not filters: D340 and the
  hypothesis plan §4 C1–C5, C7 and X1.
- **Relaxed linker.** A detection the Agent picks seeds a LocalLinker with the colour gate off and min_score lowered. OWN_BOX counts
  as adopted only when it overlaps a detection with IoU ≥ 0.3.
- **8CAM and B-05 main screen.** These go through `core_query.execute_core_track`, which has no decider. `doc.agent` reports
  `MAIN_SCREEN_AGENT_D124_RUNS_ONLY`, and manual re-selection there answers `MANUAL_SEED_UNSUPPORTED`. Both are disclosed in the UI and
  never silently ignored. Separately, the 8CAM `person` track request returns `UNKNOWN` with an empty single view even in rule mode; this
  was not investigated here.
- **Latency.** The first Agent request on a D124 run waits 40–55 s for its model calls (synchronous in `q_core_track`). Later requests are cached.
- **LIVE.** The static wall clipping uses the `live` gate. No LIVE camera is validated yet, so no clipping is applied.
- **Screenshot server.** For the evidence run only, a copy of the checkout `.venv` was placed in the scratch clone, with its `python`
  pointing to the owned runtime, so that the IO guard passes as designed.
