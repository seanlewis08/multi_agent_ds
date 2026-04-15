---
name: "Script Approval Gate"
description: Gate creation of new executable artifacts in the multi_agent_ds repo. Use when considering a new script, shell file, notebook, CLI entrypoint, module __main__, automation helper, or other runnable file, especially when it may sit outside the planned module tree.
---

# Script Approval Gate

Use this skill whenever a task might add a new executable artifact.

## What Counts As A Script

Treat all of the following as approval-gated:

- a new standalone `.py` file meant to be run directly
- a new shell script
- a new notebook used to implement or automate behavior
- a new CLI entrypoint
- a new module-level `__main__` path
- a staging helper outside the existing planned module tree

## Required Behavior

- Try to fit the work into an existing module first.
- Check `project_planning/PROJECT_TREE.md` before deciding a new executable artifact belongs in the repo.
- If the current architecture already has a valid entrypoint, extend it instead of adding another.
- If a script still seems necessary, stop and ask the user before creating it.
- If the candidate path is absent from `PROJECT_TREE.md` and not explicitly introduced by `BUILD_PLAN.md`, assume it is outside the intended original tree until the user approves it.
- When asking, state:
  - why the existing modules are not enough
  - which exact path you would create
  - what lower-scope alternative you ruled out

## Exception Rule

If `BUILD_PLAN.md` explicitly calls for a specific missing file, that planned file is allowed. Anything outside that planned structure still requires approval.
