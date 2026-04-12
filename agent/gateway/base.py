"""
Base gateway — abstract contract for all messaging platforms.

OpenClaw uses a WebSocket control plane; we adapt that pattern into
a Python ABC so each platform can implement it cleanly.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent.core import HybridAgent


@dataclass
class GatewayMessage:
    """A normalised message received from any platform."""

    content: str
    sender_id: str
    platform: str
    session_id: str
    reply_to: str | None = None
    attachments: list[Any] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"GatewayMessage(platform={self.platform!r}, "
            f"sender={self.sender_id!r}, "
            f"content={self.content[:60]!r})"
        )


class BaseGateway(ABC):
    """Abstract base for all gateways."""

    def __init__(self, agent: "HybridAgent") -> None:
        self.agent = agent
        self._queue: asyncio.Queue[GatewayMessage] = asyncio.Queue()

    @abstractmethod
    async def start(self) -> None:
        """Start listening for messages (blocking)."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stop the gateway."""
        ...

    @abstractmethod
    async def send(self, session_id: str, text: str) -> None:
        """Send a reply to the session."""
        ...

    async def dispatch(self, msg: GatewayMessage) -> None:
        """
        Called by gateway implementations when a message arrives.
        Runs the agent and sends the response back.
        """
        response = await self.agent.run_session(msg.content, msg.session_id)
        await self.send(msg.session_id, response)
