# Test Requirements — Demo Runtime Viewer

**Derived from:** `project_planning/design_plans/2026-04-16-demo-runtime-viewer.md`
**Implementation plan:** `project_planning/implementation_plans/2026-04-16-demo-runtime-viewer/`
**Generated:** 2026-04-16

This document maps every acceptance criterion from the design plan to a concrete verification method and the implementation phase responsible for producing that verification.

Three verification categories are used:

- **Automated** — a pytest or Python sanity script asserting the criterion programmatically. Runs in CI or via `uv run pytest ...`.
- **Operational** — a shell command (uv sync, file existence, git diff) with a deterministic pass/fail.
- **Manual** — a human-driven check against the running viewer (visual confirmation, click interaction). Captured in the Phase 7 rehearsal checklist.

An AC case may have more than one verification (e.g., an automated test plus a visual confirmation at rehearsal).

---

## AC1: Recording

| AC | Phase | Category | Verification |
|----|-------|----------|--------------|
| AC1.1 Success — required `node_start`/`node_end` events for `eda_raw` and `data_engineer` | Phase 2 Task 1 + Task 8 | Automated | `tests/unit/test_demo_recorder_events.py::test_should_record_node_events` (event-shape predicate) + Phase 7 Task 1 sanity script asserting the four required events exist in `data/interim/demo_run_latest.json` |
| AC1.2 Success — `artifacts.raw_eda_insights`, `artifacts.prep_plan`, `artifacts.processed_df_head` populated | Phase 2 Task 2 + Task 6 + Task 8 | Automated | `tests/unit/test_demo_recorder_artifacts.py::test_extract_artifacts_populates_all_keys` + Phase 7 Task 1 assertion `for key in required_artifacts: assert key in arts` |
| AC1.3 Success — every event has `ts` and `elapsed_ms` | Phase 2 Task 3 + Task 8 | Automated | `tests/unit/test_demo_recorder_events.py::test_event_has_ts_and_elapsed_ms` + Phase 7 Task 1 assertion iterating events |
| AC1.4 Failure — missing parquet raises `FileNotFoundError` naming the path | Phase 2 Task 5 | Automated | `tests/unit/test_demo_recorder_errors.py::test_missing_parquet_raises` |
| AC1.5 Failure — missing `OPENAI_API_KEY` raises `EnvironmentError` before invoking graph | Phase 2 Task 5 | Automated | `tests/unit/test_demo_recorder_errors.py::test_missing_openai_key_raises` with `monkeypatch.delenv` |
| AC1.6 Edge — atomic `.tmp` + `os.replace` rewrite | Phase 2 Task 5 | Automated | `tests/unit/test_demo_recorder_io.py::test_atomic_write_leaves_no_partial` |

## AC2: Streamlit integration

| AC | Phase | Category | Verification |
|----|-------|----------|--------------|
| AC2.1 Success — viewer renders via `st.components.v1.html(..., height=820, scrolling=False)` | Phase 6 Task 2 | Manual | Phase 7 rehearsal checklist item 3 — open the app, switch to the Demo tab, confirm viewer iframe height and no scrollbar |
| AC2.2 Success — reads `demo_run_latest.json`, injects as string literal | Phase 6 Task 1 | Automated | `tests/unit/test_demo_tab_inject.py::test_inject_demo_log_embeds_json` + `test_inject_escapes_closing_script_tag` (defense-in-depth for `</script>` content) |
| AC2.3 Failure — missing JSON renders error with exact re-record command | Phase 6 Task 2 | Manual | Phase 7 rehearsal checklist item 2 — temporarily rename `demo_run_latest.json`, open Demo tab, confirm error message cites `uv run python -m multi_agent_ds.orchestration.demo_recorder --output data/interim/demo_run_latest.json` |

**Note on AC2.1:** design plan reads "sidebar mode option"; Phase 6 implements this as a fourth `tab_demo` in the existing `st.tabs([...])` layout at `app.py:452`. This interpretation was flagged in the Phase 6 commit message and is equivalent in user-observable behavior.

## AC3: Config screen

| AC | Phase | Category | Verification |
|----|-------|----------|--------------|
| AC3.1 Success — source path, target, rows × cols, positive rate, scale, max_trials, cv_folds, timeout, algorithms, review settings shown | Phase 3 Task 2 + Task 4 | Manual | Phase 3 Task 4 Step 1 — open viewer with real recorded JSON, confirm every card in the Config section is populated against values in `config/settings.yaml`. `review_enabled` / `review_threshold` render `—` (no review block exists in settings). |
| AC3.2 Success — RUN button transitions to Input Preview | Phase 3 Task 2 | Manual | Phase 3 Task 4 Step 2 — click RUN, confirm Page 2 (`data-page="input"`) becomes visible |

