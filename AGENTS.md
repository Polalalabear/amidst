# Amidst Office Demo MVP

## Objective

Deliver a bounded, reproducible Office Demo: select one source observation, follow evidence across two spatially separated Office cameras through a meaningful blind interval, and inspect observed, inferred, missing, and unknown states in the shared workbench. Treat this as an engineering demo, not identity, physical-safety, or formal research acceptance.

## Shared rules

- Follow [docs/DEVELOPMENT_RULES.md](docs/DEVELOPMENT_RULES.md); it is the source of truth for architecture, source assets, GT isolation, camera conventions, uncertainty, and research boundaries. Do not duplicate or weaken those rules here.
- Preserve source/run/clock/hash provenance. Ground Truth, renderer trajectories, visibility, and depth stay out of inference, ranking, and reconstruction. Keep source observations, projections, inferences, `MISSING`, and `UNKNOWN` distinct; identity remains unconfirmed and physical navigation/collision remains unknown unless authorized evidence says otherwise.
- Do not delete, overwrite, render, copy, or otherwise modify original Blender, video, dataset, calibration, or Ground Truth assets without explicit authorization. Do not inspect large media unless a scoped task needs it.
- Use `frontend/workbench/` as the primary UI. Task ownership follows the [2026-11-01 plan](docs/agents/OFFICE_DEMO_PLAN_20261101.md#6-分工2026-10-16-起取代舊claude-只做前端) (updated 2026-10-16):
  - **Codex:** Blender feasibility checks, route planning and rendering (only when authorized), safe bundles, perception/contact estimators, backend integration and API contracts, scene presets and launcher, retrieval index and query API, Agent orchestration and recorded replay, deterministic fallback.
  - **Claude Code:** separable pure algorithm modules (blind-interval hypothesis generation, negative-evidence pruning), evaluation tooling and result charts, all workbench visualization and demo mode, browser acceptance, independent verification of Codex results, demo script, research and planning documents.
  - One owner per file set; hand off through data contracts. Interface contracts are drafted by Claude Code and confirmed by Codex before parallel work starts.
- Work on one concrete task per session. Do not recursively explore unrelated modules or the whole repository without explicit approval. Start from the named handoff and task paths; mark unresolved paths/dependencies `UNKNOWN` for the bounded audit.
- Do not create worktrees. Preserve existing checkout, branch, uncommitted changes, and frozen inputs. Never reset, rebase, force-push, or merge without explicit authorization. Stage only task files; use a narrow commit and PR workflow on the assigned branch.
- Make changes reproducible and source-bound. For code tasks, run only the focused tests named in the task and `git diff --check`; do not run full suites, Blender renders, inference, or research experiments unless the task explicitly requires and authorizes them.
- Stop when the assigned task and its focused verification are complete; report exact files, evidence, blockers, and anything not verified.

## Source-of-truth documents

- [Office demo plan to 2026-11-01](docs/agents/OFFICE_DEMO_PLAN_20261101.md) — current goals, research questions, task split, schedule and demo outline
- [Green-marker diagnosis 2026-10-16](docs/engineering/OFFICE_MARKER_DIAGNOSIS_20261016.md)
- [Pipeline map](docs/engineering/OFFICE_PIPELINE_MAP.md)
- [Initial Claude handoff](docs/operations/CLAUDE_INITIAL_HANDOFF.md)
- [Office Demo MVP](docs/agents/OFFICE_DEMO_MVP.md)
- [Claude task sequence](docs/agents/OFFICE_DEMO_TASKS.md)
- [Selected-target API contract](docs/contracts/OFFICE_DEMO_TARGET_V1.md)
- [Fixture configuration](configs/office_demo_fixture_v1.json)
- [Agent/fallback audit](docs/engineering/OFFICE_MVP_AGENT_AUDIT.md)
- [Existing development rules](docs/DEVELOPMENT_RULES.md)

## Git workflow

The integration branch is `mainline/q1q5` (D63, 2026-10-20). The old integration branch `claude/office-demo-visualization` is frozen at `f481fe0` (tag `archive/office-demo-visualization`); the paused 2D→3D line is archived on `archive/3d-line`; other superseded branches keep `archive/<branch>` tags. Work on feature branches with prefix `codex/*`, `claude/*` or `team/<name>/<task>` (team members) and merge into `mainline/q1q5` through PRs with **merge commits only** — no squash or rebase, because documents cite commit SHAs. Review each other's PRs. Check branch and status before work, keep commits scoped to the assigned task, and publish only when the user has authorized push/PR. Update `main` only after the first Demo passes and the user explicitly authorizes it, and never change another agent's checkout or worktree.

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
