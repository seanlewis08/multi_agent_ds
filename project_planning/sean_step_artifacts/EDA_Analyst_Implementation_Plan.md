# EDA Analyst Implementation Plan

**Scope:** Sean Step 3 from `Sean_Plan.md`  
**Primary targets:** `src/multi_agent_ds/skills/profiling.py`, `workflows/discovery.py`, `agents/eda_analyst.py`  
**Secondary targets:** `config/prompts.yaml`, `src/multi_agent_ds/core/contracts.py`  
**Status:** Expanded implementation in progress

## Purpose

Build the first real upstream runtime agent slice: pure profiling functions, a non-agentic discovery workflow, and an `eda_analyst` agent that turns a dataset profile into structured `eda_insights` for the rest of the graph.

This step started as the first real upstream runtime agent slice, but it has now expanded into the full pre-modeling EDA and preparation workflow:

- raw-data EDA
- downstream EDA reviews from `ml_modeler`, `ml_reviewer`, and `business_stakeholder`
- an `eda_analyst` ↔ `data_engineer` preparation loop
- one approved preparation execution
- processed-data EDA and re-review before modeling handoff

## Prompt Architecture

This step uses a hybrid prompt architecture:

- `Sequential / Pipeline` for the overall stage progression
- `Parallel / Fan-Out → Fan-In` conceptually for multi-agent EDA review
- `Reflection / Self-Critique` for the `eda_analyst` ↔ `data_engineer` refinement loop
- `Planning + Execution` because `eda_analyst` synthesizes a prep plan and `data_engineer` executes it once approved

The current graph implementation preserves this behavior as a serial review stage plus an explicit refinement loop, which is the smallest workable fit for the existing LangGraph skeleton.

## Agent-Team Framing

- `plan_guardian`: Keep this scoped to Sean Step 3 only.
- `architecture_guard`: Keep profiling logic in `skills/`, side effects in `workflows/`, and LLM reasoning in `agents/`.
- `implementation_engineer`: Build the smallest useful EDA slice that produces graph-ready insights.
- `efficiency_reviewer`: Prefer dataframe-native summaries over custom loops or oversized profiling abstractions.
- `commit_chronicler`: Commit only after profiling, discovery, and EDA agent checks pass as one coherent unit.

## Constraints

- Do not add a new dependency.
- Do not add a new script, notebook, or CLI entrypoint.
- Keep `skills/profiling.py` pure: no LLM calls, no MLflow logging, no file I/O.
- Keep the workflow responsible for loading data and writing any report artifact.
- Keep the agent responsible for interpreting profile output and producing structured `EDAOutput`.
- Do not implement the data engineer step here.

## Minimal Target Design

This step should produce:

- pure profiling functions in `skills/profiling.py`
- a `profile_dataset()` orchestration function that returns one structured profile dict
- a discovery workflow in `workflows/discovery.py` that loads data and produces profile output
- an `eda_analyst` agent node that:
  - reads `state["data"]` or loads from `data_path`
  - generates a profile via the profiling skill
  - prompts the LLM adapter for structured interpretation
  - returns `{"eda_insights": ...}` in the graph state

The output should be good enough to drive `route_after_eda()` and later feed the data-engineering step.

Special handling for this step:

- treat internal metadata columns such as `_true_probability` as excluded from EDA-facing feature summaries
- keep univariate AUC as a compact class-separation diagnostic for numeric features
- treat empty `high_correlation_pairs` as a valid outcome when no feature-feature correlation crosses the warning threshold

## Implementation Steps

### Step 1: Profiling Skill Surface

Implement the pure profiling functions in `skills/profiling.py`:

- `compute_distributions(df, target_col)`
- `compute_correlations(df, target_col)`
- `compute_target_analysis(df, target_col)`
- `compute_feature_target_relationships(df, target_col)`
- `detect_outliers(df, numerical_cols)`
- `profile_dataset(df, target_col)`

Keep the outputs compact and structured. Prefer summary stats over giant raw dumps.

### Step 2: Profile Output Shape

Make `profile_dataset()` return one dict with clear sections such as:

- dataset summary
- per-feature distribution summaries
- target analysis
- correlation flags
- feature-target signals
- outlier summary

If needed, tighten `EDAOutput` in `core/contracts.py` so the agent can cleanly map profile interpretation into the contract.

For Step 2, prefer a prompt-sized profile shape:

- keep the individual profiling helpers detailed for testing and local inspection
- make `profile_dataset()` expose compact summaries and top flagged items rather than every raw per-feature detail
- exclude internal metadata such as `_true_probability` from EDA-facing signals

### Step 3: Discovery Workflow

Implement `workflows/discovery.py` as the non-agentic EDA entrypoint:

- load parquet data
- call `profile_dataset()`
- optionally write a markdown EDA summary using the existing reporting style
- return structured workflow output that mirrors how other workflows return useful artifacts

Keep this workflow small and aligned with the existing workflow pattern.

### Step 4: EDA Agent

Implement `agents/eda_analyst.py`:

- read graph state inputs
- ensure data is available for profiling
- call the profiling skill
- format the profile into prompt context
- call `OpenAIAdapter.structured_output(...)`
- parse the response into the `EDAOutput` shape
- return `{"eda_insights": ..., "agent_decisions": ...}` or the smallest equivalent state update

The agent should identify:

- whether cleaning is needed
- major anomalies or skew
- high-correlation or leakage risks
- class imbalance or target issues
- top recommendations for the data engineer and ML modeler

### Step 5: Prompt Registry

Extend `config/prompts.yaml` with an `eda_analyst` prompt family:

- a system prompt defining the EDA role
- an analysis prompt that receives the compact structured profile

Keep prompts aligned to structured JSON output and downstream contract fields.

### Step 6: Validation and Import Surface

Validate:

- profiling functions import and return the expected keys
- discovery workflow imports and runs on the synthetic dataset
- EDA agent imports and can build a structured response with mocked adapter behavior
- `route_after_eda()` can consume realistic `eda_insights`

## Review and Test Gates

After each step, stop for:

1. human review of the profile shape and agent responsibilities
2. focused validation for that slice
3. checklist/log update before moving on

Recommended validation sequence:

1. unit tests for profiling summaries
2. workflow smoke test on synthetic data
3. EDA agent test with a mocked adapter response
4. router smoke test using realistic `needs_cleaning` values

## Done Criteria

This step is complete when:

- `profile_dataset(df, target_col)` returns a structured profile dict
- `workflows/discovery.py` can load data and produce a discovery output
- `agents/eda_analyst.py` produces graph-ready `eda_insights`
- `route_after_eda()` can consume those insights without shape ambiguity
- the graph has a real first runtime node instead of only a placeholder

## Resume Instructions

If work pauses, resume from:

- `project_planning/sean_step_artifacts/EDA_Analyst_Checklist.md`

Recommended resume prompt:

```text
Use agent teams for this task. Pick back up where I left off in project_planning/sean_step_artifacts/EDA_Analyst_Checklist.md and continue from the next unchecked item.
```
