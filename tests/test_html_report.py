"""Tests for the HTML conversation report emitter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from multi_agent_ds.tools.html_report import (
    render_conversation_html,
    write_conversation_html,
)


def _sample_turn(
    *,
    turn_index: int,
    agent: str,
    task: str | None,
    kind: str,
    response: dict[str, Any],
    messages_sent: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build one plain-dict turn matching ConversationRecorder.flush() shape."""
    return {
        "turn_index": turn_index,
        "agent": agent,
        "task": task,
        "capability": "balanced",
        "cost_tier": "cheap",
        "model": "gpt-4.1-mini",
        "kind": kind,
        "messages_sent": messages_sent
        or [
            {"role": "system", "content": f"system-{turn_index}"},
            {"role": "user", "content": f"user-{turn_index}"},
        ],
        "response": response,
        "usage": {"input_tokens": 5, "output_tokens": 7, "total_tokens": 12},
        "started_at": "2026-04-16T12:00:00+00:00",
        "elapsed_ms": 123.0,
    }


def test_render_produces_valid_html_structure() -> None:
    turns = [
        _sample_turn(
            turn_index=0,
            agent="eda_analyst",
            task="raw_review",
            kind="structured",
            response={"parsed": {"summary": "ok"}},
        ),
        _sample_turn(
            turn_index=1,
            agent="ml_modeler",
            task="baseline_decision",
            kind="structured",
            response={"parsed": {"summary": "good"}},
        ),
        _sample_turn(
            turn_index=2,
            agent="report_writer",
            task=None,
            kind="chat",
            response={"content": "final report text"},
        ),
    ]
    agent_decisions = [
        {"agent": "eda_analyst", "phase": "raw_eda"},
        {"agent": "ml_modeler", "phase": "modeling"},
        {"agent": "report_writer", "phase": "reporting"},
    ]
    meta = {
        "title": "Test Run",
        "started_at": "2026-04-16T12:00:00+00:00",
        "duration_ms": 1500.0,
        "turn_count": 3,
    }

    document = render_conversation_html(turns, agent_decisions, meta)

    assert document.startswith("<!DOCTYPE html>")
    assert "<nav" in document
    assert document.count('class="turn-card"') == 3
    # Each agent name appears as a badge.
    assert "eda_analyst" in document
    assert "ml_modeler" in document
    assert "report_writer" in document
    # Meta fields land in the header.
    assert "Test Run" in document


def test_render_escapes_html_in_prompts() -> None:
    malicious = "<script>alert('x')</script>"
    turn = _sample_turn(
        turn_index=0,
        agent="eda_analyst",
        task="raw_review",
        kind="chat",
        response={"content": malicious},
        messages_sent=[{"role": "user", "content": malicious}],
    )
    document = render_conversation_html([turn], [], {})

    assert malicious not in document
    assert "&lt;script&gt;" in document
    assert "alert(&#x27;x&#x27;)" in document or "alert('x')" not in document


def test_render_handles_zero_turns() -> None:
    document = render_conversation_html([], [], {"title": "Empty"})

    assert document.startswith("<!DOCTYPE html>")
    assert "No turns were recorded" in document
    assert "Empty" in document


def test_render_displays_error_banner() -> None:
    document = render_conversation_html(
        [],
        [],
        {"title": "Broken", "error": "ValueError: boom"},
    )

    assert "error-banner" in document
    assert "ValueError: boom" in document


def test_write_html_creates_report_and_latest(tmp_path: Path) -> None:
    primary = tmp_path / "run_one.html"
    turns = [
        _sample_turn(
            turn_index=0,
            agent="eda_analyst",
            task="raw_review",
            kind="chat",
            response={"content": "hello"},
        )
    ]

    result_path = write_conversation_html(
        turns=turns,
        agent_decisions=[{"agent": "eda_analyst", "phase": "raw_eda"}],
        meta={"title": "One"},
        path=primary,
    )

    latest = tmp_path / "conversation_latest.html"
    assert result_path == primary
    assert primary.exists()
    assert latest.exists()
    assert primary.read_text(encoding="utf-8") == latest.read_text(encoding="utf-8")
    assert "eda_analyst" in primary.read_text(encoding="utf-8")
