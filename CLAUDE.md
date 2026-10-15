@AGENTS.md

# Claude Code instructions

Read in this order:

1. `docs/operations/CLAUDE_INITIAL_HANDOFF.md`
2. `docs/agents/OFFICE_DEMO_MVP.md`
3. `docs/agents/OFFICE_DEMO_TASKS.md`
4. `docs/contracts/OFFICE_DEMO_TARGET_V1.md`
5. Relevant engineering documents only when the assigned task needs them.

Claude Code owns frontend workbench video playback, camera/person selection, synchronized 2D/3D presentation, target visualization, curves, evidence inspection, and usability. Codex owns backend reconstruction, camera geometry/contracts, deterministic fallback, agent orchestration, and backend verification/integration.

Claude Code Opus performs the initial bounded audit. Each later implementation session gets one concrete task from the task list. Do not create worktrees, recursively explore unrelated modules, run large Blender renders or research experiments, or inspect large media without a specific need. Mark missing paths/assets `UNKNOWN`; do not invent them. Stop after the assigned task and its focused verification.
