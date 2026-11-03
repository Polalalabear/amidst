@AGENTS.md

# Claude Code instructions

Current as of D108 (2026-11-01). Where an older document disagrees with this file, AGENTS.md or the decisions D104–D108 on [#93](https://github.com/Polalalabear/amidst/issues/93), the newer rule wins; superseded documents, PRs, issues and branches are listed in [`docs/operations/DEPRECATION_INDEX_20261101.md`](docs/operations/DEPRECATION_INDEX_20261101.md).

Read in this order:

1. The task's brief. A coordinating session reads the newest coordinator handoff in `docs/agents/` (`COORDINATOR_HANDOFF_*.md`, latest date) and then the decisions on [#93](https://github.com/Polalalabear/amidst/issues/93) from D104 onward.
2. The architecture baseline [#306](https://github.com/Polalalabear/amidst/issues/306): authoritative documents with ref/SHA, module boundaries, no-deviation rules and guard commands.
3. The queue [#279](https://github.com/Polalalabear/amidst/issues/279): the feature table, the [queue-resumed notice](https://github.com/Polalalabear/amidst/issues/279#issuecomment-6556614928) and the [§0 prompt, D105 version](https://github.com/Polalalabear/amidst/issues/279#issuecomment-6556632821). Then, for feature work, the feature issue (#369–#376) and its "feature 歸併" comment.
4. `docs/specs/Q1Q5_PRODUCT_SPEC.md` (the Q1–Q5 product specification) and `docs/DEVELOPMENT_RULES.md`.
5. `docs/operations/Q1Q5_PROGRESS.md` (progress guide) and `docs/operations/DEPRECATION_INDEX_20261101.md` (what is no longer current).
6. Only when the task needs them: `docs/agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md` (AC1–AC8), `docs/agents/Q1Q5_TWO_LINE_PLAN_20261027.md`, `docs/evaluation/Q5_DECISION_WINDOW_D79.md`, `docs/operations/Q1Q5_LOCAL_TEST_SETUP.md` and other engineering documents. Archived documents are listed in `docs/archive/ARCHIVE_20261027.md`.

## Claude's role

The Claude/Codex split is in AGENTS.md ("Ownership"). On the Claude side:

- **Feature review (D104-2, D105-7).** Claude reviews each feature PR for four things only: architecture boundaries (#306), conformance to the specification and contracts, Ground Truth isolation, and deviation from the design. Codex runs the integration acceptance to all green; Claude does not review code line by line. A command that waits on an external return, a user gate or LOCAL formal data is reported `NOT_RUN` with its gate, never `PASS`.
- **Low-level decisions (D104-3).** Claude settles items that do not change the goal or scope (scoring details, a single G4 edge or transition, pending `PENDING` items, labels and classification) from the design documents, and records them on #93 or the feature issue without opening a question card. Claude asks the user only about scope or goal changes, demo content (script freeze, scenario cards), merge authorization (one batch at a time), anything external (packages for yyin or team members), and demo acceptance.
- **Merging.** Merges happen only after the user approves a batch (D104-4); the coordinator then merges in the D105-7 order with merge commits.
- **Own work.** Demo UI in `frontend/workbench-v2/` (K-UI), the physical-prediction pure module, test-first specifications and `-T` tests (contracts stay PROPOSED until Codex confirms, D107-4), evaluation tooling and charts, browser acceptance, independent verification of Codex results, and planning, decision and research documents.

Each session gets one concrete task. Do not create worktrees, recursively explore unrelated modules, run Blender renders or research experiments, or inspect large media without a specific need. Mark missing paths/assets `UNKNOWN`; do not invent them. Stop after the assigned task and its focused verification.

**Checkouts and writing sessions (D87, D103-3, D108-4).** New sessions start from the clean shared checkout `~/Developer/amidst-q1q5` (`mainline/q1q5`) and do not switch branches or edit files there. A writing session works in its own scratchpad `git clone --shared` with `origin` set to the GitHub remote, and deletes that clone when done. At most three writing sessions run at a time, with non-overlapping file sets; check free disk first: below 9 GiB do not start a third, below 8 GiB all writing stops. The old checkouts `~/Developer/amidst` and `~/Developer/amidst-claude` stay as they are (fetch only). Claude does no rendering.

The coordinator updates `docs/operations/Q1Q5_PROGRESS.md` and `docs/operations/DEPRECATION_INDEX_20261101.md` in batches (D91-4); a PR does not add its own row.

## Choosing model and effort for sub-sessions

The coordinating session plans, decides, writes briefs and reads reports. It does not do task work inline: opening branches, reviews, issue comments and result records go to sub-sessions. When it dispatches a task to a new Claude Code session, it sets `model` and `effort` on `start_session` from the table below. You can only choose a model at or below the coordinator's and an effort no higher than its own. Opus is for decisions: design and architecture changes, deletion and merge decisions, rule rewrites and formal acceptance. Sonnet does feature review and technical verification. Haiku does simple routine tasks, inventory and retrieval. These settings do not apply to Codex tasks; the user picks Codex's model.

| Task type | Examples | Model | Effort |
| --- | --- | --- | --- |
| Decision review: deletion, merge, architecture change, rule rewrite, formal acceptance, complex code (see the criteria below) | Batch-merge dry run and card (D105-7), G4 hash re-check (D101-2), rule rewrite (D108-1), any branch or PR deletion, formal baseline acceptance | Opus | high |
| Feature review (every feature PR, D104-2) | The four checks on the feature diff, the integration-acceptance results in the PR, `git diff --check`, merge-tree check against the base | Sonnet | medium |
| Technical verification of inventory findings | Checking each cleanup candidate's refs, merge-base, PR state and references against raw `git`/`gh` output | Sonnet | medium |
| Algorithm and design work | Physical-prediction module, test-first specifications and `-T`, answering contract open questions, plan and decision documents | Sonnet | high |
| Complex UI and visualization | Workbench-v2 demo UI (K-UI-1/2), top-view prediction display | Sonnet | high |
| Implementation with a clear spec | Evaluation tooling and charts, demo-mode polish | Sonnet | medium |
| Browser acceptance, read-only diagnostics, recomputing numbers | Demo walkthroughs, per-frame listings, verifying Codex's numbers | Sonnet | low or medium |
| Simple routine tasks and inventory | Disk usage, listing branches, PRs and issues, posting PR links on issues, updating labels or task-table links, link checks, file searches | Haiku | low |

**Complex code** means a PR that meets any of these: it changes algorithms, geometry, projection or coordinate transforms; it changes inputs to inference, ranking or reconstruction, or touches Ground Truth isolation; it has more than about 300 lines of non-test code changes; or a Sonnet review reported it as uncertain or blocking.

**Review flow.** Sonnet runs the feature review: the four checks of D104-2 on the diff, the integration-acceptance results reported in the PR, `git diff --check` and a merge-tree check against the base. Opus decides only when the Sonnet review raises a decision, or when the feature contains complex code; Opus then checks the flagged points rather than re-reviewing the whole PR. Reviews read the diff itself; Explore and other subagents are not used unless the user asks or the brief explicitly authorizes them.

**Cleanup of disk space, branches, PRs and issues** runs in this order: Haiku inventories and retrieves the facts, Sonnet verifies each candidate technically, Opus decides on anything that deletes or merges, and then the change is executed and verified. Opus does not decide from Haiku's summary alone. For deletion, architecture changes and formal acceptance, Opus reads the raw evidence directly (`git ls-remote`, `git log`, `gh pr view`, `gh api`, and the file contents themselves), and checks that no dependency was missed. Deletion needs the user's explicit authorization, and branches that hold evidence are kept (AGENTS.md). Until the 2026-11-05 cleanup, items are only labeled and listed in the deprecation index (D108-3).

**Escalate one tier** (Haiku → Sonnet → Opus), or raise effort one step, when a sub-session reports an ambiguous spec, fails at the same point twice, or produces numbers that disagree with the expected values.

**Keeping token use low without losing accuracy:**

- Briefs quote the spec clauses, exact file paths, the consumers to check and the exact test commands, so sub-sessions do not re-read whole documents.
- Follow-ups go to the session that already has the context (`SendMessage`), not to a new session.
- Batch mechanical updates: one Haiku session per checkpoint instead of one per event.
- Accept work from the commands and numbers in the result record; read the diff only when something disagrees.
- Default effort is medium; high is for algorithm design or after the same failure twice.

Every result record states the model and effort used (the `Model / effort` line in the AGENTS.md template).
