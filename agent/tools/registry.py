"""
ToolRegistry — registers all tools and dispatches calls from the agent loop.

Each tool is an async function that takes a dict of inputs and returns a string.
Tools are exposed to the LLM as Anthropic tool definitions.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

from agent.config import AgentConfig

logger = logging.getLogger(__name__)

# Type alias for a tool handler
ToolHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, str]]


class ToolRegistry:
    """
    Central registry mapping tool names → async handlers + Anthropic schemas.

    Tools are registered lazily based on config.tools.enabled.
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._handlers: dict[str, ToolHandler] = {}
        self._schemas: list[dict[str, Any]] = []
        self._last_used: list[str] = []
        self._register_enabled_tools()

    def _register_enabled_tools(self) -> None:
        """Register tools based on the enabled list in config."""
        enabled = set(self.config.tools.enabled)

        if "web_search" in enabled:
            from agent.tools.search_tool import web_search, WEB_SEARCH_SCHEMA
            self._register("web_search", web_search, WEB_SEARCH_SCHEMA)

        if "http_request" in enabled:
            from agent.tools.http_client import http_request, HTTP_REQUEST_SCHEMA
            self._register("http_request", http_request, HTTP_REQUEST_SCHEMA)

        if "code_exec" in enabled:
            from agent.tools.code_exec import execute_python, CODE_EXEC_SCHEMA
            self._register("execute_python", execute_python, CODE_EXEC_SCHEMA)

        if "crm" in enabled:
            from agent.tools.crm import (
                crm_lookup, crm_create_contact, crm_update_deal,
                CRM_LOOKUP_SCHEMA, CRM_CREATE_CONTACT_SCHEMA, CRM_UPDATE_DEAL_SCHEMA,
            )
            self._register("crm_lookup", crm_lookup, CRM_LOOKUP_SCHEMA)
            self._register("crm_create_contact", crm_create_contact, CRM_CREATE_CONTACT_SCHEMA)
            self._register("crm_update_deal", crm_update_deal, CRM_UPDATE_DEAL_SCHEMA)

        if "email" in enabled:
            from agent.tools.email_tool import (
                email_draft, email_send,
                EMAIL_DRAFT_SCHEMA, EMAIL_SEND_SCHEMA,
            )
            self._register("email_draft", email_draft, EMAIL_DRAFT_SCHEMA)
            self._register("email_send", email_send, EMAIL_SEND_SCHEMA)

        logger.info(
            "Registered %d tools: %s",
            len(self._handlers),
            ", ".join(self._handlers.keys()),
        )

    def _register(
        self,
        name: str,
        handler: ToolHandler,
        schema: dict[str, Any],
    ) -> None:
        self._handlers[name] = handler
        self._schemas.append(schema)

    def get_anthropic_tool_definitions(self) -> list[dict[str, Any]]:
        """Return tool definitions in Anthropic API format."""
        return self._schemas

    def get_last_used_tools(self) -> list[str]:
        return list(self._last_used)

    async def execute(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        session_id: str,
    ) -> str:
        """Execute a tool call and return its string result."""
        handler = self._handlers.get(tool_name)
        if not handler:
            return f"Unknown tool: {tool_name!r}"

        # Track usage
        if tool_name not in self._last_used:
            self._last_used.append(tool_name)

        # Check approval requirements
        if tool_name in self.config.tools.require_approval:
            logger.warning(
                "Tool %r requires approval — executing anyway (CLI mode). "
                "Implement approval UI for production.",
                tool_name,
            )

        try:
            result = await handler(tool_input)
            logger.debug("Tool %s returned %d chars", tool_name, len(result))
            return result
        except Exception as e:
            logger.error("Tool %s error: %s", tool_name, e, exc_info=True)
            return f"Tool error ({tool_name}): {e}"
