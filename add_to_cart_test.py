#!/usr/bin/env python3
"""Simple sanity test that creates a cart and adds a product by SKU."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, List, Optional

from api import shopping


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a cart (if needed) and add a product via api.shopping.add_to_cart."
    )
    parser.add_argument(
        "sku",
        nargs="?",
        help="Product SKU to add to the cart.",
    )
    parser.add_argument(
        "--qty",
        type=float,
        default=1.0,
        help="Quantity to add (default: %(default)s).",
    )
    parser.add_argument(
        "--quote-id",
        help="Existing cart/quote ID. If omitted, the script creates one.",
    )
    return parser.parse_args()


def _unwrap_tool(func):
    """Return the raw coroutine behind a FastMCP FunctionTool."""

    for attr in ("fn", "func", "__wrapped__"):
        candidate = getattr(func, attr, None)
        if candidate is not None:
            func = candidate
            break
    return func


async def create_cart() -> Any:
    """Create a customer cart and return the API response."""

    func = _unwrap_tool(shopping.create_cart)
    return await func()


async def add_to_cart(sku: str, qty: float, quote_id: Optional[str]) -> Any:
    """Call the add_to_cart endpoint."""

    func = _unwrap_tool(shopping.add_to_cart)
    cart_item = shopping.CartItem(sku=sku, qty=qty, quote_id=quote_id)
    return await func(item=cart_item)


async def get_cart_items() -> Any:
    """Fetch the current cart contents."""

    func = _unwrap_tool(shopping.get_cart_items)
    return await func()


async def clear_cart_items() -> List[int]:
    """Remove every current item from the customer's cart."""

    items = await get_cart_items()
    remover = _unwrap_tool(shopping.remove_from_cart)
    removed_ids: List[int] = []
    for item_id in _collect_item_ids(items):
        try:
            numeric_id = int(item_id)
        except (ValueError, TypeError):
            continue
        await remover(item_id=numeric_id)
        removed_ids.append(numeric_id)
    return removed_ids


def _extract_quote_id(response: Any) -> str:
    """Best-effort extraction of a quote/cart identifier from create_cart."""

    if isinstance(response, dict):
        for key in ("id", "quote_id", "cart_id"):
            value = response.get(key)
            if value:
                return str(value)
    return str(response)


def _find_cart_item(payload: Any, sku: str) -> Optional[Any]:
    """Search the cart payload for an entry with the requested SKU."""

    def _walk(node: Any) -> Optional[Any]:
        if isinstance(node, dict):
            candidate = node.get("sku") or node.get("product_sku")
            if candidate == sku:
                return node
            for value in node.values():
                match = _walk(value)
                if match is not None:
                    return match
        elif isinstance(node, list):
            for item in node:
                match = _walk(item)
                if match is not None:
                    return match
        return None

    return _walk(payload)


def _collect_item_ids(payload: Any) -> List[Any]:
    """Return a list of all item_id or quote_item_id values in the payload."""

    ids: List[Any] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for key in ("item_id", "quote_item_id"):
                if key in node:
                    ids.append(node[key])
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for element in node:
                _walk(element)

    _walk(payload)
    return ids


def main() -> None:
    args = parse_args()
    sku = args.sku or input("Enter the SKU to add to the cart: ").strip()
    if not sku:
        raise SystemExit("A product SKU is required.")

    async def workflow():
        quote_id = args.quote_id
        if not quote_id:
            cart_response = await create_cart()
            quote_id_local = _extract_quote_id(cart_response)
            print(f"Created cart with ID: {quote_id_local}")
            quote_id_used = quote_id_local
        else:
            quote_id_used = args.quote_id

        cleared_item_ids = await clear_cart_items()
        add_result = await add_to_cart(
            sku=sku, qty=args.qty, quote_id=quote_id_used
        )
        items = await get_cart_items()
        matched_item = _find_cart_item(items, sku)
        return {
            "quote_id": quote_id_used,
            "cleared_item_ids": cleared_item_ids,
            "add_result": add_result,
            "cart_items": items,
            "matched_item": matched_item,
            "added_qty": args.qty,
            "sku": sku,
        }

    payload = asyncio.run(workflow())

    if payload["matched_item"] is None:
        raise SystemExit(
            f"SKU {payload['sku']} not found in cart after add.\n"
            f"Cart payload: {json.dumps(payload['cart_items'], indent=2, default=str)}"
        )

    # print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
