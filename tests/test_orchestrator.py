from __future__ import annotations

from multi_agent_ds.core import load_agents_config, load_workflows_config
from multi_agent_ds.agents.orchestrator import orchestrator_node


def test_orchestrator_node_returns_workflow_entry_decision() -> None:
    state = {
        "settings": {"data": {"source": "existing"}},
        "data_path": "s3://bucket/data/raw/input.parquet",
        "workflow_config": {
            "workflows": {
                "full_pipeline": {
                    "steps": ["eda_raw", "ml_modeler_raw_review"],
                }
            }
        },
    }

    result = orchestrator_node(state)

    assert result["selected_workflow"] == "full_pipeline"
    assert result["entry_node"] == "eda_raw"
    assert result["modeler_variant"] == "sean"
    assert result["downstream_sequence"] == []
    assert result["decision_type"] == "workflow_entry"
    assert result["status"] == "ready"
    assert result["next_agent"] == "eda_raw"
    assert result["loop_from"] is None
    assert result["should_loop"] is False
    assert result["blocked_on"] is None
    assert result["blocked_reason"] is None
    assert result["current_phase"] == "orchestrator"
    assert result["workflow_config"] == state["workflow_config"]
    assert result["agent_decisions"][-1] == {
        "agent": "orchestrator",
        "phase": "workflow_entry",
        "selected_workflow": "full_pipeline",
        "entry_node": "eda_raw",
        "modeler_variant": "sean",
        "downstream_sequence": [],
    }


def test_orchestrator_node_supports_dict_step_workflow_entry() -> None:
    state = {
        "settings": {"data": {"source": "existing"}},
        "data_path": "s3://bucket/data/raw/input.parquet",
        "workflow_config": {
            "workflows": {
                "full_pipeline": {
                    "steps": [
                        {"agent": "eda_raw", "required": True},
                        {"agent": "ml_modeler_raw_review", "required": True},
                    ],
                }
            }
        },
    }

    result = orchestrator_node(state)

    assert result["entry_node"] == "eda_raw"
    assert result["next_agent"] == "eda_raw"


def test_orchestrator_node_prefers_explicit_workflow_entry_node() -> None:
    state = {
        "settings": {"data": {"source": "existing"}},
        "data_path": "s3://bucket/data/raw/input.parquet",
        "workflow_config": {
            "workflows": {
                "full_pipeline": {
                    "entry_node": "ml_modeler_handoff",
                    "steps": ["eda_raw", "ml_modeler_raw_review"],
                }
            }
        },
    }

    result = orchestrator_node(state)

    assert result["entry_node"] == "ml_modeler_handoff"
    assert result["next_agent"] == "ml_modeler_handoff"


def test_orchestrator_node_chooses_baseline_only_for_synthetic_data() -> None:
    state = {
        "settings": {"data": {"source": "synthetic"}},
        "data_path": "s3://bucket/data/raw/input.parquet",
        "workflow_config": {
            "workflows": {
                "full_pipeline": {
                    "entry_node": "eda_raw",
                    "steps": ["eda_raw"],
                },
                "baseline_only": {
                    "entry_node": "ml_modeler_handoff",
                    "steps": ["ml_modeler_handoff"],
                },
            }
        },
    }

    result = orchestrator_node(state)

    assert result["selected_workflow"] == "baseline_only"
    assert result["entry_node"] == "ml_modeler_handoff"
    assert result["modeler_variant"] == "sean"
    assert result["next_agent"] == "ml_modeler_handoff"


def test_orchestrator_node_falls_back_to_full_pipeline_when_source_hint_is_missing() -> None:
    state = {
        "settings": {"data": {}},
        "data_path": "s3://bucket/data/raw/input.parquet",
        "workflow_config": {
            "workflows": {
                "full_pipeline": {
                    "entry_node": "eda_raw",
                    "steps": ["eda_raw"],
                },
                "baseline_only": {
                    "entry_node": "ml_modeler_handoff",
                    "steps": ["ml_modeler_handoff"],
                },
            }
        },
    }

    result = orchestrator_node(state)

    assert result["selected_workflow"] == "full_pipeline"
    assert result["entry_node"] == "eda_raw"
    assert result["next_agent"] == "eda_raw"


def test_orchestrator_node_falls_back_to_full_pipeline_when_baseline_only_is_unavailable() -> None:
    state = {
        "settings": {"data": {"source": "synthetic"}},
        "data_path": "s3://bucket/data/raw/input.parquet",
        "workflow_config": {
            "workflows": {
                "full_pipeline": {
                    "entry_node": "eda_raw",
                    "steps": ["eda_raw"],
                }
            }
        },
    }

    result = orchestrator_node(state)

    assert result["selected_workflow"] == "full_pipeline"
    assert result["entry_node"] == "eda_raw"
    assert result["next_agent"] == "eda_raw"


