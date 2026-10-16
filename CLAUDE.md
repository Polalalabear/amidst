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

## Choosing model and effort for sub-sessions

When the coordinating session dispatches a task to a new Claude Code session, set `model` and `effort` on `start_session` from the table below. You can only choose a model at or below the coordinator's and an effort no higher than its own. Hard judgment and design get a strong model at high effort; clearly specified implementation gets a mid-tier model; mechanical work gets the cheapest. These settings do not apply to Codex tasks; the user picks Codex's model.

| Task type | Examples | Model | Effort |
| --- | --- | --- | --- |
| Algorithm and design judgment, ambiguous specs | K1 hypothesis module, K7 map-verification method, answering contract open questions, plan and decision documents | Opus (inherit) | high |
| Reviewing Codex PRs for correctness and spec compliance | PRs for C4a, C4b, C5, C7 | Opus | high (medium for small or docs-only PRs) |
| Frontend implementation with a clear spec | K3, K5, K6 demo mode | Sonnet | medium |
| Complex 3D visualization | K4 hypothesis bundle and reachable-region bands | Sonnet | high |
| Evaluation tooling with defined metrics | RQ2–RQ4 evaluation and charts | Sonnet | medium |
| Browser acceptance and step-by-step screenshots | CP2/CP3 walkthroughs | Sonnet | medium |
| Read-only diagnostics, data checks, recomputing numbers | Per-frame listings, verifying Codex's numbers | Sonnet | low or medium |
| Mechanical work | Posting result records, updating issue or task-table links, link checks, file searches | Haiku | low |

**Escalate** to Opus at high effort, or handle the task in the coordinating session, when a sub-session reports an ambiguous spec, fails at the same point twice, or produces numbers that disagree with the expected values. When unsure, pick one level higher; redoing work costs more than the stronger model.

Every result record states the model and effort used (the `Model / effort` line in the AGENTS.md template).
