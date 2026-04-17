# Multi-Agent Data Science Pipeline — Complete Build Plan

**Author:** Sean Lewis  
**Date:** April 2026  
**Status:** In progress (Steps 1–5 complete, Step 5b in progress)

This document is a comprehensive guide for building a multi-agent ML pipeline step by step. It is written so that another LLM assistant can pick up at any step and walk the human through implementation with full context of what came before, what decisions were made and why, and what lies ahead.

---

## Project Overview

### What We're Building

A multi-agent system for automated data science. LLM-powered agents (orchestrated by LangGraph + OpenAI) collaborate to generate synthetic data, prepare it, train and tune multiple ML models, review those modeling decisions for mathematical rigor, and produce a human-readable report that is then reviewed from a business stakeholder perspective. The human stays in the loop at every decision point.

### Why It Exists

This is a Hack Week learning project. The goal is to understand multi-agent architecture by building one from scratch — not to use a framework that hides the plumbing. Every piece is built incrementally so Sean can learn how the layers connect.

### Key Design Principles

1. **Layered architecture with strict import direction.** `orchestration/ → workflows/ → agents/ → skills/ → tools/`. Each layer only imports from the layer to its right. Never sideways or backwards.

2. **Skills are pure.** They take data in, return structured dicts out. No MLflow logging, no LLM calls, no file I/O. The workflow/agent layer handles all side effects.

3. **Rich structured returns for agent decision-making.** Every skill function returns a dict with enough context for an LLM agent to reason about what to do next — scores, timing, metadata, summaries in natural language.

4. **Deterministic ground truth for evaluation.** The synthetic data has known coefficients, so we can compute the Bayes-optimal probability for every row. This lets us measure how close a model gets to the theoretical best, not just how well it predicts labels.

5. **Config-driven.** Algorithm lists, metrics, tuning budgets, and S3 paths all live in `config/settings.yaml`. Code reads config; humans edit YAML.

6. **Step-by-step code output.** Each build step produces code saved to `step_code/` with filenames indicating their destination in the real project tree (e.g., `skills_modeling.py` → `src/multi_agent_ds/skills/modeling.py`).

---

## Technology Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Language | Python 3.11+ | ML ecosystem |
| Package manager | uv | Fast, deterministic |
| Agent orchestration | LangGraph | Graph-based agent workflows |
| LLM provider | OpenAI | GPT-4 for agent reasoning |
| ML framework | scikit-learn + LightGBM | Sklearn-compatible API for all models |
| Hyperparameter tuning | Optuna | Bayesian optimization, pruning |
| Synthetic data | SDV (Synthetic Data Vault) | Gaussian copula preserves correlations |
| Experiment tracking | MLflow | Nested runs, model registry, artifacts |
| Data storage | S3 (with local fallback) | Parquet files |
| UI | Streamlit | Quick dashboard for config + monitoring |
| Progress bars | tqdm | Terminal + callback-based progress |

### Dependencies (pyproject.toml)

Core: `boto3`, `langchain-openai`, `langgraph`, `lightgbm`, `mlflow`, `numpy`, `optuna`, `pandas`, `pyarrow`, `pyyaml`, `scikit-learn`, `sdv`, `streamlit`, `tqdm`

Future: `shap`, `xgboost`, `randomforest` (when those models are added)

---

## Project Structure

