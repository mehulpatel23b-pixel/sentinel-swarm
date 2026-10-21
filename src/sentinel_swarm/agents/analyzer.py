"""Analyzer agent: evaluates recon findings and scores security threats."""

from __future__ import annotations

from typing import Dict, List

from ..base import BaseAgent
from ..messages import Message
from ..topics import Topics

BRUTE_FORCE_THRESHOLD = 5
MEDIUM_THRESHOLD = 1


class AnalyzerAgent(BaseAgent):
    """Security analyst: converts raw recon data into scored findings."""

    name = "analyzer"
    subscribes_to = (Topics.TASK_ANALYSIS,)

    def __init__(self, name: str = "analyzer", bus=None, max_retries: int = 2, brute_force_threshold: int = BRUTE_FORCE_THRESHOLD) -> None:
        self.brute_force_threshold = brute_force_threshold
        super().__init__(name, bus, max_retries)

    async def handle(self, message: Message) -> None:
        recon = message.payload.get("recon", {})
        findings = self.analyze(recon)
        self.bus.publish(
            Topics.RESULT_ANALYSIS,
            Message.result(
                sender=self.name,
                topic=Topics.RESULT_ANALYSIS,
                payload={"findings": findings, "recon": recon},
                correlation_id=message.correlation_id,
            ),
        )

    def analyze(self, recon: Dict) -> List[Dict]:
        """Produce ordered findings, most severe first."""
        findings: List[Dict] = []
        failed_by_ip: Dict[str, int] = recon.get("failed_by_ip", {})

        for ip, count in sorted(failed_by_ip.items(), key=lambda kv: -kv[1]):
            if count >= self.brute_force_threshold:
                findings.append(
                    {
                        "id": f"BRUTE-{ip}",
                        "title": f"Brute-force attack pattern from {ip}",
                        "severity": "high",
                        "score": min(7.0 + count * 0.1, 10.0),
                        "source_ip": ip,
                        "evidence": f"{count} failed authentication attempts",
                        "recommendation": f"Block {ip} at the firewall and enforce key-based SSH auth",
                    }
                )
            elif count >= MEDIUM_THRESHOLD:
                findings.append(
                    {
                        "id": f"SUSPECT-{ip}",
                        "title": f"Repeated failed logins from {ip}",
                        "severity": "medium",
                        "score": 4.0 + min(count, 4) * 0.25,
                        "source_ip": ip,
                        "evidence": f"{count} failed authentication attempt(s)",
                        "recommendation": f"Add {ip} to a watchlist and enable alerting",
                    }
                )

        total_failed = recon.get("failed_login_count", 0)
        if total_failed == 0:
            findings.append(
                {
                    "id": "CLEAN",
                    "title": "No authentication anomalies detected",
                    "severity": "info",
                    "score": 0.0,
                    "source_ip": None,
                    "evidence": f"Scanned {recon.get('total_lines', 0)} log lines",
                    "recommendation": "No action required",
                }
            )

        findings.sort(key=lambda f: -f["score"])
        return findings
