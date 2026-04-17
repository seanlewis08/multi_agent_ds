# Sean's Build Plan — Steps 6–10

**Author:** Sean Lewis  
**Date:** April 15, 2026  
**Scope:** Steps 6–10 of BUILD_PLAN.md (LLM adapter → agents → report generation)  
**Dependencies completed:** Steps 1–5b (config, data gen, modeling skills, workflows, artifacts, Streamlit app, MLflow integration)

---

## Overview

Sean owns the **shared infrastructure** (LLM adapter, LangGraph orchestration skeleton) and the **upstream pipeline** (EDA → data engineering → ML modeler → ML reviewer). He also owns the final report generation and business stakeholder review step.

Jonathan owns the **downstream pipeline** (evaluation, orchestrator, experiment PR agent) and the **git/PR tooling** both layers share. See `Jonathan_Plan.md`.

The modeling step is the divergence point — each person builds their own ML modeler agent with different strategies, both calling the same `skills/modeling.py` functions.

---

## Progress Tracker

Use this section as the high-level status board for Sean-owned step work. Detailed step checklists and implementation plans live in `project_planning/sean_step_artifacts/`.

| Step | Status | Tracking Docs |
|------|--------|---------------|
| Step 1: LLM Adapter | Complete | `sean_step_artifacts/LLM_Adapter_Implementation_Plan.md`, `sean_step_artifacts/LLM_Adapter_Checklist.md` |
| Step 2: LangGraph Orchestration Skeleton | Complete | `sean_step_artifacts/LangGraph_Skeleton_Implementation_Plan.md`, `sean_step_artifacts/LangGraph_Skeleton_Checklist.md` |
| Step 3: EDA Skills + Agent | Complete | `sean_step_artifacts/EDA_Analyst_Implementation_Plan.md`, `sean_step_artifacts/EDA_Analyst_Checklist.md` |
| Step 4: Data Engineering Skills + Agent | Complete | `sean_step_artifacts/Data_Engineer_Implementation_Plan.md`, `sean_step_artifacts/Data_Engineer_Checklist.md` |
| Step 5: ML Modeler + ML Reviewer | Complete (pushed, awaiting PR) | `sean_step_artifacts/ML_Modeler_Reviewer_Implementation_Plan.md`, `sean_step_artifacts/ML_Modeler_Reviewer_Checklist.md` |
| Step 6: Report + Business Stakeholder Review | Complete (pushed in 559f105) | `sean_step_artifacts/Report_Business_Review_Implementation_Plan.md`, `sean_step_artifacts/Report_Business_Review_Checklist.md` |
| Step 7: LLM Model Routing | Complete (Phases a–d shipped; Phase e LangSmith deferred) | `LLM_MODEL_ROUTING.md` |

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
| `workflows/modeling.py` | Non-agentic baseline workflow + MLflow nested runs + artifact export | ✅ |
| `app.py` | Streamlit dashboard (sidebar config, run button, results, log viewer, MLflow UI management) | ✅ |
| `config/settings.yaml` | Full config (data, S3, model, MLflow, LLM) | ✅ |

---

## Step 1: LLM Adapter

**BUILD_PLAN reference:** Step 6  
**Files to edit:** `adapters/llm/openai.py` (currently placeholder)  
**Config to edit:** `config/settings.yaml` (LLM section already exists)

### What to Build

A thin wrapper around the OpenAI API that agents call to reason about skill outputs. This is provider-agnostic — the adapter abstracts the LLM so we can swap providers later.

### Implementation Details

**`adapters/llm/openai.py`:**

```python
class OpenAIAdapter:
    """Send prompts, receive structured responses."""

    def __init__(self, settings: dict):
        # Read from settings["llm"]["providers"]["openai"]
        # API key from .env via python-dotenv (already a dependency)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Send a chat completion request. Returns parsed response."""
        # Handles: prompt formatting, function calling / tool_use schema
        # Retry with exponential backoff on rate limits
        # Token counting via tiktoken or response.usage

    def structured_output(self, messages: list[dict], schema: dict) -> dict:
        """Request a JSON response conforming to a Pydantic-like schema."""
        # Uses response_format={"type": "json_schema", ...}
```

