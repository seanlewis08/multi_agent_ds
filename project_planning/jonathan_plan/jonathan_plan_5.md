# Jonathan Plan Step 5 Checklist

Source: [Jonathan_Plan.md](/Users/jonathan.chia/code/multi_agent_ds/project_planning/Jonathan_Plan.md)

## Step 5: Integration Testing + Graph Wiring

- [x] Confirm Step 5 scope against `project_planning/Jonathan_Plan.md`
- [x] Confirm Step 5 is aligned with `project_planning/ARCHITECTURE.md`
  Expected layer ownership: `orchestration/graph.py` and `orchestration/router.py` own runtime wiring, `agents/` own node behavior, `workflows/` own multi-step side-effectful workflows, and tests validate the full runtime path without relocating business logic
  Confirmed: Step 5 is primarily an orchestration/runtime integration step. Graph node wiring belongs in `orchestration/`, node behavior stays in existing `agents/` and `workflows/` modules, and tests should validate the runtime path without moving business logic across layers.
- [x] Confirm exact file targets for Step 5 changes
  Expected primary targets:
  - `src/multi_agent_ds/orchestration/graph.py`
  - `src/multi_agent_ds/orchestration/router.py`
  - `src/multi_agent_ds/orchestration/state.py` only if the existing state keys are insufficient
  - existing Step 4/Step 2/Step 1 runtime modules only if graph integration exposes a contract mismatch
  Expected test targets:
  - prefer existing orchestrator/runtime test files first
  - use `tests/integration/` only if a graph-level test cannot fit the current test surface cleanly
  Confirmed primary Step 5 targets:
  - `src/multi_agent_ds/orchestration/graph.py`
  - `src/multi_agent_ds/orchestration/router.py`
  Likely supporting targets only if the graph integration exposes a contract mismatch:
  - `src/multi_agent_ds/orchestration/state.py`
  - `src/multi_agent_ds/agents/orchestrator.py`
  - `src/multi_agent_ds/workflows/evaluation.py`
  - `src/multi_agent_ds/agents/reviewer.py`
  - `src/multi_agent_ds/agents/report_writer.py`
  - `src/multi_agent_ds/agents/business_stakeholder.py`
  Expected test targets:
  - `tests/test_orchestrator.py`
  - existing report/reviewer/evaluation tests where possible
  - `tests/integration/` only if a true graph-level test cannot fit the current test surface
- [x] Confirm whether Step 5 can stay inside existing runtime/orchestration files or whether any additional supporting edit is required
- [x] Confirm no new dependency is needed
- [x] Confirm Step 5 still respects Jonathan's "No new files" expectation
  Current bias: prefer extending `graph.py`, `router.py`, and existing tests before introducing any new test module
  Decision:
  - Step 5 can stay inside existing runtime/orchestration files for the core graph-wiring work
  - no new dependency is needed for the current Step 5 scope
  - Jonathan's "No new files" expectation should be treated as a runtime-code constraint:
    - prefer editing `graph.py`, `router.py`, and existing tests
    - avoid creating new wrappers, scripts, or ad hoc runtime entrypoints unless a gap proves unavoidable

## Current Baseline To Plan Against

- [x] Record the actual current runtime baseline before Step 5 implementation
  Current repo reality to plan around:
  - `src/multi_agent_ds/orchestration/graph.py` already wires raw EDA, preparation, processed-data approval, and the reviewed modeling loop
  - the graph still terminates after `ml_reviewer_final_recommendation_review`
  - `src/multi_agent_ds/orchestration/router.py` already owns prep-loop, modeling-loop, and report-review loop routing helpers
  - `src/multi_agent_ds/agents/orchestrator.py` is now implemented and returns machine-readable workflow-entry, downstream-sequence, blocked-state, and loop/stop decisions
  - `src/multi_agent_ds/workflows/evaluation.py` is implemented
  - `src/multi_agent_ds/agents/reviewer.py` is implemented and supports `dry_run`
  - `src/multi_agent_ds/agents/report_writer.py` is implemented
  - `src/multi_agent_ds/agents/business_stakeholder.py` already supports `mode="report_review"`
  - `config/workflows.yaml` now declares `post_model_sequence` and `baseline_only`
  - Step 4 intentionally did not wire evaluation/reviewer/report nodes into the graph
