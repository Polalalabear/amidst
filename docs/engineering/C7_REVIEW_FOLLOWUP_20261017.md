# C7 review follow-up — 2026-10-17

Refs #29/#40; camera foot-hidden mask tracking [#49](https://github.com/Polalalabear/amidst/issues/49). Documentation only, no integration merge or geometry recomputation.

`git merge-tree --write-tree origin/claude/office-demo-visualization origin/codex/c7-source-map` at integration dcb89f4 / C7 a69e63f reported exactly one conflict: docs/history/WORK_LOG.md. Integration's C3b log and C7's appended result records both occupied the same EOF insertion. Both are retained: the two C7 records are now at the start of the Chinese history section; the integration record stays verbatim at its original location. No source/producer/geometry/evaluation history content was rewritten. The later verification below is a virtual merge, not a branch merge.

## Camera foot-hidden masks: owner and interface

Low-priority tracking is #49; no implementation started. Codex/C7 owns source-derived camera-specific foot-hidden KEEP masks and geometry evidence; Codex/C4a owns validation/resolver/clip wiring. Claude drafts/confirms public contract details with Codex and independently verifies. This records responsibilities, not an outbound agent delegation.

Existing C4a interface (PR #46 @a6ce40c) is `hybrid_contact.SourceClip`: ref/ref_sha256/source_sha256, geometry, unknown_geometry, floor_z_m, body_radius_m, tier=SOURCE_DERIVED, camera_id, **meaning=FOOT_HIDDEN_FROM_THIS_CAMERA**. Hash covers geometry and camera-specific meaning. Run/clock/calibration/source-frame/producer/config bindings must accompany any serialized artifact; that serialized contract is still pending, not invented as an approved schema here.

A plain obstacle footprint is not this mask. C5 union-visibility complement or one centre ray is not a valid substitute. Only CONTACT_OCCLUDED uses OCCLUDER_BEHIND; LOW_INCIDENCE-only foot band keeps NOT_APPLICABLE. Mismatched camera/source/hash/floor/body radius fails closed. Missing mask remains NOT_AVAILABLE, not a silently applied cut. Preserve UNKNOWN/partial support. GT, target trajectories, renderer visibility/depth cannot enter derivation. C5 foot/torso/head rule and K1 #48 sync/restricted_regions wiring remain separately deferred; C6 stays paused under D14.

## 實際產出 / Actual output

- Model / effort: **gpt-6.1-sol / high**, verified current turn_context.
- PR / commits: existing Draft #40, branch codex/c7-source-map; original tip a69e63fec7275f020a4953fab797a8c3288a72e9. Exact follow-up SHA posted to #29/#40/#49 after publication; no merge.
- Files changed: docs/history/WORK_LOG.md; this report; docs/engineering/C7_DEMO_SOURCE_MAP_20261017.md (link to follow-up).
- Commands run and results: initial git merge-tree reports1 WORK_LOG content conflict. Constructed resolution retaining both sets of records; `git merge-file -p <integration-log> <base-log> <resolved-log>` exit0 with no markers. Final git merge-tree and diff checks recorded below. Code tests not run: documentation-only, geometry/code unchanged.
- Artifacts: NONE new geometry/masks. Existing map/source hashes and physical authority are unchanged; no Blender/media/GT read, copy, write or render.
- Verified: both existing C7 records and current integration log retained; exact conflict location; current interface meaning checked against #46 SourceClip validation; no duplicate foot-mask issue, new tracking #49.
- Not verified: future integration freshness, mask geometry/serialization/false clipping, C4a mask wiring, GT/RQ2, browser/full demo, new K1 rules. Recheck mergeability against fresh integration before eventual authorized merge.
- Deviations, UNKNOWN items and follow-ups: only file contents were reconciled; no merge/rebase/squash. Mask implementation and serialization remain pending under #49. CP2 remains unapproved; #40 stays Draft.

Final virtual merge at `afe1b1f` against integration `dcb89f475f14897e1b272da61d44a25acf8f1fb8`: **exit0, no conflicts**, virtual result tree `5881a85948f92d251a6f296c27b88b79fc726a92`. Only the three documentation paths above differ from the original C7 tip; source maps, geometry/config, producer code, K1/K5 and artifacts are untouched. `git diff --check` PASS. No branch merge performed.
