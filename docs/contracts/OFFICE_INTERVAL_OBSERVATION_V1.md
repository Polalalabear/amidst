# Office Demo interval-observation contract v1

Status: **v1.1 DRAFT** for Codex confirmation, 2026-10-17 (task K0 revision of the
CP1-approved v1, merged at `dcb89f4`; the file name stays `_V1`, see
[Revision 2026-10-17 (v1.1)](#revision-2026-10-17-v11)). Additive to the
existing observation records and to the Task 3 `contact_quality` flag in the
[Office demo plan §8](../agents/OFFICE_DEMO_PLAN_20261101.md#任務-3工作台多場景預設接地點品質旗標).
No existing field, position, state, endpoint or assertion changes. Items marked
**OPEN** need Codex confirmation; names not found in
[OFFICE_DEMO_TARGET_V1](OFFICE_DEMO_TARGET_V1.md) or the
[pipeline map](../engineering/OFFICE_PIPELINE_MAP.md) are marked `UNKNOWN`.

Related drafts: [blind hypothesis v1](OFFICE_BLIND_HYPOTHESIS_V1.md) consumes this
object as its endpoint state; [frame retrieval v1](OFFICE_FRAME_RETRIEVAL_V1.md)
consumes nothing from it directly.

## 1. Purpose and authority

This contract describes the output of the hybrid ground-contact estimator
([plan §3.1](../agents/OFFICE_DEMO_PLAN_20261101.md#3-方法觀測--假設--檢索--驗證)):
for one image observation, a ground estimate that is either

- a **POINT**: the foot (contact pixel) is visible and its floor intersection is
  usable; or
- a **SEGMENT**: the foot is not usable as a point. Either the foot is believed
  hidden (`CONTACT_OCCLUDED`), so the head ray is intersected with a configured
  height range and the resulting floor interval is clipped by occluder geometry
  and the walkable area (`HEAD_RAY_HEIGHT_PRIOR`); or the foot is visible but its
  ray meets the floor at a grazing angle (`LOW_INCIDENCE` only), so the foot ray
  is widened by a declared pixel band (`FOOT_RAY_PIXEL_BAND`, v1.1, R1, D17).

The object is named `ground_estimate`. It is attached next to an existing
`observation_ref`; it is a quality-annotated projection of that same image
measurement, **not a new position authority**:

- `ground_estimate.evidence_state` is always `PROJECTED_OBSERVATION`. No new
  position state is introduced.
- The observation record's existing `world_position`, `projection_status`, motion
  curve state (`PROJECTED_OBSERVATION`, `INFERRED_INTERPOLATION`, `MISSING`, ...)
  and the `blender-office` 31-observation assertion are unchanged. A sample that is
  `MISSING` in the motion curve stays `MISSING` even when a SEGMENT exists
  (see OPEN IO-Q2).
- Consumers must not collapse a SEGMENT to its midpoint or any single point, must
  not write it into `world_position`, and must not smooth or extrapolate it.
- `identity_verdict` stays `UNCONFIRMED`; physical navigation/collision stays
  `UNKNOWN`. The walkable clip uses an annotation, not a navigation certificate.

## 2. Conventions

| Item | Rule |
| --- | --- |
| Positions | Source world axes, right-handed, Z-up, **METRES**. Floor points carry `z = floor_z_m` of the source-bound floor plane (Office 1F: `0.4959475898742676`). |
| Time | Source clock **SECONDS** (`timestamp_s`); clock id as in the bundle (Office: `BLENDER_PILOT_CONFIGURED_SECONDS_5HZ`). |
| Pixels | Image pixel coordinates `[u, v]`, origin top-left, as used by `contact_pixel` in `perception.py`. |
| Lengths | `*_m` fields are metres; `*_m_per_px` are metres of floor displacement per pixel. |
| Unknown values | `null` with a `reason`; never `0`, never a default position. |
| Hashes | Lowercase hex SHA-256. `output_sha256` hashes the canonical JSON of the object with `output_sha256` removed (canonicalisation: OPEN IO-Q7). |

### 2.1 Provenance block (shared by all three K0 contracts)

```json
{
  "provenance": {
    "scene_id": "blender-office",
    "run_ref": "UNKNOWN",
    "clock_id": "BLENDER_PILOT_CONFIGURED_SECONDS_5HZ",
    "source_sha256": "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e",
    "safe_inputs_sha256": "1ea62def6c843b3bae1c5e25584fa489915f08e678b28b6220dc88cc17b43163",
    "producer": "hybrid-ground-estimator",
    "producer_version": "v1",
    "config_sha256": "<sha256 of the estimator config incl. height prior>",
    "annotation_sha256": {"occluders": "<sha256|null>", "walkable": "<sha256|null>"},
    "run_parameters": {
      "declaration_source": "PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT",
      "declaration_ref": "<per-run setting ref>",
      "declaration_sha256": "<sha256>",
      "target_proxy": {"shape": "CYLINDER", "height_m": 1.70, "radius_m": 0.25, "label": "SYNTHETIC_CYLINDER_PERSON_SIZED"},
      "head_height_prior": {"nominal_m": 1.70, "tolerance_m": 0.10},
      "body_radius_m": 0.25,
      "foot_anchor_band_px": 2
    },
    "gt_read": false
  }
}
```

`run_ref`: the existing field that names the simulation run inside a bundle is
`UNKNOWN` to this draft (OPEN IO-Q6). `gt_read` must be `false`; a producer that
cannot assert this must not emit the object.

`run_parameters` (decisions D5, D6): the head-height prior (with tolerance) and
the body radius are **per-run declared values**, not scene-wide constants and
never GT. They are declared before predictions are frozen (the same pattern as
`PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT` in `configs/office_contact_v2.json`),
hashed in `declaration_sha256`, and echoed unchanged into every K0 output of that
run (all three contracts carry the same block). For `HEAD_RAY_HEIGHT_PRIOR`, a
producer that cannot find the declaration for the run must not emit the object
(`HEIGHT_PRIOR_UNAVAILABLE`). **This does not apply to `FOOT_RAY_PIXEL_BAND`**: that
basis does not read the head-height prior (§4.2a step 6), so a missing, `UNKNOWN`
or invalid head prior never blocks it; it needs only `foot_anchor_band_px` and
`body_radius_m` of the declaration and otherwise answers `FOOT_BAND_UNAVAILABLE`
(§5). Values by run:

| Run | `target_proxy` | `head_height_prior` | `body_radius_m` |
| --- | --- | --- | --- |
| New runs (C6, D4/D5/D6) | cylinder, height 1.70 m, radius 0.25 m, label `SYNTHETIC_CYLINDER_PERSON_SIZED` | 1.70 m ± 0.10 m | 0.25 |
| Existing Office run | declared height 2.9393 m, radius 0.1482 m, label `SYNTHETIC_CYLINDER_NOT_HUMAN_SIZED` | nominal 2.9393 m; **tolerance not decided (UNKNOWN)** — to be declared before use | 0.1482 (origin `UNKNOWN`) |

The origin of 2.9393 m (intentional or a ×0.0247 scale issue) and of 0.1482 m is
`UNKNOWN`; it is checked in task C7.

`foot_anchor_band_px` (v1.1, D17): half-width `k` in pixels of the foot-ray band
(§4.2a), a number `≥ 1`, proposed 2 for **every** run (new runs and the existing
Office run, OPEN IO-Q9). Like the other run parameters it is declared before
predictions are frozen, as `PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT`, hashed
in `declaration_sha256`, and must not be tuned against GT or evaluation results.
It is read only by the `FOOT_RAY_PIXEL_BAND` basis; the head-height prior is not
needed for that basis (§4.2a step 6).

## 3. `ground_estimate` object

Schema id: `office-demo.interval-observation.v1`.

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `schema_version` | string | yes | `office-demo.interval-observation.v1` |
| `observation_ref` | string | yes | Existing public observation ref (e.g. `observation:add9f687d311742321e80dff`). Must resolve in the same scene/run. |
| `camera_id` | string | yes | Source camera id (e.g. `CAM_1F_AUDITORIUM_FRONT`). |
| `timestamp_s` | number | yes | Source clock seconds of the frame. |
| `status` | enum | yes | `READY` or `UNKNOWN`. |
| `reason` | string\|null | yes | `null` when `READY`; one code from §5 when `UNKNOWN`. |
| `evidence_state` | enum | yes | Always `PROJECTED_OBSERVATION`. |
| `estimate_kind` | enum | yes | `POINT`, `SEGMENT`, or `NONE` (only with `status: UNKNOWN`). |
| `basis` | enum | yes | `FOOT_POINT` (POINT), `HEAD_RAY_HEIGHT_PRIOR` (SEGMENT), `FOOT_RAY_PIXEL_BAND` (SEGMENT, v1.1), `NONE`. |
| `point_m` | `[x,y,z]`\|null | yes | Floor point; non-null only for `POINT`. |
| `segment` | object\|null | yes | Non-null only for `SEGMENT`; see §3.1. |
| `image_anchor_px` | `[u,v]` | yes | Pixel used: contact pixel for POINT and for `FOOT_RAY_PIXEL_BAND` (§4.2a); head pixel for `HEAD_RAY_HEIGHT_PRIOR` (§4.2). |
| `pixel_sensitivity_m` | number\|null | yes | Floor displacement for a ±1 px change of `image_anchor_px` (§4.4). |
| `constraints_applied` | array | yes | Ordered list of §3.2 entries; empty for POINT. |
| `contact_quality` | object | yes | Verbatim copy of the Task 3 `contact_quality` object for this observation (same `version`). |
| `authority` | string | yes | `PROJECTION_ONLY_NOT_POSITION_AUTHORITY`. |
| `identity_verdict` | string | yes | `UNCONFIRMED`. |
| `physical_authority` | string | yes | `UNKNOWN`. |
| `provenance` | object | yes | §2.1. |
| `diagnostics` | object | yes (v1.1) | §3.3. Diagnostic only; never a position or endpoint (R2). |
| `output_sha256` | string | yes | §2. Covers `diagnostics`. |

`schema_version` stays `office-demo.interval-observation.v1` in v1.1: the revision
adds enum values (`basis`, `constraints_applied[].kind` and `.effect`), optional
segment fields and `diagnostics`. A consumer must treat an enum value it does not
know as unusable (fail closed), not as one of the v1 values (OPEN IO-Q12).

### 3.1 `segment`

| Field | Type | Meaning |
| --- | --- | --- |
| `near_m` | `[x,y,z]` | Floor endpoint closer to the camera (horizontal distance). |
| `far_m` | `[x,y,z]` | Floor endpoint farther from the camera. |
| `length_m` | number | Horizontal distance between endpoints, after all constraints. |
| `raw_near_m`, `raw_far_m` | `[x,y,z]` | Endpoints before occluder/walkable clipping. `HEAD_RAY_HEIGHT_PRIOR`: from the height prior alone. `FOOT_RAY_PIXEL_BAND`: the `(u, v ± k)` back-projections, before the body-radius allowance (§4.2a). They are descriptive of how the segment was built, **not** endpoints: only `near_m` and `far_m` are (R2, §3.3). |
| `height_prior` | object\|null | `HEAD_RAY_HEIGHT_PRIOR`: `{min_m, max_m, nominal_m, tolerance_m, source: "PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT", declaration_ref}`; heights above `floor_z_m`; `min_m = nominal_m - tolerance_m`, `max_m = nominal_m + tolerance_m`; equals `provenance.run_parameters.head_height_prior` (D5). `min_m < max_m` is required. `null` for `FOOT_RAY_PIXEL_BAND`. |
| `ray_origin_m` | `[x,y,z]`\|null | Camera centre used for the head ray; `null` for `FOOT_RAY_PIXEL_BAND`. |
| `ray_direction` | `[dx,dy,dz]`\|null | Unit vector, source world axes; `null` for `FOOT_RAY_PIXEL_BAND`. |
| `foot_band` | object\|null | `null` for `HEAD_RAY_HEIGHT_PRIOR`. For `FOOT_RAY_PIXEL_BAND`: `{band_px, body_radius_m, anchor_incidence, source: "PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT", declaration_ref}`; `band_px` = `provenance.run_parameters.foot_anchor_band_px`, `body_radius_m` = `provenance.run_parameters.body_radius_m`, `anchor_incidence` = `projection_quality` (`|n·d|/|d|`) of the unbanded anchor. |

`HEAD_RAY_HEIGHT_PRIOR`: the segment is a straight interval on the floor (the
vertical projection of the head ray between the two height planes). The estimate
claims only: *if* the height prior holds and the anchor pixel is the top of the
target, the foot lies on this interval.

`FOOT_RAY_PIXEL_BAND`: the segment is the floor interval between the
back-projections of the contact pixel moved `k` pixels towards and away from the
camera in `v`, with the far end extended by the body radius (§4.2a). The estimate
claims only: *if* the mask bottom is the visible contact of the target to within
`k` px in `v`, the target's floor contact lies on this interval.

### 3.2 `constraints_applied[]`

Applied in this fixed order; each entry records its effect.

| Field | Type | Meaning |
| --- | --- | --- |
| `kind` | enum | `HEIGHT_PRIOR`, `FOOT_RAY_PIXEL_BAND` (v1.1), `OCCLUDER_BEHIND`, `WALKABLE_AREA`. Exactly one of `HEIGHT_PRIOR` / `FOOT_RAY_PIXEL_BAND` comes first, according to `basis`. |
| `ref` | string\|null | Config ref (height prior, foot band) or annotation ref (occluder / walkable). Exact existing annotation names: `UNKNOWN` (OPEN IO-Q4). `null` for `OCCLUDER_BEHIND` with `NOT_APPLICABLE`. |
| `ref_sha256` | string\|null | Hash of the referenced config/annotation; `null` with `NOT_APPLICABLE`. |
| `effect` | enum | `BOUNDED` (height prior, foot band), `CLIPPED`, `NO_CHANGE`, `EMPTIED`, `NOT_AVAILABLE` (no annotation was supplied), `NOT_APPLICABLE` (v1.1: the step's premise does not hold for this basis, §4.3; distinct from `NOT_AVAILABLE`). |
| `length_before_m`, `length_after_m` | number\|null | Segment length before/after this step. |
| `walkable_unknown_length_m` | number\|null | `WALKABLE_AREA` only: length of the kept segment lying in `walkable: UNKNOWN` regions (D11); `null` for other kinds, `0` when none. |

### 3.3 `diagnostics` (R2)

Raw coordinates explain how an estimate was computed; they are never a position
and never an endpoint. Field names follow the C4a implementation
(`C4A_OFFICE_PERSON_RESULTS_20261017`, section "R2"):

| Field | Type | Meaning |
| --- | --- | --- |
| `raw_coordinates_use` | string | Always `DIAGNOSTIC_ONLY_NOT_POSITION_OR_ENDPOINT`. |
| `raw_coordinates_usable_as_position` | boolean | Always `false`. |
| `raw_coordinates_usable_as_endpoint` | boolean | Always `false`. |
| `endpoint_substitution` | string | `NOT_PERFORMED`: the estimator never substitutes (D7 is caller-side). |
| `raw_near_m`, `raw_far_m` | `[x,y,z]`, optional | The unclipped endpoints. Present in `READY` outputs and **also kept in `UNKNOWN` outputs, solely to explain a rejected computation**. |
| `raw_interval_length_m`, `clipped_interval_length_m` | number\|null, optional | Lengths before/after clipping. |

`diagnostics.raw_near_m`, `diagnostics.raw_far_m` and `segment.raw_near_m` /
`segment.raw_far_m` must not be used as points, valid interval endpoints, K1
inputs (blind hypothesis §3.1), frontend positions, or in evaluation as a stand-in
for `near_m` / `far_m`. A consumer takes endpoints only from `segment.near_m` /
`segment.far_m` (or `point_m`) of an object with `status: READY`. A historical
frozen artifact that predates this block is not rewritten; the same rule applies
to its raw fields. `diagnostics` names are kept for compatibility with C4a.

## 4. Computation rules

### 4.1 Basis selection (from `contact_quality`)

| `contact_quality.status` / reasons | Result |
| --- | --- |
| `PASS` and the observation has a projected floor point | `POINT`, basis `FOOT_POINT`, `point_m` = existing projected floor point (unchanged). |
| `FLAGGED` with exactly `{LOW_INCIDENCE}` | Attempt `SEGMENT`, basis `FOOT_RAY_PIXEL_BAND` (§4.2a). The head ray is **not** used and `OCCLUDER_BEHIND` is **not applicable** (§4.3). **A `HEAD_RAY_HEIGHT_PRIOR` segment is not a valid answer for this case in v1.1; see the historical note below the table (D17).** |
| `FLAGGED` with `CONTACT_OCCLUDED`, alone or together with `LOW_INCIDENCE` | Attempt `SEGMENT`, basis `HEAD_RAY_HEIGHT_PRIOR` (§4.2). `LOW_INCIDENCE` is ignored here: it was measured at the visible mask bottom, which is not the foot. |
| `FLAGGED` with `AMBIGUOUS_MERGE` or `TOUCHES_IMAGE_EDGE` | `NONE`, `UNKNOWN`, reason `HEAD_ANCHOR_UNRELIABLE` (OPEN IO-Q3 for `TOUCHES_IMAGE_EDGE`). **`AMBIGUOUS_MERGE` is decided (D8):** an observation carrying it is unusable as an endpoint until 2026-11-01; there is no relaxed rule, conditional exception or heuristic ("same track, stacked components") before the demo. |
| `FLAGGED` with any other reason, or with no reason | `NONE`, `UNKNOWN`, reason `HEAD_ANCHOR_UNRELIABLE`. |
| `NOT_EVALUATED` (incl. `AMBIGUOUS_MAPPING`) | `NONE`, `UNKNOWN`, reason `CONTACT_QUALITY_NOT_EVALUATED`. |
| `contact_quality` absent | `NONE`, `UNKNOWN`, reason `CONTACT_QUALITY_MISSING`. |

A FLAGGED POINT is never silently promoted to `PASS`, and a SEGMENT is never
emitted for a `PASS` observation. A `FOOT_RAY_PIXEL_BAND` SEGMENT is never
collapsed to the foot point, and is never replaced by, intersected with, or
retried as a `HEAD_RAY_HEIGHT_PRIOR` SEGMENT (no basis fallback inside the
estimator).

**Historical note (D17, 2026-10-17; the producer transition is closed).** Under
D17, until `FOOT_RAY_PIXEL_BAND` was implemented, an observation whose only reason
is `LOW_INCIDENCE` could be answered with a `HEAD_RAY_HEIGHT_PRIOR` SEGMENT and
used as a K1 endpoint (C4a's hold `R1_LOW_INCIDENCE_ONLY_PENDING` was lifted),
**provided that** its `OCCLUDER_BEHIND` step was `effect: NOT_APPLICABLE` with
`ref` and `ref_sha256` `null` and the length unchanged: the foot is visible, so
the premise of `OCCLUDER_BEHIND` (foot hidden) is false, and the occluder mask is
never intersected, even when supplied or in the sensitivity perturbations. Only
`HEIGHT_PRIOR` and `WALKABLE_AREA` acted on such a segment. The v1.1 implementation
(C4a [PR #46](https://github.com/Polalalabear/amidst/pull/46), commit `a6ce40c`,
stacked on C4b PR #44 @ `0942f5a`) **removes the head-ray path for
`LOW_INCIDENCE`-only observations**: the producer now answers them with
`FOOT_RAY_PIXEL_BAND` and rejects the head-ray basis for them. For the humanoid
Office run it reports 29 `FOOT_RAY_PIXEL_BAND` and 4 `HEAD_RAY_HEIGHT_PRIOR`
(`CONTACT_OCCLUDED`) segments. A v1.1 producer therefore must not emit a
`HEAD_RAY_HEIGHT_PRIOR` segment for `LOW_INCIDENCE`-only observations; the former
transitional paragraph is no longer a producer option and, once PR #46 is accepted,
this note is all that remains of it. `CONTACT_OCCLUDED` (with or without
`LOW_INCIDENCE`) keeps the v1 head-ray path.

Historical receipts of the transition (frozen files are retained, never rewritten):

| Commit | What it froze for the humanoid Office run | Conformant to the D17 clause? |
| --- | --- | --- |
| `46dd4df` (C4a, [PR #37](https://github.com/Polalalabear/amidst/pull/37)) | 33 head-ray segments, **all with `OCCLUDER_BEHIND: NOT_AVAILABLE`**; the caller guard withheld the **29** `LOW_INCIDENCE`-only endpoints as `R1_LOW_INCIDENCE_ONLY_PENDING` | **No.** It was frozen before D17; the earlier wording of this paragraph that called it conformant was shorthand and is corrected here. |
| `099513e` (C4a, D17/D18 follow-up) | Same 33 segments, **29** `LOW_INCIDENCE`-only with `OCCLUDER_BEHIND: NOT_APPLICABLE`, 4 `CONTACT_OCCLUDED` with `NOT_AVAILABLE` (no foot-hidden mask supplied); the hold lifted | **Yes**: the D17-conformant freeze. |
| `a6ce40c` (C4a, PR #46) | 29 `FOOT_RAY_PIXEL_BAND`, 4 `HEAD_RAY_HEIGHT_PRIOR`; no head-ray fallback for `LOW_INCIDENCE`-only | The v1.1 form; supersedes the D17 clause for new freezes. |

Consumers may still meet the D17 form in `099513e`. For such a historical file the
check is: a `HEAD_RAY_HEIGHT_PRIOR` object whose `contact_quality.reasons` lack
`CONTACT_OCCLUDED` must have `OCCLUDER_BEHIND: NOT_APPLICABLE`; anything else is
non-conformant. New files must not contain that form at all.

Rationale (informative). `LOW_INCIDENCE` means the foot ray meets the floor at a
grazing angle (`projection_quality = |n·d|/|d| < min_incidence = 0.25`, i.e.
below 14.5°). With the Office cameras (≈ 3.29 m above the floor, 23.3° down,
`fy ≈ 640`) that is a foot more than ≈ 12.7 m away, where ±1 px of the foot
anchor moves the floor point 0.08–0.22 m. The foot is still visible and the
height check passed, so the foot ray remains the best evidence: its ±2 px band
plus the body radius is 0.56–1.11 m long, while the head-ray interval at the
same distances is 1.6–2.8 m. `OCCLUDER_BEHIND` keeps only floor points whose
foot would be hidden from this camera. That premise is false for a visible foot,
so applying it removes the true contact point.

### 4.2 Head anchor and raw segment (`HEAD_RAY_HEIGHT_PRIOR`)

1. Head pixel: top-centre of the same component's bounding box,
   `((xmin + xmax - 1) / 2, ymin)`, mirroring the bottom-centre `contact_pixel`
   rule in `perception.py` (OPEN IO-Q1: v2 mask topmost pixel instead).
2. Back-project through the bundle calibration (same `InverseProjectionService`
   camera model; no calibration override).
3. Intersect the ray with planes `z = floor_z_m + max_m` and
   `z = floor_z_m + min_m`. The `max_m` intersection is `raw_near_m`, the `min_m`
   intersection is `raw_far_m`; both are dropped vertically to `floor_z_m`.
4. The ray must descend (`dz < 0`) and the camera must be above
   `floor_z_m + max_m`; otherwise `UNKNOWN`, `HEAD_RAY_NOT_DESCENDING`. For the
   legacy 2.94 m synthetic cylinder this is expected to fail or be extremely long
   (see [diagnosis §4](../engineering/OFFICE_MARKER_DIAGNOSIS_20261016.md#4-頭頂映射可行性分析)).

The height prior is the per-run declared value in `provenance.run_parameters`
(D5), never read from GT or the renderer: new runs use 1.70 m ± 0.10 m; the
existing Office run uses its declared 2.9393 m with a tolerance that is still
`UNKNOWN`. The span must satisfy `min_m < max_m` for every run (a zero-width
prior would collapse the SEGMENT to a point that carries no pixel-sensitivity
width); otherwise `HEIGHT_PRIOR_UNAVAILABLE` (`HEAD_RAY_HEIGHT_PRIOR` only).

### 4.2a Foot-ray pixel band (`FOOT_RAY_PIXEL_BAND`)

1. Anchor: the same v2 component's `contact_pixel` `(u, v)` (the anchor the
   `contact_quality` flags were computed on). `image_anchor_px = [u, v]`.
2. Band half-width `k = run_parameters.foot_anchor_band_px` (pixels, per-run
   declared, `PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT`, `k ≥ 1`; proposed
   default 2, OPEN IO-Q9). `k` covers anchor quantisation (the anchor is the
   integer bottom-row index of a `TOP_LEFT_CONTINUOUS` pixel grid) and mask-edge
   threshold blur. It must not be tuned against GT or evaluation results.
3. Back-project `(u, v + k)` and `(u, v − k)` onto the floor plane with the
   bundle calibration (same `InverseProjectionService`, no override). These are
   `raw_near_m` and `raw_far_m` (the larger `v` is nearer).
4. Body-centre allowance: the mask bottom is the visible near rim of the
   target, not its centre. Extend the far endpoint horizontally by
   `run_parameters.body_radius_m`, along the unit direction from `raw_near_m` to
   `raw_far_m`. The result is the `FOOT_RAY_PIXEL_BAND` constraint step
   (`effect: BOUNDED`).
5. If either back-projection fails (including `FAR_CLIPPED` for `v − k`):
   `UNKNOWN`, `PROJECTION_FAILED`. The band is not shortened to the part that
   projects.
6. The head pixel, `head_height_prior` and `HEIGHT_PRIOR` step are not used.
   `segment.height_prior` is `null`. A missing or invalid head prior does
   **not** block this basis; a missing or invalid `foot_anchor_band_px` or
   `body_radius_m` gives `UNKNOWN`, `FOOT_BAND_UNAVAILABLE`.

The estimate is a projection band, not an error bound or a probability. It
claims nothing about a foot that is partly hidden but not flagged (§6).

### 4.3 Clipping

Steps run in the fixed order of §3.2. Applicability per basis:

| Step | `HEAD_RAY_HEIGHT_PRIOR` | `FOOT_RAY_PIXEL_BAND` |
| --- | --- | --- |
| `HEIGHT_PRIOR` | applied, `BOUNDED` | not emitted |
| `FOOT_RAY_PIXEL_BAND` | not emitted | applied, `BOUNDED` |
| `OCCLUDER_BEHIND` | with `CONTACT_OCCLUDED`: applied (`CLIPPED` / `NO_CHANGE` / `EMPTIED` / `NOT_AVAILABLE`). A `LOW_INCIDENCE`-only head-ray segment exists only in historical D17 files (§4.1 note), with `NOT_APPLICABLE`; a v1.1 producer does not emit it | emitted with `effect: NOT_APPLICABLE`, `ref` / `ref_sha256` `null`, length unchanged; the occluder mask is never intersected, even when supplied |
| `WALKABLE_AREA` | applied (D11 `walkable: UNKNOWN` kept) | applied (D11 `walkable: UNKNOWN` kept) |

- **`OCCLUDER_BEHIND`.** Keep only floor points whose line of sight to the camera
  passes through the referenced occluder geometry (the foot is hidden, so it must
  be behind something). It is valid only when the foot is believed hidden from
  this camera (`CONTACT_OCCLUDED`); an estimator that intersects an occluder mask
  on a `LOW_INCIDENCE`-only segment (either basis) is non-conformant. Only
  occluder geometry from an approved source annotation may be used; renderer
  visibility/depth is forbidden. No annotation: `effect: NOT_AVAILABLE`, segment
  unchanged.
- **`WALKABLE_AREA`.** Intersect with the walkable map. No map:
  `effect: NOT_AVAILABLE`, segment unchanged. Map regions carry a `tier`
  (`SOURCE_DERIVED`, `ANNOTATION_ONLY`, `UNKNOWN`) and `walkable` (`TRUE` or
  `UNKNOWN`) as in [blind hypothesis §3.2](OFFICE_BLIND_HYPOTHESIS_V1.md#32-server-resolved-configuration-echoed-in-the-response)
  (D11). Parts of the segment inside a `walkable: UNKNOWN` region are **kept**,
  not clipped; the step records their length in `walkable_unknown_length_m`.
  The producer never moves, snaps or extends a POINT or SEGMENT to the nearest
  walkable point. Physical obstacles that the source mesh resolves individually,
  such as seats and lecterns (D16), are absent from the map and clip like any
  other non-walkable space. The restricted-policy layer (D15,
  [blind hypothesis §3.2.1](OFFICE_BLIND_HYPOTHESIS_V1.md#321-restricted-policy-layer-d15))
  is **not** part of this map and never clips: a segment lying in a restricted
  region is kept unchanged, and this estimator does not label it.
- If a step empties the segment: `UNKNOWN`, `SEGMENT_EMPTY_AFTER_CONSTRAINTS`
  (the measurement contradicts the geometry; do not relax constraints).
- If a step splits it into disjoint pieces: `UNKNOWN`, `SEGMENT_NON_CONTIGUOUS`
  (OPEN IO-Q5: multi-piece output).
- `SEGMENT_TOO_LONG` applies to both bases.

### 4.4 `pixel_sensitivity_m`

Computed per observation, not a constant (the pipeline map rejects a single
0.15 m/px figure). POINT: maximum floor displacement of the projected point for
±1 px in `u` and `v`. SEGMENT: maximum displacement of either endpoint for ±1 px
of the head pixel. `FOOT_RAY_PIXEL_BAND`: maximum displacement of either clipped
endpoint when the foot anchor moves ±1 px in `u`, `v` and the diagonals (the
same 8-neighbourhood as `pixel_sensitivity` in `perception_v2.py`), with `k` and
the radius allowance held fixed and the same clips re-applied. When it cannot be
computed, `null` and the estimate is
`UNKNOWN` with `PIXEL_SENSITIVITY_UNAVAILABLE`. It is a local derivative, not an
error bound or probability. It should equal `contact_quality.pixel_sensitivity_m`
for POINT estimates; a mismatch above 1e-6 m is a producer error. No equality
with `contact_quality.pixel_sensitivity_m` is required for `FOOT_RAY_PIXEL_BAND`
(that value is for the unbanded anchor).

## 5. Fail-closed reasons

Any of these yields `status: UNKNOWN`, `estimate_kind: NONE`, `point_m: null`,
`segment: null`; raw coordinates may remain only in `diagnostics` (§3.3, R2). The
estimator itself never falls back to a different observation,
timestamp, camera or default height. An endpoint substitution (D7) is a
**caller-side** step defined in
[blind hypothesis §3.1.1](OFFICE_BLIND_HYPOTHESIS_V1.md#311-endpoint-substitution-caller-side-d7);
it leaves the unusable observation's `ground_estimate` exactly as produced
(`UNKNOWN`, same reason) and uses the substitute's own `READY` `ground_estimate`.

| `reason` | When |
| --- | --- |
| `OBSERVATION_NOT_FOUND` | `observation_ref` does not resolve in this scene/run. |
| `CONTACT_QUALITY_MISSING` / `CONTACT_QUALITY_NOT_EVALUATED` | §4.1. |
| `HEAD_ANCHOR_UNRELIABLE` | §4.1. |
| `HEAD_RAY_NOT_DESCENDING` | §4.2 step 4. |
| `HEIGHT_PRIOR_UNAVAILABLE` | `HEAD_RAY_HEIGHT_PRIOR` only: no per-run declared prior (§2.1), a prior with `min_m >= max_m`, or a declaration hash mismatch. |
| `FOOT_BAND_UNAVAILABLE` | `FOOT_RAY_PIXEL_BAND` selected but `foot_anchor_band_px` or `body_radius_m` is missing, non-finite, `foot_anchor_band_px < 1` or `body_radius_m ≤ 0`, or the declaration hash does not match. |
| `PROJECTION_FAILED` | Back-projection failed (`InverseProjectionFailure`), including §4.2a step 5. |
| `SEGMENT_EMPTY_AFTER_CONSTRAINTS` / `SEGMENT_NON_CONTIGUOUS` | §4.3. |
| `SEGMENT_TOO_LONG` | `length_m > MAX_SEGMENT_LENGTH_M`. |
| `PIXEL_SENSITIVITY_UNAVAILABLE` | §4.4. |
| `PROVENANCE_MISMATCH` | Any hash in `provenance` differs from the loaded bundle. |

## 6. Limits

| Limit | Proposed value | Status |
| --- | --- | --- |
| `MAX_SEGMENT_LENGTH_M` | 8.0 | OPEN IO-Q8 (no written confirmation; user decision pending) |
| Height prior span | `0 < min_m < max_m`; `max_m <= 2.5` for person-sized runs. The existing Office cylinder (nominal 2.9393 m) is exempt from the 2.5 bound and must be labelled `SYNTHETIC_CYLINDER_NOT_HUMAN_SIZED` | OPEN IO-Q8 (tolerance of the Office run `UNKNOWN`) |
| `foot_anchor_band_px` | 2 px for every run (new and existing Office) | OPEN IO-Q9 |
| Undetected foot truncation | v2's height check tolerates `height_tolerance_px` + projected radius (≈ 11 px at 20 m), more than `k`. A foot that is partly hidden but not flagged can therefore lie nearer than `raw_near_m`. This applies equally to `FOOT_POINT`. | known limit, not corrected in v1.1 |
| Objects per response | Bounded by the carrying response (`MAX_POINTS = 400` in `blender_motion.py`) | existing |
| Deadline | Shares the carrying request's cooperative monotonic deadline | existing pattern |

## 7. Attachment points

Attach `ground_estimate` where Task 3 attaches `contact_quality` (query
observations, cross-camera path samples, physical review
`synchronized_evidence.samples`), as a sibling field. Response schemas gain one
optional field; consumers that ignore it see byte-identical existing fields. The
HTTP route names that carry these responses are `UNKNOWN` per the pipeline map
§6; this contract adds no endpoint. Where to attach first: OPEN IO-Q2.

## 8. Example (illustrative numbers, not measured)

```json
{
  "schema_version": "office-demo.interval-observation.v1",
  "observation_ref": "observation:add9f687d311742321e80dff",
  "camera_id": "CAM_1F_AUDITORIUM_FRONT",
  "timestamp_s": 4.4,
  "status": "READY",
  "reason": null,
  "evidence_state": "PROJECTED_OBSERVATION",
  "estimate_kind": "SEGMENT",
  "basis": "HEAD_RAY_HEIGHT_PRIOR",
  "point_m": null,
  "segment": {
    "near_m": [12.10, 4.35, 0.4959475898742676],
    "far_m": [13.05, 4.62, 0.4959475898742676],
    "length_m": 0.988,
    "raw_near_m": [11.40, 4.15, 0.4959475898742676],
    "raw_far_m": [14.20, 4.95, 0.4959475898742676],
    "height_prior": {"min_m": 1.6, "max_m": 1.8, "nominal_m": 1.7, "tolerance_m": 0.1, "source": "PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT", "declaration_ref": "setting:run-<new>-target-v1"},
    "ray_origin_m": [0.20, 0.10, 3.79],
    "ray_direction": [0.93, 0.26, -0.26]
  },
  "image_anchor_px": [512.5, 188.0],
  "pixel_sensitivity_m": 0.24,
  "constraints_applied": [
    {"kind": "HEIGHT_PRIOR", "ref": "setting:run-<new>-target-v1", "ref_sha256": "<sha256>", "effect": "BOUNDED", "length_before_m": null, "length_after_m": 2.912, "walkable_unknown_length_m": null},
    {"kind": "OCCLUDER_BEHIND", "ref": "UNKNOWN", "ref_sha256": "<sha256>", "effect": "CLIPPED", "length_before_m": 2.912, "length_after_m": 1.410, "walkable_unknown_length_m": null},
    {"kind": "WALKABLE_AREA", "ref": "UNKNOWN", "ref_sha256": "<sha256>", "effect": "CLIPPED", "length_before_m": 1.410, "length_after_m": 0.988, "walkable_unknown_length_m": 0.0}
  ],
  "contact_quality": {
    "version": "rgb-mask-contact-v2",
    "status": "FLAGGED",
    "reasons": ["CONTACT_OCCLUDED", "LOW_INCIDENCE"],
    "pixel_sensitivity_m": 0.15,
    "authority": "QUALITY_FLAG_ONLY_POSITION_UNCHANGED"
  },
  "authority": "PROJECTION_ONLY_NOT_POSITION_AUTHORITY",
  "identity_verdict": "UNCONFIRMED",
  "physical_authority": "UNKNOWN",
  "provenance": {"scene_id": "blender-office", "run_ref": "UNKNOWN", "clock_id": "BLENDER_PILOT_CONFIGURED_SECONDS_5HZ", "source_sha256": "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e", "safe_inputs_sha256": "1ea62def6c843b3bae1c5e25584fa489915f08e678b28b6220dc88cc17b43163", "producer": "hybrid-ground-estimator", "producer_version": "v1", "config_sha256": "<sha256>", "annotation_sha256": {"occluders": "<sha256>", "walkable": "<sha256>"}, "run_parameters": {"declaration_source": "PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT", "declaration_ref": "setting:run-<new>-target-v1", "declaration_sha256": "<sha256>", "target_proxy": {"shape": "CYLINDER", "height_m": 1.70, "radius_m": 0.25, "label": "SYNTHETIC_CYLINDER_PERSON_SIZED"}, "head_height_prior": {"nominal_m": 1.70, "tolerance_m": 0.10}, "body_radius_m": 0.25, "foot_anchor_band_px": 2}, "gt_read": false},
  "diagnostics": {"endpoint_substitution": "NOT_PERFORMED", "raw_interval_length_m": 2.912, "raw_coordinates_use": "DIAGNOSTIC_ONLY_NOT_POSITION_OR_ENDPOINT", "raw_coordinates_usable_as_position": false, "raw_coordinates_usable_as_endpoint": false, "raw_near_m": [11.40, 4.15, 0.4959475898742676], "raw_far_m": [14.20, 4.95, 0.4959475898742676], "clipped_interval_length_m": 0.988},
  "output_sha256": "<sha256>"
}
```

Note: `contact_quality.pixel_sensitivity_m` in the example is the foot-pixel
value from the Task 3 example; the SEGMENT's own `pixel_sensitivity_m` refers to
the head pixel and may differ.

### 8.1 Example: `FOOT_RAY_PIXEL_BAND` (illustrative numbers, not measured)

A `LOW_INCIDENCE`-only observation at a far Office camera. `raw_near_m` /
`raw_far_m` are the `(u, v ± 2)` back-projections; the far end is extended by
`body_radius_m = 0.25`. `OCCLUDER_BEHIND` does not apply, so no occluder
annotation is referenced.

```json
{
  "schema_version": "office-demo.interval-observation.v1",
  "observation_ref": "observation:<rear-8.2>",
  "camera_id": "CAM_1F_AUDITORIUM_REAR",
  "timestamp_s": 8.2,
  "status": "READY",
  "reason": null,
  "evidence_state": "PROJECTED_OBSERVATION",
  "estimate_kind": "SEGMENT",
  "basis": "FOOT_RAY_PIXEL_BAND",
  "point_m": null,
  "segment": {
    "near_m": [13.40, 4.60, 0.4959475898742676],
    "far_m": [14.122, 4.975, 0.4959475898742676],
    "length_m": 0.814,
    "raw_near_m": [13.40, 4.60, 0.4959475898742676],
    "raw_far_m": [13.90, 4.86, 0.4959475898742676],
    "height_prior": null,
    "ray_origin_m": null,
    "ray_direction": null,
    "foot_band": {"band_px": 2, "body_radius_m": 0.25, "anchor_incidence": 0.21, "source": "PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT", "declaration_ref": "setting:run-<new>-target-v1"}
  },
  "image_anchor_px": [290.0, 301],
  "pixel_sensitivity_m": 0.19,
  "constraints_applied": [
    {"kind": "FOOT_RAY_PIXEL_BAND", "ref": "setting:run-<new>-target-v1", "ref_sha256": "<sha256>", "effect": "BOUNDED", "length_before_m": null, "length_after_m": 0.814, "walkable_unknown_length_m": null},
    {"kind": "OCCLUDER_BEHIND", "ref": null, "ref_sha256": null, "effect": "NOT_APPLICABLE", "length_before_m": 0.814, "length_after_m": 0.814, "walkable_unknown_length_m": null},
    {"kind": "WALKABLE_AREA", "ref": "UNKNOWN", "ref_sha256": "<sha256>", "effect": "NO_CHANGE", "length_before_m": 0.814, "length_after_m": 0.814, "walkable_unknown_length_m": 0.0}
  ],
  "contact_quality": {
    "version": "rgb-mask-contact-v2",
    "status": "FLAGGED",
    "reasons": ["LOW_INCIDENCE"],
    "pixel_sensitivity_m": 0.19,
    "authority": "QUALITY_FLAG_ONLY_POSITION_UNCHANGED"
  },
  "authority": "PROJECTION_ONLY_NOT_POSITION_AUTHORITY",
  "identity_verdict": "UNCONFIRMED",
  "physical_authority": "UNKNOWN",
  "provenance": {"scene_id": "blender-office", "run_ref": "UNKNOWN", "clock_id": "BLENDER_PILOT_CONFIGURED_SECONDS_5HZ", "source_sha256": "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e", "safe_inputs_sha256": "1ea62def6c843b3bae1c5e25584fa489915f08e678b28b6220dc88cc17b43163", "producer": "hybrid-ground-estimator", "producer_version": "v1.1", "config_sha256": "<sha256>", "annotation_sha256": {"occluders": null, "walkable": "<sha256>"}, "run_parameters": {"declaration_source": "PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT", "declaration_ref": "setting:run-<new>-target-v1", "declaration_sha256": "<sha256>", "target_proxy": {"shape": "CYLINDER", "height_m": 1.70, "radius_m": 0.25, "label": "SYNTHETIC_CYLINDER_PERSON_SIZED"}, "head_height_prior": {"nominal_m": 1.70, "tolerance_m": 0.10}, "body_radius_m": 0.25, "foot_anchor_band_px": 2}, "gt_read": false},
  "diagnostics": {"endpoint_substitution": "NOT_PERFORMED", "raw_interval_length_m": 0.564, "raw_coordinates_use": "DIAGNOSTIC_ONLY_NOT_POSITION_OR_ENDPOINT", "raw_coordinates_usable_as_position": false, "raw_coordinates_usable_as_endpoint": false, "raw_near_m": [13.40, 4.60, 0.4959475898742676], "raw_far_m": [13.90, 4.86, 0.4959475898742676], "clipped_interval_length_m": 0.814},
  "output_sha256": "<sha256>"
}
```

## 9. Evaluation boundary

RQ1 metrics (truth-in-interval rate, interval length, per-pixel sensitivity) are
computed by the evaluation tool after predictions are frozen. The estimator and
this object never read GT, renderer trajectories, visibility or depth.

## 10. OPEN QUESTIONS for Codex

- **IO-Q1** Head anchor: bbox top-centre of the v1 component, or topmost pixel of
  the mapped v2 mask component?
- **IO-Q2** May a SEGMENT attach to an observation whose motion-curve state is
  `MISSING` (v2-rejected points)? This draft says yes as a sibling field, with
  the curve state unchanged. Which response carries it first: query observations
  only, or all three Task 3 attachment points?
- **IO-Q3** Should `TOUCHES_IMAGE_EDGE` (bottom edge only) still allow a head-ray
  SEGMENT? Draft: no.
- **IO-Q4** *(walkable part RESOLVED by D3, 2026-10-16: walkable, portal and obstacle geometry is derived from the source mesh by C7 #29; `WALK_*`/`PORTAL_*`/`AREA_*` annotations are cross-checks only; occluder refs and hashes still `UNKNOWN` until C7 delivers.)* Do approved occluder and walkable annotations exist for
  `school_v3.blend` 1F, and what are their ref names and hashes? (`UNKNOWN`.)
  Is occluder geometry from the source mesh permitted under DEVELOPMENT_RULES?
- **IO-Q5** Multi-piece segments after walkable clipping: keep fail-closed
  (`SEGMENT_NON_CONTIGUOUS`) or add a `pieces[]` array in v1?
- **IO-Q6** Existing field name for the run identifier in the bundle (`run_ref`
  placeholder).
- **IO-Q7** Canonical JSON rule for `output_sha256` (key order, float format);
  reuse the backend's existing receipt hashing if one exists.
- **IO-Q8** Confirm `MAX_SEGMENT_LENGTH_M` and the height-prior bounds. *(Prior
  for new runs RESOLVED by D5: 1.70 m ± 0.10 m. The legacy 2.9393 m cylinder keeps
  its declared height; its tolerance, or declaring SEGMENT unsupported there, is
  still open. At 2.9393 m ± 0.10 m the diagnosis estimates a head-ray interval
  longer than `MAX_SEGMENT_LENGTH_M`, so `SEGMENT_TOO_LONG` is expected.)*
  **Status (2026-10-17): still OPEN.** No written Codex confirmation of
  `MAX_SEGMENT_LENGTH_M = 8.0` exists: the Codex clause-by-clause confirmation of
  PR #45 does not cover it. The value is only in use as the C4a producer config
  (`max_segment_length_m` in `configs/hybrid_contact_v1.json`), not as a decided
  contract limit; the decision is the user's.

- **IO-Q9** *(v1.1)* Confirm `foot_anchor_band_px = 2` (declared, not tuned), and
  that `FOOT_RAY_PIXEL_BAND` may run on a run whose head-height tolerance is
  `UNKNOWN` (the existing Office run), because it uses only `body_radius_m`.
- **IO-Q10** *(v1.1)* `CONTACT_OCCLUDED` is set from the magnitude of the
  head-model residual only. A visible top *above* the predicted top suggests a
  hidden foot, and one *below* it suggests a hidden or wrong head anchor. Should
  v2 export the signed residual, so that the second case gives
  `HEAD_ANCHOR_UNRELIABLE` instead of a head-ray SEGMENT? Draft: not in v1.1.
- **IO-Q11** *(v1.1)* For `CONTACT_OCCLUDED`, the visible mask bottom lies above
  the hidden foot in the image. With zero camera roll, this bounds the foot's
  camera-forward depth from above, which could become an additional
  `VISIBLE_BOTTOM_FAR_BOUND` clip. Draft: not in v1.1; record the idea only.
- **IO-Q12** *(v1.1)* `schema_version` stays `office-demo.interval-observation.v1`
  while enum values and fields are added (§3). Confirm, or bump the string.

## 11. Revision 2026-10-16

Draft revision after CP1 decisions D4–D13 ([#25](https://github.com/Polalalabear/amidst/issues/25))
and the K1 contract deviations ([PR #33](https://github.com/Polalalabear/amidst/pull/33)).
Still a draft; it takes effect only when CP1 is approved.

| Change | Section | Basis |
| --- | --- | --- |
| Head-height prior and body radius are per-run declared values carried in a new `provenance.run_parameters` block (declaration ref + hash, target proxy, prior with tolerance, body radius), echoed by all three contracts; never GT. New runs: 1.70 m ± 0.10 m, radius 0.25 m. Existing Office run: 2.9393 m / 0.1482 m, labelled "synthetic cylinder, not human-sized", tolerance `UNKNOWN`. | §2.1, §3.1, §4.2, §5, §6 | D5, D6 |
| `height_prior.source` becomes `PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT` (the existing label in `office_contact_v2.json`); `nominal_m`, `tolerance_m`, `declaration_ref` added; `min_m < max_m` is mandatory. | §3.1, §4.2, §5 | D5, K1 follow-up (zero-width prior) |
| `AMBIGUOUS_MERGE` endpoints are unusable until 2026-11-01, with no relaxed rule. Text only; the behaviour was already `HEAD_ANCHOR_UNRELIABLE`. | §4.1 | D8 |
| Endpoint substitution is caller-side; the estimator never substitutes and leaves the original `ground_estimate` untouched. | §5 | D7 |
| `WALKABLE_AREA` keeps segment parts inside `walkable: UNKNOWN` regions (new `walkable_unknown_length_m`); no snapping to the nearest walkable point. | §3.2, §4.3 | D11 |
| Open questions IO-Q4 (walkable part) and IO-Q8 (new-run prior) marked resolved. | §10 | D3, D5 |

Not changed: POINT/SEGMENT rules, the `contact_quality` mapping, `output_sha256`
(IO-Q7 stays OPEN; the K1 module's canonical form is proposed there, see
[blind hypothesis §12](OFFICE_BLIND_HYPOTHESIS_V1.md#12-revision-2026-10-16)).
D9, D10, D12 and D13 do not touch this contract.

Deviation from the task wording: for the existing Office run D5 fixes the height
(2.9393 m) but not the tolerance; the contract does **not** pick one (the
decision draft only suggested ± 0.10 m as an example) and marks it `UNKNOWN`.

## Revision 2026-10-17 (v1.1)

Draft revision after the CP2 decisions D15–D18 ([#26](https://github.com/Polalalabear/amidst/issues/26)),
the C4a review finding R1/R2 ([PR #37](https://github.com/Polalalabear/amidst/pull/37))
and the K5 implementation ([PR #36](https://github.com/Polalalabear/amidst/pull/36)).
Still a draft; it takes effect only when Codex confirms and the PR merges. The
wording of the R1 rules comes from the Opus 5.5 design analysis (medium effort)
of 2026-10-17; no GT, renderer trajectory, visibility or depth enters any rule.

| Change | Section | Basis |
| --- | --- | --- |
| `LOW_INCIDENCE`-only observations use the new `FOOT_RAY_PIXEL_BAND` SEGMENT (contact pixel ± `k` px along the foot ray, far end plus body radius) instead of the head ray. | §1, §3, §3.1, §4.1, §4.2a | C4a review R1; D17 |
| `OCCLUDER_BEHIND` is `NOT_APPLICABLE` for `LOW_INCIDENCE`-only segments; new `effect` value `NOT_APPLICABLE`, distinct from `NOT_AVAILABLE`. | §3.2, §4.3 | R1 (a visible foot contradicts the foot-hidden premise); D17 |
| D17 transition, now a **historical note**: until `FOOT_RAY_PIXEL_BAND` existed, `LOW_INCIDENCE`-only could use a `HEAD_RAY_HEIGHT_PRIOR` SEGMENT with `OCCLUDER_BEHIND: NOT_APPLICABLE`. PR #46 (`a6ce40c`) removed that head-ray path; a v1.1 producer must not emit it. Receipts: `46dd4df` (not conformant: `NOT_AVAILABLE`, 29 endpoints withheld) and `099513e` (the conformant D17 freeze). | §4.1, §4.3 | D17; Codex confirmation of PR #45 |
| `HEIGHT_PRIOR_UNAVAILABLE` wording in §2.1 and §4.2 gets the explicit exception for `FOOT_RAY_PIXEL_BAND` (head prior never blocks it). | §2.1, §4.2 | Codex confirmation of PR #45 |
| IO-Q8 (`MAX_SEGMENT_LENGTH_M = 8.0`) stays OPEN: no written Codex confirmation yet. | §6, §10 | editorial |
| `CONTACT_OCCLUDED` together with `LOW_INCIDENCE` keeps the v1 head-ray path. `AMBIGUOUS_MERGE` and `TOUCHES_IMAGE_EDGE` stay unusable (D8). | §4.1 | D17, D8 |
| New `run_parameters.foot_anchor_band_px`, `segment.foot_band`, constraint kind `FOOT_RAY_PIXEL_BAND`, reason `FOOT_BAND_UNAVAILABLE`; `segment.height_prior`, `ray_origin_m`, `ray_direction` nullable. | §2.1, §3.1, §3.2, §5 | R1 |
| `pixel_sensitivity_m` for the new basis; known limit "undetected foot truncation". | §4.4, §6 | R1 |
| New `diagnostics` block: raw coordinates are diagnostic only and never a position, endpoint, K1 input or frontend position; field names as implemented by C4a. | §3, §3.3 | R2 (C4a) |
| `WALKABLE_AREA` notes: individually resolved seats and lecterns are obstacles absent from the map; the restricted-policy layer never clips. | §4.3 | D16, D15 |
| New open questions IO-Q9 to IO-Q12. | §10 | R1 |

Not changed: POINT rules, the head-ray computation (§4.2), `WALKABLE_AREA`
semantics (D11, `walkable: UNKNOWN` kept), `MAX_SEGMENT_LENGTH_M`, endpoint
substitution (D7, caller-side), `output_sha256` canonicalisation (IO-Q7 stays
OPEN). D18 (the humanoid run's blind-interval endpoints become 4.6 s → 8.2 s) is a
choice of observations by the caller and does not change this contract; for the
legacy 2.9393 m run the endpoints stay 4.4 s → 8.6 s.