- [x] Record the key Step 5 gap explicitly
  Expected current gap:
  - runtime graph wiring is missing for:
    - evaluation
    - reviewer
    - report generation
    - business stakeholder report review
  - post-evaluation loop-back wiring is also still missing
- [x] Record any Step 5 items that are blocked by unfinished upstream work
  Current likely blockers to verify:
  - Jonathan's separate runtime ML modeler variant is not yet registered as a distinct graph node
  - end-to-end real GitHub PR creation should remain gated behind `dry_run` or explicit environment readiness
  Confirmed Step 5 baseline:
  - `graph.py` currently handles:
    - raw EDA fan-out
    - preparation loop
    - processed-data approval
    - reviewed modeling loop
  - `router.py` already provides:
    - prep-loop routing
    - modeling-loop routing
    - report-review loop routing
  - `orchestrator.py` now provides:
    - workflow entry (`full_pipeline` vs `baseline_only`)
    - `entry_node`
    - `modeler_variant`
    - `downstream_sequence`
    - blocked-state and loop/stop payloads
  - `config/workflows.yaml` declares the intended post-model sequence, but `graph.py` does not yet consume it
  - the concrete Step 5 graph gap is:
    - no evaluation node wrapper after modeling
    - no reviewer node after evaluation
    - no report-writer node after reviewer
    - no business stakeholder `report_review` node after report generation
    - no post-evaluation loop-back edge when evaluation says retry modeling
  - Step 5 is also partially blocked by current runtime-variant reality:
    - `config/agents.yaml` and `orchestrator.py` can name `jonathan` as a modeler variant
    - but `src/multi_agent_ds/agents/ml_modeler.py` still only implements Sean's runtime path and prompt family (`sean_ml_modeler`)
    - so a true side-by-side Sean-vs-Jonathan runtime graph comparison is not fully implementable yet
  - real GitHub PR creation remains environment-gated and should stay behind reviewer `dry_run` for automated Step 5 testing

## 5a. Prep And Context Review

- [x] Read `src/multi_agent_ds/orchestration/graph.py` end to end and list the current terminal nodes
- [x] Read `src/multi_agent_ds/orchestration/router.py` end to end and list reusable routing helpers versus missing post-modeling helpers
- [x] Read `src/multi_agent_ds/orchestration/state.py` to confirm whether Step 5 can stay within the current `PipelineState`
- [x] Read `src/multi_agent_ds/agents/orchestrator.py` to confirm the Step 4 handoff contract that Step 5 must honor
- [x] Read `src/multi_agent_ds/workflows/evaluation.py` to confirm the callable workflow interface and return shape
- [x] Read `src/multi_agent_ds/agents/reviewer.py` to confirm:
  - required state inputs
  - `dry_run` behavior
  - PR metadata outputs
