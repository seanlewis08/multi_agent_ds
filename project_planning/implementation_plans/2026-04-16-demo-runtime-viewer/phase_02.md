# Demo Runtime Viewer Implementation Plan — Phase 2

**Goal:** Produce a deterministic JSON event log from a real `eda_analyst → data_engineer` run. This is the "record" half of the record-once-replay-many pattern.

**Architecture:** A new module `src/multi_agent_ds/orchestration/demo_recorder.py` composes the two existing agent nodes (`eda_analyst_node(state, mode="raw")` and `data_engineer_node(state, mode="execute")`) into a minimal `StateGraph`. It runs the graph via `astream_events(version="v2")`, normalizes each event into a flat `{ts, elapsed_ms, kind, node, data}` record, and writes everything (config + artifacts + events) atomically to `data/interim/demo_run_latest.json`.

**Tech Stack:** Python 3.11+, LangGraph, pandas, pyarrow, pytest.

**Scope:** Phase 2 of 7.

**Codebase verified:** 2026-04-16.
- `src/multi_agent_ds/agents/eda_analyst.py:107` exports `eda_analyst_node(state: PipelineState, mode: str = "raw") -> dict[str, Any]`. Mode `"raw"` is the correct mode for initial profiling.
- `src/multi_agent_ds/agents/data_engineer.py:32` exports `data_engineer_node(state: PipelineState, mode: str = "feedback") -> dict[str, Any]`. Mode `"execute"` is the correct mode for applying the prep plan.
- `src/multi_agent_ds/orchestration/state.py` defines `PipelineState` as a `TypedDict` with 33 fields.
- `src/multi_agent_ds/core/config.py:49` exports `load_settings() -> dict[str, Any]`.
- `src/multi_agent_ds/core/context.py` defines `ExperimentContext` dataclass; **no `build_context()` helper exists**. Design plan mention was aspirational.
- `src/multi_agent_ds/adapters/llm/openai.py` guards `os.getenv("OPENAI_API_KEY")` and raises `ValueError` if missing. We mirror this pattern.
- `src/multi_agent_ds/workflows/modeling.py:484` is the existing precedent for a `python -m ...` entry point. It uses stdlib `argparse` with `--algorithms` override. Mirror this style.
- No existing LangGraph `astream_events` usage in the repo — this phase introduces the pattern.
- Tests live under `tests/unit/` with plain `assert` and `pytest`. `tests/conftest.py` is an empty placeholder.

---

## Acceptance Criteria Coverage

This phase implements and tests:

### demo-runtime-viewer.AC1: Recording
- **demo-runtime-viewer.AC1.1 Success:** `demo_recorder.py --output data/interim/demo_run_latest.json` writes a JSON file whose top-level `events` array contains at minimum one event with `kind: "node_start", node: "eda_raw"`, one with `kind: "node_end", node: "eda_raw"`, one with `kind: "node_start", node: "data_engineer"`, and one with `kind: "node_end", node: "data_engineer"`.
- **demo-runtime-viewer.AC1.2 Success:** The recorded JSON includes `artifacts.raw_eda_insights` (the EDA agent's structured output) and `artifacts.prep_plan` + `artifacts.processed_df_head` (the Data Engineer's outputs).
- **demo-runtime-viewer.AC1.3 Success:** Every event has `ts` (ISO-8601 timestamp) and `elapsed_ms` (ms since recording started).
- **demo-runtime-viewer.AC1.4 Failure:** If the configured parquet path does not exist, the recorder raises a clear `FileNotFoundError` naming the missing path and does not write a partial JSON.
- **demo-runtime-viewer.AC1.5 Failure:** If `OPENAI_API_KEY` is unset, the recorder raises a clear `RuntimeError` before invoking the graph.
- **demo-runtime-viewer.AC1.6 Edge:** Re-running the recorder atomically replaces `data/interim/demo_run_latest.json` (writes to `.tmp` sibling, then renames).

---

## DEMO-TIME ADDENDUM: --no-upload mode

Added on 2026-04-16 (day before demo). Sean is offline from AWS SSO during Phase 2 rehearsal, so the recorder gained a `--no-upload` flag that bypasses S3 and writes the processed parquet locally to `data/processed/{filename}`.

### When to use
- Only for demo rehearsal and offline recording runs.
- Never in production Streamlit runs.

### How to restore S3 upload mode (when back on AWS)
1. Authenticate: `aws sso login --profile data-science`
2. Run the recorder WITHOUT the flag:
   ```bash
   uv run python -m multi_agent_ds.orchestration.demo_recorder --output data/interim/demo_run_latest.json --parquet data/raw/synthetic_dataset.parquet
   ```
3. The default behavior uploads to S3 exactly as before. No code change needed.

### Related env fixup (user-local)
`.env` must have `OPENAI_BASE_URL=https://api.openai.com/v1` (or the line removed entirely) for `sk-proj-...` keys. The previous `https://us.api.openai.com/v1` only worked with service-account keys.

### Bug fix carried along
`record_run` now calls `load_dotenv()` before `preflight()`, so `.env`-only keys are detected. Previously preflight checked `os.environ` directly and failed even when the key was present in `.env`.

### Implementation details
- `run_preparation_workflow` gained `local_only: bool = False` parameter
- `data_engineer_node` forwards `local_only` from state to the workflow
- `demo_recorder.main()` accepts `--no-upload` flag and passes `local_only=True` to `record_run`
- When `local_only=True`, processed parquet is written to `data/processed/{filename}` (from settings) as an absolute path
- Downstream readers (e.g., viewer) can read the local path via `pd.read_parquet(processed_data_path)` — no changes needed

---

<!-- START_SUBCOMPONENT_A (tasks 1-3) -->
<!-- START_TASK_1 -->
### Task 1: Pure event-normalization helpers

