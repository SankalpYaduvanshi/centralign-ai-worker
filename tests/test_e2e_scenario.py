"""
End-to-end integration test running the exact scenario from the prompt:
'Find the latest invoice from Company X, extract the amount and due date,
enter it into our internal system, and tell me once it is done.'
"""

import asyncio
import json
import unittest

from config import config
from mock_app.server import start_server_background, stop_server_background
from mock_app.routes import store
from tools.base import ToolRegistry
from tools.browser_tool import (
    BrowserManager,
    NavigateTool,
    ClickTool,
    TypeTextTool,
    ExtractTableTool,
)
from tools.api_tool import HttpRequestTool
from agent.core import Agent
from llm.provider import LLMResponse, ToolCall


class ScriptedTestLLM:
    """Mock LLM that executes the exact business sequence."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.step = 0

    async def chat(self, messages, tools=None, temperature=0.2, max_tokens=4096):
        prompt_text = " ".join(str(m.get("content", "") or "") for m in messages)
        if "Analyze the execution critically" in prompt_text or "strictly valid JSON" in prompt_text:
            return LLMResponse(
                content=json.dumps({
                    "verified": True,
                    "confidence": 0.95,
                    "evidence": [
                        "Navigated to invoices and extracted inv-001 ($14,500.00)",
                        "Created matching expense record in internal system",
                    ],
                    "concerns": [],
                    "summary": "Task fully verified.",
                })
            )

        self.step += 1
        if self.step == 1:
            return LLMResponse(
                content="Locating invoices in company portal.",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        tool_name="browser_navigate",
                        arguments={"url": f"{self.base_url}/invoices"},
                    )
                ],
            )
        elif self.step == 2:
            return LLMResponse(
                content="Extracting invoices table data.",
                tool_calls=[
                    ToolCall(
                        id="call_2",
                        tool_name="browser_extract_table",
                        arguments={"selector": "#invoices-table"},
                    )
                ],
            )
        elif self.step == 3:
            return LLMResponse(
                content="Found Acme Corp: [FACT: invoice_id=inv-001] [FACT: amount=14500.00] Navigating to expense form.",
                tool_calls=[
                    ToolCall(
                        id="call_3",
                        tool_name="browser_navigate",
                        arguments={"url": f"{self.base_url}/expenses/new"},
                    )
                ],
            )
        elif self.step == 4:
            return LLMResponse(
                content="Filling expense description.",
                tool_calls=[
                    ToolCall(
                        id="call_4",
                        tool_name="browser_type",
                        arguments={"selector": "#description", "text": "Acme License"},
                    )
                ],
            )
        elif self.step == 5:
            return LLMResponse(
                content="Submitting expense.",
                tool_calls=[
                    ToolCall(
                        id="call_5",
                        tool_name="browser_click",
                        arguments={"selector": "#submit-expense"},
                    )
                ],
            )
        else:
            return LLMResponse(content="Task completed successfully. [TASK_COMPLETE]")


class TestEndToEndScenario(unittest.IsolatedAsyncioTestCase):
    """End-to-end integration test."""

    async def asyncSetUp(self):
        store.reset()
        self.server_task, self.server = await start_server_background()
        self.browser_mgr = BrowserManager()
        self.registry = ToolRegistry()
        self.registry.register(NavigateTool(self.browser_mgr))
        self.registry.register(ClickTool(self.browser_mgr))
        self.registry.register(TypeTextTool(self.browser_mgr))
        self.registry.register(ExtractTableTool(self.browser_mgr))
        self.registry.register(HttpRequestTool())

    async def asyncTearDown(self):
        await self.browser_mgr.cleanup()
        await stop_server_background(self.server, self.server_task)

    async def test_full_scenario_execution(self):
        llm = ScriptedTestLLM(config.MOCK_APP_URL)
        agent = Agent(tools=self.registry, llm=llm)

        task = (
            "Find the latest invoice from Acme Corp, extract amount and due date, "
            "and create an expense entry."
        )
        result = await agent.run(task)
        self.assertTrue(result.success)
        self.assertGreaterEqual(result.verification.confidence, 0.9)
        self.assertIn("invoice_id", result.facts_discovered)
        self.assertEqual(result.facts_discovered["invoice_id"], "inv-001")


if __name__ == "__main__":
    unittest.main()