- [x] Read `src/multi_agent_ds/agents/report_writer.py` to confirm required inputs and returned fields
- [x] Read `src/multi_agent_ds/agents/business_stakeholder.py` to confirm the `report_review` mode contract
- [x] Read `config/workflows.yaml` and `config/agents.yaml` to verify the Step 4 config contract that Step 5 must consume rather than replace
- [x] Read the current relevant tests before changing graph wiring
  Expected existing test anchors:
  - `tests/test_orchestrator.py`
  - any report/reviewer/evaluation runtime tests already present
  Confirmed prep/context findings:
  - current graph terminal nodes:
    - `end` after `eda_processed_approval` when prep is rejected too many times
    - `end` after `ml_reviewer_final_recommendation_review`
  - reusable router helpers already present:
    - `route_after_raw_eda`
    - `route_after_prep_plan`
    - `route_after_data_engineer_feedback`
    - `route_after_data_engineer_execute`
    - `route_after_processed_eda`
    - `route_after_processed_approval`
    - `route_after_modeling_handoff`
    - `route_after_modeling_review`
    - `route_after_business_review`
  - missing router coverage for Step 5:
    - post-modeling route into evaluation
    - post-evaluation route into reviewer or loop-back to modeling
    - post-reviewer route into report generation
    - post-report route into business stakeholder report review
  - current `PipelineState` already contains the main Step 5 runtime fields:
    - `modeling_verdict`
    - `evaluation_result`
    - `report_draft`
    - `experiment_report`
    - `business_review`
    - `should_loop`
    - `should_revise_modeling`
    - `should_revise_report`
    - `iteration`
    - `modeling_iteration`
    - `report_iteration`
    Step 5 should try to stay within this schema unless the graph wrapper nodes expose a real gap.
  - Step 4 orchestrator contract that Step 5 must honor:
    - `selected_workflow`
    - `entry_node`
    - `modeler_variant`
    - `downstream_sequence`
    - blocked-state / loop-state fields including `next_agent`, `should_loop`, `loop_from`, `blocked_on`, `stop_reason`
  - evaluation workflow interface is already stable:
    - `run_evaluation_workflow(results, data, settings) -> dict`
    - returns `evaluation_result`, `reviewer_summary`, `shap_results`, `shap_artifacts`, `mlflow_payload`
  - reviewer agent contract is already stable and includes `dry_run`
  - report writer returns `experiment_report`, `report_draft`, `current_phase`, and `report_iteration`
  - business stakeholder `mode="report_review"` returns:
    - `business_review`
    - `should_revise_report`
    - `should_revise_modeling`
    - `current_phase: report_review`
  - current test anchors already in repo:
    - `tests/test_orchestrator.py`
    - `tests/test_langgraph_graph.py`
    - `tests/test_langgraph_router.py`
    - `tests/test_report_business_review.py`
    - `tests/unit/test_reviewer.py`
    - `tests/unit/test_evaluation_workflow.py`

## 5b. Graph Wiring Contract

- [x] Define the exact node set Step 5 must add to the runtime graph
  Expected current candidates:
  - evaluation node wrapper
  - reviewer node
  - report writer node
  - business stakeholder report-review node
- [x] Decide whether evaluation should be represented as:
  - a graph node that calls `workflows/evaluation.py`
  - a special orchestration wrapper node
  - or some other existing runtime boundary
  Expected bias: keep evaluation workflow-owned and wrap it minimally for the graph
- [x] Define the exact post-modeling sequence to wire into `graph.py`
  Expected default:
  - modeling final recommendation review
  - evaluation
  - reviewer
  - report generation
  - business stakeholder report review
- [x] Define the graph entry behavior for:
  - `full_pipeline`
  - `baseline_only`
