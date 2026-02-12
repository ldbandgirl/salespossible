# SalesOps Multi-Account AI Agent (Starter)

This repository contains a starter implementation of an AI-powered sales operations manager agent that can:

- Manage tasks across multiple customer accounts.
- Delegate work to account owners and specialists.
- Follow up on overdue/in-progress tasks.
- Generate manager-facing status updates.
- Answer questions about task progress.

## What this starter includes

- A lightweight in-memory domain model for accounts, users, and tasks.
- `SalesOpsAgent` orchestration logic for delegation, follow-ups, manager updates, and Q&A.
- A small demo script to show end-to-end usage.
- Unit tests for core behaviors.

## Structure

- `salesops_agent/models.py` — Data models.
- `salesops_agent/agent.py` — Main agent logic.
- `demo.py` — Example usage.
- `tests/test_agent.py` — Unit tests.

## Run the demo

```bash
python demo.py
```

## Run tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

## How to extend for production

1. Replace in-memory stores with a database and/or CRM integrations (Salesforce, HubSpot, etc.).
2. Add identity/permissions per account and manager role.
3. Integrate real messaging channels (Slack/Teams/email) for delegation and follow-ups.
4. Connect an LLM + RAG over task history for richer question answering.
5. Add scheduling/event-driven follow-up workers.
