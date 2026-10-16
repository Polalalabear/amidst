# Office Demo frame-retrieval contract v1

Status: DRAFT for Codex confirmation, 2026-10-16 (task K0). Additive; the
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
| `query` | object | Normalised request echo. |
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
| `negative_evidence_candidates` | array | §6 entries ready to append to a hypothesis request (either query kind). |
| `identity_verdict` | string | `UNCONFIRMED`. |
| `agent_used` | boolean | `false`. |
| `provenance`, `output_sha256` | | Shared rules; `producer: "frame-retrieval"`, plus `visibility_index_sha256`. `latency_ms` is excluded from `output_sha256` so replays hash equal (OPEN FR-Q5). |

`frame_ref` reuses the existing opaque, site/run-bound frame reference served by
`timeline` and the frame wall; its exact field name and format are `UNKNOWN`
(OPEN FR-Q3). Private paths are never returned.

### 5.1 Frame `reason`

| Field | Meaning |
| --- | --- |
| `kind` | `HYPOTHESIS_PATH_IN_VIEW`, `REACHABLE_REGION_IN_VIEW`, or `TIME_RANGE_ONLY`. |
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
`visibility_ref`, `detection_producer` (perception producer and version) and a
hash. The response lists these drafts in `negative_evidence_candidates`; the
caller (frontend or Agent replay) appends them to the hypothesis request, so each
pruning step is an explicit, logged re-run. The retrieval endpoint never edits a
hypothesis response itself.

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
  "query": {"query_kind": "HYPOTHESIS", "hypothesis": {"response_sha256": "<sha256>", "hypothesis_refs": [], "use": "REACHABLE_REGIONS"}, "time_range_s": [4.6, 8.4], "camera_ids": ["CAM_1F_AUDITORIUM_FRONT", "CAM_1F_AUDITORIUM_REAR"], "max_frames": 64},
  "results": [
    {
      "camera_id": "CAM_1F_AUDITORIUM_REAR",
      "visibility_ref": "visidx:rear-v1",
      "method": "SOURCE_MESH_RAYCAST",
      "windows": [
        {"start_s": 6.0, "end_s": 6.4, "frames": [
          {"frame_ref": "UNKNOWN", "timestamp_s": 6.0, "reason": {"kind": "REACHABLE_REGION_IN_VIEW", "hypothesis_refs": [], "overlap_area_m2": 1.8, "in_view_count": null, "footprint_method": "SOURCE_MESH_RAYCAST"}},
          {"frame_ref": "UNKNOWN", "timestamp_s": 6.2, "reason": {"kind": "REACHABLE_REGION_IN_VIEW", "hypothesis_refs": [], "overlap_area_m2": 2.3, "in_view_count": null, "footprint_method": "SOURCE_MESH_RAYCAST"}},
          {"frame_ref": "UNKNOWN", "timestamp_s": 6.4, "reason": {"kind": "REACHABLE_REGION_IN_VIEW", "hypothesis_refs": [], "overlap_area_m2": 1.1, "in_view_count": null, "footprint_method": "SOURCE_MESH_RAYCAST"}}
        ]}
      ]
    }
  ],
  "stats": {"frame_records_read": 3, "index_records_read": 2, "frames_in_scope_total": 40, "frames_matched_total": 3, "frames_suggested": 3, "frames_unavailable": 0, "latency_ms": {"index_lookup": 0.4, "frame_lookup": 0.2, "total": 1.1}},
  "truncated": false,
  "scan_mode": "INDEX",
  "negative_evidence_candidates": [
    {"negative_evidence_ref": "negev:frq9d41e0-rear", "origin": "RETRIEVAL_FEEDBACK", "camera_id": "CAM_1F_AUDITORIUM_REAR", "frame_refs": ["UNKNOWN", "UNKNOWN", "UNKNOWN"], "visibility_ref": "visidx:rear-v1", "detection_result": "NO_DETECTION", "detection_producer": {"producer": "perception", "version": "v2"}, "retrieval_query_id": "frq:9d41e0", "sha256": "<sha256>"}
  ],
  "identity_verdict": "UNCONFIRMED",
  "agent_used": false,
  "provenance": {"scene_id": "blender-office", "run_ref": "UNKNOWN", "clock_id": "BLENDER_PILOT_CONFIGURED_SECONDS_5HZ", "source_sha256": "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e", "safe_inputs_sha256": "1ea62def6c843b3bae1c5e25584fa489915f08e678b28b6220dc88cc17b43163", "producer": "frame-retrieval", "producer_version": "v1", "visibility_index_sha256": "<sha256>", "gt_read": false},
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

- **FR-Q1** May the inference-side visibility index use static source-mesh
  raycasts (`SOURCE_MESH_RAYCAST`), or only `FRUSTUM_ONLY`? If only the latter,
  negative-evidence pruning is disabled in v1.
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
  `NO_DETECTION` vs `UNKNOWN`.
- **FR-Q7** `NO_DETECTION` requires zero measurements in the whole frame (draft,
  conservative). Should it instead require zero measurements whose projection or
  segment overlaps the footprint?
