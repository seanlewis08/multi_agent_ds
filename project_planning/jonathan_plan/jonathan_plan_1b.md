# Jonathan Plan Step 1b Subplan

Source: [jonathan_plan_1.md](/Users/jonathan.chia/code/multi_agent_ds/project_planning/jonathan_plan/jonathan_plan_1.md)

## Goal

Execute Step 1b by implementing `src/multi_agent_ds/agents/reviewer.py` as the experiment PR agent that reads experiment context from orchestration state, generates PR content, and delegates git/PR side effects to `src/multi_agent_ds/tools/git.py`.

## Scope

- Target file: `src/multi_agent_ds/agents/reviewer.py`
- Expected collaborators:
  - `src/multi_agent_ds/tools/git.py`
  - orchestration state definitions for `PipelineState`
  - available config access helpers if branch prefixes or repo settings are needed
- Validation target: add or update tests for the reviewer agent without introducing a new script or dependency
- Constraints:
  - keep git side effects inside `tools/git.py`
  - keep reviewer-specific decision logic in the agent layer
  - avoid adding new dependencies
  - fit the implementation to the current architecture and available shared infrastructure

## Execution Checklist

### Prep

- [x] Review the current `src/multi_agent_ds/agents/` modules for agent style and placement
  Decision: `src/multi_agent_ds/agents/reviewer.py` does not exist yet; the best style references are node-style modules such as `business_stakeholder.py` and `ml_reviewer.py`, which define a single `*_node(state: PipelineState) -> dict`.
- [x] Inspect the available orchestration state/contracts files to see whether `PipelineState` already exists and what fields are available
  Decision: `PipelineState` already exists and exposes reviewer-relevant fields including `evaluation_result`, `report_draft`, `experiment_report`, `business_review`, `agent_decisions`, `current_phase`, `should_loop`, and `iteration`.
- [x] Confirm whether Sean-owned dependencies for Steps 3–5 are still unnecessary for this Step 1b slice
  Decision: Step 1b is not blocked at the module level; `OpenAIAdapter`, `PipelineState`, and shared contracts already exist, even though graph/orchestrator integration is still placeholder-level.
- [x] Identify any missing shared interfaces that would block a concrete `reviewer_node`
  Finding: there is no dedicated reviewer contract yet, and some reviewer-relevant state remains loosely typed, so a concrete node is possible but will require either conservative assumptions or a local reviewer-specific shape within the current layer boundaries.
- [x] Decide the exact test file target for reviewer-agent coverage
  Decision: use `tests/unit/test_reviewer.py` as the Step 1b test target.

### File Creation

- [x] Create `src/multi_agent_ds/agents/reviewer.py`
- [x] Add a module docstring describing the experiment PR reviewer agent
- [x] Add only the imports needed for state access, config access, and `tools/git.py`
- [x] Keep the file scoped to the reviewer agent responsibilities described in `Jonathan_Plan.md`
  Confirmed: `reviewer_node()` remains the single entrypoint, builds reviewer-specific context and PR content, derives branch/commit/PR inputs in the agent layer, and delegates all git/PR side effects to `tools/git.py`.

### Node Contract

- [x] Define `reviewer_node(state: PipelineState) -> dict`
- [x] Document the node’s expected inputs from orchestration state
- [x] Document the node’s returned PR metadata shape
- [x] Keep the returned data compatible with later orchestration use

### State Consumption

- [x] Gather experiment context from orchestration state
- [x] Read modeling results from state
- [x] Read evaluation results from state
- [x] Read agent decision trace or equivalent reviewable context from state
- [x] Read config snapshot or settings-derived values needed for PR creation
- [x] Handle missing optional state fields without pushing complexity into `tools/git.py`

### PR Description Generation

- [x] Decide whether Step 1b should use a temporary local formatter or a future LLM adapter hook for PR text
  Decision: target a future LLM adapter hook rather than a temporary local formatter, because the repo already has an `OpenAIAdapter` and `Jonathan_Plan.md` explicitly describes LLM-generated PR text for this agent.
- [x] Wire in `OpenAIAdapter` for PR description generation
- [x] Generate a PR description from experiment context
- [x] Ensure the description includes what was tested, why, results, key decisions, and config changes
- [x] Keep text-generation logic inside the agent layer rather than the tools layer
  Confirmed: `tools/git.py` remains limited to git/gh command wrappers, while PR description generation is implemented in `agents/reviewer.py` through `_build_pr_description()` and `OpenAIAdapter`.

### Branch and Commit Planning

- [x] Derive an experiment branch naming strategy
  Decision: use `experiment/<winner-or-phase>-<short-summary>-<YYYY-MM-DD>`; derive the slug from `evaluation_result` winner when available, otherwise `modeling_results`, otherwise `current_phase`, with fallback `experiment/run-<date>`.
- [x] Use `tools/git.create_branch()` to create the branch
- [x] Decide which experiment files should be staged for the PR
  Decision: stage `reports/experiment_log_<timestamp>.md` plus `config/settings.yaml` and any other YAML config files actually changed during the run; do not stage `mlruns/`, `mlruns/output/`, or temporary working files by default.
- [x] Use `tools/git.stage_files()` or `tools/git.stage_all_changes()` as appropriate
- [x] Build an experiment-focused commit message
- [x] Use `tools/git.commit()` to create the commit

### PR Creation Flow

- [x] Use `tools/git.push_branch()` to push the branch
- [x] Use `tools/git.create_pull_request()` to open the PR
- [x] Return PR metadata in the node result
- [x] Keep git side effects delegated to `tools/git.py`

### Behavioral Checks

- [x] Confirm the reviewer agent contains decision logic but not raw git subprocess code
  Confirmed: `reviewer.py` orchestrates decisions and delegates all git/PR side effects through `tools/git.py`, with no direct subprocess use.
- [x] Confirm the node remains within the `agents/` layer responsibilities
  Confirmed: the node reads `PipelineState`, builds reviewer context, generates PR text, derives branch/commit/PR inputs, and returns updated state metadata without moving tool logic into the agent.
- [x] Confirm any PR text generation stays out of `tools/git.py`
  Confirmed: PR description generation is implemented in `agents/reviewer.py` via `_build_pr_description()` and `OpenAIAdapter`, while `tools/git.py` remains command-wrapper only.
- [x] Confirm the node does not require a new dependency
  Confirmed: Step 1b uses the existing `OpenAIAdapter` and standard-library imports only; no new dependency was introduced.
- [x] Confirm the planned branch/commit/PR flow aligns with `Jonathan_Plan.md`

### Tests

- [x] Add or update targeted tests for `agents/reviewer.py`
- [x] Cover happy-path reviewer flow with mocked state and mocked git tool calls
- [x] Cover handling of missing or partial state inputs where applicable
- [x] Cover PR metadata returned from the node
- [x] Keep tests isolated from live git and GitHub access

### Validation

- [x] Run the targeted test selection for `agents/reviewer.py`
- [x] Review the final diff for architecture fit and scope control
- [x] Update `jonathan_plan_1.md` to mark completed Step 1b checkboxes after implementation

## Done Condition

Step 1b is complete when `src/multi_agent_ds/agents/reviewer.py` exists, `reviewer_node()` reads experiment state and orchestrates the PR flow through `tools/git.py`, targeted tests exist and pass, and the parent Step 1 checklist reflects the completed 1b items.
