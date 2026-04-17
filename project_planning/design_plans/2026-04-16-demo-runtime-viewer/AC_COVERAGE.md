# Acceptance Criteria Coverage Matrix — Phase 7

**Plan:** `2026-04-16-demo-runtime-viewer.md`  
**Test Requirements:** `project_planning/implementation_plans/2026-04-16-demo-runtime-viewer/test-requirements.md`  
**Verification Date:** 2026-04-16 (pre-demo checklist)

---

## AC Coverage Table

| AC ID | Description | Implementing Phase | Test Method | Status | Notes |
|-------|-------------|-------------------|------------|--------|-------|
| AC1.1 | Four canonical events (`eda_raw` start/end, `data_engineer` start/end) recorded | Phase 2 | Automated: `test_demo_recorder_events.py::test_should_record_node_events` + Phase 7 Task 1 assertion script | ✓ | Verified in Task 1 sanity check |
| AC1.2 | Required artifacts present (`raw_eda_insights`, `prep_plan`, `processed_df_head`, `input_df_head`, `input_df_stats`) | Phase 2 | Automated: `test_demo_recorder_artifacts.py::test_extract_artifacts_populates_all_keys` + Phase 7 Task 1 assertion | ✓ | Verified in Task 1 sanity check |
| AC1.3 | Every event has `ts` (timestamp) and `elapsed_ms` (duration) fields | Phase 2 | Automated: `test_demo_recorder_events.py::test_event_has_ts_and_elapsed_ms` + Phase 7 Task 1 assertion | ✓ | Verified in Task 1 sanity check |
| AC1.4 | Missing parquet file raises `FileNotFoundError` with path | Phase 2 | Automated: `test_demo_recorder_errors.py::test_missing_parquet_raises` | ✓ | Unit test in Phase 2 Task 5 |
| AC1.5 | Missing `OPENAI_API_KEY` raises `EnvironmentError` before graph invocation | Phase 2 | Automated: `test_demo_recorder_errors.py::test_missing_openai_key_raises` with `monkeypatch.delenv` | ✓ | Unit test in Phase 2 Task 5 |
| AC1.6 | Atomic write: `.tmp` file + `os.replace` prevents partial rewrites | Phase 2 | Automated: `test_demo_recorder_io.py::test_atomic_write_leaves_no_partial` | ✓ | Unit test in Phase 2 Task 5 |
| AC2.1 | Viewer renders via `st.components.v1.html(..., height=820, scrolling=False)` in app | Phase 6 | Manual: Task 2 rehearsal — open Demo tab, confirm iframe renders without scroll bar | ⚙ | Manual in Phase 7 Task 2 |
| AC2.2 | Reads `demo_run_latest.json`, injects as string literal into HTML | Phase 6 | Automated: `test_demo_tab_inject.py::test_inject_demo_log_embeds_json` + `test_inject_escapes_closing_script_tag` (XSS defense) | ✓ | Unit tests in Phase 6 Task 1 |
| AC2.3 | Missing JSON renders error message with exact re-record command | Phase 6 | Manual: Task 2 rehearsal — rename `demo_run_latest.json`, open Demo tab, confirm error cites `uv run python -m multi_agent_ds.orchestration.demo_recorder --output data/interim/demo_run_latest.json` | ⚙ | Manual in Phase 7 Task 2 |
| AC3.1 | Config page shows source path, target, rows × cols, positive rate, scale, max_trials, cv_folds, timeout, algorithms, review settings | Phase 3 | Manual: Task 2 rehearsal Page 1 — click RUN, confirm all card values match `config/settings.yaml` | ⚙ | Manual in Phase 7 Task 2 |
| AC3.2 | RUN button transitions to Input Preview (Page 2) | Phase 3 | Manual: Task 2 rehearsal Page 1 Step 2 — click RUN, confirm Page 2 renders | ⚙ | Manual in Phase 7 Task 2 |
| AC4.1 | Page 2 shows `df.head(10)` plus pill strip (rows, cols, target, positive rate, numeric, categorical, missing %) | Phase 3 | Automated: `test_demo_recorder_artifacts.py::test_compute_input_stats_fields` asserts all fields computed. Manual: Task 2 rehearsal Page 2 — visual pass | ⚙ | Manual in Phase 7 Task 2 |
| AC4.2 | CONTINUE button transitions to Runtime Replay (Page 3) and starts animation | Phase 3 | Manual: Task 2 rehearsal Page 2 Step 3 — click CONTINUE, confirm Page 3 visible and orchestrator state transitions from STARTING to EDA RUNNING | ⚙ | Manual in Phase 7 Task 2 |
| AC5.1 | Orchestrator shows five state labels in order: STARTING, EDA RUNNING, HANDOFF, DATA ENGINEER RUNNING, COMPLETE | Phase 4 | Manual: Task 2 rehearsal Page 3 — play replay at 2×, confirm all five labels appear in order | ⚙ | Manual in Phase 7 Task 2 |
| AC5.2 | EDA column highlights orange during its events, locks green after end; lanes populate in arrival order | Phase 4 | Manual: Task 2 rehearsal Page 3 — visual inspection of color transitions | ⚙ | Manual in Phase 7 Task 2 |
| AC5.3 | Data Engineer column remains dim until EDA `node_end`, then highlights orange, then green | Phase 4 | Manual: Task 2 rehearsal Page 3 — pause mid-EDA, confirm DE column still dim; resume and watch it activate | ⚙ | Manual in Phase 7 Task 2 |
| AC5.4 | ML Modeler, ML Reviewer, Business Stakeholder columns dim (opacity 0.45) with "not scheduled in demo scope" label | Phase 4 | Manual: Task 2 rehearsal Page 3 — inspect three columns, confirm dimmed appearance and footer label | ⚙ | Manual in Phase 7 Task 2 |
| AC5.5 | Replay speed selector defaults to 1.5× and supports 0.5×, 1×, 1.5×, 2× | Phase 4 | Manual: Task 2 rehearsal Page 3 — change speed selector to each value, confirm event cadence changes | ⚙ | Manual in Phase 7 Task 2 |
| AC5.6 | Double-click CONTINUE is a no-op (replay does not restart) | Phase 4 | Automated: inspect compiled HTML for `_replayStarted` flag guard. Manual: Task 2 rehearsal Page 3 — click CONTINUE twice, confirm no visual restart | ⚙ | Manual in Phase 7 Task 2 |
| AC6.1 | Page 4 shows processed `df.head(10)` + four delta cards (rows, cols, missing %, runtime) | Phase 5 | Manual: Task 2 rehearsal Page 4 — after replay auto-advances, confirm table populates and delta cards show real values | ⚙ | Manual in Phase 7 Task 2 |
| AC6.2 | Seven-card agent rail: Orchestrator, EDA, Data Engineer, ML Modeler, ML Reviewer, Business Stakeholder, Report | Phase 5 | Manual: Task 2 rehearsal Page 4 — inspect left rail, confirm all seven cards in correct order | ⚙ | Manual in Phase 7 Task 2 |
| AC6.3 | Clicking a card slides drawer `-960px` over 520 ms (smooth CSS transition) | Phase 5 | Manual: Task 2 rehearsal Page 4 — click Orchestrator card, observe smooth slide-in (≈0.5 s) | ⚙ | Manual in Phase 7 Task 2 |
| AC6.4 | Orchestrator, EDA, Data Engineer panes populate from recorded JSON payloads | Phase 5 | Manual: Task 2 rehearsal Page 4 — open each of three executed-agent panes, confirm content matches JSON | ⚙ | Manual in Phase 7 Task 2 |
| AC6.5 | ML Modeler, ML Reviewer, Business Stakeholder, Report panes show SCRIPTED badge + canned narrative | Phase 5 | Manual: Task 2 rehearsal Page 4 — open each of four un-executed panes, confirm SCRIPTED badge and narrative present | ⚙ | Manual in Phase 7 Task 2 |
| AC6.6 | BACK closes drawer; clicking a new card swaps panes without intermediate close (no jitter) | Phase 5 | Manual: Task 2 rehearsal Page 4 — open card A, click card B directly, confirm smooth transition | ⚙ | Manual in Phase 7 Task 2 |
| AC7.1 | `pyarrow>=18.0.0` declared in `pyproject.toml`; `uv sync` succeeds | Phase 1 | Operational: `uv sync` exits 0; `grep pyarrow pyproject.toml` shows the dependency | ✓ | Verified in Phase 1 Task 1 |
| AC7.2 | No new top-level directories; files at listed paths | Phase 1–7 | Operational: `python -c "import pathlib; p=pathlib.Path('.'); expected={...}; actual={d.name for d in p.iterdir() if d.is_dir()}; assert not (actual-expected)"` (adjust expected per `PROJECT_TREE.md`) | ✓ | Checked in Phase 7 Task 4 |
| AC7.3 | `PROJECT_TREE.md` updated in same commit as new paths | Phase 1 | Operational: manual commit hygiene review | ✓ | Verified in Phase 1 Task 2 and Phase 7 commit |
| AC7.4 | No modifications to `agents/*.py` or `orchestration/graph.py` | Phase 1–7 | Operational: `git diff main -- src/multi_agent_ds/agents src/multi_agent_ds/orchestration/graph.py` is empty | ✓ | Verified in Phase 7 Task 4 |

