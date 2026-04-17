# LLM Model Routing — Design Plan

Captured: 2026-04-16
Status: Complete — Phases (a)–(d) shipped 2026-04-16 in commits `559f105` and `b424231`. Phase (e) LangSmith metadata deferred (see `TODO(phase-e)` in `src/multi_agent_ds/adapters/llm/routing.py`).
Scope: Per-agent and per-task model selection across the multi-agent pipeline

---

## Summary

Today every agent instantiates one `OpenAIAdapter(settings)` that reads a single model name from `settings["llm"]["providers"]["openai"]["model"]`. All five agents and all of `ml_modeler`'s seven modes use the same model (currently `gpt-4o`) with the same temperature and max_tokens.

This plan introduces a two-axis routing system where every `(agent, task)` pair resolves to a `ModelConfig` combining:

- **Capability** — `coding`, `balanced`, `reasoning` (what the task needs)
- **Cost tier** — `cheap`, `moderate`, `expensive` (how much to spend)

The resolution lives in a pure function. The adapter becomes provider-dumb: it accepts a fully-resolved `ModelConfig` and makes API calls. A startup-time env var `LLM_COST_OVERRIDE` lets us force every route to a single cost tier for smoke tests or cost-budget experiments.

### Key decisions locked during brainstorming

- **Config shape:** Two-axis lookup (`model_matrix` × `capability_settings`) rather than flat profile names. Every route references `{ capability, cost }`.
- **Code shape:** External pure-function resolver (`resolve_model_config`) plus a provider-dumb adapter. Matches FCIS (functional core / imperative shell).
- **Scope:** OpenAI only for now. The existing commented-out Anthropic/Google stubs in `settings.yaml` stay commented. `ModelConfig` carries a `provider` field so multi-provider is a future extension, not a blocker.
- **Reasoning models included:** o-series (o3, o4-mini) is in scope from day one. Adapter handles the quirks.
- **Clean break:** No backward-compat shim for the old `OpenAIAdapter(settings)` constructor. Ten call sites, all in `agents/`, migrate together.

---

## Config Schema

Replace the current `llm` block in `config/settings.yaml` with:

```yaml
llm:
  default_provider: openai

  # (capability, cost) -> model name
  model_matrix:
    coding:    { cheap: gpt-4.1-mini, moderate: gpt-4.1, expensive: gpt-4.1 }
    balanced:  { cheap: gpt-4.1-mini, moderate: gpt-4.1, expensive: gpt-4.1 }
    reasoning: { cheap: o4-mini,      moderate: o3,      expensive: o3 }

  # Per-capability non-model settings. `temperature: null` means "omit the field"
  # (o-series models reject non-1.0 temperatures).
  capability_settings:
    coding:    { temperature: 0.1,  max_tokens: 4096 }
    balanced:  { temperature: 0.2,  max_tokens: 2048 }
    reasoning: { temperature: null, max_tokens: 8192 }

  # Resolution order: routes[agent][task] -> routes[agent][default]
  #                   -> routes[agent] (if string-shorthand) -> routes.default
  routes:
    default:              { capability: balanced, cost: cheap }
    eda_analyst:          { capability: balanced, cost: cheap }
    ml_reviewer:          { capability: balanced, cost: cheap }
    business_stakeholder: { capability: balanced, cost: cheap }

    data_engineer:
      default: { capability: balanced, cost: cheap }
      execute: { capability: coding,   cost: moderate }

    ml_modeler:
      default:                    { capability: balanced,  cost: cheap }
      eda_review:                 { capability: balanced,  cost: cheap }
      baseline_decision:          { capability: balanced,  cost: cheap }
      learning_rate_decision:     { capability: reasoning, cost: cheap }
      feature_selection_decision: { capability: reasoning, cost: cheap }
      tuning_decision:            { capability: reasoning, cost: expensive }
      modeling_verdict:           { capability: reasoning, cost: expensive }
      modeling_handoff:           { capability: balanced,  cost: cheap }

  # Populated at startup from env; resolver reads it via settings.
  cost_override: null
```

### Route-table intent

