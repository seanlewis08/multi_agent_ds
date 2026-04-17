"""Git and GitHub utilities for experiment and development PR flows."""

import json
import logging
import subprocess
from pathlib import Path

from multi_agent_ds.tools.skill_recorder import record_tool_call

logger = logging.getLogger(__name__)


def _run_command(command: list[str], cwd: str | Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a git or gh command and capture its result."""

    resolved_cwd = Path(cwd) if cwd is not None else None

    try:
        return subprocess.run(
            command,
            cwd=resolved_cwd,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        command_text = " ".join(command)
        raise RuntimeError(
            f"Command failed: {command_text} (cwd={resolved_cwd!r}, returncode={exc.returncode})\n"
            f"stdout:\n{exc.stdout or ''}\n"
            f"stderr:\n{exc.stderr or ''}"
        ) from exc


@record_tool_call
def get_current_branch(cwd: str | Path | None = None) -> str:
    """Return the name of the current git branch."""

    result = _run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    return result.stdout.strip()


@record_tool_call
def create_branch(branch_name: str, from_branch: str = "main", cwd: str | Path | None = None) -> str:
    """Create and check out a git branch from another branch."""

    _run_command(["git", "checkout", "-b", branch_name, from_branch], cwd=cwd)
    return branch_name


def stage_files(paths: list[str | Path], cwd: str | Path | None = None) -> list[str]:
    """Stage specific files in git and return their normalized paths."""

    normalized_paths = [str(Path(path)) for path in paths]
    if not normalized_paths:
        return []

    _run_command(["git", "add", "--", *normalized_paths], cwd=cwd)
    return normalized_paths


def stage_all_changes(cwd: str | Path | None = None) -> list[str]:
    """Stage all tracked and untracked changes in git and return staged paths."""

    _run_command(["git", "add", "--all"], cwd=cwd)
    result = _run_command(["git", "diff", "--cached", "--name-only"], cwd=cwd)
    return [line for line in result.stdout.splitlines() if line]


@record_tool_call
def commit(message: str, cwd: str | Path | None = None) -> str:
    """Create a git commit and return its hash."""

    _run_command(["git", "commit", "--quiet", "-m", message], cwd=cwd)
    result = _run_command(["git", "rev-parse", "HEAD"], cwd=cwd)
    return result.stdout.strip()


@record_tool_call
def push_branch(branch_name: str, force: bool = False, cwd: str | Path | None = None) -> None:
    """Push a git branch to origin, optionally forcing the update."""

    command = ["git", "push", "origin"]
    if force:
        command.append("--force")
    command.append(branch_name)
    _run_command(command, cwd=cwd)


def get_diff_summary(base: str = "main", cwd: str | Path | None = None) -> str:
    """Return the git diff --stat summary against a base reference."""

    result = _run_command(["git", "diff", "--stat", base], cwd=cwd)
    return result.stdout.strip()


def get_changed_files(base: str = "main", cwd: str | Path | None = None) -> list[str]:
    """Return the list of files changed against a base reference."""

    result = _run_command(["git", "diff", "--name-only", base], cwd=cwd)
    return [line for line in result.stdout.splitlines() if line]


@record_tool_call
def create_pull_request(
    title: str,
    body: str,
    base: str = "main",
    head: str | None = None,
    draft: bool = False,
    cwd: str | Path | None = None,
) -> dict:
    """Create a pull request via gh and return basic metadata."""

    head_ref = head or get_current_branch(cwd=cwd)
    command = [
        "gh",
        "pr",
        "create",
        "--title",
        title,
        "--body",
        body,
        "--base",
        base,
        "--head",
        head_ref,
    ]
    if draft:
        command.append("--draft")

    create_result = _run_command(command, cwd=cwd)
    pr_url = next(
        (line.strip() for line in reversed(create_result.stdout.splitlines()) if line.strip()),
        "",
    )

    view_result = _run_command(
        [
            "gh",
            "pr",
            "view",
            pr_url,
            "--json",
            "number,title,url,body,headRefName,baseRefName,isDraft,state",
        ],
        cwd=cwd,
    )
    metadata = json.loads(view_result.stdout)
    return {
        "number": metadata["number"],
        "title": metadata["title"],
        "url": metadata["url"],
        "body": metadata["body"],
        "head": metadata["headRefName"],
        "base": metadata["baseRefName"],
        "draft": metadata["isDraft"],
        "state": metadata["state"],
    }


def get_open_prs(base: str = "main", cwd: str | Path | None = None) -> list[dict]:
    """List open pull requests against a base branch."""

    result = _run_command(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--base",
            base,
            "--json",
            "number,title,url,headRefName,baseRefName,isDraft,state",
        ],
        cwd=cwd,
    )
    prs = json.loads(result.stdout)
    return [
        {
            "number": pr["number"],
            "title": pr["title"],
            "url": pr["url"],
            "head": pr["headRefName"],
            "base": pr["baseRefName"],
            "draft": pr["isDraft"],
            "state": pr["state"],
        }
        for pr in prs
    ]
