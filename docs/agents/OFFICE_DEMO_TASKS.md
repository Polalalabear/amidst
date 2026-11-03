> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# Claude Code Office Demo task sequence

Take one task per session and stop after its focused verification. All frontend code tasks use the existing shared workbench paths below. Do not broaden scope if an asset, field, or route is missing; document it as `UNKNOWN` and identify the dependency.

Defect IDs D1–D6 refer to the [frontend audit section](../engineering/OFFICE_MVP_AGENT_AUDIT.md) (2026-10-15). MVP scope: [`OFFICE_DEMO_MVP.md`](OFFICE_DEMO_MVP.md#minimum-viable-scope--audit-2026-10-15).

## 2026-10-16 update — plan to 2026-11-01

Ownership and priorities changed on 2026-10-16; the [2026-11-01 plan](OFFICE_DEMO_PLAN_20261101.md) is now the source of truth for scope, task split and schedule. Claude Code is no longer frontend-only. The 2026-10-15 table below is kept as a record; several items were addressed in PRs #4 and #6–#8, but per-item status was not rechecked here (**UNKNOWN**).

| ID | Task | Owner | Depends on | Status |
| --- | --- | --- | --- | --- |
| C1–C2 | Bottom-visible control run and perception v2 | Codex | — | **DONE locally** (`bb3d282`, not pushed on 2026-10-16) |
| C3 | Scene presets (a) control / (b) Office + `contact_quality` flags + launcher readiness | Codex | C1–C2 pushed | **DONE** — [PR #12](https://github.com/Polalalabear/amidst/pull/12) merged 2026-10-16 (`8266567`); acceptance in `docs/engineering/OFFICE_PRESETS_20261016.md` |
| C3b | Per-scene isolation in `load_presets`: only the default scene may fail the catalog; a failing non-default preset is listed as unavailable with a reason; a quality-mapping failure degrades that scene's flags to `NOT_EVALUATED` instead of failing the scene; data-integrity errors (hash mismatch) stay fatal | Codex | C3 | **ASSIGNED**, due before 10/29 freeze (review finding on PR #12) — [#13](https://github.com/Polalalabear/amidst/issues/13) |
| K0 | Data contracts: interval observation, blind hypothesis, frame retrieval | Claude drafts, Codex confirms | — | NEXT (target 10/17) — [#14](https://github.com/Polalalabear/amidst/issues/14) |
| C4a | Hybrid contact estimator (foot point or head-ray interval) | Codex | K0 | PENDING — [#15](https://github.com/Polalalabear/amidst/issues/15) |
| K1 | Blind-interval hypothesis module (pure functions + tests) | Claude | K0 | PENDING — [#16](https://github.com/Polalalabear/amidst/issues/16) |
| C4b | Hypothesis API integration (`target_reconstruction`, review evidence) | Codex | K1 | PENDING — [#17](https://github.com/Polalalabear/amidst/issues/17) |
| K2 | Evaluation tooling RQ1–RQ4 and result charts | Claude | C1–C2 data | PENDING — [PR #11](https://github.com/Polalalabear/amidst/pull/11) open |
| K3 | Frontend: scene presets, quality flags, interval observations | Claude | C3 | PENDING — [#20](https://github.com/Polalalabear/amidst/issues/20) |
| K4 | Frontend: hypothesis bundle and bands (P0) | Claude | C4b | PENDING — [#21](https://github.com/Polalalabear/amidst/issues/21) |
| C5 | Camera floor-visibility index and retrieval API, scale-up latency (P1) | Codex | K0 | PENDING — [#18](https://github.com/Polalalabear/amidst/issues/18) |
| K5 | Suggested-frames wall and negative-evidence pruning (P1) | Claude | C5, K1 | PENDING — [#22](https://github.com/Polalalabear/amidst/issues/22) |
| C6 | Multi-camera feasibility check (no render), benchmark routes and rendering (authorization required) | Codex | user authorization | PENDING — [#19](https://github.com/Polalalabear/amidst/issues/19) |
| K6 | Demo mode (numbered step bookmarks), browser acceptance, backup recording | Claude | K3–K5 | PENDING — [#23](https://github.com/Polalalabear/amidst/issues/23) |
| C7 | Map authority: walkable area, portals and obstacles derived from source geometry; demo areas only; annotations not used as inputs | Codex | CP1 decision D3 | PENDING — [#29](https://github.com/Polalalabear/amidst/issues/29) |
| K7 | Verify derived map: IoU vs annotations, portal matching, offline route containment, overlays | Claude | C7 | PENDING — [#30](https://github.com/Polalalabear/amidst/issues/30) |
| R1 | Merge integration into `main`, tag `office-demo-v1-20261101`, fill README results, make AGENTS.md project-general | Claude (user authorizes main merge) | 10/29 freeze + acceptance | PENDING — [#24](https://github.com/Polalalabear/amidst/issues/24) |

Live status is tracked in GitHub issues under the [Office demo 2026-11-01 milestone](https://github.com/Polalalabear/amidst/milestone/1) (labels `owner:codex` / `owner:claude`); this table links each issue and is not updated per status change. Integration point 10/24; feature freeze 10/29. Cut order if late: virtual cameras → Agent replay → scale-up retrieval → benchmark metrics → P1. Must keep: hybrid estimator, multi-camera or multi-route data, P0 hypotheses.

## Order and status (2026-10-15 record)

| # | Task | Owner | Depends on | Status |
| --- | --- | --- | --- | --- |
| 0 | Office visualization audit and smallest MVP | Claude Opus | — | **DONE** 2026-10-15 (static audit; no browser reproduction) |
| 1 | Primary source view and 0.2 s source flipbook (D1–D3) | Claude frontend | — | **IMPLEMENTED** in `3181cff` and `d2e3877` (single-camera tabbed viewer). Focused tests were not re-run in the 2026-10-15 planning session. UX-1 replaces the layout. |
| UX-1 | Primary viewport: 2D/3D toggle and synchronized multi-camera 2D tiles | Claude Sonnet | 1 | **NEXT** |
| UX-1M | **Mandatory** manual browser acceptance of UX-1 | User + Claude | UX-1 | REQUIRED GATE before UX-2 |
| UX-2 | Selection state preserved across mode switches and target chip | Claude Sonnet | UX-1, UX-1M | READY after UX-1M passes |
| UX-3 | Collapsible analysis drawer | Claude Sonnet | UX-1M (after UX-2: same file region) | READY after UX-1M passes |
| 4 | Single shared source clock across all surfaces (D4d), verified on both viewport modes | Claude frontend | UX-1M | READY after UX-1M passes |
| 2 | Per-axis curve scale (D5) | Claude frontend | — | READY (independent; renders inside the UX-3 drawer once it exists) |
| 3 | Backend: target receipt, response fixture, per-frame 2D observations, 3D proxy contract decision | Codex | — | BLOCKING 5–7 |
| 5 | 3D proxy driven by selected candidate only (D4) | Claude frontend | 3 (contract decision), 4 | BLOCKED |
| 6 | Observation selection on the 2D camera tiles (D6) | Claude frontend | UX-1, 3 | BLOCKED |
| 7 | Target Top-K drawer section and evidence/trace (D6) | Claude frontend | 3, 6, UX-3 | BLOCKED |
| 8 | Recorded replay and interactive acceptance | Claude + Codex | 1–7, UX-1–UX-3 | BLOCKED |
| UX-4 | Single-tile focus (one camera enlarged inside 2D) and keyboard mode shortcuts | Claude Sonnet | UX-1 | DEFERRABLE |

**Priority (2026-10-15 redesign):** UX-1 → UX-1M (manual browser gate) → UX-2 → UX-3 → 4. Task 2 can run at any point. After Codex task 3: 6 → 7 → 5 → 8. UX-4 runs only if time remains. The UX tasks all edit `workspaceDisplay` in `app.mjs`, so run them one per session, in sequence. The layout and interaction rules are in [`OFFICE_DEMO_MVP.md`](OFFICE_DEMO_MVP.md#primary-viewport-redesign--plan-2026-10-15).

## 0 — Office visualization audit and smallest MVP — DONE

Findings, evidence and dependencies are recorded in [`OFFICE_MVP_AGENT_AUDIT.md`](../engineering/OFFICE_MVP_AGENT_AUDIT.md) and [`OFFICE_DEMO_MVP.md`](OFFICE_DEMO_MVP.md). No application code was changed.

## 1 — Primary source view and 0.2 s source flipbook — IMPLEMENTED

*Status 2026-10-15:* implemented in `3181cff` (visible panel, `sourcePlaybackStep`/`nextPlaybackTimestamp`) and `d2e3877` (single-camera tabbed viewer `cameraViewerHTML`, marker legend). The original task text below is kept as a record. UX-1 replaces the single-camera viewer with multi-camera tiles.

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

## UX-1 — Primary viewport: 2D/3D toggle and synchronized multi-camera 2D tiles (next Sonnet task)

- **Owner:** Claude Code frontend (Sonnet). One session.
- **Problem (code reading, `3e6745a`):** `workspaceDisplay()` (`app.mjs:379-381`) stacks a `3d`/`wall` toggle section, a separate single-camera viewer (`cameraViewerHTML`, `viewerCameraId`, `data-viewer-camera`), the timeline and the camera chips. The two fixture cameras are never visible side by side at the shared time, and the diagnostic `wall` takes a primary-mode slot.
- **Paths:** `frontend/workbench/app.mjs`, `frontend/workbench/style.css`; tests `frontend/workbench/app.test.mjs`, `frontend/workbench/workbench-layout.test.mjs`.
- **Allowed changes:**
  1. `state.visualMode` takes `'2d' | '3d'`. Office/frame-query scenes (`isBlenderQuery()`) default to `'2d'`. The toolbar toggle buttons are `data-visual-mode="2d"`「2D 鏡頭」and `data-visual-mode="3d"`「3D 空間」. Both surfaces (`data-visual-surface="2d"|"3d"`) sit inside one `.primary-viewport` box of fixed height (`clamp(360px,62vh,760px)`). The existing `viewport()` goes in the 3D surface, filling the box.
  2. `setVisualMode` keeps its current behavior: it only toggles `hidden` and `aria-pressed`, and calls `state.view?.resize()` on entering 3D. No render, fetch or dispose.
  3. Export a pure `cameraTileLayout({count,width,height,aspect,gap,chromeHeight,minTileWidth=320})` that returns `{columns,rows,tileWidth,tileHeight}`. The inputs are measured, not assumed:
     - `width`/`height`: the 2D surface's actual content box (`clientWidth`/`clientHeight` minus padding).
     - `gap`: the same value the CSS uses between tiles, from one shared constant or custom property.
     - `chromeHeight`: the height of each tile's label/meta rows.
     - `aspect`: the camera image's aspect ratio. Take it from the decoded image (`naturalWidth/naturalHeight`) or from returned frame dimensions if the API provides them (currently **UNKNOWN**). Fall back to a declared 16:9 default only when neither is known, and mark the fallback in the DOM (`data-aspect-source="DEFAULT"`).
     For each balanced arrangement (`rows=ceil(count/c)`, `columns=ceil(count/rows)`), the helper computes the free cell `((width-gap·(columns-1))/columns) × ((height-gap·(rows-1))/rows - chromeHeight)` and fits the largest aspect-preserving tile in it. It picks the arrangement with the fewest rows whose fitted `tileWidth ≥ minTileWidth`, with ties going to the larger tile. If none qualifies, it picks the largest tile, with ties going to fewer rows. For `count=0` or a non-positive size it returns zeros. No window-width breakpoint or media query may decide columns.
  4. Export a pure `cameraTilesHTML({cameraIds,frames,timestamp,cameraLabel,urlFor,sourceLabel})` that renders one `[data-camera-tile="<id>"]` per id in `cameraIds` order. Each tile shows camera label, playback time, frame source time, media ref and `data-frame-availability="AVAILABLE|MISSING"`. A camera with no frame shows `MISSING · 此時間沒有回傳來源影格` and never another camera's image. Use it as the 2D surface content, replacing the single-camera viewer, and remove `viewerCameraId`/`data-viewer-camera` and their tests.
  5. In `updateTimelineDOM`, update the tiles in place. Change an `<img>` `src` only when its ref changes, and don't re-create the tile nodes. This follows the `updateFrameGrid` reuse pattern.
  6. Apply the layout through `data-columns` and CSS custom properties (`--tile-columns`, `--tile-width`, `--tile-gap`) on the 2D surface. Recompute it on a `ResizeObserver` on that surface (guarded by `typeof ResizeObserver!=='undefined'`), on camera chip toggles, on the first image decode that changes the known aspect ratio, and on entering 2D mode, since the surface measures zero while hidden. Disconnect it on scene change.
  7. Move the temporal wall unchanged (fetch, 8/12/16 sizes, retained nodes) into a collapsed `<details class="diagnostic-wall">`「診斷：分時畫面牆」below the timeline. The wall-size buttons go with it and no longer depend on `visualMode`.
- **Not allowed:** clock-owner or reconstruction-video changes (task 4); the target chip (UX-2); the drawer and moving the other panels (UX-3); observation overlays (task 6); `scene.mjs`; camera-selection caps; backend, endpoint, schema, fixture or media changes; starting a server.
- **Focused test:** `node --test frontend/workbench/app.test.mjs frontend/workbench/workbench-layout.test.mjs frontend/workbench/frame-query.test.mjs`, then `git diff --check`.
- **Acceptance:**
  - `cameraTileLayout` depends on actual container width, gap, available height (after captions) and camera aspect ratio, not on a fixed viewport breakpoint. Results below are columns×rows with `aspect:16/9, gap:8, chromeHeight:0` unless stated:
    - `{count:2,width:1400,height:600}` gives 2×1.
    - `{count:2,width:600,height:600}` gives 1×2.
    - `{count:2,width:645,height:600}` gives 1×2. The gap leaves 318.5 px per tile, so a plain 640 px breakpoint would be wrong here.
    - `{count:2,width:660,height:600}` gives 2×1.
    - `{count:2,width:1400,height:150}` gives 2×1 with `tileHeight` 150, never more.
    - `{count:2,width:900,height:260,chromeHeight:40}` gives 2×1 with `tileHeight` 220.
    - `{count:2,width:700,height:600,aspect:9/16}` gives 2×1 with `tileWidth` 337.5.
    - `{count:4,width:1000,height:700}` gives 2×2.
    - `{count:3,width:1400,height:600}` gives 3×1.
    - `{count:1,width:800,height:400}` gives 1×1.
    - `{count:0}` gives zeros.
    In every case `columns·tileWidth + gap·(columns-1) ≤ width`, `rows·(tileHeight+chromeHeight) + gap·(rows-1) ≤ height`, and `tileWidth/tileHeight` equals `aspect`.
  - The CSS gap and the helper's `gap` come from one source. A test asserts that the rendered surface's `--tile-gap` equals the value passed to the helper.
  - `cameraTilesHTML` with the two fixture camera ids and frames for both renders two tiles in order with their own refs. With a frame for only one camera, the other tile is `MISSING` and contains no `<img>`.
  - The rendered Office workspace has exactly one `.primary-viewport`, one timeline, the toggle with `2d` pressed by default, and no `data-viewer-camera`. The wall lives inside a non-`open` `<details>`.
  - Fake-DOM toggle test (adapted from `workbench-layout.test.mjs:150`): 2d→3d→2d leaves `view.renderer/pose/canvas`, tile `<img>` nodes, a playing movie (`paused`, `currentTime`), `timestamp`, `cameraIds`, `crossCameraRank`, `physicalChoice`, `reconstructionMode` and `wallSlotCount` unchanged. It makes zero fetches, and `resize` is called once per entry into 3D.
  - Non-Office scenes render as before (existing tests pass unchanged).
- **Blocking uncertainty:** whether the Office media serve in this checkout is **UNKNOWN**, so browser acceptance is not claimed unless the user authorizes a launch. The Office snapshot camera count beyond the two fixture cameras is **UNKNOWN**.
- **Done means:** focused tests pass and UX-1 is handed to UX-1M. UX-1 is not accepted until UX-1M passes.

## UX-1M — Mandatory manual browser acceptance of UX-1 (gate)

- **Owner:** the user runs or authorizes the launch, and Claude may drive the in-app browser only after that authorization. No code changes in this checkpoint. A failure goes back to UX-1 as a scoped repair.
- **Launch:** only through the existing safe launcher ([`OFFICE_DEMO_LAUNCHER.md`](../operations/OFFICE_DEMO_LAUNCHER.md)) on local Office data. If media or the bundle are unavailable, the result is **BLOCKED**, not passed, and UX-2/UX-3/4 do not start.
- **Checklist (every item observed in a real browser):**
  1. Office opens in 2D, with both fixture cameras visible at once, each labeled, at the same source time.
  2. Play and scrub: both tiles change frame together in 0.2 s steps. Playback time and each tile's frame source time agree, and a missing frame shows `MISSING` in that tile only.
  3. Layout at a minimum of four surface sizes:
     - wide desktop;
     - just above and just below the measured side-by-side threshold;
     - narrow (≤ 600 px);
     - one short-height window.
     Tiles go side by side when they fit and stack otherwise. They keep the source aspect ratio (no stretching or cropping beyond `object-fit:contain`), never overflow the viewport, and the page never scrolls horizontally.
  4. 2D → 3D → 2D: the 3D camera pose, time, candidate/choice and camera selection are unchanged. Playing evidence videos keep playing. No visible reload or image flicker.
  5. 3D fills the viewport and resizes with the window.
  6. The diagnostic wall opens from its collapsed panel and still loads its 8/12/16 slots.
- **Record:** append a dated acceptance entry to [`OFFICE_DEMO_MVP.md`](OFFICE_DEMO_MVP.md). It lists the commit SHA, browser and version, the surface sizes tested, PASS/FAIL/BLOCKED per checklist item, and screenshot paths or "not captured". It must not claim items that were not observed.

## UX-2 — Selection state preserved across mode switches and target chip

- **Owner:** Claude Code frontend (Sonnet). Depends on UX-1.
- **Paths:** `frontend/workbench/app.mjs`, `frontend/workbench/style.css`; tests `app.test.mjs`, `workbench-layout.test.mjs`.
- **Allowed changes:** a pure `targetSelectionSummary(state)` view model that reads the existing fields (`sceneId`, `timestamp`, `reconstructionMode`, `crossCameraRank`, `physicalChoice`, the cross-camera/physical result presence, and the future observation ref as `null` → `UNKNOWN`). A toolbar target chip, updated in place on candidate/choice/scene changes, worded `候選 k · 身分 UNCONFIRMED · 物理 UNKNOWN` or 「尚未選取目標」. In 2D, a per-tile badge 「所選觀測鏡頭」 appears only when returned data names that camera; otherwise there is no badge. No inference from timestamps.
- **Not allowed:** new selection sources, Top-K requests, changes to rank order, identity or physical wording beyond the contract.
- **Focused test:** `node --test frontend/workbench/app.test.mjs frontend/workbench/workbench-layout.test.mjs`, then `git diff --check`.
- **Acceptance:** the summary is unchanged by any number of mode switches; a scene change resets it; with no result it reports no selection; the chip text is identical in 2D and 3D; selecting another rank updates the chip without a workspace re-render.

## UX-3 — Collapsible analysis drawer

- **Owner:** Claude Code frontend (Sonnet). Depends on UX-1. Run it after UX-2, since both edit the same `workspaceDisplay` region.
- **Paths:** `frontend/workbench/app.mjs`, `frontend/workbench/style.css`; tests `workbench-layout.test.mjs`, `app.test.mjs`.
- **Allowed changes:** move the existing auxiliary panels (frame query, physical, cross-camera, motion, diagnostic wall, scene objects, inspector) into an `<aside class="analysis-drawer">` of `<details>` sections, plus one drawer collapse toggle. Section and drawer open states are kept in `state` and survive renders. The layout is two columns at ≥1000 px and stacked below the timeline under 1000 px. On drawer collapse or expand, call `view.resize()` and recompute the tile layout. Panel contents and their modules are unchanged.
- **Not allowed:** changing panel modules (`cross-camera.mjs`, `blender-motion.mjs`, `physical-review*.mjs`), their requests, or video clock behavior.
- **Focused test:** `node --test frontend/workbench/workbench-layout.test.mjs frontend/workbench/app.test.mjs frontend/workbench/cross-camera.test.mjs frontend/workbench/blender-motion.test.mjs`, then `git diff --check`.
- **Acceptance:** every existing panel is found once inside the drawer; collapsing a section or the drawer neither re-creates nor pauses retained `<video>`/`<img>` nodes (`retainElements` selectors updated only as far as the move requires); open states survive a routine render; the viewport surfaces stay outside the drawer.

## UX-4 — Single-tile focus and keyboard shortcuts (deferrable)

- **Owner:** Claude Code frontend (Sonnet). Depends on UX-1. Do it only if time remains after task 8's dependencies.
- **Scope:** double-click or a button on a 2D tile shows that camera alone in the viewport (1×1 through `cameraTileLayout`), and Esc returns. The `2`/`3` keys switch modes when focus is not in a form field. Focus never changes `cameraIds` or selection state.
- **Focused test:** `node --test frontend/workbench/app.test.mjs frontend/workbench/workbench-layout.test.mjs`, then `git diff --check`.

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
- **Allowed changes:** overlay returned public 2D observations on each UX-1 camera tile (scaled to that tile's displayed image) and bind the clicked `observation_ref`, camera and time into state. No browser-side detection, no fallback to the nearest timestamp.
- **Focused test:** `node --test frontend/workbench/app.test.mjs frontend/workbench/frame-query.test.mjs`.
- **Acceptance:** the selected ref/camera/time are displayed; switching camera/time clears the selection; frames without observations show `UNKNOWN`, not a guessed box.
- **Blocking uncertainty:** depends on task 3(b).

## 7 — Target Top-K panel and evidence/trace (D6)

- **Owner:** Claude Code frontend; Codex owns API behavior.
- **Paths:** `frontend/workbench/app.mjs`, `frontend/workbench/cross-camera.mjs`, `frontend/workbench/presentation-data.mjs`, `frontend/workbench/index.html`; tests `cross-camera.test.mjs`, `app.test.mjs`.
- **Allowed changes:** consume `POST /api/target_reconstruction` per [`OFFICE_DEMO_TARGET_V1.md`](../contracts/OFFICE_DEMO_TARGET_V1.md) and render candidates/evidence/trace in the UX-3 drawer section 「目標與候選 Top-K」, feeding the UX-2 target chip; do not add browser fallback inference or present score as probability.
- **Focused test:** `node --test frontend/workbench/cross-camera.test.mjs frontend/workbench/app.test.mjs` against the Codex response fixture from task 3(a).
- **Acceptance:** canonical rank/ref preserved; fewer-than-K and `UNKNOWN` not padded or hidden; identity `UNCONFIRMED`; deterministic mode visible; selecting another observation invalidates the result.
- **Blocking uncertainty:** depends on tasks 3(a) and 6.

## 8 — Recorded replay and interactive Office Demo acceptance

- **Owner:** Claude frontend for UI; Codex for API/replay; joint evidence review.
- **Paths:** only files changed by tasks 1–7, plus `docs/agents/OFFICE_DEMO_MVP.md` for the acceptance receipt.
- **Allowed changes:** scoped repairs and a concise acceptance record after dependencies are validated. No source asset or GT edits.
- **Focused test:** relevant tests from completed tasks and Codex's scripted HTTP/replay checks; browser walk-through only on available local data.
- **Acceptance:** source/time/camera/rank agree across all views; the 4.4–8.6 s gap and uncertainty are clear; replay hash is stable; no asset/GT boundary crossed. Report unavailable requirements rather than substituting another dataset.