| Agent | Mode | Capability | Cost | Reason |
|---|---|---|---|---|
| eda_analyst | all | balanced | cheap | Structured summaries and plans |
| ml_reviewer | all | balanced | cheap | Light judgment on EDA outputs |
| business_stakeholder | all | balanced | cheap | Business-relevance check |
| data_engineer | feedback | balanced | cheap | Plan review (analysis) |
| data_engineer | execute | coding | moderate | Code-shaped outputs; determinism matters |
| ml_modeler | eda_review, handoff, baseline_decision | balanced | cheap | Analysis or packaging |
| ml_modeler | learning_rate_decision, feature_selection_decision | reasoning | cheap | Real trade-offs, but inexpensive |
| ml_modeler | tuning_decision, modeling_verdict | reasoning | expensive | Highest-leverage decisions in the pipeline |

Net effect: `o3` is invoked twice per pipeline run (the two decisions that gate model acceptance); everything else runs on `gpt-4.1-mini` or `gpt-4.1`.

---

## New Module: `adapters/llm/routing.py`

Pure functional core. No HTTP, no env reads, no file I/O inside the resolver.

### `ModelConfig` dataclass

```python
@dataclass(frozen=True)
class ModelConfig:
    provider: str            # "openai"
    model: str               # resolved string, e.g. "o3"
    temperature: float | None
    max_tokens: int
    capability: str          # "reasoning" — metadata for adapter quirks + tracing
    cost_tier: str           # "expensive" — metadata for tracing
    profile_label: str       # "reasoning_expensive" — display-only, e.g. for logs
```

Frozen dataclass so it can safely be cached, hashed, and compared in tests.

### `resolve_model_config` contract

```python
def resolve_model_config(
    settings: dict,
    *,
    agent: str,
    task: str | None,
    cost_override: str | None = None,
) -> ModelConfig:
    """
    Walk the routing table and return a fully-resolved ModelConfig.

    Resolution order:
      1. settings['llm']['routes'][agent][task]
      2. settings['llm']['routes'][agent]['default']
      3. settings['llm']['routes'][agent]        (if agent-level is a {capability,cost} dict)
      4. settings['llm']['routes']['default']

    After the capability and cost are resolved:
      - If cost_override is provided (and valid), it replaces the resolved cost.
      - Look up model_matrix[capability][cost] -> model name.
      - Look up capability_settings[capability] -> temperature + max_tokens.
      - Assemble ModelConfig.

    Raises ValueError with an actionable message on:
      - Unknown agent (no route + no global default)
      - Malformed route entry (missing capability or cost)
      - Unknown capability or cost tier
      - Unknown cost_override value
    """
```

The function is pure: same inputs always produce the same `ModelConfig`. Testable without mocking anything.

### `build_adapter` factory (imperative shell)

Lives in `adapters/llm/__init__.py` so every agent imports the same symbol:

```python
def build_adapter(
    settings: dict,
    *,
    agent: str,
    task: str | None,
) -> OpenAIAdapter:
    cost_override = settings.get("llm", {}).get("cost_override")
    config = resolve_model_config(settings, agent=agent, task=task, cost_override=cost_override)
    return OpenAIAdapter(config)
```

Every agent instantiation becomes a one-liner. The resolver stays pure; the factory handles the env-var stash.

---

## Updated Adapter: `adapters/llm/openai.py`

New constructor:

```python
class OpenAIAdapter:
    def __init__(self, config: ModelConfig):
        self.config = config
        self.client = wrap_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))
        # No settings-dict walking. No field-by-field key validation.
```

Public methods keep their current shape:

- `chat(messages, tools=None) -> dict`
- `structured_output(messages, schema) -> dict`

### Reasoning-model quirks (handled inside the adapter)

| Quirk | Handling |
|---|---|
| `max_tokens` field is rejected by o-series; must use `max_completion_tokens` | Adapter checks `config.capability == "reasoning"` (or model string starts with `o`) and emits the correct field name |
| Temperature must be 1.0 on o-series | When `config.temperature is None`, the adapter **omits** the `temperature` field entirely — does not pass `temperature=None` |
| Reasoning tokens consume budget invisibly | `capability_settings.reasoning.max_tokens` defaulted to 8192; bump per-route if long reasoning traces blow the budget |
| Structured output on reasoning models | `response_format={"type": "json_schema", ...}` is supported on o3 and o4-mini as of April 2026; no special casing needed |

