# api/shopping.py
"""
Client wrappers for the WebArena/Magento shopping MCP server.

Each function here calls the corresponding MCP tool defined in `shopping_server.py`,
so agent code can do:

    import api
    result = await api.shopping.search_products("lawnmower", page_size=20)

without needing to know anything about MCP client details.
"""

from __future__ import annotations

from typing import Any, Dict

from .mcp_client import mcp_client_for


async def _call_tool(tool_name: str, params: Dict[str, Any]) -> Any:
    """Internal helper to call a tool on the shopping MCP server."""
    async with mcp_client_for("shopping") as client:
        return await client.call_tool(tool_name, params)


# ---------------------------------------------------------------------------
# Authentication / Account
# ---------------------------------------------------------------------------

async def customer_login(credentials: Any) -> Any:
    """Client wrapper for `customer_login` MCP tool on the shopping server."""
    return await _call_tool("customer_login", {"credentials": credentials})


async def admin_login(credentials: Any) -> Any:
    """Client wrapper for `admin_login` MCP tool on the shopping server."""
    return await _call_tool("admin_login", {"credentials": credentials})


async def customer_logout() -> Any:
    """Client wrapper for `customer_logout` MCP tool on the shopping server."""
    return await _call_tool("customer_logout", {})


async def customer_register(customer: Any) -> Any:
    """Client wrapper for `customer_register` MCP tool on the shopping server."""
    return await _call_tool("customer_register", {"customer": customer})


async def check_email_available(email: Any) -> Any:
    """Client wrapper for `check_email_available` MCP tool on the shopping server."""
    return await _call_tool("check_email_available", {"email": email})


async def get_current_customer() -> Any:
    """Client wrapper for `get_current_customer` MCP tool on the shopping server."""
    return await _call_tool("get_current_customer", {})


async def reset_password_request(
    email: Any,
    template: Any = "email_reset",
) -> Any:
    """Client wrapper for `reset_password_request` MCP tool on the shopping server."""
    return await _call_tool(
        "reset_password_request",
        {"email": email, "template": template},
    )


# ---------------------------------------------------------------------------
# Products / Catalog
# ---------------------------------------------------------------------------

async def get_products(
    page_size: Any = 20,
    current_page: Any = 1,
    sort_field: Any = None,
    sort_direction: Any = None,
) -> Any:
    """Client wrapper for `get_products` MCP tool on the shopping server."""
    return await _call_tool(
        "get_products",
        {
            "page_size": page_size,
            "current_page": current_page,
            "sort_field": sort_field,
            "sort_direction": sort_direction,
        },
    )


async def get_product_by_sku(sku: Any) -> Any:
    """Client wrapper for `get_product_by_sku` MCP tool on the shopping server."""
    return await _call_tool("get_product_by_sku", {"sku": sku})


async def create_product(
    product: Any,
    use_admin: Any = True,
) -> Any:
    """Client wrapper for `create_product` MCP tool on the shopping server."""
    return await _call_tool(
        "create_product",
        {"product": product, "use_admin": use_admin},
    )


async def update_product(
    sku: Any,
    updates: Any,
    use_admin: Any = True,
) -> Any:
    """Client wrapper for `update_product` MCP tool on the shopping server."""
    return await _call_tool(
        "update_product",
        {"sku": sku, "updates": updates, "use_admin": use_admin},
    )


async def delete_product(
    sku: Any,
    use_admin: Any = True,
) -> Any:
    """Client wrapper for `delete_product` MCP tool on the shopping server."""
    return await _call_tool(
        "delete_product",
        {"sku": sku, "use_admin": use_admin},
    )


async def get_product_attributes() -> Any:
    """Client wrapper for `get_product_attributes` MCP tool on the shopping server."""
    return await _call_tool("get_product_attributes", {})


async def get_product_types() -> Any:
    """Client wrapper for `get_product_types` MCP tool on the shopping server."""
    return await _call_tool("get_product_types", {})


