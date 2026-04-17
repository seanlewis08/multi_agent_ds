# Jonathan Plan Step 4 Checklist

Source: [Jonathan_Plan.md](/Users/jonathan.chia/code/multi_agent_ds/project_planning/Jonathan_Plan.md)

## Step 4: Orchestrator Agent

- [ ] Confirm Step 4 scope against `project_planning/Jonathan_Plan.md`
- [ ] Confirm Step 4 is aligned with `project_planning/ARCHITECTURE.md`
  Expected layer ownership: orchestration owns the graph, `agents/orchestrator.py` owns top-level workflow decisions, and configs own role/sequence definitions
- [ ] Confirm exact file targets for Step 4 changes
  Expected primary targets:
  - `src/multi_agent_ds/agents/orchestrator.py`
  - `config/agents.yaml`
  - `config/workflows.yaml`
- [ ] Confirm whether Step 4 should stay isolated to the orchestrator/config layer or whether any supporting edit is required in `orchestration/graph.py`, `orchestration/router.py`, or `orchestration/state.py`
- [ ] Confirm no new dependency is needed
  Expected: use existing config loading, existing state object, and current LangGraph skeleton/adapters
- [ ] Confirm which Step 4 prerequisites are already present versus still placeholders
  Expected dependencies to inspect:
  - `src/multi_agent_ds/agents/orchestrator.py`
  - `config/agents.yaml`
  - `config/workflows.yaml`
  - `src/multi_agent_ds/orchestration/graph.py`
  - `src/multi_agent_ds/orchestration/state.py`
  - currently implemented agent nodes (`reviewer`, modeling-related agents, report path if present)
- [ ] Decide the minimum Step 4 implementation slice if dependencies are incomplete
  Expected bias: build the orchestrator node around the current pre-modeling graph and already-built reviewer/evaluation outputs, then keep unavailable-node handling explicit rather than inventing runtime steps that are not built yet

## Current Baseline To Plan Against

- [ ] Record the actual current orchestrator baseline before implementation
  Current repo reality to plan around:
  - `src/multi_agent_ds/agents/orchestrator.py` is still a placeholder
  - `config/agents.yaml` is already populated and not a placeholder
  - `config/workflows.yaml` already describes the current EDA/preparation, modeling, and report-loop workflows and is not a placeholder
  - `src/multi_agent_ds/orchestration/graph.py` already wires the pre-modeling review/preparation flow plus the phased modeling loop
  - `src/multi_agent_ds/workflows/evaluation.py` is now implemented
  - `src/multi_agent_ds/agents/reviewer.py` is now implemented
  - `src/multi_agent_ds/agents/report_writer.py` now exists as the runtime report-writing agent
- [ ] Decide whether Step 4 should extend the current graph-first design or attempt to replace it
  Expected decision: extend the current graph-first design and let `orchestrator.py` choose or summarize workflow decisions at the top level, rather than replacing the existing `orchestration/graph.py` flow with a second parallel orchestrator
- [ ] Decide how to handle Jonathan's Step 4 references to placeholder configs now that those config files already contain repo-specific content
  Expected bias: merge the new orchestrator contract into the existing config shapes instead of rewriting them to match the idealized examples verbatim

## 4a. Prep And Context Review

- [ ] Read the current placeholder or implementation in `src/multi_agent_ds/agents/orchestrator.py`
- [ ] Read `src/multi_agent_ds/orchestration/state.py` to understand the current `PipelineState` contract
- [ ] Read `src/multi_agent_ds/orchestration/graph.py` to understand existing node/edge wiring
- [ ] Read `src/multi_agent_ds/orchestration/router.py` if present to avoid duplicating routing logic in the orchestrator agent
- [ ] Read `config/agents.yaml` and `config/workflows.yaml` to confirm current placeholder shape or existing config loader expectations
- [ ] Read `src/multi_agent_ds/core/config.py` for the exact config loading helpers already available
- [ ] Read the currently implemented agent nodes that Step 4 will sequence
  Expected candidates:
  - `src/multi_agent_ds/agents/reviewer.py`
  - any existing `ml_modeler`, `eda_analyst`, `data_engineer`, `business_stakeholder`, or report-generation agent paths
