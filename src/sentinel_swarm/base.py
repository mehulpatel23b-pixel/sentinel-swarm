"""Base class shared by every agent in the swarm."""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional, Sequence

from .bus import EventBus
from .messages import Message, MessageType
from .topics import Topics


class BaseAgent:
    """An autonomous worker with an inbox, retries, and failure reporting.

    Error recovery happens at two levels:

    1. **Agent level** - ``handle`` failures are retried up to ``max_retries``
       times, absorbing transient errors without operator intervention.
    2. **Mission level** - when retries are exhausted the agent publishes an
       ERROR envelope so the orchestrator can re-route or fail over.
    """

    name: str = "agent"
    subscribes_to: Sequence[str] = ()

    def __init__(self, name: str, bus: EventBus, max_retries: int = 2) -> None:
        self.name = name
        self.bus = bus if bus is not None else EventBus()
        self.max_retries = max_retries
        self.inbox = self.bus.subscribe(Topics.agent(name))
        self._queues: List[asyncio.Queue] = [self.inbox]
        for topic in self.subscribes_to:
            self._queues.append(self.bus.subscribe(topic))
        self.processed = 0
        self.failures = 0
        self.last_error: Optional[str] = None
        self._running = False

    async def start(self) -> None:
        """Run until :meth:`stop` is called or the bus closes."""
        self._running = True
        consumers = [asyncio.create_task(self._consume(queue)) for queue in self._queues]
        await asyncio.gather(*consumers)

    def stop(self) -> None:
        """Signal the agent to finish its current message and exit."""
        self._running = False
        for queue in self._queues:
            try:
                queue.put_nowait(None)
            except Exception:  # pragma: no cover - defensive
                pass

    async def _consume(self, queue: asyncio.Queue) -> None:
        while self._running:
            message = await queue.get()
            if message is None:
                self._running = False
                break
            await self._dispatch(message)

    async def _dispatch(self, message: Message) -> None:
        attempts = self.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                await self.handle(message)
                self.processed += 1
                return
            except Exception as exc:  # noqa: BLE001 - agents must never crash the bus
                self.failures += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
                if attempt < attempts:
                    await asyncio.sleep(0)  # yield to the loop before retrying
                    continue
                await self._report_failure(message, self.last_error, attempt)

    async def _report_failure(self, message: Message, error: str, attempt: int) -> None:
        self.bus.publish(
            Topics.ERRORS,
            Message(
                type=MessageType.ERROR,
                sender=self.name,
                topic=Topics.ERRORS,
                payload={
                    "correlation_id": message.correlation_id,
                    "failed_phase": self.name,
                    "error": error,
                    "attempt": attempt,
                },
            ),
        )

    async def handle(self, message: Message) -> None:
        """Process one envelope. Subclasses implement this."""
        raise NotImplementedError(f"{self.__class__.__name__} does not implement handle()")

    def metrics(self) -> dict:
        """Runtime health snapshot used by the reporter."""
        return {
            "agent": self.name,
            "processed": self.processed,
            "failures": self.failures,
            "last_error": self.last_error,
        }
