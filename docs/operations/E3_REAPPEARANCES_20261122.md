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
render is needed. F4 owns experimental Agent/rule runs and scoring, outside this production.

## Focused checks

```sh
node --test tests/evaluation/e3_reappearance_events.test.mjs
uv run --no-project --python "$E3_PYTHON" python -B -m pytest tests/evaluation/test_e3_reappearances.py -o addopts= -q -p no:cacheprovider
git diff --check
```

Set `AMIDST_REPO` to the pinned checkout and run source commands from the
scratch clone. The delivered inputs use these LOCAL dependencies:

```sh
EVIDENCE_ROOT="${AMIDST_ARTIFACTS:-$AMIDST_REPO/local/evidence}"
BASE_ROOT="$EVIDENCE_ROOT/e3-652-20261122"
LIVE_ASSETS="$AMIDST_REPO/local/data/live-assets-20261115"
MODEL_ROOT="$AMIDST_REPO/local/data/demo-owned-v1/models/rtdetr"
RUNTIME_DEPS="$AMIDST_REPO/local/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps"
E3_PYTHON="$AMIDST_REPO/.venv/bin/python"
```

For regeneration, choose a **new** LOCAL `NEW_ROOT`; do not overwrite either
frozen corpus. The following are the production stages. Before indexing a new
capture, commit its new GT definition under a new version and bind the release
gate to that version. The current gate intentionally accepts only this
release's committed freeze, and refuses to overwrite an existing MANIFEST.

