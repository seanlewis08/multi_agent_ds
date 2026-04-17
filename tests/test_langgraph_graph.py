from __future__ import annotations

import pytest
from langgraph.graph.state import CompiledStateGraph, StateGraph

from multi_agent_ds.orchestration import graph as runtime_graph
from multi_agent_ds.orchestration.graph import build_graph


def test_build_graph_returns_state_graph() -> None:
    graph = build_graph()

    assert isinstance(graph, StateGraph)
    assert "eda_raw" in graph.nodes
    assert "data_engineer_execute" in graph.nodes
    assert "ml_modeler_handoff" in graph.nodes
    assert "evaluation" in graph.nodes
    assert "reviewer" in graph.nodes
    assert "report_writer" in graph.nodes
    assert "business_stakeholder_report_review" in graph.nodes


def test_build_graph_compiles() -> None:
    compiled = build_graph().compile()

    assert isinstance(compiled, CompiledStateGraph)


@pytest.mark.parametrize(
    "node_name",
    [
        "ml_modeler_baseline",
        "ml_reviewer_baseline_review",
        "ml_modeler_n_estimator_search",
        "ml_modeler_tune",
        "ml_reviewer_tuning_review",
        "ml_modeler_train_tuned",
        "ml_modeler_adjust_lr",
        "ml_reviewer_lr_adjustment_review",
        "ml_modeler_importance_review",
        "ml_modeler_feature_selection",
        "ml_reviewer_feature_selection_review",
        "ml_modeler_final_recommendation",
        "ml_reviewer_final_recommendation_review",
    ],
)
def test_modeling_loop_nodes_are_registered(node_name: str) -> None:
    graph = build_graph()
    assert node_name in graph.nodes


def test_modeling_loop_graph_compiles_end_to_end() -> None:
    """The full graph (pre-modeling EDA loop + modeling loop) must compile."""
    compiled = build_graph().compile()
    assert isinstance(compiled, CompiledStateGraph)


def test_build_graph_supports_baseline_only_entry_point() -> None:
    compiled = build_graph(entry_node="ml_modeler_handoff").compile()

    assert isinstance(compiled, CompiledStateGraph)


def test_evaluation_node_delegates_to_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = {
        "evaluation_result": {"winner": "lightgbm"},
        "reviewer_summary": {"winner": "lightgbm"},
        "shap_results": {"available": False},
        "shap_artifacts": {"metadata": {"available": False}},
        "mlflow_payload": {"metrics": {}},
    }

    monkeypatch.setattr(
        runtime_graph,
        "run_evaluation_from_state",
        lambda state: {**expected, "current_phase": "evaluation", "agent_decisions": state.get("agent_decisions", [])},
    )

    result = runtime_graph._evaluation_node({"modeling_results": {"baseline": {}}})

    assert result["evaluation_result"] == expected["evaluation_result"]
    assert result["reviewer_summary"] == expected["reviewer_summary"]
    assert result["current_phase"] == "evaluation"


def test_evaluation_node_requires_modeling_results() -> None:
    with pytest.raises(ValueError, match="state\\['modeling_results'\\]"):
        runtime_graph._evaluation_node({})