One private helper inside the adapter assembles request kwargs; both `chat()` and `structured_output()` use it. Retry wrapper (`_with_retries`, 3 attempts, exponential backoff) stays as-is. Optionally bump base backoff from 1.0s to 2.0s if reasoning-model latencies cause false-positive retries during testing.

### LangSmith tag propagation

Calls are tagged with `capability` and `cost_tier` from the `ModelConfig` so trace spans show e.g. `ml_modeler::tuning_decision [reasoning/expensive → o3]`. Mechanism: `@traceable(metadata=...)` decorator on `chat()`/`structured_output()`, or `wrap_openai` metadata kwarg if the SDK supports it at call time.

---

## Integration Plan

### File manifest

| Change | File | Notes |
|---|---|---|
| NEW | `src/multi_agent_ds/adapters/llm/routing.py` | `ModelConfig`, `resolve_model_config` |
| MODIFY | `src/multi_agent_ds/adapters/llm/openai.py` | Constructor takes `ModelConfig`; no more settings walking |
| MODIFY | `src/multi_agent_ds/adapters/llm/__init__.py` | Export `ModelConfig`, `resolve_model_config`, `build_adapter` |
| MODIFY | `src/multi_agent_ds/agents/eda_analyst.py` | 1 call site |
| MODIFY | `src/multi_agent_ds/agents/data_engineer.py` | 1 call site |
| MODIFY | `src/multi_agent_ds/agents/ml_reviewer.py` | 1 call site |
| MODIFY | `src/multi_agent_ds/agents/business_stakeholder.py` | 1 call site |
| MODIFY | `src/multi_agent_ds/agents/ml_modeler.py` | 6 call sites (one per LLM-calling mode) |
| MODIFY | `config/settings.yaml` | New `llm` block per schema above |
| MODIFY | `app.py` | Read `LLM_COST_OVERRIDE` env and stash in `settings["llm"]["cost_override"]` |
| MODIFY | `project_planning/PROJECT_TREE.md` | Add `adapters/llm/routing.py` to the tree |
| MODIFY | `tests/unit/adapters/llm/test_openai.py` | Swap settings-dict fixtures for `ModelConfig` fixtures |
| NEW | `tests/unit/adapters/llm/test_routing.py` | Pure-function tests for `resolve_model_config` |

Total: 10 LLM call sites to update, plus 2 new files and 9 modifications. No orchestration or graph-topology changes.

### Call-site pattern

Every agent instantiation becomes:

```python
from multi_agent_ds.adapters.llm import build_adapter

# before
adapter = OpenAIAdapter(settings)

# after
adapter = build_adapter(settings, agent="ml_modeler", task=mode)
```

`mode` is already a local variable in every node function, so no signature changes propagate to the graph or orchestration layer.

### Cost override flow

```python
# in app.py, at startup
import os

cost_override = os.getenv("LLM_COST_OVERRIDE")   # None | "cheap" | "moderate" | "expensive"
settings["llm"]["cost_override"] = cost_override
```

From there the resolver picks it up automatically via `build_adapter`. Set `LLM_COST_OVERRIDE=cheap` before running to force every route onto its capability's cheap-tier model — useful for smoke tests or cost-budget experiments.

---

## Error Handling

Three failure modes, each with one clear owner:

