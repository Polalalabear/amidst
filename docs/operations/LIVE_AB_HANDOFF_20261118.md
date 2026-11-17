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
and is not a runtime collision pass.

## Remaining scope and gates

#569 depends on this crowd interface but C-5 remains unaccepted; #570 and #573 are
independent ready work. #571/#572/#574 remain blocked until board prerequisites clear.
#559 remains a separate feature branch/PR with D273 follow-up; do not merge it into
this branch before the user merges it to main. No rebase, force-push, PR merge or
cleanup process/file deletion is performed by this session (current AGENTS workflow).