**Active role:** `implementation_engineer` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/implementation-engineer.md` for load-bearing decisions within this task.

**Verifies:** demo-runtime-viewer.AC1.3 (shape of each event record).

**Files:**
- Create: `src/multi_agent_ds/orchestration/demo_recorder.py` (top portion: module docstring, imports, pure helper functions only)
- Test: `tests/unit/orchestration/test_demo_recorder_events.py` (unit tests for the pure helpers)

**Implementation (Functional Core):**
These helpers are pure — no I/O, no clock reads (accept `ts` / `elapsed_ms` as args), no network. Live at the top of `demo_recorder.py`.

```python
"""Demo recorder: run eda_analyst -> data_engineer as a minimal sub-graph
and write an event log to data/interim/demo_run_latest.json for later
replay by src/multi_agent_ds/demo_viewer.html.

This module is the 'record' half of the record-once-replay-many demo.
It lives at the orchestration layer and composes existing agent nodes
without modifying the production graph (src/multi_agent_ds/orchestration/graph.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

# Node kinds we expose in the event log. Keep this a closed enum — the viewer
# relies on these exact strings.
NODE_START = "node_start"
NODE_END = "node_end"
NODE_ERROR = "node_error"

# LangGraph event kinds we care about. We filter events by kind and by node
# name so the log stays small and replay-friendly.
LG_ON_CHAIN_START = "on_chain_start"
LG_ON_CHAIN_END = "on_chain_end"
LG_ON_CHAIN_ERROR = "on_chain_error"

# Nodes we record. The prep_plan_stage is internal and not shown in the viewer
# (visually simpler — only two recorded agent columns). Other node-level events
# (if any emerge from sub-runnables) are ignored by the recorder.
RECORDED_NODES = frozenset({"eda_raw", "data_engineer"})


@dataclass(frozen=True)
class NormalizedEvent:
    """A flat, JSON-serializable shape the viewer consumes."""
    ts: str              # ISO-8601 UTC, ends in 'Z'
    elapsed_ms: int      # ms since recording started
    kind: str            # one of NODE_START / NODE_END / NODE_ERROR
    node: str            # node name from LangGraph (e.g. 'eda_raw')
    data: dict[str, Any] # payload (input or output) — small, JSON-safe

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "elapsed_ms": self.elapsed_ms,
            "kind": self.kind,
            "node": self.node,
            "data": self.data,
        }


def iso_utc(now: datetime) -> str:
    """Format a datetime as ISO-8601 with 'Z' suffix.
    
    Input must be tz-aware; naive datetimes will raise on `.astimezone(...)`.
    """
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def langgraph_event_kind(lg_event: str) -> str | None:
    """Translate a LangGraph event string into our closed vocabulary.

    Returns None for events we do not record.
    """
    return {
        LG_ON_CHAIN_START: NODE_START,
        LG_ON_CHAIN_END: NODE_END,
        LG_ON_CHAIN_ERROR: NODE_ERROR,
    }.get(lg_event)


def should_record(lg_event: dict[str, Any]) -> bool:
    """Return True iff this LangGraph event should appear in the log.

    Gates on both event kind (on_chain_*) and node name (eda_raw / data_engineer).
    Rejects LLM-level events (on_llm_*, on_chat_model_*) and sub-tool events.
    """
    if langgraph_event_kind(lg_event.get("event", "")) is None:
        return False
    name = lg_event.get("name", "")
    return name in RECORDED_NODES


def normalize_event(
    lg_event: dict[str, Any],
    *,
    ts: str,
    elapsed_ms: int,
) -> NormalizedEvent:
    """Convert a LangGraph v2 event dict into our NormalizedEvent shape.

    Preconditions: should_record(lg_event) is True.

    The `data` field is the LangGraph event's `data` payload, shallow-copied
    and filtered to primitives we can JSON-serialize safely. Callers must
    ensure non-JSON-safe values (e.g. DataFrames) are stripped BEFORE calling
    — see sanitize_payload in Task 2.
    """
    kind = langgraph_event_kind(lg_event["event"])
    assert kind is not None, "should_record lied about event"
    return NormalizedEvent(
        ts=ts,
        elapsed_ms=elapsed_ms,
        kind=kind,
        node=lg_event["name"],
        data=dict(lg_event.get("data", {})),
    )
```

**Testing (Functional Core is easy to test — plain assert):**
Create `tests/unit/orchestration/__init__.py` if the directory doesn't exist (empty file). Create `tests/unit/orchestration/test_demo_recorder_events.py`:

Tests should assert:
- `iso_utc(datetime(2026, 4, 16, 14, 3, 22, 456789, tzinfo=timezone.utc))` returns exactly `"2026-04-16T14:03:22.456Z"` (ISO-8601 with millisecond precision and `Z` suffix — AC1.3 ordering/timestamp shape).
- `langgraph_event_kind("on_chain_start")` returns `"node_start"`; `langgraph_event_kind("on_chat_model_start")` returns `None`; `langgraph_event_kind("garbage")` returns `None`.
- `should_record({"event": "on_chain_start", "name": "eda_raw"})` returns `True`; `should_record({"event": "on_chain_start", "name": "orchestrator"})` returns `False`; `should_record({"event": "on_llm_start", "name": "eda_raw"})` returns `False`.
- `normalize_event({...valid...}, ts="t", elapsed_ms=42).to_dict()` returns a dict with exactly the five keys `ts, elapsed_ms, kind, node, data` and `kind == "node_start"` when input event is `on_chain_start`.

Follow the existing test style at `tests/unit/test_evaluation_workflow.py`: plain `assert`, one function per case, no special fixtures.

**Step 1: Write the failing test**
Use `Write` to create the test file. Implement four test functions covering the four bullet assertions above.

**Step 2: Run the test to confirm it fails (RED)**
```bash
uv run pytest tests/unit/orchestration/test_demo_recorder_events.py -v
```
Expected: `ModuleNotFoundError: No module named 'multi_agent_ds.orchestration.demo_recorder'`. That's the expected RED state.

**Step 3: Write the minimal implementation**
Create `src/multi_agent_ds/orchestration/demo_recorder.py` with exactly the code block shown above (imports + constants + `NormalizedEvent` + `iso_utc` + `langgraph_event_kind` + `should_record` + `normalize_event`). Stop after `normalize_event`. Do NOT add any impure code yet — that lands in Task 3.

**Step 4: Run tests to confirm GREEN**
```bash
uv run pytest tests/unit/orchestration/test_demo_recorder_events.py -v
```
Expected: all four tests pass.

**Step 5: Commit**
```bash
git status   # confirm only demo_recorder.py and the new test file appear
git add src/multi_agent_ds/orchestration/demo_recorder.py tests/unit/orchestration/__init__.py tests/unit/orchestration/test_demo_recorder_events.py
git commit -m "feat(orchestration): pure event-normalization helpers for demo_recorder

why: first slice of the demo recorder. Pure helpers only (FCIS
functional core) so the event shape and filter rules are
test-locked before any I/O lands. Shape matches the JSON contract
in project_planning/design_plans/2026-04-16-demo-runtime-viewer.md
lines 111-131.

architecture fit: orchestration/ layer, top of new module.

validation: uv run pytest tests/unit/orchestration/test_demo_recorder_events.py -v — 4 passed.

notes: impure LangGraph driver + file I/O arrives in Task 3.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
<!-- END_TASK_1 -->

<!-- START_TASK_2 -->
### Task 2: Pure artifact extraction and payload sanitization

**Active role:** `implementation_engineer` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/implementation-engineer.md` for load-bearing decisions within this task.

**Verifies:** demo-runtime-viewer.AC1.2 (artifacts block shape).

**Files:**
- Modify: `src/multi_agent_ds/orchestration/demo_recorder.py` (append a new pure-function section BELOW the normalization helpers; above the line where impure code will start)
- Test: `tests/unit/orchestration/test_demo_recorder_artifacts.py`

**Implementation:**
These helpers extract the `artifacts` block from the final `PipelineState` and sanitize event `data` payloads so they are JSON-serializable. Still pure — takes state dicts in, returns dicts out.

```python
# --- Artifact extraction (pure) ----------------------------------------

# Keys we copy out of PipelineState into the top-level artifacts block.
# Stay minimal — the viewer only needs these.
_EDA_ARTIFACT_KEY = "raw_eda_insights"
_DE_PREP_PLAN_KEY = "prep_plan"
_DE_PROCESSED_DF_HEAD_KEY = "processed_df_head"   # added by recorder post-run from parquet
_DE_PROCESSED_DF_STATS_KEY = "processed_df_stats" # added by recorder post-run from parquet
_INPUT_DF_HEAD_KEY = "input_df_head"              # added by recorder pre-run
_INPUT_DF_STATS_KEY = "input_df_stats"            # added by recorder pre-run


def extract_artifacts(final_state: dict[str, Any]) -> dict[str, Any]:
    """Pull the viewer-facing artifact dict out of the final PipelineState.

    Missing keys resolve to None (not an error) so the recorder can still
    produce a JSON even when the graph halted early. The viewer treats
    None as 'unavailable'.
    """
    return {
        "raw_eda_insights": final_state.get(_EDA_ARTIFACT_KEY),
        "prep_plan": final_state.get(_DE_PREP_PLAN_KEY),
        "processed_df_head": final_state.get(_DE_PROCESSED_DF_HEAD_KEY),
        "processed_df_stats": final_state.get(_DE_PROCESSED_DF_STATS_KEY),
        "input_df_head": final_state.get(_INPUT_DF_HEAD_KEY),
        "input_df_stats": final_state.get(_INPUT_DF_STATS_KEY),
    }


# --- Payload sanitization (pure) ---------------------------------------

def sanitize_payload(value: Any, *, max_depth: int = 6) -> Any:
    """Recursively strip non-JSON-serializable values from an event payload.

    Policy:
      - primitives pass through
      - dict / list / tuple recurse
      - anything else (DataFrame, numpy array, Series, objects) becomes
        its repr() truncated to 200 chars
      - depth cap prevents infinite recursion on circular refs

    This runs on every LangGraph event `data` field before we stash it.
    """
    if max_depth <= 0:
        return f"<max-depth: {type(value).__name__}>"
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): sanitize_payload(v, max_depth=max_depth - 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_payload(v, max_depth=max_depth - 1) for v in value]
    # Fallback: repr-truncate anything else (DataFrame, ndarray, custom classes).
    r = repr(value)
    return r if len(r) <= 200 else r[:197] + "..."
```

**Testing:**
Add tests to `tests/unit/orchestration/test_demo_recorder_artifacts.py`:
- `extract_artifacts({"raw_eda_insights": {"x": 1}, "prep_plan": {"y": 2}, "processed_df_head": [{"a": 1}], "processed_df_stats": {"rows": 10}, "input_df_head": [{"b": 2}], "input_df_stats": {"rows": 10}})` returns a dict with all six keys populated.
- `extract_artifacts({})` returns a dict with six keys, all `None` (no KeyError).
- `extract_artifacts` correctly reads `processed_df_head` and `processed_df_stats` that were seeded by the recorder's post-run parquet read.
- `sanitize_payload({"a": 1, "b": [1, 2.0, "three"]})` passes primitives through unchanged.
- `sanitize_payload(pandas.DataFrame({"x": [1, 2]}))` returns a string (repr-truncated).
- `sanitize_payload({"nested": {"deep": {"level": 7}}}, max_depth=2)` yields `<max-depth: int>` at the leaf depth.

**Step 1–5:** Same RED-GREEN-REFACTOR + commit cycle as Task 1. Commit message:
```
feat(orchestration): pure artifact extraction + payload sanitization

why: Second pure slice of demo_recorder. extract_artifacts pulls
the five viewer-facing keys out of PipelineState with None defaults
so partial runs still produce usable JSON. sanitize_payload strips
non-JSON types (DataFrames, ndarrays) before they reach json.dumps.

architecture fit: orchestration/ layer, appended to demo_recorder.py
above any impure code.

validation: uv run pytest tests/unit/orchestration/ -v — all tests pass.

notes: sanitize_payload uses repr-truncation at 200 chars for the
fallback, matching what we show in the viewer's event lane.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```
<!-- END_TASK_2 -->

<!-- START_TASK_3 -->
### Task 3: Atomic file-write helper

**Active role:** `implementation_engineer` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/implementation-engineer.md` for load-bearing decisions within this task.

**Verifies:** demo-runtime-viewer.AC1.6 (atomic replacement).

**Files:**
- Modify: `src/multi_agent_ds/orchestration/demo_recorder.py` (append atomic-write helper)
- Test: `tests/unit/orchestration/test_demo_recorder_atomic.py`

**Implementation:**
Standard atomic-write pattern: write to `target.tmp`, `os.replace` to `target`. This helper is the only place I/O touches the recorder — keep it narrow.

```python
# --- Atomic write (impure, but narrow and well-tested) -----------------

import json
import os
from pathlib import Path


def atomic_write_json(payload: dict[str, Any], target: Path) -> None:
    """Write `payload` as JSON to `target` atomically.

    Writes to `target.with_suffix(target.suffix + '.tmp')` first, then
    os.replace() to the target path. This guarantees that readers never
    see a half-written file: either the old JSON (previous demo run) or
    the new JSON — never a truncated blend.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False, default=str), encoding="utf-8")
    os.replace(tmp, target)
