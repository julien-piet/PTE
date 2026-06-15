import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Dict, List, Optional
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
import uvicorn
from bs4 import BeautifulSoup
from fastapi import FastAPI
from pydantic import BaseModel
from playwright.sync_api import sync_playwright

from api.shopping_pw import add_product_to_wishlist, get_default_customer_credentials, login_customer
from api.shopping_pw.constants import BASE_URL

app = FastAPI(
    title="Shopping Extra API",
    description="Custom endpoints for the WebArena Shopping website.",
    version="1.0.0",
)


# ── Auth helper ───────────────────────────────────────────────────────────────

def _make_browser_page(playwright):
    """Create a browser page authenticated as the default storefront customer."""
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    email, password = get_default_customer_credentials()
    login_result = login_customer(page, email, password)
    if not login_result.success:
        browser.close()
        raise RuntimeError(f"Login failed: {login_result.error_message or 'Unknown error'}")
    return browser, page


class AddToWishlistResponse(BaseModel):
    success: bool
    product_url: str
    requested_quantity: int
    wishlist_count_after: Optional[int] = None
    error_message: Optional[str] = None


class AddToWishlistRequest(BaseModel):
    product_url: str
    quantity: int = 1
    options: Optional[Dict[str, str]] = None


class ProductSearchResult(BaseModel):
    rank: int
    name: str
    url: str
    sku: Optional[str] = None


@app.get("/fuzzy_search", response_model=List[ProductSearchResult])
async def fuzzy_search(q: str) -> List[ProductSearchResult]:
    """
    Search the shopping website and return an ordered list of products with
    their rank, name, URL, and SKU (if available).
    """
    url = f"{BASE_URL}/catalogsearch/result/?q={quote_plus(q)}"

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    results = []
    for i, item in enumerate(soup.select("li.product-item"), start=1):
        link_tag = item.select_one("a.product-item-link")
        if not link_tag:
            continue
        name = link_tag.get_text(strip=True)
        raw_url = link_tag.get("href", "")
        parsed = urlparse(raw_url)
        product_url = parsed.path.lstrip("/")

        form_tag = item.select_one("form[data-role='tocart-form']")
        sku = form_tag.get("data-product-sku") if form_tag else None

        results.append(ProductSearchResult(rank=i, name=name, url=product_url, sku=sku))

    return results


def _default_required_options(product_url: str) -> Dict[str, str]:
    """
    Fetch the product page and return a dict mapping every required option's
    input name (e.g. "options[62548]") to the first available value. Returns
    an empty dict when the product page has no required options.
    """
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(product_url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    defaults: Dict[str, str] = {}
    wrapper = soup.select_one("#product-options-wrapper")
    if wrapper is None:
        return defaults

    for field in wrapper.select(".field.required"):
        first_input = field.select_one(
            'input[name^="options["], select[name^="options["], textarea[name^="options["]'
        )
        if first_input is None:
            continue
        name = first_input.get("name")
        if not name or name in defaults:
            continue

        if first_input.name == "select":
            option_tag = first_input.find("option", attrs={"value": True})
            if option_tag is None:
                continue
            value = option_tag.get("value")
        else:
            value = first_input.get("value")

        if value:
            defaults[name] = value

    return defaults


@app.post("/add_to_wishlist", response_model=AddToWishlistResponse)
def add_to_wishlist(payload: AddToWishlistRequest) -> AddToWishlistResponse:
    """
    Log in as a storefront customer and add a product page item to wishlist.
    """
    product_url = payload.product_url
    quantity = payload.quantity

    normalized_product_url = product_url

    if not product_url.startswith(("http://", "https://")):
        normalized_product_url = urljoin(f"{BASE_URL}/", product_url.lstrip("/"))

    option_values: Optional[Dict[str, str]] = None
    if payload.options:
        option_values = {}
        for option_id, option_value_id in payload.options.items():
            key = option_id if option_id.startswith("options[") else f"options[{option_id}]"
            option_values[key] = str(option_value_id)
    else:
        # If the user did not specify options, use the default required options from the product page.
        try:
            defaults = _default_required_options(normalized_product_url)
        except httpx.HTTPError:
            defaults = {}
        if defaults:
            option_values = defaults

    with sync_playwright() as p:
        try:
            browser, page = _make_browser_page(p)
        except RuntimeError as exc:
            return AddToWishlistResponse(
                success=False,
                product_url=normalized_product_url,
                requested_quantity=quantity,
                error_message=str(exc),
            )
        try:
            result = add_product_to_wishlist(
                page=page,
                product_url=normalized_product_url,
                quantity=quantity,
                option_values=option_values,
            )

            return AddToWishlistResponse(
                success=result.success,
                product_url=result.product_url,
                requested_quantity=result.requested_quantity,
                wishlist_count_after=result.wishlist_count_after,
                error_message=result.error_message,
            )
        finally:
            browser.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7790)
