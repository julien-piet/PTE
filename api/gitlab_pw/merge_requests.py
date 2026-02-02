"""GitLab merge request management helpers."""

import re
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page, TimeoutError, expect

from .constants import (
    GITLAB_DOMAIN,
    Selectors,
    get_new_merge_request_url,
    get_merge_request_url,
    get_project_merge_requests_url,
)


@dataclass
class MergeRequest:
    """Representation of a GitLab merge request."""

    mr_id: int
    title: str
    url: str
    source_branch: str
    target_branch: Optional[str] = None
    state: Optional[str] = None  # "opened", "merged", "closed"
    author: Optional[str] = None


@dataclass
class CreateMergeRequestResult:
    """Result of attempting to create a merge request."""

    success: bool
    mr_id: Optional[int]
    mr_url: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class CloseMergeRequestResult:
    """Result of attempting to close a merge request."""

    success: bool
    error_message: Optional[str] = None


def create_merge_request(
    page: Page,
    namespace: str,
    project: str,
    source_branch: str,
    title: str,
) -> CreateMergeRequestResult:
    """
    Create a merge request from a branch.

    FIXED: Uses sync pattern instead of expect_navigation context manager.

    Args:
        page: Playwright Page instance
        namespace: Project namespace
        project: Project name
        source_branch: Branch to merge from
        title: Merge request title

    Returns:
        CreateMergeRequestResult with success status, ID, and any error message
    """
    url = get_new_merge_request_url(namespace, project, source_branch)
    page.goto(url, wait_until="networkidle")

    # Check for page not found
    if _is_page_not_found(page):
        return CreateMergeRequestResult(
            success=False,
            mr_id=None,
            error_message=f"Cannot access merge request page at {url}"
        )

    # Check for errors (e.g., branch doesn't have commits different from target)
    error_container = page.locator(Selectors.ERROR_CONTAINER)
    if error_container.count() > 0:
        errors = error_container.locator("ul li").all_inner_texts()
        return CreateMergeRequestResult(
            success=False,
            mr_id=None,
            error_message="; ".join(errors)
        )

    # Fill title
    try:
        page.wait_for_selector(Selectors.MR_TITLE_INPUT, timeout=10000)
        page.fill(Selectors.MR_TITLE_INPUT, title)
    except TimeoutError:
        return CreateMergeRequestResult(
            success=False,
            mr_id=None,
            error_message="Merge request title field not found"
        )

    # Submit - FIXED: sync pattern
    page.click(Selectors.MR_CREATE_BUTTON)
    page.wait_for_load_state("networkidle")

    # Verify we landed on the MR page
    gitlab_domain_escaped = re.escape(GITLAB_DOMAIN)
    namespace_escaped = re.escape(namespace)
    project_escaped = re.escape(project)
    mr_url_pattern = rf"^{gitlab_domain_escaped}/{namespace_escaped}/{project_escaped}/-/merge_requests/(\d+)$"

    match = re.match(mr_url_pattern, page.url)
    if match:
        mr_id = int(match.group(1))
        return CreateMergeRequestResult(
            success=True,
            mr_id=mr_id,
            mr_url=page.url,
            error_message=None
        )

    return CreateMergeRequestResult(
        success=False,
        mr_id=None,
        error_message=f"MR creation may have failed; ended up at {page.url}"
    )


def close_merge_request(
    page: Page,
    namespace: str,
    project: str,
    mr_id: int,
) -> CloseMergeRequestResult:
    """
    Close a merge request.

    Args:
        page: Playwright Page instance
        namespace: Project namespace
        project: Project name
        mr_id: Merge request ID number

    Returns:
        CloseMergeRequestResult with success status and any error message
    """
    url = get_merge_request_url(namespace, project, mr_id)
    page.goto(url, wait_until="networkidle")

    if _is_page_not_found(page):
        return CloseMergeRequestResult(
            success=False,
            error_message=f"Merge request not found at {url}"
        )

    # Click close button
    try:
        page.click(Selectors.MR_CLOSE_BUTTON)
    except Exception:
        return CloseMergeRequestResult(
            success=False,
            error_message="Close button not found"
        )

    # Verify status changed to "Closed"
    try:
        expect(page.locator(Selectors.MR_STATUS_SPAN)).to_have_text("Closed", timeout=10000)
        return CloseMergeRequestResult(success=True)
    except TimeoutError:
        return CloseMergeRequestResult(
            success=False,
            error_message="Status did not change to 'Closed'"
        )


def close_merge_request_by_url(page: Page, mr_url: str) -> CloseMergeRequestResult:
    """
    Close a merge request given its URL.

    Args:
        page: Playwright Page instance
        mr_url: Full URL of the merge request

    Returns:
        CloseMergeRequestResult with success status and any error message
    """
    page.goto(mr_url, wait_until="networkidle")

    if _is_page_not_found(page):
        return CloseMergeRequestResult(
            success=False,
            error_message=f"Merge request not found at {mr_url}"
        )

    # Click close button
    try:
        page.click(Selectors.MR_CLOSE_BUTTON)
    except Exception:
        return CloseMergeRequestResult(
            success=False,
            error_message="Close button not found"
        )

    # Verify status
    try:
        expect(page.locator(Selectors.MR_STATUS_SPAN)).to_have_text("Closed", timeout=10000)
        return CloseMergeRequestResult(success=True)
    except TimeoutError:
        return CloseMergeRequestResult(
            success=False,
            error_message="Status did not change to 'Closed'"
        )


def _is_page_not_found(page: Page) -> bool:
    """Check if the current page shows a 'Page Not Found' error."""
    container = page.locator(Selectors.PAGE_NOT_FOUND)
    if container.count() > 0:
        text = container.text_content()
        if text and "Page Not Found" in text:
            return True
    return False