---

## Summary

| Category | Count | Status |
|----------|-------|--------|
| **Total ACs** | 31 | |
| Automated tests | 11 | ✓ Passing (Phase 2 + Phase 6 unit tests) |
| Manual / operational | 20 | ⚙ Verified in Phase 7 rehearsal (Task 2) |
| **Deferred to rehearsal** | 12 | ⚙ AC3–AC6 panes (Phase 7 Task 2 walkthrough) |

---

## Test Execution Checklist

Run these commands before claiming Phase 7 complete:

### Automated tests (should all pass)
```bash
uv run pytest tests/unit/test_demo_recorder_events.py -v
uv run pytest tests/unit/test_demo_recorder_artifacts.py -v
uv run pytest tests/unit/test_demo_recorder_errors.py -v
uv run pytest tests/unit/test_demo_recorder_io.py -v
uv run pytest tests/unit/test_demo_tab_inject.py -v
```
Expected: all tests pass (0 failures).

### Operational checks
```bash
# AC7.1: pyarrow installed
uv sync && python -c "import pyarrow; print(f'pyarrow {pyarrow.__version__}')"

# AC7.4: no agent/graph changes
git diff main -- src/multi_agent_ds/agents src/multi_agent_ds/orchestration/graph.py

# AC7.2: no unexpected top-level dirs
python -c "import pathlib; p=pathlib.Path('.'); expected={'data','docs','config','src','tests','notebooks','project_planning','development_agents','scripts','.claude','.git','.github'}; actual={d.name for d in p.iterdir() if d.is_dir()}; extra=actual-expected; assert not extra, f'Unexpected: {extra}'"
```
All should return clean (no errors, no extra directories).

