"""LangGraph skeleton for the expanded pre-modeling EDA workflow."""

from __future__ import annotations

from langgraph.graph import END
from langgraph.graph.state import StateGraph

from multi_agent_ds.agents.business_stakeholder import business_stakeholder_node
from multi_agent_ds.agents.data_engineer import data_engineer_node
from multi_agent_ds.agents.eda_analyst import eda_analyst_node
from multi_agent_ds.agents.ml_modeler import ml_modeler_node
from multi_agent_ds.agents.ml_reviewer import ml_reviewer_node
from multi_agent_ds.orchestration.router import (
    route_after_data_engineer_execute,
    route_after_data_engineer_feedback,
    route_after_modeling_handoff,
    route_after_modeling_review,
    route_after_prep_plan,
    route_after_processed_approval,
    route_after_processed_eda,
    route_after_raw_eda,
)
from multi_agent_ds.orchestration.state import PipelineState


def build_graph() -> StateGraph:
    """Build the shared LangGraph state graph for pre-modeling review and prep."""
    graph = StateGraph(PipelineState)

    graph.add_node("eda_raw", lambda state: eda_analyst_node(state, mode="raw"))
    graph.add_node(
        "ml_modeler_raw_review",
        lambda state: ml_modeler_node(state, mode="raw_review"),
    )
    graph.add_node(
        "ml_reviewer_raw_review",
        lambda state: ml_reviewer_node(state, mode="raw_review"),
    )
    graph.add_node(
        "business_stakeholder_raw_review",
        lambda state: business_stakeholder_node(state, mode="raw_review"),
    )
    graph.add_node("eda_prep_plan", lambda state: eda_analyst_node(state, mode="prep_plan"))
    graph.add_node(
        "data_engineer_feedback",
        lambda state: data_engineer_node(state, mode="feedback"),
    )
    graph.add_node(
        "data_engineer_execute",
        lambda state: data_engineer_node(state, mode="execute"),
    )
    graph.add_node("eda_processed", lambda state: eda_analyst_node(state, mode="processed"))
    graph.add_node(
        "ml_modeler_processed_review",
        lambda state: ml_modeler_node(state, mode="processed_review"),
    )
    graph.add_node(
        "ml_reviewer_processed_review",
        lambda state: ml_reviewer_node(state, mode="processed_review"),
    )
    graph.add_node(
        "business_stakeholder_processed_review",
        lambda state: business_stakeholder_node(state, mode="processed_review"),
    )
    graph.add_node(
        "eda_processed_approval",
        lambda state: eda_analyst_node(state, mode="processed_approval"),
    )
    graph.add_node(
        "ml_modeler_handoff",
        lambda state: ml_modeler_node(state, mode="modeling_handoff"),
    )

    # --- modeling loop: 5 reviewed modeler modes + 3 non-reviewed bridges + 5 reviewer verdicts ---
    graph.add_node("ml_modeler_baseline", lambda state: ml_modeler_node(state, mode="baseline"))
    graph.add_node(
        "ml_reviewer_baseline_review",
        lambda state: ml_reviewer_node(state, mode="baseline_review"),
    )
    graph.add_node(
        "ml_modeler_n_estimator_search",
        lambda state: ml_modeler_node(state, mode="n_estimator_search"),
    )
    graph.add_node("ml_modeler_tune", lambda state: ml_modeler_node(state, mode="tune"))
    graph.add_node(
        "ml_reviewer_tuning_review",
        lambda state: ml_reviewer_node(state, mode="tuning_review"),
    )
    graph.add_node(
        "ml_modeler_train_tuned",
        lambda state: ml_modeler_node(state, mode="train_tuned"),
    )
    graph.add_node("ml_modeler_adjust_lr", lambda state: ml_modeler_node(state, mode="adjust_lr"))
    graph.add_node(
        "ml_reviewer_lr_adjustment_review",
        lambda state: ml_reviewer_node(state, mode="lr_adjustment_review"),
    )
    graph.add_node(
        "ml_modeler_importance_review",
        lambda state: ml_modeler_node(state, mode="importance_review"),
    )
    graph.add_node(
        "ml_modeler_feature_selection",
        lambda state: ml_modeler_node(state, mode="feature_selection"),
    )
    graph.add_node(
        "ml_reviewer_feature_selection_review",
        lambda state: ml_reviewer_node(state, mode="feature_selection_review"),
    )
    graph.add_node(
        "ml_modeler_final_recommendation",
        lambda state: ml_modeler_node(state, mode="final_recommendation"),
    )
    graph.add_node(
        "ml_reviewer_final_recommendation_review",
        lambda state: ml_reviewer_node(state, mode="final_recommendation_review"),
    )

    graph.set_entry_point("eda_raw")
    graph.add_conditional_edges(
        "eda_raw",
        route_after_raw_eda,
        {
            "ml_modeler_raw_review": "ml_modeler_raw_review",
            "ml_reviewer_raw_review": "ml_reviewer_raw_review",
            "business_stakeholder_raw_review": "business_stakeholder_raw_review",
        },
    )
    graph.add_edge(
        [
            "ml_modeler_raw_review",
            "ml_reviewer_raw_review",
            "business_stakeholder_raw_review",
        ],
        "eda_prep_plan",
    )
    graph.add_conditional_edges(
        "eda_prep_plan",
        route_after_prep_plan,
        {
            "data_engineer_feedback": "data_engineer_feedback",
            "data_engineer_execute": "data_engineer_execute",
        },
    )
    graph.add_conditional_edges(
        "data_engineer_feedback",
        route_after_data_engineer_feedback,
        {"eda_prep_plan": "eda_prep_plan"},
    )
    graph.add_conditional_edges(
        "data_engineer_execute",
        route_after_data_engineer_execute,
        {"eda_processed": "eda_processed"},
    )
    graph.add_conditional_edges(
        "eda_processed",
        route_after_processed_eda,
        {
            "ml_modeler_processed_review": "ml_modeler_processed_review",
            "ml_reviewer_processed_review": "ml_reviewer_processed_review",
            "business_stakeholder_processed_review": "business_stakeholder_processed_review",
        },
    )
    graph.add_edge(
        [
            "ml_modeler_processed_review",
            "ml_reviewer_processed_review",
            "business_stakeholder_processed_review",
        ],
        "eda_processed_approval",
    )
    graph.add_conditional_edges(
        "eda_processed_approval",
        route_after_processed_approval,
        {
            "eda_prep_plan": "eda_prep_plan",
            "ml_modeler_handoff": "ml_modeler_handoff",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "ml_modeler_handoff",
        route_after_modeling_handoff,
        {"ml_modeler_baseline": "ml_modeler_baseline"},
    )

    # Modeling loop edges: each reviewed modeler phase flows into its reviewer,
    # whose verdict drives route_after_modeling_review (loop back or advance).
    # Non-reviewed bridges (n_estimator_search, train_tuned, importance_review)
    # use direct edges — no decision at those nodes.
    graph.add_edge("ml_modeler_baseline", "ml_reviewer_baseline_review")
    graph.add_conditional_edges(
        "ml_reviewer_baseline_review",
        route_after_modeling_review,
        {
            "ml_modeler_baseline": "ml_modeler_baseline",
            "ml_modeler_n_estimator_search": "ml_modeler_n_estimator_search",
        },
    )
    graph.add_edge("ml_modeler_n_estimator_search", "ml_modeler_tune")
    graph.add_edge("ml_modeler_tune", "ml_reviewer_tuning_review")
    graph.add_conditional_edges(
        "ml_reviewer_tuning_review",
        route_after_modeling_review,
        {
            "ml_modeler_tune": "ml_modeler_tune",
            "ml_modeler_train_tuned": "ml_modeler_train_tuned",
        },
    )
    graph.add_edge("ml_modeler_train_tuned", "ml_modeler_adjust_lr")
    graph.add_edge("ml_modeler_adjust_lr", "ml_reviewer_lr_adjustment_review")
    graph.add_conditional_edges(
        "ml_reviewer_lr_adjustment_review",
        route_after_modeling_review,
        {
            "ml_modeler_adjust_lr": "ml_modeler_adjust_lr",
            "ml_modeler_importance_review": "ml_modeler_importance_review",
        },
    )
    graph.add_edge("ml_modeler_importance_review", "ml_modeler_feature_selection")
    graph.add_edge("ml_modeler_feature_selection", "ml_reviewer_feature_selection_review")
    graph.add_conditional_edges(
        "ml_reviewer_feature_selection_review",
        route_after_modeling_review,
        {
            "ml_modeler_feature_selection": "ml_modeler_feature_selection",
            "ml_modeler_final_recommendation": "ml_modeler_final_recommendation",
        },
    )
    graph.add_edge("ml_modeler_final_recommendation", "ml_reviewer_final_recommendation_review")
    graph.add_conditional_edges(
        "ml_reviewer_final_recommendation_review",
        route_after_modeling_review,
        {
            "ml_modeler_final_recommendation": "ml_modeler_final_recommendation",
            "end": END,
        },
    )

    return graph
