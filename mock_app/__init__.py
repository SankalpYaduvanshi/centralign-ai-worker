"""
CentrAlign Mock Company Application Package.
Simulates internal company portals and APIs for testing autonomous task workers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mock_app.models import (
    Contact,
    ExpenseCreate,
    ExpenseEntry,
    Invoice,
    InvoiceItem,
    TaskItem,
    TaskUpdate,
)
from mock_app.seed_data import get_seed_data

if TYPE_CHECKING:
    from mock_app.routes import router, store
    from mock_app.server import (
        app,
        start_server,
        start_server_background,
        stop_server_background,
    )


def __getattr__(name: str) -> Any:
    """Lazy-load server and route objects to prevent circular/runpy warnings."""
    if name in ("router", "store"):
        from mock_app import routes
        return getattr(routes, name)
    if name in ("app", "start_server", "start_server_background", "stop_server_background"):
        from mock_app import server
        return getattr(server, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "app",
    "router",
    "store",
    "get_seed_data",
    "start_server",
    "start_server_background",
    "stop_server_background",
    "Invoice",
    "InvoiceItem",
    "ExpenseEntry",
    "ExpenseCreate",
    "Contact",
    "TaskItem",
    "TaskUpdate",
]
