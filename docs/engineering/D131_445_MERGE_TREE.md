# #445 merge-tree dry run (LOCAL)

All heads are live Draft PR heads read on 2026-11-07. `git merge-tree --write-tree --name-only` only; no merge commit, rebase, integration branch checkout or conflict resolution.

| Pair | Common base | Result | Conflict files / types |
| --- | --- | --- | --- |
| #443 + #452 | `796cc176cd40` | CONFLICT | `frontend/workbench-v2/core-search-track-model.mjs` (add/add) |
| #443 + #408 | `796cc176cd40` | CLEAN | NONE |
| #443 + #442 | `6065cd2608be` | CLEAN | NONE |
| #443 + #447 | `796cc176cd40` | CLEAN | NONE |
| #443 + #470 | `796cc176cd40` | CONFLICT | `configs/architecture/schema_registry_v1.json` (content) |
| #443 + #473 | `796cc176cd40` | CLEAN | NONE |
| #452 + #408 | `796cc176cd40` | CONFLICT | `frontend/workbench-v2/app.mjs` (content); `frontend/workbench-v2/index.html` (content); `frontend/workbench-v2/q-time.test.mjs` (content) |
| #452 + #442 | `6065cd2608be` | CLEAN | NONE |
| #452 + #447 | `796cc176cd40` | CLEAN | NONE |
| #452 + #470 | `796cc176cd40` | CONFLICT | `configs/architecture/schema_registry_v1.json` (content) |
| #452 + #473 | `796cc176cd40` | CLEAN | NONE |
| #408 + #442 | `6065cd2608be` | CLEAN | NONE |
| #408 + #447 | `796cc176cd40` | CLEAN | NONE |
| #408 + #470 | `796cc176cd40` | CLEAN | NONE |
| #408 + #473 | `796cc176cd40` | CLEAN | NONE |
| #442 + #447 | `6065cd2608be` | CLEAN | NONE |
| #442 + #470 | `6065cd2608be` | CLEAN | NONE |
| #442 + #473 | `6065cd2608be` | CLEAN | NONE |
| #447 + #470 | `796cc176cd40` | CLEAN | NONE |
| #447 + #473 | `796cc176cd40` | CLEAN | NONE |
| #470 + #473 | `796cc176cd40` | CLEAN | NONE |

## Exact heads

- PR #443: `20ea00fbfc0aa927a1fbc73b048d81641ccdd413`
- PR #452: `088252833665a4bca9fcfbf31597b4bb296fb549`
- PR #408: `eb10d4c62ce09a765488cdd0548cfdd3abfd5109`
- PR #442: `62a8979632d800e9ac6d23fc29789e56a11550bc`
- PR #447: `39b9c4323288cae8c52532277cdd6dc75b63a965`
- PR #470: `ea707902690d568700c90a3894805f168e244695`
- PR #473: `df493522fa10308a8712316a8881879cddd981ac`

## Interpretation and proposed order

Pairwise clean results do not prove a multi-PR sequence will merge cleanly. Keep #445 waiting for Claude review and checkpoint approval. Suggested order after future explicit merge authorization: #442 → #447 → #470 (issue #457) → #473 → #443 → #408 → #452. #408 establishes the older navigation/events/speed behavior; #452 should be reconciled last so its actual browser fixes are retained. Before each actual authorized merge, rerun merge-tree against the new integration head and resolve conflicts with both owners. #408 contains actual demo UI/event code; documentation alone cannot supply it. #443 supplies core behavior and #452 supplies frontend screens; their overlapping paths need source review, not a blind file choice. This is a planning order, not an approval or merge action.

## Concrete conflict handling plan

17 clean pairs; 4 conflicting pairs; 0 command errors. The six pairs involving #442 have common base 6065cd2608be7925e4e0e98f4e4ce0d213fe5eab; other pairs use 796cc176cd40bedbfe701b95192d3c8679755aa9.

- core-search-track-model.mjs: reconcile both exported request/response helpers and view-model helpers; preserve strict input validation, source pinning, single-view state boundaries and identity UNCONFIRMED. Run both sets of focused Python/Node tests.
- schema_registry_v1.json: combine only the exact new schema registrations and source-bound authority records; do not replace the registry wholesale or add allow exceptions. Run the no-allow architecture guard.
- app.mjs / index.html / any timing files listed above: retain #408 event navigation while preserving #452 core dispatch, monitor-wall visibility fix, missing-media distinction, bounded synthetic timeline playback and the complete 1.5x clock path. Run the actual Mac E2E, not just DOM tests.
- #442 / #447 / #473 may be textually clean, but keep r004/r005, source/run/clock/hash and LOCAL media separate. A clean merge-tree is not source/physical/research acceptance.
- No actual resolution, integration branch, index staging or merge commit was created. Pairwise tree previews are not a seven-way integration test; after any future authorized merge the next preview must be recomputed against the real resulting head.