- [x] Decide how the graph should consume `selected_workflow`, `entry_node`, and `downstream_sequence` from the orchestrator contract
- [x] Confirm whether the orchestrator node itself must be inserted into the graph in Step 5 or remain an external selector
- [x] Define the exact graph terminal conditions after report review and after accepted loop-stop outcomes
  Graph-wiring contract decided:
  - Step 5 should add these runtime graph nodes after the existing modeling loop:
    - `evaluation`
    - `reviewer`
    - `report_writer`
    - `business_stakeholder_report_review`
  - evaluation should stay workflow-owned:
    - the graph node should be a thin orchestration wrapper around `workflows/evaluation.py`
    - do not move evaluation logic into `graph.py` or `router.py`
  - the default post-modeling runtime sequence should be:
    - `ml_reviewer_final_recommendation_review`
    - `evaluation`
    - `reviewer`
    - `report_writer`
    - `business_stakeholder_report_review`
  - graph entry behavior should stay aligned with the Step 4 contract:
    - `full_pipeline` enters at `eda_raw`
    - `baseline_only` enters at `ml_modeler_handoff`
  - the graph should consume the orchestrator contract by honoring:
    - `entry_node` for initial graph entry selection
    - `downstream_sequence` as the intended post-model path
    - `selected_workflow` only as coordination/debug metadata, not as a second routing DSL inside the graph
  - the orchestrator node itself should remain an external selector in Step 5:
    - do not insert it as a LangGraph runtime node in this slice
    - use its payload to choose the graph entry and to define what the graph wiring must support
  - Step 5 graph terminal conditions should be:
    - accepted business report review -> `END`
    - report/modeling revise outcomes continue into the existing bounded loops
    - explicit loop-stop outcomes from post-evaluation routing continue forward rather than creating a second hidden terminal path
  Implemented 5b slice:
  - `graph.py` now registers these runtime nodes:
    - `evaluation`
    - `reviewer`
    - `report_writer`
    - `business_stakeholder_report_review`
  - `build_graph()` now accepts an `entry_node` argument so the graph can compile from:
    - `eda_raw` for `full_pipeline`
    - `ml_modeler_handoff` for `baseline_only`
  - the evaluation node is intentionally only a structural wrapper in this slice:
    - it is registered in the graph
    - its actual workflow invocation contract is still deferred to Step 5d
  - no post-modeling edges were added yet; those remain part of Step 5c
  Verified by:
  - `uv run pytest tests/test_langgraph_graph.py`
  - current result: `17 passed`

## 5c. Router And Transition Logic

- [x] Decide whether new routing helpers are required after modeling, after evaluation, after reviewer, and after report generation
- [x] Reuse existing router helpers wherever the graph already has the needed logic
- [x] Define the post-modeling route from final modeling review to evaluation
- [x] Define the post-evaluation route:
  - to reviewer when continuing forward
  - back to modeling when the orchestrator loop contract says to retry
- [x] Define the post-reviewer route to report generation
- [x] Define the post-report route to business stakeholder report review
- [x] Reuse or adapt `route_after_business_review()` for final report acceptance / revise-report / revise-modeling behavior
- [x] Define iteration-cap behavior when report or modeling loops are already exhausted
- [x] Keep router behavior machine-readable and config-driven where the repo already expects that
  Implemented router/transition slice:
  - `route_after_modeling_review()` now advances `final_recommendation` to `evaluation` instead of `end`
  - new router helpers added:
    - `route_after_evaluation()`
    - `route_after_reviewer()`
    - `route_after_report_generation()`
  - `route_after_evaluation()` uses the existing orchestrator-style loop fields:
    - `should_loop`
    - `loop_from`
    and otherwise advances to `reviewer`
  - `route_after_reviewer()` advances to `report_writer`
  - `route_after_report_generation()` advances to `business_stakeholder_report_review`
  - `route_after_business_review()` was reused unchanged for:
    - accept -> `end`
    - revise_report -> `report_writer`
    - revise_modeling -> `ml_modeler_baseline`
    with the existing bounded-cap behavior still intact
  - `graph.py` now wires these post-model transitions:
    - `ml_reviewer_final_recommendation_review` -> `evaluation`
    - `evaluation` -> `reviewer` or `ml_modeler_baseline`
    - `reviewer` -> `report_writer`
    - `report_writer` -> `business_stakeholder_report_review`
    - `business_stakeholder_report_review` -> `end`, `report_writer`, or `ml_modeler_baseline`
  Verified by:
  - `uv run pytest tests/test_langgraph_router.py tests/test_langgraph_graph.py`
  - current result: `42 passed`

## 5d. Graph Node Wrappers And State Flow

- [x] Define the graph wrapper node for evaluation without moving evaluation logic out of `workflows/evaluation.py`
- [x] Decide how the evaluation node pulls its inputs from state
  Expected current inputs:
  - modeling results
  - prepared data artifacts or data payload
  - settings
- [x] Decide how the evaluation node writes outputs back into state
  Expected fields:
  - `evaluation_result`
  - `reviewer_summary`
  - `shap_results`
  - `shap_artifacts`
  - `mlflow_payload`
