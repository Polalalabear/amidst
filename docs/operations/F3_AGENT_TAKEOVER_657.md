# F3 (#657): Agent takes over in 8785 and LIVE

Status: engineering record for the F3 PR on `claude/feat-e3` (2026-11-22). Identity stays `UNCONFIRMED` throughout. Ground Truth, renderer
trajectories, visibility and depth are not read by any path below.

## What changed

| Area | Path | Behaviour in Agent mode | Rule mode |
| --- | --- | --- | --- |
| 8785 Q2/Q5 controller | `src/amidst/q1q5/service_agent_q5.py`, `openai_gateway.py` (v2 request) | `agent_service.decide` sees every detection (score ≥ 0.3, all classes), all frames, the reference crop and the D340 scene context. SELECT / OWN_BOX is adopted even when the colour gate, score, top-k or graph would block it (`submitted.linked_without_rule_gates`, `RULE_OVERRIDE:` reason codes). NOT_VISIBLE / STILL_HERE → stay (decided_by AGENT). A failed call → RULE_FALLBACK with the contract `fallback_reason`. | Byte-identical to `RuleController` (test). |
| 8785 main tracking screen | `service_agent_track.py`, `cross_camera_demo.associate(decider=, manual=)`, `serve_demo_integration.py` | The track request carries `switch_mode: AGENT_SEQUENTIAL`. At every loss the model is asked with zero, one or many candidates (C3), including colour-incompatible candidates (C2) and still-observed ones (C4). A SELECT adopts that local track (`AGENT_ASSOCIATION_HYPOTHESIS`, `rule_override` kept). Only an explicit STILL_HERE_OCCLUDED / NOT_VISIBLE keeps the target lost (WAIT). A SELECT with no local track, an OWN_BOX, or a failed call hands that loss back to the rule (`RULE_FALLBACK` with `NO_LOCAL_TRACK_FOR_DETECTION` / `OWN_BOX_NOT_LINKED` / the contract reason; #666 Opus M1). Answers are cached per run, so a replay costs nothing. `doc.agent` summarises decisions, adoptions and fallbacks. | `decider=None`: unchanged (existing golden tests). |
| LIVE | `src/amidst/live_mode/service_decider.py`, `server.py` (`--advisor agent`), switch / HUD / admin | People of any colour are candidates. The model is asked on LOST (any count), on AMBIGUOUS (≥ 2 near) and on a periodic recheck. SELECT reseeds the tracker; NOT_VISIBLE records `next_camera_hint`. | The `rule` / `llm` modes are unchanged. |
| 8785 UI | `frontend/workbench-v2/ui-shell.mjs`, `ui-model.mjs`, `q-api.mjs`, `app.mjs` | The title, state chip, stage, multi-view tiles and floor-plan note all use one source (`stagePlan` at the playhead). The "observed again" note shows only while the playhead is inside that segment. The multi view shows every camera of the run (8 tiles for 8CAM), labelled 目前追蹤 / 候選 / 未見目標. Manual re-selection: candidates are the other local tracks at the playhead, and `manual_seed {track_ref, at_us}` makes that track the target from there (`OPERATOR_SELECTION`, decided_by USER). The journal shows the Agent summary and each Agent or operator decision. | Rule requests carry no `switch_mode` (unchanged). |

## Evidence (LOCAL)

`local/evidence/f3-657-20261122/` (MANIFEST.sha256 SHA-256 `3f6f4647b86db4760a64bceb4610c29add2a03629080b5ac545d34376a84608a`) has 42 files (13 MB); the first version (before M1) had MANIFEST SHA-256 `4c329e6f8c2332bd3aacf3285bc51a04eec68c269539a84e1e3fc3a6c0926588`, 27 files. It cannot be rebuilt byte for byte, because the model answers vary.

- `track/{A4-1,B4-1,A4-1-8CAM}-{rule,agent,agent-replay}.json` are the q_core_track responses from the clone server (port 8795). `track/summary.json` summarises them.
- `screens/screenshots/*.png` are headless screenshots (1440×900). `screens/f3-screens-results.json` lists each screenshot's title, plan note, tiles and manual note, with its SHA-256.
- `m1/screens/` is the rerun after #666 M1 (server on port 8796 from commit `454a5b62`): the A4-1 / B4-1 Agent track responses, 12 screenshots and `f3-screens-results.json` (SHA-256 `7631cfa7ac1b77c94eef00306ec99a8b48aece907a82323decbbe791c8d403be`). These replace the earlier screenshots for review.
- `usage/usage.jsonl` is the ApiGuard log: 35 calls, all `OK`, estimated USD 0.3327 (`gpt-6.1-terra`); the M1 rerun added 14 calls, USD 0.1293.

### Agent adoption on real data (D124 runs, whole window)

After #666 M1 (`m1/screens/*-agent-track-response.json`):

| Run | Decisions | Adopted (SELECT) | Rule fallback | Explicit WAIT | Model calls |
| --- | --- | --- | --- | --- | --- |
| A4-1 | 8 | 7 | 1 (`OWN_BOX_NOT_LINKED`) | 0 | 8 |
| B4-1 | 6 | 3 | 3 (2 `OWN_BOX_NOT_LINKED`, 1 `NO_LOCAL_TRACK_FOR_DETECTION`) | 0 | 6 |

Before M1 (first version, an unadoptable answer was turned into WAIT):

| Run | Decisions | Adopted | Fallbacks | First request | Replay | Est. USD |
| --- | --- | --- | --- | --- | --- | --- |
| A4-1 | 8 | 7 | 0 | 40.2 s | 0.01 s, 0 calls | 0.066 |
| B4-1 | 13 | 3 | 0 | 55.6 s | 0.01 s, 0 calls | 0.137 |

A sample adopted row (A4-1, t = 5.0 s) reads: `AGENT_SERVICE_DECISION`, decision_source `AGENT`, answer SELECT `CAM_EXT_CLEAR D1`, reason
codes `RULE_OVERRIDE:SCORE_BELOW_0.4`, `adopted_track_ref` set, 4 detections, 4 frames, and a reference crop attached. The matching
`AGENT_ASSOCIATION_HYPOTHESIS` event switches the chain at 5.0 s. Under the rule, the target had cut to EXT_CLEAR at 3.0 s instead.

Before M1, B4-1 got ten SELECT answers but only three picked a detection that belongs to a local track. The others became WAIT, so
CAM_WIDE (14.0–20.8 s under the rule) was left as a blind interval: an artefact of the implementation, not a model judgement (Opus,
#666). After M1 those losses go back to the rule, and the B4-1 single view shows CAM_WIDE 14.0–20.8 s again. Fewer decisions (6
instead of 13) follow from the cadence: after a fallback the same loss is not asked again until the candidate set changes. This is an
observation for F4/E3, not a scored result: no accuracy claim is made here.

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
- **LIVE.** The static wall clipping uses the `live` gate. No LIVE camera is validated yet, so no clipping is applied. If the scene
  context cannot be built, Agent mode does not start: `/config` `llm_switch` reports `SCENE_CONTEXT_UNAVAILABLE:<type>` and the log says so (#666 M3).
- **Contract.** `switch_mode` and `manual_seed` are in the `q-core.track-request.v1` schema and §3.1 of `Q_CORE_SEARCH_TRACK_V1.md` (#666 M2; compatible addition, no new pin).
- **Follow-up (not blocking).** The UI does not yet show "Agent deciding" or progress during the first 40–55 s request.
- **Screenshot server.** For the evidence run only, a copy of the checkout `.venv` was placed in the scratch clone, with its `python`
  pointing to the owned runtime, so that the IO guard passes as designed.