**Protocol / base class** (in same file or `adapters/llm/__init__.py`):

```python
class LLMAdapter(Protocol):
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict: ...
    def structured_output(self, messages: list[dict], schema: dict) -> dict: ...
```

### Design Decisions

- **No new dependencies.** `openai` is already in `pyproject.toml`. `python-dotenv` is already there for `.env` loading.
- **Function calling format** for agent tool use — agents express decisions as structured actions (e.g., `{"action": "tune", "algorithm": "lightgbm", "params": {...}}`).
- **Retry logic** — exponential backoff on `RateLimitError` and `APIConnectionError`.
- **Token counting** — track usage per call, surface in agent context so the orchestrator can budget.
- **Temperature from config** — `settings.yaml` already has `llm.providers.openai.temperature: 0.2`.

### Done When

- `from multi_agent_ds.adapters.llm.openai import OpenAIAdapter` works
- Can send a prompt and get a structured response
- Retries on rate limit
- Jonathan can import and use it for his agents

---

## Step 2: LangGraph Orchestration (Shared Skeleton)

**BUILD_PLAN reference:** Step 7  
**Files to edit:** `orchestration/state.py`, `orchestration/graph.py`, `orchestration/router.py`, `core/context.py`, `core/contracts.py` (all currently placeholders)

### What to Build

The shared graph infrastructure that all agents plug into. Both Sean's and Jonathan's agents register as nodes in the same graph.

### Implementation Details

**`orchestration/state.py` — Shared State Schema:**

```python
from typing import TypedDict, Any

class PipelineState(TypedDict, total=False):
    """State passed between graph nodes."""
    # Data references
    data_path: str
    data: dict                    # Output of prepare_data()
    settings: dict

    # Agent outputs (each agent writes to its key)
    eda_insights: dict            # From eda_analyst
    prep_result: dict             # From data_engineer
    modeling_results: dict        # From ml_modeler
    evaluation_result: dict       # From evaluation pipeline
    experiment_report: str        # From report generator

    # Control flow
    agent_decisions: list[dict]   # Trace of all agent reasoning
    current_phase: str
    should_loop: bool
    iteration: int
```

**`orchestration/graph.py` — StateGraph:**

```python
from langgraph.graph import StateGraph, END
from multi_agent_ds.orchestration.state import PipelineState

def build_graph() -> StateGraph:
    """Build the LangGraph state graph with agent nodes."""
    graph = StateGraph(PipelineState)

    # Nodes registered here — each agent file exports a function
    # that takes PipelineState and returns partial PipelineState
    graph.add_node("eda", eda_node)
    graph.add_node("data_engineer", data_engineer_node)
    graph.add_node("ml_modeler", ml_modeler_node)
    graph.add_node("ml_reviewer", ml_reviewer_node)
    graph.add_node("evaluation", evaluation_node)
    graph.add_node("reviewer", reviewer_node)       # Jonathan's PR agent
    graph.add_node("report", report_node)
    graph.add_node("business_stakeholder", business_stakeholder_node)

    # Edges (sequential for now, conditional routing added later)
    graph.set_entry_point("eda")
    graph.add_conditional_edges("eda", route_after_eda)
    graph.add_edge("data_engineer", "ml_modeler")
    graph.add_conditional_edges("ml_modeler", route_after_modeling)
    graph.add_conditional_edges("ml_reviewer", route_after_ml_review)
    graph.add_edge("evaluation", "reviewer")
    graph.add_edge("reviewer", "report")
    graph.add_edge("report", "business_stakeholder")
    graph.add_conditional_edges("business_stakeholder", route_after_business_review)

    return graph
```

