#!/usr/bin/env python3
"""
Reddit MCP Server - FastMCP implementation for this repo's Reddit-like REST API.

Aligned with `servers/shopping_server.py`:
- executable `@mcp.tool()` functions
- shared HTTP request helper
- `__main__` runs FastMCP over `streamable-http`, binding host/port/path from `config/config.yaml`

Notes:
- `REDDIT_BASE_URL` is the backend app base URL (the API you want to call).
- `mcp_server.reddit` in `config/config.yaml` is the MCP server URL the agent connects to.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Literal, Optional

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

# Initialize FastMCP server
mcp = FastMCP("Reddit API Server")

# ---------------------------------------------------------------------------
# Backend API configuration (THIS is the Reddit-like app base URL)
# ---------------------------------------------------------------------------

BASE_URL = (
    os.getenv("REDDIT_BASE_URL")
    or os.getenv("Reddit_BASE_URL")
    or "http://127.0.0.1:9999"
).rstrip("/")
DEFAULT_TIMEOUT = float(os.getenv("REDDIT_TIMEOUT", "30"))

# Optional bearer tokens for the backend (not MCP auth)
auth_tokens: Dict[str, Optional[str]] = {
    "user": os.getenv("REDDIT_USER_TOKEN") or os.getenv("REDDIT_TOKEN"),
    "moderator": os.getenv("REDDIT_MODERATOR_TOKEN"),
}


class TokenSetRequest(BaseModel):
    """Set a token used for backend requests made by this MCP server."""

    token_type: Literal["user", "moderator"] = Field(default="user", description="Which token slot to set")
    token: str = Field(description="Bearer token value (without the 'Bearer ' prefix)")


class ForumData(BaseModel):
    """Forum payload (schema depends on your backend)."""

    forum_data: Dict[str, Any] = Field(description="ForumData payload as an object")


class CommentUpdate(BaseModel):
    """Comment update payload."""

    content: str = Field(description="Updated comment content")


class SubmissionBody(BaseModel):
    """Submission create/update payload (schema depends on your backend)."""

    body: Dict[str, Any] = Field(description="Submission payload as an object")


class PreferencesBody(BaseModel):
    """User preferences update payload (schema depends on your backend)."""

    body: Dict[str, Any] = Field(description="Preferences payload as an object")


async def make_request(
    method: str,
    endpoint: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    token: Optional[str] = None,
    use_moderator: bool = False,
) -> Any:
    """Make HTTP request to the Reddit-like backend."""
    url = f"{BASE_URL}{endpoint}"
    headers: Dict[str, str] = {"Content-Type": "application/json"}

    tok = token or (auth_tokens["moderator"] if use_moderator else auth_tokens["user"])
    if tok:
        headers["Authorization"] = f"Bearer {tok}"

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        try:
            resp = await client.request(method=method, url=url, headers=headers, params=params, json=data)
            resp.raise_for_status()
            ctype = resp.headers.get("content-type", "")
            if ctype.startswith("application/json"):
                return resp.json()
            return {"result": resp.text}
        except httpx.HTTPStatusError as e:
            return {
                "error": True,
                "status_code": e.response.status_code,
                "message": e.response.text,
                "url": url,
            }
        except Exception as e:
            return {"error": True, "message": str(e), "url": url}


# ---------------------------------------------------------------------------
# Token utilities
# ---------------------------------------------------------------------------

@mcp.tool()
async def reddit_set_token(req: TokenSetRequest) -> Dict[str, str]:
    """Set the bearer token used for backend requests from this MCP server."""
    auth_tokens[req.token_type] = req.token
    return {"message": f"Token set for {req.token_type}"}


@mcp.tool()
async def reddit_get_current_tokens() -> Dict[str, Optional[str]]:
    """Return which tokens are currently set (masked)."""

    def mask(t: Optional[str]) -> Optional[str]:
        if not t:
            return None
        if len(t) <= 10:
            return "***"
        return f"{t[:4]}***{t[-4:]}"

    return {"user": mask(auth_tokens["user"]), "moderator": mask(auth_tokens["moderator"])}


@mcp.tool()
async def reddit_clear_tokens() -> Dict[str, str]:
    """Clear stored tokens."""
    auth_tokens["user"] = None
    auth_tokens["moderator"] = None
    return {"message": "All tokens cleared"}


# ---------------------------------------------------------------------------
# Forums
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_forum_by_id(id: int) -> Any:
    """Retrieve a forum by ID. GET /api/forums/{id}"""
    return await make_request("GET", f"/api/forums/{id}")


@mcp.tool()
async def get_forum_by_name(name: str) -> Any:
    """Retrieve a forum by name. GET /api/forums/by_name/{name}"""
    return await make_request("GET", f"/api/forums/by_name/{name}")


@mcp.tool()
async def create_forum(payload: ForumData) -> Any:
    """Create a new forum. POST /api/forums"""
    return await make_request("POST", "/api/forums", data={"forum_data": payload.forum_data}, use_moderator=True)


@mcp.tool()
async def update_forum(id: int, payload: ForumData) -> Any:
    """Update an existing forum. PUT /api/forums/{id}"""
    return await make_request("PUT", f"/api/forums/{id}", data={"forum_data": payload.forum_data}, use_moderator=True)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

@mcp.tool()
async def list_comments() -> Any:
    """List all comments. GET /api/comments"""
    return await make_request("GET", "/api/comments")


@mcp.tool()
async def read_comment(id: int) -> Any:
    """Read a specific comment. GET /api/comments/{id}"""
    return await make_request("GET", f"/api/comments/{id}")


@mcp.tool()
async def update_comment(id: int, payload: CommentUpdate) -> Any:
    """Update a specific comment. PUT /api/comments/{id}"""
    return await make_request("PUT", f"/api/comments/{id}", data={"content": payload.content})


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------

@mcp.tool()
async def list_submissions(
    sortBy: Optional[str] = None,
    filter: Optional[Literal["featured", "subscribed", "moderated", "all"]] = None,
) -> Any:
    """List submissions (front page). GET /api/submissions"""
    params: Dict[str, Any] = {}
    if sortBy is not None:
        params["sortBy"] = sortBy
    if filter is not None:
        params["filter"] = filter
    return await make_request("GET", "/api/submissions", params=params or None)


@mcp.tool()
async def read_submission(id: int) -> Any:
    """Read a submission by ID. GET /api/submissions/{id}"""
    return await make_request("GET", f"/api/submissions/{id}")


@mcp.tool()
async def create_submission(payload: SubmissionBody) -> Any:
    """Create a submission. POST /api/submissions"""
    return await make_request("POST", "/api/submissions", data={"body": payload.body})


@mcp.tool()
async def update_submission(id: int, payload: SubmissionBody) -> Any:
    """Update a submission. PUT /api/submissions/{id}"""
    return await make_request("PUT", f"/api/submissions/{id}", data={"body": payload.body})


@mcp.tool()
async def delete_submission(id: int) -> Any:
    """Delete a submission. DELETE /api/submissions/{id}"""
    return await make_request("DELETE", f"/api/submissions/{id}")


@mcp.tool()
async def get_submission_comments(id: int) -> Any:
    """Get comments for a submission. GET /api/submissions/{id}/comments"""
    return await make_request("GET", f"/api/submissions/{id}/comments")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_user_details(id: int) -> Any:
    """Retrieve user details by ID. GET /api/users/{id}"""
    return await make_request("GET", f"/api/users/{id}")


@mcp.tool()
async def get_current_user_details() -> Any:
    """Retrieve current user's details. GET /api/users/self"""
    return await make_request("GET", "/api/users/self")