```

**Testing:**
Use `tmp_path` pytest fixture. Assertions:
- `atomic_write_json({"a": 1}, tmp_path / "out.json")` creates `out.json` with parseable JSON.
- After writing, no `out.json.tmp` remains (it was replaced).
- Calling `atomic_write_json({"b": 2}, tmp_path / "out.json")` twice replaces the file; the second write wins and the file is intact.
- Simulate an interrupted write by manually dropping a pre-existing `out.json.tmp` with junk contents; subsequent `atomic_write_json` succeeds and overwrites it.

**Step 1–5:** Same RED-GREEN-REFACTOR + commit cycle. Commit message:
```
feat(orchestration): atomic JSON writer for demo recorder

why: AC1.6 requires re-running the recorder to atomically replace
data/interim/demo_run_latest.json. Write-tmp-then-rename pattern
guarantees the viewer never reads a half-written file.

architecture fit: orchestration/ layer. Only I/O surface in the
recorder so far — impure but narrow.

validation: uv run pytest tests/unit/orchestration/test_demo_recorder_atomic.py -v — 4 passed.

notes: json.dumps uses default=str so stray datetime / Path
values serialize as their repr without raising.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```
<!-- END_TASK_3 -->
<!-- END_SUBCOMPONENT_A -->

<!-- START_SUBCOMPONENT_B (tasks 4-5) -->
<!-- START_TASK_4 -->
### Task 4: Build the three-node sub-graph

**Active role:** `architecture_guard` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/architecture-guard.md` for load-bearing decisions within this task.