**`orchestration/router.py` — Conditional Routing:**

```python
def route_after_eda(state: PipelineState) -> str:
    """After EDA: skip to modeling if data is clean, else route to data_engineer."""
    insights = state.get("eda_insights", {})
    if insights.get("needs_cleaning", False):
        return "data_engineer"
    return "ml_modeler"

def route_after_modeling(state: PipelineState) -> str:
    """After modeling: loop if improvement threshold not met."""
    if state.get("should_loop", False) and state.get("iteration", 0) < 5:
        return "ml_modeler"
    return "evaluation"
```

**`core/context.py` — Domain Payload:**

```python
@dataclass
class ExperimentContext:
    """Domain-specific payload agents read and write."""
    dataset_info: dict
    feature_insights: dict
    model_comparisons: list[dict]
    agent_reasoning_trace: list[dict]
    config_snapshot: dict
```

**`core/contracts.py` — Inter-Agent Schemas:**

```python
from pydantic import BaseModel

class EDAOutput(BaseModel):
    """What the EDA agent must produce for downstream agents."""
    n_rows: int
    n_features: int
    target_rate: float
    needs_cleaning: bool
    feature_summaries: list[dict]
    correlation_flags: list[dict]
    recommendations: list[str]

class ModelingOutput(BaseModel):
    """What the ML modeler agent must produce."""
    algorithm: str
    phase: str
    scores: dict
    params_used: dict
    reasoning: str
    next_action: str
```

### Done When

- `from multi_agent_ds.orchestration.graph import build_graph` works
- Graph compiles with placeholder nodes
- Jonathan can register his agents as nodes

---

## Step 3: EDA Skills + Agent

**BUILD_PLAN reference:** Steps 3 + 8 (partial)  
**Files to edit:** `skills/profiling.py`, `workflows/discovery.py`, `agents/eda_analyst.py` (all placeholders)  
**Config to edit:** `config/prompts.yaml`

### What to Build

#### `skills/profiling.py` — Pure Profiling Functions

All functions take a DataFrame and return rich dicts. No LLM calls, no MLflow, no file I/O.

```python
def compute_distributions(df, target_col) -> dict:
    """Distribution summary: per-feature stats, skewness, percentiles."""

def compute_correlations(df, target_col) -> dict:
    """Correlation matrix + high-correlation pairs flagged."""

def compute_target_analysis(df, target_col) -> dict:
    """Target rate, class balance, target-vs-feature relationships."""

def compute_feature_target_relationships(df, target_col) -> dict:
    """Per-feature AUC with target, IV (information value), WoE."""

def detect_outliers(df, numerical_cols) -> dict:
    """IQR-based outlier detection per numerical feature."""

def profile_dataset(df, target_col) -> dict:
    """Orchestrator: calls all above, returns combined profile dict."""
```

#### `workflows/discovery.py` — Non-Agentic EDA Workflow

Loads data, calls `profile_dataset()`, writes an EDA markdown report. Mirrors the pattern of `workflows/modeling.py`.

#### `agents/eda_analyst.py` — LLM-Powered Agent

```python
def eda_node(state: PipelineState) -> dict:
    """LangGraph node: profile data, ask LLM to interpret, produce insights."""
    # 1. Call skills/profiling.profile_dataset()
    # 2. Format profile as prompt context
    # 3. Call LLM adapter: "Given these distributions and correlations, what stands out?"
    # 4. Parse LLM response into EDAOutput contract
    # 5. Return {"eda_insights": insights_dict}
```

#### `config/prompts.yaml` — EDA Prompts

```yaml
eda_analyst:
  system: |
    You are an expert data scientist analyzing a dataset for a binary classification problem.
    Review the provided data profile and identify: anomalies, skewed distributions,
    high correlations, class imbalance, and features that may need cleaning or engineering.
  analysis: |
    Here is the data profile for a dataset with {n_rows} rows and {n_features} features.
    Target rate: {target_rate:.4f}
    {profile_json}
    Provide your analysis as structured JSON with keys: needs_cleaning, recommendations, feature_flags.
```

