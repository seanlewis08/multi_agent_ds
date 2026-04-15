# Jonathan's Build Plan — Steps 6–10

**Author:** Sean Lewis  
**Date:** April 15, 2026  
**Scope:** Steps 6–10 of BUILD_PLAN.md (git/PR tooling → evaluation → ML modeler → orchestrator)  
**Dependencies completed:** Steps 1–5b (config, data gen, modeling skills, workflows, artifacts, Streamlit app, MLflow integration)

---

## Overview

Jonathan owns the **git/PR infrastructure** (both runtime experiment PRs and development PRs), the **downstream pipeline** (evaluation + SHAP), his own **ML modeler agent** variant, and the **orchestrator agent** that ties the full pipeline together.

Sean owns the **shared infrastructure** (LLM adapter, LangGraph skeleton) and the **upstream pipeline** (EDA → data engineering → ML modeler → report). See `Sean_Plan.md`.

The modeling step is the divergence point — each person builds their own ML modeler agent with different strategies, both calling the same `skills/modeling.py` functions.

---

## What's Already Built

Before starting, confirm these are working:

| Layer | File | Status |
|-------|------|--------|
| `core/config.py` | YAML loader, `load_settings()`, `build_s3_uri()` | ✅ |
| `tools/io.py` | S3 upload/download, `write_json()` | ✅ |
| `tools/data_generator.py` | SDV synthetic data + deterministic DGP | ✅ |
| `tools/evaluation.py` | Custom scorers, `evaluate_on_test()` (returns scores + y_pred + y_prob) | ✅ |
| `tools/artifacts.py` | 7 diagnostic generators (ROC, confusion matrix, calibration, feature importance, prob dist, classification report, ground truth comparison) | ✅ |
| `tools/reporting.py` | `ExperimentLogger` — markdown reports + terminal progress | ✅ |
| `skills/modeling.py` | 9 skill functions, `ALGORITHM_REGISTRY` (lightgbm, logistic_regression), search spaces | ✅ |
| `workflows/modeling.py` | Non-agentic baseline workflow + MLflow nested runs + artifact export to `mlruns/output/` | ✅ |
| `app.py` | Streamlit dashboard (sidebar config, run button, results, log viewer, MLflow UI management) | ✅ |
| `config/settings.yaml` | Full config (data, S3, model, MLflow, LLM) | ✅ |

---

## What Sean Builds First (Dependencies for Jonathan)

Jonathan can start on Steps 1–2 immediately (git tool + evaluation pipeline — no LLM dependency). Steps 3–5 require Sean's shared infrastructure:

| Sean's Step | What Jonathan Needs From It | When |
|-------------|----------------------------|------|
| Sean Step 1: LLM Adapter (`adapters/llm/openai.py`) | Import `OpenAIAdapter` for agent LLM calls | Before Jonathan Steps 3–5 |
| Sean Step 2: LangGraph Skeleton (`orchestration/state.py`, `graph.py`, `router.py`) | `PipelineState` TypedDict, node registration pattern | Before Jonathan Step 5 |
| Sean Step 2: Contracts (`core/contracts.py`) | Schema base classes for agent outputs | Before Jonathan Steps 3–5 |

---

## Step 1: Git Tool + Experiment PR Agent

**BUILD_PLAN reference:** New addition (not in original Steps 6–10)  
**New file:** `tools/git.py`  
**New file:** `agents/reviewer.py`  
**Config to edit:** `config/settings.yaml` (add git section)

### Concept: Two PR Layers

1. **Runtime experiment PR agent** (`agents/reviewer.py` + `tools/git.py`) — after the multi-agent system completes an experiment cycle, this agent commits experiment artifacts and opens a PR documenting the full cycle.
2. **Development PR agent** (`development_agents/skills/pr-workflow.md`) — instructions for coding agents (human or LLM) to follow when committing code changes for BUILD_PLAN steps.

### 1a. `tools/git.py` — Stateless Git Utilities

Pure subprocess wrappers around git CLI and GitHub API. No LLM calls, no business logic. Follows the same pattern as `tools/io.py` for S3.

