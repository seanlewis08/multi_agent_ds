# Full Pipeline Runbook — CLI + Agent Conversation HTML Report

**Slice commit:** `f3e5ee9` (on `demo-runtime-viewer`)
**Design doc:** `/Users/seanlewis/.claude/plans/i-want-to-generate-delegated-hartmanis.md`
**Captured:** 2026-04-17

This runbook documents how to run and test the new `multi-agent-ds` CLI, the full end-to-end pipeline workflow, and the per-run agent conversation HTML report.

---

## 1. One-time install (new CLI script)

```bash
cd /Users/seanlewis/DataspellProjects/multi_agent_ds
uv sync   # installs the console-script entry
```

After `uv sync`, the script lives at `.venv/bin/multi-agent-ds`. Use it via `uv run multi-agent-ds ...` or by activating the venv first (`source .venv/bin/activate`).

---

## 2. Prerequisites

```bash
export OPENAI_API_KEY=sk-...   # or keep it in .env (already loaded by the adapter)

# Generate small synthetic dataset (if you haven't already)
uv run python -c "from multi_agent_ds.tools.data_generator import generate_synthetic_data, save_local; save_local(generate_synthetic_data())"
```

Temporarily drop `config/settings.yaml` → `data.synthetic.scale: small` before the first run. `large` is 500k rows and blows token budgets.

---

## 3. Run the full graph end-to-end (the headline use case)

```bash
uv run multi-agent-ds full --scale small --cost-override cheap --yes
```

What happens:

1. **Cost preflight** — warns if scale is `medium`/`large` or any route resolves to `expensive`. `--yes` skips the interactive prompt.
2. **Graph execution** — async `build_graph().compile().ainvoke()` walks EDA → prep → modeling loop → report → business-stakeholder review → evaluation → reviewer.
3. **Conversation recording** — every `adapter.chat()` / `adapter.structured_output()` call captured into a `ConversationTurn` with messages sent, response received, timing, model, capability, cost tier.
4. **HTML report written** — `reports/conversation_<ISO8601>.html` plus a `reports/conversation_latest.html` copy. Self-contained (embedded CSS + JS, no external dependencies).

Open the report:

```bash
open reports/conversation_latest.html
```

Expected layout:

- **Header:** run metadata (start time, duration, turn count, total tokens, error banner if any)
- **Sidebar:** anchor links per phase (`raw_eda`, `prep_plan`, `baseline`, `tune`, ...)
- **Main:** chronological timeline of turn cards. Each card shows agent/task/model badges, elapsed ms, collapsible system prompt, expanded user prompt, structured JSON or text response

---

## 4. Other subcommands (non-agentic, no HTML report)

```bash
uv run multi-agent-ds discovery --data-path data/raw/synthetic_dataset.parquet
uv run multi-agent-ds preparation --data-path data/raw/synthetic_dataset.parquet --prep-plan path/to/plan.json
uv run multi-agent-ds modeling --algorithms lightgbm logistic_regression
uv run multi-agent-ds evaluation --state path/to/state.json
uv run multi-agent-ds --help       # subcommand index
uv run multi-agent-ds full --help  # full-pipeline flags
```

These delegate to the existing non-agentic workflow functions unchanged. No LLM calls, no conversation report — they produce their normal artifacts (MLflow runs, markdown logs in `reports/`, processed parquet in `data/processed/`).

---

## 5. Run the test suite

```bash
# New tests for this slice (fast, no network)
uv run pytest tests/test_conversation_recorder.py tests/test_html_report.py tests/test_cli.py tests/test_full_pipeline_workflow.py -v

# Full suite (excluding live OpenAI integration)
uv run pytest tests/ --ignore=tests/integration -q

# Live OpenAI integration (costs real tokens)
OPENAI_API_KEY=sk-... RUN_OPENAI_LIVE_TESTS=1 uv run pytest tests/integration/ -q
```

Expected: 19 new tests pass. Full suite 268 pass + 3 pre-existing failures unrelated to this slice (hardcoded `/Users/sean.lewis/` path in `test_modeling_export.py`; two demo_recorder preflight / data_engineer execute failures).

