"""Tests for the unified multi-agent-ds CLI dispatcher."""

from __future__ import annotations

from typing import Any

import pytest

from multi_agent_ds import cli as cli_module


def _minimal_settings_with_expensive_route() -> dict[str, Any]:
    """Settings that resolve at least one route to the 'expensive' cost tier."""
    return {
        "data": {"synthetic": {"scale": "small", "scales": {"small": {"n_rows": 100}}}},
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
                "ml_modeler": {
                    "default": {"capability": "balanced", "cost": "cheap"},
                    "tuning_decision": {"capability": "reasoning", "cost": "expensive"},
                },
            },
        },
    }


def _minimal_cheap_settings() -> dict[str, Any]:
    """Settings where every route resolves to 'cheap' — no preflight warning."""
    settings = _minimal_settings_with_expensive_route()
    settings["llm"]["routes"]["ml_modeler"]["tuning_decision"] = {
        "capability": "balanced",
        "cost": "cheap",
    }
    return settings


def test_full_subcommand_dispatches_to_full_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_module, "load_settings", _minimal_cheap_settings)

    captured: dict[str, Any] = {}

    async def _fake_run_full_pipeline(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "final_state": {},
            "html_path": None,
            "started_at": "now",
            "duration_ms": 0.0,
            "turn_count": 0,
            "error": None,
        }

    # Patch the lazy import target inside the ``full_pipeline`` module.
    import multi_agent_ds.workflows.full_pipeline as fp_module

    monkeypatch.setattr(fp_module, "run_full_pipeline", _fake_run_full_pipeline)

    exit_code = cli_module._main(["full", "--no-record", "--entry-node", "eda_raw"])

    assert exit_code == 0
    assert captured["data_path"] is None
    assert captured["entry_node"] == "eda_raw"
    assert captured["record"] is False


def test_cost_preflight_triggers_on_expensive_tier(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_module, "load_settings", _minimal_settings_with_expensive_route
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": "n")

    exit_code = cli_module._main(["full"])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "cost preflight warning" in captured.err.lower()


def test_cost_preflight_bypassed_by_yes_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli_module, "load_settings", _minimal_settings_with_expensive_route
    )

    called: dict[str, Any] = {}

    async def _fake_run_full_pipeline(**kwargs: Any) -> dict[str, Any]:
        called["ran"] = True
        return {
            "final_state": {},
            "html_path": None,
            "started_at": "t",
            "duration_ms": 0.0,
            "turn_count": 0,
            "error": None,
        }

    import multi_agent_ds.workflows.full_pipeline as fp_module

    monkeypatch.setattr(fp_module, "run_full_pipeline", _fake_run_full_pipeline)
    # If input() is somehow called, the test should fail loudly.
    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt="": pytest.fail("preflight prompt should be skipped"),
    )

    exit_code = cli_module._main(["full", "--yes", "--no-record"])

    assert exit_code == 0
    assert called.get("ran") is True


def test_cost_preflight_bypassed_on_medium_scale_requires_yes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli_module, "load_settings", _minimal_cheap_settings)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "n")

    exit_code = cli_module._main(["full", "--scale", "medium"])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "cost preflight warning" in captured.err.lower()


def test_discovery_subcommand_invokes_discovery_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_module, "load_settings", _minimal_cheap_settings)

    captured: dict[str, Any] = {}

    def _fake_run_discovery_workflow(
        data_path: str | None = None,
        settings: dict[str, Any] | None = None,
        target_col: str | None = None,
    ) -> dict[str, Any]:
        captured["data_path"] = data_path
        captured["target_col"] = target_col
        return {
            "data_path": "x",
            "target_column": "target",
            "n_rows": 10,
            "n_features": 3,
            "profile": {},
        }

    import multi_agent_ds.workflows.discovery as discovery_module

    monkeypatch.setattr(
        discovery_module,
        "run_discovery_workflow",
        _fake_run_discovery_workflow,
    )

    exit_code = cli_module._main(
        ["discovery", "--data-path", "foo.parquet", "--target-col", "target"]
    )

    assert exit_code == 0
    assert captured["data_path"] == "foo.parquet"
    assert captured["target_col"] == "target"


def test_help_renders_for_all_subcommands() -> None:
    parser = cli_module._build_parser()
    help_text = parser.format_help()

    for command in ("full", "discovery", "preparation", "modeling", "evaluation"):
        assert command in help_text
