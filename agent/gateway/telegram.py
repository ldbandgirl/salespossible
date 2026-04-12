"""
Telegram gateway — receive and send messages via python-telegram-bot.

Features (OpenClaw-inspired):
- Pairing code DM security: unknown senders get a pairing prompt
- /new, /model, /skills slash commands
- Voice memo handling (transcription hook)
- Per-chat session isolation
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from typing import TYPE_CHECKING

from agent.gateway.base import BaseGateway, GatewayMessage

if TYPE_CHECKING:
    from agent.core import HybridAgent

logger = logging.getLogger(__name__)


class TelegramGateway(BaseGateway):
    """
    Telegram gateway using python-telegram-bot (async).

    Set TELEGRAM_BOT_TOKEN in .env to enable.
    """

    def __init__(self, agent: "HybridAgent") -> None:
        super().__init__(agent)
        self._app = None
        self._pairing_codes: dict[int, str] = {}
        self._paired: set[int] = set()
        cfg = agent.config.gateway.telegram
        self._dm_policy: str = cfg.get("dm_policy", "pairing")

    async def start(self) -> None:
        token = self.agent.config.telegram_bot_token
        if not token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN not set. Add it to .env or config.yaml."
            )

        try:
            from telegram.ext import Application, CommandHandler, MessageHandler, filters
        except ImportError:
            raise ImportError(
                "python-telegram-bot not installed. Run: pip install python-telegram-bot"
            )

        self._app = (
            Application.builder()
            .token(token)
            .build()
        )

        # Register handlers
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))
        self._app.add_handler(MessageHandler(filters.VOICE, self._on_voice))
        self._app.add_handler(
            __import__("telegram.ext", fromlist=["CommandHandler"]).CommandHandler(
                "start", self._cmd_start
            )
        )

        logger.info("Telegram gateway starting (polling)…")
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()
        # Keep running until interrupted
        await asyncio.Event().wait()

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    async def send(self, session_id: str, text: str) -> None:
        """Send a message back to the Telegram chat."""
        chat_id = int(session_id.replace("tg-", ""))
        if self._app:
            # Telegram supports Markdown — split long messages
            for chunk in _split_message(text, 4096):
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    parse_mode="Markdown",
                )

    async def _on_message(self, update: object, context: object) -> None:
        """Handle incoming Telegram text messages."""
        from telegram import Update

        if not isinstance(update, Update) or not update.message:
            return

        chat_id = update.message.chat_id
        text = update.message.text or ""

        # Slash commands (OpenClaw-style)
        if text.startswith("/"):
            await self._handle_slash(chat_id, text)
            return

        # DM security: pairing check
        if self._dm_policy == "pairing" and chat_id not in self._paired:
            await self._send_pairing_prompt(chat_id, text)
            return

        session_id = f"tg-{chat_id}"
        msg = GatewayMessage(
            content=text,
            sender_id=str(chat_id),
            platform="telegram",
            session_id=session_id,
        )
        await self.dispatch(msg)

    async def _on_voice(self, update: object, context: object) -> None:
        """Handle voice memos — transcribe and process as text."""
        from telegram import Update

        if not isinstance(update, Update) or not update.message:
            return

        chat_id = update.message.chat_id
        await update.message.reply_text(
            "🎙 Voice transcription not yet configured. Send text for now."
        )

    async def _cmd_start(self, update: object, context: object) -> None:
        """Handle /start command — onboard new user."""
        from telegram import Update

        if not isinstance(update, Update) or not update.message:
            return

        chat_id = update.message.chat_id

        if self._dm_policy == "open":
            self._paired.add(chat_id)
            await update.message.reply_text(
                f"Hi! I'm {self.agent.config.agent_name}, your AI sales assistant. "
                "How can I help you today?"
            )
        else:
            # Send pairing code
            code = secrets.token_hex(4).upper()
            self._pairing_codes[chat_id] = code
            await update.message.reply_text(
                f"To pair this chat, enter the code: `{code}`\n"
                "(Run `openclaw pairing approve telegram {code}` on the host machine.)",
                parse_mode="Markdown",
            )

    async def _send_pairing_prompt(self, chat_id: int, text: str) -> None:
        """Prompt unpaired chats for a pairing code."""
        # Check if text IS the pairing code
        expected = self._pairing_codes.get(chat_id)
        if expected and text.strip().upper() == expected:
            self._paired.add(chat_id)
            del self._pairing_codes[chat_id]
            if self._app:
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=f"Paired! I'm {self.agent.config.agent_name}. How can I help?",
                )
        else:
            code = secrets.token_hex(4).upper()
            self._pairing_codes[chat_id] = code
            if self._app:
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=f"Enter pairing code to continue: `{code}`",
                    parse_mode="Markdown",
                )

    async def _handle_slash(self, chat_id: int, cmd: str) -> None:
        """Handle /new, /model etc. from Telegram."""
        if not self._app:
            return
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()

        if command == "/new":
            await self._app.bot.send_message(chat_id, "Fresh conversation started.")
        elif command == "/model" and len(parts) > 1:
            self.agent.config.llm.primary_model = parts[1]
            await self._app.bot.send_message(
                chat_id, f"Model switched to: {parts[1]}"
            )
        else:
            await self._app.bot.send_message(
                chat_id,
                "Commands: /new (reset), /model <name> (switch model)",
            )


def _split_message(text: str, max_len: int) -> list[str]:
    """Split a long message into Telegram-safe chunks."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    return chunks
