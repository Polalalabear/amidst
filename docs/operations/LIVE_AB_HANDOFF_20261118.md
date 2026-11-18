# CX-L5 staged handoff — 2026-11-18

Feature branch `codex/feat-live-ab`, base main `0606b164`; contract PR #567 v2
`6e3a35f0`, decisions D279. One Draft PR for all #566 sub-issues.

## #568: C-5 passes under D282

[D282](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6966400705)
keeps the no-player baseline at zero script forced overlaps. If either script actor
already lost script time to direct player blocking, the force event carries
`kind: "script", cause: "player_phase_shift"`. A force event without that cause
still fails C-5. The existing `chain` flag records whether the peer is currently
player-blocked at the force step. The offline scorer counts tagged events under
`forced_overlap.player_phase_shift` and retains its legacy buckets for earlier logs.
A copies these events into its private download.

At seed `0x568` and 0.1 s steps, each 100 s A4-1/B4-1 × T/A/B/C trial had zero
baseline forced overlaps, zero other script forced overlaps, zero player forced
passes and zero player penetrations. Separation was 1.0 after declared script pair
exclusion. Tagged events were A4 T/A/B/C = 2/2/2/2 and B4 = 1/0/1/1.
The regression asserts that tick 787 (78.7 s, A4 player T) classifies C passing B
as a phase shift even with `chain: false`. B had 19.0 s of direct player wait and
21.9 s of total script pause. A separate fixture with neither script delayed by the
player still emits an unclassified script force event with or without a player present.

The final LIVE Node suite passed 61 tests with N6 assets and the fake-backend browser
test enabled. Run it with `LIVE_AB_BROWSER=1 AMIDST_LIVE_ASSETS=<N6 assets>
LIVE_AB_TEST_OUTPUT=<new evidence directory> AMIDST_TEST_EVIDENCE=<new evidence directory>
node --test frontend/live-mode/test/*.test.mjs`. The offline scorer passed 27 tests with
`python -B -m pytest tests/evaluation/test_live_ab_score.py -q`. `git diff --check` passed.
LOCAL `local/evidence/cx568-d282-20261118/MANIFEST.json`, SHA-256 `7f37f44bf1d0606e30441a90a2718937d11ef9055085bf569d74b4d7234cc021`, 8 files / 38,558 bytes.
The manifest binds both test logs, test-first failure, stress counts, scenario hash,
browser receipt and diff check. Run times and browser clocks vary between runs.

### Original C-5 checkpoint before D282

Pure crowd/sim implementation is present. No operator/backend/B wiring in this stage.
Player waits forever; script/script waits 3 s, only later-priority script gets a
pair-specific pass; never a player pass. C-8 uses simultaneous proposals, stable
player > T > A > B > C priority, then full/X/Y/stay rejection until no approaching
pair violates 0.60 m. No renderer, inference or GT authority is involved.

`node --test frontend/live-mode/test/crowd.test.mjs`: **7 passed, 1 failed**.
The remaining failure is the unchanged C-5 zero non-chain forced-overlap assertion.
All eight fixed-seed stress runs (100 s, dt=.1, seed0x568, four selections per run)
had zero raw and adjusted player penetrations and separated ratio1.0 after declared
script forced-pair exclusion. All script coordinates match scriptedPose at their own
clock within1mm; own clock + own pause = sim time. Unaffected actors match a no-player
baseline. C-8, legacy movement/sliding, and real A4/B4 60-second stationary player
wait/release checks pass. C-7 mean step range 0.022720–0.030177 ms (report only).

C-5 actual non-chain counts: A4 T/A/B/C =2/2/1/2; B4=0/0/1/1. Chain counts A4=0/0/1/0;
B4=1/0/0/0. The historical chain labels are retained. Counterexample:
A4 selectedT, tick787 (78.7s), C waits3s for B at0.67738m; B is not currently blocked
by player (chain=false), but its clock is delayed21.9s, so the original synchronous
route separation does not guarantee separation after individual pauses. Original
scenario remains unchanged. This was the C-5 checkpoint that prompted D282.