## AC4: Input Preview screen

| AC | Phase | Category | Verification |
|----|-------|----------|--------------|
| AC4.1 Success — `df.head(10)` plus pill strip (rows, cols, target, positive rate, numeric count, categorical count, missing pct) | Phase 3 Task 3 + Phase 2 Task 6 (`_compute_input_stats`) | Automated + Manual | Automated: `tests/unit/test_demo_recorder_artifacts.py::test_compute_input_stats_fields` asserts all pill-strip fields are computed. Manual: Phase 3 Task 4 Step 3 visual pass. |
| AC4.2 Success — CONTINUE transitions to Runtime and starts replay | Phase 3 Task 3 + Phase 4 Task 2 | Manual | Phase 7 rehearsal checklist item 5 — click CONTINUE, confirm Page 3 visible, orchestrator band transitions STARTING → EDA RUNNING |

## AC5: Runtime animation

| AC | Phase | Category | Verification |
|----|-------|----------|--------------|
| AC5.1 Success — orchestrator shows `STARTING`, `EDA RUNNING`, `HANDOFF`, `DATA ENGINEER RUNNING`, `COMPLETE` | Phase 4 Task 2 + Task 3 | Manual | Phase 4 Task 3 Step 1 — play the replay at `2x`, confirm all five labels appear in order |
| AC5.2 Success — EDA column highlights orange between its events, then locks green; lanes populate in arrival order | Phase 4 Task 2 + Task 3 | Manual | Phase 4 Task 3 Step 2 — visual pass; lane labels are cosmetic (documented in `_laneItemsFor` comment), but the .col state transitions must be correct |
| AC5.3 Success — Data Engineer activates only after EDA `node_end` | Phase 4 Task 2 + Task 3 | Manual | Phase 4 Task 3 Step 3 — pause replay mid-EDA, confirm DE column remains dim until EDA locks green |
| AC5.4 Success — ML Modeler/Reviewer/Biz Stakeholder dim + "not scheduled in demo scope" label | Phase 4 Task 1 | Manual | Phase 4 Task 3 Step 4 — inspect Page 3, confirm three columns carry `opacity: 0.45` and the muted footer label |
| AC5.5 Success — replay speed selector `0.5x / 1x / 1.5x / 2x`, default `1.5x` | Phase 4 Task 2 | Manual | Phase 4 Task 3 Step 5 — change selector to each value, confirm event cadence changes proportionally |
| AC5.6 Failure — double-click CONTINUE is a no-op | Phase 4 Task 2 (`_replayStarted` guard) | Automated + Manual | Automated: inspect the compiled viewer HTML for `_replayStarted` flag presence (grep check in Phase 4 Task 3). Manual: click CONTINUE twice, confirm no visual restart. |

## AC6: Output & Summary drawer

| AC | Phase | Category | Verification |
|----|-------|----------|--------------|
| AC6.1 Success — Page 4 shows processed `df.head(10)` + four delta cards | Phase 5 Task 1 + Task 2 | Manual | Phase 5 Task 3 Step 1 — after replay completes and auto-advances to summary, confirm processed table populates and four delta cards show real values (ROC-AUC = `n/a`, features/missing/runtime from real data) |
| AC6.2 Success — seven-card agent rail (Orch, EDA, DE, MLM, MLR, Biz, Report) | Phase 5 Task 1 | Manual | Phase 5 Task 3 Step 2 — inspect rail, confirm all seven cards present in order |
| AC6.3 Success — click card → slider translates `-960px` over 520ms | Phase 5 Task 1 + Task 2 | Manual | Phase 5 Task 3 Step 3 — click Orchestrator card, measure transition timing visually (should be smooth, ~half-second) |
| AC6.4 Success — Orch/EDA/DE panes populate from recorded JSON | Phase 5 Task 2 (`_renderOrchPane`, `_renderEdaPane`, `_renderDePane`) | Manual | Phase 5 Task 3 Step 4 — open each of the three executed-agent panes, confirm payloads match `data/interim/demo_run_latest.json` |
| AC6.5 Success — MLM/MLR/Biz/Report panes show SCRIPTED badge + canned content | Phase 5 Task 1 (`DEMO_CANNED` constant) | Manual | Phase 5 Task 3 Step 5 — open each of the four un-executed panes, confirm SCRIPTED badge visible and rail subtitle suffix `(scripted)` present |
| AC6.6 Success — BACK closes drawer; new-card click swaps panes without intermediate close | Phase 5 Task 2 | Manual | Phase 5 Task 3 Step 6 — click card A, then click card B directly; confirm no transition-jitter to closed state |

