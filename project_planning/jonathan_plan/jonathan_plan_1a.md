# Jonathan Plan Step 1a Subplan

Source: [jonathan_plan_1.md](/Users/jonathan.chia/code/multi_agent_ds/project_planning/jonathan_plan/jonathan_plan_1.md)

## Goal

Execute Step 1a by implementing `src/multi_agent_ds/tools/git.py` as a stateless git and GitHub utility module with no new dependencies.

## Scope

- Target file: `src/multi_agent_ds/tools/git.py`
- Validation target: add or update tests for the git tool without introducing a new script or dependency
- Constraints:
  - keep the module stateless
  - use `subprocess.run()` wrappers rather than `gitpython` or `PyGithub`
  - keep business logic and LLM behavior out of `tools/git.py`
  - use `gh` CLI for PR operations

## Execution Checklist

### Prep

- [x] Review `tools/io.py` for module structure and error-handling style to mirror in `tools/git.py`
  Decision: mirror `tools/io.py` with a flat module shape, module docstring, narrow imports, module-level logger, standalone stateless helpers, and explicit error handling around each subprocess boundary.
- [x] Review existing tests under `tests/` to choose the right test file location for git utility coverage
  Decision: use `tests/unit/test_git.py` as the primary target because `tests/unit/` is already part of the planned tree; fallback is `tests/test_git.py` only if we need to match the current flat test habit.
- [x] Confirm `src/multi_agent_ds/tools/__init__.py` does not require updates for the new module
  Decision: no `__init__.py` update is needed for Step 1a.

### File Creation

- [x] Create `src/multi_agent_ds/tools/git.py`
- [x] Add a module docstring describing git and GitHub utilities for experiment and development PR flows
- [x] Add imports for `subprocess`, `logging`, and `Path`
- [x] Add logger setup with `logging.getLogger(__name__)`

### Core Command Helper

- [x] Add one internal helper for running commands consistently
- [x] Ensure the helper captures stdout/stderr and raises clear errors on failure
- [x] Ensure the helper supports git and `gh` command execution without embedding workflow decisions
  Confirmed: `_run_command()` accepts a generic `list[str]` and passes it directly to `subprocess.run()` without command-specific branching or workflow logic.

### Function Implementation

- [x] Implement `get_current_branch()`
- [x] Implement `create_branch(branch_name, from_branch="main")`
- [x] Implement `stage_files(paths)`
- [x] Implement `stage_all_changes()`
- [x] Implement `commit(message)`
- [x] Implement `push_branch(branch_name, force=False)`
- [x] Implement `get_diff_summary(base="main")`
- [x] Implement `get_changed_files(base="main")`
- [x] Implement `create_pull_request(title, body, base="main", head=None, draft=False)`
- [x] Implement `get_open_prs(base="main")`

### Behavioral Checks

- [x] Confirm each function is a standalone wrapper with no persisted state
  Confirmed: each function builds a command, delegates execution to `_run_command()`, and returns a derived value without storing state between calls.
- [x] Confirm `create_pull_request()` uses `gh pr create`
  Confirmed: `create_pull_request()` builds a `["gh", "pr", "create", ...]` command and then uses `gh pr view` only to fetch structured metadata after creation.
- [x] Confirm `get_open_prs()` uses `gh pr list`
  Confirmed: `get_open_prs()` builds a `["gh", "pr", "list", ...]` command with `--state open`, `--base`, and `--json`, then parses the JSON response into normalized dicts.
- [x] Confirm path inputs are normalized safely for `git add`
  Confirmed with caveat: `stage_files()` normalizes each path with `Path(...)` and uses `git add -- ...` to avoid option injection, but it does not validate repository membership or filesystem existence.
- [x] Confirm branch and commit functions return the values promised in the parent checklist
  Confirmed: `create_branch()` returns the branch name and `commit()` returns the new commit hash, matching the parent checklist contracts.
- [x] Confirm no new dependency was introduced
  Confirmed: `tools/git.py` uses only standard-library imports (`json`, `logging`, `subprocess`, and `Path`).

### Tests

- [x] Add or update targeted tests for `tools/git.py`
- [x] Cover successful command execution paths
- [x] Cover failure handling for subprocess errors
- [x] Cover parsing behavior for changed files and PR responses where applicable

### Validation

- [x] Run the targeted test selection for `tools/git.py`
- [x] Review the final diff for architecture fit and scope control
  Confirmed: the implementation stays in `tools/`, uses no new dependency, and remains scoped to Step 1a; unrelated worktree changes still require narrow staging later.
- [x] Update `jonathan_plan_1.md` to mark completed Step 1a checkboxes after implementation

## Done Condition

Step 1a is complete when `src/multi_agent_ds/tools/git.py` exists, the required wrappers are implemented in a stateless form, targeted tests exist and pass, and the parent checklist is updated to reflect the completed 1a items.
