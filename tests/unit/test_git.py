from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from multi_agent_ds.tools import git as git_tools


class CommandRecorder:
    def __init__(self, responses: dict[tuple[str, ...], str]) -> None:
        self.responses = responses
        self.calls: list[tuple[list[str], Path | None]] = []

    def __call__(self, command: list[str], cwd: str | Path | None = None) -> subprocess.CompletedProcess[str]:
        resolved_cwd = Path(cwd) if cwd is not None else None
        self.calls.append((command, resolved_cwd))
        key = tuple(command)
        if key not in self.responses:
            raise AssertionError(f"Unexpected command: {command!r}")
        return subprocess.CompletedProcess(command, 0, stdout=self.responses[key], stderr="")


def test_run_command_wraps_subprocess_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: object, **kwargs: object) -> None:
        exc = subprocess.CalledProcessError(2, args[0] if args else ["git", "status"])
        exc.stdout = "stdout output"
        exc.stderr = "stderr output"
        raise exc

    monkeypatch.setattr(git_tools.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as excinfo:
        git_tools._run_command(["git", "status"], cwd=Path("/tmp/repo"))

    message = str(excinfo.value)
    assert "Command failed: git status" in message
    assert "returncode=2" in message
    assert "stdout output" in message
    assert "stderr output" in message


def test_git_wrapper_propagates_subprocess_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: object, **kwargs: object) -> None:
        exc = subprocess.CalledProcessError(128, args[0] if args else ["git", "rev-parse"])
        exc.stdout = ""
        exc.stderr = "fatal: not a git repository"
        raise exc

    monkeypatch.setattr(git_tools.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as excinfo:
        git_tools.get_current_branch(cwd=Path("/tmp/repo"))

    message = str(excinfo.value)
    assert "Command failed: git rev-parse --abbrev-ref HEAD" in message
    assert "returncode=128" in message
    assert "fatal: not a git repository" in message


def test_run_command_returns_successful_completed_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    expected = subprocess.CompletedProcess(["git", "status"], 0, stdout="ok\n", stderr="")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return expected

    monkeypatch.setattr(git_tools.subprocess, "run", fake_run)

    result = git_tools._run_command(["git", "status"], cwd=Path("/tmp/repo"))

    assert result is expected
    assert captured["args"] == (["git", "status"],)
    assert captured["kwargs"] == {
        "cwd": Path("/tmp/repo"),
        "check": True,
        "text": True,
        "capture_output": True,
    }


def test_git_wrappers_use_expected_commands_and_return_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = CommandRecorder(
        {
            ("git", "rev-parse", "--abbrev-ref", "HEAD"): "feature/test\n",
            ("git", "checkout", "-b", "feature/new", "main"): "",
            ("git", "add", "--", "README.md", "src/multi_agent_ds/tools/git.py"): "",
            ("git", "add", "--all"): "",
            ("git", "diff", "--cached", "--name-only"): "README.md\nsrc/multi_agent_ds/tools/git.py\n",
            ("git", "commit", "--quiet", "-m", "Add git helpers"): "",
            ("git", "rev-parse", "HEAD"): "abc123def456\n",
            ("git", "push", "origin", "--force", "feature/new"): "",
            ("git", "diff", "--stat", "main"): " README.md | 2 ++\n 1 file changed\n",
            ("git", "diff", "--name-only", "main"): "README.md\nsrc/multi_agent_ds/tools/git.py\n",
        }
    )
    monkeypatch.setattr(git_tools, "_run_command", recorder)

    assert git_tools.get_current_branch() == "feature/test"
    assert git_tools.create_branch("feature/new") == "feature/new"
    assert git_tools.stage_files([Path("README.md"), "src/multi_agent_ds/tools/git.py"]) == [
        "README.md",
        "src/multi_agent_ds/tools/git.py",
    ]
    assert git_tools.stage_all_changes() == [
        "README.md",
        "src/multi_agent_ds/tools/git.py",
    ]
    assert git_tools.commit("Add git helpers") == "abc123def456"
    assert git_tools.push_branch("feature/new", force=True) is None
    assert git_tools.get_diff_summary() == "README.md | 2 ++\n 1 file changed"
    assert git_tools.get_changed_files() == ["README.md", "src/multi_agent_ds/tools/git.py"]

    assert recorder.calls == [
        (["git", "rev-parse", "--abbrev-ref", "HEAD"], None),
        (["git", "checkout", "-b", "feature/new", "main"], None),
        (["git", "add", "--", "README.md", "src/multi_agent_ds/tools/git.py"], None),
        (["git", "add", "--all"], None),
        (["git", "diff", "--cached", "--name-only"], None),
        (["git", "commit", "--quiet", "-m", "Add git helpers"], None),
        (["git", "rev-parse", "HEAD"], None),
        (["git", "push", "origin", "--force", "feature/new"], None),
        (["git", "diff", "--stat", "main"], None),
        (["git", "diff", "--name-only", "main"], None),
    ]


def test_get_changed_files_parses_name_only_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command: list[str], cwd: str | Path | None = None) -> subprocess.CompletedProcess[str]:
        assert command == ["git", "diff", "--name-only", "main"]
        assert cwd == Path("/tmp/repo")
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="README.md\n\nsrc/multi_agent_ds/tools/git.py\n",
            stderr="",
        )

    monkeypatch.setattr(git_tools, "_run_command", fake_run)

    assert git_tools.get_changed_files(cwd=Path("/tmp/repo")) == [
        "README.md",
        "src/multi_agent_ds/tools/git.py",
    ]


