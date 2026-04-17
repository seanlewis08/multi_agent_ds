"""Pure-function tests for ``resolve_model_config``.

No mocks or fixtures beyond literal settings dicts — the resolver is pure.
"""

from __future__ import annotations

from typing import Any

import pytest

from multi_agent_ds.adapters.llm import ModelConfig, resolve_model_config


def _routing_settings() -> dict[str, Any]:
    """Return a fully-populated settings dict that mirrors config/settings.yaml."""
    return {
        "llm": {
            "default_provider": "openai",
            "model_matrix": {
                "coding": {"cheap": "gpt-4.1-mini", "moderate": "gpt-4.1", "expensive": "gpt-4.1"},
                "balanced": {"cheap": "gpt-4.1-mini", "moderate": "gpt-4.1", "expensive": "gpt-4.1"},
                "reasoning": {"cheap": "o4-mini", "moderate": "o3", "expensive": "o3"},
            },
            "capability_settings": {
                "coding": {"temperature": 0.1, "max_tokens": 4096},
                "balanced": {"temperature": 0.2, "max_tokens": 2048},
                "reasoning": {"temperature": None, "max_tokens": 8192},
            },
            "routes": {
                "default": {"capability": "balanced", "cost": "cheap"},
                "eda_analyst": {"capability": "balanced", "cost": "cheap"},
                "ml_reviewer": {"capability": "balanced", "cost": "cheap"},
                "business_stakeholder": {"capability": "balanced", "cost": "cheap"},
                "data_engineer": {
                    "default": {"capability": "balanced", "cost": "cheap"},
                    "execute": {"capability": "coding", "cost": "moderate"},
                },
                "ml_modeler": {
                    "default": {"capability": "balanced", "cost": "cheap"},
                    "eda_review": {"capability": "balanced", "cost": "cheap"},
                    "baseline_decision": {"capability": "balanced", "cost": "cheap"},
                    "learning_rate_decision": {"capability": "reasoning", "cost": "cheap"},
                    "feature_selection_decision": {"capability": "reasoning", "cost": "cheap"},
                    "tuning_decision": {"capability": "reasoning", "cost": "expensive"},
                    "modeling_verdict": {"capability": "reasoning", "cost": "expensive"},
                    "modeling_handoff": {"capability": "balanced", "cost": "cheap"},
                },
            },
        }
    }


def test_direct_route_hit_returns_expected_reasoning_expensive_config() -> None:
    config = resolve_model_config(
        _routing_settings(),
        agent="ml_modeler",
        task="tuning_decision",
    )

    assert config == ModelConfig(
        provider="openai",
        model="o3",
        temperature=None,
        max_tokens=8192,
        capability="reasoning",
        cost_tier="expensive",
        profile_label="reasoning_expensive",
    )


def test_per_task_override_returns_balanced_cheap() -> None:
    config = resolve_model_config(
        _routing_settings(),
        agent="ml_modeler",
        task="baseline_decision",
    )

    assert config.capability == "balanced"
    assert config.cost_tier == "cheap"
    assert config.model == "gpt-4.1-mini"
    assert config.temperature == 0.2
    assert config.max_tokens == 2048
    assert config.profile_label == "balanced_cheap"


def test_agent_level_fallback_uses_agent_default() -> None:
    config = resolve_model_config(
        _routing_settings(),
        agent="ml_modeler",
        task="unknown_mode",
    )

    # ml_modeler.default is balanced/cheap.
    assert config.capability == "balanced"
    assert config.cost_tier == "cheap"
    assert config.profile_label == "balanced_cheap"


def test_global_fallback_uses_routes_default() -> None:
    config = resolve_model_config(
        _routing_settings(),
        agent="unknown_agent",
        task=None,
    )

    assert config.capability == "balanced"
    assert config.cost_tier == "cheap"
    assert config.model == "gpt-4.1-mini"


def test_shorthand_agent_route_resolves_without_default_nesting() -> None:
    """routes['eda_analyst'] is a bare {capability,cost} dict (no 'default' key)."""
    config = resolve_model_config(
        _routing_settings(),
        agent="eda_analyst",
        task="anything",
    )

    assert config.capability == "balanced"
    assert config.cost_tier == "cheap"
    assert config.model == "gpt-4.1-mini"


def test_cost_override_cheap_downshifts_cost_but_preserves_capability() -> None:
    config = resolve_model_config(
        _routing_settings(),
        agent="ml_modeler",
        task="tuning_decision",
        cost_override="cheap",
    )

    # Capability MUST be preserved; only the cost tier downshifts.
    assert config.capability == "reasoning"
    assert config.cost_tier == "cheap"
    assert config.model == "o4-mini"
    assert config.temperature is None
    assert config.max_tokens == 8192
    assert config.profile_label == "reasoning_cheap"


def test_cost_override_moderate_is_valid() -> None:
    config = resolve_model_config(
        _routing_settings(),
        agent="ml_modeler",
        task="tuning_decision",
        cost_override="moderate",
    )

    assert config.cost_tier == "moderate"
    assert config.capability == "reasoning"
    assert config.model == "o3"


def test_unknown_cost_override_raises_actionable_error() -> None:
    with pytest.raises(ValueError) as excinfo:
        resolve_model_config(
            _routing_settings(),
            agent="ml_modeler",
            task="tuning_decision",
            cost_override="bogus",
        )

    message = str(excinfo.value)
    assert "cost_override" in message
    assert "bogus" in message
    assert "cheap" in message  # nearest valid options are surfaced


def test_malformed_route_missing_capability_raises() -> None:
    settings = _routing_settings()
    settings["llm"]["routes"]["default"] = {"cost": "cheap"}  # missing capability
    settings["llm"]["routes"].pop("unknown_agent", None)

    with pytest.raises(ValueError, match="missing 'capability' or 'cost'"):
        resolve_model_config(settings, agent="unknown_agent", task=None)


def test_unknown_capability_in_route_raises_with_valid_options() -> None:
    settings = _routing_settings()
    settings["llm"]["routes"]["default"] = {"capability": "nonsense", "cost": "cheap"}

    with pytest.raises(ValueError) as excinfo:
        resolve_model_config(settings, agent="unknown_agent", task=None)

    message = str(excinfo.value)
    assert "nonsense" in message
    assert "balanced" in message
    assert "reasoning" in message


def test_reasoning_capability_preserves_temperature_null() -> None:
    config = resolve_model_config(
        _routing_settings(),
        agent="ml_modeler",
        task="tuning_decision",
    )

    # Must remain None — do NOT coerce to 0.0.
    assert config.temperature is None


def test_profile_label_format_is_capability_underscore_cost() -> None:
    for agent, task, expected in [
        ("ml_modeler", "tuning_decision", "reasoning_expensive"),
        ("ml_modeler", "learning_rate_decision", "reasoning_cheap"),
        ("eda_analyst", None, "balanced_cheap"),
        ("data_engineer", "execute", "coding_moderate"),
    ]:
        config = resolve_model_config(_routing_settings(), agent=agent, task=task)
        assert config.profile_label == expected, (agent, task)


def test_missing_llm_block_raises() -> None:
    with pytest.raises(ValueError, match="settings\\['llm'\\] is missing"):
        resolve_model_config({}, agent="eda_analyst", task=None)


def test_missing_routes_block_raises() -> None:
    settings = {"llm": {"model_matrix": {}, "capability_settings": {}}}
    with pytest.raises(ValueError, match="routes.*missing"):
        resolve_model_config(settings, agent="eda_analyst", task=None)
