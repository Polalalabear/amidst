# Live relock R1 replay (#588)

This PR contains the pure relock state machine, the optional velocity-based shortlist,
and offline replay and scoring. The D331 merge and replay pass R-6 and the user-approved
R-5a. Runtime relock and prediction remain disabled by default. Earlier checkpoints below
retain their historical measurements.

## Inputs

- The fixed observation payloads are the two files under
  `local/evidence/cx552-c-20261117/redetected`, receipt SHA-256 `c98407004c5acfb021f0a0c108990603ced2efadd07bf30b0017b253f4212936`.
  The 37 listed files include derived replay and receipt files. Counting those copies as new
  episodes would duplicate observations.
- D273's four additional recordings are in
  `local/evidence/cx552-d-20261118/fresh/latency`, receipt SHA-256 `803e6e09ade8ab128f9e7387e42cf568127858832335892389aff7348f507090`.
  Their ENTRY results are reported separately. An adaptive recording only contains
  detections from captured cameras, so it does not establish an all-camera counterfactual.
- The prediction sweep uses 18 `sol2` recordings, 20 `gate` recordings and the two fixed
  observations. The source, calibration and configuration hashes are in the output receipts.

## D308 fixed observation results

| Scene | Visible scored ticks | Baseline on-target / lost | Relock on-target / lost | R-6 |
| --- | ---: | --- | --- | --- |
| A4 | 95 | 67/95 (70.53%) / 4/95 (4.21%) | 67/95 (70.53%) / 4/95 (4.21%) | Pass |
| B4 | 60 | 58/60 (96.67%) / 1/60 (1.67%) | 23/60 (38.33%) / 36/60 (60.00%) | Fail |

B4 begins waiting at capture index 28. At index 37 (19.011 s since capture start),
the widened radius admits one projection 10.448 m from the last estimate. The
appearance cutoff is unknown, so the tracker presents the candidate and enters
`NEEDS_CONFIRM`. The old tracker instead remains governed by the 4 m gate.
At index 46 (23.512 s), the closest group is 1.743 m away, inside that gate.
The old tracker reacquires. The new tracker is already waiting for appearance
or manual confirmation and stays there. Both returning earlier inside the
gate and retaining the waiting state deserve an explicit contract decision
before enabling R1 in the demo.

There are seven visible failed episodes after a correct track (A4 five, B4 two).
At 1 s, short-gate recovery contributes no events. At each of 2, 3, 4, 6, 8 and 10 s
there are two correct and zero wrong short-gate recoveries, both in A4. The
contract's sample minimum leaves `t_short_s` UNKNOWN for both scenes.
R-5 observed zero incorrect automatic recoveries on these two fixed inputs.

Projected speed has N=150, p50 0.6615 m/s, p95 2.4494 m/s, maximum 5.7310 m/s.
On the same pairs, the evaluation-only scripted positions give p50 0.8678 m/s,
p95 1.4253 m/s, maximum 1.4334 m/s. The projection p95 is 71.8% higher. It
includes frame-to-frame changes in selected boxes and camera projections.
The samples do not isolate those jumps from true movement in the observation
stream. The replay applies the projected p95 as specified.

Appearance has two usable return episodes with a complete reference, two
target samples and three comparator samples. Red-ratio normalized gap is
−0.64564, blue-ratio gap is 0, and joint gap is −0.64564. None separates the
recorded samples. `tau_app` and `margin_app` remain UNKNOWN and appearance
cannot automatically select a target.

## D273 ENTRY supplement

| Recording | Capture index | Previous estimate to target-like projection | State | Correct candidate delay | Automatic relock delay |
| --- | ---: | ---: | --- | ---: | --- |
| A4 all | 52 | 4.7596 m | NEEDS_CONFIRM | 0 ms | null |
| A4 adaptive capture | 62 | 4.6824 m | NEEDS_CONFIRM | 0 ms | null |

The correct candidate is present on the first return capture in both recordings.
All eight cameras were observed at those indices. This evaluates the offline
R1 candidate presentation; R2 owns the server and adaptive scheduling gate.

## Shortlist prediction

| Horizon | Questions | Pool misses | Miss rate | Wrong ticks / 2,286 visible | Wrong automatic relocks |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 s | 147 | 2 | 1.3605% | 137 | 5 |
| 1, 2 or 3 s (each) | 144 | 2 | 1.3889% | 121 | 4 |

The measured minimum of three baseline misses was not met. None of the
horizons reduced misses or met the zero-wrong-relock rule. The shortlist
prediction remains disabled. Case references for #591 are both on CAM_WIDE,
recording `gate__b4_8cam_g3_r2` tick 30 and `gate__b4_8cam_g4_r1` tick 27.
The legacy recordings have no A/B session token, so the receipt uses their
stable source labels.

