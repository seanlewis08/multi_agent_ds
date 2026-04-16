# multi_agent_ds — Development Protocol

**This protocol is MANDATORY. Do not skip steps "because the task is small".**

## Pre-Edit Checklist

Before any `Edit`, `Write`, or commit-creating `Bash` call in this repo, I MUST:

1. Read `development_agents/checklist.md` and confirm the pre-edit items.
2. State the active role for this slice:
   - `plan_guardian` — scope check against the planning docs
   - `architecture_guard` — placement and import direction
   - `implementation_engineer` — the actual code change
   - `efficiency_reviewer` — simplicity / no wasted abstraction
   - `commit_chronicler` — commit and push flow
3. Spawn the matching subagent via the `Agent` tool for load-bearing decisions.
   The subagents live at `.claude/agents/`:
   `plan-guardian`, `architecture-guard`, `implementation-engineer`,
   `efficiency-reviewer`, `commit-chronicler`.

Inline execution (no subagent) is acceptable only for trivial edits, and the
role must still be named out loud in the user-facing update.

## Approval Gates

Stop and ask the user **before** doing any of the following:

- New script, notebook, CLI entrypoint, or `__main__` path
- New dependency
- New top-level directory
- Path not listed in `project_planning/PROJECT_TREE.md`
- Work marked as deferred in `project_planning/FUTURE_WORK.md`

## Commit Flow (commit_chronicler)

- Ask `Should I commit and push these changes?` before running `git commit`.
- Inspect `git status` and stage only the slice's files — never bundle
  unrelated worktree edits.
- Commit body MUST cover: **what changed**, **why**, **architecture fit**,
  **validation**, and **notes / follow-ups**.
- Push the current branch only. Never force-push, amend, rebase, or squash
  unless the user explicitly asks.
- After committing, report each `git` command that was run, in order.

## Cadence

- Do NOT pause mid-step for review unless the user asks.
- Finish the whole checklist step, run the focused tests, then present the
  structured summary and ask about committing.

## End-of-Slice Summary Format

Every slice or step must end with this structure:

1. **Files edited / added / deleted** — table, one line per file with *why*.
2. **Functions / methods added** — table, one line per callable with *why*.
3. **Behavior changes in existing functions** — listed separately if any.
4. **Validation** — exact test command and pass count.

Hyperlink file paths from the repo root.

## Reference Docs

- `development_agents/team.md` — roles and team workflow
- `development_agents/checklist.md` — pre-edit checklist
- `development_agents/skills/*.md` — role-specific skill rules
- `project_planning/ARCHITECTURE.md` — layer and import rules
- `project_planning/BUILD_PLAN.md` — current scope and sequence
- `project_planning/PROJECT_TREE.md` — canonical repo shape
- `project_planning/FUTURE_WORK.md` — deferred work (never pull forward silently)
