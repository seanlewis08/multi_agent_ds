# ML Modeler + ML Reviewer Implementation Plan

**Scope:** Sean Step 5 from `Sean_Plan.md` (BUILD_PLAN reference: Step 8 — ML modeler)
**Primary targets:** `src/multi_agent_ds/agents/ml_modeler.py`, `agents/ml_reviewer.py`, `workflows/modeling.py`
**Secondary targets:** `config/prompts.yaml`, `src/multi_agent_ds/core/contracts.py`, `orchestration/state.py`, `orchestration/router.py`, `orchestration/graph.py`, `config/workflows.yaml`
**Status:** Complete — 66 tests passing; branch `feature/step-10-ml-modeler-reviewer` pushed to origin at `6e732de`; awaiting PR open against `develop/multi_agent`.

## Purpose

Turn the existing modeling skills surface into an agentic modeling loop.

`skills/modeling.py` already exposes the nine pure modeling functions (baseline training, n-estimator search, Optuna tuning, re-training, learning-rate adjustment, native and permutation importance, feature-subset training). `workflows/modeling.py` already runs the non-agentic baseline with MLflow logging. This step adds the LLM reasoning layer on top:

- `ml_modeler` agent walks the nine-phase workflow, asking the LLM between phases to decide the next action.
- `ml_reviewer` agent inspects the modeler's decisions, challenges weak reasoning, and routes unfinished or unsound outputs back for revision.

The existing `eda_review` modes on both agents must keep working. This step adds new modes and keeps the current surface backwards-compatible at the agent-call boundary.

## Agent-Team Framing

- `plan_guardian`: Keep this scoped to Sean Step 5 only. No report generation, no business stakeholder review work, no evaluation-pipeline work.
- `architecture_guard`: Keep pure modeling logic in `skills/modeling.py`, MLflow and artifact persistence in `workflows/modeling.py`, and LLM reasoning in `agents/ml_modeler.py` and `agents/ml_reviewer.py`.
- `implementation_engineer`: Reuse the existing skill functions and registry. Do not rewrite or mirror skill logic inside the agent. Do not add a parallel modeling path.
- `efficiency_reviewer`: Keep per-phase LLM calls the smallest useful surface. Avoid round-tripping the full dataset through prompts. Serialize just the structured skill results.
- `commit_chronicler`: Commit after each coherent slice (baseline-review, tuning-review, feature-selection-review, reviewer integration, final validation) — not one mega-commit.

## Constraints

- Do not add a new script or CLI entrypoint.
- Per-step human-review notebooks under `notebooks/` are allowed (one per step, matching the established `Data_Engineer_Testing.ipynb` pattern). These are throwaway review aids, not runtime code.
- Do not add a new dependency.
- Do not duplicate modeling logic inside the agents. Agents orchestrate; skills compute.
- Do not move MLflow logging or artifact writes out of the workflow layer.
- Do not change `ALGORITHM_REGISTRY` shape or add new algorithms as part of this step (defer to FUTURE_WORK item 6).
- Keep the existing `eda_review` and `modeling_handoff` modes on both agents working unchanged.
- Keep the ML reviewer focused on challenging the modeler's reasoning — it does not retrain or re-tune models itself.

## Accepted Plan Deviations

The implementation intentionally diverges from the minimal-target list below in three places. Each deviation is documented here so later steps (router wiring, evaluation) do not re-introduce the original expectation.

- **`n_estimator_search` runs without an LLM call.** The plan originally called for an LLM to "accept or try a different lr" at this phase. No existing Pydantic contract captures that decision cleanly, and the learning-rate decision is already revisited in the `adjust_lr` phase via `LearningRateDecision`. Adding a second lr decision here would duplicate that surface. The mode is a pure skill wrapper that records the optimal n for each boosting algorithm; the LLM's first look at the lr happens at `adjust_lr`.
- **`importance_review` runs without an LLM call.** The plan originally called for an LLM to identify safe-to-drop features here. The `safe_to_remove` list returned by `get_permutation_importances` already encodes that signal deterministically, and the LLM's accept/reject call happens at the `feature_selection` phase via `FeatureSelectionDecision`. Splitting drop proposal and drop acceptance across two LLM calls adds a round-trip with no decision gained.
- **`adjust_lr` uses a fixed `lr/2` reduction rule.** The new learning rate is `current_lr * settings.model.tuning.lr_reduction_factor` (default `0.5`). The LLM only decides whether to keep or revert the adjustment. The factor is config-driven so future slices can tune the schedule without touching the agent.

## Minimal Target Design

This step produces:

- a new set of modeling modes on `agents/ml_modeler.py` that walk the nine-phase workflow with LLM decisions between phases
- a new set of review modes on `agents/ml_reviewer.py` that inspect each modeler decision against a checklist of mathematical-soundness rules
- a set of structured Pydantic contracts in `core/contracts.py` that describe modeler decisions and reviewer verdicts
- prompt templates in `config/prompts.yaml` under `sean_ml_modeler` and `ml_reviewer` keyed by phase
- state keys in `orchestration/state.py` for the modeling results, per-phase decisions, reviewer verdicts, and routing flags
- a router update in `orchestration/router.py` that sends unsound modeler output back for revision and sound output forward to downstream evaluation

