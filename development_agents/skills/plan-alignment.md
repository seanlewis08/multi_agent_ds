# Skill: Plan Alignment

Use this skill before changing code.

## Required Reads

Read these files in order:

1. `project_planning/ARCHITECTURE.md`
2. `project_planning/BUILD_PLAN.md`
3. `project_planning/PROJECT_TREE.md`
4. `project_planning/FUTURE_WORK.md`

## Rules

- `ARCHITECTURE.md` decides placement, ownership, and import direction.
- `BUILD_PLAN.md` decides what the project is building now and which layers are intentionally incomplete.
- `PROJECT_TREE.md` captures the original repository tree and is the baseline for deciding whether a new path or script belongs in the repo.
- `FUTURE_WORK.md` marks ideas that should stay deferred unless the user explicitly asks for them.
- If a request conflicts with the plan, follow the user only after stating the deviation clearly in your reasoning.
- If the plan already names the missing file or layer, prefer that path over inventing a parallel structure.
- If a proposed new script, helper, or entrypoint is outside `PROJECT_TREE.md` and not explicitly introduced by `BUILD_PLAN.md`, treat it as a likely plan deviation and prefer an existing module.
