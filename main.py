#!/usr/bin/env python3
"""
CentrAlign AI — Autonomous Task Worker
=======================================
Main entry point. Starts the mock company app, initializes the agent
with all available tools, and runs the interactive task loop.

Usage:
    python main.py                        # Interactive mode
    python main.py "Find the latest..."   # Single task mode
    python main.py --demo                 # Run demo scenario
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich.markdown import Markdown
from rich.table import Table
from rich.logging import RichHandler

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from config import config

console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging with rich output."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )
    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def print_banner() -> None:
    """Display the startup banner."""
    banner = Text()
    banner.append("╔══════════════════════════════════════════════════════╗\n", style="bold cyan")
    banner.append("║        ", style="bold cyan")
    banner.append("CentrAlign AI", style="bold white")
    banner.append(" — Autonomous Task Worker", style="bold cyan")
    banner.append("   ║\n", style="bold cyan")
    banner.append("║          ", style="bold cyan")
    banner.append("AI employees for enterprises", style="dim white")
    banner.append("              ║\n", style="bold cyan")
    banner.append("╚══════════════════════════════════════════════════════╝", style="bold cyan")
    console.print(banner)
    console.print()


def print_result(result) -> None:
    """Display the task result in a beautiful format."""
    # Summary panel
    status = "✅ COMPLETED" if result.success else "❌ FAILED"
    style = "green" if result.success else "red"

    console.print()
    console.print(Panel(
        f"[bold]{status}[/bold]\n\n{result.summary}",
        title="[bold]Task Result[/bold]",
        border_style=style,
        padding=(1, 2),
    ))

    # Verification
    if result.verification:
        v = result.verification
        conf_bar = "█" * int(v.confidence * 20) + "░" * (20 - int(v.confidence * 20))
        v_status = "✅ Verified" if v.verified else "⚠️  Unverified"
        console.print(Panel(
            f"{v_status}\n"
            f"Confidence: [{style}]{conf_bar}[/{style}] {v.confidence:.0%}\n\n"
            f"{v.summary}",
            title="[bold]Verification[/bold]",
            border_style="blue",
            padding=(1, 2),
        ))

    # Evidence
    if result.evidence:
        console.print(Panel(
            "\n".join(f"  • {e}" for e in result.evidence),
            title="[bold]Evidence[/bold]",
            border_style="blue",
            padding=(1, 2),
        ))

    # Facts discovered
    if result.facts_discovered:
        table = Table(title="Facts Discovered", show_header=True)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        for k, v_item in result.facts_discovered.items():
            table.add_row(k, str(v_item))
        console.print(table)

    # Steps summary
    console.print(f"\n[dim]Total steps: {len(result.steps_taken)}[/dim]")


async def start_mock_app() -> None:
    """Start the mock company app in the background."""
    from mock_app.server import start_server_background
    console.print("[dim]Starting mock company portal...[/dim]", end=" ")
    await start_server_background()
    # Give server a moment to start
    await asyncio.sleep(1.5)
    console.print(f"[green]✓[/green] Running at [link={config.MOCK_APP_URL}]{config.MOCK_APP_URL}[/link]")


async def create_agent():
    """Initialize the agent with all tools."""
    from llm.provider import LLMProvider
    from tools.base import ToolRegistry
    from tools.browser_tool import (
        BrowserManager, NavigateTool, ClickTool, TypeTextTool,
        ExtractTextTool, ExtractTableTool, GetPageInfoTool, ScreenshotTool,
    )
    from tools.filesystem_tool import ReadFileTool, WriteFileTool, ListFilesTool
    from tools.api_tool import HttpRequestTool
    from agent.core import Agent

    # Initialize LLM
    llm = LLMProvider()

    # Initialize browser manager (shared across browser tools)
    browser_mgr = BrowserManager()

    # Build tool registry
    registry = ToolRegistry()
    registry.register(NavigateTool(browser_mgr))
    registry.register(ClickTool(browser_mgr))
    registry.register(TypeTextTool(browser_mgr))
    registry.register(ExtractTextTool(browser_mgr))
    registry.register(ExtractTableTool(browser_mgr))
    registry.register(GetPageInfoTool(browser_mgr))
    registry.register(ScreenshotTool(browser_mgr))
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(ListFilesTool())
    registry.register(HttpRequestTool())

    # Create agent
    agent = Agent(llm=llm, tools=registry)
    return agent


async def run_single_task(agent, task: str) -> None:
    """Run a single task and display the result."""
    console.print(Panel(
        task,
        title="[bold]Task[/bold]",
        border_style="yellow",
        padding=(1, 2),
    ))
    console.print()

    result = await agent.run(task)
    print_result(result)


async def run_interactive(agent) -> None:
    """Run the interactive task loop."""
    console.print(
        "[bold cyan]Interactive Mode[/bold cyan] — Enter tasks in natural language.\n"
        "Type [bold]quit[/bold] or [bold]exit[/bold] to stop.\n"
    )

    while True:
        try:
            task = Prompt.ask("\n[bold yellow]📋 Task[/bold yellow]")
        except (KeyboardInterrupt, EOFError):
            break

        task = task.strip()
        if not task:
            continue
        if task.lower() in ("quit", "exit", "q"):
            break

        await run_single_task(agent, task)

    console.print("\n[dim]Goodbye![/dim]")


DEMO_TASKS = [
    (
        "Find the latest invoice from Acme Corp in our internal portal, "
        "extract the amount and due date, create a new expense entry with those details, "
        "and confirm it was saved."
    ),
    (
        "Go to our internal portal and find all invoices that are overdue. "
        "List them with their vendor names and amounts."
    ),
    (
        "Look up the contact information for our Globex Industries representative "
        "in the company portal."
    ),
]


async def run_demo(agent) -> None:
    """Run the demo scenario."""
    console.print(Panel(
        "[bold]Demo Mode[/bold]\n\n"
        "Running a pre-defined scenario that demonstrates the agent's capabilities:\n"
        "• Browser navigation and data extraction\n"
        "• Form filling and submission\n"
        "• Verification of completed work\n"
        "• Memory and fact tracking",
        border_style="magenta",
        padding=(1, 2),
    ))
    console.print()

    # Run the primary demo task
    demo_task = DEMO_TASKS[0]
    await run_single_task(agent, demo_task)


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="CentrAlign AI — Autonomous Task Worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("task", nargs="?", help="Task to execute (omit for interactive mode)")
    parser.add_argument("--demo", action="store_true", help="Run the demo scenario")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    parser.add_argument("--no-mock-app", action="store_true", help="Skip starting the mock app")

    args = parser.parse_args()

    setup_logging(verbose=args.verbose)
    print_banner()

    # Validate config
    errors = config.validate()
    if errors:
        for err in errors:
            console.print(f"[red]❌ {err}[/red]")
        console.print("\n[dim]Copy .env.example to .env and configure your settings.[/dim]")
        sys.exit(1)

    # Start mock company app
    if not args.no_mock_app:
        await start_mock_app()

    # Create agent
    console.print("[dim]Initializing AI agent...[/dim]", end=" ")
    agent = await create_agent()
    console.print("[green]✓[/green] Ready")
    console.print()

    try:
        if args.demo:
            await run_demo(agent)
        elif args.task:
            await run_single_task(agent, args.task)
        else:
            await run_interactive(agent)
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
    finally:
        # Cleanup
        console.print("[dim]Cleaning up...[/dim]")
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
