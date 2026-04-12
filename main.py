#!/usr/bin/env python3
"""
SalesPossible — OpenClaw/Hermes Hybrid AI Sales Agent
Entry-point CLI.

Usage:
    salespossible                    # Start CLI gateway (interactive)
    salespossible --gateway telegram # Start Telegram gateway
    salespossible --gateway discord  # Start Discord gateway
    salespossible setup              # Run setup wizard
    salespossible model              # Switch LLM model
    salespossible skills list        # List installed skills
    salespossible skills install <name>   # Install a skill
    salespossible memory show        # Show MEMORY.md
    salespossible run "<message>"    # One-shot message (no gateway)
"""

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

BANNER = """
  ____        _           ____                   _ _     _
 / ___|  __ _| | ___  ___|  _ \\ ___  ___ ___(_) |__  | | ___
 \\___ \\ / _` | |/ _ \\/ __| |_) / _ \\/ __/ __| | '_ \\ | |/ _ \\
  ___) | (_| | |  __/\\__ \\  __/ (_) \\__ \\__ \\ | |_) ||  |  __/
 |____/ \\__,_|_|\\___||___/_|   \\___/|___/___/_|_.__(_)|_|\\___|

  OpenClaw × Hermes Hybrid Sales Agent  •  v0.1.0
"""


def _load_agent():
    """Lazy import agent to keep CLI startup fast."""
    from agent.core import HybridAgent
    from agent.config import AgentConfig

    config = AgentConfig.load()
    return HybridAgent(config)


@click.group(invoke_without_command=True)
@click.option("--gateway", default="cli", help="Gateway to start (cli/telegram/discord)")
@click.option("--config", default=None, help="Path to config.yaml override")
@click.pass_context
def cli(ctx: click.Context, gateway: str, config: str | None) -> None:
    """SalesPossible — OpenClaw/Hermes Hybrid AI Sales Agent."""
    if ctx.invoked_subcommand is not None:
        return

    console.print(Text(BANNER, style="bold cyan"))
    console.print(
        Panel(
            f"[bold]Gateway:[/bold] {gateway}  •  "
            "[dim]Type /help for commands, Ctrl-C to exit[/dim]",
            border_style="dim",
        )
    )

    asyncio.run(_start_gateway(gateway, config))


async def _start_gateway(gateway_name: str, config_override: str | None) -> None:
    from agent.core import HybridAgent
    from agent.config import AgentConfig

    config = AgentConfig.load(config_override)
    agent = HybridAgent(config)
    await agent.start(gateway_name)


# ── Sub-commands ──────────────────────────────────────────────────────────────

@cli.command()
def setup() -> None:
    """Interactive setup wizard — configure LLM keys, gateways, CRM."""
    from agent.setup_wizard import run_setup_wizard
    asyncio.run(run_setup_wizard())


@cli.command()
@click.argument("message")
@click.option("--session-id", default="cli-oneshot", help="Session identifier")
def run(message: str, session_id: str) -> None:
    """Send a single message to the agent and print the response."""
    async def _run() -> None:
        agent = _load_agent()
        response = await agent.run_session(message, session_id)
        console.print(Panel(response, title="[bold green]Agent[/bold green]", border_style="green"))

    asyncio.run(_run())


@cli.group()
def skills() -> None:
    """Manage agent skills."""


@skills.command("list")
def skills_list() -> None:
    """List all installed skills."""
    from agent.skills.loader import SkillsLoader
    from agent.config import AgentConfig
    from rich.table import Table

    config = AgentConfig.load()
    loader = SkillsLoader(Path(config.skills_dir))
    all_skills = loader.load_all()

    table = Table(title="Installed Skills", border_style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Triggers")
    table.add_column("Tools")
    table.add_column("Ver", justify="right")

    for skill in all_skills.values():
        table.add_row(
            skill.name,
            skill.description,
            ", ".join(skill.triggers[:3]),
            ", ".join(skill.tools[:3]),
            str(skill.version),
        )

    console.print(table)


@cli.group()
def memory() -> None:
    """Inspect and manage agent memory."""


@memory.command("show")
def memory_show() -> None:
    """Display the current MEMORY.md content."""
    from agent.config import AgentConfig

    config = AgentConfig.load()
    memory_path = Path(config.soul_dir) / "MEMORY.md"
    if memory_path.exists():
        content = memory_path.read_text()
        console.print(Panel(content, title="[bold]MEMORY.md[/bold]", border_style="yellow"))
    else:
        console.print("[dim]MEMORY.md not found.[/dim]")


@memory.command("search")
@click.argument("query")
def memory_search(query: str) -> None:
    """Full-text search across session history."""
    async def _search() -> None:
        from agent.memory.persistent import PersistentMemory
        from agent.config import AgentConfig

        config = AgentConfig.load()
        mem = PersistentMemory(config.db_path)
        results = await mem.search(query, top_k=10)
        if not results:
            console.print(f"[dim]No results for '{query}'[/dim]")
            return
        for r in results:
            console.print(
                Panel(
                    f"[bold]You:[/bold] {r['user_input']}\n\n"
                    f"[bold]Agent:[/bold] {r['agent_response'][:300]}...",
                    title=f"[dim]{r['created_at']}[/dim]",
                    border_style="dim",
                )
            )

    asyncio.run(_search())


if __name__ == "__main__":
    cli()