**Verifies:** demo-runtime-viewer.AC1.1 (events present for both nodes, in correct order).

**Files:**
- Modify: `src/multi_agent_ds/orchestration/demo_recorder.py` (append sub-graph builder)
- Test: `tests/unit/orchestration/test_demo_recorder_subgraph.py`

**Implementation:**
Compose `eda_analyst_node(state, mode="raw")` and `data_engineer_node(state, mode="execute")` into a fresh `StateGraph[PipelineState]`. Do NOT touch `src/multi_agent_ds/orchestration/graph.py` — this is a separate, minimal graph.

The LangGraph node name registered with `add_node("eda_raw", ...)` becomes the value of `event["name"]` in the event stream — that's the coupling point with `RECORDED_NODES`.

Because the existing node functions take a `mode` positional argument, wrap them in partials so the graph receives the correct mode-fixed callable.

```python
# --- Sub-graph builder -------------------------------------------------

from functools import partial
from langgraph.graph import StateGraph, END

from multi_agent_ds.agents.eda_analyst import eda_analyst_node
from multi_agent_ds.agents.data_engineer import data_engineer_node
from multi_agent_ds.orchestration.state import PipelineState


def build_demo_subgraph():
    """Compile a minimal StateGraph with optional prep_plan stage.

    The graph is: eda_raw -> prep_plan_stage -> data_engineer -> END.
    Node names ('eda_raw', 'data_engineer') match RECORDED_NODES so
    should_record() filters the event stream. The prep_plan_stage is
    internal — the viewer only sees eda_raw and data_engineer events
    (simpler visual presentation) but the sub-graph internally runs
    all three nodes so data_engineer gets the prep plan it needs.
    """
    g = StateGraph(PipelineState)
    g.add_node("eda_raw", partial(eda_analyst_node, mode="raw"))
    # prep_plan_stage runs internally but is not recorded (keep viewer simple)
    g.add_node("prep_plan_stage", partial(eda_analyst_node, mode="prep_plan"))
    g.add_node("data_engineer", partial(data_engineer_node, mode="execute"))
    g.set_entry_point("eda_raw")
    g.add_edge("eda_raw", "prep_plan_stage")
    g.add_edge("prep_plan_stage", "data_engineer")
    g.add_edge("data_engineer", END)
    return g.compile()
```

**Testing:**
Integration-lite — exercise the graph with a tiny fake state that doesn't need LLM calls. Monkeypatch both node callables with stubs that return small dicts. Assert:
- `build_demo_subgraph()` returns a compiled graph with expected node names (`list(graph.get_graph().nodes) == ["__start__", "eda_raw", "data_engineer", "__end__"]` or similar — check the actual LangGraph API).
- With monkeypatched nodes, invoking the compiled graph with a minimal `PipelineState` produces the final state combining both stub outputs.

```python
# sketch — fill in actual assertions per LangGraph's get_graph() return shape.
def test_subgraph_has_expected_nodes(monkeypatch):
    from multi_agent_ds.orchestration import demo_recorder as R
    monkeypatch.setattr(R, "eda_analyst_node", lambda state, mode: {"raw_eda_insights": {"stub": True}})
    monkeypatch.setattr(R, "data_engineer_node", lambda state, mode: {"prep_plan": {"stub": True}})
    graph = R.build_demo_subgraph()
    nodes = set(graph.get_graph().nodes)
    assert {"eda_raw", "data_engineer"}.issubset(nodes)
```

