# Live relock R1 replay (#588)

This Draft contains the pure relock state machine, the optional velocity-based shortlist, and
offline replay and scoring. The runtime continues to use its existing tracker configuration.
R1 fails R-6 on the fixed B4 recording. The prediction sweep leaves prediction disabled.

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

## Fixed observation results

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
