from __future__ import annotations

from multi_agent_ds.agents.business_stakeholder import business_stakeholder_node
from multi_agent_ds.agents.ml_reviewer import ml_reviewer_node
from multi_agent_ds.core.contracts import BusinessReviewOutput, MLReviewOutput


def test_ml_reviewer_placeholder_imports() -> None:
    assert callable(ml_reviewer_node)


def test_business_stakeholder_placeholder_imports() -> None:
    assert callable(business_stakeholder_node)


def test_ml_review_output_accepts_structured_review() -> None:
    review = MLReviewOutput(
        summary="Mathematical case is acceptable.",
        approved=True,
        next_action="accept",
        decisions=[
            {
                "decision": "Tune learning rate downward.",
                "classification": "scientific",
                "mathematical_basis": "Cross-validation improved after the adjustment.",
                "reasoning_quality": "strong",
            }
        ],
    )

    assert review.approved is True
    assert review.decisions[0].classification == "scientific"


def test_business_review_output_accepts_revision_request() -> None:
    review = BusinessReviewOutput(
        summary="The report overstates business impact.",
        approved=False,
        next_action="revise_report",
        readability_assessment="Mostly readable but too technical in the caveats.",
        plausibility_assessment="The uplift claim needs better business framing.",
        concerns=[
            {
                "topic": "impact",
                "issue": "Business value is overstated.",
                "severity": "high",
            }
        ],
    )

    assert review.approved is False
    assert review.next_action == "revise_report"
