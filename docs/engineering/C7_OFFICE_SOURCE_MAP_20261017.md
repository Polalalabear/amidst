> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# C7 Office-first source map — 2026-10-17

Status: Office / adjacent Auditorium source geometry delivered for CP2 / K7 review. No checkpoint approval or merge. Remaining C6 areas are a separate extension of this C7 task; the Office artifact is frozen before those checks. The follow-up [Demo-area extension](C7_DEMO_SOURCE_MAP_20261017.md) records their results separately.

Model / effort: gpt-6.1-sol / high. The frozen Office builder/exporter/verifier are retained at commit `4a692c631ca88d24ba2d40a5935421cee4832069`; later Demo extension code is versioned separately.

## Source and authority

- Source `blender/school_v3.blend`, SHA-256 `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`, 468300506 bytes, mtime_ns 1791198236746106977. Scene `Scene`, frame 220 / subframe 0; 0.0247 m/BU exactly once.
- Camera-origin ROI, fixed before derivation: X [25.0126787964, 52.0234940918], Y [36.0426556152, 60.1683429688] m. This is the Office camera pair's neighbourhood, not an approved semantic room boundary. Source hash, size and mtime remained unchanged; no save or render.
- 299 evaluated physical mesh instances, 76 unique evaluated-local geometries, 638682 expanded triangles. Per-instance IDs, evaluated geometry SHA-256, native matrices, bounds and transform checks are in the map ledger. The LOCAL compressed intermediate is reproducible with the commands below; it is not an input to inference.
- `WALK_*`, `PORTAL_*`, `AREA_*` and other annotation objects/collections are excluded. No observation, GT, target trajectory, renderer visibility or depth is read by the exporter or map builder. Annotation/endpoint inputs are read by a separate post-freeze verifier only.
- Horizontal source support uses connected non-furniture patches >=4 m² to establish the level; coplanar small threshold patches connected to support remain included. Abs normal Z >=0.999, level tolerance 0.002 m, coordinate precision 0.00001 m. Unsupported floor fails instead of inventing support.
- Obstacles are source triangles clipped to the nominal upright body's height slab (floor+0.005 m to floor+run height). Furniture uses conservative per-component XY hulls; architectural footprints retain zero-thickness wall lines. Body radius is applied once to obstacles and floor boundaries, with conservative polygonal round buffers.
- Every derived region has `SOURCE_DERIVED`; outside scope is UNKNOWN. `physical_navigation=NOT_CERTIFIED`. Source parent names are furniture grouping evidence only. No previous display-only footprint is promoted without re-extraction.

## Floor and legacy marker origins

The derived floor is **0.4959475898742675 m**, matching the projection plane **0.49594758987426757 m** to numerical precision. Annotation floor objects are at **25 BU = 0.6175 m**; the source support is at about **20.0788479 BU**. Thus the 0.12 m discrepancy is **0.12155241012573242 m** caused by different declared annotation/support Z levels, not a second scale conversion. Why the annotation author chose 25 BU remains UNKNOWN: no tracked authoring record was found. The direct source annotation diagnostic confirms these Z values after map freeze.

Legacy marker dimensions originate in `scripts/plan_blender_pilot_sites.py`: radius=6 BU, height=119 BU, probe_height=55 BU; `scripts/export_blender_pilot.py` constructs a cylinder plus sphere envelope of `2*55+1.5*6=119 BU`. Therefore 119×0.0247=**2.9393 m** and 6×0.0247=**0.1482 m**. These are explicit native-unit settings, not evidence of a conversion bug. The original rationale for selecting this non-human size is UNKNOWN. Legacy is labelled **synthetic capsule, not human sized**; the new run uses 1.70 m / r 0.25 m. Both remain per-run configuration.

## Furniture inventory

Fresh source extraction resolves 16 five-part chairs and one 14-part lectern (94 source meshes). These lie east of the coarse Office obstacle, in the adjacent Auditorium source area. **None intersects `OBSTACLE_1F_OFFICE_01`.** Calling them Office-room chairs would contradict their coordinates. Other physical meshes in the ROI remain in the obstacle ledger even without furniture labels; semantic classification and completeness of human room labels await K7.

