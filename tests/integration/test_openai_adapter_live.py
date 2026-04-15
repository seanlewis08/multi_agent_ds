from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from multi_agent_ds.adapters.llm import OpenAIAdapter
from multi_agent_ds.core import load_settings

load_dotenv()

_LIVE_CHAT_PROMPT = os.getenv(
    "OPENAI_LIVE_CHAT_PROMPT",
    "Reply in fewer than 20 words hello world.",
)
_MAX_CHAT_WORDS = 20

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("RUN_OPENAI_LIVE_TESTS") != "1",
    reason=(
        "OPENAI_API_KEY and RUN_OPENAI_LIVE_TESTS=1 are required "
        "for live OpenAI integration tests"
    ),
)


@pytest.fixture
def adapter() -> OpenAIAdapter:
    return OpenAIAdapter(load_settings())


def test_live_chat_round_trip(adapter: OpenAIAdapter) -> None:
    result = adapter.chat([{"role": "user", "content": _LIVE_CHAT_PROMPT}])
    print(f"\nLive chat response: {result['content']}")

    assert isinstance(result["content"], str)
    assert result["content"].strip()
    assert len(result["content"].split()) < _MAX_CHAT_WORDS
    assert isinstance(result["tool_calls"], list)
    assert result["usage"] is None or isinstance(result["usage"], dict)


def test_live_structured_output_round_trip(adapter: OpenAIAdapter) -> None:
    result = adapter.structured_output(
        messages=[
            {
                "role": "user",
                "content": "Return JSON with answer=42 and ok=true.",
            }
        ],
        schema={
            "type": "object",
            "properties": {
                "answer": {"type": "integer"},
                "ok": {"type": "boolean"},
            },
            "required": ["answer", "ok"],
            "additionalProperties": False,
        },
    )

    assert result["parsed"] == {"answer": 42, "ok": True}
    assert result["usage"] is None or isinstance(result["usage"], dict)
