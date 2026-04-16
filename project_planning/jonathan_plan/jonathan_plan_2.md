# Jonathan Plan Step 2 Checklist

Source: [Jonathan_Plan.md](/Users/jonathan.chia/code/multi_agent_ds/project_planning/Jonathan_Plan.md)

## Step 2: Evaluation Pipeline

- [ ] Confirm Step 2 scope against `project_planning/Jonathan_Plan.md`
- [ ] Confirm Step 2 is still aligned with `project_planning/BUILD_PLAN.md` Step 9
- [ ] Confirm exact file targets for Step 2 changes
  Expected primary target: `src/multi_agent_ds/workflows/evaluation.py`
- [ ] Confirm whether any supporting edits are needed in adjacent modules or whether Step 2 can stay isolated to the workflow layer
- [ ] Confirm no new dependency is needed
  Expected: use existing `shap`, `matplotlib`, sklearn, NumPy, and current artifact helpers

## 2a. Prep And Context Review

- [ ] Read the current placeholder in `src/multi_agent_ds/workflows/evaluation.py`
- [ ] Read `src/multi_agent_ds/tools/evaluation.py` to understand available scoring outputs
- [ ] Read `src/multi_agent_ds/tools/artifacts.py` to match current artifact-return conventions
- [ ] Read the relevant portions of `src/multi_agent_ds/workflows/modeling.py` to understand the structure of `results` and `data`
- [ ] Read `project_planning/Ground_Truth_Feature_Importance.md` before implementing feature-importance validation logic
- [ ] Decide the minimal Step 2 surface area
  Expected bias: keep SHAP computation, ranking, summary building, and artifact packaging in `workflows/evaluation.py` unless a helper is clearly reusable

## 2b. Workflow Interface Definition

- [ ] Define `run_evaluation_workflow(results, data, settings) -> dict`
- [ ] Document the expected `results` input shape from the modeling workflow
- [ ] Confirm the current modeling result fields that already exist
  Expected fields per algorithm include `cv_scores`, `cv_std`, `validation_scores`, `test_scores`, `y_pred`, `y_prob`, `model`, `params_used`, `feature_names`, `training_history`, `encoding`, and `elapsed_seconds`
- [ ] Document the expected `data` input shape
  Expected keys include `X_validation`, `X_test`, `y_validation`, `y_test`, `feature_names`, and optionally `true_prob_validation` / `true_prob_test`
- [ ] Document the returned evaluation summary structure before filling in implementation details
- [ ] Define the `rankings` return shape
- [ ] Define the `winner` return shape
- [ ] Define the `ground_truth_comparison` return shape
- [ ] Define the `shap_results` return shape
- [ ] Define the `shap_artifacts` return shape
- [ ] Define the future logging-bundle return shape
- [ ] Define a reviewer-compatible summary contract for the evaluation output
  Expected: include a top-level scalar winner signal such as `winner`, `best_model`, or `model_name` so `agents/reviewer.py` can derive branch names, commit messages, and PR titles cleanly
- [ ] Separate reviewer-facing summary fields from heavy artifact payloads
  Expected bias: keep the state-friendly evaluation summary compact and serializable, while keeping PNG bytes and other bulky artifact content outside the prompt-heavy reviewer context
- [ ] Define an explicit MLflow-ready output contract
  Expected: the workflow should return a compact evaluation/state summary plus a separate artifact/logging bundle that can be handed to MLflow later without reshaping the whole result
- [ ] Define the compact `evaluation_result` state payload
- [ ] Define the prompt-safe `reviewer_summary` payload
- [ ] Define the artifact bundle payload
- [ ] Define the future `mlflow_payload` payload
- [ ] Decide where raw bytes are allowed versus where JSON-safe data is required
- [ ] Define which fields belong in state versus which belong in future MLflow logging payloads
  Expected bias: metrics, rankings, winner, caveats, and reviewer-safe summary stay in state; bulky figures, artifact bytes, and logging metadata stay in the artifact/logging bundle
- [ ] Decide whether the workflow returns artifacts only, or also performs MLflow logging in this step
  Expected bias: return structured artifacts from the workflow first unless the plan explicitly requires direct MLflow side effects here
