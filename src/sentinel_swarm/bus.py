"""In-memory asynchronous publish/subscribe event bus."""

from __future__ import annotations

import asyncio
from typing import Dict, KeysView, List

from .messages import Message

_SHUTDOWN = None  # sentinel pushed into every queue on close()


class EventBus:
    """A lightweight, dependency-free async message bus.

    Agents subscribe to topics and receive :class:`Message` envelopes through
    per-subscriber :class:`asyncio.Queue` objects, which keeps every agent
    isolated: a slow consumer never blocks a fast one.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, topic: str) -> asyncio.Queue:
        """Subscribe to ``topic`` and get the queue messages arrive on."""
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(topic, []).append(queue)
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        """Remove a subscriber; its queue stops receiving messages."""
        queues = self._subscribers.get(topic, [])
        if queue in queues:
            queues.remove(queue)
        if not queues and topic in self._subscribers:
            del self._subscribers[topic]

    def publish(self, topic: str, message: Message) -> None:
        """Deliver ``message`` to every current subscriber of ``topic``."""
        message.topic = topic
        for queue in self._subscribers.get(topic, []):
            queue.put_nowait(message)

    async def publish_async(self, topic: str, message: Message) -> None:
        """Coroutine-friendly alias for :meth:`publish`."""
        self.publish(topic, message)

    async def close(self) -> None:
        """Wake every consumer so agents can shut down gracefully."""
        for queues in self._subscribers.values():
            for queue in queues:
                queue.put_nowait(_SHUTDOWN)

    def subscriber_count(self, topic: str) -> int:
        return len(self._subscribers.get(topic, []))

    def topics(self) -> KeysView:
        return self._subscribers.keys()
