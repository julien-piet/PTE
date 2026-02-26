# api/mcp_client.py
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict

from fastmcp import Client


# Central place to configure all your MCP servers
# You can override each URL via environment variables.
SERVER_CONFIG: Dict[str, Dict[str, str]] = {
    "shopping": {
        "env": "Shopping_BASE_URL",
        "default": "127.0.0.1:7770",
    },
    "gitlab": {
        "env": "Gitlab_BASE_URL",
        "default": "127.0.0.1:8023",
    }
    # Example for future servers:
    # "flights": {
    #     "env": "FLIGHTS_MCP_URL",
    #     "default": "http://localhost:8001/mcp",
    # },
}


def _get_server_url(server_name: str) -> str:
    """
    Resolve the MCP server URL for a given logical name.
    Prefers environment variables, falls back to a default.
    """
    if server_name not in SERVER_CONFIG:
        raise ValueError(f"Unknown MCP server: {server_name!r}")

    cfg = SERVER_CONFIG[server_name]
    return os.getenv(cfg["env"], cfg["default"])


@asynccontextmanager
async def mcp_client_for(server_name: str) -> AsyncIterator[Client]:
    """
    Async context manager that yields a connected MCP Client
    for the given server (e.g., 'shopping').

    Usage:
        async with mcp_client_for("shopping") as client:
            result = await client.call_tool("search_products", {...})
    """
    url = _get_server_url(server_name)
    client = Client(url)

    # Manage connection lifecycle
    async with client:
        yield client
