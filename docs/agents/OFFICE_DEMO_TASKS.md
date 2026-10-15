# Claude Code Office Demo task sequence

Take one task per session and stop after its focused verification. All frontend code tasks use the existing shared workbench paths below. Do not broaden scope if an asset, field, or route is missing; document it as `UNKNOWN` and identify the dependency.

## P0 — Office visualization audit and smallest MVP

- **Owner:** Claude Code Opus.
- **Paths:** read `docs/operations/CLAUDE_INITIAL_HANDOFF.md`, this task list, `docs/agents/OFFICE_DEMO_MVP.md`, `docs/contracts/OFFICE_DEMO_TARGET_V1.md`; inspect only `frontend/workbench/app.mjs`, `cross-camera.mjs`, `blender-motion.mjs`, `scene.mjs`, `index.html`, and `style.css` as needed. Deliver report to `docs/agents/OFFICE_DEMO_AUDIT.md` only if the user requests a saved artifact; otherwise return the findings in the session.
- **Allowed changes:** documentation-only audit note if requested; no app implementation during the initial audit.
- **Dependencies:** current checkout and source code. Media/bundle is optional for static classification; if unavailable, mark visual reproduction blocked/UNKNOWN.
- **Expected result:** classify each reported defect as frontend, backend-contract/data, asset/dependency, or not reproduced; define the smallest one-area/one-target multi-camera MVP and one first repair task.
- **Focused test:** none for a read-only audit. If a defect cannot be classified statically, propose the smallest relevant existing test from the task below; do not run a broad suite.
- **Acceptance:** cite exact files/lines and evidence state; no unsupported root-cause claim; first implementation task has one owner, bounded files, acceptance criteria, and blocker list.
- **Blocking uncertainty:** actual local bundle/video availability, selected observation camera, and browser reproduction state are UNKNOWN.

## P0 — Restore source media playback and observation selection

- **Owner:** Claude Code frontend.
- **Paths:** `frontend/workbench/app.mjs`, `frontend/workbench/index.html`, `frontend/workbench/blender-motion.mjs`; tests `frontend/workbench/app.test.mjs`, `frontend/workbench/frame-query.test.mjs`, `frontend/workbench/blender-motion.test.mjs`.
- **Allowed changes:** scoped UI state/render/event handling and media/observation binding in those files; add a focused test only for the changed behavior. Do not edit backend source, media assets, or fixture contents.
- **Dependencies:** valid source-bound Office frame/video refs and session; bundle path is UNKNOWN and must be confirmed before claiming browser acceptance.
- **Expected result:** each selected camera shows its own source media; choosing a visible source observation selects that observation/time and exposes its public reference to the reconstruction flow.
- **Focused test:** `node --test frontend/workbench/frame-query.test.mjs frontend/workbench/blender-motion.test.mjs frontend/workbench/app.test.mjs`.
- **Acceptance:** no camera switch that only changes a border; displayed media camera/time/ref match the selected source; no fabricated playback when media is missing.
- **Blocking uncertainty:** stored materials are not in the fixture; missing media remains a dependency blocker, not permission to substitute unrelated footage.

## P0 — Bind camera media and one shared source clock

- **Owner:** Claude Code frontend; Codex consulted only if the API contract lacks required source timestamps/refs.
- **Paths:** `frontend/workbench/app.mjs`, `frontend/workbench/cross-camera.mjs`, `frontend/workbench/blender-motion.mjs`, `frontend/workbench/scene.mjs`; tests `cross-camera.test.mjs`, `blender-motion.test.mjs`, `scene.test.mjs` in `frontend/workbench/`.
- **Allowed changes:** frontend synchronization and stale-response guards in those files; no endpoint/schema edits in this task.
- **Dependencies:** source clock timestamps, session/scene refs, camera IDs, media refs, and a valid target response.
- **Expected result:** seeking one source time updates selected camera frame, video, 3D marker, curve cursor, and candidate view together; switching scenes/cameras invalidates stale results.
- **Focused test:** `node --test frontend/workbench/cross-camera.test.mjs frontend/workbench/blender-motion.test.mjs frontend/workbench/scene.test.mjs`.
- **Acceptance:** all synchronized surfaces carry the same source time and run binding; zero-time values remain valid; missing/stale frames are explicit.
- **Blocking uncertainty:** if the available endpoint media uses a different clock or lacks per-frame refs, stop and hand the exact contract gap to Codex.

## P1 — Correct 3D target coordinates and proxy motion

