# Architecture Reference — multi_agent_ds

How every directory and file is used. Consult this before placing new functions.

---

## Layer Overview

```
orchestration/  →  workflows/  →  agents/  →  skills/  →  tools/
  (graph)         (sequences)    (decisions)   (logic)    (utilities)
```

Each layer only imports from the layer to its right. Never sideways or backwards.

---

## tools/ — Stateless Utilities

Low-level, reusable functions. No business logic. No awareness of agents, workflows, or config structure beyond what's passed in.

### tools/io.py
S3 upload/download and auth handling.
- `get_s3_client(settings)` — creates boto3 client with SSO fallback
- `upload_to_s3(local_path, path_key, filename, settings)` — push file to S3
- `download_from_s3(path_key, filename, local_dir, settings)` — pull file from S3

### tools/evaluation.py
Custom scoring metrics and test-set evaluation.
- `average_squared_error(y_true, y_pred)` — ASE metric (TODO: replace with real formula)
- `gini_coefficient(y_true, y_prob)` — Gini = 2*AUC - 1
- `CUSTOM_SCORERS` — registry mapping string names to sklearn scorer objects
- `resolve_scorers(metric_names)` — looks up custom scorers, falls back to sklearn built-ins
- `evaluate_on_test(model, X_test, y_test, metric_names, true_prob_test)` — scores a fitted model on held-out data, includes Bayes-optimal comparison if deterministic data

### tools/dataframes.py
Generic DataFrame utilities shared across the project.
- Currently empty. Use for: loading parquet/csv, column type enforcement, null handling, merging, filtering — anything pandas-related that multiple modules need.

### tools/data_generator.py
SDV synthetic data generation with optional deterministic target.
- `COEFFICIENTS`, `CATEGORICAL_MAPS`, `INTERCEPT`, `NOISE_SCALE` — ground truth constants
- `sigmoid(x)` — numerically stable sigmoid
- `true_probability(df)` — computes Bayes-optimal P(target=1) from known coefficients
- `apply_ground_truth(df, seed)` — overwrites target with deterministic labels, adds `_true_probability`
- `_build_seed_dataframe(settings)` — creates 200-row seed DataFrame from config
- `_build_metadata(seed_df, settings)` — constructs SDV SingleTableMetadata
- `generate_synthetic_data(settings)` — full pipeline: seed → metadata → fit → sample → optional DGP
- `save_local(df, path)` — writes parquet to disk

---

## skills/ — Domain Logic

Functions that combine multiple tools into a coherent capability. Called by agents. No awareness of LLMs, orchestration, or MLflow.

### skills/modeling.py
Model training with cross-validation and test-set evaluation.
- `ALGORITHM_REGISTRY` — maps string names (e.g. "lightgbm") to sklearn-compatible constructors
- `prepare_data(df, test_size, random_state)` — stratified train/test split, categorical encoding, preserves `_true_probability` alignment
- `train_and_evaluate(df, settings)` — loops over configured algorithms, runs CV on train set, fits on train, evaluates on test via tools/evaluation.py. Returns dict of results per algorithm.

### skills/cleaning.py
Data cleaning operations.
- Not yet implemented. Will handle: missing value imputation, outlier detection, type coercion.

### skills/feature_engineering.py
Feature transforms and creation.
- Not yet implemented. Will handle: scaling, encoding strategies, interaction terms, binning.

### skills/profiling.py
Exploratory data analysis.
- Not yet implemented. Will handle: distribution summaries, correlation analysis, target analysis.

---

## workflows/ — End-to-End Pipelines

Predefined sequences that load data, call skills, and handle side effects (MLflow logging, file I/O). These are the entry points agents trigger.

### workflows/modeling.py
Full modeling workflow.
- `run_modeling_workflow(data_path, settings)` — loads parquet, calls `skills/modeling.train_and_evaluate()`, logs all results to MLflow (CV scores, test scores, per-fold scores, model artifacts). Has `__main__` block for CLI testing.
- Run: `uv run python -m multi_agent_ds.workflows.modeling`

