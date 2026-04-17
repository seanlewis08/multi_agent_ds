# Jonathan Plan Step 4 Checklist

Source: [Jonathan_Plan.md](/Users/jonathan.chia/code/multi_agent_ds/project_planning/Jonathan_Plan.md)

## Step 4: Orchestrator Agent

- [x] Confirm Step 4 scope against `project_planning/Jonathan_Plan.md`
- [x] Confirm Step 4 is aligned with `project_planning/ARCHITECTURE.md`
  Expected layer ownership: orchestration owns the graph, `agents/orchestrator.py` owns top-level workflow decisions, and configs own role/sequence definitions
  Confirmed: Step 4 belongs primarily in the agent/config/orchestration boundary already described by the architecture docs. `agents/orchestrator.py` should own top-level runtime decisions, while `orchestration/graph.py` and `router.py` remain the graph/routing owners.
- [x] Confirm exact file targets for Step 4 changes
  Expected primary targets:
  - `src/multi_agent_ds/agents/orchestrator.py`
  - `config/agents.yaml`
  - `config/workflows.yaml`
  Confirmed primary targets for the first Step 4 slice:
  - `src/multi_agent_ds/agents/orchestrator.py`
  - `config/agents.yaml`
  - `config/workflows.yaml`
  Possible supporting targets if the contract cannot fit cleanly without them:
  - `src/multi_agent_ds/orchestration/graph.py`
  - `src/multi_agent_ds/orchestration/router.py`
  - `src/multi_agent_ds/orchestration/state.py`
- [x] Confirm whether Step 4 should stay isolated to the orchestrator/config layer or whether any supporting edit is required in `orchestration/graph.py`, `orchestration/router.py`, or `orchestration/state.py`
- [x] Confirm no new dependency is needed
  Expected: use existing config loading, existing state object, and current LangGraph skeleton/adapters
  Decision: start in the orchestrator/config layer first. Supporting graph/router/state edits may be needed later, but they should follow the orchestrator contract rather than precede it. No new dependency is needed.
- [x] Confirm which Step 4 prerequisites are already present versus still placeholders
  Expected dependencies to inspect:
  - `src/multi_agent_ds/agents/orchestrator.py`
  - `config/agents.yaml`
  - `config/workflows.yaml`
  - `src/multi_agent_ds/orchestration/graph.py`
  - `src/multi_agent_ds/orchestration/state.py`
  - currently implemented agent nodes (`reviewer`, modeling-related agents, report path if present)
  Confirmed:
  - `src/multi_agent_ds/agents/orchestrator.py` is still a placeholder
  - `config/agents.yaml` is implemented
  - `config/workflows.yaml` is implemented
  - `src/multi_agent_ds/orchestration/graph.py` is implemented through the preparation and modeling-loop stages
  - `src/multi_agent_ds/orchestration/state.py` already contains the core workflow-control fields
  - `src/multi_agent_ds/workflows/evaluation.py` is implemented
  - `src/multi_agent_ds/agents/reviewer.py` is implemented
  - `src/multi_agent_ds/agents/report_writer.py` is implemented
  - graph wiring after the modeling loop is still incomplete
- [x] Decide the minimum Step 4 implementation slice if dependencies are incomplete
  Expected bias: build the orchestrator node around the current pre-modeling graph and already-built reviewer/evaluation outputs, then keep unavailable-node handling explicit rather than inventing runtime steps that are not built yet
  Decision: the minimum Step 4 slice should define the `orchestrator_node(...)` contract, align agent/workflow config with that contract, and make the current post-modeling graph gap explicit. It should not try to finish full evaluation/reviewer/report graph integration in the same unit.

## Current Baseline To Plan Against

- [x] Record the actual current orchestrator baseline before implementation
  Current repo reality to plan around:
  - `src/multi_agent_ds/agents/orchestrator.py` is still a placeholder
  - `config/agents.yaml` is already populated and not a placeholder
  - `config/workflows.yaml` already describes the current EDA/preparation, modeling, and report-loop workflows and is not a placeholder
  - `src/multi_agent_ds/orchestration/graph.py` already wires the pre-modeling review/preparation flow plus the phased modeling loop
  - `src/multi_agent_ds/workflows/evaluation.py` is now implemented
  - `src/multi_agent_ds/agents/reviewer.py` is now implemented
  - `src/multi_agent_ds/agents/report_writer.py` now exists as the runtime report-writing agent
  - the current graph still ends after the modeling-review loop; evaluation, reviewer, report writer, and business report review are not yet graph-wired
  - `config/workflows.yaml` has `modeling` and `report` sections, but `full_pipeline` does not yet enumerate the post-modeling evaluation/reviewer/report path
- [x] Decide whether Step 4 should extend the current graph-first design or attempt to replace it
  Expected decision: extend the current graph-first design and let `orchestrator.py` choose or summarize workflow decisions at the top level, rather than replacing the existing `orchestration/graph.py` flow with a second parallel orchestrator
  Decision: extend the current graph-first design. The existing preparation and modeling graph is already substantial enough that Step 4 should complement it, not replace it.
- [x] Decide how to handle Jonathan's Step 4 references to placeholder configs now that those config files already contain repo-specific content
  Expected bias: merge the new orchestrator contract into the existing config shapes instead of rewriting them to match the idealized examples verbatim
  Decision: preserve the merged config shapes as the baseline and merge the orchestrator contract into them. Do not rewrite `config/agents.yaml` or `config/workflows.yaml` to mirror Jonathan’s original placeholder examples.