Requested regression command (hud/llm_switch/n6/protocol/schedule), with
`AMIDST_LIVE_ASSETS` pointing at existing LOCAL assets: **41 passed**, zero skipped.
`git diff --check` passed. No model/API/key access, Blender render, source asset changes,
server/protocol/system edits, primary checkout changes or service operations.

LOCAL `local/evidence/cx568-20261118/MANIFEST.json`: SHA-256 `406760de912a24db6b3590e661fd23a487b6a31766a8a1598b8e840bbab5b862`;
8 files / 40,307 bytes. Logs retain test-first missing-module
failure, initial implementation and full stress failure; c5-counterexample.json includes
before/after snapshots. Generate again by running the crowd test with
`AMIDST_TEST_EVIDENCE=<new LOCAL output>`; test reads the unchanged scenario directly.
Numbers depending on performance timing cannot be rebuilt byte-for-byte. The earlier
read-only script-distance audit is `local/evidence/cx566-20261117/scripts-baseline.json`, SHA-256 `5b2f80eeaa044ed6804277e1aeefb62508baa4aaa574eb2bea10d4047132bbf4`, 1 file / 2,455 bytes;
it is not a runtime collision pass. It can be rebuilt from the same scenario and
scriptedPose at dt=.1s.

## Remaining scope and gates

#568, #569, #570 and #573 are in the same draft #584. #571, #572 and #574 depend on
#559 reaching main and on the prerequisites listed in their issues.
#559 moved to Ready under D282 after merging main into its feature branch.


## #570: offline scorer complete, producer integration pending

`python scripts/live_ab_score.py --operator-json A.json --system-json B.json --out result.json`
reads only those two logs, imports only Python stdlib, and refuses output aliases (including
hard links) of either input. Malformed JSON/unsupported schemas return nonzero without
writing output. JSON NaN/Infinity are rejected. No live backend, HTTP, scenario, assets,
key, model or inference is accessed.

Canonical v1 input container shapes for #569/#572:

- A: `schema_version:live-ab.a-log.v1`, `session_id`, `run_id`, selected `actor_id`,
  `config:{r_person,eps_m}`, `ticks:[{tick,t_capture,actors:[{id,present,xy,gt_visible}],
  pause_total_i:{actor:seconds},block_wait:[{i,j:'player',waited_s}],forced_pairs:[[i,j]]}]`.
  Every actor must have its own visibility; absent actor xy=null. All these data stay
  private to A and its downloaded log. `forced_pairs` is a private active-interval
  annotation from crowd.snapshot, needed to exclude only declared script/script
  overlap intervals; it never crosses frame-batch. Top-level `forced_overlap`,
  `spawn_adjusted`, `block_wait` retain ended events. Ended block_wait has event tick;
  ongoing wait entries on the latest capture tick have no event tick. Event tick is
  simulation-step clock; log ticks[].tick is capture clock, not interchangeable.
- B: `schema_version:live-ab.b-log.v1`, own backend `session_id`, `ticks:[{tick,
  t_capture,t_resp,t_display,tracking}]`, `actions:[{type,t_op,...}]`.
  Successful pick stores cand_id, candidate source `tick` and `est_xy`. A successful
  synchronous start with mode=TRACKING also stores its one candidate's source tick
  and est_xy. Ordinary start ends the previous segment; reselect (or start with
  reselect=true) keeps it until a successful pick; rejected operations use ok=false.
  AUTO_SINGLE events emitted during infer are deduplicated by source tick and take
  that frame's capture time as their effective frame. Synchronous start/pick use the
  recorded successful-operation t_op, not candidate tick; source target annotation
  still uses candidate tick. Source frames missing GT/clock yield UNKNOWN.

Full synthetic examples: `tests/evaluation/fixtures/live_ab/a.json`, `b.json`.
Output `live-ab.score.v1` reports each segment's target_gt (offline annotation only),
MISPICK/AMBIGUOUS_PICK, six tick categories, visible-known denominator, rates, camera
switches, >=2-consecutive-tick wrong-person proxy episodes and lost episodes with
sample-clock duration/censoring. UNKNOWN and invisible-target frames are excluded
from visible ratios; explicit absent actor is out of view. No hard tracking threshold
is imposed. Session mismatch returns a wholly UNKNOWN result with no metrics.

