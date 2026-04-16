"""OpenAI provider adapter."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from typing import Any

from dotenv import load_dotenv
from openai import APIConnectionError, OpenAI, RateLimitError

from multi_agent_ds.adapters.llm.routing import ModelConfig


class OpenAIAdapter:
    """Thin OpenAI provider wrapper for agent-facing LLM calls.

    The adapter is provider-dumb: it accepts a fully-resolved ``ModelConfig``
    (see ``multi_agent_ds.adapters.llm.routing``) and issues API calls. All
    model / capability / cost routing lives upstream in
    ``resolve_model_config`` and ``build_adapter``.
    """

    _MAX_RETRY_ATTEMPTS = 3
    _BACKOFF_BASE_SECONDS = 1.0

    def __init__(self, config: ModelConfig):
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set in the environment or .env file")
        self.config = config
        self.model = config.model
        self.client = OpenAI(api_key=api_key)

    def _with_retries(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Retry transient OpenAI request errors with exponential backoff."""
        delay_seconds = self._BACKOFF_BASE_SECONDS

        for attempt in range(1, self._MAX_RETRY_ATTEMPTS + 1):
            try:
                return func(*args, **kwargs)
            except (RateLimitError, APIConnectionError):
                if attempt == self._MAX_RETRY_ATTEMPTS:
                    raise
                time.sleep(delay_seconds)
                delay_seconds *= 2

    def _build_request_kwargs(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assemble the SDK request kwargs, honoring reasoning-model quirks.

        Reasoning models (capability == 'reasoning', e.g. o3, o4-mini) require
        ``max_completion_tokens`` instead of ``max_tokens`` and reject any
        explicit ``temperature`` other than 1.0 — so we omit the field entirely
        when ``config.temperature is None``.
        """
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if self.config.capability == "reasoning":
            request_kwargs["max_completion_tokens"] = self.config.max_tokens
            # Intentionally omit `temperature` — do NOT pass temperature=None.
        else:
            request_kwargs["max_tokens"] = self.config.max_tokens
            request_kwargs["temperature"] = self.config.temperature
        if tools is not None:
            request_kwargs["tools"] = tools
        if response_format is not None:
            request_kwargs["response_format"] = response_format
        return request_kwargs

    def _create_chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> Any:
        """Create a chat completion request through one shared SDK path."""
        request_kwargs = self._build_request_kwargs(
            messages=messages,
            tools=tools,
            response_format=response_format,
        )
        return self._with_retries(self.client.chat.completions.create, **request_kwargs)

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Send a chat completion request."""
        response = self._create_chat_completion(messages=messages, tools=tools)
        message = response.choices[0].message
        return {
            "content": self._extract_text_content(message.content),
            "tool_calls": self._normalize_tool_calls(getattr(message, "tool_calls", None)),
            "usage": self._normalize_usage(getattr(response, "usage", None)),
        }

    def structured_output(self, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        """Request structured JSON output."""
        response = self._create_chat_completion(
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "schema": schema,
                },
            },
        )
        message = response.choices[0].message
        content = self._extract_text_content(message.content)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("OpenAI structured output was not valid JSON") from exc
        return {
            "parsed": parsed,
            "usage": self._normalize_usage(getattr(response, "usage", None)),
        }

    @staticmethod
    def _extract_text_content(content: Any) -> str:
        """Flatten assistant message content into a single text string."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content

        text_parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
                continue

            item_type = getattr(item, "type", None)
            if item_type == "text":
                text_value = getattr(item, "text", None)
                if isinstance(text_value, str):
                    text_parts.append(text_value)
                elif hasattr(text_value, "value"):
                    text_parts.append(str(text_value.value))
            elif hasattr(item, "text") and isinstance(item.text, str):
                text_parts.append(item.text)

        return "".join(text_parts)

    @staticmethod
    def _normalize_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
        """Convert SDK tool call objects into simple dictionaries."""
        if not tool_calls:
            return []

        normalized: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            function = getattr(tool_call, "function", None)
            normalized.append(
                {
                    "id": getattr(tool_call, "id", None),
                    "type": getattr(tool_call, "type", None),
                    "function": {
                        "name": getattr(function, "name", None),
                        "arguments": getattr(function, "arguments", None),
                    },
                }
            )
        return normalized

    @staticmethod
    def _normalize_usage(usage: Any) -> dict[str, int] | None:
        """Map SDK usage objects into a compact stable shape."""
        if usage is None:
            return None

        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)
        if prompt_tokens is None and completion_tokens is None and total_tokens is None:
            return None

        return {
            "input_tokens": int(prompt_tokens or 0),
            "output_tokens": int(completion_tokens or 0),
            "total_tokens": int(total_tokens or 0),
        }
