# Report + Business Stakeholder Review Checklist

**Plan file:** `project_planning/sean_step_artifacts/Report_Business_Review_Implementation_Plan.md`
**Primary implementation files:** `src/multi_agent_ds/agents/report_writer.py` (NEW), `src/multi_agent_ds/agents/business_stakeholder.py`
**Secondary files:** `src/multi_agent_ds/tools/reporting.py`, `config/prompts.yaml`, `src/multi_agent_ds/orchestration/router.py`, `src/multi_agent_ds/orchestration/state.py`, `project_planning/PROJECT_TREE.md`
**Resume phrase:** `Pick back up where I left off`

## How To Resume

When returning to this work, use a prompt like:

```text
Use agent teams for this task. Pick back up where I left off in project_planning/sean_step_artifacts/Report_Business_Review_Checklist.md and continue from the next unchecked item. Update the checklist and progress log as you go.
```

The current agent should:

1. read this checklist
2. read `project_planning/sean_step_artifacts/Report_Business_Review_Implementation_Plan.md`
3. inspect the current state of `agents/report_writer.py` (if present), `agents/business_stakeholder.py`, `tools/reporting.py`, `core/contracts.py`, `orchestration/state.py`, `orchestration/router.py`, and `config/prompts.yaml`
4. confirm Sean Step 5 (ML Modeler + ML Reviewer) is merged before starting code work — Step 6 cannot ship before Step 5 closes
5. continue from the next unchecked task

## Current Status

- Overall status: `not started — planning artifacts only`
- Current checkpoint: `Pre-implementation — awaiting Sean Step 5 closeout and approval to create agents/report_writer.py`
- Human review completed through: `n/a`
- Testing completed through: `n/a`

## Pre-Implementation Gate

Before any code is written for Step 6:

- [ ] Sean Step 5 (ML Modeler + ML Reviewer) is merged to `main`
- [ ] Step 6 is on its own branch cut from `main` (do not layer onto the Step 5 branch)
- [ ] User has explicitly approved creation of `src/multi_agent_ds/agents/report_writer.py` (new file, not in PROJECT_TREE.md)
- [ ] Cross-owner check: confirm whether Jonathan's evaluation pipeline (Jonathan Step 2 / BUILD_PLAN Step 9) is producing `state["evaluation_result"]`. If not, plan to use a stub payload in tests and treat the field as optional in the report writer.

## Checkpoint Checklist

### Step 1: Contracts + State (verify-only, mostly)

- [ ] Verify `BusinessReviewOutput` and `BusinessConcern` in `core/contracts.py` cover the report-review surface (no edits expected)
- [ ] Verify `report_draft`, `experiment_report`, `business_review` are in `PipelineState` (no edits expected)
- [ ] Decide whether to add `should_revise_report` flag to `PipelineState` (decision deferred to Step 4 router design)
- [ ] Decide whether to add a `ReportDraft` Pydantic schema (default: no — emit raw markdown)

Human review checkpoint:

- [ ] Confirm no contract gaps for Step 6
- [ ] Confirm no state-key collisions

Testing checkpoint:

- [ ] Existing contract round-trip tests still pass

### Step 2: Report Writer Agent

- [ ] Surface `agents/report_writer.py` new-file approval gate to user
- [ ] Add pure state-summarization formatters to `tools/reporting.py` (data summary, modeling summary, evaluation summary, decision-trace summary) — return strings, no I/O, no agent imports
- [ ] Create `agents/report_writer.py` with `report_writer_node(state, mode="generate")`
- [ ] Implement `generate` mode: gather context, build prompt, call LLM, write to `state["experiment_report"]`, append `agent_decisions` entry
- [ ] Treat `state["evaluation_result"]` as optional; produce a report (with caveat) if absent
- [ ] Raise informative error if `state["modeling_verdict"]` is absent (cannot run out of order)

Human review checkpoint:

- [ ] Confirm `agents/report_writer.py` mirrors the `business_stakeholder.py` shape (helpers, prompt loading, structured-output pattern)
- [ ] Confirm `tools/reporting.py` formatters do not import from `agents/`, `orchestration/`, or `workflows/`
- [ ] Confirm `ExperimentLogger` in `tools/reporting.py` is untouched

Testing checkpoint:

