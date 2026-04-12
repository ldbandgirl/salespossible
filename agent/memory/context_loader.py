"""
ContextLoader — loads SOUL.md, STYLE.md, MEMORY.md and active skills
into the system prompt (OpenClaw identity pattern).

The system prompt has three sections:
  1. Identity   — SOUL.md (who the agent is)
  2. Style      — STYLE.md (how the agent communicates)
  3. Memory     — MEMORY.md (persistent facts about the user)
  4. Skills     — triggered skill instructions appended per-session
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.config import AgentConfig

logger = logging.getLogger(__name__)

SYSTEM_TEMPLATE = """\
{soul}

---

{style}

---

{memory}

---

## Active Skills
{skills}

---

## Today
Date: {date}
"""


class ContextLoader:
    """
    Assembles the system prompt from identity + memory + skill files.

    Cached in-process; re-reads files on each call so live edits are picked up.
    """

    def __init__(self, config: "AgentConfig") -> None:
        self.config = config
        self._soul_dir = Path(config.soul_dir)

    async def build_system_prompt(
        self,
        session_id: str,
        user_input: str,
    ) -> str:
        """Return the full system prompt for this session."""
        from datetime import date

        soul = self._read("SOUL.md", _DEFAULT_SOUL)
        style = self._read("STYLE.md", _DEFAULT_STYLE)
        memory = self._read("MEMORY.md", "*(No persistent memory yet.)*")

        # Load any skill instructions relevant to this input
        skill_instructions = self._load_skill_instructions(user_input)

        return SYSTEM_TEMPLATE.format(
            soul=soul,
            style=style,
            memory=memory,
            skills=skill_instructions or "*(No skill active for this request.)*",
            date=date.today().isoformat(),
        )

    def _read(self, filename: str, default: str = "") -> str:
        path = self._soul_dir / filename
        if path.exists():
            return path.read_text().strip()
        logger.debug("Context file %s not found, using default", filename)
        return default

    def _load_skill_instructions(self, user_input: str) -> str:
        """
        Find skills triggered by the user's input and return their instructions.
        (Trigger matching is keyword-based; fuzzy matching is in skills/manager.py.)
        """
        from agent.skills.loader import SkillsLoader

        loader = SkillsLoader(Path(self.config.skills_dir))
        skills = loader.load_all()

        triggered = []
        lower_input = user_input.lower()

        for skill in skills.values():
            for trigger in skill.triggers:
                if trigger.lower() in lower_input:
                    triggered.append(skill)
                    break

        if not triggered:
            return ""

        parts = []
        for skill in triggered:
            parts.append(f"### Skill: {skill.name}\n\n{skill.instructions}")

        return "\n\n".join(parts)


# ── Sensible defaults if soul files don't exist yet ──────────────────────────

_DEFAULT_SOUL = """\
# Identity

You are Alex, a sharp and empathetic AI sales assistant.
You help sales professionals close more deals by doing research,
drafting outreach, managing pipeline, and preparing for calls.

You think in outcomes, not tasks. You're direct, data-driven, and
always focused on the next step that moves a deal forward.
"""

_DEFAULT_STYLE = """\
# Communication Style

- Be concise and action-oriented. Lead with the key point.
- Use plain language. Avoid jargon unless the user uses it first.
- When presenting data, use tables or bullet points.
- For drafts (emails, proposals), wrap in a code block for easy copying.
- Ask one clarifying question at a time — not a list of five.
"""
