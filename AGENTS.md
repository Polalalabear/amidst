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

The integration branch is `claude/office-demo-visualization`; Codex's backend branch is `codex/mvp-backend-integration`. Work on feature branches (`codex/*` or `claude/*`) and merge into the integration branch through PRs with **merge commits only** — no squash or rebase, because documents cite commit SHAs. Review each other's PRs. Check branch and status before work, keep commits scoped to the assigned task, and publish only when the user has authorized push/PR. Update `main` only with the user's explicit authorization, and never change another agent's checkout or worktree.
