"""Team assembly: wires the five agents onto one event bus."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from .agents import AnalyzerAgent, ExecutorAgent, OrchestratorAgent, ReconAgent, ReporterAgent
from .base import BaseAgent
from .bus import EventBus


class SentinelTeam:
    """A five-agent swarm: orchestrator, recon, analyzer, executor, reporter."""

    def __init__(self, agents: Optional[List[BaseAgent]] = None, default_timeout: float = 30.0) -> None:
        self.bus = EventBus()
        if agents is None:
            agents = [
                OrchestratorAgent("orchestrator", self.bus, default_timeout=default_timeout),
                ReconAgent("recon", self.bus),
                AnalyzerAgent("analyzer", self.bus),
                ExecutorAgent("executor", self.bus),
                ReporterAgent("reporter", self.bus),
            ]
        self.agents = agents
        self.orchestrator = next(a for a in agents if isinstance(a, OrchestratorAgent))
        self._tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        """Launch every agent as an independent async worker."""
        self._tasks = [asyncio.create_task(agent.start()) for agent in self.agents]

    async def stop(self) -> None:
        """Gracefully shut the swarm down and await agent exit."""
        for agent in self.agents:
            agent.stop()
        await self.bus.close()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def run(self, description: str, artifacts: Optional[List[str]] = None, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Run one mission end-to-end and return its report envelope."""
        return await self.orchestrator.run_mission(description, artifacts, timeout)

    @property
    def metrics(self) -> List[Dict[str, Any]]:
        return [agent.metrics() for agent in self.agents]

    async def __aenter__(self) -> "SentinelTeam":
        await self.start()
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.stop()
