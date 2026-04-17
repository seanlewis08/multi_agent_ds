"""Tests for demo_recorder atomic JSON write helper."""
import json
from pathlib import Path

from multi_agent_ds.orchestration.demo_recorder import atomic_write_json


def test_atomic_write_json_creates_file(tmp_path: Path):
    """atomic_write_json creates a valid JSON file at the target path."""
    target = tmp_path / "out.json"
    payload = {"a": 1, "b": "test"}
    atomic_write_json(payload, target)

    assert target.exists()
    # Verify it's valid JSON and parseable
    parsed = json.loads(target.read_text(encoding="utf-8"))
    assert parsed == payload


def test_atomic_write_json_no_tmp_leftover(tmp_path: Path):
    """atomic_write_json leaves no .tmp sibling after write."""
    target = tmp_path / "out.json"
    payload = {"a": 1}
    atomic_write_json(payload, target)

    tmp_file = target.with_suffix(target.suffix + ".tmp")
    assert not tmp_file.exists(), "Temporary file should not remain after successful write"


def test_atomic_write_json_replaces_existing(tmp_path: Path):
    """atomic_write_json replaces existing file atomically."""
    target = tmp_path / "out.json"

    # First write
    first_payload = {"version": 1, "data": "first"}
    atomic_write_json(first_payload, target)
    first_content = target.read_text(encoding="utf-8")

    # Second write (replacement)
    second_payload = {"version": 2, "data": "second"}
    atomic_write_json(second_payload, target)

    # Verify second content is present and valid
    parsed = json.loads(target.read_text(encoding="utf-8"))
    assert parsed == second_payload
    assert parsed != first_payload


def test_atomic_write_json_overwrites_stale_tmp(tmp_path: Path):
    """atomic_write_json overwrites a stale .tmp file from a previous crash."""
    target = tmp_path / "out.json"
    tmp_file = target.with_suffix(target.suffix + ".tmp")

    # Simulate a crashed previous run that left junk in .tmp
    tmp_file.write_text("corrupted junk data", encoding="utf-8")

    # Now run atomic_write_json
    payload = {"clean": True}
    atomic_write_json(payload, target)

    # Verify the output is clean and .tmp is gone
    assert target.exists()
    assert not tmp_file.exists()
    parsed = json.loads(target.read_text(encoding="utf-8"))
    assert parsed == payload
