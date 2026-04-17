"""Contextvar-scoped recording of skill / tool / workflow function calls.

Mirrors the conversation_recorder pattern: a module-level ContextVar holds an
active SkillCallRecorder; a decorator stamps calls into it when active; when
no recorder is active, decorated functions behave exactly as before (zero
overhead beyond a ContextVar.get).

This module originally recorded only skill-layer calls. It now supports three
co-equal layers — ``skill``, ``tool``, and ``workflow`` — via three decorators
that share one private factory and one active recorder. The original
``SkillCall`` / ``record_skill_call`` names remain as back-compat aliases.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import wraps
from time import perf_counter
from typing import Any, Callable, Iterator


@dataclass(frozen=True)
class RecordedCall:
    """One recorded function invocation from the skill / tool / workflow layers."""

    call_index: int
    node: str | None  # current graph node if known (from conversation_recorder)
    skill: str  # ``<module>.<qualname>`` — retained for key stability
    elapsed_ms: float
    started_at: str  # ISO8601 UTC
    layer: str = "skill"  # one of "skill" | "tool" | "workflow"
    # Args intentionally NOT captured by default — inputs can be huge
    # dataframes. A future slice can add a redaction mechanism.


# Back-compat alias: older imports and tests read ``SkillCall`` directly.
SkillCall = RecordedCall


class SkillCallRecorder:
    """Ordered collection of recorded calls for a single pipeline run."""

    def __init__(self) -> None:
        self.calls: list[RecordedCall] = []

    def record(self, call: RecordedCall) -> None:
        """Append one call to the recorder."""
        self.calls.append(call)

    def flush(self) -> list[dict[str, Any]]:
        """Return all calls as plain dicts (safe for JSON / HTML emission)."""
        return [asdict(call) for call in self.calls]


_active_skill_recorder: ContextVar[SkillCallRecorder | None] = ContextVar(
    "_active_skill_recorder", default=None
)


def get_active_skill_recorder() -> SkillCallRecorder | None:
    """Return the recorder active in the current context, or None."""
    return _active_skill_recorder.get()


@contextmanager
def skill_recording() -> Iterator[SkillCallRecorder]:
    """Activate a fresh recorder for the enclosed scope.

    The same recorder captures skill / tool / workflow layers — all three
    decorators push into whatever recorder is active here.

    Usage::

        with skill_recording() as recorder:
            run_pipeline(...)
        calls = recorder.flush()
    """
    recorder = SkillCallRecorder()
    token = _active_skill_recorder.set(recorder)
    try:
        yield recorder
    finally:
        _active_skill_recorder.reset(token)


def _make_recorder(layer: str) -> Callable[[Callable], Callable]:
    """Build a decorator that stamps calls with the given ``layer`` value.

    When no recorder is active, decorated functions are a near-zero-overhead
    pass-through (one ContextVar.get per call).
    """

    def decorator(func: Callable) -> Callable:
        skill_name = f"{func.__module__.split('.')[-1]}.{func.__qualname__}"

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            recorder = _active_skill_recorder.get()
            if recorder is None:
                return func(*args, **kwargs)
            # Try to get current graph node from the conversation recorder.
            try:
                from multi_agent_ds.tools.conversation_recorder import (
                    get_active_recorder,
                )

                conv_rec = get_active_recorder()
                node = conv_rec.current_node if conv_rec is not None else None
            except Exception:
                node = None
            t0 = perf_counter()
            started = datetime.now(timezone.utc).isoformat()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed_ms = (perf_counter() - t0) * 1000
                call = RecordedCall(
                    call_index=len(recorder.calls),
                    node=node,
                    skill=skill_name,
                    elapsed_ms=elapsed_ms,
                    started_at=started,
                    layer=layer,
                )
                recorder.record(call)

        return wrapper

    return decorator


# Three co-equal decorators sharing one factory and one active recorder.
record_skill_call = _make_recorder("skill")
record_tool_call = _make_recorder("tool")
record_workflow_call = _make_recorder("workflow")