Two latency distributions are separate: raw t_resp−t_capture and an inclusive trailing
1000ms median per response, windowed by t_resp. This follows v2's requested calculation;
current main@0606b164 HUD source has no rolling-latency implementation, so matching it
with #572 UI remains to be integrated, not claimed already verified. The scorer derives
its own series instead of trusting a downloaded precomputed median. Negative/missing
response clocks cannot become successful tracking ticks.

Collision statistics include raw/adjusted player overlap, separation with active forced
pairs excluded, chain/nonchain/player counts, spawn records, ended+current block waits
without repeated-event double counting, and latest own pause totals. A player pair cannot
be concealed by an invalid script-only forced-pair marker. GT fields never leave this
standalone offline evaluator.

Focused `uv run --offline --no-project --python "$PYTHON" python -B -m pytest
tests/evaluation/test_live_ab_score.py -q`: **27 passed**. Test-first failed collection
before module existed. Targeted ruff check and git diff --check passed. CLI executed on
both fixtures; inputs unchanged, expected result PARTIAL due intentional missing GT.
No frontend or backend runtime file changed for #570.

LOCAL `local/evidence/cx570-20261118/MANIFEST.json` SHA-256 `70502c38edff6be63cff7d4799f74ec2d05f986ef0a06480f94343527ab85477`;
5 listed files / 4,518 bytes. Contains test-first and
focused logs plus fixture-score.json. Rebuild by the above CLI and focused command
with a fresh LOCAL output path; fixtures are synthetic committed test data.


## #573: smoke output path complete

`frontend/live-mode/measure/smoke.mjs` now creates its output parent before launching.
If OUT is set it remains the filename prefix (including relative-path semantics).
Otherwise the default prefix is smoke under:

- `$AMIDST_ARTIFACTS/evidence/live-mode/smoke/` when AMIDST_ARTIFACTS is set (SHA: not applicable, output-directory template);
- repo-relative `local/evidence/live-mode/smoke/` when unset (SHA: not applicable, output-directory template), resolved from import.meta.url,
  independent of cwd and without a hardcoded home path.

Names remain `<prefix>_sys.png` and `<prefix>_op.png`; metrics/JSON and browser flow
are unchanged. Scoped search found no other private-tmp references in measure/ after
this fix, so no other measurement scripts or lib were edited.

