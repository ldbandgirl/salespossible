from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from .models import Account, Task, TaskStatus, User


class SalesOpsAgent:
    """A starter orchestration layer for sales operations workflows."""

    def __init__(self) -> None:
        self.users: Dict[str, User] = {}
        self.accounts: Dict[str, Account] = {}
        self.tasks: Dict[str, Task] = {}

    def register_user(self, user: User) -> None:
        self.users[user.user_id] = user

    def register_account(self, account: Account) -> None:
        self.accounts[account.account_id] = account

    def create_task(self, task: Task) -> None:
        if task.account_id not in self.accounts:
            raise ValueError(f"Unknown account_id: {task.account_id}")
        self.tasks[task.task_id] = task

    def delegate_task(self, task_id: str, owner_user_id: str, note: str = "") -> str:
        task = self._get_task(task_id)
        if owner_user_id not in self.users:
            raise ValueError(f"Unknown user_id: {owner_user_id}")

        account = self.accounts[task.account_id]
        if owner_user_id not in account.members and owner_user_id != account.manager_user_id:
            raise ValueError("Owner is not assigned to this account")

        task.owner_user_id = owner_user_id
        task.status = TaskStatus.IN_PROGRESS
        task.add_update(f"Delegated to {owner_user_id}. {note}".strip())
        return f"Task '{task.title}' delegated to {self.users[owner_user_id].name}."

    def update_task_status(self, task_id: str, status: TaskStatus, note: str = "") -> str:
        task = self._get_task(task_id)
        task.status = status
        if note:
            task.add_update(note)
        else:
            task.add_update(f"Status updated to {status.value}")
        return f"Task '{task.title}' updated to {status.value}."

    def follow_up_messages(self, now: Optional[datetime] = None) -> List[str]:
        """Create follow-up prompts for overdue and blocked tasks."""
        now = now or datetime.utcnow()
        messages: List[str] = []

        for task in self.tasks.values():
            if task.status in {TaskStatus.DONE}:
                continue

            owner_name = self.users.get(task.owner_user_id).name if task.owner_user_id in self.users else "Unassigned"
            account_name = self.accounts[task.account_id].name

            if task.status == TaskStatus.BLOCKED:
                messages.append(
                    f"Follow-up (BLOCKED): {task.title} for {account_name} is blocked. "
                    f"Owner: {owner_name}. Please provide unblock plan by EOD."
                )
                continue

            if task.due_at < now:
                messages.append(
                    f"Follow-up (OVERDUE): {task.title} for {account_name} was due {task.due_at.date()}. "
                    f"Owner: {owner_name}. Please send ETA and recovery plan."
                )

        return messages

    def manager_update(self, manager_user_id: str) -> str:
        """Generate a manager summary across all of their accounts."""
        managed_accounts = [a for a in self.accounts.values() if a.manager_user_id == manager_user_id]
        if not managed_accounts:
            return "No accounts found for this manager."

        task_buckets: Dict[str, int] = defaultdict(int)
        lines = [f"Manager update for {self.users.get(manager_user_id, User(manager_user_id, manager_user_id, 'manager')).name}:"]

        for account in managed_accounts:
            account_tasks = [t for t in self.tasks.values() if t.account_id == account.account_id]
            open_count = sum(1 for t in account_tasks if t.status == TaskStatus.OPEN)
            in_progress_count = sum(1 for t in account_tasks if t.status == TaskStatus.IN_PROGRESS)
            blocked_count = sum(1 for t in account_tasks if t.status == TaskStatus.BLOCKED)
            done_count = sum(1 for t in account_tasks if t.status == TaskStatus.DONE)

            lines.append(
                f"- {account.name}: open={open_count}, in_progress={in_progress_count}, "
                f"blocked={blocked_count}, done={done_count}"
            )

            task_buckets["open"] += open_count
            task_buckets["in_progress"] += in_progress_count
            task_buckets["blocked"] += blocked_count
            task_buckets["done"] += done_count

        lines.append(
            "Overall totals: "
            f"open={task_buckets['open']}, in_progress={task_buckets['in_progress']}, "
            f"blocked={task_buckets['blocked']}, done={task_buckets['done']}"
        )
        return "\n".join(lines)

    def answer_question(self, question: str) -> str:
        """Simple deterministic Q&A over current task state.

        This starter supports:
        - "what is blocked"
        - "what is overdue"
        - "status for <account name>"
        """
        q = question.lower().strip()
        now = datetime.utcnow()

        if "blocked" in q:
            blocked = [t for t in self.tasks.values() if t.status == TaskStatus.BLOCKED]
            if not blocked:
                return "No blocked tasks right now."
            return "Blocked tasks: " + "; ".join(f"{t.title} ({self.accounts[t.account_id].name})" for t in blocked)

        if "overdue" in q:
            overdue = [t for t in self.tasks.values() if t.status != TaskStatus.DONE and t.due_at < now]
            if not overdue:
                return "No overdue tasks right now."
            return "Overdue tasks: " + "; ".join(f"{t.title} ({self.accounts[t.account_id].name})" for t in overdue)

        if "status for" in q:
            account_name = q.split("status for", maxsplit=1)[1].strip()
            account = self._find_account_by_name(account_name)
            if not account:
                return f"I couldn't find account '{account_name}'."
            account_tasks = [t for t in self.tasks.values() if t.account_id == account.account_id]
            if not account_tasks:
                return f"No tasks for account {account.name}."
            detail = "; ".join(f"{t.title}: {t.status.value}" for t in account_tasks)
            return f"Status for {account.name}: {detail}"

        return "I can answer about blocked tasks, overdue tasks, or status for a specific account."

    def list_tasks(self) -> Iterable[Task]:
        return self.tasks.values()

    def _get_task(self, task_id: str) -> Task:
        if task_id not in self.tasks:
            raise ValueError(f"Unknown task_id: {task_id}")
        return self.tasks[task_id]

    def _find_account_by_name(self, name: str) -> Optional[Account]:
        needle = name.lower().strip()
        for account in self.accounts.values():
            if account.name.lower() == needle:
                return account
        return None