## 4a. Prep And Context Review

- [x] Read the current placeholder or implementation in `src/multi_agent_ds/agents/orchestrator.py`
  Confirmed: the file is still only `"""Orchestrator agent placeholder."""`
- [x] Read `src/multi_agent_ds/orchestration/state.py` to understand the current `PipelineState` contract
  Confirmed current orchestrator-relevant state fields already exist, including:
  - `data_path`
  - `settings`
  - `workflow_config`
  - `current_phase`
  - `should_loop`
  - `should_revise_modeling`
  - `should_revise_report`
  - `iteration`
  - `modeling_iteration`
  - `report_iteration`
  - `modeling_results`
  - `modeling_verdict`
  - `evaluation_result`
  - `business_review`
- [x] Read `src/multi_agent_ds/orchestration/graph.py` to understand existing node/edge wiring
  Confirmed: the graph already wires the raw/processed EDA review flow, preparation loop, modeling handoff, and phased modeling loop. It still terminates after `ml_reviewer_final_recommendation_review` and does not yet wire evaluation, reviewer, or report-stage nodes.
- [x] Read `src/multi_agent_ds/orchestration/router.py` if present to avoid duplicating routing logic in the orchestrator agent
  Confirmed: router helpers already own:
  - preparation loop routing
  - modeling review-loop routing
  - report-loop routing decisions
  Step 4 should not duplicate that detailed routing logic inside `agents/orchestrator.py`.
- [x] Read `config/agents.yaml` and `config/workflows.yaml` to confirm current placeholder shape or existing config loader expectations
  Confirmed: both files are already populated. `config/workflows.yaml` already contains `full_pipeline`, `eda_preparation`, `modeling`, and `report` sections.
- [x] Read `src/multi_agent_ds/core/config.py` for the exact config loading helpers already available
  Confirmed available helpers:
  - `load_settings()`
  - `load_agents_config()`
  - `load_prompts_config()`
  - `load_workflows_config()`
  No new config loader is needed for Step 4.
- [x] Read the currently implemented agent nodes that Step 4 will sequence
  Expected candidates:
  - `src/multi_agent_ds/agents/reviewer.py`
  - any existing `ml_modeler`, `eda_analyst`, `data_engineer`, `business_stakeholder`, or report-generation agent paths
  Confirmed implemented downstream/runtime agent paths relevant to Step 4 include:
  - `ml_modeler`
  - `eda_analyst`
  - `data_engineer`
  - `business_stakeholder`
  - `reviewer`
  - `report_writer`
- [x] Confirm which runtime agents named in Jonathan's Step 4 actually exist today versus which are still not built
- [x] Record the currently wired graph nodes versus merely configured runtime roles
  Expected current mismatch to capture:
  - graph nodes already exist for raw/processed EDA reviews and preparation loops
  - graph nodes already exist for the phased modeling loop
  - `reviewer` exists as an agent file but is not yet wired into `orchestration/graph.py`
  - `evaluation` exists as a workflow, not as an agent node
  - `report_writer` exists as a runtime agent, but report-stage graph wiring is not present in `orchestration/graph.py`
  - `business_stakeholder` supports `report_review`, but the report-review loop is not yet graph-wired
  Confirmed current wiring mismatch:
  - implemented graph nodes cover EDA, preparation, and modeling
  - `evaluation` is implemented as a workflow, not a graph node
  - `reviewer` exists but is not graph-wired
  - `report_writer` exists and `router.py` has report-loop logic, but `graph.py` does not yet wire the report stage
- [x] Decide the smallest initial Step 4 surface area
  Expected bias: keep workflow-selection and top-level phase/next-step decisions in `agents/orchestrator.py`; do not move orchestration policy into config loaders or tools, and do not duplicate the already-built preparation router logic
  Decision: the smallest Step 4 slice is to define an orchestrator contract that selects workflow/high-level next-phase behavior around the existing graph and explicitly represents the current post-modeling gap, without rewriting the current preparation/modeling routers.

## 4b. Orchestrator Interface Definition

- [x] Define `orchestrator_node(state: PipelineState) -> dict`
- [x] Define `orchestrator_node(state: PipelineState) -> dict`
  Implemented in `src/multi_agent_ds/agents/orchestrator.py` as a pure decision node that returns partial-state updates for workflow-entry, downstream-route, and blocked/pending orchestration states.
- [x] Document the expected orchestrator inputs from state
  Expected minimum inputs:
  - `settings`
  - `data_path` or equivalent data-source hint
  - any current phase / iteration / evaluation result fields needed for routing
  Confirmed minimum orchestrator inputs for the first slice:
  - `settings`
  - `data_path`
  - `workflow_config` when already loaded
  - `current_phase`
  - `iteration`
  - `modeling_verdict`
  - `evaluation_result`
  These are sufficient to support workflow entry decisions plus future post-modeling routing decisions.
