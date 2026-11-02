# QT-25-T SYNTHETIC checker fixtures

These files contain no model execution, source RGB, original asset, or formal run
bytes. They test the checker requested by #312, not the acceptance of a real index.
Every reported PASS retains `authority_verified=false` and
`formal_acceptance=NOT_EVALUATED`.

`SYNTHETIC_TEST_ONLY_V1` is an explicitly selected test input envelope. It is not a
new `q-demo.*` schema, a production receipt decoder, an authority registry, or an
approval. No formal receipt wire/decoder is established by the pinned contract;
omitting `--decoder`, or selecting an unknown decoder, returns `INCOMPLETE` (exit
2). The formal command in #312 therefore stays fail closed until that prerequisite
is adopted and implemented. The synthetic option cannot accept formal inputs.

The index and records are adapted from #127's
`tests/fixtures/q1q5_conformance/SYNTHETIC/valid/detection_index{.json,.records.jsonl}`
at `e1415f32a778f497bdd048d992440718bf0a9310`. The original has ten records and broad
60-second declarations; it is not evidence of complete per-camera coverage. This
fixture instead has two cameras, four frames per camera, 200000 µs intervals,
stride 1, and exact 800000 µs ranges. One frame contains two synthetic detections;
the other seven contain explicit empty detection arrays. No inference runs.

The synthetic source manifest and parameter set are checker inputs, not added
product schemas. All parameter entries and the enclosing approval remain
`PROPOSED`. The explicit HSV values are synthetic test values, not a claim that
§11/D75 initial values have been approved or reproduced. Their complete bytes,
canonical HSV value, parameter-set canonical hash, and bindings are verified.
The detector manifest config hash follows the existing producer's canonical
wrapper `{model_config_sha256, index_score_floor, nms}`. It is distinct from the
receipt's raw detector-config file SHA-256. All six input roles have independent
raw byte pins; re-pinning changed bytes does not bypass binding checks.

Coverage is recomputed from source `fps`, `duration_s`, frame count, camera set,
every record's frame index/timestamp, and the index sampling grid. Every absent
frame or explicit `MISSING`/`NOT_INFERRED` frame needs an exact receipt-only
`NOT_EVALUATED` frame range with a reason. Explicit `NOT_SAMPLED` rows count as
recorded sampling skips, not inferred observations. An absent off-grid row still
needs a gap declaration. The existing four index frame states are unchanged.
An inferred range cannot claim an absent or uninferred on-grid frame. Declared
gaps allow a checker consistency PASS; they never mean the run was fully evaluated.

All six timing categories are either numeric, finite, nonnegative `MEASURED`
seconds or null `NOT_MEASURED` with a reason. The fixture uses nulls because no
producer ran. A focused test measures an actual local JSON read/parse operation;
it provides no model, HSV, or production performance evidence. The checker checks
the declarations; it cannot independently prove a producer's measurement source.

The existing reader is `src/amidst/q1q5/store.py`'s
`JsonRunStore.load_detection_index`, reached from `q1_search.py`; the file named in
#312, `detection_index.py`, is the producer, not a loader. The checker does not
create a replacement reader. It calls the real reader, then the fixed #127 kit
and detection-index/record schemas. `KIT_PINS` pins the module and its relevant
dependency/schema bytes at the commit above. The supplied kit root and imported
dependency origins must agree. Tests accept `AMIDST_INDEX_KIT_ROOT`; the CLI
accepts `--kit-root`. Only the pinned checker modules are loaded;
unrelated evaluation/trajectory metrics are not imported.

The kit's 2000-record limit is handled by checking every chunk, while the existing
reader checks global record order/IDs and the checker checks the full run grid.
The 2004-record positive and a below-floor detection in its last row guard against
silently sampling away an invalid tail. A skip or missing kit check is rejected.
The positive case requires 17 kit PASS results, not merely absence of failures.

The checker rejects duplicate JSON keys, nonfinite numbers, symlinks, path escape,
unknown synthetic envelope fields, forbidden input keys, and byte/hash/scope
mismatches. The legitimate `provenance.gt_read=false` remains allowed;
`gt_read=true` and actual forbidden data keys are rejected. No GT, trajectory,
visibility, depth, or event-script input is read for inference or these fixtures.

`invalid/` contains six separate receipt negatives (missing pin, coverage count,
estimated timing, cross-run binding, forbidden key, wrong SHA). Focused tests add
re-sealed semantic corruptions, gaps, timestamp/state errors, and source safety
checks. They use `importorskip` for a missing existing reader; strict mode converts
that missing implementation into failure. An unavailable/different fixed kit also
skips in normal mode and fails in strict mode; skips are not kit PASS results.
The checker itself is implemented here.

For the bounded verification export, set `PYTHONPATH=<export>/src` and use a kit
root containing the exact pinned files (normally the same export). Run:

```bash
python scripts/check_detection_index_receipt.py --receipt tests/fixtures/detection_index_receipt/SYNTHETIC/valid/receipt.json --index-root tests/fixtures/detection_index_receipt/SYNTHETIC/valid --decoder SYNTHETIC_TEST_ONLY_V1
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/q1q5/test_check_detection_index_receipt.py
```

The first command returns `PASS_SYNTHETIC_ONLY`; the same receipt without the
explicit test decoder returns `INCOMPLETE`. These results do not authorize QT-25
inference, accept a real run, approve parameters, or replace independent review.