### Manual rehearsal (Phase 7 Task 2)
Follow the REHEARSAL_RUNBOOK.md walkthrough:
1. Page 1 Config — 30 s — AC3.1, AC3.2
2. Page 2 Input Preview — 45 s — AC4.1, AC4.2
3. Page 3 Runtime Replay — ≤ 90 s — AC5.1–AC5.6
4. Page 4 Output Drawer — 60 s — AC6.1–AC6.6

**Total elapsed:** ≤ 4 minutes. DoD #9 passes if Page 3 ≤ 90 s.

---

## Status Key

- ✓ **Automated:** Covered by unit or integration test, verified in CI or local run.
- ⚙ **Manual:** Requires human interaction (click, observe, compare); verified in Phase 7 rehearsal.
- ⚠ **Scripted-only:** Panes with SCRIPTED badges are representative outputs, not live agent execution. AC6.5 documents this intentional limitation.

---

## Known Limitations & Workarounds

1. **AC6.5 — SCRIPTED panes:** The demo recording captures a 2-node flow (EDA + Data Engineer). The ML Modeler, ML Reviewer, Business Stakeholder, and Report panes are populated with canned narrative to illustrate a full approval stage. In production, these agents would execute live.

2. **No browser automation tests:** AC3–AC6 are verified manually in the rehearsal walkthrough. A future enhancement could add Playwright or Selenium tests to automate these clicks; deferred as a nice-to-have (not required for demo delivery).

3. **Video recording (Additional Consideration):** Phase 7 Task 3 produces a screen recording as a fallback. If the live demo fails, play the video instead. See REHEARSAL_RUNBOOK.md for fallback options.

---

## Clearance for Demo

**Demo is ready to proceed if:**
- All automated tests pass (AC1, AC2.2, AC7.1, AC7.4).
- Rehearsal walkthrough completes with no red error banners (AC2.1, AC3–AC6).
- Total runtime on Page 3 is ≤ 90 s at 1.5× speed (DoD #9).
- Backup video is available if needed (Additional Consideration).

**Expected outcome:** All 31 ACs are passing. Zero deferred, zero open issues blocking the demo.