- [x] Align the orchestrator inputs with the state fields that already exist in `PipelineState`
  Expected current fields to reuse:
  - `data_path`
  - `settings`
  - `workflow_config`
  - `current_phase`
  - `iteration`
  - `evaluation_result`
  - `modeling_results`
  - `modeling_verdict`
  - `processed_data_path`
  - `prep_approved`
  - `processed_eda_approved`
  - `should_revise_modeling`
  - `should_revise_report`
  - `modeling_iteration`
  - `report_iteration`
  Confirmed reusable state fields for Step 4:
  - required first-slice inputs: `settings`, `data_path`
  - optional first-slice inputs: `workflow_config`, `current_phase`, `iteration`
  - later-phase routing inputs already present: `modeling_results`, `modeling_verdict`, `evaluation_result`, `business_review`, `should_revise_modeling`, `should_revise_report`, `modeling_iteration`, `report_iteration`
- [x] Define which of those current state inputs are required versus optional for the first Step 4 slice
  Decision:
  - required for first-slice workflow entry: `settings`, `data_path`
  - optional for first-slice workflow entry: `workflow_config`, `current_phase`, `iteration`
  - optional but reserved for later downstream routing: `modeling_verdict`, `evaluation_result`, `business_review`, loop flags and counters
- [x] Define the minimum state assumptions for pre-graph workflow entry decisions
  Decision: assume only `settings`, `data_path`, and optionally `workflow_config`. The first-slice orchestrator should not require prior modeling or review outputs just to choose an entry workflow or entry node.
- [x] Define the minimum state assumptions for post-modeling / post-evaluation decisions
  Decision: assume `current_phase` plus whichever downstream artifact is available:
  - `modeling_verdict` for post-modeling decisions
  - `evaluation_result` for post-evaluation decisions
  - `business_review` for report-loop decisions
  Missing downstream artifacts should produce an explicit blocked/pending decision, not an implicit skip.
- [x] Document the orchestrator node's returned shape before implementation details
- [x] Document the orchestrator node's returned shape before implementation details
  Implemented top-level fields:
  - `selected_workflow`
  - `entry_node`
  - `decision_type`
  - `status`
  - `next_agent`
  - `loop_from`
  - `should_loop`
  - `stop_reason`
  - `blocked_on`
  - `blocked_reason`
  - `decision_summary`
  - `current_phase`
  - `agent_decisions`
- [x] Decide whether the node returns:
  - a `next_agent`
  - a selected workflow name
  - loop control fields
  - updated iteration / stop flags
  - or a combination of these
  Decision: the node should return a combination of:
  - workflow-selection fields for graph entry
  - next-step / blocked-state fields for downstream routing
  - minimal rationale and bookkeeping fields
- [x] Define a compact decision payload for graph/router consumption
  Expected bias: return explicit machine-readable routing fields, not only prose reasoning
  Decision: use an explicit machine-readable payload rather than prose parsing. The orchestrator should follow the repo’s existing pattern of returning partial state updates.
- [x] Define the machine-readable workflow-entry fields
  Expected candidates:
  - `selected_workflow`
  - `entry_node`
  - `decision_type`
  Decision: first-slice workflow-entry fields should be:
  - `selected_workflow`
  - `entry_node`
  - `decision_type` with values like `workflow_entry` or `downstream_route`
- [x] Define the machine-readable post-modeling / post-evaluation routing fields
  Expected candidates:
  - `next_agent`
  - `loop_from`
  - `should_loop`
  - `stop_reason`
  Decision: downstream-routing fields should include:
  - `next_agent`
  - `loop_from`
  - `should_loop`
  - `stop_reason`
  - `current_phase`
- [x] Define the blocked or pending-state return shape for unavailable downstream steps
  Expected candidates:
  - `status`
  - `blocked_on`
  - `blocked_reason`
  Decision: blocked/pending shape should include:
  - `status`
  - `blocked_on`
  - `blocked_reason`
  - `next_agent` set to `None` when appropriate
- [x] Decide whether the orchestrator should emit graph-entry guidance, post-modeling guidance, or both
  Expected bias: use one node contract that can support:
  - workflow entry selection before the existing graph runs
  - post-modeling / post-evaluation decisions after later graph expansion
  Decision: emit both, but keep the first implementation slice focused on graph-entry guidance plus explicit downstream placeholders so the contract does not need reshaping later.
- [x] Decide where human-readable orchestrator reasoning belongs
  Expected: short state-safe rationale field if useful, but routing should not depend on prose parsing
  Decision: include a short `decision_summary` / rationale field in state if useful, but routing must depend only on explicit structured fields.
- [x] Define any optional rationale/debug fields without making graph behavior depend on them
  Decision: optional debug/rationale fields may include:
  - `decision_summary`
  - `decision_inputs`
  but they must be observational only.
- [x] Confirm the node remains an agent-layer decision maker rather than taking over graph construction
  Confirmed: `orchestrator_node(...)` should return state updates and high-level decisions only. It should not own node creation, edge wiring, or detailed router branching already handled by `orchestration/graph.py` and `orchestration/router.py`.
  Implemented accordingly: the node computes workflow-entry and downstream decisions but does not import or mutate LangGraph graph construction.

## 4c. Agent Config Contract

- [x] Define the `config/agents.yaml` shape needed by the orchestrator
- [x] Add or confirm entries for:
  - `eda_analyst`
  - `data_engineer`
  - `ml_modeler`
  - `reviewer`
  - `orchestrator`
  Implemented shape: the existing agent entries remain in place and now carry small orchestrator-facing metadata where useful, including `enabled`, `max_retries`, `runtime_node`, `active_variant`, `supported_variants`, and `max_iterations`.
