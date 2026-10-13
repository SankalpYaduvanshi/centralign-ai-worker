"""
LLM provider abstraction for the Autonomous AI Task Worker.
Wraps the OpenAI API and provides a clean interface for the agent core.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

from config import config

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """A single tool/function call returned by the LLM."""

    id: str
    tool_name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Parsed response from the LLM."""

    content: str | None = None  # Text response (thinking / final answer)
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMProvider:
    """
    Async wrapper around the OpenAI chat completions API
    with support for function calling (tool use).
    """

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or config.OPENAI_MODEL
        self._client = AsyncOpenAI(api_key=api_key or config.OPENAI_API_KEY)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        Send a chat completion request.

        Args:
            messages: OpenAI-format message list.
            tools: OpenAI-format tool definitions (optional).
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the response.

        Returns:
            Parsed LLMResponse with optional tool calls.
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        logger.debug("LLM request: model=%s, messages=%d, tools=%d",
                      self.model, len(messages), len(tools or []))

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        # Parse tool calls if present
        parsed_tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {"raw": tc.function.arguments}
                parsed_tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        tool_name=tc.function.name,
                        arguments=args,
                    )
                )

        return LLMResponse(
            content=message.content,
            tool_calls=parsed_tool_calls,
            finish_reason=choice.finish_reason,
        )

    async def simple_chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
    ) -> str:
        """Convenience method for a simple system+user chat (no tools)."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        resp = await self.chat(messages, temperature=temperature)
        return resp.content or ""
