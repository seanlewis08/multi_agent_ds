# Data Engineer Implementation Plan

**Scope:** Sean Step 4 from `Sean_Plan.md`  
**Primary targets:** `src/multi_agent_ds/skills/cleaning.py`, `skills/feature_engineering.py`, `workflows/preparation.py`, `agents/data_engineer.py`  
**Secondary targets:** `config/prompts.yaml`, `src/multi_agent_ds/core/contracts.py`  
**Status:** Implemented

## Purpose

Build the real data-engineering slice behind the now-complete EDA/preparation workflow.

This step should turn the current minimal preparation actions into a stronger, more explicit data-engineering surface that:

- interprets the approved prep plan
- applies cleaning and feature engineering deterministically
- returns structured summaries of what changed
- keeps the processed-data artifact path and processed-data handoff stable for downstream modeling

## Agent-Team Framing

- `plan_guardian`: Keep this scoped to Sean Step 4 only.
- `architecture_guard`: Keep pure transforms in `skills/`, persistence in `workflows/`, and LLM reasoning in `agents/`.
- `implementation_engineer`: Strengthen the existing preparation path instead of creating a parallel pipeline.
- `efficiency_reviewer`: Prefer dataframe-native operations and the smallest useful action surface.
- `commit_chronicler`: Commit only after the preparation slice and its focused tests pass as one coherent unit.

## Constraints

- Do not add a new script, notebook, or CLI entrypoint.
- Do not add a new dependency unless there is a clear blocker.
- Keep `skills/cleaning.py` and `skills/feature_engineering.py` pure.
- Keep file I/O and S3 writes in `workflows/preparation.py` or existing tools.
- Keep `data_engineer` responsible for reasoning about feasibility and execution summaries, not final approval.
- Preserve the already-approved prep loop shape and workflow iteration controls.

## Minimal Target Design

This step should produce:

- stronger cleaning helpers with explicit supported actions and structured summaries
- stronger feature-engineering helpers with explicit supported actions and structured summaries
- a preparation workflow that clearly separates:
  - load source data
  - apply approved cleaning actions
  - apply approved feature actions
  - save processed parquet
  - return a structured preparation result
- a `data_engineer` node that:
  - reviews prep-plan feasibility
  - executes approved plans
  - returns graph-ready prep state updates

The goal is not to add a huge action catalog. The goal is to make the currently supported actions robust, inspectable, and ready for the modeling step.

## Implementation Steps

### Step 1: Cleaning Surface

Tighten `skills/cleaning.py` around the currently supported actions:

- `drop_columns`
- `impute_numeric_median`
- `impute_categorical_mode`
- `clip_outliers_iqr`

Make sure each action:

- validates columns cleanly
- avoids touching the target column
- returns structured summaries of applied vs skipped actions

### Step 2: Feature Engineering Surface

Tighten `skills/feature_engineering.py` around the currently supported actions:

- `log1p`
- `ratio`

Make sure each action:

- validates source columns
- returns structured created-feature summaries
- handles invalid inputs cleanly

### Step 3: Preparation Workflow

Strengthen `workflows/preparation.py` so the execution path is explicit and inspectable:

- load source dataframe
- resolve target column
- apply cleaning actions
- apply feature actions
- save the processed parquet artifact
- return a structured result with:
  - source path
  - processed path
  - row/feature counts
  - cleaning summary
  - feature summary

### Step 4: Data Engineer Agent

Strengthen `agents/data_engineer.py`:

- keep `mode="feedback"` focused on feasibility review
- keep `mode="execute"` focused on approved-plan execution
- make outputs consistently structured for the orchestration layer
- keep prompt use aligned to the existing prep loop, not a new workflow shape

### Step 5: Validation and Closeout

Validate:

- cleaning actions behave correctly on representative fixtures
- feature actions behave correctly on representative fixtures
- preparation workflow produces a stable artifact result
- `data_engineer` feedback and execute modes return the expected state updates
- architecture boundaries remain intact

## Done Criteria

This step is complete when:

- the current cleaning and feature actions are robust enough for real Step 4 use
- `workflows/preparation.py` returns stable structured results
- `agents/data_engineer.py` has a reliable feedback/execution split
- the processed-data artifact path and summaries are trustworthy for downstream modeling

## Closeout

Implemented in completed slices:

- Step 1 tightened the cleaning surface and added focused cleaning tests.
- Step 2 tightened the feature-engineering surface and added focused feature tests.
- Step 3 strengthened the preparation workflow result contract and target-column validation.
- Step 4 tightened `data_engineer` feedback/execute outputs and added mocked agent coverage plus a human-run testing notebook.

Focused validation completed:

- `uv run pytest tests/test_cleaning.py tests/test_feature_engineering.py tests/test_preparation_workflow.py tests/test_pre_modeling_review_agents.py`

Remaining limitations:

- the supported prep actions are intentionally narrow for now
- the notebook is a manual validation aid rather than CI coverage
- the next planned build step is Sean Step 5: `ML Modeler + ML Reviewer`

## Resume Instructions

If work pauses, resume from:

- `project_planning/sean_step_artifacts/Data_Engineer_Checklist.md`

Recommended resume prompt:

```text
Use agent teams for this task. Pick back up where I left off in project_planning/sean_step_artifacts/Data_Engineer_Checklist.md and continue from the next unchecked item.
```