The goal is **not** to rewrite the modeling skill surface. The goal is to give agents a structured way to drive it and to challenge each other's choices.

## Implementation Steps

### Step 1: Contracts + State

Extend `core/contracts.py`:

- `BaselineDecision` — which algorithms to tune, why.
- `TuningDecision` — accept tuned params or keep defaults, why.
- `LearningRateDecision` — keep adjusted lr or revert, why.
- `FeatureSelectionDecision` — which features to drop and the accept/revert call.
- `ModelingVerdict` — final modeler recommendation: best algorithm, reasoning, next action.
- `MLReviewerVerdict` — reviewer per-phase verdict: approve / request revision / escalate, with specific critique fields.

Extend `orchestration/state.py` with:

- `modeling_results` — structured per-algorithm phase outputs from skills
- `modeling_decisions` — list of per-phase modeler decisions
- `modeling_reviews` — list of reviewer verdicts keyed by phase
- `modeling_verdict` — final modeler recommendation
- `should_revise_modeling` — routing flag

### Step 2: ML Modeler Agent — Modeling Modes

Extend `agents/ml_modeler.py`:

- Keep existing `raw_review`, `processed_review`, `modeling_handoff` modes unchanged.
- Add `baseline` mode: runs `train_with_defaults`, asks LLM which algorithms to tune, returns decision + updated state.
- Add `n_estimator_search` mode (boosting only, guarded): runs `find_optimal_estimators`, asks LLM to accept or try a different lr.
- Add `tune` mode: runs `tune_algorithm`, asks LLM whether tuned params are worth adopting.
- Add `train_tuned` mode: runs `train_with_params`, records comparison against baseline.
- Add `adjust_lr` mode (boosting only, guarded): runs `adjust_learning_rate`, asks LLM whether to keep the new lr.
- Add `importance_review` mode: runs `get_feature_importances` and `get_permutation_importances`, asks LLM which features look safe to drop.
- Add `feature_selection` mode: runs `train_with_feature_subset`, asks LLM whether the reduced model wins.
- Add `final_recommendation` mode: asks LLM to compare all algorithms and produce a `ModelingVerdict`.

Each mode reuses the existing `_schema_for` / `_dump_model` / `_append_decision` helpers.

### Step 3: ML Reviewer Agent — Modeling Review Modes

Extend `agents/ml_reviewer.py`:

- Keep existing `raw_review` and `processed_review` modes unchanged.
- Add per-phase review modes that consume the modeler's latest decision plus the underlying skill result and produce an `MLReviewerVerdict`:
  - `baseline_review`
  - `tuning_review`
  - `lr_adjustment_review`
  - `feature_selection_review`
  - `final_recommendation_review`
- Each review mode returns either approve or `should_revise_modeling=True` plus a critique string the modeler can react to on the next pass.

### Step 4: Prompts + Router

Populate `config/prompts.yaml`:

- Under `sean_ml_modeler`: one `system` block and one prompt per new mode (`baseline`, `tune`, `adjust_lr`, `feature_selection`, `final_recommendation`, etc.).
- Under `ml_reviewer`: one prompt per new review mode, instructing the reviewer to challenge CV-vs-test gaps, unjustified param changes, and feature-drop decisions that lack permutation evidence.

Update `orchestration/router.py`:

- Add a router function that reads `should_revise_modeling` and either loops back to the modeler's previous mode or advances to the next modeling phase.
- Cap the revision loop with the existing `iteration` state field.

### Step 5: Validation and Closeout

Validate:

- each new modeler mode returns the expected state-update shape for the matching contract
- each new reviewer mode returns an `MLReviewerVerdict` with the approve / revise flag populated
- the existing EDA review modes on both agents still pass their tests
- the router correctly loops back on revise verdicts and advances on approve verdicts
- architecture boundaries hold — no skill logic migrated into the agent, no LLM calls migrated into the skill

## Done Criteria

This step is complete when:

- `agents/ml_modeler.py` can walk the full nine-phase workflow driven by LLM decisions
- `agents/ml_reviewer.py` produces phase-level verdicts that the router can act on
- every modeler decision and reviewer verdict is recorded in `agent_decisions` and the matching state keys
- the existing EDA review behavior is unchanged
- focused tests cover baseline, tuning, lr-adjustment, feature-selection, and final-recommendation modes plus the reviewer mirror modes

## Closeout

Not started.

## Resume Instructions

If work pauses, resume from:

- `project_planning/sean_step_artifacts/ML_Modeler_Reviewer_Checklist.md`

Recommended resume prompt:

```text
Use agent teams for this task. Pick back up where I left off in project_planning/sean_step_artifacts/ML_Modeler_Reviewer_Checklist.md and continue from the next unchecked item.
```