- [x] Decide whether existing config role names like `ml_reviewer`, `business_stakeholder`, and `report` need orchestrator-facing metadata additions
- [x] Decide whether any additional agent entries are needed for evaluation and report generation
  Expected question: are these represented as agents, workflows, or graph nodes elsewhere in the repo?
  Current bias from repo state:
  - `evaluation` should likely remain workflow-owned, not a new runtime agent file
  - `report_writer` already exists as the runtime report-writing agent, so Step 4 should plan around that actual path rather than a hypothetical `report` agent file
  Decision implemented:
  - no `evaluation` agent entry was added
  - the existing `report` role remains the logical config label
  - `report.runtime_node: report_writer` aligns the role with the actual runtime node
- [x] Confirm which existing agent entries should remain unchanged in the first Step 4 slice
- [x] Define the minimal new orchestrator-facing config fields, if any
  Expected candidates:
  - `active_variant`
  - `max_retries`
  - `max_iterations`
  - `enabled`
  Implemented minimal fields:
  - `enabled` across current orchestrator-relevant roles
  - `max_retries` for review/execution agents
  - `active_variant` and `supported_variants` for `ml_modeler`
  - `runtime_node` for `reviewer` and `report`
  - `max_iterations` for `orchestrator`
- [x] Decide whether `evaluation` needs config representation at all before graph wiring catches up
- [x] Decide whether the existing `report` config entry should remain a logical role label or be renamed/aligned with `report_writer`
- [x] Confirm the `ml_modeler.active_variant` contract
  Expected values: `sean` or `jonathan`
  Implemented contract:
  - `ml_modeler.active_variant: sean`
  - `ml_modeler.supported_variants: [sean, jonathan]`
- [x] Define the precedence order for modeler-variant selection
  Expected candidates to order:
  - `config/agents.yaml`
  - `settings.yaml`
  - state override
  Decision: precedence should be `state override` -> `config/agents.yaml` -> `settings.yaml` fallback, though the first Step 4 slice only establishes the config contract and does not yet consume state overrides.
- [x] Confirm where retry and max-iteration settings should live
  Expected bias: keep agent-specific retry settings in `config/agents.yaml`; keep workflow-loop settings in `config/workflows.yaml` or `settings.yaml` only if already established there
  Decision implemented:
  - agent retry counts stay in `config/agents.yaml`
  - workflow/report/modeling loop caps stay in `config/workflows.yaml`
  - top-level modeling iteration cap stays in `settings.yaml`
  - orchestrator-facing `max_iterations` is available in `config/agents.yaml`
- [x] Keep the config schema consistent with `core/config.py` loaders
- [x] Confirm the final agent-config shape is loadable without changing unrelated config loaders
  Verified by the focused agent-config test in `tests/test_orchestrator.py`.

## 4d. Workflow Config Contract

- [x] Define the `config/workflows.yaml` shape needed for orchestrator routing
- [x] Add or confirm the `full_pipeline` workflow definition
- [x] Add or confirm the `baseline_only` workflow definition
- [x] Reconcile Jonathan's proposed workflow examples with the existing `full_pipeline` and `eda_preparation` workflow shapes already in the repo
  Expected bias: extend existing workflow records rather than replacing the current step lists with a second incompatible schema
- [x] Document the current workflow schema already present in `config/workflows.yaml`
- [x] Decide whether Step 4 should extend that schema or normalize it first
- [x] Account for the already-present `modeling` and `report` workflow sections in the Step 4 contract
- [x] Record the current `full_pipeline` mismatch explicitly
  Expected current state:
  - `full_pipeline` currently ends at `ml_modeler_handoff`
  - post-modeling evaluation / reviewer / report steps are not yet represented in the top-level workflow sequence
- [x] Define each workflow step record shape
  Expected fields:
  - `agent`
  - `required`
  - optional `condition`
- [x] Decide whether the repo should keep the current string-step list format, migrate to richer step records, or support both temporarily
- [x] Define the loop block shape
  Expected fields:
  - `max_iterations`
  - `loop_from`
  - `stop_condition`
- [x] Define the workflow-level metadata fields beyond steps and loops
  Expected candidates:
  - `description`
  - `entry_node`
  - `post_model_sequence`
- [x] Decide whether workflow conditions should stay declarative strings for now or become normalized machine-readable flags
  Expected bias: keep config simple, but do not create a brittle mini-language unless the existing graph layer already expects one
- [x] Define the first-step condition format the orchestrator will actually evaluate
- [x] Define any deferred condition formats explicitly so they do not silently slip into implementation
- [x] Confirm config values line up with what the orchestrator node can actually evaluate
  Implemented workflow contract:
  - existing graph-owned `steps` remain string lists for `full_pipeline`
  - `entry_node` is now the orchestrator-facing entry contract and is preferred over the first step when present
  - `full_pipeline` now explicitly declares `post_model_sequence: [evaluation, reviewer, report, business_stakeholder_report_review]`
  - `baseline_only` now exists as a minimal synthetic-data workflow with `entry_node: ml_modeler_handoff`
  - existing `eda_preparation`, `modeling`, and `report` sections remain intact and continue owning loop caps and sink behavior
  - richer per-step records are still supported by `orchestrator.py`, but the repo is intentionally not normalizing all workflow steps yet
  - condition mini-language work is deferred; the first Step 4 slice only evaluates workflow choice via Python logic plus explicit `entry_node`
  Verified by:
  - `tests/test_orchestrator.py::test_orchestrator_node_prefers_explicit_workflow_entry_node`
  - `tests/test_orchestrator.py::test_orchestrator_node_chooses_baseline_only_for_synthetic_data`
  - `tests/test_orchestrator.py::test_workflows_config_exposes_orchestrator_facing_workflow_metadata`