async def search_products(
    search_term: Any,
    page_size: Any = 20,
) -> Any:
    """Client wrapper for `search_products` MCP tool on the shopping server."""
    return await _call_tool(
        "search_products",
        {"search_term": search_term, "page_size": page_size},
    )


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

async def get_categories() -> Any:
    """Client wrapper for `get_categories` MCP tool on the shopping server."""
    return await _call_tool("get_categories", {})


async def get_category(category_id: Any) -> Any:
    """Client wrapper for `get_category` MCP tool on the shopping server."""
    return await _call_tool("get_category", {"category_id": category_id})


async def create_category(
    name: Any,
    is_active: Any = True,
    parent_id: Any = 2,
    use_admin: Any = True,
) -> Any:
    """Client wrapper for `create_category` MCP tool on the shopping server."""
    return await _call_tool(
        "create_category",
        {
            "name": name,
            "is_active": is_active,
            "parent_id": parent_id,
            "use_admin": use_admin,
        },
    )


async def get_category_products(category_id: Any) -> Any:
    """Client wrapper for `get_category_products` MCP tool on the shopping server."""
    return await _call_tool(
        "get_category_products",
        {"category_id": category_id},
    )


# ---------------------------------------------------------------------------
# Carts (Customer & Guest)
# ---------------------------------------------------------------------------

async def create_cart() -> Any:
    """Client wrapper for `create_cart` MCP tool on the shopping server."""
    return await _call_tool("create_cart", {})


async def create_guest_cart() -> Any:
    """Client wrapper for `create_guest_cart` MCP tool on the shopping server."""
    return await _call_tool("create_guest_cart", {})


async def get_cart() -> Any:
    """Client wrapper for `get_cart` MCP tool on the shopping server."""
    return await _call_tool("get_cart", {})


async def get_guest_cart(cart_id: Any) -> Any:
    """Client wrapper for `get_guest_cart` MCP tool on the shopping server."""
    return await _call_tool("get_guest_cart", {"cart_id": cart_id})


async def add_to_cart(item: Any) -> Any:
    """Client wrapper for `add_to_cart` MCP tool on the shopping server."""
    return await _call_tool("add_to_cart", {"item": item})


async def add_to_guest_cart(
    cart_id: Any,
    sku: Any,
    qty: Any,
) -> Any:
    """Client wrapper for `add_to_guest_cart` MCP tool on the shopping server."""
    return await _call_tool(
        "add_to_guest_cart",
        {"cart_id": cart_id, "sku": sku, "qty": qty},
    )


async def get_cart_items() -> Any:
    """Client wrapper for `get_cart_items` MCP tool on the shopping server."""
    return await _call_tool("get_cart_items", {})


async def update_cart_item(
    item_id: Any,
    qty: Any,
) -> Any:
    """Client wrapper for `update_cart_item` MCP tool on the shopping server."""
    return await _call_tool(
        "update_cart_item",
        {"item_id": item_id, "qty": qty},
    )


async def remove_from_cart(item_id: Any) -> Any:
    """Client wrapper for `remove_from_cart` MCP tool on the shopping server."""
    return await _call_tool("remove_from_cart", {"item_id": item_id})


async def get_cart_totals() -> Any:
    """Client wrapper for `get_cart_totals` MCP tool on the shopping server."""
    return await _call_tool("get_cart_totals", {})


async def apply_coupon(coupon_code: Any) -> Any:
    """Client wrapper for `apply_coupon` MCP tool on the shopping server."""
    return await _call_tool("apply_coupon", {"coupon_code": coupon_code})


async def remove_coupon() -> Any:
    """Client wrapper for `remove_coupon` MCP tool on the shopping server."""
    return await _call_tool("remove_coupon", {})


# ---------------------------------------------------------------------------
# Checkout / Shipping / Payment
# ---------------------------------------------------------------------------