@mcp.tool()
async def get_user_preferences(id: int) -> Any:
    """Retrieve user preferences. GET /api/users/{id}/preferences"""
    return await make_request("GET", f"/api/users/{id}/preferences")


@mcp.tool()
async def update_user_preferences(id: int, payload: PreferencesBody) -> Any:
    """Update user preferences. PUT /api/users/{id}/preferences"""
    return await make_request("PUT", f"/api/users/{id}/preferences", data={"body": payload.body})


@mcp.tool()
async def get_user_submissions(id: int) -> Any:
    """Retrieve user submissions. GET /api/users/{id}/submissions"""
    return await make_request("GET", f"/api/users/{id}/submissions")


@mcp.tool()
async def get_user_moderated_forums(id: int) -> Any:
    """Retrieve forums moderated by a user. GET /api/users/{id}/moderator_of"""
    return await make_request("GET", f"/api/users/{id}/moderator_of")


# ---------------------------------------------------------------------------
# Run the MCP server (streamable-http), aligned with shopping_server.py
# ---------------------------------------------------------------------------

from agent.common.configurator import Configurator
from agent.common.utils import get_mcp_logger

logger = get_mcp_logger()

if __name__ == "__main__":
    print("Starting reddit-mcp server")
    logger.debug("Starting reddit-mcp server")

    config = Configurator()
    config.load_mcpserver_env()
    config.load_shared_env()

    # Read URL from config.yaml -> mcp_server.reddit (fallback to env/default)
    mcp_servers = config.get_key("mcp_server") or {}
    mcp_server_url = mcp_servers.get("reddit") or os.getenv("REDDIT_MCP_SERVER_URL") or "http://localhost:8002/"
    hostname, port, path = config.get_hostname_port(mcp_server_url)

    mcp.run(
        transport="streamable-http",
        host=hostname,
        port=port,
        path=path,
    )

