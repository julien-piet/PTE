"""User logout helpers."""

from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page

from .constants import USER_MENU_SELECTORS, LOGOUT_SELECTORS


@dataclass
class LogoutResult:
    """Outcome of attempting to log out."""
    
    success: bool
    error_message: Optional[str] = None


def logout_user(page: Page) -> LogoutResult:
    """
    Log out the current user.
    
    Opens the user menu dropdown (if needed) and clicks the logout button.
    The logout button is often hidden in a dropdown menu that must be opened first.
    
    Args:
        page: Playwright page object
    
    Returns:
        LogoutResult with success status
    """
    # Try to open user menu dropdown
    for selector in USER_MENU_SELECTORS:
        menu_elem = page.locator(selector)
        if menu_elem.count() > 0 and menu_elem.first.is_visible():
            menu_elem.first.click()
            page.wait_for_timeout(500)  # Wait for menu animation
            break
    
    # Try to click logout button
    for selector in LOGOUT_SELECTORS:
        logout_elem = page.locator(selector)
        if logout_elem.count() > 0:
            try:
                # Use force=True to click even if visibility checks fail
                logout_elem.first.click(force=True, timeout=5000)
                page.wait_for_load_state("domcontentloaded")
                return LogoutResult(True)
            except Exception as e:
                # Try next selector
                continue
    
    return LogoutResult(False, "Could not find or click logout button")