def test_orchestrator_node_uses_state_override_for_modeler_variant() -> None:
    state = {
        "settings": {"data": {"source": "existing"}},
        "data_path": "s3://bucket/data/raw/input.parquet",
        "modeler_variant": "jonathan",
        "agents_config": {
            "agents": {
                "ml_modeler": {
                    "active_variant": "sean",
                    "supported_variants": ["sean", "jonathan"],
                }
            }
        },
        "workflow_config": {
            "workflows": {
                "full_pipeline": {
                    "entry_node": "eda_raw",
                    "steps": ["eda_raw"],
                    "post_model_sequence": ["evaluation", "reviewer", "report"],
                }
            }
        },
    }

    result = orchestrator_node(state)

    assert result["modeler_variant"] == "jonathan"
    assert result["downstream_sequence"] == ["evaluation", "reviewer", "report"]


def test_orchestrator_node_uses_agents_config_for_modeler_variant_when_no_override_exists() -> None:
    state = {
        "settings": {"data": {"source": "existing"}},
        "data_path": "s3://bucket/data/raw/input.parquet",
        "agents_config": {
            "agents": {
                "ml_modeler": {
                    "active_variant": "jonathan",
                    "supported_variants": ["sean", "jonathan"],
                }
            }
        },
        "workflow_config": {
            "workflows": {
                "full_pipeline": {
                    "entry_node": "eda_raw",
                    "steps": ["eda_raw"],
                    "post_model_sequence": ["evaluation", "reviewer"],
                }
            }
        },
    }

    result = orchestrator_node(state)

    assert result["modeler_variant"] == "jonathan"
    assert result["downstream_sequence"] == ["evaluation", "reviewer"]


def test_orchestrator_node_defers_when_current_phase_is_graph_owned() -> None:
    state = {
        "settings": {"data": {"source": "existing"}},
        "data_path": "s3://bucket/data/raw/input.parquet",
        "current_phase": "baseline",
    }

    result = orchestrator_node(state)

    assert result["decision_type"] == "downstream_route"
    assert result["status"] == "ready"
    assert result["next_agent"] is None
    assert result["should_loop"] is False
    assert result["blocked_on"] is None
    assert "graph/router flow" in result["decision_summary"]


def test_orchestrator_node_blocks_post_modeling_evaluation_gap() -> None:
    state = {
        "settings": {"data": {"source": "existing"}},
        "data_path": "s3://bucket/data/raw/input.parquet",
        "current_phase": "final_recommendation",
        "modeling_verdict": {"winner": "lightgbm"},
    }

    result = orchestrator_node(state)

    assert result["decision_type"] == "downstream_route"
    assert result["status"] == "blocked"
    assert result["next_agent"] == "evaluation"
    assert result["modeler_variant"] == "sean"
    assert result["downstream_sequence"] == [
        "evaluation",
        "reviewer",
        "report",
        "business_stakeholder_report_review",
    ]
    assert result["blocked_on"] == "evaluation_graph_wiring"
    assert "evaluation workflow" in result["blocked_reason"]
    assert result["should_loop"] is False


def test_orchestrator_node_blocks_post_evaluation_reviewer_gap() -> None:
    state = {
        "settings": {"data": {"source": "existing"}},
        "data_path": "s3://bucket/data/raw/input.parquet",
        "current_phase": "evaluation",
        "evaluation_result": {"winner": "lightgbm"},
    }

    result = orchestrator_node(state)

    assert result["status"] == "blocked"
    assert result["next_agent"] == "reviewer"
    assert result["downstream_sequence"] == [
        "evaluation",
        "reviewer",
        "report",
        "business_stakeholder_report_review",
    ]
    assert result["blocked_on"] == "reviewer_graph_wiring"
    assert "reviewer agent" in result["blocked_reason"]


def test_orchestrator_node_loops_back_after_flat_evaluation_improvement() -> None:
    state = {
        "settings": {
            "data": {"source": "existing"},
            "model": {"tuning": {"min_improvement": 0.01}},
        },
        "data_path": "s3://bucket/data/raw/input.parquet",
        "current_phase": "evaluation",
        "iteration": 1,
        "evaluation_result": {
            "winner": "lightgbm",
            "improvement": 0.004,
        },
    }

    result = orchestrator_node(state)

    assert result["status"] == "blocked"
    assert result["next_agent"] == "ml_modeler_baseline"
    assert result["should_loop"] is True
    assert result["loop_from"] == "ml_modeler_baseline"
    assert result["blocked_on"] == "post_evaluation_loop_wiring"
    assert result["stop_reason"] is None
    assert result["iteration"] == 1
    assert result["max_iterations"] == 5


def test_orchestrator_node_stops_looping_when_improvement_threshold_is_met() -> None:
    state = {
        "settings": {
            "data": {"source": "existing"},
            "model": {"tuning": {"min_improvement": 0.01}},
        },
        "data_path": "s3://bucket/data/raw/input.parquet",
        "current_phase": "evaluation",
        "iteration": 1,
        "evaluation_result": {
            "winner": "lightgbm",
            "improvement": 0.02,
        },
    }

    result = orchestrator_node(state)

    assert result["status"] == "blocked"
    assert result["next_agent"] == "reviewer"
    assert result["should_loop"] is False
    assert result["blocked_on"] == "reviewer_graph_wiring"
    assert result["stop_reason"] == "improvement_threshold_met"


