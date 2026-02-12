from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


@dataclass
class User:
    user_id: str
    name: str
    role: str


@dataclass
class Account:
    account_id: str
    name: str
    manager_user_id: str
    members: List[str] = field(default_factory=list)


@dataclass
class Task:
    task_id: str
    account_id: str
    title: str
    description: str
    created_at: datetime
    due_at: datetime
    owner_user_id: Optional[str] = None
    status: TaskStatus = TaskStatus.OPEN
    updates: List[str] = field(default_factory=list)

    def add_update(self, message: str) -> None:
        timestamp = datetime.utcnow().isoformat(timespec="seconds")
        self.updates.append(f"[{timestamp}] {message}")
