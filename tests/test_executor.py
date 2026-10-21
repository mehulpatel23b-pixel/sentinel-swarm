"""Executor agent remediation and validation."""

from sentinel_swarm.agents import ExecutorAgent

HIGH_FINDING = {
    "id": "BRUTE-203.0.113.7",
    "severity": "high",
    "source_ip": "203.0.113.7",
}
MEDIUM_FINDING = {
    "id": "SUSPECT-198.51.100.9",
    "severity": "medium",
    "source_ip": "198.51.100.9",
}


def test_blocks_every_threatening_ip_and_hardens_for_high():
    actions = ExecutorAgent.remediate([HIGH_FINDING, MEDIUM_FINDING])
    blocked = [a for a in actions if a["type"] == "block_ip"]
    assert {a["target"] for a in blocked} == {"203.0.113.7", "198.51.100.9"}
    assert any(a["type"] == "harden_auth" for a in actions)  # high severity triggers hardening
    assert all(a["status"] == "applied" for a in actions)


def test_no_actions_for_clean_findings():
    findings = [{"id": "CLEAN", "severity": "info", "source_ip": None, "recommendation": "No action required"}]
    actions = ExecutorAgent.remediate(findings)
    assert actions == []
    validation = ExecutorAgent.validate(actions)
    assert validation["passed"] is True


def test_validation_reports_unique_applied_rules():
    actions = ExecutorAgent.remediate([HIGH_FINDING, dict(HIGH_FINDING)])  # duplicate finding
    validation = ExecutorAgent.validate(actions)
    assert validation["checks"]["action_ids_unique"] is True
    assert validation["checks_run"] == 4
