# Claude Code initial handoff — Office Demo

**Purpose:** scoped frontend audit and handoff. This is a WIP status report, not a feature acceptance record. No application implementation is requested in Claude's first session.

## Git baseline

- Codex checkout: `/Users/polalabear/.codex/worktrees/mvp-backend-integration/amidst`, branch `codex/mvp-backend-integration`; parent baseline `c6661dd53507805deb4613f30afb31798987bfd5`.
- Claude checkout: `/Users/polalabear/Developer/amidst-claude`, branch `claude/office-demo-visualization`, current baseline `c6661dd53507805deb4613f30afb31798987bfd5` (read-only status check on 2026-10-15; clean at that check).
- The backend WIP and this handoff are committed together on the Codex branch. **Resulting WIP commit:** `COMMIT_SHA_PENDING` (replace with the resulting commit SHA before finalizing this commit).
- From Claude's checkout, obtain the WIP without changing branches:

  ```sh
  git -C /Users/polalabear/Developer/amidst-claude fetch /Users/polalabear/.codex/worktrees/mvp-backend-integration/amidst codex/mvp-backend-integration
  git -C /Users/polalabear/Developer/amidst-claude cherry-pick <WIP_COMMIT_SHA>
  ```

  Review Claude's working tree before cherry-picking. This fetch reads the Codex local branch; it does not push or merge a remote branch.

## Existing backend progress

- **VERIFIED (code inspection only):** the working-tree WIP adds `POST /api/target_reconstruction` as an additive workbench action, a selected-observation adapter over the existing bounded cross-camera candidates, a fixed Office fixture config, a runner/replay script, a contract, and focused tests. The adapter preserves candidate refs/ranks, refuses to silently choose another observation, labels identity `UNCONFIRMED`, and keeps long gaps `MISSING`.
- **REPORTED (pre-existing documentation):** the existing Office pipeline uses source-bound Blender RGB and calibration, deterministic local tracks/projections, and bounded cross-camera Top-K. The Office physical verdicts remain `UNKNOWN`; no physical clearance is established. See [Demo v1](../engineering/DEMO_V1.md) and [cross-camera reconstruction](../engineering/BLENDER_CROSS_CAMERA_RECONSTRUCTION.md).
- **UNKNOWN / not verified in this handoff:** the new endpoint, runner, focused tests, runtime startup/hard timeout, recorded replay, and interactive UI have not been run or accepted. No Office run receipt exists yet. Contract/runtime parity beyond the inspected request model and dispatch branch is unverified. This WIP is not a completed or fully verified feature.
- **Known blockers:** the safe-input bundle, original `.blend`, RGB, and evidence materialization are local/ignored dependencies and are not present in the fixture config. The runner needs an explicit `--bundle`; its runtime manifest supplies source and dataset paths. Availability at Claude's checkout is **UNKNOWN**. The optional Office Agent is not connected. Physical navigation/collision remains **UNKNOWN**.

## Demo data and assets

- Fixture: [`configs/office_demo_fixture_v1.json`](../../configs/office_demo_fixture_v1.json), scene `blender-office`, two cameras `CAM_1F_AUDITORIUM_FRONT` and `CAM_1F_AUDITORIUM_REAR`, source interval 0–9.8 s at 5 Hz, selected observation at 4.4 s, next observation at 8.6 s, requested K=3. Its source, dataset, and safe-input SHA-256 bindings are recorded there.
- **REPORTED:** existing demo docs describe 100 source RGB frames and source camera calibration for the two-camera Office scope; the runner reads camera calibration from the safe-input bundle and validates frame hashes. See [camera frame retrieval](../engineering/BLENDER_CAMERA_FRAME_RETRIEVAL.md) and [Demo v1 dependencies](../engineering/DEMO_V1.md).
- **UNKNOWN:** physical file paths and availability of the Office safe-input bundle and original media/calibration in the Claude checkout. The fixture contains hashes, not local paths. The original dataset includes trajectory/GT material, but this inference path must not read it; no trajectory answer is an allowed input. Candidate curves are reconstructed from permitted RGB-derived observations/projections and association evidence.
- Do not open or copy large binary assets for this handoff. No original Blender, video, dataset, or Ground Truth files were changed in this commit; only source/document/config/test text files are included.

## Backend / frontend contract

The canonical selected-target contract is [`OFFICE_DEMO_TARGET_V1.md`](../contracts/OFFICE_DEMO_TARGET_V1.md); this section is a navigation summary, not a duplicate API spec.

- `POST /api/target_reconstruction`: requires server-issued `session_ref`, `scene_id`, `camera_ids`, `start`, `end`, strict integer `top_k` (1–5), and an existing public `observation_ref` selected from the source frame. No caller path, GT, identity label, calibration override, or speed override.
- Response schema `workbench.target-reconstruction.v1` carries the selected observation, existing association response, selected-target candidates preserving canonical refs/ranks, evidence-graph `reachable_cameras` proposals, constraints and deterministic trace. `agent_used=false`; identity is `UNCONFIRMED`.
- Coordinates are right-handed world XYZ, Z-up, metres; source-clock timestamps are seconds. RGB observation, projected observation, inferred/interpolated cross-camera evidence, `MISSING`, and `UNKNOWN` must stay distinct. Long gaps have null positions. Physical navigation/collision is `UNKNOWN`.
- Existing API context: [`BLENDER_CROSS_CAMERA_RECONSTRUCTION.md`](../engineering/BLENDER_CROSS_CAMERA_RECONSTRUCTION.md) documents `POST /api/cross_camera_reconstruction` and issued-reference media; [`BLENDER_MOTION_RECONSTRUCTION.md`](../engineering/BLENDER_MOTION_RECONSTRUCTION.md) covers camera-local curves and gaps. Existing Top-K candidates are association hypotheses, not person identity probabilities.

## Ownership

Claude Code owns frontend video playback, camera selection/person interaction, 2D/3D synchronization, 3D target display, trajectory/physical-curve presentation, and workbench usability. Codex retains backend reconstruction, camera geometry/data contracts, deterministic fallback, agent orchestration, and backend verification/integration.

## User-reported demo issues

These are **REPORTED**, not root-cause findings: 3D markers drift unpredictably; eight 2D panels remain static; camera switching primarily changes borders; physical curves do not reflect expected movement; animation does not reproduce actual simulation footage. Do not infer causes before the audit.

## Claude's first task

Audit the existing Office visualization pipeline; classify defects as frontend, backend contract/data, asset/dependency, or not yet reproduced; define the smallest working multi-camera MVP; and identify one first frontend repair task with evidence and acceptance criteria. Do not implement application changes during this first audit session. Start with this handoff, [`docs/README.md`](../README.md), [Demo v1](../engineering/DEMO_V1.md), [the selected-target API contract](../contracts/OFFICE_DEMO_TARGET_V1.md), and the fixture above.
