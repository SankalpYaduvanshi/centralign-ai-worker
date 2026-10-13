"""
File system tools for the Autonomous AI Task Worker.

Provides tools for reading, writing, and listing files:
- ReadFileTool: Reads text, JSON, and CSV files, returning structured data for CSV/JSON.
- WriteFileTool: Writes text content to disk, creating directories as needed.
- ListFilesTool: Lists directory contents with item types and human-readable sizes.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from typing import Any

from tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)


def _format_size(size_bytes: int) -> str:
    """Format byte count into a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


class ReadFileTool(Tool):
    """Tool to read content from files (supporting plain text, CSV, and JSON)."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read and return the content of a file. Supports .txt, .csv, and .json files. "
            "Returns structured records for CSV files and parsed JSON data."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read (relative or absolute).",
                },
            },
            "required": ["path"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Read the specified file and return its content or structured data.

        Args:
            path: Path to the target file.

        Returns:
            ToolResult containing file text or parsed data.
        """
        path_str = kwargs.get("path")
        if not path_str:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: 'path'",
            )

        try:
            file_path = Path(path_str).resolve()
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File not found: '{path_str}' (resolved: {file_path})",
                )

            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Target path is not a file: '{path_str}'",
                )

            suffix = file_path.suffix.lower()

            # Read content with UTF-8 encoding
            content = file_path.read_text(encoding="utf-8")

            # Parse JSON files
            if suffix == ".json":
                try:
                    parsed_json = json.loads(content)
                    preview = json.dumps(parsed_json, indent=2)
                    if len(preview) > 3000:
                        preview = preview[:3000] + "\n... [truncated]"
                    return ToolResult(
                        success=True,
                        output=f"Read JSON file '{file_path.name}':\n{preview}",
                        data={
                            "path": str(file_path),
                            "content": parsed_json,
                            "type": "json",
                            "size_bytes": len(content.encode("utf-8")),
                        },
                    )
                except json.JSONDecodeError as je:
                    logger.warning("JSON decode error reading %s: %s", file_path, je)
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Failed to parse JSON file '{file_path.name}': {str(je)}",
                    )

            # Parse CSV files
            if suffix == ".csv":
                try:
                    reader = csv.DictReader(io.StringIO(content))
                    rows = [dict(row) for row in reader]
                    fieldnames = list(reader.fieldnames or [])

                    summary_lines = [
                        f"Read CSV file '{file_path.name}' with {len(rows)} row(s).",
                        f"Columns: {', '.join(fieldnames)}",
                    ]
                    for i, r in enumerate(rows[:5]):
                        summary_lines.append(f"  Row {i + 1}: {r}")
                    if len(rows) > 5:
                        summary_lines.append(f"  ... ({len(rows) - 5} more rows)")

                    return ToolResult(
                        success=True,
                        output="\n".join(summary_lines),
                        data={
                            "path": str(file_path),
                            "headers": fieldnames,
                            "rows": rows,
                            "count": len(rows),
                            "type": "csv",
                            "size_bytes": len(content.encode("utf-8")),
                        },
                    )
                except Exception as ce:
                    logger.warning("CSV parse error reading %s: %s", file_path, ce)
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Failed to parse CSV file '{file_path.name}': {str(ce)}",
                    )

            # Plain text and all other text file types
            output_preview = content
            if len(output_preview) > 4000:
                output_preview = output_preview[:4000] + "\n... [truncated]"

            return ToolResult(
                success=True,
                output=output_preview,
                data={
                    "path": str(file_path),
                    "content": content,
                    "type": "text",
                    "character_count": len(content),
                    "size_bytes": len(content.encode("utf-8")),
                },
            )

        except PermissionError as pe:
            logger.error("Permission denied reading %s: %s", path_str, pe)
            return ToolResult(
                success=False,
                output="",
                error=f"Permission denied reading file: '{path_str}'",
            )
        except UnicodeDecodeError as ue:
            logger.error("Encoding error reading %s: %s", path_str, ue)
            return ToolResult(
                success=False,
                output="",
                error=f"Unable to decode file as UTF-8: '{path_str}' ({str(ue)})",
            )
        except Exception as e:
            logger.error("Error reading file %s: %s", path_str, e)
            return ToolResult(
                success=False,
                output="",
                error=f"Error reading file '{path_str}': {str(e)}",
            )


