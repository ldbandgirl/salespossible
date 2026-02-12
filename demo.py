from datetime import datetime, timedelta

from salesops_agent import Account, SalesOpsAgent, Task, TaskStatus, User


if __name__ == "__main__":
    agent = SalesOpsAgent()

    agent.register_user(User("u_mgr", "Morgan Manager", "manager"))
    agent.register_user(User("u_ae_1", "Alex AE", "account_executive"))
    agent.register_user(User("u_csm_1", "Casey CSM", "customer_success"))

    agent.register_account(Account("a_100", "Acme Corp", manager_user_id="u_mgr", members=["u_ae_1", "u_csm_1"]))

    t1 = Task(
        task_id="t_1",
        account_id="a_100",
        title="Prepare renewal forecast",
        description="Collect usage and forecast renewal probability",
        created_at=datetime.utcnow(),
        due_at=datetime.utcnow() + timedelta(days=1),
    )
    t2 = Task(
        task_id="t_2",
        account_id="a_100",
        title="Legal redline follow-up",
        description="Push legal team for updated contract redlines",
        created_at=datetime.utcnow(),
        due_at=datetime.utcnow() - timedelta(days=2),
    )

    agent.create_task(t1)
    agent.create_task(t2)

    print(agent.delegate_task("t_1", "u_ae_1", "Prioritize before pipeline review."))
    print(agent.delegate_task("t_2", "u_csm_1", "Coordinate with procurement."))

    print(agent.update_task_status("t_2", TaskStatus.BLOCKED, "Waiting on legal response."))

    print("\n--- Follow-ups ---")
    for msg in agent.follow_up_messages():
        print(msg)

    print("\n--- Manager update ---")
    print(agent.manager_update("u_mgr"))

    print("\n--- Q&A ---")
    print(agent.answer_question("What is blocked?"))
    print(agent.answer_question("What is overdue?"))
    print(agent.answer_question("Status for Acme Corp"))