- [x] Confirm reviewer node state flow after evaluation
- [x] Confirm report writer node state flow after reviewer
- [x] Confirm business stakeholder report-review node state flow after report generation
- [x] Verify that state updates remain compatible with the current `PipelineState` without forcing a broad schema rewrite
- [x] Add state fields only if the graph cannot be wired cleanly without them
  Implemented notes:
  - `graph.py` now delegates the `evaluation` node directly to `workflows.evaluation.run_evaluation_from_state(...)`
  - `run_evaluation_from_state(...)` reconstructs workflow inputs from runtime state by:
    - preferring `processed_data_path`
    - then `modeling_context.processed_data_path`
    - then `data_path`
    - then existing-data `settings.data.existing.uri`
  - the workflow wrapper reconstructs split evaluation data with the current model settings:
    - `test_size`
    - `validation_size`
    - `random_state`
    - configured target column
  - nested `modeling_results` phase buckets are flattened into the latest fitted per-algorithm result before calling `run_evaluation_workflow(...)`
  - the evaluation node now writes back:
    - `evaluation_result`
    - `reviewer_summary`
    - `shap_results`
    - `shap_artifacts`
    - `mlflow_payload`
    - `current_phase: "evaluation"`
    - appended `agent_decisions`
    - `should_loop: False`
    - `loop_from: None`
  - a targeted `PipelineState` expansion was required once the graph-level happy path was exercised, so the runtime graph now preserves:
    - `reviewer_summary`
    - `shap_results`
    - `shap_artifacts`
    - `mlflow_payload`
    - reviewer dry-run / PR planning fields such as `branch_name`, `staged_paths`, `pr_metadata`, and related metadata
    - `loop_from` for post-evaluation loop-back compatibility
  - verification:
    - `uv run pytest tests/test_langgraph_graph.py tests/unit/test_evaluation_workflow.py`
    - `uv run pytest tests/unit/test_reviewer.py tests/test_report_business_review.py`

## 5e. Contract Compliance Checks

- [x] Verify agent contract compliance at each runtime node boundary
  Expected checks:
  - EDA nodes produce the review payloads downstream nodes expect
  - modeling nodes still produce `modeling_verdict`
  - evaluation node produces the Step 2 contract
  - reviewer node produces PR metadata / dry-run metadata
  - report writer produces `experiment_report`
  - business review produces `business_review`, `should_revise_report`, `should_revise_modeling`
- [x] Verify state fields flow correctly between graph nodes
- [x] Verify no node now depends on prose-only fields when machine-readable fields already exist
- [x] Verify graph wiring does not bypass the Step 4 orchestrator contract silently
  Implemented notes:
  - EDA and preparation contracts remain unchanged; existing graph/router tests still cover the pre-modeling handoff path
  - modeling still terminates in a machine-readable `modeling_verdict`, and the post-model edge now advances into `evaluation` instead of silently ending
  - the `evaluation` node now returns the Step 2 state contract:
    - `evaluation_result`
    - `reviewer_summary`
    - `shap_results`
    - `shap_artifacts`
    - `mlflow_payload`
  - the `reviewer` node remains the owner of PR planning / creation behavior and already returns:
    - dry-run PR metadata for automated paths
    - commit / PR metadata for real execution paths
  - the `report_writer` node still produces:
    - `experiment_report`
    - `report_draft`
    - report-phase `agent_decisions`
  - the business stakeholder report review still produces:
    - `business_review`
    - `should_revise_report`
    - `should_revise_modeling`
  - the new Step 5 graph wiring stays aligned with the Step 4 orchestrator contract rather than replacing it:
    - orchestrator still selects `entry_node`
    - graph entry still respects `full_pipeline -> eda_raw`
    - graph entry still respects `baseline_only -> ml_modeler_handoff`
    - the graph does not embed a new internal orchestrator node
  - the post-model runtime path uses structured routing fields, not prose-only summaries:
    - `should_loop`
    - `loop_from`
    - `current_phase`
    - `evaluation_result`
    - `business_review`
  - verification:
    - `uv run pytest tests/test_orchestrator.py`
    - `uv run pytest tests/test_langgraph_router.py tests/test_langgraph_graph.py`
    - `uv run pytest tests/unit/test_evaluation_workflow.py`
    - `uv run pytest tests/unit/test_reviewer.py tests/test_report_business_review.py`

