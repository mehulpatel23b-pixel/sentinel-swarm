"""Message envelopes used by every agent on the bus."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict


class MessageType(str, Enum):
    """Kinds of messages agents exchange."""

    TASK = "task"
    RESULT = "result"
    ERROR = "error"
    LOG = "log"
    SHUTDOWN = "shutdown"


@dataclass
class Message:
    """A single envelope travelling between agents.

    ``correlation_id`` ties every task and result back to the mission that
    produced it, so concurrent missions can share the bus safely.
    """

    type: MessageType
    sender: str
    topic: str
    payload: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(
            type=MessageType(data["type"]),
            sender=data["sender"],
            topic=data["topic"],
            payload=dict(data.get("payload", {})),
            correlation_id=data["correlation_id"],
            created_at=data.get("created_at", time.time()),
        )

    @classmethod
    def task(cls, sender: str, topic: str, payload: Dict[str, Any], correlation_id: str) -> "Message":
        return cls(type=MessageType.TASK, sender=sender, topic=topic, payload=payload, correlation_id=correlation_id)

    @classmethod
    def result(cls, sender: str, topic: str, payload: Dict[str, Any], correlation_id: str) -> "Message":
        return cls(type=MessageType.RESULT, sender=sender, topic=topic, payload=payload, correlation_id=correlation_id)