```python
"""Git and GitHub utilities for experiment and development PRs."""

import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_current_branch() -> str:
    """Return the name of the current git branch."""

def create_branch(branch_name: str, from_branch: str = "main") -> str:
    """Create and checkout a new branch. Returns branch name."""

def stage_files(paths: list[str | Path]) -> list[str]:
    """Stage specific files. Returns list of staged paths."""

def stage_all_changes() -> list[str]:
    """Stage all modified/new/deleted files. Returns list of staged paths."""

def commit(message: str) -> str:
    """Create a commit with the given message. Returns commit hash."""

def push_branch(branch_name: str, force: bool = False) -> None:
    """Push the current branch to origin."""

def get_diff_summary(base: str = "main") -> str:
    """Return `git diff --stat` summary against base branch."""

def get_changed_files(base: str = "main") -> list[str]:
    """Return list of files changed vs base branch."""

def create_pull_request(
    title: str,
    body: str,
    base: str = "main",
    head: str | None = None,
    draft: bool = False,
) -> dict:
    """Create a GitHub PR via `gh` CLI. Returns PR URL and number.

    Uses `gh pr create` — requires `gh` CLI installed and authenticated
    via `gh auth login`. No PyGithub dependency needed.
    """

def get_open_prs(base: str = "main") -> list[dict]:
    """List open PRs against the base branch via `gh pr list`."""
```

**Design decisions:**
- **Use `gh` CLI** for GitHub API calls instead of adding `PyGithub` as a dependency. `gh` handles auth via `gh auth login` and is already standard on most dev machines.
- **Subprocess-based** — all git operations via `subprocess.run()` with error handling. No gitpython dependency.
- **Stateless** — each function is a standalone utility. The agent layer (reviewer) decides *what* to commit and *when*.

### 1b. `agents/reviewer.py` — Experiment PR Agent

This agent runs as the second-to-last node in the LangGraph graph (after evaluation, before report). It reads the full experiment context from the orchestration state and creates a PR documenting the experiment cycle.

```python
def reviewer_node(state: PipelineState) -> dict:
    """LangGraph node: create a PR documenting the experiment cycle."""
    # 1. Gather experiment context from state:
    #    - eda_insights: what was discovered about the data
    #    - prep_result: what cleaning/engineering was applied
    #    - modeling_results: which algorithms, what scores, what params
    #    - evaluation_result: which model won and why
    #    - agent_decisions: trace of all LLM reasoning at each phase
    #    - config snapshot: current settings.yaml values used

    # 2. Call LLM to generate PR description:
    #    "Summarize this experiment cycle as a PR description.
    #     Include: what was tested, why, results, key decisions, config changes."

    # 3. Determine branch name:
    #    e.g., "experiment/baseline-lgbm-lr-2026-04-15"

    # 4. Create branch via tools/git.create_branch()

    # 5. Stage experiment files:
    #    - config/settings.yaml (snapshot of config used)
    #    - reports/experiment_log_<timestamp>.md
    #    - Any YAML config changes the agent made during the run

    # 6. Commit with detailed message:
    #    "[experiment] Baseline: lightgbm, logistic_regression
    #     Gini: 0.38 (lgbm), 0.35 (lr) | Best: lightgbm
    #     See PR description for full agent reasoning trace."

    # 7. Push and create PR via tools/git.create_pull_request()

    # 8. Return {"pr_url": url, "pr_number": number, "branch": branch_name}
```

### 1c. Config Addition — `config/settings.yaml`

Add a `git` section to the existing settings:

```yaml
# Git & GitHub Configuration
git:
  default_base_branch: main
  experiment_branch_prefix: experiment/
  development_branch_prefix: build/
  auto_push: true               # Push branches automatically
  auto_pr: true                 # Create PRs automatically

github:
  repo: ""                      # e.g., "owner/multi_agent_ds" — set in .env or here
```

### 1d. Development PR Agent — `development_agents/skills/pr-workflow.md`

Instructions for coding agents to follow when committing BUILD_PLAN step changes:

```markdown
# Skill: PR Workflow

Use this skill after completing a BUILD_PLAN step.

## Branch Naming
- Format: `build/step-N-short-description`
- Example: `build/step-6-llm-adapter`

## Commit Message Format
- First line: `[step N] Short description`
- Body: what was built, which files were changed, what was tested

## PR Description
- Reference the BUILD_PLAN step number
- List files changed
- Describe what was built and why
- Note what's next (the following step)

## Workflow
1. Create branch from main: `git checkout -b build/step-N-description`
2. Make changes
3. Stage changed files only (not generated files)
4. Commit with formatted message
5. Push and create PR
6. Request review
```