```
src/multi_agent_ds/
├── __init__.py
├── app.py                          # Streamlit dashboard (Step 5b)
├── adapters/
│   ├── llm/openai.py               # OpenAI API adapter (Step 6)
│   ├── llm/local.py                # Local model adapter (future)
│   ├── agent_frameworks/langgraph.py
│   └── agent_frameworks/crewai.py  # Future alternative
├── agents/
│   ├── data_engineer.py            # Step 8
│   ├── eda_analyst.py              # Step 8
│   ├── ml_modeler.py               # Step 8
│   ├── ml_reviewer.py              # Step 8 review gate
│   ├── business_stakeholder.py     # Step 10 review gate
│   └── orchestrator.py             # Step 8
├── core/
│   ├── __init__.py                 # re-exports load_settings etc.
│   ├── config.py                   # YAML loader (Step 1) ✅
│   ├── context.py                  # Shared agent state (Step 7)
│   ├── contracts.py                # Inter-agent data contracts (Step 7)
│   └── registry.py                 # Service registry (Step 7)
├── orchestration/
│   ├── graph.py                    # LangGraph state graph (Step 7)
│   ├── router.py                   # Agent routing logic (Step 7)
│   └── state.py                    # Shared state schema (Step 7)
├── skills/
│   ├── cleaning.py                 # Data cleaning (Step 4, not yet built)
│   ├── feature_engineering.py      # Feature transforms (Step 4, not yet built)
│   ├── modeling.py                 # Model training + tuning (Step 5) ✅
│   └── profiling.py                # EDA (Step 3, not yet built)
├── tools/
│   ├── data_generator.py           # SDV synthetic data (Step 2) ✅
│   ├── dataframes.py               # Pandas utilities (empty, use as needed)
│   ├── evaluation.py               # Custom metrics + test scoring (Step 5) ✅
│   ├── io.py                       # S3 upload/download (Step 1) ✅
│   └── reporting.py                # ExperimentLogger markdown reports (Step 5b) ✅
└── workflows/
    ├── discovery.py                # EDA workflow (Step 3, not yet built)
    ├── evaluation.py               # Post-training eval (Step 9)
    ├── modeling.py                 # Training workflow + MLflow (Step 5) ✅
    └── preparation.py              # Data prep workflow (Step 4, not yet built)

config/
├── settings.yaml                   # Central config
├── agents.yaml                     # Agent definitions
├── prompts.yaml                    # Prompt templates
└── workflows.yaml                  # Workflow step sequences

step_code/                          # LLM-generated code staged here before copying
├── app.py                          # → src/multi_agent_ds/app.py
├── skills_modeling.py              # → src/multi_agent_ds/skills/modeling.py
├── tools_evaluation.py             # → src/multi_agent_ds/tools/evaluation.py
├── tools_reporting.py              # → src/multi_agent_ds/tools/reporting.py
└── workflows_modeling.py           # → src/multi_agent_ds/workflows/modeling.py
```

---

## Build Steps — Detailed Walkthrough

### Step 1: Project Skeleton + Config Loader + S3 I/O ✅ COMPLETE

**What was built:**
- `pyproject.toml` with uv, project metadata, initial dependencies
- `core/config.py` — YAML config loader with helper functions: `load_settings()`, `load_agents_config()`, `load_prompts_config()`, `load_workflows_config()`, `get_active_scale()`, `build_s3_uri()`
- `tools/io.py` — S3 client with SSO fallback: `get_s3_client()`, `upload_to_s3()`, `download_from_s3()`
- `config/settings.yaml` — initial structure with data paths, S3 config, scales
- Full directory tree scaffolded with `__init__.py` files

**Key decisions:**
- Used `uv` instead of pip/poetry for speed and deterministic resolution
- Config is YAML (human-editable, agent-readable)
- S3 auth uses AWS SSO with fallback to environment credentials

**How to test:** `uv run python -c "from multi_agent_ds.core import load_settings; print(load_settings())"`

---

### Step 2: Synthetic Data Generator ✅ COMPLETE

**What was built:**
- `tools/data_generator.py` — SDV-based synthetic data generator with a deterministic ground truth function

**Key concepts — the Deterministic Data Generating Process (DGP):**

The synthetic data has a known logistic regression formula with hardcoded coefficients:

```python
COEFFICIENTS = {"age": 0.03, "income": -0.00002, "credit_score": -0.005, ...}
INTERCEPT = 1.5
NOISE_SCALE = 0.3
```

For every row, we can compute the *true* probability that `target=1` using the sigmoid of the linear combination. This creates a `_true_probability` column alongside the synthetic `target` labels. This means we can measure `mse_vs_ground_truth` — how close a model's predicted probabilities are to the Bayes-optimal. A model that achieves MSE ≈ 0 has learned the true data-generating process.

**Key functions:**
- `generate_synthetic_data(settings)` — full pipeline: build seed DataFrame → SDV metadata → GaussianCopulaSynthesizer fit → sample → optionally apply deterministic DGP → save
- `true_probability(df)` — computes exact P(target=1) from known coefficients
- `apply_ground_truth(df, seed)` — replaces SDV's stochastic target with deterministic labels from the known DGP

