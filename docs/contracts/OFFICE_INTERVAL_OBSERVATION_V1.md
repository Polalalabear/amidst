> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# Office Demo interval-observation contract v1

Status: DRAFT for Codex confirmation, 2026-10-16 (task K0). Additive to the
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
- a **SEGMENT**: the foot is not usable, so the head ray is intersected with a
  configured height range and the resulting floor interval is clipped by occluder
  geometry and the walkable area.

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
    "body_radius_m": 0.25
  },
  "gt_read": false
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
run (all three contracts carry the same block). A producer that cannot find the
declaration for the run must not emit the object (`HEIGHT_PRIOR_UNAVAILABLE`).
Values by run:

| Run | `target_proxy` | `head_height_prior` | `body_radius_m` |
| --- | --- | --- | --- |
| New runs (C6, D4/D5/D6) | cylinder, height 1.70 m, radius 0.25 m, label `SYNTHETIC_CYLINDER_PERSON_SIZED` | 1.70 m ± 0.10 m | 0.25 |
| Existing Office run | declared height 2.9393 m, radius 0.1482 m, label `SYNTHETIC_CYLINDER_NOT_HUMAN_SIZED` | nominal 2.9393 m; **tolerance not decided (UNKNOWN)** — to be declared before use | 0.1482 (origin `UNKNOWN`) |

The origin of 2.9393 m (intentional or a ×0.0247 scale issue) and of 0.1482 m is
`UNKNOWN`; it is checked in task C7.

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
| `basis` | enum | yes | `FOOT_POINT` (POINT), `HEAD_RAY_HEIGHT_PRIOR` (SEGMENT), `NONE`. |
| `point_m` | `[x,y,z]`\|null | yes | Floor point; non-null only for `POINT`. |
| `segment` | object\|null | yes | Non-null only for `SEGMENT`; see §3.1. |
| `image_anchor_px` | `[u,v]` | yes | Pixel used: contact pixel for POINT; head pixel for SEGMENT (§4.2). |
| `pixel_sensitivity_m` | number\|null | yes | Floor displacement for a ±1 px change of `image_anchor_px` (§4.4). |
| `constraints_applied` | array | yes | Ordered list of §3.2 entries; empty for POINT. |
| `contact_quality` | object | yes | Verbatim copy of the Task 3 `contact_quality` object for this observation (same `version`). |
| `authority` | string | yes | `PROJECTION_ONLY_NOT_POSITION_AUTHORITY`. |
| `identity_verdict` | string | yes | `UNCONFIRMED`. |
| `physical_authority` | string | yes | `UNKNOWN`. |
| `provenance` | object | yes | §2.1. |
| `output_sha256` | string | yes | §2. |

### 3.1 `segment`

| Field | Type | Meaning |
| --- | --- | --- |
| `near_m` | `[x,y,z]` | Floor endpoint closer to the camera (horizontal distance). |
| `far_m` | `[x,y,z]` | Floor endpoint farther from the camera. |
| `length_m` | number | Horizontal distance between endpoints, after all constraints. |
| `raw_near_m`, `raw_far_m` | `[x,y,z]` | Endpoints from the height prior alone, before occluder/walkable clipping. |
| `height_prior` | object | `{min_m, max_m, nominal_m, tolerance_m, source: "PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT", declaration_ref}`; heights above `floor_z_m`; `min_m = nominal_m - tolerance_m`, `max_m = nominal_m + tolerance_m`; equals `provenance.run_parameters.head_height_prior` (D5). `min_m < max_m` is required. |
| `ray_origin_m` | `[x,y,z]` | Camera centre used for the head ray. |
| `ray_direction` | `[dx,dy,dz]` | Unit vector, source world axes. |

The segment is a straight interval on the floor (the vertical projection of the
head ray between the two height planes). The estimate claims only: *if* the
height prior holds and the anchor pixel is the top of the target, the foot lies
on this interval.

### 3.2 `constraints_applied[]`

Applied in this fixed order; each entry records its effect.

| Field | Type | Meaning |
| --- | --- | --- |
| `kind` | enum | `HEIGHT_PRIOR`, `OCCLUDER_BEHIND`, `WALKABLE_AREA`. |
| `ref` | string\|null | Config ref (height prior) or annotation ref (occluder / walkable). Exact existing annotation names: `UNKNOWN` (OPEN IO-Q4). |
| `ref_sha256` | string\|null | Hash of the referenced config/annotation. |
| `effect` | enum | `BOUNDED` (height prior), `CLIPPED`, `NO_CHANGE`, `EMPTIED`, `NOT_AVAILABLE`. |
| `length_before_m`, `length_after_m` | number\|null | Segment length before/after this step. |
| `walkable_unknown_length_m` | number\|null | `WALKABLE_AREA` only: length of the kept segment lying in `walkable: UNKNOWN` regions (D11); `null` for other kinds, `0` when none. |

## 4. Computation rules

### 4.1 Basis selection (from `contact_quality`)

| `contact_quality.status` / reasons | Result |
| --- | --- |
| `PASS` and the observation has a projected floor point | `POINT`, basis `FOOT_POINT`, `point_m` = existing projected floor point (unchanged). |
| `FLAGGED` with only `CONTACT_OCCLUDED` and/or `LOW_INCIDENCE` | Attempt `SEGMENT`, basis `HEAD_RAY_HEIGHT_PRIOR`. |
| `FLAGGED` with `AMBIGUOUS_MERGE` or `TOUCHES_IMAGE_EDGE` | `NONE`, `UNKNOWN`, reason `HEAD_ANCHOR_UNRELIABLE` (OPEN IO-Q3 for `TOUCHES_IMAGE_EDGE`). **`AMBIGUOUS_MERGE` is decided (D8):** an observation carrying it is unusable as an endpoint until 2026-11-01; there is no relaxed rule, conditional exception or heuristic ("same track, stacked components") before the demo. |
| `NOT_EVALUATED` (incl. `AMBIGUOUS_MAPPING`) | `NONE`, `UNKNOWN`, reason `CONTACT_QUALITY_NOT_EVALUATED`. |
| `contact_quality` absent | `NONE`, `UNKNOWN`, reason `CONTACT_QUALITY_MISSING`. |