## 4e. Current-Graph Compatibility

- [x] Decide how the orchestrator should work with the already-built pre-modeling graph
  Expected options to resolve explicitly:
  - select a workflow name and let `orchestration/graph.py` own intra-workflow routing
  - emit only top-level phase decisions while existing routers continue handling detailed prep-loop transitions
  - or make a minimal graph change to insert an orchestrator entry node before `eda_raw`
- [x] Confirm the orchestrator does not duplicate logic already present in `orchestration/router.py`
- [x] Decide whether Step 4 should stop at "choose workflow / next high-level phase" rather than trying to directly route every raw and processed EDA review node
- [x] Define how the orchestrator hands off to the current graph entry point
  Expected current candidates:
  - `eda_raw`
  - `ml_modeler_handoff`
  - the existing modeling-loop entry nodes already present in the graph
  - a future post-modeling evaluation/reviewer handoff path once expanded
- [x] Identify the exact existing graph entry points and handoff nodes available today
- [x] Identify the exact router functions whose logic must not be duplicated
- [x] Decide whether the orchestrator is pre-graph only in the first slice or also owns post-modeling decisions
- [x] Decide whether the first Step 4 slice can avoid graph edits entirely
- [x] If graph edits are needed, define the smallest possible insertion point
- [x] Decide how post-modeling orchestration should be represented before full graph expansion lands
  Expected bias: explicit pending/blocked state is acceptable if later nodes are not wired yet
- [x] Record the current graph terminal condition precisely
  Expected current state:
  - after `ml_reviewer_final_recommendation_review`, the graph currently routes to `END`
  - Step 4 must decide whether orchestrator output bridges that gap conceptually now, or whether the actual graph edge additions are deferred to Step 5
  Decisions recorded for current-graph compatibility:
  - the orchestrator should select a workflow / entry node and otherwise stay at the high-level phase boundary
  - `orchestration/graph.py` remains the owner of all detailed pre-modeling and modeling transitions once a graph entry node is chosen
  - no orchestrator entry node is being inserted into the LangGraph in this Step 4 slice
  - the concrete current graph entry / handoff nodes available today are:
    - `eda_raw` as the graph entry point
    - `ml_modeler_handoff` as the modeling shortcut / synthetic-data handoff
    - `ml_modeler_baseline` as the first internal reviewed modeling phase reached from the handoff
  - router logic that must not be duplicated in `agents/orchestrator.py` includes:
    - `route_after_raw_eda`
    - `route_after_prep_plan`
    - `route_after_data_engineer_feedback`
    - `route_after_data_engineer_execute`
    - `route_after_processed_eda`
    - `route_after_processed_approval`
    - `route_after_modeling_handoff`
    - `route_after_modeling_review`
    - `route_after_business_review`
  - the orchestrator is both:
    - pre-graph at workflow-entry time
    - post-modeling/post-evaluation as a high-level blocked-or-ready decision maker
    but it is not taking over intra-graph routing
  - the first Step 4 slice avoids graph edits entirely
  - if a later Step 4/5 slice needs a graph insertion point, the smallest viable place is before the current `eda_raw` entry or after `ml_reviewer_final_recommendation_review`; neither is required yet
  - post-modeling orchestration is currently represented as explicit blocked decisions for:
    - `evaluation_graph_wiring`
    - `reviewer_graph_wiring`
    - `report_review_graph_wiring`
  - the graph terminal condition is still unchanged:
    - after `ml_reviewer_final_recommendation_review`, `graph.py` routes to `END`
    - Step 4 bridges that gap conceptually through orchestrator return values only
    - the actual graph edge additions are deferred to Step 5

## 4f. Workflow Selection Logic

- [x] Decide how the orchestrator distinguishes synthetic-data runs from existing-data runs
- [x] Define the initial branch for synthetic data
  Expected behavior: align with current graph reality rather than Jonathan's idealized shortcut. If the existing graph always enters EDA/preparation, the plan should either:
  - record that synthetic-data optimization is deferred to a later graph revision, or
  - define the exact minimal graph/orchestrator change needed to allow a direct modeling handoff
- [x] Define the initial branch for existing data
  Expected behavior: full EDA -> preparation review loop -> processed-data approval -> modeling handoff, matching the current graph
- [x] Decide how the orchestrator chooses between `full_pipeline` and `baseline_only`
- [x] Define fallback behavior when data-source hints are missing or ambiguous
- [x] Record any assumptions about state fields needed to make this decision
- [x] Keep the decision logic explicit and testable rather than embedding hidden config magic
- [x] Define the exact synthetic-data detection rule for the first slice
  Expected candidates:
  - path naming convention
  - settings flag
  - state hint
