"""Ad-hoc tests for wishlist helper functions."""

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

from api.shipping_pw import wishlist  # noqa:E402
from api.shipping_pw.test_utils import FakeLocator, FakePage  # noqa:E402


ERROR_SELECTOR = (
    ".page.messages .message-error, "
    ".page.messages .error.message, "
    "div.messages .message-error, "
    "div.messages .error.message"
)


class WishlistTests(unittest.TestCase):
    def test_add_product_to_wishlist_success(self) -> None:
        form = FakeLocator(
            nested={
                "#product-options-wrapper .field.required": FakeLocator(count_value=0),
                "input#qty": FakeLocator(count_value=1),
            }
        )
        page = FakePage(
            locators={
                "form#product_addtocart_form": form,
                "a.action.towishlist[data-post]": FakeLocator(count_value=1),
                ".link.wishlist .counter": FakeLocator(text="1"),
                ERROR_SELECTOR: FakeLocator(count_value=0),
            }
        )

        result = wishlist.add_product_to_wishlist(page, "http://example.com/p/sku123", quantity=2)
        self.assertTrue(result.success)
        self.assertEqual(result.wishlist_count_after, 1)
        self.assertEqual(result.requested_quantity, 2)

    def test_add_product_to_wishlist_missing_options(self) -> None:
        required_field = FakeLocator(
            count_value=1,
            nested={
                'input[name^="options["]': FakeLocator(count_value=1, attributes={"name": "options[200]"})
            },
        )
        form = FakeLocator(
            nested={
                "#product-options-wrapper .field.required": required_field,
            }
        )
        page = FakePage(
            locators={
                "form#product_addtocart_form": form,
                ERROR_SELECTOR: FakeLocator(count_value=0),
            }
        )

        result = wishlist.add_product_to_wishlist(page, "http://example.com/p/sku123", option_values=None)
        self.assertFalse(result.success)
        self.assertIn("Missing required", result.error_message or "")

    def test_get_wishlist_items_parses_row(self) -> None:
        item = FakeLocator(
            attributes={"id": "item_3"},
            nested={
                "strong.product-item-name a": FakeLocator(text="Wish Item", attributes={"href": "http://example.com/p"}),
                "input[type='number'][name^='qty['": FakeLocator(count_value=1, attributes={"value": "4"}),
                "span.price": FakeLocator(text="$10.00"),
                "img.product-image-photo": FakeLocator(attributes={"src": "http://img/wish.jpg"}),
            },
        )
        product_items = FakeLocator(children=[item], count_value=1)
        page = FakePage(
            locators={
                "div.products-grid.wishlist ol.product-items > li": product_items,
            }
        )

        items = wishlist.get_wishlist_items(page)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].item_id, "3")
        self.assertEqual(items[0].quantity, 4)
        self.assertEqual(items[0].price, 10.0)

    def test_set_wishlist_item_quantity_defaults_minimum(self) -> None:
        qty_input = FakeLocator(count_value=1)
        update_btn = FakeLocator(count_value=1)
        page = FakePage(
            locators={
                "form.form-wishlist-items input[name='qty[abc]']": qty_input,
                "form.form-wishlist-items button.action.update": update_btn,
            }
        )
        result = wishlist.set_wishlist_item_quantity(page, "abc", 0)
        self.assertTrue(result)
        self.assertEqual(qty_input.text, "1")
        self.assertTrue(any(action[0] == "click" for action in update_btn.actions))

    def test_remove_and_empty_wishlist(self) -> None:
        remove_link = FakeLocator(count_value=1)
        page = FakePage(
            locators={
                "li#item_5": FakeLocator(
                    count_value=1,
                    nested={
                        "a[data-role='remove'], a.action.delete": remove_link,
                    },
                ),
            }
        )
        self.assertTrue(wishlist.remove_wishlist_item(page, "5"))
        self.assertTrue(any(action[0] == "click" for action in remove_link.actions))

        def locator_func(selector: str) -> FakeLocator:
            if selector.startswith("div.products-grid.wishlist ol.product-items"):
                if getattr(page, "cleared", False):
                    return FakeLocator(count_value=0)
                delete_link = FakeLocator(
                    count_value=1,
                    on_click=lambda: setattr(page, "cleared", True),
                )
                item = FakeLocator(
                    nested={
                        "a[data-role='remove'], a.action.delete": delete_link,
                    }
                )
                return FakeLocator(children=[item], count_value=1)
            return page.locators.get(selector, FakeLocator())

        page.locator = locator_func  # type: ignore[assignment]
        page.locators = {}
        wishlist.empty_wishlist(page)
        self.assertTrue(getattr(page, "cleared", False))


if __name__ == "__main__":
    unittest.main()