- [ ] Confirm which runtime agents named in Jonathan's Step 4 actually exist today versus which are still not built
- [ ] Record the currently wired graph nodes versus merely configured runtime roles
  Expected current mismatch to capture:
  - graph nodes already exist for raw/processed EDA reviews and preparation loops
  - graph nodes already exist for the phased modeling loop
  - `reviewer` exists as an agent file but is not yet wired into `orchestration/graph.py`
  - `evaluation` exists as a workflow, not as an agent node
  - `report_writer` exists as a runtime agent, but report-stage graph wiring should be checked explicitly rather than assumed
- [ ] Decide the smallest initial Step 4 surface area
  Expected bias: keep workflow-selection and top-level phase/next-step decisions in `agents/orchestrator.py`; do not move orchestration policy into config loaders or tools, and do not duplicate the already-built preparation router logic

## 4b. Orchestrator Interface Definition

- [ ] Define `orchestrator_node(state: PipelineState) -> dict`
- [ ] Document the expected orchestrator inputs from state
  Expected minimum inputs:
  - `settings`
  - `data_path` or equivalent data-source hint
  - any current phase / iteration / evaluation result fields needed for routing
- [ ] Align the orchestrator inputs with the state fields that already exist in `PipelineState`
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
- [ ] Define which of those current state inputs are required versus optional for the first Step 4 slice
- [ ] Define the minimum state assumptions for pre-graph workflow entry decisions
- [ ] Define the minimum state assumptions for post-modeling / post-evaluation decisions
- [ ] Document the orchestrator node's returned shape before implementation details
- [ ] Decide whether the node returns:
  - a `next_agent`
  - a selected workflow name
  - loop control fields
  - updated iteration / stop flags
  - or a combination of these
- [ ] Define a compact decision payload for graph/router consumption
  Expected bias: return explicit machine-readable routing fields, not only prose reasoning
- [ ] Define the machine-readable workflow-entry fields
  Expected candidates:
  - `selected_workflow`
  - `entry_node`
  - `decision_type`
- [ ] Define the machine-readable post-modeling / post-evaluation routing fields
  Expected candidates:
  - `next_agent`
  - `loop_from`
  - `should_loop`
  - `stop_reason`
- [ ] Define the blocked or pending-state return shape for unavailable downstream steps
  Expected candidates:
  - `status`
  - `blocked_on`
  - `blocked_reason`
- [ ] Decide whether the orchestrator should emit graph-entry guidance, post-modeling guidance, or both
  Expected bias: use one node contract that can support:
  - workflow entry selection before the existing graph runs
  - post-modeling / post-evaluation decisions after later graph expansion
- [ ] Decide where human-readable orchestrator reasoning belongs
  Expected: short state-safe rationale field if useful, but routing should not depend on prose parsing
- [ ] Define any optional rationale/debug fields without making graph behavior depend on them
- [ ] Confirm the node remains an agent-layer decision maker rather than taking over graph construction

## 4c. Agent Config Contract

- [ ] Define the `config/agents.yaml` shape needed by the orchestrator
- [ ] Add or confirm entries for:
  - `eda_analyst`
  - `data_engineer`
  - `ml_modeler`
  - `reviewer`
  - `orchestrator`
- [ ] Decide whether existing config role names like `ml_reviewer`, `business_stakeholder`, and `report` need orchestrator-facing metadata additions
- [ ] Decide whether any additional agent entries are needed for evaluation and report generation
  Expected question: are these represented as agents, workflows, or graph nodes elsewhere in the repo?
  Current bias from repo state:
  - `evaluation` should likely remain workflow-owned, not a new runtime agent file
  - `report_writer` already exists as the runtime report-writing agent, so Step 4 should plan around that actual path rather than a hypothetical `report` agent file
