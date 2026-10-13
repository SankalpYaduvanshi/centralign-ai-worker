"""
Browser automation tools powered by Playwright for the Autonomous AI Task Worker.

Provides individual tool classes managed by a shared BrowserManager singleton:
- BrowserManager: Manages the browser lifecycle, contexts, pages, and screenshots.
- NavigateTool: Navigates to a given URL.
- ClickTool: Clicks elements matching CSS selectors.
- TypeTextTool: Fills text into input fields and forms.
- ExtractTextTool: Extracts text content from page elements.
- ExtractTableTool: Extracts structured table data as lists of dictionaries.
- GetPageInfoTool: Extracts URL, title, and interactive element inventory.
- ScreenshotTool: Captures base64-encoded screenshots of the page.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from config import config
from tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)


class BrowserManager:
    """
    Shared singleton manager for Playwright browser automation.

    Provides lazy initialization of the Chromium browser, page access,
    context management, base64 screenshot capture, and clean shutdown.
    """

    _instance: BrowserManager | None = None

    def __new__(cls, *args: Any, **kwargs: Any) -> BrowserManager:
        """Ensure singleton pattern across all tool instances."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, headless: bool | None = None, timeout: int | None = None) -> None:
        """
        Initialize the browser manager with configuration options.

        Args:
            headless: Whether to run the browser in headless mode. Defaults to config setting.
            timeout: Default timeout in milliseconds for browser operations.
        """
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.headless: bool = headless if headless is not None else config.BROWSER_HEADLESS
        self.timeout: int = timeout if timeout is not None else config.BROWSER_TIMEOUT
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> BrowserManager:
        """Get or create the singleton BrowserManager instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (useful in test teardowns)."""
        cls._instance = None

    async def get_page(self) -> Page:
        """
        Lazily initialize Playwright, browser, context, and page on first use.

        Returns:
            The active Playwright Page instance.
        """
        async with self._lock:
            if self._playwright is None:
                logger.info("Initializing Playwright runtime...")
                self._playwright = await async_playwright().start()

            if self._browser is None:
                logger.info("Launching Chromium browser (headless=%s)...", self.headless)
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                )

            if self._context is None:
                self._context = await self._browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                    ),
                )

            if self._page is None or self._page.is_closed():
                self._page = await self._context.new_page()
                self._page.set_default_timeout(self.timeout)

            return self._page

    async def take_screenshot(self, full_page: bool = False) -> str | None:
        """
        Capture a base64-encoded PNG screenshot of the current active page.

        Args:
            full_page: Whether to capture the entire scrollable page height.

        Returns:
            Base64 encoded PNG string, or None if no page is active or capture failed.
        """
        try:
            if self._page and not self._page.is_closed():
                screenshot_bytes = await self._page.screenshot(full_page=full_page)
                return base64.b64encode(screenshot_bytes).decode("utf-8")
        except Exception as e:
            logger.warning("Failed to capture browser screenshot: %s", e)
        return None

    async def cleanup(self) -> None:
        """
        Close page, context, browser, and stop Playwright cleanly.
        Safe to call multiple times (idempotent).
        """
        async with self._lock:
            if self._page is not None:
                try:
                    if not self._page.is_closed():
                        await self._page.close()
                except Exception as e:
                    logger.warning("Error closing page: %s", e)
                finally:
                    self._page = None

            if self._context is not None:
                try:
                    await self._context.close()
                except Exception as e:
                    logger.warning("Error closing browser context: %s", e)
                finally:
                    self._context = None

            if self._browser is not None:
                try:
                    await self._browser.close()
                except Exception as e:
                    logger.warning("Error closing browser: %s", e)
                finally:
                    self._browser = None

            if self._playwright is not None:
                try:
                    await self._playwright.stop()
                except Exception as e:
                    logger.warning("Error stopping Playwright runtime: %s", e)
                finally:
                    self._playwright = None

            logger.info("BrowserManager cleanup completed.")


