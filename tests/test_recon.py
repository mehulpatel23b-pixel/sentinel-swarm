"""Recon agent data extraction."""

from sentinel_swarm.agents import ReconAgent

AUTH_LINES = [
    "Oct 20 02:14:01 host sshd[101]: Failed password for root from 203.0.113.7 port 41822 ssh2",
    "Oct 20 02:14:03 host sshd[102]: Failed password for root from 203.0.113.7 port 41823 ssh2",
    "Oct 20 02:14:05 host sshd[103]: invalid user admin from 198.51.100.9 port 51004",
    "Oct 20 02:15:00 host CRON[110]: pam_unix(cron:session): session opened for user backup",
    "",
    "Oct 20 02:16:00 host sshd[120]: Accepted publickey for deploy from 10.0.0.5 port 22 ssh2",
]


def test_recon_extracts_ips_and_failed_logins():
    findings = ReconAgent.scan(AUTH_LINES)
    assert findings["total_lines"] == 5  # blank line ignored
    assert findings["ip_addresses"]["203.0.113.7"] == 2
    assert findings["failed_login_count"] == 3
    assert findings["failed_by_ip"]["203.0.113.7"] == 2
    assert findings["ports"]["41822"] == 1
    assert "sshd" in findings["services"]


def test_recon_empty_artifacts_returns_clean_summary():
    findings = ReconAgent.scan([])
    assert findings["total_lines"] == 0
    assert findings["ip_addresses"] == {}
    assert findings["failed_login_count"] == 0
    assert findings["suspicious_lines"] == []


def test_recon_flags_suspicious_lines():
    findings = ReconAgent.scan(AUTH_LINES)
    assert any("Failed password" in line for line in findings["suspicious_lines"])
    assert all("session opened" not in line for line in findings["suspicious_lines"])