| Mode | Owner | Behavior |
|---|---|---|
| Unknown `(agent, task)` | `resolve_model_config` | Raises `ValueError` at node entry, before any API call. Message includes the offending strings and the nearest valid keys. |
| Missing `OPENAI_API_KEY` | `OpenAIAdapter.__init__` | Raises at adapter construction (today's behavior, unchanged). |
| OpenAI API errors | `OpenAIAdapter._with_retries` | 3-attempt retry with exponential backoff on `RateLimitError` / `APIConnectionError` (today's behavior, unchanged). |

No config validation at app startup — resolution is lazy, per-call. If the config is malformed, you find out when the first agent that hits the broken route runs. An optional `validate_routing_config(settings)` function could be added later that walks every `routes` entry and resolves each one; not in scope for this slice.

---

## Testing Strategy

### Unit tests — `tests/unit/adapters/llm/test_routing.py`

Pure-function tests, no mocking required. Cover:

- Direct route hit: `resolve_model_config(settings, agent="ml_modeler", task="tuning_decision")` → `reasoning_expensive`
- Agent-level fallback: `resolve_model_config(settings, agent="ml_modeler", task="unknown_mode")` → uses `ml_modeler.default`
- Global fallback: `resolve_model_config(settings, agent="unknown_agent", task=None)` → uses `routes.default`
- Cost override: same call with `cost_override="cheap"` → downshifts cost tier only, keeps capability
- Malformed route raises with actionable message
- `temperature: null` preserved through resolution (not coerced to 0.0)
- `profile_label` correctly composes `"<capability>_<cost>"`

Target: ≥95% line coverage on `routing.py`. These tests should run in milliseconds with no fixtures beyond a settings dict literal.

### Unit tests — `tests/unit/adapters/llm/test_openai.py`

Swap the old settings-dict fixtures for `ModelConfig` fixtures:

- Construct adapter with `ModelConfig(capability="reasoning", ...)` and verify request kwargs use `max_completion_tokens`, omit `temperature`
- Construct adapter with `ModelConfig(capability="balanced", ...)` and verify request kwargs use `max_tokens`, include `temperature`
- Verify retry wrapper still fires on `RateLimitError`
- Verify LangSmith metadata contains `capability` and `cost_tier`

Mock the OpenAI client so no network calls happen.

### Integration test — smoke with `LLM_COST_OVERRIDE=cheap`

One end-to-end test that runs the full graph with `cost_override="cheap"` set and asserts that every spawned adapter's `ModelConfig.cost_tier == "cheap"`. This is the single highest-value integration test because it validates the whole routing chain in one run.

### Manual verification checklist

Post-implementation, before marking the slice done:

- Run the pipeline with default settings; confirm LangSmith trace shows `gpt-4.1-mini` for reviewers, `o3` for `tuning_decision` and `modeling_verdict`
- Run with `LLM_COST_OVERRIDE=cheap`; confirm all spans show cheap-tier models
- Run with an intentionally broken route (e.g., `capability: nonsense`); confirm the pipeline fails fast with a clear error message at the first affected node

---

## Follow-ups / Deferred Work

Keep these out of this slice; revisit after the baseline routing lands:

- **Multi-provider support.** Add an `LLMAdapter` protocol and an `AnthropicAdapter` / `GoogleAdapter`. `ModelConfig` already carries a `provider` field so the routing layer is unchanged. Trigger: when a Claude or Gemini model is preferred for a specific route.
- **Per-route `max_tokens` override.** Today, token budget is set at the capability level. A route like `ml_modeler.modeling_verdict` might need a higher budget than `ml_modeler.learning_rate_decision` even though both are reasoning. Trigger: when token overflow appears in LangSmith traces.
- **Startup config validation.** Optional `validate_routing_config(settings)` that walks every route entry at app startup. Trigger: when a malformed config has caused a mid-run failure in a long pipeline more than once.
- **Cost reporting from traces.** Aggregate LangSmith `capability` / `cost_tier` tags into a per-run cost summary. Trigger: when cost analysis is a recurring question.
- **Profile inheritance / aliases.** Allow a route to say `{ like: ml_modeler.tuning_decision }` to inherit. Trigger: when route duplication becomes noisy (not today).

---

## Open Items for Implementation Planning

Handed to the next skill (writing-implementation-plans):

1. Phase structure — recommended slicing: (a) add `routing.py` + tests, (b) refactor `openai.py`, (c) migrate call sites agent-by-agent with tests, (d) wire cost_override in `app.py`, (e) LangSmith metadata pass.
2. Whether to bump retry base backoff from 1.0s → 2.0s (low-risk defensive change; probably yes).
3. Exact LangSmith metadata mechanism — `@traceable(metadata=...)` decorator vs. `wrap_openai` kwarg. Quick doc check needed.