### 1e. Update `development_agents/team.md`

Add a `pr_manager` agent role:

```markdown
### `pr_manager`

- Runs after `efficiency_reviewer` confirms the change is complete.
- Creates a branch following the naming convention in `skills/pr-workflow.md`.
- Writes a commit message referencing the BUILD_PLAN step.
- Opens a PR with a description linking to the relevant planning doc section.
- Does not merge — waits for human review.
```

### Done When

- `tools/git.py` functions work (create branch, commit, push, create PR via `gh`)
- `agents/reviewer.py` can create a PR documenting an experiment
- Development agents have PR workflow instructions
- Config has git/GitHub settings

---

## Step 2: Evaluation Pipeline

**BUILD_PLAN reference:** Step 9  
**Files to edit:** `workflows/evaluation.py` (currently placeholder)  
**No LLM dependency** — this is pure Python + sklearn + shap. Can start immediately.

### What to Build

Post-training evaluation workflow that compares models, validates against ground truth, and produces SHAP analysis.

### Implementation Details

**`workflows/evaluation.py`:**

```python
def run_evaluation_workflow(
    results: dict,
    data: dict,
    settings: dict,
) -> dict:
    """Post-training evaluation: compare models, ground truth validation, SHAP.

    Args:
        results: Output of train_with_defaults() — dict keyed by algorithm name
        data: Output of prepare_data() — contains X_test, y_test, true_prob_test
        settings: Pipeline config

    Returns:
        Evaluation summary dict with rankings, ground truth comparison, SHAP results
    """

    # 1. Model Ranking
    #    - Rank all trained models by primary_metric (from settings)
    #    - Compute ranking by each scoring metric
    #    - Identify winner and runner-up

    # 2. Bayes-Optimal Comparison (if deterministic DGP data)
    #    - Use data["true_prob_test"] (the ground truth probability)
    #    - Compute MSE vs ground truth for each model's predicted probabilities
    #    - Compare against COEFFICIENTS from tools/data_generator.py
    #    - Reference Ground_Truth_Feature_Importance.md for expected rankings

    # 3. SHAP Analysis (for top model)
    #    - shap.TreeExplainer for LightGBM
    #    - shap.LinearExplainer for logistic regression
    #    - Compute SHAP values on test set
    #    - Global ranking: mean absolute SHAP values
    #    - Per-feature direction (positive/negative impact)
    #    - Validate feature importance ranking against ground truth doc

    # 4. SHAP Artifacts
    #    - Generate beeswarm plot → PNG bytes
    #    - Generate waterfall plot (single sample) → PNG bytes
    #    - Generate SHAP summary JSON for LLM agents
    #    - Log all as MLflow artifacts (follows tools/artifacts.py pattern)

    # 5. Model Selection Summary
    #    - Winner: algorithm name, key metrics, reasoning
    #    - Trade-offs: if runner-up is close, explain why winner was chosen
    #    - Caveats: overfitting risk, metric limitations

    return {
        "rankings": [...],
        "winner": {"algorithm": "...", "scores": {...}, "reasoning": "..."},
        "ground_truth_comparison": {...},
        "shap_results": {...},
        "shap_artifacts": {"beeswarm.png": bytes, "summary.json": dict},
    }
```

### Ground Truth Validation

The synthetic dataset has known coefficients (see `tools/data_generator.py` and `project_planning/Ground_Truth_Feature_Importance.md`). The evaluation workflow should:

1. Compute each model's predicted probabilities on the test set
2. Compare against `data["true_prob_test"]` via MSE
3. Rank models by how close they get to the Bayes-optimal predictions
4. Compare model feature importances against the known coefficient ranking:
   - Top tier expected: `credit_score`, `num_prior_claims`, `annual_income`
   - Lowest tier expected: `state`, `coverage_tier`, `marital_status`, `vehicle_type`, `education_level`

### SHAP Integration

`shap` is already in `pyproject.toml`. Use the correct explainer per algorithm:

```python
import shap

def compute_shap_values(model, X_test, algo_name):
    if algo_name == "lightgbm":
        explainer = shap.TreeExplainer(model)
    elif algo_name == "logistic_regression":
        explainer = shap.LinearExplainer(model, X_test)
    else:
        explainer = shap.Explainer(model, X_test)

    shap_values = explainer.shap_values(X_test)
    return shap_values
```