**How to test:** `uv run python -c "from multi_agent_ds.tools.data_generator import generate_synthetic_data; from multi_agent_ds.core import load_settings; df = generate_synthetic_data(load_settings()); print(df.shape, df.columns.tolist())"`

**Known issue (deferred):** SDV v1.32.1 shows a `FutureWarning` about `SingleTableMetadata` being deprecated. Works fine. See FUTURE_WORK.md item 1.

---

### Step 3: EDA / Profiling ⬜ NOT YET BUILT

**Planned:**
- `skills/profiling.py` — distribution summaries, correlation analysis, target rate analysis, feature-target relationships
- `workflows/discovery.py` — orchestrates profiling, generates EDA report
- Agent (`eda_analyst.py`) will call profiling skills and produce insights that feed into the data engineer and ML modeler agents

**Note:** Sean chose to skip ahead to modeling (Step 5) to get the core ML pipeline working first. EDA can be added later — it doesn't block modeling.

---

### Step 4: Data Cleaning + Feature Engineering ⬜ NOT YET BUILT

**Planned:**
- `skills/cleaning.py` — missing value imputation, outlier detection, type coercion
- `skills/feature_engineering.py` — scaling, encoding, interaction terms, binning
- `workflows/preparation.py` — full data prep pipeline

**Note:** Also skipped for now. The synthetic data from Step 2 is clean by construction. Real data would need this.

---

### Step 5: Model Training + Evaluation ✅ COMPLETE (core logic)

This is the largest and most complex step. It was built iteratively across multiple sessions.

**What was built:**

#### tools/evaluation.py (101 lines)
Custom metrics and test-set evaluation.

- `average_squared_error(y_true, y_pred)` — ASE metric (placeholder formula — Sean needs to implement the real one)
- `gini_coefficient(y_true, y_prob)` — Gini = 2*AUC - 1
- `CUSTOM_SCORERS` — dict mapping "ase" and "gini" to sklearn-compatible scorer objects
- `resolve_scorers(metric_names)` — resolves a list of metric names to scorer objects, checking custom registry first, then falling back to sklearn built-in names
- `evaluate_on_test(model, X_test, y_test, metric_names, true_prob_test)` — scores predictions against held-out test set; also computes `mse_vs_ground_truth` if deterministic DGP data is available

#### skills/modeling.py (996 lines)
The heart of the ML pipeline. Every function is designed to be called by an agent, returning rich structured dicts for decision-making.

**Algorithm Registry:**
```python
ALGORITHM_REGISTRY = {
    "lightgbm": {
        "class": LGBMClassifier,
        "encoding": "native",          # categoricals handled natively
        "search_space": _lightgbm_search_space,
        "supports_boosting_phases": True,
        "constructor_args": {"verbose": -1},   # suppress warnings
        "default_params": { ... },
    },
    "logistic_regression": {
        "class": LogisticRegression,
        "encoding": "onehot",           # needs dummy encoding
        "search_space": _logistic_regression_search_space,
        "supports_boosting_phases": False,
        "constructor_args": {"verbose": 0},
        "default_params": { ... },
    },
}
```

Adding a new algorithm = adding an entry to this dict. No other code changes required.

**Per-algorithm encoding strategy:**
- `"native"` — pass categoricals as-is (LightGBM handles them internally)
- `"onehot"` — `pd.get_dummies()` with `drop_first=True` and column alignment between train/test

This is handled by `_encode_for_algorithm(X_train, X_test, encoding, cat_cols)`.

**The 9-step agent workflow** (documented in the module docstring):

1. `prepare_data(df)` — stratified train/test split, tag categoricals, preserve `_true_probability` alignment. Returns a data dict that all subsequent functions consume.

2. `train_with_defaults(data, settings, algorithms=None)` — baseline run. Trains each algorithm with curated default params. Supports an `algorithms` override parameter so you can pass `["lightgbm"]` to run just one model. Returns dict keyed by algorithm name.

3. `find_optimal_estimators(algo_name, X_train, y_train, ...)` — CV search for best `n_estimators` at a fixed learning rate. Tests candidates in steps of 50 up to 2000. Early stops if score declines for 3 consecutive steps. **Only for boosting algorithms** — returns an error dict for non-boosting models (guarded by `supports_boosting_phases` flag).

