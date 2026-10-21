"""Canonical topic names for the event bus."""

from __future__ import annotations


class Topics:
    """Every publish/subscribe channel used by the swarm."""

    # inbound mission requests
    MISSIONS = "missions.new"

    # task routing (orchestrator -> specialist agents)
    TASK_RECON = "tasks.recon"
    TASK_ANALYSIS = "tasks.analysis"
    TASK_EXECUTION = "tasks.execution"
    TASK_REPORT = "tasks.report"

    # result streaming (specialist agents -> orchestrator)
    RESULT_RECON = "results.recon"
    RESULT_ANALYSIS = "results.analysis"
    RESULT_EXECUTION = "results.execution"
    REPORT_READY = "results.report"

    # agent failure notifications (any agent -> orchestrator)
    ERRORS = "system.errors"

    # direct addressing convention: agent.<name>
    @classmethod
    def agent(cls, name: str) -> str:
        return f"agent.{name}"
