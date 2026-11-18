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
