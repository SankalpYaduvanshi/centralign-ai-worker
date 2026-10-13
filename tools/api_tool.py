"""
API tools for the Autonomous AI Task Worker.

Provides HTTP request capabilities for querying REST APIs and web services:
- HttpRequestTool: Makes GET, POST, PUT, PATCH, DELETE requests using httpx,
  automatically parsing JSON responses and returning status and headers.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)


class HttpRequestTool(Tool):
    """Tool to make HTTP requests (GET, POST, PUT, PATCH, DELETE) using httpx."""

    @property
    def name(self) -> str:
        return "http_request"

    @property
    def description(self) -> str:
        return (
            "Make an HTTP request (GET, POST, PUT, PATCH, DELETE) to an external or local API endpoint. "
            "Returns HTTP status code, headers, and automatically parsed JSON or text body."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "description": "HTTP method to invoke.",
                    "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                    "default": "GET",
                },
                "url": {
                    "type": "string",
                    "description": "The destination endpoint URL (e.g. 'http://127.0.0.1:8042/api/v1/users').",
                },
                "body": {
                    "type": "object",
                    "description": "Optional JSON payload object for POST, PUT, or PATCH requests.",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP request headers dictionary (e.g. {'Authorization': 'Bearer ...'}).",
                },
                "timeout": {
                    "type": "number",
                    "description": "Request timeout in seconds. Defaults to 30.0.",
                    "default": 30.0,
                },
            },
            "required": ["url"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute an HTTP request and return the structured response.

        Args:
            method: HTTP verb (GET, POST, etc.). Defaults to 'GET'.
            url: Destination URL.
            body: Optional JSON dictionary payload.
            headers: Optional headers dictionary.
            timeout: Optional timeout in seconds.

        Returns:
            ToolResult containing status, headers, and body content.
        """
        method = (kwargs.get("method") or "GET").upper()
        url = kwargs.get("url")
        body = kwargs.get("body")
        headers = kwargs.get("headers")
        timeout_val = kwargs.get("timeout")
        timeout = float(timeout_val) if timeout_val is not None else 30.0

        if not url:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: 'url'",
            )

        valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
        if method not in valid_methods:
            return ToolResult(
                success=False,
                output="",
                error=f"Unsupported HTTP method: '{method}'. Supported methods: {', '.join(sorted(valid_methods))}",
            )

        try:
            logger.info("Sending HTTP %s request to %s", method, url)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                req_kwargs: dict[str, Any] = {}
                if headers and isinstance(headers, dict):
                    req_kwargs["headers"] = headers

                if body is not None and method in {"POST", "PUT", "PATCH"}:
                    req_kwargs["json"] = body

                response = await client.request(method=method, url=url, **req_kwargs)

            # Extract response headers
            response_headers = dict(response.headers)

            # Automatically parse JSON response if possible
            parsed_json: Any = None
            is_json = False
            content_type = response.headers.get("content-type", "").lower()

            if "application/json" in content_type or response.text.strip().startswith(("{", "[")):
                try:
                    parsed_json = response.json()
                    is_json = True
                except Exception:
                    parsed_json = None

            body_content = parsed_json if is_json else response.text
            status_code = response.status_code

            # Format body preview for the agent observation
            if is_json:
                body_str = json.dumps(parsed_json, indent=2)
                preview = body_str if len(body_str) <= 3000 else body_str[:3000] + "\n... [truncated]"
            else:
                preview = response.text if len(response.text) <= 3000 else response.text[:3000] + "\n... [truncated]"

            output_summary = (
                f"HTTP {method} {url} -> {status_code} {response.reason_phrase}\n"
                f"Response Body:\n{preview}"
            )

            result_data = {
                "status_code": status_code,
                "reason": response.reason_phrase,
                "headers": response_headers,
                "body": body_content,
                "is_json": is_json,
                "url": str(response.url),
            }

            if response.is_success:
                return ToolResult(
                    success=True,
                    output=output_summary,
                    data=result_data,
                )
            else:
                error_msg = (
                    f"HTTP {status_code} ({response.reason_phrase}) returned from {url}.\n"
                    f"Response: {response.text[:500]}"
                )
                return ToolResult(
                    success=False,
                    output=output_summary,
                    error=error_msg,
                    data=result_data,
                )

        except httpx.TimeoutException as te:
            logger.error("HTTP request timed out for %s %s: %s", method, url, te)
            return ToolResult(
                success=False,
                output="",
                error=f"HTTP request timed out after {timeout} seconds: {url}",
            )
        except httpx.RequestError as re:
            logger.error("HTTP network/request error for %s %s: %s", method, url, re)
            return ToolResult(
                success=False,
                output="",
                error=f"HTTP network request error: {str(re)}",
            )
        except Exception as e:
            logger.error("Unexpected error in HttpRequestTool for %s %s: %s", method, url, e)
            return ToolResult(
                success=False,
                output="",
                error=f"Unexpected error executing HTTP request: {str(e)}",
            )
