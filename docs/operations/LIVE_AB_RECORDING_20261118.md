# LIVE A input recording and playback

Issue #596 uses the A-private schema `live-ab.case.v1`. Start A with
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

The #615 route operator supplies the same keys through its
`keys(playerPose,t_sim)` function. Its owner should feed these keys at the
fixed-step input selection in operator.mjs and call recorder.append after
crowd.step. The capture barrier owns advancement while infer is pending.
The script route, player pose, clocks and expected snapshots stay in A.
The #615 branch's renderer integration has not been combined in this
checkpoint. Its generated case format can already use this playback module.

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

The full LIVE Node run passed 119 tests including the A/B browser flows,
with zero failures and zero skips. The focused scoring suite passed 37
tests. Architecture guard and diff check passed. Physical mouse feel,
real detector replay and real provider decisions remain unverified.

LOCAL `local/evidence/cx596-d326-20261118/MANIFEST.json` SHA-256 `1db1d23e5e9112f9bfa657736c1a1d2a76925626471c6d8f1995818ed80f4175`, 52 files / 3,319,040 bytes. The commands regenerate the final receipts and browser cases, with variable wall clocks and capture timings. Probe logs retain the initial camera-wrapper hash error and its correction.
