#!/usr/bin/env python3
"""
WebArena MCP Server - FastMCP implementation for WebArena/Magento 2 REST APIs
Provides MCP functions for all major e-commerce operations
"""

import os
import json
import httpx
from typing import Optional, Dict, Any, List
from fastmcp import FastMCP
from pydantic import BaseModel, Field

# Initialize FastMCP server
mcp = FastMCP("WebArena API Server")

# Configuration
BASE_URL = os.getenv("WEBARENA_BASE_URL", "http://ec2-18-218-205-96.us-east-2.compute.amazonaws.com:8082/")
API_PREFIX = "/rest/V1"
DEFAULT_TIMEOUT = 30.0

# Store tokens for authenticated requests
auth_tokens = {
    "customer": None,
    "admin": None
}


class AuthCredentials(BaseModel):
    """Authentication credentials"""
    username: str = Field(description="Username or email for authentication")
    password: str = Field(description="Password for authentication")


class CustomerData(BaseModel):
    """Customer data for registration"""
    email: str = Field(description="Customer email address")
    firstname: str = Field(description="Customer first name")
    lastname: str = Field(description="Customer last name")
    password: str = Field(description="Customer password")
    website_id: int = Field(default=1, description="Website ID")
    store_id: int = Field(default=1, description="Store ID")
    group_id: int = Field(default=1, description="Customer group ID")


class ProductData(BaseModel):
    """Product data structure"""
    sku: str = Field(description="Product SKU")
    name: str = Field(description="Product name")
    price: float = Field(description="Product price")
    status: int = Field(default=1, description="Product status (1=enabled)")
    visibility: int = Field(default=4, description="Product visibility")
    type_id: str = Field(default="simple", description="Product type")
    attribute_set_id: int = Field(default=4, description="Attribute set ID")
    weight: Optional[float] = Field(default=1.0, description="Product weight")


class CartItem(BaseModel):
    """Cart item structure"""
    sku: str = Field(description="Product SKU to add to cart")
    qty: float = Field(description="Quantity to add")
    quote_id: Optional[str] = Field(default=None, description="Cart/Quote ID")


class AddressData(BaseModel):
    """Address data structure"""
    firstname: str = Field(description="First name")
    lastname: str = Field(description="Last name")
    street: List[str] = Field(description="Street address lines")
    city: str = Field(description="City")
    postcode: str = Field(description="Postal code")
    telephone: str = Field(description="Phone number")
    country_id: str = Field(default="US", description="Country code")
    region_id: Optional[int] = Field(default=None, description="Region/State ID")
    region: Optional[str] = Field(default=None, description="Region/State name")


# Utility functions
async def make_request(
    method: str,
    endpoint: str,
    data: Optional[Dict[str, Any]] = None,
    token: Optional[str] = None,
    use_admin: bool = False
) -> Dict[str, Any]:
    """Make HTTP request to WebArena API"""
    url = f"{BASE_URL}{API_PREFIX}{endpoint}"
    headers = {"Content-Type": "application/json"}

    # Add authentication token if available
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif use_admin and auth_tokens["admin"]:
        headers["Authorization"] = f"Bearer {auth_tokens['admin']}"
    elif not use_admin and auth_tokens["customer"]:
        headers["Authorization"] = f"Bearer {auth_tokens['customer']}"

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=data
            )
            response.raise_for_status()

            # Handle empty responses
            if response.text:
                return response.json() if response.headers.get("content-type", "").startswith("application/json") else {"result": response.text}
            return {"success": True, "status_code": response.status_code}

        except httpx.HTTPStatusError as e:
            print("HTTP error:", e)
            return {
                "error": True,
                "status_code": e.response.status_code,
                "message": e.response.text,
                "url": url
            }
        except Exception as e:
            print("Request error:", e)
            return {
                "error": True,
                "message": str(e),
                "url": url
            }


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@mcp.tool()
async def customer_login(credentials: AuthCredentials) -> Dict[str, Any]:
    """
    Customer login - Returns authentication token
    POST /V1/integration/customer/token
    """
    result = await make_request(
        "POST",
        "/integration/customer/token",
        {"username": credentials.username, "password": credentials.password}
    )

    if "error" not in result and isinstance(result, str): # FIX
        auth_tokens["customer"] = result
        return {"token": result, "message": "Login successful"}
    return result