class _BaseBrowserTool(Tool):
    """Internal base class for tools that interact with BrowserManager."""

    def __init__(self, browser_manager: BrowserManager | None = None) -> None:
        """
        Initialize tool with a shared BrowserManager.

        Args:
            browser_manager: Optional BrowserManager instance. If None, uses singleton.
        """
        self.browser_manager = browser_manager or BrowserManager.get_instance()

    async def cleanup(self) -> None:
        """Clean up shared browser resources when shutting down."""
        await self.browser_manager.cleanup()


class NavigateTool(_BaseBrowserTool):
    """Tool to navigate the browser to a URL and wait for page load."""

    @property
    def name(self) -> str:
        return "browser_navigate"

    @property
    def description(self) -> str:
        return (
            "Navigate to a specified URL, wait for the page to load, and return the page title, "
            "final URL, and a screenshot."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The destination URL to navigate to (e.g. 'http://127.0.0.1:8042').",
                },
            },
            "required": ["url"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute URL navigation and capture page info and screenshot.

        Args:
            url: The destination web address.

        Returns:
            ToolResult containing navigation status, title, URL, and screenshot.
        """
        url = kwargs.get("url")
        if not url:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: 'url'",
            )

        try:
            page = await self.browser_manager.get_page()
            logger.info("Navigating to URL: %s", url)
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.browser_manager.timeout,
            )

            # Wait briefly for full load state if possible
            try:
                await page.wait_for_load_state("load", timeout=5000)
            except Exception:
                pass

            title = await page.title()
            current_url = page.url
            screenshot = await self.browser_manager.take_screenshot()
            status_code = response.status if response else 200

            return ToolResult(
                success=True,
                output=f"Navigated to '{current_url}'. Page title: '{title}' (HTTP {status_code}).",
                data={
                    "url": current_url,
                    "title": title,
                    "status_code": status_code,
                },
                screenshot_b64=screenshot,
            )
        except Exception as e:
            logger.error("Navigation error to %s: %s", url, e)
            screenshot = await self.browser_manager.take_screenshot()
            return ToolResult(
                success=False,
                output=f"Failed to navigate to {url}",
                error=f"Navigation failed: {str(e)}",
                screenshot_b64=screenshot,
            )


class ClickTool(_BaseBrowserTool):
    """Tool to click an element matching a CSS selector and wait for page updates."""

    @property
    def name(self) -> str:
        return "browser_click"

    @property
    def description(self) -> str:
        return (
            "Click an element matching the CSS selector, wait for resulting page updates "
            "or navigation, and return what was clicked and the updated page state."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector of the element to click (e.g. 'button#submit', 'a.nav-link').",
                },
            },
            "required": ["selector"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Click an element by selector, observe state change, and capture screenshot.

        Args:
            selector: CSS selector identifying target element.

        Returns:
            ToolResult containing clicked element information and current page state.
        """
        selector = kwargs.get("selector")
        if not selector:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: 'selector'",
            )

        try:
            page = await self.browser_manager.get_page()
            logger.info("Waiting for element to click: %s", selector)
            element = await page.wait_for_selector(
                selector,
                state="visible",
                timeout=self.browser_manager.timeout,
            )
            if not element:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Element matching selector '{selector}' was not found or is not visible.",
                )

            element_text = (await element.inner_text()).strip() if element else ""
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")

            await element.click()

            # Wait for potential navigation or network activity
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass

            title = await page.title()
            current_url = page.url
            screenshot = await self.browser_manager.take_screenshot()

            return ToolResult(
                success=True,
                output=(
                    f"Clicked <{tag_name}> '{selector}' (text: '{element_text}'). "
                    f"Resulting URL: '{current_url}', Title: '{title}'."
                ),
                data={
                    "selector": selector,
                    "tag": tag_name,
                    "element_text": element_text,
                    "url": current_url,
                    "title": title,
                },
                screenshot_b64=screenshot,
            )
        except Exception as e:
            logger.error("Click error on selector %s: %s", selector, e)
            screenshot = await self.browser_manager.take_screenshot()
            return ToolResult(
                success=False,
                output=f"Failed to click selector: {selector}",
                error=f"Click failed: {str(e)}",
                screenshot_b64=screenshot,
            )