### Done When

- `profile_dataset(df, "binary_target")` returns a complete profile dict
- EDA agent produces structured insights via LLM
- Wired as the first node in the LangGraph graph

---

## Step 4: Data Engineering Skills + Agent

**BUILD_PLAN reference:** Steps 4 + 8 (partial)  
**Files to edit:** `skills/cleaning.py`, `skills/feature_engineering.py`, `workflows/preparation.py`, `agents/data_engineer.py` (all placeholders)  
**Config to edit:** `config/prompts.yaml`

### What to Build

#### `skills/cleaning.py` — Pure Cleaning Functions

```python
def impute_missing(df, strategy_map) -> dict:
    """Impute missing values per-column using specified strategy (mean, median, mode, constant)."""

def detect_and_handle_outliers(df, method, columns) -> dict:
    """Cap/floor outliers using IQR or z-score method. Returns cleaned df + report."""

def coerce_types(df, type_map) -> dict:
    """Enforce column dtypes. Returns cleaned df + coercion report."""

def clean_dataset(df, cleaning_plan) -> dict:
    """Apply a full cleaning plan (dict of strategies). Returns cleaned df + summary."""
```

#### `skills/feature_engineering.py` — Pure Feature Transforms

```python
def scale_features(df, columns, method) -> dict:
    """StandardScaler or MinMaxScaler. Returns transformed df + scaler params."""

def create_interactions(df, interaction_pairs) -> dict:
    """Create interaction features (product terms). Returns df with new columns."""

def bin_features(df, binning_plan) -> dict:
    """Bin continuous features into categories. Returns df + bin edges."""

def engineer_features(df, engineering_plan) -> dict:
    """Apply a full engineering plan. Returns transformed df + summary."""
```

#### `agents/data_engineer.py` — LLM-Powered Agent

```python
def data_engineer_node(state: PipelineState) -> dict:
    """LangGraph node: decide cleaning/engineering based on EDA insights."""
    # 1. Read state["eda_insights"]
    # 2. Call LLM: "Given these data issues, what cleaning and engineering should I apply?"
    # 3. Parse LLM response into a cleaning_plan and engineering_plan
    # 4. Call skills/cleaning.clean_dataset() with the plan
    # 5. Call skills/feature_engineering.engineer_features() with the plan
    # 6. Return {"prep_result": {...}, "data": updated_data_dict}
```

### Done When

- Cleaning and engineering functions work on the synthetic dataset
- Data engineer agent makes LLM-driven decisions about what to apply
- Wired into the graph after the EDA node

---

## Step 5: ML Modeler + ML Reviewer

**BUILD_PLAN reference:** Step 8 (ML modeler)  
**Files to edit:** `agents/ml_modeler.py` (currently placeholder)  
**Config to edit:** `config/prompts.yaml`

### What to Build

Sean's ML modeler agent implements the full 9-step phased tuning workflow from `skills/modeling.py`. A separate `ml_reviewer` agent then challenges those choices, checks the mathematical reasoning, and decides whether the modeling output is ready for downstream evaluation.

### Agent Flow

```
Phase 1: train_with_defaults()
  → LLM reviews baseline scores
  → Decides: which algorithms are worth tuning?

Phase 2: find_optimal_estimators() [boosting algos only]
  → LLM reviews n_estimator search results
  → Decides: accept this lr/n_est pair or try different lr?

Phase 3: tune_algorithm()
  → LLM reviews Optuna results (best score, improvement, param importances)
  → Decides: accept tuned params or keep defaults?

Phase 4: train_with_params()
  → Re-train with tuned params
  → LLM compares tuned vs baseline

Phase 5: adjust_learning_rate() [boosting algos only]
  → LLM reviews score change after lr adjustment
  → Decides: keep new lr or revert?

Phase 6: get_feature_importances()
  → LLM reviews native importance ranking (fast diagnostic)

Phase 7: get_permutation_importances()
  → LLM reviews permutation importance + safe_to_remove flags
  → Decides: which features to drop?

Phase 8: train_with_feature_subset()
  → LLM compares before/after feature selection
  → Decides: keep reduced set or revert?

Phase 9: Compare all algorithms
  → LLM recommends best model with justification
```

