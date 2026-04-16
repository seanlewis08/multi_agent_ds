# Jonathan Plan Step 1 Checklist

Source: [Jonathan_Plan.md](/Users/jonathan.chia/code/multi_agent_ds/project_planning/Jonathan_Plan.md)

## Step 1: Git Tool + Experiment PR Agent

- [x] Confirm Step 1 scope against `project_planning/Jonathan_Plan.md`
  Scope confirmed: Step 1 covers the runtime experiment PR agent, development PR workflow guidance, and the supporting git/config changes.
- [x] Confirm Sean-owned dependencies are not required for Step 1
  Confirmed: `Jonathan_Plan.md` states Jonathan can start Steps 1–2 immediately; Sean's LLM adapter, LangGraph skeleton, and contracts are only needed before Jonathan Steps 3–5.
- [x] Decide exact file targets for Step 1 changes
  Target files: `src/multi_agent_ds/tools/git.py`, `src/multi_agent_ds/agents/reviewer.py`, `config/settings.yaml`, `development_agents/skills/pr-workflow.md`, and `development_agents/team.md`.

## 1a. `tools/git.py`

- [x] Create `src/multi_agent_ds/tools/git.py`
- [x] Add module docstring for git and GitHub utilities
- [x] Add logging setup
- [x] Implement `get_current_branch()`
- [x] Implement `create_branch(branch_name, from_branch="main")`
- [x] Implement `stage_files(paths)`
- [x] Implement `stage_all_changes()`
- [x] Implement `commit(message)`
- [x] Implement `push_branch(branch_name, force=False)`
- [x] Implement `get_diff_summary(base="main")`
- [x] Implement `get_changed_files(base="main")`
- [x] Implement `create_pull_request(...)`
- [x] Implement `get_open_prs(base="main")`
- [x] Keep the module stateless and subprocess-based
- [x] Avoid adding new Python dependencies
- [x] Add or update tests for `tools/git.py`

## 1b. `agents/reviewer.py`

- [x] Create `src/multi_agent_ds/agents/reviewer.py`
- [x] Define `reviewer_node(state: PipelineState) -> dict`
- [x] Gather experiment context from orchestration state
- [x] Generate PR description from experiment context
- [x] Derive experiment branch naming strategy
- [x] Create branch through `tools/git.py`
- [x] Stage experiment files for the PR
- [x] Commit with an experiment-focused message
- [x] Push branch and open PR
- [x] Return PR metadata in the node result
- [x] Keep git side effects delegated to `tools/git.py`
- [x] Add or update tests for `agents/reviewer.py`

## 1c. `config/settings.yaml`

- [x] Add a `git` section
- [x] Add `default_base_branch`
- [x] Add `experiment_branch_prefix`
- [x] Add `development_branch_prefix`
- [x] Add `auto_push`
- [x] Add `auto_pr`
- [x] Add a `github.repo` setting
- [x] Keep config changes consistent with existing settings structure

## 1d. `development_agents/skills/pr-workflow.md`

- [x] Create `development_agents/skills/pr-workflow.md`
- [x] Document branch naming convention
- [x] Document commit message format
- [x] Document PR description requirements
- [x] Document the step-by-step development PR workflow

## 1e. `development_agents/team.md`

- [x] Add `pr_manager` role definition
- [x] Describe when `pr_manager` runs
- [x] Link `pr_manager` behavior to `skills/pr-workflow.md`
- [x] Keep the role aligned with the existing team workflow

## Validation

- [x] Run targeted tests for Step 1 changes
  Verified: `uv run pytest tests/unit/test_git.py` passed (`6 passed`) and `uv run pytest tests/unit/test_reviewer.py` passed (`3 passed`).
- [x] Review changed files for architecture fit
  Confirmed: Step 1 changes stay in the planned files and layers: `tools/git.py`, `agents/reviewer.py`, `config/settings.yaml`, `development_agents/skills/pr-workflow.md`, and `development_agents/team.md`.
- [x] Confirm no new dependency was added
  Confirmed: `pyproject.toml` was not changed for Step 1.
- [x] Confirm no unintended files are staged
  Confirmed: `git diff --name-only --cached` returned no staged files.
- [x] Prepare a commit only after Step 1 is a complete reviewable unit
  Confirmed: Step 1 is complete and reviewable; the branch already contains the Step 1 commits, while unrelated `.env.example` and `uv.lock` worktree changes remain outside this unit.