- [ ] Keep the implementation in the workflow layer rather than pushing business logic into `tools/evaluation.py`

## 2c. Model Ranking

- [ ] Extract per-algorithm test scores from `results`
- [ ] Read the primary metric from `settings["model"]["primary_metric"]`
- [ ] Decide the ranking sort direction for each supported metric
  Expected: metrics like `gini`, `roc_auc`, `f1`, `precision`, `recall`, and `accuracy` sort descending; error metrics like `ase` and `mse_vs_ground_truth` sort ascending
- [ ] Compute an overall ranking by the configured primary metric
- [ ] Extract comparable primary-metric scores for all candidate algorithms
- [ ] Apply the metric-direction rule to produce sortable ranking values
- [ ] Decide how to handle algorithms missing the primary metric
- [ ] Apply tie-breaking rules when needed
- [ ] Emit winner and runner-up from the final ordering
- [ ] Compute per-metric rankings for the scoring metrics present in the results
- [ ] Identify winner and runner-up
- [ ] Define tie-breaking behavior when two algorithms are equal or nearly equal on the primary metric
- [ ] Decide whether validation scores should inform tie-breaking or caveat reporting
- [ ] Record any missing-metric or partial-result behavior so the workflow fails clearly or degrades predictably

## 2d. Ground Truth Comparison

- [ ] Detect whether `true_prob_test` is available
- [ ] If available, compute each model's closeness to the Bayes-optimal probabilities
- [ ] Normalize the ground-truth comparison into a structured summary per algorithm
- [ ] Rank algorithms by closeness to ground truth
- [ ] Compare model behavior against the expectations from `Ground_Truth_Feature_Importance.md`
- [ ] Decide whether to use existing `ground_truth_artifact()` output as part of the Step 2 summary structure
- [ ] If `true_prob_test` is absent, return a clear structured "not available" result instead of failing implicitly

## 2e. SHAP Strategy

- [ ] Select the winning model as the default SHAP target
- [ ] Decide how to access the fitted winning model and aligned test features from `results` / `data`
- [ ] Confirm the winning model's `feature_names` align with the encoded matrix used to fit that model
- [ ] Implement explainer selection by algorithm
  Expected:
  - `lightgbm` -> `shap.TreeExplainer`
  - `logistic_regression` -> `shap.LinearExplainer`
  - fallback -> `shap.Explainer`
- [ ] Confirm the correct handling of SHAP return types across explainers
  Examples: binary classification arrays vs `shap.Explanation`
- [ ] Decide how to normalize binary-class SHAP outputs to one consistent summary representation
- [ ] Compute SHAP values on the test set
- [ ] Select the exact feature matrix passed to the explainer
- [ ] Instantiate the algorithm-appropriate explainer
- [ ] Normalize the raw SHAP output into one internal representation
- [ ] Validate row count and feature count alignment after normalization
- [ ] Derive global ranking via mean absolute SHAP values
- [ ] Compute mean absolute SHAP importance per feature
- [ ] Sort and truncate the global ranking for summary use
- [ ] Derive per-feature directional summary where feasible
- [ ] Compute signed direction summaries for the top features when supported
- [ ] Decide how to handle unsupported or failing explainers without breaking the full evaluation summary
- [ ] Keep SHAP logic deterministic and bounded enough for unit tests

## 2f. SHAP Artifacts

- [ ] Decide whether to generate SHAP figures directly in `workflows/evaluation.py` or via small local helper functions inside the same module
- [ ] Generate a beeswarm plot as PNG bytes
- [ ] Generate a waterfall plot for a representative sample as PNG bytes
- [ ] Generate a structured SHAP summary payload for downstream agents
- [ ] Build the global importance section of the SHAP summary payload
- [ ] Build the directional-effects section of the SHAP summary payload
- [ ] Build a reviewer-safe top-features summary section
- [ ] Build an MLflow-safe JSON summary section
- [ ] Keep artifact output format consistent with `tools/artifacts.py`
  Expected pattern: return JSON-serializable structured content plus PNG bytes keyed by filename
- [ ] Ensure figures use a non-interactive backend path compatible with test execution
- [ ] Decide how to choose the representative sample for the waterfall plot
  Expected options: highest predicted risk, largest SHAP magnitude, or a fixed deterministic row
