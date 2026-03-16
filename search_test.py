#!/usr/bin/env python3
"""Minimal test harness for the shopping search endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from api import shopping


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call api.shopping.search_products with a user-provided query."
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Search term to send to the Magento storefront.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=5,
        help="Number of products to request (default: %(default)s).",
    )
    parser.add_argument(
        "--username",
        help="Customer username/email for login. Prompted if omitted.",
    )
    parser.add_argument(
        "--password",
        help="Customer password for login. Prompted if omitted.",
    )
    return parser.parse_args()


def _unwrap_tool(func):
    """Return the raw coroutine function behind a FastMCP FunctionTool."""

    for attr in ("fn", "func", "__wrapped__"):
        candidate = getattr(func, attr, None)
        if candidate is not None:
            func = candidate
            break
    return func


async def customer_login(username: str, password: str) -> Any:
    """Authenticate before exercising search."""

    login_fn = _unwrap_tool(shopping.customer_login)
    credentials = shopping.AuthCredentials(username=username, password=password)
    return await login_fn(credentials=credentials)


async def run_search(query: str, page_size: int) -> Any:
    """Invoke the search endpoint and return the payload."""

    func = _unwrap_tool(shopping.search_products)
    return await func(search_term=query, page_size=page_size)


def main() -> None:
    args = parse_args()
    query = args.query or input("Enter a product search term: ").strip()
    if not query:
        raise SystemExit("A search term is required.")
    username = args.username or input("Customer username/email: ").strip()
    password = args.password or input("Customer password: ").strip()
    if not username or not password:
        raise SystemExit("Username and password are required to login.")

    async def workflow():
        await customer_login(username=username, password=password)
        return await run_search(query, args.page_size)

    result = asyncio.run(workflow())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