class TypeTextTool(_BaseBrowserTool):
    """Tool to type text into an input field or textarea."""

    @property
    def name(self) -> str:
        return "browser_type"

    @property
    def description(self) -> str:
        return (
            "Type text into an input field or textarea matching the CSS selector. "
            "Optionally clears the field before typing."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector of the input field or textarea.",
                },
                "text": {
                    "type": "string",
                    "description": "The text to type into the field.",
                },
                "clear_first": {
                    "type": "boolean",
                    "description": "Whether to clear existing text before typing. Defaults to true.",
                    "default": True,
                },
            },
            "required": ["selector", "text"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Fill or type text into a form input.

        Args:
            selector: CSS selector for the input element.
            text: Text to enter into the input.
            clear_first: If True, clears existing content first.

        Returns:
            ToolResult confirming successful typing operation.
        """
        selector = kwargs.get("selector")
        text = kwargs.get("text")
        clear_first = kwargs.get("clear_first", True)

        if not selector:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: 'selector'",
            )
        if text is None:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: 'text'",
            )

        text_str = str(text)

        try:
            page = await self.browser_manager.get_page()
            logger.info("Locating input element to type: %s", selector)
            element = await page.wait_for_selector(
                selector,
                state="visible",
                timeout=self.browser_manager.timeout,
            )
            if not element:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Element matching selector '{selector}' not found or not visible.",
                )

            if clear_first:
                await page.fill(selector, text_str)
            else:
                await element.focus()
                await element.type(text_str)

            return ToolResult(
                success=True,
                output=f"Successfully typed text into '{selector}' (length: {len(text_str)} chars).",
                data={
                    "selector": selector,
                    "text_length": len(text_str),
                    "clear_first": clear_first,
                },
            )
        except Exception as e:
            logger.error("Typing error on selector %s: %s", selector, e)
            return ToolResult(
                success=False,
                output=f"Failed to type into {selector}",
                error=f"Type operation failed: {str(e)}",
            )


class ExtractTextTool(_BaseBrowserTool):
    """Tool to extract text content from an element or the entire page body."""

    @property
    def name(self) -> str:
        return "browser_extract_text"

    @property
    def description(self) -> str:
        return (
            "Extract text content from an element matching the CSS selector (defaults to 'body')."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector to extract text from. Defaults to 'body'.",
                    "default": "body",
                },
            },
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Extract visible text from the specified selector.

        Args:
            selector: CSS selector to extract from. Defaults to 'body'.

        Returns:
            ToolResult containing extracted text in output and data.
        """
        selector = kwargs.get("selector") or "body"

        try:
            page = await self.browser_manager.get_page()
            logger.info("Extracting text from selector: %s", selector)
            element = await page.wait_for_selector(
                selector,
                timeout=self.browser_manager.timeout,
            )
            if not element:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Element matching selector '{selector}' was not found.",
                )

            text = (await element.inner_text()).strip()
            return ToolResult(
                success=True,
                output=text if text else "[No text content found]",
                data={
                    "selector": selector,
                    "text": text,
                    "character_count": len(text),
                },
            )
        except Exception as e:
            logger.error("Extract text error on %s: %s", selector, e)
            return ToolResult(
                success=False,
                output=f"Failed to extract text from {selector}",
                error=f"Extract text failed: {str(e)}",
            )


