# Office demo visual acceptance repair

Base: Task C `9917305c02bb9dbf006fb72a90e697b15aa0de5c` (stacked on Task B `3cc3f68`). Frontend presentation only. No backend, DTO, schema, calibration, coordinate, ranking or Ground Truth change.

## Reproduced defects (local runtime `http://127.0.0.1:54442/`, served files byte-identical to the checkout)

| Anchor | Before | Owning render path |
| --- | --- | --- |
| 0.4→0.6 s, 1.8→2.0 s | One `#76d9cf` sphere jumped 1.70 m / 2.01 m. The jump came from candidate 1 path 1 → path 2 → path 3, which are separate unassociated fragments drawn in the same colour. A one-tick ring was the only cue. | `SceneView.setCrossCamera` / `updateCrossCamera` cursor, coloured per candidate rank (`crossCameraScenePlan`) |
| all | The co-located `0x66dfd0` physical-review marker is a different source (synchronized evidence) with nearly the same colour. | `SceneView.reviewEvidenceMarker` |
| 4.4 s | Two FRONT observations 4.4 m apart, unlabeled. In RGB they are adjacent pixel components (y 23–119 and 119–147) of one faint occluded target. | Same cursor path |
| any | The 2D tiles showed no detection, so it was unclear which pixels produced a 3D point. | `syncGeometryOverlays` only drew portal annotations |
| video clock 8.5 s | The panel path clock (`crossCameraCursor`) used nearest-sample without Task B's segment rules, so it reported the 8.6 s REAR observation at 8.5 s while the 3D cursor was hidden. | `updateCrossCameraCursor` |
| inspector | `uncertainty` (0.25/0.6) appeared under "路徑資料與不確定性". It is a pixel heuristic, not metres. `projection_incidence`/`projection_quality` is ray–floor incidence geometry, not accuracy. | `crossCameraCandidateHTML` details |

## Contact-point evidence

`src/amidst/engineering/perception.py`: `contact = ((xmin + xmax - 1) / 2, ymax - 1)` of a background-difference component. `MERGED_OR_PARTIAL` means only `width > 32 or height < 20`. RGB crops at 0.4/0.6 s show the orange target's lower body hidden behind a seat back. Its visible bottom rises about 11 px (136→125) while the status is `DETECTED`, and this 11 px shift moves the floor intersection 1.70 m at about 0.17 incidence. True ground contact is therefore unsupported for every sample: `ground_contact = UNKNOWN`. The frontend reports `contact_basis = VISIBLE_COMPONENT_BBOX_BOTTOM_CENTER` only when a sample's own bbox reproduces its contact pixel.

## Repair

- `cross-camera.mjs`: `crossCameraCursor` is the single cursor rule (Task B: usable samples only, a segment start never early, a run end never held). It is now used by the 3D cursor, the panel clock and the 2D box. Adds `groundContactBasis`, `groundContactLabel`, `cameraShortLabel`, `path.associated`, and `candidateEvidenceOverlays` / `candidateEvidenceSVG`, which take original bbox/contact pixels bound by exact `frame_ref`. The panel marks unassociated fragments. Details use `pixel_measurement_uncertainty` / `ray_floor_incidence` with an explicit non-accuracy note, plus `contact_basis` and `ground_contact`.
- `scene.mjs`: the private cursor copy is removed. Each candidate cursor carries per-camera captions (`候選N·路徑M · FRONT|REAR · 未關聯? · 接地UNKNOWN`), and simultaneous captions stack.
- `app.mjs` / `style.css`: `syncCandidateEvidenceOverlays` draws the cursor sample's bbox and contact cross on its own tile. It draws only when `frame_ref` matches and the image size equals the calibration size. The observed legend states the contact semantics.

## Verification

- `node --test frontend/workbench/*.test.mjs`: 271 passed. New tests use real Office candidate-1 rows (`cross-camera-office.fixture.mjs`).
- Backend regression, unchanged code: the six Task C pytest modules, 105 passed. `git diff --check` is clean.
- Browser at 0.4/0.6/1.8/2.0/2.2/4.4/5.0/8.4/8.6 s: the 3D cursor, its caption, the 2D box and the panel clock agree. 5.0/8.4 s show nothing. 8.6 s shows a REAR restart ring. The source slider snaps to 0.2 s, and no video artifact is materialized, so 8.5 s is covered by unit tests only. Candidate 1→2→3→baseline labels stay consistent. No console messages.

Not established: true foot position, cross-camera identity, physical navigation, the full 8-minute demo (Classroom101, E1, save/reopen, report export).