- [ ] Mocked-LLM test: `report_writer_node(mode="generate")` happy path
- [ ] Mocked-LLM test: `report_writer_node(mode="generate")` with `evaluation_result=None`
- [ ] Test: report writer raises when `modeling_verdict` is missing
- [ ] Pure-function tests for each new `tools/reporting.py` formatter

### Step 3: Business Stakeholder `report_review` Mode

- [ ] Add `"report_review"` to `business_stakeholder_node` mode whitelist
- [ ] Implement `report_review` branch: read `state["experiment_report"]` + business context, call structured output with `BusinessReviewOutput`, write to `state["business_review"]`, append `agent_decisions` entry
- [ ] Set routing flag(s) for the Step 4 router based on `next_action` (`accept`, `revise_report`, `revise_modeling`)
- [ ] Preserve existing `raw_review` / `processed_review` modes unchanged

Human review checkpoint:

- [ ] Confirm new mode reuses the existing helper pattern (`_schema_for`, `_dump_model`, `_append_decision`)
- [ ] Confirm existing EDA review state keys (`raw_eda_business_review`, `processed_eda_business_review`) are not touched

Testing checkpoint:

- [ ] Mocked-LLM test for each `next_action` outcome (`accept`, `revise_report`, `revise_modeling`)
- [ ] Existing `raw_review` / `processed_review` tests still pass

### Step 4: Prompts + Router

- [ ] Add `report_writer.system` and `report_writer.generate` to `config/prompts.yaml`
- [ ] Add `business_stakeholder.report_review` to `config/prompts.yaml`
- [ ] Add a router function in `orchestration/router.py` that consumes the business review verdict and routes to accept / revise_report / revise_modeling
- [ ] Cap any revise_report loop with the existing `iteration` field; force-accept after the cap and record a note in `agent_decisions`

Human review checkpoint:

- [ ] Confirm prompts instruct the writer to address a non-technical audience and the reviewer to challenge unclear or unrealistic claims
- [ ] Confirm the router cannot loop forever

Testing checkpoint:

- [ ] Router tests cover accept, revise_report, revise_modeling, and iteration-cap paths

### Step 5: Validation, PROJECT_TREE Refresh, Commit Readiness

- [ ] Run the focused Step 6 tests
- [ ] Re-check the slice against `Sean_Plan.md` Step 6
- [ ] Re-check the slice against architecture boundaries (no skill / orchestration imports in `tools/reporting.py`; no I/O in formatter functions)
- [ ] Update `PROJECT_TREE.md`: add `agents/report_writer.py`; back-fill `agents/business_stakeholder.py` and `agents/ml_reviewer.py`; bump captured date
- [ ] Summarize remaining limitations
- [ ] Ask: `Should I commit and push these changes?`

Human review checkpoint:

- [ ] Confirm the completed unit is reviewable on its own
- [ ] Confirm no unrelated worktree changes are being bundled
- [ ] Confirm PROJECT_TREE update is minimal and in-scope

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
Status: Implementation plan and checklist created
Files touched:
- project_planning/sean_step_artifacts/Report_Business_Review_Implementation_Plan.md
- project_planning/sean_step_artifacts/Report_Business_Review_Checklist.md
Validation run:
- documentation-only; no tests run
Notes:
- This checklist covers Sean Step 6 from Sean_Plan.md (BUILD_PLAN Step 10).
- Step 6 must not start until Sean Step 5 (ML Modeler + ML Reviewer) is merged. The current branch (feature/step-10-ml-modeler-reviewer) belongs to Step 5.
- BusinessReviewOutput and the relevant PipelineState slots already exist; Step 1 of the implementation is mostly verification.
- The plan introduces one new agent file (agents/report_writer.py) — explicit user approval is required before that file is created.
- The plan extends agents/business_stakeholder.py with one new mode (report_review). Existing modes are untouched.
- tools/reporting.py gets new pure formatters; ExperimentLogger is not modified.
- evaluation_result is owned by Jonathan's pipeline (Step 9). Treat it as optional in the report writer and stub it in tests.
Next item:
- Pre-implementation gate: wait for Sean Step 5 to merge, then update Sean_Plan.md tracker to mark Step 6's tracking docs as present.
```

### Progress Updates

(none yet)
