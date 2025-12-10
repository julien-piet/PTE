"""Quick checks for constants module."""

from __future__ import annotations

import sys
from pathlib import Path
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

api_stub = types.ModuleType("api")
api_stub.__path__ = [str(Path(__file__).resolve().parents[1])]
sys.modules["api"] = api_stub

playwright_stub = types.ModuleType("playwright")
playwright_stub.sync_api = types.SimpleNamespace(Page=object)
sys.modules["playwright"] = playwright_stub
sys.modules["playwright.sync_api"] = playwright_stub.sync_api

from api.shipping_pw import constants  # noqa:E402


class ConstantsTests(unittest.TestCase):
    def test_urls_share_base(self) -> None:
        for name in (
            "CART_URL",
            "CHECKOUT_URL",
            "WISHLIST_URL",
            "ACCOUNT_EDIT_URL",
            "ADDRESS_BOOK_URL",
            "ORDER_HISTORY_URL",
            "LOGIN_URL",
        ):
            value = getattr(constants, name)
            self.assertTrue(value.startswith(constants.BASE_URL), f"{name} should start with BASE_URL")

    def test_base_url_shape(self) -> None:
        self.assertIn("http", constants.BASE_URL)
        self.assertTrue(len(constants.BASE_URL) > 10)


if __name__ == "__main__":
    unittest.main()
