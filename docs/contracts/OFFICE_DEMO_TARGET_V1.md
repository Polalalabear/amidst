# Office Demo selected-target contract v1

Status: versioned implementation contract, 2026-10-15. Additive to existing
`workbench.blender-association.v1`; existing interfaces are unchanged.

`POST /api/target_reconstruction` uses a research session and a server-owned
Blender scene. Request: `session_ref`, `scene_id`, `camera_ids`, `start`, `end`,
`top_k` (strict integer 1–5), and `observation_ref` (an existing public 2D
observation selected in the source frame). No caller path, GT, identity label,
calibration override, or speed override is accepted.

Response schema: `workbench.target-reconstruction.v1`. Required fields:
`status` READY or UNKNOWN; `reason`; `selection`; `selected_observation`;
`association` (existing source-bound response); `target_candidates` (each retains
original candidate_ref/rank and only the path containing the selected observation);
`reachable_cameras` (evidence graph proposals, never navigational certification);
`constraints`; `trace`; `agent_used=false`; `identity_verdict=UNCONFIRMED`.
Unknown observation returns UNKNOWN without choosing a different target. An
observation lacking a usable projection/node or cross-camera continuation returns
UNKNOWN. Do not silently select by timestamp alone. The selected source observation
is the last valid observation supplied to fallback; later evidence may propose a
cross-camera continuation, but no global person identity is asserted.

Reuse `BaselineAssociationIndex`; do not create a second reconstruction algorithm.
Graph/search limits and source refs must remain present. Querying a narrow time
window only slices displayed curves; graph ranking uses the selected cameras' full
source time. Long gaps remain MISSING with null positions. RGB observation,
PROJECTED_OBSERVATION, INTERPOLATED/INFERRED_CROSS_CAMERA, MISSING, and UNKNOWN are
distinct. No smoothing, extrapolation, or whole-scene physical authority is added.
All XYZ values use source world axes, metres, right handed Z-up; timestamps use
source clock seconds. Cross-camera identity remains UNCONFIRMED.

Deterministic mode makes zero model/tool calls. Trace entries identify algorithmic
selection/graph filtering/candidate or UNKNOWN decisions. Search is precomputed
with existing bounded graph/beam caps; request processing must enforce bounded
candidate/path scans and a cooperative monotonic deadline, returning UNKNOWN when
exhausted. Startup and hard process timeout are separately verified by the demo
runner. Recorded replay is hash-verified stored output from that runner, not a new
Agent inference. Physical navigation/collision remains UNKNOWN until independently
approved geometry is available.

Real requests/responses, fixture hashes, executable commands, and acceptance status
will be linked from `docs/engineering/OFFICE_MVP_BACKEND_HANDOFF.md` after execution.