## 5f. Experiment PR Flow Validation

- [x] Decide whether Step 5 integration tests should default to `reviewer.dry_run=True`
  Expected bias: yes for automated tests, unless a deliberate real-GitHub/manual test is being run
- [x] Define the exact dry-run state assertions for the reviewer stage
  Expected checks:
  - branch name shape
  - staged paths
  - commit message
  - PR title/body
  - `pr_metadata` payload
- [x] Decide how to validate changed-file staging without performing real git side effects in automated tests
- [x] Decide whether a real PR creation smoke test is in scope for Step 5 or remains a manual/human-gated validation step
- [x] If a manual real-PR validation is kept, document the exact prerequisites and keep it out of the automated test path
  Implemented notes:
  - automated Step 5 reviewer-path tests should default to `dry_run=True`
  - automated tests should validate the reviewer stage through the returned dry-run plan payload, not through real git index inspection
  - exact dry-run assertions are now pinned by `tests/unit/test_reviewer.py`:
    - branch name shape
    - staged paths
    - commit message
    - PR title
    - PR body
    - base branch
    - `pr_metadata`
    - absence of git side effects (`commit_sha`, `pr_number`, `pr_url` remain `None`)
  - changed-file staging is validated by asserting `staged_paths` in the dry-run result, not by performing real `git add` in automated tests
  - real GitHub PR creation remains out of automated Step 5 scope and should stay a manual, human-gated validation
  - manual real-PR prerequisites:
    - clean disposable repo or throwaway branch
    - valid OpenAI settings / API key for reviewer PR text generation
    - authenticated `gh` session with push + PR permissions
    - explicit `dry_run=False`
    - acceptance that the run will create a real branch, commit, push, and PR
  - verification:
    - `uv run pytest tests/unit/test_reviewer.py`

## 5g. MLflow Integration Validation

- [x] Confirm what MLflow integration already exists in `workflows/modeling.py`
- [x] Define whether Step 5 must add any graph-time MLflow wiring or only validate that the current workflow-owned logging still works
- [x] Verify that nested runs and artifact logging still work when the graph invokes the evaluation/report path after modeling
- [x] Decide whether Step 5 should log evaluator/reviewer/report artifacts directly or keep that deferred
  Expected bias: validate current MLflow behavior first; add new logging only if the current graph integration requires it
- [x] Confirm that Step 2's `mlflow_payload` can flow through state without breaking graph execution
  Implemented notes:
  - current real MLflow side effects are owned by `workflows/modeling.py`, which already handles:
    - experiment setup
    - parent run creation
    - nested child runs per algorithm / phase
    - metric logging
    - model logging
    - artifact logging
    - export-bundle generation
  - Step 5 graph runtime does not call `run_modeling_workflow(...)`; it uses the agentic modeling graph instead, so Step 5 should not try to duplicate or relocate modeling MLflow behavior into the graph layer
  - evaluation continues to expose an MLflow-ready payload only:
    - `metrics`
    - `params`
    - `tags`
    - `context`
    - `artifacts`
  - Step 5 therefore keeps evaluator / reviewer / report MLflow logging deferred rather than adding new graph-time side effects
  - `mlflow_payload` already flows through runtime state without breaking graph execution because:
    - the evaluation node returns it as part of the Step 2 contract
    - downstream report/reviewer tests still pass with the post-evaluation graph wiring in place
    - no downstream node requires raw MLflow objects
  - validation note:
    - an attempted local re-run of `tests/test_modeling_export.py` and `tests/unit/test_evaluation_workflow.py` hit a machine-level LightGBM `libomp.dylib` load failure during import
    - this is an environment dependency issue, not a Step 5 contract regression
    - earlier Step 5 validation already confirmed the evaluation / graph / reviewer / report path itself