4. `tune_algorithm(algo_name, X_train, y_train, ...)` — Optuna Bayesian optimization on tree/regularization params. **Learning rate is never in the search space** — the agent controls it explicitly. Returns full trial history, parameter importances, convergence info, score distributions. Encoding is applied once outside the Optuna objective function (not per-trial).

5. `train_with_params(algo_name, params, data)` — re-train with explicit params after tuning. Same structure as baseline results.

6. `adjust_learning_rate(algo_name, current_params, current_score, new_learning_rate, data)` — lowers learning rate, scales `n_estimators` inversely (if rate halves, estimators double). Returns comparison against previous score. **Boosting-only** — guarded.

7. `get_feature_importances(model, feature_names, algo_name)` — native importance (split-based for trees, coefficient magnitude for linear models). Fast diagnostic only. **Not for removal decisions** — use permutation importance for that.

8. `get_permutation_importances(model, X_test, y_test, ...)` — held-out permutation importance for feature removal decisions. For native-encoded models, uses sklearn's `permutation_importance` directly. For onehot-encoded models, **shuffles the original categorical column before re-encoding** so all dummy columns derived from it move together — prevents impossible feature combinations (e.g., `region_A=1` and `region_B=1` simultaneously). Returns ranked features with `safe_to_remove` flags based on configurable threshold.

9. `train_with_feature_subset(algo_name, params, data, keep_features)` — re-train on a reduced feature set. Pass pre-encoding column names; encoding is applied after subsetting. Returns same structure as `train_with_params` plus `feature_selection` metadata.

**Key fixes that were made during development:**
- `verbose=-1` crashes `LogisticRegression` → fixed with per-algorithm `constructor_args` and a `_build_model()` helper
- `tune_algorithm()` never encoded data → fixed by adding `cat_cols` parameter and encoding once outside the Optuna objective
- No guards on boosting-only functions → fixed with `supports_boosting_phases` flag; functions return error dicts for non-boosting models
- Feature selection was entirely missing → added `get_feature_importances()`, `get_permutation_importances()`, and `train_with_feature_subset()`

#### workflows/modeling.py (184 lines)
Non-agentic baseline workflow with MLflow logging.

- `run_modeling_workflow(data_path, settings, algorithms)` — loads parquet, prepares data, trains baselines, logs to MLflow with nested runs, writes ExperimentLogger markdown report
- MLflow nested runs: parent run wraps the experiment, child runs per algorithm
- Accepts `--algorithms` CLI arg via argparse for selecting models from the command line
- Supports `algorithms` parameter for programmatic override

**How to test:**
```bash
# All algorithms
uv run python -m multi_agent_ds.workflows.modeling

# Just LightGBM
uv run python -m multi_agent_ds.workflows.modeling --algorithms lightgbm

# Just logistic regression
uv run python -m multi_agent_ds.workflows.modeling --algorithms logistic_regression
```

---

### Step 5b: Observability & Reporting ✅ COMPLETE (implementation done, not yet tested)

This was originally FUTURE_WORK item 2 but Sean decided to implement it before testing the baseline workflow.

**What was built:**

#### tools/reporting.py (289 lines)
`ExperimentLogger` class — appends to `reports/experiment_log_<timestamp>.md` in real time as each phase completes. Also prints timestamped progress to the terminal.

Methods:
- `start_experiment()` — creates the file, writes header
- `log_data_summary(summary)` — train/test sizes, feature counts, target rates
- `log_baseline(algo_name, result)` — per-algorithm baseline: params, CV scores, test scores, timing
- `log_n_estimators(result)` — optimal n_estimators search result
- `log_tuning(result)` — Optuna results: trials, best score, improvement, param importances
- `log_lr_adjustment(result)` — learning rate adjustment: old→new params, score change
- `log_lr_adjustment_header(algo_name)` — phase header for lr adjustment section
- `log_permutation_importance(result)` — feature table with ranks, mean drop, std, safe-to-remove flags
- `log_feature_selection(algo_name, selection_meta, old_scores, new_scores)` — before/after score comparison table
- `finalize()` — total elapsed time, closing line

#### tqdm progress bars (added to skills/modeling.py)
- `train_with_defaults()` — bar over algorithms
- `find_optimal_estimators()` — bar over n_estimator candidates with current score in postfix
- `tune_algorithm()` — Optuna callback updating a tqdm bar per trial with best score
- `get_permutation_importances()` — bar over features (onehot path); log message for native path

