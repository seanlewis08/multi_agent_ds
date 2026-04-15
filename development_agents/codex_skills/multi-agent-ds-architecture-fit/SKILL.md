---
name: "Architecture Fit"
description: Choose correct code placement and layer ownership in the multi_agent_ds repository. Use when deciding where new code should live, whether to create a new file, whether logic belongs in core/tools/skills/workflows/agents/orchestration/adapters, or whether import direction matches the planned architecture.
---

# Architecture Fit

Use this skill when deciding where code belongs.

## Placement Rules

- Keep import direction `orchestration -> workflows -> agents -> skills -> tools`.
- Put pure reusable helpers in `tools/`.
- Put domain logic that combines helpers in `skills/`.
- Put end-to-end pipelines and side effects in `workflows/`.
- Put LLM decision logic in `agents/`.
- Put graph state and routing in `orchestration/`.
- Put provider abstractions in `adapters/`.
- Put shared config, contracts, and registries in `core/`.

## File Decision Rules

- Prefer the existing file that already owns the concern.
- If no existing file is right, prefer the nearest planned file in the same layer.
- Use `project_planning/PROJECT_TREE.md` as the baseline for which paths originally belonged to the repo before accepting a new file location.
- Do not add a new top-level pattern when the planning docs already define the layer map.
- Treat scripts, notebooks, and one-off helpers as last resorts that require explicit approval, especially when they do not appear in `PROJECT_TREE.md`.

## Purity Rules

- `skills/` should not do file I/O, MLflow logging, or LLM calls.
- `tools/` should stay stateless and reusable.
- Side effects belong in workflows, adapters, or explicit utility modules already meant for that purpose.