### Implementation Pattern

```python
def ml_modeler_node(state: PipelineState) -> dict:
    """LangGraph node: phased model training with LLM reasoning between phases."""
    data = state["data"]
    settings = state["settings"]
    adapter = OpenAIAdapter(settings)
    decisions = []

    # Phase 1: Baseline
    results = train_with_defaults(data, settings)
    prompt = format_baseline_results(results)
    decision = adapter.structured_output(
        messages=[{"role": "system", "content": ML_MODELER_SYSTEM},
                  {"role": "user", "content": prompt}],
        schema=BaselineDecisionSchema
    )
    decisions.append({"phase": "baseline", "decision": decision})

    # Phase 2-8: conditional on LLM decisions
    for algo_name in decision["algorithms_to_tune"]:
        # ... each phase follows the same pattern:
        # run skill → format result → ask LLM → parse decision → act

    return {
        "modeling_results": results,
        "agent_decisions": state.get("agent_decisions", []) + decisions,
    }
```

### Prompts (`config/prompts.yaml`)

```yaml
sean_ml_modeler:
  system: |
    You are an ML modeler agent. You train and tune binary classification models.
    You make decisions about hyperparameter tuning, learning rate schedules,
    and feature selection based on cross-validation and test scores.
    Always explain your reasoning. Prefer conservative changes that improve
    generalization over aggressive tuning that risks overfitting.
  baseline_review: |
    Here are the baseline results for {n_algorithms} algorithms:
    {results_json}
    Which algorithms should be tuned further? Respond with a JSON object:
    {"algorithms_to_tune": [...], "reasoning": "..."}
  tuning_review: |
    Optuna tuning results for {algorithm}:
    {tuning_json}
    Should we accept these tuned parameters? Respond with:
    {"accept": true/false, "reasoning": "..."}
```

### Done When

- ML modeler agent runs the full phased workflow with LLM reasoning
- ML reviewer agent distinguishes scientific reasoning from rule-of-thumb judgment
- ML reviewer can route weak modeling decisions back for revision
- Each decision is logged to `agent_decisions` in the state
- Wired as a node in the LangGraph graph

---

## Step 6: Report + Business Stakeholder Review

**BUILD_PLAN reference:** Step 10  
**Files to edit:** Extend `tools/reporting.py` or create logic in the report graph node  
**Config to edit:** `config/prompts.yaml`

### What to Build

An LLM-powered report generator that produces a non-technical experiment summary after the full pipeline completes, followed by a `business_stakeholder` agent that checks business realism and report readability before final approval.

### Output

A markdown report containing:
- What data was used (size, features, target rate)
- What models were tried and why
- Which model won and why (with key metrics)
- Top features and their business interpretation
- Confidence levels and caveats
- Link to MLflow experiment for detailed review

### Implementation

```python
def report_node(state: PipelineState) -> dict:
    """LangGraph node: generate stakeholder-facing experiment summary."""
    # 1. Gather: eda_insights, modeling_results, evaluation_result, agent_decisions
    # 2. Call LLM: "Summarize this experiment for a non-technical audience"
    # 3. Write markdown to reports/experiment_summary_<timestamp>.md
    # 4. Return {"experiment_report": report_markdown}
```

### Done When

- Report node produces a readable markdown summary
- Business stakeholder agent can reject unclear or unrealistic summaries
- Summary is saved to `reports/` alongside the existing experiment logs

---

