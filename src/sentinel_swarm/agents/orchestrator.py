"""Orchestrator agent: parses intent, routes work, and guarantees delivery."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..base import BaseAgent
from ..messages import Message
from ..topics import Topics

INTENT_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("security", ("security", "attack", "intrusion", "breach", "malware", "incident", "ssh", "log", "scan", "threat", "brute")),
    ("software", ("code", "bug", "test", "build", "refactor", "deploy", "pipeline", "coverage")),
    ("analysis", ("data", "metric", "trend", "analyze", "analyse", "insight", "summar")),
]

@dataclass
class MissionState:
    """Everything the orchestrator remembers about one in-flight mission."""

    mission_id: str
    intent: Dict[str, Any] = field(default_factory=dict)
    phase: str = "recon"
    recon: Dict[str, Any] = field(default_factory=dict)
    analysis: Dict[str, Any] = field(default_factory=dict)
    execution: Dict[str, Any] = field(default_factory=dict)
    last_task: Optional[Tuple[str, Dict[str, Any]]] = None
    error_attempts: int = 0
    errors: List[str] = field(default_factory=list)
    future: Optional[asyncio.Future] = None
    timeout_task: Optional[asyncio.Task] = None

    def done(self) -> bool:
        return self.phase in ("done", "failed")


class OrchestratorAgent(BaseAgent):
    """Manager: turns a natural-language mission into a coordinated pipeline."""

    name = "orchestrator"
    subscribes_to = (
        Topics.MISSIONS,
        Topics.RESULT_RECON,
        Topics.RESULT_ANALYSIS,
        Topics.RESULT_EXECUTION,
        Topics.REPORT_READY,
        Topics.ERRORS,
    )

    MAX_MISSION_RETRIES = 1

    def __init__(self, name: str = "orchestrator", bus=None, max_retries: int = 2, default_timeout: float = 30.0) -> None:
        self.default_timeout = default_timeout
        self.missions: Dict[str, MissionState] = {}
        super().__init__(name, bus, max_retries)

    # ------------------------------------------------------------------ API

    @staticmethod
    def parse_intent(description: str) -> Dict[str, Any]:
        """Classify a free-form mission description into a mission type."""
        text = (description or "").lower()
        for mission_type, keywords in INTENT_RULES:
            if any(keyword in text for keyword in keywords):
                return {"mission_type": mission_type, "description": description}
        return {"mission_type": "analysis", "description": description}

    async def run_mission(
        self,
        description: str,
        artifacts: Optional[List[str]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Submit a mission and await its final report envelope."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        mission_id = uuid.uuid4().hex[:12]
        state = MissionState(mission_id=mission_id, future=future)
        self.missions[mission_id] = state
        effective_timeout = self.default_timeout if timeout is None else timeout
        state.timeout_task = asyncio.create_task(self._watchdog(mission_id, effective_timeout))
        self.bus.publish(
            Topics.MISSIONS,
            Message.task(
                sender="user",
                topic=Topics.MISSIONS,
                payload={"description": description, "artifacts": artifacts or []},
                correlation_id=mission_id,
            ),
        )
        return await future

    # --------------------------------------------------------------- router

    async def handle(self, message: Message) -> None:
        handlers = {
            Topics.MISSIONS: self._on_mission,
            Topics.RESULT_RECON: self._on_recon,
            Topics.RESULT_ANALYSIS: self._on_analysis,
            Topics.RESULT_EXECUTION: self._on_execution,
            Topics.REPORT_READY: self._on_report_ready,
            Topics.ERRORS: self._on_error,
        }
        handler = handlers.get(message.topic)
        if handler is not None:
            await handler(message)

    # -------------------------------------------------------------- mission

    async def _on_mission(self, message: Message) -> None:
        mission_id = message.correlation_id
        state = self.missions.get(mission_id) or MissionState(mission_id=mission_id)
        self.missions[mission_id] = state
        state.intent = self.parse_intent(message.payload.get("description", ""))
        await self._dispatch_task(
            state,
            Topics.TASK_RECON,
            {"artifacts": message.payload.get("artifacts", []), "intent": state.intent},
        )

    async def _on_recon(self, message: Message) -> None:
        state = self.missions.get(message.correlation_id)
        if not state or state.done():
            return
        state.recon = message.payload
        state.phase = "analysis"
        await self._dispatch_task(state, Topics.TASK_ANALYSIS, {"recon": message.payload, "intent": state.intent})

    async def _on_analysis(self, message: Message) -> None:
        state = self.missions.get(message.correlation_id)
        if not state or state.done():
            return
        state.analysis = message.payload
        state.phase = "execution"
        await self._dispatch_task(
            state,
            Topics.TASK_EXECUTION,
            {"findings": message.payload.get("findings", []), "recon": state.recon},
        )

    async def _on_execution(self, message: Message) -> None:
        state = self.missions.get(message.correlation_id)
        if not state or state.done():
            return
        state.execution = message.payload
        state.phase = "report"
        findings = state.analysis.get("findings", [])
        actions = message.payload.get("actions", [])
        metrics = {
            "lines_scanned": state.recon.get("total_lines", 0),
            "failed_logins": state.recon.get("failed_login_count", 0),
            "findings": len(findings),
            "actions_applied": len([a for a in actions if a.get("status") == "applied"]),
            "validation": message.payload.get("validation", {}),
        }
        await self._dispatch_task(
            state,
            Topics.TASK_REPORT,
            {
                "mission_id": state.mission_id,
                "mission_type": state.intent.get("mission_type", "analysis"),
                "status": "completed",
                "summary": self._summarize(state, findings, actions),
                "findings": findings,
                "actions": actions,
                "errors": state.errors,
                "metrics": metrics,
            },
        )

    async def _on_report_ready(self, message: Message) -> None:
        state = self.missions.get(message.correlation_id)
        if not state or state.done():
            return
        state.phase = "done"
        self._cancel_timeout(state)
        result = {
            "mission_id": state.mission_id,
            "status": message.payload.get("report", {}).get("status", "completed"),
            "report": message.payload.get("report", {}),
            "markdown": message.payload.get("markdown", ""),
        }
        if state.future and not state.future.done():
            state.future.set_result(result)

    # ------------------------------------------------------- error recovery

    async def _on_error(self, message: Message) -> None:
        payload = message.payload
        state = self.missions.get(payload.get("correlation_id"))
        if not state or state.done():
            return
        state.error_attempts += 1
        error_text = f"{payload.get('failed_phase', 'unknown')}: {payload.get('error', 'unknown error')}"
        state.errors.append(error_text)
        if state.error_attempts <= self.MAX_MISSION_RETRIES and state.last_task:
            # mission-level retry: re-dispatch the phase that failed
            topic, task_payload = state.last_task
            self.bus.publish(
                topic,
                Message.task(sender=self.name, topic=topic, payload=task_payload, correlation_id=state.mission_id),
            )
            return
        await self._fail(state, f"Agent failure could not be recovered: {error_text}")

    async def _watchdog(self, mission_id: str, timeout: float) -> None:
        await asyncio.sleep(timeout)
        state = self.missions.get(mission_id)
        if state and not state.done():
            await self._fail(state, f"Mission timed out after {timeout}s in phase '{state.phase}'")

    async def _fail(self, state: MissionState, error_text: str) -> None:
        state.phase = "failed"
        state.errors.append(error_text)
        self._cancel_timeout(state)
        # ask the reporter for a proper failure report
        self.bus.publish(
            Topics.TASK_REPORT,
            Message.task(
                sender=self.name,
                topic=Topics.TASK_REPORT,
                payload={
                    "mission_id": state.mission_id,
                    "mission_type": state.intent.get("mission_type", "analysis"),
                    "status": "failed",
                    "summary": f"Mission failed: {error_text}",
                    "findings": state.analysis.get("findings", []),
                    "actions": state.execution.get("actions", []),
                    "errors": state.errors,
                    "metrics": {},
                },
                correlation_id=state.mission_id,
            ),
        )
        # safety net: if the reporter is itself unavailable, still unblock callers
        asyncio.create_task(self._fallback_result(state, error_text))

    async def _fallback_result(self, state: MissionState, error_text: str) -> None:
        await asyncio.sleep(2.0)
        if state.future and not state.future.done():
            state.future.set_result(
                {
                    "mission_id": state.mission_id,
                    "status": "failed",
                    "report": {"status": "failed", "summary": error_text, "errors": state.errors},
                    "markdown": f"# Mission Report: {state.mission_id}\n\n**Status:** failed\n\n{error_text}\n",
                }
            )

    # -------------------------------------------------------------- helpers

    async def _dispatch_task(self, state: MissionState, topic: str, payload: Dict[str, Any]) -> None:
        state.last_task = (topic, payload)
        self.bus.publish(
            topic,
            Message.task(sender=self.name, topic=topic, payload=payload, correlation_id=state.mission_id),
        )

    @staticmethod
    def _summarize(state: MissionState, findings: List[Dict], actions: List[Dict]) -> str:
        high = [f for f in findings if f.get("severity") == "high"]
        return (
            f"Scanned {state.recon.get('total_lines', 0)} lines, found {len(findings)} findings "
            f"({len(high)} high severity) and applied {len(actions)} remediation(s)."
        )

    @staticmethod
    def _cancel_timeout(state: MissionState) -> None:
        if state.timeout_task and not state.timeout_task.done():
            state.timeout_task.cancel()