### Done When

- `run_evaluation_workflow()` produces a complete evaluation dict
- SHAP beeswarm and waterfall plots are generated
- Ground truth comparison validates feature importance rankings
- Results can be logged to MLflow as artifacts

---

## Step 3: ML Modeler Agent (Jonathan's Version)

**BUILD_PLAN reference:** Step 8 (ML modeler)  
**Files to edit:** `agents/ml_modeler.py` (currently placeholder — coordinate with Sean)  
**Config to edit:** `config/prompts.yaml`  
**Depends on:** Sean's LLM adapter (Step 1) and LangGraph skeleton (Step 2)

### What to Build

Jonathan's ML modeler agent — a different strategy from Sean's version. Both call the same `skills/modeling.py` functions but make different decisions about tuning, stopping, and feature selection.

### Possible Divergence Points

Jonathan's agent could differ from Sean's in any of these ways:

1. **Algorithm selection** — add XGBoost to `ALGORITHM_REGISTRY` (`xgboost` already in `pyproject.toml`):
   ```python
   # Add to skills/modeling.py ALGORITHM_REGISTRY
   "xgboost": {
       "class": XGBClassifier,
       "encoding": "native",
       "search_space": _xgboost_search_space,
       "supports_boosting_phases": True,
       "constructor_args": {"verbosity": 0, "use_label_encoder": False},
       "default_params": {
           "n_estimators": 500,
           "max_depth": 6,
           "learning_rate": 0.01,
           "subsample": 0.8,
           "colsample_bytree": 0.8,
       },
   }
   ```

2. **More aggressive early stopping** — stop tuning sooner if improvement is marginal
3. **Different feature selection criteria** — lower threshold for dropping features
4. **Different learning rate schedule** — try more aggressive rate reductions
5. **Different LLM reasoning prompts** — ask the LLM different questions between phases
6. **Skip phases** — e.g., skip `find_optimal_estimators()` and go straight to Optuna

### Implementation Pattern

Same pattern as Sean's agent (run skill → LLM reasons → structured decision → next action), but with different system prompt and decision thresholds:

```python
def ml_modeler_node(state: PipelineState) -> dict:
    """LangGraph node: Jonathan's modeling strategy."""
    # Same skill function calls, different LLM reasoning strategy
    # Key difference: Jonathan's prompts and stopping criteria
```

### Prompts (`config/prompts.yaml`)

```yaml
jonathan_ml_modeler:
  system: |
    You are an ML modeler agent focused on efficient model selection.
    You prefer early stopping over exhaustive tuning. If the baseline
    score is already strong (gini > 0.5), focus on feature selection
    rather than hyperparameter tuning. Always consider the cost-benefit
    of additional tuning iterations.
  baseline_review: |
    Baseline results: {results_json}
    Should we tune, or is the baseline good enough? Consider the gap
    between algorithms and the absolute score level.
```

### Coordination with Sean

- **Both agents need to coexist.** They should be registered as separate nodes in the LangGraph graph, with the orchestrator (Step 5) or config deciding which one runs.
- **`skills/modeling.py` is shared.** If adding XGBoost, coordinate with Sean to avoid merge conflicts. The skill functions themselves don't change — only `ALGORITHM_REGISTRY` gets a new entry.
- **Prompt key prefixes.** Jonathan uses `jonathan_ml_modeler_*` in `prompts.yaml`.

### Done When

- Jonathan's ML modeler agent runs the phased workflow with his own strategy
- Registered as an alternative node in the LangGraph graph
- Config can select which modeler to use

---

## Step 4: Orchestrator Agent

**BUILD_PLAN reference:** Step 8 (orchestrator)  
**Files to edit:** `agents/orchestrator.py` (currently placeholder)  
**Config to edit:** `config/agents.yaml` (currently placeholder), `config/workflows.yaml` (currently placeholder)  
**Depends on:** Sean's LLM adapter + LangGraph skeleton, all other agents

### What to Build

The meta-agent that controls the entire pipeline flow. It decides which agents to invoke, in what order, whether to loop, and when to stop.

### Implementation

**`agents/orchestrator.py`:**