class ExtractTableTool(_BaseBrowserTool):
    """Tool to extract HTML table data into a structured list of dictionaries."""

    @property
    def name(self) -> str:
        return "browser_extract_table"

    @property
    def description(self) -> str:
        return (
            "Extract table data as a structured list of dictionaries with header columns as keys."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for the table element (e.g. 'table#invoices', '.data-table').",
                },
            },
            "required": ["selector"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Extract table headers and rows as structured dictionaries.

        Args:
            selector: CSS selector matching the table element.

        Returns:
            ToolResult with structured row list in data and readable preview in output.
        """
        selector = kwargs.get("selector")
        if not selector:
            return ToolResult(
                success=False,
                output="",
                error="Missing required parameter: 'selector'",
            )

        try:
            page = await self.browser_manager.get_page()
            logger.info("Extracting table from selector: %s", selector)
            element = await page.wait_for_selector(
                selector,
                timeout=self.browser_manager.timeout,
            )
            if not element:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Table matching selector '{selector}' was not found.",
                )

            extracted = await element.evaluate(
                """(table) => {
                    const headers = [];
                    // Extract headers from thead th/td or first row th
                    const headerCells = table.querySelectorAll('thead th, thead td, tr:first-child th');
                    if (headerCells.length > 0) {
                        headerCells.forEach((th, idx) => {
                            const txt = th.innerText.trim();
                            headers.push(txt || `col_${idx + 1}`);
                        });
                    }

                    const rows = [];
                    const trs = Array.from(table.querySelectorAll('tr'));
                    let startIndex = 0;

                    if (headerCells.length > 0 && trs.length > 0 && trs[0].querySelector('th')) {
                        startIndex = 1;
                    }

                    for (let i = startIndex; i < trs.length; i++) {
                        const tr = trs[i];
                        if (tr.parentElement && tr.parentElement.tagName.toLowerCase() === 'thead') {
                            continue;
                        }
                        const cells = tr.querySelectorAll('td, th');
                        if (cells.length === 0) continue;

                        const rowData = {};
                        cells.forEach((td, idx) => {
                            const key = headers[idx] || `col_${idx + 1}`;
                            rowData[key] = td.innerText.trim();
                        });
                        rows.push(rowData);
                    }

                    return { headers, rows };
                }"""
            )

            headers: list[str] = extracted.get("headers", [])
            rows: list[dict[str, Any]] = extracted.get("rows", [])

            lines = [f"Table from '{selector}' ({len(rows)} rows):"]
            if headers:
                lines.append("Columns: " + ", ".join(headers))
            for i, r in enumerate(rows[:10]):
                lines.append(f"  Row {i + 1}: {r}")
            if len(rows) > 10:
                lines.append(f"  ... ({len(rows) - 10} more rows)")

            return ToolResult(
                success=True,
                output="\n".join(lines),
                data={
                    "selector": selector,
                    "headers": headers,
                    "rows": rows,
                    "count": len(rows),
                },
            )
        except Exception as e:
            logger.error("Extract table error on %s: %s", selector, e)
            return ToolResult(
                success=False,
                output=f"Failed to extract table from {selector}",
                error=f"Extract table failed: {str(e)}",
            )


class GetPageInfoTool(_BaseBrowserTool):
    """Tool to extract the current URL, page title, and interactive element inventory."""

    @property
    def name(self) -> str:
        return "browser_get_page_info"

    @property
    def description(self) -> str:
        return (
            "Get current URL, title, and a structured inventory of visible interactive elements "
            "(links, buttons, inputs, selects) with their CSS selectors and text."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Inspect the active page and inventory interactive elements.

        Returns:
            ToolResult containing current page URL, title, and interactive element list.
        """
        try:
            page = await self.browser_manager.get_page()
            url = page.url
            title = await page.title()

            elements: list[dict[str, Any]] = await page.evaluate(
                """() => {
                    const isVisible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        return style.display !== 'none' &&
                               style.visibility !== 'hidden' &&
                               style.opacity !== '0' &&
                               el.offsetWidth > 0 &&
                               el.offsetHeight > 0;
                    };

                    const candidates = document.querySelectorAll(
                        'a[href], button, input, select, textarea, [role="button"], [role="link"], [onclick]'
                    );

                    const results = [];
                    for (let i = 0; i < candidates.length && results.length < 100; i++) {
                        const el = candidates[i];
                        if (!isVisible(el)) continue;

                        const tag = el.tagName.toLowerCase();
                        const id = el.id ? `#${el.id}` : '';
                        const name = el.getAttribute('name') || '';
                        const type = el.getAttribute('type') || '';
                        
                        let text = '';
                        if (tag === 'input' && (type === 'button' || type === 'submit')) {
                            text = el.value || '';
                        } else if (tag === 'input' || tag === 'textarea') {
                            text = el.placeholder || el.getAttribute('aria-label') || el.value || '';
                        } else {
                            text = el.innerText || el.getAttribute('aria-label') || '';
                        }
                        text = text.trim().replace(/\\s+/g, ' ').substring(0, 80);

                        let selector = tag;
                        if (el.id) {
                            selector = `#${el.id}`;
                        } else if (name) {
                            selector = `${tag}[name="${name}"]`;
                        } else if (el.getAttribute('data-testid')) {
                            selector = `[data-testid="${el.getAttribute('data-testid')}"]`;
                        } else if (el.className && typeof el.className === 'string') {
                            const classes = el.className.trim().split(/\\s+/).filter(c => !c.includes(':')).slice(0, 2).join('.');
                            if (classes) {
                                selector = `${tag}.${classes}`;
                            }
                        }

                        results.push({
                            tag,
                            selector,
                            type: type || undefined,
                            name: name || undefined,
                            id: el.id || undefined,
                            text: text || undefined,
                            href: el.getAttribute('href') || undefined,
                        });
                    }
                    return results;
                }"""
            )

            output_lines = [
                f"Page URL: {url}",
                f"Page Title: '{title}'",
                f"Interactive Elements ({len(elements)} found):",
            ]
            for el in elements:
                parts = [f"<{el['tag']}>"]
                if el.get("type"):
                    parts.append(f"type='{el['type']}'")
                if el.get("name"):
                    parts.append(f"name='{el['name']}'")
                if el.get("text"):
                    parts.append(f"text='{el['text']}'")
                if el.get("href"):
                    parts.append(f"href='{el['href']}'")
                parts.append(f"selector='{el['selector']}'")
                output_lines.append("  - " + " ".join(parts))

            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                data={
                    "url": url,
                    "title": title,
                    "interactive_elements": elements,
                    "count": len(elements),
                },
            )
        except Exception as e:
            logger.error("GetPageInfo error: %s", e)
            return ToolResult(
                success=False,
                output="Failed to get page information",
                error=f"GetPageInfo failed: {str(e)}",
            )


