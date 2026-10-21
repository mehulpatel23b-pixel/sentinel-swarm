"""Analyzer agent threat scoring."""

from sentinel_swarm.agents import AnalyzerAgent


def make_analyzer() -> AnalyzerAgent:
    return AnalyzerAgent("analyzer", None)


BRUTE_IP = "203.0.113.7"
CASUAL_IP = "198.51.100.9"


def test_brute_force_detected_and_scored_high():
    recon = {"failed_by_ip": {BRUTE_IP: 20}, "failed_login_count": 20, "total_lines": 25}
    findings = make_analyzer().analyze(recon)
    assert findings[0]["id"] == f"BRUTE-{BRUTE_IP}"
    assert findings[0]["severity"] == "high"
    assert findings[0]["score"] >= 8.0


def test_repeated_low_failures_flagged_medium():
    recon = {"failed_by_ip": {CASUAL_IP: 3}, "failed_login_count": 3, "total_lines": 10}
    findings = make_analyzer().analyze(recon)
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"


def test_clean_logs_produce_informational_finding_only():
    recon = {"failed_by_ip": {}, "failed_login_count": 0, "total_lines": 40}
    findings = make_analyzer().analyze(recon)
    assert len(findings) == 1
    assert findings[0]["severity"] == "info"
    assert findings[0]["recommendation"] == "No action required"


def test_findings_sorted_most_severe_first():
    recon = {"failed_by_ip": {CASUAL_IP: 2, BRUTE_IP: 12}, "failed_login_count": 14, "total_lines": 20}
    findings = make_analyzer().analyze(recon)
    assert findings[0]["id"] == f"BRUTE-{BRUTE_IP}"
    assert findings[-1]["source_ip"] == CASUAL_IP