A FLAGGED POINT is never silently promoted to `PASS`, and a SEGMENT is never
emitted for a `PASS` observation.

### 4.2 Head anchor and raw segment

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
width); otherwise `HEIGHT_PRIOR_UNAVAILABLE`.

### 4.3 Clipping

- **`OCCLUDER_BEHIND`.** Keep only floor points whose line of sight to the camera
  passes through the referenced occluder geometry (the foot is hidden, so it must
  be behind something). Only occluder geometry from an approved source annotation
  may be used; renderer visibility/depth is forbidden. No annotation:
  `effect: NOT_AVAILABLE`, segment unchanged.
- **`WALKABLE_AREA`.** Intersect with the walkable map. No map:
  `effect: NOT_AVAILABLE`, segment unchanged. Map regions carry a `tier`
  (`SOURCE_DERIVED`, `ANNOTATION_ONLY`, `UNKNOWN`) and `walkable` (`TRUE` or
  `UNKNOWN`) as in [blind hypothesis §3.2](OFFICE_BLIND_HYPOTHESIS_V1.md#32-server-resolved-configuration-echoed-in-the-response)
  (D11). Parts of the segment inside a `walkable: UNKNOWN` region are **kept**,
  not clipped; the step records their length in `walkable_unknown_length_m`.
  The producer never moves, snaps or extends a POINT or SEGMENT to the nearest
  walkable point.
- If a step empties the segment: `UNKNOWN`, `SEGMENT_EMPTY_AFTER_CONSTRAINTS`
  (the measurement contradicts the geometry; do not relax constraints).
- If a step splits it into disjoint pieces: `UNKNOWN`, `SEGMENT_NON_CONTIGUOUS`
  (OPEN IO-Q5: multi-piece output).

### 4.4 `pixel_sensitivity_m`

Computed per observation, not a constant (the pipeline map rejects a single
0.15 m/px figure). POINT: maximum floor displacement of the projected point for
±1 px in `u` and `v`. SEGMENT: maximum displacement of either endpoint for ±1 px
of the head pixel. When it cannot be computed, `null` and the estimate is
`UNKNOWN` with `PIXEL_SENSITIVITY_UNAVAILABLE`. It is a local derivative, not an
error bound or probability. It should equal `contact_quality.pixel_sensitivity_m`
for POINT estimates; a mismatch above 1e-6 m is a producer error.

## 5. Fail-closed reasons

Any of these yields `status: UNKNOWN`, `estimate_kind: NONE`, `point_m: null`,
`segment: null`. The estimator itself never falls back to a different observation,
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
| `HEIGHT_PRIOR_UNAVAILABLE` | No per-run declared prior (§2.1), a prior with `min_m >= max_m`, or a declaration hash mismatch. |
| `PROJECTION_FAILED` | Back-projection failed (`InverseProjectionFailure`). |
| `SEGMENT_EMPTY_AFTER_CONSTRAINTS` / `SEGMENT_NON_CONTIGUOUS` | §4.3. |
| `SEGMENT_TOO_LONG` | `length_m > MAX_SEGMENT_LENGTH_M`. |
| `PIXEL_SENSITIVITY_UNAVAILABLE` | §4.4. |
| `PROVENANCE_MISMATCH` | Any hash in `provenance` differs from the loaded bundle. |

## 6. Limits

| Limit | Proposed value | Status |
| --- | --- | --- |
| `MAX_SEGMENT_LENGTH_M` | 8.0 | OPEN IO-Q8 |
| Height prior span | `0 < min_m < max_m`; `max_m <= 2.5` for person-sized runs. The existing Office cylinder (nominal 2.9393 m) is exempt from the 2.5 bound and must be labelled `SYNTHETIC_CYLINDER_NOT_HUMAN_SIZED` | OPEN IO-Q8 (tolerance of the Office run `UNKNOWN`) |
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
  "provenance": {"scene_id": "blender-office", "run_ref": "UNKNOWN", "clock_id": "BLENDER_PILOT_CONFIGURED_SECONDS_5HZ", "source_sha256": "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e", "safe_inputs_sha256": "1ea62def6c843b3bae1c5e25584fa489915f08e678b28b6220dc88cc17b43163", "producer": "hybrid-ground-estimator", "producer_version": "v1", "config_sha256": "<sha256>", "annotation_sha256": {"occluders": "<sha256>", "walkable": "<sha256>"}, "run_parameters": {"declaration_source": "PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT", "declaration_ref": "setting:run-<new>-target-v1", "declaration_sha256": "<sha256>", "target_proxy": {"shape": "CYLINDER", "height_m": 1.70, "radius_m": 0.25, "label": "SYNTHETIC_CYLINDER_PERSON_SIZED"}, "head_height_prior": {"nominal_m": 1.70, "tolerance_m": 0.10}, "body_radius_m": 0.25}, "gt_read": false},
  "output_sha256": "<sha256>"
}
```

Note: `contact_quality.pixel_sensitivity_m` in the example is the foot-pixel
value from the Task 3 example; the SEGMENT's own `pixel_sensitivity_m` refers to
the head pixel and may differ.

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
