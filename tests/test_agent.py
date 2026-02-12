import unittest
from datetime import datetime, timedelta

from salesops_agent import Account, SalesOpsAgent, Task, TaskStatus, User


class SalesOpsAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = SalesOpsAgent()
        self.agent.register_user(User("mgr", "Mia Manager", "manager"))
        self.agent.register_user(User("ae", "Avery AE", "ae"))
        self.agent.register_user(User("csm", "Chris CSM", "csm"))
        self.agent.register_account(Account("acc1", "Beta Inc", manager_user_id="mgr", members=["ae", "csm"]))

    def _task(self, task_id: str, title: str, due_offset_days: int) -> Task:
        return Task(
            task_id=task_id,
            account_id="acc1",
            title=title,
            description="desc",
            created_at=datetime.utcnow(),
            due_at=datetime.utcnow() + timedelta(days=due_offset_days),
        )

    def test_delegate_and_status_update(self):
        task = self._task("t1", "Call prep", 2)
        self.agent.create_task(task)

        self.agent.delegate_task("t1", "ae")
        self.assertEqual(task.owner_user_id, "ae")
        self.assertEqual(task.status, TaskStatus.IN_PROGRESS)

        self.agent.update_task_status("t1", TaskStatus.DONE, "Completed")
        self.assertEqual(task.status, TaskStatus.DONE)
        self.assertTrue(any("Completed" in u for u in task.updates))

    def test_follow_up_for_overdue_and_blocked(self):
        overdue = self._task("t2", "Overdue thing", -1)
        blocked = self._task("t3", "Blocked thing", 1)
        self.agent.create_task(overdue)
        self.agent.create_task(blocked)
        self.agent.delegate_task("t2", "ae")
        self.agent.delegate_task("t3", "csm")
        self.agent.update_task_status("t3", TaskStatus.BLOCKED, "Need legal")

        messages = self.agent.follow_up_messages()
        self.assertEqual(len(messages), 2)
        self.assertTrue(any("OVERDUE" in m for m in messages))
        self.assertTrue(any("BLOCKED" in m for m in messages))

    def test_manager_update_and_qa(self):
        t_open = self._task("t4", "Open thing", 1)
        t_blocked = self._task("t5", "Blocked thing", -2)
        self.agent.create_task(t_open)
        self.agent.create_task(t_blocked)
        self.agent.delegate_task("t5", "ae")
        self.agent.update_task_status("t5", TaskStatus.BLOCKED)

        update = self.agent.manager_update("mgr")
        self.assertIn("Beta Inc", update)
        self.assertIn("blocked=1", update)

        blocked_answer = self.agent.answer_question("what is blocked")
        self.assertIn("Blocked tasks:", blocked_answer)

        overdue_answer = self.agent.answer_question("what is overdue")
        self.assertIn("Overdue tasks:", overdue_answer)


if __name__ == "__main__":
    unittest.main()
