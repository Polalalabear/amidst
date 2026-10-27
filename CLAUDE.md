@AGENTS.md

# Claude Code instructions

Read in this order:

1. The task's brief, or, for a coordinating session, the handoff: `docs/agents/COORDINATOR_HANDOFF_20261027.md`, then the pinned task board [#93](https://github.com/Polalalabear/amidst/issues/93).
2. `docs/agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md` (acceptance criteria AC1–AC8 and the Codex/Claude split) and the [two-line plan](https://github.com/Polalalabear/amidst/pull/252) (`docs/agents/Q1Q5_TWO_LINE_PLAN_20261027.md` once #252 merges).
3. `docs/evaluation/Q5_DECISION_WINDOW_D79.md` (the D79 decision-window document).
4. `docs/specs/Q1Q5_PRODUCT_SPEC.md` (the Q1–Q5 product specification).
5. `docs/operations/Q1Q5_PROGRESS.md` (every PR and issue, by category and status).
6. `docs/operations/Q1Q5_LOCAL_TEST_SETUP.md` only when the task runs the local engineering scene.
7. Relevant engineering documents only when the assigned task needs them. Superseded documents are listed in `docs/archive/ARCHIVE_20261027.md`.

For Office demo tasks, Claude Code owns all workbench visualization and usability (playback, camera/target selection, synchronized 2D/3D, hypothesis bands, curves, evidence inspection, demo mode), separable pure algorithm modules (blind-interval hypotheses, negative-evidence pruning), evaluation tooling and charts, browser acceptance, independent verification of Codex results, and planning/research documents. Codex owns Blender planning/rendering, perception and contact estimators, backend reconstruction and integration, camera geometry and API contracts, scene presets and launcher, retrieval index, deterministic fallback, and Agent orchestration. See the plan's task split (`docs/agents/OFFICE_DEMO_PLAN_20261101.md`, archived; see `docs/archive/ARCHIVE_20261027.md`) for details.

Q1–Q5 work is self-selected from the task board: take only `ready` issues with your own `owner:*` label, one task at a time, and stop at `needs-auth` or checkpoints. Each session gets one concrete task. Do not create worktrees, recursively explore unrelated modules, run large Blender renders or research experiments, or inspect large media without a specific need. Mark missing paths/assets `UNKNOWN`; do not invent them. Stop after the assigned task and its focused verification.

Writing sessions: at most three at a time (D87), with non-overlapping file sets, at least 9 GiB of free disk before the third one starts, and no rendering on the Claude side. Each writes in its own scratchpad `git clone --shared` with `origin` set to the GitHub remote, and deletes that clone when done. Stop when free disk space drops below 8 GiB.

The coordinator updates [`docs/operations/Q1Q5_PROGRESS.md`](docs/operations/Q1Q5_PROGRESS.md) in batches for the PRs and issues opened (D91-4; see "Progress guide" in AGENTS.md); a PR does not need to add its own row.

## Choosing model and effort for sub-sessions

The coordinating session plans, decides, writes briefs and reads reports. It does not do task work inline: opening branches, reviews, issue comments and result records go to sub-sessions. When it dispatches a task to a new Claude Code session, it sets `model` and `effort` on `start_session` from the table below. You can only choose a model at or below the coordinator's and an effort no higher than its own. Opus is for decisions: design and architecture changes, deletion and merge decisions, and formal acceptance. Sonnet does formal code review and technical verification. Haiku does simple routine tasks, inventory and retrieval. These settings do not apply to Codex tasks; the user picks Codex's model.

| Task type | Examples | Model | Effort |
| --- | --- | --- | --- |
| Decision review: deletion, merge, architecture change, formal acceptance, complex code (see the criteria below) | PRs for K1, K4, C4a, C4b, C5, C7; any branch or PR deletion; formal baseline acceptance | Opus | high |
| Formal code review (every code PR) | Sonnet reviews the diff, focused tests, `git diff --check`, merge-tree check | Sonnet | medium |
| Technical verification of inventory findings | Checking each cleanup candidate's refs, merge-base, PR state and references against raw `git`/`gh` output | Sonnet | medium |
| Algorithm and design work | K1 hypothesis module, K7 map-verification method, answering contract open questions, plan and decision documents | Sonnet | high |
| Complex 3D visualization | K4 hypothesis bundle and reachable-region bands | Sonnet | high |
| Implementation with a clear spec | K3, K5, K6 demo mode, RQ2–RQ4 evaluation and charts | Sonnet | medium |
| Browser acceptance, read-only diagnostics, recomputing numbers | CP2/CP3 walkthroughs, per-frame listings, verifying Codex's numbers | Sonnet | low or medium |
| Simple routine tasks and inventory | Disk usage, listing branches, PRs and issues, posting result records, updating issue or task-table links, link checks, file searches | Haiku | low |

**Complex code** means a PR that meets any of these: it changes algorithms, geometry, projection or coordinate transforms; it changes inputs to inference, ranking or reconstruction, or touches Ground Truth isolation; it has more than about 300 lines of non-test code changes; or a Sonnet review reported it as uncertain or blocking.

**Review flow.** Sonnet runs the formal review of every code PR: the full diff, the focused tests, `git diff --check` and a merge-tree check against the integration branch. Opus decides only when the Sonnet review raises a decision, or when the PR is complex code. Opus then checks the flagged points rather than re-reviewing the whole PR. Reviews read the diff itself; Explore and other subagents are not used unless the user asks or the brief explicitly authorizes them.

**Cleanup of disk space, branches, PRs and issues** runs in this order: Haiku inventories and retrieves the facts, Sonnet verifies each candidate technically, Opus decides on anything that deletes or merges, and then the change is executed and verified. Opus does not decide from Haiku's summary alone. For deletion, architecture changes and formal acceptance, Opus reads the raw evidence directly (`git ls-remote`, `git log`, `gh pr view`, `gh api`, and the file contents themselves), and checks that no dependency was missed. Deletion needs the user's explicit authorization, and branches that hold evidence are kept (AGENTS.md).

**Escalate one tier** (Haiku → Sonnet → Opus), or raise effort one step, when a sub-session reports an ambiguous spec, fails at the same point twice, or produces numbers that disagree with the expected values.

**Keeping token use low without losing accuracy:**

- Briefs quote the spec clauses, exact file paths, the consumers to check and the exact test commands, so sub-sessions do not re-read whole documents.
- Follow-ups go to the session that already has the context (`SendMessage`), not to a new session.
- Batch mechanical updates: one Haiku session per checkpoint instead of one per event.
- Accept work from the commands and numbers in the result record; read the diff only when something disagrees.
- Default effort is medium; high is for algorithm design or after the same failure twice.

Every result record states the model and effort used (the `Model / effort` line in the AGENTS.md template).
