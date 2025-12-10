"""Wishlist management helpers mirroring the cart flows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from playwright.sync_api import Page

from .constants import WISHLIST_URL

@dataclass
class AddToWishlistResult:
    """Result of attempting to add a product to the wishlist from its product page."""

    success: bool
    product_url: str
    requested_quantity: int
    wishlist_count_after: Optional[int]
    error_message: Optional[str] = None


@dataclass
class WishlistItem:
    """Representation of a wishlist line item on the wishlist page."""

    item_id: Optional[str]  # Magento wishlist item id, e.g. "3"
    name: str
    quantity: int
    price: Optional[float]
    product_url: str
    image_url: Optional[str]


def add_product_to_wishlist(
    page: Page,
    product_url: str,
    quantity: int = 1,
    option_values: Optional[dict[str, str]] = None,
) -> AddToWishlistResult:
    """
    Navigate to a product page, set quantity/required options, and add the item to the wishlist.
    Mirrors the cart add flow but clicks the Add to Wish List control instead.
    """
    if quantity < 1:
        quantity = 1

    with page.expect_load_state("networkidle"):
        page.goto(product_url)

    form = page.locator("form#product_addtocart_form")
    form.wait_for()

    # Identify required product options.
    required_option_names: list[str] = []
    required_fields = form.locator("#product-options-wrapper .field.required")
    for i in range(required_fields.count()):
        field = required_fields.nth(i)
        input_loc = field.locator('input[name^="options["]').first
        select_loc = field.locator('select[name^="options["]').first
        textarea_loc = field.locator('textarea[name^="options["]').first

        input_name: Optional[str] = None
        for loc in (input_loc, select_loc, textarea_loc):
            if loc.count() > 0:
                input_name = loc.get_attribute("name")
                break

        if input_name:
            required_option_names.append(input_name)

    if required_option_names:
        if option_values is None:
            return AddToWishlistResult(
                success=False,
                product_url=product_url,
                requested_quantity=quantity,
                wishlist_count_after=None,
                error_message=(
                    "Missing required product options: "
                    + ", ".join(sorted(set(required_option_names)))
                ),
            )

        missing = [
            name for name in required_option_names if name not in option_values
        ]
        if missing:
            return AddToWishlistResult(
                success=False,
                product_url=product_url,
                requested_quantity=quantity,
                wishlist_count_after=None,
                error_message="Missing required product options: "
                + ", ".join(missing),
            )

    # Set quantity on the product form.
    qty_input = form.locator("input#qty")
    if qty_input.count() > 0:
        qty_input.fill(str(quantity))

    # Apply provided option values (required and optional).
    if option_values:
        for input_name, input_value in option_values.items():
            radio_or_checkbox = form.locator(
                f'input[name="{input_name}"][value="{input_value}"]'
            ).first
            if radio_or_checkbox.count() > 0:
                radio_or_checkbox.check()
                continue

            select_el = form.locator(f'select[name="{input_name}"]').first
            if select_el.count() > 0:
                try:
                    select_el.select_option(value=input_value)
                except Exception:
                    return AddToWishlistResult(
                        success=False,
                        product_url=product_url,
                        requested_quantity=quantity,
                        wishlist_count_after=None,
                        error_message=(
                            f"Could not select option '{input_name}' "
                            f"with value '{input_value}'"
                        ),
                    )
                continue

            textarea_el = form.locator(f'textarea[name="{input_name}"]').first
            if textarea_el.count() > 0:
                textarea_el.fill(input_value)
                continue

            return AddToWishlistResult(
                success=False,
                product_url=product_url,
                requested_quantity=quantity,
                wishlist_count_after=None,
                error_message=(
                    f"No matching input found on page for option '{input_name}'"
                ),
            )

    # Trigger Add to Wish List.
    wishlist_btn = page.locator("a.action.towishlist[data-post]").first
    if wishlist_btn.count() == 0:
        return AddToWishlistResult(
            success=False,
            product_url=product_url,
            requested_quantity=quantity,
            wishlist_count_after=None,
            error_message="Add to Wish List button not found",
        )

    with page.expect_load_state("networkidle"):
        wishlist_btn.click()

    # Capture any error messages surfaced by Magento.
    error_loc = page.locator(
        ".page.messages .message-error, "
        ".page.messages .error.message, "
        "div.messages .message-error, "
        "div.messages .error.message"
    )
    if error_loc.count() > 0:
        text = error_loc.nth(0).inner_text().strip()
        if not text:
            text = "Unknown error adding product to wishlist"
        return AddToWishlistResult(
            success=False,
            product_url=product_url,
            requested_quantity=quantity,
            wishlist_count_after=None,
            error_message=text,
        )

    # Read wishlist counter from header.
    wishlist_count_after: Optional[int] = None
    counter = page.locator(".link.wishlist .counter")
    try:
        if counter.count() > 0:
            txt = counter.inner_text().strip()
            match = re.search(r"\d+", txt)
            if match:
                wishlist_count_after = int(match.group(0))
    except Exception:
        wishlist_count_after = None

    return AddToWishlistResult(
        success=True,
        product_url=product_url,
        requested_quantity=quantity,
        wishlist_count_after=wishlist_count_after,
    )


def get_wishlist_items(page: Page) -> List[WishlistItem]:
    """Return the list of products currently in the wishlist, with quantities."""
    with page.expect_load_state("networkidle"):
        page.goto(WISHLIST_URL)

    items: List[WishlistItem] = []
    product_items = page.locator("div.products-grid.wishlist ol.product-items > li")

    for i in range(product_items.count()):
        item = product_items.nth(i)

        # Item id comes from the li id="item_<id>".
        raw_id = item.get_attribute("id") or ""
        match = re.search(r"item_(\d+)", raw_id)
        item_id = match.group(1) if match else None

        name_loc = item.locator("strong.product-item-name a").first
        if name_loc.count() == 0:
            continue
        name = name_loc.inner_text().strip()
        product_url = name_loc.get_attribute("href") or ""

        qty_input = item.locator("input[type='number'][name^='qty[']").first
        qty_val = qty_input.get_attribute("value") if qty_input.count() > 0 else "0"
        try:
            quantity = int(float(qty_val or "0"))
        except ValueError:
            quantity = 0

        price_loc = item.locator("span.price").first
        if price_loc.count() > 0:
            price_text = price_loc.inner_text()
            try:
                price = float(re.sub(r"[^0-9.]", "", price_text))
            except ValueError:
                price = None
        else:
            price = None

        img_loc = item.locator("img.product-image-photo").first
        image_url = img_loc.get_attribute("src") if img_loc.count() > 0 else None

        items.append(
            WishlistItem(
                item_id=item_id,
                name=name,
                quantity=quantity,
                price=price,
                product_url=product_url,
                image_url=image_url,
            )
        )

    return items


def set_wishlist_item_quantity(page: Page, item_id: str, quantity: int) -> bool:
    """Change the quantity of an item in the wishlist based on its item id."""
    if quantity < 1:
        quantity = 1

    with page.expect_load_state("networkidle"):
        page.goto(WISHLIST_URL)

    # Locate the specific quantity input for this item.
    qty_input = page.locator(
        f"form.form-wishlist-items input[name='qty[{item_id}]']"
    ).first
    if qty_input.count() == 0:
        # Fallback: search within the list item container.
        qty_input = page.locator(
            f"li#item_{item_id} input[type='number'][name^='qty[']"
        ).first

    if qty_input.count() == 0:
        return False

    qty_input.fill(str(quantity))

    update_button = page.locator("form.form-wishlist-items button.action.update").first
    if update_button.count() == 0:
        return False

    with page.expect_load_state("networkidle"):
        update_button.click()

    return True


def remove_wishlist_item(page: Page, item_id: str) -> bool:
    """Delete an item from the wishlist based on its item id."""
    with page.expect_load_state("networkidle"):
        page.goto(WISHLIST_URL)

    item = page.locator(f"li#item_{item_id}").first
    if item.count() == 0:
        return False

    remove_link = item.locator("a[data-role='remove'], a.action.delete").first
    if remove_link.count() == 0:
        return False

    with page.expect_load_state("networkidle"):
        remove_link.click()

    return True


def empty_wishlist(page: Page) -> None:
    """Remove all items from the wishlist by iteratively deleting them."""
    while True:
        with page.expect_load_state("networkidle"):
            page.goto(WISHLIST_URL)

        item_links = page.locator(
            "div.products-grid.wishlist ol.product-items > li a[data-role='remove'], "
            "div.products-grid.wishlist ol.product-items > li a.action.delete"
        )
        if item_links.count() == 0:
            break

        with page.expect_load_state("networkidle"):
            item_links.nth(0).click()
