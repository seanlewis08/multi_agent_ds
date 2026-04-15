# Development Agent Contract

This repository has two separate agent layers:

- Runtime project agents live in `src/multi_agent_ds/agents/`.
- Development agents that build and change this repository live in `development_agents/`.

Any coding agent working in this repo must follow the development-agent instructions before making changes.

## Instruction Order

Use these sources in this order when they conflict:

1. `project_planning/ARCHITECTURE.md`
2. `project_planning/BUILD_PLAN.md`
3. `project_planning/PROJECT_TREE.md`
4. `project_planning/FUTURE_WORK.md`
5. `development_agents/checklist.md`
6. `development_agents/team.md`
7. `development_agents/agent.md`
8. Relevant files in `development_agents/skills/`

## Non-Negotiables

- Fit changes into the existing architecture before inventing a new structure.
- Keep import direction `orchestration -> workflows -> agents -> skills -> tools`.
- Keep `skills/` pure: no LLM calls, no MLflow logging, no file I/O.
- Put side effects in workflows, tools, or adapters where the architecture already expects them.
- Prefer editing an existing module over adding a new file.
- Treat `project_planning/PROJECT_TREE.md` as the canonical original repo tree when evaluating whether a new path belongs in the repository.
- Never add a new script, notebook, CLI entrypoint, or standalone executable without explicit user approval.
- If a proposed script, notebook, helper, or entrypoint is not present in `PROJECT_TREE.md` and not explicitly called for in `BUILD_PLAN.md`, treat it as likely unnecessary and prefer folding the work into an existing planned module.
- If a new file seems necessary, stop and ask unless that file is already called for in `BUILD_PLAN.md`.
- Keep behavior config-driven when the repo already uses `config/*.yaml` for that concern.
- Prefer the smallest workable change that preserves readability and reuses current utilities.
- Bias toward efficient additions: vectorized/dataframe-native operations, no redundant scans, no avoidable copies, no extra dependency unless the payoff is clear.
- After any implementation task, ask the user whether to commit and push the completed changes before ending the turn.
- If a commit or push happens, include a summary of each `git` command that was run so the user can review the exact commit flow.

## Required Development Flow

1. Read the planning docs that apply to the task. Include `project_planning/PROJECT_TREE.md` whenever file placement, new files, or possible script drift is involved.
2. Complete `development_agents/checklist.md` before making edits.
3. Use `development_agents/team.md` to choose the right development agent role.
4. Follow `development_agents/agent.md` when the task includes commit discipline.
5. Load only the skill files needed for the task.
6. Before closing an implementation task, ask whether to commit and push the completed unit of work.
7. If the work would add a script or new entrypoint, ask first.
