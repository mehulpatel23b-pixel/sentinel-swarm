"""Shared fixtures and helpers for the Sentinel Swarm test suite."""

import asyncio

import pytest

from sentinel_swarm import EventBus, MessageType


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


def run(coro):
    """Run a coroutine to completion (keeps the suite plugin-free)."""
    return asyncio.run(coro)


def make_message(sender: str = "test", payload=None):
    from sentinel_swarm.messages import Message

    return Message(type=MessageType.TASK, sender=sender, topic="test.topic", payload=payload or {})
