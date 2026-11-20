# LIVE A input recording and playback

Issues #596 and #654 (PR #617) use the A-private schema `live-ab.case.v1`. Start A with
`?record=1`, choose the scene and character, then move with the usual
controls. End recording and download the case. Save the case in a LOCAL
evidence directory, using its case ID and the suffix `.case.json`.

Open A with `?auto=recorded` and select the case file. It is read in the
A page and has no server download route. Each new playback resets the
tracking session. The file contains run_id, actor_id, seed, crowd and capture
configuration, source bindings, inputs, optional expected snapshots and
public target-selection actions.

Every input is `{step, dt:0.05, keys:{w,a,s,d,shift,view_yaw}}`.
Playback feeds these inputs through the original crowd resolver. Expected
snapshots are only compared after each step. They include the actual
positions, headings, script clocks, pause times and crowd events. The first
divergence stops playback. Generated cases may omit expected snapshots.
The current crowd step has no random source. Seed is retained as provenance.

Bindings are SHA-256 hashes of JSON.stringify output. The scene binding
covers the selected scenario run and wall segments. The camera binding
covers each camera's world and projection matrices. The recording retains
the capture dimensions, quality, model, scene, camera IDs and crowd settings.
Changing a binding rejects the case before its first step.

Capture tick k occurs at simulation time k/fps, including tick zero.
The fixed step is 0.05 s and fps must divide 20 Hz. The simulation waits
at the boundary until capture and inference finish. Every configured camera
is captured, with all animation mixers advanced by fixed simulation steps.
The backend's adaptive selection remains a decision made on these frames.
For a comparison that holds scheduling fixed, launch the backend with its
existing `--schedule all` option.

The inference header uses k*1000/fps as its capture clock. The A and system
logs use the actual wall capture time for joining and latency, while A also
records `t_infer_capture_ms`. Tracking receives only the inference clock
and camera images. The renderer's scenario and expected positions stay in A.

To include human target-selection operations, download B's log from the
same session and attach it using A's file input. Each operation is assigned
to the first capture following its wall-clock operation time. A resolved
color replaces the original sentence. Actions after the final captured
frame require another capture before export.

Actions have `{tick, action, color?, candidate?:{cam?,est_xy}}`.
Playback applies them before capture using the new session. A pick resolves
exactly one current candidate within 1 mm of the recorded projection, with
an optional camera constraint. An absent or ambiguous candidate stops
playback. This matches an observation and retains the usual unconfirmed
identity boundary.

The replay system download has the scorer's B-log shape, with
`capture_source: A_REPLAY_RESPONSE`. It records the sanitized backend
response and executed public actions. Its display time is null. B's own
download remains the source for display and HUD latency measurements.
Neither output contains the case, expected snapshots or player configuration.

Use the existing #563 switch for the decision mode. The default is advisor
off. Fake providers or the synthetic HTTP fixture exercise the path without
model calls. Paid model runs require ApiGuard, a dry-run and a separately
approved amount for that run.

## Script operator integration

The merged #615 route operator supplies keys through
`keys(playerPose,t_sim)`. With ?script=<case_id>&record=1, the recorder's
capture barrier calls this function at each 0.05 s step and appends the
resulting crowd snapshot. Only one stepper advances the recording. Without
recording, the existing route stepper remains available. Nine hardset
routes each have a 400-step fixture replayed twice, and the browser smoke
records and replays H1-1 through this entry point.

The existing ?auto=A4/B4 loop semantics remain part of the case. If a second
loop resets the scripted player to its start, recording retains that input
and state transition. A case ends when its finite input sequence ends.
Any answer-table exclusion around that reset is applied offline to both
decision modes using the same window.

The existing public advisor receipts retain their original fields.
Missing pool coordinates, rule choice and cost remain UNKNOWN. Full
decision receipts for #597 require the advisor contract's additional fields.

## Focused verification

With existing Node dependencies, Chrome and N6 assets configured through
AMIDST_LIVE_ASSETS, run the following. Set OUT to an evidence directory.

