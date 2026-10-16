@AGENTS.md

# Claude Code instructions

Read in this order:

1. `docs/agents/OFFICE_DEMO_PLAN_20261101.md` (current plan and task split)
2. `docs/operations/CLAUDE_INITIAL_HANDOFF.md`
3. `docs/agents/OFFICE_DEMO_MVP.md`
4. `docs/agents/OFFICE_DEMO_TASKS.md`
5. `docs/contracts/OFFICE_DEMO_TARGET_V1.md`
6. Relevant engineering documents (start with `docs/engineering/OFFICE_PIPELINE_MAP.md`) only when the assigned task needs them.

Claude Code owns all workbench visualization and usability (playback, camera/target selection, synchronized 2D/3D, hypothesis bands, curves, evidence inspection, demo mode), separable pure algorithm modules (blind-interval hypotheses, negative-evidence pruning), evaluation tooling and charts, browser acceptance, independent verification of Codex results, and planning/research documents. Codex owns Blender planning/rendering, perception and contact estimators, backend reconstruction and integration, camera geometry and API contracts, scene presets and launcher, retrieval index, deterministic fallback, and Agent orchestration. See the plan's task split for details.

Claude Code Opus performs the initial bounded audit. Each later implementation session gets one concrete task from the task list. Do not create worktrees, recursively explore unrelated modules, run large Blender renders or research experiments, or inspect large media without a specific need. Mark missing paths/assets `UNKNOWN`; do not invent them. Stop after the assigned task and its focused verification.
