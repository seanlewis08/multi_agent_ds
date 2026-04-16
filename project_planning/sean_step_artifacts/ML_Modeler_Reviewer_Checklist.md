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
- Current checkpoint: `Step 5 - Final validation and closeout`
- Human review completed through: `Step 3 - ML Reviewer agent modeling review modes`
- Testing completed through: `Step 5 - Final focused validation (47 passed)`

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

- [x] Add `baseline` mode
- [x] Add `n_estimator_search` mode with boosting guard
- [x] Add `tune` mode
- [x] Add `train_tuned` mode
- [x] Add `adjust_lr` mode with boosting guard
- [x] Add `importance_review` mode
- [x] Add `feature_selection` mode
- [x] Add `final_recommendation` mode
- [x] Preserve existing `raw_review`, `processed_review`, `modeling_handoff` modes

Human review checkpoint:

- [ ] Confirm every new mode delegates compute to `skills/modeling.py` and does no math itself
- [ ] Confirm per-mode state updates match the contracts from Step 1

Testing checkpoint:

- [x] Mocked-LLM agent tests cover each new mode
- [x] Boosting-guard modes return an informative skip on non-boosting algorithms

### Step 3: ML Reviewer Agent — Modeling Review Modes

- [x] Add `baseline_review` mode
- [x] Add `tuning_review` mode
- [x] Add `lr_adjustment_review` mode
- [x] Add `feature_selection_review` mode
- [x] Add `final_recommendation_review` mode
- [x] Preserve existing `raw_review` and `processed_review` modes

Human review checkpoint:

- [ ] Confirm each review mode returns an `MLReviewerVerdict` with an explicit approve/revise flag
- [ ] Confirm the reviewer never retrains or re-tunes models

Testing checkpoint:

- [x] Mocked-LLM reviewer tests cover each new review mode
- [x] Revise verdicts populate `should_revise_modeling` and a critique string

### Step 4: Prompts + Router

- [x] Add `sean_ml_modeler` prompts for each new mode
- [x] Add `ml_reviewer` prompts for each new review mode
- [x] Add a modeling revise/advance router function
- [x] Cap the revision loop with `iteration`

Human review checkpoint:

- [ ] Confirm prompts instruct the modeler to explain reasoning and the reviewer to challenge weak reasoning
- [ ] Confirm the router cannot loop forever

Testing checkpoint:

- [x] Router tests cover approve, revise, and iteration-cap paths

### Step 5: Final Validation and Commit Readiness

- [x] Run the focused Step 5 tests
- [x] Re-check the final ML Modeler + Reviewer slice against `Sean_Plan.md`
- [x] Re-check the final slice against architecture boundaries
- [x] Summarize remaining limitations, if any
- [ ] Ask: `Should I commit and push these changes?`

Human review checkpoint:

- [ ] Confirm the completed unit is reviewable on its own
- [ ] Confirm no unrelated worktree changes are being bundled

Testing checkpoint:

- [x] Final focused validation is complete and recorded below

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

```text
Date: 2026-04-16
Checkpoint: Step 2 - baseline mode
Status: Implementation complete, awaiting human review
Files touched:
- src/multi_agent_ds/agents/ml_modeler.py
- config/prompts.yaml (sean_ml_modeler.baseline_review)
- tests/test_pre_modeling_review_agents.py
- project_planning/sean_step_artifacts/ML_Modeler_Reviewer_Checklist.md
Validation run:
- uv run pytest tests/test_pre_modeling_review_agents.py tests/test_cleaning.py tests/test_feature_engineering.py tests/test_preparation_workflow.py (15 passed; +1 new)
Notes:
- baseline mode delegates compute to skills.modeling.train_with_defaults and only wraps the LLM call around the result; no math inside the agent.
- _serialize_baseline_for_prompt strips model, y_pred, y_prob before prompt serialization — those aren't JSON-serializable and aren't useful to the LLM.
- The decision is stored at modeling_results["baseline_decision"] and a summary is appended to agent_decisions, matching the existing pattern of "rich payload in a typed state key + brief metadata in agent_decisions".
- Remaining Step 2 modes (n_estimator_search, tune, train_tuned, adjust_lr, importance_review, feature_selection, final_recommendation) will follow the same shape.
Next item:
- Step 2 - tune + train_tuned modes (or n_estimator_search with boosting guard — order open)
```

