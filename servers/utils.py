"""
Shared utilities for MCP servers.
"""

import json
from typing import Any

MAX_RESPONSE_CHARS = 50_000  # ~50 KB — safe limit for MCP SSE transport


def truncate_mcp_response(data: Any, max_chars: int = MAX_RESPONSE_CHARS) -> Any:
    """
    Ensure an MCP tool response fits within the SSE transport size limit.

    Large API responses (e.g. message histories, user lists) exceed the MCP
    SSE transport's effective single-message size and get truncated mid-JSON,
    causing a pydantic ValidationError: 'EOF while parsing a string'.

    Strategy:
    - If the serialized response is under the limit, return it unchanged.
    - Otherwise, trim the largest list fields one item at a time until it fits,
      then add a '_truncated' note so the agent knows to paginate.
    """
    if json.dumps(data, default=str).__len__() <= max_chars:
        return data

    if not isinstance(data, dict):
        # Non-dict (e.g. bare list or string) — just stringify and slice
        text = json.dumps(data, default=str)
        return {"_truncated": True, "partial_data": text[:max_chars], "_note": "Response truncated. Request smaller pages."}

    result = dict(data)

    # Repeatedly shrink the largest list until we fit
    for _ in range(1000):
        serialized = json.dumps(result, default=str)
        if len(serialized) <= max_chars:
            break

        # Find the largest list field
        list_fields = {k: v for k, v in result.items() if isinstance(v, list)}
        if not list_fields:
            # No more lists to shrink — hard truncate as last resort
            result = {"_truncated": True, "_note": "Response too large to transmit. Use pagination parameters (limit/cursor/page)."}
            break

        largest_key = max(list_fields, key=lambda k: len(json.dumps(list_fields[k], default=str)))
        current = result[largest_key]
        if len(current) == 0:
            break
        result[largest_key] = current[: max(1, len(current) // 2)]
        result["_truncated"] = True
        result["_note"] = f"Field '{largest_key}' truncated. Use pagination parameters (limit/cursor/page) for full results."

    return result
