# Auditorium display restoration — Task C

Implementation base: Task B `3cc3f6885246ebdffc1af3315347341cc81707b2`, stacked on PR #4. Audit: PR #5. No history integration is required.

## Additive presentation compatibility decision

The Office launcher attaches only `snapshot.presentation.supplemental_display` after source/config/asset validation. The existing presentation fields, meshes and references stay identical. This is an optional additive presentation extension, not a safe-input fixture, inference, observation, candidate, physical or navigation contract change. Existing clients ignore the new key. General Blender adapters are unchanged; only the Office factory attaches it. No calibration or coordinates are rewritten. Invalid/missing configured assets fail startup, rather than silently displaying an unrelated source.

The companion contains partial Auditorium architecture derived from the pinned Auditorium presentation with the Office crop volume subtracted without caps; 19 exact evaluated-local geometry definitions and 94 source instances. Raw local vertices use BU; each instance matrix maps them directly to world metres by scaling the first three rows of the Blender world matrix by 0.0247. This introduces no alignment/recentering. Architecture already uses world metres.

Generated-asset estimate before generation: 3–10 MiB JSON and 1–4 MiB gzip, bounded at 32 MiB raw / 8 MiB compressed. Source scan only; no save/render, dependency install, source copy, dataset, video or new worktree. Free space is checked before and after export and must remain at least 8 GiB.

The launcher adds only the requested repair branch, requiring the exact Task B commit as ancestor; original branch support remains. Its startup fingerprint includes config, asset and exporter. A launcher-owned service restart is required because the old process caches backend snapshots and reads frontend files live.

## Coverage

`PARTIAL_DISPLAY_CONTEXT`: the verified 16 five-part chairs and 14-part lectern plus the existing bounded source architectural crop. The entire Auditorium envelope, upper walls/roof, other furniture, installation hardware and surrounding coverage remain UNKNOWN. These meshes are never physical-review, collision, navigation, inference or Ground Truth inputs.

## Validation receipt

2026-10-16 Asia/Taipei, verified in the existing checkout. Critical Task C audit reproduction matched all reported hashes and counts: source inventory 133 bounded objects, 94 furniture meshes absent from the archive/26 ROIs, Office 1,662 and Auditorium 318 triangles, compatible source/calibration/scale. This confirms the loss precedes Three.js. Source `.blend` SHA-256 `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`, size 468,300,506 bytes and mtime_ns 1791198236746106977 remained unchanged before/after both exports.

| Result | Verified value |
| --- | --- |
| Furniture | 16 five-mesh chair assemblies (80 meshes), one 14-mesh lectern |
| Shared furniture geometry | 19 definitions, 117,103 unique triangles; 94 instances, 611,598 expanded triangles; both armrest variants retained |
| Supplemental architecture | 2 source crops, 366 triangles after subtracting Office volume and triangulating remaining fragments; no new caps |
| Original Office | All 1,662 triangles and existing references unchanged |
| Asset | 5,730,870 bytes JSON / 1,771,647 bytes gzip |
| Asset SHA-256 | `8a189e096e5c155bba584e152eebc37944950a56d83eb3b6cab4908c4821dbd6` |
| Archive SHA-256 | `6d30e591d6210707f2b6175bf96dc2fe2395fe0202b24bd0a6df7ee87a5d997c` |
| Scale config SHA-256 | `7e3615a3b0b4485585da9c0f7beefb96955517f7a321910fc008c041f99a3eaf` |
| Office safe inputs SHA-256 | `1ea62def6c843b3bae1c5e25584fa489915f08e678b28b6220dc88cc17b43163` |
| Auditorium safe inputs SHA-256 | `9555df8e0947a0eb951c2d21d63687ac81033748178d397e45e5221a4f7f321c` |
| Coordinates | Right-handed native XYZ, Z-up, 0.0247 m/BU, no alignment transform |
| Max export transform residual | 0.0000030253298035631815 m versus Blender float world evaluation, below 1e-5 m tolerance |
| Actual supplemental vertex bounds m | `[37.044,38.4025,0.47594759]` → `[50.60939169,57.59680483,3.29594759]` |
| FRONT camera m | `[50.02349409,57.16834297,3.78438704]`, unchanged; included in display framing |
| REAR camera m | `[50.01267880,39.04265562,3.78483027]`, unchanged; included in display framing |