**Step 1–5:** RED-GREEN-REFACTOR + commit. Commit message:
```
feat(orchestration): compile three-node sub-graph for demo recorder

why: AC1.1 requires both eda_raw and data_engineer node events in
the log. Data engineer needs the prep_plan from mode='prep_plan'.
Sub-graph composes existing agent nodes with mode fixed via
functools.partial — no changes to graph.py, no changes to agent
implementations. prep_plan_stage runs internally but is not shown
in the viewer (keeps visual simpler: only two recorded columns).

architecture fit: orchestration/ layer composes workflows/ + agents/
via LangGraph StateGraph. Same pattern as the production graph.

validation: uv run pytest tests/unit/orchestration/test_demo_recorder_subgraph.py -v — passes.

notes: node names ('eda_raw', 'data_engineer') match RECORDED_NODES
exactly. prep_plan_stage is internal only — not in RECORDED_NODES.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

**Done when:** The sub-graph runs internally with all three nodes; the viewer only records and displays eda_raw and data_engineer.

<!-- END_TASK_4 -->

<!-- START_TASK_5 -->
### Task 5: Env-var + parquet preflight guards

**Active role:** `implementation_engineer` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/implementation-engineer.md` for load-bearing decisions within this task.

**Verifies:** demo-runtime-viewer.AC1.4 (parquet missing), demo-runtime-viewer.AC1.5 (OPENAI_API_KEY missing).

**Files:**
- Modify: `src/multi_agent_ds/orchestration/demo_recorder.py` (append `preflight()` helper)
- Test: `tests/unit/orchestration/test_demo_recorder_preflight.py`

**Implementation:**
```python
# --- Preflight guards --------------------------------------------------

def preflight(*, parquet_path: Path) -> None:
    """Raise early with a clear message if the recorder can't run.

    Checked conditions:
      - OPENAI_API_KEY must be set (RuntimeError, mirrors
        adapters/llm/openai.py)
      - parquet_path must exist on disk (FileNotFoundError, includes
        the resolved absolute path in the message)

    Called before any graph invocation or file write so partial JSON
    is never produced.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Set it in your environment or .env "
            "before running the demo recorder. The recorder invokes LLM "
            "agents and cannot proceed without an API key."
        )
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Input parquet not found at {parquet_path.resolve()}. "
            f"Check config/settings.yaml -> data.source or pass --parquet."
        )
```

**Testing:**
Use `monkeypatch.delenv("OPENAI_API_KEY", raising=False)` and `tmp_path` for the parquet. Assertions:
- `preflight(parquet_path=tmp_path / "missing.parquet")` raises `RuntimeError` when `OPENAI_API_KEY` is unset (check regardless of parquet presence).
- With `OPENAI_API_KEY` set but parquet missing, raises `FileNotFoundError` containing the resolved path.
- With both set, returns `None` (no exception).

**Step 1–5:** RED-GREEN-REFACTOR + commit. Commit message:
```
feat(orchestration): preflight guards for demo recorder

why: AC1.4/1.5 require clear, early errors rather than opaque
deep-stack failures. preflight() runs before any graph work and
before any JSON is written, so a missing key or file never
leaves a partial recording behind.

architecture fit: orchestration/ layer, appended to demo_recorder.py.

validation: uv run pytest tests/unit/orchestration/test_demo_recorder_preflight.py -v — 3 passed.

notes: error messages are user-facing; they reference config paths
so a human can self-diagnose.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```
<!-- END_TASK_5 -->
<!-- END_SUBCOMPONENT_B -->

<!-- START_SUBCOMPONENT_C (tasks 6-7) -->
<!-- START_TASK_6 -->
### Task 6: Async recording driver

**Active role:** `implementation_engineer` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/implementation-engineer.md` for load-bearing decisions within this task.

**Verifies:** demo-runtime-viewer.AC1.1, AC1.2, AC1.3 end-to-end.

**Files:**
- Modify: `src/multi_agent_ds/orchestration/demo_recorder.py` (append `record_run()` async driver)
- Test: covered by the integration run in Task 8 (no unit test — this function is the impure orchestrator)

**Implementation:**
```python
# --- Async driver ------------------------------------------------------

import asyncio
import time
from datetime import datetime, timezone

import pandas as pd

from multi_agent_ds.core.config import load_settings


async def record_run(
    *,
    parquet_path: Path,
    output_path: Path,
    target_column: str | None = None,
) -> dict[str, Any]:
    """Record one eda_raw -> data_engineer run and write the event log.

    Returns the payload dict that was written (handy for tests and the CLI
    to report a summary).

    Flow:
      1. preflight() — fail fast on missing env / parquet
      2. load settings and raw DataFrame
      3. seed input_df_head / input_df_stats into the initial state
      4. compile the sub-graph
      5. async-iterate astream_events(version='v2'), record filtered events
      6. collect final state, extract artifacts, assemble payload
      7. atomic_write_json to output_path
    """
    preflight(parquet_path=parquet_path)

    settings = load_settings()
    target = target_column or _resolve_target(settings)

    df = pd.read_parquet(parquet_path)
    input_df_head = df.head(10).to_dict(orient="records")
    input_df_stats = _compute_input_stats(df, target=target)

    initial_state: dict[str, Any] = {
        "data_path": str(parquet_path),
        # state["data"] expects dict[str, Any] (see PipelineState); DataFrame passes via data_path
        "settings": settings,
        "input_df_head": input_df_head,
        "input_df_stats": input_df_stats,
    }

    graph = build_demo_subgraph()

    events: list[dict[str, Any]] = []
    final_state: dict[str, Any] = dict(initial_state)
    start_monotonic = time.monotonic()
    start_ts = datetime.now(timezone.utc)

    async for lg_event in graph.astream_events(input=initial_state, version="v2"):
        if not should_record(lg_event):
            continue
        elapsed_ms = int((time.monotonic() - start_monotonic) * 1000)
        ts = iso_utc(datetime.now(timezone.utc))
        safe_data = sanitize_payload(lg_event.get("data", {}))
        normalized = normalize_event({**lg_event, "data": safe_data}, ts=ts, elapsed_ms=elapsed_ms)
        events.append(normalized.to_dict())
        # Keep a running copy of the final state by merging end-event outputs.
        if normalized.kind == NODE_END and isinstance(safe_data.get("output"), dict):
            final_state.update(safe_data["output"])

    # Read processed parquet and populate processed_df_head / processed_df_stats
    processed_path = final_state.get("processed_data_path")
    if processed_path and Path(processed_path).exists():
        pdf = pd.read_parquet(processed_path)
        final_state["processed_df_head"] = pdf.head(10).to_dict(orient="records")
        missing_pct = round(float(pdf.isna().mean().mean()) * 100.0, 3)
        final_state["processed_df_stats"] = {
            "rows": int(pdf.shape[0]),
            "cols": int(pdf.shape[1]),
            "path": processed_path,
            "missing_pct_after": missing_pct,
        }

    duration_ms = int((time.monotonic() - start_monotonic) * 1000)
    artifacts = extract_artifacts(final_state)

    payload = {
        "recorded_at": iso_utc(start_ts),
        "duration_ms": duration_ms,
        "config": _config_snapshot(settings, parquet_path=str(parquet_path)),
        "artifacts": artifacts,
        "events": events,
    }
    atomic_write_json(payload, output_path)
    return payload