```text
Date: 2026-04-16
Checkpoint: Step 2 - tune + train_tuned modes
Status: Implementation complete, awaiting human review
Files touched:
- src/multi_agent_ds/agents/ml_modeler.py
- config/prompts.yaml (sean_ml_modeler.tuning_review)
- tests/test_pre_modeling_review_agents.py
- project_planning/sean_step_artifacts/ML_Modeler_Reviewer_Checklist.md
Validation run:
- uv run pytest tests/test_pre_modeling_review_agents.py tests/test_cleaning.py tests/test_feature_engineering.py tests/test_preparation_workflow.py (17 passed; +2 new)
Notes:
- tune mode iterates over baseline_decision.algorithms_to_tune and calls tune_algorithm per algo. Boosting-only inputs (learning_rate, n_estimators) come from a prior n_estimator_search if present, otherwise from ALGORITHM_REGISTRY defaults via _boosting_inputs_for. Non-boosting models get None/None as intended by the skill signature.
- Each tuning result is serialized for the LLM by dropping trial_history (keeps param importances, convergence, rolling_best, best_params).
- train_tuned mode has no LLM call — it just executes the tune-phase decision. It re-fits only the algorithms flagged accept_tuned_params=True, stores the result, and records the primary-metric test-score delta vs. baseline.
- Per-algo decisions go into modeling_results["tuning_decisions"][algo] and brief entries accumulate in agent_decisions. This mirrors the baseline-mode storage pattern.
Next item:
- Step 2 - n_estimator_search mode with boosting guard
```

```text
Date: 2026-04-16
Checkpoint: Step 2 - n_estimator_search + adjust_lr + importance_review + feature_selection + final_recommendation
Status: Implementation complete, awaiting human review
Files touched:
- src/multi_agent_ds/agents/ml_modeler.py
- config/prompts.yaml (sean_ml_modeler.lr_adjustment_review, feature_selection_review, final_recommendation)
- tests/test_pre_modeling_review_agents.py
- project_planning/sean_step_artifacts/ML_Modeler_Reviewer_Checklist.md
Validation run:
- uv run pytest tests/test_pre_modeling_review_agents.py tests/test_cleaning.py tests/test_feature_engineering.py tests/test_preparation_workflow.py (22 passed; +5 new)
Notes:
- Fixed two bugs from the prior tune slice: _boosting_inputs_for now reads the skill's optimal_n_estimators key (was incorrectly reading best_n_estimators), and train_tuned now merges the fixed boosting inputs (learning_rate, n_estimators) from the tuning skill result into chosen_params so the retrained model uses the same rate/n_est pair tuning was evaluated against.
- n_estimator_search is a pure skill wrapper with no LLM call. Non-boosting algos are pre-filtered out (recorded in state["n_estimator_search_skipped"]); the skill's own boosting guard is belt-and-suspenders. Plan called for an LLM review here but no contract fits — the lr decision happens later in adjust_lr.
- adjust_lr applies a deterministic lr/2 rule, calls adjust_learning_rate, and asks the LLM to keep or revert via LearningRateDecision. Skips non-boosting and also skips boosting algos whose tune decision was accept_tuned_params=False (nothing to adjust from).
- importance_review is pure (no LLM). It picks the most recent fitted result per algo via _latest_result_for (phase preference: feature_selection -> adjust_lr -> train_tuned -> baseline) and collects native + permutation importance.
- feature_selection uses the permutation importance safe_to_remove list directly as the drop candidate set, refits with train_with_feature_subset, and asks the LLM to accept/reject. Skipped algos (no safe_to_remove) are recorded in state["feature_selection_skipped"].
- final_recommendation assembles a per-algo final-phase summary and asks the LLM for a ModelingVerdict. Verdict is stored at state["modeling_verdict"].
- All five new modes are covered by dedicated mocked-LLM tests; prior baseline/tune/train_tuned tests still pass unchanged.
Next item:
- Step 3 - ML Reviewer agent modeling review modes
```

