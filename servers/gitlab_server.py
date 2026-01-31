import os
import base64
from urllib.parse import quote
from typing import Any, Optional

import requests
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("GitLab API Server")

# Configuration
BASE_URL = os.getenv("GITLAB_BASE_URL", "http://127.0.0.1:8023").rstrip("/")
API_PREFIX = "/api/v4"
DEFAULT_TIMEOUT = float(os.getenv("GITLAB_TIMEOUT", "30"))

# Store token for authenticated requests (global; shared across clients)
auth = {
    "token": os.getenv("GITLAB_TOKEN")  # can be None; you can also set via a tool
}

def _gitlab_request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json: dict | None = None,
    token: Optional[str] = None,
) -> Any:
    """
    Core HTTP helper: builds URL, attaches PRIVATE-TOKEN auth, makes request, returns JSON or text.
    """
    tok = token or auth.get("token")
    if not tok:
        raise ValueError("Missing GitLab token. Set GITLAB_TOKEN env var or call gitlab_set_token().")

    url = f"{BASE_URL}{API_PREFIX}{path}"
    headers = {"PRIVATE-TOKEN": tok}

    resp = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        json=json,
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()

    ctype = resp.headers.get("content-type", "")
    return resp.json() if ctype.startswith("application/json") else resp.text

# --- Token management tools ---

@mcp.tool()
def gitlab_set_token(token: str) -> str:
    """Set (or replace) the GitLab token used by this server."""
    auth["token"] = token
    return "ok"

# --- Example GitLab tools ---
@mcp.tool()
def gitlab_get_metadata(token: Optional[str] = None) -> dict[str, Any]:
    """
    Retrieve metadata information for this GitLab instance.
    GET /api/v4/metadata

    Args:
        token: Optional GitLab token to use for this call (sent as PRIVATE-TOKEN header).
               If not provided, falls back to the server's configured token.
    """
    return _gitlab_request("GET", "/metadata", token=token)


if __name__ == "__main__":
    # Run GitLab MCP server over HTTP (streamable-http transport) so the agent can connect via URL.
    #
    # IMPORTANT:
    # - This server URL (below) is NOT your GitLab instance URL.
    # - Your GitLab instance is at GITLAB_BASE_URL (default http://127.0.0.1:8023).
    # - The MCP server must listen on a DIFFERENT port than GitLab to avoid conflicts.
    from agent.common.configurator import Configurator
    from agent.common.utils import get_mcp_logger

    logger = get_mcp_logger()
    logger.debug("Starting gitlab-mcp server (streamable-http)")

    config = Configurator()
    config.load_mcpserver_env()
    config.load_shared_env()

    # Read URL from config.yaml -> mcp_server.gitlab
    # Example: http://localhost:8001/
    mcp_server_url = config.get_key("mcp_server")["gitlab"]
    hostname, port, path = config.get_hostname_port(mcp_server_url)

    mcp.run(
        transport="streamable-http",
        host=hostname,
        port=port,
        path=path,
    )