- [ ] Confirm which existing agent entries should remain unchanged in the first Step 4 slice
- [ ] Define the minimal new orchestrator-facing config fields, if any
  Expected candidates:
  - `active_variant`
  - `max_retries`
  - `max_iterations`
  - `enabled`
- [ ] Decide whether `evaluation` needs config representation at all before graph wiring catches up
- [ ] Decide whether the existing `report` config entry should remain a logical role label or be renamed/aligned with `report_writer`
- [ ] Confirm the `ml_modeler.active_variant` contract
  Expected values: `sean` or `jonathan`
- [ ] Define the precedence order for modeler-variant selection
  Expected candidates to order:
  - `config/agents.yaml`
  - `settings.yaml`
  - state override
- [ ] Confirm where retry and max-iteration settings should live
  Expected bias: keep agent-specific retry settings in `config/agents.yaml`; keep workflow-loop settings in `config/workflows.yaml` or `settings.yaml` only if already established there
- [ ] Keep the config schema consistent with `core/config.py` loaders
- [ ] Confirm the final agent-config shape is loadable without changing unrelated config loaders

## 4d. Workflow Config Contract

- [ ] Define the `config/workflows.yaml` shape needed for orchestrator routing
- [ ] Add or confirm the `full_pipeline` workflow definition
- [ ] Add or confirm the `baseline_only` workflow definition
- [ ] Reconcile Jonathan's proposed workflow examples with the existing `full_pipeline` and `eda_preparation` workflow shapes already in the repo
  Expected bias: extend existing workflow records rather than replacing the current step lists with a second incompatible schema
- [ ] Document the current workflow schema already present in `config/workflows.yaml`
- [ ] Decide whether Step 4 should extend that schema or normalize it first
- [ ] Account for the already-present `modeling` and `report` workflow sections in the Step 4 contract
- [ ] Define each workflow step record shape
  Expected fields:
  - `agent`
  - `required`
  - optional `condition`
- [ ] Decide whether the repo should keep the current string-step list format, migrate to richer step records, or support both temporarily
- [ ] Define the loop block shape
  Expected fields:
  - `max_iterations`
  - `loop_from`
  - `stop_condition`
- [ ] Define the workflow-level metadata fields beyond steps and loops
  Expected candidates:
  - `description`
  - `entry_node`
  - `post_model_sequence`
- [ ] Decide whether workflow conditions should stay declarative strings for now or become normalized machine-readable flags
  Expected bias: keep config simple, but do not create a brittle mini-language unless the existing graph layer already expects one
- [ ] Define the first-step condition format the orchestrator will actually evaluate
- [ ] Define any deferred condition formats explicitly so they do not silently slip into implementation
- [ ] Confirm config values line up with what the orchestrator node can actually evaluate

## 4e. Current-Graph Compatibility

- [ ] Decide how the orchestrator should work with the already-built pre-modeling graph
  Expected options to resolve explicitly:
  - select a workflow name and let `orchestration/graph.py` own intra-workflow routing
  - emit only top-level phase decisions while existing routers continue handling detailed prep-loop transitions
  - or make a minimal graph change to insert an orchestrator entry node before `eda_raw`
- [ ] Confirm the orchestrator does not duplicate logic already present in `orchestration/router.py`
- [ ] Decide whether Step 4 should stop at "choose workflow / next high-level phase" rather than trying to directly route every raw and processed EDA review node
- [ ] Define how the orchestrator hands off to the current graph entry point
  Expected current candidates:
  - `eda_raw`
  - `ml_modeler_handoff`
  - the existing modeling-loop entry nodes already present in the graph
  - a future post-modeling evaluation/reviewer handoff path once expanded
