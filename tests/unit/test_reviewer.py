from __future__ import annotations

import pytest

from multi_agent_ds.agents import reviewer as reviewer_agent


class RecordingAdapter:
    def __init__(self, settings: dict[str, object]) -> None:
        self.settings = settings
        self.messages: list[dict[str, object]] = []

    def chat(self, messages: list[dict[str, object]]) -> dict[str, object]:
        self.messages = messages
        return {"content": "generated pr description", "tool_calls": [], "usage": None}


class FixedDate:
    @staticmethod
    def today() -> object:
        class _Today:
            @staticmethod
            def isoformat() -> str:
                return "2026-04-15"

        return _Today()


def test_reviewer_node_uses_state_settings_and_builds_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, RecordingAdapter] = {}
    branch_calls: list[str] = []
    stage_calls: list[list[str]] = []
    commit_messages: list[str] = []
    push_calls: list[str] = []
    pr_calls: list[dict[str, object]] = []

    class FakeAdapter(RecordingAdapter):
        def __init__(self, settings: dict[str, object]) -> None:
            super().__init__(settings)
            captured["adapter"] = self

    monkeypatch.setattr(reviewer_agent, "OpenAIAdapter", FakeAdapter)
    monkeypatch.setattr(reviewer_agent.git_tools, "create_branch", branch_calls.append)
    monkeypatch.setattr(reviewer_agent.git_tools, "stage_files", stage_calls.append)

    def fake_commit(message: str) -> str:
        commit_messages.append(message)
        return "commit-123"

    def fake_push(branch_name: str, force: bool = False, cwd: object = None) -> None:
        push_calls.append(branch_name)

    def fake_create_pull_request(
        *,
        title: str,
        body: str,
        base: str = "main",
        head: str | None = None,
        draft: bool = False,
        cwd: object = None,
    ) -> dict[str, object]:
        pr_calls.append(
            {
                "title": title,
                "body": body,
                "base": base,
                "head": head,
                "draft": draft,
            }
        )
        return {
            "number": 7,
            "title": title,
            "url": "https://example.com/pr/7",
            "body": body,
            "head": head,
            "base": base,
            "draft": draft,
            "state": "OPEN",
        }

    monkeypatch.setattr(reviewer_agent.git_tools, "commit", fake_commit)
    monkeypatch.setattr(reviewer_agent.git_tools, "push_branch", fake_push)
    monkeypatch.setattr(reviewer_agent.git_tools, "create_pull_request", fake_create_pull_request)
    monkeypatch.setattr(reviewer_agent, "date", FixedDate)

    state = {
        "settings": {
            "git": {"default_base_branch": "develop"},
            "llm": {
                "providers": {
                    "openai": {
                        "model": "test-model",
                        "temperature": 0.1,
                        "max_tokens": 128,
                    }
                }
            }
        },
        "data_path": "data/raw.csv",
        "modeling_results": {"accuracy": 0.93},
        "evaluation_result": {"status": "pass"},
        "agent_decisions": [{"agent": "ml", "decision": "accept"}],
        "current_phase": "review",
        "should_loop": False,
        "iteration": 2,
        "report_draft": "draft report",
        "experiment_report": "final report",
        "experiment_log_path": "reports/experiment_log_2026-04-15_070704.md",
        "business_review": {"ready": True},
    }

    result = reviewer_agent.reviewer_node(state)

    assert result["branch_name"] == "experiment/pass-2026-04-15"
    assert result["commit_sha"] == "commit-123"
    assert result["pr_number"] == 7
    assert result["pr_url"] == "https://example.com/pr/7"
    assert result["pr_title"] == "Experiment: pass"
    assert result["pr_metadata"]["number"] == 7

    assert branch_calls == ["experiment/pass-2026-04-15"]
    assert stage_calls == [[
        "config/settings.yaml",
        "reports/experiment_log_2026-04-15_070704.md",
    ]]
    assert commit_messages == ["[experiment] document pass cycle (config snapshot, experiment log)"]
    assert push_calls == ["experiment/pass-2026-04-15"]
    assert pr_calls == [
        {
            "title": "Experiment: pass",
            "body": "generated pr description",
            "base": "develop",
            "head": "experiment/pass-2026-04-15",
            "draft": False,
        }
    ]

    adapter = captured["adapter"]
    assert adapter.settings is state["settings"]
    assert len(adapter.messages) == 2
    assert adapter.messages[0]["role"] == "system"
    assert (
        "include what was tested, why, the results, key decisions, and config changes"
        in str(adapter.messages[0]["content"]).lower()
    )

    prompt = str(adapter.messages[1]["content"])
    assert "Generate a pull request description from this experiment context:" in prompt
    assert '"data_path": "data/raw.csv"' in prompt
    assert '"accuracy": 0.93' in prompt
    assert '"status": "pass"' in prompt
    assert '"agent": "ml"' in prompt
    assert '"iteration": 2' in prompt


