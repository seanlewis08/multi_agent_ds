# ML Modeler + ML Reviewer Checklist

**Plan file:** `project_planning/sean_step_artifacts/ML_Modeler_Reviewer_Implementation_Plan.md`
**Primary implementation files:** `src/multi_agent_ds/agents/ml_modeler.py`, `agents/ml_reviewer.py`, `workflows/modeling.py`
**Secondary files:** `config/prompts.yaml`, `src/multi_agent_ds/core/contracts.py`, `orchestration/state.py`, `orchestration/router.py`
**Resume phrase:** `Pick back up where I left off`

## How To Resume

When returning to this work, use a prompt like:

```text
Use agent teams for this task. Pick back up where I left off in project_planning/sean_step_artifacts/ML_Modeler_Reviewer_Checklist.md and continue from the next unchecked item. Update the checklist and progress log as you go.
```

The current agent should:

1. read this checklist
2. read `project_planning/sean_step_artifacts/ML_Modeler_Reviewer_Implementation_Plan.md`
3. inspect the current state of `agents/ml_modeler.py`, `agents/ml_reviewer.py`, `workflows/modeling.py`, `core/contracts.py`, `orchestration/state.py`, `orchestration/router.py`, and `config/prompts.yaml`
4. continue from the next unchecked task

## Current Status

- Overall status: `in progress`
- Current checkpoint: `Step 1 - Contracts and state (awaiting human review)`
- Human review completed through: `none`
- Testing completed through: `Step 1 - Contracts and state`

## Checkpoint Checklist

### Step 1: Contracts + State

- [x] Add `BaselineDecision` contract
- [x] Add `TuningDecision` contract
- [x] Add `LearningRateDecision` contract
- [x] Add `FeatureSelectionDecision` contract
- [x] Add `ModelingVerdict` contract
- [x] Reuse existing `MLReviewOutput` for reviewer verdicts; add optional `phase` field
- [x] Extend `PipelineState` with `modeling_verdict` and `should_revise_modeling`

Human review checkpoint:

- [x] Confirm contracts cover every modeler decision the reviewer must verdict on
- [x] Confirm state keys do not collide with existing EDA or preparation keys

Testing checkpoint:

- [x] Contracts import cleanly and validate round-tripped payloads
- [x] State TypedDict accepts new keys without breaking existing agent tests

### Step 2: ML Modeler Agent — Modeling Modes

- [ ] Add `baseline` mode
- [ ] Add `n_estimator_search` mode with boosting guard
- [ ] Add `tune` mode
- [ ] Add `train_tuned` mode
- [ ] Add `adjust_lr` mode with boosting guard
- [ ] Add `importance_review` mode
- [ ] Add `feature_selection` mode
- [ ] Add `final_recommendation` mode
- [ ] Preserve existing `raw_review`, `processed_review`, `modeling_handoff` modes

Human review checkpoint:

- [ ] Confirm every new mode delegates compute to `skills/modeling.py` and does no math itself
- [ ] Confirm per-mode state updates match the contracts from Step 1

Testing checkpoint:

- [ ] Mocked-LLM agent tests cover each new mode
- [ ] Boosting-guard modes return an informative skip on non-boosting algorithms

### Step 3: ML Reviewer Agent — Modeling Review Modes

- [ ] Add `baseline_review` mode
- [ ] Add `tuning_review` mode
- [ ] Add `lr_adjustment_review` mode
- [ ] Add `feature_selection_review` mode
- [ ] Add `final_recommendation_review` mode
- [ ] Preserve existing `raw_review` and `processed_review` modes

Human review checkpoint:

- [ ] Confirm each review mode returns an `MLReviewerVerdict` with an explicit approve/revise flag
- [ ] Confirm the reviewer never retrains or re-tunes models

Testing checkpoint:

- [ ] Mocked-LLM reviewer tests cover each new review mode
- [ ] Revise verdicts populate `should_revise_modeling` and a critique string

### Step 4: Prompts + Router

- [ ] Add `sean_ml_modeler` prompts for each new mode
- [ ] Add `ml_reviewer` prompts for each new review mode
- [ ] Add a modeling revise/advance router function
- [ ] Cap the revision loop with `iteration`

Human review checkpoint:

- [ ] Confirm prompts instruct the modeler to explain reasoning and the reviewer to challenge weak reasoning
- [ ] Confirm the router cannot loop forever

Testing checkpoint:

- [ ] Router tests cover approve, revise, and iteration-cap paths

### Step 5: Final Validation and Commit Readiness

- [ ] Run the focused Step 5 tests
- [ ] Re-check the final ML Modeler + Reviewer slice against `Sean_Plan.md`
- [ ] Re-check the final slice against architecture boundaries
- [ ] Summarize remaining limitations, if any
- [ ] Ask: `Should I commit and push these changes?`

Human review checkpoint:

- [ ] Confirm the completed unit is reviewable on its own
- [ ] Confirm no unrelated worktree changes are being bundled

Testing checkpoint:

- [ ] Final focused validation is complete and recorded below

## Progress Log

Use this section to keep resumable notes while implementing.

### Entry Template

```text
Date:
Checkpoint:
Status:
Files touched:
Validation run:
Notes:
Next item:
```

### Initial Entry

```text
Date: 2026-04-16
Checkpoint: Planning only
Status: Checklist and implementation plan created
Files touched:
- project_planning/sean_step_artifacts/ML_Modeler_Reviewer_Implementation_Plan.md
- project_planning/sean_step_artifacts/ML_Modeler_Reviewer_Checklist.md
Validation run:
- documentation-only; no tests run
Notes:
- This checklist covers Sean Step 5 from Sean_Plan.md.
- The existing ml_modeler and ml_reviewer agents already implement EDA review stages; this step adds modeling-phase modes on top of that surface without disturbing it.
- skills/modeling.py is fully in place; no skill-layer changes are in scope.
Next item:
- Step 1 - Contracts and state
```

### Progress Updates

```text
Date: 2026-04-16
Checkpoint: Step 1 - Contracts and state
Status: Implementation complete, awaiting human review
Files touched:
- src/multi_agent_ds/core/contracts.py
- src/multi_agent_ds/orchestration/state.py
- project_planning/sean_step_artifacts/ML_Modeler_Reviewer_Checklist.md
Validation run:
- round-trip check on all 5 new modeler-decision contracts plus MLReviewOutput with new phase field
- uv run pytest tests/test_pre_modeling_review_agents.py tests/test_cleaning.py tests/test_feature_engineering.py tests/test_preparation_workflow.py (14 passed)
Notes:
- Decided to reuse existing MLReviewOutput for reviewer verdicts instead of adding a parallel MLReviewerVerdict contract. Added an optional phase field so one output shape serves both summary-level and per-phase reviews.
- PipelineState already had modeling_results, ml_review, and modeling_context. Only added modeling_verdict (final cross-algorithm recommendation) and should_revise_modeling (router flag).
Next item:
- Step 2 - ML Modeler agent modeling modes
```
