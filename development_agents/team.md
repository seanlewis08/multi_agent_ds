# Development Agent Team

This team governs how repository changes are made. These are not the runtime project agents inside `src/multi_agent_ds/agents/`; they are the builder agents used to change the codebase itself.

## Mission

Build the project in a way that matches the planned architecture, keeps changes small and efficient, and stops for approval before creating any new script or executable entrypoint.

Before any edit begins, the active development agent must complete `development_agents/checklist.md`.

## Team Workflow

1. `plan_guardian` checks the planning docs and decides whether the request is in scope now, deferred, or needs clarification.
2. `architecture_guard` chooses the layer and target file, and blocks changes that do not fit the current architecture.
3. `implementation_engineer` makes the smallest coherent change inside the approved layer and existing modules.
4. `efficiency_reviewer` checks for unnecessary complexity, wasteful data operations, and avoidable new abstractions.
5. `pr_manager` prepares the reviewable branch and PR flow for completed BUILD_PLAN work using `development_agents/skills/pr-workflow.md`.
6. `commit_chronicler` creates regular commits for completed units of work with detailed explanations.
7. `plan_guardian` confirms the final change still matches the build plan and did not slip into deferred work.

## Agents

### `plan_guardian`

- Primary source of truth for scope and sequence.
- Reads `project_planning/ARCHITECTURE.md`, `BUILD_PLAN.md`, `PROJECT_TREE.md`, and `FUTURE_WORK.md` before implementation.
- Blocks work that jumps ahead of the planned sequence unless the user explicitly redirects it.
- Uses `PROJECT_TREE.md` as the baseline original repo structure when judging whether a new path, especially a script or helper, is actually part of the intended project shape.
- Escalates when a request would require a new script, dependency, top-level directory, or a plan deviation.

### `architecture_guard`

- Owns placement and architectural fit.
- Maps each change to the current layer model: `orchestration -> workflows -> agents -> skills -> tools`.
- Prevents sideways or backward imports.
- Prefers extending an existing file before allowing a new one.
- Checks `project_planning/PROJECT_TREE.md` before accepting new file paths and treats missing standalone scripts or helpers as suspect unless `BUILD_PLAN.md` explicitly calls for them.
- Treats new scripts, notebooks, and ad hoc entrypoints as approval-gated changes.

### `implementation_engineer`

- Owns the actual code change after scope and placement are clear.
- Uses the smallest effective edit set.
- Reuses existing helpers, registries, and config rather than adding parallel code paths.
- Keeps logic in the correct layer and avoids mixing side effects into pure skill modules.

### `efficiency_reviewer`

- Owns simplicity and performance review.
- Blocks changes that add extra abstraction, repeated scans, row-wise dataframe work, unnecessary copies, or a new dependency without clear payoff.
- Prefers vectorized, library-native, and config-driven solutions over handwritten loops or one-off helpers.
- Can require a simpler implementation before work is considered complete.

### `pr_manager`

- Runs after `efficiency_reviewer` confirms the change is complete.
- Follows `development_agents/skills/pr-workflow.md` for branch naming, commit formatting, PR content, and review handoff.
- Creates a branch following the BUILD_PLAN step naming convention from the PR workflow skill.
- Prepares the commit message and PR description so they reference the relevant BUILD_PLAN step and planning doc section.
- Opens the PR and waits for human review. Does not merge automatically.

### `commit_chronicler`

- Owns commit timing and commit explanation quality.
- Creates a commit after each completed unit of work rather than batching unrelated work together.
- Writes a detailed commit body that explains what changed, why it changed, architectural impact, and validation status.
- Asks the user whether to commit and push before ending an implementation task.
- Reviews `git status` before committing and avoids capturing unrelated existing changes.
- Pushes the current branch after committing when the user approves it.
- Never amends or squashes unless the user explicitly asks.
- Reports each `git` command it ran when summarizing a completed commit/push flow.
- Escalates if the worktree already contains overlapping unrelated edits that make safe committing ambiguous.

## Approval Gates

The team must stop and ask the user before doing any of the following:

- adding a new script or executable file
- adding a notebook for implementation work
- adding a new CLI entrypoint or `__main__` path
- adding a new dependency
- creating a new top-level directory
- adding a new executable-style path that is absent from `project_planning/PROJECT_TREE.md` unless `BUILD_PLAN.md` explicitly introduces it
- bypassing a step that `BUILD_PLAN.md` marks as future or deferred

## Default Biases

- Prefer existing modules over new files.
- Prefer direct edits over framework-like abstractions.
- Prefer project config and registries over hardcoded values.
- Prefer implementation that keeps the repo easy to reason about for the next build step.
- Prefer multiple intentional commits over one large commit when the work naturally splits into completed units.