---

## 6. Quick runtime smoke — verify recorder wiring without spending tokens

```bash
uv run python -c "
from multi_agent_ds.core import load_settings
from multi_agent_ds.adapters.llm import build_adapter
from multi_agent_ds.tools.conversation_recorder import conversation_recording, RecordingOpenAIAdapter

settings = load_settings()
print('outside:', type(build_adapter(settings, agent='eda_analyst', task=None)).__name__)
with conversation_recording() as rec:
    inside = build_adapter(settings, agent='eda_analyst', task=None)
    print('inside:', type(inside).__name__)
    assert isinstance(inside, RecordingOpenAIAdapter)
print('after:', type(build_adapter(settings, agent='eda_analyst', task=None)).__name__)
print('OK')
"
```

Should print `OpenAIAdapter` → `RecordingOpenAIAdapter` → `OpenAIAdapter` → `OK`. Confirms the contextvar wiring works.

---

## 7. Debug a run that failed mid-graph

The `try/finally` in `run_full_pipeline` ensures the HTML report is written **even if the graph raises**. Look at `reports/conversation_latest.html` — the error banner in the header will show the exception + traceback, and whatever turns were captured up to the failure will be in the timeline. That's usually enough to see "which agent's output broke the next agent's contract".

---

## 8. Programmatic use (tests, notebooks)

```python
import asyncio
from multi_agent_ds.workflows import run_full_pipeline

result = asyncio.run(run_full_pipeline(
    data_path="data/raw/synthetic_dataset.parquet",
    record=True,
    html_output="reports/my_custom_name.html",
))
print(result["html_path"], result["turn_count"], result["duration_ms"])
```

---

## Architecture notes (how it works under the hood)

- **Recorder lives in `tools/conversation_recorder.py`.** A `ContextVar[ConversationRecorder | None]` is set by a `conversation_recording()` contextmanager at workflow entry.
- **`adapters/llm/routing.py::build_adapter` checks the contextvar** and, when active, wraps the returned `OpenAIAdapter` in `RecordingOpenAIAdapter`. Zero changes to the 11 agent call sites. Zero changes to `OpenAIAdapter` itself.
- **`RecordingOpenAIAdapter` proxies** `chat()` and `structured_output()`, captures `messages_sent` + `response` + `usage` + elapsed_ms + capability/cost-tier/model from `ModelConfig`, and forwards every other attribute via `__getattr__` so future LangSmith `@traceable` integration still fires.
- **HTML emitter lives in `tools/html_report.py`.** Pure function — no Jinja2, no external dependencies. Embedded CSS. Phase sidebar derived from `agent_decisions` ordering.
- **Full-pipeline workflow lives in `workflows/full_pipeline.py`.** Async `ainvoke()` on the compiled graph; `try/finally` ensures the HTML is always written, even on exceptions.
- **CLI lives at `src/multi_agent_ds/cli.py`.** Unified dispatcher with five subcommands; `full` records + writes HTML; the other four delegate to existing non-agentic workflow functions.

## Known gotchas

- **First run over `medium`/`large` scale will trigger the cost preflight prompt.** Use `--yes` in scripts.
- **HTML report empty?** Means the recorder didn't wrap — check that you're running through `multi-agent-ds full` (which opens the contextmanager), not a bare ad-hoc script that bypasses it.
- **Circular-import error on `from multi_agent_ds.workflows import run_full_pipeline`?** Shouldn't happen — `workflows/__init__.py` uses lazy `__getattr__`. If you see it, report the traceback.
- **Very long prompts (EDA profile JSON) blowing the page?** Each response block has `max-height: 400px` with vertical scroll per card — should stay tidy. System prompts are collapsed by default.

## Deferred (not in this slice)

- Phase (e) LangSmith metadata propagation (`langsmith` not a project dep).
- Replay capability for the HTML report (use `demo_app.py` for interactive replay).
- Agentic variants of `discovery`/`preparation`/`modeling`/`evaluation` subcommands.
- Checkpoint/resume across runs.
