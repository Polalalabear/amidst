> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# C7 Demo source map and C6 route recheck — 2026-10-17

Model / effort: **gpt-6.1-sol / high**. C7 implementation / focused verification delivered for CP2 and K7 review. No checkpoint approval or merge. The separate [Office-first report](C7_OFFICE_SOURCE_MAP_20261017.md) preserves commit `4a692c631ca88d24ba2d40a5935421cee4832069` and the earlier frozen Office artifact, including individual furniture footprints, floor/marker origins and the two annotation gaps.

## Scope and reproducibility

`configs/c7_demo_source_map_v1.json` fixes a union of camera neighbourhoods **before** route evaluation: the original Office camera-pair box plus independent 12 m half-width boxes around CLASS101, CORRIDOR_02/03/04 and SIDE_ENTRANCE camera origins. Space between boxes is not filled by their bounding rectangle. These are explicit geometry extraction neighbourhoods, not semantic room claims, a whole-school inventory or navigation certification. Areas not covered by source support remain outside the map; they are not silently marked walkable.

Same immutable source `school_v3.blend`, SHA-256 `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`, Scene/frame 220/subframe 0, 0.0247 m/BU. No save or render; source hash/size/mtime unchanged. Export: **1119 evaluated physical mesh instances, 220 unique evaluated-local geometries, 2773707 expanded triangles**. All modifiers evaluated; each source instance keeps ID, matrix, geometry hash and transform check. Maximum independent transform arithmetic difference: **0.000003415 m**. Raw evaluated intermediate is LOCAL, not published or used as renderer GT.

The level anchor remains the large connected source support (`mesh:1140a89a4d33a6bb3e7aa83a`); expanded support evidence includes 41 source instances and 1478 anchor-level horizontal triangles. The area-weighted level is **0.4959475898741955 m**, differing from the source-bound projection plane by -7.205e-14 m. The supported source range is [0.4959474171, 0.4959476684] m. The 25 BU annotation plane is **0.1215524101 m higher**; its original authoring intent remains UNKNOWN. Legacy dimensions are explicit 119 BU / 6 BU declarations, giving 2.9393 m / 0.1482 m, with no evidence of double conversion; the original size rationale remains UNKNOWN.

D3 boundaries are unchanged: annotation objects are excluded, no GT/target trajectory/renderer visibility/depth enters map derivation. The verifier freezes/hash-checks the map and constructs K1 types **before** opening annotation, source-observation and C6-route diagnostic inputs. No map parameter is adjusted using these checks.

## Map handoff

| Variant | Radius m | Height m | Connected components | Opening candidates | Body-centre area m² |
|---|---:|---:|---:|---:|---:|
| legacy_office | 0.1482 | 2.9393 | 70 | 22 | 939.173542 |
| person | 0.25 | 1.7 | 6 | 28 | 853.985496 |

Regions are connected body-centre polygons, not named rooms. They carry `tier: SOURCE_DERIVED`, `walkable: TRUE`; physical navigation remains `NOT_CERTIFIED`. Per-run radius is applied once, using conservative round buffers; K1 must not erode the walkable map a second time. Height also differs between variants, so component counts and area do not compare radius alone. The person variant is bound to the declared Office-person run; future rendered benchmark runs need their own matching run declarations, not a borrowed run ID.

The bundle's obstacle ledger includes all extracted physical components (including classroom desks/chairs, tables and floor-covering geometry), not only the explicitly grouped Auditorium furniture. Its 16 chairs / lectern retain individually grouped footprints from fresh source meshes; other component semantics are not inferred from appearance. Floor coverings above the 0.005 m floor exclusion are conservatively included as obstacles. Source completeness and semantic room/door labels await K7; this is a nominal body model, not a real-building certificate.