class ScreenshotTool(_BaseBrowserTool):
    """Tool to capture a screenshot of the current page as a base64 PNG."""

    @property
    def name(self) -> str:
        return "browser_screenshot"

    @property
    def description(self) -> str:
        return (
            "Capture a screenshot of the current browser page and return it as a base64-encoded PNG."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "full_page": {
                    "type": "boolean",
                    "description": "Whether to capture the entire scrollable page height. Defaults to false.",
                    "default": False,
                },
            },
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Capture a base64 screenshot of the active page.

        Args:
            full_page: Whether to capture full scrollable height.

        Returns:
            ToolResult containing base64 screenshot in screenshot_b64.
        """
        full_page = bool(kwargs.get("full_page", False))
        try:
            page = await self.browser_manager.get_page()
            url = page.url
            title = await page.title()
            screenshot = await self.browser_manager.take_screenshot(full_page=full_page)

            if not screenshot:
                return ToolResult(
                    success=False,
                    output="",
                    error="Failed to generate screenshot bytes from browser.",
                )

            return ToolResult(
                success=True,
                output=f"Captured screenshot of '{url}' (title: '{title}').",
                data={
                    "url": url,
                    "title": title,
                    "full_page": full_page,
                },
                screenshot_b64=screenshot,
            )
        except Exception as e:
            logger.error("Screenshot capture error: %s", e)
            return ToolResult(
                success=False,
                output="Failed to capture screenshot",
                error=f"Screenshot failed: {str(e)}",
            )
