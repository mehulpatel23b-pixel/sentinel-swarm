"""Report model: the single deliverable every mission produces."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class Report:
    """Structured mission outcome, serialisable to markdown and JSON."""

    mission_id: str
    mission_type: str
    status: str
    summary: str
    findings: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# Mission Report: {self.mission_id}")
        lines.append("")
        lines.append(f"**Type:** {self.mission_type}  ")
        lines.append(f"**Status:** {self.status}")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append(self.summary or "_No summary provided._")
        lines.append("")
        lines.append("## Findings")
        lines.append("")
        if self.findings:
            lines.append("| ID | Severity | Title | Evidence |")
            lines.append("|----|----------|-------|----------|")
            for finding in self.findings:
                lines.append(
                    f"| {finding.get('id', '-')} | {finding.get('severity', '-')} "
                    f"| {finding.get('title', '-')} | {finding.get('evidence', '-')} |"
                )
        else:
            lines.append("_No findings._")
        lines.append("")
        lines.append("## Actions Taken")
        lines.append("")
        if self.actions:
            for action in self.actions:
                lines.append(f"- **{action.get('type', '-')}** -> {action.get('target', '-')} ({action.get('status', '-')})")
        else:
            lines.append("_No actions were necessary._")
        lines.append("")
        if self.errors:
            lines.append("## Errors")
            lines.append("")
            for error in self.errors:
                lines.append(f"- {error}")
            lines.append("")
        if self.metrics:
            lines.append("## Metrics")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(self.metrics, indent=2, sort_keys=True))
            lines.append("```")
            lines.append("")
        return "\n".join(lines)
