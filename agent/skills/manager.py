"""
SkillsManager — orchestrates skill loading, trigger dispatch, and self-improvement.

Combines:
- OpenClaw: skill-as-markdown, trigger matching, skill registry
- Hermes: auto-create skills from sessions, self-improve via LLM
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent.skills.loader import Skill, SkillsLoader

if TYPE_CHECKING:
    from agent.config import AgentConfig
    from agent.llm import LLMClient

logger = logging.getLogger(__name__)


class SkillsManager:
    """
    Manages the full skill lifecycle:
    1. Load skills from SKILL.md files
    2. Match triggers against user input
    3. Track triggered skills for memory & self-improvement
    4. Hermes loop: auto-create and auto-improve skills
    """

    def __init__(self, config: "AgentConfig") -> None:
        self.config = config
        self._loader = SkillsLoader(Path(config.skills_dir))
        self._skills: dict[str, Skill] = {}
        self._last_triggered: list[str] = []
        self._reload()

    def _reload(self) -> None:
        self._skills = self._loader.load_all()
        logger.info("Loaded %d skills", len(self._skills))

    # ── Trigger Matching (OpenClaw-style) ─────────────────────────────────────

    def match_triggers(self, user_input: str) -> list[Skill]:
        """Return skills whose trigger keywords appear in the user input."""
        lower = user_input.lower()
        matched = []
        for skill in self._skills.values():
            for trigger in skill.triggers:
                if trigger.lower() in lower:
                    matched.append(skill)
                    break
        self._last_triggered = [s.name for s in matched]
        return matched

    def get_last_triggered_skills(self) -> list[str]:
        return list(self._last_triggered)

    def get_all_skills(self) -> dict[str, Skill]:
        self._reload()
        return self._skills

    # ── Hermes: Auto-Create Skill from Session ─────────────────────────────────

    async def maybe_create_skill(
        self,
        user_input: str,
        agent_response: str,
        llm: "LLMClient",
    ) -> bool:
        """
        After a complex session, ask the fast model if this should become a skill.
        If yes, generate and save a new SKILL.md.
        """
        if len(user_input.split()) < 15:
            return False  # Too simple to be a skill

        response = await llm.run_fast(
            system=_SKILL_CREATE_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"User request: {user_input}\n\n"
                        f"Agent response (summary): {agent_response[:500]}"
                    ),
                }
            ],
            max_tokens=1200,
        )

        from agent.llm import LLMClient
        text = LLMClient.extract_text(response).strip()

        if text.lower().startswith("no"):
            return False

        # Parse the generated SKILL.md
        from agent.skills.loader import SkillsLoader
        import re, yaml as _yaml

        match = re.match(r"```(?:yaml|markdown)?\n?(---.*?---\n.*?)```", text, re.DOTALL)
        skill_md = match.group(1) if match else text

        # Write to generated skills directory
        gen_dir = Path(self.config.skills.generated_dir)
        gen_dir.mkdir(parents=True, exist_ok=True)

        # Extract skill name from frontmatter
        name_match = re.search(r"name:\s*(\S+)", skill_md)
        skill_name = name_match.group(1) if name_match else "auto_skill"

        skill_path = gen_dir / skill_name / "SKILL.md"
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(skill_md)

        logger.info("Auto-created skill: %s", skill_name)
        self._reload()
        return True

    # ── Hermes: Self-Improve Skill ─────────────────────────────────────────────

    async def maybe_improve_skill(
        self,
        skill_name: str,
        user_input: str,
        agent_response: str,
        llm: "LLMClient",
    ) -> bool:
        """
        After a successful session that triggered a skill, consider improving it.
        Only runs if the skill has been triggered >= improvement_threshold times.
        """
        from agent.memory.persistent import PersistentMemory
        from agent.config import AgentConfig

        skill = self._skills.get(skill_name)
        if not skill or not skill.auto_improve or not skill.file_path:
            return False

        # Check trigger count in DB
        # (SkillsManager doesn't hold a DB ref — use a lightweight check)
        threshold = self.config.skills.improvement_threshold

        response = await llm.run_fast(
            system=_SKILL_IMPROVE_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Current SKILL.md instructions:\n{skill.instructions}\n\n"
                        f"Recent successful session:\n"
                        f"User: {user_input}\n"
                        f"Agent: {agent_response[:600]}\n\n"
                        "Return ONLY the improved instructions (the body after frontmatter). "
                        "If no improvement needed, reply with exactly: NO_CHANGE"
                    ),
                }
            ],
            max_tokens=1000,
        )

        from agent.llm import LLMClient
        improved = LLMClient.extract_text(response).strip()

        if improved == "NO_CHANGE" or not improved:
            return False

        # Write improved instructions back to file
        skill.instructions = improved
        new_version = skill.version + 1
        skill.version = new_version
        skill.file_path.write_text(skill.render_skill_md())

        logger.info("Improved skill %s → v%d", skill_name, new_version)
        self._reload()
        return True


# ── Prompts ───────────────────────────────────────────────────────────────────

_SKILL_CREATE_SYSTEM = """\
You are a skill curator for an AI sales agent.
Given a conversation, decide if it represents a reusable workflow that should
become a skill (a saved procedure the agent can invoke in future sessions).

If YES, generate a complete SKILL.md in this format:
```
---
name: snake_case_name
description: One-sentence description
triggers:
  - keyword1
  - keyword2
tools:
  - tool_name
version: 1
auto_improve: true
---

# Skill Title

Step-by-step instructions for executing this skill...
```

If NO, reply with: no
"""

_SKILL_IMPROVE_SYSTEM = """\
You are a skill optimizer for an AI sales agent.
Given the current skill instructions and a recent successful session,
suggest concise improvements to make the skill more effective.

Rules:
- Keep improvements minimal and targeted
- Do NOT change the overall structure
- If the instructions are already optimal, reply with exactly: NO_CHANGE
- Return ONLY the improved instruction body (no frontmatter, no code fences)
"""
