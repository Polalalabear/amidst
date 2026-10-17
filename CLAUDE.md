@AGENTS.md

# Claude Code instructions

Read in this order:

0. Coordinator sessions first read `docs/agents/COORDINATOR_HANDOFF_20261017.md`.
1. `docs/agents/OFFICE_DEMO_PLAN_20261101.md` (current plan and task split)
2. `docs/operations/CLAUDE_INITIAL_HANDOFF.md`
3. `docs/agents/OFFICE_DEMO_MVP.md`
4. `docs/agents/OFFICE_DEMO_TASKS.md`
5. `docs/contracts/OFFICE_DEMO_TARGET_V1.md`
6. Relevant engineering documents (start with `docs/engineering/OFFICE_PIPELINE_MAP.md`) only when the assigned task needs them.

Claude Code owns all workbench visualization and usability (playback, camera/target selection, synchronized 2D/3D, hypothesis bands, curves, evidence inspection, demo mode), separable pure algorithm modules (blind-interval hypotheses, negative-evidence pruning), evaluation tooling and charts, browser acceptance, independent verification of Codex results, and planning/research documents. Codex owns Blender planning/rendering, perception and contact estimators, backend reconstruction and integration, camera geometry and API contracts, scene presets and launcher, retrieval index, deterministic fallback, and Agent orchestration. See the plan's task split for details.

Claude Code Opus performs the initial bounded audit. Each later implementation session gets one concrete task from the task list. Do not create worktrees, recursively explore unrelated modules, run large Blender renders or research experiments, or inspect large media without a specific need. Mark missing paths/assets `UNKNOWN`; do not invent them. Stop after the assigned task and its focused verification.

## Choosing model and effort for sub-sessions

The coordinating session plans, decides, writes briefs and reads reports. It does not do task work inline: opening branches, reviews, issue comments and result records go to sub-sessions. When it dispatches a task to a new Claude Code session, it sets `model` and `effort` on `start_session` from the table below. You can only choose a model at or below the coordinator's and an effort no higher than its own. Opus is reserved for reviewing complex code; everything else runs on Sonnet or Haiku. These settings do not apply to Codex tasks; the user picks Codex's model.

| Task type | Examples | Model | Effort |
| --- | --- | --- | --- |
| Reviewing complex code (see the criteria below) | PRs for K1, K4, C4a, C4b, C5, C7 | Opus | medium (high only when it cannot decide) |
| Algorithm and design work | K1 hypothesis module, K7 map-verification method, answering contract open questions, plan and decision documents | Sonnet | high |
| Complex 3D visualization | K4 hypothesis bundle and reachable-region bands | Sonnet | high |
| Implementation with a clear spec | K3, K5, K6 demo mode, RQ2–RQ4 evaluation and charts | Sonnet | medium |
| Other PR reviews | Error handling, launcher, docs-only or small fixes (e.g. C3b) | Sonnet | medium |
| Browser acceptance, read-only diagnostics, recomputing numbers | CP2/CP3 walkthroughs, per-frame listings, verifying Codex's numbers | Sonnet | low or medium |
| Mechanical work | Posting result records, updating issue or task-table links, link checks, file searches, committing documentation text given in the brief | Haiku | low |

**Complex code** means a PR that meets any of these: it changes algorithms, geometry, projection or coordinate transforms; it changes inputs to inference, ranking or reconstruction, or touches Ground Truth isolation; it has more than about 300 lines of non-test code changes; or a Sonnet review reported it as uncertain or blocking.

**Review flow.** Sonnet reviews the full diff first and runs the focused tests, `git diff --check` and a merge-tree check against the integration branch. Opus (medium) runs only for complex code. It receives the Sonnet findings and checks the flagged points rather than re-reviewing the whole PR. Reviews read the diff itself; Explore and other subagents are not used unless the user asks or the brief explicitly authorizes them.

**Escalate one tier** (Haiku → Sonnet → Opus), or raise effort one step, when a sub-session reports an ambiguous spec, fails at the same point twice, or produces numbers that disagree with the expected values.

**Keeping token use low without losing accuracy:**

- Briefs quote the spec clauses, exact file paths, the consumers to check and the exact test commands, so sub-sessions do not re-read whole documents.
- Follow-ups go to the session that already has the context (`SendMessage`), not to a new session.
- Batch mechanical updates: one Haiku session per checkpoint instead of one per event.
- Accept work from the commands and numbers in the result record; read the diff only when something disagrees.
- Default effort is medium; high is for algorithm design or after the same failure twice.

Every result record states the model and effort used (the `Model / effort` line in the AGENTS.md template).
