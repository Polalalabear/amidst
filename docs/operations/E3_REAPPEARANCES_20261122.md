# #652 B/C reappearance extension (before E3)

This follow-up uses `codex/feat-e3-reappearances`, base main
`8af69ea42cfb06a799952ddb27f97a32a721bde4`. The original nine-case corpus and
its manifest SHA-256 `853390e3dbecc8209c16c47d6e6a6cd5fc73d57bef2d1c4e11c757f8fa8b812e`
remain frozen at LOCAL `local/evidence/e3-652-20261122`.

The new LOCAL output is `local/evidence/e3-reappearances-20261122`.
Source edits happen only in the retained scratchpad clone; the demo checkout
and services remain untouched apart from its ignored LOCAL artifacts.

## Design fixed before group outputs

`configs/evaluation/e3_reappearances_design_v1.json` records six authored
control plans and their GT-only preflight: B3/B4/B5 and C3/C4/C5, five returns
each, 542.2 s in total. This is a planned count, not yet a formal recorded result.
The base counts 3 reappearances / 38 primary points come from the user's
2026-11-22 instruction; no base experiment outputs are opened or reclassified.
If all planned returns survive actual recording, the combined counts are
33 H4 reappearances and 68 primary points, in 15 clips.

A return point is counted once per complete target-visible → globally unseen →
target-visible transition. The target must remain present in the scene during
the gap. The blind gap must last 3–10 s, with at least 3 s visible before it and
3 s continuously visible after the return. The evaluation window is fixed to
[return, return+3 s]. B may return on the same camera; C must return on a camera
set disjoint from its last visible camera set. All qualifying events are kept;
subsequent visible ticks and diagnostic anchors are not additional samples.

The producer uses scripts, static geometry and A-private GT only. It does not
open Agent answers, B logs, baseline snapshots, rankings, group scores or output
folders, and never invokes `baseline.py`, an advisor or an E3 group runner.
C's new top-k rank is UNKNOWN; no output-based ranking is used to construct
these new cases. The original two beyond-top-three cases are preserved.
Repeated events remain clustered within six authored clips, not thirty
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
node scripts/evaluation/e3_cases/record.mjs "$NEW_ROOT" "$LIVE_ASSETS" E3-B3 E3-B4 E3-B5 E3-C3 E3-C4 E3-C5
node scripts/evaluation/e3_cases/freeze_reappearances.mjs "$NEW_ROOT" "$LIVE_ASSETS"
# Commit the case/GT point pins before the following index-production step.
PYTHONPATH="src:$RUNTIME_DEPS" uv run --no-project --python "$E3_PYTHON" python -B scripts/evaluation/e3_cases/index.py --root "$NEW_ROOT" --models "$MODEL_ROOT" --cases E3-B3 E3-B4 E3-B5 E3-C3 E3-C4 E3-C5
```