- [x] Map each supported detection outcome to an existing workflow or graph entry point
- [x] Define the fallback/default workflow when no detection signal is available
- [x] Record which idealized Step 4 branches are intentionally deferred because the current graph does not yet support them cleanly
  Implemented workflow-selection contract:
  - the first-slice detection rule is `settings.data.source == "synthetic"`
  - when the source is synthetic and `baseline_only` is present, the orchestrator selects `baseline_only`
  - `baseline_only` maps to the existing graph handoff node `ml_modeler_handoff`
  - existing-data runs select `full_pipeline`, which maps to the graph entry node `eda_raw`
  - when the source hint is missing or ambiguous but a non-empty settings payload is present, the orchestrator falls back to `full_pipeline`
  - when synthetic is declared but `baseline_only` is not configured, the orchestrator also falls back to `full_pipeline`
  - this logic is intentionally explicit in Python rather than driven by a config mini-language
  - path-based detection and richer state-hint precedence are deferred
  - the idealized direct synthetic-data shortcut to a new modeling-only graph is not being invented here; the current shortcut still enters through the already-built `ml_modeler_handoff` node
  Verified by:
  - `tests/test_orchestrator.py::test_orchestrator_node_returns_workflow_entry_decision`
  - `tests/test_orchestrator.py::test_orchestrator_node_chooses_baseline_only_for_synthetic_data`
  - `tests/test_orchestrator.py::test_orchestrator_node_falls_back_to_full_pipeline_when_source_hint_is_missing`
  - `tests/test_orchestrator.py::test_orchestrator_node_falls_back_to_full_pipeline_when_baseline_only_is_unavailable`

## 4g. Modeler Variant And Downstream Routing

- [x] Decide how the orchestrator selects Sean's versus Jonathan's modeling path
- [x] Confirm whether that decision should come from:
  - `config/agents.yaml`
  - `settings.yaml`
  - state
  - or a precedence order across them
- [x] Define the required downstream sequence after modeling
  Expected default:
  - modeling
  - evaluation
  - reviewer
  - report generation
- [x] Confirm whether evaluation and report generation are represented as agents, workflows, or special graph nodes in the current architecture
- [x] Define unavailable-node behavior if one downstream step is not yet implemented
  Expected bias: fail clearly or emit a blocked/pending state rather than silently skipping required steps
- [x] Adjust the downstream plan to current repo reality
  Expected current-state notes to capture:
  - evaluation should likely be invoked via `workflows/evaluation.py` or a future orchestration node, not treated as an already-built runtime agent
  - reviewer exists and can be planned as the post-evaluation consumer
  - report generation should be planned around the existing `report_writer` agent plus the already-present report-loop router/config sections
- [x] Record the exact current post-modeling gap
  Expected current state:
  - evaluation workflow exists but is not called by the graph
  - reviewer agent exists but is not called by the graph
  - report writer agent exists and business report-review routing exists in `router.py`, but neither is graph-wired
- [x] Define the exact modeler-variant decision rule for the first slice
- [x] Define the modeling -> evaluation handoff contract
- [x] Define the evaluation -> reviewer handoff contract
- [x] Define the reviewer -> report handoff behavior for the current repo state
- [x] Define the blocked-state behavior when the report path is absent
- [x] Decide whether the first Step 4 slice should emit a future-ready downstream plan even if later nodes are not wired yet
  Implemented downstream-routing contract:
  - the orchestrator now emits `modeler_variant` as runtime metadata without inventing separate graph nodes for Sean vs Jonathan
  - first-slice precedence is:
    - `state["modeler_variant"]`
    - `agents_config["agents"]["ml_modeler"]["active_variant"]`
    - fallback `"sean"`
  - the declared downstream path is carried as `downstream_sequence`, sourced from `config/workflows.yaml`
  - for the shipped `full_pipeline`, the future-ready downstream path is:
    - `evaluation`
    - `reviewer`
    - `report`
    - `business_stakeholder_report_review`
  - evaluation remains workflow-owned, not a runtime agent file
  - reviewer remains the post-evaluation runtime agent target
  - report generation remains logically represented as `report`, but its runtime node is `report_writer`
  - because the graph is not yet wired through those stages, the orchestrator emits explicit blocked states rather than skipping them:
    - `evaluation_graph_wiring`
    - `reviewer_graph_wiring`
    - `report_review_graph_wiring`
  - the first Step 4 slice intentionally emits a future-ready downstream plan even though later nodes are not graph-wired yet
  Verified by:
  - `tests/test_orchestrator.py::test_orchestrator_node_uses_state_override_for_modeler_variant`
  - `tests/test_orchestrator.py::test_orchestrator_node_uses_agents_config_for_modeler_variant_when_no_override_exists`
  - `tests/test_orchestrator.py::test_orchestrator_node_blocks_post_modeling_evaluation_gap`
  - `tests/test_orchestrator.py::test_orchestrator_node_blocks_post_evaluation_reviewer_gap`

## 4h. Loop And Stop Logic

- [x] Define how the orchestrator reads iteration count from state
- [x] Define where `max_iterations` is sourced from
  Expected references:
  - `config/agents.yaml`
  - `config/workflows.yaml`
  - `settings.model.max_iterations`
- [x] Define the stop condition contract
  Expected inputs:
  - current `evaluation_result`
  - prior score or improvement signal if available
