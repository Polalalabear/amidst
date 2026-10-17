# P1 bounded metadata-index latency rerun — 2026-10-18

Existing `scripts/benchmark_frame_retrieval_index.py` was rerun without code changes on `225f2461ec3b38b6855d8c6b26d4cc17cb77aaba` (Claude rehearsal base plus launcher receipt feature). Each scale uses one synthetic camera and 100 identical TIME_RANGE queries for [4.8, 8.0] s with max_frames 64. The footprint is FRUSTUM_ONLY, perception_evaluated=false; no candidate can become negative evidence. Metadata is excluded from demo inputs and scientific evaluation.

| Indexed records | Build s | p50 ms | p95 ms | max ms | Records read/query |
| --- | --- | --- | --- | --- | --- |
| 100,000 | 0.046495 | 0.494292 | 0.517542 | 0.723083 | 17 |
| 1,000,000 | 0.422123 | 0.497500 | 0.504500 | 0.711375 | 17 |

This measures in-process metadata lookup plus response construction, not HTTP/browser/socket, RGB hashing/I/O, hypothesis matching, multiple-camera expansion, concurrent clients, startup perception or geometry. A fixed short range near the beginning of one camera's time axis is the tested workload; it does not establish worst-case latency. No performance pass/fail target was invented. The 100 queries at each scale are warm-loop measurements with no separate cold-cache distribution.

Environment: macOS 26.6.1 arm64; existing Python 3.12.12 (Clang 21.1.4), offline uv. `/usr/bin/time -l`: elapsed 1.08 s, max resident set size 432,472,064 bytes, swaps 0. No environment/dependencies or asset files were created. Original `C5_INDEX_SCALE_20261017.json` is preserved.

```sh
PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache \
  /usr/bin/time -l uv run --no-project --offline \
  .local-worktrees/phase1-finalization/.venv/bin/python \
  scripts/benchmark_frame_retrieval_index.py \
  --output /private/tmp/C5_INDEX_SCALE_20261018.json
```

Choose a fresh output path; the script refuses overwrite. LOCAL raw result SHA-256 `8b0ca92bffe59e7f96a394f3659c848e9c15170a309901fbc5267f964f9fc62f`. The committed [result JSON](C5_INDEX_SCALE_20261018.json) adds measurement source/platform metadata, so it has its own hash. Benchmark Git blob `354dafb3c16f5f52efc586306b08862b5dcc8009`; frame index blob `faf000d8fe341d88ff796350670c8a54c75e2548`.

## 實際產出 / Actual output
- Model / effort: UNKNOWN
- PR / commits: docs-only #54; measured program source `225f2461ec3b38b6855d8c6b26d4cc17cb77aaba`; no code changes.
- Files changed: this report and `C5_INDEX_SCALE_20261018.json` only.
- Commands run and results: command above; 100,000/1,000,000 records, 100 TIME_RANGE queries each; both read exactly 17 records/query and return READY/no negative-evidence candidates; latency table above; diff check PASS.
- Artifacts: committed JSON; LOCAL `/private/tmp/C5_INDEX_SCALE_20261018.json` SHA above and `.log` with time resource counters.
- Verified: bounded metadata-index query scaling on current rehearsal backend; original prior result retained; no RGB/GT/raycast/inference read or rerun.
- Not verified: full HTTP/RGB/hypothesis/concurrency scale or worst-case retrieval latency; no benchmark SLO acceptance. No code tests needed for this unchanged benchmark/report task.
- Deviations, UNKNOWN items and follow-ups: optional item completed only for this explicitly labelled metadata workload; broader P1 latency remains unmeasured. RQ1 evaluation was not used in this workload or any code change.