```python
def orchestrator_node(state: PipelineState) -> dict:
    """Top-level meta-agent: decides the overall workflow."""

    # 1. Read state and config
    # 2. Decide workflow based on data source and goals:
    #    - Synthetic data → skip heavy cleaning, go to modeling
    #    - Existing data → full EDA → cleaning → engineering → modeling
    # 3. Decide which ML modeler to use (Sean's or Jonathan's)
    # 4. After modeling → always run evaluation
    # 5. After evaluation → run reviewer (experiment PR)
    # 6. After reviewer → run report generation
    # 7. Decide whether to loop:
    #    - If score improved significantly, stop
    #    - If score is flat, try different feature engineering
    #    - Max iterations from config (settings.model.max_iterations = 5)
```

**`config/agents.yaml` — Agent Definitions:**

```yaml
agents:
  eda_analyst:
    role: "Data profiling and exploratory analysis"
    skills: [profiling]
    tools: []
    max_retries: 2

  data_engineer:
    role: "Data cleaning and feature engineering"
    skills: [cleaning, feature_engineering]
    tools: []
    max_retries: 2

  ml_modeler:
    role: "Model training, tuning, and selection"
    skills: [modeling]
    tools: [evaluation, artifacts]
    active_variant: sean          # or "jonathan"
    max_retries: 3

  reviewer:
    role: "Experiment documentation and PR creation"
    skills: []
    tools: [git]
    auto_pr: true

  orchestrator:
    role: "Pipeline orchestration and workflow control"
    skills: []
    tools: []
    max_iterations: 5
```

**`config/workflows.yaml` — Workflow Step Sequences:**

```yaml
workflows:
  full_pipeline:
    description: "Complete EDA → prep → model → eval → PR → report pipeline"
    steps:
      - agent: eda_analyst
        required: true
      - agent: data_engineer
        required: false           # Skipped if EDA says data is clean
        condition: "eda_insights.needs_cleaning"
      - agent: ml_modeler
        required: true
      - agent: evaluation
        required: true
      - agent: reviewer
        required: true
      - agent: report
        required: true
    loop:
      max_iterations: 5
      loop_from: ml_modeler       # Re-enter at modeling if looping
      stop_condition: "evaluation_result.improvement < 0.01"

  baseline_only:
    description: "Quick baseline — no tuning, no EDA"
    steps:
      - agent: ml_modeler
        required: true
      - agent: evaluation
        required: true
      - agent: reviewer
        required: true
```

### Done When

- Orchestrator agent controls the full pipeline flow
- `config/agents.yaml` defines all agent roles
- `config/workflows.yaml` defines step sequences
- End-to-end test: orchestrator → EDA → data engineer → ML modeler → evaluation → reviewer → report

---

## Step 5: Integration Testing + Graph Wiring

**No new files.** This step validates the full pipeline.

### What to Test

1. **End-to-end graph execution:**
   ```python
   from multi_agent_ds.orchestration.graph import build_graph
   graph = build_graph().compile()
   result = graph.invoke({
       "data_path": "data/raw/synthetic_dataset.parquet",
       "settings": load_settings(),
   })
   ```

2. **Verify agent contract compliance:**
   - Each agent's output matches its `core/contracts.py` schema
   - State flows correctly between nodes

3. **Verify experiment PR creation:**
   - Branch created with correct naming convention
   - PR body contains experiment summary, agent reasoning trace, config diff
   - Changed files (config YAML, reports) are committed

4. **Verify MLflow integration:**
   - Nested runs still work with agent-driven workflow
   - Artifacts logged for each phase

5. **Compare Sean's vs Jonathan's modeler:**
   - Run both on the same dataset
   - Evaluation pipeline compares their outputs
   - PR documents the comparison

### Done When

- Full pipeline runs end-to-end: orchestrator → EDA → data engineer → ML modeler → evaluation → reviewer (PR) → report
- Experiment PR is created with full cycle documentation
- Both ML modeler variants can be selected via config

---

## How the Experiment PR Flow Works End-to-End