#### Algorithm selection override
- `train_with_defaults(data, settings, algorithms=["lightgbm"])` — optional parameter overrides config
- `workflows/modeling.py` accepts `--algorithms` CLI arg
- Streamlit app has multiselect widget for the same purpose

#### MLflow nested runs (added to workflows/modeling.py)
- Parent run named `"experiment"` wraps the whole workflow
- Each algorithm baseline is a child run via `mlflow.start_run(nested=True)`
- Parent run logs experiment-level metadata (algorithm list, dataset shape, ground truth flag)
- Child runs log per-algorithm metrics, params, and model artifacts

#### Streamlit App — app.py (364 lines)
Dashboard for configuring and running experiments without touching YAML or the command line.

**Sidebar:**
- Data path text input
- Algorithm multiselect (pick which models to run)
- CV folds slider (2–10)
- Test size slider (0.1–0.4)
- Primary metric dropdown
- Scoring metrics multiselect
- Optuna max trials, timeout, min improvement inputs
- MLflow experiment name and tracking URI
- MLflow UI server launcher: "Start MLflow UI" button spawns `uv run mlflow ui` as a background subprocess; shows green status + "Open MLflow" link + "Stop" button when running

**Three tabs:**
1. **Run Experiment** — "Run Baseline Workflow" button with `st.status` progress indicator. Quick links to MLflow and latest experiment log.
2. **Results** — metric cards per algorithm, comparison DataFrame, expandable per-algorithm detail sections with params and scores. Only shows the current session's latest run.
3. **Experiment Log** — dropdown to select past markdown logs from `reports/`, renders them in the UI.

**Architecture note:** The app builds a settings dict in-memory from widget values and passes it directly to `run_modeling_workflow()`. No YAML file needed for Streamlit runs.

**How to run:** `uv run streamlit run src/multi_agent_ds/app.py`

---

### Step 5c: Testing the Baseline ⬜ NOT YET DONE

**What to do:**
1. Make sure all dependencies are in `pyproject.toml` and run `uv sync`
2. Make sure `config/settings.yaml` has the model section (see below)
3. Generate synthetic data if not already done
4. Run `uv run python -m multi_agent_ds.workflows.modeling`
5. Verify: MLflow runs appear, experiment log is written to `reports/`, tqdm bars show progress
6. Test single-model override: `--algorithms lightgbm`
7. Test the Streamlit app: `uv run streamlit run src/multi_agent_ds/app.py`

**Required settings.yaml model section:**
```yaml
model:
  problem_type: binary_classification
  algorithms:
    - lightgbm
    - logistic_regression
  cv_folds: 5
  test_size: 0.2
  primary_metric: gini
  scoring_metrics:
    - gini
    - ase
    - roc_auc
    - f1
  tuning:
    max_trials: 50
    timeout: 300
    min_improvement: 0.01

mlflow:
  experiment_name: multi_agent_ds
  tracking_uri: mlruns
```

**What success looks like:**
- Terminal shows tqdm progress bars during training
- MLflow UI (localhost:5000) shows a parent run with child runs per algorithm
- `reports/` contains a markdown file with data summary and baseline results
- Both algorithms produce reasonable scores (AUC > 0.5, Gini > 0)

---

### Step 5d: Demo runtime viewer

**Status:** In progress (Phase 2 of 7 from `project_planning/design_plans/2026-04-16-demo-runtime-viewer.md`) — Core recording complete, addendum for offline mode added 2026-04-16.

**What:** A record-once-replay-many demo viewer. A new `demo_recorder.py` builds a two-node `StateGraph` (`eda_raw → data_engineer → END`), streams `astream_events(version="v2")`, and writes `data/interim/demo_run_latest.json`. A new `demo_viewer.html` replays the recording as four screens (Config → Input → Runtime → Output+Summary) inside the existing `app.py` via `st.components.v1.html`. A standalone Streamlit entry point `demo_app.py` exposes the same viewer in isolation (no MLflow auto-launch, no pipeline imports, hidden Streamlit chrome) for clean screen recording.

