# Amidst Q1–Q5 第一版 Demo

## Objective

Deliver the Q1–Q5 first demo: find cameras by a condition (Q1), find a person in the footage (Q2), parse the user's question (Q3), judge whether a frame contains the target (Q4), and decide when to switch cameras as the target leaves (Q5), with every answer traceable to source evidence. Two lines run in parallel (D87, [#251](https://github.com/Polalalabear/amidst/issues/251)):

- **Line 1, baseline:** the r004 scenes A4-1 (50 s) and B4-1 (42 s) on the graph v3 cameras (D89). This is the first demo's acceptance target.
- **Line 2, complex scenes:** cases the current scorer and rules cannot judge (several RETURN events in one window, long LOST spans, D77 overlap handoff, new cameras or routes).

This is an engineering demo, not identity, physical-safety, or formal research acceptance.

## Shared rules

- Follow [docs/DEVELOPMENT_RULES.md](docs/DEVELOPMENT_RULES.md); it is the source of truth for architecture, source assets, GT isolation, camera conventions, uncertainty, and research boundaries. Do not duplicate or weaken those rules here.
- Preserve source/run/clock/hash provenance. Ground Truth, renderer trajectories, visibility, and depth stay out of inference, ranking, and reconstruction. Keep source observations, projections, inferences, `MISSING`, and `UNKNOWN` distinct; identity remains unconfirmed and physical navigation/collision remains unknown unless authorized evidence says otherwise.
- Do not delete, overwrite, render, copy, or otherwise modify original Blender, video, dataset, calibration, or Ground Truth assets without explicit authorization. Do not inspect large media unless a scoped task needs it.
- Use `frontend/workbench/` as the primary UI. Task ownership follows [§4 of the baseline acceptance plan](docs/agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md#4-工作分配) and the [two-line plan](https://github.com/Polalalabear/amidst/pull/252) (D87; file `docs/agents/Q1Q5_TWO_LINE_PLAN_20261027.md`, on mainline once #252 merges). One owner per file set; hand off through data contracts. Interface contracts are drafted by Claude Code and confirmed by Codex before parallel work starts.
- Work on one concrete task per session. Do not recursively explore unrelated modules or the whole repository without explicit approval. Start from the named handoff and task paths; mark unresolved paths/dependencies `UNKNOWN` for the bounded audit.
- Do not create worktrees. Preserve existing checkout, branch, uncommitted changes, and frozen inputs. Never reset, rebase, force-push, or merge without explicit authorization. Stage only task files; use a narrow commit and PR workflow on the assigned branch.
- Make changes reproducible and source-bound. For code tasks, run only the focused tests named in the task and `git diff --check`; do not run full suites, Blender renders, inference, or research experiments unless the task explicitly requires and authorizes them.
- Stop when the assigned task and its focused verification are complete; report exact files, evidence, blockers, and anything not verified.

## Source-of-truth documents

- [Development rules](docs/DEVELOPMENT_RULES.md)
- [Q1–Q5 first-demo contract](docs/contracts/Q1_Q2_FIRST_DEMO_V1.md) — the current version is on `codex/q1q5-staging` (contract B, [#237](https://github.com/Polalalabear/amidst/pull/237), SHA `b700bf86…`); the mainline copy is not edited by hand
- [Baseline acceptance plan](docs/agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md) (Line 1)
- [Two-line plan](https://github.com/Polalalabear/amidst/pull/252) (D87; `docs/agents/Q1Q5_TWO_LINE_PLAN_20261027.md` once #252 merges)
- [D79 decision-window document](docs/evaluation/Q5_DECISION_WINDOW_D79.md)
- [A4/B4 scenario cards v1](https://github.com/Polalalabear/amidst/pull/253) (D89; `docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md` once #253 merges)
- [Progress guide](docs/operations/Q1Q5_PROGRESS.md)
- [Latest coordinator handoff (2026-10-27)](docs/agents/COORDINATOR_HANDOFF_20261027.md)
- [Task board and decision log #93](https://github.com/Polalalabear/amidst/issues/93)
- [Archive index](docs/archive/ARCHIVE_20261027.md) — superseded Office, 3D-line, Phase 1/2 and early Q1–Q5 documents (D91)
- [Q1–Q5 product specification](docs/specs/Q1Q5_PRODUCT_SPEC.md) — replaces the archived PRD, system design, data schema and interfaces

## Git workflow

The integration branch is `mainline/q1q5` (D63, 2026-10-20). The old integration branch `claude/office-demo-visualization` is frozen at `f481fe0` (tag `archive/office-demo-visualization`); the paused 2D→3D line is archived on `archive/3d-line`; other superseded branches keep `archive/<branch>` tags. Work on feature branches with prefix `codex/*`, `claude/*` or `team/<name>/<task>` (team members) and merge into `mainline/q1q5` through PRs with **merge commits only** — no squash or rebase, because documents cite commit SHAs. Review each other's PRs. Check branch and status before work, keep commits scoped to the assigned task, and publish only when the user has authorized push/PR. Update `main` only after the first Demo passes and the user explicitly authorizes it, and never change another agent's checkout or worktree.

Q1–Q5 work is self-selected from the pinned task board [#93](https://github.com/Polalalabear/amidst/issues/93): take only `ready` issues with your own `owner:*` label, claim by comment and `in-progress`, one task at a time, open a Draft PR (base `mainline/q1q5`) with the actual-output record, and stop at `needs-auth` or checkpoints. Claude maintains the `ready`/`blocked`/`needs-auth` labels.

### Progress guide

[`docs/operations/Q1Q5_PROGRESS.md`](docs/operations/Q1Q5_PROGRESS.md) lists every PR and issue exactly once, by primary category (Q1–Q5, shared, process, paused, legacy) and status (已完成, 進行中, 未完成, 待確認). Keep it current:

- **Opening a PR:** the coordinator adds its row and moves the rows of the issues it advances in a batch (D91-4), updates the overview counts and the snapshot date, and keeps numbering without gaps.
- **Opening an issue:** the coordinator adds its row in the same batch (D91-4). Task authors do not add rows in their own PRs.
- **Merging or closing:** the coordinator moves the row to 已完成 in a batch (note the merge branch, or "關閉未合併" / "已完成" / "關閉（不處理）"). Task authors do not update the guide in their next PR.
- Rows for PRs based on `codex/q1q5-staging` are added by a docs PR on `mainline/q1q5` or by the coordinator in a batch (D91-4), not on staging. When staging merges into `mainline/q1q5`, resolve guide conflicts by keeping every row once and recounting the overview.

### Handoff documents go on GitHub

Codex and Claude must both follow this rule (user, 2026-10-25). The trigger was that Codex's handoff and reproduction documents (`DEMO_V1_HANDOFF.md`, `HANDOFF_REQUIREMENTS.json`, `CURRENT.md`, `BASELINE_READINESS.md`, `DELIVERY_COMPOSITION.json`) existed only in `~/amidst-artifacts` and on no GitHub branch.

- **Commit every handoff document.** This covers any document written for another agent, the user or the team member:
  - handoff, reproduction or delivery notes;
  - run commands;
  - readiness lists;
  - source compositions.

  Commit it in the same PR as the work it describes, under `docs/operations/` or `docs/engineering/`. A copy only in `~/amidst-artifacts`, `/private/tmp` or chat does not count.
- **Keep raw artifacts LOCAL** ([DEVELOPMENT_RULES](docs/DEVELOPMENT_RULES.md)): RGB, recordings, weights, databases and human returns. The committed document lists each LOCAL artifact:
  - path relative to `$AMIDST_ARTIFACTS`, with no absolute home paths;
  - size and file count;
  - SHA-256 (or the MANIFEST SHA-256);
  - whether and how it can be regenerated.
- **Commit multi-branch compositions.** When a runnable build combines several branches (for example a delivery `COMPOSITION.json`), commit it as JSON listing the exact PR heads.
- **Block incomplete PRs.** A PR whose result can only be started from a LOCAL folder is not complete until its start-up document is committed. Reviewers mark it NEEDS_CHANGES otherwise.
- **Upload existing LOCAL-only documents in the next PR.** Codex uploads its current ones in its next PR (CX-4 or CX-10), with private paths removed.

## Checkpoints and result records

Human review gates are tracked as GitHub issues labeled `checkpoint` in the [Q1–Q5 第一版 milestone](https://github.com/Polalalabear/amidst/milestone/2); live task status is in the task issues. When work reaches a checkpoint:

- Stop and post the result record. Nothing in that checkpoint's scope merges into the integration branch until the user records approval on the checkpoint issue. Before that, PRs may be opened and reviewed by the other agent, but not merged.
- Do not start work that depends on an unapproved checkpoint unless the user says so.
- If an issue's or PR's scope is already completed elsewhere, comment where it was completed (PR, merge commit, file) and close it. Never close by deleting a branch, and keep the branches that hold the evidence.

Every task records its **actual output**, both in its PR description and as a comment on its issue, using this template. Planned or expected outcomes are not results; leave a field `NONE` or `UNKNOWN` rather than guessing.

```markdown
## 實際產出 / Actual output
- Model / effort: <model and effort used; UNKNOWN if not known>
- PR / commits: <links and SHAs>
- Files changed: <paths>
- Commands run and results: <exact commands; pass/fail counts; metrics with units>
- Artifacts: <paths and SHA-256; mark local paths outside the repository as LOCAL>
- Verified: <what was checked, and how>
- Not verified: <what was not run or checked, and why>
- Deviations, UNKNOWN items and follow-ups: <spec deviations, open questions, new issues>
```