```
Human clicks "Run" in Streamlit (or CLI)
  │
  ▼
Orchestrator decides workflow
  │
  ▼
EDA Agent profiles data
  → Writes insights to state
  │
  ▼
Data Engineer cleans/engineers (if needed)
  → May modify config YAML (e.g., add engineered features)
  → Writes prep_result to state
  │
  ▼
ML Modeler runs phased training
  → Each phase: skill call → LLM reasoning → decision
  → Config changes saved (e.g., tuned params written to YAML)
  → All decisions logged to agent_decisions in state
  │
  ▼
Evaluation pipeline compares models
  → Ground truth validation
  → SHAP analysis
  → Winner selected with justification
  │
  ▼
Reviewer Agent creates PR:
  ┌─────────────────────────────────────────────────────┐
  │ Branch: experiment/baseline-lgbm-lr-2026-04-15      │
  │                                                     │
  │ PR Title: [experiment] Baseline: lightgbm, lr       │
  │                                                     │
  │ PR Body:                                            │
  │   ## Experiment Summary                             │
  │   - Dataset: 500,000 rows, 17 features              │
  │   - Target rate: 27%                                │
  │   - Algorithms: lightgbm, logistic_regression       │
  │                                                     │
  │   ## Results                                        │
  │   | Algorithm | Gini  | AUC   | Time  |             │
  │   |-----------|-------|-------|-------|             │
  │   | lightgbm  | 0.381 | 0.691 | 27.9s |             │
  │   | log_reg   | 0.352 | 0.676 | 3.2s  |             │
  │                                                     │
  │   ## Agent Reasoning Trace                          │
  │   - Phase 1 (baseline): Both algorithms trained...  │
  │   - Phase 2 (tuning decision): LLM decided to...   │
  │   - Phase 3 (feature selection): Dropped 2 features │
  │                                                     │
  │   ## Config Changes                                 │
  │   - model.algorithms: [lightgbm, logistic_reg]      │
  │   - model.primary_metric: gini                      │
  │   - model.cv_folds: 5                               │
  │                                                     │
  │   ## Files Changed                                  │
  │   - config/settings.yaml (config snapshot)           │
  │   - reports/experiment_log_2026-04-15_070704.md       │
  │                                                     │
  │   📊 MLflow: http://localhost:5000                    │
  └─────────────────────────────────────────────────────┘
  │
  ▼
Report Agent generates stakeholder summary
  │
  ▼
Human reviews PR → approves/requests changes
```

---

## Files to Create or Edit (Summary)

| File | Action | Step |
|------|--------|------|
| `tools/git.py` | **Create new** | 1 |
| `agents/reviewer.py` | **Create new** | 1 |
| `config/settings.yaml` | Add `git` and `github` sections | 1 |
| `development_agents/skills/pr-workflow.md` | **Create new** | 1 |
| `development_agents/team.md` | Add `pr_manager` role | 1 |
| `development_agents/checklist.md` | Add post-edit PR section | 1 |
| `workflows/evaluation.py` | Implement (currently placeholder) | 2 |
| `agents/ml_modeler.py` | Implement — Jonathan's version (currently placeholder, coordinate with Sean) | 3 |
| `skills/modeling.py` | Add XGBoost to `ALGORITHM_REGISTRY` (if desired) | 3 |
| `agents/orchestrator.py` | Implement (currently placeholder) | 4 |
| `config/agents.yaml` | Populate with agent definitions | 4 |
| `config/workflows.yaml` | Populate with workflow step sequences | 4 |
| `config/prompts.yaml` | Add Jonathan's prompt templates | 3, 4 |

---

## Coordination with Sean

| Concern | Owner | Coordination Needed |
|---------|-------|---------------------|
| LLM adapter | Sean builds | Jonathan imports `OpenAIAdapter` |
| LangGraph skeleton | Sean builds | Jonathan registers reviewer + orchestrator nodes |
| `skills/modeling.py` | Shared | If adding XGBoost, tell Sean before editing `ALGORITHM_REGISTRY` |
| `config/prompts.yaml` | Both edit | Jonathan prefixes with `jonathan_ml_modeler_`, `orchestrator_`, `reviewer_` |
| `tools/git.py` | Jonathan builds | Sean's report node runs before reviewer — no dependency on git tool |
| `config/agents.yaml` | Jonathan populates | Sean may add EDA/data_engineer entries |
| `config/workflows.yaml` | Jonathan populates | Sean may reference for graph wiring |

### Sequencing

1. **Jonathan starts Steps 1–2 immediately** (git tool + evaluation pipeline) — no LLM dependency.
2. **Sean commits adapter + orchestration skeleton** — Jonathan picks these up for Steps 3–5.
3. **Steps 3–5 proceed after shared infrastructure is ready.**

