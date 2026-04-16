"""Pure-function LLM model routing.

Maps ``(agent, task)`` pairs onto a fully-resolved ``ModelConfig`` using a
two-axis lookup (capability x cost). The resolver is a pure function with no
I/O, no env reads, and no logging — all side effects (env, adapter construction)
live in the ``build_adapter`` imperative shell below.

See ``project_planning/LLM_MODEL_ROUTING.md`` for the underlying design.

TODO(phase-e): LangSmith metadata propagation (``capability`` / ``cost_tier`` /
``profile_label`` as trace tags via ``@traceable(metadata=...)`` or
``wrap_openai``) is deferred until ``langsmith`` is added as a project
dependency. When that lands, wrap ``OpenAIAdapter.chat`` /
``structured_output`` with a traceable decorator that reads the fields off
``self.config`` and emits them as span metadata. This module is already
structured so that wiring is a local adapter change — no routing-layer change
required.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from multi_agent_ds.adapters.llm.openai import OpenAIAdapter

VALID_CAPABILITIES: tuple[str, ...] = ("coding", "balanced", "reasoning")
VALID_COST_TIERS: tuple[str, ...] = ("cheap", "moderate", "expensive")


@dataclass(frozen=True)
class ModelConfig:
    """Fully-resolved configuration for a single LLM invocation.

    Frozen so instances are hashable and safe to compare in tests.
    """

    provider: str
    model: str
    temperature: float | None
    max_tokens: int
    capability: str
    cost_tier: str
    profile_label: str


def _raise_resolution_error(stage: str, key: str, valid: tuple[str, ...] | list[str]) -> None:
    """Raise a ValueError with a uniform actionable message shape."""
    raise ValueError(
        f"LLM routing resolution failed at stage '{stage}': unknown key '{key}'. "
        f"Valid options: {sorted(valid)}."
    )


def _route_entry_for(
    routes: dict[str, Any],
    *,
    agent: str,
    task: str | None,
) -> dict[str, Any]:
    """Walk the route table and return the ``{capability, cost}`` leaf entry.

    Resolution order:
      1. ``routes[agent][task]`` if the agent block is a dict and contains ``task``
      2. ``routes[agent]['default']`` if the agent block is a dict with a default
      3. ``routes[agent]`` if it's already a ``{capability, cost}`` shorthand
      4. ``routes['default']``
    """
    agent_block = routes.get(agent)

    if isinstance(agent_block, dict):
        if "capability" in agent_block and "cost" in agent_block:
            # Shorthand: agent_block is itself the {capability, cost} entry.
            return agent_block
        if task is not None and isinstance(agent_block.get(task), dict):
            return agent_block[task]
        if isinstance(agent_block.get("default"), dict):
            return agent_block["default"]

    default_entry = routes.get("default")
    if isinstance(default_entry, dict):
        return default_entry

    raise ValueError(
        f"LLM routing resolution failed: no route for agent='{agent}', "
        f"task='{task}' and no 'default' route defined."
    )


def resolve_model_config(
    settings: dict[str, Any],
    *,
    agent: str,
    task: str | None,
    cost_override: str | None = None,
) -> ModelConfig:
    """Walk ``routes`` -> ``model_matrix`` -> ``capability_settings`` and assemble a ``ModelConfig``.

    Resolution order for the route entry:
      1. ``settings['llm']['routes'][agent][task]``        if dict-with-task
      2. ``settings['llm']['routes'][agent]['default']``   if dict-with-default
      3. ``settings['llm']['routes'][agent]``              if shorthand ``{capability,cost}``
      4. ``settings['llm']['routes']['default']``

    After the capability and cost are resolved, ``cost_override`` (if provided
    and valid) replaces the resolved cost but preserves the capability. The
    resolver then looks up the model name from ``model_matrix[capability][cost]``
    and the temperature / max_tokens from ``capability_settings[capability]``.

    Raises ``ValueError`` with an actionable message for every failure mode:
    missing ``llm`` block, malformed route entry, unknown capability, unknown
    cost tier, unknown ``cost_override``.
    """
    llm_cfg = settings.get("llm")
    if not isinstance(llm_cfg, dict):
        raise ValueError(
            "LLM routing resolution failed: settings['llm'] is missing or not a dict. "
            "Populate the llm block per project_planning/LLM_MODEL_ROUTING.md."
        )

    routes = llm_cfg.get("routes")
    if not isinstance(routes, dict):
        raise ValueError(
            "LLM routing resolution failed: settings['llm']['routes'] is missing or not a dict."
        )

    model_matrix = llm_cfg.get("model_matrix")
    if not isinstance(model_matrix, dict):
        raise ValueError(
            "LLM routing resolution failed: settings['llm']['model_matrix'] is missing or not a dict."
        )

    capability_settings = llm_cfg.get("capability_settings")
    if not isinstance(capability_settings, dict):
        raise ValueError(
            "LLM routing resolution failed: settings['llm']['capability_settings'] is missing or not a dict."
        )

    entry = _route_entry_for(routes, agent=agent, task=task)

    capability = entry.get("capability")
    cost_tier = entry.get("cost")
    if capability is None or cost_tier is None:
        raise ValueError(
            "LLM routing resolution failed: route entry for "
            f"agent='{agent}', task='{task}' is missing 'capability' or 'cost'. "
            f"Entry: {entry!r}."
        )

    if capability not in VALID_CAPABILITIES:
        _raise_resolution_error("capability", capability, VALID_CAPABILITIES)

    if cost_tier not in VALID_COST_TIERS:
        _raise_resolution_error("cost_tier", cost_tier, VALID_COST_TIERS)

    if cost_override is not None:
        if cost_override not in VALID_COST_TIERS:
            _raise_resolution_error("cost_override", cost_override, VALID_COST_TIERS)
        cost_tier = cost_override

    capability_matrix = model_matrix.get(capability)
    if not isinstance(capability_matrix, dict):
        raise ValueError(
            "LLM routing resolution failed: "
            f"settings['llm']['model_matrix']['{capability}'] is missing or not a dict."
        )
    model_name = capability_matrix.get(cost_tier)
    if not isinstance(model_name, str) or not model_name:
        raise ValueError(
            "LLM routing resolution failed: "
            f"settings['llm']['model_matrix']['{capability}']['{cost_tier}'] "
            "is missing or not a string."
        )

    cap_settings = capability_settings.get(capability)
    if not isinstance(cap_settings, dict):
        raise ValueError(
            "LLM routing resolution failed: "
            f"settings['llm']['capability_settings']['{capability}'] is missing or not a dict."
        )
    if "max_tokens" not in cap_settings:
        raise ValueError(
            "LLM routing resolution failed: "
            f"settings['llm']['capability_settings']['{capability}'] missing 'max_tokens'."
        )

    temperature_raw = cap_settings.get("temperature", None)
    # Preserve explicit None (reasoning models want temperature omitted entirely).
    temperature = None if temperature_raw is None else float(temperature_raw)
    max_tokens = int(cap_settings["max_tokens"])

    provider = default_provider(settings)

    return ModelConfig(
        provider=provider,
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        capability=capability,
        cost_tier=cost_tier,
        profile_label=f"{capability}_{cost_tier}",
    )


def default_provider(settings: dict[str, Any]) -> str:
    """Return ``settings['llm']['default_provider']`` or ``'openai'`` if unset."""
    llm_cfg = settings.get("llm")
    if not isinstance(llm_cfg, dict):
        return "openai"
    provider = llm_cfg.get("default_provider")
    if isinstance(provider, str) and provider:
        return provider
    return "openai"


def build_adapter(
    settings: dict[str, Any],
    *,
    agent: str,
    task: str | None,
) -> OpenAIAdapter:
    """Imperative-shell factory that returns a ready-to-call adapter.

    Reads ``settings['llm']['cost_override']`` (populated upstream from the
    ``LLM_COST_OVERRIDE`` env var) and passes it to ``resolve_model_config``.
    The local import of ``OpenAIAdapter`` breaks the circular import between
    this module and ``openai.py``.
    """
    from multi_agent_ds.adapters.llm.openai import OpenAIAdapter

    llm_cfg = settings.get("llm") if isinstance(settings, dict) else None
    cost_override = llm_cfg.get("cost_override") if isinstance(llm_cfg, dict) else None
    config = resolve_model_config(
        settings,
        agent=agent,
        task=task,
        cost_override=cost_override,
    )
    return OpenAIAdapter(config)