def test_reviewer_node_falls_back_to_loaded_settings_and_handles_missing_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, RecordingAdapter] = {}
    branch_calls: list[str] = []
    stage_calls: list[list[str]] = []
    commit_messages: list[str] = []
    push_calls: list[str] = []
    pr_calls: list[dict[str, object]] = []
    fallback_settings = {
        "llm": {
            "providers": {
                "openai": {
                    "model": "fallback-model",
                    "temperature": 0.0,
                    "max_tokens": 64,
                }
            }
        }
    }

    class FakeAdapter(RecordingAdapter):
        def __init__(self, settings: dict[str, object]) -> None:
            super().__init__(settings)
            captured["adapter"] = self

    monkeypatch.setattr(reviewer_agent, "OpenAIAdapter", FakeAdapter)
    monkeypatch.setattr(reviewer_agent, "load_settings", lambda: fallback_settings)
    monkeypatch.setattr(reviewer_agent.git_tools, "create_branch", branch_calls.append)
    monkeypatch.setattr(reviewer_agent.git_tools, "stage_files", stage_calls.append)

    def fake_commit(message: str) -> str:
        commit_messages.append(message)
        return "commit-456"

    def fake_push(branch_name: str, force: bool = False, cwd: object = None) -> None:
        push_calls.append(branch_name)

    def fake_create_pull_request(
        *,
        title: str,
        body: str,
        base: str = "main",
        head: str | None = None,
        draft: bool = False,
        cwd: object = None,
    ) -> dict[str, object]:
        pr_calls.append(
            {
                "title": title,
                "body": body,
                "base": base,
                "head": head,
                "draft": draft,
            }
        )
        return {
            "number": 8,
            "title": title,
            "url": "https://example.com/pr/8",
            "body": body,
            "head": head,
            "base": base,
            "draft": draft,
            "state": "OPEN",
        }

    monkeypatch.setattr(reviewer_agent.git_tools, "commit", fake_commit)
    monkeypatch.setattr(reviewer_agent.git_tools, "push_branch", fake_push)
    monkeypatch.setattr(reviewer_agent.git_tools, "create_pull_request", fake_create_pull_request)
    monkeypatch.setattr(reviewer_agent, "date", FixedDate)

    state = {
        "modeling_results": {"loss": 0.21},
    }

    result = reviewer_agent.reviewer_node(state)

    assert result["branch_name"] == "experiment/run-2026-04-15"
    assert result["commit_sha"] == "commit-456"
    assert result["pr_number"] == 8
    assert result["pr_url"] == "https://example.com/pr/8"
    assert result["pr_title"] == "Experiment: run"
    assert result["pr_metadata"]["number"] == 8

    assert branch_calls == ["experiment/run-2026-04-15"]
    assert stage_calls == [["config/settings.yaml"]]
    assert commit_messages == ["[experiment] document run cycle (config snapshot, experiment log)"]
    assert push_calls == ["experiment/run-2026-04-15"]
    assert pr_calls == [
        {
            "title": "Experiment: run",
            "body": "generated pr description",
            "base": "main",
            "head": "experiment/run-2026-04-15",
            "draft": False,
        }
    ]

    adapter = captured["adapter"]
    assert adapter.settings is fallback_settings
    assert len(adapter.messages) == 2
    assert (
        "include what was tested, why, the results, key decisions, and config changes"
        in str(adapter.messages[0]["content"]).lower()
    )

    prompt = str(adapter.messages[1]["content"])
    assert '"data_path": null' in prompt
    assert '"evaluation_result": null' in prompt
    assert '"agent_decisions": []' in prompt
    assert '"current_phase": null' in prompt
    assert '"should_loop": null' in prompt
    assert '"iteration": null' in prompt
    assert '"report_draft": null' in prompt
    assert '"experiment_report": null' in prompt
    assert '"business_review": null' in prompt
    assert '"loss": 0.21' in prompt


def test_reviewer_node_dry_run_returns_plan_without_git_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, RecordingAdapter] = {}

    class FakeAdapter(RecordingAdapter):
        def __init__(self, settings: dict[str, object]) -> None:
            super().__init__(settings)
            captured["adapter"] = self

    def unexpected_call(*args: object, **kwargs: object) -> None:
        raise AssertionError("git side effects should not run during dry_run")

    monkeypatch.setattr(reviewer_agent, "OpenAIAdapter", FakeAdapter)
    monkeypatch.setattr(reviewer_agent.git_tools, "create_branch", unexpected_call)
    monkeypatch.setattr(reviewer_agent.git_tools, "stage_files", unexpected_call)
    monkeypatch.setattr(reviewer_agent.git_tools, "commit", unexpected_call)
    monkeypatch.setattr(reviewer_agent.git_tools, "push_branch", unexpected_call)
    monkeypatch.setattr(reviewer_agent.git_tools, "create_pull_request", unexpected_call)
    monkeypatch.setattr(reviewer_agent, "date", FixedDate)

    state = {
        "dry_run": True,
        "settings": {
            "git": {"default_base_branch": "develop"},
            "llm": {
                "providers": {
                    "openai": {
                        "model": "test-model",
                        "temperature": 0.1,
                        "max_tokens": 128,
                    }
                }
            },
        },
        "evaluation_result": {"winner": "lightgbm"},
        "experiment_log_path": "reports/experiment_log_2026-04-15_070704.md",
    }

    result = reviewer_agent.reviewer_node(state)

    assert result["dry_run"] is True
    assert result["branch_name"] == "experiment/lightgbm-2026-04-15"
    assert result["staged_paths"] == [
        "config/settings.yaml",
        "reports/experiment_log_2026-04-15_070704.md",
    ]
    assert result["commit_message"] == "[experiment] document lightgbm cycle (config snapshot, experiment log)"
    assert result["pr_title"] == "Experiment: lightgbm"
    assert result["base_branch"] == "develop"
    assert result["commit_sha"] is None
    assert result["pr_number"] is None
    assert result["pr_url"] is None
    assert result["pr_metadata"] == {
        "title": "Experiment: lightgbm",
        "body": "generated pr description",
        "base": "develop",
        "head": "experiment/lightgbm-2026-04-15",
        "draft": False,
    }

    adapter = captured["adapter"]
    assert adapter.settings is state["settings"]
