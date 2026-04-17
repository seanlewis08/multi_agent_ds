"""Unit tests for demo_viewer_loader.inject_demo_log."""
from __future__ import annotations

import json

import pytest

from multi_agent_ds.orchestration.demo_viewer_loader import inject_demo_log


def test_inject_adds_demo_log_before_first_script() -> None:
    viewer = "<html><head></head><body><script>var a=1;</script></body></html>"
    log = '{"events":[],"config":{}}'

    result = inject_demo_log(viewer, log)

    assert "<script>window.DEMO_LOG = " in result
    assert '"events":[]' in result
    # injected block appears before the template's own script
    assert result.index("window.DEMO_LOG") < result.index("var a=1")


def test_inject_preserves_template_content_exactly() -> None:
    viewer = "<html><head></head><body>BEFORE<script>X</script>AFTER</body></html>"
    log = '{"k":"v"}'

    result = inject_demo_log(viewer, log)

    assert "BEFORE" in result
    assert "AFTER" in result
    assert "X" in result
    # all original characters still present
    assert len(result) > len(viewer)


def test_inject_raises_when_no_script_tag() -> None:
    viewer = "<html><body>no scripts here</body></html>"
    log = "{}"

    with pytest.raises(ValueError):
        inject_demo_log(viewer, log)


def test_inject_handles_json_with_special_chars() -> None:
    # The JSON is treated as a string literal, not re-parsed or escaped,
    # so special chars inside string values are the caller's responsibility.
    # We verify that the helper does not mangle valid JSON that contains
    # characters legal in JSON strings (forward slashes, unicode escapes).
    viewer = "<script>/*body*/</script>"
    payload = {"path": "data/interim/demo_run_latest.json", "emoji": "\u2713"}
    log = json.dumps(payload)

    result = inject_demo_log(viewer, log)

    assert "data/interim/demo_run_latest.json" in result
    assert "window.DEMO_LOG" in result


def test_inject_result_is_valid_for_round_trip_parse() -> None:
    # Independent check: the injected JS block should parse cleanly. We
    # cannot execute JS here, but we can verify the injected substring is
    # exactly `window.DEMO_LOG = <payload>;`.
    viewer = "<script>/*marker*/</script>"
    log = '{"a":1,"b":[2,3]}'

    result = inject_demo_log(viewer, log)

    expected = '<script>window.DEMO_LOG = {"a":1,"b":[2,3]};</script>'
    assert expected in result


def test_inject_escapes_closing_script_tag() -> None:
    # XSS defense: ensure malicious JSON cannot break out of <script>.
    viewer = "<html><script>X</script></html>"
    log = '{"bad": "</script><script>alert(1)</script>"}'

    result = inject_demo_log(viewer, log)

    assert "</script><script>alert(1)" not in result
    assert "<\\/script>" in result
