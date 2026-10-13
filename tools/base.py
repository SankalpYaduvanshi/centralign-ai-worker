"""
Base tool interface for the Autonomous AI Task Worker.
All tools implement this interface so the agent can discover,
describe, and invoke them uniformly.
"""

from __future__ import annotations

import abc
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Standardized result returned by every tool execution."""

    success: bool
    output: str  # Human-readable description of what happened
    error: str | None = None  # Error message if success is False
    data: dict[str, Any] | None = None  # Structured data extracted
    screenshot_b64: str | None = None  # Base64 screenshot (browser tool)

    def to_observation(self) -> str:
        """Format this result as an observation string for the LLM."""
        parts = []
        if self.success:
            parts.append(f"✅ Success: {self.output}")
        else:
            parts.append(f"❌ Failed: {self.error or self.output}")
        if self.data:
            parts.append(f"Extracted data: {json.dumps(self.data, indent=2)}")
        if self.screenshot_b64:
            parts.append("[Screenshot captured]")
        return "\n".join(parts)


class Tool(abc.ABC):
    """Abstract base class for agent tools."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique tool name used by the LLM to invoke it."""

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """One-line description shown to the LLM."""

    @property
    @abc.abstractmethod
    def parameters_schema(self) -> dict:
        """
        JSON Schema describing the tool's parameters.
        Used to build the OpenAI-style function calling spec.
        """

    @abc.abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Run the tool with the given arguments and return a ToolResult."""

    def to_openai_tool(self) -> dict:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }

    async def cleanup(self) -> None:
        """Optional cleanup hook called when the agent shuts down."""
        pass


class ToolRegistry:
    """Registry of available tools — the agent's toolbox."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def to_openai_tools(self) -> list[dict]:
        return [t.to_openai_tool() for t in self._tools.values()]

    async def cleanup_all(self) -> None:
        for tool in self._tools.values():
            await tool.cleanup()