@mcp.tool()
async def admin_login(credentials: AuthCredentials) -> Dict[str, Any]:
    """
    Admin login - Returns authentication token
    POST /V1/integration/admin/token
    """
    result = await make_request(
        "POST",
        "/integration/admin/token",
        {"username": credentials.username, "password": credentials.password}
    )

    if "error" not in result and isinstance(result, str):
        auth_tokens["admin"] = result
        return {"token": result, "message": "Admin login successful"}
    return result


@mcp.tool()
async def customer_logout() -> Dict[str, Any]:
    """
    Revoke customer access token (logout)
    POST /V1/integration/customer/revoke-customer-token
    """
    result = await make_request("POST", "/integration/customer/revoke-customer-token")
    print("hello")
    if result != "error":
    # if not result.get("error"):
        auth_tokens["customer"] = None
    return result


@mcp.tool()
async def customer_register(customer: CustomerData) -> Dict[str, Any]:
    """
    Register new customer account
    POST /V1/customers
    """
    data = {
        "customer": {
            "email": customer.email,
            "firstname": customer.firstname,
            "lastname": customer.lastname,
            "website_id": customer.website_id,
            "store_id": customer.store_id,
            "group_id": customer.group_id
        },
        "password": customer.password
    }
    return await make_request("POST", "/customers", data)


@mcp.tool()
async def check_email_available(email: str) -> Dict[str, Any]:
    """
    Check if email is available for registration
    POST /V1/customers/isEmailAvailable
    """
    return await make_request("POST", "/customers/isEmailAvailable", {"customerEmail": email})


@mcp.tool()
async def get_current_customer() -> Dict[str, Any]:
    """
    Get current logged-in customer information
    GET /V1/customers/me
    """
    return await make_request("GET", "/customers/me")


@mcp.tool()
async def reset_password_request(email: str, template: str = "email_reset") -> Dict[str, Any]:
    """
    Request password reset email
    PUT /V1/customers/password
    """
    return await make_request("PUT", "/customers/password", {
        "email": email,
        "template": template,
        "websiteId": 1
    })


# ============================================================================
# PRODUCT MANAGEMENT ENDPOINTS
# ============================================================================

