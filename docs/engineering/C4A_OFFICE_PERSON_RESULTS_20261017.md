> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# C4a Office person run — frozen results 2026-10-17

> Historical receipt at 46dd4df. Superseded for endpoint eligibility by [D17/D18 follow-up](C4A_D17_D18_20261017.md); frozen files below remain unchanged.

Model / effort: **gpt-6.1-sol / high**. First-priority update for [PR #37](https://github.com/Polalalabear/amidst/pull/37), [#15](https://github.com/Polalalabear/amidst/issues/15), CP2 [#26](https://github.com/Polalalabear/amidst/issues/26). CP1 is approved; K0 v1 is now an approved **draft**, with v1.1 questions open. CP2 is not approved; do not merge this PR.

## Frozen result and endpoint boundary

Run `blender-contact-control-office-person-20261016-v1`: declared **1.70±0.10 m**, **r 0.25 m**. The v1 estimator geometry and 8 m limit are unchanged; no C7 clipping, endpoint substitution or GT was used.

| C4a estimate | Count |
|---|---:|
| POINT | 0 |
| SEGMENT (`status: READY`) | 33 |
| UNKNOWN | 0 |
| UNKNOWN reason counts | NONE |

All 33 original source observations remain **MISSING / world_position=null**. The C4a segment is a sibling projection estimate, not a filled original position. Contact flags remain unchanged: LOW_INCIDENCE 33; CONTACT_OCCLUDED 4; AMBIGUOUS_MERGE 0; TOUCHES_IMAGE_EDGE 0. The 100-frame table also contains 67 `NO_OBSERVATION` slots; these are not fabricated C4a UNKNOWN observations and are not included in the 33-observation counts.

Segment lengths **2.161564727–2.572813405 m**, none >8 m. FRONT 4.2 s = **2.187352951 m**, FRONT 4.4 s = **2.189380408 m**, REAR 8.6 s = **2.532272652 m**. This matches the coordinator's predeclared overall 0.4–3.3 m and anchor-neighbourhood 1.5–2.9 m ranges; the observed components cover only part of the full visible-floor geometry, so the measured min/max need not attain 0.4/3.3 m. No parameter was tuned to match those expectations.

**R1 remains undecided.** The existing v1 estimator emits 33 mathematical READY segments. A separate caller guard, `k1_endpoint_eligibility`, explicitly withholds the **29 LOW_INCIDENCE-only** head estimates as `R1_LOW_INCIDENCE_ONLY_PENDING`. This is a temporary use restriction requested by the coordinator, not a contract decision or a change to contact_quality. Only four observations pass that C4a guard (FRONT1.6, REAR8.2/9.4/9.6); K1 map/clock/interval checks still have to pass.

**There is no eligible FRONT start in 3.4–4.4 s while R1 is pending.** REAR9.4/9.6 pass the C4a guard, but no start/end pair or K1 path is claimed. REAR8.2 is outside the requested outward end-substitution window, and FRONT1.6 is outside the 1 s start window; neither is selected. No D7 replacement was performed. Consumers must require both `ground_estimate.status == READY` **and** `k1_endpoint_eligibility(...).eligible`; raw READY alone does not bypass R1. The frozen file binds the per-observation eligibility alongside the unchanged geometric output.

FRONT4.4 s in this **new** run has only LOW_INCIDENCE; it does not carry AMBIGUOUS_MERGE. Old-run 4.4 s still does. New body dimensions change RGB component shape and the configured-width check; old-run flags are not copied across runs. D8 is unchanged and regression-tested: any future AMBIGUOUS_MERGE or TOUCHES_IMAGE_EDGE remains UNKNOWN and ineligible.

## Requested endpoint windows

FRONT/REAR abbreviate `CAM_1F_AUDITORIUM_FRONT` / `CAM_1F_AUDITORIUM_REAR`. reasons is the C4a reason (NONE for mathematical READY); K1 use restrictions appear separately. Head anchors are same-component bbox top centres, not renderer head coordinates. All 12 focus rows actually use the listed head anchor. YES means C4a gate only, not K1 acceptance or confirmed identity.

| timestamp_s | Camera | observation_ref | Estimate | Length m | reasons | contact_quality.reasons | Head anchor px | K1 endpoint gate |
|---:|---|---|---|---:|---|---|---|---|
| 3.4 | FRONT | `observation:8cbeff88b10eff537347482f` | SEGMENT | 2.209137 | NONE | LOW_INCIDENCE | [823.5, 69] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 3.6 | FRONT | `observation:413559766e66fe506a289273` | SEGMENT | 2.211161 | NONE | LOW_INCIDENCE | [825.0, 69] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 3.8 | FRONT | `observation:546b3d551fec650bf5618717` | SEGMENT | 2.182649 | NONE | LOW_INCIDENCE | [826.5, 70] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 4.0 | FRONT | `observation:372e6c138999e8dbc0a833b3` | SEGMENT | 2.184660 | NONE | LOW_INCIDENCE | [828.0, 70] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 4.2 | FRONT | `observation:a739dae6df76c477a3ac6b44` | SEGMENT | 2.187353 | NONE | LOW_INCIDENCE | [830.0, 70] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 4.4 | FRONT | `observation:a9373842c11b3e81fdecf2a8` | SEGMENT | 2.189380 | NONE | LOW_INCIDENCE | [831.5, 70] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 8.6 | REAR | `observation:eb179c141a066caa4d0126a2` | SEGMENT | 2.532273 | NONE | LOW_INCIDENCE | [284.5, 54] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 8.8 | REAR | `observation:e99997c4f6140fc97d3b315a` | SEGMENT | 2.531268 | NONE | LOW_INCIDENCE | [285.5, 54] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 9.0 | REAR | `observation:45a9fa074b8fe89991f31e95` | SEGMENT | 2.529769 | NONE | LOW_INCIDENCE | [287.0, 54] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 9.2 | REAR | `observation:f8e26cab0bf0ff9798cff121` | SEGMENT | 2.572813 | NONE | LOW_INCIDENCE | [288.0, 53] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 9.4 | REAR | `observation:f67af940cd7f645c19420beb` | SEGMENT | 2.571809 | NONE | LOW_INCIDENCE, CONTACT_OCCLUDED | [289.0, 53] | YES (C4a only) |
| 9.6 | REAR | `observation:3ea5a25311c06233ca1e9265` | SEGMENT | 2.570810 | NONE | LOW_INCIDENCE, CONTACT_OCCLUDED | [290.0, 53] | YES (C4a only) |

## Camera geometry, no GT

Calibration camera origins: FRONT [50.023494092,57.168342969,3.784387042] m; REAR [50.012678796,39.042655615,3.784830267] m. Floor Z = 0.49594758987426757 m. Heights above the floor are **3.288439452 m / 3.288882677 m**.

At REAR8.6, measured bbox head anchor is **[284.5,54] px**. Calibration plus the declared height interval gives horizontal distance **18.851284430–21.383557082 m**, nominal-height ray intersection **20.117420756 m**. This is a projection/height-prior distance range, **not the actual target's known position or GT distance**. Calibration alone cannot supply the unique actual person distance. The approximate length formula 0.2×D/(Hc−h) is consistent with ~2.53 m here. The prior's larger separation from camera height explains why these intervals are much shorter than the legacy run's 10.237 m.

## R2: raw coordinates are not positions

Every new estimate includes `diagnostics.raw_coordinates_use=DIAGNOSTIC_ONLY_NOT_POSITION_OR_ENDPOINT`, `raw_coordinates_usable_as_position=false` and `raw_coordinates_usable_as_endpoint=false`. UNKNOWN outputs retain raw_near_m/raw_far_m solely to explain a rejected computation; they must not be used as points, valid interval endpoints, K1 inputs or frontend positions. Authoritative machine fields for a usable estimate remain the published status/kind/point/segment plus the R1 caller guard. Diagnostic names are kept for compatibility. The old frozen legacy artifact is not rewritten; this same no-use rule applies to its historical raw fields.

## Provenance and reproduction

The branch incorporated `dcb89f475f14897e1b272da61d44a25acf8f1fb8` using merge commit **21e4c777ab705593b4b3ddf5fdf384ef320a4070**, without rebase/force-push. C3b degraded quality handling, integrity rejection and C4a matching were preserved; both sides' tests and dated logs remain. 59 focused tests passed immediately after merge; the feature/R2/report checks then passed **62 in43.71s**, with final zero-count report tests separately **2 passed in0.27s** (overlapping checks, not64 distinct tests).

The person fixture and contact config are read-only LOCAL exports from C6 commit `9937135f69da3e768c1d2714ee416dc3a780f04c`, hashes `a5bbd285d717f759d1e8a1aeaf95702d1adbcbdb0eb5ceccee60a323f6050f29` and `b84a2d328159e9c12ffe59dfef015cce65ebd2bd966551a731c7bf2df2bac3d5`. They supply a trusted validation pin; the script does not silently trust a pin from the input bundle. No preset was registered or split as part of this first-priority task.

Existing environment is this checkout's `.local-worktrees/phase1-finalization/.venv/bin/python` (Python3.12.12, NumPy2.5.3, Shapely2.1.2). No access to the `amidst-claude` checkout, new environment, dependency install or Blender process. Only safe RGB/calibration and declared config enter estimation. Dataset bytes may be hash-verified as opaque provenance by the existing loader; no GT/renderer trajectory/visibility/depth is interpreted. The original bundle/media are read-only and no path is inferred from GT.

```sh
git show 9937135f69da3e768c1d2714ee416dc3a780f04c:configs/office_demo_office_person_fixture_v1.json > /tmp/person-fixture-new.json
git show 9937135f69da3e768c1d2714ee416dc3a780f04c:configs/office_person_contact_v2.json > /tmp/person-contact-new.json
PYTHONPATH=src:scripts uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/freeze_person_hybrid_contact.py --bundle data/engineering/office_person_20261016_v1/office --fixture /tmp/person-fixture-new.json --contact-config /tmp/person-contact-new.json --hybrid-config configs/hybrid_contact_v1.json --output /tmp/person-predictions-new.json --summary /tmp/person-summary-new.json --table /tmp/person-table-new.json
```

Choose new output paths: exclusive-create refuses existing/aliased files and outputs inside the source bundle. Summary/table reference the frozen prediction SHA; dependencies/config/producer and individual output hashes are recorded. First local freeze was preserved under `/private/tmp/amidst-c4a-person-20261017/preliminary-*` before adding explicit zero state counts and nominal-distance metadata; geometry is unchanged and only final files below are delivered.

No C7 clip, K1 hypotheses, GT/RQ1 metrics, browser/live preset integration or full suite was run. Physical navigation and identity remain UNKNOWN/UNCONFIRMED. C6 benchmark rendering remains deferred (D14). Preset/fixture split is the next independent task, followed by C4b; this report does not claim those tasks completed.

## SHA-256

- `C4A_OFFICE_PERSON_PREDICTIONS_20261017.json`: `ee1dc3d2f50ce2d9e0100c62708ddf6c675c8d68cb2ebed73cccbee886c14460`
- `C4A_OFFICE_PERSON_SUMMARY_20261017.json`: `6284caf68c35735ee930c3237f95a1a446fbe02df8d8f6bdc6b8252817e2501c`
- `C4A_OFFICE_PERSON_TABLE_20261017.json`: `28227d677489b5d010fe1498241f86303bb2805130094a6d4c02dc46ea2cf982`

## Complete frame/camera table

| timestamp_s | Camera | observation_ref | Estimate | Length m | reasons | contact_quality.reasons | Head anchor px | K1 endpoint gate |
|---:|---|---|---|---:|---|---|---|---|
| 0.0 | FRONT | `observation:fedf7a4ddd340324bc9c6c0c` | SEGMENT | 2.305806 | NONE | LOW_INCIDENCE | [772.5, 64] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 0.0 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 0.2 | FRONT | `observation:0f0bbd6ace315f8392a2a991` | SEGMENT | 2.274221 | NONE | LOW_INCIDENCE | [774.5, 65] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 0.2 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 0.4 | FRONT | `observation:5d1242422b57cc4d7c7ecac8` | SEGMENT | 2.277998 | NONE | LOW_INCIDENCE | [777.5, 65] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 0.4 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 0.6 | FRONT | `observation:b5956a91a461ff1bf2469bd2` | SEGMENT | 2.281170 | NONE | LOW_INCIDENCE | [780.0, 65] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 0.6 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 0.8 | FRONT | `observation:9b5338776cd7eabf33ad83cf` | SEGMENT | 2.286291 | NONE | LOW_INCIDENCE | [784.0, 65] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 0.8 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 1.0 | FRONT | `observation:2e6426929697b700a1e7cb84` | SEGMENT | 2.256794 | NONE | LOW_INCIDENCE | [787.0, 66] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 1.0 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 1.2 | FRONT | `observation:d03904ded81db69f2e2dede6` | SEGMENT | 2.260650 | NONE | LOW_INCIDENCE | [790.0, 66] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 1.2 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 1.4 | FRONT | `observation:1f16d48b8c91a891e5a1df05` | SEGMENT | 2.264537 | NONE | LOW_INCIDENCE | [793.0, 66] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 1.4 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 1.6 | FRONT | `observation:843713ceaeafa1bca7b4bf5f` | SEGMENT | 2.268454 | NONE | LOW_INCIDENCE, CONTACT_OCCLUDED | [796.0, 66] | YES (C4a only) |
| 1.6 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 1.8 | FRONT | `observation:1e7a61829d651aeda627624d` | SEGMENT | 2.240397 | NONE | LOW_INCIDENCE | [799.5, 67] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 1.8 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 2.0 | FRONT | `observation:76c438f3419f664f53a31551` | SEGMENT | 2.244985 | NONE | LOW_INCIDENCE | [803.0, 67] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 2.0 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 2.2 | FRONT | `observation:b6581bc00b871921ee512373` | SEGMENT | 2.248949 | NONE | LOW_INCIDENCE | [806.0, 67] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 2.2 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 2.4 | FRONT | `observation:aab170b1d939d9f6672cb0b9` | SEGMENT | 2.221007 | NONE | LOW_INCIDENCE | [809.0, 68] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 2.4 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 2.6 | FRONT | `observation:996939aec772baf11a8753fb` | SEGMENT | 2.226308 | NONE | LOW_INCIDENCE | [813.0, 68] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 2.6 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 2.8 | FRONT | `observation:2bdcdd1c61a2cd2ca9b6deed` | SEGMENT | 2.230316 | NONE | LOW_INCIDENCE | [816.0, 68] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 2.8 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 3.0 | FRONT | `observation:a14f32e09592d66bc76803d7` | SEGMENT | 2.233005 | NONE | LOW_INCIDENCE | [818.0, 68] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 3.0 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 3.2 | FRONT | `observation:2cda3999d57cfc3bc4c19ab6` | SEGMENT | 2.205110 | NONE | LOW_INCIDENCE | [820.5, 69] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 3.2 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 3.4 | FRONT | `observation:8cbeff88b10eff537347482f` | SEGMENT | 2.209137 | NONE | LOW_INCIDENCE | [823.5, 69] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 3.4 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 3.6 | FRONT | `observation:413559766e66fe506a289273` | SEGMENT | 2.211161 | NONE | LOW_INCIDENCE | [825.0, 69] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 3.6 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 3.8 | FRONT | `observation:546b3d551fec650bf5618717` | SEGMENT | 2.182649 | NONE | LOW_INCIDENCE | [826.5, 70] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 3.8 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 4.0 | FRONT | `observation:372e6c138999e8dbc0a833b3` | SEGMENT | 2.184660 | NONE | LOW_INCIDENCE | [828.0, 70] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 4.0 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 4.2 | FRONT | `observation:a739dae6df76c477a3ac6b44` | SEGMENT | 2.187353 | NONE | LOW_INCIDENCE | [830.0, 70] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 4.2 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 4.4 | FRONT | `observation:a9373842c11b3e81fdecf2a8` | SEGMENT | 2.189380 | NONE | LOW_INCIDENCE | [831.5, 70] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 4.4 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 4.6 | FRONT | `observation:218abc805d72fe39c4496da0` | SEGMENT | 2.161565 | NONE | LOW_INCIDENCE | [833.0, 71] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 4.6 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 4.8 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 4.8 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 5.0 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 5.0 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 5.2 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 5.2 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 5.4 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 5.4 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 5.6 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 5.6 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 5.8 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 5.8 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 6.0 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 6.0 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 6.2 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 6.2 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 6.4 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 6.4 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 6.6 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 6.6 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 6.8 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 6.8 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 7.0 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 7.0 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 7.2 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 7.2 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 7.4 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 7.4 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 7.6 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 7.6 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 7.8 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 7.8 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 8.0 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 8.0 | REAR | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 8.2 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 8.2 | REAR | `observation:a012bc1b71556a46191bc68a` | SEGMENT | 2.492612 | NONE | LOW_INCIDENCE, CONTACT_OCCLUDED | [281.5, 55] | YES (C4a only) |
| 8.4 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 8.4 | REAR | `observation:b5caf7791776d7d3b02d249a` | SEGMENT | 2.533789 | NONE | LOW_INCIDENCE | [283.0, 54] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 8.6 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 8.6 | REAR | `observation:eb179c141a066caa4d0126a2` | SEGMENT | 2.532273 | NONE | LOW_INCIDENCE | [284.5, 54] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 8.8 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 8.8 | REAR | `observation:e99997c4f6140fc97d3b315a` | SEGMENT | 2.531268 | NONE | LOW_INCIDENCE | [285.5, 54] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 9.0 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 9.0 | REAR | `observation:45a9fa074b8fe89991f31e95` | SEGMENT | 2.529769 | NONE | LOW_INCIDENCE | [287.0, 54] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 9.2 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 9.2 | REAR | `observation:f8e26cab0bf0ff9798cff121` | SEGMENT | 2.572813 | NONE | LOW_INCIDENCE | [288.0, 53] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
| 9.4 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 9.4 | REAR | `observation:f67af940cd7f645c19420beb` | SEGMENT | 2.571809 | NONE | LOW_INCIDENCE, CONTACT_OCCLUDED | [289.0, 53] | YES (C4a only) |
| 9.6 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 9.6 | REAR | `observation:3ea5a25311c06233ca1e9265` | SEGMENT | 2.570810 | NONE | LOW_INCIDENCE, CONTACT_OCCLUDED | [290.0, 53] | YES (C4a only) |
| 9.8 | FRONT | NONE | NO_OBSERVATION | — | NO_RGB_COMPONENT | NOT_AVAILABLE | — | NO: NO_OBSERVATION |
| 9.8 | REAR | `observation:fe859083b5afa5ce1b7afc1d` | SEGMENT | 2.568825 | NONE | LOW_INCIDENCE | [292.0, 53] | NO: R1_LOW_INCIDENCE_ONLY_PENDING |
