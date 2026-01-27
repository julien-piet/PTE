"""Submit product reviews."""

from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page


@dataclass
class ReviewResult:
    success: bool
    rating: int
    nickname: str
    title: str
    detail: str
    error_message: Optional[str] = None


def leave_product_review(
    page: Page,
    product_url: str,
    rating: int,
    nickname: str,
    title: str,
    detail: str,
) -> ReviewResult:
    """
    Open a product page and submit a review with the given rating (1-5 stars).
    """
    if rating < 1:
        rating = 1
    if rating > 5:
        rating = 5

    page.goto(product_url)

    page.wait_for_load_state("networkidle")
    # Reveal the reviews tab / form.
    reviews_tab = page.locator("a#tab-label-reviews-title")
    if reviews_tab.count() == 0:
        reviews_tab = page.locator("a.data.switch[href$='#reviews']")
    if reviews_tab.count() > 0:
        reviews_tab.first.click()

    # Select the desired star rating (inputs are ordered 1->5).
    rating_inputs = page.locator(".review-control-vote input.radio")
    if rating_inputs.count() >= rating:
        rating_inputs.nth(rating - 1).check()

    page.locator("input#nickname_field").fill(nickname)
    page.locator("input#summary_field").fill(title)
    page.locator("textarea#review_field").fill(detail)

    page.locator("form#review-form button.action.submit").click()

    page.wait_for_load_state("networkidle")
    error_loc = page.locator(
        ".page.messages .message-error, "
        ".page.messages .error.message, "
        "div.messages .message-error, "
        "div.messages .error.message"
    )
    if error_loc.count() > 0:
        msg = error_loc.nth(0).inner_text().strip() or "Unknown review error."
        return ReviewResult(
            success=False,
            rating=rating,
            nickname=nickname,
            title=title,
            detail=detail,
            error_message=msg,
        )

    success_loc = page.locator(
        ".page.messages .message-success, div.messages .message-success"
    )
    success = success_loc.count() > 0

    return ReviewResult(
        success=success,
        rating=rating,
        nickname=nickname,
        title=title,
        detail=detail,
        error_message=None if success else "Review submission may have failed.",
    )
