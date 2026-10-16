# Office Demo blind-interval hypothesis contract v1

Status: DRAFT for Codex confirmation, 2026-10-16 (task K0). Additive; no existing
endpoint, response field, curve state or `blender-office` assertion changes.
Claude Code implements the pure algorithm module (task K1) against this contract;
Codex wires it into the backend (task 4, P0). Items marked **OPEN** need Codex
confirmation; names not found in [OFFICE_DEMO_TARGET_V1](OFFICE_DEMO_TARGET_V1.md)
or the [pipeline map](../engineering/OFFICE_PIPELINE_MAP.md) are `UNKNOWN`.

Method: [plan §3.2](../agents/OFFICE_DEMO_PLAN_20261101.md#3-方法觀測--假設--檢索--驗證).
Endpoint ground estimates: [interval observation v1](OFFICE_INTERVAL_OBSERVATION_V1.md).
Negative evidence from retrieval: [frame retrieval v1](OFFICE_FRAME_RETRIEVAL_V1.md).

## 1. Purpose and authority

Given the two observed endpoints of a blind interval (e.g. Office FRONT 4.4 s and
REAR 8.6 s, gap 4.6–8.4 s), produce:

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

Schema id: `office-demo.blind-hypothesis-request.v1`. Transport (new endpoint vs.
an additive field on `POST /api/target_reconstruction`) is OPEN BH-Q1. Callers may
not supply file paths, GT, calibration, speed or annotation overrides; speed range
and annotation refs are resolved server-side from scene configuration and echoed.

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | `office-demo.blind-hypothesis-request.v1` |
| `session_ref`, `scene_id` | string | As in the target contract. |
| `candidate_ref` | string\|null | Existing cross-camera candidate whose gap is queried, or `null` with explicit endpoints. |
| `start`, `end` | endpoint | See §3.1. `end.timestamp_s > start.timestamp_s`. |
| `top_k` | integer | Strict integer 1–5 (same bound as `target_reconstruction`). |
| `negative_evidence` | array | §3.3; may be empty. Order is significant and recorded. |
| `previous_response_sha256` | string\|null | Set when re-running after new negative evidence (§6). |

### 3.1 Endpoint state

| Field | Type | Meaning |
| --- | --- | --- |
| `observation_ref` | string | Existing public observation (must resolve). |
| `camera_id` | string | Source camera. |
| `timestamp_s` | number | Source clock seconds. |
| `evidence_state` | enum | Must be `PROJECTED_OBSERVATION`. |
| `ground_estimate` | object | An [interval observation v1](OFFICE_INTERVAL_OBSERVATION_V1.md) object with `status: READY`. POINT → endpoint region is a disc of radius `pixel_sensitivity_m`; SEGMENT → the segment (OPEN BH-Q4). |

An endpoint whose `ground_estimate` is `UNKNOWN` makes the whole response
`UNKNOWN` (`ENDPOINT_UNUSABLE`); the module never substitutes a nearby
observation or timestamp.

### 3.2 Server-resolved configuration (echoed in the response)

| Field | Meaning |
| --- | --- |
| `speed_range_m_s` | `{min, max, source: "CONFIGURED_NOT_GT", config_ref, config_sha256}`; `0 <= min < max <= MAX_SPEED_M_S (8.0)`. Proposed humanoid default `[0.0, 2.0]` (OPEN BH-Q5). |
| `walkable_ref` | `{annotation_ref, sha256}` walkable polygons on the floor plane. Name/existence `UNKNOWN` (OPEN BH-Q2). |
| `portal_ref` | `{annotation_ref, sha256}` doorway/portal segments joining walkable polygons. Name/existence `UNKNOWN`. |
| `visibility_index_ref` | `{index_ref, sha256, method}` camera floor-visibility index from [frame retrieval v1 §2](OFFICE_FRAME_RETRIEVAL_V1.md#2-camera-floor-visibility-index). |
| `body_radius_m` | Configured target radius used to erode visible footprints (humanoid proxy 0.25; legacy cylinder about 0.148). |
| `grid_step_m`, `time_step_s` | Lattice spacing (proposed 0.25 m) and clock step. |

### 3.3 Negative evidence entry

| Field | Type | Meaning |
| --- | --- | --- |
| `negative_evidence_ref` | string | Opaque, stable ref. |
| `origin` | enum | `BLIND_INTERVAL_BASELINE` (all frames of all cameras inside the gap) or `RETRIEVAL_FEEDBACK` (from a retrieval query). |
| `camera_id` | string | Camera whose frames showed no detection. |
| `frame_refs` | array | Frames that contributed; each has `timestamp_s`. |
| `visibility_ref` | string | Footprint entry used; method must be `SOURCE_MESH_RAYCAST`. |
| `detection_result` | enum | Must be `NO_DETECTION`. |
| `detection_producer` | object | `{producer, version}` of the perception run (e.g. perception v2). |
| `retrieval_query_id` | string\|null | Contract C query that produced it. |
| `sha256` | string | Hash of the entry. |

Entries are produced only by the rules in
[frame retrieval v1 §6](OFFICE_FRAME_RETRIEVAL_V1.md#6-from-no-detection-to-negative-evidence).
`DETECTION_PRESENT` and `UNKNOWN` frames are never negative evidence.

## 4. Computation rules

1. **Lattice.** Cells of `grid_step_m` inside the walkable polygons; adjacency
   only within a polygon or across a portal segment. No cell outside the walkable
   annotation exists.
2. **Times.** `t_i = start.timestamp_s + i * time_step_s`, excluding both
   endpoints, up to `end.timestamp_s - time_step_s`.
3. **Unseen mask.** For each `t_i` and each negative-evidence frame at `t_i`
   (within half a clock step), a cell is excluded if the disc of radius
   `body_radius_m` around it lies **fully inside** the camera's visible footprint
   (footprint eroded by the body radius). Partly visible cells are kept: the rule
   errs toward not pruning a true path. Frames that are `MISSING` contribute
   nothing.
4. **Reachable region.** Forward reachability from the start region and backward
   reachability from the end region, each with step reach `max_speed * time_step_s`
   along lattice adjacency, intersected with the unseen mask:
   `R(t_i) = Fwd(t_i) ∩ Bwd(t_i) ∩ Unseen(t_i)`.
5. **Paths.** A path picks one cell per `t_i` from `R(t_i)`, with consecutive
   cells reachable at `≤ max_speed`, and its mean speed over the whole interval
   `≥ min_speed` (OPEN BH-Q5: per-step minimum). Candidate pool bounded by
   `MAX_CANDIDATE_PATHS`; deterministic beam search; ties broken by
   `hypothesis_ref` lexical order.
6. **Plausibility.** Configured cost combining path length, turning and deviation
   from a configured nominal speed; `score = -cost`, higher is more plausible.
   Components are reported. Weights live in the config (`config_sha256`).
7. **Representatives.** Select K by score with a diversity rule: a path is
   skipped if its maximum distance to an already selected path at every `t_i` is
   below `MIN_SEPARATION_M`, or if it uses the same portal sequence (OPEN BH-Q6).
8. **Checks.** Every returned path carries `speed`, `walkable` and `unseen` checks
   recomputed on its own samples (not inherited from the lattice), so a
   consumer can audit each claim.

## 5. Response

Schema id: `workbench.blind-hypothesis.v1`.

| Field | Type | Meaning |
| --- | --- | --- |
| `status` | enum | `READY` or `UNKNOWN`. |
| `reason` | string\|null | §7 code when `UNKNOWN`. |
| `interval` | object | `{start_s, end_s, duration_s, start_observation_ref, end_observation_ref}`. |
| `configuration` | object | §3.2 echo including hashes. |
| `hypotheses` | array | ACTIVE paths, rank 1..≤K (§5.1). |
| `pruned_hypotheses` | array | Paths that were ACTIVE in `previous_response_sha256` and fail `unseen` now (§6). |
| `reachable_regions` | array | One per `t_i` (§5.2). |
| `rejected_counts` | object | Pool paths dropped, by check: `{speed, walkable, unseen, diversity}`. |
| `negative_evidence_applied` | array | `negative_evidence_ref`s in application order. |
| `pruning_log` | array | §6. |
| `limits` | object | Effective caps and whether any was hit. |
| `trace` | array | Algorithmic decisions (as in the target contract). |
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
| `rank` | integer | 1 = most plausible in this response. |
| `status` | enum | `ACTIVE` or `PRUNED`. |
| `pruned_by` | string\|null | `pruning_ref` when PRUNED. |
| `plausibility` | object | `{score, basis: "CONFIGURED_PLAUSIBILITY_NOT_PROBABILITY", components: {path_length_m, turn_rad, speed_deviation_m_s}}`. |
| `samples` | array | `{timestamp_s, position_m: [x,y,z], evidence_state: "INFERRED_HYPOTHESIS"}` for every `t_i`; no sample at the endpoints. |
| `portal_sequence` | array | Portal refs crossed, in order. |
| `checks.speed` | object | `{result, max_step_speed_m_s, mean_speed_m_s, limit_m_s: [min, max]}`. |
| `checks.walkable` | object | `{result, walkable_ref, violations: [{timestamp_s, position_m}]}`. |
| `checks.unseen` | object | `{result, conflicts: [{timestamp_s, camera_id, negative_evidence_ref}]}`. |
| `physical_authority` | string | `UNKNOWN`. |

Check `result` is `PASS`, `FAIL` or `UNKNOWN`. ACTIVE paths have `PASS` on all
three, except `unseen` may be `UNKNOWN` when a camera's footprint is not
`SOURCE_MESH_RAYCAST` for some `t_i` (it then cannot prune). A `FAIL` path is
never ACTIVE.

### 5.2 Reachable region

| Field | Type | Meaning |
| --- | --- | --- |
| `timestamp_s` | number | `t_i`. |
| `kind` | enum | `POLYGON` or `SAMPLE_SET` (OPEN BH-Q3: which one v1 emits). |
| `polygons` | array\|null | Floor polygons `[[x, y], ...]` (z = `floor_z_m`), outer rings counter-clockwise. |
| `samples` | array\|null | Cell centres `[[x, y], ...]` with `cell_size_m`. |
| `area_m2` | number | Region area. |
| `max_extent_m` | number | Largest distance between two region points (band-width metric for RQ2). |
| `evidence_state` | string | `INFERRED_HYPOTHESIS`. |
| `truncated` | boolean | True if `MAX_REGION_VERTICES` / `MAX_REGION_SAMPLES` was hit; never silent. |

## 6. Pruning by new negative evidence

Pruning is a deterministic re-run, not an in-place edit:

1. The caller sends the same request plus appended `negative_evidence` and
   `previous_response_sha256`.
2. The server verifies the previous response hash and that the earlier evidence
   list is a prefix of the new one (append-only); otherwise `UNKNOWN`,
   `NEGATIVE_EVIDENCE_NOT_APPEND_ONLY`.
3. Regions and paths are recomputed. Previously ACTIVE paths that now fail
   `unseen` are listed in `pruned_hypotheses` with `status: PRUNED`; surviving and
   newly selected paths are re-ranked in `hypotheses`.
4. One `pruning_log` entry is appended per new evidence entry:

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

If the reachable region becomes empty at any `t_i`, the response is `UNKNOWN`,
`REACHABLE_SET_EMPTY`; constraints are not relaxed and the evidence conflict is
reported in `trace`.

## 7. Fail-closed reasons

| `reason` | When |
| --- | --- |
| `ENDPOINT_UNUSABLE` | Missing/unresolvable endpoint, wrong state, or `ground_estimate` not READY. |
| `INTERVAL_INVALID` | `end <= start`, or not on the clock grid. |
| `INTERVAL_TOO_LONG` | `duration_s > MAX_BLIND_INTERVAL_S`. |
| `WALKABLE_ANNOTATION_UNAVAILABLE` | No approved walkable annotation; the floor plane is not substituted. |
| `SPEED_CONFIG_UNAVAILABLE` | No configured range, or it violates §3.2 bounds. |
| `ENDPOINT_OUTSIDE_WALKABLE` | An endpoint region has no walkable cell. |
| `ENDPOINTS_UNREACHABLE` | No path at `max_speed` even without negative evidence. |
| `REACHABLE_SET_EMPTY` | §6. |
| `NEGATIVE_EVIDENCE_INVALID` / `NEGATIVE_EVIDENCE_NOT_APPEND_ONLY` | Entry fails §3.3 or §6 checks. |
| `SEARCH_BUDGET_EXHAUSTED` | Any cap or the cooperative monotonic deadline hit before completion. |
| `PROVENANCE_MISMATCH` | Any hash differs from the loaded scene. |

`UNKNOWN` responses carry `hypotheses: []`, `reachable_regions: []` and the
`trace`; no partial paths are presented as results.

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
| `MAX_REGION_VERTICES` / `MAX_REGION_SAMPLES` | 256 per polygon / 2 000 per timestamp |
| Deadline | Cooperative monotonic deadline as in the target contract; UNKNOWN on expiry |

## 9. Example (illustrative numbers, not computed)

```json
{
  "schema_version": "workbench.blind-hypothesis.v1",
  "status": "READY",
  "reason": null,
  "interval": {"start_s": 4.4, "end_s": 8.6, "duration_s": 4.2, "start_observation_ref": "observation:add9f687d311742321e80dff", "end_observation_ref": "observation:<rear-8.6>"},
  "configuration": {
    "speed_range_m_s": {"min": 0.0, "max": 2.0, "source": "CONFIGURED_NOT_GT", "config_ref": "config:speed-humanoid-v1", "config_sha256": "<sha256>"},
    "walkable_ref": {"annotation_ref": "UNKNOWN", "sha256": "<sha256>"},
    "portal_ref": {"annotation_ref": "UNKNOWN", "sha256": "<sha256>"},
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
        {"timestamp_s": 4.6, "position_m": [13.10, 4.70, 0.4959475898742676], "evidence_state": "INFERRED_HYPOTHESIS"},
        {"timestamp_s": 4.8, "position_m": [13.38, 4.85, 0.4959475898742676], "evidence_state": "INFERRED_HYPOTHESIS"}
      ],
      "portal_sequence": [],
      "checks": {
        "speed": {"result": "PASS", "max_step_speed_m_s": 1.62, "mean_speed_m_s": 1.45, "limit_m_s": [0.0, 2.0]},
        "walkable": {"result": "PASS", "walkable_ref": "UNKNOWN", "violations": []},
        "unseen": {"result": "PASS", "conflicts": []}
      },
      "physical_authority": "UNKNOWN"
    }
  ],
  "pruned_hypotheses": [],
  "reachable_regions": [
    {"timestamp_s": 4.6, "kind": "POLYGON", "polygons": [[[12.8, 4.3], [13.6, 4.3], [13.6, 5.1], [12.8, 5.1]]], "samples": null, "area_m2": 0.64, "max_extent_m": 1.13, "evidence_state": "INFERRED_HYPOTHESIS", "truncated": false}
  ],
  "rejected_counts": {"speed": 112, "walkable": 0, "unseen": 37, "diversity": 9},
  "negative_evidence_applied": ["negev:baseline-front-4.6-8.4", "negev:baseline-rear-4.6-8.4"],
  "pruning_log": [],
  "limits": {"max_blind_interval_s": 20.0, "max_candidate_paths": 256, "hit": []},
  "trace": [{"step": "LATTICE_BUILT", "cells": 1840}, {"step": "REPRESENTATIVES_SELECTED", "k": 1}],
  "evidence_state": "INFERRED_HYPOTHESIS",
  "ranking_basis": "CONFIGURED_PLAUSIBILITY_NOT_PROBABILITY",
  "physical_authority": "UNKNOWN",
  "identity_verdict": "UNCONFIRMED",
  "agent_used": false,
  "reconstruction_rng": "NOT_USED",
  "provenance": {"scene_id": "blender-office", "run_ref": "UNKNOWN", "clock_id": "BLENDER_PILOT_CONFIGURED_SECONDS_5HZ", "source_sha256": "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e", "safe_inputs_sha256": "1ea62def6c843b3bae1c5e25584fa489915f08e678b28b6220dc88cc17b43163", "producer": "blind-hypothesis", "producer_version": "v1", "config_sha256": "<sha256>", "annotation_sha256": {"walkable": "<sha256>", "portals": "<sha256>"}, "gt_read": false},
  "output_sha256": "<sha256>"
}
```

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

- **BH-Q1** Transport: new endpoint (name to be chosen by Codex) or an additive
  `blind_hypotheses` field on `target_reconstruction`? Session/deadline handling
  as in the target contract either way?
- **BH-Q2** Do approved walkable and portal annotations exist for 1F (refs,
  hashes, format)? If not, is fail-closed `WALKABLE_ANNOTATION_UNAVAILABLE`
  acceptable for the Office demo, or should Codex author an annotation (needs
  source-asset rules check)?
- **BH-Q3** Reachable region as `POLYGON` (needs polygon ops in the backend) or
  `SAMPLE_SET` (cell centres; simpler and exact on the lattice) for v1?
- **BH-Q4** SEGMENT endpoints: treat the whole segment as the start/end region
  (draft), or require POINT endpoints in v1?
- **BH-Q5** Speed range defaults and whether `min` applies per step or to the
  interval mean (draft: mean, so stopping is allowed).
- **BH-Q6** Diversity rule for the K representatives (distance threshold, portal
  sequence, or both).
- **BH-Q7** Confirm all §8 limits, especially `MAX_BLIND_INTERVAL_S` vs. the
  existing `MAX_WINDOW_S = 10.0`.
- **BH-Q8** Which existing ref gives the "same target" pairing of endpoints: a
  cross-camera `candidate_ref` only, or also the selected-target response?
