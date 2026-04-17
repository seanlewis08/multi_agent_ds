"""Regression tests for the `agent_decisions` channel-reducer contract.

`PipelineState.agent_decisions` is reduced with `operator.add` in
`multi_agent_ds.orchestration.state`. Every node MUST return only the NEW
entries it wants to contribute — the reducer concatenates with the current
channel value.

History: a prior version of every `_append_decision` helper returned
`state.get("agent_decisions", []) + [new]`, which combined with the reducer
produced exponential duplication across serial + fan-out nodes. A 40-event
demo recording grew to 271 MB and 65,536 agent_decisions entries before
`eda_processed_approval`. This test locks the contract so the bug cannot
regress silently.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest

from multi_agent_ds.agents.business_stakeholder import (
    _append_decision as business_stakeholder_append,
)
from multi_agent_ds.agents.data_engineer import _append_decision as data_engineer_append
from multi_agent_ds.agents.eda_analyst import _append_decision as eda_analyst_append
from multi_agent_ds.agents.ml_modeler import _append_decision as ml_modeler_append
from multi_agent_ds.agents.ml_reviewer import _append_decision as ml_reviewer_append
from multi_agent_ds.agents.report_writer import _append_decision as report_writer_append


_HELPERS: list[tuple[str, Callable[..., list[dict[str, Any]]]]] = [
    ("eda_analyst", eda_analyst_append),
    ("data_engineer", data_engineer_append),
    ("ml_reviewer", ml_reviewer_append),
    ("ml_modeler", ml_modeler_append),
    ("business_stakeholder", business_stakeholder_append),
    ("report_writer", report_writer_append),
]


@pytest.mark.parametrize("agent_name,helper", _HELPERS, ids=[name for name, _ in _HELPERS])
def test_append_decision_returns_only_the_delta(agent_name: str, helper: Callable[..., list[dict[str, Any]]]) -> None:
    """The helper must return exactly the one new entry, regardless of prior history."""
    # Empty history.
    delta = helper({"agent_decisions": []}, "some_phase", detail="x")
    assert delta == [{"agent": agent_name, "phase": "some_phase", "detail": "x"}]

    # Populated history — the helper must NOT echo existing entries.
    prior = [{"agent": "prior_agent", "phase": "prior_phase", "i": i} for i in range(100)]
    delta = helper({"agent_decisions": prior}, "some_phase", detail="x")
    assert delta == [{"agent": agent_name, "phase": "some_phase", "detail": "x"}], (
        f"{agent_name}._append_decision returned more than the delta; this reintroduces "
        "exponential duplication under PipelineState's operator.add reducer."
    )


def test_reducer_concatenates_deltas_linearly() -> None:
    """Two nodes each returning a 1-element delta must yield a 2-element channel under operator.add."""
    import operator

    # Simulate what LangGraph's channel reducer does: apply operator.add between
    # the current channel value and each update.
    state: list[dict[str, Any]] = []
    delta1 = eda_analyst_append({"agent_decisions": state}, "raw_eda")
    state = operator.add(state, delta1)

    delta2 = data_engineer_append({"agent_decisions": state}, "prep_execute")
    state = operator.add(state, delta2)

    assert len(state) == 2
    assert state[0]["agent"] == "eda_analyst"
    assert state[1]["agent"] == "data_engineer"