## AC7: Repo hygiene

| AC | Phase | Category | Verification |
|----|-------|----------|--------------|
| AC7.1 Success — `pyarrow>=18.0.0` in pyproject; `uv sync` succeeds | Phase 1 Task 1 | Operational | `uv sync` exits 0; `grep -q "pyarrow>=18.0.0" pyproject.toml` |
| AC7.2 Success — no new top-level directories; files at the listed paths | Phase 1 Task 2 + Phase 6 Task 1 | Operational | Phase 7 Task 4 matrix row — `uv run python -c "import pathlib; p=pathlib.Path('.'); expected={'data','docs','config','src','tests','notebooks','project_planning','development_agents','scripts','.claude','.git','.github'}; actual={d.name for d in p.iterdir() if d.is_dir()}; extra=actual-expected; assert not extra"` (adjust `expected` to match the actual set at execution time per `PROJECT_TREE.md`) |
| AC7.3 Success — PROJECT_TREE.md updated in the same commit as new paths | Phase 1 Task 2 | Operational | Manual commit hygiene; reviewed during Phase 1 commit step |
| AC7.4 Success — no modifications to `agents/*.py` or `orchestration/graph.py` | Phases 1–7 | Operational | Phase 7 Task 4 matrix row — `git diff main -- src/multi_agent_ds/agents src/multi_agent_ds/orchestration/graph.py` must be empty. Confirm `main` is the real base branch (run `git branch --show-current` and `git merge-base HEAD main`) before relying on this command. |

---

## DoD #9 — Rehearsal timing

**Not an AC.** The design plan's Definition of Done #9 requires the live demo from clicking RUN to the final panel to complete in under 90 seconds at `1.5x` replay speed.

| Phase | Category | Verification |
|-------|----------|--------------|
| Phase 7 Task 2 | Manual | End-to-end rehearsal with stopwatch; pass/fail at 90 s |

## Additional Consideration — Backup video

**Not an AC.** Design plan line 276 recommends a backup screen recording in case the live demo fails.

| Phase | Category | Verification |
|-------|----------|--------------|
| Phase 7 Task 3 | Manual | Screen recording produced; executor chooses checked-in vs local-only location per user direction |

---

## Test file inventory

Expected test files (created during phases 2 and 6):

```
tests/unit/
├── test_demo_recorder_events.py      # AC1.1, AC1.3
├── test_demo_recorder_artifacts.py   # AC1.2, AC4.1
├── test_demo_recorder_errors.py      # AC1.4, AC1.5
├── test_demo_recorder_io.py          # AC1.6
└── test_demo_tab_inject.py           # AC2.2 (includes XSS escape case)
```

Viewer-side behavior (AC3–AC6) is verified via manual rehearsal in Phases 3–5 Task 3/4 steps rather than headless-browser tests. A future enhancement could add Playwright coverage for AC5/AC6 click paths; captured as follow-up, not required for the demo deliverable.

## Execution-time checklist

When the executor finishes all seven phases, run this single-pass check before declaring the plan complete:

1. `uv sync` — AC7.1
2. `uv run pytest tests/unit/test_demo_*.py -v` — AC1, AC2.2
3. `uv run python -m multi_agent_ds.orchestration.demo_recorder --output data/interim/demo_run_latest.json` — produces recording
4. `uv run python -c "<sanity script from phase_07.md Task 1>"` — AC1 artifact assertions
5. `uv run streamlit run src/multi_agent_ds/app.py` — manual rehearsal for AC2–AC6
6. Stopwatch the rehearsal — DoD #9
7. Record backup video — Additional Consideration
8. `git diff main -- src/multi_agent_ds/agents src/multi_agent_ds/orchestration/graph.py` returns empty — AC7.4
9. Top-level directory set check — AC7.2
10. Spot-check `PROJECT_TREE.md` committed alongside new paths — AC7.3

All ten items must pass for the implementation plan to be considered complete.
