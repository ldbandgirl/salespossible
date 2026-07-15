"""Shared, thread-safe-enough app state surfaced to the settings web UI."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class AppState:
    """Written by the pipeline threads, read by the /api/status endpoint.

    Simple attribute reads/writes are atomic under the GIL, which is all we
    need for a status display. The shared conversation transcript (voice +
    text turns) is guarded by a lock since both the voice loop and the web
    chat endpoint append to it.
    """

    phase: str = "starting"  # starting | listening | thinking | speaking | paused | error
    paused: bool = False
    mic_level: float = 0.0
    last_heard: str = ""
    last_reply: str = ""
    last_error: str = ""
    turns: int = 0
    hermes_mode_in_use: str = ""
    started_at: float = field(default_factory=time.time)
    messages: deque = field(default_factory=lambda: deque(maxlen=200))
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _seq: int = 0

    def add_message(self, role: str, text: str, source: str) -> dict:
        """Append a turn to the shared transcript. source = voice | text."""
        with self._lock:
            self._seq += 1
            msg = {"id": self._seq, "role": role, "text": text, "source": source}
            self.messages.append(msg)
            return msg

    def transcript(self) -> list[dict]:
        with self._lock:
            return list(self.messages)

    def to_dict(self) -> dict:
        return {
            "phase": "paused" if self.paused else self.phase,
            "paused": self.paused,
            "mic_level": round(self.mic_level, 3),
            "last_heard": self.last_heard,
            "last_reply": self.last_reply,
            "last_error": self.last_error,
            "turns": self.turns,
            "hermes_mode_in_use": self.hermes_mode_in_use,
            "uptime_s": int(time.time() - self.started_at),
        }