async def set_shipping_address(address: Any) -> Any:
    """Client wrapper for `set_shipping_address` MCP tool on the shopping server."""
    return await _call_tool("set_shipping_address", {"address": address})


async def set_billing_address(address: Any) -> Any:
    """Client wrapper for `set_billing_address` MCP tool on the shopping server."""
    return await _call_tool("set_billing_address", {"address": address})


async def get_shipping_methods() -> Any:
    """Client wrapper for `get_shipping_methods` MCP tool on the shopping server."""
    return await _call_tool("get_shipping_methods", {})


async def get_payment_methods() -> Any:
    """Client wrapper for `get_payment_methods` MCP tool on the shopping server."""
    return await _call_tool("get_payment_methods", {})


async def place_order(
    payment_method: Any = "checkmo",
) -> Any:
    """Client wrapper for `place_order` MCP tool on the shopping server."""
    return await _call_tool(
        "place_order",
        {"payment_method": payment_method},
    )


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

async def get_orders(
    page_size: Any = 20,
    current_page: Any = 1,
) -> Any:
    """Client wrapper for `get_orders` MCP tool on the shopping server."""
    return await _call_tool(
        "get_orders",
        {"page_size": page_size, "current_page": current_page},
    )


async def get_order(order_id: Any) -> Any:
    """Client wrapper for `get_order` MCP tool on the shopping server."""
    return await _call_tool("get_order", {"order_id": order_id})


async def cancel_order(order_id: Any) -> Any:
    """Client wrapper for `cancel_order` MCP tool on the shopping server."""
    return await _call_tool("cancel_order", {"order_id": order_id})


async def add_order_comment(
    order_id: Any,
    comment: Any,
    is_visible: Any = True,
) -> Any:
    """Client wrapper for `add_order_comment` MCP tool on the shopping server."""
    return await _call_tool(
        "add_order_comment",
        {"order_id": order_id, "comment": comment, "is_visible": is_visible},
    )


async def create_invoice(order_id: Any) -> Any:
    """Client wrapper for `create_invoice` MCP tool on the shopping server."""
    return await _call_tool("create_invoice", {"order_id": order_id})


async def create_shipment(order_id: Any) -> Any:
    """Client wrapper for `create_shipment` MCP tool on the shopping server."""
    return await _call_tool("create_shipment", {"order_id": order_id})


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

async def get_customers(
    page_size: Any = 20,
    current_page: Any = 1,
) -> Any:
    """Client wrapper for `get_customers` MCP tool on the shopping server."""
    return await _call_tool(
        "get_customers",
        {"page_size": page_size, "current_page": current_page},
    )


async def get_customer(customer_id: Any) -> Any:
    """Client wrapper for `get_customer` MCP tool on the shopping server."""
    return await _call_tool("get_customer", {"customer_id": customer_id})


async def update_customer(
    customer_id: Any,
    updates: Any,
) -> Any:
    """Client wrapper for `update_customer` MCP tool on the shopping server."""
    return await _call_tool(
        "update_customer",
        {"customer_id": customer_id, "updates": updates},
    )


async def delete_customer(customer_id: Any) -> Any:
    """Client wrapper for `delete_customer` MCP tool on the shopping server."""
    return await _call_tool("delete_customer", {"customer_id": customer_id})


async def get_customer_groups() -> Any:
    """Client wrapper for `get_customer_groups` MCP tool on the shopping server."""
    return await _call_tool("get_customer_groups", {})


# ---------------------------------------------------------------------------
# Inventory / Stock
# ---------------------------------------------------------------------------

async def get_stock_status(sku: Any) -> Any:
    """Client wrapper for `get_stock_status` MCP tool on the shopping server."""
    return await _call_tool("get_stock_status", {"sku": sku})


async def check_product_salable(
    sku: Any,
    stock_id: Any = 1,
) -> Any:
    """Client wrapper for `check_product_salable` MCP tool on the shopping server."""
    return await _call_tool(
        "check_product_salable",
        {"sku": sku, "stock_id": stock_id},
    )


