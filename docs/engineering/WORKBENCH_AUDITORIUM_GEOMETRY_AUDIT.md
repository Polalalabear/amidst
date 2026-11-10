# Workbench Auditorium geometry completeness audit — Task C

2026-10-16 (Asia/Taipei). **Decision: READY_TO_FIX**, limited to the source-verified display subset below. **Root cause confirmed; repair proposed; repair NOT implemented; repaired browser / 8-minute demo NOT validated.** Whole-Auditorium completeness remains UNKNOWN. This audit does not grant physical/navigation authority.

## Checkout, runtime and evidence binding

CONFIRMED: inspected `/Users/polalabear/Developer/amidst-claude`, clean at start, branch `fix/workbench-marker-continuity`, HEAD `3cc3f6885246ebdffc1af3315347341cc81707b2`; origin `https://github.com/Polalalabear/amidst.git`. [Task B PR #4](https://github.com/Polalalabear/amidst/pull/4) is OPEN/DRAFT, base `claude/office-demo-visualization` at `57eab7eae6ea27fb75a3bf7ad3e460e7caee3675`, head matches checkout. The sole commit since that baseline changes five frontend/test files, not exporter, safe bundles or calibration. Preserve it.

Read `AGENTS.md`, `CLAUDE.md`, `docs/DEVELOPMENT_RULES.md` and the [published prior audit](https://github.com/Polalalabear/amidst/blob/65f5b6e6131cb1507b1ee1c287315399a524d58e/docs/engineering/WORKBENCH_2D3D_ROOT_CAUSE_AUDIT.md). Findings here are independently reproduced rather than inherited from that audit.

CONFIRMED: PID 25413, listener `127.0.0.1:65262`, cwd this checkout, existing finalization Python running `scripts/start_office_demo.py --_serve`. `/__office_launcher.commit` is **57eab7e**, while HTTP `scene.mjs` and `physical-review.mjs` match **3cc3f68**. The service reads frontend files per request (`service.py`, `Application._dispatch`, 1178–1182); startup metadata is not a live whole-application version certificate. No restart or branch switch was performed. `start_office_demo.py:56–66,132–137` rejects other branches / changed startup fingerprints: current Task B branch is a reproducible relaunch obstacle, separate from geometry repair. A later owner-approved demo lifecycle step must resolve it before acceptance.

Source references below are to inspected **3cc3f68**, not the documentation branch's main base. [Inspected source tree](https://github.com/Polalalabear/amidst/tree/3cc3f6885246ebdffc1af3315347341cc81707b2). JSON references use exact field paths; no invented JSON line numbers.

| Input ID | Existing local input / independently verified SHA-256 |
| --- | --- |
| S | Canonical `blender/school_v3.blend`: `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`; 468,300,506 bytes; mtime_ns `1791198236746106977` unchanged before/after background probes |
| G | Evidence `data/scene_audit/phase1_physical_policy_approval_20261006/source_evidence.json.gz`: `6d30e591d6210707f2b6175bf96dc2fe2395fe0202b24bd0a6df7ee87a5d997c` |
| H | Same directory `floor_support_details.json.gz`: `6a37b041a368e3e576da4c3f3894708462c0504956f82ad599082acd816b23d0` |
| K | `configs/architectural_scale_school_v3.json`: `7e3615a3b0b4485585da9c0f7beefb96955517f7a321910fc008c041f99a3eaf` |
| O | Evidence `data/engineering/local_run/blender_camera_v1/office/safe_inputs.json`: `1ea62def6c843b3bae1c5e25584fa489915f08e678b28b6220dc88cc17b43163` |
| A | Sibling `auditorium/safe_inputs.json`: `9555df8e0947a0eb951c2d21d63687ac81033748178d397e45e5221a4f7f321c` |
| E | `scripts/export_policy_source_evidence.py`: `f27a559c2243fa8baaaa70d03e0f5a7b662412b58d3af123b8ebd0c5e36fa9d2`, matches G.exporter_code_sha256. Selection config canonical JSON hash `07153554c4306f0ab0e09d9b341a2dd6c33534695310e09c979d52a649e4126f`, matches G.config_content_sha256 |
| I | Final bounded source inventory, local temporary output: `f87663045286ad5fbae69f2314e6ac4b904943d5bf6cbb0d2153463562ef4a76`; 368,244 bytes, Blender `5.2.1 LTS`, build `9e2066aef7ef`. Reproduce, do not assume temporary output persists |

Canonical root is `/Users/polalabear/Developer/amidst`; evidence root is its existing `.local-worktrees/phase1-finalization`. These are existing prerequisites, not new worktrees or assets distributed by this PR. Dataset hashes below are **recorded bindings in O/A**, not a fresh audit of dataset/media contents; no RGB, observations or GT were combined or regenerated.

## Verified data flow and first exclusion

| Stage / status | Exact source / function / inspected lines | Observed behavior |
| --- | --- | --- |
| S → evaluated scene, CONFIRMED | `scripts/export_policy_source_evidence.py`, `main`, 158–181,196–208; `selection_regions`, 87–144; `configs/physical_policy_source_selection_school_v3.json:14–26` | Scene `Scene`, frame 220/subframe 0. Full evaluated local coordinates transformed with evaluated.matrix_world. All scene.objects inspected regardless of hidden state; explicit audited annotations/helpers excluded. ROI list includes Office/corridors/CLASS201/stairs, **no Auditorium full-body region**. |
| First furniture loss, CONFIRMED | Same `main`, 211–217; G.regions and G.meshes; I.objects[*].evaluated_bounds_m | All **94 furniture mesh AABBs miss all 26 archive regions**; `if not relevant: continue` removes them **before budgets/export**. G contains none of their exact object names. None match G.excluded_annotation_object_ids or have phase1_annotation_only=true, so the earlier annotation exclusion does not apply. The source furniture is present and visible. This is not a missing `.blend` asset or renderer-only failure. |
| Archive → display selection, CONFIRMED | `blender_scene.py`, `_pinned`, 108–118; `_source_meshes`, 148–167 | G has 660 objects / 1,548,921 full-object triangles, not a whole scene. Hard allowlist selects `group_0` and `group_0.002` only. Auditorium-intersecting archive object `group_0.263` is omitted here, even though already available. |
| First room-context loss in selected building meshes, CONFIRMED | `_source_meshes`, 153–162,174–213,224–233 | Site-specific approved-support XY bounds plus 0.5 m, floor−0.02 m to floor+2.8 m. Six-plane clipping, triangulation, no caps; scaling 0.0247 m/BU. Office's crop removes Auditorium-side building triangles. Furniture could not return here because already absent from G. |
| Materialized presentation → safe inputs, CONFIRMED | `materialize_blender_workbench`, 325–339,362–371,407–425 | Source/archive/scale pins → `_source_meshes(..., site)` → safe_inputs.presentation. This audit called only the pure crop function in memory; did not run materialization. |
| Safe inputs → snapshot/API, CONFIRMED | `BlenderSceneAdapter.__init__`, 445–450,475–489,491–527; `snapshot`, 592–594; `scenes.py:509–510`; `service.py`, action `scene`, 771–783 | Loads pinned bundle, camera point objects from calibration, deep-copies presentation into snapshot; research `/api/scene` returns it. Runtime presentation equals **all** O.presentation fields exactly. |
| API → Three.js, CONFIRMED, code/data boundary | `app.mjs`, `loadScene`, 181–187 and SceneView options 1078–1082; `scene.mjs`, `setData`, 98–112; `addSourceMeshes`, 415–426 | Supplied vertices/index triangles become BufferGeometry; no missing-furniture recovery or object-name selection. All O indices/vertices valid. Renderer receives already incomplete geometry. This is not WebGL visual acceptance. |

`selected_objects_complete=true` means the two selected objects were available before cropping; `truncated=false` means no budget truncation in that display operation. Neither flag means complete room, furniture, roof, occlusion or navigation coverage.

## Counts, cameras and coordinate compatibility

CONFIRMED by reproduction R1: `_source_meshes(G,H,site)` equals the existing presentation **including hashes, arrays and metadata**, not just triangle counts.

| Presentation | Mesh triangles (`group_0` / `group_0.002`) | Actual vertex bounds metres, min → max |
| --- | --- | --- |
| Office O | 1,592 / 70 = **1,662** | `[27.7815,41.7370,0.47594759]` → `[37.4265,57.5570,3.29594759]` |
| Auditorium A | 286 / 32 = **318** | `[37.0440,38.4025,0.47594759]` → `[50.60939169,57.59680483,3.29594759]` |

A.presentation.bounds_metres is the **crop box**, max `[50.6410,57.6805,3.29594759]`, slightly larger than actual vertices. Do not confuse crop metadata with mesh occupancy. G also has `group_0.263`, 78 triangles; its AABB overlaps A but no triangles from this object are in O/A.

| Camera, identical O/A calibration and S world location | Position metres |
| --- | --- |
| `CAM_1F_AUDITORIUM_FRONT` | `[50.02349409179688,57.16834296875,3.784387042236328]` |
| `CAM_1F_AUDITORIUM_REAR` | `[50.012678796386716,39.042655615234374,3.784830267333984]` |

CONFIRMED: both cameras are >12.58 m beyond Office's max X, and above its max Z; REAR is also below min Y. Both are inside A's XY crop but above its Z cap. Camera installation **coordinates** are verified; bracket/housing hardware geometry is UNKNOWN. `boundsOf` (`scene.mjs:52–59`) prefers snapshot.bounds over objects; `SceneView` uses that box for initial framing (72–84). Loading extra meshes without updating display framing is insufficient.

CONFIRMED: O/A share S, G, K, `SOURCE_SCENE_FRAME_220`, `METRES`, `NATIVE_BU`, 0.0247 m/BU; every calibration field matches by camera ID. `camera_ref` differs because run-scoped, so the entire camera DTO arrays correctly differ. S.scene.unit_settings is METRIC, scale_length=1; this native UI setting does **not** replace the independently approved research scale. `_calibration` (`blender_scene.py:129–145`) scales only translation/clips; G exports world-transformed vertices; Three.js uses those XYZ directly with Z-up (`scene.mjs:66–68`). **No undocumented alignment transform is needed for these display assets.**

O/A keep distinct run IDs `blender-pilot-office-baseline-v1` / `blender-pilot-auditorium-baseline-v1`, dataset bindings `2367ecc30c05740e64320130237878315034f61b6b91ec92979fd2deba8619c4` / `b298220834b8e7b239a59cd64628aedf555639a09cff801ec6f3849d122ca93f`, same named 5 Hz clock. This permits common source geometry, **not** exchanging frames, observations, tracks, GT or run identity.

## Source inventory and coverage

CONFIRMED by R2: Scene has 2,873 objects; bounded MESH/CAMERA/EMPTY AABB query `[37.044,38.4025,0.47594758]` → `[50.641,57.6805,4.2]` returns 133 objects. It includes 80 chair meshes + 16 parent empties, 14 lectern meshes + 1 parent empty, 11 other source meshes, 8 annotations/support helpers, 3 camera objects. No collection instances in this returned set. This is a bounded inventory, not an exhaustive survey of every source type, upper floor, roof, outside-ROI object or dependency-graph instance.

Geometry, not labels alone: a small diagnostic line projection of the five unsubdivided representative chair parts shows seat pad, upright back, arms and support foot. The `Main Board`/inner boards/doors/microphone projections show a sloped-top lectern with microphones. Evaluated bounds match base bounds within 1e-5 m for all 94 meshes. Repeated chair assemblies occupy four X columns and four Y rows. Exact evaluated-local geometry hashes establish repeated source mesh equivalence; armrests have **two** hash variants, not one. No name-based semantic/physical authority was assigned.

| Coverage category / status | Result |
| --- | --- |
| Existing display geometry, CONFIRMED | O/A each contain only clipped `group_0` / `group_0.002`. A is useful partial architecture, insufficient for the requested furnished environment. |
| Existing source furniture missing from display, CONFIRMED | 16 five-part chairs (80 meshes, **528,784** evaluated triangles), one 14-part lectern (**82,814**); **611,598** total, none in G/O/A. Exact part inventory below. |
| Exporter exclusions, CONFIRMED | All 94 miss G.regions, so excluded at E:211–217. `group_0.263` survives G but fails display allowlist. Office XY and both sites' height cap exclude further building geometry intentionally. |
| Source room/floor/walls, CONFIRMED partial / UNKNOWN complete | Real source triangles exist in `group_0`; source-support H for `WALK_1F_AUDITORIUM` includes `group_0` and 16 `Pied` surfaces at 20.07884979248047 BU (~0.49594759 m). Annotation `AREA_1F_AUDITORIUM` is not room geometry. Full wall/roof/aperture correspondence was not certified. `group_0.263` is a low slab candidate, not automatically an approved floor. |
| Source unavailable/unverified, UNKNOWN | All other Auditorium furnishings beyond this source-bound ROI, complete room envelope, real installation hardware, source rendering visibility/appearance, physical clearance. Nothing here proves whole-scene completeness or real-world dimensions. |

All 94 furniture meshes: object hide_render/hide_viewport/hide_get = false, visible_get = true; direct collections hide_render/hide_viewport = false. They are not lost because of these visibility flags. Chair collection is `Theatre Chair`; parent names map by identical suffix. Lectern collection/parent is `N1 Hamburg`. Both parents are EMPTY, not geometry. Rows below report evaluated world AABBs in metres (rounded to 3 decimals); exact matrices, flags, parts and bounds are reproduced in I.

### Exact bounded furniture inventory

Each suffix below applies to **all five** mesh names `Accoudoir`, `Assise`, `Dossier`, `Fond Dossier`, `Pied`; parent is `Theatre Chair` with the same suffix. Collection `Theatre Chair`; all excluded at E:211–217; none in current presentation. This explicitly enumerates the 80 mesh identities without treating parent empties as seats.

| Suffix / parent suffix | Five-part assembly world AABB m |
| --- | --- |
| `(none)` | `[42.919,54.010,0.496] → [43.798,55.100,1.961]` |
| `.001` | `[41.909,54.010,0.496] → [42.789,55.100,1.961]` |
| `.002` | `[39.924,54.010,0.496] → [40.803,55.100,1.961]` |
| `.003` | `[40.933,54.010,0.496] → [41.813,55.100,1.961]` |
| `.004` | `[40.933,51.583,0.496] → [41.813,52.673,1.961]` |
| `.005` | `[39.924,51.583,0.496] → [40.803,52.673,1.961]` |
| `.006` | `[41.909,51.583,0.496] → [42.789,52.673,1.961]` |
| `.007` | `[42.919,51.583,0.496] → [43.798,52.673,1.961]` |
| `.008` | `[42.919,46.954,0.496] → [43.798,48.044,1.961]` |
| `.009` | `[41.909,46.954,0.496] → [42.789,48.044,1.961]` |
| `.010` | `[39.924,46.954,0.496] → [40.803,48.044,1.961]` |
| `.011` | `[40.933,46.954,0.496] → [41.813,48.044,1.961]` |
| `.012` | `[40.933,49.381,0.496] → [41.813,50.471,1.961]` |
| `.013` | `[39.924,49.381,0.496] → [40.803,50.471,1.961]` |
| `.014` | `[41.909,49.381,0.496] → [42.789,50.471,1.961]` |
| `.015` | `[42.919,49.381,0.496] → [43.798,50.471,1.961]` |

All lectern rows: type MESH, parent/collection `N1 Hamburg`; flags described above; excluded at E:211–217, not in G/O/A.

| Exact object name | World AABB m | Evaluated triangles |
| --- | --- | --- |
| `Cable Opening` | `[47.087,54.209,1.745] → [47.560,54.618,1.766]` | 3,072 |
| `Door.l` | `[47.683,54.558,1.240] → [48.034,54.856,1.746]` | 300 |
| `Main Board` | `[46.864,53.991,0.521] → [48.049,55.154,2.006]` | 1,548 |
| `Mic holders` | `[47.129,54.287,1.765] → [47.758,54.828,1.771]` | 4,224 |
| `XRL port` | `[47.382,54.612,0.708] → [47.454,54.675,0.742]` | 5,680 |
| `base opening` | `[47.466,54.597,0.623] → [47.696,54.812,0.638]` | 636 |
| `conference mic L` | `[47.705,54.311,1.763] → [47.871,54.503,2.320]` | 12,840 |
| `conference mic R` | `[47.151,54.776,1.763] → [47.317,54.968,2.320]` | 12,840 |
| `door.r` | `[47.344,54.842,1.240] → [47.695,55.141,1.746]` | 300 |
| `holder 1` | `[47.366,54.501,0.690] → [47.582,54.685,0.759]` | 3,254 |
| `inner boards` | `[46.884,54.010,0.621] → [48.037,55.143,2.003]` | 3,616 |
| `light` | `[47.222,54.343,1.957] → [47.508,54.585,1.978]` | 1,148 |
| `speakon 2` | `[47.497,54.507,0.705] → [47.574,54.575,0.740]` | 3,740 |
| `wheels` | `[47.063,54.190,0.496] → [47.899,55.014,0.622]` | 29,616 |

Other relevant source objects (type MESH, collection `Collection`, all visible with render/viewport flags false; parent none unless shown):

| Exact object / parent | World AABB m | Presentation inclusion / reason |
| --- | --- | --- |
| `group_0` / `none` | `[5.280,5.341,0.000] → [50.609,57.597,7.984]` | O/A clipped subset |
| `group_0.002` / `none` | `[36.252,41.586,0.496] → [37.370,49.165,3.802]` | O/A clipped subset |
| `group_0.127` / `none` | `[37.370,38.614,3.997] → [40.596,39.835,7.984]` | Absent from G; no archive ROI intersection (E:211–217) |
| `group_0.263` / `none` | `[28.252,38.566,0.000] → [50.609,57.596,0.496]` | Present in G; excluded at display allowlist (165) |
| `group_0.341` / `none` | `[50.562,38.613,3.802] → [50.562,38.614,3.802]` | Absent from G; no polygons (E:203–204) |
| `group_0.358` / `none` | `[37.370,57.597,3.802] → [37.370,57.597,3.997]` | Absent from G; no polygons (E:203–204) |
| `instance_189` / `group_0` | `[37.939,57.316,3.997] → [40.858,57.410,5.460]` | Absent from G; no archive ROI intersection (E:211–217) |
| `instance_190` / `group_0` | `[42.312,57.308,3.997] → [45.230,57.402,5.460]` | Absent from G; no archive ROI intersection (E:211–217) |
| `instance_191` / `group_0` | `[46.636,57.308,3.997] → [49.554,57.402,5.460]` | Absent from G; no archive ROI intersection (E:211–217) |
| `instance_192` / `group_0` | `[50.273,53.365,3.997] → [50.367,56.283,5.460]` | Absent from G; no archive ROI intersection (E:211–217) |
| `instance_193` / `group_0` | `[50.273,47.440,3.997] → [50.367,50.358,5.460]` | Absent from G; no archive ROI intersection (E:211–217) |

Annotation/support identities in this ROI: `AREA_1F_AUDITORIUM`, `AREA_1F_SIDE_ENTRANCE`, `PORTAL_1F_AUDITORIUM`, `PORTAL_1F_AUDITORIUM_OFFICE` (collection `Areas`, collection hide_render=true); `WALK_1F_AUDITORIUM`, `WALK_1F_AUDITORIUM_OFFICE_THRESHOLD`, `WALK_1F_AUDITORIUM_THRESHOLD`, `WALK_1F_SIDE_ENTRANCE` (`WALKABLE_AREAS`). None are presentation furniture/room authority. Camera objects include the two tabled Auditorium cameras plus `CAM_1F_SIDE_ENTRANCE` at `[43.937,38.575,3.495]`, collection `Cameras`; the third is not part of the Office fixture.


## Minimal demo-safe repair proposal (not implemented)

READY_TO_FIX applies to displaying the verified architecture + 16 chairs + lectern, while keeping `PARTIAL_DISPLAY_CONTEXT`. It does not assert every Auditorium source object is mapped. No proposed dependency requires unknown spatial alignment or invented furniture.

1. Keep original O, fixture hash, source assets and research inputs immutable. Build an **optional Office display-only companion** with S/G/K, Scene/frame 220/subframe 0, exporter version/code hash, exact object IDs, evaluated geometry hashes and source world matrices. Reuse A.presentation architecture only, not its run/media/observation DTOs. Use it as the Office demo's selected background context rather than blindly concatenating overlapping Office/Auditorium crops (duplicate faces/seams).
2. Explicitly extract only the 94 verified furniture meshes from S in an unsaved process, all modifiers evaluated, with bounded output. Reuse exact identical evaluated-local meshes with source transforms; **19 unique geometry hashes / 117,103 unique triangles** across 94 objects (611,598 triangles when expanded). Keep the two armrest variants separate. No arbitrary alignment, recentering, calibration edit or decimation. Only world-unit normalization is `local → matrix_world → ×0.0247`.
3. Existing A already supplies source-supported partial floor/wall context. Do not promote `group_0.263` or annotations to physical geometry. If visually useful, that existing slab may be added only as source-bound display context after a focused face check; it is **not a prerequisite** of this minimal proposal. No rebuild of G/physical evidence or complete scene datasets is required.
4. Validate companion source/scale/model hashes before attaching its presentation layer to the Office snapshot. Reject missing/mismatched assets; no silent fallback to foreign-run RGB. Office source/run/clock, projections, candidates and physical-source loader stay unchanged. Frame both Auditorium XY and camera Z, keeping labels and PARTIAL status visible. Exact geometry sharing may use InstancedMesh; preserve source-instance IDs/matrices and dispose GPU resources.

Proposed narrowly scoped files for a **separately authorized repair** (this audit changes none of them):

| File | Purpose |
| --- | --- |
| `scripts/materialize_office_display.py` (new) | Explicit bounded source extraction; no render/save; separate companion output |
| `configs/office_demo_display_v1.json` (new) | Verified source/object allowlist, display provenance and resource limits |
| `src/amidst/workbench/office_display.py` (new) | Fail-closed companion validation/attachment, presentation only |
| `scripts/office_demo_backend.py` | Attach optional companion at Office scene creation, preserving original bundle/fixture |
| `frontend/workbench/scene.mjs` | Render exact geometry instances and frame display context/cameras |
| `tests/workbench/test_office_display.py` (new), `frontend/workbench/scene.test.mjs` | Focused boundary, provenance, instance/bounds/resource regression checks |
| Local ignored `data/engineering/local_run/office_display_v1/` | New small display companion only, no committed raw asset or overwrite |

Lifecycle issue: `scripts/start_office_demo.py` needs a separately reviewed branch/version policy adjustment or an owner-coordinated return to its supported branch after Task B integration. Do not switch the active checkout or fold that change into this audit. This remains a gate for a stable relaunch, not a geometry-alignment uncertainty.

## Reproduction and falsifiable evidence ledger

R0 (read-only repository/runtime checks):

```sh
cd /Users/polalabear/Developer/amidst-claude
git status --short --branch
git rev-parse HEAD
git remote -v
git diff --stat 57eab7eae6ea27fb75a3bf7ad3e460e7caee3675..HEAD
git worktree list --porcelain
gh pr view 4 --json state,isDraft,baseRefName,baseRefOid,headRefName,headRefOid
ps -p 25413 -o pid,ppid,lstart,command
lsof -a -p 25413 -d cwd
lsof -nP -a -p 25413 -iTCP -sTCP:LISTEN
df -h . /private/tmp
```

R2 then R1 (existing executable/environment; no dependency install; choose a fresh output path; missing/hash-mismatched prerequisites mean BLOCKED):

```sh
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --factory-startup --disable-autoexec \
  /Users/polalabear/Developer/amidst/blender/school_v3.blend \
  --python-exit-code 2 --python scripts/audit_auditorium_source.py \
  -- /private/tmp/amidst-auditorium-inventory-reproduction.json

UV_CACHE_DIR=/private/tmp/amidst-auditorium-uv-cache PYTHONDONTWRITEBYTECODE=1 \
  /opt/homebrew/bin/uv run --offline --no-project \
  --python /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/.venv/bin/python \
  python scripts/audit_auditorium_geometry.py \
  --repo /Users/polalabear/Developer/amidst-claude \
  --evidence /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization \
  --canonical /Users/polalabear/Developer/amidst \
  --inventory /private/tmp/amidst-auditorium-inventory-reproduction.json \
  --url http://127.0.0.1:65262
```

R1 optional `--url` creates a transient research authentication session and reads `/api/scene` and static assets; no observation/inference/materialization action. Omit it for an offline audit. R2 writes only a capped (<1 MiB) inventory with hashes/counts/matrices and small sampled edge profiles; no full furniture mesh dataset. Guards S hash, Scene/frame and >=2 GiB free disk; uses exclusive output creation. Source save/render is absent. Small geometry line profiles are diagnostic projections, not regenerated source RGB.

| Claim / status | Inputs; reproduction; expected → observed | Falsification criterion / limitation |
| --- | --- | --- |
| C1 CONFIRMED: counts/crops | O,A,G,H,K; R1; 1,662/318 and identical parsed presentation → exact equality PASS | Any unequal field/triangle/geometry hash refutes reproduction. Counts alone do not prove visual completeness. |
| C2 CONFIRMED: cameras outside Office | O,A,S; R1 camera XYZ; R2 I camera matrix_world; expected same source positions, Office X/Z outside → observed | Different source-scaled locations or Office enclosing both positions refutes. Does not prove calibration accuracy, coverage or hardware. |
| C3 CONFIRMED: 94 source furniture meshes | S,I; R2; 80+14, shown flags, source unchanged → 133 bounded objects / 611,598 furniture triangles | Missing parts, hash drift, different frame/bounds or hidden flags refute. Shape check uses representative profiles plus part equivalence, not labels; whole source inventory outside ROI UNKNOWN. |
| C4 CONFIRMED: earliest furniture loss | E,G,I; R1 --inventory; 0 names in G and 0 evaluated AABB/region intersections → PASS | Any relevant region intersection or included object refutes this exclusion reason for that object. Annotation identity/budget paths remain separate; no claim every missing object in scene shares this reason. |
| C5 CONFIRMED: display compatibility | O,A,G,K,S; R1; equal source/model/scale and every calibration field, distinct runs → PASS | Source/scale/frame/coordinate mismatch blocks reuse. Camera DTO refs differ intentionally. Never combine separate-run science inputs. |
| C6 REFUTED: 318 triangles restore furniture | A.presentation.meshes.derivation.source_geometry_sha256 maps only to G's two building meshes; C3/C4 | A containing any of these 94 mesh geometries would refute. Furniture embedded elsewhere beyond bounded inventory remains UNKNOWN. |
| C7 CONFIRMED: loss before renderer | O + runtime; R1 --url; exact snapshot.presentation equality and served bytes equal checkout → PASS | Complete source furniture already in API or mismatched served code refutes present diagnosis. Code/API success is not GPU/visual correctness. |
| C8 CONFIRMED: mixed running version | R0 + R1; start 57eab7e, served scene/physical-review equal 3cc3f68 → observed | Runtime restart/coherent hashes falsify this current snapshot. No server process was altered. |
| C9 UNKNOWN: repair speed / full room / 8-minute stability | No repaired artifact or timed browser run in this task | Only source-bound repair + browser criteria below can resolve it. READY_TO_FIX is not READY_TO_DEMO. |

Observed served SHA-256: app `80d740f6c804c7e8e3c81aae292493a276a070fcaaa76e00b559c1cfef9d0ee5`; scene `984ed63ec1fd3b8c7ef3635ba38b13eb5247d53796073eca936d1482ae7c4174`; physical-review `d03fdd17b1df92bca36e67460f8f3b5dea52f670937331bb17f5aa6784fabb44`. Runtime API retained 2 cameras / 100 frames / 31 observations. No repaired browser result is inferred from those counts.

CONFIRMED documentation validation: both final probes passed; the final source probe reproduced the bounded inventory and immutable-source fingerprint; R1 passed annotation/ROI/visibility/mesh-sharing/camera checks and exact API presentation equality. Python syntax compilation, focused Ruff checks, exact diff review and temporary-index `git diff --check` passed. No application suite was run.

## Subsequent regression and browser acceptance

Proposed regression tests: original O/fixture/calibration/data hashes unchanged; companion source/scale/frame/hash mismatch and invalid matrices/indices fail closed; 94 explicit source IDs, 16 chair parents and 14 lectern parts, both armrest variants, geometry sharing reproduces each original evaluated world bbox; correct normalization exactly once; no helper-as-mesh or new physical authority; source/run/observation/candidate DTOs unchanged; display bounds include cameras; repeated setData/dispose releases instances/edges; Task B marker discontinuity tests still pass. Commands after repair: `uv run pytest tests/workbench/test_office_display.py tests/workbench/test_blender_scene.py`; `node --test frontend/workbench/scene.test.mjs frontend/workbench/physical-review-continuity.test.mjs`; `git diff --check`. These application tests were **not run by this documentation task**.

Browser gate on a coherent, owner-coordinated local restart: verify actual PID/listener/served hashes; cold load the Office fixture; see all four rows × four seats, identifiable sloped lectern and source floor/wall context, both camera markers/frusta, no unexplained shifts or duplicate crop faces; retain PARTIAL and UNKNOWN authority labels. Orbit/front/rear/top views must show the selected furniture in its source world location, not simply return HTTP 200. Run 8 continuous minutes including timeline replay, scrubbing 4.4/4.6/8.4/8.6 s, reconstruction/review toggles, orbit/zoom and reload. Require no uncaught console errors, missing assets, WebGL context loss, disappearing geometry or growing GPU allocations after repeated mount/unmount; record cold-load time, FPS/frame times and memory on this machine. Treat >2 s UI stalls or inability to orbit/scrub at >=30 FPS as a demo-budget failure requiring a smaller **source-verified** presentation, not hidden scientific changes. These thresholds are proposed acceptance criteria, not measurements.

## Safety and documentation delivery

CONFIRMED: approximately 13 GiB free at start and 12 GiB at final check; no clone/worktree/venv, source copy, full-scene render, media regeneration, dependency installation, asset/cache deletion or application change. Sandboxed Blender first crashed in Metal startup (1.5 KiB crash log, before source load); approved background execution succeeded. One diagnostic-output attempt exceeded the 1 MiB guard and exited before writing; reducing edge sampling produced bounded output. All successful source runs checked S hash/size/mtime unchanged. Raw inventories/diagnostic PNG remain temporary and are not committed.

Documentation uses a separate temporary Git index and commit-tree on verified `main` (`f9b563fffcfeabeeb828ccff924a81420da6b88f`), without switching the running checkout or touching Task B's ref/index. The two probe dependencies (`blender_scene.py`, `source_presentation.py`) and pinned exporter/config match that main base. Only this report, two read-only probes and a documentation-index entry belong in the documentation branch `docs/auditorium-geometry-audit`. Review exact tree diff and run `git diff --check` before commit/push. Publish a Draft PR to main; do not merge. Commit/PR receipt is reported separately so this document does not contain a self-referential commit hash.
