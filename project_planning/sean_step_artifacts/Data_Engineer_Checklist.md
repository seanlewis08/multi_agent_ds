# Data Engineer Checklist

**Plan file:** `project_planning/sean_step_artifacts/Data_Engineer_Implementation_Plan.md`  
**Primary implementation files:** `src/multi_agent_ds/skills/cleaning.py`, `skills/feature_engineering.py`, `workflows/preparation.py`, `agents/data_engineer.py`  
**Secondary files:** `config/prompts.yaml`, `src/multi_agent_ds/core/contracts.py`  
**Resume phrase:** `Pick back up where I left off`

## How To Resume

When returning to this work, use a prompt like:

```text
Use agent teams for this task. Pick back up where I left off in project_planning/sean_step_artifacts/Data_Engineer_Checklist.md and continue from the next unchecked item. Update the checklist and progress log as you go.
```

The current agent should:

1. read this checklist
2. read `project_planning/sean_step_artifacts/Data_Engineer_Implementation_Plan.md`
3. inspect the current state of `skills/cleaning.py`, `skills/feature_engineering.py`, `workflows/preparation.py`, and `agents/data_engineer.py`
4. continue from the next unchecked task

## Current Status

- Overall status: `planning complete`
- Current checkpoint: `Step 1 - Cleaning surface`
- Human review completed through: `planning only`
- Testing completed through: `none yet`

## Checkpoint Checklist

### Step 1: Cleaning Surface

- [ ] Tighten `drop_columns`
- [ ] Tighten `impute_numeric_median`
- [ ] Tighten `impute_categorical_mode`
- [ ] Tighten `clip_outliers_iqr`
- [ ] Keep cleaning logic pure and target-column safe

Human review checkpoint:

- [ ] Confirm the supported cleaning actions are still the intended initial scope
- [ ] Confirm no file I/O or workflow logic leaked into `skills/cleaning.py`

Testing checkpoint:

- [ ] Focused cleaning tests pass
- [ ] Cleaning summaries show applied vs skipped actions clearly

### Step 2: Feature Engineering Surface

- [ ] Tighten `log1p`
- [ ] Tighten `ratio`
- [ ] Keep feature engineering logic pure and target-column safe

Human review checkpoint:

- [ ] Confirm the supported feature actions are still the intended initial scope
- [ ] Confirm created-feature summaries are inspectable

Testing checkpoint:

- [ ] Focused feature-engineering tests pass
- [ ] Feature summaries show created vs skipped actions clearly

### Step 3: Preparation Workflow

- [ ] Re-check source-data loading path
- [ ] Re-check target-column resolution
- [ ] Re-check cleaning application
- [ ] Re-check feature application
- [ ] Re-check processed parquet save path and result structure

Human review checkpoint:

- [ ] Confirm side effects stay in the workflow layer
- [ ] Confirm the workflow result is stable enough for downstream modeling

Testing checkpoint:

- [ ] Preparation workflow tests pass
- [ ] Processed artifact result is inspectable

### Step 4: Data Engineer Agent

- [ ] Re-check `mode="feedback"` output structure
- [ ] Re-check `mode="execute"` output structure
- [ ] Keep the feedback/execution split clean
- [ ] Keep the agent aligned to the approved prep loop

Human review checkpoint:

- [ ] Confirm `data_engineer` still owns feasibility and execution only
- [ ] Confirm no final-approval logic leaked into the agent

Testing checkpoint:

- [ ] Mocked `data_engineer` agent tests pass
- [ ] Prep-loop state updates are stable for orchestration

### Step 5: Final Validation and Commit Readiness

- [ ] Run all focused Step 4 tests/checks
- [ ] Re-check the final Data Engineer slice against `Sean_Plan.md`
- [ ] Re-check the final Data Engineer slice against architecture boundaries
- [ ] Summarize remaining limitations, if any
- [ ] Ask: `Should I commit and push these changes?`

Human review checkpoint:

- [ ] Confirm the completed unit is reviewable on its own
- [ ] Confirm no unrelated worktree changes are being bundled

Testing checkpoint:

- [ ] Final focused validation is complete and recorded below

## Progress Log

Use this section to keep resumable notes while implementing.

### Entry Template

```text
Date:
Checkpoint:
Status:
Files touched:
Validation run:
Notes:
Next item:
```

### Initial Entry

```text
Date: 2026-04-16
Checkpoint: Planning only
Status: Checklist and implementation plan created
Files touched:
- project_planning/sean_step_artifacts/Data_Engineer_Implementation_Plan.md
- project_planning/sean_step_artifacts/Data_Engineer_Checklist.md
- project_planning/Sean_Plan.md
Validation run:
- documentation-only; no tests run
Notes:
- This checklist covers Sean Step 4 from Sean_Plan.md.
- The implementation starts from the existing minimal preparation actions and strengthens them into the real data-engineering slice.
- The main files are skills/cleaning.py, skills/feature_engineering.py, workflows/preparation.py, and agents/data_engineer.py.
Next item:
- Step 1 - Cleaning surface
```