**Scope excluded:** `ml_modeler`, `ml_reviewer`, `business_stakeholder`, `report_writer` are NOT executed live in this demo. Their drawer panes show clearly-labeled `SCRIPTED` canned content.

**Files introduced:**
- `src/multi_agent_ds/orchestration/demo_recorder.py` — 20 unit tests passing; Phase 2 complete
- `src/multi_agent_ds/demo_viewer.html` (Phase 3)
- `src/multi_agent_ds/demo_app.py` — standalone Streamlit replay entry point (2026-04-17)
- `data/interim/demo_run_latest.json` (runtime output, not checked in)

**Phase 2 addendum — offline mode for AWS SSO downtime:**
- Added `--no-upload` flag to `demo_recorder` CLI for offline demo rehearsal
- `run_preparation_workflow` accepts `local_only: bool = False` parameter
- When `local_only=True`, processed parquet is written to `data/processed/{filename}` locally instead of uploading to S3
- `preflight()` now loads `.env` before checking `OPENAI_API_KEY` (bug fix)
- 3 new test files added with 6 new tests; all 49 unit tests passing

---

### Step 6: LLM Adapter ⬜ NOT YET BUILT

**What to build:**
- `adapters/llm/openai.py` — thin wrapper around the OpenAI API for agent reasoning
- Handles: prompt formatting, response parsing, token counting, retry logic
- Should abstract away the provider so we can swap to local models later

**Design notes:**
- Agents will call the adapter to reason about skill outputs (e.g., "should I tune further or stop?")
- The adapter doesn't need to know about the ML pipeline — it just sends prompts and returns structured responses
- Use function calling / tool use format so agents can express decisions as structured actions

