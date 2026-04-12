"""
CLI gateway — interactive terminal interface.

Supports:
- Multiline editing
- Slash commands (/help, /new, /skills, /memory, /model, /usage)
- Streaming-style output via Rich
- Session persistence
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from agent.gateway.base import BaseGateway, GatewayMessage

if TYPE_CHECKING:
    from agent.core import HybridAgent

logger = logging.getLogger(__name__)
console = Console()

SLASH_COMMANDS = {
    "/help": "Show this help",
    "/new": "Start a fresh conversation (clear context)",
    "/skills": "List available skills",
    "/memory": "Show MEMORY.md",
    "/model [name]": "Switch LLM model",
    "/usage": "Show token/cost stats for this session",
    "/quit": "Exit the agent",
}

SESSION_ID = "cli-session"


class CLIGateway(BaseGateway):
    """Interactive CLI gateway with Rich formatting."""

    def __init__(self, agent: "HybridAgent") -> None:
        super().__init__(agent)
        self._running = False
        self._session_id = SESSION_ID
        self._prompt = agent.config.gateway.cli.get("prompt", "You → ")

    async def start(self) -> None:
        self._running = True
        console.print(
            Panel(
                "[bold green]Agent ready.[/bold green] Type [cyan]/help[/cyan] for commands.\n"
                f"[dim]Session: {self._session_id}[/dim]",
                border_style="green",
            )
        )

        while self._running:
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, self._read_input
                )
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Goodbye.[/dim]")
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                await self._handle_slash(user_input)
                continue

            msg = GatewayMessage(
                content=user_input,
                sender_id="user",
                platform="cli",
                session_id=self._session_id,
            )

            console.print("[dim]Thinking…[/dim]")
            await self.dispatch(msg)

    async def stop(self) -> None:
        self._running = False

    async def send(self, session_id: str, text: str) -> None:
        """Print agent response, rendered as Markdown."""
        console.print(
            Panel(
                Markdown(text),
                title=f"[bold cyan]{self.agent.config.agent_name}[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    def _read_input(self) -> str:
        """Read a line from stdin (blocking, run in executor)."""
        try:
            return input(self._prompt).strip()
        except EOFError:
            return "/quit"

    async def _handle_slash(self, cmd: str) -> None:
        """Handle slash commands inline."""
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if command == "/help":
            table_lines = [f"  [cyan]{k}[/cyan]  {v}" for k, v in SLASH_COMMANDS.items()]
            console.print(
                Panel("\n".join(table_lines), title="Commands", border_style="dim")
            )

        elif command in ("/new", "/reset"):
            self._session_id = f"cli-{asyncio.get_event_loop().time():.0f}"
            console.print("[dim]Fresh conversation started.[/dim]")

        elif command == "/skills":
            from agent.skills.loader import SkillsLoader
            from pathlib import Path
            from rich.table import Table

            loader = SkillsLoader(Path(self.agent.config.skills_dir))
            skills = loader.load_all()
            table = Table(border_style="dim")
            table.add_column("Skill", style="bold")
            table.add_column("Description")
            table.add_column("Triggers")
            for s in skills.values():
                table.add_row(s.name, s.description, ", ".join(s.triggers[:3]))
            console.print(table)

        elif command == "/memory":
            from pathlib import Path
            mp = Path(self.agent.config.soul_dir) / "MEMORY.md"
            if mp.exists():
                console.print(
                    Panel(mp.read_text(), title="MEMORY.md", border_style="yellow")
                )
            else:
                console.print("[dim]MEMORY.md is empty.[/dim]")

        elif command == "/model":
            if arg:
                self.agent.config.llm.primary_model = arg
                console.print(f"[green]Model switched to:[/green] {arg}")
            else:
                console.print(
                    f"Current model: [bold]{self.agent.config.llm.primary_model}[/bold]"
                )

        elif command in ("/quit", "/exit"):
            console.print("[dim]Goodbye.[/dim]")
            self._running = False
            sys.exit(0)

        else:
            console.print(f"[red]Unknown command:[/red] {command}")
