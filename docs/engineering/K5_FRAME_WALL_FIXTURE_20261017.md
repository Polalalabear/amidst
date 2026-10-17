# K5 real HTTP frame-wall fixture — 2026-10-17

Refs #22/#18/#17. Base #53 @4019a44. No runtime/frontend production changes. Fixture is **actual POST over short-lived loopback HTTP**, with fixed capture-only session and dynamic port; server is closed after capture. No GT, renderer visibility/depth or trajectory is read.

- Fixture: `tests/fixtures/k5_person_frame_wall_v1.json` (2462118 bytes), SHA-256 `466720c2a86694891eb6d63fafb05e53533a787e4560128952fd91e3603992ff`; adjacent `.sha256` file.
- `cases[0]`: POST `/api/target_reconstruction`, `negative_evidence_mode: NONE`. Existing outer UNKNOWN/SELECTED_PROJECTION_UNAVAILABLE remains; nested `blind_hypotheses` READY, no applied evidence. This exact nested response supplies each HYPOTHESIS request hash.
- TIME_RANGE: 34 frames, 2 candidate entries. HYPOTHESIS/PATHS: 5 frames, 2 candidates. HYPOTHESIS/REACHABLE_REGIONS: 32 frames, 2 candidates. All three READY, actual results/windows/frames, outcomes, evaluations, candidates and stats retained.
- Every case includes method/path/request/response/request_sha256/response_sha256. These case hashes are canonical JSON content hashes. Existing native seals are retained and verified.
- Only `response.stats.latency_ms` is omitted for deterministic freeze; actual measured latency is printed to console and is not a frozen measurement/benchmark. No other response field is changed. Session ref is usable only within the isolated capture process, not a running launcher.
- API resolved `visibility_entries` contains **strict polygons**. It does **not** expose suggestion_polygons. This missing API field is reported honestly in `api_absent_fields`; full strict vs suggestion geometry is separately retained under `visibility_index_context.entries`, hash-bound to C5 index7c464ec4…0d83c. It is supplemental index context, not an invented API response. Suggestions never enter evidence polygons.
- Original observation hash is unchanged; no MISSING is filled. Hypothesis selection/truncation explains why HYPOTHESIS results differ from TIME_RANGE; no unreturned frames are fabricated.

Reproduce from this branch, with a fresh output filename:

```sh
PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/freeze_frame_wall_fixture.py --bundle data/engineering/office_person_20261016_v1/office --output /private/tmp/k5_person_frame_wall_new.json
cmp tests/fixtures/k5_person_frame_wall_v1.json /private/tmp/k5_person_frame_wall_new.json
shasum -a 256 /private/tmp/k5_person_frame_wall_new.json
.local-worktrees/phase1-finalization/.venv/bin/ruff check scripts/freeze_frame_wall_fixture.py
git diff --check
```

## 實際產出 / Actual output
- Model / effort: UNKNOWN.
- PR / commits: `codex/k5-frame-wall-fixtures`, exact commit/PR recorded on #22/#18.
- Files changed: capture producer, fixture, adjacent SHA and this report only; no production API/frontend changes.
- Commands run and results: actual HTTP200 for target NONE and three retrieval requests; native seals, producer/index/source/observation hashes verified; independent final captures byte-identical; Ruff/diff PASS. Reproduction command above. Initial formatting-only E501 corrected before final freeze; initial trial files kept LOCAL.
- Artifacts: fixture path/SHA above; timings/dynamic endpoint only LOCAL console, not a live service.
- Verified: both query kinds use C4b NONE context; all requested arrays/stats/candidates populated; D21 geometry distinction; original33 MISSING; deterministic fixture after latency exclusion; owned temporary server closed.
- Not verified: frontend/browser/K5 wall rendering, detector recall/GT, full suite; not a scale latency benchmark.
- Deviations, UNKNOWN items and follow-ups: API suggestion_polygons absent by existing contract reduction, exposed separately as explicit index context. No other missing/unavailable retrieval fields in these captures.
