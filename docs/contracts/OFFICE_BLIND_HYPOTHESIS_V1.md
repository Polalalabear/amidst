# Office Demo blind-interval hypothesis contract v1

Status: **v1.1 DRAFT** for Codex confirmation, 2026-10-17 (task K0 revision of the
CP1-approved v1, merged at `dcb89f4`; the file name stays `_V1`, see
[Revision 2026-10-17 (v1.1)](#revision-2026-10-17-v11)). Additive; no existing
endpoint, response field, curve state or `blender-office` assertion changes.
Claude Code implements the pure algorithm module (task K1) against this contract;
Codex wires it into the backend (task 4, P0). Items marked **OPEN** need Codex
confirmation; names not found in [OFFICE_DEMO_TARGET_V1](OFFICE_DEMO_TARGET_V1.md)
or the [pipeline map](../engineering/OFFICE_PIPELINE_MAP.md) are `UNKNOWN`.

Method: [plan §3.2](../agents/OFFICE_DEMO_PLAN_20261101.md#3-方法觀測--假設--檢索--驗證).
Endpoint ground estimates: [interval observation v1](OFFICE_INTERVAL_OBSERVATION_V1.md).
Negative evidence from retrieval: [frame retrieval v1](OFFICE_FRAME_RETRIEVAL_V1.md).

## 1. Purpose and authority

Given the two observed endpoints of a blind interval (e.g. the Office humanoid
run: FRONT 4.6 s and REAR 8.2 s, gap 4.8–8.0 s, D18; the legacy 2.9393 m cylinder
run keeps FRONT 4.4 s and REAR 8.6 s, gap 4.6–8.4 s), produce:

- up to **K representative hypothesis paths** with timestamped samples, and
- a **reachable region per timestamp** (every floor point consistent with all
  constraints at that time).

Rules that do not change:

- Every sample and region is `INFERRED_HYPOTHESIS`. The existing curve state for
  the gap stays `MISSING` with null positions; hypotheses are a separate layer and
  never fill `world_position` or the motion/association samples.
- Ranking is by **plausibility** (`CONFIGURED_PLAUSIBILITY_NOT_PROBABILITY`). Scores
  are not normalised and must not be shown or summed as probabilities.
- `physical_authority` is `UNKNOWN`: the walkable check uses an annotation, not
  collision, body-clearance or doorway certification.
- `identity_verdict` is `UNCONFIRMED`; the two endpoints are assumed to be the same
  target only for the purpose of this hypothesis (they come from an existing
  `INFERRED_CROSS_CAMERA` candidate or the selected target).
- Inputs exclude GT, renderer trajectories, target visibility and depth. The speed
  range is configuration, not measured from GT.
- Deterministic: no RNG (`reconstruction_rng: NOT_USED`), no model/tool calls,
  `agent_used: false`.

## 2. Conventions

METRES, source world axes right-handed Z-up; SECONDS on the source clock. Floor
points carry `z = floor_z_m`. Samples lie on the scene clock grid
(`time_step_s = 1 / sampling_hz`, Office `0.2`). The `provenance` block has the
shape of [interval observation §2.1](OFFICE_INTERVAL_OBSERVATION_V1.md#21-provenance-block-shared-by-all-three-k0-contracts)
with `producer: "blind-hypothesis"`. `output_sha256` follows the same rule.

## 3. Request

Schema id: `office-demo.blind-hypothesis-request.v1`. Transport (BH-Q1, resolved
in v1.1 by the C4b implementation, PR #44 @ `0942f5a`): there is no separate
endpoint; the registered person preset returns the response as an additive nested
`blind_hypotheses` object in the response of `POST /api/target_reconstruction`.
This section describes the **module-level** request that the backend assembles; the
client body of that route carries `session_ref`, `scene_id`, `camera_ids`, the
existing time window, `top_k`, `observation_ref`, optionally
`negative_evidence_refs` and `previous_response_sha256`, and **no** blind-interval
endpoints, evidence geometry, speed/config, paths or GT (C4b handoff,
`docs/engineering/C4B_OFFICE_PERSON_20261017.md`). Evidence refs are resolved to
entries server-side (unknown refs: `UNKNOWN`, `NEGATIVE_EVIDENCE_UNAVAILABLE`, a
backend reason); `previous_response_sha256` resolves only a server-held sealed
response of the same scene and session. Callers may not supply file paths, GT,
calibration, speed or annotation overrides; speed range and annotation refs are
resolved server-side from scene configuration and echoed.

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | `office-demo.blind-hypothesis-request.v1` |
| `session_ref`, `scene_id` | string | As in the target contract. |
| `candidate_ref` | string\|null | Existing cross-camera candidate whose gap is queried, or `null` with explicit endpoints. |
| `start`, `end` | endpoint | See §3.1. `end.timestamp_s > start.timestamp_s`. |
| `top_k` | integer | Strict integer 1–5 (same bound as `target_reconstruction`). |
| `negative_evidence` | array | §3.3; may be empty. Order is significant and recorded. |
| `previous_response_sha256` | string\|null | `output_sha256` of the response being extended; set when re-running after new negative evidence (§6). Must be accompanied by the module input `previous_response`. |

**Module input `previous_response`** (not a request field; v1.1, K5). The module is
pure and looks nothing up, so a re-run passes the complete previous response
object next to the request. Its canonical hash must equal
`previous_response_sha256` (§6). The backend keeps each sealed response and hands
it over (OPEN BH-Q10). A `previous_response_sha256` without the object fails
closed (`NEGATIVE_EVIDENCE_NOT_APPEND_ONLY`, `PREVIOUS_RESPONSE_MISSING`, never
silently ignored); the object without the hash is a malformed call, rejected by
the module before any computation.

### 3.1 Endpoint state

| Field | Type | Meaning |
| --- | --- | --- |
| `observation_ref` | string | Existing public observation (must resolve). |
| `camera_id` | string | Source camera. |
| `timestamp_s` | number | Source clock seconds. |
| `evidence_state` | enum | Must be `PROJECTED_OBSERVATION`. |
| `ground_estimate` | object | An [interval observation v1](OFFICE_INTERVAL_OBSERVATION_V1.md) object with `status: READY`. POINT → endpoint region is a disc of radius `pixel_sensitivity_m`; SEGMENT → the segment (OPEN BH-Q4). |

| `substitution` | object\|null | `null`, or the §3.1.1 record when the caller replaced an unusable endpoint (D7). When set, `observation_ref`, `camera_id`, `timestamp_s` and `ground_estimate` above are the **substitute's**. |

An endpoint whose `ground_estimate` is `UNKNOWN` makes the whole response
`UNKNOWN` (`ENDPOINT_UNUSABLE`); **the module never substitutes** a nearby
observation or timestamp. Only the caller (C4b) may do so, and only under §3.1.1.
An observation carrying `AMBIGUOUS_MERGE` is unusable as an endpoint until
2026-11-01 (D8, see [interval observation §4.1](OFFICE_INTERVAL_OBSERVATION_V1.md#41-basis-selection-from-contact_quality)),
so it never reaches this contract as a `READY` endpoint, and it cannot serve as
a substitute either.

**Humanoid Office run endpoints (D18).** For the humanoid run the blind interval
is FRONT 4.6 s (last observation) → REAR 8.2 s (earliest observation), i.e. the
gap 4.8–8.0 s between the two endpoint observations. Both are actual
observations, so this interval needs **no** D7 substitution and D7 is not an
alternative way to obtain it. The legacy 2.9393 m run keeps 4.4 s → 8.6 s. The
endpoint pair is chosen by the caller; this contract does not change.

### 3.1.1 Endpoint substitution (caller-side, D7)

When a blind-interval endpoint is unusable, the caller may use the **nearest
usable observation on the same track**, at most `MAX_ENDPOINT_SUBSTITUTION_S`
(1.0 s, from the versioned configuration) away. The substitution is explicit;
the original endpoint stays `UNKNOWN` and is never rewritten.

Rules (all must hold):

1. Same track: the substitute belongs to the same `track_ref` as the original
   (the existing field name is `UNKNOWN`, OPEN BH-Q9). The module cannot see
   tracks; the caller asserts this and records the examined observations.
2. **Outward only:** for `start`, the substitute is earlier than the original
   (`time_offset_s < 0`); for `end`, later (`time_offset_s > 0`). The blind
   interval can only grow, never shrink. (D7 says "back or ahead"; this is the
   reading that cannot hide an observation inside the interval.)
3. `abs(time_offset_s) <= 1.0`.
4. Nearest: no usable observation of that track lies between the original and the
   substitute. Observations that were examined and found unusable are listed in
   `skipped_observation_refs`.
5. The substitute has its own `ground_estimate` with `status: READY`; one
   substitution per endpoint, no chaining, and the substitute is never
   `AMBIGUOUS_MERGE`.

Record (request side, in `start.substitution` / `end.substitution`):

```json
{
  "substitution": {
    "rule": "SAME_TRACK_NEAREST_USABLE_OUTWARD_V1",
    "track_ref": "UNKNOWN",
    "original": {"observation_ref": "observation:add9f687d311742321e80dff", "timestamp_s": 4.4, "ground_estimate_status": "UNKNOWN", "ground_estimate_reason": "HEAD_ANCHOR_UNRELIABLE"},
    "substitute": {"observation_ref": "observation:<front-4.2>", "timestamp_s": 4.2},
    "time_offset_s": -0.2,
    "max_offset_s": 1.0,
    "skipped_observation_refs": []
  }
}
```

(Illustrative; the 4.2 s observation has not been checked. `time_offset_s` =
substitute minus original, in seconds.) The module checks what it can see: rules
2, 3 and 5, that `original.ground_estimate_status` is `UNKNOWN`, and that the
numbers are consistent; otherwise `UNKNOWN`, `ENDPOINT_SUBSTITUTION_INVALID`.
The interval used by every other rule (§4, `INTERVAL_TOO_LONG`) is the
substituted one.

The response repeats every substitution in `endpoint_substitutions` (§5) and in
`trace` (step `ENDPOINT_SUBSTITUTED`). **Display is mandatory:** the workbench UI
and any recorded Agent/replay trace must show, wherever the interval or its
hypotheses are shown, that the endpoint was substituted, with the original
reference and time, its `UNKNOWN` reason, the substitute reference and time, and
the signed time difference. The original observation stays visible as an
observed, flagged (`UNKNOWN` ground) point; it is not drawn as the start of the
hypothesis. Downstream contracts (retrieval) echo the same record.

### 3.2 Server-resolved configuration (echoed in the response)

| Field | Meaning |
| --- | --- |
| `speed_range_m_s` | `{min, max, source: "CONFIGURED_NOT_GT", config_ref, config_sha256, config_version, freeze_status}`; `0 <= min < max <= MAX_SPEED_M_S (8.0)`, and for person-sized runs `max <= 2.0` in the current config version (D12). `freeze_status` is `DRAFT_NOT_FROZEN` or `FROZEN_BEFORE_EVALUATION`; see the rule below the table. Humanoid default `[0.0, 2.0]`. |
| `walkable_ref` | `{map_ref, sha256, map_kind}` map of walkable regions on the floor plane; `map_kind` is `ANNOTATION_INTERIM` (annotations, until K7 passes) or `SOURCE_DERIVED` (C7 bundle, D3). Each region is `{area_ref, tier, walkable}`, see below. |
| `portal_ref` | `{map_ref, sha256}` doorway/portal segments joining walkable regions (same map bundle as `walkable_ref` when derived). |
| `restricted_ref` | `{map_ref, sha256, source: "USER_CONFIRMED_ANNOTATION", tier: "RESTRICTED_POLICY"}` or `null` (v1.1, D15): the restricted-policy layer of §3.2.1. A scene without a user-confirmed restricted region has `null`; nothing is then labelled. Not part of `walkable_ref`. |
| `visibility_index_ref` | `{index_ref, sha256, method}` camera floor-visibility index from [frame retrieval v1 §2](OFFICE_FRAME_RETRIEVAL_V1.md#2-camera-floor-visibility-index). |
| `body_radius_m` | Target radius used to erode visible footprints. It is the per-run declared value from `provenance.run_parameters` (D6; new runs 0.25 m, existing Office run 0.1482 m, origin `UNKNOWN`), not a scene constant and never GT. |
| `grid_step_m`, `time_step_s` | Lattice spacing (proposed 0.25 m) and clock step. |

Speed range (D2, D12): the range comes from a **versioned configuration**
(`CONFIGURED_NOT_GT`), never from GT or a route's own motion. It is chosen to be
realistic and frozen (`freeze_status: FROZEN_BEFORE_EVALUATION`) before any
evaluation; it is not tuned per route or after seeing results, and any change is
a new `config_version`. RQ2 evaluation accepts only responses whose
configuration is frozen. The current upper limit is `<= 2.0 m/s`: D12 records
that at `>= 2.14 m/s` the two unannotated doorway gaps of the Office map start to
matter (computed for a 4.2 s interval; with a D7-substituted start of 4.4 s the
same arithmetic, 8.96 m / 4.4 s, gives about 2.04 m/s — recomputed, not
verified). Raising the limit therefore needs a new config version and a C7/K7
re-check of portal connectivity. The 2.14 m/s figure was computed for the legacy
4.4 → 8.6 s endpoints; the humanoid run's 4.6 → 8.2 s interval (D18) has not been
re-computed here (`UNKNOWN`) and needs its own check against the derived map before
the configured `max` is called sufficient for that run.

Walkable map regions (D11, D3; `tier` matches C7 [#29](https://github.com/Polalalabear/amidst/issues/29)):

| Field | Values | Meaning |
| --- | --- | --- |
| `tier` | `SOURCE_DERIVED`, `ANNOTATION_ONLY`, `UNKNOWN` | Where the region comes from: derived from the source mesh (C7), annotation only, or not established. |
| `walkable` | `TRUE`, `UNKNOWN` | `TRUE`: part of the walkable map. `UNKNOWN`: area-level "walkability not established", used **only** for seating or similar areas whose individual pieces the source mesh cannot resolve (D16, below). |

A region with `tier: UNKNOWN` must have `walkable: UNKNOWN`; a map that violates
this, or has no regions, is `WALKABLE_ANNOTATION_UNAVAILABLE`. Space that is
established as not walkable is simply absent from the map (the map producer has
already subtracted obstacles). Physical traversability stays `UNKNOWN` for every
region, whatever its tier. `RESTRICTED_POLICY` is **not** a tier of a walkable-map
region; it belongs to the separate layer of §3.2.1 and appears on links as a tier
label (§5.1).

**Seats and lecterns (D16, revises D11).** Seats and lecterns that the source mesh
resolves piece by piece are **physical obstacles**: their footprints are subtracted
from the walkable map like any other obstacle, and the aisles between rows are
walkable as derived from the source mesh (K7 report: auditorium, 22.06 m²
subtracted, 9.36 m² of aisle). Only a seating area that the source mesh cannot
resolve piece by piece is a `walkable: UNKNOWN` region. D11's other requirements
stand unchanged: no endpoint (or anything) is moved, snapped or extended to the
nearest walkable point, and a path through a `walkable: UNKNOWN` region is kept but
labelled, never promoted to `PASS` and never given a false `READY`. The earlier
wording of D11 that treated the Office seating area as `UNKNOWN` "under fallback 2C,
not subtracted as an obstacle" no longer applies where the source mesh resolves the
seats.

### 3.2.1 Restricted-policy layer (D15)

A *restricted region* is a floor area that the user has confirmed, region by
region, as **off limits by policy**. The Office west area, annotated
`OBSTACLE_1F_OFFICE_01/02`, is the first case (source-mesh humanoid-walkable
area 64.4 m²). The annotation is correct; the defect of the earlier map was that it
mixed "restricted" with "physical obstacle". D15 separates them:

- **Not an obstacle.** The area is physically enterable. It stays in the walkable
  map exactly as the source mesh derives it (D3). Restricted regions are neither
  subtracted from the lattice nor excluded from reachable regions, paths, `speed`
  or `unseen` checks: "may have entered a restricted area" is itself an
  investigative lead, so a path through it is **allowed but labelled**.
- **Separate layer.** `restricted_ref` names a map of restricted regions
  `{region_id, tier: "RESTRICTED_POLICY", geometry, confirmation_ref}` with its
  own hash, outside `walkable_ref`/`portal_ref`. Where the layer is stored and the
  region ids are `UNKNOWN` until C7 delivers it (D15 asks C7 to output the layer and
  its tier).
- **Authority and the D3 exception.** D3 says annotations are cross-checks only and
  not an inference input. The restricted layer is the **explicit exception**, limited
  to regions the user confirmed one by one (`confirmation_ref`); an annotation that
  has not been confirmed that way must not enter the layer. Physical walkable
  areas, portals and obstacles remain derived from the source mesh only. The layer
  carries a hash like any other map and is echoed in `provenance.annotation_sha256`
  (key `restricted`). It changes **labels only**: it adds no constraint, changes no
  reachability, score or check result.
- **Labelling.** For every link of `checks.walkable.segments[]` (§5.1) any part of
  which lies in a restricted region, `tiers` includes `RESTRICTED_POLICY` (next to the
  tier of the physical region, e.g. `SOURCE_DERIVED`) and `area_refs` includes the
  restricted `region_id`. `walkable` of the link keeps the value given by the
  physical map. `checks.walkable.restricted_area_crossed` is `true` when any link
  carries the tier. Workbench UIs use the same mechanism as for
  `walkable: UNKNOWN`: a distinct style (K4: dashed line with a label, "enters a
  restricted area"), different from "passes an unconfirmed area"; both labels can
  apply to one path. Whether a restricted crossing should instead change
  `result` is OPEN BH-Q12.
- **Cannot create walkability.** A restricted region lying outside the physical map
  has no effect; it never makes a violation a pass.
- **Reachable regions** may flag cells in restricted regions (§5.2,
  `restricted_policy_sample_indices`, proposed, BH-Q12).
- **Interval observation.** The layer never clips a `ground_estimate`
  ([interval observation §4.3](OFFICE_INTERVAL_OBSERVATION_V1.md#43-clipping)).
- Physical navigation stays `UNKNOWN`; restriction is a policy statement and says
  nothing about identity or intent.

### 3.3 Negative evidence entry

| Field | Type | Meaning |
| --- | --- | --- |
| `negative_evidence_ref` | string | Opaque, stable ref. |
| `origin` | enum | `BLIND_INTERVAL_BASELINE` (all frames of all cameras inside the gap) or `RETRIEVAL_FEEDBACK` (from a retrieval query). |
| `camera_id` | string | Camera whose frames showed no detection. |
| `frame_refs` | array | Frames that contributed; each has `timestamp_s`. |
| `visibility_ref` | string | Footprint entry used (traceability only; the module cannot resolve it). |
| `visible_floor` | object | The **resolved** footprint, copied by the backend from the visibility-index entry: `{method, floor_z_m, polygons: [[[x, y], ...], ...], index_sha256}`. `method` must be `SOURCE_MESH_RAYCAST`. `polygons` may be empty (the camera sees none of the gap floor); an empty entry is valid and prunes nothing. |
| `detection_result` | enum | Must be `NO_DETECTION`. |
| `detection_producer` | object | `{producer, version}` of the perception run (e.g. perception v2). |
| `retrieval_query_id` | string\|null | Contract C query that produced it. |
| `sha256` | string | Canonical hash of the entry **without** the `sha256` field: the module recomputes it (K1 `canonical_sha256`: sorted keys, compact separators, no NaN, UTF-8; byte-exact rule is OPEN IO-Q7). |

Entries are produced only by the rules in
[frame retrieval v1 §6](OFFICE_FRAME_RETRIEVAL_V1.md#6-from-no-detection-to-negative-evidence).
`DETECTION_PRESENT` and `UNKNOWN` frames are never negative evidence. The module
is pure and does no lookups, so an entry that carries only `visibility_ref` is
`NEGATIVE_EVIDENCE_INVALID`; so is an entry whose `visible_floor.method` is not
`SOURCE_MESH_RAYCAST`, whose `floor_z_m` differs from the scene floor, whose
frames are empty, whose `negative_evidence_ref` repeats, or whose frame time is
not inside the open blind interval (the endpoints' own frames are never negative
evidence). An entry whose `sha256` differs from the recomputed value is
`NEGATIVE_EVIDENCE_INVALID`, `problem: SHA256_MISMATCH`; this applies to every
origin, including `BLIND_INTERVAL_BASELINE` entries built by the backend and to
entries in a re-run (editing an old entry's content, ref or hash is detected by the
fingerprint of §6).

## 4. Computation rules

1. **Lattice.** Cells of `grid_step_m` inside the walkable map regions
   (`walkable: TRUE` or `UNKNOWN`, §3.2); adjacency only within a region or across
   a portal segment (no tolerance bridging of gaps between regions). No cell
   outside the map exists. An endpoint region must contain at least one cell;
   assigning an endpoint region to lattice cells may be off by up to half a cell
   diagonal, but an endpoint is **never moved, snapped or extended to the nearest
   walkable point** (D11): outside the map is `ENDPOINT_OUTSIDE_WALKABLE`, inside
   a `walkable: UNKNOWN` region is valid and its first/last link is labelled
   `UNKNOWN`.
2. **Times.** `t_i = start.timestamp_s + i * time_step_s`, excluding both
   endpoints, up to `end.timestamp_s - time_step_s`.
3. **Unseen mask.** For each `t_i` and each negative-evidence frame at `t_i`
   (within half a clock step), a cell is excluded if the disc of radius
   `body_radius_m` around it lies **fully inside** the camera's visible footprint
   (footprint eroded by the body radius). Partly visible cells are kept: the rule
   errs toward not pruning a true path. Frames that are `MISSING` contribute
   nothing. A cell stands for its **square** (rule 8), so the mask that prunes a
   region cell erodes the footprint by `body_radius_m` plus half a cell diagonal
   (`grid_step_m * sqrt(2) / 2`): a cell is dropped only if its whole square, with
   the body disc, is inside the footprint. The `unseen` check on a path sample
   (rule 8) erodes by `body_radius_m` only, so a sample that passes it never lies
   in a pruned cell.
4. **Reachable region.** Forward reachability from the start region and backward
   reachability from the end region, each with step reach `max_speed * time_step_s`
   along lattice adjacency, intersected with the unseen mask:
   `R(t_i) = Fwd(t_i) ∩ Bwd(t_i) ∩ Unseen(t_i)`.
5. **Paths.** A path picks one cell per `t_i` from `R(t_i)`, with consecutive
   cells reachable at `≤ max_speed`, and its mean speed over the whole interval
   `≥ min_speed` (mean, so stopping is allowed). Candidate pool bounded by
   `MAX_CANDIDATE_PATHS`; deterministic generation (the algorithm is declared in
   `trace`); ties broken by `hypothesis_ref` lexical order. v1 representatives
   may be constant-speed traversals of straightened routes (no dwell, route
   reported as `route_m`); reachable regions still allow dwell, so they are a
   superset of what the representatives cover. "Superset" is measured on grid-cell
   squares (rule 8): a sample whose square has no cell centre on the map (a strip
   along a wall narrower than half a step; no cell exists there, rule 1) is
   exempt, and the checks recomputed on the samples stay authoritative. An
   implementation may report the exceptions as a diagnostic (K1: `trace` step
   `SAMPLE_REGION_CONSISTENCY`); they are not a `FAIL`.
6. **Plausibility.** Configured cost combining path length, turning and deviation
   from a configured nominal speed; `score = -cost`, higher is more plausible.
   Components are reported. Weights live in the config (`config_sha256`).
7. **Representatives.** Select K by score with a diversity rule: a path is
   skipped if its maximum distance to an already selected path at every `t_i` is
   below `MIN_SEPARATION_M`. **Distance rule only:** a "same portal sequence"
   rule would leave K = 1 for any blind interval inside one room (e.g. Office);
   `portal_sequence` is still reported.
8. **Checks.** Every returned path carries `speed`, `walkable` and `unseen` checks
   recomputed on its own samples (not inherited from the lattice), so a
   consumer can audit each claim. The `walkable` check labels every link
   (§5.1): a path through a `walkable: UNKNOWN` region is kept, but marked, never
   promoted to `PASS`. A sample inside a portal footprint passes the walkable
   check (a doorway footprint is passable by definition, with the portal's tier;
   physical clearance stays `UNKNOWN`). The "fully inside the visible footprint"
   test in rule 3 is on the closed set (a cell whose disc touches the footprint
   boundary from inside is excluded). **Region semantics:** a reachable region is
   the union of the squares (side `grid_step_m`, centred on the cell centres) of
   the cells in `samples`; consumers draw and measure it that way. Reachable
   regions are widened conservatively for lattice distortion: by
   `lattice_metric_factor` (multiplicative) **and** by the additive
   `reach_slack_m = grid_step_m * sqrt(2)` (one cell diagonal), both echoed in the
   configuration, so the lattice never prunes a path the continuous problem
   allows. Endpoint regions seed the lattice only through cells they can see
   along the map (the straight segment from the nearest point of the endpoint
   region within the map to the cell centre is on the map), never through a wall.
   Limit: a passage narrower than about `grid_step_m * sqrt(2)`, in particular
   a diagonal one, can disconnect on the lattice, and no additive slack repairs a
   disconnected lattice; such maps are rejected by the C7/K7 map acceptance, not
   handled here. The slack is verified against exact visibility-graph geodesics on
   test maps (concave corners), not proved.

## 5. Response

Schema id: `workbench.blind-hypothesis.v1`.

| Field | Type | Meaning |
| --- | --- | --- |
| `status` | enum | `READY` or `UNKNOWN`. |
| `reason` | string\|null | §7 code when `UNKNOWN`. |
| `interval` | object | `{start_s, end_s, duration_s, start_observation_ref, end_observation_ref}`; the **used** (possibly substituted) endpoints. |
| `endpoint_substitutions` | array | One entry per substituted endpoint, else `[]` (§3.1.1): `{endpoint: "START"\|"END", original_observation_ref, original_timestamp_s, original_reason, substitute_observation_ref, substitute_timestamp_s, time_offset_s, max_offset_s, rule, track_ref, skipped_observation_refs}`. `original_reason` is the original `ground_estimate.reason`; the original endpoint itself stays `UNKNOWN`. |
| `configuration` | object | §3.2 echo including hashes. |
| `hypotheses` | array | ACTIVE paths, rank 1..≤K (§5.1). |
| `pruned_hypotheses` | array | Paths that were ACTIVE in the previous response and fail `unseen` against a **new** entry of this re-run, and are not re-selected (§6). Only this step's paths; earlier ones stay in the carried-over `pruning_log`. |
| `reachable_regions` | array | One per `t_i` (§5.2). |
| `rejected_counts` | object | Pool paths dropped, by check: `{speed, walkable, unseen, diversity}`. |
| `negative_evidence_applied` | array | `negative_evidence_ref`s in application order. |
| `pruning_log` | array | §6. |
| `limits` | object | Effective caps and whether any was hit. |
| `trace` | array | Algorithmic decisions (as in the target contract); steps this contract defines are listed in §5.3. |
| `evidence_state` | string | `INFERRED_HYPOTHESIS`. |
| `ranking_basis` | string | `CONFIGURED_PLAUSIBILITY_NOT_PROBABILITY`. |
| `physical_authority` | string | `UNKNOWN`. |
| `identity_verdict` | string | `UNCONFIRMED`. |
| `agent_used` | boolean | `false`. |
| `reconstruction_rng` | string | `NOT_USED`. |
| `provenance`, `output_sha256` | | §2. |

### 5.1 Hypothesis path

| Field | Type | Meaning |
| --- | --- | --- |
| `hypothesis_ref` | string | Stable, derived from content hash of the samples + config. |
| `rank` | integer\|null | 1 = most plausible in this response; `null` for a PRUNED path. |
| `status` | enum | `ACTIVE` or `PRUNED`. |
| `pruned_by` | string\|null | `pruning_ref` of the first new entry (application order) the path conflicts with, when PRUNED. A PRUNED path keeps its samples; its `checks.unseen` is recomputed (`FAIL`, with `conflicts`). |
| `plausibility` | object | `{score, basis: "CONFIGURED_PLAUSIBILITY_NOT_PROBABILITY", components: {path_length_m, turn_rad, speed_deviation_m_s}}`. |
| `samples` | array | `{timestamp_s, position_m: [x,y,z], evidence_state: "INFERRED_HYPOTHESIS"}` for every `t_i`; no sample at the endpoints. |
| `route_m` | array | The straightened route `[[x, y], ...]` the samples follow (informational). |
| `portal_sequence` | array | Portal refs crossed, in order. |
| `checks.speed` | object | `{result, max_step_speed_m_s, mean_speed_m_s, limit_m_s: [min, max]}`. |
| `checks.walkable` | object | `{result, walkable_ref, violations: [{timestamp_s, position_m}], unconfirmed_area_crossed, restricted_area_crossed, segments}`; `segments` is described below the table. `restricted_area_crossed` (v1.1, D15) is `true` iff some link carries `RESTRICTED_POLICY`; `false` when `restricted_ref` is `null`. |
| `checks.unseen` | object | `{result, conflicts: [{timestamp_s, camera_id, negative_evidence_ref}], steps_without_negative_evidence}`; the last field counts `t_i` that no negative-evidence frame covers. |
| `physical_authority` | string | `UNKNOWN`. |

Check `result` is `PASS`, `FAIL` or `UNKNOWN`. ACTIVE paths have `PASS` on
`speed`; `walkable` is `PASS`, or `UNKNOWN` when the path passes an unconfirmed
area (D11); `unseen` is `PASS`, or `UNKNOWN` when some `t_i` has no
negative-evidence coverage (`steps_without_negative_evidence > 0`: nothing was
excluded there, so the claim is not made). Negative evidence whose method is not
`SOURCE_MESH_RAYCAST` is not a path-level `UNKNOWN`: it invalidates the request
(`NEGATIVE_EVIDENCE_INVALID`, §3.3). A `FAIL` path is never ACTIVE.

`checks.walkable.segments[]` (D11) labels every link between consecutive
times, including endpoint to first sample and last sample to endpoint:
`{from_timestamp_s, to_timestamp_s, walkable: "TRUE" | "UNKNOWN", area_refs: [...], tiers: [...]}`.
A link is `UNKNOWN` if any part of it lies in a `walkable: UNKNOWN` region.
`result: UNKNOWN` iff at least one link is `UNKNOWN` and none leaves the map;
`unconfirmed_area_crossed` is then `true`, and UIs must label the path as
"passes an unconfirmed area" in a style distinct from verified paths.
`tiers` lists the tiers of the physical regions the link touches (`SOURCE_DERIVED`,
`ANNOTATION_ONLY`, `UNKNOWN`) and, if any part of the link lies in a restricted
region (§3.2.1, D15), also `RESTRICTED_POLICY`, with the restricted `region_id` in
`area_refs`. The restricted tier never changes `walkable` of the link or `result`
(BH-Q12); it is what makes UIs show "enters a restricted area".

### 5.2 Reachable region

| Field | Type | Meaning |
| --- | --- | --- |
| `timestamp_s` | number | `t_i`. |
| `kind` | enum | `SAMPLE_SET` in v1 (`POLYGON` is reserved, not emitted). |
| `polygons` | array\|null | Always `null` in v1. Reserved: floor polygons `[[x, y], ...]` (z = `floor_z_m`), outer rings counter-clockwise. |
| `samples` | array\|null | Cell centres `[[x, y], ...]` with `cell_size_m`. |
| `cell_size_m` | number | Lattice spacing of `samples`. |
| `walkable_unknown_sample_indices` | array | Indices into `samples` whose cell lies in a `walkable: UNKNOWN` region (D11). |
| `restricted_policy_sample_indices` | array | Proposed (v1.1, D15, BH-Q12): indices into `samples` whose cell centre lies in a restricted region; `[]` when `restricted_ref` is `null`. Labels only; the cells stay in the region. |
| `area_m2` | number | Region area. |
| `max_extent_m` | number | Largest distance between two region points (band-width metric for RQ2). |
| `evidence_state` | string | `INFERRED_HYPOTHESIS`. |
| `truncated` | boolean | True if `MAX_REGION_SAMPLES` (or, for the reserved `POLYGON` kind, `MAX_REGION_VERTICES`) was hit; never silent. |

### 5.3 `trace` steps defined by this contract

Other steps are informative (the generation algorithm is declared in `trace`).

| `step` | Fields | Meaning |
| --- | --- | --- |
| `ENDPOINT_SUBSTITUTED` | `endpoint`, `original_timestamp_s`, `substitute_timestamp_s`, `time_offset_s` | §3.1.1. |
| `REQUEST_FINGERPRINT` | `request_sha256` | Canonical hash of the request **without** `negative_evidence`, `previous_response_sha256` and `top_k` (the fields a re-run may change). `null` if the request is not canonical JSON (then a re-run never matches). Basis of the same-request check of §6. |
| `NEGATIVE_EVIDENCE_FINGERPRINT` | `entries: [{negative_evidence_ref, sha256}]` | One element per applied entry, in application order. The response lists only evidence refs; this step lets a re-run detect an old entry whose content was edited while its ref stayed. |
| `PRUNING_RERUN` | `previous_response_sha256`, `new_negative_evidence`, `previous_active`, `hypotheses_pruned`, `hypotheses_surviving` | Present on a re-run (§6). `new_negative_evidence` lists the refs of the new entries. |
| `FAIL_CLOSED` | `reason`, optional `problem`, other detail | Present on every `UNKNOWN` response. `problem` is a sub-code (§7). For `REACHABLE_SET_EMPTY` it also names `first_emptying_negative_evidence_ref`, the first entry in application order whose application leaves some `R(t_i)` empty; this holds on first runs as well. |

`REQUEST_FINGERPRINT` and `NEGATIVE_EVIDENCE_FINGERPRINT` are part of every
response, so they enter `output_sha256`.

## 6. Pruning by new negative evidence

Pruning is a deterministic re-run, not an in-place edit:

1. The caller sends the same request plus appended `negative_evidence` and
   `previous_response_sha256`, and passes the previous response object as the
   module input `previous_response` (§3).
2. The module verifies, in this order, and answers `UNKNOWN` at the first failure
   (`reason: NEGATIVE_EVIDENCE_NOT_APPEND_ONLY` unless noted; `problem` is the
   sub-code recorded in the `FAIL_CLOSED` trace step):
   1. the previous response is present (`PREVIOUS_RESPONSE_MISSING`) and has
      schema `workbench.blind-hypothesis.v1` (`PREVIOUS_RESPONSE_SCHEMA`);
   2. its `output_sha256` equals `previous_response_sha256` **and** equals the
      recomputed canonical hash (`PREVIOUS_RESPONSE_HASH_MISMATCH`);
   3. its `status` is `READY` (`PREVIOUS_RESPONSE_NOT_READY`);
   4. its evidence list is present and consistent with its
      `NEGATIVE_EVIDENCE_FINGERPRINT` (`PREVIOUS_EVIDENCE_LIST_MISSING`,
      `PREVIOUS_EVIDENCE_LIST_INCONSISTENT`), and is a **prefix** of the new list,
      by ref **and** entry `sha256` (`EVIDENCE_NOT_A_PREFIX_EXTENSION`);
   5. the request is the same: its `REQUEST_FINGERPRINT` equals the previous one
      (`REQUEST_CHANGED`; `PREVIOUS_REQUEST_FINGERPRINT_MISSING` for a response
      that has none). Endpoints, scene, session and candidate may not change;
      `negative_evidence`, `previous_response_sha256` and `top_k` may;
   6. the `interval`, `configuration`, `provenance` and `endpoint_substitutions` of
      the new response equal the previous ones, and the previous ACTIVE paths lie on
      the same clock grid (`reason: PROVENANCE_MISMATCH`, `problem`
      `PREVIOUS_RESPONSE_INTERVAL`, `PREVIOUS_RESPONSE_CONFIGURATION`,
      `PREVIOUS_RESPONSE_PROVENANCE`, `PREVIOUS_RESPONSE_ENDPOINT_SUBSTITUTIONS`,
      `PREVIOUS_HYPOTHESIS_SAMPLE_TIMES`).
3. Regions and paths are recomputed from scratch with all evidence. A previously
   ACTIVE path that now fails `unseen` against a **new** entry and is not itself
   re-selected is listed in `pruned_hypotheses` with `status: PRUNED`,
   `rank: null`, `pruned_by` = the `pruning_ref` of the first new entry (in
   application order) it conflicts with, and `checks.unseen` recomputed. Surviving
   and newly selected paths are re-ranked in `hypotheses`. A previously ACTIVE path
   that conflicts **only with old evidence** means the previous response is not what
   is being extended: `NEGATIVE_EVIDENCE_NOT_APPEND_ONLY`,
   `PREVIOUS_HYPOTHESIS_CONFLICTS_WITH_PRIOR_EVIDENCE`.
4. `pruned_hypotheses` lists only this step's pruned paths. `pruning_log` carries
   the previous entries over unchanged and appends one entry per new evidence
   entry:

```json
{
  "pruning_ref": "pruning:<sha256-prefix>",
  "order": 1,
  "negative_evidence_ref": "negev:<id>",
  "camera_id": "CAM_1F_AUDITORIUM_REAR",
  "time_window_s": [6.0, 6.4],
  "hypotheses_pruned": ["hyp:<id>"],
  "region_area_before_m2": 41.75,
  "region_area_after_m2": 28.50,
  "previous_response_sha256": "<sha256>"
}
```

   - `order`: 1-based position of the entry in the **full** evidence list.
   - `pruning_ref`: `"pruning:" + sha256({previous_response_sha256, order,
     negative_evidence_ref, negative_evidence_sha256})[:24]` over the canonical JSON.
   - `time_window_s`: `[first, last]` clock step the entry acts on (its frames, on
     the clock grid), or `null` if it acts on none.
   - `region_area_before_m2` / `region_area_after_m2`: the **mean, over the entry's
     own clock steps, of the reachable-region area** (cells × `grid_step_m²`, in the
     sense of §4 rule 8), with entries `< order` applied (before) and entries
     `≤ order` applied (after). An entry that prunes nothing (empty or fully
     eroded footprint) reports the unchanged area, not 0. Because each entry
     averages over its own window, values of different entries are not comparable
     with each other; the exact per-`t_i` areas are in `reachable_regions`.
5. If the reachable region becomes empty at any `t_i`, the response is `UNKNOWN`,
   `REACHABLE_SET_EMPTY`; constraints are not relaxed, the evidence conflict is
   reported in `trace`, and the `FAIL_CLOSED` step names
   `first_emptying_negative_evidence_ref` (§5.3).

**Demo application mode (D19) — OPEN.** The user decided (D19, 2026-10-17, relayed
by the coordinator; the record in [#26](https://github.com/Polalalabear/amidst/issues/26)
was not yet posted when this was written) that the demo shows the hypotheses first
**without** applying negative evidence, then **with** it applied. C4b is to support
an explicit negative-evidence application mode, and Codex chooses the field name.
This contract defines no such field yet (today's C4b body only carries optional
`negative_evidence_refs`, default `[]`, §3); BH-Q13 stays OPEN until Codex has
implemented it, and the formal request/response field is added then. The
re-run semantics of steps 1–5 are unchanged by it.

The v1 transitional rule (a module that does not implement steps 1–5 answers with
`PRUNING_RERUN_NOT_IMPLEMENTED`) is **removed**: K5 implements this section, and a
v1.1 implementation must not emit that reason.

## 7. Fail-closed reasons

| `reason` | When |
| --- | --- |
| `ENDPOINT_UNUSABLE` | Missing/unresolvable endpoint, wrong state, or `ground_estimate` not READY. |
| `ENDPOINT_SUBSTITUTION_INVALID` | A `substitution` record violates §3.1.1 rules 2, 3 or 5, or is inconsistent. |
| `INTERVAL_INVALID` | `end <= start`, or not on the clock grid. |
| `INTERVAL_TOO_LONG` | `duration_s > MAX_BLIND_INTERVAL_S`. |
| `WALKABLE_ANNOTATION_UNAVAILABLE` | No walkable map, or an invalid one (§3.2); the floor plane is not substituted. (Name kept from the draft; it covers derived maps too.) |
| `SPEED_CONFIG_UNAVAILABLE` | No configured range, or it violates §3.2 bounds (including `source` not `CONFIGURED_NOT_GT`). |
| `ENDPOINT_OUTSIDE_WALKABLE` | An endpoint region has no map cell (neither `TRUE` nor `UNKNOWN`). Never repaired by snapping (D11). |
| `ENDPOINTS_UNREACHABLE` | No path at `max_speed` even without negative evidence. |
| `REACHABLE_SET_EMPTY` | §6. |
| `NEGATIVE_EVIDENCE_INVALID` / `NEGATIVE_EVIDENCE_NOT_APPEND_ONLY` | Entry fails §3.3 or §6 checks; the `FAIL_CLOSED` trace step carries a `problem` sub-code (below the table). |
| `NO_HYPOTHESIS_PASSED_CHECKS` | The reachable regions are non-empty but no candidate path passes `speed`, `walkable` and `unseen` (distinct from `REACHABLE_SET_EMPTY`; `rejected_counts` and `trace` give the reasons). |
| `SEARCH_BUDGET_EXHAUSTED` | A grid, time-step or negative-evidence cap, or the cooperative monotonic deadline, hit before completion. Hitting `MAX_CANDIDATE_PATHS` alone is **not** fail-closed: the response is `READY`, ranks within the bounded pool, and records it in `limits.hit`. |
| `PROVENANCE_MISMATCH` | Any hash differs from the loaded scene. |

`UNKNOWN` responses carry `hypotheses: []`, `reachable_regions: []` and the
`trace`; no partial paths are presented as results.

`problem` sub-codes (in the `FAIL_CLOSED` trace step, v1.1):

| `reason` | `problem` |
| --- | --- |
| `NEGATIVE_EVIDENCE_NOT_APPEND_ONLY` | `PREVIOUS_RESPONSE_MISSING`, `PREVIOUS_RESPONSE_SCHEMA`, `PREVIOUS_RESPONSE_HASH_MISMATCH`, `PREVIOUS_RESPONSE_NOT_READY`, `PREVIOUS_EVIDENCE_LIST_MISSING`, `PREVIOUS_EVIDENCE_LIST_INCONSISTENT`, `EVIDENCE_NOT_A_PREFIX_EXTENSION`, `PREVIOUS_REQUEST_FINGERPRINT_MISSING`, `REQUEST_CHANGED`, `PREVIOUS_HYPOTHESIS_CONFLICTS_WITH_PRIOR_EVIDENCE` |
| `NEGATIVE_EVIDENCE_INVALID` | `SHA256_MISMATCH`; the K1 module also uses structural codes such as `FIELDS` and `REF_MISSING_OR_DUPLICATE` (informative, not enumerated here) |
| `PROVENANCE_MISMATCH` | `PREVIOUS_RESPONSE_INTERVAL`, `PREVIOUS_RESPONSE_CONFIGURATION`, `PREVIOUS_RESPONSE_PROVENANCE`, `PREVIOUS_RESPONSE_ENDPOINT_SUBSTITUTIONS`, `PREVIOUS_HYPOTHESIS_SAMPLE_TIMES` |

## 8. Limits (proposed, OPEN BH-Q7)

| Limit | Proposed |
| --- | --- |
| `MAX_BLIND_INTERVAL_S` | 20.0 (plan §5 asks to relax `MAX_WINDOW_S = 10.0` for multi-camera routes) |
| `MAX_TIME_STEPS` | 100 |
| `MAX_GRID_CELLS` | 20 000 |
| `MAX_CANDIDATE_PATHS` | 256 (same order as `BEAM_WIDTH`) |
| `top_k` | 1–5 |
| `MIN_SEPARATION_M` | 0.75 (same as `MAX_OVERLAP_DISTANCE_M`) |
| `MAX_NEGATIVE_EVIDENCE` | 400 entries |
| `MAX_ENDPOINT_SUBSTITUTION_S` | 1.0 (D7; from the versioned configuration, not a caller field) |
| `MAX_REGION_VERTICES` / `MAX_REGION_SAMPLES` | 256 per polygon (reserved kind) / 2 000 per timestamp |
| Deadline | Cooperative monotonic deadline as in the target contract; UNKNOWN on expiry. The pure module reads no clock: the caller passes a stop callback. |

## 9. Example (illustrative numbers, not computed)

```json
{
  "schema_version": "workbench.blind-hypothesis.v1",
  "status": "READY",
  "reason": null,
  "interval": {"start_s": 4.6, "end_s": 8.2, "duration_s": 3.6, "start_observation_ref": "observation:<front-4.6>", "end_observation_ref": "observation:<rear-8.2>"},
  "endpoint_substitutions": [],
  "configuration": {
    "speed_range_m_s": {"min": 0.0, "max": 2.0, "source": "CONFIGURED_NOT_GT", "config_ref": "config:speed-humanoid-v1", "config_sha256": "<sha256>", "config_version": "v1", "freeze_status": "FROZEN_BEFORE_EVALUATION"},
    "walkable_ref": {"map_ref": "UNKNOWN", "sha256": "<sha256>", "map_kind": "SOURCE_DERIVED"},
    "portal_ref": {"map_ref": "UNKNOWN", "sha256": "<sha256>"},
    "restricted_ref": {"map_ref": "UNKNOWN", "sha256": "<sha256>", "source": "USER_CONFIRMED_ANNOTATION", "tier": "RESTRICTED_POLICY"},
    "visibility_index_ref": {"index_ref": "visidx:<id>", "sha256": "<sha256>", "method": "SOURCE_MESH_RAYCAST"},
    "body_radius_m": 0.25,
    "grid_step_m": 0.25,
    "time_step_s": 0.2
  },
  "hypotheses": [
    {
      "hypothesis_ref": "hyp:3f2a9c",
      "rank": 1,
      "status": "ACTIVE",
      "pruned_by": null,
      "plausibility": {"score": -6.42, "basis": "CONFIGURED_PLAUSIBILITY_NOT_PROBABILITY", "components": {"path_length_m": 6.10, "turn_rad": 0.35, "speed_deviation_m_s": 0.12}},
      "samples": [
        {"timestamp_s": 4.8, "position_m": [13.10, 4.70, 0.4959475898742676], "evidence_state": "INFERRED_HYPOTHESIS"},
        {"timestamp_s": 5.0, "position_m": [13.38, 4.85, 0.4959475898742676], "evidence_state": "INFERRED_HYPOTHESIS"}
      ],
      "portal_sequence": [],
      "checks": {
        "speed": {"result": "PASS", "max_step_speed_m_s": 1.62, "mean_speed_m_s": 1.45, "limit_m_s": [0.0, 2.0]},
        "walkable": {"result": "PASS", "walkable_ref": "UNKNOWN", "violations": [], "unconfirmed_area_crossed": false, "restricted_area_crossed": true, "segments": [{"from_timestamp_s": 4.6, "to_timestamp_s": 4.8, "walkable": "TRUE", "area_refs": ["UNKNOWN", "UNKNOWN"], "tiers": ["SOURCE_DERIVED", "RESTRICTED_POLICY"]}]},
        "unseen": {"result": "PASS", "conflicts": [], "steps_without_negative_evidence": 0}
      },
      "physical_authority": "UNKNOWN"
    }
  ],
  "pruned_hypotheses": [],
  "reachable_regions": [
    {"timestamp_s": 4.8, "kind": "SAMPLE_SET", "polygons": null, "samples": [[12.875, 4.375], [13.125, 4.375], [13.375, 4.375]], "cell_size_m": 0.25, "walkable_unknown_sample_indices": [], "restricted_policy_sample_indices": [0, 1], "area_m2": 0.64, "max_extent_m": 1.13, "evidence_state": "INFERRED_HYPOTHESIS", "truncated": false}
  ],
  "rejected_counts": {"speed": 112, "walkable": 0, "unseen": 37, "diversity": 9},
  "negative_evidence_applied": ["negev:baseline-front-4.8-8.0", "negev:baseline-rear-4.8-8.0"],
  "pruning_log": [],
  "limits": {"max_blind_interval_s": 20.0, "max_candidate_paths": 256, "hit": []},
  "trace": [
    {"step": "REQUEST_FINGERPRINT", "request_sha256": "<sha256>"},
    {"step": "NEGATIVE_EVIDENCE_FINGERPRINT", "entries": [{"negative_evidence_ref": "negev:baseline-front-4.8-8.0", "sha256": "<sha256>"}, {"negative_evidence_ref": "negev:baseline-rear-4.8-8.0", "sha256": "<sha256>"}]},
    {"step": "LATTICE_BUILT", "cells": 1840},
    {"step": "REPRESENTATIVES_SELECTED", "k": 1}
  ],
  "evidence_state": "INFERRED_HYPOTHESIS",
  "ranking_basis": "CONFIGURED_PLAUSIBILITY_NOT_PROBABILITY",
  "physical_authority": "UNKNOWN",
  "identity_verdict": "UNCONFIRMED",
  "agent_used": false,
  "reconstruction_rng": "NOT_USED",
  "provenance": {"scene_id": "blender-office", "run_ref": "UNKNOWN", "clock_id": "BLENDER_PILOT_CONFIGURED_SECONDS_5HZ", "source_sha256": "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e", "safe_inputs_sha256": "1ea62def6c843b3bae1c5e25584fa489915f08e678b28b6220dc88cc17b43163", "producer": "blind-hypothesis", "producer_version": "v1", "config_sha256": "<sha256>", "annotation_sha256": {"walkable": "<sha256>", "portals": "<sha256>", "restricted": "<sha256>"}, "run_parameters": {"declaration_source": "PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT", "declaration_ref": "setting:run-<new>-target-v1", "declaration_sha256": "<sha256>", "target_proxy": {"shape": "CYLINDER", "height_m": 1.70, "radius_m": 0.25, "label": "SYNTHETIC_CYLINDER_PERSON_SIZED"}, "head_height_prior": {"nominal_m": 1.70, "tolerance_m": 0.10}, "body_radius_m": 0.25, "foot_anchor_band_px": 2}, "gt_read": false},
  "output_sha256": "<sha256>"
}
```

Substituted-endpoint variant (illustrative; the humanoid run itself needs no
substitution, D18): if the 4.6 s endpoint were unusable and the 4.4 s observation
of the same track were `READY`, the response would have `interval.start_s: 4.4`,
`start_observation_ref` = the 4.4 s observation, and these fields (shown as one
object for validity):

```json
{
  "endpoint_substitutions": [
    {"endpoint": "START", "original_observation_ref": "observation:<front-4.6>", "original_timestamp_s": 4.6, "original_reason": "HEAD_ANCHOR_UNRELIABLE", "substitute_observation_ref": "observation:<front-4.4>", "substitute_timestamp_s": 4.4, "time_offset_s": -0.2, "max_offset_s": 1.0, "rule": "SAME_TRACK_NEAREST_USABLE_OUTWARD_V1", "track_ref": "UNKNOWN", "skipped_observation_refs": []}
  ],
  "trace": [{"step": "ENDPOINT_SUBSTITUTED", "endpoint": "START", "original_timestamp_s": 4.6, "substitute_timestamp_s": 4.4, "time_offset_s": -0.2}]
}
```

Pruning re-run variant (illustrative; fields that change in the second response
after one retrieval entry is appended):

```json
{
  "pruned_hypotheses": [
    {"hypothesis_ref": "hyp:7be410", "rank": null, "status": "PRUNED", "pruned_by": "pruning:<24-hex>", "checks": {"unseen": {"result": "FAIL", "conflicts": [{"timestamp_s": 6.2, "camera_id": "CAM_1F_AUDITORIUM_REAR", "negative_evidence_ref": "negev:frq9d41e0-rear"}], "steps_without_negative_evidence": 0}}}
  ],
  "pruning_log": [
    {"pruning_ref": "pruning:<24-hex>", "order": 3, "negative_evidence_ref": "negev:frq9d41e0-rear", "camera_id": "CAM_1F_AUDITORIUM_REAR", "time_window_s": [6.0, 6.4], "hypotheses_pruned": ["hyp:7be410"], "region_area_before_m2": 6.52, "region_area_after_m2": 4.31, "previous_response_sha256": "<sha256>"}
  ],
  "trace": [
    {"step": "PRUNING_RERUN", "previous_response_sha256": "<sha256>", "new_negative_evidence": ["negev:frq9d41e0-rear"], "previous_active": 3, "hypotheses_pruned": 1, "hypotheses_surviving": 2}
  ]
}
```

(`pruned_hypotheses` elements are shortened here to the fields that differ; a real
element has the full §5.1 shape. `order: 3` follows the two baseline entries of the
main example.)

Office caveat: with two cameras the gap has only its two endpoints as positive
evidence; negative evidence inside the gap needs footprints that actually cover
part of the gap floor (plan §10). If the Office cameras see none of the gap
floor, the baseline negative evidence prunes nothing, and the response must still
say so through `rejected_counts.unseen = 0`.

## 10. Evaluation boundary

RQ2 metrics (coverage of truth inside the band, band width, best-hypothesis
distance and rank) are computed by the Claude evaluation tool after the response
is frozen and hashed. The module never reads GT.

## 11. OPEN QUESTIONS for Codex

- **BH-Q1** *(RESOLVED by implementation, 2026-10-17: C4b, PR #44 @ `0942f5a`,
  returns an additive nested `blind_hypotheses` object on `POST /api/target_reconstruction`
  for the registered person preset; no new endpoint. Session handling: the existing
  research session; a 5 s cooperative deadline and 8 cached sealed responses per
  scene/session bound the work. The source is the C4b handoff document; PR #44 is
  not yet approved (CP2 open), so this records what was built, not a checkpoint
  decision.)*
- **BH-Q2** *(RESOLVED by D3, 2026-10-16: walkable areas, portals and obstacles
  are derived from the source mesh by C7 [#29](https://github.com/Polalalabear/amidst/issues/29);
  annotations are cross-checks only. K1 uses the annotations as `ANNOTATION_INTERIM`
  until K7 passes. Map refs and hashes stay `UNKNOWN` until C7 delivers.)*
- **BH-Q3** *(Draft resolution, §12: `SAMPLE_SET` only in v1; `POLYGON` reserved.)*
- **BH-Q4** *(Draft resolution, §12: the whole SEGMENT is the endpoint region.)*
- **BH-Q5** *(Draft resolution, §12: speed range from a versioned config, `max <= 2.0`
  now, frozen before evaluation (D2, D12); `min` applies to the interval mean.)*
- **BH-Q6** *(Draft resolution, §12: distance rule only.)*
- **BH-Q7** Confirm all §8 limits, especially `MAX_BLIND_INTERVAL_S` vs. the
  existing `MAX_WINDOW_S = 10.0`.
- **BH-Q8** Which existing ref gives the "same target" pairing of endpoints: a
  cross-camera `candidate_ref` only, or also the selected-target response?
- **BH-Q9** Existing field name of the track identifier used by D7 substitution
  (`track_ref` is a placeholder), and how C4b enumerates "usable observations on
  the same track" without reading GT.

- **BH-Q10** *(v1.1, K5 question 1)* The backend must keep each sealed hypothesis
  response and hand it to the module with the re-run request (lookup by
  `previous_response_sha256`). Acceptable, or should the module receive the previous
  *request* instead (the module would then recompute the previous response)? Also
  confirm that `BLIND_INTERVAL_BASELINE` entries built by the backend use the same
  canonical entry hash (§3.3).
- **BH-Q11** *(v1.1, K5 question 5)* Confirm the `region_area_before_m2` /
  `region_area_after_m2` definition (mean over the entry's own clock steps, §6) and
  that `pruned_hypotheses` lists only the current step's paths.
- **BH-Q12** *(v1.1, D15)* Restricted-policy layer: (a) a restricted crossing leaves
  `checks.walkable.result` unchanged and only adds the `RESTRICTED_POLICY` tier,
  `restricted_area_crossed` and `area_refs` (draft), or should it change `result`?
  (b) Add `restricted_policy_sample_indices` to reachable regions (draft)? (c) Does
  the C7 bundle carry `restricted_regions` per variant next to `regions`,
  `unknown_regions` and `portals` (the current builder emits none), and can the K1
  floor map accept it without any lattice effect? (d) Where are the per-region user
  confirmations recorded (`confirmation_ref`)?
- **BH-Q13** *(v1.1, D19)* Name and semantics of the explicit negative-evidence
  application mode that lets the demo show the hypotheses without, then with,
  negative evidence (chosen by Codex in C4b). OPEN until implemented; then the field
  is specified in §3 and §5.

## 12. Revision 2026-10-16

Draft revision after CP1 decisions D4–D13 ([#25](https://github.com/Polalalabear/amidst/issues/25))
and the contract deviations listed by K1 ([PR #33](https://github.com/Polalalabear/amidst/pull/33),
implemented against the earlier draft). Still a draft; it takes effect only when
CP1 is approved. Where two wordings were reasonable, the smallest and most
reversible one was written.

### 12.1 Decisions written into the contract

| Change | Section | Basis |
| --- | --- | --- |
| Endpoint substitution by the caller: nearest usable observation on the same track, at most 1.0 s, outward only; record in the request and in the response `endpoint_substitutions`, plus a `trace` step; UI and replay must display it; the original endpoint stays `UNKNOWN`; the module never substitutes; new reason `ENDPOINT_SUBSTITUTION_INVALID`; new limit `MAX_ENDPOINT_SUBSTITUTION_S`; new open question BH-Q9 (track field name). | §3.1, §3.1.1, §5, §7, §8, §9 | D7 |
| `AMBIGUOUS_MERGE` endpoint unusable until 2026-11-01; also not a valid substitute. | §3.1 | D8 |
| Walkable map regions carry `tier` (`SOURCE_DERIVED`/`ANNOTATION_ONLY`/`UNKNOWN`, as C7 #29) and `walkable` (`TRUE`/`UNKNOWN`). `UNKNOWN` regions enter the lattice; paths through them stay ACTIVE with `checks.walkable.result: UNKNOWN`, per-link `segments[]`, `unconfirmed_area_crossed`, and a distinct UI label ("passes an unconfirmed area"). No snapping of endpoints (or anything) to the nearest walkable point. Reachable regions flag cells in `UNKNOWN` regions. | §3.2, §4 rule 1, §4 rule 8, §5.1, §5.2 | D11, D3 |
| `body_radius_m` is the per-run declared value (0.25 m new runs, 0.1482 m existing Office run); `provenance.run_parameters` echoes the per-run declaration (head prior, body radius), never GT. | §3.2, §9 | D5, D6 |
| Speed range from a versioned configuration (`CONFIGURED_NOT_GT`), `max <= 2.0` m/s now, `freeze_status` echoed, frozen before evaluation, no per-route tuning; RQ2 accepts frozen configs only. The 2.14 m/s doorway-gap threshold is recorded with a note that D7 shortens it (about 2.04 m/s, recomputed, not verified). | §3.2, §9 | D12, D2 |
| Open questions BH-Q2 resolved (D3); BH-Q3 to BH-Q6 given draft resolutions below. | §11 | D3, K1 |

D9, D10 and D13 are schedule or verification decisions and do not change this
contract.

### 12.2 K1 deviations: adopted or rejected

| K1 deviation | Decision | Reason |
| --- | --- | --- |
| New reason `NO_HYPOTHESIS_PASSED_CHECKS` | **Adopted** (§7) | A non-empty reachable region with no path passing the checks is a different fact from an empty region; collapsing it into `REACHABLE_SET_EMPTY` would hide why nothing is shown. |
| New reason `PRUNING_RERUN_NOT_IMPLEMENTED` | **Adopted as transitional** (§6, §7) | Fail-closed is better than silently ignoring `previous_response_sha256`. Removed when K5 implements §6; a final v1 must not emit it. |
| Negative-evidence entries carry the resolved `visible_floor {method, floor_z_m, polygons, index_sha256}`, not only `visibility_ref` | **Adopted** (§3.3; [retrieval §5, §6](OFFICE_FRAME_RETRIEVAL_V1.md#6-from-no-detection-to-negative-evidence)) | The module is pure and cannot resolve a ref; without the polygons it cannot prune or even check the method. Non-`SOURCE_MESH_RAYCAST` entries are `NEGATIVE_EVIDENCE_INVALID`, and `unseen: UNKNOWN` now means incomplete coverage (this replaces the earlier draft wording in §5.1). An empty polygon list is valid and prunes nothing (two-camera Office case). |
| Portal footprint counts as passable in the walkable check | **Adopted** (§4 rule 8) | A portal is a doorway by definition; the unmarked-threshold case would otherwise reject honest paths. This does **not** bridge gaps between regions (decision draft §4, options 3A/3B: no tolerance bridging); physical clearance stays `UNKNOWN`. |
| Diversity uses the distance rule only (BH-Q6) | **Adopted** (§4 rule 7) | A same-portal-sequence rule leaves K = 1 for blind intervals inside one room (Office). `portal_sequence` is still reported. |
| `SAMPLE_SET` of cell centres with `cell_size_m` (BH-Q3) | **Adopted**, `POLYGON` reserved (§5.2) | Exact on the lattice and needs no polygon operations in the backend; reversible by emitting `POLYGON` later. |
| Whole SEGMENT as endpoint region (BH-Q4) | **Adopted** (§3.1) | Does not pick a point inside the interval; consistent with the interval-observation rule against collapsing a SEGMENT. |
| Minimum speed on the interval mean (BH-Q5) | **Adopted** (§4 rule 5) | Stopping stays allowed; avoids rejecting a path for one slow step. |
| `MAX_CANDIDATE_PATHS` hit is recorded in `limits.hit`, not fail-closed; grid cap is fail-closed (BH-Q7) | **Adopted** (§7, §8) | A bounded pool is still a truthful, ranked answer when the cap is disclosed; an over-large grid cannot be answered at all. |
| "Fully inside the visible footprint" is a closed-set test | **Adopted** (§4 rule 8) | The boundary belongs to the visible set: a cell whose disc touches the footprint boundary from inside counts as fully inside and is excluded. The effect is measure-zero; it is written down only so independent implementations agree. |
| Lattice conservative widening (`lattice_metric_factor`, half-diagonal tolerance) | **Adopted** (§4 rule 8) | Biased toward not pruning a true path; echoed in `configuration` so it is auditable. |
| Constant-speed traversal of straightened routes, `route_m` | **Adopted as a generation choice** (§4 rule 5, §5.1) | Generation algorithm is declared in `trace`, not frozen by the contract; reachable regions still allow dwell. |
| Additive fields: `route_m`, `checks.unseen.steps_without_negative_evidence`, `configuration.nominal_speed_m_s` / `plausibility_weights` / `lattice_metric_factor`, `walkable_ref.map_kind`, `provenance.floor_map_kind` | **Adopted** (`route_m`, `steps_without_negative_evidence`, `map_kind` written in the tables; the three configuration echoes and `floor_map_kind` are informational and are covered by `config_sha256` / `walkable_ref`) | Additive, no authority change, they make a response reproducible. |
| POINT endpoint requires `contact_quality: PASS`; endpoint region is a disc of radius `pixel_sensitivity_m` | **Adopted** (already interval observation §4 rule 1, BH §3.1) | Confirms existing text. |
| `output_sha256` uses sorted-key compact JSON with coordinates rounded to 1e-6 | **Proposed, IO-Q7 stays OPEN** | Canonicalisation must be shared with the backend's receipts; Codex confirms. |
| Pure function reads no clock; the caller passes a deadline callback | **Adopted** (§8, Deadline row read as caller-supplied) | Keeps determinism; the deadline is a request-side concern. |
| Interim map from annotations until K7 passes | **Adopted** (`map_kind: ANNOTATION_INTERIM`, §3.2) | Consistent with D3; annotations stay cross-checks only once the derived map exists. |
| Floor z of annotations (25 BU = 0.6175 m) differs from the bound plane (0.4959 m); module uses XY and config z | **Not contract text** | Cause `UNKNOWN`; C7 acceptance item. |

Rejected: none outright. Two items were kept narrower than K1 implemented:
`PRUNING_RERUN_NOT_IMPLEMENTED` is transitional only, and the fields above that are
purely implementation echoes are not made mandatory.

### 12.3 Conservativeness notes after the K1 review (PR #33)

Clarifications only; no field, reason or request shape changes.

| Change | Section | Basis |
| --- | --- | --- |
| A reachable region is the union of grid-cell squares; the region mask prunes a cell only if its whole square plus the body disc is inside the visible footprint (erosion `body_radius_m` + half cell diagonal). The sample-level `unseen` check keeps the `body_radius_m` erosion. | §4 rule 3, rule 8 | Opus stage-2 review: with centre-based masking a sample could pass the check while its cell was pruned. |
| The "superset of what the representatives cover" in rule 5 is on cell squares; samples in a wall strip with no cell centre on the map are exempt; the checks on samples are authoritative. | §4 rule 5 | Same review. |
| Additive slack `reach_slack_m = grid_step_m * sqrt(2)` replaces the half-diagonal slack, together with seeds that are visible from the endpoint region along the map; the lattice limit for passages narrower than about `grid_step_m * sqrt(2)` is stated. | §4 rule 8 | Same review: the half-diagonal slack fell short by up to 0.49 m at concave corners (square reading). The new value is measured, not proved. |

Rule 1 text is unchanged. Reading used by K1 (the review proposes writing it into
rule 1 in a later revision): an endpoint region must itself intersect the map
(regions, `UNKNOWN` regions, portals), the reported route starts at a point of the
endpoint region on the map, and the link from that point to the first cell is
checked against the map like every other link. Nothing is snapped, so the "off by
up to half a cell diagonal" sentence in rule 1 no longer describes a tolerance
K1 uses.


### 12.4 Known limitation: thin-wall tips (Opus re-check of K1 `7c01522`, 2026-10-17)

- Near the tip of a thin wall, a lattice cell whose centre is reachable by a body centre passing **closer than 0.15 m** to the wall can be missing from `reachable_regions` at some `t_i`: the lattice path around the tip is longer than the continuous path by more than `reach_slack_m` (0.354 m).
- With a body-centre clearance of at least 0.15 m (and therefore at the 0.25 m body radius), 412 random READY cases showed **no** missing reachable cell. A real person cannot use the uncovered cells, so this is accepted as a known limitation, not a conservativeness defect.
- Raising `reach_slack_m` was rejected: it grows region area by about 5 % and still cannot recover cells that lie across a thin wall.
- Passages narrower than one lattice cell are not guaranteed to connect; this errs towards `ENDPOINTS_UNREACHABLE` (UNKNOWN), never towards a false READY.
- K7 must flag map features thinner or narrower than one cell when it verifies the C7 map.

## Revision 2026-10-17 (v1.1)

Draft revision after the CP2 decisions D15–D18 ([#26](https://github.com/Polalalabear/amidst/issues/26))
and the K5 implementation ([PR #36](https://github.com/Polalalabear/amidst/pull/36),
"Suggested contract revisions"). Still a draft; it takes effect only when Codex
confirms and the PR merges.

| Change | Section | Basis |
| --- | --- | --- |
| Pruning re-run is specified in full: module input `previous_response`, ordered verification (schema, hash, `READY`, evidence prefix by ref and `sha256`, same request, same interval/configuration/provenance/substitutions), `pruned_hypotheses` lists only this step's paths with `rank: null`, `pruning_log` carried over. | §3, §5, §5.1, §6 | K5 (PR #36) |
| Trace steps `REQUEST_FINGERPRINT` and `NEGATIVE_EVIDENCE_FINGERPRINT` (in every response), `PRUNING_RERUN`, and `FAIL_CLOSED` with `problem`; `REACHABLE_SET_EMPTY` names `first_emptying_negative_evidence_ref`. | §5.3, §6, §7 | K5 |
| Negative-evidence `sha256` is the canonical hash of the entry without `sha256`, recomputed by the module; `SHA256_MISMATCH`; applies to backend-built baseline entries. | §3.3, §7 | K5 |
| `order`, `pruning_ref`, `time_window_s` and `region_area_before/after_m2` are defined. | §6 | K5 |
| `problem` sub-codes under `NEGATIVE_EVIDENCE_NOT_APPEND_ONLY`, `NEGATIVE_EVIDENCE_INVALID`, `PROVENANCE_MISMATCH`. | §7 | K5 |
| `PRUNING_RERUN_NOT_IMPLEMENTED` and the transitional paragraph are removed. | §6, §7 | K5 |
| Restricted-policy layer: separate from obstacles, allowed but labelled with tier `RESTRICTED_POLICY` in `checks.walkable.segments[].tiers`, source is user-confirmed annotation with hash, **explicit exception to D3**; new `restricted_ref`, `restricted_area_crossed`, proposed `restricted_policy_sample_indices`. | §3.2, §3.2.1, §5.1, §5.2 | D15 |
| **D11 revised:** seats and lecterns that the source mesh resolves are physical obstacles (aisles walkable from the source mesh); only unresolvable seating areas are `walkable: UNKNOWN`. D11's no-snapping and no-false-`READY` rules stay. | §3.2 | D16 |
| Humanoid run blind interval is 4.6 s → 8.2 s (gap 4.8–8.0 s), no D7 substitution; legacy run stays 4.4 s → 8.6 s; the D12 speed arithmetic was for the legacy interval and the humanoid interval is not re-computed here. Examples updated. | §1, §3.1, §3.2, §9 | D18, D12 |
| `provenance.run_parameters` echoes `foot_anchor_band_px` (same block in all three K0 contracts). Endpoints keep using only `near_m` / `far_m` / `point_m` of a `READY` `ground_estimate`; the new `basis` values and the R2 `diagnostics` rule are in the [interval observation contract](OFFICE_INTERVAL_OBSERVATION_V1.md#revision-2026-10-17-v11). | §3.1, §9 | D17, R2 |
| Substituted-endpoint example is now a valid JSON object; a pruning re-run example is added. | §9 | editorial |
| New open questions BH-Q10 to BH-Q12. | §11 | K5, D15 |
| OPEN note for the demo's "without, then with negative evidence" mode (field name to be chosen by Codex in C4b); new BH-Q13. | §6, §11 | D19 (#26) |
| BH-Q1 recorded as resolved by the C4b implementation: nested `blind_hypotheses` object on `POST /api/target_reconstruction`; client body shape stated; §3 is the module-level request. | §3, §11 | C4b (PR #44 @ `0942f5a`) |

Not changed: the lattice, unseen mask, reachable-region and path rules (§4), the
plausibility ranking, limits, `SAMPLE_SET`-only regions, D7 caller-side
substitution, D8 (`AMBIGUOUS_MERGE` unusable), D12 speed bound `max ≤ 2.0`.
