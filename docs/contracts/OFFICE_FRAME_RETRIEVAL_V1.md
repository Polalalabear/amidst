# Office Demo frame-retrieval contract v1

Status: **v1.2 DRAFT** for Codex confirmation, 2026-10-17 (task K0 revision of the
CP1-approved v1, merged at `dcb89f4`; the file name stays `_V1`, see
[Revision 2026-10-17 (v1.1)](#revision-2026-10-17-v11) and
[Revision 2026-10-17 (v1.2, K8 synthetic method)](#revision-2026-10-17-v12-k8-synthetic-method)).
Additive; the existing `timeline`, `query` and frame-wall interfaces and their
bounded indexes are unchanged, and a real conversion's output is unchanged by v1.2. Codex owns the floor-visibility index and query API (task 4, P1);
Claude Code owns the "suggested review" frame wall and the latency charts. Items
marked **OPEN** need Codex confirmation; names not found in
[OFFICE_DEMO_TARGET_V1](OFFICE_DEMO_TARGET_V1.md) or the
[pipeline map](../engineering/OFFICE_PIPELINE_MAP.md) are `UNKNOWN`.

Method: [plan §3.3–3.4](../agents/OFFICE_DEMO_PLAN_20261101.md#3-方法觀測--假設--檢索--驗證).
Hypothesis input: [blind hypothesis v1](OFFICE_BLIND_HYPOTHESIS_V1.md).
Shared conventions and provenance block:
[interval observation v1 §2](OFFICE_INTERVAL_OBSERVATION_V1.md#2-conventions).

## 1. Purpose and authority

Answer "which camera, which time window, which frames should an investigator look
at" for either a blind-interval hypothesis or a plain time range, by intersecting
the query's space-time extent with a precomputed per-camera floor-visibility
index, without scanning every frame. Then turn "no detection in the retrieved
frames" into negative evidence for the hypothesis module.

- A suggested frame is a pointer for review, not an observation, detection or
  identity claim. `identity_verdict` stays `UNCONFIRMED`.
- Retrieval reads no GT, renderer trajectory, target visibility or depth. The
  index describes cameras and static source geometry only.
- Deterministic; `agent_used: false`. Results are reproducible from the request,
  the index hash and the bundle hashes.

## 2. Camera floor-visibility index

One entry per camera (static cameras only in v1). Built offline by Codex.

| Field | Type | Meaning |
| --- | --- | --- |
| `visibility_ref` | string | Opaque, stable ref for the entry. |
| `camera_id` | string | Source camera id. |
| `valid_time_range_s` | `[t0, t1]` | Source-clock range the footprint applies to (whole run for static cameras). |
| `method` | enum | `SOURCE_MESH_RAYCAST` (calibration + floor plane + static source mesh occlusion) or `FRUSTUM_ONLY` (calibration + floor plane, no occlusion). v1.2: `SYNTHETIC_DECLARED_FOOTPRINT` (polygons declared by the K8 generator, no ray casting) appears **only** in a `data_origin: "SYNTHETIC"` index (K8 fixture) and never in the C5 real index. |
| `floor_z_m` | number | Floor plane height (Office 1F `0.4959475898742676`). |
| `visibility_rule` | enum | How one XY sample counts as visible (v1.1, D21). `FOOT_AND_TORSO_PROBES_VISIBLE`: the floor-clearance probe and the mid-height probe are both `VISIBLE` (either `UNKNOWN` → `UNKNOWN`; otherwise `NOT_VISIBLE`). `ANY_PROBE_VISIBLE`: any probe `VISIBLE`. (Office probe heights above the floor: foot +0.002 m, waist +0.852 m, head +1.702 m, per the C5 binding.) |
| `detectability` | object | `{min_predicted_px, required_px, detectability_factor, detector: {producer, version, difference_threshold, min_pixels}}` (v1.1, D21). `min_predicted_px` is the smallest image area, over a cell's nine samples, of a `2·body_radius × (mid − floor-clearance probe height)` box projected with the entry's calibration only. `required_px = detectability_factor × min_pixels`; default factor 4, Office `min_pixels` 28, so 112 px. |
| `polygons` | array | Floor polygons `[[x, y], ...]`, METRES, source axes, in which a no-detection may be **negative evidence**: see the entry condition below the table. |
| `suggestion_polygons` | array | Cells visible under `ANY_PROBE_VISIBLE` (v1.1, D21). Ranking of suggested frames only; never negative evidence. Absent for `FRUSTUM_ONLY` entries. |
| `cell_size_m` | number | Raster resolution used before polygonisation. |
| `area_m2` | number | Total area of `polygons`. |
| `negative_evidence_eligible` | boolean | `true` only for `SOURCE_MESH_RAYCAST` **with** `visibility_rule: FOOT_AND_TORSO_PROBES_VISIBLE`. v1.2: in a `data_origin: "SYNTHETIC"` index it may also be `true` for `SYNTHETIC_DECLARED_FOOTPRINT` with a **declared** `FOOT_AND_TORSO_PROBES_VISIBLE`. Either way the flag is a **necessary condition only**: a frame becomes negative evidence only after all checks of §6 pass. |
| `sha256` | string | Entry hash. |
| `provenance` | object | Shared block; `producer: "floor-visibility-index"`. |

**Entry condition for `polygons` (D21).** `polygons` contains a cell only if all nine
samples of the cell are visible under `FOOT_AND_TORSO_PROBES_VISIBLE`,
`detectability.min_predicted_px ≥ detectability.required_px`, and the whole cell lies
within source floor support. A visible probe says that one ray is clear, not how much
of the body is visible: a head-top probe can be clear while fewer pixels than the
detector minimum are exposed (at 16 m, 10 cm of head top is about 33 px, at 18 m about
26 px, below the 28 px component minimum). `ANY_PROBE_VISIBLE` therefore never yields
negative evidence. Per-probe sample codes are retained in the index so that any rule
can be recomputed from the index's source rays. The calibration-only detectability
check keeps the guard valid for another scene or a more distant camera; it does not
use GT or any perception output.

**Declared synthetic entries (v1.2, D23/K8).** In a `SYNTHETIC_DECLARED_FOOTPRINT`
entry the `polygons`, `visibility_rule` and `detectability` are **declared** by the
K8 generator. They are not the result of the nine-sample ray rule above, nor of the
calibration-only detectability area check: a synthetic index carries no source rays
or calibration evidence, and the entry condition above is not claimed for it. Only the
real index's `SOURCE_MESH_RAYCAST` entries carry that evidence. Synthetic index
entries are labelled `data_origin: "SYNTHETIC"` in their `provenance` block.

`FRUSTUM_ONLY` overstates what a camera sees (furniture, walls), so it may rank
suggestions but must never produce negative evidence. Whether static source-mesh
raycasts are allowed in an inference-side index (planning raycasts in
`plan_blender_pilot_sites.py` are GT-side) is OPEN FR-Q1. Footprints for the
corridor cameras are `UNKNOWN` (plan §5).

## 3. Request

Schema id: `office-demo.frame-retrieval-request.v1`. Endpoint name: OPEN FR-Q2
(this draft does not invent one). No caller paths, GT, footprint overrides or
unbounded ranges.

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | `office-demo.frame-retrieval-request.v1` |
| `session_ref`, `scene_id` | string | As in the target contract. |
| `query_kind` | enum | `HYPOTHESIS` or `TIME_RANGE`. |
| `hypothesis` | object\|null | For `HYPOTHESIS`: `{response_sha256, hypothesis_refs: [...] or [], use: "PATHS" or "REACHABLE_REGIONS"}`. Empty `hypothesis_refs` = all ACTIVE. |
| `time_range_s` | `[t0, t1]` | Required for `TIME_RANGE`; for `HYPOTHESIS` defaults to the blind interval and may only narrow it. |
| `camera_ids` | array\|null | Restrict cameras; `null` = all cameras in the scene, at most `MAX_CAMERAS = 4`. |
| `max_frames` | integer | Strict integer 1–`MAX_RESULT_FRAMES`. |

## 4. Matching rules

- **HYPOTHESIS / PATHS.** A frame of camera `c` at time `t` is suggested if some
  ACTIVE path's sample at `t` (within half a clock step) lies inside `c`'s
  footprint, with the body disc (`body_radius_m` from the hypothesis
  configuration) overlapping the footprint. The footprint used for matching and
  ranking is `suggestion_polygons` (an entry without it, i.e. `FRUSTUM_ONLY`, uses
  `polygons`); negative evidence uses `polygons` only (§6, D21).
- **HYPOTHESIS / REACHABLE_REGIONS.** Suggested if the reachable region at `t`
  overlaps `c`'s footprint; `overlap_area_m2` is reported.
- **TIME_RANGE.** Every valid frame of the selected cameras in range (footprint not
  used); this is the "all frames" baseline for RQ4.
- Consecutive suggested frames of one camera are merged into windows
  (gap ≤ one clock step).
- Ordering: windows by descending best `overlap_area_m2` (or `in_view_count`),
  then `camera_id`, then `start_s`. When more than `max_frames` match, keep that
  order, set `truncated: true` and report `frames_matched_total`; never drop
  silently.
- Frames without a valid RGB record (missing or hash-mismatched) are not
  suggested and are counted in `frames_unavailable`.

## 5. Response

Schema id: `workbench.frame-retrieval.v1`.

| Field | Type | Meaning |
| --- | --- | --- |
| `status` | enum | `READY` or `UNKNOWN`. |
| `reason` | string\|null | §7 code when `UNKNOWN`. |
| `query_id` | string | Stable hash-derived id of the normalised request + index hash. |
| `query` | object | Normalised request echo. In HYPOTHESIS mode it includes `hypothesis_interval` = the referenced response's `interval` and a copy of its `endpoint_substitutions` (D7), so the frame wall shows that an endpoint was substituted (original ref/time, `UNKNOWN` reason, substitute ref/time, signed time difference). |
| `results` | array | Per camera: `{camera_id, visibility_ref, method, windows: [...]}`. |
| `results[].windows[]` | object | `{start_s, end_s, frames: [...]}`. |
| `results[].windows[].frames[]` | object | `{frame_ref, timestamp_s, reason}` (§5.1). |
| `stats.frame_records_read` | integer | Frame records actually read to answer, counted by the server. |
| `stats.index_records_read` | integer | Visibility-index entries read. |
| `stats.frames_in_scope_total` | integer | All valid frames of the queried cameras in the time range (denominator for "fraction to review"). |
| `stats.frames_matched_total` | integer | Matches before `max_frames`. |
| `stats.frames_suggested` | integer | Returned frames. |
| `stats.frames_unavailable` | integer | §4 last bullet. |
| `stats.latency_ms` | object | `{index_lookup, frame_lookup, total}`, from a monotonic clock in the server process. |
| `truncated` | boolean | §4. |
| `scan_mode` | string | `INDEX`. A full frame scan is not a valid implementation. |
| `negative_evidence_candidates` | array | §6 entries ready to append to a hypothesis request (either query kind). Each carries the resolved `visible_floor` (§6). |
| `frame_outcomes` | array | Proposed (v1.1, K5, OPEN FR-Q8): one row per retrieved frame with its §6 outcome, for the frame wall (§6.3). |
| `identity_verdict` | string | `UNCONFIRMED`. |
| `agent_used` | boolean | `false`. |
| `provenance`, `output_sha256` | | Shared rules (including `run_parameters`, whose `body_radius_m` must equal the referenced hypothesis configuration, D5/D6; mismatch is `PROVENANCE_MISMATCH`); `producer: "frame-retrieval"`, plus `visibility_index_sha256`. `latency_ms` is excluded from `output_sha256` so replays hash equal (OPEN FR-Q5). |

`frame_ref` reuses the existing opaque, site/run-bound frame reference served by
`timeline` and the frame wall; its exact field name and format are `UNKNOWN`
(OPEN FR-Q3). Private paths are never returned.

### 5.1 Frame `reason`

| Field | Meaning |
| --- | --- |
| `kind` | `HYPOTHESIS_PATH_IN_VIEW`, `REACHABLE_REGION_IN_VIEW`, or `TIME_RANGE_ONLY`. |
| `walkable_status` | `TRUE` or `UNKNOWN` (D11), HYPOTHESIS mode only, else `null`. `UNKNOWN` if any matching path link, or any overlapping region cell, at this time lies in a `walkable: UNKNOWN` map region; the frame wall must label such frames as concerning an unconfirmed area. |
| `hypothesis_refs` | Paths whose sample at this time is in view (PATHS mode). |
| `overlap_area_m2` | Region ∩ footprint area (REACHABLE_REGIONS mode); `null` otherwise. |
| `in_view_count` | Number of matching paths (PATHS mode). |
| `footprint_method` | `SOURCE_MESH_RAYCAST` or `FRUSTUM_ONLY`; v1.2: also `SYNTHETIC_DECLARED_FOOTPRINT`, only in a synthetic retrieval (§2). |

## 6. From no detection to negative evidence

After retrieval, each suggested frame is checked against the **existing
precomputed perception results** for that frame (no new detector, no Agent):

| Frame outcome | Condition | Use |
| --- | --- | --- |
| `NO_DETECTION` | RGB record valid and hash-verified; the perception run evaluated the frame; zero measurements in the whole frame; footprint `method` is `SOURCE_MESH_RAYCAST` (v1.2: or `SYNTHETIC_DECLARED_FOOTPRINT` in a synthetic conversion, §6.1) with an eligible `visibility_rule` and matching detector parameters (§6.1). | Eligible negative evidence. |
| `DETECTION_PRESENT` | At least one measurement in the frame (any component, since identity is unconfirmed). | Never negative evidence. May be offered as a candidate `observation_ref` for human review; not an identity or position claim. |
| `UNKNOWN` | Frame unavailable, not evaluated by perception, `FRUSTUM_ONLY` footprint, a synthetic footprint outside a synthetic conversion, a visibility rule that is not eligible, mismatching detector parameters, or provenance mismatch. | Never negative evidence; never treated as "absent". |

**What the four flags mean for synthetic records (v1.2).** The `NO_DETECTION`
decision and its four flags (`frame_available`, `rgb_hash_verified`, `provenance_ok`,
`perception_evaluated`) are unchanged and still required, each exactly `true`. For a
real frame they state that the RGB record exists, its hash was verified against the
source, its provenance matches and the perception run evaluated it. For a synthetic
frame (K8) there are no rendered pixels: the flags are **declared values** of the K8
generator's JSON records, and what they bind is the synthetic record set identified
by the fixture hash. In that case `rgb_hash_verified` means only "the synthetic
record is the one in the hashed fixture"; no synthetic output may claim that RGB
pixels were verified or that a detector ran on images. The real meaning of every
flag is unchanged.

Eligible frames of one camera are grouped into a
[blind hypothesis §3.3](OFFICE_BLIND_HYPOTHESIS_V1.md#33-negative-evidence-entry)
entry with `origin: RETRIEVAL_FEEDBACK`, `retrieval_query_id`, `frame_refs`,
`visibility_ref`, the **resolved `visible_floor`** (`{method, floor_z_m, polygons,
index_sha256}`, copied from the index entry's `polygons` after the §6.1 rule checks, so
the pure hypothesis module can prune without any lookup; `index_sha256` binds the
rule and detectability of the entry, and `suggestion_polygons` are never copied), `detection_producer` (perception producer and version)
and a hash. The entry has exactly the hypothesis contract's field set: a synthetic
entry carries no `provenance` or `data_origin` field (v1.2); its method stays in
`visible_floor.method`. The same rule applies to `BLIND_INTERVAL_BASELINE` entries built by
the backend. A camera that sees none of the gap floor yields an entry with empty
`polygons`: valid, and it prunes nothing.

With an endpoint substitution (D7) the blind interval used here is the
substituted one. The original, unusable endpoint's own frame contains a
detection (the flagged observation), so it is `DETECTION_PRESENT` and is never
negative evidence; frames strictly between the substitute and the original
endpoint are treated like any other frame of the interval. The response lists these drafts in `negative_evidence_candidates`; the
caller (frontend or Agent replay) appends them to the hypothesis request, so each
pruning step is an explicit, logged re-run. The retrieval endpoint never edits a
hypothesis response itself.

### 6.1 Perception lookup and resolved footprint (inputs to the conversion)

The conversion is a pure function (K5 `negative_evidence_from_retrieval`, task
K5 / PR #36): it reads nothing and receives two lookups from the backend, neither
of which is part of the retrieval response.

`frame_evaluations`, keyed by `frame_ref` (shape proposed by K5; OPEN FR-Q6 asks
Codex to confirm or replace it):

```json
{
  "frame:<ref>": {
    "frame_available": true,
    "rgb_hash_verified": true,
    "provenance_ok": true,
    "perception_evaluated": true,
    "measurement_count": 0,
    "detection_producer": {
      "producer": "rgb-mask-contact",
      "version": "rgb-mask-contact-v2",
      "difference_threshold": 30,
      "min_pixels": 28
    }
  }
}
```

`detection_producer` carries four fields (v1.2, recording existing behaviour since
D21): `{producer: string, version: string, difference_threshold: integer,
min_pixels: integer}`, and all four must equal the visibility entry's
`detectability.detector` in value **and** JSON type (below). The values above are the
real Office person run's detector (`rgb-mask-contact` / `rgb-mask-contact-v2` /
`30` / `28`), as in the C5 D21 index (`C5_PERSON_VISIBILITY_INDEX_D21_20261017.json`,
SHA-256 `7c464ec4…0d83c`, `detectability.detector` of every entry) and in the
backend's `frame_evaluations` (producer version of the run's perception output), on
#53 @ `4019a44`. A record
with producer and version only is `DETECTOR_PARAMETERS_MISMATCH`. The K8 synthetic
declaration (v1.2) uses its own producer name, so it is never read as the real
detector's output, and copies the two parameters for comparability:

```json
{
  "synthetic-frame:SYN_CAM_N:11.0": {
    "frame_available": true,
    "rgb_hash_verified": true,
    "provenance_ok": true,
    "perception_evaluated": true,
    "measurement_count": 0,
    "detection_producer": {
      "producer": "synthetic-k8",
      "version": "v1",
      "difference_threshold": 30,
      "min_pixels": 28
    }
  }
}
```

and its visibility entry declares `"detectability": {"detector": {"producer":
"synthetic-k8", "version": "v1", "difference_threshold": 30, "min_pixels": 28}}`.

Each of the four flags must be exactly `true`; a missing record, a malformed record
or any other flag value makes the frame `UNKNOWN`. `measurement_count` is a
non-negative integer (booleans and negative values are `UNKNOWN`); `> 0` means
`DETECTION_PRESENT`; `0` needs a `detection_producer` with a non-empty
`producer`. The record distinguishes "zero measurements" from "not processed"
(`perception_evaluated`), which is what FR-Q6 asked for.

`visibility_entries`, keyed by `visibility_ref`: the resolved index entry
`{method, visibility_rule, detectability, floor_z_m, polygons, index_sha256}` (the §2
entry reduced to what the conversion needs). It is usable only if `method` is
`SOURCE_MESH_RAYCAST` (v1.2: or `SYNTHETIC_DECLARED_FOOTPRINT` in a synthetic
conversion, and then the same method as the camera block and frame), `floor_z_m` is finite, `polygons` is a list of rings with at
least three finite points each (an empty list is valid), and `index_sha256` is
non-empty; otherwise the frame is `UNKNOWN` (`VISIBILITY_ENTRY_UNRESOLVED`). In
addition (D21):

- `visibility_rule` must be `FOOT_AND_TORSO_PROBES_VISIBLE`; otherwise the frame is
  `UNKNOWN`, `VISIBILITY_RULE_NOT_ELIGIBLE`.
- `detectability.detector` must equal the frame's `detection_producer` and its
  configured `difference_threshold` and `min_pixels`; otherwise the frame is
  `UNKNOWN`, `DETECTOR_PARAMETERS_MISMATCH`. All four fields (`producer`, `version`,
  `difference_threshold`, `min_pixels`) must be present on both sides with equal
  values **and equal JSON types** (`30` is not `30.0`, `true` is not `1`); a missing
  field fails. The converted entry's `detection_producer` keeps only
  `{producer, version}`.

**Synthetic conversion (v1.2, D23/K8).** The conversion takes a `data_origin`
argument from its **trusted caller** (the backend, from the configured scene of
[blind hypothesis §3.2](OFFICE_BLIND_HYPOTHESIS_V1.md#32-server-resolved-configuration-echoed-in-the-response)):
`REAL` (default) or `SYNTHETIC`; any other value is a caller error. Nothing in the
retrieval response, `frame_evaluations` or `visibility_entries` (for example a
`provenance.data_origin` there) can switch it to `SYNTHETIC`. With `REAL` the output
is exactly the v1.1 output. With `SYNTHETIC`, `SYNTHETIC_DECLARED_FOOTPRINT` is also
accepted when the camera block, the frame's `footprint_method` and the visibility
entry all name it, and the returned mapping gains `data_origin: "SYNTHETIC"`; the
D21 rule, the detector match and every other check above apply unchanged, to
declared values. Synthetic frame records and index entries are produced by the K8
generator; their `SYNTHETIC` label is on the fixture, the synthetic index, the
synthetic retrieval response and the conversion output, never on the entry.

A `frame_ref` that is the placeholder `UNKNOWN` (OPEN FR-Q3) cannot be keyed and is
`UNKNOWN` (`FRAME_REF_UNKNOWN`).

### 6.2 Eligibility and grouping

A frame yields negative evidence only if **all** hold: the lookup record says
`NO_DETECTION` (§6 table); the camera block and the frame both report
`SOURCE_MESH_RAYCAST` (v1.2: or, in a synthetic conversion, both report
`SYNTHETIC_DECLARED_FOOTPRINT`, §6.1); the visibility entry resolves and passes the D21 checks of §6.1;
the used blind interval is
known and the frame time lies strictly inside it (open interval; a tolerance of
1e-6 s at each end excludes the endpoints' own frames); and the frame is not the
frame of an original, substituted endpoint (`ORIGINAL_ENDPOINT_FRAME`, reported as
`DETECTION_PRESENT`, D7). The used interval is `query.hypothesis_interval` and/or an
interval the caller supplies (both: their intersection); a `TIME_RANGE` query that
names no interval yields no evidence (`INTERVAL_UNKNOWN`).

Eligible frames are grouped into **one entry per (camera, `visibility_ref`,
detection producer and version)**, frames sorted by time then `frame_ref`.
Content-derived, deterministic fields:

- `frame_refs`: `[{frame_ref, timestamp_s}, ...]` (objects, as the hypothesis
  contract §3.3 requires a time per frame).
- `negative_evidence_ref`: `"negev:"` + the first 24 hex characters of the canonical
  hash of `{query_id, camera_id, visibility_ref, detection_producer: [producer,
  version], frames: [[timestamp_s, frame_ref], ...]}`.
- `sha256`: canonical hash of the entry **without** the `sha256` field (the rule the
  hypothesis module recomputes; [hypothesis §3.3](OFFICE_BLIND_HYPOTHESIS_V1.md#33-negative-evidence-entry),
  byte-exact form OPEN IO-Q7).
- **Deduplication is by frame, not by entry ref** (D21). The caller passes
  `applied_frame_keys`, the set of `(camera_id, frame_ref, visibility_ref, producer,
  version)` already carried by the hypothesis request under any `origin`. A matching
  frame yields no evidence and its `frame_outcomes` row is `NO_DETECTION` /
  `ALREADY_APPLIED_FRAME` with `negative_evidence_eligible: false`. A draft left with
  no frames is not emitted. Skipping a draft whose ref the request already carries is
  kept as a second check. (The ref hashes the `query_id`, so a baseline entry and a
  feedback entry over the same frames have different refs; with ref-only
  deduplication the same 34 frames of the C5 freeze were applied twice.)
- **Malformed applied frame keys** (v1.2, recording existing behaviour). A key in
  `applied_frame_keys` that is not a tuple or list, does not have exactly five
  elements, or has an element that is not a string is dropped and never matches a
  frame; the conversion does not raise. Each dropped key is listed in the output
  field `invalid_applied_frame_keys` as `{key, reason: "APPLIED_FRAME_KEY_MALFORMED"}`
  (`key` is a printable representation of the input). Well-formed keys in the same
  set deduplicate as usual. Without malformed keys the field is `[]`.

The conversion returns `{negative_evidence_candidates, frame_outcomes,
skipped_already_applied, invalid_applied_frame_keys, interval_s}` (v1.2: plus
`data_origin: "SYNTHETIC"` for a synthetic conversion only, §6.1).

### 6.3 `frame_outcomes[]` (frame wall)

One row per retrieved frame:
`{camera_id, frame_ref, timestamp_s, outcome, reason, negative_evidence_eligible}`
with `outcome` in `NO_DETECTION`, `DETECTION_PRESENT`, `UNKNOWN`:

| `reason` | `outcome` | Meaning |
| --- | --- | --- |
| `ELIGIBLE` | `NO_DETECTION` | Passed §6.1 and §6.2; `negative_evidence_eligible: true`. |
| `OUTSIDE_OPEN_INTERVAL`, `INTERVAL_UNKNOWN` | `NO_DETECTION` | A true no-detection that is not eligible: the frame is outside the open interval, or the interval is unknown. `negative_evidence_eligible: false`. |
| `ALREADY_APPLIED_FRAME` | `NO_DETECTION` | The frame key is in `applied_frame_keys` (§6.2); no second use. `negative_evidence_eligible: false`. |
| `MEASUREMENTS_PRESENT` | `DETECTION_PRESENT` | `measurement_count > 0`. |
| `ORIGINAL_ENDPOINT_FRAME` | `DETECTION_PRESENT` | Frame of a substituted (original) endpoint. |
| `FRAME_EVALUATION_MISSING`, `FRAME_UNAVAILABLE`, `RGB_HASH_NOT_VERIFIED`, `PROVENANCE_MISMATCH`, `PERCEPTION_NOT_EVALUATED`, `MEASUREMENT_COUNT_UNKNOWN`, `DETECTION_PRODUCER_MISSING` | `UNKNOWN` | A §6.1 condition failed. |
| `FRAME_REF_UNKNOWN`, `FRAME_MALFORMED` | `UNKNOWN` | The frame cannot be keyed or read. |
| `FOOTPRINT_NOT_SOURCE_MESH_RAYCAST`, `VISIBILITY_ENTRY_UNRESOLVED` | `UNKNOWN` | No usable `SOURCE_MESH_RAYCAST` footprint (v1.2: or, in a synthetic conversion, no consistent `SYNTHETIC_DECLARED_FOOTPRINT` one). No new reason in v1.2: in a real conversion, a `SYNTHETIC_DECLARED_FOOTPRINT` frame whose other conditions all pass is `FOOTPRINT_NOT_SOURCE_MESH_RAYCAST`. This holds for the pure conversion layer; the order of the other failure conditions is unchanged. A backend wrapper that screens entries before the conversion may report its own earlier reason: the C5 wrapper (`frame_retrieval.py`) reports `VISIBILITY_RULE_NOT_ELIGIBLE` for any entry whose method is not `SOURCE_MESH_RAYCAST`, which is expected and not changed by v1.2. |
| `VISIBILITY_RULE_NOT_ELIGIBLE`, `DETECTOR_PARAMETERS_MISMATCH` | `UNKNOWN` | The D21 checks of §6.1 failed. |

Limits of the rule: evidence holds only at frame times (5 Hz in Office); passage
through a footprint between frames is not excluded. A detector miss (the target
present but below the 28 px component minimum, or absorbed by the median
background) would wrongly prune; the conservative "fully inside eroded footprint"
rule in the hypothesis contract reduces but does not remove this risk, and
evaluation must report false prunes against GT after freeze.

### 6.4 Blind-interval baseline and conditioning

`BLIND_INTERVAL_BASELINE` entries use the same no-detection frames whose absence of a
usable observation makes the interval blind. This is one use of each frame, not two:
the interval boundaries come from the endpoint detections, and each interior frame
enters pruning at most once (§6.2). The frames are, however, selected *because*
detection failed, so the detector-recall assumption behind hard pruning is weakest
exactly there (missing-not-at-random). Consequently:

1. baseline and feedback entries keep their `origin`, and the hypothesis response
   reports removed region cells per origin (the field is not yet specified in the
   hypothesis contract: OPEN FR-Q9);
2. a frame's no-detection is never also used to support endpoint association,
   identity or the choice of interval;
3. evaluation (§10) reports false prunes from `BLIND_INTERVAL_BASELINE` frames
   separately from `RETRIEVAL_FEEDBACK`;
4. a deployment without a declared detector recall for the footprint's distance range
   must treat baseline pruning as `INFERRED`, not as an observation.

## 7. Fail-closed reasons

| `reason` | When |
| --- | --- |
| `HYPOTHESIS_NOT_FOUND` | `response_sha256` or a `hypothesis_ref` does not resolve, or refers to PRUNED paths only. |
| `HYPOTHESIS_NOT_READY` | Referenced hypothesis response is `UNKNOWN`. |
| `TIME_RANGE_INVALID` | Empty, reversed, outside the scene clock, or wider than `MAX_QUERY_WINDOW_S`. |
| `CAMERA_NOT_IN_SCENE` / `TOO_MANY_CAMERAS` | Camera checks. |
| `VISIBILITY_INDEX_UNAVAILABLE` | No index entry for a requested camera in HYPOTHESIS mode; that camera is not silently dropped. |
| `SEARCH_BUDGET_EXHAUSTED` | Record caps or the cooperative deadline hit. |
| `PROVENANCE_MISMATCH` | Index or bundle hash differs. |

## 8. Limits (proposed, OPEN FR-Q4)

| Limit | Proposed |
| --- | --- |
| `MAX_CAMERAS` | 4 (existing `frame_baseline.py` / `blender_motion.py` cap) |
| `MAX_QUERY_WINDOW_S` | 20.0 (same as `MAX_BLIND_INTERVAL_S`) |
| `MAX_RESULT_FRAMES` | 64 |
| `MAX_FRAME_RECORDS_READ` | 512 per query |
| Scale test | Index and frame tables synthetically expanded to 10⁵–10⁶ records for latency measurement (plan §4 RQ4); expansion data labelled SYNTHETIC and kept out of the demo scene |
| Deadline | Cooperative monotonic deadline; `UNKNOWN` on expiry |

## 9. Example (illustrative numbers, not measured)

```json
{
  "schema_version": "workbench.frame-retrieval.v1",
  "status": "READY",
  "reason": null,
  "query_id": "frq:9d41e0",
  "query": {"query_kind": "HYPOTHESIS", "hypothesis": {"response_sha256": "<sha256>", "hypothesis_refs": [], "use": "REACHABLE_REGIONS"}, "time_range_s": [4.8, 8.0], "hypothesis_interval": {"start_s": 4.6, "end_s": 8.2}, "endpoint_substitutions": [], "camera_ids": ["CAM_1F_AUDITORIUM_FRONT", "CAM_1F_AUDITORIUM_REAR"], "max_frames": 64},
  "results": [
    {
      "camera_id": "CAM_1F_AUDITORIUM_REAR",
      "visibility_ref": "visidx:rear-v1",
      "method": "SOURCE_MESH_RAYCAST",
      "windows": [
        {"start_s": 6.0, "end_s": 6.4, "frames": [
          {"frame_ref": "UNKNOWN", "timestamp_s": 6.0, "reason": {"kind": "REACHABLE_REGION_IN_VIEW", "hypothesis_refs": [], "overlap_area_m2": 1.8, "in_view_count": null, "footprint_method": "SOURCE_MESH_RAYCAST", "walkable_status": "TRUE"}},
          {"frame_ref": "UNKNOWN", "timestamp_s": 6.2, "reason": {"kind": "REACHABLE_REGION_IN_VIEW", "hypothesis_refs": [], "overlap_area_m2": 2.3, "in_view_count": null, "footprint_method": "SOURCE_MESH_RAYCAST", "walkable_status": "TRUE"}},
          {"frame_ref": "UNKNOWN", "timestamp_s": 6.4, "reason": {"kind": "REACHABLE_REGION_IN_VIEW", "hypothesis_refs": [], "overlap_area_m2": 1.1, "in_view_count": null, "footprint_method": "SOURCE_MESH_RAYCAST", "walkable_status": "TRUE"}}
        ]}
      ]
    }
  ],
  "stats": {"frame_records_read": 3, "index_records_read": 2, "frames_in_scope_total": 40, "frames_matched_total": 3, "frames_suggested": 3, "frames_unavailable": 0, "latency_ms": {"index_lookup": 0.4, "frame_lookup": 0.2, "total": 1.1}},
  "truncated": false,
  "scan_mode": "INDEX",
  "negative_evidence_candidates": [
    {"negative_evidence_ref": "negev:frq9d41e0-rear", "origin": "RETRIEVAL_FEEDBACK", "camera_id": "CAM_1F_AUDITORIUM_REAR", "frame_refs": [{"frame_ref": "UNKNOWN", "timestamp_s": 6.0}, {"frame_ref": "UNKNOWN", "timestamp_s": 6.2}, {"frame_ref": "UNKNOWN", "timestamp_s": 6.4}], "visibility_ref": "visidx:rear-v1", "visible_floor": {"method": "SOURCE_MESH_RAYCAST", "floor_z_m": 0.4959475898742676, "polygons": [[[12.0, 4.0], [14.0, 4.0], [14.0, 5.5], [12.0, 5.5]]], "index_sha256": "<sha256>"}, "detection_result": "NO_DETECTION", "detection_producer": {"producer": "perception", "version": "v2"}, "retrieval_query_id": "frq:9d41e0", "sha256": "<sha256>"}
  ],
  "frame_outcomes": [
    {"camera_id": "CAM_1F_AUDITORIUM_REAR", "frame_ref": "UNKNOWN", "timestamp_s": 6.0, "outcome": "NO_DETECTION", "reason": "ELIGIBLE", "negative_evidence_eligible": true},
    {"camera_id": "CAM_1F_AUDITORIUM_REAR", "frame_ref": "UNKNOWN", "timestamp_s": 6.2, "outcome": "NO_DETECTION", "reason": "ELIGIBLE", "negative_evidence_eligible": true},
    {"camera_id": "CAM_1F_AUDITORIUM_REAR", "frame_ref": "UNKNOWN", "timestamp_s": 6.4, "outcome": "NO_DETECTION", "reason": "ELIGIBLE", "negative_evidence_eligible": true}
  ],
  "identity_verdict": "UNCONFIRMED",
  "agent_used": false,
  "provenance": {"scene_id": "blender-office", "run_ref": "UNKNOWN", "clock_id": "BLENDER_PILOT_CONFIGURED_SECONDS_5HZ", "source_sha256": "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e", "safe_inputs_sha256": "1ea62def6c843b3bae1c5e25584fa489915f08e678b28b6220dc88cc17b43163", "producer": "frame-retrieval", "producer_version": "v1", "visibility_index_sha256": "<sha256>", "run_parameters": {"declaration_source": "PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT", "declaration_ref": "setting:run-<new>-target-v1", "declaration_sha256": "<sha256>", "target_proxy": {"shape": "CYLINDER", "height_m": 1.70, "radius_m": 0.25, "label": "SYNTHETIC_CYLINDER_PERSON_SIZED"}, "head_height_prior": {"nominal_m": 1.70, "tolerance_m": 0.10}, "body_radius_m": 0.25, "foot_anchor_band_px": 2}, "gt_read": false},
  "output_sha256": "<sha256>"
}
```

Office caveat: REAR frames 0.0–8.2 s are pixel-identical (route chosen
visible → blind → visible), so on the current run a REAR footprint that covers
gap floor would yield `NO_DETECTION` there; that is consistent with the gap but
proves nothing about where the target was outside the footprint.

## 10. Evaluation boundary

RQ4 metrics (recall of truth-containing frames, fraction of frames to review,
`latency_ms`, `frame_records_read`) are computed by the evaluation tool after
freeze; recall uses GT only there. False prunes caused by §6 are reported
separately, and by origin (§6.4).

Synthetic truth (v1.2, D23/K8): as in
[blind hypothesis §10](OFFICE_BLIND_HYPOTHESIS_V1.md#10-evaluation-boundary), K8 truth
trajectories are read only by the K8 evaluation tool; synthetic `NO_DETECTION`
records are generated from them before conversion and never carry truth positions.

## 11. OPEN QUESTIONS for Codex

- **FR-Q1** *(RESOLVED by D1, 2026-10-16: the visibility index may ray-test
  against static source geometry, scene meshes at the pinned frame with
  provenance hashes. Renderer per-frame visibility, target trajectories and depth
  stay forbidden.)*
- **FR-Q2** Endpoint name and whether retrieval is a new route or an extension of
  the existing `timeline` handler (route names are `UNKNOWN` in the pipeline map).
- **FR-Q3** Existing frame-ref field name/format served by `timeline` and the
  frame wall.
- **FR-Q4** Confirm §8 limits and the scale-test method (synthetic expansion vs.
  more renders).
- **FR-Q5** Exclude `latency_ms` from `output_sha256` (draft) so recorded replays
  verify, with latency kept in a separate receipt?
- **FR-Q6** Does the perception output keep a per-frame "evaluated" status that
  distinguishes "zero measurements" from "not processed"? Needed for
  `NO_DETECTION` vs `UNKNOWN`. *(v1.1: K5 assumes the `frame_evaluations` lookup of
  §6.1, which assumes it does; confirm that C5 can serve exactly this record, or
  replace it. K5 question 2.)*
- **FR-Q7** `NO_DETECTION` requires zero measurements in the whole frame (draft,
  conservative). Should it instead require zero measurements whose projection or
  segment overlaps the footprint?

- **FR-Q8** *(v1.1, K5)* Return `frame_outcomes` (§6.3) in the retrieval response
  for the frame wall, or keep it in a separate backend call? Also confirm that the
  backend resolves each `visibility_ref` to the `visibility_entries` record of §6.1
  (K5 question 2), and that `BLIND_INTERVAL_BASELINE` entries use the same
  `sha256` rule as §6.2.
- **FR-Q9** *(v1.1, D21)* Codex to confirm and implement: the exporter stores per-probe
  codes (foot, waist, head) and per-camera `probe_visible_counts`; the index computes
  cell status under `FOOT_AND_TORSO_PROBES_VISIBLE` plus the calibration-only
  detectability check and keeps the any-probe footprint as `suggestion_polygons`;
  `frame_retrieval` matches on `suggestion_polygons` and rejects non-eligible entries
  with `VISIBILITY_RULE_NOT_ELIGIBLE` / `DETECTOR_PARAMETERS_MISMATCH`. Also: where
  the per-origin removed-cell count of §6.4 (1) is reported. The convergence under the
  new rule is `UNKNOWN` until Codex re-exports (bounded by 0 and the earlier −15.7 %
  union).

## 12. Revision 2026-10-16

Draft revision after CP1 decisions D4–D13 ([#25](https://github.com/Polalalabear/amidst/issues/25))
and the K1 contract deviations ([PR #33](https://github.com/Polalalabear/amidst/pull/33)).
Still a draft; it takes effect only when CP1 is approved.

| Change | Section | Basis |
| --- | --- | --- |
| `negative_evidence_candidates` (and baseline entries) carry the resolved `visible_floor`, matching the hypothesis contract's new negative-evidence entry; empty `polygons` is valid. | §5, §6 | K1 deviation (adopted; [hypothesis §12.2](OFFICE_BLIND_HYPOTHESIS_V1.md#122-k1-deviations-adopted-or-rejected)) |
| HYPOTHESIS queries echo the referenced interval and its `endpoint_substitutions`; the original unusable endpoint's frame is `DETECTION_PRESENT`, never negative evidence. | §5, §6 | D7 |
| Frame `reason.walkable_status` (`TRUE`/`UNKNOWN`) for frames matched through a path link or region cell in a `walkable: UNKNOWN` area. | §5.1 | D11 |
| `provenance.run_parameters` echoed; its body radius must equal the hypothesis configuration's. | §5 | D5, D6 |
| FR-Q1 marked resolved. | §11 | D1 |

Not changed: matching rules, limits, `scan_mode: INDEX`, GT isolation. D8, D9,
D10, D12 and D13 do not touch this contract.

## Revision 2026-10-17 (v1.1)

Draft revision after the K5 implementation ([PR #36](https://github.com/Polalalabear/amidst/pull/36),
`retrieval_evidence.py`, "Suggested contract revisions"), the CP2 decision D18
([#26](https://github.com/Polalalabear/amidst/issues/26)) and the CP3 decision D21
([record](https://github.com/Polalalabear/amidst/issues/26#issuecomment-6233644309)). Still a draft; it takes
effect only when Codex confirms and the PR merges.

| Change | Section | Basis |
| --- | --- | --- |
| The per-frame perception record `frame_evaluations[frame_ref]` `{frame_available, rgb_hash_verified, provenance_ok, perception_evaluated, measurement_count, detection_producer}` (each flag exactly `true`) and the resolved visibility entry `{method, floor_z_m, polygons, index_sha256}` are specified as the conversion inputs. | §6.1 | K5 (PR #36) |
| Eligibility and grouping rules: open used interval, original-endpoint frame, one entry per (camera, `visibility_ref`, producer), content-derived `negative_evidence_ref` and `sha256`, dedup against applied refs; `frame_refs` are objects with `timestamp_s`. | §6.2 | K5 |
| `frame_outcomes[]` rows with `reason` codes for the frame wall (proposed response field); `FRAME_REF_UNKNOWN` handling for the placeholder `frame_ref`. | §5, §6.3 | K5 |
| Example moves to the humanoid run's interval 4.6 s → 8.2 s (queried gap 4.8–8.0 s); `run_parameters` echoes `foot_anchor_band_px`. | §9 | D18; [interval observation v1.1](OFFICE_INTERVAL_OBSERVATION_V1.md#revision-2026-10-17-v11) |
| FR-Q6 annotated with the `frame_evaluations` proposal; new FR-Q8. | §11 | K5 |
| **D21, negative evidence needs foot and torso visible:** index entries gain `visibility_rule` (`FOOT_AND_TORSO_PROBES_VISIBLE`, `ANY_PROBE_VISIBLE`), `detectability` (calibration-only minimum projected area, `required_px = 4 × min_pixels`) and `suggestion_polygons` (any-probe footprint, ranking only); `polygons` has an entry condition; `negative_evidence_eligible` requires the strict rule; matching uses `suggestion_polygons`. | §2, §4 | D21 (#26); C5 review (Opus 5.5 / medium, head-top-only visibility) |
| Resolved visibility entry gains `visibility_rule` and `detectability`; new `UNKNOWN` reasons `VISIBILITY_RULE_NOT_ELIGIBLE`, `DETECTOR_PARAMETERS_MISMATCH`. | §6, §6.1, §6.3 | D21 |
| Deduplication by frame key via `applied_frame_keys` (`ALREADY_APPLIED_FRAME`) instead of by entry ref; ref skipping kept as a second check. | §6.2, §6.3 | D21; C5 review (34 frames applied twice) |
| New §6.4 "Blind-interval baseline and conditioning" (origin kept, no reuse for association, false prunes reported by origin, `INFERRED` without a declared recall); §10 and new FR-Q9. | §6.4, §10, §11 | D21; C5 review |

Not changed: matching rules, limits, `scan_mode: INDEX`, GT isolation, D7/D11
handling. The restricted-policy layer of D15 and the seat-obstacle revision D16
([blind hypothesis v1.1](OFFICE_BLIND_HYPOTHESIS_V1.md#revision-2026-10-17-v11)) do
not touch this contract; `reason.walkable_status` keeps its D11 meaning.

## Revision 2026-10-17 (v1.2, K8 synthetic method)

Draft revision for D23 (K8, design
[K8_SYNTHETIC_CAPABILITY_DEMO §5.2(a), §5.3](../agents/K8_SYNTHETIC_CAPABILITY_DEMO.md),
Draft PR [#56](https://github.com/Polalalabear/amidst/pull/56) @ `91d944a`), with
Codex's corrections to §5.3 applied; companion of
[blind hypothesis v1.2](OFFICE_BLIND_HYPOTHESIS_V1.md#revision-2026-10-17-v12-k8-synthetic-method).
Implementation: K8a, branch `claude/k8a-synthetic-method`. Still a draft; it takes
effect only when Codex confirms and the PR merges.

| Change | Section | Basis |
| --- | --- | --- |
| New index `method` `SYNTHETIC_DECLARED_FOOTPRINT`, only in a SYNTHETIC index (K8 fixture), never in the C5 real index; new `footprint_method` value with the same limit. | §2, §5.1 | D23 |
| `negative_evidence_eligible` may be `true` for a declared synthetic footprint with a declared strict rule; for every method it is a necessary condition only. Declared synthetic entries are distinguished from the real index's nine-sample ray and calibration-area evidence. | §2 | Codex correction 3 |
| `NO_DETECTION` decision and its four flags unchanged; for synthetic records the flags are declared values that bind the fixture hash, and no synthetic output claims RGB pixels were verified. Real meaning unchanged. | §6 | Codex correction 4 |
| Detector match: four fields, equal values and equal JSON types; synthetic example with `synthetic-k8` / `v1` / integer `30` / integer `28`. | §6.1 | Codex correction 5 |
| Trusted-caller `data_origin` argument to the conversion (default `REAL`); payload provenance cannot enable the synthetic method; `REAL` output is exactly the v1.1 output; `SYNTHETIC` output gains `data_origin`. | §6.1, §6.2 | Codex correction 2 |
| No `provenance` / `data_origin` field on a converted entry; labels stay on the fixture, index, retrieval and conversion layers. | §6, §6.1 | Codex correction 6 |
| No new `frame_outcomes` reason: a synthetic method in a real conversion is `FOOTPRINT_NOT_SOURCE_MESH_RAYCAST` (pure conversion layer), other failure priorities unchanged; the C5 wrapper's earlier `VISIBILITY_RULE_NOT_ELIGIBLE` is expected and `frame_retrieval.py` is not changed. | §6.3 | Codex correction 7 |
| Synthetic truth is read only by the K8 evaluation tool. | §10 | D1, D23 |

**Recorded existing behaviour (no code change).** These rows write down what the K5
conversion already does (K1/K5 [#48](https://github.com/Polalalabear/amidst/pull/48)
@ `74c6ace`, accepted by Codex; found missing from the contract in the #53 re-review
@ `0cb2c22`). They are separate from the K8a additions above.

| Change | Section | Basis |
| --- | --- | --- |
| Output field `invalid_applied_frame_keys`: malformed `applied_frame_keys` entries (not a tuple/list, not five elements, or a non-string element) are dropped and listed as `{key, reason: "APPLIED_FRAME_KEY_MALFORMED"}`; well-formed keys deduplicate as usual; the conversion never raises on them. The conversion's return fields are listed. | §6.2 | #48 @ `74c6ace`; #53 re-review @ `0cb2c22` |
| `frame_evaluations[*].detection_producer` carries `{producer: string, version: string, difference_threshold: integer, min_pixels: integer}`, equal in value and type to `detectability.detector`; the §6.1 example now shows the real detector `rgb-mask-contact` / `rgb-mask-contact-v2` / `30` / `28` (version corrected from `v2` after the [Codex confirmation](https://github.com/Polalalabear/amidst/pull/45#issuecomment-6235792437); source: C5 D21 index `7c464ec4…0d83c` and `frame_evaluations` on #53 @ `4019a44`). | §6.1 | #48 @ `74c6ace` (D21); #53 re-review @ `0cb2c22` |

Hash acceptance is layered as in
[blind hypothesis v1.2](OFFICE_BLIND_HYPOTHESIS_V1.md#revision-2026-10-17-v12-k8-synthetic-method):
real API results, result hashes, D19 numbers and the C5 index SHA-256
`7c464ec4…0d83c` must not change; existing frozen files stay as originals; a rebuilt
reproduction bundle records its new pins and may get a new wrapper hash.

Not changed: matching rules, limits, `scan_mode: INDEX`, GT isolation, D7/D11
handling, the D21 rule, frame-key deduplication, and every real index, response and
conversion output.
