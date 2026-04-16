"""Experiment logging — real-time markdown reports and terminal progress.

Produces a human-readable experiment log at reports/experiment_log_<timestamp>.md
that grows as each phase completes. Also prints phase transitions to the terminal.
Also exposes pure state-to-markdown formatters used by the report_writer agent
to assemble prompt context. Formatters take plain mappings (not PipelineState)
and perform no I/O.

This is a tool (stateless utility). The workflow/agent layer calls it alongside
MLflow logging. Skills never import this directly.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ExperimentLogger:
    """Appends experiment results to a markdown file and prints to terminal.

    Usage:
        exp_log = ExperimentLogger()
        exp_log.start_experiment()
        exp_log.log_data_summary(data["data_summary"])
        exp_log.log_baseline("lightgbm", results["lightgbm"])
        ...
        exp_log.finalize()
    """

    def __init__(self, report_dir: str = "reports"):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.filepath = self.report_dir / f"experiment_log_{timestamp}.md"
        self.start_time = None
        self._phase_count = 0

    # ── Internal helpers ───────────────────────────────────────────────

    def _write(self, text: str) -> None:
        """Append text to the report file."""
        with open(self.filepath, "a") as f:
            f.write(text + "\n")

    def _timestamp(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _terminal(self, msg: str) -> None:
        """Print a timestamped message to the terminal."""
        print(f"[{self._timestamp()}] {msg}")

    def _phase_header(self, title: str) -> None:
        """Write a phase separator to both terminal and file."""
        self._phase_count += 1
        self._terminal(f"Phase {self._phase_count}: {title}")
        self._write(f"\n---\n\n## Phase {self._phase_count}: {title}\n")

    def _format_scores(self, scores: dict[str, float], prefix: str = "") -> str:
        """Format a dict of metric scores as a readable string."""
        parts = [f"{prefix}{k}={v:.4f}" for k, v in scores.items()]
        return ", ".join(parts)

    # ── Public API ─────────────────────────────────────────────────────

    def start_experiment(self) -> None:
        """Initialize the experiment log file."""
        self.start_time = datetime.now()
        timestamp_str = self.start_time.strftime("%Y-%m-%d %H:%M:%S")

        self._terminal(f"═══ Experiment started ═══")
        self._terminal(f"Log: {self.filepath}")

        self._write(f"# Experiment Log — {timestamp_str}\n")

    def log_data_summary(self, summary: dict[str, Any]) -> None:
        """Log the data preparation summary."""
        self._write("## Data Summary\n")
        self._write(f"- **Train:** {summary['n_train']} rows")
        self._write(f"- **Validation:** {summary['n_validation']} rows")
        self._write(f"- **Test:** {summary['n_test']} rows")
        self._write(
            f"- **Features:** {summary['n_features']} "
            f"({summary['n_numerical']} numerical, {summary['n_categorical']} categorical)"
        )
        self._write(
            f"- **Target rate:** {summary['target_rate_train']:.4f} (train), "
            f"{summary['target_rate_validation']:.4f} (validation), "
            f"{summary['target_rate_test']:.4f} (test)"
        )
        self._write(
            f"- **Ground truth:** {'available (deterministic DGP)' if summary['has_ground_truth'] else 'not available'}"
        )
        self._write("")

    def log_baseline(self, algo_name: str, result: dict[str, Any]) -> None:
        """Log a baseline training result for one algorithm."""
        phase_title = f"Baseline — {algo_name}"
        if self._phase_count == 0 or "Baseline" not in getattr(self, "_last_phase", ""):
            self._phase_header("Baseline")
        self._last_phase = "Baseline"

        elapsed = result.get("elapsed_seconds", 0)
        params = result.get("params_used", {})
        cv = result.get("cv_scores", {})
        cv_std = result.get("cv_std", {})
        validation = result.get("validation_scores", {})
        test = result.get("test_scores", {})

        # Terminal output
        primary = list(test.keys())[0] if test else "?"
        primary_val = test.get(primary, 0)
        self._terminal(f"  ✓ {algo_name} — {primary}: {primary_val:.4f} ({elapsed:.1f}s)")

        # File output
        self._write(f"### {algo_name}\n")

        params_str = ", ".join(f"{k}={v}" for k, v in params.items())
        self._write(f"**Params:** {params_str}\n")

        cv_parts = [f"{k}={v:.4f} (+/- {cv_std.get(k, 0):.4f})" for k, v in cv.items()]
        self._write(f"**CV scores:** {', '.join(cv_parts)}\n")

        if validation:
            validation_parts = [f"{k}={v:.4f}" for k, v in validation.items()]
            self._write(f"**Validation scores:** {', '.join(validation_parts)}\n")

        test_parts = [f"{k}={v:.4f}" for k, v in test.items()]
        self._write(f"**Test scores:** {', '.join(test_parts)}\n")

        self._write(f"**Time:** {elapsed:.1f}s\n")

    def log_n_estimators(self, result: dict[str, Any]) -> None:
        """Log the optimal n_estimators search result."""
        algo = result.get("algorithm", "unknown")
        self._phase_header(f"Optimal n_estimators — {algo}")

        lr = result.get("learning_rate", 0)
        optimal_n = result.get("optimal_n_estimators", 0)
        best_score = result.get("best_score", 0)
        best_std = result.get("best_std", 0)
        n_tested = len(result.get("scores_by_n", []))
        early = result.get("search_stopped_early", False)

        self._terminal(
            f"  ✓ optimal: {optimal_n} at lr={lr} "
            f"(score: {best_score:.4f}, tested {n_tested} candidates)"
        )

        self._write(f"**Learning rate:** {lr}")
        self._write(f"**Optimal n_estimators:** {optimal_n} (score: {best_score:.4f} +/- {best_std:.4f})")
        self._write(f"**Search:** tested {n_tested} candidates{', early stopped' if early else ''}\n")

    def log_tuning(self, result: dict[str, Any]) -> None:
        """Log Optuna tuning results."""
        algo = result.get("algorithm", "unknown")
        self._phase_header(f"Optuna Tuning — {algo}")

        total_trials = result.get("total_trials", 0)
        best_trial = result.get("best_trial_number", 0)
        best_score = result.get("best_score", 0)
        baseline = result.get("baseline_score", 0)
        improvement = result.get("score_improvement", 0)
        best_params = result.get("best_params", {})
        importances = result.get("param_importances", {})
        converged = result.get("convergence_reached", False)
        elapsed = result.get("total_duration_seconds", 0)

        self._terminal(
            f"  ✓ best trial #{best_trial} of {total_trials} — "
            f"score: {best_score:.4f} (+{improvement:.4f}) ({elapsed:.1f}s)"
        )

        self._write(f"**Trials:** {total_trials} | **Best trial:** #{best_trial}")
        self._write(
            f"**Best score:** {best_score:.4f} "
            f"(improvement: {'+' if improvement >= 0 else ''}{improvement:.4f} over baseline {baseline:.4f})"
        )

        params_str = ", ".join(f"{k}={v}" for k, v in best_params.items())
        self._write(f"**Best params:** {params_str}")

        if importances:
            imp_parts = [f"{k} ({v:.2f})" for k, v in sorted(importances.items(), key=lambda x: -x[1])[:5]]
            self._write(f"**Top param importances:** {', '.join(imp_parts)}")

        self._write(f"**Convergence:** {'yes' if converged else 'no'}")
        self._write(f"**Time:** {elapsed:.1f}s\n")

    def log_lr_adjustment(self, result: dict[str, Any]) -> None:
        """Log a learning rate adjustment result."""
        adj = result.get("learning_rate_adjustment", {})
        algo = result.get("algorithm", "unknown")

        old_lr = adj.get("old_learning_rate", 0)
        new_lr = adj.get("new_learning_rate", 0)
        old_n = adj.get("old_n_estimators", 0)
        new_n = adj.get("new_n_estimators", 0)
        old_score = adj.get("old_score", 0)
        new_score = adj.get("new_score", 0)
        improved = adj.get("improved", False)

        symbol = "✓ improved" if improved else "✗ declined"

        self._terminal(
            f"  {symbol}: lr {old_lr} → {new_lr}, "
            f"n_est {old_n} → {new_n}, "
            f"score {old_score:.4f} → {new_score:.4f}"
        )

        self._write(
            f"**{old_lr} → {new_lr}:** n_estimators {old_n} → {new_n} | "
            f"score: {old_score:.4f} → {new_score:.4f} "
            f"{'✓ improved' if improved else '✗ declined'}"
        )

    def log_lr_adjustment_header(self, algo_name: str) -> None:
        """Write the phase header for learning rate adjustments."""
        self._phase_header(f"Learning Rate Adjustment — {algo_name}")

    def log_permutation_importance(self, result: dict[str, Any]) -> None:
        """Log permutation importance results with a feature table."""
        algo = result.get("algorithm", "unknown")
        self._phase_header(f"Permutation Importance — {algo}")

        n_features = result.get("n_features", 0)
        n_safe = result.get("n_safe_to_remove", 0)
        safe_list = result.get("safe_to_remove", [])
        scoring = result.get("scoring", "roc_auc")
        n_repeats = result.get("n_repeats", 0)
        ranked = result.get("ranked_features", [])

        self._terminal(
            f"  ✓ {n_safe} of {n_features} features safe to remove "
            f"({scoring}, {n_repeats} repeats)"
        )

        self._write(f"**Scoring:** {scoring} | **Repeats:** {n_repeats}\n")

        # Feature table
        self._write("| Rank | Feature | Mean Drop | Std | Safe to Remove |")
        self._write("|------|---------|-----------|-----|----------------|")
        for feat in ranked:
            safe_str = "Yes" if feat["safe_to_remove"] else "No"
            self._write(
                f"| {feat['rank']} | {feat['name']} | "
                f"{feat['mean_auc_drop']:.6f} | {feat['std']:.6f} | {safe_str} |"
            )
        self._write("")

        if safe_list:
            self._write(f"**Safe to remove:** {', '.join(safe_list)}\n")

    def log_feature_selection(
        self,
        algo_name: str,
        selection_meta: dict[str, Any],
        old_scores: dict[str, float],
        new_scores: dict[str, float],
    ) -> None:
        """Log feature selection results (before vs after)."""
        self._phase_header(f"Feature Selection — {algo_name}")

        dropped = selection_meta.get("dropped_features", [])
        n_orig = selection_meta.get("n_original", 0)
        n_kept = selection_meta.get("n_kept", 0)

        self._terminal(
            f"  ✓ dropped {len(dropped)} features ({n_orig} → {n_kept})"
        )

        self._write(f"**Dropped:** {', '.join(dropped)} ({len(dropped)} of {n_orig} features)")
        self._write(f"**Remaining:** {n_kept} features\n")

        # Score comparison
        self._write("| Metric | Before | After | Change |")
        self._write("|--------|--------|-------|--------|")
        for metric in old_scores:
            old = old_scores[metric]
            new = new_scores.get(metric, 0)
            diff = new - old
            sign = "+" if diff >= 0 else ""
            self._write(f"| {metric} | {old:.4f} | {new:.4f} | {sign}{diff:.4f} |")
        self._write("")

    def finalize(self) -> None:
        """Write the closing section with total elapsed time."""
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            self._write(f"\n---\n")
            self._write(f"**Total experiment time:** {elapsed:.1f}s")
            self._terminal(f"═══ Experiment complete ({elapsed:.1f}s) ═══")
            self._terminal(f"Report: {self.filepath}")


# ── Pure prompt-context formatters ────────────────────────────────────
#
# Used by the report_writer agent to slice pipeline state into compact markdown
# blocks for prompt assembly. Pure: take plain mappings, return strings, no I/O,
# no imports from agents/orchestration/workflows.

_DECISION_TRACE_DEFAULT_LIMIT = 25


def format_data_summary(data_summary: Mapping[str, Any] | None) -> str:
    """Format a data_summary dict (from prepare_data) as a markdown bullet list."""
    if not data_summary:
        return "_Data summary unavailable._"

    lines: list[str] = []
    n_train = data_summary.get("n_train")
    n_validation = data_summary.get("n_validation")
    n_test = data_summary.get("n_test")
    if n_train is not None:
        lines.append(f"- **Train rows:** {n_train}")
    if n_validation is not None:
        lines.append(f"- **Validation rows:** {n_validation}")
    if n_test is not None:
        lines.append(f"- **Test rows:** {n_test}")
    n_features = data_summary.get("n_features")
    n_numerical = data_summary.get("n_numerical")
    n_categorical = data_summary.get("n_categorical")
    if n_features is not None:
        feature_detail = f"{n_features}"
        if n_numerical is not None or n_categorical is not None:
            feature_detail += (
                f" ({n_numerical or 0} numerical, {n_categorical or 0} categorical)"
            )
        lines.append(f"- **Features:** {feature_detail}")
    target_train = data_summary.get("target_rate_train")
    target_test = data_summary.get("target_rate_test")
    if target_train is not None or target_test is not None:
        train_str = f"{target_train:.4f}" if target_train is not None else "?"
        test_str = f"{target_test:.4f}" if target_test is not None else "?"
        lines.append(f"- **Target rate:** train={train_str}, test={test_str}")
    if data_summary.get("has_ground_truth"):
        lines.append("- **Ground truth:** available (deterministic DGP)")
    return "\n".join(lines) if lines else "_Data summary unavailable._"


def format_modeling_summary(
    modeling_verdict: Mapping[str, Any] | None,
    modeling_results: Mapping[str, Any] | None = None,
) -> str:
    """Format the final modeling verdict + supporting per-algorithm scores."""
    if not modeling_verdict:
        return "_Modeling verdict unavailable._"

    lines = [
        f"- **Best algorithm:** {modeling_verdict.get('best_algorithm', '?')}",
        f"- **Summary:** {modeling_verdict.get('summary', '')}".rstrip(),
    ]
    ranked = modeling_verdict.get("ranked_algorithms") or []
    if ranked:
        lines.append(f"- **Ranking:** {', '.join(ranked)}")
    final_metrics = modeling_verdict.get("final_metrics") or {}
    if final_metrics:
        lines.append("- **Final per-algorithm metrics:**")
        for algo in ranked or list(final_metrics.keys()):
            algo_metrics = final_metrics.get(algo) or {}
            metric_pairs = ", ".join(
                f"{name}={value:.4f}" for name, value in algo_metrics.items()
                if isinstance(value, (int, float))
            )
            lines.append(f"  - {algo}: {metric_pairs}")
    justification = modeling_verdict.get("justification")
    if justification:
        lines.append(f"- **Justification:** {justification}")
    next_action = modeling_verdict.get("next_action")
    if next_action:
        lines.append(f"- **Modeler next action:** {next_action}")

    if modeling_results:
        candidates = modeling_results.get("final_candidates") or {}
        if candidates:
            lines.append("- **Final phase per algorithm:**")
            for algo, payload in candidates.items():
                phase = payload.get("final_phase", "?")
                lines.append(f"  - {algo}: {phase}")

    return "\n".join(lines)


def format_evaluation_summary(evaluation_result: Mapping[str, Any] | None) -> str:
    """Format Jonathan's evaluation_result. Returns a caveat block when missing."""
    if not evaluation_result:
        return (
            "_Evaluation pipeline output not available — the report relies solely "
            "on modeler-stage scores. Re-run after Jonathan's evaluation step "
            "completes for a fuller picture._"
        )

    lines: list[str] = []
    winner = evaluation_result.get("winner") or evaluation_result.get("best_algorithm")
    if winner:
        lines.append(f"- **Evaluation winner:** {winner}")
    primary_metric = evaluation_result.get("primary_metric")
    if primary_metric:
        lines.append(f"- **Primary metric:** {primary_metric}")
    rankings = evaluation_result.get("rankings") or {}
    if rankings:
        lines.append("- **Rankings:**")
        for metric, ranked in rankings.items():
            if isinstance(ranked, list):
                lines.append(f"  - {metric}: {', '.join(str(item) for item in ranked)}")
    ground_truth = evaluation_result.get("ground_truth_comparison") or {}
    if ground_truth:
        lines.append("- **Ground-truth comparison:**")
        for algo, payload in ground_truth.items():
            mse = payload.get("mse_vs_true_prob") if isinstance(payload, Mapping) else None
            if isinstance(mse, (int, float)):
                lines.append(f"  - {algo}: MSE vs true probability = {mse:.6f}")
    shap = evaluation_result.get("shap") or {}
    if shap:
        top = shap.get("top_features") or shap.get("global_ranking")
        if isinstance(top, list) and top:
            lines.append(f"- **Top features (SHAP):** {', '.join(str(t) for t in top[:10])}")
    notes = evaluation_result.get("notes")
    if notes:
        lines.append(f"- **Evaluation notes:** {notes}")

    return "\n".join(lines) if lines else "_Evaluation result present but empty._"


def format_decision_trace(
    agent_decisions: Sequence[Mapping[str, Any]] | None,
    max_entries: int = _DECISION_TRACE_DEFAULT_LIMIT,
) -> str:
    """Format the recent agent_decisions trace as a compact bullet list."""
    if not agent_decisions:
        return "_No agent decisions recorded._"

    recent = list(agent_decisions)[-max_entries:]
    lines: list[str] = []
    for entry in recent:
        agent = entry.get("agent", "?")
        phase = entry.get("phase", "?")
        detail_keys = ("summary", "best_algorithm", "next_action", "approved", "algorithm")
        details = []
        for key in detail_keys:
            if key in entry and entry[key] not in (None, ""):
                details.append(f"{key}={entry[key]}")
        suffix = f" — {'; '.join(details)}" if details else ""
        lines.append(f"- **{agent} / {phase}**{suffix}")
    return "\n".join(lines)