async def get_sources() -> Any:
    """Client wrapper for `get_sources` MCP tool on the shopping server."""
    return await _call_tool("get_sources", {})


async def get_stocks() -> Any:
    """Client wrapper for `get_stocks` MCP tool on the shopping server."""
    return await _call_tool("get_stocks", {})


# ---------------------------------------------------------------------------
# Store / Configuration
# ---------------------------------------------------------------------------

async def get_store_config() -> Any:
    """Client wrapper for `get_store_config` MCP tool on the shopping server."""
    return await _call_tool("get_store_config", {})


async def get_websites() -> Any:
    """Client wrapper for `get_websites` MCP tool on the shopping server."""
    return await _call_tool("get_websites", {})


async def get_store_views() -> Any:
    """Client wrapper for `get_store_views` MCP tool on the shopping server."""
    return await _call_tool("get_store_views", {})


async def get_countries() -> Any:
    """Client wrapper for `get_countries` MCP tool on the shopping server."""
    return await _call_tool("get_countries", {})


async def get_currency() -> Any:
    """Client wrapper for `get_currency` MCP tool on the shopping server."""
    return await _call_tool("get_currency", {})


# ---------------------------------------------------------------------------
# CMS / Tax / Sales Rules
# ---------------------------------------------------------------------------

async def get_cms_pages(page_size: Any = 20) -> Any:
    """Client wrapper for `get_cms_pages` MCP tool on the shopping server."""
    return await _call_tool("get_cms_pages", {"page_size": page_size})


async def get_cms_page(page_id: Any) -> Any:
    """Client wrapper for `get_cms_page` MCP tool on the shopping server."""
    return await _call_tool("get_cms_page", {"page_id": page_id})


async def get_cms_blocks(page_size: Any = 20) -> Any:
    """Client wrapper for `get_cms_blocks` MCP tool on the shopping server."""
    return await _call_tool("get_cms_blocks", {"page_size": page_size})


async def get_tax_classes() -> Any:
    """Client wrapper for `get_tax_classes` MCP tool on the shopping server."""
    return await _call_tool("get_tax_classes", {})


async def get_tax_rates() -> Any:
    """Client wrapper for `get_tax_rates` MCP tool on the shopping server."""
    return await _call_tool("get_tax_rates", {})


async def get_tax_rules() -> Any:
    """Client wrapper for `get_tax_rules` MCP tool on the shopping server."""
    return await _call_tool("get_tax_rules", {})


async def get_sales_rules(page_size: Any = 20) -> Any:
    """Client wrapper for `get_sales_rules` MCP tool on the shopping server."""
    return await _call_tool("get_sales_rules", {"page_size": page_size})


async def get_sales_rule(rule_id: Any) -> Any:
    """Client wrapper for `get_sales_rule` MCP tool on the shopping server."""
    return await _call_tool("get_sales_rule", {"rule_id": rule_id})


async def search_coupons(page_size: Any = 20) -> Any:
    """Client wrapper for `search_coupons` MCP tool on the shopping server."""
    return await _call_tool("search_coupons", {"page_size": page_size})


# ---------------------------------------------------------------------------
# Auth Token Management
# ---------------------------------------------------------------------------

async def set_auth_token(
    token: Any,
    token_type: Any = "customer",
) -> Any:
    """Client wrapper for `set_auth_token` MCP tool on the shopping server."""
    return await _call_tool(
        "set_auth_token",
        {"token": token, "token_type": token_type},
    )


async def get_current_tokens() -> Any:
    """Client wrapper for `get_current_tokens` MCP tool on the shopping server."""
    return await _call_tool("get_current_tokens", {})


async def clear_tokens() -> Any:
    """Client wrapper for `clear_tokens` MCP tool on the shopping server."""
    return await _call_tool("clear_tokens", {})
