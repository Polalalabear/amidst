# Amidst Q1–Q5 第一版 Demo

Current as of D108 (2026-11-01). Rules here follow the decisions D104–D108 on [#93](https://github.com/Polalalabear/amidst/issues/93); until this version is merged, and wherever a document disagrees, those decisions win. Superseded rules, documents, PRs, issues and branches are listed in [`docs/operations/DEPRECATION_INDEX_20261101.md`](docs/operations/DEPRECATION_INDEX_20261101.md).

## Objective

Deliver the Q1–Q5 first demo on **2026-11-04** (D100-8): find cameras by a condition (Q1), find a person in the footage (Q2), parse the user's question (Q3), judge whether a frame contains the target (Q4), and decide when to switch cameras as the target leaves (Q5), with every answer traceable to source evidence. Two lines run in parallel (D87, [#251](https://github.com/Polalalabear/amidst/issues/251)):

- **Line 1, baseline:** the r004 scenes A4-1 (50 s) and B4-1 (42 s) on the graph v3 cameras (D89; script freeze approved in D105-1). This is the first demo's acceptance target.
- **Line 2, complex events:** cases the current scorer and rules cannot judge; the first batch is card set 甲 (RR＋LG＋PE1＋OV1, D99, D105-2).

Without the render approvals in time, the demo runs the P1 engineering/synthetic fallback and says so on [#346](https://github.com/Polalalabear/amidst/issues/346) (D100-8). This is an engineering demo, not identity, physical-safety, or formal research acceptance.

Schedule (D104-6): 11-02 Claude reviews by feature; 11-03 the user approves one merge batch, then rehearsal; 11-04 demo; from 11-05 the GitHub cleanup (branches, PRs, issues, following the deprecation index), then UI/UX changes.

## Shared rules

- Follow [docs/DEVELOPMENT_RULES.md](docs/DEVELOPMENT_RULES.md); it is the source of truth for architecture, source assets, GT isolation, camera conventions, uncertainty, and research boundaries. Do not duplicate or weaken those rules here.
- Preserve source/run/clock/hash provenance. Ground Truth, renderer trajectories, visibility, and depth stay out of inference, ranking, and reconstruction. Keep source observations, projections, inferences, `MISSING`, and `UNKNOWN` distinct; identity remains unconfirmed and physical navigation/collision remains unknown unless authorized evidence says otherwise.
- Do not delete, overwrite, render, copy, or otherwise modify original Blender, video, dataset, calibration, or Ground Truth assets without explicit authorization. Do not inspect large media unless a scoped task needs it.
- Stay inside the architecture baseline [#306](https://github.com/Polalalabear/amidst/issues/306): do not change authoritative contracts, schemas or decision semantics, and do not invent authorities, fields or flows. When a deviation is unavoidable, continue through the contract's fallback or fail closed, or write a deviation proposal on the issue and mark it `blocked-user`. Where a contract says PROPOSED or UNKNOWN, build only a configurable switch that fails closed by default.
- `frontend/workbench-v2/` is the only UI entry (#306 §2). It reaches data only through the HTTP API or recorded responses, never Ground Truth or scripts directly. `frontend/workbench/` is historical.
- **External model exception (D107).** The tracking top view may show an OpenAI estimate next to the physical prediction. It is off by default, labeled 「外部模型推測（非系統判斷）」, and used only as an illustration on the top view: it never enters scoring, Q1–Q5 judgments, ranking or fallback. Only a whitelisted structured payload is sent (no images, GT, scripts, renderer trajectories, visibility or depth; in playback, only data up to the current time); at most one call per search with one retry, cached, about 5 s timeout, a per-session cap, and any error falls back to the physical prediction. The demo replays recorded responses rather than calling live. The key lives only in the user's environment variable `OPENAI_API_KEY`; agents never read, print or write it to any file, PR or comment, and automated tests use fake responses.
- One owner per file set (see "Ownership" below); hand off through data contracts. Interface contracts are drafted by Claude Code and confirmed by Codex before parallel work starts.
- Work on one concrete task per session. Do not recursively explore unrelated modules or the whole repository without explicit approval. Start from the named handoff and task paths; mark unresolved paths/dependencies `UNKNOWN` for the bounded audit.
- **Checkouts (D108-4).** New sessions start from the clean shared checkout `~/Developer/amidst-q1q5` (`mainline/q1q5`); do not switch branches or edit files there. Writing happens in a separate clone (Claude: its own scratchpad `git clone --shared`, deleted when done). The old checkouts `~/Developer/amidst` and `~/Developer/amidst-claude` stay untouched except for `git fetch`. Do not create worktrees, and never change another agent's checkout or worktree.
- **Writers and disk (D87, D103-3).** At most three sessions write at the same time on each side, including sub-agents, with non-overlapping files. Below 9 GiB of free disk do not start a third; below 8 GiB all writing stops.
- Never reset, rebase, force-push, or merge without explicit authorization. Stage only task files; use a narrow commit and PR workflow on the assigned branch.
- Make changes reproducible and source-bound. For code tasks, run only the focused tests, `-T` tests and guards named in the task, and `git diff --check`; do not run full suites, Blender renders, inference, or research experiments unless the task explicitly requires and authorizes them.
- Stop when the assigned task and its focused verification are complete; report exact files, evidence, blockers, and anything not verified.

## Ownership

| Claude Code | Codex |
| --- | --- |
| Feature review (the four D104-2 checks) and low-level decisions (D104-3) | Feature integration branches and feature PRs (D104-1) |
| Demo UI in `frontend/workbench-v2/` (K-UI search, monitor wall, top view) | Blender planning and rendering (only when authorized), perception, detection index |
| Physical-prediction pure module (D107-4) | Adapters and backend interfaces, including the OpenAI adapter (Agent orchestration, D107-4) |
| Test-first specifications and `-T` drafts; contracts stay PROPOSED until Codex confirms | Backend reconstruction and integration, camera geometry and API contracts |
| Evaluation tooling and charts, browser acceptance, independent recomputation of scores | Scoring runs and packaging (yyin main pack, team evaluation pack; D97, D98-4) |
| Planning, decision, research and rule documents; progress guide and deprecation index | Scene presets and launcher, deterministic replay fallback, composition receipts |

Team members (`owner:team`) evaluate; they do not write answers they will later be scored against (D96-4).

## Source-of-truth documents

- [Development rules](docs/DEVELOPMENT_RULES.md)
- [Architecture baseline #306](https://github.com/Polalalabear/amidst/issues/306): authoritative document pins, module boundaries, no-deviation rules, guard commands. Only the coordinator updates its pins.
- [Decision log #93](https://github.com/Polalalabear/amidst/issues/93): the current process is D104 (feature delivery), D105 (U4/U6/U7/U8 and the settlement table B-1–B-29), D106 (feature-level labels only), D107 (external model only for the top view), D108 (rule rewrite and deprecation marking).
- [Codex queue #279](https://github.com/Polalalabear/amidst/issues/279): feature table, [queue-resumed notice](https://github.com/Polalalabear/amidst/issues/279#issuecomment-6556614928), [§0 prompt, D105 version](https://github.com/Polalalabear/amidst/issues/279#issuecomment-6556632821) (the §0 text in the issue body is the old version), [old-index retirement](https://github.com/Polalalabear/amidst/issues/279#issuecomment-6556897337).
- Feature issues FEAT-1 #376, FEAT-2 #369, FEAT-3 #370, FEAT-4 #371, FEAT-5 #372, FEAT-6 #373, FEAT-7 #374, FEAT-8 #375, each with its "feature 歸併" comment (sub-PR order, required fixes, integration acceptance).
- [Q1–Q5 product specification](docs/specs/Q1Q5_PRODUCT_SPEC.md) — replaces the archived PRD, system design, data schema and interfaces
- [Q1–Q5 first-demo contract](docs/contracts/Q1_Q2_FIRST_DEMO_V1.md) — the current version is on `codex/q1q5-staging` (contract B, #237, SHA `b700bf86…`); the mainline copy is not edited by hand
- [Baseline acceptance plan](docs/agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md) (Line 1) and [two-line plan](docs/agents/Q1Q5_TWO_LINE_PLAN_20261027.md) (D87)
- [D79 decision-window document](docs/evaluation/Q5_DECISION_WINDOW_D79.md) and [A4/B4 scenario cards v1](docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md) (D89)
- [Progress guide](docs/operations/Q1Q5_PROGRESS.md)
- [Deprecation index (2026-11-01)](docs/operations/DEPRECATION_INDEX_20261101.md) and [archive index](docs/archive/ARCHIVE_20261027.md) (D91)
- Coordinator handoffs in `docs/agents/COORDINATOR_HANDOFF_*.md` (newest date is current; [2026-10-27](docs/agents/COORDINATOR_HANDOFF_20261027.md) is a snapshot from before D95)

## Git workflow

- **Branches.** The integration branch is `mainline/q1q5` (D63). Codex product work sits on `codex/q1q5-staging` until the staging→mainline PR #267 merges as the last step of a batch. `main` stays frozen until the first demo passes and the user explicitly authorizes an update. Feature branches use `codex/*`, `claude/*` or `team/<name>/<task>`. Superseded branches keep `archive/<branch>` tags (for example `archive/office-demo-visualization` at `f481fe0`, `archive/3d-line`).
- **Feature delivery (D104-1, D105-7).** Codex delivers one feature per branch and per PR: the integration branch `codex/feat-<n>-<簡述>` starts from `codex/q1q5-staging`@`434e579`, and the feature PR's base is `codex/q1q5-staging`. Delivered sub-PRs are merged into it with `git merge --no-ff` in the order of the feature's "feature 歸併" comment, after checking each head against the SHA listed there; `git cherry-pick -x` only where that comment says so (#361). Sub-PRs are not merged on their own. The mainline-direct items #240 and #261 are fixed on their own branches and merged straight into `mainline/q1q5`. A shared sub-PR is changed only by its primary feature. Sub-task issues track progress only.
- **Integration acceptance (D104-2).** A feature passes only when every command listed on its feature issue is green: `-T` with `AMIDST_REQUIRE_IMPL=1`, the focused tests, the architecture guard (#307, `--base origin/codex/q1q5-staging`), the GT isolation check and `git diff --check`. Commands that wait on an external return, a user gate or LOCAL formal data are reported `NOT_RUN` with the gate, never `PASS` (D105-7-8).
- **Merging.** Merge commits only — no squash or rebase, because documents cite commit SHAs. Merges happen only after the user approves a batch (D104-4); the 11-03 order is FEAT-7 → FEAT-3 → FEAT-2 → FEAT-5 → FEAT-1 → FEAT-4 → FEAT-6 → #240, #261 (mainline) → #267 (staging→mainline), dry-run first with `git merge-tree`. Rule and documentation PRs from Claude use base `mainline/q1q5`; Claude's UI and specification PRs use base `codex/q1q5-staging`.
- Check branch and status before work, keep commits scoped to the assigned task, and publish only when the user has authorized push/PR.

### Claiming work

Codex claims by feature, following the [§0 prompt (D105 version)](https://github.com/Polalalabear/amidst/issues/279#issuecomment-6556632821): comment 「認領 FEAT-n：<chat 名>」 on the feature issue and add `codex-claimed`; one feature per chat at a time; priority FEAT-3 → FEAT-2 → FEAT-7 → FEAT-5 → FEAT-6 → FEAT-1 → FEAT-4 → FEAT-8 (D103-5). Within a feature, at most two sub-agents run in parallel on non-overlapping files. Stop rules are in the §0 prompt. This replaces the old `ready`/`in-progress` self-selection.

### Decision tiers (D104-3)

- Claude settles low-level items that do not change the goal or scope from the design documents (scoring details, a single G4 edge or transition, pending `PENDING` items, labels and classification), recorded on #93 or the feature issue, without a question card.
- Only these go to the user: scope or goal changes, demo content (script freeze U4, scenario cards U7), merge authorization (one batch at a time), anything external (packages for yyin or team members), and demo acceptance. Rendering, G4 and data-source approvals stay `blocked-user`.

### Labels (D106, D108-3)

- Status labels live only on feature issues and feature PRs: `codex-claimed` on a feature issue while it is claimed (removed on delivery), `needs-claude-review` on a feature PR when delivered. `blocked-user` stays where a user decision is pending. Sub-task issues carry no queue label; they link to their feature's "feature 歸併" comment.
- `deprecated` (no longer used, history only), `superseded` (replaced; a comment names the replacement) and `out-of-demo-scope` (still useful, not in the 11-04 demo; handled in the 11-05 cleanup) mark items listed in the deprecation index. Marking never closes a PR or issue or deletes a branch.
- The old labels `ready`, `in-progress`, `needs-auth`, `blocked` and `codex-queue` are no longer used for claiming (see the deprecation index).

### Progress guide

[`docs/operations/Q1Q5_PROGRESS.md`](docs/operations/Q1Q5_PROGRESS.md) lists every PR and issue exactly once, by primary category and status (已完成, 進行中, 未完成, 待確認). The coordinator keeps it current in batches (D91-4): new PRs and issues, merges and closures, overview counts and the snapshot date. Task authors do not add rows in their own PRs. PRs based on `codex/q1q5-staging` get their rows on `mainline/q1q5`, never on staging; when staging merges into `mainline/q1q5`, the coordinator resolves guide conflicts in a follow-up batch (the merge PR keeps the mainline version, D105 B-24).

### Handoff documents go on GitHub

Codex and Claude must both follow this rule (user, 2026-10-25).

- **Commit every handoff document.** This covers any document written for another agent, the user or the team member: handoff, reproduction or delivery notes; run commands; readiness lists; source compositions. Commit it in the same PR as the work it describes, under `docs/operations/` or `docs/engineering/`. A copy only in `~/amidst-artifacts`, `/private/tmp` or chat does not count.
- **Keep raw artifacts LOCAL** ([DEVELOPMENT_RULES](docs/DEVELOPMENT_RULES.md)): RGB, recordings, weights, databases and human returns. The committed document lists each LOCAL artifact: path relative to `$AMIDST_ARTIFACTS`, with no absolute home paths; size and file count; SHA-256 (or the MANIFEST SHA-256); whether and how it can be regenerated.
- **Commit multi-branch compositions.** When a runnable build combines several branches (for example a demo composition receipt), commit it as JSON listing the exact PR heads.
- **Block incomplete PRs.** A PR whose result can only be started from a LOCAL folder is not complete until its start-up document is committed. Reviewers mark it NEEDS_CHANGES otherwise.

## Checkpoints and result records

Human review gates are tracked as GitHub issues labeled `checkpoint` in the [Q1–Q5 第一版 milestone](https://github.com/Polalalabear/amidst/milestone/2). When work reaches a checkpoint:

- Stop and post the result record. Nothing in that checkpoint's scope merges into the integration branch until the user records approval on the checkpoint issue (for G4, the coordinator then records a D decision citing the same hash and the user's comment ID, D105-5). Before that, PRs may be opened and reviewed, but not merged.
- Do not start work that depends on an unapproved checkpoint unless the user says so.
- If an issue's or PR's scope is already completed elsewhere, comment where it was completed (PR, merge commit, file) and close it. Never close by deleting a branch, and keep the branches that hold the evidence.

Every task records its **actual output** in its PR description only (D104-5); the issue gets a link to the PR. Planned or expected outcomes are not results; leave a field `NONE` or `UNKNOWN` rather than guessing. When the effort is unknown, write 「<模型>／effort UNKNOWN（使用者設定）」 (D105 B-16).

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