- [x] Decide how to handle missing prior-iteration context
- [x] Define the "score improved significantly" stop behavior
- [x] Define the "score is flat" loop behavior
  Expected next action: try different feature engineering or re-enter at modeling depending on available nodes
- [x] Define the exact loop output fields written back into state
  Expected candidates:
  - `should_loop`
  - `loop_from`
  - `next_agent`
  - `stop_reason`
  - `iteration`
- [x] Keep loop logic deterministic and bounded
- [x] Reconcile loop fields with the current state schema
  Expected current fields already present:
  - `should_loop`
  - `iteration`
  - `should_revise_modeling`
  - `should_revise_report`
  - `modeling_iteration`
  - `report_iteration`
  Required decision: whether Step 4 should add new state keys or stay within the current schema for the first slice
- [x] Define the exact source of the improvement signal for stop/loop decisions
  Expected candidates:
  - `evaluation_result`
  - previous iteration state
  - explicit improvement field if later added
- [x] Define the fallback behavior when prior-iteration comparison data is missing
- [x] Define the stop-output payload
- [x] Define the loop-output payload
- [x] Define iteration-cap behavior independently from score-based stop behavior
  Implemented loop/stop contract:
  - the orchestrator reads the top-level iteration counter from `state["iteration"]`
  - `max_iterations` precedence is:
    - `agents_config["agents"]["orchestrator"]["max_iterations"]`
    - `settings["model"]["max_iterations"]`
    - fallback `5`
  - the improvement threshold comes from:
    - `settings["model"]["tuning"]["min_improvement"]`
    - fallback `0.01`
  - the improvement signal is read conservatively from `evaluation_result`, supporting:
    - `improvement`
    - `improvement_vs_prior`
    - `score_improvement`
    - `model_selection_summary.winner.score_improvement`
  - if evaluation improvement is explicitly present and below the threshold while under the iteration cap, the orchestrator emits a loop-back decision:
    - `next_agent: ml_modeler_baseline`
    - `should_loop: true`
    - `loop_from: ml_modeler_baseline`
    - `blocked_on: post_evaluation_loop_wiring`
  - if improvement meets/exceeds the threshold, the orchestrator stops looping and proceeds toward reviewer:
    - `next_agent: reviewer`
    - `stop_reason: improvement_threshold_met`
  - if the iteration cap is already reached, the orchestrator also stops looping and proceeds toward reviewer:
    - `stop_reason: max_iterations_reached`
  - when prior/improvement context is missing, the first slice defaults to stop rather than inventing a loop:
    - `stop_reason: prior_context_missing`
  - the payload now carries:
    - `should_loop`
    - `loop_from`
    - `next_agent`
    - `stop_reason`
    - `iteration`
    - `max_iterations`
  - no new top-level state keys were added beyond fields already tolerated by the current partial-state contract
  Verified by:
  - `tests/test_orchestrator.py::test_orchestrator_node_loops_back_after_flat_evaluation_improvement`
  - `tests/test_orchestrator.py::test_orchestrator_node_stops_looping_when_improvement_threshold_is_met`
  - `tests/test_orchestrator.py::test_orchestrator_node_stops_looping_at_iteration_cap_even_when_score_is_flat`
  - `tests/test_orchestrator.py::test_orchestrator_node_defaults_to_stop_when_prior_improvement_context_is_missing`

## 4i. Integration Boundary With Graph Wiring

- [x] Decide what Step 4 must implement directly versus what belongs to Step 5 graph wiring
- [x] Confirm whether `agents/orchestrator.py` alone is sufficient for Step 4 or whether limited graph edits are required now
- [x] If graph edits are needed, identify the exact minimal paths before implementation
  Expected candidates:
  - `src/multi_agent_ds/orchestration/graph.py`
  - `src/multi_agent_ds/orchestration/router.py`
- [x] Keep orchestrator decisions machine-readable enough that Step 5 can wire them without reshaping the contract
- [x] Avoid building Step 5 end-to-end integration logic inside the Step 4 implementation
- [x] Explicitly protect the already-working preparation graph from unnecessary rewrites
  Expected bias: no broad graph redesign in Step 4 unless the orchestrator contract truly cannot fit the current flow
- [x] Separate Step 4 deliverables into:
  - agent contract
  - config contract
  - optional minimal graph touch
- [x] Define the exact items deferred to Step 5 so Step 4 does not quietly absorb graph-integration work
- [x] Decide whether graph-wiring of evaluation/reviewer/report is explicitly deferred to Step 5 or partially included now
- [x] Confirm the first Step 4 implementation unit is reviewable on its own without end-to-end graph execution
  Integration-boundary decision:
  - Step 4 directly owns:
    - the orchestrator decision contract in `agents/orchestrator.py`
    - the orchestrator-facing schema additions in `config/agents.yaml`
    - the orchestrator-facing schema additions in `config/workflows.yaml`
    - focused orchestrator tests in `tests/test_orchestrator.py`
  - Step 4 does not directly own:
    - adding runtime nodes to `orchestration/graph.py`
    - adding new graph edges after modeling
    - invoking `workflows/evaluation.py` from the graph
    - wiring `reviewer` or `report_writer` into the graph
    - wiring the business report-review loop into the graph
  - `agents/orchestrator.py` plus config changes are sufficient for the Step 4 implementation unit; no graph edit was required
  - if later graph edits are needed, the minimal deferred paths are:
    - `src/multi_agent_ds/orchestration/graph.py`
    - `src/multi_agent_ds/orchestration/router.py`
  - the current orchestrator payload is already machine-readable enough for Step 5 wiring because it now carries:
    - `selected_workflow`
    - `entry_node`
    - `modeler_variant`
    - `downstream_sequence`
    - `next_agent`
    - `should_loop`
    - `loop_from`
    - `stop_reason`
    - `blocked_on`
    - `blocked_reason`
    - `iteration`
    - `max_iterations`
  - evaluation / reviewer / report graph wiring is explicitly deferred to Step 5
  - the already-working preparation/modeling graph was intentionally left unchanged in Step 4
  - this Step 4 unit is reviewable without end-to-end graph execution because the runtime boundary is expressed and tested through orchestrator return payloads rather than graph mutation

