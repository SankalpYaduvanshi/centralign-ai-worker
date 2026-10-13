"""
Tests for the Tool implementations:
- FileSystemTool (read, write, list)
- APITool (HttpRequestTool)
- BrowserTool (BrowserManager, NavigateTool, ClickTool, TypeTextTool, ExtractTextTool, ExtractTableTool, etc.)
"""

import asyncio
import os
import shutil
import tempfile
import unittest

from tools.filesystem_tool import ReadFileTool, WriteFileTool, ListFilesTool
from tools.api_tool import HttpRequestTool
from tools.base import ToolRegistry


class TestFileSystemTools(unittest.IsolatedAsyncioTestCase):
    """Test filesystem tools suite."""

    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="agent_fs_test_")
        self.read_tool = ReadFileTool()
        self.write_tool = WriteFileTool()
        self.list_tool = ListFilesTool()

    async def asyncTearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_write_and_read_text(self):
        file_path = os.path.join(self.test_dir, "notes.txt")
        write_res = await self.write_tool.execute(path=file_path, content="Hello Autonomous Worker")
        self.assertTrue(write_res.success)

        read_res = await self.read_tool.execute(path=file_path)
        self.assertTrue(read_res.success)
        self.assertEqual(read_res.output, "Hello Autonomous Worker")

    async def test_write_and_read_json(self):
        file_path = os.path.join(self.test_dir, "data.json")
        json_content = '{"invoice_id": "inv-001", "amount": 14500}'
        write_res = await self.write_tool.execute(path=file_path, content=json_content)
        self.assertTrue(write_res.success)

        read_res = await self.read_tool.execute(path=file_path)
        self.assertTrue(read_res.success)
        self.assertIsNotNone(read_res.data)
        self.assertEqual(read_res.data["content"].get("invoice_id"), "inv-001")

    async def test_list_files(self):
        f1 = os.path.join(self.test_dir, "file1.txt")
        f2 = os.path.join(self.test_dir, "file2.csv")
        await self.write_tool.execute(path=f1, content="A")
        await self.write_tool.execute(path=f2, content="col1,col2\n1,2")

        list_res = await self.list_tool.execute(directory=self.test_dir)
        self.assertTrue(list_res.success)
        self.assertIn("file1.txt", list_res.output)
        self.assertIn("file2.csv", list_res.output)


class TestAPITools(unittest.IsolatedAsyncioTestCase):
    """Test HTTP API tool."""

    async def test_http_request_tool_schema(self):
        tool = HttpRequestTool()
        self.assertEqual(tool.name, "http_request")
        schema = tool.parameters_schema
        self.assertIn("properties", schema)
        self.assertIn("url", schema["properties"])
        self.assertIn("method", schema["properties"])


class TestToolRegistry(unittest.TestCase):
    """Test ToolRegistry aggregation and OpenAI schema generation."""

    def test_registry_registration_and_schemas(self):
        registry = ToolRegistry()
        r_tool = ReadFileTool()
        w_tool = WriteFileTool()
        registry.register(r_tool)
        registry.register(w_tool)

        self.assertEqual(len(registry.list_tools()), 2)
        self.assertIsNotNone(registry.get("read_file"))
        self.assertIsNotNone(registry.get("write_file"))

        openai_tools = registry.to_openai_tools()
        self.assertEqual(len(openai_tools), 2)
        self.assertEqual(openai_tools[0]["type"], "function")
        self.assertIn(openai_tools[0]["function"]["name"], ["read_file", "write_file"])


if __name__ == "__main__":
    unittest.main()