def test_pr_wrappers_parse_json_output(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = CommandRecorder(
        {
            (
                "gh",
                "pr",
                "create",
                "--title",
                "Add git helpers",
                "--body",
                "Implements the git utility wrappers.",
                "--base",
                "main",
                "--head",
                "feature/new",
                "--draft",
            ): "https://github.com/acme/repo/pull/7\n",
            (
                "gh",
                "pr",
                "view",
                "https://github.com/acme/repo/pull/7",
                "--json",
                "number,title,url,body,headRefName,baseRefName,isDraft,state",
            ): (
                '{"number":7,"title":"Add git helpers","url":"https://github.com/acme/repo/pull/7",'
                '"body":"Implements the git utility wrappers.","headRefName":"feature/new",'
                '"baseRefName":"main","isDraft":true,"state":"OPEN"}'
            ),
            (
                "gh",
                "pr",
                "list",
                "--state",
                "open",
                "--base",
                "main",
                "--json",
                "number,title,url,headRefName,baseRefName,isDraft,state",
            ): (
                '[{"number":7,"title":"Add git helpers","url":"https://github.com/acme/repo/pull/7",'
                '"headRefName":"feature/new","baseRefName":"main","isDraft":true,"state":"OPEN"}]'
            ),
        }
    )
    monkeypatch.setattr(git_tools, "_run_command", recorder)

    pr = git_tools.create_pull_request(
        title="Add git helpers",
        body="Implements the git utility wrappers.",
        base="main",
        head="feature/new",
        draft=True,
    )
    assert pr == {
        "number": 7,
        "title": "Add git helpers",
        "url": "https://github.com/acme/repo/pull/7",
        "body": "Implements the git utility wrappers.",
        "head": "feature/new",
        "base": "main",
        "draft": True,
        "state": "OPEN",
    }

    open_prs = git_tools.get_open_prs(base="main")
    assert open_prs == [
        {
            "number": 7,
            "title": "Add git helpers",
            "url": "https://github.com/acme/repo/pull/7",
            "head": "feature/new",
            "base": "main",
            "draft": True,
            "state": "OPEN",
        }
    ]

    assert recorder.calls == [
        (
            [
                "gh",
                "pr",
                "create",
                "--title",
                "Add git helpers",
                "--body",
                "Implements the git utility wrappers.",
                "--base",
                "main",
                "--head",
                "feature/new",
                "--draft",
            ],
            None,
        ),
        (
            [
                "gh",
                "pr",
                "view",
                "https://github.com/acme/repo/pull/7",
                "--json",
                "number,title,url,body,headRefName,baseRefName,isDraft,state",
            ],
            None,
        ),
        (
            [
                "gh",
                "pr",
                "list",
                "--state",
                "open",
                "--base",
                "main",
                "--json",
                "number,title,url,headRefName,baseRefName,isDraft,state",
            ],
            None,
        ),
    ]
