from typing import Dict, Optional
from urllib.parse import quote_plus, urljoin

import httpx
import uvicorn
from bs4 import BeautifulSoup
from fastapi import FastAPI
from pydantic import BaseModel
from playwright.sync_api import sync_playwright

from shopping_pw import add_product_to_wishlist, get_default_customer_credentials, login_customer
from shopping_pw.constants import BASE_URL

app = FastAPI(
    title="Shopping Extra API",
    description="Custom endpoints for the WebArena Shopping website.",
    version="1.0.0",
)


class AddToWishlistResponse(BaseModel):
    success: bool
    product_url: str
    requested_quantity: int
    wishlist_count_after: Optional[int] = None
    error_message: Optional[str] = None


class AddToWishlistRequest(BaseModel):
    product_url: str
    quantity: int = 1


@app.get("/fuzzy_search", response_model=Dict[str, str])
async def fuzzy_search(q: str) -> Dict[str, str]:
    """
    Search the shopping website and return an ordered dict of rank → product name
    as they appear in the search results UI (e.g. {"1": "Echo Dot", "2": "..."}).
    """
    url = f"{BASE_URL}/catalogsearch/result/?q={quote_plus(q)}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    names = [
        name for tag in soup.select("a.product-item-link")
        if (name := tag.get_text(strip=True))
    ]
    return {str(i + 1): name for i, name in enumerate(names)}


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

    default_email, default_password = get_default_customer_credentials()

    email = default_email
    password = default_password

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            login_result = login_customer(page, email, password)
            if not login_result.success:
                return AddToWishlistResponse(
                    success=False,
                    product_url=normalized_product_url,
                    requested_quantity=quantity,
                    wishlist_count_after=None,
                    error_message=f"Login failed: {login_result.error_message or 'Unknown error'}",
                )

            result = add_product_to_wishlist(
                page=page,
                product_url=normalized_product_url,
                quantity=quantity,
                option_values=None,
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