def test_orchestrator_node_stops_looping_at_iteration_cap_even_when_score_is_flat() -> None:
    state = {
        "settings": {
            "data": {"source": "existing"},
            "model": {
                "max_iterations": 5,
                "tuning": {"min_improvement": 0.01},
            },
        },
        "data_path": "s3://bucket/data/raw/input.parquet",
        "current_phase": "evaluation",
        "iteration": 5,
        "evaluation_result": {
            "winner": "lightgbm",
            "improvement": 0.0,
        },
    }

    result = orchestrator_node(state)

    assert result["status"] == "blocked"
    assert result["next_agent"] == "reviewer"
    assert result["should_loop"] is False
    assert result["blocked_on"] == "reviewer_graph_wiring"
    assert result["stop_reason"] == "max_iterations_reached"
    assert result["iteration"] == 5
    assert result["max_iterations"] == 5


def test_orchestrator_node_defaults_to_stop_when_prior_improvement_context_is_missing() -> None:
    state = {
        "settings": {"data": {"source": "existing"}},
        "data_path": "s3://bucket/data/raw/input.parquet",
        "current_phase": "evaluation",
        "iteration": 1,
        "evaluation_result": {
            "winner": "lightgbm",
        },
    }

    result = orchestrator_node(state)

    assert result["status"] == "blocked"
    assert result["next_agent"] == "reviewer"
    assert result["should_loop"] is False
    assert result["blocked_on"] == "reviewer_graph_wiring"
    assert result["stop_reason"] == "prior_context_missing"


def test_orchestrator_node_blocks_report_review_gap_after_report_generation() -> None:
    state = {
        "settings": {"data": {"source": "existing"}},
        "data_path": "s3://bucket/data/raw/input.parquet",
        "current_phase": "report_generate",
        "experiment_report": "# Report\n\nDone.",
    }

    result = orchestrator_node(state)

    assert result["status"] == "blocked"
    assert result["next_agent"] == "business_stakeholder_report_review"
    assert result["blocked_on"] == "report_review_graph_wiring"
    assert "report_review" in result["blocked_reason"]


def test_orchestrator_node_loops_back_when_business_review_requests_report_revision() -> None:
    state = {
        "settings": {"data": {"source": "existing"}},
        "data_path": "s3://bucket/data/raw/input.parquet",
        "current_phase": "report_review",
        "business_review": {"next_action": "revise_report"},
        "should_revise_report": True,
        "report_iteration": 1,
    }

    result = orchestrator_node(state)

    assert result["status"] == "blocked"
    assert result["next_agent"] == "report_writer"
    assert result["should_loop"] is True
    assert result["loop_from"] == "report_writer"
    assert result["blocked_on"] == "report_review_graph_wiring"


def test_orchestrator_node_stops_when_business_review_accepts_report() -> None:
    state = {
        "settings": {"data": {"source": "existing"}},
        "data_path": "s3://bucket/data/raw/input.parquet",
        "current_phase": "report_review",
        "business_review": {"next_action": "accept"},
    }

    result = orchestrator_node(state)

    assert result["status"] == "ready"
    assert result["next_agent"] is None
    assert result["stop_reason"] == "business_review_accepted"
    assert result["should_loop"] is False


def test_agents_config_exposes_orchestrator_facing_metadata() -> None:
    agents = load_agents_config()["agents"]

    assert agents["ml_modeler"]["active_variant"] == "sean"
    assert agents["ml_modeler"]["supported_variants"] == ["sean", "jonathan"]
    assert agents["reviewer"]["runtime_node"] == "reviewer"
    assert agents["report"]["runtime_node"] == "report_writer"
    assert agents["orchestrator"]["max_iterations"] == 5
    assert "evaluation" not in agents


def test_workflows_config_exposes_orchestrator_facing_workflow_metadata() -> None:
    workflows = load_workflows_config()["workflows"]

    assert workflows["full_pipeline"]["entry_node"] == "eda_raw"
    assert workflows["full_pipeline"]["steps"][-1] == "ml_modeler_handoff"
    assert workflows["full_pipeline"]["post_model_sequence"] == [
        "evaluation",
        "reviewer",
        "report",
        "business_stakeholder_report_review",
    ]
    assert workflows["baseline_only"]["entry_node"] == "ml_modeler_handoff"
    assert workflows["baseline_only"]["steps"] == ["ml_modeler_handoff"]
    assert workflows["baseline_only"]["post_model_sequence"] == [
        "evaluation",
        "reviewer",
        "report",
        "business_stakeholder_report_review",
    ]
    assert workflows["modeling"]["max_iterations"] == 3
    assert workflows["report"]["max_iterations"] == 2