`verify_office_display.py` independently loaded the existing Office inputs, bound the same physical source, and compared before/after: the complete original snapshot (minus the new supplemental key), all original safe inputs, both camera queries/all observation fields, Top-K 1/3/5, and physical-review results were equal. Every observation remained absent from 4.6–8.4 s. No inference repair or Ground Truth access occurred.

Focused automated verification:

```sh
# Reuse the existing uv-managed Python environment; no dependency installation.
# Set PYTHONPATH=src and PYTHONDONTWRITEBYTECODE=1.
uv run --offline --no-project --python "$EXISTING_PYTHON" python -m pytest \
  tests/workbench/test_office_display.py tests/workbench/test_blender_scene.py \
  tests/workbench/test_blender_service.py tests/workbench/test_target_reconstruction.py \
  tests/workbench/test_blender_association.py tests/workbench/test_blender_physical_review.py
# 105 passed; final regenerated asset: its 10 focused geometry tests passed again.

node --test frontend/workbench/scene.test.mjs frontend/workbench/physical-review.test.mjs \
  frontend/workbench/physical-review-office.test.mjs frontend/workbench/cross-camera.test.mjs \
  frontend/workbench/motion.test.mjs frontend/workbench/app.test.mjs \
  frontend/workbench/workbench-layout.test.mjs frontend/workbench/frame-query.test.mjs
# 118 passed; after the final opacity adjustment, all 21 SceneView tests passed again.

uv run --offline --no-project --python "$EXISTING_PYTHON" python scripts/verify_office_display.py \
  --evidence "$EXISTING_EVIDENCE_CHECKOUT"
uv run --offline --no-project --python "$EXISTING_PYTHON" python -m ruff check \
  src/amidst/workbench/office_display.py scripts/materialize_office_display.py \
  scripts/verify_office_display.py tests/workbench/test_office_display.py
uv run --offline --no-project --python "$EXISTING_PYTHON" python -m mypy \
  --follow-imports=silent src/amidst/workbench/office_display.py
git diff --check
```

Python/Blender macOS configuration probes crashed inside the sandbox; both completed with normal host permissions. No missing dependency was installed. The Blender probe/export ran in background with `--factory-startup --disable-autoexec`, without save/render. Reproduction uses the exporter command in its module docstring and a fresh output path; configure the existing checkout/evidence/source paths, never duplicate the `.blend`. The gzip is deterministic (`mtime=0`); exporter code, config policy, source, archive, scale and safe-input hashes are bound and checked. A missing/stale artifact fails Office startup.

Actual browser validation: **PASS (bounded Task C scope)** using the repaired Office factory on a temporary dynamic-port localhost server. Observed architecture, all four rows/columns of chairs, lectern and FRONT/REAR frusta with no obvious displacement or scale mismatch. Zoom/orbit and timeline remained responsive. Changed candidate 1→2→3, verified 2D FRONT/REAR synchronization at 8.6 s and visible restart marker, and 5.0 s MISSING for every candidate path without a current-position continuation. Task B automated coverage checks every gap tick and observation identity/segment rings. The visible supplemental status retained PARTIAL/UNKNOWN. Browser console had no warning/error. Two compact local screenshots record restored geometry and the missing interval; they are not a generated RGB dataset.

Disk before: 13,037,272 KiB available (~12.43 GiB), checkout 129 MiB. After initial implementation/browser: 11,960,432 KiB (~11.41 GiB), checkout 133 MiB; free space remained above 8 GiB. Filesystem-wide usage can change independently of this checkout. No caches, user files, worktrees or prior assets were deleted. Three original untracked audit deliverables were preserved and excluded from staging.

Changed files: source-bound display config and compact gzip; bounded exporter; fail-closed display loader; Office factory attachment; SceneView layer/framing/status and regression; narrow launcher branch/fingerprint extension; real-input verifier; focused Python tests; this receipt and documentation index.

Full 8-minute demo acceptance additionally requires Office, Classroom101, E1, investigation save/reopen and report export; Task C alone does not establish it. These cross-scene flows remain **NOT TESTED** here. Existing Task A floor-projection quality/room attribution is unchanged; camera frusta remain geometric with visibility UNKNOWN. Coverage is partial and physical/navigation authority is unchanged.

Launcher restart and final publication verification are recorded after the focused commit; no automatic merge is authorized.
