# CX-L5 staged handoff — 2026-11-18

Feature branch `codex/feat-live-ab`, base main `0606b164`; contract PR #567 v2
`6e3a35f0`, decisions D279. One Draft PR for all #566 sub-issues.

## #568: blocked on C-5, not accepted

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
B4=1/0/0/0. Do not relabel them, change seed or weaken the test. Counterexample:
A4 selectedT, tick787 (78.7s), C waits3s for B at0.67738m; B is not currently blocked
by player (chain=false), but its clock is delayed21.9s, so the original synchronous
route separation does not guarantee separation after individual pauses. Original
scenario remains unchanged. C-5 requires a contract decision; this stage is not complete.

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
read-only script-distance audit is `local/evidence/cx566-20261117/scripts-baseline.json`
SHA-256 `5b2f80eeaa044ed6804277e1aeefb62508baa4aaa574eb2bea10d4047132bbf4`, 1 file / 2,455 bytes;
it is not a runtime collision pass. It can be rebuilt from the same scenario and
scriptedPose at dt=.1s.

## Remaining scope and gates

#569 depends on this crowd interface but C-5 remains unaccepted; #570 and #573 are
independent ready work. #571/#572/#574 remain blocked until board prerequisites clear.
#559 remains a separate feature branch/PR with D273 follow-up; do not merge it into
this branch before the user merges it to main. No rebase, force-push, PR merge or
cleanup process/file deletion is performed by this session (current AGENTS workflow).


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

- `$AMIDST_ARTIFACTS/evidence/live-mode/smoke/` when AMIDST_ARTIFACTS is set;
- repo-relative `local/evidence/live-mode/smoke/` when unset, resolved from import.meta.url,
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

LOCAL `local/evidence/cx573-20261118/MANIFEST.json` SHA-256 `079366027f2d4df6d6a16799f2a664f2ff0a2ed9936f445210e0cd920ac3f216`;
4 listed files / 322 bytes. Contains syntax, scoped
search and before/after reference-check output; can regenerate with the issue's
listed commands. Empty syntax/search logs denote successful no-output checks.
