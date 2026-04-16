# Jonathan Plan Step 1 Checklist

Source: [Jonathan_Plan.md](/Users/jonathan.chia/code/multi_agent_ds/project_planning/Jonathan_Plan.md)

## Step 1: Git Tool + Experiment PR Agent

- [ ] Confirm Step 1 scope against `project_planning/Jonathan_Plan.md`
- [ ] Confirm Sean-owned dependencies are not required for Step 1
- [ ] Decide exact file targets for Step 1 changes

## 1a. `tools/git.py`

- [ ] Create `src/multi_agent_ds/tools/git.py`
- [ ] Add module docstring for git and GitHub utilities
- [ ] Add logging setup
- [ ] Implement `get_current_branch()`
- [ ] Implement `create_branch(branch_name, from_branch="main")`
- [ ] Implement `stage_files(paths)`
- [ ] Implement `stage_all_changes()`
- [ ] Implement `commit(message)`
- [ ] Implement `push_branch(branch_name, force=False)`
- [ ] Implement `get_diff_summary(base="main")`
- [ ] Implement `get_changed_files(base="main")`
- [ ] Implement `create_pull_request(...)`
- [ ] Implement `get_open_prs(base="main")`
- [ ] Keep the module stateless and subprocess-based
- [ ] Avoid adding new Python dependencies
- [ ] Add or update tests for `tools/git.py`

## 1b. `agents/reviewer.py`

- [ ] Create `src/multi_agent_ds/agents/reviewer.py`
- [ ] Define `reviewer_node(state: PipelineState) -> dict`
- [ ] Gather experiment context from orchestration state
- [ ] Generate PR description from experiment context
- [ ] Derive experiment branch naming strategy
- [ ] Create branch through `tools/git.py`
- [ ] Stage experiment files for the PR
- [ ] Commit with an experiment-focused message
- [ ] Push branch and open PR
- [ ] Return PR metadata in the node result
- [ ] Keep git side effects delegated to `tools/git.py`
- [ ] Add or update tests for `agents/reviewer.py`

## 1c. `config/settings.yaml`

- [ ] Add a `git` section
- [ ] Add `default_base_branch`
- [ ] Add `experiment_branch_prefix`
- [ ] Add `development_branch_prefix`
- [ ] Add `auto_push`
- [ ] Add `auto_pr`
- [ ] Add a `github.repo` setting
- [ ] Keep config changes consistent with existing settings structure

## 1d. `development_agents/skills/pr-workflow.md`

- [ ] Create `development_agents/skills/pr-workflow.md`
- [ ] Document branch naming convention
- [ ] Document commit message format
- [ ] Document PR description requirements
- [ ] Document the step-by-step development PR workflow

## 1e. `development_agents/team.md`

- [ ] Add `pr_manager` role definition
- [ ] Describe when `pr_manager` runs
- [ ] Link `pr_manager` behavior to `skills/pr-workflow.md`
- [ ] Keep the role aligned with the existing team workflow

## Validation

- [ ] Run targeted tests for Step 1 changes
- [ ] Review changed files for architecture fit
- [ ] Confirm no new dependency was added
- [ ] Confirm no unintended files are staged
- [ ] Prepare a commit only after Step 1 is a complete reviewable unit
