"""Test ensuring an SD Card can be added to the wishlist."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional

from playwright.sync_api import sync_playwright

from api.shipping_pw import login as storefront_login
from api.shipping_pw import wishlist
from api.shipping_pw.config import get_default_customer_credentials
from tests.test import Test


@dataclass
class AddProductToWishlistTest(Test):
    query: str = "Add a {{product}} to my wish list."
    parameters: Optional[Dict[str, str]] = field(
        default_factory=lambda: {"product": "SD Card"}
    )

    def setup_env(self) -> bool:
        """
        Log in with configured credentials and empty the wishlist before running.
        """
        try:
            email, password = get_default_customer_credentials()
            with self._authenticated_page(email, password) as page:
                wishlist.empty_wishlist(page)
            return True
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"Failed to prepare wishlist environment: {exc}")
            return False

    def check_env(self, result: Optional[Any] = None) -> bool:
        """
        Verify the wishlist now contains an item whose name mentions 'SD Card'.
        """
        try:
            email, password = get_default_customer_credentials()
            with self._authenticated_page(email, password) as page:
                items = wishlist.get_wishlist_items(page)
            return any("sd card" in (item.name or "").lower() for item in items)
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"Failed to validate wishlist contents: {exc}")
            return False

    @contextlib.contextmanager
    def _authenticated_page(self, email: str, password: str) -> Iterator[Any]:
        """Yield a logged-in Playwright page for wishlist interactions."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            login_result = storefront_login.login_customer(
                page, email, password
            )
            if not login_result.success:
                browser.close()
                raise RuntimeError(
                    f"Customer login failed: {login_result.error_message}"
                )

            try:
                yield page
            finally:
                browser.close()