## Step 7: LLM Model Routing

**Status:** Complete — Phases (a)–(d) shipped in commits `559f105` (Step 6 ride-along: `business_stakeholder`, `report_writer` migrations) and `b424231` (routing module, remaining agent migrations, settings schema, app env wiring, tests, review notebook). Phase (e) LangSmith metadata deferred (see `TODO(phase-e)` in `adapters/llm/routing.py`).
**Design doc:** `project_planning/LLM_MODEL_ROUTING.md`
**BUILD_PLAN reference:** Cross-cutting refactor of Step 6 (LLM Adapter)
**Files added:** `src/multi_agent_ds/adapters/llm/routing.py`, `tests/test_routing.py`, `notebooks/LLM_Model_Routing_Review.ipynb`
**Files modified:** `adapters/llm/openai.py`, `adapters/llm/__init__.py`, `agents/{eda_analyst,data_engineer,ml_reviewer,ml_modeler,business_stakeholder,report_writer}.py`, `src/multi_agent_ds/app.py`, `config/settings.yaml`, `tests/{test_openai_adapter,test_eda_analyst,test_pre_modeling_review_agents}.py`, `tests/integration/test_openai_adapter_live.py`

### What to Build

A two-axis `(capability, cost)` routing layer so every `(agent, task)` pair can resolve to its own `ModelConfig` (e.g. `o3` for `ml_modeler.tuning_decision`, `gpt-4.1-mini` for `ml_reviewer`). Resolution is a pure function (`resolve_model_config`); the adapter becomes provider-dumb (`OpenAIAdapter(config)`); `LLM_COST_OVERRIDE` env var lets us force every route to a single cost tier for smoke tests.

### Sequencing Constraints

- **Depends on Step 5 finishing first.** Six of the ten LLM call sites that need to migrate live in `ml_modeler.py`, which is still being planned. Easiest path: finish and merge Step 5 against today's `OpenAIAdapter(settings)` API, then land Step 7 as a clean refactor on a new branch.
- **Breaking change for Jonathan's branch.** The constructor swap from `OpenAIAdapter(settings)` to `OpenAIAdapter(config: ModelConfig)` affects every call site, including any in `agents/orchestrator.py` or downstream nodes Jonathan owns. Coordinate before opening the routing branch.

### Phasing (per LLM_MODEL_ROUTING.md §Open Items)

1. Phase (a) — Add `adapters/llm/routing.py` (`ModelConfig` + `resolve_model_config` + `build_adapter` factory) plus pure-function unit tests. Dormant until imported.
2. Phase (b) — Refactor `adapters/llm/openai.py` constructor to take `ModelConfig`. Update existing OpenAI adapter tests.
3. Phase (c) — Migrate the four shipped agents' call sites (`eda_analyst`, `data_engineer`, `ml_reviewer`, `business_stakeholder`) plus the six `ml_modeler` modes (once Step 5 has shipped them).
4. Phase (d) — Wire `LLM_COST_OVERRIDE` env var in `src/multi_agent_ds/app.py`.
5. Phase (e) — LangSmith metadata pass: tag spans with `capability` and `cost_tier` from each `ModelConfig`.

### What Can Land Before Step 5 Finishes

Phase (a) and a settings.yaml additive (new `model_matrix`, `capability_settings`, `routes` keys alongside the existing `providers.openai.model`) are fully decoupled from Step 5 and can land first as standalone slices. This also unblocks Step 5's `ml_modeler` to be written against `build_adapter(settings, agent="ml_modeler", task=mode)` from day one.

### Done When

- Every `OpenAIAdapter` instance is constructed via `build_adapter(settings, agent=..., task=...)`
- LangSmith trace shows `gpt-4.1-mini` for reviewers and `o3` for `tuning_decision` / `modeling_verdict`
- `LLM_COST_OVERRIDE=cheap` forces every span onto its capability's cheap-tier model
- Resolver fails fast with an actionable `ValueError` on a malformed route
- Unit tests cover resolver fallbacks, cost override, malformed config, and reasoning-model adapter quirks