Numbers match the review figure. Area is the person-height footprint before radius buffering; bounds are minX, minY, maxX, maxY in metres.

| Figure | Source assembly | Parts | Area m² | XY bounds m |
|---|---|---:|---:|---|
| 1 | `N1 Hamburg` | 14 | 0.678611 | 46.9170, 54.0459, 48.0485, 55.1531 |
| 2 | `Theatre Chair` | 5 | 0.827263 | 42.9188, 54.0155, 43.7985, 55.0872 |
| 3 | `Theatre Chair.001` | 5 | 0.827267 | 41.9093, 54.0155, 42.7890, 55.0872 |
| 4 | `Theatre Chair.002` | 5 | 0.827266 | 39.9237, 54.0155, 40.8034, 55.0872 |
| 5 | `Theatre Chair.003` | 5 | 0.827259 | 40.9331, 54.0155, 41.8128, 55.0872 |
| 6 | `Theatre Chair.004` | 5 | 0.827259 | 40.9331, 51.5882, 41.8128, 52.6599 |
| 7 | `Theatre Chair.005` | 5 | 0.827265 | 39.9237, 51.5882, 40.8034, 52.6599 |
| 8 | `Theatre Chair.006` | 5 | 0.827266 | 41.9093, 51.5882, 42.7890, 52.6599 |
| 9 | `Theatre Chair.007` | 5 | 0.827262 | 42.9188, 51.5882, 43.7985, 52.6599 |
| 10 | `Theatre Chair.008` | 5 | 0.827262 | 42.9188, 46.9595, 43.7985, 48.0312 |
| 11 | `Theatre Chair.009` | 5 | 0.827266 | 41.9093, 46.9595, 42.7890, 48.0312 |
| 12 | `Theatre Chair.010` | 5 | 0.827265 | 39.9237, 46.9595, 40.8034, 48.0312 |
| 13 | `Theatre Chair.011` | 5 | 0.827258 | 40.9331, 46.9595, 41.8128, 48.0312 |
| 14 | `Theatre Chair.012` | 5 | 0.827258 | 40.9331, 49.3868, 41.8128, 50.4585 |
| 15 | `Theatre Chair.013` | 5 | 0.827265 | 39.9237, 49.3868, 40.8034, 50.4585 |
| 16 | `Theatre Chair.014` | 5 | 0.827266 | 41.9093, 49.3868, 42.7890, 50.4585 |
| 17 | `Theatre Chair.015` | 5 | 0.827262 | 42.9188, 49.3868, 43.7985, 50.4585 |

## Endpoint and coarse obstacle

The old 8.6 s REAR observation `observation:997166541f223b4f923d8bff` is at [31.5440606701, 53.6489210628, 0.4959475899] m. It is inside the 36.639382 m² coarse annotation but **outside every source obstacle footprint**. With the old run's radius 0.1482 m / height 2.9393 m it is inside the derived body-centre domain. The source-obstacle clearance is 0.201501063 m (post-freeze calculation), between the two radii. With r 0.25 m / height 1.70 m that same old point does not have sufficient body-centre clearance; do not reuse a legacy observation as a new-run position.

The coarse annotation has **0 m²** overlap with extracted furniture or physical obstacle footprints in both variants. It overlaps 32.952450 m² (legacy) / 30.274323 m² (person) of source-derived body-centre area. This is a post-freeze diagnostic, not tuning evidence or a guarantee that C4a intervals become valid. C4a clipping and endpoint quality handling are separate; `AMBIGUOUS_MERGE` remains unchanged.

## Doorway cross-checks

Both annotation gaps have source floor support across the comparison band. Each band intersects a derived source opening of about 1.75039 m; the annotation gap widths are not door aperture widths.

| Annotation pair | Annotation gap m | Source candidate | Aperture m |
|---|---:|---|---:|
| AUDITORIUM_OFFICE_THRESHOLD ↔ AUDITORIUM | 0.123500 | `portal:07a7dd7bc486e579` | 1.750389 |
| CORRIDOR_03 ↔ AUDITORIUM_THRESHOLD | 0.169635 | `portal:0307a946d770750e` | 1.750395 |

