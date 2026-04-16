# Skill: PR Workflow

Use this skill after completing a BUILD_PLAN step that is ready for review.

## Branch Naming

- Format: `build/step-N-short-description`
- Create the branch from the configured development base branch unless the user directs otherwise.
- Keep the description short, lowercase, and hyphenated.
- Example: `build/step-6-llm-adapter`

## Commit Message Format

- Subject format: `[step N] Short description`
- The commit body should explain:
  - what was built
  - which files changed
  - what was tested or checked
- Keep the commit scoped to one completed step or one reviewable sub-step.

## PR Description Requirements

- Reference the relevant BUILD_PLAN step number.
- List the main files changed.
- Describe what was built and why it belongs in this step.
- Note any validation that was run.
- State what comes next in the following step.

## Workflow

1. Create a branch from the base branch using the build-step naming convention.
2. Make the planned changes for the completed step only.
3. Stage only the changed files for that step. Do not stage generated files or unrelated worktree changes.
4. Commit using the step-formatted subject and a detailed body.
5. Push the branch and create a PR.
6. Request human review and wait for feedback. Do not merge automatically.
