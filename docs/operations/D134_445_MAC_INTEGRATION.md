# #445 Mac integration — 2026-11-08

The local branch is `claude/445-demo-integration`, based on the handed-off
`ac6cd12225ceb2c8f236ce9e1f9f2420f29bfdb4` (Draft #485). Implementation commit:
`741478b3c499ed8552b92e44606f5f46e5284cb6`. No merge, rebase, force push, branch
removal, `mainline/q1q5` update or `main` update is part of this delivery.

## Start and open

Use the existing Mac checkout and existing Python environment. No install,
render, detection or model call occurs. The launcher reuses `uv` offline and
creates fresh small runtime state outside the source bundles:

```sh
"$CHECKOUT/start_445_demo.command"
```

`AMIDST_DEMO_PYTHON` can select an existing Python. The default reuses the earlier
Phase 1 environment. `--artifacts-root`, `--p1-bundle` and `--port` are explicit
launcher overrides. The default port is 8785; an occupied port fails rather than
stopping another service. Ctrl-C stops this service.

| Event | View | Search | Single-camera track | Multi-camera track |
| --- | --- | --- | --- | --- |
| B-05 | [view](http://127.0.0.1:8785/workbench-v2/?run=B-05) | [search](http://127.0.0.1:8785/workbench-v2/?run=B-05&screen=search) | [single](http://127.0.0.1:8785/workbench-v2/?run=B-05&screen=track-single) | [multi](http://127.0.0.1:8785/workbench-v2/?run=B-05&screen=track-multi) |
| A4-1 | [view](http://127.0.0.1:8785/workbench-v2/?run=A4-1) | [search](http://127.0.0.1:8785/workbench-v2/?run=A4-1&screen=search) | [single](http://127.0.0.1:8785/workbench-v2/?run=A4-1&screen=track-single) | [multi](http://127.0.0.1:8785/workbench-v2/?run=A4-1&screen=track-multi) |
| B4-1 | [view](http://127.0.0.1:8785/workbench-v2/?run=B4-1) | [search](http://127.0.0.1:8785/workbench-v2/?run=B4-1&screen=search) | [single](http://127.0.0.1:8785/workbench-v2/?run=B4-1&screen=track-single) | [multi](http://127.0.0.1:8785/workbench-v2/?run=B4-1&screen=track-multi) |

Additional source-bound links:

- [A4 blind sketch](http://127.0.0.1:8785/workbench-v2/?run=A4-1&screen=blind&as_of_us=9400000)
- [B4 blind sketch](http://127.0.0.1:8785/workbench-v2/?run=B4-1&screen=blind&as_of_us=2100000)
- [B-05 blind UNKNOWN](http://127.0.0.1:8785/workbench-v2/?run=B-05&screen=blind&as_of_us=3000000)
- [r005 101 classroom](http://127.0.0.1:8785/workbench-v2/?run=r005&screen=search&region=R101)
- [r005 laptop](http://127.0.0.1:8785/workbench-v2/?run=r005&screen=search&class=laptop)

## Inputs and authority

- B-05 uses P1 v4 **SYNTHETIC RGB**, not the synthetic SVG API fixture. Bundle
  manifest SHA-256: `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`.
- A4/B4 use #442 D124 **ACTUAL_BLENDER RGB** and #475's saved detection indexes.
  Safe media manifest SHA-256: `ad3c66f21ef6713a76b0bb6505a7e5eb3514fa346f9279c42d7b486479281f01`.
  They are 50 s / 42 s at 5 fps, with their own Asia/Taipei declared clocks.
- #478's exact cross-camera job has SHA-256
  `8586dce9a965193edc456e5a6bed48e331de874f678f85e5b5b20b7449dd71f7`.
  Its explicit scene-name/catalog binding is projected into separate in-memory
  display/search graphs; original graph bytes remain unchanged. Tracking calls
  recompute the pure #478 response at the requested as-of cutoff from its pinned
  local tracks. No final full-run response is replayed for an earlier request.
  The fixed earliest-local-seed preset accepts person / no color / no region;
  a wall-time request must start at source zero. Other tracking filters fail
  closed. Automatic seed, `DEMO_DEFAULT`, `GRAPH_NOT_APPROVED` and identity
  UNCONFIRMED remain visible. This is not arbitrary identity tracking.
- r005 uses #464's saved 33 displayed model candidates (fixed score floor 0.30),
  report SHA-256 `0915d54d585fcbd8e89575bf1ab43dec0ae3b8e85839b8e59704fa9d03b6b021`.
  Its one-second declared static display slot is **not a capture time or video**.
- Human coverage comes only from the user's approved return SHA-256
  `336bd2f8fe418d8a615821bf2e36a65ae783d022a81e00c77e011efe7cfdfad2`,
  [approved in #464](https://github.com/Polalalabear/amidst/issues/464#issuecomment-6715801218).
  The derived curated graph record binds six exact camera/frame/region pairs,
  reviewer 使用者 (Polalalabear), review date 2026-11-07. Raw user return stays LOCAL.
  Undeclared or UNKNOWN coverage remains NOT_EVALUATED. Historical AI preview
  files do not grant human authority. Graphs remain DRAFT / TOPOLOGICAL_ONLY;
  physical navigation and collision remain UNKNOWN.

The source-bound room gate now checks the adopted r005 scene through its pinned
loader. Historical r004 files and their uncovered-room facts are unchanged;
remaining r004 location tests still use r004. Pending-only r005 tests explicitly
select the original skeleton. Missing/tampered human-review pins fail closed.

RGB paths and per-frame hashes are checked against the saved index and safe
manifest. PNGs are read in place and metadata-stripped only for serving. The P1
bridge adds the missing microsecond wire field. Location-only cards show source
RGB without inventing a target observation. Multi-camera mode loads synchronized
RGB for all found cameras, keeping inactive/candidate badges. Playback waits for
actual RGB decode and updates on source sample boundaries. Requested multiplier
is a source-clock control; physical screen fps is unmeasured.

B-05 has no usable calibrated display positions: its blind state is INFERRED /
UNKNOWN with no drawable curve. A4/B4 have dashed display-only sketches from the
pinned static camera catalog and prior observations; B4 confidence can remain
UNKNOWN. These are not measured paths, identity matches or walkability evidence.

## Verification and LOCAL evidence

Implementation verification on Mac Google Chrome:

- `AMIDST_REQUIRE_IMPL=1 ... python -m pytest -o addopts= -q tests/q1q5/test_core_search_track_t.py tests/q1q5/test_scene_graphs.py`: **121 passed**, no skips. This includes the requested #410 file and changed loader tests.
- `AMIDST_REQUIRE_IMPL=1 node --test frontend/workbench-v2/*.test.mjs frontend/event-viewer/*.test.mjs`: **478 passed**, 0 failed.
- #476 `core-e2e.mjs`: **49 checks**, 16 synthetic screenshots; clean source head above, head guard enabled. The preview resolves `refs/heads/claude/445-demo-integration` and verifies the handed-off base is its ancestor; `CORE_INTEGRATION_HEAD` can provide an explicit pin. The old #452 head is no longer the default.
- `real-e2e.mjs`: **53 checks**, 17 screenshots; all requested event screens, actual image decode, source-clock bounds, GAP/LOST, speeds 1/1.5/2, automatic next-camera playback, three blind states and two r005 searches. Zero page errors / failed API responses.
- Automatic switches: B-05 A → B; A4 EXT_CLEAR → W1; B4 W2 → W1. These remain engineering associations. A4's W1 observation is weak, as described in #478.
- Six direct search/multi links additionally decoded RGB successfully. View and single links are exercised by the event matrix / playback checks.
- No-allow architecture guard against PR #485 base `796cc176cd40bedbfe701b95192d3c8679755aa9`, and `git diff --check`: PASS. Final Git state, commands and LOCAL manifest hash are reported on #445.

Reproduce the real browser gate against the already running service using the
existing locked Playwright Core package and installed Chrome:

```sh
INTEGRATION_OUTPUT="$AMIDST_ARTIFACTS/new-445-evidence" PLAYWRIGHT_CORE_MODULE="$EXISTING_PLAYWRIGHT_CORE_MODULE" node tests/browser/core-preview/real-e2e.mjs
```

LOCAL artifacts live under `$AMIDST_ARTIFACTS/d134-445-integration/`:
`browser-results.json` (17 image hashes and 53 checks), `screenshots/` (17 PNGs),
`synthetic-screenshots/` (16 PNGs), saved safe search/track responses, logs,
`synthetic-e2e.json`, `link-results.json`, `playback-results.json`, and `MANIFEST.json`.
The final manifest lists exact sizes/counts/hashes; its hash and absolute locator
are posted to #445. Screenshots can be regenerated by the two browser gates,
provided the pinned source inputs and existing Chrome remain available. Original
RGB, P1 bundle, raw return and model outputs are not committed or copied.

#475 indexes/configuration still use original LOCAL locators recorded in the
pinned cross-camera job, including existing temporary directories. Retain those
inputs; the launcher does not recreate them or rerun inference. No model,
renderer, source dataset, GT or witness receipt is read by this integration.
Windows/Linux, formal parameters, detection accuracy, identity accuracy, physical
navigation/collision, physical display fps and formal research acceptance are
NOT_VERIFIED. PR #485 remains Draft and unmerged. New commits are local; pushing
was not included in this request.