class WriteFileTool(Tool):
    """Tool to write text content to disk."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "Write content to a file at the specified path. "
            "Creates parent directories if they do not exist."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to create or overwrite.",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write into the file.",
                },
            },
            "required": ["path", "content"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Write text content to a destination file path.

        Args:
            path: Destination file path.
            content: Text content to write.

        Returns:
            ToolResult confirming file path and byte count.
        """
        path_str = kwargs.get("path")
        content = kwargs.get("content")

        if not path_str:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: 'path'",
            )
        if content is None:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: 'content'",
            )

        try:
            file_path = Path(path_str).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)

            text_content = str(content)
            file_path.write_text(text_content, encoding="utf-8")
            bytes_written = len(text_content.encode("utf-8"))

            logger.info("Wrote %d bytes to %s", bytes_written, file_path)
            return ToolResult(
                success=True,
                output=f"Successfully wrote {bytes_written} bytes to '{file_path}'.",
                data={
                    "path": str(file_path),
                    "bytes_written": bytes_written,
                    "character_count": len(text_content),
                },
            )
        except PermissionError as pe:
            logger.error("Permission denied writing %s: %s", path_str, pe)
            return ToolResult(
                success=False,
                output="",
                error=f"Permission denied writing file: '{path_str}'",
            )
        except Exception as e:
            logger.error("Error writing file %s: %s", path_str, e)
            return ToolResult(
                success=False,
                output="",
                error=f"Error writing file '{path_str}': {str(e)}",
            )


class ListFilesTool(Tool):
    """Tool to list directory contents with file sizes and types."""

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return (
            "List files and directories in a directory with file sizes and type indicators. "
            "Defaults to current working directory."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory path to inspect (defaults to current directory '.').",
                    "default": ".",
                },
            },
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        List items in the given directory.

        Args:
            directory: Path to inspect. Defaults to '.'.

        Returns:
            ToolResult containing listing overview and detailed file metadata.
        """
        dir_str = kwargs.get("directory") or "."

        try:
            dir_path = Path(dir_str).resolve()
            if not dir_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Directory does not exist: '{dir_str}' (resolved: {dir_path})",
                )

            if not dir_path.is_dir():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path is not a directory: '{dir_str}'",
                )

            entries: list[dict[str, Any]] = []
            for item in sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                try:
                    is_dir = item.is_dir()
                    size_bytes = 0 if is_dir else item.stat().st_size
                    entries.append({
                        "name": item.name,
                        "path": str(item),
                        "is_dir": is_dir,
                        "size_bytes": size_bytes,
                        "size_human": "<DIR>" if is_dir else _format_size(size_bytes),
                    })
                except (PermissionError, FileNotFoundError):
                    continue

            output_lines = [
                f"Directory contents of '{dir_path}' ({len(entries)} items):",
            ]
            for entry in entries:
                kind = "[DIR] " if entry["is_dir"] else "[FILE]"
                output_lines.append(f"  {kind} {entry['name']:<35} {entry['size_human']}")

            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                data={
                    "directory": str(dir_path),
                    "items": entries,
                    "count": len(entries),
                },
            )
        except PermissionError as pe:
            logger.error("Permission denied listing %s: %s", dir_str, pe)
            return ToolResult(
                success=False,
                output="",
                error=f"Permission denied accessing directory: '{dir_str}'",
            )
        except Exception as e:
            logger.error("Error listing directory %s: %s", dir_str, e)
            return ToolResult(
                success=False,
                output="",
                error=f"Error listing directory '{dir_str}': {str(e)}",
            )
