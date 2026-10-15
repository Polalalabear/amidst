# Claude Code Office Demo task sequence

Take one task per session and stop after its focused verification. All frontend code tasks use the existing shared workbench paths below. Do not broaden scope if an asset, field, or route is missing; document it as `UNKNOWN` and identify the dependency.

Defect IDs D1–D6 refer to the [frontend audit section](../engineering/OFFICE_MVP_AGENT_AUDIT.md) (2026-10-15). MVP scope: [`OFFICE_DEMO_MVP.md`](OFFICE_DEMO_MVP.md#minimum-viable-scope--audit-2026-10-15).

## Order and status

| # | Task | Owner | Depends on | Status |
| --- | --- | --- | --- | --- |
| 0 | Office visualization audit and smallest MVP | Claude Opus | — | **DONE** 2026-10-15 (static audit; no browser reproduction) |
| 1 | Primary source view and 0.2 s source flipbook (D1–D3) | Claude frontend | — | **NEXT: Session 2** |
| 2 | Per-axis curve scale (D5) | Claude frontend | — | READY (independent) |
| 3 | Backend: target receipt, response fixture, per-frame 2D observations, 3D proxy contract decision | Codex | — | BLOCKING 4–7 |
| 4 | Single shared source clock across all surfaces (D4d) | Claude frontend | 1 | READY after 1 |
| 5 | 3D proxy driven by selected candidate only (D4) | Claude frontend | 3 (contract decision), 4 | BLOCKED |
| 6 | Observation selection on source view (D6) | Claude frontend | 1, 3 | BLOCKED |
| 7 | Target Top-K panel and evidence/trace (D6) | Claude frontend | 3, 6 | BLOCKED |
| 8 | Recorded replay and interactive acceptance | Claude + Codex | 1–7 | BLOCKED |

## 0 — Office visualization audit and smallest MVP — DONE

Findings, evidence and dependencies are recorded in [`OFFICE_MVP_AGENT_AUDIT.md`](../engineering/OFFICE_MVP_AGENT_AUDIT.md) and [`OFFICE_DEMO_MVP.md`](OFFICE_DEMO_MVP.md). No application code was changed.

## 1 — Primary source view and 0.2 s source flipbook (Session 2 first task)

- **Owner:** Claude Code frontend (Sonnet).
- **Problem (CONFIRMED by code):** in the Blender/Office workspace the current per-camera source frames render only inside the collapsed `<details class="source-evidence blender-source-evidence">` (`frontend/workbench/app.mjs:348-349`); the default `visualMode:'3d'` (`app.mjs:74`) hides the temporal wall, so camera chips visibly change only their styling (`app.mjs:340-342`, `1125-1130`). Source playback `togglePlayback` advances `+.4` s per 400 ms tick (`app.mjs:1007-1010`) while Office source sampling is 0.2 s (fixture `sampling_hz: 5`; timeline `step=.2` at `app.mjs:331`), so every other source frame is skipped.
- **Paths:** `frontend/workbench/app.mjs`; `frontend/workbench/style.css` only if the new panel needs layout rules; tests `frontend/workbench/app.test.mjs`, `frontend/workbench/frame-query.test.mjs`, `frontend/workbench/workbench-layout.test.mjs`.
- **Allowed changes:**
  1. In `workspaceDisplay()` (Blender/frame-query scenes only), render the existing `data-frames="workspace"` source-frame grid as a visible primary panel directly next to (or above) the 3D/wall surface, not inside a collapsed `<details>`. Each card keeps camera label, source timestamp, frame source label, and the existing explicit empty/`MISSING` state. Keep `updateFrameGrid` node reuse so images are not re-created on every tick.
  2. Extract a small exported pure helper (e.g. `sourcePlaybackStep(snapshot)` and/or `nextPlaybackTimestamp(timestamp, range, step)`) and use it in `togglePlayback`, so Blender/frame-query scenes advance by 0.2 s and other scenes keep the current 0.4 s. Keep the epoch/stop guards and the `fetchTimeline` call unchanged.
  3. Add focused tests only for the helper and for the panel being present and not collapsed in Blender mode.
- **Not allowed:** backend, endpoint or schema edits; media/fixture/asset changes; video generation; changing the temporal wall, 3D scene, cross-camera, physical, or motion modules; adding observation overlays (task 6) or clock-owner changes (task 4).
- **Dependencies:** existing `timeline` API (`fetchTimeline`, `app.mjs:217-230`) returning frames with `media_ref`/`timestamp`. Live Office media availability is **UNKNOWN**. Without it, browser acceptance stays **UNKNOWN**, and only the unit tests are claimed.
- **Focused test:** `node --test frontend/workbench/app.test.mjs frontend/workbench/frame-query.test.mjs frontend/workbench/workbench-layout.test.mjs` and `git diff --check`.
- **Acceptance:**
  - The helper returns 0.2 for a snapshot with `capabilities.frame_query === true` and 0.4 otherwise. Stepping from 0 to 9.8 s at 0.2 s visits 50 timestamps, with the last clamped to the range end and no floating-point drift past `end`.
  - In Blender mode, the rendered workspace HTML contains the source-frame grid outside any `<details>` element. The existing `retainElements` expectations in `workbench-layout.test.mjs` are updated only as far as the selector move requires.
  - Toggling a camera changes which camera cards appear in the visible panel. With no frames, the existing explicit empty state is shown and no substitute footage appears.
  - Non-Blender scenes render unchanged.
- **Blocking uncertainty:** whether the local Office bundle and session serve frames in this checkout is **UNKNOWN**. Do not start the server or claim browser acceptance unless the user authorizes it.

## 2 — Per-axis curve scale (D5)

- **Owner:** Claude Code frontend.
- **Paths:** `frontend/workbench/cross-camera.mjs` (`chart()`, `:124-138`); `frontend/workbench/blender-motion.mjs` (`chart()`, `:80-101`) only if it shares the single-scale pattern; tests `cross-camera.test.mjs`, `blender-motion.test.mjs`.
- **Allowed changes:** render X, Y and Z as separately scaled small-multiple rows (or one per-axis-normalised panel with per-axis value labels); keep the existing `connect_from_previous` gap rule, state styling, units and cursor attributes.
- **Focused test:** `node --test frontend/workbench/cross-camera.test.mjs frontend/workbench/blender-motion.test.mjs`.
- **Acceptance:** a fixture path with constant Z and X/Y offsets of several metres shows visible per-axis variation; missing spans stay disconnected; the velocity chart is unchanged unless it has the same defect.
- **Blocking uncertainty:** the user-reported mismatch is not reproduced; if the backend samples themselves are flat, hand off to Codex.

## 3 — Backend dependencies for the selected-target flow (Codex)

- **Owner:** Codex. Claude must not implement this.
- **Needed:** (a) an executed `POST /api/target_reconstruction` request/response receipt for the fixture and a validated response JSON usable as a frontend test fixture; (b) per-frame public 2D observations for Office frames (`observation_ref`, camera, timestamp, pixel bbox or point), or confirmation of the existing endpoint that provides them (currently **UNKNOWN**); (c) the source camera of fixture `observation:add9f687d311742321e80dff`; (d) a contract decision on whether `snapshot.presentation.frames` (historical diagnostic track, `source_presentation.py:304-320`, positions inside `INFERRED_GAP`) may drive the 3D proxy in the Office Demo.

## 4 — Single shared source clock (D4d)

- **Owner:** Claude Code frontend; Codex consulted only if the API lacks source timestamps/refs.
- **Paths:** `frontend/workbench/app.mjs` (`activeReconstructionTime`, `claimSourceClock`, `claimVideoClock`, `bindVideoOwnership`, `app.mjs:834-870`), `frontend/workbench/cross-camera.mjs`, `frontend/workbench/blender-motion.mjs`, `frontend/workbench/scene.mjs`; tests `cross-camera.test.mjs`, `blender-motion.test.mjs`, `scene.test.mjs`.
- **Allowed changes:** frontend synchronization and stale-response guards; no endpoint/schema edits.
- **Expected result:** seeking one source time updates source view, 3D, curve cursors and candidate view together; reconstruction artifact videos are labeled evidence and cannot silently move the source clock; switching scenes/cameras invalidates stale results.
- **Focused test:** `node --test frontend/workbench/cross-camera.test.mjs frontend/workbench/blender-motion.test.mjs frontend/workbench/scene.test.mjs`.
- **Acceptance:** all synchronized surfaces show the same source time and run binding; zero-time values remain valid; missing/stale frames are explicit.

## 5 — 3D proxy driven by the selected candidate only (D4)

- **Owner:** Claude Code frontend; Codex owns any backend coordinate/data correction.
- **Paths:** `frontend/workbench/scene.mjs` (`updateBodies`, `setTimestamp`, `updateCrossCamera`, `scene.mjs:185-190,357-393`), `frontend/workbench/geometry.mjs`, `frontend/workbench/cross-camera.mjs`, `frontend/workbench/app.mjs`; tests `scene.test.mjs`, `geometry.test.mjs`, `cross-camera.test.mjs`.
- **Allowed changes:** display mapping, state styling, and focused frontend tests only. Do not alter calibration, source axes, fixture or physical geometry.
- **Expected result:** exactly one proxy follows the selected candidate's valid samples; hidden or frozen in `MISSING`; inferred parts visually distinct; yaw taken from returned data (or omitted) rather than from the previous rendered position; no gait swing implying measured motion.
- **Focused test:** `node --test frontend/workbench/scene.test.mjs frontend/workbench/geometry.test.mjs frontend/workbench/cross-camera.test.mjs`.
- **Acceptance:** at fixture observation times the proxy matches returned XYZ within a tolerance taken from the source/projection precision; no movement inside 4.6–8.4 s unless backed by returned inferred samples; camera switch does not move the proxy.
- **Blocking uncertainty:** depends on task 3(d).

## 6 — Observation selection on the source view (D6)

- **Owner:** Claude Code frontend.
- **Paths:** `frontend/workbench/app.mjs`, `frontend/workbench/style.css`; tests `app.test.mjs`, `frame-query.test.mjs`.
- **Allowed changes:** overlay returned public 2D observations on the primary source view and bind the clicked `observation_ref`, camera and time into state. No browser-side detection, no fallback to the nearest timestamp.
- **Focused test:** `node --test frontend/workbench/app.test.mjs frontend/workbench/frame-query.test.mjs`.
- **Acceptance:** the selected ref/camera/time are displayed; switching camera/time clears the selection; frames without observations show `UNKNOWN`, not a guessed box.
- **Blocking uncertainty:** depends on task 3(b).

## 7 — Target Top-K panel and evidence/trace (D6)

- **Owner:** Claude Code frontend; Codex owns API behavior.
- **Paths:** `frontend/workbench/app.mjs`, `frontend/workbench/cross-camera.mjs`, `frontend/workbench/presentation-data.mjs`, `frontend/workbench/index.html`; tests `cross-camera.test.mjs`, `app.test.mjs`.
- **Allowed changes:** consume `POST /api/target_reconstruction` per [`OFFICE_DEMO_TARGET_V1.md`](../contracts/OFFICE_DEMO_TARGET_V1.md) and render candidates/evidence/trace; do not add browser fallback inference or present score as probability.
- **Focused test:** `node --test frontend/workbench/cross-camera.test.mjs frontend/workbench/app.test.mjs` against the Codex response fixture from task 3(a).
- **Acceptance:** canonical rank/ref preserved; fewer-than-K and `UNKNOWN` not padded or hidden; identity `UNCONFIRMED`; deterministic mode visible; selecting another observation invalidates the result.
- **Blocking uncertainty:** depends on tasks 3(a) and 6.

## 8 — Recorded replay and interactive Office Demo acceptance

- **Owner:** Claude frontend for UI; Codex for API/replay; joint evidence review.
- **Paths:** only files changed by tasks 1–7, plus `docs/agents/OFFICE_DEMO_MVP.md` for the acceptance receipt.
- **Allowed changes:** scoped repairs and a concise acceptance record after dependencies are validated. No source asset or GT edits.
- **Focused test:** relevant tests from completed tasks and Codex's scripted HTTP/replay checks; browser walk-through only on available local data.
- **Acceptance:** source/time/camera/rank agree across all views; the 4.4–8.6 s gap and uncertainty are clear; replay hash is stable; no asset/GT boundary crossed. Report unavailable requirements rather than substituting another dataset.
