"""Recon agent: scans raw artifacts and extracts structured intelligence."""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List

from ..base import BaseAgent
from ..messages import Message, MessageType
from ..topics import Topics

IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
PORT_PATTERN = re.compile(r"\bport\s+(\d{1,5})\b", re.IGNORECASE)
FAILED_LOGIN_PATTERN = re.compile(
    r"(failed|invalid user|authentication failure|bad password|login failed|"
    r"connection closed by authenticating user|possible breaking-in attempt)",
    re.IGNORECASE,
)
SERVICE_PATTERN = re.compile(r"\b(ssh2?|sshd|sudo|CRON|systemd|httpd|nginx|mysql)\b", re.IGNORECASE)


class ReconAgent(BaseAgent):
    """Gathers data: parses logs, extracts IPs, ports, services and events."""

    name = "recon"
    subscribes_to = (Topics.TASK_RECON,)

    async def handle(self, message: Message) -> None:
        artifacts: List[str] = message.payload.get("artifacts", [])
        findings = self.scan(artifacts)
        self.bus.publish(
            Topics.RESULT_RECON,
            Message.result(
                sender=self.name,
                topic=Topics.RESULT_RECON,
                payload=findings,
                correlation_id=message.correlation_id,
            ),
        )

    @staticmethod
    def scan(artifacts: List[str]) -> Dict:
        """Turn raw log lines into a structured recon summary."""
        ip_counter: Counter = Counter()
        failed_by_ip: Counter = Counter()
        ports: Counter = Counter()
        services: Counter = Counter()
        suspicious_lines: List[str] = []
        failed_login_count = 0

        for line in artifacts:
            line = str(line).strip()
            if not line:
                continue
            line_ips = IP_PATTERN.findall(line)
            ip_counter.update(line_ips)
            if FAILED_LOGIN_PATTERN.search(line):
                failed_login_count += 1
                for ip in line_ips:
                    failed_by_ip[ip] += 1
                suspicious_lines.append(line[:240])
            match = PORT_PATTERN.search(line)
            if match:
                ports[match.group(1)] += 1
            services.update(s.strip().lower() for s in SERVICE_PATTERN.findall(line))

        return {
            "total_lines": len([l for l in artifacts if str(l).strip()]),
            "ip_addresses": dict(ip_counter),
            "failed_login_count": failed_login_count,
            "failed_by_ip": dict(failed_by_ip),
            "ports": dict(ports),
            "services": dict(services),
            "suspicious_lines": suspicious_lines[:25],
        }
