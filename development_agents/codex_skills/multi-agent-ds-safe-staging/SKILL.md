---
name: "Safe Staging"
description: Stage and review only the correct files before committing. Use before git add or git commit, especially in a dirty worktree, when unrelated local changes exist, or when the same file contains both task-related and unrelated edits.
---

# Safe Staging

Use this skill before creating a commit.

## Staging Rules

- Check `git status` and confirm the files for this unit of work.
- Stage only the paths that belong to the current unit.
- Leave unrelated modifications unstaged.
- If the same file contains both your changes and unrelated changes, inspect carefully before staging.
- If safe separation is not clear, stop and ask the user.

## Review Rules

- Read the staged diff before committing.
- Make sure the commit contains one coherent change.
- Confirm the commit body matches the staged diff.

## Repository Safety

- Do not use destructive git commands to force a clean staging area.
- Do not amend prior commits unless the user explicitly asks.