### workflows/evaluation.py
Post-training evaluation workflow.
- Not yet implemented. Will handle: Bayes-optimal comparison reporting, model selection summary, SHAP analysis, diagnostic plots.

### workflows/discovery.py
Data discovery and profiling workflow.
- Not yet implemented. Will orchestrate: data loading → profiling skill → EDA report generation.

### workflows/preparation.py
Data preparation workflow.
- Not yet implemented. Will orchestrate: loading → cleaning skill → feature engineering skill → save processed data.

---

## agents/ — LLM-Powered Decision Makers

Each agent has a role, receives context, reasons about what to do, then calls skills.

### agents/ml_modeler.py
Decides which algorithms to try, whether to tune hyperparameters, calls skills/modeling.py.

### agents/ml_reviewer.py
Reviews the ML modeler's decisions for mathematical rigor, distinguishes evidence-based choices from rules of thumb, and can request revisions.

### agents/business_stakeholder.py
Reviews the final report and modeling conclusions for business realism, readability, and stakeholder fit.

### agents/data_engineer.py
Decides how to clean and prepare data, calls skills/cleaning.py and skills/feature_engineering.py.

### agents/eda_analyst.py
Analyzes data characteristics, calls skills/profiling.py, generates insights for other agents.

### agents/orchestrator.py
Top-level agent that decides which other agents to invoke and in what order.

### agents/reviewer.py
Jonathan-owned experiment/PR reviewer. Distinct from `ml_reviewer.py`.

---

## orchestration/ — LangGraph Graph

### orchestration/graph.py
Defines the LangGraph state graph — nodes (agents) and edges (transitions).

### orchestration/state.py
Defines the shared state object passed between graph nodes.

### orchestration/router.py
Routing logic that decides which agent node executes next.

### orchestration/demo_recorder.py
Record-once-replay-many driver for the Demo tab. Delegates to `build_graph()` and records the 13-node pre-modeling EDA workflow (see `project_planning/sean_step_artifacts/EDA_LANGGRAPH_WORKFLOW.md`). Streams `astream_events(version="v2")`, filters to the closed `RECORDED_NODES` set, sanitizes payloads, and writes `data/interim/demo_run_latest.json` atomically. `data/` is gitignored — the JSON is regenerated locally via `uv run python -m multi_agent_ds.orchestration.demo_recorder`.

Key exports / contracts:
- `RECORDED_NODES` — frozenset of the 13 pre-modeling node names the viewer replays (`eda_raw`, `ml_modeler_raw_review`, `ml_reviewer_raw_review`, `business_stakeholder_raw_review`, `eda_prep_plan`, `data_engineer_feedback`, `data_engineer_execute`, `eda_processed`, `ml_modeler_processed_review`, `ml_reviewer_processed_review`, `business_stakeholder_processed_review`, `eda_processed_approval`, `ml_modeler_handoff`).
- `ACCUMULATE_NODES` — nodes whose `on_chain_end` outputs merge into `final_state`. Invariant: `RECORDED_NODES ⊆ ACCUMULATE_NODES`.
- `record_run(*, parquet_path, output_path, local_only=False)` — async driver that emits the JSON event log.

### orchestration/demo_viewer_loader.py
Pure helper (no I/O) that fuses the viewer HTML template with the recorded JSON:
- `inject_demo_log(viewer_html: str, demo_log_json: str) -> str` — inserts `<script>window.DEMO_LOG = …</script>` before the first existing `<script>` tag, escaping `</` so embedded JSON cannot break out. Raises `ValueError` if no `<script>` tag is present. Called from `app.py`'s Demo tab; safe to import there because it stays within the orchestration layer and reads no files.

---

## Presentation Assets

