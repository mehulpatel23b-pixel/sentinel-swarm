"""Reporter agent: compiles the final mission report (markdown + JSON)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..base import BaseAgent
from ..messages import Message
from ..reports import Report
from ..topics import Topics


class ReporterAgent(BaseAgent):
    """Auditor: aggregates everything into a structured final report."""

    name = "reporter"
    subscribes_to = (Topics.TASK_REPORT,)

    async def handle(self, message: Message) -> None:
        payload = message.payload
        report = Report(
            mission_id=payload.get("mission_id", message.correlation_id),
            mission_type=payload.get("mission_type", "unknown"),
            status=payload.get("status", "completed"),
            summary=payload.get("summary", ""),
            findings=payload.get("findings", []),
            actions=payload.get("actions", []),
            errors=payload.get("errors", []),
            metrics=payload.get("metrics", {}),
        )
        self.bus.publish(
            Topics.REPORT_READY,
            Message.result(
                sender=self.name,
                topic=Topics.REPORT_READY,
                payload={
                    "report": report.to_dict(),
                    "markdown": report.to_markdown(),
                    "json": report.to_json(),
                },
                correlation_id=message.correlation_id,
            ),
        )
