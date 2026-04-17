from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from multi_agent_ds.adapters.llm import ModelConfig, OpenAIAdapter
from openai import APIConnectionError, RateLimitError


def _balanced_config() -> ModelConfig:
    return ModelConfig(
        provider="openai",
        model="gpt-4.1-mini",
        temperature=0.2,
        max_tokens=2048,
        capability="balanced",
        cost_tier="cheap",
        profile_label="balanced_cheap",
    )


def _reasoning_config() -> ModelConfig:
    return ModelConfig(
        provider="openai",
        model="o3",
        temperature=None,
        max_tokens=8192,
        capability="reasoning",
        cost_tier="expensive",
        profile_label="reasoning_expensive",
    )


@pytest.fixture
def adapter(monkeypatch: pytest.MonkeyPatch) -> OpenAIAdapter:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    return OpenAIAdapter(_balanced_config())


@pytest.fixture
def reasoning_adapter(monkeypatch: pytest.MonkeyPatch) -> OpenAIAdapter:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    return OpenAIAdapter(_reasoning_config())


def test_openai_adapter_is_exported_from_llm_package() -> None:
    from multi_agent_ds.adapters.llm import OpenAIAdapter as ExportedOpenAIAdapter

    assert ExportedOpenAIAdapter is OpenAIAdapter


def test_with_retries_retries_then_succeeds(
    adapter: OpenAIAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(429, request=request)
    attempts = {"count": 0}
    sleep_calls: list[float] = []

    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RateLimitError("rate limited", response=response, body=None)
        return "ok"

    monkeypatch.setattr("multi_agent_ds.adapters.llm.openai.time.sleep", sleep_calls.append)

    result = adapter._with_retries(flaky)

    assert result == "ok"
    assert attempts["count"] == 3
    assert sleep_calls == [1.0, 2.0]


def test_with_retries_raises_after_exhausting_attempts(
    adapter: OpenAIAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    attempts = {"count": 0}
    sleep_calls: list[float] = []

    def always_fails() -> None:
        attempts["count"] += 1
        raise APIConnectionError(message="boom", request=request)

    monkeypatch.setattr("multi_agent_ds.adapters.llm.openai.time.sleep", sleep_calls.append)

    with pytest.raises(APIConnectionError):
        adapter._with_retries(always_fails)

    assert attempts["count"] == 3
    assert sleep_calls == [1.0, 2.0]


def test_balanced_request_kwargs_use_max_tokens_and_include_temperature(
    adapter: OpenAIAdapter,
) -> None:
    """Non-reasoning models MUST use ``max_tokens`` and include ``temperature``."""
    kwargs = adapter._build_request_kwargs(
        messages=[{"role": "user", "content": "hi"}],
    )

    assert kwargs["model"] == "gpt-4.1-mini"
    assert kwargs["max_tokens"] == 2048
    assert kwargs["temperature"] == 0.2
    assert "max_completion_tokens" not in kwargs


def test_reasoning_request_kwargs_use_max_completion_tokens_and_omit_temperature(
    reasoning_adapter: OpenAIAdapter,
) -> None:
    """Reasoning models MUST use ``max_completion_tokens`` and OMIT ``temperature``."""
    kwargs = reasoning_adapter._build_request_kwargs(
        messages=[{"role": "user", "content": "think"}],
    )

    assert kwargs["model"] == "o3"
    assert kwargs["max_completion_tokens"] == 8192
    assert "max_tokens" not in kwargs
    assert "temperature" not in kwargs


def test_create_chat_completion_uses_shared_request_path(
    adapter: OpenAIAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = [{"role": "user", "content": "hello"}]
    tools = [{"type": "function", "function": {"name": "ping", "parameters": {"type": "object"}}}]
    response_format = {"type": "json_schema", "json_schema": {"name": "shape", "schema": {"type": "object"}}}
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_create(**kwargs: object) -> object:
        captured["create_kwargs"] = kwargs
        return sentinel

    def fake_with_retries(func, *args, **kwargs):
        captured["func"] = func
        captured["args"] = args
        captured["kwargs"] = kwargs
        return func(*args, **kwargs)

    monkeypatch.setattr(adapter.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(adapter, "_with_retries", fake_with_retries)

    result = adapter._create_chat_completion(
        messages=messages,
        tools=tools,
        response_format=response_format,
    )

    assert result is sentinel
    assert captured["args"] == ()
    assert captured["kwargs"] == {
        "model": adapter.model,
        "messages": messages,
        "temperature": adapter.config.temperature,
        "max_tokens": adapter.config.max_tokens,
        "tools": tools,
        "response_format": response_format,
    }


def test_chat_returns_normalized_content_tool_calls_and_usage(
    adapter: OpenAIAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Hello "),
            SimpleNamespace(type="text", text=SimpleNamespace(value="world")),
        ],
        tool_calls=[
            SimpleNamespace(
                id="call_1",
                type="function",
                function=SimpleNamespace(name="ping", arguments='{"value":1}'),
            )
        ],
    )
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18),
    )

    monkeypatch.setattr(adapter, "_create_chat_completion", lambda **_: response)

    result = adapter.chat(messages=[{"role": "user", "content": "hi"}])

    assert result == {
        "content": "Hello world",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "ping",
                    "arguments": '{"value":1}',
                },
            }
        ],
        "usage": {
            "input_tokens": 11,
            "output_tokens": 7,
            "total_tokens": 18,
        },
    }


def test_chat_returns_empty_tool_calls_and_usage_when_missing(
    adapter: OpenAIAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = SimpleNamespace(content="Plain text", tool_calls=None)
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    monkeypatch.setattr(adapter, "_create_chat_completion", lambda **_: response)

    result = adapter.chat(messages=[{"role": "user", "content": "hi"}])

    assert result == {
        "content": "Plain text",
        "tool_calls": [],
        "usage": None,
    }


def test_structured_output_returns_parsed_json_and_usage(
    adapter: OpenAIAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = SimpleNamespace(content='{"answer": 42}', tool_calls=None)
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3, total_tokens=8),
    )

    monkeypatch.setattr(adapter, "_create_chat_completion", lambda **_: response)

    result = adapter.structured_output(
        messages=[{"role": "user", "content": "Return JSON"}],
        schema={"type": "object", "properties": {"answer": {"type": "integer"}}},
    )

    assert result == {
        "parsed": {"answer": 42},
        "usage": {
            "input_tokens": 5,
            "output_tokens": 3,
            "total_tokens": 8,
        },
    }


def test_structured_output_raises_for_invalid_json(
    adapter: OpenAIAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = SimpleNamespace(content="not-json", tool_calls=None)
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    monkeypatch.setattr(adapter, "_create_chat_completion", lambda **_: response)

    with pytest.raises(ValueError, match="not valid JSON"):
        adapter.structured_output(
            messages=[{"role": "user", "content": "Return JSON"}],
            schema={"type": "object"},
        )