## 5h. Sean Vs Jonathan Modeler Comparison Gate

- [x] Confirm whether both runtime modeler variants actually exist as separate callable graph/runtime nodes today
- [x] If not, record that Step 5 cannot fully execute Jonathan's comparison requirement yet
- [x] Decide whether Step 5 should:
  - wire only the current active variant
  - add variant-selection plumbing only
  - or stop and defer the true side-by-side comparison until Jonathan's runtime modeler exists
- [x] If variant comparison is partially implementable now, define the smallest non-misleading validation path
- [x] Keep the plan explicit about what is fully testable now versus what remains blocked by missing runtime variant implementation
  Implemented notes:
  - the runtime currently exposes exactly one callable modeler node:
    - `src/multi_agent_ds/agents/ml_modeler.py::ml_modeler_node(...)`
  - that runtime node is still hard-wired to Sean's prompt/config surface:
    - it loads `prompts["sean_ml_modeler"]`
    - it does not branch on `modeler_variant`
    - there is no separate Jonathan-owned runtime modeler module or graph node
  - Step 4's variant work is therefore currently limited to orchestration/config plumbing:
    - `config/agents.yaml` exposes `active_variant` and `supported_variants`
    - `orchestrator.py` resolves and returns `modeler_variant`
  - Step 5 cannot honestly claim a true Sean-vs-Jonathan runtime comparison yet
  - the correct Step 5 behavior is:
    - wire only the current active runtime variant
    - preserve the variant-selection plumbing
    - explicitly defer the real side-by-side runtime comparison until a Jonathan runtime modeler actually exists
  - the smallest non-misleading validation path right now is:
    - verify `modeler_variant` still flows through orchestrator decisions
    - verify graph entry and post-model routing do not break when the selected variant is `jonathan`
    - do not claim that the runtime modeler behavior changes, because it does not
  - what is fully testable now:
    - config-driven variant selection metadata
    - orchestrator return payloads
    - graph wiring around the existing single runtime modeler
  - what remains blocked:
    - a true side-by-side runtime comparison
    - Jonathan-specific runtime prompts / behavior
    - separate runtime-node invocation paths by variant

## 5i. End-To-End Test Plan

- [x] Define the minimum automated graph-integration test path
  Expected flow:
  - orchestrator/workflow selection
  - graph execution through modeling
  - evaluation wrapper
  - reviewer dry run
  - report generation
  - business report review
- [x] Define the minimum realistic invocation payload for end-to-end graph tests
- [x] Decide whether that test should:
  - mock LLM adapters
  - mock git/GitHub side effects
  - use lightweight fixture data
  - or combine these approaches
- [x] Define a second test path for `baseline_only`
- [x] Define the minimal manual runbook for a human-triggered end-to-end test outside pytest
- [x] Keep the end-to-end tests bounded so Step 5 does not become an environment-dependent integration slog
  Implemented notes:
  - the minimum automated graph-integration path should be one graph-level happy path with:
    - orchestrator selecting the workflow / entry node
    - graph advancing through the existing modeling terminal handoff
    - evaluation wrapper execution
    - reviewer `dry_run`
    - report generation
    - business stakeholder report review
  - the minimum realistic invocation payload for that test should include:
    - `settings`
    - `workflow_config`
    - `agents_config`
    - `data` or a lightweight reconstructed evaluation payload
    - `modeling_results`
    - `modeling_verdict`
    - any control fields needed for post-evaluation routing
  - the automated end-to-end test should combine:
    - mocked LLM adapters
    - mocked git / GitHub side effects
    - lightweight fixture data
    - real router + graph transitions
  - a second automated path should cover `baseline_only`:
    - graph entry at `ml_modeler_handoff`
    - same downstream evaluation -> reviewer(dry_run) -> report -> business review path
  - the manual human-triggered runbook should stay outside pytest and require:
    - environment-ready LLM credentials
    - `gh` authentication if real reviewer PR creation is desired
    - disposable repo / branch for `dry_run=False`
    - willingness to accept graph-driven side effects
  - the Step 5 end-to-end tests should stay bounded by:
    - preferring one mocked graph-level happy path over a broad environment-dependent suite
    - not requiring real GitHub, real MLflow UI validation, or real multi-variant modeler comparison
    - keeping full manual smoke tests separate from automated pytest

