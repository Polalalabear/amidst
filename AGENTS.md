# Amidst Q1–Q5 第一版 Demo

## Objective

Deliver the Q1–Q5 first demo: find cameras by a condition (Q1), find a person in the footage (Q2), parse the user's question (Q3), judge whether a frame contains the target (Q4), and decide when to switch cameras as the target leaves (Q5), with every answer traceable to source evidence. Two lines run in parallel (D87, [#251](https://github.com/Polalalabear/amidst/issues/251)):

- **Line 1, baseline:** the r004 scenes A4-1 (50 s) and B4-1 (42 s) on the graph v3 cameras (D89). This is the first demo's acceptance target.
- **Line 2, complex scenes:** cases the current scorer and rules cannot judge (several RETURN events in one window, long LOST spans, D77 overlap handoff, new cameras or routes).

This is an engineering demo, not identity, physical-safety, or formal research acceptance.

## Shared rules

- Follow [docs/specs/DEVELOPMENT_RULES.md](docs/specs/DEVELOPMENT_RULES.md) (`docs/DEVELOPMENT_RULES.md` is a symlink to it); it is the source of truth for architecture, source assets, GT isolation, camera conventions, uncertainty, and research boundaries. Do not duplicate or weaken those rules here.
- Preserve source/run/clock/hash provenance. Ground Truth, renderer trajectories, visibility, and depth stay out of inference, ranking, and reconstruction. Keep source observations, projections, inferences, `MISSING`, and `UNKNOWN` distinct; identity remains unconfirmed and physical navigation/collision remains unknown unless authorized evidence says otherwise.
- Do not delete, overwrite, render, copy, or otherwise modify original Blender, video, dataset, calibration, or Ground Truth assets without explicit authorization. Do not inspect large media unless a scoped task needs it.
- Use `frontend/workbench-v2/` as the primary UI (served on 8785 by `scripts/serve_demo_integration.py`). The old `frontend/workbench/` is being retired (user decision 2026-11-17, D268; plan in [#486](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6950051568)): do not add features to it. Task ownership follows [§4 of the baseline acceptance plan](docs/agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md#4-工作分配) and the [two-line plan](https://github.com/Polalalabear/amidst/pull/252) (D87; `docs/agents/Q1Q5_TWO_LINE_PLAN_20261027.md`). One owner per file set; hand off through data contracts. Interface contracts are drafted by Claude Code and confirmed by Codex before parallel work starts.
- Work on one concrete task per session. Do not recursively explore unrelated modules or the whole repository without explicit approval. Start from the named handoff and task paths; mark unresolved paths/dependencies `UNKNOWN` for the bounded audit.
- Do not create worktrees. Preserve existing checkout, branch, uncommitted changes, and frozen inputs. Never reset, rebase, force-push, or merge without explicit authorization. Stage only task files; use a narrow commit and PR workflow on the assigned branch.
- Paid API calls always go through `ApiGuard` (#537): dry-run first, and run only after the user approves the amount in chat. An approved budget covers only its stated purpose and does not carry over to other uses or later runs (D242). The guard is `src/amidst/q1q5/api_budget.py` (ledger in `AMIDST_API_USAGE_DIR`); D339 lets OpenAI runs within the USD 50 allowance proceed without asking each time, but every run still dry-runs first and records its spend. G7 is fixed: every paid call goes through ApiGuard (`4f665d55`, #655; `docs/operations/PAID_API_G7_20261120.md`).
- The Q1–Q5 Agent mode follows D340 (supersedes D64; rule in DEVELOPMENT_RULES, interface in product spec §4.3): rule mode is the default and fallback; Agent mode is off by default, may see rendered frames and choose among all detections, and every request carries the scene context. GT isolation, `ApiGuard`, `UNCONFIRMED` identity and response validation stay hard-blocked. Research hypotheses H1–H6 and their current evidence are in the hypothesis plan below.
- Make changes reproducible and source-bound. For code tasks, run only the focused tests named in the task and `git diff --check`; do not run full suites, Blender renders, inference, or research experiments unless the task explicitly requires and authorizes them.
- Stop when the assigned task and its focused verification are complete; report exact files, evidence, blockers, and anything not verified.
- Browser tests and smoke runs are headless by default and never open windows on the user's desktop (D334). Open a visible browser only when the user asks to watch or for visual debugging (for example `HEADLESS=0`), and close it afterwards. Chrome may add `--disable-background-timer-throttling` and `--disable-backgrounding-occluded-windows`. Applies to Claude and Codex.
- Every piece of work has an issue before it starts (open one if missing), and every delivery is a PR (base `main`) linked to that issue, with the actual-output record on both (D334).

## Source-of-truth documents

- [Development rules](docs/specs/DEVELOPMENT_RULES.md) — D340 Agent mode (supersedes D64)
- [Q1–Q5 first-demo contract](docs/contracts/Q1_Q2_FIRST_DEMO_V1.md) — contract B ([#237](https://github.com/Polalalabear/amidst/pull/237), SHA `b700bf86…`, pinned in `configs/architecture/authority_pins_v1.json`); not edited by hand
- [Baseline acceptance plan](docs/agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md) (Line 1)
- [Two-line plan](https://github.com/Polalalabear/amidst/pull/252) (D87; `docs/agents/Q1Q5_TWO_LINE_PLAN_20261027.md`)
- [D79 decision-window document](docs/evaluation/Q5_DECISION_WINDOW_D79.md)
- [A4/B4 scenario cards v1](https://github.com/Polalalabear/amidst/pull/253) (D89; `docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md` once #253 merges)
- [Progress guide](docs/operations/Q1Q5_PROGRESS.md)
- [Latest coordinator handoff (2026-11-24)](docs/agents/COORDINATOR_HANDOFF_20261124.md)
- [Task board and decision log #93](https://github.com/Polalalabear/amidst/issues/93)
- [Archive index](docs/archive/ARCHIVE_20261027.md) — superseded Office, 3D-line, Phase 1/2 and early Q1–Q5 documents (D91)
- [Q1–Q5 product specification](docs/specs/Q1Q5_PRODUCT_SPEC.md) — replaces the archived PRD, system design, data schema and interfaces; §2 data flow and §4.3 Agent request structure (`agent_service.py`, `scene_context.py`, `camera_projection.py`)
- [Agent vs rule hypotheses H1–H6](docs/evaluation/AGENT_VS_RULE_HYPOTHESES_20261120.md) (D340/D341) — §0 current evidence; results in [W1 frame evaluation](docs/evaluation/W1_FRAME_EVAL_20261120.md), [W2 active Agent](docs/evaluation/W2_ACTIVE_AGENT_20261120.md) and the [vision-agent pilot](docs/evaluation/VISION_AGENT_RECORDED_20261120.md)
- [Agent API wiring audit](docs/engineering/AGENT_API_WIRING_AUDIT_20261120.md) — every model call path, ApiGuard coverage; G7 fixed in #655 (`4f665d55`)
- [E3 report (F4)](docs/operations/F4_E3_REPORT_658.md) — [#678](https://github.com/Polalalabear/amidst/pull/678) (`3c436357`): H1, H2 and H4 not supported for this dependent integration (D354)
- [Code ↔ document map](docs/index/CODE_DOC_MAP.md) and [index](docs/index/README.md)

## Git workflow

The integration branch is `main` (D200; the GitHub default since D214). `mainline/q1q5` is frozen at `8c741451` and is history only; the old `claude/office-demo-visualization` is frozen at `f481fe0` (tag `archive/office-demo-visualization`), the paused 2D→3D line is on `archive/3d-line`, and other superseded branches keep `archive/<branch>` tags. Every PR has base `main`, needs the CI check `checks` green, and merges with a **merge commit only** (no squash, rebase or force-push; documents cite commit SHAs). Merging needs the user's explicit approval in chat. The user runs merges, branch deletions, file deletions and process kills in their own terminal; commands given to the user include `--repo Polalalabear/amidst`. Review each other's PRs, keep commits scoped to the task, and publish only when the user has authorized push/PR. Never change another agent's checkout.

**Branches (D216, D248):** open a branch only for a large feature: one feature line, one branch, one PR, named `claude/feat-<line>` (Codex: `codex/feat-<line>`; team: `team/<name>/<task>`). Related work of a similar nature shares one feature branch rather than one branch per task (D334); small fixes, review fixes, document updates and follow-up work commit to the existing feature branch instead of a new one. Merge into `main` as soon as possible, and delete merged branches (the user runs the deletion). Superseded branches are deleted directly without an `archive/` tag; a closed PR still keeps its commits (`refs/pull/<n>/head`) (D249). Only one writing session per branch at a time; long tasks commit and push in stages.

**GitHub (D245):** interact with GitHub through `gh` (`gh pr view/diff/checks/comment`, `gh issue comment`, `gh api` to read files on other branches). Do not `git fetch` in `~/amidst` to read other branches.

**Folder (D171, D218):** the only local checkout is `~/amidst` (branch `main`), shared by Claude and Codex as the project folder. It runs the demo on 8785 with `local/demo-pin.json` locked to a commit, so never edit, switch branches or commit there, and never run `git clean`, `git checkout .` or `git reset` in it. All writing happens in a scratchpad clone: `git clone --shared --no-checkout ~/amidst <scratchpad>/clone`, set `origin` to the GitHub remote, branch from `origin/main`, and delete the clone when done. At most three writing sessions at once, with non-overlapping files; check `df` first.

**LOCAL artifacts:** non-git items live under the git-ignored `~/amidst/local/{data,evidence,archive}` (code finds them through `amidst.paths`; `AMIDST_ARTIFACTS` overrides the evidence root). Never use `/tmp`, absolute home paths or the old `~/amidst-artifacts` <!-- local-ref-ignore -->. Documents cite a LOCAL artifact by its path relative to `local/…` or `$AMIDST_ARTIFACTS`, with its SHA-256 (or "cannot be rebuilt" / "not applicable"); `scripts/check_local_artifact_refs.py` reports violations in CI (warning only for now).

**Work list (D281):** the work list is in the body of [#93](https://github.com/Polalalabear/amidst/issues/93), the only source. Assigning, taking and updating work all happen on the issues; the taking rules are in #93.

**Work status (D334):** keep every work item's status current on its issue (status label and the status line in the body) at each change, using fixed wording: `待認領` → `進行中（<agent>）` → `<agent> 已完成，待 Claude 審查` → `審查中` → `審查完畢（APPROVE／NEEDS_CHANGES／NEEDS_OPUS）` → `已合併 <SHA>`／`關閉`; keep the PR description's status in sync. One agent or session works an item at a time: claim it with an issue comment and `in-progress`, and nobody else takes it meanwhile. Do not leave stale status. After a review, the reviewer also updates the issue status, the affected rows of the #93 work list and any affected documents or records, not only the review comment.

Q1–Q5 work is self-selected from the pinned task board [#93](https://github.com/Polalalabear/amidst/issues/93): take only `ready` issues with your own `owner:*` label, claim by comment and `in-progress`, one task at a time, open a Draft PR (base `main`) with the actual-output record, and stop at `needs-auth` or checkpoints. Claude maintains the `ready`/`blocked`/`needs-auth` labels.

### Progress guide

[`docs/operations/Q1Q5_PROGRESS.md`](docs/operations/Q1Q5_PROGRESS.md) lists every PR and issue exactly once, by primary category (Q1–Q5, shared, process, paused, legacy) and status (已完成, 進行中, 未完成, 待確認). Keep it current:

- **Opening a PR:** the coordinator adds its row and moves the rows of the issues it advances in a batch (D91-4), updates the overview counts and the snapshot date, and keeps numbering without gaps.
- **Opening an issue:** the coordinator adds its row in the same batch (D91-4). Task authors do not add rows in their own PRs.
- **Merging or closing:** the coordinator moves the row to 已完成 in a batch (note the merge branch, or "關閉未合併" / "已完成" / "關閉（不處理）"). Task authors do not update the guide in their next PR.

### Handoff documents go on GitHub

Codex and Claude must both follow this rule (user, 2026-10-25). The trigger was that Codex's handoff and reproduction documents (`DEMO_V1_HANDOFF.md`, `HANDOFF_REQUIREMENTS.json`, `CURRENT.md`, `BASELINE_READINESS.md`, `DELIVERY_COMPOSITION.json`) existed only in `~/amidst-artifacts` (since replaced by `local/evidence`) and on no GitHub branch. <!-- local-ref-ignore -->

- **Commit every handoff document.** This covers any document written for another agent, the user or the team member:
  - handoff, reproduction or delivery notes;
  - run commands;
  - readiness lists;
  - source compositions.

  Commit it in the same PR as the work it describes, under `docs/operations/` or `docs/engineering/`. A copy only in `local/`, `/private/tmp` or chat does not count. <!-- local-ref-ignore -->
- **Keep raw artifacts LOCAL** ([DEVELOPMENT_RULES](docs/specs/DEVELOPMENT_RULES.md)): RGB, recordings, weights, databases and human returns. The committed document lists each LOCAL artifact:
  - path relative to `local/{data,evidence,archive}` or `$AMIDST_ARTIFACTS`, with no absolute home paths;
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
