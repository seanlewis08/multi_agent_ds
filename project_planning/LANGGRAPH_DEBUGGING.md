# LangGraph Debugging

This document describes the recommended way to debug the routing setup between nodes in the LangGraph workflow.

## Debugging Layers

Use three layers, in this order:

1. local graph rendering
2. local event streaming
3. LangSmith tracing

Why this order:

- graph rendering is best for checking static routing shape
- event streaming is best for checking what actually ran
- LangSmith is best for UI-driven trace inspection once the graph shape is already reasonable

## Local Graph Rendering

Use the helpers in:

- `/Users/sean.lewis/DataspellProjects/multi_agent_ds/src/multi_agent_ds/adapters/agent_frameworks/langgraph.py`

Key functions:

- `get_debug_graph(...)`
- `render_graph_ascii(...)`
- `render_graph_mermaid(...)`

### ASCII

Run:

```bash
uv run python -c "from multi_agent_ds.orchestration.graph import build_graph; \
from multi_agent_ds.adapters.agent_frameworks.langgraph import render_graph_ascii; \
compiled = build_graph().compile(); \
print(render_graph_ascii(compiled, xray=True))"
```

Use this for:

- checking fan-out/fan-in visually
- checking loop edges
- checking merge nodes

### Mermaid

Run:

```bash
uv run python -c "from multi_agent_ds.orchestration.graph import build_graph; \
from multi_agent_ds.adapters.agent_frameworks.langgraph import render_graph_mermaid; \
compiled = build_graph().compile(); \
print(render_graph_mermaid(compiled, xray=True))"
```

Use this for:

- pasting into docs
- visually inspecting the graph in Markdown/Mermaid tools
- confirming the exact edge shape around review nodes

## Local Event Streaming

Use the helpers:

- `stream_graph_events(...)`
- `collect_graph_events(...)`

### Example collection pass

Run:

```bash
uv run python -c "from multi_agent_ds.orchestration.graph import build_graph; \
from multi_agent_ds.adapters.agent_frameworks.langgraph import collect_graph_events; \
events = collect_graph_events( \
    build_graph().compile(), \
    {'data_path': 'data/raw/synthetic_dataset.parquet'}, \
    include_names=['eda_raw', 'ml_modeler_raw_review', 'ml_reviewer_raw_review', 'business_stakeholder_raw_review'], \
); \
print('event_count:', len(events)); \
print('first_event:', events[0] if events else None)"
```

Use this for:

- confirming which nodes actually ran
- checking whether all fan-in branches executed
- checking event order for loops and approvals

## LangSmith Tracing

LangSmith is a good runtime debugger for:

- per-node run traces
- timing
- inputs and outputs
- failures inside a specific branch
- comparing multiple runs

### Current repo defaults

Non-secret defaults live in:

- `/Users/sean.lewis/DataspellProjects/multi_agent_ds/config/settings.yaml`

Current keys:

- `debug.langgraph.xray`
- `debug.langgraph.event_stream.version`
- `debug.langgraph.event_stream.verbose`
- `debug.langsmith.enabled`
- `debug.langsmith.project`

### Required environment variables

Set these in your shell or `.env`:

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=your-key
export LANGSMITH_PROJECT=multi_agent_ds_graph_debug
```

Then run the graph normally. If tracing is enabled in env, LangChain/LangGraph will send trace data to LangSmith.

## Which Tool To Use

### Use ASCII or Mermaid when

- a route looks wrong
- a fan-out/fan-in looks wrong
- a loop edge looks wrong
- you want to confirm the static graph shape

### Use event streaming when

- the graph shape looks correct but execution behaves incorrectly
- you want to see which nodes actually ran
- you want to inspect branch behavior without opening LangSmith

### Use LangSmith when

- you want a UI
- you need per-node timing
- you want to inspect nested run data
- you are debugging a real invocation rather than just the graph shape

## Best Practice For This Repo

For this graph, the fastest debugging sequence is:

1. render ASCII with `xray=True`
2. render Mermaid with `xray=True`
3. collect a small event trace with `include_names=...`
4. only then enable LangSmith if you need full trace UI
