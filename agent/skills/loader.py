"""
SkillsLoader — parses SKILL.md files (OpenClaw format).

SKILL.md format:
───────────────
---
name: crm_lookup
description: Look up a contact, company, or deal in the CRM
triggers:
  - "look up"
  - "find contact"
  - "check CRM"
tools:
  - crm
  - http_request
version: 1
auto_improve: true
---

# CRM Lookup

When the user asks to find a contact or company...

Instructions go here in plain Markdown.
───────────────
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """A loaded skill with parsed frontmatter + instruction body."""

    name: str
    description: str
    triggers: list[str]
    tools: list[str]
    version: int
    auto_improve: bool
    instructions: str
    file_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "triggers": self.triggers,
            "tools": self.tools,
            "version": self.version,
            "auto_improve": self.auto_improve,
        }

    def render_skill_md(self) -> str:
        """Regenerate SKILL.md content from this object."""
        fm = yaml.dump(
            self.to_dict(),
            default_flow_style=False,
            allow_unicode=True,
        ).strip()
        return f"---\n{fm}\n---\n\n{self.instructions}\n"


class SkillsLoader:
    """
    Scans a skills directory recursively for SKILL.md files and parses them.

    Usage:
        loader = SkillsLoader(Path("skills/"))
        skills = loader.load_all()   # → {name: Skill}
    """

    def __init__(self, skills_dir: Path) -> None:
        self.skills_dir = skills_dir

    def load_all(self) -> dict[str, Skill]:
        """Load and return all skills keyed by name."""
        skills: dict[str, Skill] = {}

        if not self.skills_dir.exists():
            return skills

        for skill_file in sorted(self.skills_dir.rglob("SKILL.md")):
            skill = self._parse(skill_file)
            if skill:
                skills[skill.name] = skill
                logger.debug("Loaded skill: %s (v%d)", skill.name, skill.version)
            else:
                logger.warning("Failed to parse skill file: %s", skill_file)

        return skills

    def load_one(self, name: str) -> Skill | None:
        """Load a single skill by name."""
        for skill_file in self.skills_dir.rglob("SKILL.md"):
            skill = self._parse(skill_file)
            if skill and skill.name == name:
                return skill
        return None

    def _parse(self, path: Path) -> Skill | None:
        """Parse a single SKILL.md file."""
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.error("Cannot read %s: %s", path, e)
            return None

        # Extract YAML frontmatter between --- delimiters
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", raw, re.DOTALL)
        if not match:
            logger.warning("No YAML frontmatter in %s", path)
            return None

        try:
            fm: dict[str, Any] = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as e:
            logger.error("YAML parse error in %s: %s", path, e)
            return None

        instructions = match.group(2).strip()
        name = str(fm.get("name", path.parent.name))

        return Skill(
            name=name,
            description=str(fm.get("description", "")),
            triggers=[str(t) for t in fm.get("triggers", [])],
            tools=[str(t) for t in fm.get("tools", [])],
            version=int(fm.get("version", 1)),
            auto_improve=bool(fm.get("auto_improve", True)),
            instructions=instructions,
            file_path=path,
        )
