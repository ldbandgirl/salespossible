"""
HybridAgent — Core agentic loop combining OpenClaw and Hermes patterns.

OpenClaw contributions:
  • SOUL.md / STYLE.md / MEMORY.md identity system loaded as context
  • Skill-as-markdown (SKILL.md) dispatched via trigger matching
  • Multi-platform gateway abstraction

Hermes contributions:
  • Self-improving skill loop (skills created & improved from sessions)
  • SQLite + FTS5 persistent memory with cross-session recall
  • Subagent spawning for parallel workstreams
  • Cron/scheduling integration
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from anthropic.types import MessageParam, ToolResultBlockParam, ToolUseBlock

from agent.config import AgentConfig
from agent.llm import LLMClient
from agent.memory.context_loader import ContextLoader
from agent.memory.persistent import PersistentMemory
from agent.skills.manager import SkillsManager
from agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class HybridAgent:
    """
    OpenClaw × Hermes Hybrid AI Agent.

    The agent maintains:
    - An identity (SOUL.md) loaded on every session
    - Persistent memory (SQLite FTS5) for cross-session recall
    - A skills library (SKILL.md files) that can be triggered and self-improved
    - A tool registry for browser, CRM, email, search, code execution
    - A multi-platform gateway for messaging
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.llm = LLMClient(config)
        self.memory = PersistentMemory(config.db_path)
        self.context_loader = ContextLoader(config)
        self.skills = SkillsManager(config)
        self.tools = ToolRegistry(config)
        self._gateway: Any = None
        self._session_turn_count: dict[str, int] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    async def start(self, gateway_name: str = "cli") -> None:
        """Start the agent with the specified gateway."""
        from agent.gateway.cli import CLIGateway
        from agent.gateway.telegram import TelegramGateway

        gateway_map = {
            "cli": CLIGateway,
            "telegram": TelegramGateway,
        }

        cls = gateway_map.get(gateway_name)
        if cls is None:
            raise ValueError(f"Unknown gateway: {gateway_name!r}")

        self._gateway = cls(self)
        logger.info("Starting %s gateway…", gateway_name)
        await self._gateway.start()

    async def run_session(
        self,
        user_input: str,
        session_id: str | None = None,
    ) -> str:
        """
        Process one user message and return the agent's response.

        This is the main entry point for all gateways.
        """
        session_id = session_id or str(uuid.uuid4())

        # ── 1. Load context (SOUL.md + MEMORY.md + skill instructions) ───────
        system_prompt = await self.context_loader.build_system_prompt(
            session_id=session_id,
            user_input=user_input,
        )

        # ── 2. Retrieve relevant past sessions (Hermes FTS recall) ───────────
        past = await self.memory.search(user_input, top_k=self.config.memory.recall_top_k)
        recall_block = _format_recall(past)

        # ── 3. Build initial messages list ───────────────────────────────────
        messages: list[MessageParam] = []
        if recall_block:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"<past_context>\n{recall_block}\n</past_context>\n\n{user_input}"
                    ),
                }
            )
        else:
            messages.append({"role": "user", "content": user_input})

        # ── 4. Agentic tool-use loop ──────────────────────────────────────────
        response_text = await self._agent_loop(system_prompt, messages, session_id)

        # ── 5. Persist session to SQLite ──────────────────────────────────────
        tools_used = self.tools.get_last_used_tools()
        skills_triggered = self.skills.get_last_triggered_skills()

        await self.memory.save_session(
            session_id=session_id,
            user_input=user_input,
            agent_response=response_text,
            tools_used=tools_used,
            skills_triggered=skills_triggered,
        )

        # ── 6. Hermes self-improvement nudge ──────────────────────────────────
        turn = self._session_turn_count.get(session_id, 0) + 1
        self._session_turn_count[session_id] = turn

        if self.config.self_improve.enabled:
            asyncio.create_task(
                self._maybe_improve(session_id, user_input, response_text, turn)
            )

        return response_text

    # ── Agentic Loop ──────────────────────────────────────────────────────────

    async def _agent_loop(
        self,
        system: str,
        messages: list[MessageParam],
        session_id: str,
    ) -> str:
        """
        Core agentic loop with multi-step tool execution.

        Continues until the model issues end_turn (no more tool calls).
        """
        tool_defs = self.tools.get_anthropic_tool_definitions()
        max_iterations = 10  # Safety ceiling

        for iteration in range(max_iterations):
            response = await self.llm.run(
                system=system,
                messages=messages,
                tools=tool_defs if tool_defs else None,
            )

            if response.stop_reason == "end_turn":
                return LLMClient.extract_text(response)

            if response.stop_reason == "tool_use":
                tool_calls = LLMClient.extract_tool_calls(response)
                logger.info(
                    "Session %s iter %d: executing %d tool(s): %s",
                    session_id[:8],
                    iteration,
                    len(tool_calls),
                    [t["name"] for t in tool_calls],
                )

                # Execute all tool calls (may be parallel)
                tool_results = await self._execute_tools(tool_calls, session_id)

                # Append assistant turn + tool results to messages
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
                continue

            # Unexpected stop reason — return whatever text we have
            logger.warning("Unexpected stop_reason: %s", response.stop_reason)
            return LLMClient.extract_text(response)

        logger.warning("Agent loop hit max_iterations (%d)", max_iterations)
        return LLMClient.extract_text(response)  # type: ignore[reportPossiblyUnbound]

    async def _execute_tools(
        self,
        tool_calls: list[dict[str, Any]],
        session_id: str,
    ) -> list[ToolResultBlockParam]:
        """Execute tool calls, potentially in parallel."""
        tasks = [
            self.tools.execute(call["name"], call["input"], session_id)
            for call in tool_calls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        tool_results: list[ToolResultBlockParam] = []
        for call, result in zip(tool_calls, results):
            if isinstance(result, Exception):
                content = f"Error: {result}"
                is_error = True
            else:
                content = str(result)
                is_error = False

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call["id"],
                    "content": content,
                    "is_error": is_error,
                }
            )

        return tool_results

    # ── Hermes Self-Improvement ────────────────────────────────────────────────

    async def _maybe_improve(
        self,
        session_id: str,
        user_input: str,
        agent_response: str,
        turn: int,
    ) -> None:
        """
        Hermes-style: after N turns, nudge the agent to update MEMORY.md
        and improve any triggered skills.
        """
        interval = self.config.self_improve.memory_nudge_interval

        # Memory nudge every N turns
        if turn % interval == 0:
            await self._nudge_memory_update(session_id)

        # Skill self-improvement
        triggered = self.skills.get_last_triggered_skills()
        for skill_name in triggered:
            await self.skills.maybe_improve_skill(
                skill_name=skill_name,
                user_input=user_input,
                agent_response=agent_response,
                llm=self.llm,
            )

        # Auto-create skill if session was complex
        if self.config.skills.auto_create and len(user_input.split()) > 20:
            await self.skills.maybe_create_skill(
                user_input=user_input,
                agent_response=agent_response,
                llm=self.llm,
            )

    async def _nudge_memory_update(self, session_id: str) -> None:
        """Ask the fast model to update MEMORY.md with new user facts."""
        from pathlib import Path

        memory_path = Path(self.config.soul_dir) / "MEMORY.md"
        current_memory = memory_path.read_text() if memory_path.exists() else ""

        recent = await self.memory.get_recent_sessions(limit=10)
        if not recent:
            return

        recent_text = "\n\n".join(
            f"User: {s['user_input']}\nAgent: {s['agent_response'][:200]}"
            for s in recent
        )

        response = await self.llm.run_fast(
            system=(
                "You are a memory curator for an AI sales agent. "
                "Given recent conversation history, update the MEMORY.md to reflect "
                "new facts about the user, their company, deals, and preferences. "
                "Keep it under 100 lines. Return ONLY the updated MEMORY.md content."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Current MEMORY.md:\n{current_memory}\n\n"
                        f"Recent sessions:\n{recent_text}\n\n"
                        "Return the updated MEMORY.md:"
                    ),
                }
            ],
        )

        updated = LLMClient.extract_text(response)
        if updated:
            memory_path.parent.mkdir(parents=True, exist_ok=True)
            memory_path.write_text(updated)
            logger.info("MEMORY.md updated via self-improvement nudge")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_recall(past_sessions: list[dict[str, Any]]) -> str:
    """Format past sessions for injection into the user message."""
    if not past_sessions:
        return ""
    lines = []
    for s in past_sessions[:3]:  # Limit to 3 most relevant
        lines.append(
            f"[{s.get('created_at', 'past')}]\n"
            f"User: {s['user_input']}\n"
            f"Agent: {s['agent_response'][:300]}"
        )
    return "\n\n---\n\n".join(lines)
