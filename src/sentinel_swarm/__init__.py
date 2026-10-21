"""Sentinel Swarm - autonomous multi-agent security operations framework."""

__version__ = "0.1.0"
__all__ = ["EventBus", "Message", "MessageType", "SentinelTeam"]

from .bus import EventBus
from .messages import Message, MessageType
from .team import SentinelTeam