---

## Coordination with Jonathan

| Concern | Owner | Coordination Needed |
|---------|-------|---------------------|
| LLM adapter | Sean builds first | Jonathan uses it for his agents |
| LangGraph skeleton | Sean builds first | Jonathan registers his nodes |
| `skills/modeling.py` | Shared | Coordinate if adding algorithms to `ALGORITHM_REGISTRY` |
| `config/prompts.yaml` | Both edit | Sean prefixes with `eda_`, `data_engineer_`, `sean_ml_modeler_` |
| `tools/git.py` | Jonathan builds | Sean's agents may use it for experiment PRs |
| `agents/reviewer.py` | Jonathan builds | Sean's report node runs before reviewer |
| `OpenAIAdapter` constructor (Step 7) | Sean | **Landed 2026-04-16** in `b424231`. Breaking change: `OpenAIAdapter(settings)` → `OpenAIAdapter(config: ModelConfig)`. Jonathan must migrate any call sites he owns when pulling main. |

### Sequencing

1. **Sean commits Steps 1–2 first** (adapter + orchestration skeleton) — these are shared dependencies.
2. **Jonathan starts on Step 1** (git tool + evaluation pipeline) while waiting — no LLM dependency needed.
3. **Steps 3–6 can proceed in parallel** once the shared infrastructure is in place.

---

## Files to Create or Edit (Summary)

| File | Action | Step |
|------|--------|------|
| `adapters/llm/openai.py` | Implement (currently placeholder) | 1 |
| `orchestration/state.py` | Implement (currently placeholder) | 2 |
| `orchestration/graph.py` | Implement (currently placeholder) | 2 |
| `orchestration/router.py` | Implement (currently placeholder) | 2 |
| `core/context.py` | Implement (currently placeholder) | 2 |
| `core/contracts.py` | Implement (currently placeholder) | 2 |
| `skills/profiling.py` | Implement (currently placeholder) | 3 |
| `workflows/discovery.py` | Implement (currently placeholder) | 3 |
| `agents/eda_analyst.py` | Implement (currently placeholder) | 3 |
| `skills/cleaning.py` | Implement (currently placeholder) | 4 |
| `skills/feature_engineering.py` | Implement (currently placeholder) | 4 |
| `workflows/preparation.py` | Implement (currently placeholder) | 4 |
| `agents/data_engineer.py` | Implement (currently placeholder) | 4 |
| `agents/ml_modeler.py` | Implement — Sean's version (currently placeholder) | 5 |
| `config/prompts.yaml` | Populate with prompt templates | 3, 4, 5, 6 |
| `tools/reporting.py` | Extend with report generation helpers | 6 |
| `adapters/llm/routing.py` | Create — `ModelConfig`, `resolve_model_config`, `build_adapter` | 7 |
| `adapters/llm/openai.py` | Refactor constructor to take `ModelConfig` (breaking change) | 7 |
| `adapters/llm/__init__.py` | Re-export `ModelConfig`, `resolve_model_config`, `build_adapter` | 7 |
| `agents/eda_analyst.py`, `data_engineer.py`, `ml_modeler.py`, `ml_reviewer.py`, `business_stakeholder.py` | Migrate every `OpenAIAdapter(settings)` call site to `build_adapter(settings, agent=..., task=...)` | 7 |
| `src/multi_agent_ds/app.py` | Read `LLM_COST_OVERRIDE` env var, stash in `settings["llm"]["cost_override"]` | 7 |
| `config/settings.yaml` | Add `model_matrix`, `capability_settings`, `routes`, `cost_override` (additive in early slice; remove old `providers.openai.model` once Phase b ships) | 7 |
| `tests/unit/adapters/llm/test_routing.py` | Create — pure-function tests for `resolve_model_config` | 7 |