The nearest pair of annotation vertices is **not itself a body-clear crossing** in either case. Portal acceptance instead requires the midpoint crossing through the actual wall opening to be inside the full body-centre free domain. Door identity / connectivity semantics remain for K7. This first extractor finds axis-aligned low-wall flank gaps only; it does not claim all door orientations or de-duplicate both wall faces into semantic doors.

## K1 handoff and verification

The bundle contains legacy (17 connected regions, 13 opening candidates, 361.468389 m²) and person (1 connected region, 14 candidates, 329.773913 m²) variants. Height and radius both change, so counts/areas need not be monotonic in radius alone.

`load_polygon_floor_map(path, variant=..., expected_sha256=..., expected_source_sha256=...)` builds the real K1 `PolygonFloorMap`, preserving polygon holes, regions, tiers and portals. The post-freeze verifier loaded actual classes from pinned `origin/claude/k1-hypothesis` without editing K1 files; both variants constructed successfully. It did not execute K1 hypotheses. K1 must not apply the body-radius erosion a second time to this body-centre map.

C6's 15 selected routes are outside this Office ROI; all are `OUTSIDE_SOURCE_MAP_SCOPE`, not accepted or declared unwalkable. Their recheck awaits the remaining Demo-area extension. No benchmark route was rendered.

C4a is on its separate unmerged branch (PR #37); its `SourceClip` adapter is not wired here. Its exact floor float guard needs a source-bound tolerance/canonical-plane decision before integration (derived/projection delta is about 5.6e-17 m). CP2 approval and K7 semantic review remain pending.

## Reproduction

Use an existing Python environment with NumPy, Shapely, Matplotlib and pytest; no dependency install is needed. Outputs are exclusive-create: use new paths, never overwrite frozen artifacts.

```sh
/Applications/Blender.app/Contents/MacOS/Blender --factory-startup --disable-autoexec -b blender/school_v3.blend --python scripts/export_demo_source_mesh.py -- --config configs/c7_office_source_map_v1.json --output /tmp/c7-office-source-mesh.json.gz
PYTHONPATH=src python scripts/derive_demo_source_map.py --input /tmp/c7-office-source-mesh.json.gz --output /tmp/c7-office-map.json
PYTHONPATH=src python scripts/verify_demo_source_map.py --map /tmp/c7-office-map.json --annotation-geometry data/scene_audit/school_v3_approved_scale_20261006/geometry.json --observations data/engineering/blender_workbench_20261011/frame_queries.json --safe-inputs .local-worktrees/phase1-finalization/data/engineering/local_run/blender_camera_v1/office/safe_inputs.json --output /tmp/c7-office-verification.json
/Applications/Blender.app/Contents/MacOS/Blender --factory-startup --disable-autoexec -b blender/school_v3.blend --python scripts/inspect_demo_annotation_origins.py -- --map /tmp/c7-office-map.json --output /tmp/c7-office-origins.json
PYTHONPATH=src python scripts/plot_demo_source_map.py --input /tmp/c7-office-map.json --output /tmp/c7-office-map.png
PYTHONPATH=src python -m pytest -q tests/unit/test_source_floor_map.py
git diff --check
```

Focused tests: **12 passed**. Source provenance, synthetic wall/door clearance at both heights/radii, zero-thickness walls, independent furniture footprints, no-floor rejection, small threshold support, authority flags and K1 adapter/hash guards. Figure visually checked. No full suite, inference, GT metrics, real-navigation validation, K7 or hypothesis generation was run.

## Artifact SHA-256

- `C7_OFFICE_SOURCE_MAP_20261017.json`: `53c3771327ad71e26f0a5f1f4db580eaafb7bc7d028b9c250c9f401495bbcd61`
- `C7_OFFICE_VERIFICATION_20261017.json`: `55cf0175978d72b1b4978f16fe7d95b6d74fc4e17c2d0a6c66ed24290f687dc3`
- `C7_OFFICE_ANNOTATION_ORIGINS_20261017.json`: `a611e8856f728ca34557e9b2a77f6c098f6d6958ba1298963e3f88184b5e161f`
- `C7_OFFICE_SOURCE_MAP_20261017.png`: `306918bba59259177b6655daf8c803074f201ea202ed72b7b8ead08e7329873d`
