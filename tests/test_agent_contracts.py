from __future__ import annotations

from multi_agent_ds.agents.business_stakeholder import business_stakeholder_node
from multi_agent_ds.agents.data_engineer import data_engineer_node
from multi_agent_ds.agents.ml_modeler import ml_modeler_node
from multi_agent_ds.agents.ml_reviewer import ml_reviewer_node
from multi_agent_ds.core.contracts import (
    EDAReviewOutput,
    PreparationFeedbackOutput,
    PreparationPlanOutput,
    ProcessedApprovalOutput,
)


def test_agent_nodes_import() -> None:
    assert callable(business_stakeholder_node)
    assert callable(data_engineer_node)
    assert callable(ml_modeler_node)
    assert callable(ml_reviewer_node)


def test_eda_review_output_accepts_structured_review() -> None:
    review = EDAReviewOutput(
        reviewer_role="ml_reviewer",
        summary="The EDA identifies plausible leakage risk.",
        concerns=[{"topic": "leakage", "issue": "Target proxy is present.", "severity": "high"}],
        recommendations=["Drop the proxy column before modeling."],
        modeling_implications=["Feature screening should happen before fitting."],
        scientific_vs_art=[{"decision": "drop proxy column", "classification": "scientific"}],
    )

    assert review.reviewer_role == "ml_reviewer"
    assert review.concerns[0].severity == "high"


def test_preparation_plan_output_accepts_action_lists() -> None:
    prep_plan = PreparationPlanOutput(
        summary="Clip one outlier feature and impute numeric gaps.",
        approved=True,
        cleaning_actions=[
            {
                "area": "cleaning",
                "action": "clip_outliers_iqr",
                "rationale": "Reduce extreme leverage points.",
                "params": {"columns": ["claim_amount_avg"]},
            }
        ],
        feature_actions=[],
        handoff_notes=["Keep the target column untouched."],
    )

    assert prep_plan.approved is True
    assert prep_plan.cleaning_actions[0].action == "clip_outliers_iqr"


def test_preparation_feedback_output_accepts_feasibility_notes() -> None:
    feedback = PreparationFeedbackOutput(
        summary="The plan is feasible as written.",
        ready_for_execution=True,
        action_feedback=[
            {
                "action": "clip_outliers_iqr",
                "feasible": True,
                "reason": "The feature is numeric and bounded.",
            }
        ],
        execution_notes=["Run the plan once and re-profile the processed data."],
    )

    assert feedback.ready_for_execution is True
    assert feedback.action_feedback[0].feasible is True


def test_processed_approval_output_accepts_revision_request() -> None:
    approval = ProcessedApprovalOutput(
        approved=False,
        summary="The processed data still needs another prep iteration.",
        next_action="revise_preparation",
        concerns=["Missing-value handling needs another pass."],
        recommendations=["Impute the remaining gaps before modeling."],
    )

    assert approval.approved is False
    assert approval.next_action == "revise_preparation"
