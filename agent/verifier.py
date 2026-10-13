"""
Verification system for the Autonomous AI Task Worker.
Verifies whether the agent's task was actually completed successfully
using both programmatic checks and LLM-based evaluation.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from agent.memory import Memory
from llm.provider import LLMProvider
from tools.base import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Standardized result of task verification."""

    verified: bool
    confidence: float  # 0.0 to 1.0
    evidence: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert verification result to dictionary."""
        return {
            "verified": self.verified,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "concerns": self.concerns,
            "summary": self.summary,
        }


class Verifier:
    """Verifies whether the agent's task was actually completed successfully."""

    VERIFICATION_SYSTEM_PROMPT = """You are a rigorous Quality and Verification Auditor for an autonomous AI agent system.
Your job is to objectively evaluate whether the agent has genuinely achieved the user's end goal.

Analyze the execution critically:
1. What was the user's specific end goal?
2. What concrete steps were taken by the agent?
3. What factual evidence exists in the tool outputs confirming completion?
4. Are there any indicators of failure, unhandled errors, hallucinated claims, or missed instructions?

You must respond with a strictly valid JSON object conforming to this schema:
{
  "verified": true | false,
  "confidence": 0.0 to 1.0,
  "evidence": ["list of concrete facts/outputs proving success"],
  "concerns": ["list of unresolved errors, risks, or missing steps"],
  "summary": "Brief 1-3 sentence evaluation summary"
}

Do not include any text outside the JSON object.
"""

    def __init__(self) -> None:
        pass

    async def verify(
        self,
        original_task: str,
        memory: Memory,
        tools: ToolRegistry,
        llm: LLMProvider,
    ) -> VerificationResult:
        """
        Verify if the given task was completed successfully.

        Args:
            original_task: The original task description prompt.
            memory: The agent's memory containing steps, facts, and errors.
            tools: Registry of available tools for programmatic inspection.
            llm: LLM provider for reasoning and verification.

        Returns:
            VerificationResult detailing verification status, confidence, evidence, and concerns.
        """
        logger.info("Starting verification for task: %s", original_task)

        # 1. Edge case: No steps taken
        if memory.get_step_count() == 0:
            return VerificationResult(
                verified=False,
                confidence=1.0,
                evidence=[],
                concerns=["No actions or steps were executed by the agent."],
                summary="Task unfulfilled: No steps were taken.",
            )

        # 2. Attempt programmatic checks where applicable
        programmatic_evidence: list[str] = []
        programmatic_concerns: list[str] = []

        try:
            await self._run_programmatic_checks(
                memory=memory,
                tools=tools,
                evidence_out=programmatic_evidence,
                concerns_out=programmatic_concerns,
            )
        except Exception as exc:
            logger.warning("Programmatic verification check encountered error: %s", exc)
            programmatic_concerns.append(f"Programmatic check error: {exc}")

        # 3. LLM verification analysis
        llm_result = await self._run_llm_analysis(
            original_task=original_task,
            memory=memory,
            llm=llm,
            programmatic_evidence=programmatic_evidence,
            programmatic_concerns=programmatic_concerns,
        )

        # Merge programmatic findings with LLM findings
        merged_evidence = list(dict.fromkeys(programmatic_evidence + llm_result.evidence))
        merged_concerns = list(dict.fromkeys(programmatic_concerns + llm_result.concerns))

        # Adjust confidence and verification if there are severe programmatic concerns
        verified = llm_result.verified
        confidence = llm_result.confidence

        if programmatic_concerns and verified:
            confidence = max(0.0, confidence - 0.25)
            if confidence < 0.5:
                verified = False

        if not memory.get_steps()[-1].success and verified:
            # If the final step ended in an unhandled error, reduce confidence
            confidence = min(confidence, 0.4)
            verified = False
            merged_concerns.append("The final recorded execution step ended with a failure.")

        return VerificationResult(
            verified=verified,
            confidence=round(confidence, 2),
            evidence=merged_evidence,
            concerns=merged_concerns,
            summary=llm_result.summary or ("Task verified successfully." if verified else "Task verification failed."),
        )

    async def _run_programmatic_checks(
        self,
        memory: Memory,
        tools: ToolRegistry,
        evidence_out: list[str],
        concerns_out: list[str],
    ) -> None:
        """
        Attempt programmatic verification based on memory and available tools.
        Checks for:
        - Created/written files on disk
        - API read-backs if an API tool exists and a resource was created
        - Browser page verification if a browser tool is active
        """
        steps = memory.get_steps()
        facts = memory.get_facts()

        for step in steps:
            # Check for file writes
            if step.tool_name in ("write_file", "save_file", "create_file", "edit_file"):
                file_path = step.tool_args.get("path") or step.tool_args.get("file_path") or step.tool_args.get("filename")
                if file_path and isinstance(file_path, str):
                    if os.path.exists(file_path):
                        size = os.path.getsize(file_path)
                        evidence_out.append(f"Programmatic check: File '{file_path}' exists with size {size} bytes.")
                    else:
                        concerns_out.append(f"Programmatic check: Target file '{file_path}' was not found on disk.")

            # Check for API creation with potential read-back
            if step.tool_name in ("api_request", "http_request", "call_api"):
                method = str(step.tool_args.get("method", "")).upper()
                endpoint = str(step.tool_args.get("endpoint", step.tool_args.get("url", "")))
                if method == "POST" and step.success:
                    # Check if response data contains an id or created object
                    created_id = None
                    if isinstance(step.result, ToolResult) and step.result.data:
                        created_id = step.result.data.get("id") or step.result.data.get("item_id")
                    if not created_id and facts.get("created_id"):
                        created_id = facts.get("created_id")

                    if created_id:
                        evidence_out.append(f"Programmatic check: Resource created at {endpoint} with ID {created_id}.")

        # Check browser state if a browser inspection tool exists
        browser_tool = tools.get("browser_state") or tools.get("browser_get_page") or tools.get("browser_inspect")
        if browser_tool:
            try:
                res = await browser_tool.execute()
                if res.success and res.output:
                    evidence_out.append(f"Programmatic check: Current browser state verified: {res.output[:150]}")
            except Exception as e:
                logger.debug("Browser programmatic check skipped: %s", e)

    async def _run_llm_analysis(
        self,
        original_task: str,
        memory: Memory,
        llm: LLMProvider,
        programmatic_evidence: list[str],
        programmatic_concerns: list[str],
    ) -> VerificationResult:
        """Query LLM to evaluate execution history against the original task."""
        context_summary = memory.get_context_summary(detailed_steps=8)
        facts = memory.get_facts()
        errors = memory.get_errors()

        prompt_parts = [
            f"ORIGINAL TASK:\n{original_task}\n",
            f"EXECUTION HISTORY & MEMORY SUMMARY:\n{context_summary}\n",
            f"DISCOVERED FACTS:\n{json.dumps(facts, indent=2)}\n",
            f"ERRORS ENCOUNTERED:\n{json.dumps(errors, indent=2)}\n",
        ]

        if programmatic_evidence:
            prompt_parts.append(
                f"PROGRAMMATIC EVIDENCE DETECTED:\n" + "\n".join(f"- {e}" for e in programmatic_evidence) + "\n"
            )
        if programmatic_concerns:
            prompt_parts.append(
                f"PROGRAMMATIC CONCERNS DETECTED:\n" + "\n".join(f"- {c}" for c in programmatic_concerns) + "\n"
            )

        prompt_parts.append(
            "Please analyze whether the original task's end goal has been achieved, "
            "and output the JSON verification assessment."
        )

        user_prompt = "\n".join(prompt_parts)

        messages = [
            {"role": "system", "content": self.VERIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await llm.chat(messages=messages, temperature=0.1)
            raw_content = response.content or "{}"
            parsed = self._parse_llm_json(raw_content)
            return parsed
        except Exception as exc:
            logger.error("LLM verification failed with error: %s", exc, exc_info=True)
            return VerificationResult(
                verified=False,
                confidence=0.3,
                evidence=[],
                concerns=[f"Verification evaluation failed with LLM error: {exc}"],
                summary="Verification could not complete due to an evaluation error.",
            )

    def _parse_llm_json(self, content: str) -> VerificationResult:
        """Robustly parse the JSON response from the LLM."""
        cleaned = content.strip()

        # Remove markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        # Extract json object if surrounded by text
        json_match = re.search(r"(\{[\s\S]*\})", cleaned)
        if json_match:
            cleaned = json_match.group(1)

        try:
            data = json.loads(cleaned)
            verified = bool(data.get("verified", False))
            confidence = float(data.get("confidence", 0.5 if verified else 0.2))
            confidence = max(0.0, min(1.0, confidence))
            evidence = [str(e) for e in data.get("evidence", [])]
            concerns = [str(c) for c in data.get("concerns", [])]
            summary = str(data.get("summary", ""))

            return VerificationResult(
                verified=verified,
                confidence=confidence,
                evidence=evidence,
                concerns=concerns,
                summary=summary,
            )
        except Exception as exc:
            logger.warning("Failed to parse JSON verification response: %s (raw content: %s)", exc, content)
            # Fallback heuristic
            verified = "true" in cleaned.lower() and "verified" in cleaned.lower()
            return VerificationResult(
                verified=verified,
                confidence=0.4,
                evidence=[],
                concerns=["LLM output could not be parsed as structured JSON"],
                summary=cleaned[:200],
            )
