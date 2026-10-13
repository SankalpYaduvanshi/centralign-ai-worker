"""
Comprehensive unit tests for the core agent system.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from agent.core import Agent, TaskResult
from agent.human_loop import HumanApprovalSystem
from agent.memory import Memory, StepRecord
from agent.verifier import VerificationResult, Verifier
from config import config
from llm.provider import LLMProvider, LLMResponse, ToolCall
from tools.base import Tool, ToolRegistry, ToolResult


class DummyTool(Tool):
    """Test tool for verifying execution and retries."""

    def __init__(self, name: str = "dummy_tool", success: bool = True, output: str = "done") -> None:
        self._name = name
        self._success = success
        self._output = output
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Dummy test tool"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"action": {"type": "string"}},
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        self.call_count += 1
        return ToolResult(
            success=self._success,
            output=self._output,
            error=None if self._success else "Execution failed",
            data={"status": "ok"} if self._success else None,
        )


class TestMemory(unittest.TestCase):
    """Tests for agent/memory.py."""

    def setUp(self) -> None:
        self.memory = Memory()

    def test_record_step_and_get_count(self) -> None:
        self.assertEqual(self.memory.get_step_count(), 0)
        step = self.memory.record_step(
            action="Test step",
            tool_name="dummy_tool",
            tool_args={"action": "test"},
            result=ToolResult(success=True, output="All good"),
        )
        self.assertEqual(self.memory.get_step_count(), 1)
        self.assertEqual(step.step_number, 1)
        self.assertTrue(step.success)
        self.assertEqual(self.memory.get_step(1), step)

    def test_facts_storage_and_extraction(self) -> None:
        self.memory.add_fact("invoice_amount", "$5,230.00")
        self.assertEqual(self.memory.get_fact("invoice_amount"), "$5,230.00")
        self.assertIsNone(self.memory.get_fact("non_existent"))

        extracted = self.memory.record_facts_from_text(
            "Found invoice details: [FACT: customer_name=Acme Corp] and [FACT: order_id=ORD-991]"
        )
        self.assertEqual(len(extracted), 2)
        facts = self.memory.get_facts()
        self.assertEqual(facts["customer_name"], "Acme Corp")
        self.assertEqual(facts["order_id"], "ORD-991")
        self.assertEqual(facts["invoice_amount"], "$5,230.00")

    def test_errors_storage(self) -> None:
        self.memory.add_error("Failed to connect")
        self.memory.record_step(
            action="Failed step",
            error="Something broke",
        )
        errors = self.memory.get_errors()
        self.assertEqual(len(errors), 2)
        self.assertIn("Failed to connect", errors[0])

    def test_context_summary(self) -> None:
        # Record 7 steps to test both summarized older steps and detailed recent steps
        for i in range(1, 8):
            self.memory.record_step(
                action=f"Action {i}",
                tool_name=f"tool_{i}",
                tool_args={"param": i},
                result=ToolResult(success=True, output=f"Result {i}"),
            )
        self.memory.add_fact("company", "Centralign")
        self.memory.add_error("Minor timeout")

        summary = self.memory.get_context_summary(detailed_steps=4)
        self.assertIn("Steps 1 to 3 summary", summary)
        self.assertIn("Recent steps (Steps 4 to 7)", summary)
        self.assertIn("Centralign", summary)
        self.assertIn("Minor timeout", summary)


class TestHumanApprovalSystem(unittest.TestCase):
    """Tests for agent/human_loop.py."""

    def setUp(self) -> None:
        self.human = HumanApprovalSystem(auto_approve_all=False, interactive=False)

    def test_auto_approve_low_risk_when_disabled(self) -> None:
        with patch.object(config, "HUMAN_APPROVAL_REQUIRED", False):
            approved = self.human.ask_approval("Read database table", risk_level="low")
            self.assertTrue(approved)

    def test_auto_approve_all_override(self) -> None:
        approver = HumanApprovalSystem(auto_approve_all=True, interactive=False)
        approved = approver.ask_approval("Delete production database", risk_level="high")
        self.assertTrue(approved)

    def test_clarification_non_interactive(self) -> None:
        res = self.human.ask_clarification("Select option", options=["Option A", "Option B"])
        self.assertEqual(res, "Option A")

    def test_notify(self) -> None:
        # Should not raise
        self.human.notify("Operation complete", level="success")
        self.human.notify("High CPU", level="warning")
        self.human.notify("Crash", level="error")
        self.human.notify("FYI", level="info")


class TestVerifier(unittest.IsolatedAsyncioTestCase):
    """Tests for agent/verifier.py."""

    async def test_verifier_no_steps(self) -> None:
        verifier = Verifier()
        mem = Memory()
        tools = ToolRegistry()
        llm = AsyncMock(spec=LLMProvider)

        result = await verifier.verify("Do something", mem, tools, llm)
        self.assertFalse(result.verified)
        self.assertEqual(result.confidence, 1.0)
        self.assertIn("No actions or steps were executed", result.concerns[0])

    async def test_verifier_llm_parsing(self) -> None:
        verifier = Verifier()
        mem = Memory()
        mem.record_step(
            action="Retrieve invoice",
            tool_name="dummy_tool",
            result=ToolResult(success=True, output="Invoice retrieved: ID 101"),
        )
        tools = ToolRegistry()
        llm = AsyncMock(spec=LLMProvider)
        llm.chat = AsyncMock(return_value=LLMResponse(
            content='```json\n{\n  "verified": true,\n  "confidence": 0.95,\n  "evidence": ["Invoice 101 retrieved"],\n  "concerns": [],\n  "summary": "Completed successfully."\n}\n```'
        ))

        result = await verifier.verify("Find invoice 101", mem, tools, llm)
        self.assertTrue(result.verified)
        self.assertEqual(result.confidence, 0.95)
        self.assertIn("Invoice 101 retrieved", result.evidence)
        self.assertEqual(result.summary, "Completed successfully.")


class TestAgent(unittest.IsolatedAsyncioTestCase):
    """Tests for agent/core.py ReAct loop."""

    async def test_agent_run_success(self) -> None:
        tool_reg = ToolRegistry()
        tool = DummyTool("fetch_data", success=True, output="Records found")
        tool_reg.register(tool)

        mock_llm = AsyncMock(spec=LLMProvider)
        # Turn 1: LLM outputs tool call
        # Turn 2: LLM observes result and concludes with [TASK_COMPLETE]
        mock_llm.chat = AsyncMock(side_effect=[
            LLMResponse(
                content="I will fetch the data. [FACT: record_count=42]",
                tool_calls=[ToolCall(id="call_1", tool_name="fetch_data", arguments={"action": "fetch"})],
            ),
            LLMResponse(
                content="Data verified. [TASK_COMPLETE] Task is complete.",
                tool_calls=[],
            ),
            # Verifier LLM call
            LLMResponse(
                content='{"verified": true, "confidence": 0.9, "evidence": ["Fetched 42 records"], "concerns": [], "summary": "Done"}',
            ),
        ])

        human = HumanApprovalSystem(auto_approve_all=True, interactive=False)
        agent = Agent(tools=tool_reg, llm=mock_llm, human_loop=human)

        result: TaskResult = await agent.run("Fetch records")
        self.assertTrue(result.success)
        self.assertEqual(tool.call_count, 1)
        self.assertEqual(result.facts_discovered.get("record_count"), "42")
        self.assertEqual(len(result.steps_taken), 1)
        self.assertTrue(result.verification.verified)

    async def test_agent_stuck_triggers_human_guidance(self) -> None:
        tool_reg = ToolRegistry()
        fail_tool = DummyTool("flaky_tool", success=False, output="Internal error")
        tool_reg.register(fail_tool)

        mock_llm = AsyncMock(spec=LLMProvider)
        # Produce 3 consecutive failures, then human input injected, then completion
        mock_llm.chat = AsyncMock(side_effect=[
            LLMResponse(content="Try step 1", tool_calls=[ToolCall(id="1", tool_name="flaky_tool", arguments={})]),
            LLMResponse(content="Try step 2", tool_calls=[ToolCall(id="2", tool_name="flaky_tool", arguments={})]),
            LLMResponse(content="Try step 3", tool_calls=[ToolCall(id="3", tool_name="flaky_tool", arguments={})]),
            LLMResponse(content="Recovering... [TASK_COMPLETE] Done.", tool_calls=[]),
            LLMResponse(content='{"verified": false, "confidence": 0.3, "evidence": [], "concerns": ["Failed"], "summary": "Failed"}'),
        ])

        human = HumanApprovalSystem(auto_approve_all=True, interactive=False)
        human.ask_clarification = MagicMock(return_value="Try alternative approach")

        agent = Agent(tools=tool_reg, llm=mock_llm, human_loop=human, max_retries=1)
        result = await agent.run("Perform operation")

        self.assertTrue(human.ask_clarification.called)


if __name__ == "__main__":
    unittest.main()
