"""Reporter agent and Report model output."""

import json

from sentinel_swarm.reports import Report

REPORT = Report(
    mission_id="m1",
    mission_type="security",
    status="completed",
    summary="Scanned 10 lines, found 1 findings (1 high severity).",
    findings=[{"id": "BRUTE-1.2.3.4", "severity": "high", "title": "Brute-force attack", "evidence": "12 failures"}],
    actions=[{"type": "block_ip", "target": "1.2.3.4", "status": "applied"}],
    errors=[],
    metrics={"lines_scanned": 10},
)


def test_markdown_report_contains_all_sections():
    markdown = REPORT.to_markdown()
    assert markdown.startswith("# Mission Report: m1")
    assert "## Summary" in markdown
    assert "## Findings" in markdown
    assert "BRUTE-1.2.3.4" in markdown
    assert "## Actions Taken" in markdown
    assert "block_ip" in markdown
    assert "## Metrics" in markdown


def test_json_report_round_trips():
    restored = json.loads(REPORT.to_json())
    assert restored["mission_id"] == "m1"
    assert restored["status"] == "completed"
    assert restored["findings"][0]["severity"] == "high"
    assert restored["metrics"]["lines_scanned"] == 10


def test_failed_report_lists_errors():
    failed = Report(mission_id="m2", mission_type="security", status="failed", summary="boom", errors=["timeout"])
    markdown = failed.to_markdown()
    assert "## Errors" in markdown
    assert "- timeout" in markdown
    assert "_No actions were necessary._" in markdown