`node --check frontend/live-mode/measure/smoke.mjs` passed;
`git grep -n '/private/tmp' -- frontend/live-mode/measure/` returned1 with no matches;
`python scripts/check_local_artifact_refs.py` final result0 findings (warn mode);
`git diff --check` passed. The first ref-check found this handoff's older baseline
JSON locator lacked a SHA; it is now source-bound above, and both logs are preserved.
No browser/backend smoke was run (explicitly not a #573 gate), no screenshot generated,
and no service operation performed.

LOCAL `local/evidence/cx573-20261118/MANIFEST.json` SHA-256 `aa82de742c0565ac8b997fcabc7d83136ad820c05f2a24d63fdbefc1db3d3970`;
5 listed files / 365 bytes. Contains syntax, scoped
search and before/after reference-check output; can regenerate with the issue's
listed commands. Empty syntax/search logs denote successful no-output checks.

## #569: A menu, view and private-log producer

A now defaults to A4-1, then selects one of the four N6 variants. Each card renders
an idle preview; fallback swatches are decoded from the GLB variant shirt's linear
baseColorFactor and converted to sRGB. Run changes update source waypoint appearance
times. No simulation, capture, reset or infer occurs before Begin. URL short/full run
ids and actor ids bypass the menu; legacy auto=B4/A4 remains available and forces
mouse off. After Begin, the internal selection is frozen. `window.__op` contains only
a read-only P0 snapshot for the old measurement hook, with no character, variant,
run, actor or heading setter. There is no A target control or tracking endpoint.

Begin first requires a successful /reset with a 16-hex session_id. Missing-token old
backends fail closed and require reload; real integration awaits #571. Only after
this response does A set up the scene, one selected player and three distinct
script variants via the #568 crowd interface, render and capture camera pixels.
The earlier #569 run preceded the D282 C-5 fix described above.

Camera decision resolving spec §1.2 UNKNOWN: old A used a fixed world +Y view (N6
height9m/back2.2m), independent of player heading. The new orbit follows player xy
at back4.5m/eye2.1m, oriented by private view_yaw/view_pitch; yaw0 faces +Y. Body heading
uses the actual accepted movement, including wall sliding. Mouse defaults to click
pointer lock; rejection/unavailability uses left drag; Esc unlocks without changing
selection. Pitch, sensitivity and event clamps are in DEFAULT_VIEW_CONFIG. WASD uses
moveVector, preserving yaw0 speeds/diagonal/wall behavior. N6's baked wall shares its
material with the floor, so A clones only the wall material assignment in memory;
transparency/ceiling visibility are restored in finally before virtual camera capture.
No asset file changes occur.

A's downloadable JSON is live-ab.a-log.v1 with backend session_id, run/actor, config,
per-capture all-actor present/xy/GT visibility, pause totals, active private forced_pairs
and active block waits. Ended wait and forced events are snapshotted at the same capture
boundary so scoring does not combine later ended waits with an earlier active wait.
These data stay in A; header/channel use only existing protocol builders. All camera
shoot calls start synchronously before the next animation frame so a capture's actor
snapshot and virtual camera renders refer to the same poses.

Verification:

- `LIVE_AB_BROWSER=1 AMIDST_LIVE_ASSETS=<existing N6 folder> LIVE_AB_TEST_OUTPUT=<new LOCAL folder> node --test frontend/live-mode/test/ab_menu.test.mjs frontend/live-mode/test/mouse_view.test.mjs frontend/live-mode/test/crowd.test.mjs`:
  **18 passed / 1 failed / 0 skipped**. The only failure is the unchanged #568 C-5.
  Menu/view-specific tests including real headless Chrome + fake backend: 11 passed.
- Browser before Begin: zero reset/infer. After selection: reset, token, render, infer.
  Four previews and explicit WebGL-disabled swatch fallback verified; JSON download
  parsed; actor/run fixed after Escape; short URL+auto selected C and forced mouse off.
  Drag90deg leaves xy/heading unchanged; W then moves +X (~0.42m), unchanged Y.
  Request headers contain no actor/run/GT/view fields; no tracking endpoint requests;
  zero page errors. Synthetic backend has no model, parser or API calls.
- Requested hud/llm_switch/n6/protocol/schedule regression: 41 passed / 0 skipped.
  `git diff --check`: pass.

LOCAL `local/evidence/cx569-20261118/MANIFEST.json`: SHA-256 `6ce697e7731141460b2a60d5d82b96b30aa1ccb376a78f1fc37c547ee4b68685`,
34 listed files / 1,896,544 bytes. Includes test-first missing exports, intermediate and
final logs, screenshots (menu, before/after drag and WebGL-off fallback), private A
logs, downloaded JSON and fake-backend request receipts. Final screenshots/receipt are
under the manifest's verified-browser entries. Rebuild using the command above and
the same source N6 assets/scenario; timing, screenshots and logs are not byte-identical.
No real pointer-lock feel, full B/backend, detector latency, session reset across B,
identity or physical safety verified. Backend and full A/B acceptance depend on #559/#571/#572/#574.

### #569 CI follow-up: schema inventory

Initial CI at5771ef79 rejected the new A schema literal as SCHEMA_UNREGISTERED;
the two cross-platform verifier assertions consequently failed. Register A/B private
log v1 and the offline score v1 with their owning source paths and issues in
configs/architecture/schema_registry_v1.json. Registration grants no inference
or approval authority. Architecture guard now PASS (zero findings); the exact two
CI-failing pytest nodes pass. LOCAL `local/evidence/cx569-ci-20261118/MANIFEST.json`, SHA-256 `129c6bbb579af788c62d8c86c461d91922a0019a0b739bb6174699740932e132`, 3 files /40,255bytes:
pre-fix CI log, post-fix guard and focused pytest output. Rebuild the guard with
scripts/check_architecture_guard.py and the two test_verify_clean_clone nodes in
tests/q1q5/test_cross_platform_scripts.py; the historical CI log is a retained receipt.

## D308 review corrections for #569 and #570

A download records visibility only in each tick's `actors[].gt_visible`. The offline
latency measurement derives its selected actor's view list from that array and can
still read earlier flat measurement logs. The A download keeps actor visibility
private and the wire protocol is unchanged.

Scoring checks tracking state before lost ticks or estimate presence. IDLE,
ACQUIRING, SEARCHING and NEEDS_PICK contribute UNKNOWN with NOT_TRACKING. They
stay out of the visible-scored denominator, even if a delayed sample falls
inside a scoring segment. A reselect frame whose old tracker is still TRACKING
continues to score that old target until pick.

## v2.1 split wait totals and transitive phase changes (#568)

The crowd simulation records direct player pauses and script pauses separately in
`pause_player_i` and `pause_script_i`. Their sum remains `pause_total_i`. An actor
whose clock was delayed by the player, or by an already affected script actor,
remains marked for the run. Each forced script overlap records both actors'
marks and direct player pause times. The scorer lists `script` and
`player_phase_shift` counts and keeps chain events as a subset of phase shifts
when the source log records a cause.

The original eight role trials still show eleven phase shifts and zero failures
under C-5. At 78.7 s both C and B are marked, with direct player pause times of
0.0 and 19.0 s. The explicit zero-player-delay control emits `cause: "script"`.
The original seed, scenario and collision movement rules were kept for this run.
LOCAL `local/evidence/cx568-d308-20261118/MANIFEST.json`, SHA-256 `6432c321bd66b39655cfb91712ef3a3a2d70f04dd5205c355673b0f19ea9b021`, 3 files / 19,485 bytes.
Run the crowd test with `AMIDST_TEST_EVIDENCE` pointing to a new output directory
and the offline scorer's focused pytest to regenerate the results.

## D311 formal review

Each capture in the A download includes the forced overlaps and completed waits
since the previous capture, plus the current waits and both pause counters.
The first capture includes any spawn adjustment. Run totals remain available at
the top level, and the offline scorer deduplicates the copies.

The JSON counts `script` and `player_phase_shift` from the recorded cause and
taint. The reported `chain` count includes only events in `player_phase_shift`.
An event with a missing or conflicting cause is counted under `unknown_cause`.
The event rows retain actor pair, taint, direct pause seconds and simulation
time. Segment reports count loss episodes and record whether each out-of-view
sample has a `LOST` or `TARGET_OUT_OF_VIEW` declaration. The spike latency tool
uses the selected operator's visibility as a proxy. A/B target tracking metrics
come from the offline scorer.

The merge preview against main `7f8e8443` passed 67 Node tests with browser
coverage and 108 Python tests across the scorer and live-mode suites. The eight
fixed-seed trials preserve the 11 player phase shifts (2 chain) and zero pure
script violations. The A4 player T counterexample remains fixed at 78.7 s.
LOCAL `local/evidence/cx584-d311-20261118/MANIFEST.json`, SHA-256 `bc91325a0f4e474f5d58ad06ae87df5e6c0bd72f567768f1485aff890cb9458a`, 20 files / 1,350,129 bytes.

## D315 tracking endpoints (#571)

The A reset response supplies a new 16-hex session ID. B reads that session
through `GET /track/state` and uses it on each mutation. Candidate IDs are
scoped to a session, selection epoch and tick. The backend keeps seven
generations, so age six is selectable and age seven is stale. IDLE continues
to expose pixel-derived candidates. A selection that reaches NEEDS_PICK
requires a click even if the next capture has one candidate.

Q3 uses the fixed LIVE person, red and blue vocabulary. The aliases are based
on `configs/q1q5/class_alias_v1.json` and the LIVE chip labels. Parsing defaults
to RULES and the client only receives a receipt. The existing effective LLM
switch and a separate injected sentence ApiGuard are both needed for paid
parsing. Tests use fake clients. The current image advisor shortlists red
observations. Blue targets use the color-symmetric rule tracker.

Run `python -B -m pytest tests/live_mode -q` and
`python -B -m pytest tests/q1q5/test_nl_query_parse.py -q` with `PYTHONPATH=src`.
The D315 branch from `3b5a987a` passed 107 live-mode tests and 35 Q3 tests.
The endpoint tests serve synthetic camera frames on a temporary loopback port.
LOCAL `local/evidence/cx571-d315-20261118/MANIFEST.json` SHA-256 `2fadd8c8d6e91029e365d902293bde85adea40835fac5f416cdebf30719a931d`, 5 files / 19,875 bytes. The commands above regenerate the test results.

## D315 B screen and wire validation (#572)

Use the existing operator page for A and open the same LIVE service with
`?role=system` for B. Choose a chip or enter a sentence and start. When a
choice is needed, the same numbered candidate is selectable by frame box,
map point or list button. B uses only an exact capture tick and camera ID
from its five-frame cache. A candidate without that frame stays selectable
on the map and in the list. Reselect keeps the earlier tracking view and
trail until a new person is picked. Stop clears the follow view.

B polls the backend session at 1 Hz. A new session clears intent, traces,
candidates and cached frames. In-flight results from the old session and
frames older than the session observation are dropped. A stale pick fetches
a new candidate snapshot. B's download contains only the current session.

The protocol strips extras at send and rejects non-whitelisted or malformed
input at receive. ACQUIRE accepts `by: USER_PICK|AUTO_SINGLE`, including
legacy null detail. SWITCH uses `from` with `gap_ticks` or the advisor's
`by: AGENT`. TARGET_OUT_OF_VIEW, LOST and REACQUIRE have null details.
ADJUDICATE_ASK uses `kind,candidates`. ADJUDICATED uses
`choice,applied,cleared,source,latency_ms`. The timing keys are
`decode,preprocess,forward,post,detect_total,color,track,server_total`.

The A-to-B header gains only the tracking target allowed by §5.2. B records
`t_resp` at its BroadcastChannel receive boundary, which includes channel
delivery. It records `t_display` after rendering, or null if a selection
change interrupts painting. The HUD median and download use the inclusive
previous 1000 ms ending at `t_resp`. The recorded action `t_op` is the B
operation time, while the candidate tick stays the original observation tick.

Run `LIVE_AB_BROWSER=1 LIVE_AB_B_OUTPUT="$OUT" node --test frontend/live-mode/test/{ab_flow,hud,protocol}.test.mjs`
for the 55 focused cases with the synthetic HTTP and JPEG browser fixture.
Set `AMIDST_LIVE_ASSETS` to the existing N6 base and run
`node --test frontend/live-mode/test/{llm_switch,n6,schedule,crowd}.test.mjs`
for the 27 regression cases. The production-detector dual-window and
performance checks belong to #574.
LOCAL `local/evidence/cx572-d315-20261118/MANIFEST.json` SHA-256 `73ac3374e34428920886d3d4ee090bfe2f376204bb0ceddb731c80ce1bd26b12`, 7 files / 173,623 bytes. The commands above reproduce the behavior; browser clocks and image captures may vary.

## D315 P3 follow-up

A failed pointer-lock request enables drag immediately. A later click without
a drag can retry lock. Explicit drag mode has no pointer-lock request. The
test exercises both transitions with synthetic pointer events. Physical
pointer-lock feel is unverified.

A script that is still hidden advances its own clock when another person
obstructs its entrance. It becomes visible at a later pose with clearance.
Those hidden steps add neither direct nor indirect waiting time. An already
visible script that is blocked still follows §3.4. The fixed trials retain
11 player phase-shift events, two of them chain events, and zero script or
player-penetration violations.

The added fixtures confirm that taint survives release under v2.1 and a pass
exemption never skips a third actor's pair. The B4 player T trial still records
783 exempt pair samples. The review's pending Opus questions about taint
duration, pass lifetime and the resolver's error behavior are still open.

The final behavioral preview against main `b98fac2a` includes #609's
missing-capture-clock check. The scheduling-only fixture now uses the
real inference path with an injected synthetic tracking step, so both
scheduling tests exercise clock behavior independently of target selection.
The preview passed 102 LIVE Node cases, including both browser fixtures,
and 177 Python cases covering LIVE, Q3 parsing and offline scoring.
LOCAL `local/evidence/cx610-d315-final-20261118/MANIFEST.json` SHA-256 `ac1d2b2dda7b3fb4c55258dfa141c5db7b74db55da971758c2ecd032a4a28aff`, 16 files / 838,750 bytes. Regenerate by running the above tests on the merged content, with the existing N6 and owned fixtures.

## D323 bounded passes and resolver errors

The [Opus decision](https://github.com/Polalalabear/amidst/pull/610#issuecomment-6974004318)
keeps taint for the entire run. Each script crossing records
`phase_offset_s = pause_total_i − pause_total_j` after that step. The 100 s
headless trials verify the phase offset, the equivalence of taint and a
positive pause time, and the final candidate's equality to the starting pose.

The default `pass_max_s` is 3 s. Each expired or completed pass records
`pass_end` with a reason, elapsed time and exempt solver steps. Ordinary pair
checks resume on the next step. The solver count includes the step that ends
the pass, while C-2 counts pairs in the post-step snapshot. The offline scorer
reports both separation rates and summarizes pass ends by reason.

The live A operator skips the entire step on either resolver invariant error
and displays a HUD warning. The A log records each occurrence as
`crowd_error`. The offline scorer marks the report partial and preserves its
tracking scores. Headless calls still raise by default. B's frame protocol
rejects the private crowd events and phase offset.

Within a capture session, the backend rejects repeated or regressing
`/infer` ticks with 409 `NON_MONOTONIC_TICK` before detector, tracker or
scheduler calls. The response includes `next_tick` so A can continue after a
lost response. Reset starts a fresh sequence. The pointer-lock retry threshold
is 3 CSS pixels and the synthetic tests cover DPR 1 and 2.

Standard LIVE startup uses Q3 RULES. Under §4.2, paid Q3 parsing requires the
effective #563 switch and its own approved sentence guard. The advisor guard
does not enable it. The integration test uses a fake budget to check this
boundary without creating a client.

### Fixed trials

| Run | Player | C-2 excluding passes | C-2 including passes | Excluded pair samples before → after | Exempt solver steps | Pass ends |
|---|---|---:|---:|---:|---:|---|
| A4-1 | T | 100% | 99.863% | 7 → 7 | 9 | 2 separated |
| A4-1 | A | 100% | 99.825% | 10 → 10 | 12 | 2 separated |
| A4-1 | B | 100% | 99.612% | 23 → 23 | 25 | 2 separated |
| A4-1 | C | 100% | 99.532% | 27 → 27 | 29 | 2 separated |
| B4-1 | T | 85.933% | 85.454% | 783 → 30 | 31 | 1 timeout |
| B4-1 | A | 100% | 100% | 0 → 0 | 0 | 0 |
| B4-1 | B | 100% | 99.910% | 5 → 5 | 6 | 1 separated |
| B4-1 | C | 100% | 99.874% | 6 → 6 | 7 | 1 separated |

Both no-player baselines produced zero crossings. The pressure trials
produced zero player penetrations and zero pure-script crossings. There were
11 player phase-shift crossings, including two chain crossings. The fixed
A4-1 player T C→B crossing still occurs at 78.7 s.

B4-1 player T fails C-2's 99% threshold. B→A starts at tick 218
(21.8 s) and ends at tick 248 (24.8 s). Of 5,383 pair samples, 30 are
excluded and 753 of the remaining 5,353 are below 0.58 m. In the separate
stationary-player test, C→A times out at 13.1 s. At 60.1 s player T is
0.895 m from A, but C still blocks A. A's script clock stays at 4.1 s
through 62.0 s. On base `118c2035`, A advances to 4.2 s at 60.1 s.
The two B4-1 T failures remain visible in the original C-2 and C-6 tests.

Set `AMIDST_LIVE_ASSETS` using the existing N6 base and `$OUT` to an
evidence directory. Run the following from the checkout with the existing
Python and Node dependencies and Chrome installed.

```sh
python -B -m pytest tests/live_mode tests/q1q5/test_nl_query_parse.py tests/evaluation/test_live_ab_score.py -o addopts= -q -p no:cacheprovider
LIVE_AB_BROWSER=1 LIVE_AB_TEST_OUTPUT="$OUT/browser" AMIDST_TEST_EVIDENCE="$OUT" node --test frontend/live-mode/test/*.test.mjs
git diff --check
python -B scripts/check_local_artifact_refs.py --strict --files docs/operations/LIVE_AB_HANDOFF_20261118.md
```

Python passed 182 tests. Node passed 112 tests including the A and B browser
flows, with two failures and zero skips. The stationary comparison runs the
C-6 fixture's B4-1 player T sequence on base and head with 600 stationary
steps followed by 20 steps away at 0.1 s each. The evidence contains this
comparison as `b4-stationary-release.json` and the pressure counts as
`crowd-stress.json`. The commands regenerate the test receipts, with variable
wall-clock timings and browser captures.

LOCAL `local/evidence/cx-live-d323-20261118/MANIFEST.json` SHA-256 `f1f8666bcbadfdd8444b6bb4d365f7aab63d3ae8dbfa275c5bd19c19b86face4`, 11 files / 807,624 bytes.

## D327 pass correction

The [revised Opus decision](https://github.com/Polalalabear/amidst/pull/617#issuecomment-6979242886)
keeps an entered pass exempt until separation or hiding. An unentered pass
still times out after 3 s. Entered passes gain `lingering` and
`lingering_steps` at the 3 s mark. Ended passes carry these fields in
`pass_end`. Active passes are recorded in A's private `active_passes`
snapshot so unfinished crossings are included in the duration and lingering
totals. The scorer exposes these active records as well.

The D323 trace showed C→A losing its exemption at 13.1 s while the two were
still overlapping. Once the player left, A waited for C. With the correction,
the pass remains active at 13.1 s. At 60.1 s A advances from script time
4.1 s to 4.2 s in one step, with no blocker. Its distance from T is 0.7604 m.
This restores C-6 with the original scenario and original 20-step test.

In the eight fixed pressure trials C-2 excluding passes is 100% for every
trial. B4 player T has 5,383 pair samples and 783 exempt samples, 783 solver
exemptions, one lingering pass and 753 lingering steps. Separation including
passes is 85.4542%. The B→A pass starts at 21.8 s and remains active at
100 s, with duration 78.2 s. The other seven trials have zero lingering
steps and retain the D323 pair counts. All trials still have zero player
penetrations, zero pure-script violations and eleven player phase-shift
crossings, including two chain crossings. Both no-player baselines have zero
crossings. The 78.7 s A4 player T regression remains covered.

Repeated resolver errors at the same `(code, tick)` update the existing
`crowd_error.count`. A's cumulative log refreshes the count even without
a new event entry. The scorer reports distinct error entries and their total
occurrences. The strict-mode behavior and whole-step rollback remain covered.

Using the D323 commands, with `LIVE_AB_B_OUTPUT="$OUT/b"` also set to save
B's receipt, Node passes 116 tests including both browser flows with zero
skips. Python passes 182 tests. Architecture guard and diff check pass.
Physical pointer-lock feel, production inference and the 8785 gate remain
unverified in this checkpoint.

LOCAL `local/evidence/cx617-d327-20261118/MANIFEST.json` SHA-256 `a3efe8a6217592b7c7ef66731a423d58c532bf7d781978c76b4847a1ffc64321`, 15 files / 846,548 bytes. Regenerate with the focused commands above. Browser timestamps and screenshots can vary.
