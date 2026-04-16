"""Experiment PR reviewer agent placeholder for Jonathan's workflow."""

from __future__ import annotations

import json
import re
from datetime import date

from multi_agent_ds.adapters.llm.openai import OpenAIAdapter
from multi_agent_ds.core.config import load_settings
from multi_agent_ds.orchestration.state import PipelineState
from multi_agent_ds.tools import git as git_tools


def _build_pr_description(review_context: dict[str, object], settings: dict[str, object]) -> str:
    """Generate a PR description from experiment context through the OpenAI adapter."""

    adapter = OpenAIAdapter(settings)
    response = adapter.chat(
        [
            {
                "role": "system",
                "content": (
                    "You write GitHub pull request descriptions for machine learning "
                    "experiment runs. Include what was tested, why, the results, "
                    "key decisions, and config changes."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Generate a pull request description from this experiment context:\n"
                    f"{json.dumps(review_context, indent=2, default=str)}"
                ),
            },
        ]
    )
    return response["content"].strip()


def _derive_branch_name(review_context: dict[str, object]) -> str:
    """Derive a conservative experiment branch name from the review context."""

    candidates = [
        review_context.get("evaluation_result"),
        review_context.get("modeling_results"),
        review_context.get("current_phase"),
    ]
    summary_source = next((candidate for candidate in candidates if candidate), "run")

    if isinstance(summary_source, dict):
        summary_source = (
            summary_source.get("winner")
            or summary_source.get("model_name")
            or summary_source.get("best_model")
            or summary_source.get("status")
            or "run"
        )

    summary = re.sub(r"[^a-z0-9]+", "-", str(summary_source).lower()).strip("-")
    if not summary:
        summary = "run"

    today = date.today().isoformat()
    return f"experiment/{summary}-{today}"


def _select_stage_paths(review_context: dict[str, object]) -> list[str]:
    """Select the explicit paths that should be staged for the reviewer commit."""

    stage_paths = ["config/settings.yaml"]
    log_path = review_context.get("experiment_log_path") or review_context.get("report_path")
    if isinstance(log_path, str) and log_path not in stage_paths:
        stage_paths.append(log_path)

    extra_paths = review_context.get("config_files", [])
    if isinstance(extra_paths, list):
        for path in extra_paths:
            if isinstance(path, str) and path not in stage_paths:
                stage_paths.append(path)
    return stage_paths


def _build_commit_message(review_context: dict[str, object]) -> str:
    """Build a concise experiment-focused commit message."""

    candidates = [
        review_context.get("evaluation_result"),
        review_context.get("modeling_results"),
        review_context.get("current_phase"),
    ]
    summary_source = next((candidate for candidate in candidates if candidate), "run")

    if isinstance(summary_source, dict):
        summary_source = (
            summary_source.get("winner")
            or summary_source.get("model_name")
            or summary_source.get("best_model")
            or summary_source.get("status")
            or "run"
        )

    summary = re.sub(r"[^a-z0-9]+", "-", str(summary_source).lower()).strip("-")
    if not summary:
        summary = "run"

    return f"[experiment] document {summary} cycle (config snapshot, experiment log)"


def _build_pull_request_title(review_context: dict[str, object]) -> str:
    """Build a concise PR title from the experiment context."""

    candidates = [
        review_context.get("evaluation_result"),
        review_context.get("modeling_results"),
        review_context.get("current_phase"),
    ]
    summary_source = next((candidate for candidate in candidates if candidate), "run")

    if isinstance(summary_source, dict):
        summary_source = (
            summary_source.get("winner")
            or summary_source.get("model_name")
            or summary_source.get("best_model")
            or summary_source.get("status")
            or "run"
        )

    summary = re.sub(r"[^a-z0-9]+", " ", str(summary_source).lower()).strip()
    if not summary:
        summary = "run"
    return f"Experiment: {summary}"


def reviewer_node(state: PipelineState) -> dict:
    """Placeholder reviewer node for the experiment PR flow.

    Expected inputs:
    - experiment context from orchestration state, including evaluation_result,
      report_draft, experiment_report, agent_decisions, current_phase,
      should_loop, and iteration when available
    - config-derived settings for future branch and PR naming decisions
    - a PipelineState mapping that may omit optional fields during early runs

    Returned data shape:
    - for now, the node passes PipelineState through unchanged
    - later orchestration use should be able to layer in PR metadata such as
      branch_name, commit_sha, pr_number, and pr_url without changing the node
      boundary
    """
    settings = state.get("settings") or load_settings()
    dry_run = bool(state.get("dry_run", False))
    review_context = {
        "data_path": state.get("data_path"),
        "modeling_results": state.get("modeling_results"),
        "evaluation_result": state.get("evaluation_result"),
        "agent_decisions": state.get("agent_decisions", []),
        "current_phase": state.get("current_phase"),
        "should_loop": state.get("should_loop"),
        "iteration": state.get("iteration"),
        "report_draft": state.get("report_draft"),
        "experiment_report": state.get("experiment_report"),
        "experiment_log_path": state.get("experiment_log_path"),
        "report_path": state.get("report_path"),
        "business_review": state.get("business_review"),
        "settings": settings,
    }
    branch_name = _derive_branch_name(review_context)
    stage_paths = _select_stage_paths(review_context)
    commit_message = _build_commit_message(review_context)
    pr_description = _build_pr_description(review_context, settings)
    pr_title = _build_pull_request_title(review_context)
    git_settings = settings.get("git", {}) if isinstance(settings, dict) else {}
    base_branch = git_settings.get("default_base_branch", "main") if isinstance(git_settings, dict) else "main"

    result = dict(state)
    result.update(
        {
            "branch_name": branch_name,
            "staged_paths": stage_paths,
            "commit_message": commit_message,
            "pr_title": pr_title,
            "pr_body": pr_description,
            "base_branch": str(base_branch),
        }
    )

    if dry_run:
        result.update(
            {
                "dry_run": True,
                "commit_sha": None,
                "pr_metadata": {
                    "title": pr_title,
                    "body": pr_description,
                    "base": str(base_branch),
                    "head": branch_name,
                    "draft": False,
                },
                "pr_number": None,
                "pr_url": None,
            }
        )
        return result

    git_tools.create_branch(branch_name)
    git_tools.stage_files(stage_paths)
    commit_sha = git_tools.commit(commit_message)
    git_tools.push_branch(branch_name)
    pr_metadata = git_tools.create_pull_request(
        title=pr_title,
        body=pr_description,
        base=str(base_branch),
        head=branch_name,
    )
    result.update(
        {
            "branch_name": branch_name,
            "commit_sha": commit_sha,
            "pr_metadata": pr_metadata,
            "pr_number": pr_metadata.get("number"),
            "pr_url": pr_metadata.get("url"),
            "pr_title": pr_metadata.get("title"),
        }
    )
    return result
