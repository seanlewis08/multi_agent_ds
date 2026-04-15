# LLM Adapter Implementation Plan

**Scope:** Sean Step 1 from `Sean_Plan.md`  
**Primary target:** `src/multi_agent_ds/adapters/llm/openai.py`  
**Secondary target:** `src/multi_agent_ds/adapters/llm/__init__.py` only if export cleanup is useful  
**Status:** Implemented

## Purpose

Build the thinnest useful OpenAI provider adapter for the repository's agent layer. The adapter should be easy for Jonathan and later agent nodes to import without introducing extra architecture, scripts, or sidecar abstractions.

## Agent-Team Framing

- `plan_guardian`: Keep this scoped to Sean Step 1 and note the tension with project-level `BUILD_PLAN.md` step `5c`.
- `architecture_guard`: Keep all logic in `adapters/llm/`; do not move request logic into agents, workflows, skills, tools, or core.
- `implementation_engineer`: Build one concrete adapter class with the smallest coherent interface.
- `efficiency_reviewer`: Avoid registries, factories, `tiktoken`, retry frameworks, or split SDK paths.
- `commit_chronicler`: Commit only after a complete checkpoint passes its review and tests.

## Constraints

- Use only existing dependencies already in the repo:
  - `openai`
  - `python-dotenv`
  - `pydantic` only if clearly needed
- Do not add a new dependency.
- Do not add a new script, CLI entrypoint, or notebook.
- Do not create new provider abstractions beyond what this step actually needs.
- Do not put file I/O, MLflow logic, workflow state, or model-selection logic in the adapter.

## Minimal Target Design

Implement one class:

```python
class OpenAIAdapter:
    def __init__(self, settings: dict): ...
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict: ...
    def structured_output(self, messages: list[dict], schema: dict) -> dict: ...
```

Use one SDK path:

- `chat.completions.create` for both plain chat and structured output

Keep the normalized return shape compact:

- `chat(...)`
  - `content`
  - `tool_calls`
  - `usage`
- `structured_output(...)`
  - `parsed`
  - `usage`

## Implementation Steps

### Step 1: Constructor and Config Wiring

Build `__init__` to:

- load `.env`
- read `settings["llm"]["providers"]["openai"]`
- store `model`, `temperature`, and `max_tokens`
- read `OPENAI_API_KEY`
- create the `OpenAI` client
- fail fast on missing config or API key

### Step 2: Retry Helper

Add one private helper that:

- retries only `RateLimitError` and `APIConnectionError`
- uses small exponential backoff
- stops after a fixed small number of attempts

### Step 3: Raw Chat Request Path

Add one private request path around `chat.completions.create` that:

- accepts `messages`
- optionally accepts `tools`
- optionally accepts `response_format`
- returns the SDK response

This keeps request construction and retries in one place.

### Step 4: `chat(...)`

Implement `chat(messages, tools=None)` to:

- call the shared request path
- extract assistant text content
- extract tool calls if present
- extract usage if present
- return a normalized dict instead of the raw SDK object

### Step 5: `structured_output(...)`

Implement `structured_output(messages, schema)` to:

- call the same request path with JSON-schema response formatting
- parse the returned text with `json.loads`
- return the parsed dict and usage metadata

### Step 6: Optional Export Cleanup

Only if useful, update `adapters/llm/__init__.py` to export `OpenAIAdapter`.

Do not add a protocol, registry, or second provider abstraction unless a real caller requires it.

## Review and Test Gates

Each implementation step should stop for:

1. human review of the code shape
2. focused validation for that step
3. checklist/log update before moving on

Recommended validation sequence:

1. import-only smoke test
2. constructor/config smoke test
3. `chat()` smoke test
4. `structured_output()` smoke test
5. retry-path test with mocking

## Done Criteria

This step is complete when:

- `from multi_agent_ds.adapters.llm.openai import OpenAIAdapter` works
- `chat()` returns normalized content and usage
- `structured_output()` returns parsed JSON and usage
- retry behavior exists for the two transient error types
- Jonathan can import this adapter for future agent work

## Resume Instructions

If work pauses, resume from the checklist file:

- `project_planning/LLM_Adapter_Checklist.md`

Recommended resume prompt:

```text
Use agent teams for this task. Pick back up where I left off in project_planning/LLM_Adapter_Checklist.md and continue from the next unchecked item.
```