The existing default lost branch can ask about all observed people. With
prediction on it preserves that eligibility, ranks the camera's members
before truncating, and numbers the selected boxes left to right as before.
The replay's fixture returns choice 0 while measuring tracking and captures
the proposed question pools. The #544 one-metre oracle scores those pools
after replay, with no feedback into tracking. The reported wrong ticks
therefore measure the observation-only policy with no applied model answer.
Provider calls and spend are zero.

## Reproduction

Use the existing safe camera catalog, with `EVIDENCE` set to the LOCAL
evidence root and `OUT` set to a new output directory. Use the checkout's Python
with `PYTHONPATH=src`.

```bash
python -B scripts/live_mode/replay_relock.py \
  --src "C=$EVIDENCE/cx552-c-20261117/redetected" \
  --entry-src "D273=$EVIDENCE/cx552-d-20261118/fresh/latency" \
  --entry-main-rows "$EVIDENCE/cx552-d-20261118/fresh/latency/t1_rows.json" \
  --cameras "$CAMERAS" --out "$OUT/relock" --sweep-t-short 1,2,3,4,6,8,10
python -B scripts/live_mode/replay_advisor.py \
  --in "$EVIDENCE/live-mode-advisor-20261116/sol2" \
  --additional-in "gate=$EVIDENCE/live-mode-tracker-20261116/gate" \
  --additional-in "C=$EVIDENCE/cx552-c-20261117/redetected" \
  --out "$OUT/prediction" --mode review --gate-m 4 --oracle-m 1.0 \
  --cameras "$CAMERAS" --relock-receipt "$OUT/relock/relock.json" --predict-horizon 0,1,2,3
python -B -m pytest tests/live_mode/test_relock.py tests/live_mode/test_relock_replay.py -q
python -B -m pytest tests/live_mode -q
git diff --check
```

`relock.json`, `prediction.json` and `pool-misses.json` each matched byte-for-byte
on two runs. The focused tests are 14/14, the live-mode suite 88/88, and the
architecture guard passes. The R1 tracker’s `confirm` method handles a current
pure-policy candidate. Session-scoped candidate IDs and the wire protocol are R2 work.

LOCAL `local/evidence/cx588-d308-20261118/MANIFEST.json` SHA-256 `814ebe0448a6f54e39934ee92959ec722ed7b23e5962ffce3f01406a117e0447`, 220 files / 29,843,802 bytes.
LOCAL `local/evidence/cx588-d308-20261118/prediction/pool-misses.json` SHA-256 `e0f8ad2d7769b60eb0504622dc961a8f4fed49d315d43405811023b379965b7b`, two question receipts.

## D322 conditional short-gate exit

This candidate implements the #611 contract and the Opus decision on #588.
A unique in-gate group can leave NEEDS_CONFIRM through short_gate when the
existing short-limit policy permits it. A same-tick confirmation wins. The
group outside the gate stays eligible for appearance or explicit confirmation.
The previous checkpoint above records behavior before this change.

R-6 fixed observations pass. A4 has 67/95 on target and 4/95 lost; B4 has
58/60 on target and 1/60 lost. At fixed B4 capture 46, short_gate selects T
at 1.7430 m with 9.5005 s unseen. R-5 fails. The six replays have 6 correct,
5 wrong and 0 unknown automatic recoveries, all short_gate. Nine are exits
from NEEDS_CONFIRM, with 4 correct and 5 wrong. The other two are the
existing fixed A4 recoveries.

| D273 source | Wrong capture | Unseen (s) | Gate distance (m) | Offline match |
| --- | ---: | ---: | ---: | --- |
| all A4 | 12 | 1.9999 | 3.0944 | A |
| all A4 | 56 | 24.7996 | 0.4940 | A |
| adaptive A4 | 13 | 2.4003 | 2.9656 | A |
| adaptive A4 | 66 | 25.0005 | 0.2781 | A |
| all B4 | 31 | 1.7995 | 2.3292 | B |

The correct ENTRY candidate is still presented after 0 ms in both A4 recordings
at captures 52 and 62. Correct automatic relock delay is null for both.
At D322's stop condition, the prediction sweep and the second deterministic
replay were left pending. The live wire was not exercised. No runtime default
or threshold was changed.

LOCAL `local/evidence/cx588-d322-20261118/MANIFEST.json` SHA-256 `de9f17069dc2dcfa89ac8c9d25eab5f1b691d8045387baebbc2f9a3ab97f1e50`, 45 files / 4,775,119 bytes. The replay command above regenerates the trace and scores; `gate-audit.json` records the six-run event join and waiting durations.

## D326 R-5a acceptance

The user approved the revised R-5a in D326. The runtime policy remains
`bc86630f`. This checkpoint supersedes the earlier Draft acceptance status.
The replay now joins every automatic recovery to main's score at the same
source capture index and capture clock. Fixed C uses the baseline replay.
D273 uses the original main capture's scored rows, whose SHA-256 is recorded
in `relock.json`. Both the scored action and the last matched capture before
loss are retained. Main can match through SWITCH or ordinary continuation,
so its action need not have a REACQUIRE event.