## 4j. Tests

- [x] Decide the Step 4 test target file
  Expected candidate: `tests/unit/test_orchestrator.py`
  Chosen implementation target: `tests/test_orchestrator.py`
- [x] Define the pure orchestrator-node test matrix before implementation
- [x] Add or update focused tests for workflow selection
  Expected cases:
  - synthetic data chooses the lighter path
  - existing data chooses the fuller path
- [x] Add or update focused tests for modeler variant selection
- [x] Add or update focused tests for default downstream routing after modeling
- [x] Add or update focused tests for loop-stop behavior
  Expected cases:
  - significant improvement -> stop
  - flat score -> loop
  - iteration cap reached -> stop
- [x] Add or update focused tests for missing or partial state inputs
- [x] Add or update focused tests for config-driven behavior
- [x] Add or update focused tests for blocked/unimplemented downstream steps if that condition is part of the Step 4 contract
- [x] Keep tests isolated from real LangGraph execution unless Step 4 explicitly requires graph-level validation
- [x] Add or update focused tests for compatibility with the existing graph entry/hand-off decisions
  Expected cases:
  - current pre-modeling graph path selection
  - blocked post-modeling/report step behavior when later nodes are not wired yet
- [x] Decide whether a graph-level smoke test is needed in Step 4 or should remain deferred to Step 5
  Implemented Step 4 test matrix:
  - workflow-entry selection:
    - existing-data `full_pipeline`
    - synthetic-data `baseline_only`
    - fallback to `full_pipeline` when source is ambiguous
    - fallback to `full_pipeline` when `baseline_only` is unavailable
    - explicit `entry_node` precedence
    - support for dict-style workflow step records
  - config-driven behavior:
    - `agents.yaml` orchestrator-facing metadata
    - `workflows.yaml` orchestrator-facing metadata
    - `modeler_variant` precedence from state override and agent config
  - downstream routing:
    - graph-owned-phase deferral
    - blocked modeling -> evaluation handoff
    - blocked evaluation -> reviewer handoff
    - blocked report generation -> business review handoff
    - report revision loop-back
    - accepted business-review stop
  - loop/stop behavior:
    - flat explicit improvement under cap -> loop back toward modeling
    - improvement above threshold -> stop looping and proceed toward reviewer
    - cap reached -> stop looping and proceed toward reviewer
    - missing prior/improvement context -> conservative stop
  - tests stay isolated from LangGraph execution and assert only orchestrator return payloads
  - a graph-level smoke test is explicitly deferred to Step 5, when graph wiring is actually added
  Verified by:
  - `uv run pytest tests/test_orchestrator.py`
  - current result: `20 passed`

## 4k. Validation

- [x] Run the targeted Step 4 tests
- [x] Review the final orchestrator decision payload for architecture fit
- [x] Review config diffs for schema clarity and minimalism
- [x] Confirm no new dependency was introduced
- [x] Confirm no new script, notebook, or entrypoint was added
- [x] Confirm Step 4 remains a reviewable unit separate from Step 5 graph integration
- [x] Update `jonathan_plan.md` Step 4 checkboxes after implementation
- [x] Prepare a commit only after Step 4 is a complete reviewable unit
  Validation summary:
  - targeted Step 4 verification passed:
    - `uv run pytest tests/test_orchestrator.py`
    - current result: `20 passed, 1 warning`
  - architecture fit remains correct:
    - orchestrator behavior lives in `src/multi_agent_ds/agents/orchestrator.py`
    - config contract changes are limited to `config/agents.yaml` and `config/workflows.yaml`
    - no graph or router files were edited in Step 4
  - config diffs remain small and schema-focused:
    - `agents.yaml` gained orchestrator-facing metadata
    - `workflows.yaml` gained `entry_node`, `baseline_only`, and `post_model_sequence`
  - no new dependency was introduced:
    - no `pyproject.toml` or dependency-lock edits were required for Step 4
  - no new script, notebook, CLI, or entrypoint was added
  - Step 4 remains reviewable independently from Step 5 because:
    - the orchestrator contract is implemented and tested
    - graph integration is still explicitly deferred
  - there is no separate `project_planning/jonathan_plan/jonathan_plan.md` parent checklist file to update
    - the authoritative source spec remains `project_planning/Jonathan_Plan.md`
    - the Step 4 execution checklist in `project_planning/jonathan_plan/jonathan_plan_4.md` is therefore treated as the completed tracker for this unit
  - the Step 4 implementation unit is now complete and ready for a single commit at the plan boundary
