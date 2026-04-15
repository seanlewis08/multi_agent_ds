# Future Work

Items to circle back to when time allows.

---

## 0. Plan Change: Multi-Model Pipeline Starting with LightGBM

**Change:** The ML modeling step is no longer a single logistic regression baseline. The multi-agent system will fit multiple models. The first model we're implementing is a **Gradient Boosting Machine via LightGBM**.

**What this means for the build:**
- `settings.yaml` → `model.baseline` changes from `logistic_regression` to `lightgbm`; add a `model.algorithms` list to support multiple models
- Add `lightgbm` as a dependency in `pyproject.toml`
- The ML modeler agent needs to be designed for a loop: iterate over configured algorithms, fit each, log each to MLflow
- LightGBM uses scikit-learn's compatible API (`LGBMClassifier`), so it plugs into the same CV/scoring pipeline
- Future models to add after LightGBM: logistic regression, random forest, XGBoost, etc.

---

## 1. Migrate from SingleTableMetadata to new Metadata API (SDV)

**Context:** SDV v1.32.1 shows a `FutureWarning` that `SingleTableMetadata` is deprecated in favor of the new `Metadata` class. Our `tools/data_generator.py` currently uses `SingleTableMetadata` and works fine.

**What to change in `_build_metadata()`:**
- Replace `SingleTableMetadata()` with `Metadata()`
- Replace `metadata.detect_from_dataframe(seed_df)` with `metadata.detect_from_dataframe(data=seed_df, table_name="dataset")`
- Replace `metadata.update_column(column_name=..., sdtype=..., ...)` with the new `Metadata.update_column()` signature (verify docs at time of migration)
- Remove `table_name="dataset"` from `GaussianCopulaSynthesizer(metadata)` if the new API handles it internally

**Why not now:** `SingleTableMetadata` works on v1.32.1. The new `Metadata` API won't recreate the `add_table(name=...)` error we hit — it uses `detect_from_dataframe()` instead, which is a completely different method. Safe to defer until SDV drops `SingleTableMetadata` support.

**Risk if ignored:** A future SDV update will remove `SingleTableMetadata`, breaking the data generator.

---

## 2. Observability & Reporting Enhancements

**Context:** The modeling skill functions return rich structured data for the agent, but there's no way for the human-in-the-loop to monitor experiments in real time or review results without reading raw dicts.

**Planned changes (implement together as one update):**

### 2a. MLflow Nested Runs
- Each experiment gets a parent MLflow run
- Each phase (baseline, tuning, lr adjustment, feature selection) becomes a nested child run via `mlflow.start_run(nested=True)`
- Human can watch runs appear in real time via `mlflow ui` (localhost:5000)
- Logging happens in the workflow/agent layer, NOT in skills (keeps skills pure)

### 2b. Local Experiment Log (Markdown)
- New `tools/reporting.py` with an `ExperimentLogger` class
- Appends to `reports/experiment_log_<timestamp>.md` after each phase
- Includes data summary, phase results, agent decisions, and final comparison
- Human can read it in their IDE without starting MLflow

### 2c. Progress Bars (tqdm)
- Add `tqdm` progress bars inside skill functions for long-running loops:
  - `find_optimal_estimators()` — n_estimator candidates
  - `tune_algorithm()` — Optuna trials (via callback)
  - `train_with_defaults()` — algorithm loop
  - `get_permutation_importances()` — feature × repeat loop
- Terminal shows real-time progress: "Optuna tuning: 23/50 [00:45<00:55, best=0.8612]"
- Add `tqdm` as a dependency

### 2d. Algorithm Selection Override
- `train_with_defaults()` gets an optional `algorithms` parameter that overrides `settings["model"]["algorithms"]`
- Agent or human can pass `["lightgbm"]` to run a single model
- Config list remains the default when no override is provided
- `workflows/modeling.py` gets `--algorithms` CLI argument via argparse
- Future: parallel execution with `ProcessPoolExecutor` when 4+ algorithms are configured

**Why not now:** The core skill functions need to be tested first. These are quality-of-life improvements that layer on top of working code.

---

## 3. SHAP Integration for Model Explainability

**Context:** The article "You Are Probably Reading XGBoost Feature Importance Wrong" (Iakubovskyi, 2026) recommends SHAP as the most theoretically sound method for feature importance — satisfies efficiency, symmetry, dummy, and additivity axioms. Provides per-sample decomposition and directional impact.

**Planned changes:**
- New `get_shap_importances()` function in `skills/modeling.py`
- Uses `shap.TreeExplainer` for tree models (exact, polynomial time)
- Returns global ranking (mean absolute SHAP), per-feature direction, and raw SHAP matrix
- Agent uses this for stakeholder communication and model explanation
- SHAP beeswarm and waterfall plots logged as MLflow artifacts
- Add `shap` as a dependency

**When to implement:** After tuning and feature selection workflow is tested. SHAP is for analysis and communication, not for feature removal decisions (use permutation importance for that).