- [ ] Identify the exact existing graph entry points and handoff nodes available today
- [ ] Identify the exact router functions whose logic must not be duplicated
- [ ] Decide whether the orchestrator is pre-graph only in the first slice or also owns post-modeling decisions
- [ ] Decide whether the first Step 4 slice can avoid graph edits entirely
- [ ] If graph edits are needed, define the smallest possible insertion point
- [ ] Decide how post-modeling orchestration should be represented before full graph expansion lands
  Expected bias: explicit pending/blocked state is acceptable if later nodes are not wired yet

## 4f. Workflow Selection Logic

- [ ] Decide how the orchestrator distinguishes synthetic-data runs from existing-data runs
- [ ] Define the initial branch for synthetic data
  Expected behavior: align with current graph reality rather than Jonathan's idealized shortcut. If the existing graph always enters EDA/preparation, the plan should either:
  - record that synthetic-data optimization is deferred to a later graph revision, or
  - define the exact minimal graph/orchestrator change needed to allow a direct modeling handoff
- [ ] Define the initial branch for existing data
  Expected behavior: full EDA -> preparation review loop -> processed-data approval -> modeling handoff, matching the current graph
- [ ] Decide how the orchestrator chooses between `full_pipeline` and `baseline_only`
- [ ] Define fallback behavior when data-source hints are missing or ambiguous
- [ ] Record any assumptions about state fields needed to make this decision
- [ ] Keep the decision logic explicit and testable rather than embedding hidden config magic
- [ ] Define the exact synthetic-data detection rule for the first slice
  Expected candidates:
  - path naming convention
  - settings flag
  - state hint
- [ ] Map each supported detection outcome to an existing workflow or graph entry point
- [ ] Define the fallback/default workflow when no detection signal is available
- [ ] Record which idealized Step 4 branches are intentionally deferred because the current graph does not yet support them cleanly

## 4g. Modeler Variant And Downstream Routing

- [ ] Decide how the orchestrator selects Sean's versus Jonathan's modeling path
- [ ] Confirm whether that decision should come from:
  - `config/agents.yaml`
  - `settings.yaml`
  - state
  - or a precedence order across them
- [ ] Define the required downstream sequence after modeling
  Expected default:
  - modeling
  - evaluation
  - reviewer
  - report generation
- [ ] Confirm whether evaluation and report generation are represented as agents, workflows, or special graph nodes in the current architecture
- [ ] Define unavailable-node behavior if one downstream step is not yet implemented
  Expected bias: fail clearly or emit a blocked/pending state rather than silently skipping required steps
- [ ] Adjust the downstream plan to current repo reality
  Expected current-state notes to capture:
  - evaluation should likely be invoked via `workflows/evaluation.py` or a future orchestration node, not treated as an already-built runtime agent
  - reviewer exists and can be planned as the post-evaluation consumer
  - report generation should be planned around the existing `report_writer` agent plus the already-present report-loop router/config sections
- [ ] Define the exact modeler-variant decision rule for the first slice
- [ ] Define the modeling -> evaluation handoff contract
- [ ] Define the evaluation -> reviewer handoff contract
- [ ] Define the reviewer -> report handoff behavior for the current repo state
- [ ] Define the blocked-state behavior when the report path is absent
- [ ] Decide whether the first Step 4 slice should emit a future-ready downstream plan even if later nodes are not wired yet

## 4h. Loop And Stop Logic

- [ ] Define how the orchestrator reads iteration count from state
- [ ] Define where `max_iterations` is sourced from
  Expected references:
  - `config/agents.yaml`
  - `config/workflows.yaml`
  - `settings.model.max_iterations`
- [ ] Define the stop condition contract
  Expected inputs:
  - current `evaluation_result`
  - prior score or improvement signal if available
- [ ] Decide how to handle missing prior-iteration context
- [ ] Define the "score improved significantly" stop behavior
- [ ] Define the "score is flat" loop behavior
  Expected next action: try different feature engineering or re-enter at modeling depending on available nodes