- [ ] Confirm artifact filenames are stable and distinct from the existing modeling artifact names
- [ ] Add MLflow-friendly artifact metadata alongside content
  Expected fields: artifact category, stable filename, short summary, and content type so a later logging step does not need to infer those values

## 2g. Model Selection Summary

- [ ] Build a winner summary containing algorithm name and key metrics
- [ ] Add concise reasoning for why the winner was chosen
- [ ] Add a runner-up or trade-off summary when the second model is close
- [ ] Record caveats such as overfitting concerns, calibration issues, or metric limitations when that information is available
- [ ] Keep the summary structured enough for future agent consumption rather than only prose
- [ ] Include enough text-ready summary content for the reviewer agent to explain:
  - what was tested
  - why the winner was chosen
  - the key results
  - important caveats or trade-offs

## 2h. Final Return Shape

- [ ] Return `rankings`
- [ ] Return `winner`
  Expected: winner should be available as a simple scalar algorithm name in addition to any richer nested winner details
- [ ] Return `runner_up` or include runner-up data within the ranking summary
- [ ] Return `ground_truth_comparison`
- [ ] Return `shap_results`
- [ ] Return `shap_artifacts`
- [ ] Return enough algorithm-level metadata to support later agents without forcing them to inspect raw model objects
- [ ] Return a compact `reviewer_summary` or equivalent prompt-safe summary if the full evaluation payload includes large nested structures
- [ ] Ensure the state-facing evaluation payload avoids raw PNG bytes in the portion likely to be passed into `agents/reviewer.py`
- [ ] Return an `mlflow_payload` or equivalently named logging bundle for future workflow integration
  Expected contents: loggable metrics, tags, params/context summary, and artifact descriptors/content that a later MLflow step can consume directly
- [ ] Define the loggable metrics included in `mlflow_payload`
- [ ] Define the tags included in `mlflow_payload`
- [ ] Define the context/params summary included in `mlflow_payload`
- [ ] Define the artifact descriptor records included in `mlflow_payload`
- [ ] Define how artifact content is attached or referenced within `mlflow_payload`
- [ ] Define stable metric/tag names now so later MLflow integration does not require renaming the evaluation outputs
  Expected candidates: winner algorithm, primary metric, runner-up, has_ground_truth, shap_available, and evaluation phase/status
- [ ] Confirm the final dict is JSON-serializable except for expected artifact byte payloads

## 2i. Tests

- [ ] Decide the Step 2 test target file
  Expected candidate: `tests/unit/test_evaluation_workflow.py`
- [ ] Add or update focused tests for ranking behavior
- [ ] Add or update focused tests for ground-truth comparison behavior
- [ ] Add or update focused tests for missing `true_prob_test`
- [ ] Add or update focused tests for SHAP explainer selection
- [ ] Add or update focused tests for SHAP output normalization across explainer return types
- [ ] Add or update focused tests for tie-breaking or near-tie winner selection
- [ ] Add or update focused tests for final return shape
- [ ] Add or update focused tests for the MLflow-ready output contract
  Expected: confirm state summary and logging bundle stay separate and structurally stable
- [ ] Add a test that state-facing evaluation output excludes raw PNG bytes
- [ ] Add a test that `reviewer_summary` stays compact and serializable
- [ ] Add a test that `mlflow_payload` contains the expected sections
- [ ] Add a test that artifact filenames and logging keys are stable
- [ ] Mock or stub expensive SHAP operations where needed so tests stay fast and deterministic

## 2j. Validation

- [ ] Run the targeted test selection for the Step 2 workflow
- [ ] Run at least one realistic happy-path evaluation invocation with mocked SHAP internals if full SHAP computation is too expensive for routine tests
- [ ] Review the MLflow-ready bundle to confirm a later workflow step could log it without reshaping
- [ ] Review the final diff for architecture fit
- [ ] Confirm no new dependency was introduced
- [ ] Confirm no new script, notebook, or entrypoint was added
- [ ] Update any parent Step 2 checklist if you create one later for sub-steps
- [ ] Prepare a commit only after Step 2 is a complete reviewable unit