```text
Date: 2026-04-16
Checkpoint: Step 3 - ML Reviewer agent modeling review modes
Status: Implementation complete, awaiting human review
Files touched:
- src/multi_agent_ds/agents/ml_reviewer.py
- config/prompts.yaml (ml_reviewer.baseline_review, tuning_review, lr_adjustment_review, feature_selection_review, final_recommendation_review)
- tests/test_pre_modeling_review_agents.py
- project_planning/sean_step_artifacts/ML_Modeler_Reviewer_Checklist.md
Validation run:
- uv run pytest tests/test_pre_modeling_review_agents.py tests/test_cleaning.py tests/test_feature_engineering.py tests/test_preparation_workflow.py (28 passed; +6 new)
Notes:
- The five new review modes share a single code path dispatched via _MODELING_REVIEW_MODES. Each mode calls _modeling_payload(state, phase) to build the {decision + underlying skill output} payload the LLM reviews, then asks for an MLReviewOutput with the matching phase field.
- Reused MLReviewOutput (with the optional phase field added in Step 1) for reviewer verdicts. The reviewer never retrains or re-tunes — it only inspects the modeler's decisions and the skill result that drove them.
- Revise verdicts set should_revise_modeling=True and leave summary + decisions[].revision_questions as the critique channel. The router in Step 4 will read should_revise_modeling to loop back.
- _strip_nested drops the same non-serializable / verbose keys the modeler strips (model, y_pred, y_prob, trial_history) so the reviewer's prompt payload stays compact.
- The per-phase review is unified across algorithms (one LLM call covers every algo's decision in that phase) rather than per-algo. This reduces LLM calls and keeps the reviewer's reasoning holistic.
- Existing raw_review and processed_review modes are untouched and still return EDAReviewOutput into their prior state keys (raw_eda_ml_review / processed_eda_ml_review).
- The agent_decisions entry uses review_phase instead of phase for the reviewed phase name, because _append_decision already takes phase as its positional argument for the current-mode label.
Next item:
- Step 4 - Prompts + router (router in orchestration/router.py)
```

```text
Date: 2026-04-16
Checkpoint: Step 4 - Prompts + router
Status: Implementation complete, awaiting human review
Files touched:
- src/multi_agent_ds/orchestration/router.py
- src/multi_agent_ds/orchestration/state.py
- src/multi_agent_ds/agents/ml_modeler.py
- config/workflows.yaml
- tests/test_langgraph_router.py
- tests/test_pre_modeling_review_agents.py
- notebooks/ML_Modeler_Reviewer_Step4_Review.ipynb
- project_planning/sean_step_artifacts/ML_Modeler_Reviewer_Checklist.md
Validation run:
- uv run pytest tests/test_langgraph_router.py tests/test_pre_modeling_review_agents.py tests/test_cleaning.py tests/test_feature_engineering.py tests/test_preparation_workflow.py (47 passed; +12 new router-plus-iteration tests, +5 assertions on modeling_iteration in existing modeler tests)
Notes:
- architecture-guard ruled option (a): modeler increments modeling_iteration per reviewed phase run, matching the existing eda_analyst.prep_plan precedent.
- Added modeling_iteration: int to PipelineState under Control flow (alongside iteration, should_loop, should_revise_modeling).
- Added config/workflows.yaml workflows.modeling.max_iterations: 3, read by a new _modeling_iteration_limit() helper in router.py paralleling _prep_iteration_limit().
- route_after_modeling_review reads current_phase + should_revise_modeling + modeling_iteration: revise + under cap -> f"ml_modeler_{current_phase}"; else advance to _MODELING_REVIEW_NEXT_NODE[current_phase]; unknown phase raises.
- The 5 reviewed modeler modes (baseline, tune, adjust_lr, feature_selection, final_recommendation) all return "modeling_iteration": state.get("modeling_iteration", 0) + 1. The 3 non-reviewed modes (n_estimator_search, train_tuned, importance_review) do not increment.
- Human-review notebook ML_Modeler_Reviewer_Step4_Review.ipynb walks accept / revise-under-cap / revise-at-cap / unknown-phase branches plus the pytest run.
Next item:
- Step 5 - Final validation and closeout
```

```text
Date: 2026-04-16
Checkpoint: Step 5 - Final validation and closeout
Status: Implementation complete, awaiting commit
Files touched:
- project_planning/sean_step_artifacts/ML_Modeler_Reviewer_Checklist.md
Validation run:
- uv run pytest tests/test_langgraph_router.py tests/test_pre_modeling_review_agents.py tests/test_cleaning.py tests/test_feature_engineering.py tests/test_preparation_workflow.py (47 passed)
Notes:
- Final ML Modeler + Reviewer slice is consistent with Sean_Plan.md (Step 5) and ML_Modeler_Reviewer_Implementation_Plan.md, with three documented deviations recorded in the plan's Accepted Plan Deviations section (notebooks allowed, n_estimator_search and importance_review run LLM-free by design, adjust_lr factor is config-driven).
- Architecture boundaries hold: skill math stays in skills/modeling.py, LLM calls stay in agents/, routing stays read-only in orchestration/router.py, no new files introduced in this final slice.
- Remaining limitations (follow-up slices, not Step 5 scope):
  * graph.py wiring (add_conditional_edges for the 5 review checkpoints against route_after_modeling_review) is deferred.
  * The modeler does not yet incorporate the reviewer's revision_questions into its next-turn prompt on loop-back; revision loops currently re-execute the same prompt.
  * An end-to-end graph integration test cannot be added until graph.py lands.
Next item:
- Commit-chronicler commit + push of Step 4 + Step 5 closeout.
```
