# #652 B/C reappearance extension (before E3)

This follow-up uses `codex/feat-e3-reappearances`, base main
`8af69ea42cfb06a799952ddb27f97a32a721bde4`. The original nine-case corpus and
its manifest SHA-256 `853390e3dbecc8209c16c47d6e6a6cd5fc73d57bef2d1c4e11c757f8fa8b812e`
remain frozen at LOCAL `local/evidence/e3-652-20261122`.

The new LOCAL output is `local/evidence/e3-reappearances-20261122`.
Source edits happen only in the retained scratchpad clone; the demo checkout
and services remain untouched apart from its ignored LOCAL artifacts.

## Design fixed before group outputs

`configs/evaluation/e3_reappearances_design_v1.json` records the first six authored
control plans. Before index production or E3, GT QA found four repeated windows
between C4/C5, so the precommitted v2 design adds C6 and a 1 cm GT-window
deduplication rule. The v2 design is
`configs/evaluation/e3_reappearances_design_v2.json`. No group outputs informed
either design revision.
The base counts 3 reappearances / 38 primary points come from the user's
2026-11-22 instruction; no base experiment outputs are opened or reclassified.
Actual Chrome GT now yields 35 raw returns in seven new clips (625.0 s).
Five repeated three-second GT windows are retained as exclusions; **30 unique
primary/H4 return points** remain. The combined declared counts are **33 H4
returns and 68 primary points, in 16 clips**. These are input/GT counts, not
performance results.

A return point is counted once per complete target-visible → globally unseen →
target-visible transition. The target must remain present in the scene during
the gap. The blind gap must last 3–10 s, with at least 3 s visible before it and
3 s continuously visible after the return. The evaluation window is fixed to
[return, return+3 s]. B may return on the same camera; C must return on a camera
set disjoint from its last visible camera set. All qualifying raw events are kept. Primary counting deduplicates full
three-second scene windows using renderer run, presence, actor XY quantized to
1 cm and camera visibility. Ties retain the first case ID; excluded points name
that source. This does not claim identical RGB or independent trials.
Subsequent visible ticks and diagnostic anchors are not additional samples.

The producer uses scripts, static geometry and A-private GT only. It does not
open Agent answers, B logs, baseline snapshots, rankings, group scores or output
folders, and never invokes `baseline.py`, an advisor or an E3 group runner.
C's new top-k rank is UNKNOWN; no output-based ranking is used to construct
these new cases. The original two beyond-top-three cases are preserved.
Repeated events remain clustered within seven authored clips, not thirty
independent trials.

## Production order

1. Freeze the authored plans and GT event policy in Git before capture.
2. Generate `live-ab.case.v1` controls with the existing crowd resolver.
3. Capture each complete case through the unchanged LIVE A page, then replay
   twice. The private loopback server is a pixel sink with a fixed IDLE response;
   it runs no real rule tracker or Agent. All eight N6 cameras are captured.
4. Extract actual return timestamps/cameras and separate GT body-box sidecars
   from A logs. Write `GT_FREEZE.json`, formal case SHA-256 and the point catalog
   before starting RT-DETR or any E3 group. Planned Node times do not replace
   measured Chrome GT times.
5. Only then materialize shared PNG and existing-format detection_index inputs.
   RT-DETR is an input producer, not an E3 rule-arm experiment. Neither its
   detections nor any experiment outputs select or edit the frozen point list.
6. Validate clocks, complete camera grids, GT separation, source pins and
   replays; publish a new Draft PR for #652 and stop for Claude review.

The source GLBs, videos, calibration, original GT and old corpus are not
modified. GT uses the existing static-wall body-point-ray visibility proxy and
`person.mjs::projectBox` standing-body box proxy. Person-person occlusion masks,
identity and physical navigation remain unvalidated. No paid API or Blender
render is needed. F4 owns model calls and scoring, outside this production.

## Focused checks

```sh
node --test tests/evaluation/e3_reappearance_events.test.mjs
uv run --no-project --python "$E3_PYTHON" python -B -m pytest tests/evaluation/test_e3_reappearances.py tests/evaluation/test_e3_cases.py -o addopts= -q -p no:cacheprovider
git diff --check
```

Use existing `LIVE_ASSETS`, `MODEL_ROOT`, `RUNTIME_DEPS` and `E3_PYTHON`.
Rebuild into a new LOCAL directory; do not overwrite either frozen corpus.

```sh
node scripts/evaluation/e3_cases/prepare_reappearances.mjs "$NEW_ROOT" "$LIVE_ASSETS"
node scripts/evaluation/e3_cases/record.mjs "$NEW_ROOT" "$LIVE_ASSETS" E3-B3 E3-B4 E3-B5 E3-C3 E3-C4 E3-C5 E3-C6
node scripts/evaluation/e3_cases/freeze_reappearances.mjs "$NEW_ROOT" "$LIVE_ASSETS"
# Commit the case/GT point pins before the following index-production step.
PYTHONPATH="src:$RUNTIME_DEPS" uv run --no-project --python "$E3_PYTHON" python -B scripts/evaluation/e3_cases/index.py --root "$NEW_ROOT" --models "$MODEL_ROOT" --cases E3-B3 E3-B4 E3-B5 E3-C3 E3-C4 E3-C5 E3-C6
```

## GT freeze before index production

LOCAL `local/evidence/e3-reappearances-20261122/GT_FREEZE.json` SHA-256:
`850a232d4aca832b87262ee32ea8497ae0e6be82c9ac8ea2d5dba6177236fe49`.
The identical committed point catalog is
`configs/evaluation/e3_reappearances_v1.json`. Every formal case and separate
GT sidecar has its own SHA in that catalog. The release gate requires the LOCAL
freeze to match that committed definition byte-for-byte; neither index
production nor later group results can redefine the point list.

The earlier six-clip candidate freeze (raw returns, before anti-repeat QA) is
preserved as `GT_FREEZE_CANDIDATE_V1.json`, SHA-256
`2f346b54e8d7bd5153c8faa5756287442865c65aef8871def13727e8ca55278b`.
The six already recorded cases and GT sidecars retain their original bytes;
only point eligibility is revised before experiments, and C6 is an added case.
There was no RT-DETR index or E3 group output when these definitions were frozen.

| Case | Raw returns | Unique primary/H4 returns |
| --- | ---: | ---: |
| E3-B3 | 5 | 5 |
| E3-B4 | 5 | 5 |
| E3-B5 | 5 | 5 |
| E3-C3 | 5 | 5 |
| E3-C4 | 5 | 5 |
| E3-C5 | 5 | 1 |
| E3-C6 | 5 | 4 |

The original corpus is now at canonical LOCAL
`local/evidence/e3-652-20261122`; it is not in the scratch clone. Both base and
extension input registries will be composed with explicit root references.
The base evaluation catalog and its old baseline snapshots are not opened by
this producer; base counts are the user's declared 3/38, with its manifest pin
checked without parsing group outputs.