@mcp.tool()
async def get_products(
    page_size: int = 20,
    current_page: int = 1,
    sort_field: Optional[str] = None,
    sort_direction: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get list of products with pagination
    GET /V1/products
    """
    params = f"?searchCriteria[pageSize]={page_size}&searchCriteria[currentPage]={current_page}"
    if sort_field:
        params += f"&searchCriteria[sortOrders][0][field]={sort_field}"
        if sort_direction:
            params += f"&searchCriteria[sortOrders][0][direction]={sort_direction}"

    return await make_request("GET", f"/products{params}", use_admin=True)


@mcp.tool()
async def get_product_by_sku(sku: str) -> Dict[str, Any]:
    """
    Get product details by SKU
    GET /V1/products/:sku
    """
    return await make_request("GET", f"/products/{sku}", use_admin=True)


@mcp.tool()
async def create_product(product: ProductData, use_admin: bool = True) -> Dict[str, Any]:
    """
    Create new product (requires admin token)
    POST /V1/products
    """
    data = {
        "product": {
            "sku": product.sku,
            "name": product.name,
            "price": product.price,
            "status": product.status,
            "visibility": product.visibility,
            "type_id": product.type_id,
            "attribute_set_id": product.attribute_set_id,
            "weight": product.weight
        }
    }
    return await make_request("POST", "/products", data, use_admin=use_admin)


@mcp.tool()
async def update_product(sku: str, updates: Dict[str, Any], use_admin: bool = True) -> Dict[str, Any]:
    """
    Update existing product (requires admin token)
    PUT /V1/products/:sku
    """
    data = {"product": updates}
    return await make_request("PUT", f"/products/{sku}", data, use_admin=use_admin)


@mcp.tool()
async def delete_product(sku: str, use_admin: bool = True) -> Dict[str, Any]:
    """
    Delete product by SKU (requires admin token)
    DELETE /V1/products/:sku
    """
    return await make_request("DELETE", f"/products/{sku}", use_admin=use_admin)


@mcp.tool()
async def get_product_attributes() -> Dict[str, Any]:
    """
    Get list of all product attributes
    GET /V1/products/attributes
    """
    return await make_request("GET", "/products/attributes?searchCriteria[pageSize]=100", use_admin=True)


@mcp.tool()
async def get_product_types() -> Dict[str, Any]:
    """
    Get list of available product types
    GET /V1/products/types
    """
    return await make_request("GET", "/products/types", use_admin=True)


@mcp.tool()
async def search_products(search_term: str, page_size: int = 20) -> Dict[str, Any]:
    """
    Search products by keyword
    GET /V1/products (with search filter)
    """
    params = (
        f"?searchCriteria[filter_groups][0][filters][0][field]=name"
        f"&searchCriteria[filter_groups][0][filters][0][value]=%{search_term}%"
        f"&searchCriteria[filter_groups][0][filters][0][condition_type]=like"
        f"&searchCriteria[pageSize]={page_size}"
    )
    return await make_request("GET", f"/products{params}", use_admin=True)


# ============================================================================
# CATEGORY ENDPOINTS
# ============================================================================

@mcp.tool()
async def get_categories() -> Dict[str, Any]:
    """
    Get category tree
    GET /V1/categories
    """
    return await make_request("GET", "/categories", use_admin=True)


@mcp.tool()
async def get_category(category_id: int) -> Dict[str, Any]:
    """
    Get category details by ID
    GET /V1/categories/:categoryId
    """
    return await make_request("GET", f"/categories/{category_id}", use_admin=True)


@mcp.tool()
async def create_category(
    name: str,
    is_active: bool = True,
    parent_id: int = 2,
    use_admin: bool = True
) -> Dict[str, Any]:
    """
    Create new category (requires admin token)
    POST /V1/categories
    """
    data = {
        "category": {
            "name": name,
            "is_active": is_active,
            "parent_id": parent_id
        }
    }
    return await make_request("POST", "/categories", data, use_admin=use_admin)


@mcp.tool()
async def get_category_products(category_id: int) -> Dict[str, Any]:
    """
    Get products in a category
    GET /V1/categories/:categoryId/products
    """
    return await make_request("GET", f"/categories/{category_id}/products", use_admin=True)


# ============================================================================
# SHOPPING CART ENDPOINTS
# ============================================================================

@mcp.tool()
async def create_cart() -> Dict[str, Any]:
    """
    Create new shopping cart for logged-in customer
    POST /V1/carts/mine
    """
    result = await make_request("POST", "/carts/mine")
    return result


@mcp.tool()
async def create_guest_cart() -> Dict[str, Any]:
    """
    Create guest shopping cart (returns cart ID)
    POST /V1/guest-carts
    """
    return await make_request("POST", "/guest-carts")


@mcp.tool()
async def get_cart() -> Dict[str, Any]:
    """
    Get current customer's cart
    GET /V1/carts/mine
    """
    return await make_request("GET", "/carts/mine")


@mcp.tool()
async def get_guest_cart(cart_id: str) -> Dict[str, Any]:
    """
    Get guest cart by ID
    GET /V1/guest-carts/:cartId
    """
    return await make_request("GET", f"/guest-carts/{cart_id}")


@mcp.tool()
async def add_to_cart(item: CartItem) -> Dict[str, Any]:
    """
    Add item to customer's cart
    POST /V1/carts/mine/items
    """
    data = {
        "cartItem": {
            "sku": item.sku,
            "qty": item.qty,
            "quote_id": item.quote_id
        }
    }
    return await make_request("POST", "/carts/mine/items", data)


@mcp.tool()
async def add_to_guest_cart(cart_id: str, sku: str, qty: float) -> Dict[str, Any]:
    """
    Add item to guest cart
    POST /V1/guest-carts/:cartId/items
    """
    data = {
        "cartItem": {
            "sku": sku,
            "qty": qty,
            "quote_id": cart_id
        }
    }
    return await make_request("POST", f"/guest-carts/{cart_id}/items", data)


@mcp.tool()
async def get_cart_items() -> Dict[str, Any]:
    """
    Get items in customer's cart
    GET /V1/carts/mine/items
    """
    return await make_request("GET", "/carts/mine/items")


@mcp.tool()
async def update_cart_item(item_id: int, qty: float) -> Dict[str, Any]:
    """
    Update quantity of item in cart
    PUT /V1/carts/mine/items/:itemId
    """
    data = {
        "cartItem": {
            "qty": qty,
            "item_id": item_id
        }
    }
    return await make_request("PUT", f"/carts/mine/items/{item_id}", data)


@mcp.tool()
async def remove_from_cart(item_id: int) -> Dict[str, Any]:
    """
    Remove item from customer's cart
    DELETE /V1/carts/mine/items/:itemId
    """
    return await make_request("DELETE", f"/carts/mine/items/{item_id}")


@mcp.tool()
async def get_cart_totals() -> Dict[str, Any]:
    """
    Get cart totals for current customer
    GET /V1/carts/mine/totals
    """
    return await make_request("GET", "/carts/mine/totals")


@mcp.tool()
async def apply_coupon(coupon_code: str) -> Dict[str, Any]:
    """
    Apply coupon to customer's cart
    PUT /V1/carts/mine/coupons/:couponCode
    """
    return await make_request("PUT", f"/carts/mine/coupons/{coupon_code}")


@mcp.tool()
async def remove_coupon() -> Dict[str, Any]:
    """
    Remove coupon from customer's cart
    DELETE /V1/carts/mine/coupons
    """
    return await make_request("DELETE", "/carts/mine/coupons")


# ============================================================================
# CHECKOUT ENDPOINTS
# ============================================================================

@mcp.tool()
async def set_shipping_address(address: AddressData) -> Dict[str, Any]:
    """
    Set shipping address for customer's cart
    POST /V1/carts/mine/shipping-information
    """
    data = {
        "addressInformation": {
            "shippingAddress": {
                "firstname": address.firstname,
                "lastname": address.lastname,
                "street": address.street,
                "city": address.city,
                "postcode": address.postcode,
                "telephone": address.telephone,
                "country_id": address.country_id,
                "region_id": address.region_id,
                "region": address.region
            },
            "shippingMethodCode": "flatrate",
            "shippingCarrierCode": "flatrate"
        }
    }
    return await make_request("POST", "/carts/mine/shipping-information", data)


@mcp.tool()
async def set_billing_address(address: AddressData) -> Dict[str, Any]:
    """
    Set billing address for customer's cart
    POST /V1/carts/mine/billing-address
    """
    data = {
        "address": {
            "firstname": address.firstname,
            "lastname": address.lastname,
            "street": address.street,
            "city": address.city,
            "postcode": address.postcode,
            "telephone": address.telephone,
            "country_id": address.country_id,
            "region_id": address.region_id,
            "region": address.region
        }
    }
    return await make_request("POST", "/carts/mine/billing-address", data)


@mcp.tool()
async def get_shipping_methods() -> Dict[str, Any]:
    """
    Get available shipping methods for cart
    GET /V1/carts/mine/shipping-methods
    """
    return await make_request("GET", "/carts/mine/shipping-methods")


@mcp.tool()
async def get_payment_methods() -> Dict[str, Any]:
    """
    Get available payment methods for cart
    GET /V1/carts/mine/payment-methods
    """
    return await make_request("GET", "/carts/mine/payment-methods")


@mcp.tool()
async def place_order(payment_method: str = "checkmo") -> Dict[str, Any]:
    """
    Place order for customer's cart
    POST /V1/carts/mine/payment-information
    """
    data = {
        "paymentMethod": {
            "method": payment_method
        }
    }
    return await make_request("POST", "/carts/mine/payment-information", data)


# ============================================================================
# ORDER MANAGEMENT ENDPOINTS
# ============================================================================

@mcp.tool()
async def get_orders(page_size: int = 20, current_page: int = 1) -> Dict[str, Any]:
    """
    Get list of orders (requires admin token)
    GET /V1/orders
    """
    params = f"?searchCriteria[pageSize]={page_size}&searchCriteria[currentPage]={current_page}"
    return await make_request("GET", f"/orders{params}", use_admin=True)


@mcp.tool()
async def get_order(order_id: int) -> Dict[str, Any]:
    """
    Get order details by ID
    GET /V1/orders/:id
    """
    return await make_request("GET", f"/orders/{order_id}", use_admin=True)


@mcp.tool()
async def cancel_order(order_id: int) -> Dict[str, Any]:
    """
    Cancel an order (requires admin token)
    POST /V1/orders/:id/cancel
    """
    return await make_request("POST", f"/orders/{order_id}/cancel", use_admin=True)


@mcp.tool()
async def add_order_comment(order_id: int, comment: str, is_visible: bool = True) -> Dict[str, Any]:
    """
    Add comment to order (requires admin token)
    POST /V1/orders/:id/comments
    """
    data = {
        "statusHistory": {
            "comment": comment,
            "is_customer_notified": 1 if is_visible else 0,
            "is_visible_on_front": 1 if is_visible else 0
        }
    }
    return await make_request("POST", f"/orders/{order_id}/comments", data, use_admin=True)


@mcp.tool()
async def create_invoice(order_id: int) -> Dict[str, Any]:
    """
    Create invoice for order (requires admin token)
    POST /V1/order/:orderId/invoice
    """
    return await make_request("POST", f"/order/{order_id}/invoice", {}, use_admin=True)


@mcp.tool()
async def create_shipment(order_id: int) -> Dict[str, Any]:
    """
    Create shipment for order (requires admin token)
    POST /V1/order/:orderId/ship
    """
    return await make_request("POST", f"/order/{order_id}/ship", {}, use_admin=True)


# ============================================================================
# CUSTOMER MANAGEMENT ENDPOINTS
# ============================================================================

@mcp.tool()
async def get_customers(page_size: int = 20, current_page: int = 1) -> Dict[str, Any]:
    """
    Get list of customers (requires admin token)
    GET /V1/customers/search
    """
    params = f"?searchCriteria[pageSize]={page_size}&searchCriteria[currentPage]={current_page}"
    return await make_request("GET", f"/customers/search{params}", use_admin=True)


@mcp.tool()
async def get_customer(customer_id: int) -> Dict[str, Any]:
    """
    Get customer details by ID (requires admin token)
    GET /V1/customers/:customerId
    """
    return await make_request("GET", f"/customers/{customer_id}", use_admin=True)


@mcp.tool()
async def update_customer(customer_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update customer information (requires admin token)
    PUT /V1/customers/:customerId
    """
    data = {"customer": updates}
    return await make_request("PUT", f"/customers/{customer_id}", data, use_admin=True)


@mcp.tool()
async def delete_customer(customer_id: int) -> Dict[str, Any]:
    """
    Delete customer (requires admin token)
    DELETE /V1/customers/:customerId
    """
    return await make_request("DELETE", f"/customers/{customer_id}", use_admin=True)


@mcp.tool()
async def get_customer_groups() -> Dict[str, Any]:
    """
    Get list of customer groups
    GET /V1/customerGroups/search
    """
    return await make_request("GET", "/customerGroups/search?searchCriteria[pageSize]=100", use_admin=True)


# ============================================================================
# INVENTORY ENDPOINTS
# ============================================================================

@mcp.tool()
async def get_stock_status(sku: str) -> Dict[str, Any]:
    """
    Get stock status for a product SKU
    GET /V1/stockStatuses/:productSku
    """
    return await make_request("GET", f"/stockStatuses/{sku}", use_admin=True)


@mcp.tool()
async def check_product_salable(sku: str, stock_id: int = 1) -> Dict[str, Any]:
    """
    Check if product is salable
    GET /V1/inventory/is-product-salable/:sku/:stockId
    """
    return await make_request("GET", f"/inventory/is-product-salable/{sku}/{stock_id}", use_admin=True)


@mcp.tool()
async def get_sources() -> Dict[str, Any]:
    """
    Get list of inventory sources
    GET /V1/inventory/sources
    """
    return await make_request("GET", "/inventory/sources", use_admin=True)


@mcp.tool()
async def get_stocks() -> Dict[str, Any]:
    """
    Get list of inventory stocks
    GET /V1/inventory/stocks
    """
    return await make_request("GET", "/inventory/stocks", use_admin=True)


# ============================================================================
# STORE CONFIGURATION ENDPOINTS
# ============================================================================

@mcp.tool()
async def get_store_config() -> Dict[str, Any]:
    """
    Get store configuration
    GET /V1/store/storeConfigs
    """
    return await make_request("GET", "/store/storeConfigs", use_admin=True)


@mcp.tool()
async def get_websites() -> Dict[str, Any]:
    """
    Get list of websites
    GET /V1/store/websites
    """
    return await make_request("GET", "/store/websites", use_admin=True)


@mcp.tool()
async def get_store_views() -> Dict[str, Any]:
    """
    Get list of store views
    GET /V1/store/storeViews
    """
    return await make_request("GET", "/store/storeViews", use_admin=True)


@mcp.tool()
async def get_countries() -> Dict[str, Any]:
    """
    Get list of countries
    GET /V1/directory/countries
    """
    return await make_request("GET", "/directory/countries")


@mcp.tool()
async def get_currency() -> Dict[str, Any]:
    """
    Get currency information
    GET /V1/directory/currency
    """
    return await make_request("GET", "/directory/currency")


# ============================================================================
# CMS ENDPOINTS
# ============================================================================

@mcp.tool()
async def get_cms_pages(page_size: int = 20) -> Dict[str, Any]:
    """
    Get list of CMS pages
    GET /V1/cmsPage/search
    """
    params = f"?searchCriteria[pageSize]={page_size}"
    return await make_request("GET", f"/cmsPage/search{params}", use_admin=True)


@mcp.tool()
async def get_cms_page(page_id: int) -> Dict[str, Any]:
    """
    Get CMS page by ID
    GET /V1/cmsPage/:id
    """
    return await make_request("GET", f"/cmsPage/{page_id}", use_admin=True)


@mcp.tool()
async def get_cms_blocks(page_size: int = 20) -> Dict[str, Any]:
    """
    Get list of CMS blocks
    GET /V1/cmsBlock/search
    """
    params = f"?searchCriteria[pageSize]={page_size}"
    return await make_request("GET", f"/cmsBlock/search{params}", use_admin=True)


# ============================================================================
# TAX ENDPOINTS
# ============================================================================

@mcp.tool()
async def get_tax_classes() -> Dict[str, Any]:
    """
    Get list of tax classes
    GET /V1/taxClasses/search
    """
    return await make_request("GET", "/taxClasses/search?searchCriteria[pageSize]=100", use_admin=True)


@mcp.tool()
async def get_tax_rates() -> Dict[str, Any]:
    """
    Get list of tax rates
    GET /V1/taxRates/search
    """
    return await make_request("GET", "/taxRates/search?searchCriteria[pageSize]=100", use_admin=True)


@mcp.tool()
async def get_tax_rules() -> Dict[str, Any]:
    """
    Get list of tax rules
    GET /V1/taxRules/search
    """
    return await make_request("GET", "/taxRules/search?searchCriteria[pageSize]=100", use_admin=True)


# ============================================================================
# SALES RULE/COUPON ENDPOINTS
# ============================================================================

@mcp.tool()
async def get_sales_rules(page_size: int = 20) -> Dict[str, Any]:
    """
    Get list of sales rules (requires admin token)
    GET /V1/salesRules/search
    """
    params = f"?searchCriteria[pageSize]={page_size}"
    return await make_request("GET", f"/salesRules/search{params}", use_admin=True)


@mcp.tool()
async def get_sales_rule(rule_id: int) -> Dict[str, Any]:
    """
    Get sales rule by ID (requires admin token)
    GET /V1/salesRules/:ruleId
    """
    return await make_request("GET", f"/salesRules/{rule_id}", use_admin=True)


@mcp.tool()
async def search_coupons(page_size: int = 20) -> Dict[str, Any]:
    """
    Search for coupons (requires admin token)
    GET /V1/coupons/search
    """
    params = f"?searchCriteria[pageSize]={page_size}"
    return await make_request("GET", f"/coupons/search{params}", use_admin=True)


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@mcp.tool()
async def set_auth_token(token: str, token_type: str = "customer") -> Dict[str, str]:
    """
    Manually set authentication token for subsequent requests
    """
    if token_type in auth_tokens:
        auth_tokens[token_type] = token
        return {"message": f"{token_type} token set successfully"}
    return {"error": f"Invalid token type. Use 'customer' or 'admin'"}


@mcp.tool()
async def get_current_tokens() -> Dict[str, Any]:
    """
    Get currently stored authentication tokens (for debugging)
    """
    return {
        "customer_token": auth_tokens["customer"][:10] + "..." if auth_tokens["customer"] else None,
        "admin_token": auth_tokens["admin"][:10] + "..." if auth_tokens["admin"] else None
    }


@mcp.tool()
async def clear_tokens() -> Dict[str, str]:
    """
    Clear all stored authentication tokens
    """
    auth_tokens["customer"] = None
    auth_tokens["admin"] = None
    return {"message": "All tokens cleared"}


# Run the MCP server
# if __name__ == "__main__":
#     import asyncio
#     import sys

#     # For testing individual functions
#     if len(sys.argv) > 1 and sys.argv[1] == "test":
#         async def test():
#             # Test getting products
#             result = await get_products(page_size=5)
#             print("Products:", json.dumps(result, indent=2))

#         asyncio.run(test())
#     else:
#         # Run as MCP server
#         # Default: stdio transport (requires subprocess)
#         # For HTTP: use the SSE transport built into FastMCP
#         mcp.run()

# python
import sys
from pathlib import Path

# Add project root to path so agent module can be imported
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agent.common.configurator import Configurator
from agent.common.utils import get_mcp_logger

logger = get_mcp_logger()

if __name__ == "__main__":
    print("Starting webarena-mcp server")
    logger.debug("Starting webarena-mcp server")

    config = Configurator()
    config.load_mcpserver_env()
    config.load_shared_env()

    # Read URL from config.yaml -> mcp_server.webarena
    mcp_server_url = config.get_key("mcp_server")["webarena"]
    hostname, port, path = config.get_hostname_port(mcp_server_url)

    # Run FastMCP over HTTP (streamable-http transport)
    mcp.run(
        transport="streamable-http",
        host=hostname,
        port=port,
        path=path,
    )