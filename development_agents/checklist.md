# Development Agent Pre-Edit Checklist

Complete this checklist before making any code edit.

## Required Readback

- I read `project_planning/ARCHITECTURE.md` for placement and import rules.
- I read `project_planning/BUILD_PLAN.md` for current scope and intended sequence.
- I read `project_planning/PROJECT_TREE.md` to understand the original repo tree before accepting new file paths or scripts.
- I read `project_planning/FUTURE_WORK.md` to confirm this work is not deferred.
- I read `development_agents/team.md` to pick the active development-agent role.
- I loaded only the `development_agents/skills/` files needed for this task.

## Scope Check

- I can state the user request in one or two sentences.
- I can name the exact file or files I expect to edit before I start.
- I am fitting this work into the current architecture, not creating a parallel structure.
- I am extending an existing module unless the plan already calls for a missing file.
- I checked `project_planning/PROJECT_TREE.md` before deciding that a new file, script, or helper path was necessary.

## Placement Check

- I know which layer owns this change: `orchestration`, `workflows`, `agents`, `skills`, `tools`, `adapters`, or `core`.
- I am preserving import direction: `orchestration -> workflows -> agents -> skills -> tools`.
- I am keeping `skills/` pure if this change touches that layer.
- I am keeping side effects out of layers that are supposed to stay pure.

## Efficiency Check

- I chose the smallest coherent implementation.
- I am reusing existing config, helpers, registries, or workflows before adding new ones.
- I am avoiding row-wise dataframe work when vectorized/library-native operations exist.
- I am not adding abstraction, copies, scans, or dependencies without a clear payoff.

## Approval Gate

- I am not adding a new script, notebook, CLI entrypoint, or standalone executable.
- I am not adding a new dependency.
- I am not creating a new top-level directory.
- If I think a new executable path is needed, I verified whether that path already exists in `project_planning/PROJECT_TREE.md` or is explicitly introduced by `BUILD_PLAN.md`.
- If any item above is false, I will stop and ask the user before editing.

## Commit Discipline Check

- I know whether this task should produce one commit or multiple commits.
- I will commit only completed units of work, not half-finished edits.
- I will not include unrelated existing worktree changes in my commit.
- I will explain each commit with what changed, why it changed, and how it was checked.
- If I commit or push, I will summarize each `git` command I ran so the user can review the sequence.
- After implementation, I will explicitly ask the user whether to commit and push this unit of work.

## Pre-Edit Output

Before editing, report:

1. the active development-agent role
2. the files you plan to edit
3. any approval-gated change you identified

## Post-Implementation Prompt

Before ending an implementation turn, ask:

`Should I commit and push these changes?`

If the user says yes:

1. review `git status`
2. stage only the files for the completed unit of work
3. create the detailed commit
4. push the current branch

If the user says no:

- leave the changes uncommitted
- summarize what is ready to commit later
