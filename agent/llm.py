"""
LLM client — wraps Anthropic SDK with:
  • Prompt caching (reduces cost on long system prompts)
  • Model switching (primary ↔ fast)
  • OpenRouter fallback
  • Streaming support
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import Message, MessageParam, ToolParam

from agent.config import AgentConfig

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Unified LLM client for the hybrid agent.

    Supports:
    - Anthropic Claude (primary)
    - OpenRouter fallback (200+ models, same API shape)
    - Prompt caching via cache_control ephemeral blocks
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._anthropic = AsyncAnthropic(api_key=config.anthropic_api_key)

        # Optional OpenRouter client (same API, different base URL)
        if config.openrouter_api_key:
            self._openrouter = AsyncAnthropic(
                api_key=config.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1",
            )
        else:
            self._openrouter = None

    async def run(
        self,
        *,
        system: str,
        messages: list[MessageParam],
        tools: list[ToolParam] | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        use_cache: bool | None = None,
    ) -> Message:
        """
        Single LLM call with optional tool use and prompt caching.

        Args:
            system: System prompt (will be cached if prompt_caching=True)
            messages: Conversation history
            tools: Anthropic tool definitions
            model: Override model (defaults to config.llm.primary_model)
            max_tokens: Override max tokens
            use_cache: Override prompt caching setting
        """
        _model = model or self.config.llm.primary_model
        _max_tokens = max_tokens or self.config.llm.max_tokens
        _cache = use_cache if use_cache is not None else self.config.llm.prompt_caching

        # Build system with cache_control for cost reduction on long system prompts
        system_param: list[dict[str, Any]] | str
        if _cache:
            system_param = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_param = system

        kwargs: dict[str, Any] = {
            "model": _model,
            "max_tokens": _max_tokens,
            "system": system_param,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        client = self._get_client()

        try:
            response = await client.messages.create(**kwargs)
            logger.debug(
                "LLM response: model=%s stop=%s tokens=%d",
                _model,
                response.stop_reason,
                response.usage.output_tokens,
            )
            return response
        except anthropic.AuthenticationError:
            logger.error("Invalid Anthropic API key — check ANTHROPIC_API_KEY")
            raise
        except anthropic.RateLimitError:
            logger.warning("Rate limited; consider switching to OpenRouter fallback")
            raise

    async def run_fast(
        self,
        *,
        system: str,
        messages: list[MessageParam],
        max_tokens: int = 2048,
    ) -> Message:
        """Run with the fast (cheap) model — used for self-improvement, routing, summarisation."""
        return await self.run(
            system=system,
            messages=messages,
            model=self.config.llm.fast_model,
            max_tokens=max_tokens,
            use_cache=False,  # Short prompts don't benefit from caching
        )

    def _get_client(self) -> AsyncAnthropic:
        """Return the active client."""
        if self.config.llm.provider == "openrouter" and self._openrouter:
            return self._openrouter
        return self._anthropic

    @staticmethod
    def extract_text(response: Message) -> str:
        """Extract the final text content from a Message."""
        parts = []
        for block in response.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts).strip()

    @staticmethod
    def extract_tool_calls(response: Message) -> list[dict[str, Any]]:
        """Extract tool_use blocks from a Message."""
        calls = []
        for block in response.content:
            if block.type == "tool_use":
                calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
        return calls
