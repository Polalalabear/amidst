# C3b review follow-up — 2026-10-17

Refs #13, merged #32; implements review suggestions1/2/6 only. Independent small PR based on integration `dcb89f475f14897e1b272da61d44a25acf8f1fb8`; no dependency on #50 or the C4/C5 stack.

Added integrity markers PRESET_DEFAULT_OBSERVATION_MISMATCH, FRAME_CAMERA_MISMATCH and FLOOR_SOURCE_MISMATCH. These now fail closed even for non-default scenes. Existing hash/source/pin/stale handling is unchanged. The review explicitly allowed marker supplementation instead of a broader whitelist migration; unrelated exception behavior was not redesigned.

Optional fixture/load and contact-quality failures now emit SCENE_LOAD_FAILURE JSON to stderr containing scene_id, error_type and layer. Public reason sanitization remains unchanged; stderr does not include exception text or private paths. Default/integrity errors still propagate. v2 quality degradation preserves the original index, null positions and missing observations.

## 實際產出 / Actual output

- Model / effort: **gpt-6.1-sol / high**, current session turn_context verified.
- PR / commits: `codex/c3b-review-followup`, Draft PR and exact SHA posted on #13/#32. No merge.
- Files changed: scripts/office_demo_backend.py; src/amidst/workbench/{scene_errors,contact_scene}.py; tests/workbench/test_office_demo_presets.py; this record/index/WORK_LOG.
- Commands run and results: two specified test files **41 passed in67.46s**,0failed/skipped. Final stale-manifest test uses in-memory injection (no source/calibration copy); affected-case rerun recorded below. Ruff checks on three formatted Python files, F checks on existing backend, git diff --check PASS. No full suite.
- Artifacts: no new inference/media/GT artifacts. Code SHA-256: office_demo_backend.py `4fa95c853d6de8b949948eada7bece8aaab81455432ec02b6f2f536ad924f908`; scene_errors.py `34dac052521e2aad2ba2f1662fb015db0896bc9392097e5544f55432fcc9b890`; contact_scene.py `3ea154313262b5a0426e2dd0f790f438e5d4990f713ab4e2db36413540f77ae5`; preset tests `9d09fe0d05040ee7835deef751f81ecf953e3cf8be3fae03a98e27c194b05add`.
- Verified: optional missing/malformed fixture downgrade and scene mismatch fatal; media size/symlink/frame-count/camera guards; real adapter FIXTURE_BINDING_MISMATCH and BLENDER_SCENE_STALE paths; real default-observation mismatch; actual index floor/camera checks; v2 prediction and v1 telemetry hash rejection; v2 quality bug preserves original observations/MISSING; stderr type/scene/layer and no private-message leak; canonical Office regression and launcher tests.
- Not verified: browser/UI suggestions3/4/5, live degraded service (unit regression only), C4/C5/#50 integration, full suite. No source/calibration/media/GT writes, render, dependency/environment/worktree creation, other-checkout access or service changes.
- Deviations, UNKNOWN items and follow-ups: marker supplementation chosen as authorized. Final stale-manifest injection runs through real adapter verification, not a mock error string. Test-only prediction/telemetry corruption is explicit. No K3/UI changes.

```sh
PYTHONPATH=src:scripts OFFICE_TEST_ASSETS=/Users/polalabear/Developer/amidst UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -m pytest tests/workbench/test_office_demo_presets.py tests/workbench/test_office_launcher.py -o addopts='' -q
PYTHONPATH=src:scripts OFFICE_TEST_ASSETS=/Users/polalabear/Developer/amidst UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -m pytest tests/workbench/test_office_demo_presets.py::test_optional_real_fixture_binding_and_stale_manifest_are_fatal -o addopts='' -q
.local-worktrees/phase1-finalization/.venv/bin/ruff check src/amidst/workbench/scene_errors.py src/amidst/workbench/contact_scene.py tests/workbench/test_office_demo_presets.py
.local-worktrees/phase1-finalization/.venv/bin/ruff check --select F scripts/office_demo_backend.py
git diff --check
```

Final affected-case rerun: **1 passed in32.88s**,0failed/skipped. This overlaps the41-case run and is not added to it.