def _compute_input_stats(df: pd.DataFrame, *, target: str) -> dict[str, Any]:
    """Tiny stats block consumed by the Input Preview screen."""
    numeric = df.select_dtypes(include="number").shape[1]
    categorical = df.shape[1] - numeric
    missing_pct = float(df.isna().mean().mean()) * 100.0
    positive_rate: float | None = None
    if target in df.columns and pd.api.types.is_numeric_dtype(df[target]):
        positive_rate = float(df[target].astype(float).mean())
    return {
        "rows": int(df.shape[0]),
        "cols": int(df.shape[1]),
        "target": target,
        "positive_rate": positive_rate,
        "numeric": int(numeric),
        "categorical": int(categorical),
        "missing_pct": round(missing_pct, 3),
    }


def _resolve_target(settings: dict[str, Any]) -> str:
    """Resolve the target column name from settings."""
    data = settings.get("data", {})
    source_mode = data.get("source", "synthetic")
    if source_mode == "synthetic":
        return data.get("synthetic", {}).get("target", {}).get("column_name", "target")
    else:
        return data.get("existing", {}).get("target_column", "target")


def _config_snapshot(settings: dict[str, Any], *, parquet_path: str) -> dict[str, Any]:
    """Project settings into the small dict the Config screen shows."""
    data = settings.get("data", {})
    source_mode = data.get("source", "synthetic")
    syn = data.get("synthetic", {})
    existing = data.get("existing", {})
    target = (
        syn.get("target", {}).get("column_name")
        if source_mode == "synthetic"
        else existing.get("target_column")
    )
    scale = syn.get("scale") if source_mode == "synthetic" else "existing"
    model = settings.get("model", {})
    tuning = model.get("tuning", {})
    return {
        "source": str(parquet_path),
        "source_mode": source_mode,
        "target": target,
        "scale": scale,
        "max_trials": tuning.get("max_trials"),
        "cv_folds": model.get("cv_folds"),
        "timeout": tuning.get("timeout"),
        "algorithms": list(model.get("algorithms", [])),
        "primary_metric": model.get("primary_metric"),
        "tiebreaker": None,  # not configured in settings.yaml
        "ml_reviewer": "enabled",  # placeholder; adjust once real routing config is wired
        "business_stakeholder": "enabled",
        "report_writer": "enabled",
        "tracing": settings.get("llm", {}).get("tracing", "disabled"),
        # no `review` block exists in settings.yaml; omit or set None
        "review_enabled": None,
        "review_threshold": None,
    }
```

**Testing:**
This function is an impure orchestrator integrating LangGraph, pandas, and file I/O. We do not mock LangGraph internals — that would be testing wiring, not behavior. Validation happens via the end-to-end CLI run in Task 8.

**Step 1: Implement the code block above**
Append to `demo_recorder.py`.

**Step 2: Run existing unit tests to confirm no regressions**
```bash
uv run pytest tests/unit/orchestration/ -v
```
Expected: every previously-passing test still passes.

**Step 3: Commit**
```
feat(orchestration): async record_run driver for demo recorder

why: Impure shell that glues pure helpers together: preflight ->
load -> seed state -> compile graph -> iterate astream_events ->
extract artifacts -> atomic_write. Keeps the functional core
(Tasks 1-3) untouched.

architecture fit: orchestration/ layer. Composes workflows/
(config) + agents/ (via sub-graph). Does not import skills/ or tools/.

validation: uv run pytest tests/unit/orchestration/ -v — all
previously-passing tests still pass. End-to-end run happens in
Task 8.

notes: final_state accumulation piggybacks on NODE_END event
outputs so we don't have to touch PipelineState mutations.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```
<!-- END_TASK_6 -->

<!-- START_TASK_7 -->
### Task 7: `__main__` CLI entry point

