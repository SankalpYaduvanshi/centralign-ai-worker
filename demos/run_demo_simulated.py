"""
Self-contained live demo runner for the Autonomous AI Task Worker.
Simulates LLM tool selection in a deterministic scenario to showcase
the entire ReAct execution loop, real Playwright browser automation,
mock company portal, memory fact extraction, and verifier without needing
an external OpenAI API key.

Usage:
    python demos/run_demo_simulated.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from config import config
from mock_app.server import start_server_background, stop_server_background
from tools.base import ToolRegistry
from tools.browser_tool import (
    BrowserManager,
    NavigateTool,
    ClickTool,
    TypeTextTool,
    ExtractTextTool,
    ExtractTableTool,
    GetPageInfoTool,
    ScreenshotTool,
)
from tools.filesystem_tool import ReadFileTool, WriteFileTool, ListFilesTool
from tools.api_tool import HttpRequestTool
from agent.core import Agent, TaskResult
from agent.memory import StepRecord
from agent.verifier import VerificationResult
from llm.provider import LLMResponse, ToolCall
from rich.console import Console

console = Console()


class ScriptedLLMProvider:
    """Deterministic LLM Provider that executes the problem statement scenario."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.step = 0

    async def chat(self, messages, tools=None, temperature=0.2, max_tokens=4096):
        prompt_text = " ".join(str(m.get("content", "") or "") for m in messages)
        if "Analyze the execution critically" in prompt_text or "strictly valid JSON" in prompt_text:
            import json
            return LLMResponse(
                content=json.dumps({
                    "verified": True,
                    "confidence": 0.98,
                    "evidence": [
                        "Identified latest Acme Corp invoice inv-001 with amount $14,500.00 and due date 2026-11-15",
                        "Filled and submitted expense creation form via browser automation",
                        "Verified new expense record exists via /api/expenses endpoint",
                    ],
                    "concerns": [],
                    "summary": "All task requirements autonomously completed and verified across browser and API.",
                })
            )

        self.step += 1

        if self.step == 1:
            return LLMResponse(
                content=(
                    "The user wants me to find the latest invoice from Acme Corp, extract the amount "
                    "and due date, record an expense entry in our internal portal, and verify completion. "
                    "Step 1: Navigate to the internal portal invoices page."
                ),
                tool_calls=[
                    ToolCall(
                        id="call_nav_inv",
                        tool_name="browser_navigate",
                        arguments={"url": f"{self.base_url}/invoices"},
                    )
                ],
            )
        elif self.step == 2:
            return LLMResponse(
                content=(
                    "We are on the invoices page. Let's inspect the invoices table to locate the latest invoice from Acme Corp."
                ),
                tool_calls=[
                    ToolCall(
                        id="call_extract_table",
                        tool_name="browser_extract_table",
                        arguments={"selector": "#invoices-table"},
                    )
                ],
            )
        elif self.step == 3:
            return LLMResponse(
                content=(
                    "Examining the table: Acme Corp invoice is inv-001 with amount $14,500.00 and due date 2026-11-15. "
                    "[FACT: vendor=Acme Corp] "
                    "[FACT: invoice_id=inv-001] "
                    "[FACT: amount=14500.00] "
                    "[FACT: due_date=2026-11-15] "
                    "Next, let's navigate to the New Expense form at /expenses/new."
                ),
                tool_calls=[
                    ToolCall(
                        id="call_nav_exp",
                        tool_name="browser_navigate",
                        arguments={"url": f"{self.base_url}/expenses/new"},
                    )
                ],
            )
        elif self.step == 4:
            return LLMResponse(
                content=(
                    "On the expense form. Now entering description: 'Acme Corp Software License (inv-001)'."
                ),
                tool_calls=[
                    ToolCall(
                        id="call_fill_desc",
                        tool_name="browser_type",
                        arguments={
                            "selector": "#description",
                            "text": "Acme Corp Software License (inv-001)",
                            "clear_first": True,
                        },
                    )
                ],
            )
        elif self.step == 5:
            return LLMResponse(
                content="Now entering the amount: '14500.00'.",
                tool_calls=[
                    ToolCall(
                        id="call_fill_amount",
                        tool_name="browser_type",
                        arguments={
                            "selector": "#amount",
                            "text": "14500.00",
                            "clear_first": True,
                        },
                    )
                ],
            )
        elif self.step == 6:
            return LLMResponse(
                content="Entering invoice reference 'inv-001' and submit the expense form.",
                tool_calls=[
                    ToolCall(
                        id="call_fill_ref",
                        tool_name="browser_type",
                        arguments={
                            "selector": "#invoice_ref",
                            "text": "inv-001",
                            "clear_first": True,
                        },
                    )
                ],
            )
        elif self.step == 7:
            return LLMResponse(
                content="Clicking the submit button to save the new expense entry.",
                tool_calls=[
                    ToolCall(
                        id="call_click_submit",
                        tool_name="browser_click",
                        arguments={"selector": "#submit-expense"},
                    )
                ],
            )
        elif self.step == 8:
            return LLMResponse(
                content=(
                    "The form submitted and redirected to /expenses. "
                    "Let's make an API call to verify the expense record exists in our database."
                ),
                tool_calls=[
                    ToolCall(
                        id="call_api_check",
                        tool_name="http_request",
                        arguments={"method": "GET", "url": f"{self.base_url}/api/expenses"},
                    )
                ],
            )
        else:
            return LLMResponse(
                content=(
                    "Successfully identified the latest Acme Corp invoice (inv-001), extracted amount "
                    "$14,500.00 and due date 2026-11-15, and recorded a new expense entry via the company portal. "
                    "The expense record was confirmed in the system. [TASK_COMPLETE]"
                )
            )


async def main():
    console.print("\n[bold cyan]════════════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan] CentrAlign AI Worker — Live End-to-End Simulation [/bold cyan]")
    console.print("[bold cyan]════════════════════════════════════════════════════════════════[/bold cyan]\n")

    # 1. Start mock company portal
    console.print("[dim]Starting mock company portal on port 8042...[/dim]")
    task, server = await start_server_background()
    base_url = config.MOCK_APP_URL

    # 2. Build Tools Registry
    browser_mgr = BrowserManager()
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

    # 3. Create Agent with Scripted LLM Provider
    scripted_llm = ScriptedLLMProvider(base_url)
    agent = Agent(tools=registry, llm=scripted_llm, console=console)

    task_prompt = (
        "Find the latest invoice from Acme Corp, extract the amount and due date, "
        "enter it into our internal system, and tell me once it is done."
    )

    try:
        result = await agent.run(task_prompt)
        console.print(f"\n[bold green]✅ Simulation Finished: Success = {result.success}[/bold green]")
        console.print(f"[bold cyan]Facts Discovered:[/bold cyan] {result.facts_discovered}")
    finally:
        await agent.cleanup()
        await stop_server_background(server, task)


if __name__ == "__main__":
    asyncio.run(main())
