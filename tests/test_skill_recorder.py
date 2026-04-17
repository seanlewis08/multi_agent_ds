"""Tests for the skill-call recorder and decorator."""

from __future__ import annotations

import time

from multi_agent_ds.tools.conversation_recorder import (
    NodeBoundary,
    conversation_recording,
)
from multi_agent_ds.tools.skill_recorder import (
    RecordedCall,
    SkillCall,
    SkillCallRecorder,
    get_active_skill_recorder,
    record_skill_call,
    record_tool_call,
    record_workflow_call,
    skill_recording,
)


@record_skill_call
def _fake_skill(x: int, y: int = 1) -> int:
    """Stand-in skill function for decorator tests."""
    return x + y


@record_skill_call
def _slow_skill() -> str:
    """Stand-in skill function with measurable latency."""
    time.sleep(0.005)
    return "done"


def test_decorator_is_a_no_op_when_no_recorder_active() -> None:
    assert get_active_skill_recorder() is None
    # Function still works and returns its real value.
    assert _fake_skill(2, 3) == 5
    # Recorder remains unset.
    assert get_active_skill_recorder() is None


def test_decorator_records_call_when_recorder_active() -> None:
    with skill_recording() as recorder:
        result = _fake_skill(2, 3)

    assert result == 5
    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call.call_index == 0
    assert call.skill.endswith("_fake_skill")
    # The decorator stamps the module's last component as the prefix.
    assert call.skill.startswith("test_skill_recorder.")
    assert call.elapsed_ms >= 0.0
    assert call.started_at  # ISO8601 string
    assert call.node is None  # no conversation_recorder active


def test_call_index_is_monotonic() -> None:
    with skill_recording() as recorder:
        _fake_skill(1)
        _fake_skill(2)
        _fake_skill(3)
    assert [c.call_index for c in recorder.calls] == [0, 1, 2]


def test_contextvar_isolates_nested_scopes() -> None:
    with skill_recording() as outer:
        _fake_skill(1)
        with skill_recording() as inner:
            _fake_skill(2)
        _fake_skill(3)

    assert len(outer.calls) == 2
    assert len(inner.calls) == 1


def test_node_inferred_from_active_conversation_recorder() -> None:
    with conversation_recording() as conv_rec:
        conv_rec.record_boundary(
            NodeBoundary(kind="start", node="ml_modeler_baseline", ts="t", elapsed_ms=0.0)
        )
        with skill_recording() as skill_rec:
            _fake_skill(1)
        conv_rec.record_boundary(
            NodeBoundary(kind="end", node="ml_modeler_baseline", ts="t1", elapsed_ms=10.0)
        )
        with skill_recording() as skill_rec_outside:
            _fake_skill(2)

    assert skill_rec.calls[0].node == "ml_modeler_baseline"
    # After the boundary closes, current_node clears and the next call has no node.
    assert skill_rec_outside.calls[0].node is None


def test_elapsed_is_monotonic_and_positive() -> None:
    with skill_recording() as recorder:
        _slow_skill()
    assert len(recorder.calls) == 1
    assert recorder.calls[0].elapsed_ms > 0.0


def test_flush_returns_dicts() -> None:
    with skill_recording() as recorder:
        _fake_skill(1)
    flushed = recorder.flush()
    assert len(flushed) == 1
    assert flushed[0]["skill"].endswith("_fake_skill")
    assert "elapsed_ms" in flushed[0]
    assert "started_at" in flushed[0]
    assert flushed[0]["call_index"] == 0


def test_skill_call_is_a_frozen_dataclass() -> None:
    call = SkillCall(
        call_index=0,
        node=None,
        skill="x.y",
        elapsed_ms=1.0,
        started_at="2026-04-16T00:00:00+00:00",
    )
    try:
        call.call_index = 1  # type: ignore[misc]
    except Exception as exc:
        assert "frozen" in str(exc).lower() or "cannot assign" in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError("SkillCall should be frozen")


def test_recorder_record_and_flush() -> None:
    recorder = SkillCallRecorder()
    recorder.record(
        SkillCall(
            call_index=0,
            node="eda_raw",
            skill="profiling.profile_dataset",
            elapsed_ms=12.5,
            started_at="2026-04-16T00:00:00+00:00",
        )
    )
    assert len(recorder.calls) == 1
    flushed = recorder.flush()
    assert flushed == [
        {
            "call_index": 0,
            "node": "eda_raw",
            "skill": "profiling.profile_dataset",
            "elapsed_ms": 12.5,
            "started_at": "2026-04-16T00:00:00+00:00",
            "layer": "skill",
        }
    ]


def test_runtime_smoke_records_modeling_skill_name() -> None:
    """Validation #3: with skill_recording active, a skills.modeling.* call
    is captured with the expected ``modeling.<func>`` skill name.
    """
    from multi_agent_ds.skills.modeling import prepare_data
    import pandas as pd

    df = pd.DataFrame({"x": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                        "target": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1]})
    with skill_recording() as recorder:
        prepare_data(df, target_col="target", test_size=0.2)

    assert any(call.skill == "modeling.prepare_data" for call in recorder.calls)


# ── Layer-aware decorators (tool / workflow) ───────────────────────────

@record_tool_call
def _fake_tool(x: int) -> int:
    """Stand-in tool function."""
    return x * 2


@record_workflow_call
def _fake_workflow(x: int) -> int:
    """Stand-in workflow function."""
    return x + 100


def test_record_tool_call_sets_layer() -> None:
    with skill_recording() as recorder:
        result = _fake_tool(5)
    assert result == 10
    assert len(recorder.calls) == 1
    assert recorder.calls[0].layer == "tool"
    assert recorder.calls[0].skill.endswith("_fake_tool")


def test_record_workflow_call_sets_layer() -> None:
    with skill_recording() as recorder:
        result = _fake_workflow(5)
    assert result == 105
    assert len(recorder.calls) == 1
    assert recorder.calls[0].layer == "workflow"
    assert recorder.calls[0].skill.endswith("_fake_workflow")


def test_all_three_decorators_share_one_active_recorder() -> None:
    with skill_recording() as recorder:
        _fake_skill(1)
        _fake_tool(2)
        _fake_workflow(3)

    assert len(recorder.calls) == 3
    layers_by_index = {call.call_index: call.layer for call in recorder.calls}
    assert layers_by_index == {0: "skill", 1: "tool", 2: "workflow"}


def test_default_layer_is_skill_for_back_compat() -> None:
    """Legacy ``SkillCall(...)`` construction without ``layer`` still works."""
    call = SkillCall(
        call_index=0,
        node=None,
        skill="x.y",
        elapsed_ms=1.0,
        started_at="2026-04-16T00:00:00+00:00",
    )
    assert call.layer == "skill"


def test_skill_call_is_alias_of_recorded_call() -> None:
    """``SkillCall`` must remain an alias of ``RecordedCall`` for imports."""
    assert SkillCall is RecordedCall