- **Owner:** Claude Code frontend; Codex owns any backend coordinate/data correction.
- **Paths:** `frontend/workbench/scene.mjs`, `frontend/workbench/geometry.mjs`, `frontend/workbench/cross-camera.mjs`, `frontend/workbench/app.mjs`; tests `scene.test.mjs`, `geometry.test.mjs`, `cross-camera.test.mjs`.
- **Allowed changes:** display mapping, state styling, and focused frontend tests only. Do not alter camera calibration, source axes, fixture, or physical geometry.
- **Dependencies:** source-world XYZ in metres, right-handed Z-up; candidate/sample state and timestamps from a validated response.
- **Expected result:** one proxy follows selected evidence points; inferred parts are visually distinct; missing intervals hold no invented coordinate or motion.
- **Focused test:** `node --test frontend/workbench/scene.test.mjs frontend/workbench/geometry.test.mjs frontend/workbench/cross-camera.test.mjs`.
- **Acceptance:** selected marker follows source coordinates without camera-switch drift; coordinate convention is visible/consistent; unsupported interpolation is absent.
- **Blocking uncertainty:** current marker drift is user-reported and not reproduced; numerical display tolerance must be defined from the source and projection precision, not guessed.

## P1 — Render observed, predicted, and missing trajectory curves

- **Owner:** Claude Code frontend; Codex owns reconstruction/state semantics.
- **Paths:** `frontend/workbench/blender-motion.mjs`, `frontend/workbench/cross-camera.mjs`, `frontend/workbench/app.mjs`, `frontend/workbench/style.css`; tests `blender-motion.test.mjs`, `cross-camera.test.mjs`.
- **Allowed changes:** chart rendering, labels, and synchronization in these files; do not modify reconstruction algorithm or claim physical feasibility.
- **Dependencies:** ordered samples, XYZ, velocity, timestamps, state enum, gap reasons, selected candidate refs.
- **Expected result:** synchronized XYZ/velocity curves distinguish observed/projected/inferred samples and leave missing gaps disconnected.
- **Focused test:** `node --test frontend/workbench/blender-motion.test.mjs frontend/workbench/cross-camera.test.mjs`.
- **Acceptance:** curve cursor follows source video time; values/units and state labels match response; no straight-line bridge through long gaps; physical status `UNKNOWN` remains visible.
- **Blocking uncertainty:** user-reported curve mismatch has no current reproduction receipt.

## P1 — Connect target Top-K selection and evidence inspection

- **Owner:** Claude Code frontend; Codex backend owner for API behavior.
- **Paths:** `frontend/workbench/app.mjs`, `frontend/workbench/cross-camera.mjs`, `frontend/workbench/presentation-data.mjs`, `frontend/workbench/index.html`; tests `cross-camera.test.mjs`, `app.test.mjs`.
- **Allowed changes:** consume the existing target endpoint and render candidate/evidence states; do not add fallback inference in browser or reinterpret score as probability.
- **Dependencies:** endpoint `POST /api/target_reconstruction`, selected `observation_ref`, canonical candidate refs/ranks, status/trace schema; endpoint execution/acceptance is currently UNKNOWN.
- **Expected result:** user selects the source observation, sees only continuations containing it, compares available Top-K hypotheses and unassociated/unknown outcomes, and can inspect evidence/fallback trace.
- **Focused test:** `node --test frontend/workbench/cross-camera.test.mjs frontend/workbench/app.test.mjs` plus a scripted request fixture only after Codex provides a validated response receipt.
- **Acceptance:** candidate rank/ref and evidence are traceable; fewer-than-K and UNKNOWN are not padded or hidden; no identity verdict beyond `UNCONFIRMED`; deterministic mode is visibly reported.
- **Blocking uncertainty:** target API is WIP and unverified; do not integrate against assumed response fields.

## P1 — Interactive Office Demo acceptance

- **Owner:** Claude frontend for UI; Codex backend owner for API/replay; jointly review evidence.
- **Paths:** only the files changed by completed tasks above, plus `docs/agents/OFFICE_DEMO_MVP.md` for acceptance evidence. Do not widen paths without a new task.
- **Allowed changes:** scoped repairs and a concise acceptance receipt/documentation after dependencies are validated. No source asset or GT edits.
- **Dependencies:** usable Office bundle/media, validated backend response and replay receipt, stable source clock, and the prior P0/P1 fixes.
- **Expected result:** run the single target from selected observation through the 4.4–8.6 s gap, candidates, 3D, curves, traces, and recorded replay.
- **Focused test:** relevant tests from each completed task and scripted HTTP/replay checks from Codex's receipt; browser walk-through only on the available local data.
- **Acceptance:** source/time/camera/rank agree across all views; long gap and uncertainty remain clear; replay hash is stable; no asset/GT boundary is crossed. Report unavailable requirements rather than substituting another dataset.
- **Blocking uncertainty:** no new Office target-run receipt exists; ignored assets may be unavailable at Claude's checkout.
