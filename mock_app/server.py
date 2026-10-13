"""
Server module for the CentrAlign Internal Portal mock application.
Initializes FastAPI, mounts static assets, registers routes, and provides
synchronous and background server startup helpers.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Ensure project root is in sys.path for config import
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config import config
from mock_app.routes import router, store

logger = logging.getLogger(__name__)

# Static assets directory
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Create the FastAPI application
app = FastAPI(
    title="CentrAlign Internal Portal",
    description="Mock internal company portal for Autonomous AI Task Worker automation and API testing.",
    version="1.0.0",
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include web and API routes
app.include_router(router)


def start_server(
    host: str | None = None,
    port: int | None = None,
    reload: bool = False,
    log_level: str = "info",
) -> None:
    """
    Start the CentrAlign Portal server synchronously using uvicorn.

    Args:
        host: Host IP to bind (defaults to config.MOCK_APP_HOST)
        port: Port number to bind (defaults to config.MOCK_APP_PORT)
        reload: Enable uvicorn autoreload
        log_level: Logging verbosity level (e.g. 'info', 'warning', 'debug')
    """
    server_host = host or config.MOCK_APP_HOST
    server_port = port or config.MOCK_APP_PORT
    logger.info(
        "Starting CentrAlign Internal Portal on http://%s:%d",
        server_host,
        server_port,
    )
    uvicorn.run(
        app,
        host=server_host,
        port=server_port,
        reload=reload,
        log_level=log_level,
    )


async def start_server_background(
    host: str | None = None,
    port: int | None = None,
    log_level: str = "warning",
) -> tuple[asyncio.Task, uvicorn.Server]:
    """
    Start the server in an asynchronous background task.
    Waits until the server has bound and started before returning.

    Args:
        host: Host IP to bind (defaults to config.MOCK_APP_HOST)
        port: Port number to bind (defaults to config.MOCK_APP_PORT)
        log_level: Logging verbosity level

    Returns:
        A tuple of (asyncio.Task, uvicorn.Server) for server control.
    """
    server_host = host or config.MOCK_APP_HOST
    server_port = port or config.MOCK_APP_PORT

    server_config = uvicorn.Config(
        app=app,
        host=server_host,
        port=server_port,
        log_level=log_level,
        loop="asyncio",
    )
    server = uvicorn.Server(server_config)
    task = asyncio.create_task(server.serve())

    # Wait until server has successfully started or failed
    retries = 60
    while not server.started and retries > 0:
        await asyncio.sleep(0.05)
        retries -= 1

    logger.info(
        "CentrAlign Internal Portal background server listening on http://%s:%d",
        server_host,
        server_port,
    )
    return task, server


async def stop_server_background(
    server: uvicorn.Server, task: asyncio.Task | None = None
) -> None:
    """
    Gracefully shut down a background server instance.

    Args:
        server: The uvicorn.Server instance to shut down
        task: The asyncio.Task running server.serve()
    """
    server.should_exit = True
    if task:
        await task
    logger.info("CentrAlign Internal Portal background server stopped.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    start_server()
