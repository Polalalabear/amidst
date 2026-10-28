> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# C7 D15 restricted-policy handoff — 2026-10-17

User instruction: K1/K5 remain Claude-owned. This PR supplies policy output, loader format and a small test map; it does not modify K1 or claim native labels have been implemented.

D15 policy is a **separate** layer, never an obstacle or UNKNOWN walkability region. Only user-confirmed OBSTACLE_1F_OFFICE_01/02 are exported. Every entry carries tier RESTRICTED_POLICY, source_annotation_ref, full annotation-file SHA-256, per-annotation record SHA-256, confirmation_ref (the CP2 D15 comment), geometry, and explicit false flags for physical_obstacle / affects_walkability / affects_ranking. D16 seats and lecterns stay physical source obstacles.

`docs/engineering/C7_OFFICE_RESTRICTED_POLICY_20261017.json` has schema office-demo.restricted-policy.v1. It binds the unchanged physical map file/output hashes and has variants legacy_office/person, each with its own unchanged run parameters, floor Z, physical_sections_sha256 and **restricted_regions**. Policy geometry is the original annotated XY footprint, scaled once by0.0247; no erosion, body-radius inflation, snapping, physical-map clipping or C4a clipping. The original annotation role/booleans are not reused as collision or visibility authority.

The additive layer deliberately avoids rewriting the frozen C7 physical map. Its own SHA forms restricted_ref. `load_restricted_policy(...)` verifies file/canonical/source/physical-map hashes and returns separate restricted_ref/restricted_regions; C4b can pass these into Claude's extended floor-map interface once available. Do not place them into regions or unknown_regions as a workaround.

## Small map for Claude

`tests/fixtures/c7_restricted_policy_small_map_v1.json` is a small SYNTHETIC_CONTRACT_INPUT_NOT_SOURCE_MAP, not real source evidence: one8×4m physical room, one crossing policy strip, a second policy polygon wholly outside the physical room, and a route crossing the first. Expected: physical PASS remains PASS; crossing gets RESTRICTED_POLICY/area_refs/restricted_area_crossed; all lattice/reachable/scores remain unchanged; outside policy cannot create walkability. The fixture is ready for K1 tests. Our geometry tests check the input separation, not K1 engine implementation.

## 實際產出 / Actual output

- Model / effort: UNKNOWN (authoritative session model/effort not exposed).
- PR / commits: PR #40, codex/c7-source-map, parent7214ef7; exact new commit in publication. No merge.
- Files changed: src/amidst/geometry/restricted_policy.py; scripts/export_restricted_policy.py; configs/c7_office_restricted_policy_v1.json; docs/engineering/C7_OFFICE_RESTRICTED_POLICY_20261017.json; tests/fixtures/c7_restricted_policy_small_map_v1.json; tests/unit/test_restricted_policy.py; this handoff, docs index and WORK_LOG.
- Commands/results: commands below; **17 passed in0.38s, 0failed/skipped** (3policy +14source-floor regression); Ruff check/format three changed Python files PASS; git diff --check PASS.
- Artifacts: hashes below. Original physical map SHA53c3771327ad71e26f0a5f1f4db580eaafb7bc7d028b9c250c9f401495bbcd61 unchanged.
- Verified: two user-confirmed source refs in both variants; correct tier/confirmation/hash fields; physical sections and input bundle unchanged; policy file/source pins fail closed; fixture does not create physical walkability.
- Not verified: K1 policy labels, K4 rendering, C4b native transmission to an extended K1 interface, browser, real navigation. These depend on Claude's K1 change by explicit user choice; no workaround was applied. No Blender/export/render of source meshes, GT, venv/worktree or dependency installation.
- Deviations/UNKNOWN/follow-ups: output is additive separate policy bundle, not a rewrite of frozen physical map. K1 owner must add optional restricted_ref/restricted_regions, echo restricted hash, label links/cell sample indices without changing check result/search/ranking. CP2 stays unapproved.

```sh
PYTHONPATH=src UV_CACHE_DIR=/private/tmp/amidst-c7-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python scripts/export_restricted_policy.py --map docs/engineering/C7_OFFICE_SOURCE_MAP_20261017.json --annotations data/scene_audit/school_v3_approved_scale_20261006/geometry.json --config configs/c7_office_restricted_policy_v1.json --output docs/engineering/C7_OFFICE_RESTRICTED_POLICY_20261017.json
PYTHONPATH=src UV_CACHE_DIR=/private/tmp/amidst-c7-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -m pytest tests/unit/test_restricted_policy.py tests/unit/test_source_floor_map.py -o addopts='' -q
```

- `docs/engineering/C7_OFFICE_RESTRICTED_POLICY_20261017.json` SHA-256 `3f821beae59aa57a6d5459a6a4993fcb36c58ecc3f2c79bf7646dc162a99b270`
- `tests/fixtures/c7_restricted_policy_small_map_v1.json` SHA-256 `d71475f9bef24fb2a38bc12e73cc7a211d0b779b70beea151f877da869620540`
- `configs/c7_office_restricted_policy_v1.json` SHA-256 `4929941092b581d651dbde8abb8697592c066ddb06cf1212ac8e79806534fc43`
