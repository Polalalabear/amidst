# Office Demo frame-retrieval contract v1

Status: **v1.1 DRAFT** for Codex confirmation, 2026-10-17 (task K0 revision of the
CP1-approved v1, merged at `dcb89f4`; the file name stays `_V1`, see
[Revision 2026-10-17 (v1.1)](#revision-2026-10-17-v11)). Additive; the
existing `timeline`, `query` and frame-wall interfaces and their bounded indexes
are unchanged. Codex owns the floor-visibility index and query API (task 4, P1);
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
| `method` | enum | `SOURCE_MESH_RAYCAST` (calibration + floor plane + static source mesh occlusion) or `FRUSTUM_ONLY` (calibration + floor plane, no occlusion). |
| `floor_z_m` | number | Floor plane height (Office 1F `0.4959475898742676`). |
| `polygons` | array | Visible floor polygons `[[x, y], ...]`, METRES, source axes. |
| `cell_size_m` | number | Raster resolution used before polygonisation. |
| `area_m2` | number | Total visible floor area. |
| `negative_evidence_eligible` | boolean | `true` only for `SOURCE_MESH_RAYCAST`. |
| `sha256` | string | Entry hash. |
| `provenance` | object | Shared block; `producer: "floor-visibility-index"`. |

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
  configuration) overlapping the footprint.
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
| `footprint_method` | `SOURCE_MESH_RAYCAST` or `FRUSTUM_ONLY`. |

## 6. From no detection to negative evidence

After retrieval, each suggested frame is checked against the **existing
precomputed perception results** for that frame (no new detector, no Agent):

| Frame outcome | Condition | Use |
| --- | --- | --- |
| `NO_DETECTION` | RGB record valid and hash-verified; the perception run evaluated the frame; zero measurements in the whole frame; footprint `method` is `SOURCE_MESH_RAYCAST`. | Eligible negative evidence. |
| `DETECTION_PRESENT` | At least one measurement in the frame (any component, since identity is unconfirmed). | Never negative evidence. May be offered as a candidate `observation_ref` for human review; not an identity or position claim. |
| `UNKNOWN` | Frame unavailable, not evaluated by perception, `FRUSTUM_ONLY` footprint, or provenance mismatch. | Never negative evidence; never treated as "absent". |

Eligible frames of one camera are grouped into a
[blind hypothesis §3.3](OFFICE_BLIND_HYPOTHESIS_V1.md#33-negative-evidence-entry)
entry with `origin: RETRIEVAL_FEEDBACK`, `retrieval_query_id`, `frame_refs`,
`visibility_ref`, the **resolved `visible_floor`** (`{method, floor_z_m, polygons,
index_sha256}`, copied from the index entry, so the pure hypothesis module can
prune without any lookup), `detection_producer` (perception producer and version)
and a hash. The same rule applies to `BLIND_INTERVAL_BASELINE` entries built by
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
    "detection_producer": {"producer": "perception", "version": "v2"}
  }
}
```

Each of the four flags must be exactly `true`; a missing record, a malformed record
or any other flag value makes the frame `UNKNOWN`. `measurement_count` is a
non-negative integer (booleans and negative values are `UNKNOWN`); `> 0` means
`DETECTION_PRESENT`; `0` needs a `detection_producer` with a non-empty
`producer`. The record distinguishes "zero measurements" from "not processed"
(`perception_evaluated`), which is what FR-Q6 asked for.

`visibility_entries`, keyed by `visibility_ref`: the resolved index entry
`{method, floor_z_m, polygons, index_sha256}` (the §2 entry reduced to what the
hypothesis module needs). It is usable only if `method` is `SOURCE_MESH_RAYCAST`,
`floor_z_m` is finite, `polygons` is a list of rings with at least three finite
points each (an empty list is valid), and `index_sha256` is non-empty; otherwise the
frame is `UNKNOWN` (`VISIBILITY_ENTRY_UNRESOLVED`).

A `frame_ref` that is the placeholder `UNKNOWN` (OPEN FR-Q3) cannot be keyed and is
`UNKNOWN` (`FRAME_REF_UNKNOWN`).

### 6.2 Eligibility and grouping

A frame yields negative evidence only if **all** hold: the lookup record says
`NO_DETECTION` (§6 table); the camera block and the frame both report
`SOURCE_MESH_RAYCAST`; the visibility entry resolves; the used blind interval is
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
- Drafts whose ref the hypothesis request already carries are dropped and listed as
  skipped, so repeated retrieval does not append duplicates.

### 6.3 `frame_outcomes[]` (frame wall)

One row per retrieved frame:
`{camera_id, frame_ref, timestamp_s, outcome, reason, negative_evidence_eligible}`
with `outcome` in `NO_DETECTION`, `DETECTION_PRESENT`, `UNKNOWN`:

| `reason` | `outcome` | Meaning |
| --- | --- | --- |
| `ELIGIBLE` | `NO_DETECTION` | Passed §6.1 and §6.2; `negative_evidence_eligible: true`. |
| `OUTSIDE_OPEN_INTERVAL`, `INTERVAL_UNKNOWN` | `NO_DETECTION` | A true no-detection that is not eligible: the frame is outside the open interval, or the interval is unknown. `negative_evidence_eligible: false`. |
| `MEASUREMENTS_PRESENT` | `DETECTION_PRESENT` | `measurement_count > 0`. |
| `ORIGINAL_ENDPOINT_FRAME` | `DETECTION_PRESENT` | Frame of a substituted (original) endpoint. |
| `FRAME_EVALUATION_MISSING`, `FRAME_UNAVAILABLE`, `RGB_HASH_NOT_VERIFIED`, `PROVENANCE_MISMATCH`, `PERCEPTION_NOT_EVALUATED`, `MEASUREMENT_COUNT_UNKNOWN`, `DETECTION_PRODUCER_MISSING` | `UNKNOWN` | A §6.1 condition failed. |
| `FRAME_REF_UNKNOWN`, `FRAME_MALFORMED` | `UNKNOWN` | The frame cannot be keyed or read. |
| `FOOTPRINT_NOT_SOURCE_MESH_RAYCAST`, `VISIBILITY_ENTRY_UNRESOLVED` | `UNKNOWN` | No usable `SOURCE_MESH_RAYCAST` footprint. |

Limits of the rule: evidence holds only at frame times (5 Hz in Office); passage
through a footprint between frames is not excluded. A detector miss (the target
present but below the 28 px component minimum, or absorbed by the median
background) would wrongly prune; the conservative "fully inside eroded footprint"
rule in the hypothesis contract reduces but does not remove this risk, and
evaluation must report false prunes against GT after freeze.

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
separately.

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
`retrieval_evidence.py`, "Suggested contract revisions") and the CP2 decision D18
([#26](https://github.com/Polalalabear/amidst/issues/26)). Still a draft; it takes
effect only when Codex confirms and the PR merges.

| Change | Section | Basis |
| --- | --- | --- |
| The per-frame perception record `frame_evaluations[frame_ref]` `{frame_available, rgb_hash_verified, provenance_ok, perception_evaluated, measurement_count, detection_producer}` (each flag exactly `true`) and the resolved visibility entry `{method, floor_z_m, polygons, index_sha256}` are specified as the conversion inputs. | §6.1 | K5 (PR #36) |
| Eligibility and grouping rules: open used interval, original-endpoint frame, one entry per (camera, `visibility_ref`, producer), content-derived `negative_evidence_ref` and `sha256`, dedup against applied refs; `frame_refs` are objects with `timestamp_s`. | §6.2 | K5 |
| `frame_outcomes[]` rows with `reason` codes for the frame wall (proposed response field); `FRAME_REF_UNKNOWN` handling for the placeholder `frame_ref`. | §5, §6.3 | K5 |
| Example moves to the humanoid run's interval 4.6 s → 8.2 s (queried gap 4.8–8.0 s); `run_parameters` echoes `foot_anchor_band_px`. | §9 | D18; [interval observation v1.1](OFFICE_INTERVAL_OBSERVATION_V1.md#revision-2026-10-17-v11) |
| FR-Q6 annotated with the `frame_evaluations` proposal; new FR-Q8. | §11 | K5 |

Not changed: matching rules, limits, `scan_mode: INDEX`, GT isolation, D7/D11
handling. The restricted-policy layer of D15 and the seat-obstacle revision D16
([blind hypothesis v1.1](OFFICE_BLIND_HYPOTHESIS_V1.md#revision-2026-10-17-v11)) do
not touch this contract; `reason.walkable_status` keeps its D11 meaning.