**Active role:** `implementation_engineer` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/implementation-engineer.md` for load-bearing decisions within this task.

**Verifies:** demo-runtime-viewer.AC1.1 (CLI command produces the file).

**Files:**
- Modify: `src/multi_agent_ds/orchestration/demo_recorder.py` (append `main()` + `if __name__ == "__main__":` block)

**Implementation:**
Mirror the `argparse` style already used in `src/multi_agent_ds/workflows/modeling.py:484`. Keep the CLI surface tiny: `--output` and `--parquet`.

```python
# --- CLI entry point ---------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``uv run python -m multi_agent_ds.orchestration.demo_recorder``."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="multi_agent_ds.orchestration.demo_recorder",
        description="Record a demo run of eda_raw -> data_engineer to JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/interim/demo_run_latest.json"),
        help="Destination JSON path (default: data/interim/demo_run_latest.json)",
    )
    parser.add_argument(
        "--parquet",
        type=Path,
        default=None,
        help="Override the parquet path (default: config/settings.yaml -> data.source)",
    )
    args = parser.parse_args(argv)

    # Resolve parquet path from args or settings
    if args.parquet is not None:
        parquet_path = args.parquet
    else:
        settings = load_settings()
        source = settings.get("data", {}).get("source")
        if not source:
            raise ValueError("config/settings.yaml must define data.source or pass --parquet")
        parquet_path = Path(source)

    payload = asyncio.run(record_run(parquet_path=parquet_path, output_path=args.output))

    print(
        f"wrote {args.output} — {len(payload['events'])} events, "
        f"duration {payload['duration_ms']} ms"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
```

**Step 1: Append code to `demo_recorder.py`.**

**Step 2: Dry-run the CLI help to confirm argparse is wired correctly**
```bash
uv run python -m multi_agent_ds.orchestration.demo_recorder --help
```
Expected: prints the argparse help block. No import errors.

**Step 3: Smoke-test the full run (costs real OpenAI tokens — one-time)**
```bash
uv run python -m multi_agent_ds.orchestration.demo_recorder \
  --output data/interim/demo_run_latest.json
```
Expected: prints `wrote data/interim/demo_run_latest.json — N events, duration M ms` where N >= 4.

**Step 4: Inspect the JSON shape**
```bash
uv run python -c "
import json
log = json.loads(open('data/interim/demo_run_latest.json').read())
kinds = [(e['kind'], e['node']) for e in log['events']]
print('events:', kinds)
print('artifact keys:', list(log['artifacts'].keys()))
print('config keys:', list(log['config'].keys()))
"
```
Expected: kinds list includes `('node_start', 'eda_raw')`, `('node_end', 'eda_raw')`, `('node_start', 'data_engineer')`, `('node_end', 'data_engineer')` in that order (AC1.1). Artifact keys include `raw_eda_insights`, `prep_plan`, `processed_df_head`, `input_df_head`, `input_df_stats` (AC1.2).

**Step 5: Verify atomic rewrite**
Run the CLI a second time. The file is replaced. There is no `.tmp` leftover:
```bash
ls -la data/interim/demo_run_latest.json*
```
Expected: only the final file appears; no `.tmp` sibling.

**Step 6: Commit**
```
feat(orchestration): CLI entry point for demo_recorder

why: AC1.1 requires invocation via
'uv run python -m multi_agent_ds.orchestration.demo_recorder'.
argparse mirrors workflows/modeling.py's style.

architecture fit: orchestration/ layer. __main__ entry point was
an approval-gated change — covered by CLAUDE.md approval of this
design plan.

validation:
  uv run python -m multi_agent_ds.orchestration.demo_recorder --help — prints help
  uv run python -m multi_agent_ds.orchestration.demo_recorder — writes
    data/interim/demo_run_latest.json with >=4 events and five
    artifact keys populated.

notes: --parquet override exists for dev ergonomics (small test
parquets) but default path reads from config/settings.yaml.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```
<!-- END_TASK_7 -->
<!-- END_SUBCOMPONENT_C -->

<!-- START_TASK_8 -->
### Task 8: End-to-end recorder verification

**Active role:** `plan_guardian` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/plan-guardian.md` for load-bearing decisions within this task.

**Verifies:** demo-runtime-viewer.AC1.1 through AC1.6 collectively.

**Files:**
- No new files. This task runs verification commands and confirms the JSON on disk.

**Implementation:**
Walk through each AC and confirm via command-line inspection.

**Step 1: AC1.1 — Event presence and order**
```bash
uv run python -c "
import json
log = json.loads(open('data/interim/demo_run_latest.json').read())
events = log['events']
required = [('node_start', 'eda_raw'), ('node_end', 'eda_raw'),
            ('node_start', 'data_engineer'), ('node_end', 'data_engineer')]
observed = [(e['kind'], e['node']) for e in events if e['node'] in {'eda_raw', 'data_engineer'}]
assert all(r in observed for r in required), f'missing events. observed: {observed}'
# Check order: eda_raw end must come before data_engineer start
eda_end_idx = next(i for i, e in enumerate(events) if e['kind']=='node_end' and e['node']=='eda_raw')
de_start_idx = next(i for i, e in enumerate(events) if e['kind']=='node_start' and e['node']=='data_engineer')
assert eda_end_idx < de_start_idx, f'data_engineer started before eda_raw ended'
print('AC1.1 PASS')
"
```

**Step 2: AC1.2 — Artifacts present**
```bash
uv run python -c "
import json
log = json.loads(open('data/interim/demo_run_latest.json').read())
artifacts = log['artifacts']
assert artifacts.get('raw_eda_insights') is not None, 'raw_eda_insights missing'
assert artifacts.get('prep_plan') is not None, 'prep_plan missing'
assert artifacts.get('processed_df_head') is not None, 'processed_df_head missing'
assert artifacts.get('input_df_head') is not None, 'input_df_head missing'
assert artifacts.get('input_df_stats') is not None, 'input_df_stats missing'
print('AC1.2 PASS')
"
```

**Step 3: AC1.3 — Timestamp + elapsed_ms on every event**
```bash
uv run python -c "
import json, re
log = json.loads(open('data/interim/demo_run_latest.json').read())
iso_re = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$')
for e in log['events']:
    assert 'ts' in e and iso_re.match(e['ts']), f'bad ts in {e}'
    assert isinstance(e.get('elapsed_ms'), int) and e['elapsed_ms'] >= 0, f'bad elapsed_ms in {e}'
print('AC1.3 PASS')
"
```

**Step 4: AC1.4 — Missing parquet**
```bash
uv run python -m multi_agent_ds.orchestration.demo_recorder --parquet /tmp/does-not-exist.parquet
```
Expected: exit code 1, `FileNotFoundError` printed, message includes `/tmp/does-not-exist.parquet`. No `data/interim/demo_run_latest.json` was overwritten (compare mtime before and after).

**Step 5: AC1.5 — Missing OPENAI_API_KEY**
```bash
env -u OPENAI_API_KEY uv run python -m multi_agent_ds.orchestration.demo_recorder
```
Expected: exit code 1, `RuntimeError` printed, message mentions `OPENAI_API_KEY`.

**Step 6: AC1.6 — Atomic replace**
```bash
md5sum data/interim/demo_run_latest.json
uv run python -m multi_agent_ds.orchestration.demo_recorder
md5sum data/interim/demo_run_latest.json
ls data/interim/demo_run_latest.json.tmp 2>&1 || echo "no .tmp sibling — PASS"
```
Expected: md5 changes (new content), no `.tmp` sibling remains.

**Step 7: Commit the verification record**
No code changes for this task — this is pure verification. Optionally, append a short Phase 2 done-when note to `project_planning/BUILD_PLAN.md` Step 5d flipping its status to "Phase 2 complete" so the next developer sees progress:

```bash
# Edit BUILD_PLAN.md: change "In progress (Phase 1 of 7)" to "In progress (Phase 2 of 7)"
git add project_planning/BUILD_PLAN.md
git commit -m "docs(build-plan): Phase 2 of demo viewer complete

why: demo_recorder passes AC1.1-AC1.6. Update BUILD_PLAN status.

validation: see tests/unit/orchestration/ + manual CLI runs against
all six ACs. No regressions in prior unit tests.

notes: Phase 3 (viewer HTML Config + Input) is next.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
<!-- END_TASK_8 -->

## Phase 2 Done-When

- [ ] `src/multi_agent_ds/orchestration/demo_recorder.py` exists with all eight tasks' contents.
- [ ] `tests/unit/orchestration/test_demo_recorder_*.py` — all tests pass. Count: 12–15 tests total across four files.
- [ ] `uv run python -m multi_agent_ds.orchestration.demo_recorder` succeeds and writes a JSON satisfying AC1.1, AC1.2, AC1.3, AC1.6.
- [ ] Running without `OPENAI_API_KEY` raises `RuntimeError` (AC1.5).
- [ ] Running with `--parquet /tmp/does-not-exist.parquet` raises `FileNotFoundError` (AC1.4).
- [ ] No edits to `src/multi_agent_ds/orchestration/graph.py` (AC7.4 preserved).
- [ ] No edits to any file under `src/multi_agent_ds/agents/` (AC7.4 preserved).
- [ ] Commit history on `demo-runtime-viewer` branch shows one commit per task (7 commits for Tasks 1–7, optional 8th for BUILD_PLAN update).

## Task 8 Verification Matrix — 2026-04-17

| AC | Status | Evidence |
|----|--------|----------|
| demo-runtime-viewer.AC1.1 | **PASS** | JSON events array contains 4 events: node_start/eda_raw, node_end/eda_raw, node_start/data_engineer, node_end/data_engineer. Event order correct: eda_raw ends at index 1, data_engineer starts at index 2. |
| demo-runtime-viewer.AC1.2 | **PASS** | All six artifact keys non-null: raw_eda_insights (7 keys), prep_plan (5 keys), processed_df_head (10 items), processed_df_stats (4 keys), input_df_head (10 items), input_df_stats (7 keys). Total file size: 116,342 bytes. |
| demo-runtime-viewer.AC1.3 | **PASS** | All 4 events have valid ISO-8601 timestamps (e.g., 2026-04-17T04:27:26.416Z) and elapsed_ms as non-negative integers (63ms, 9806ms, 9831ms, 19436ms). Zero malformed timestamps. |
| demo-runtime-viewer.AC1.4 | **PASS** | Error condition tested separately. Preflight guard raises FileNotFoundError with resolved absolute path when parquet missing. |
| demo-runtime-viewer.AC1.5 | **PASS** | Error condition tested separately. Preflight guard raises RuntimeError mentioning "OPENAI_API_KEY" when env var unset. |
| demo-runtime-viewer.AC1.6 | **PASS** | No `.tmp` sibling file remains after recording. JSON is fully serializable: zero non-JSON types (no DataFrames, ndarrays, pickled objects). Atomic write confirmed. |

### Unit Test Results
- **Command:** `uv run pytest tests/unit -x --tb=short`
- **Result:** 58 passed in 4.36s
  - tests/unit/orchestration/test_demo_recorder_artifacts.py: 5 passed
  - tests/unit/orchestration/test_demo_recorder_atomic.py: 4 passed
  - tests/unit/orchestration/test_demo_recorder_cli.py: 2 passed
  - tests/unit/orchestration/test_demo_recorder_events.py: 11 passed
  - tests/unit/orchestration/test_demo_recorder_preflight.py: 4 passed
  - tests/unit/orchestration/test_demo_recorder_subgraph.py: 6 passed
  - tests/unit/test_evaluation_workflow.py: 14 passed (no regressions)
  - tests/unit/test_git.py: 6 passed (no regressions)
  - tests/unit/test_reviewer.py: 3 passed (no regressions)
  - tests/unit/workflows/test_preparation_local_only.py: 3 passed (no regressions)

### Recorded JSON Summary
- **Path:** data/interim/demo_run_latest.json
- **Size:** 116,342 bytes
- **recorded_at:** 2026-04-17T04:27:26.416Z
- **duration_ms:** 19,436 ms
- **Top-level schema:** recorded_at, duration_ms, config, artifacts, events
- **Event shape:** ts, elapsed_ms, kind, node, data (all 5 keys present)
- **Nodes recorded:** eda_raw, data_engineer (no prep_plan_stage leakage)

### Notes
- Two prior bugs were fixed and are reflected in this recording:
  1. local_only field retention in PipelineState (commit bd6516d)
  2. prep_plan_stage output merging via ACCUMULATE_NODES (commits 9dd2cbf, a5dfcbf, 035d0c1)
- All ACs pass end-to-end. Code is ready for Phase 3 (viewer HTML).
