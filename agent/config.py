"""
Agent configuration — loads config.yaml and environment variables.

Priority (highest → lowest):
  1. Environment variables
  2. config.yaml overrides
  3. Defaults
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# Load .env if present
load_dotenv()


class LLMConfig(BaseModel):
    primary_model: str = "claude-sonnet-4-6"
    fast_model: str = "claude-haiku-4-5-20251001"
    provider: str = "anthropic"
    max_tokens: int = 8096
    prompt_caching: bool = True


class MemoryConfig(BaseModel):
    db_file: str = "memory.db"
    memory_md_max_lines: int = 100
    recall_top_k: int = 5
    context_files: list[str] = Field(
        default_factory=lambda: ["soul/SOUL.md", "soul/STYLE.md", "soul/MEMORY.md"]
    )


class SkillsConfig(BaseModel):
    directory: str = "skills/"
    auto_create: bool = True
    improvement_threshold: int = 5
    generated_dir: str = "skills/_generated/"


class ToolsConfig(BaseModel):
    enabled: list[str] = Field(
        default_factory=lambda: ["web_search", "http_request", "code_exec", "crm", "email"]
    )
    require_approval: list[str] = Field(
        default_factory=lambda: ["email_send", "crm_write"]
    )


class GatewayConfig(BaseModel):
    active: list[str] = Field(default_factory=lambda: ["cli"])
    cli: dict[str, Any] = Field(default_factory=lambda: {"prompt": "You → ", "multiline": False})
    telegram: dict[str, Any] = Field(default_factory=lambda: {"dm_policy": "pairing"})
    discord: dict[str, Any] = Field(default_factory=lambda: {"prefix": "!"})


class CRMConfig(BaseModel):
    provider: str = "mock"


class SelfImproveConfig(BaseModel):
    enabled: bool = True
    memory_nudge_interval: int = 10
    model: str = "claude-haiku-4-5-20251001"


class AgentConfig(BaseModel):
    """Top-level configuration object for the Hybrid Agent."""

    # Agent identity
    agent_name: str = "Alex"
    data_dir: Path = Path("~/.salespossible").expanduser()
    log_level: str = "INFO"

    # API keys (from env)
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""
    telegram_bot_token: str = ""
    discord_bot_token: str = ""
    hubspot_api_key: str = ""

    # Sub-configs
    llm: LLMConfig = Field(default_factory=LLMConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    crm: CRMConfig = Field(default_factory=CRMConfig)
    self_improve: SelfImproveConfig = Field(default_factory=SelfImproveConfig)

    # Derived paths (set after init)
    db_path: Path = Path("~/.salespossible/memory.db")
    soul_dir: str = "soul"
    skills_dir: str = "skills/"

    @classmethod
    def load(cls, config_path: str | None = None) -> "AgentConfig":
        """Load config from YAML file + environment variables."""
        raw: dict[str, Any] = {}

        # 1. Read YAML
        yaml_path = Path(config_path or "config.yaml")
        if yaml_path.exists():
            with yaml_path.open() as f:
                raw = yaml.safe_load(f) or {}

        # 2. Build sub-config dicts
        agent_raw = raw.get("agent", {})
        data_dir = Path(agent_raw.get("data_dir", "~/.salespossible")).expanduser()
        data_dir.mkdir(parents=True, exist_ok=True)

        db_file = raw.get("memory", {}).get("db_file", "memory.db")

        config = cls(
            agent_name=agent_raw.get("name", "Alex"),
            data_dir=data_dir,
            log_level=agent_raw.get("log_level", "INFO"),
            # API keys from environment
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            discord_bot_token=os.environ.get("DISCORD_BOT_TOKEN", ""),
            hubspot_api_key=os.environ.get("HUBSPOT_API_KEY", ""),
            # Sub-configs from YAML
            llm=LLMConfig(**raw.get("llm", {})),
            memory=MemoryConfig(**raw.get("memory", {})),
            skills=SkillsConfig(**raw.get("skills", {})),
            tools=ToolsConfig(**raw.get("tools", {})),
            gateway=GatewayConfig(**raw.get("gateway", {})),
            crm=CRMConfig(**raw.get("crm", {})),
            self_improve=SelfImproveConfig(**raw.get("self_improve", {})),
            # Derived
            db_path=data_dir / db_file,
            soul_dir="soul",
            skills_dir=raw.get("skills", {}).get("directory", "skills/"),
        )
        return config
