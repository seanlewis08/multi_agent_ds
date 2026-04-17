# Project Tree — multi_agent_ds

_Last updated: 2026-04-16 (added demo_viewer.html, demo_recorder.py, demo_viewer_loader.py, design_plans/, implementation_plans/)_

Captured: 2026-04-16

```
├── LICENSE
├── README.md
├── config
│   ├── agents.yaml
│   ├── prompts.yaml
│   ├── settings.yaml
│   └── workflows.yaml
├── data
│   ├── external
│   ├── interim
│   ├── processed
│   └── raw
├── notebooks
├── project_planning
│   ├── design_plans
│   ├── implementation_plans
│   ├── Multi_Agent_Framework_Research_Paper.docx
│   └── Multi_Agent_Framework_Technical_Brief.docx
├── pyproject.toml
├── src
│   └── multi_agent_ds
│       ├── __init__.py
│       ├── adapters
│       │   ├── __init__.py
│       │   ├── agent_frameworks
│       │   │   ├── __init__.py
│       │   │   ├── crewai.py
│       │   │   └── langgraph.py
│       │   └── llm
│       │       ├── __init__.py
│       │       ├── local.py
│       │       ├── openai.py
│       │       └── routing.py
│       ├── agents
│       │   ├── __init__.py
│       │   ├── business_stakeholder.py
│       │   ├── data_engineer.py
│       │   ├── eda_analyst.py
│       │   ├── ml_modeler.py
│       │   ├── ml_reviewer.py
│       │   ├── orchestrator.py
│       │   └── report_writer.py
│       ├── app.py
│       ├── demo_viewer.html (planned)
│       ├── core
│       │   ├── __init__.py
│       │   ├── context.py
│       │   ├── contracts.py
│       │   └── registry.py
│       ├── orchestration
│       │   ├── __init__.py
│       │   ├── demo_recorder.py (planned)
│       │   ├── demo_viewer_loader.py (planned)
│       │   ├── graph.py
│       │   ├── router.py
│       │   └── state.py
│       ├── skills
│       │   ├── __init__.py
│       │   ├── cleaning.py
│       │   ├── feature_engineering.py
│       │   ├── modeling.py
│       │   └── profiling.py
│       ├── tools
│       │   ├── __init__.py
│       │   ├── dataframes.py
│       │   ├── evaluation.py
│       │   ├── io.py
│       │   └── reporting.py
│       └── workflows
│           ├── __init__.py
│           ├── discovery.py
│           ├── evaluation.py
│           ├── modeling.py
│           └── preparation.py
├── tests
│   ├── conftest.py
│   ├── fixtures
│   ├── integration
│   └── unit
└── uv.lock
```
