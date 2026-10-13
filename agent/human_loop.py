"""
Human-in-the-loop approval and interaction system for the Autonomous AI Task Worker.
Provides formatted CLI interaction using the Rich library.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from config import config

logger = logging.getLogger(__name__)


class HumanApprovalSystem:
    """Manages human-in-the-loop interactions via CLI."""

    def __init__(
        self,
        console: Console | None = None,
        auto_approve_all: bool = False,
        interactive: bool | None = None,
    ) -> None:
        """
        Initialize the human approval system.

        Args:
            console: Optional Rich console instance.
            auto_approve_all: If True, bypass prompts and approve all actions.
            interactive: Whether running in an interactive terminal. Defaults to auto-detect.
        """
        self.console = console or Console()
        self.auto_approve_all = auto_approve_all
        if interactive is not None:
            self._interactive = interactive
        else:
            self._interactive = sys.stdin.isatty()

    def ask_approval(
        self,
        action_description: str,
        risk_level: str = "medium",
        context: dict[str, Any] | None = None,
    ) -> bool:
        """
        Prompt the user for approval to execute an action.

        Args:
            action_description: Detailed description of the action to be taken.
            risk_level: 'low', 'medium', or 'high'.
            context: Optional dictionary of additional parameters or metadata.

        Returns:
            True if approved, False otherwise.
        """
        risk_level_normalized = risk_level.strip().lower()

        # Check auto-approve condition:
        # Low risk actions are auto-approved if config.HUMAN_APPROVAL_REQUIRED is False
        if risk_level_normalized == "low" and not config.HUMAN_APPROVAL_REQUIRED:
            logger.info("Auto-approved low risk action: %s", action_description)
            return True

        if self.auto_approve_all:
            logger.info("Auto-approved (auto_approve_all active): %s", action_description)
            return True

        # Non-interactive fallback: if running headless or in CI/sandbox without TTY
        if not self._interactive:
            if not config.HUMAN_APPROVAL_REQUIRED:
                logger.warning(
                    "Non-interactive terminal: auto-approving action (HUMAN_APPROVAL_REQUIRED=False): %s",
                    action_description,
                )
                return True
            else:
                logger.warning(
                    "Non-interactive terminal with HUMAN_APPROVAL_REQUIRED=True: rejecting action %s",
                    action_description,
                )
                return False

        # Visual styling based on risk level
        risk_colors = {
            "low": "green",
            "medium": "yellow",
            "high": "bold red",
        }
        color = risk_colors.get(risk_level_normalized, "yellow")

        # Build display content
        content_lines = [
            f"[bold]Action:[/bold] {action_description}",
            f"[bold]Risk Level:[/bold] [{color}]{risk_level.upper()}[/{color}]",
        ]

        if context:
            table = Table(show_header=True, header_style="bold magenta", expand=False)
            table.add_column("Parameter")
            table.add_column("Value")
            for k, v in context.items():
                table.add_row(str(k), str(v))
            self.console.print(
                Panel(
                    "\n".join(content_lines),
                    title=f"⚠️ Human Approval Required [{risk_level.upper()}]",
                    border_style=color,
                )
            )
            self.console.print(table)
        else:
            self.console.print(
                Panel(
                    "\n".join(content_lines),
                    title=f"⚠️ Human Approval Required [{risk_level.upper()}]",
                    border_style=color,
                )
            )

        # Prompt user
        try:
            default_choice = True if risk_level_normalized == "low" else False
            approved = Confirm.ask(
                f"[{color}]Do you approve this action?[/{color}]",
                default=default_choice,
                console=self.console,
            )
            logger.info(
                "Human approval for '%s' (risk=%s): %s",
                action_description,
                risk_level,
                approved,
            )
            return approved
        except (EOFError, KeyboardInterrupt):
            logger.warning("Human approval prompt interrupted/closed; defaulting to reject.")
            return False

    def ask_clarification(
        self,
        question: str,
        options: list[str] | None = None,
    ) -> str:
        """
        Ask the human supervisor a clarifying question.

        Args:
            question: The question to prompt the user with.
            options: Optional list of predefined response options.

        Returns:
            The user's response string.
        """
        # Non-interactive check
        if not self._interactive:
            logger.warning("Non-interactive mode: cannot prompt for clarification: %s", question)
            return options[0] if options else "No human input available (non-interactive)"

        self.console.print(
            Panel(
                f"[bold cyan]{question}[/bold cyan]",
                title="❓ Clarification Needed",
                border_style="cyan",
            )
        )

        try:
            if options:
                self.console.print("[dim]Options:[/dim]")
                for idx, opt in enumerate(options, 1):
                    self.console.print(f"  [bold cyan]{idx}.[/bold cyan] {opt}")

                choice_str_list = [str(i) for i in range(1, len(options) + 1)]
                response = Prompt.ask(
                    "Select an option (or enter custom text)",
                    console=self.console,
                ).strip()

                if response in choice_str_list:
                    selected = options[int(response) - 1]
                    logger.info("Human selected clarification option: %s", selected)
                    return selected
                logger.info("Human provided custom clarification: %s", response)
                return response
            else:
                response = Prompt.ask(
                    "[bold]Your answer[/bold]",
                    console=self.console,
                ).strip()
                logger.info("Human provided clarification: %s", response)
                return response
        except (EOFError, KeyboardInterrupt):
            logger.warning("Clarification prompt interrupted; returning empty response.")
            return ""

    def notify(self, message: str, level: str = "info") -> None:
        """
        Display a formatted notification to the user.

        Args:
            message: The message to display.
            level: 'info', 'warning', 'error', or 'success'.
        """
        level_normalized = level.strip().lower()
        styles = {
            "info": ("ℹ️ INFO", "cyan"),
            "success": ("✅ SUCCESS", "green"),
            "warning": ("⚠️ WARNING", "yellow"),
            "error": ("❌ ERROR", "bold red"),
        }
        title, color = styles.get(level_normalized, ("NOTIFICATION", "white"))

        logger.log(
            logging.ERROR if level_normalized == "error" else logging.INFO,
            "Notification [%s]: %s",
            level,
            message,
        )

        self.console.print(
            Panel(
                message,
                title=f"[{color}]{title}[/{color}]",
                border_style=color,
                expand=False,
            )
        )