## 5j. Tests

- [x] Decide the exact Step 5 test targets before implementation
  Expected bias:
  - extend existing tests first
  - use `tests/integration/` only for the graph-level path that cannot fit unit-style tests
- [x] Add or update focused tests for graph-node contract compliance
- [x] Add or update focused tests for post-modeling graph transitions
- [x] Add or update focused tests for reviewer dry-run graph behavior
- [x] Add or update focused tests for report-review loop behavior after graph wiring
- [x] Add or update focused tests for `baseline_only` graph entry
- [x] Add or update focused tests for missing/partial state at the new graph boundaries
- [x] Add or update focused tests for blocked or deferred Sean-vs-Jonathan comparison behavior if that remains in scope
- [x] Keep automated tests isolated from real GitHub side effects unless the user explicitly asks for a real end-to-end run
  Implemented notes:
  - Step 5 test targets stayed inside existing files:
    - `tests/test_langgraph_graph.py`
    - `tests/test_langgraph_router.py`
    - `tests/test_orchestrator.py`
  - new / updated coverage now includes:
    - graph-node contract compliance for the `evaluation` wrapper
    - full post-model routing transitions
    - a mocked graph-level `baseline_only` happy path through:
      - modeling handoff
      - evaluation
      - reviewer dry run
      - report generation
      - business report review acceptance
    - preservation of reviewer dry-run metadata through the graph state
    - missing-state failure at the new evaluation boundary
    - blocked/deferred variant behavior remains covered through existing orchestrator tests
  - automated tests remain isolated from real git / GitHub side effects by using mocked reviewer dry-run behavior
  - verification:
    - `uv run pytest tests/test_langgraph_graph.py tests/test_langgraph_router.py tests/test_orchestrator.py`
    - current result: `65 passed`

## 5k. Validation

- [x] Run the targeted Step 5 tests
- [x] Review graph and router diffs for architecture fit and minimalism
- [x] Confirm no new dependency was introduced
- [x] Confirm no new script, notebook, or entrypoint was added
- [x] Confirm Step 5 remains a reviewable unit separate from future runtime polishing
- [x] Record any still-blocked Step 5 acceptance criteria explicitly
- [x] Prepare a commit only after Step 5 is a complete reviewable unit
  Validation notes:
  - targeted Step 5 validation suite:
    - `uv run pytest tests/test_orchestrator.py tests/test_langgraph_router.py tests/test_langgraph_graph.py tests/unit/test_evaluation_workflow.py tests/unit/test_reviewer.py tests/test_report_business_review.py`
    - current result: `108 passed`
  - architecture/minimalism review:
    - Step 5 stayed concentrated in:
      - `orchestration/graph.py`
      - `orchestration/router.py`
      - `orchestration/state.py`
      - the evaluation workflow wrapper seam in `workflows/evaluation.py`
      - existing test files
    - no business logic was moved out of existing agents/workflows just to satisfy graph wiring
  - no new dependency was introduced:
    - no `pyproject.toml` change
    - no new package dependency added for Step 5
  - no new script, notebook, or entrypoint was added
  - Step 5 remains a reviewable unit because it closes one coherent gap:
    - post-model graph wiring from modeling -> evaluation -> reviewer -> report -> business review
    - with supporting state preservation and bounded tests
  - still-blocked Step 5 acceptance criteria:
    - a true Sean-vs-Jonathan runtime modeler comparison is still blocked because there is only one callable runtime `ml_modeler` implementation today
    - real GitHub PR creation remains intentionally outside automated Step 5 validation and should stay manual / human-gated
    - graph-time MLflow side effects for evaluation / reviewer / report remain deferred; Step 5 preserves the current workflow-owned MLflow boundary instead
