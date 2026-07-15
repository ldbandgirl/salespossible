"""In-memory ring buffer of recent log lines, surfaced to the settings UI.

The app runs headless on the robot, so the settings page is the only window
into what it's doing. This handler keeps the most recent log records in memory
and the /api/logs endpoint serves them to the web UI.
"""

from __future__ import annotations

import logging
from collections import deque

_handler: "RingBufferHandler | None" = None


class RingBufferHandler(logging.Handler):
    """A logging handler that retains the last `capacity` formatted records."""

    def __init__(self, capacity: int = 500) -> None:
        super().__init__()
        self.buffer: deque[str] = deque(maxlen=capacity)
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.buffer.append(self.format(record))
        except Exception:  # never let logging crash the app
            pass

    def lines(self) -> list[str]:
        return list(self.buffer)


def install(level: int = logging.INFO) -> RingBufferHandler:
    """Attach the ring buffer to the root logger (idempotent)."""
    global _handler
    if _handler is None:
        _handler = RingBufferHandler()
        root = logging.getLogger()
        root.addHandler(_handler)
        if root.level == logging.NOTSET or root.level > level:
            root.setLevel(level)
    return _handler


def get_lines() -> list[str]:
    return _handler.lines() if _handler is not None else []
