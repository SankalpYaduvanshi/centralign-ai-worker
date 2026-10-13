"""
Memory system for the Autonomous AI Task Worker.
Tracks execution history, discovered facts, and provides structured context summaries to the LLM.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from tools.base import ToolResult

logger = logging.getLogger(__name__)


@dataclass
class StepRecord:
    """Record of a single execution step taken by the agent."""

    step_number: int
    action: str
    tool_name: str | None
    tool_args: dict[str, Any] = field(default_factory=dict)
    result: ToolResult | str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    thought: str | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        """Whether this step executed successfully."""
        if isinstance(self.result, ToolResult):
            return self.result.success
        return self.error is None

    @property
    def result_text(self) -> str:
        """Normalized string representation of the step result."""
        if isinstance(self.result, ToolResult):
            return self.result.to_observation()
        if self.result is not None:
            return str(self.result)
        if self.error:
            return f"❌ Failed: {self.error}"
        return "No output"

    def to_dict(self) -> dict[str, Any]:
        """Convert this step record into a serializable dictionary."""
        return {
            "step_number": self.step_number,
            "action": self.action,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "result": self.result_text,
            "timestamp": self.timestamp.isoformat(),
            "thought": self.thought,
            "error": self.error,
            "success": self.success,
        }


class Memory:
    """Tracks execution history, discovered facts, and provides context to the LLM."""

    # Matches pattern [FACT: key=value]
    FACT_PATTERN = re.compile(r"\[FACT:\s*([^=\]]+)=(.*?)\]", re.IGNORECASE)

    def __init__(self) -> None:
        self._steps: list[StepRecord] = []
        self._facts: dict[str, str] = {}
        self._errors: list[str] = []

    def record_step(
        self,
        action: str,
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
        result: ToolResult | str | None = None,
        thought: str | None = None,
        error: str | None = None,
    ) -> StepRecord:
        """
        Create and store a new StepRecord.

        Args:
            action: Human-readable description of the action.
            tool_name: Name of tool invoked, if any.
            tool_args: Arguments passed to the tool.
            result: ToolResult or string result.
            thought: Reasoning/thought accompanying the step.
            error: Error message if failed.

        Returns:
            The created StepRecord.
        """
        step_number = len(self._steps) + 1
        record = StepRecord(
            step_number=step_number,
            action=action,
            tool_name=tool_name,
            tool_args=tool_args or {},
            result=result,
            thought=thought,
            error=error,
        )
        self._steps.append(record)

        if error:
            self._errors.append(f"Step {step_number} ({tool_name or action}): {error}")
        elif isinstance(result, ToolResult) and not result.success:
            err_msg = result.error or result.output
            self._errors.append(f"Step {step_number} ({tool_name or action}): {err_msg}")

        logger.debug(
            "Recorded step %d: tool=%s, success=%s",
            step_number,
            tool_name,
            record.success,
        )
        return record

    def add_step(self, step: StepRecord) -> None:
        """Add an already constructed StepRecord."""
        self._steps.append(step)
        if step.error:
            self._errors.append(f"Step {step.step_number}: {step.error}")

    def add_fact(self, key: str, value: str) -> None:
        """
        Store a discovered fact as a key-value pair.

        Args:
            key: Fact identifier (e.g., 'invoice_amount', 'user_email').
            value: Discovered value.
        """
        cleaned_key = key.strip()
        cleaned_val = value.strip()
        self._facts[cleaned_key] = cleaned_val
        logger.debug("Fact stored: %s = %s", cleaned_key, cleaned_val)

    def get_fact(self, key: str) -> str | None:
        """Retrieve a specific fact by key, returning None if not found."""
        return self._facts.get(key.strip())

    def get_facts(self) -> dict[str, str]:
        """Return a copy of all discovered facts."""
        return dict(self._facts)

    def add_error(self, error: str) -> None:
        """Record an error string encountered during execution."""
        cleaned = error.strip()
        if cleaned:
            self._errors.append(cleaned)
            logger.warning("Error recorded in memory: %s", cleaned)

    def get_errors(self) -> list[str]:
        """Return a copy of all recorded errors."""
        return list(self._errors)

    def get_steps(self) -> list[StepRecord]:
        """Return a copy of all step records in chronological order."""
        return list(self._steps)

    def get_step(self, step_number: int) -> StepRecord | None:
        """Get a step by 1-indexed step number."""
        if 1 <= step_number <= len(self._steps):
            return self._steps[step_number - 1]
        return None

    def get_step_count(self) -> int:
        """Return the total number of steps recorded so far."""
        return len(self._steps)

    def record_facts_from_text(self, text: str | None) -> list[tuple[str, str]]:
        """
        Parse and store any [FACT: key=value] tokens found in the given text.

        Args:
            text: Text to scan for fact tokens.

        Returns:
            List of (key, value) pairs extracted.
        """
        if not text:
            return []

        extracted: list[tuple[str, str]] = []
        for match in self.FACT_PATTERN.finditer(text):
            k, v = match.group(1).strip(), match.group(2).strip()
            self.add_fact(k, v)
            extracted.append((k, v))
        return extracted

    def get_context_summary(self, detailed_steps: int = 5) -> str:
        """
        Generate a structured summary of execution history, facts, and errors.
        Recent steps are detailed while older steps are summarized to save context window.

        Args:
            detailed_steps: Number of most recent steps to display with full details.

        Returns:
            Formatted context summary string.
        """
        sections: list[str] = []

        # --- Section 1: Execution History ---
        total_steps = len(self._steps)
        if total_steps == 0:
            sections.append("### Execution Steps\nNo steps taken yet.")
        else:
            step_lines: list[str] = ["### Execution Steps"]
            if total_steps > detailed_steps:
                older_count = total_steps - detailed_steps
                step_lines.append(f"*Steps 1 to {older_count} summary:*")
                for s in self._steps[:older_count]:
                    status_icon = "✅" if s.success else "❌"
                    step_lines.append(
                        f"  - Step {s.step_number} [{status_icon}]: {s.action} "
                        f"({s.tool_name or 'no tool'})"
                    )
                step_lines.append(f"\n*Recent steps (Steps {older_count + 1} to {total_steps}):*")
                recent_steps = self._steps[older_count:]
            else:
                recent_steps = self._steps

            for s in recent_steps:
                status_icon = "✅" if s.success else "❌"
                args_preview = json.dumps(s.tool_args) if s.tool_args else "{}"
                if len(args_preview) > 120:
                    args_preview = args_preview[:117] + "..."
                step_lines.append(
                    f"- Step {s.step_number} [{status_icon}] {s.action}\n"
                    f"  Tool: {s.tool_name or 'None'} with args {args_preview}\n"
                    f"  Result: {s.result_text[:300]}"
                )
            sections.append("\n".join(step_lines))

        # --- Section 2: Discovered Facts ---
        facts_lines = ["### Discovered Facts"]
        if self._facts:
            for k, v in self._facts.items():
                facts_lines.append(f"- **{k}**: {v}")
        else:
            facts_lines.append("None discovered yet.")
        sections.append("\n".join(facts_lines))

        # --- Section 3: Errors Encountered ---
        errors_lines = ["### Errors Encountered"]
        if self._errors:
            for err in self._errors:
                errors_lines.append(f"- ⚠️ {err}")
        else:
            errors_lines.append("None encountered.")
        sections.append("\n".join(errors_lines))

        return "\n\n".join(sections)

    def clear(self) -> None:
        """Reset all memory state."""
        self._steps.clear()
        self._facts.clear()
        self._errors.clear()
        logger.debug("Memory cleared")
