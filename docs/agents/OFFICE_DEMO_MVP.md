# Office Demo MVP

## Objective and scope

Demonstrate one selected source observation across the two spatially separated Office cameras, including the meaningful observation interval from 4.4 s to 8.6 s in the current fixture. The exact source camera for the selected observation and availability of the local bundle are **UNKNOWN** until the source-bound manifest is inspected. Do not imply that a cross-camera candidate proves a person's identity or that a path is physically safe.

Required user flow:

Select one person-like source observation in a camera frame → inspect other-camera evidence → expose the blind interval → show the available bounded Top-K hypotheses and physical evidence state → visualize source observations and projected/inferred segments with a cylinder or human proxy → inspect synchronized XYZ and velocity curves → inspect backend decision/fallback trace → replay the recorded request/result.

The MVP prioritizes one area, one selected target, and the 4.4–8.6 s fixture gap. If a dependency or evidence link is absent, show `UNKNOWN` or `MISSING`; do not substitute a different target, camera run, trajectory answer, or synthetic UI motion.

## Feature requirements and current evidence

Status meanings: **VERIFIED** means directly confirmed for the cited bounded scope; **REPORTED** means stated in a dated source or by the user but not rechecked here; **UNKNOWN** means evidence is insufficient; **MISSING** means the requested capability/evidence is not currently available or accepted.

| Feature | Current status | Required backend data | Visible expected behavior | Acceptance criteria | Deferrable |
| --- | --- | --- | --- | --- | --- |
| Office source footage and camera selection | **REPORTED**: two-camera source RGB exists in existing demo documentation. **CONFIRMED (static audit D1–D3, D6)**: the 2D wall is a fixed temporal mosaic; per-camera current frames sit in a collapsed auxiliary panel; camera chips only toggle styling in default 3D mode; no source video and no observation-selection UI exist. **UNKNOWN**: local bundle/media availability and current browser reproduction. | Source/run-bound frame or video refs, camera IDs, exact timestamps, hashes, session/scene scope. | Selecting a camera displays its own source media; selecting a visible observation binds the selected `observation_ref` and timestamp. | Both fixture cameras load source-bound media; camera switching changes media and labels, not only border styling; selection shows matching camera/time/ref; unavailable media is explicit. | Live real-world camera stream; user/account/deployment flow. Current footage is synthetic Blender simulation imagery, not real-world surveillance footage. |
| Shared clock and camera/media binding | **CONFIRMED (D3, D4d)**: source playback advances 0.4 s per tick against 0.2 s source sampling, and four clock owners (source/association/physical/motion) compete for the displayed time. Browser reproduction **UNKNOWN**. | Source clock seconds, camera IDs, session/scene-bound media refs, source time range, frame/sample references. | Video seek, timeline, 2D frame panels, 3D target and curves show the same source time; wrong-run refs fail visibly. | Seek to a known timestamp; every visible panel and marker reports the same time and source binding; stale responses cannot replace the current scene/selection. | Multi-run comparison and arbitrary clock synchronization. |
| Selected-target cross-camera Top-K | **UNKNOWN**: new `target_reconstruction` endpoint/adapter is committed WIP but not executed or accepted. Existing `cross_camera_reconstruction` behavior is **REPORTED** in dated engineering docs. | Public selected observation, source-bound association response, candidate refs/ranks/paths, selected camera/time scope, deterministic trace. | Only candidate paths containing the selected observation appear; ranks remain canonical; unassociated baseline and fewer-than-K results remain visible. | Request/response match [`OFFICE_DEMO_TARGET_V1.md`](../contracts/OFFICE_DEMO_TARGET_V1.md); selecting another observation invalidates old results; no silent timestamp-based target switch; agent/model calls are zero in deterministic mode. | Ranking personalization, identity claims, full-scene matching. |
| Blind interval and prediction | **REPORTED**: existing backend keeps long gaps missing; **UNKNOWN**: new target endpoint/UI integration. | Observed timestamps, projected samples, gap interval/reason, inferred segment state, null positions for missing samples. | Observation markers are solid; permitted inferred segments are visibly distinct/dashed; unsupported interval remains a gap, not a filled straight path. | Fixture interval 4.4–8.6 s is visibly identified as missing/inferred only where backed by returned evidence; no positions, velocity, or animation are fabricated through `MISSING`. | Gap uncertainty visualization beyond available fields. |
| Physically constrained Top-K | **MISSING** as a positive physical-safety claim. Existing physical candidate verdicts are reported **UNKNOWN**, with no known hard exclusions in the cited Office checkpoint. | Per-candidate physical checks, support scope, source/hash and geometry authority, PASS/REJECT/UNKNOWN reasons. | Display source-supported checks and their scope. Unknown geometry remains `UNKNOWN`; do not label a candidate safe/reachable. | Candidate count/ranks are preserved; physical evidence is not confused with association score; all absent or partial authority remains explicit. | Human body clearance, complete obstacle/doorway/corridor certification, collision-free route assertion. |
| 3D target proxy and animation | **REPORTED**: markers drift. **SUSPECTED (D4)**: the humanoid is driven by a frozen historical presentation track (including positions inside the `INFERRED_GAP`), independent of the selected candidate; separate cursor/time markers use different tolerances; yaw is derived from the last rendered position. | Source-world XYZ in metres, right-handed Z-up, timestamp, state, selected target/candidate refs, camera/source binding. | Proxy follows only valid observed/projected points; inferred portions use a separate style and missing portions do not move. | At fixture observation times proxy matches returned XYZ within a declared display tolerance; changing camera or time does not change coordinate axes or jump to another target; gap state is apparent. | Photorealistic avatar, joints, inferred posture, smooth motion not supported by source samples. |
| XYZ/velocity curves and evidence | **REPORTED**: curves do not reflect expected movement. **SUSPECTED (D5)**: X/Y/Z share one y-axis scale, compressing per-axis motion; gap disconnection is already correct. Not reproduced. | Samples, states, timestamps, XYZ, finite-difference velocity, missing reasons, candidate refs, trace and artifact refs. | Curves share the video/timeline cursor; units and observed/inferred/missing states are labeled; trace identifies deterministic decisions and fallback status. | Selected candidate, displayed curve, marker, source frame and trace refer to the same scene/camera/time/rank; missing spans are not connected. | Statistical confidence, probability calibration, formal benchmark metrics. |
| Reproduction | **UNKNOWN**: no receipt exists for the new WIP endpoint. Existing runner can produce a receipt when supplied local dependencies. | Exact request/response, config and code hashes, fixture/media manifest, trace, validation receipt. | User can replay the recorded response and see that it is stored deterministic output, not a new model decision. | Same canonical response hash on replay; receipt lists scope and limitations; unavailable inputs produce an explicit blocker without modifying source assets. | Portable clone containing ignored local media/DB and live model service. |