### src/multi_agent_ds/demo_viewer.html
Single-file, 4-page demo viewer (Config → Input Preview → Runtime Replay → Output Drawer) rendered inside the Streamlit Demo tab via `st.components.v1.html`. Reads `window.DEMO_LOG` (injected by `demo_viewer_loader.inject_demo_log`) and exposes `window.renderConfig`, `window.renderInputPreview`, `window.startRuntimeReplay`, `window.pauseReplay`, `window.continueReplay`, `window.renderSummary`. This is the only HTML asset in the repo; additional presentation assets should land next to it under `src/multi_agent_ds/`.

---

## adapters/ — Provider Abstraction

### adapters/llm/openai.py
OpenAI API adapter for LLM calls. After Step 7 (LLM Model Routing) the constructor takes a fully-resolved `ModelConfig` rather than the raw settings dict — `OpenAIAdapter(config: ModelConfig)`. Reasoning-model quirks (`max_completion_tokens` field name, omitted `temperature`) are handled inside the adapter based on `config.capability`.

### adapters/llm/routing.py
Pure-function model routing layer (Step 7). Owns:
- `ModelConfig` — frozen dataclass carrying `provider`, `model`, `temperature`, `max_tokens`, `capability`, `cost_tier`, `profile_label`
- `resolve_model_config(settings, *, agent, task, cost_override)` — pure resolver. Walks `settings["llm"]["routes"]` (per-task → per-agent default → global default), looks up `model_matrix[capability][cost]` for the model name and `capability_settings[capability]` for non-model fields, and returns a `ModelConfig`. Raises `ValueError` with actionable messages on unknown route, malformed entry, or unknown override.
- `build_adapter(settings, *, agent, task)` — imperative-shell factory. Reads `settings["llm"]["cost_override"]`, calls the resolver, returns an `OpenAIAdapter(config)`. This is the symbol every agent imports.

Re-exported from `adapters/llm/__init__.py` so agents do `from multi_agent_ds.adapters.llm import build_adapter`.

### adapters/llm/local.py
Local model adapter (future use).

### adapters/agent_frameworks/langgraph.py
LangGraph framework adapter.

### adapters/agent_frameworks/crewai.py
CrewAI framework adapter (future use).

---

## core/ — Shared Infrastructure

### core/config.py
YAML config loader. Already implemented:
- `load_config(name)`, `load_settings()`, `load_agents_config()`, `load_prompts_config()`, `load_workflows_config()`
- `get_active_scale(settings)` — resolves current data scale from config
- `build_s3_uri(settings, path_key, filename)` — constructs S3 paths

### core/context.py
Shared context object passed between agents (not yet implemented).

### core/contracts.py
Data contracts / schemas for inter-agent communication (not yet implemented).

### core/registry.py
Service registry for dependency injection (not yet implemented).

---

## config/ — YAML Configuration

### config/settings.yaml
Central config: data sources, S3 paths, model algorithms, scoring metrics, MLflow settings, LLM providers.

### config/agents.yaml
Agent definitions: roles, prompts, tool access, constraints.

### config/prompts.yaml
Prompt templates for agent reasoning.

### config/workflows.yaml
Workflow definitions: step sequences, agent assignments, conditions.

---

## Decision Guide: Where Does New Code Go?

| If you're writing... | Put it in... |
|---|---|
| A pure math/stats function | `tools/evaluation.py` |
| A pandas helper | `tools/dataframes.py` |
| S3 or file I/O | `tools/io.py` |
| Data generation | `tools/data_generator.py` |
| Training/CV/model fitting logic | `skills/modeling.py` |
| Data cleaning logic | `skills/cleaning.py` |
| Feature transforms | `skills/feature_engineering.py` |
| EDA/profiling logic | `skills/profiling.py` |
| An end-to-end pipeline with MLflow | `workflows/` |
| LLM decision-making logic | `agents/` |
| Graph node/edge definitions | `orchestration/` |
| LLM or framework abstraction | `adapters/` |
| LLM model selection / per-agent routing | `adapters/llm/routing.py` |
| Config loading helpers | `core/config.py` |
| Shared state/contracts | `core/` |