```sh
LIVE_AB_BROWSER=1 LIVE_AB_TEST_OUTPUT="$OUT/full-a" LIVE_AB_B_OUTPUT="$OUT/full-b" AMIDST_TEST_EVIDENCE="$OUT" node --test frontend/live-mode/test/*.test.mjs
python -B -m pytest tests/evaluation/test_live_ab_score.py -o addopts= -q -p no:cacheprovider
git diff --check
python -B scripts/check_architecture_guard.py --repo . --base origin/main
```

The unit fixtures record 1,600 fixed steps in each A4/B4 scene and check
two complete replays against all expected states. Other fixtures cover
generated inputs, malformed clocks, ambiguous picks and private data
isolation. The browser fixture records a moving player, uploads the case
twice, checks both sequences and runs live_ab_score.py on both downloads.
Its synthetic estimator yields MISPICK and a PARTIAL score. It exercises
the input and report pipeline without measuring detector accuracy.

At the historical D326 checkpoint, the full LIVE Node run passed 119 tests including the A/B browser flows,
with zero failures and zero skips. The focused scoring suite passed 37
tests. Architecture guard and diff check passed. Physical mouse feel,
real detector replay and real provider decisions remain unverified.

LOCAL `local/evidence/cx596-d326-20261118/MANIFEST.json` SHA-256 `1db1d23e5e9112f9bfa657736c1a1d2a76925626471c6d8f1995818ed80f4175`, 52 files / 3,319,040 bytes. The commands regenerate the final receipts and browser cases, with variable wall clocks and capture timings. Probe logs retain the initial camera-wrapper hash error and its correction.

## 2026-11-20 integration and E3 scope

Merge commit `f51c5362` includes main `8290f190` and its workbench-v2
LIVE styling. The browser fixtures now serve CSS with text/css and assert
that the real grid style loaded. They retain mouse, frame/map/list picks,
session reset, download and recording/playback assertions. The final LIVE
Node run passes 133 tests, zero failures/skips; the LIVE/Q3/scorer Python
set passes 185. The headless launcher/failure-cleanup set passes 3 tests.
Commands are the focused verification commands above plus
`AMIDST_BROWSER_TEST=1 AMIDST_BROWSER_EVIDENCE="$OUT/browser" node --test
tests/browser/browser-options.test.mjs`. No render or model call is run.

The current merged hardset has 15 generated routes and 3 baselines.
All 15 route input fixtures run 400 steps (20 s) and replay twice; this is
prefix coverage, not completion of every hard case. A4/B4 each record
1,600 steps (80 s) and replay twice against every expected pose and clock.
The browser records a short H1-1 case and checks two replays' simulation
ticks, poses and logical capture indices for equality. Thus the same
finite case file can reproduce its simulation inputs deterministically.
Wall-clock timings, JPEG bytes, real detector/Agent outputs and paid-provider
latency are not asserted deterministic. E3 must reuse the same source-bound
case, and separately measure these outputs in both modes.

The runtime calibration registers 8 cameras, including CAM_ENTRY. Adaptive
scheduling can submit fewer than 8 on a tick; this is not an eight-camera
E3 result. H2-1/2/3 are 3 similar-color crossing cases. H5-1/2 add 2 cases
with two red distractors; H5-3 is a single-distractor control. That gives
5 designed multi-person similar-color cases plus 1 control, not six
two-distractor cases. No new complete E3 recordings or paired rule/Agent
results are delivered by this integration. Existing Claude smoke receipts
in LIVE_HARDSET_V1.md are historical and not deterministic case recordings.

LOCAL `local/evidence/cx617-main-20261120/MANIFEST.json` SHA-256 `dde8dddd7a4505e7676ef1555a3b5184cd2bdf278e9c075551bbf5c9ea042a9f`, 30 files / 1,237,143 bytes. Includes initial fixture failures, final passing tests, A/B screenshots, case and two replays, merge pin audit and E3 readiness metadata. Rebuild with the focused commands above; wall-clock fields vary. Full E3 and 8785 gate remain unverified.