def test_baseline_only_entry_runs_through_evaluation_review_report_and_business_accept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_trace: list[tuple[str, str]] = []

    def fake_ml_modeler_node(state: dict, mode: str = "eda_review") -> dict:
        call_trace.append(("ml_modeler", mode))
        if mode == "modeling_handoff":
            return {
                "modeling_results": {
                    "baseline": {
                        "lightgbm": {"phase": "baseline", "test_scores": {"gini": 0.41}},
                    }
                }
            }
        if mode == "baseline":
            return {"current_phase": "baseline"}
        if mode == "tune":
            return {"current_phase": "tune"}
        if mode == "adjust_lr":
            return {"current_phase": "adjust_lr"}
        if mode == "feature_selection":
            return {"current_phase": "feature_selection"}
        if mode == "final_recommendation":
            return {
                "current_phase": "final_recommendation",
                "modeling_verdict": {"best_algorithm": "lightgbm"},
            }
        return {}

    def fake_ml_reviewer_node(state: dict, mode: str = "raw_review") -> dict:
        call_trace.append(("ml_reviewer", mode))
        review_phase = {
            "baseline_review": "baseline",
            "tuning_review": "tune",
            "lr_adjustment_review": "adjust_lr",
            "feature_selection_review": "feature_selection",
            "final_recommendation_review": "final_recommendation",
        }.get(mode, mode.replace("_review", ""))
        return {
            "current_phase": review_phase,
            "should_revise_modeling": False,
        }

    def fake_evaluation_from_state(state: dict) -> dict:
        call_trace.append(("workflow", "evaluation"))
        return {
            "evaluation_result": {"winner": "lightgbm", "primary_metric": "gini"},
            "reviewer_summary": {"winner": "lightgbm"},
            "shap_results": {"available": False},
            "shap_artifacts": {"metadata": {"available": False}},
            "mlflow_payload": {"metrics": {}},
            "current_phase": "evaluation",
            "should_loop": False,
            "loop_from": None,
        }

    def fake_reviewer_node(state: dict) -> dict:
        call_trace.append(("agent", "reviewer"))
        return {
            "dry_run": True,
            "branch_name": "experiment/lightgbm-2026-04-16",
            "staged_paths": [
                "config/settings.yaml",
                "reports/experiment_log_2026-04-16_000000.md",
            ],
            "commit_message": "[experiment] document lightgbm cycle (config snapshot, experiment log)",
            "pr_title": "Experiment: lightgbm",
            "pr_body": "generated pr description",
            "base_branch": "main",
            "commit_sha": None,
            "pr_number": None,
            "pr_url": None,
            "pr_metadata": {
                "title": "Experiment: lightgbm",
                "body": "generated pr description",
                "base": "main",
                "head": "experiment/lightgbm-2026-04-16",
                "draft": False,
            },
        }

    def fake_report_writer_node(state: dict, mode: str = "generate") -> dict:
        call_trace.append(("agent", "report_writer"))
        return {
            "experiment_report": "# Report\n\nLightGBM wins.",
            "report_draft": "# Report\n\nLightGBM wins.",
            "current_phase": "report_generate",
            "report_iteration": 1,
        }

    def fake_business_stakeholder_node(state: dict, mode: str = "raw_review") -> dict:
        call_trace.append(("agent", f"business_stakeholder:{mode}"))
        return {
            "business_review": {
                "approved": True,
                "next_action": "accept",
                "summary": "ready",
            },
            "should_revise_report": False,
            "should_revise_modeling": False,
            "current_phase": "report_review",
        }

    monkeypatch.setattr(runtime_graph, "ml_modeler_node", fake_ml_modeler_node)
    monkeypatch.setattr(runtime_graph, "ml_reviewer_node", fake_ml_reviewer_node)
    monkeypatch.setattr(runtime_graph, "run_evaluation_from_state", fake_evaluation_from_state)
    monkeypatch.setattr(runtime_graph, "reviewer_node", fake_reviewer_node)
    monkeypatch.setattr(runtime_graph, "report_writer_node", fake_report_writer_node)
    monkeypatch.setattr(
        runtime_graph,
        "business_stakeholder_node",
        fake_business_stakeholder_node,
    )

    compiled = build_graph(entry_node="ml_modeler_handoff").compile()
    result = compiled.invoke({"agent_decisions": []})

    assert result["evaluation_result"] == {"winner": "lightgbm", "primary_metric": "gini"}
    assert result["reviewer_summary"] == {"winner": "lightgbm"}
    assert result["mlflow_payload"] == {"metrics": {}}
    assert result["dry_run"] is True
    assert result["branch_name"] == "experiment/lightgbm-2026-04-16"
    assert result["pr_metadata"]["head"] == "experiment/lightgbm-2026-04-16"
    assert result["experiment_report"] == "# Report\n\nLightGBM wins."
    assert result["business_review"]["next_action"] == "accept"
    assert result["should_revise_report"] is False
    assert result["should_revise_modeling"] is False
    assert ("workflow", "evaluation") in call_trace
    assert ("agent", "reviewer") in call_trace
    assert ("agent", "report_writer") in call_trace
    assert ("agent", "business_stakeholder:report_review") in call_trace