R-6 passes with A4 67/95 correct and 4/95 lost, B4 58/60 correct and 1/60 lost.
The eleven automatic recoveries have six correct and five wrong matches.
Main matches the same actor at all eleven captures. R-5a adds zero wrong
matches, appearance adds zero wrong matches, and fixed C has zero wrong
recoveries. All five wrong recoveries were already following the wrong
person before the loss. The detailed capture rows and original main event
names are in `relock.json.r5a.events`.

ENTRY presentation remains 0 ms at all-A4 capture 52 and adaptive-A4 capture
62. Correct automatic recovery delay is null in each.

The 40-input prediction sweep reports 3/114 pool misses and 30 wrong
recoveries with horizon zero. Each horizon of 1, 2 and 3 s reports 1/128
pool misses and 26 wrong recoveries. The earlier D308 values were 2/147
and 5 wrong recoveries, or 2/144 and 4 wrong recoveries with prediction.
The sweep uses the same inputs and commands, with the D326 relock receipt.
The new short-gate exit also operates from NEEDS_CONFIRM, changing subsequent
tracking, references and question times. Wrong recoveries remain above zero,
so R-13 leaves prediction disabled. The fixture applies no paid model answer
and records zero provider calls.

Two runs produced identical bytes for `relock.json`, `prediction.json`
and `pool-misses.json`. The full branch LIVE suite passes 96 tests.
Ruff on both changed Python files, architecture guard and diff check pass.
R2 session and HTTP integration remains the scope of #589.

LOCAL `local/evidence/cx588-d326-20261118/MANIFEST.json` SHA-256 `e938d246a8839291d97a9fc9b18bf2691b8e5d7dc6a290719384c8556fe4a924`, 471 files / 59,799,138 bytes. The reproduction commands above regenerate the reports. The matching runs are run2 and run3, and their file hashes are in determinism.json.

## D331 merge and verification

Merge commit 460d24dc has parents 533b4e99 and main 7393bf62. Tracker
retains target_color, the projected=True path, explicit seed and session
selection behavior from main. The optional relock policy uses the selected
color. A seed creates fresh reference and velocity memory, clears pending
confirmation options and resets the confirmation tick latch. The shared
result method serves seed, normal updates and pure-policy confirmation.
Synthetic regressions cover blue relock, projection reuse and fresh seed.
HTTP relock candidate binding remains R2 work.

The same six observation sources pass R-6 after the merge. A4 has 67/95
correct and 4/95 lost. B4 has 58/60 correct and 1/60 lost. Fixed C acceptance
checks that tracking preserves the baseline. It demonstrates no regression
on these captures. Its two A4 and one B4 relock events do not establish an
improvement over baseline.

R-5a is unchanged after merge. The six correct and five wrong automatic
recoveries all match the baseline actor at the same capture. New wrong
recoveries, fixed C wrong recoveries and appearance wrong recoveries are
zero. All five wrong recoveries were following the wrong person before
loss. The D273 comparison uses its historical main runtime rows with
SHA-256 a079664ed041486c1bdeaf12e8824d0466f751ac1f5814e51d356952a705e6a8.
Fixed C uses the merged code's baseline replay. The historical comparison
is explicitly retained under D326's approved acceptance rule.

The D326 run1 folder is an intermediate comparison implementation which
required a main REACQUIRE event. It counted SWITCH and continuing matches
as different behavior and reported three new errors. Run2 and run3 use
the final same-capture, same-actor comparison. They are the two deterministic
runs at that checkpoint. D331 uses the final comparison for both run1 and
run2.

The appearance scale 0.2452331002331002 is GT-derived in offline calibration
and used only in the replay configuration. Runtime appearance scales
remain 1.0 and the appearance thresholds remain UNKNOWN. The projected
speed and GT speed comparison also remains offline.

The post-merge prediction sweep remains at 3/114 misses and 30 wrong
recoveries for horizon zero, and 1/128 with 26 wrong recoveries for each
1/2/3 s horizon. These equal D326 and retain its documented difference
from D308. Prediction stays disabled. ENTRY remains 0 ms at all-A4 52
and adaptive-A4 62, with null correct automatic recovery delay.

Both runs produce identical relock.json, prediction.json and pool-misses.json
bytes. The full LIVE suite passes 132 tests. Three browser-default and
failure-cleanup tests pass in headless mode. The branch also carries the
shared headless launcher and hardset two-page fix. Ruff passes for the new
policy/replay tests and replay script. Tracker's existing layout is checked
with F/I/UP. Architecture guard and diff check pass.

LOCAL `local/evidence/cx588-d331-20261118/MANIFEST.json` SHA-256 `b8a9e5dd46ef583cef44ffb78a4728412a96240e5d93c90cd0d93990a77a65ad`, 433 files / 55,723,922 bytes. The documented commands regenerate the two replay sets. Model / effort for this checkpoint is gpt-6.1-sol / UNKNOWN.