- [ ] Define the exact loop output fields written back into state
  Expected candidates:
  - `should_loop`
  - `loop_from`
  - `next_agent`
  - `stop_reason`
  - `iteration`
- [ ] Keep loop logic deterministic and bounded
- [ ] Reconcile loop fields with the current state schema
  Expected current fields already present:
  - `should_loop`
  - `iteration`
  - `should_revise_modeling`
  - `should_revise_report`
  - `modeling_iteration`
  - `report_iteration`
  Required decision: whether Step 4 should add new state keys or stay within the current schema for the first slice
- [ ] Define the exact source of the improvement signal for stop/loop decisions
  Expected candidates:
  - `evaluation_result`
  - previous iteration state
  - explicit improvement field if later added
- [ ] Define the fallback behavior when prior-iteration comparison data is missing
- [ ] Define the stop-output payload
- [ ] Define the loop-output payload
- [ ] Define iteration-cap behavior independently from score-based stop behavior

## 4i. Integration Boundary With Graph Wiring

- [ ] Decide what Step 4 must implement directly versus what belongs to Step 5 graph wiring
- [ ] Confirm whether `agents/orchestrator.py` alone is sufficient for Step 4 or whether limited graph edits are required now
- [ ] If graph edits are needed, identify the exact minimal paths before implementation
  Expected candidates:
  - `src/multi_agent_ds/orchestration/graph.py`
  - `src/multi_agent_ds/orchestration/router.py`
- [ ] Keep orchestrator decisions machine-readable enough that Step 5 can wire them without reshaping the contract
- [ ] Avoid building Step 5 end-to-end integration logic inside the Step 4 implementation
- [ ] Explicitly protect the already-working preparation graph from unnecessary rewrites
  Expected bias: no broad graph redesign in Step 4 unless the orchestrator contract truly cannot fit the current flow
- [ ] Separate Step 4 deliverables into:
  - agent contract
  - config contract
  - optional minimal graph touch
- [ ] Define the exact items deferred to Step 5 so Step 4 does not quietly absorb graph-integration work
- [ ] Confirm the first Step 4 implementation unit is reviewable on its own without end-to-end graph execution

## 4j. Tests

- [ ] Decide the Step 4 test target file
  Expected candidate: `tests/unit/test_orchestrator.py`
- [ ] Define the pure orchestrator-node test matrix before implementation
- [ ] Add or update focused tests for workflow selection
  Expected cases:
  - synthetic data chooses the lighter path
  - existing data chooses the fuller path
- [ ] Add or update focused tests for modeler variant selection
- [ ] Add or update focused tests for default downstream routing after modeling
- [ ] Add or update focused tests for loop-stop behavior
  Expected cases:
  - significant improvement -> stop
  - flat score -> loop
  - iteration cap reached -> stop
- [ ] Add or update focused tests for missing or partial state inputs
- [ ] Add or update focused tests for config-driven behavior
- [ ] Add or update focused tests for blocked/unimplemented downstream steps if that condition is part of the Step 4 contract
- [ ] Keep tests isolated from real LangGraph execution unless Step 4 explicitly requires graph-level validation
- [ ] Add or update focused tests for compatibility with the existing graph entry/hand-off decisions
  Expected cases:
  - current pre-modeling graph path selection
  - blocked post-modeling/report step behavior when later nodes are not wired yet
- [ ] Decide whether a graph-level smoke test is needed in Step 4 or should remain deferred to Step 5

## 4k. Validation

- [ ] Run the targeted Step 4 tests
- [ ] Review the final orchestrator decision payload for architecture fit
- [ ] Review config diffs for schema clarity and minimalism
- [ ] Confirm no new dependency was introduced
- [ ] Confirm no new script, notebook, or entrypoint was added
- [ ] Confirm Step 4 remains a reviewable unit separate from Step 5 graph integration
- [ ] Update `jonathan_plan.md` Step 4 checkboxes after implementation
- [ ] Prepare a commit only after Step 4 is a complete reviewable unit
