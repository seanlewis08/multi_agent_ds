# Wiring Next Steps

Source context:
- [Jonathan_Plan.md](/Users/jonathan.chia/code/multi_agent_ds/project_planning/Jonathan_Plan.md)
- [BUILD_PLAN.md](/Users/jonathan.chia/code/multi_agent_ds/project_planning/BUILD_PLAN.md)
- [project_planning/jonathan_plan/jonathan_plan_4.md](/Users/jonathan.chia/code/multi_agent_ds/project_planning/jonathan_plan/jonathan_plan_4.md)
- [project_planning/jonathan_plan/jonathan_plan_5.md](/Users/jonathan.chia/code/multi_agent_ds/project_planning/jonathan_plan/jonathan_plan_5.md)

## What Is Already Wired

- The runtime graph now supports the post-model path:
  - modeling final review
  - evaluation
  - reviewer
  - report generation
  - business stakeholder report review
- The evaluation wrapper is graph-wired and preserves:
  - `evaluation_result`
  - `reviewer_summary`
  - `shap_results`
  - `shap_artifacts`
  - `mlflow_payload`
- Reviewer dry-run metadata now survives graph execution:
  - `branch_name`
  - `staged_paths`
  - `commit_message`
  - `pr_title`
  - `pr_body`
  - `pr_metadata`
- Step 4 orchestrator selection still remains external to the graph and continues to own:
  - `selected_workflow`
  - `entry_node`
  - `modeler_variant`
  - `downstream_sequence`

## Remaining Wiring Gaps

### 1. True Sean-vs-Jonathan Runtime Modeler Split

Current status:
- `config/agents.yaml` and `orchestrator.py` can name `sean` and `jonathan`
- runtime execution still only has one callable modeler:
  - [src/multi_agent_ds/agents/ml_modeler.py](/Users/jonathan.chia/code/multi_agent_ds/src/multi_agent_ds/agents/ml_modeler.py)
- that runtime node still uses Sean's prompt/config surface

What still needs wiring:
- a real Jonathan-owned runtime modeler implementation
- runtime branching on `modeler_variant`
- honest graph/runtime validation for:
  - Sean path
  - Jonathan path
  - side-by-side comparison behavior

Recommended execution order:
1. Add the Jonathan runtime modeler behavior inside the existing modeler module if possible.
2. If that is not clean, introduce the minimum planned runtime split only after re-checking `PROJECT_TREE.md` and `BUILD_PLAN.md`.
3. Make `ml_modeler_node(...)` or a thin runtime wrapper dispatch on `modeler_variant`.
4. Add tests that prove different runtime behavior actually occurs for the two variants.

### 2. Graph-Time MLflow Follow-Through

Current status:
- real MLflow side effects still live in [src/multi_agent_ds/workflows/modeling.py](/Users/jonathan.chia/code/multi_agent_ds/src/multi_agent_ds/workflows/modeling.py)
- evaluation only returns an MLflow-ready payload
- reviewer/report/business-review do not log to MLflow

What still needs wiring if MLflow expansion is desired:
- decide whether evaluation artifacts should be logged by:
  - the evaluation workflow
  - a later orchestration sink
  - a dedicated observability workflow
- decide whether reviewer/report artifacts should also become MLflow artifacts
- decide whether graph execution should open or extend an experiment run context

Recommended execution order:
1. Keep the current boundary unless a user explicitly wants graph-time MLflow side effects.
2. If expansion is needed, add one orchestration-owned logging sink rather than distributing MLflow calls across agents.
3. Log `evaluation.mlflow_payload` first before expanding to reviewer/report artifacts.
4. Validate nested-run behavior only after the logging ownership decision is explicit.

### 3. Real Reviewer Execution Path

Current status:
- automated tests use `reviewer.dry_run=True`
- real PR creation is intentionally manual / environment-gated

What still needs wiring for live execution:
- decide where `dry_run=False` is enabled in real runtime usage
- decide how the runtime surfaces:
  - repo cleanliness requirements
  - GitHub auth readiness
  - OpenAI readiness for PR body generation
- decide whether failed PR creation should:
  - fail the run hard
  - return a blocked state
  - fall back to a dry-run plan

Recommended execution order:
1. Keep automated coverage on `dry_run=True`.
2. Add one explicit human-gated runtime path for `dry_run=False`.
3. Return a blocked/error state rather than silently skipping reviewer-side git/PR failures.
4. Only after that, consider a manual smoke-test checklist for real PR creation.

## Recommended Next Wiring Unit

The next highest-value wiring unit is:
- implement the real Jonathan runtime modeler path
- wire runtime dispatch off `modeler_variant`
- keep graph topology unchanged

Why this should be next:
- it is the main still-blocked Step 5 acceptance criterion
- the graph and downstream path are already in place
- without it, the repo advertises variant selection but cannot execute a real variant comparison

## Suggested Execution Sequence

1. Runtime modeler variant split
2. Variant-aware tests in existing orchestrator / graph surfaces
3. Manual reviewer live-run gating
4. Optional MLflow sink for evaluation payload
5. Optional reviewer/report artifact logging after the sink decision is stable

## Guardrails

- Do not move business logic out of existing agents/workflows just to wire the next step.
- Prefer extending existing runtime modules before adding a new file.
- Keep `skills/` pure.
- Keep git/GitHub side effects behind explicit reviewer ownership.
- Keep automated tests isolated from real GitHub and real PR creation.
- Do not claim a Sean-vs-Jonathan runtime comparison until both runtime paths are truly callable.
