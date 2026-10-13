"""
Core Autonomous AI Task Worker implementation.
Executes tasks using a ReAct (Reason + Act) loop with memory tracking,
human-in-the-loop approvals, and post-execution verification.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent.human_loop import HumanApprovalSystem
from agent.memory import Memory, StepRecord
from agent.verifier import VerificationResult, Verifier
from config import config
from llm.provider import LLMProvider, ToolCall
from tools.base import Tool, ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Standardized result returned by Agent upon completing a task run."""

    success: bool
    summary: str
    steps_taken: list[StepRecord]
    evidence: list[str]
    verification: VerificationResult
    facts_discovered: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        """Convert task result to dictionary."""
        return {
            "success": self.success,
            "summary": self.summary,
            "steps_taken": [s.to_dict() for s in self.steps_taken],
            "evidence": self.evidence,
            "verification": self.verification.to_dict(),
            "facts_discovered": self.facts_discovered,
        }


class Agent:
    """
    Autonomous AI Task Worker using ReAct (Reason + Act) loop.

    Coordinates LLM reasoning, tool invocations, human-in-the-loop oversight,
    persistent memory, and goal verification to reliably accomplish complex tasks.
    """

    SYSTEM_PROMPT = """You are an Autonomous AI Task Worker executing enterprise operations and workflows.
You operate with a high degree of autonomy, technical precision, diligence, and accountability.

### CORE OPERATING PRINCIPLES:
1. UNDERSTAND THE END GOAL:
   - Look beyond literal wording to understand the user's true underlying business outcome.
   - Always verify prerequisites before mutating state and verify results after executing actions.
   - Never assume an operation succeeded without validating tool outputs and response data.

2. REACT (REASON + ACT) CYCLE:
   - Reason: In each step, clearly articulate your understanding, what has been accomplished so far, what is still missing, and why you are taking the next specific action.
   - Act: Use the available tools to take real actions across browsers, APIs, systems, and files. Provide exact, well-formed arguments.
   - Observe: Thoroughly examine every tool result. Check returned status, payload fields, and error codes.
   - Adapt: If an action fails or returns an error, do not repeat the exact same call. Diagnose what went wrong and execute an alternative strategy.

3. SPECIAL SYNTAX & MARKERS:
   - [FACT: key=value]
     Whenever you discover important domain data (e.g. IDs, invoice amounts, status codes, dates, URLs, email addresses), record them in your thinking using this marker.
     Examples: [FACT: invoice_id=INV-4091] [FACT: total_amount=$3,450.00] [FACT: status=paid]
   - [TASK_COMPLETE]
     When and ONLY when you have achieved the user's end goal and verified the outcome, output [TASK_COMPLETE] in your final message, along with a comprehensive summary of actions taken and concrete evidence.
   - [NEED_HUMAN_INPUT: question]
     When you are genuinely blocked by missing credentials, ambiguous requirements, or high-risk unapproved destructive actions, ask for human help with this marker.

4. ERROR HANDLING & RETRIES:
   - When an action fails, explain: "Previous attempt failed because [cause]. Retrying with alternative approach [new method]."
   - If a selector, URL, or endpoint fails, search for alternative routes or inspect surrounding context.

5. VERIFICATION BEFORE COMPLETION:
   - Before outputting [TASK_COMPLETE], verify that every requirement of the task has been satisfied.
   - Summarize the concrete evidence confirming that the task succeeded.
"""

    HUMAN_INPUT_PATTERN = re.compile(r"\[NEED_HUMAN_INPUT:\s*(.*?)\]", re.IGNORECASE | re.DOTALL)
    TASK_COMPLETE_PATTERN = re.compile(r"\[TASK_COMPLETE\]", re.IGNORECASE)

    def __init__(
        self,
        tools: ToolRegistry | None = None,
        llm: LLMProvider | None = None,
        human_loop: HumanApprovalSystem | None = None,
        verifier: Verifier | None = None,
        console: Console | None = None,
        max_steps: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        """
        Initialize the autonomous agent.

        Args:
            tools: Registry of tools available to the agent.
            llm: LLMProvider abstraction for model inference.
            human_loop: Human approval system for interactive supervision.
            verifier: Verifier system to validate goal completion.
            console: Rich console for formatting terminal output.
            max_steps: Maximum iterations in the ReAct loop (defaults to config.MAX_STEPS).
            max_retries: Maximum retries per tool failure (defaults to config.MAX_RETRIES).
        """
        self.tools = tools or ToolRegistry()
        self.llm = llm or LLMProvider()
        self.human_loop = human_loop or HumanApprovalSystem()
        self.verifier = verifier or Verifier()
        self.console = console or Console()
        self.max_steps = max_steps or config.MAX_STEPS
        self.max_retries = max_retries or config.MAX_RETRIES
        self.memory = Memory()

    def _determine_risk_level(self, tool_name: str, tool_args: dict[str, Any]) -> str:
        """
        Determine the risk level ('low', 'medium', 'high') of a planned tool invocation.

        Args:
            tool_name: The name of the tool to be called.
            tool_args: Arguments passed to the tool.

        Returns:
            'low', 'medium', or 'high'.
        """
        name_lower = tool_name.lower()

        # High risk: destructive operations
        high_risk_keywords = ["delete", "drop", "destroy", "truncate", "remove", "kill", "purge", "format"]
        if any(kw in name_lower for kw in high_risk_keywords):
            return "high"

        # Check API HTTP methods
        method = str(tool_args.get("method", "")).upper()
        if method == "DELETE":
            return "high"
        if method in ("POST", "PUT", "PATCH"):
            return "medium"

        # Medium risk: mutations, writes, sends
        medium_risk_keywords = ["create", "write", "update", "modify", "send", "post", "put", "patch", "submit", "execute"]
        if any(kw in name_lower for kw in medium_risk_keywords):
            return "medium"

        # Low risk: read-only, inspection, navigation
        return "low"

    def _should_ask_approval(self, tool_name: str, tool_args: dict[str, Any], risk_level: str) -> bool:
        """
        Check whether an action requires explicit human approval before execution.

        Args:
            tool_name: Name of tool to execute.
            tool_args: Parameters passed to the tool.
            risk_level: Assessed risk level.

        Returns:
            True if approval is required, False otherwise.
        """
        # Low-risk actions (read, navigate, inspect) do not modify data
        if risk_level == "low":
            return False

        # Medium and High risk actions are write/modify operations
        if config.HUMAN_APPROVAL_REQUIRED:
            return True

        # If HUMAN_APPROVAL_REQUIRED is disabled globally, still require approval for high-risk operations
        return risk_level == "high"

    async def _execute_tool_with_retries(
        self,
        tool: Tool,
        tool_args: dict[str, Any],
    ) -> ToolResult:
        """
        Execute a tool safely with retry handling.

        Args:
            tool: The Tool instance to run.
            tool_args: Parameters for tool execution.

        Returns:
            The resulting ToolResult.
        """
        attempts = 0
        last_error = ""

        while attempts < self.max_retries:
            attempts += 1
            try:
                result = await tool.execute(**tool_args)
                if result.success:
                    return result

                last_error = result.error or result.output
                logger.warning(
                    "Tool %s failed attempt %d/%d: %s",
                    tool.name,
                    attempts,
                    self.max_retries,
                    last_error,
                )

                if attempts < self.max_retries:
                    await asyncio.sleep(0.5)
                else:
                    return result
            except Exception as exc:
                last_error = str(exc)
                logger.error(
                    "Exception executing tool %s (attempt %d/%d): %s",
                    tool.name,
                    attempts,
                    self.max_retries,
                    exc,
                    exc_info=True,
                )
                if attempts < self.max_retries:
                    await asyncio.sleep(0.5)
                else:
                    return ToolResult(
                        success=False,
                        output=f"Tool failed with exception: {exc}",
                        error=str(exc),
                    )

        return ToolResult(
            success=False,
            output=f"Tool failed after {attempts} attempts: {last_error}",
            error=last_error,
        )

    async def run(self, task: str) -> TaskResult:
        """
        Execute the autonomous agent on the specified task.

        Args:
            task: The user's task instruction.

        Returns:
            TaskResult detailing execution steps, verification, and outcomes.
        """
        logger.info("Agent started task: %s", task)
        self.console.print(
            Panel(
                f"[bold white]{task}[/bold white]",
                title="🚀 New Task Initiated",
                border_style="bold blue",
            )
        )

        # 1. Initialize Memory
        self.memory.clear()

        # 2. Build initial conversation messages
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"Task:\n{task}"},
        ]

        tools_spec = self.tools.to_openai_tools() if self.tools.list_tools() else None

        step_count = 0
        consecutive_failures = 0
        task_completed_signaled = False
        final_summary = ""

        # 3. Main ReAct Loop
        while step_count < self.max_steps:
            step_count += 1
            logger.info("Beginning ReAct step %d/%d", step_count, self.max_steps)

            # a. Call LLM
            with self.console.status(
                f"[bold cyan]Step {step_count}/{self.max_steps}: Thinking...[/bold cyan]",
                spinner="dots",
            ):
                try:
                    response = await self.llm.chat(
                        messages=messages,
                        tools=tools_spec,
                    )
                except Exception as exc:
                    logger.error("LLM chat error on step %d: %s", step_count, exc, exc_info=True)
                    self.memory.add_error(f"LLM request failure on step {step_count}: {exc}")
                    self.console.print(f"[bold red]❌ LLM Error:[/bold red] {exc}")
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        guidance = self.human_loop.ask_clarification(
                            f"The agent encountered repeated LLM errors: {exc}. How should it proceed?"
                        )
                        messages.append({"role": "user", "content": f"Human supervisor guidance: {guidance}"})
                        consecutive_failures = 0
                    continue

            # Process LLM thinking and fact extraction
            thought_text = response.content or ""
            if thought_text:
                self.console.print(
                    Panel(
                        thought_text,
                        title=f"🤔 Step {step_count} Thinking",
                        border_style="cyan",
                    )
                )

                # Extract facts
                facts_found = self.memory.record_facts_from_text(thought_text)
                for fk, fv in facts_found:
                    self.console.print(f"  [bold yellow]💡 Fact Discovered:[/bold yellow] [bold]{fk}[/bold] = {fv}")

                # Check for human input request
                human_match = self.HUMAN_INPUT_PATTERN.search(thought_text)
                if human_match:
                    question = human_match.group(1).strip()
                    self.console.print(f"[bold magenta]🙋 Agent is requesting human input:[/bold magenta] {question}")
                    human_reply = self.human_loop.ask_clarification(question)
                    messages.append({"role": "assistant", "content": thought_text})
                    messages.append({"role": "user", "content": f"Human supervisor response: {human_reply}"})
                    continue

            # b. If LLM returns text only (no tool calls)
            if not response.has_tool_calls:
                # Check for completion marker
                if self.TASK_COMPLETE_PATTERN.search(thought_text):
                    logger.info("Agent signaled task completion with [TASK_COMPLETE]")
                    self.console.print("[bold green]🏁 Agent signaled [TASK_COMPLETE]![/bold green]")
                    task_completed_signaled = True
                    final_summary = thought_text
                    break

                # If no tool calls and not completed, add thinking to conversation
                messages.append({"role": "assistant", "content": thought_text})
                # Prompt the LLM to continue or conclude
                messages.append({
                    "role": "user",
                    "content": (
                        "Please proceed by invoking the necessary tools to accomplish the task, "
                        "or include [TASK_COMPLETE] if the task is already finished."
                    ),
                })
                continue

            # c. If LLM returns tool calls
            # Format assistant message per OpenAI tool calling schema
            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": thought_text or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.tool_name,
                            "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else str(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ],
            }
            messages.append(assistant_message)

            for tc in response.tool_calls:
                tool_instance = self.tools.get(tc.tool_name)
                risk_level = self._determine_risk_level(tc.tool_name, tc.arguments)

                self.console.print(
                    f"[bold blue]🔧 Action ({tc.tool_name}):[/bold blue] "
                    f"args={json.dumps(tc.arguments)}"
                )

                # Check if human approval is needed
                needs_approval = self._should_ask_approval(tc.tool_name, tc.arguments, risk_level)
                if needs_approval:
                    action_desc = f"Execute tool `{tc.tool_name}` with arguments {json.dumps(tc.arguments)}"
                    approved = self.human_loop.ask_approval(
                        action_description=action_desc,
                        risk_level=risk_level,
                        context=tc.arguments,
                    )
                    if not approved:
                        self.console.print(f"[bold red]⛔ Human supervisor denied action `{tc.tool_name}`[/bold red]")
                        rejected_result = ToolResult(
                            success=False,
                            output="Action denied by human supervisor.",
                            error="Human supervisor rejected approval for this action. Choose an alternative approach.",
                        )
                        self.memory.record_step(
                            action=f"Tool `{tc.tool_name}` rejected by human supervisor",
                            tool_name=tc.tool_name,
                            tool_args=tc.arguments,
                            result=rejected_result,
                            thought=thought_text,
                            error=rejected_result.error,
                        )
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": tc.tool_name,
                            "content": rejected_result.to_observation(),
                        })
                        consecutive_failures += 1
                        continue

                # Execute tool
                if not tool_instance:
                    err_msg = f"Tool `{tc.tool_name}` is not registered in ToolRegistry."
                    tool_result = ToolResult(success=False, output=err_msg, error=err_msg)
                else:
                    tool_result = await self._execute_tool_with_retries(tool_instance, tc.arguments)

                # Record step in memory
                self.memory.record_step(
                    action=f"Call tool `{tc.tool_name}`",
                    tool_name=tc.tool_name,
                    tool_args=tc.arguments,
                    result=tool_result,
                    thought=thought_text,
                    error=tool_result.error if not tool_result.success else None,
                )

                # If tool extracted data, record any relevant facts
                if tool_result.data and isinstance(tool_result.data, dict):
                    for k, v in tool_result.data.items():
                        if isinstance(v, (str, int, float, bool)):
                            self.memory.add_fact(str(k), str(v))

                # Handle tool success / failure
                if tool_result.success:
                    consecutive_failures = 0
                    self.console.print(f"  [bold green]✅ Tool `{tc.tool_name}` succeeded[/bold green]")
                else:
                    consecutive_failures += 1
                    err = tool_result.error or tool_result.output
                    self.console.print(f"  [bold red]❌ Tool `{tc.tool_name}` failed:[/bold red] {err}")
                    self.memory.add_error(f"Tool `{tc.tool_name}` failed: {err}")

                # Format tool observation message
                obs_content = tool_result.to_observation()
                if not tool_result.success and consecutive_failures < self.max_retries:
                    obs_content += "\n[Context: Analyze the failure above and retry with an alternative approach or adjusted parameters.]"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.tool_name,
                    "content": obs_content,
                })

            # d. Check if stuck (3+ consecutive failures)
            if consecutive_failures >= 3:
                self.console.print(
                    "[bold yellow]⚠️ Agent encountered 3 consecutive failures. Seeking human assistance...[/bold yellow]"
                )
                recent_errors = self.memory.get_errors()
                last_err = recent_errors[-1] if recent_errors else "Repeated failures"
                guidance = self.human_loop.ask_clarification(
                    f"The agent has failed 3 consecutive actions. Recent error: {last_err}. What should it do next?"
                )
                messages.append({
                    "role": "user",
                    "content": f"Human supervisor guidance: {guidance}",
                })
                consecutive_failures = 0

        # Loop ended (either complete, max steps hit, or interrupted)
        if not task_completed_signaled and step_count >= self.max_steps:
            self.console.print(
                f"[bold yellow]⚠️ Reached maximum step limit ({self.max_steps}). Proceeding to verification.[/bold yellow]"
            )

        # 4. Run Verification
        self.console.print("\n[bold magenta]🔍 Initiating Verification...[/bold magenta]")
        with self.console.status("[bold magenta]Verifying task completion...[/bold magenta]", spinner="dots"):
            verification = await self.verifier.verify(
                original_task=task,
                memory=self.memory,
                tools=self.tools,
                llm=self.llm,
            )

        # Overall success determination:
        # Verified by Verifier with confidence >= 0.5 and (signaled complete or non-empty evidence)
        is_success = verification.verified and verification.confidence >= 0.5

        if not final_summary:
            final_summary = verification.summary or ("Task completed successfully." if is_success else "Task failed to achieve the goal.")

        # 5. Display Final Results beautifully
        self._display_task_result(is_success, final_summary, verification)

        return TaskResult(
            success=is_success,
            summary=final_summary,
            steps_taken=self.memory.get_steps(),
            evidence=verification.evidence,
            verification=verification,
            facts_discovered=self.memory.get_facts(),
        )

    def _display_task_result(
        self,
        is_success: bool,
        summary: str,
        verification: VerificationResult,
    ) -> None:
        """Render a formatted summary table and panel of the completed task."""
        color = "green" if is_success else "red"
        status_text = "PASSED" if is_success else "FAILED"

        table = Table(title="📊 Task Execution Summary", expand=False)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value")

        table.add_row("Status", f"[{color}]{status_text}[/{color}]")
        table.add_row("Confidence", f"{verification.confidence * 100:.1f}%")
        table.add_row("Total Steps Executed", str(self.memory.get_step_count()))
        table.add_row("Discovered Facts", str(len(self.memory.get_facts())))
        table.add_row("Errors Encountered", str(len(self.memory.get_errors())))

        if verification.evidence:
            table.add_row("Key Evidence", "\n".join(f"• {e}" for e in verification.evidence[:5]))
        if verification.concerns:
            table.add_row("Concerns", "\n".join(f"• {c}" for c in verification.concerns[:5]))

        self.console.print("\n")
        self.console.print(table)
        self.console.print(
            Panel(
                summary,
                title=f"[{color}]🎯 Final Outcome: {status_text}[/{color}]",
                border_style=color,
            )
        )

    async def cleanup(self) -> None:
        """Clean up tools and resources used by the agent."""
        if self.tools:
            await self.tools.cleanup_all()

