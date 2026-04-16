# Step 7 LangGraph Skeleton

This document explains what was built in Step 7, how the pieces fit together, and how to verify the skeleton locally.

## What Step 7 Built

Step 7 added the first shared orchestration scaffold for the multi-agent system.

It introduced:

- a shared graph state schema
- shared context and contract objects for inter-agent payloads
- router helpers that choose the next node from state
- a LangGraph skeleton with the planned node and edge layout

This step is intentionally thin. It gives the project a correct orchestration shape without yet wiring in real agent behavior.

## Files and Responsibilities

- [src/multi_agent_ds/orchestration/state.py](/Users/sean.lewis/DataspellProjects/multi_agent_ds/src/multi_agent_ds/orchestration/state.py)
  Defines `PipelineState`, the shared state object passed between graph nodes.

- [src/multi_agent_ds/core/context.py](/Users/sean.lewis/DataspellProjects/multi_agent_ds/src/multi_agent_ds/core/context.py)
  Defines `ExperimentContext`, a small shared dataclass for domain payloads and reasoning traces.

- [src/multi_agent_ds/core/contracts.py](/Users/sean.lewis/DataspellProjects/multi_agent_ds/src/multi_agent_ds/core/contracts.py)
  Defines `EDAOutput` and `ModelingOutput`, the first structured contracts for inter-agent communication.

- [src/multi_agent_ds/orchestration/router.py](/Users/sean.lewis/DataspellProjects/multi_agent_ds/src/multi_agent_ds/orchestration/router.py)
  Defines `route_after_eda()` and `route_after_modeling()`, the first state-based routing decisions.

- [src/multi_agent_ds/orchestration/graph.py](/Users/sean.lewis/DataspellProjects/multi_agent_ds/src/multi_agent_ds/orchestration/graph.py)
  Defines `build_graph()`, which creates the LangGraph skeleton with placeholder nodes and planned edges.

## Layer Ownership

Step 7 follows the planned architecture:

- `orchestration/` owns graph state, routing, and graph wiring
- `core/` owns shared context and contracts
- no LLM calls were added here
- no workflow side effects were added here
- no file I/O or reporting logic was added here

That keeps this step aligned with the repo import direction:

```text
orchestration -> workflows -> agents -> skills -> tools
```

## Graph Diagram

```text
                          needs_cleaning = true
                    +------------------------------+
                    |                              v
[eda] ------------------------------------> [data_engineer]
  |
  | needs_cleaning = false
  v
[ml_modeler] -- should_loop = true and iteration < 5 --> [ml_modeler]
  |
  | otherwise
  v
[evaluation] -> [reviewer] -> [report] -> [END]

[data_engineer] -> [ml_modeler]
```

## What the Skeleton Does Today

Today the graph gives the project:

- a shared `PipelineState` shape
- a concrete place for agent outputs to accumulate
- a real LangGraph object that can be built and compiled
- simple routing behavior after EDA and modeling
- a stable place to attach real agent nodes in later steps

The placeholder nodes currently just return the incoming state unchanged.

## What It Does Not Do Yet

This is not a working end-to-end pipeline yet.

It does not yet:

- run real EDA logic
- run real cleaning or preparation logic
- run real model training or evaluation through the graph
- call any LLM-backed agents
- write reports or artifacts
- persist graph results anywhere

Those behaviors belong to later build steps.

## State and Contracts

### `PipelineState`

The graph state currently holds three kinds of information:

- data references such as `data_path`, `data`, and `settings`
- agent outputs such as `eda_insights`, `prep_result`, `modeling_results`, `evaluation_result`, and `experiment_report`
- control-flow flags such as `should_loop`, `iteration`, and `current_phase`

### `ExperimentContext`

The shared experiment context currently holds:

- `dataset_info`
- `feature_insights`
- `model_comparisons`
- `agent_reasoning_trace`
- `config_snapshot`

### Structured contracts

The first structured payloads are:

- `EDAOutput`
  Includes row count, feature count, target rate, cleaning flag, summaries, correlation flags, and recommendations.

- `ModelingOutput`
  Includes algorithm, phase, scores, params used, reasoning, and next action.

## Routing Rules

### After EDA

`route_after_eda(state)` does this:

- if `state["eda_insights"]["needs_cleaning"]` is true, route to `data_engineer`
- otherwise route to `ml_modeler`

### After Modeling

`route_after_modeling(state)` does this:

- if `should_loop` is true and `iteration < 5`, route back to `ml_modeler`
- otherwise route to `evaluation`

This gives the graph one early branch and one bounded modeling loop.

## How To Use It

The current use case is structural verification and future integration, not production execution.

### Build and compile the graph

```bash
uv run python -c "from multi_agent_ds.orchestration.graph import build_graph; \
graph = build_graph(); \
compiled = graph.compile(); \
print(type(graph).__name__); \
print(type(compiled).__name__)"
```

Expected output shape:

```text
StateGraph
CompiledStateGraph
```

### Check the router helpers directly

```bash
uv run python -c "from multi_agent_ds.orchestration.router import route_after_eda, route_after_modeling; \
print(route_after_eda({'eda_insights': {'needs_cleaning': True}})); \
print(route_after_eda({'eda_insights': {'needs_cleaning': False}})); \
print(route_after_modeling({'should_loop': True, 'iteration': 0})); \
print(route_after_modeling({'should_loop': True, 'iteration': 5}))"
```

Expected output shape:

```text
data_engineer
ml_modeler
ml_modeler
evaluation
```

### Check the shared types

```bash
uv run python -c "from multi_agent_ds.orchestration.state import PipelineState; \
from multi_agent_ds.core.context import ExperimentContext; \
from multi_agent_ds.core.contracts import EDAOutput, ModelingOutput; \
print(PipelineState.__name__); \
print(ExperimentContext.__name__); \
print(EDAOutput.__name__); \
print(ModelingOutput.__name__)"
```

Expected output shape:

```text
PipelineState
ExperimentContext
EDAOutput
ModelingOutput
```

## Tests

Run the focused Step 7 tests:

```bash
uv run pytest tests/test_langgraph_router.py
uv run pytest tests/test_langgraph_graph.py
```

Or run both together:

```bash
uv run pytest tests/test_langgraph_router.py tests/test_langgraph_graph.py
```

What these tests cover:

- router decisions for cleaning vs direct modeling
- router decisions for looping vs advancing to evaluation
- graph construction
- graph compilation

## Why This Step Matters

This step established the correct orchestration seams before adding real agent logic.

That matters because later steps can now plug real nodes into a stable graph shape instead of inventing routing and state contracts ad hoc inside agents or workflows.

## Agent-Team Summary

- `plan_guardian`
  Kept the explanation aligned to Sean Step 7 and the saved checklist.

- `architecture_guard`
  Confirmed the document explains the real layer boundaries: `orchestration/` for graph logic and `core/` for shared contracts.

- `implementation_engineer`
  Mapped the code that exists today into a practical usage guide and verification commands.

- `efficiency_reviewer`
  Kept the document focused on the thin skeleton that exists now, without inventing extra runtime behavior.

- `commit_chronicler`
  Left unused for this doc-only change until commit time.