**Follow-up refactor (Sean's Step 7 — ✅ LANDED 2026-04-16 in commits `559f105` and `b424231`):** The single-model `OpenAIAdapter(settings)` was replaced by a two-axis `(capability, cost)` routing layer that lets every `(agent, task)` pair resolve to its own `ModelConfig`. See `project_planning/LLM_MODEL_ROUTING.md` for the design and `src/multi_agent_ds/adapters/llm/routing.py` for the resolver + `build_adapter` factory. The `OpenAIAdapter` constructor now takes `ModelConfig` directly. Phase (e) LangSmith metadata propagation is the only remaining piece, deferred until `langsmith` is added as a project dependency.

---

### Step 7: LangGraph Orchestration ⬜ NOT YET BUILT

**What to build:**

#### orchestration/state.py
Shared state schema passed between graph nodes. Should include:
- Current dataset reference
- Results from each phase
- Agent decisions and reasoning
- Config/settings reference

#### orchestration/graph.py
LangGraph state graph defining:
- Nodes: each agent is a node
- Edges: transitions between agents
- Conditional routing based on state

#### orchestration/router.py
Routing logic for conditional edges. Examples:
- After EDA agent → if data is clean, skip to modeling; if dirty, route to data engineer
- After modeling agent → if improvement threshold met, stop; else continue tuning

#### core/context.py
Shared context object that agents read from and write to. Different from LangGraph state — this is the domain-specific payload.

#### core/contracts.py
Data contracts defining what each agent must provide in its output for downstream agents to consume.

---

### Step 8: Agent Implementations ⬜ NOT YET BUILT

**What to build:**

Each agent file in `agents/` follows the same pattern:
1. Receive context (previous agent outputs + shared state)
2. Construct a prompt from templates in `config/prompts.yaml`
3. Call the LLM adapter to reason about the context
4. Parse the LLM's decision
5. Call the appropriate skill function(s)
6. Return structured results to the graph

#### agents/eda_analyst.py
- Calls `skills/profiling.py` to analyze the dataset
- Produces insights: feature distributions, correlations, anomalies, target characteristics
- Feeds context to data engineer and ML modeler

#### agents/data_engineer.py
- Decides what cleaning and feature engineering to apply based on EDA insights
- Calls `skills/cleaning.py` and `skills/feature_engineering.py`
- Outputs cleaned/engineered dataset

#### agents/ml_modeler.py
This is the most complex agent. It orchestrates the phased tuning workflow:

1. Call `train_with_defaults()` → review baseline scores
2. For each boosting algorithm: call `find_optimal_estimators()` → decide on lr/n_est pair
3. Call `tune_algorithm()` → review Optuna results → decide if tuning helped
4. Call `adjust_learning_rate()` → try lower rates → keep best
5. Call `get_permutation_importances()` → identify removable features
6. Call `train_with_feature_subset()` → compare with/without features → decide final model
7. Compare all algorithms → recommend best

Each step involves: run the skill → send results to LLM → parse decision → take next action.

#### agents/orchestrator.py
Top-level meta-agent that decides the overall workflow:
- Which agents to invoke and in what order
- Whether to loop (e.g., re-do feature engineering after seeing model results)
- When to stop and produce final output

---

### Step 9: Evaluation Pipeline ⬜ NOT YET BUILT

**What to build:**
- `workflows/evaluation.py` — post-training evaluation workflow
- Bayes-optimal comparison report (using `_true_probability`)
- Model selection summary with justification
- Diagnostic plots logged as MLflow artifacts
- SHAP analysis for the winning model (see Deferred Items)

---

### Step 10: Final Report Generation ⬜ NOT YET BUILT

**What to build:**
- Agent-generated summary of the entire experiment
- Intended audience: non-technical stakeholders
- Includes: what data was used, what models were tried, which won and why, key features, confidence levels
- Output format: markdown report + MLflow experiment link

---

## Config Reference — settings.yaml

The full `config/settings.yaml` structure needed for the current implementation:

```yaml
# Data generation
data:
  scales:
    small:
      n_rows: 1000
    medium:
      n_rows: 10000
    large:
      n_rows: 100000
  active_scale: medium
  features:
    numerical:
      - name: age
        type: numerical
        mean: 45
        std: 15
      - name: income
        type: numerical
        mean: 65000
        std: 25000
      # ... more features
    categorical:
      - name: region
        type: categorical
        values: [Northeast, Southeast, Midwest, West, Southwest]
      # ... more features
  target:
    name: target
    type: boolean
    deterministic: true    # Use known DGP
  seed: 42

# S3 storage
s3:
  bucket: your-bucket-name
  paths:
    raw: data/raw/
    processed: data/processed/

# Model training
model:
  problem_type: binary_classification
  algorithms:
    - lightgbm
    - logistic_regression
  cv_folds: 5
  test_size: 0.2
  primary_metric: gini
  scoring_metrics:
    - gini
    - ase
    - roc_auc
    - f1
  tuning:
    max_trials: 50
    timeout: 300
    min_improvement: 0.01

# MLflow
mlflow:
  experiment_name: multi_agent_ds
  tracking_uri: mlruns

# LLM (for agents, Step 6+)
llm:
  provider: openai
  model: gpt-4
  temperature: 0.1
  max_tokens: 4096
```

---

## Deferred Items (FUTURE_WORK.md)

These are items we explicitly decided to defer. Each has a "when to do it" trigger.

### 1. SDV Metadata API Migration

**What:** Replace `SingleTableMetadata` with the new `Metadata` class in `tools/data_generator.py`.

**When:** When SDV drops `SingleTableMetadata` support (currently works on v1.32.1).

**Changes:** `SingleTableMetadata()` → `Metadata()`, `detect_from_dataframe(seed_df)` → `detect_from_dataframe(data=seed_df, table_name="dataset")`, update `update_column()` signatures.

**Risk if ignored:** Future SDV update will break the data generator.

### 2. SHAP Integration for Model Explainability

**What:** Add `get_shap_importances()` to `skills/modeling.py` using `shap.TreeExplainer` for tree models.

**When:** After tuning and feature selection workflow is tested and working (after Step 5c).

**What it provides:**
- Global ranking via mean absolute SHAP values
- Per-feature directional impact (positive/negative)
- Raw SHAP matrix for per-sample explanations
- Beeswarm and waterfall plots logged as MLflow artifacts

**Why not permutation importance for this:** SHAP is for *explanation and communication* (tells stakeholders *how* features affect predictions). Permutation importance is for *feature removal decisions* (tells the modeler *whether* removing a feature hurts). We already have permutation importance. SHAP adds the explainability layer.

**Design reference:** The article "You Are Probably Reading XGBoost Feature Importance Wrong" (Iakubovskyi, 2026) covers the three types: native gain (fast diagnostic, biased toward high-cardinality), permutation importance (model-agnostic, held-out), and SHAP (theoretically sound, satisfies efficiency/symmetry/dummy/additivity axioms).

### 3. Streamlit App Enhancements

**What:** Beef up the Streamlit dashboard with deeper observability.

**When:** After the baseline workflow is tested and the basic app is working.

**Planned additions:**
- Experiment history browser (query MLflow via `mlflow.search_runs()`, render as DataFrame with filters)
- Cross-experiment comparison view (select two runs, diff metrics/params)
- Live training output streaming (replace spinner with `st.empty()` updated per phase)
- Real-time tqdm integration (Streamlit `st.progress()` instead of terminal tqdm)
- Agent decision log viewer (for Step 8+, show agent reasoning in a chat-style interface)

### 4. Parallel Algorithm Training

**What:** Run multiple algorithms concurrently using `ProcessPoolExecutor` in `train_with_defaults()`.

**When:** When 4+ algorithms are configured and sequential training becomes a bottleneck.

**Design note:** Each algorithm is independent (no shared state), so parallelism is straightforward. The tqdm bar would need to become a shared progress counter.

### 5. ASE Metric Formula

**What:** Replace the placeholder `average_squared_error` in `tools/evaluation.py` with the real ASE formula.

**When:** Sean needs to provide the actual formula. Currently it's just MSE as a placeholder.

### 6. Additional Algorithms

**What:** Add more entries to `ALGORITHM_REGISTRY` in `skills/modeling.py`.

**When:** After baseline workflow is tested with LightGBM + Logistic Regression.

**Candidates:** XGBoost, Random Forest, CatBoost, Elastic Net. Each just needs a registry entry with class, encoding, search space, default params, and constructor args.

---

## Key Design Decisions and Rationale

### Why learning rate is never in the Optuna search space

The agent controls learning rate explicitly through `adjust_learning_rate()`. Optuna tunes tree structure and regularization params (max_depth, num_leaves, subsample, reg_alpha, reg_lambda). This separation exists because learning rate interacts with n_estimators in a way that's better handled by a deliberate schedule (lower rate → proportionally more estimators) than by random search.

### Why permutation importance shuffles original columns for onehot models

Standard sklearn `permutation_importance` shuffles individual columns. For onehot-encoded features, this creates impossible combinations (e.g., `region_Northeast=1` and `region_Southeast=1` simultaneously). The fix: shuffle the original categorical column's values, then re-encode. This means all dummy columns derived from one original feature move together coherently.

### Why skills don't log to MLflow

Skills are pure domain logic. MLflow logging is a side effect that belongs in the workflow/agent layer. This keeps skills testable (no need to mock MLflow), reusable (can be called from notebooks, scripts, or agents), and simple (take data in, return dict out).

### Why the app builds settings in-memory instead of writing YAML

The `run_modeling_workflow()` function already accepts `settings: dict | None`. The Streamlit app constructs this dict from widget values and passes it directly. No file I/O, no YAML serialization, no risk of stale config files. The YAML file is still the source of truth for CLI runs.

### Why _build_model() exists as a separate helper

Different algorithms need different constructor arguments (`verbose=-1` for LightGBM, `verbose=0` for LogisticRegression). Rather than sprinkling if/else logic everywhere a model is instantiated, `_build_model()` centralizes it: look up `constructor_args` from the registry, merge with user params, instantiate.

---

## How to Continue This Build

If you're an LLM assistant picking this up:

1. **Read this document first.** It has the full context.
2. **Read ARCHITECTURE.md** for the layer rules and file placement guide.
3. **Read FUTURE_WORK.md** for deferred items.
4. **Check `step_code/`** for the latest versions of all implemented files.
5. **Sean works incrementally.** He wants to understand each piece before moving on. Don't rush ahead.
6. **Sean stages code in `step_code/`** with descriptive filenames, then copies to the real project tree himself.
7. **Show complete files** when making changes — Sean prefers seeing the whole thing rather than diffs.
8. **The next step is 5c** — testing the baseline workflow. After that, Sean may want to enhance the Streamlit app or move to Step 6 (LLM adapter).
9. **All code is optimized for agent consumption** — functions return rich dicts with summaries, timing, and metadata so an LLM agent can reason about what to do next.
10. **Sean values knowing *why* decisions were made.** Explain trade-offs, not just implementations.