`amidst.geometry.source_floor_map.load_polygon_floor_map` returns the existing `PolygonFloorMap`, with descriptor `kind: SOURCE_DERIVED`, holes, portals, tiers and unknown regions preserved, and raw-file / output / source hash guards. Actual types loaded from pinned K1 commit `7c01522523d61c7c6453521b59478e6990ec241e` construct both variants successfully. No K1 file was changed and no hypothesis search was run. K0 contracts remain **unapproved drafts (PR #10)**; K7 must check thin map features versus the 0.25 m lattice and semantic portal connectivity before promotion. The portal generator handles axis-aligned low-wall flank gaps only and retains geometric opening candidates, potentially on both wall faces.

The old 8.6 s point is still clear for r 0.1482 m and outside the person-radius body-centre domain; nearest source-obstacle clearance is **0.201501063 m**. It is not inside any source obstacle. The coarse Office obstacle has **0 m²** overlap with source obstacle footprints or grouped furniture. Both annotation doorway-gap bands intersect a source opening about 1.75039 m wide; nearest annotation-vertex links themselves are not body-clear. See the separate frozen Office diagnostic for full coordinates and gap evidence.

## Post-freeze C6 recheck

Pinned candidate JSON from `codex/c6-multicamera-feasibility` (commit `9937135f69da3e768c1d2714ee416dc3a780f04c`), hash recorded in verification. All **15 routes / 858 individual edges pass** the person body-centre domain and source floor support. Repeated path traversals are counted in route length and supported length; they are not erased by set intersection. No route was changed or selected using this map. All cross source opening `portal:691025ceab19efd7`; examples benchmark-001/002/003 each cross it on edges 3–6. This is geometry evidence only, not RGB visibility, benchmark admission or coordinator approval.

| Benchmark | Geometry status | Edges | Traversed length m | Minimum raw obstacle clearance m |
|---|---|---:|---:|---:|
| `c6-benchmark-001` | PASS | 59 | 14.75 | 0.268680 |
| `c6-benchmark-002` | PASS | 59 | 14.75 | 0.268680 |
| `c6-benchmark-003` | PASS | 60 | 15.00 | 0.287820 |
| `c6-benchmark-004` | PASS | 59 | 14.75 | 0.268680 |
| `c6-benchmark-005` | PASS | 60 | 15.00 | 0.268680 |
| `c6-benchmark-006` | PASS | 59 | 14.75 | 0.268680 |
| `c6-benchmark-007` | PASS | 59 | 14.75 | 0.287820 |
| `c6-benchmark-008` | PASS | 58 | 14.50 | 0.268680 |
| `c6-benchmark-009` | PASS | 57 | 14.25 | 0.268680 |
| `c6-benchmark-010` | PASS | 58 | 14.50 | 0.287820 |
| `c6-benchmark-011` | PASS | 56 | 14.00 | 0.287820 |
| `c6-benchmark-012` | PASS | 56 | 14.00 | 0.287820 |
| `c6-benchmark-013` | PASS | 55 | 13.75 | 0.268680 |
| `c6-benchmark-014` | PASS | 52 | 13.00 | 0.287820 |
| `c6-benchmark-015` | PASS | 51 | 12.75 | 0.287820 |

Independent source-furniture aisle probes: three row aisles (widths 1.35565 / 1.12973 / 1.35565 m) pass the r 0.25 m body check. Twelve gaps between adjacent chairs (widths 0.09654–0.12976 m) are correctly rejected for a 0.50 m body diameter. Probes and outcomes are recorded; no narrow gap is silently treated as a portal.

**Benchmark routes remain unrendered and await coordinator confirmation.** C6's 5 Hz frame admission and between-frame visibility caveats remain as reported in PR #34. C5 must use the same visibility definition: any visible bottom/torso/head probe means non-blind, evaluated at actual fixed 5 Hz frame times for K1 negative evidence (time_step_s=0.2 s aligned with the render clock). C7 rechecks only geometry.

## Commands and checks

Existing environment: Python 3.12.12, NumPy 2.5.3, Shapely 2.1.2 / GEOS 3.13.1, Blender 5.2.1 LTS build `9e2066aef7ef`. No dependency install, new venv or worktree.

```sh
/Applications/Blender.app/Contents/MacOS/Blender --factory-startup --disable-autoexec -b blender/school_v3.blend --python scripts/export_demo_source_mesh.py -- --config configs/c7_demo_source_map_v1.json --output /tmp/c7-demo-source-mesh.json.gz
PYTHONPATH=src python scripts/derive_demo_source_map.py --input /tmp/c7-demo-source-mesh.json.gz --output /tmp/c7-demo-map.json
PYTHONPATH=src python scripts/verify_demo_source_map.py --map /tmp/c7-demo-map.json --annotation-geometry data/scene_audit/school_v3_approved_scale_20261006/geometry.json --observations data/engineering/blender_workbench_20261011/frame_queries.json --safe-inputs .local-worktrees/phase1-finalization/data/engineering/local_run/blender_camera_v1/office/safe_inputs.json --output /tmp/c7-demo-verification.json
PYTHONPATH=src python scripts/plot_demo_source_map.py --input /tmp/c7-demo-map.json --output /tmp/c7-demo-map.png
PYTHONPATH=src python -m pytest tests/unit/test_source_floor_map.py -o addopts='' -q
git diff --check
```

All outputs use exclusive-create; choose new paths. Actual LOCAL source intermediate `/private/tmp/amidst-c7-20261017/source-mesh-demo-v1.json.gz`, 13827818 bytes, SHA-256 `e92f4c5384696c1646ad1fe14c3001bd08d4c3985e4e17aa493240cef01ccf82`. Office LOCAL intermediate `source-mesh-v2.json.gz`, 2017992 bytes, SHA-256 `46d980c64c914252f9514543a9d729936fdb089739ab257bff7064fd5ca78b4d`.

Focused tests **14 passed in 0.22 s**, Ruff check/format pass on seven task Python files; diff checks pass. Tests cover source/hash guards, floor support vs furniture, retained threshold patches, zero-thickness walls, height/radius doorway clearance, K1 shape preservation, camera-box union and near-coincident projected triangles. Figures visually inspected.

A first expanded derivation failed in GEOS on near-coincident dense source-furniture edges. The fix applies the already-declared 1e-5 m grid **during** polygon union rather than only after union; regression passes and full bounded derivation succeeds. The first verifier counted unique support length for self-revisiting paths; the final record sums edge lengths and adds furniture-aisle probes without changing the map. Preliminary outputs are preserved LOCAL, not presented as final.

Not run: render, perception/inference, GT metrics, full test suite, K1 hypotheses, browser/demo or K7 review. Source `.blend`, calibration, original data, C6 candidate list and K1 files were not modified. C4a PR #37 still needs a separately integrated source clip resolver (walkable KEEP mask plus camera-specific foot-hidden mask); this map does not itself implement that camera shadow or change endpoint quality. Floor float binding needs a documented canonical-plane/tolerance decision. CP2 remains unapproved; no merge.

## Artifact SHA-256

- `C7_DEMO_SOURCE_MAP_20261017.json`: `79da9ba747c38c62731c50c91c76d936a97042cba5551451b85047690cf6ca37`
- `C7_DEMO_VERIFICATION_20261017.json`: `420c561ef27845eae04f2d1a7eb45dc52bb5b0d0c45d1be09071a0e1d5fc5afa`
- `C7_DEMO_SOURCE_MAP_20261017.png`: `d461236f74b93bd2d369c2a8141956fc1199541f3e82af36ffabe1dd9c8de42f`

2026-10-17 review follow-up: WORK_LOG conflict reconciliation and camera-specific foot-hidden-mask responsibility/interface tracking are recorded [here](C7_REVIEW_FOLLOWUP_20261017.md); implementation remains pending in [#49](https://github.com/Polalalabear/amidst/issues/49). Geometry/route outputs above are historical and unchanged.
