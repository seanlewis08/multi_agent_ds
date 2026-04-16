# LangGraph Skeleton Implementation Plan

**Scope:** Sean Step 2 from `Sean_Plan.md`  
**Primary targets:** `src/multi_agent_ds/orchestration/state.py`, `graph.py`, `router.py`  
**Secondary targets:** `src/multi_agent_ds/core/context.py`, `contracts.py`  
**Status:** Implemented

## Purpose

Build the shared orchestration skeleton that later agents plug into. This step should create the smallest useful graph/state/contracts foundation without pulling in agent logic, workflow side effects, or premature routing complexity.

## Agent-Team Framing

- `plan_guardian`: Keep this scoped to Sean Step 2 only.
- `architecture_guard`: Keep graph/state/routing in `orchestration/` and shared payload/contracts in `core/`.
- `implementation_engineer`: Build the smallest compiling LangGraph skeleton.
- `efficiency_reviewer`: Avoid extra orchestration abstractions, helper layers, or placeholder complexity.
- `commit_chronicler`: Commit only after the skeleton compiles and its focused tests/checks pass.

## Constraints

- Do not add a new dependency.
- Do not add a new script, CLI entrypoint, or notebook.
- Do not put LLM calls in this step.
- Do not implement real agent business logic in this step.
- Prefer placeholder nodes and simple routing over speculative framework code.

## Minimal Target Design

This step should produce:

- a `PipelineState` type in `orchestration/state.py`
- a `build_graph()` function in `orchestration/graph.py`
- basic routing helpers in `orchestration/router.py`
- a small `ExperimentContext` dataclass in `core/context.py`
- minimal Pydantic-style contracts in `core/contracts.py`

The graph only needs to compile. It does not need full end-to-end runtime behavior yet.

## Implementation Steps

### Step 1: Shared State Schema

Implement `PipelineState` in `orchestration/state.py` with:

- `data_path`
- `data`
- `settings`
- `eda_insights`
- `prep_result`
- `modeling_results`
- `evaluation_result`
- `experiment_report`
- `agent_decisions`
- `current_phase`
- `should_loop`
- `iteration`

### Step 2: Core Context and Contracts

Implement:

- `ExperimentContext` in `core/context.py`
- `EDAOutput` in `core/contracts.py`
- `ModelingOutput` in `core/contracts.py`

Keep these minimal and aligned to Sean’s plan examples.

### Step 3: Router Helpers

Implement basic routing helpers in `orchestration/router.py`:

- `route_after_eda`
- `route_after_modeling`

Keep the logic small and state-based only.

### Step 4: Graph Skeleton

Implement `build_graph()` in `orchestration/graph.py`:

- create a `StateGraph(PipelineState)`
- register placeholder nodes
- add the planned edges
- return the graph

Do not implement real node logic here beyond what is needed to compile.

### Step 5: Validation and Import Surface

Validate:

- `from multi_agent_ds.orchestration.graph import build_graph` works
- graph construction works
- graph compiles with placeholder nodes
- the state/contracts/context imports cleanly

## Review and Test Gates

After each step, stop for:

1. human review of the design shape
2. focused validation for that slice
3. checklist/log update before moving on

Recommended validation sequence:

1. import smoke tests for each touched module
2. graph construction smoke test
3. graph compile smoke test

## Done Criteria

This step is complete when:

- `build_graph()` imports and returns a graph object
- the graph compiles with placeholder nodes
- `PipelineState`, `ExperimentContext`, and the initial contracts exist
- Jonathan has a stable skeleton to register his nodes against later

## Resume Instructions

If work pauses, resume from:

- `project_planning/sean_step_artifacts/LangGraph_Skeleton_Checklist.md`

Recommended resume prompt:

```text
Use agent teams for this task. Pick back up where I left off in project_planning/sean_step_artifacts/LangGraph_Skeleton_Checklist.md and continue from the next unchecked item.
```