```sh
node scripts/evaluation/e3_cases/prepare_reappearances.mjs "$NEW_ROOT" "$LIVE_ASSETS"
node scripts/evaluation/e3_cases/record.mjs "$NEW_ROOT" "$LIVE_ASSETS" E3-B3 E3-B4 E3-B5 E3-C3 E3-C4 E3-C5 E3-C6
node scripts/evaluation/e3_cases/freeze_reappearances.mjs "$NEW_ROOT" "$LIVE_ASSETS"
# Commit the case/GT point pins before the following index-production step.
PYTHONPATH="src:$RUNTIME_DEPS" uv run --no-project --python "$E3_PYTHON" python -B scripts/evaluation/e3_cases/index.py --root "$NEW_ROOT" --models "$MODEL_ROOT" --cases E3-B3 E3-B4 E3-B5 E3-C3 E3-C4 E3-C5 E3-C6
PYTHONPATH="src:$RUNTIME_DEPS" uv run --no-project --python "$E3_PYTHON" python -B scripts/evaluation/e3_cases/release_reappearances.py --root "$NEW_ROOT" --base-root "$BASE_ROOT" --assets "$LIVE_ASSETS"
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

| Case | Duration s | Indexed PNGs | Raw returns | Unique primary/H4 returns | Blind gaps s |
| --- | ---: | ---: | ---: | ---: | ---: |
| E3-B3 | 86.6 | 3,464 | 5 | 5 | 4.8–6.8 |
| E3-B4 | 99.4 | 3,976 | 5 | 5 | 5.0–6.8 |
| E3-B5 | 93.2 | 3,728 | 5 | 5 | 4.8–7.0 |
| E3-C3 | 81.8 | 3,272 | 5 | 5 | 4.0–5.2 |
| E3-C4 | 90.6 | 3,624 | 5 | 5 | 4.0–5.2 |
| E3-C5 | 90.6 | 3,624 | 5 | 1 | 4.0 |
| E3-C6 | 82.8 | 3,312 | 5 | 4 | 4.0–5.2 |

The original corpus is now at canonical LOCAL
`local/evidence/e3-652-20261122`; it is not in the scratch clone. Both base and
extension input registries will be composed with explicit root references.
The base evaluation catalog and its old baseline snapshots are not opened by
this producer; base counts are the user's declared 3/38, with its manifest pin
checked without parsing group outputs. The clean base runtime registry matches
its committed `E3_INPUTS_20261122.json` byte-for-byte (SHA-256
`4810734697a5b0cee292b3b7e4ca7e2592e5f2f26cc0b5c707eb7285a07e9cb8`);
the release gate also pins that registry.

## F4 input contract

The clean combined runtime registry is `COMBINED_INPUTS.json`: resolve each
run's `root_ref` through its `roots` mapping, then use its hash-bound
`rgb_index_path`, `index_path` and `records_path`. All arms consume the same
320×180 PNGs and native `q-demo.detection-index.v1` index at 5 Hz. The PNGs
preserve the exact decoded pixels of the recorded camera JPEGs. The last
endpoint guard capture is excluded from inference, giving 25,000 indexed
camera frames across the seven new cases.

Only the scoring process reads `GT_FREEZE.json`, the committed point catalog
and the separate `gt-boxes/*.a-log.json` files. Do not mount `.case.json`, A
logs, control plans, point catalogs or GT sidecars into runtime/Agent inputs.
Each scoring window is listed explicitly in microseconds; use 200,000 µs ticks
and the 320×180 image size for the F1 LIVE adapter. Diagnostic/excluded returns
are not additional primary points. The five duplicate exclusions retain
`duplicate_of` references for audit.

Release validation uses `JsonRunStore.load_detection_index`, verifies the
complete eight-camera/time grid and file SHA-256 pins, and compares all three
logical capture runs per case (21 complete runs). It does not execute or score
an Agent/rule arm. This delivery establishes usable input/GT counts; H4
performance and statistical power remain untested.

`GT_FREEZE.json` and `configs/evaluation/e3_reappearances_v1.json` must remain
byte-identical. A fresh capture has a new provenance/timestamp and therefore
requires its own committed GT definition before indexing; do not replace the
current frozen definition to make a rebuild pass. Exact F4 reuse requires the
preserved artifacts, because JPEG/GPU/RT-DETR output bytes are not promised to
repeat. The v2 pre-capture forecast was 31 unique points; measured Chrome GT
produced 30 after deduplication, and the delivered count uses that measurement.

The design was committed in `de32fae6`, the prospective anti-repeat/C6 revision
in `7d54c91e`, and the final case/GT SHA pins in `08d70d78`, before RT-DETR
production. `source_receipt.json` pins unchanged LIVE capture files. This PR
does not change `operator.mjs` or the minimap, so F2's file ownership is preserved.

## Final delivery (2026-11-22)

LOCAL `local/evidence/e3-reappearances-20261122/MANIFEST.json` lists
**50,176 delivered files / 874,503,221 bytes**, excluding the manifest itself,
caches and intermediate PR text. SHA-256:
`5eac93379533485e754f29ebf54f409e7992bd551db822ab6aeea2022aa78517`.
Every listed file was rehashed after release: **50,176 checked, zero mismatches**.
All seven native JsonRunStore checks pass, covering 25,000 PNG/index frames,
complete eight-camera grids, separate GT pins and 21 matching logical browser
runs. All 30 inclusive three-second scoring windows finish before their indexed
interval endpoint. Focused checks: Node 12 passed, Python 3 passed;
`git diff --check` passed. No Agent/rule experiment or H4 scoring was run.

The committed clean registry is
`docs/operations/E3_REAPPEARANCES_INPUTS_20261122.json`, byte-identical to LOCAL
`COMBINED_INPUTS.json`. It contains 16 runtime runs (9 base + 7 extension), with
explicit LOCAL root references and individual pixel/index SHA pins. Use it for
F4 inputs; use the frozen point catalog separately in the scoring process.
The new private release catalog is LOCAL `CORPUS.json`; `COMPOSITION.json`
records the declared 33 H4 / 68 primary counts and their base-count source.
The original manifest remains `853390e3…` and the retained scratch clone is
preserved. No paid API calls, Blender renders or demo-service changes occurred.