## Dependencies and limits

- Fixture config: [`configs/office_demo_fixture_v1.json`](../../configs/office_demo_fixture_v1.json).
- Backend contract: [`OFFICE_DEMO_TARGET_V1.md`](../contracts/OFFICE_DEMO_TARGET_V1.md).
- Existing pipeline guide: [`DEMO_V1.md`](../engineering/DEMO_V1.md); association and motion documents are linked from the handoff.
- Exact local `--bundle` path and media/calibration availability at Claude's checkout are **UNKNOWN**. The config contains source/data/safe-input hashes, not local file paths. The original dataset's trajectory/GT content is forbidden to the inference path.
- No endpoint execution, focused tests, browser acceptance, or recorded receipt for the target-reconstruction WIP is claimed here. Existing historical checks retain their own dates/scopes.

## Minimum viable scope — audit 2026-10-15

Evidence: [frontend audit section](../engineering/OFFICE_MVP_AGENT_AUDIT.md#office-視覺化前端稽核--claude-code-opus2026-10-15) (defect IDs D1–D6). One area (`blender-office`), the two fixture cameras, one selected target, the 0–9.8 s source window and the 4.4–8.6 s gap.

**Essential (MVP cannot be shown without these):**

1. **Primary source view.** For each selected fixture camera, show the actual source still at the current source time as a primary, visible panel, with camera, time and media ref labeled. Playback steps through every source frame (0.2 s) as a flipbook. Uses the existing `timeline` API; no video generation. Fixes D1–D3.
2. **One shared source clock.** One timestamp drives source view, 3D, curves and candidate cursor; reconstruction videos never silently take over the clock while the user scrubs the source timeline.
3. **Observation selection.** Clickable public 2D observations on the source still, binding `observation_ref` + camera + time. Blocked on backend data (see below).
4. **Selected-target Top-K panel.** Calls `POST /api/target_reconstruction`; shows ranks, `UNCONFIRMED` identity, `UNKNOWN` physical verdict, fewer-than-K, trace. Blocked on a Codex receipt.
5. **One 3D proxy driven only by the selected candidate's samples.** Hidden or frozen in `MISSING`; inferred segments dashed; no historical presentation body moving through the gap (D4).
6. **XYZ/velocity curves** with per-axis scale and the shared cursor, gaps left disconnected (D5).
7. **Recorded replay** of the stored deterministic response, hash shown.

**Optional (keep if already working, do not invest):** 8/12/16-slot temporal wall (secondary mode), guidance graph, physical review panel, motion/cross-camera pre-materialized artifact videos (as labeled evidence only), cylinder vs humanoid proxy choice.

**Deferred:** Agent connection, physical safety/clearance claims, identity verdicts, multi-run comparison, live streams, gait/posture animation, full-scene matching.

### Missing backend and asset dependencies

- **Codex:** executed `target_reconstruction` request/response receipt and a validated response fixture for frontend tests; per-frame public 2D observations (`observation_ref` + pixel bbox/point) for Office frames (existing endpoint **UNKNOWN**); the selected observation's source camera (**UNKNOWN**); a contract decision on whether the 3D proxy may use the historical presentation track at all.
- **Assets:** Office safe-input bundle path **UNKNOWN**. `data/engineering/blender_*_2026101x/` directories exist in the Claude checkout (listing only, unverified).
- **Runtime:** browser reproduction of D1–D5 not performed in the audit session.
