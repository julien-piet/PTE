"""Customer login helpers."""

from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page

from .constants import (
    LOGIN_URL,
    LOGIN_USERNAME_SELECTOR,
    LOGIN_PASSWORD_SELECTOR,
    LOGIN_REMEMBER_SELECTOR,
    LOGIN_SUBMIT_SELECTOR,
    ERROR_SELECTOR,
)


@dataclass
class LoginResult:
    """Outcome of attempting to sign in."""
    
    success: bool
    redirect_url: Optional[str]
    username: Optional[str] = None
    error_message: Optional[str] = None


def login_user(page: Page, username: str, password: str, remember_me: bool = True) -> LoginResult:
    """
    Sign in through the login form.
    
    Navigates to the login page, fills the username/password fields, submits the form,
    and reports whether the attempt succeeded. Failed logins remain on the login page
    or show error messages.
    
    Args:
        page: Playwright page object
        username: Username or email
        password: User password
        remember_me: Whether to check "Remember Me" checkbox
    
    Returns:
        LoginResult with success status and details
    """
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
    
    # Fill username
    username_input = page.locator(LOGIN_USERNAME_SELECTOR)
    if username_input.count() == 0:
        return LoginResult(False, None, None, "Username field not found")
    
    username_input.fill(username)
    
    # Fill password
    password_input = page.locator(LOGIN_PASSWORD_SELECTOR)
    if password_input.count() == 0:
        return LoginResult(False, None, None, "Password field not found")
    
    password_input.fill(password)
    
    # Handle remember me checkbox
    if remember_me:
        remember_checkbox = page.locator(LOGIN_REMEMBER_SELECTOR)
        if remember_checkbox.count() > 0:
            remember_checkbox.check()
    
    # Submit form
    submit_btn = page.locator(LOGIN_SUBMIT_SELECTOR)
    if submit_btn.count() == 0:
        return LoginResult(False, None, None, "Login button not found")
    
    submit_btn.click()
    page.wait_for_load_state("domcontentloaded", timeout=30000)
    
    # Check for errors
    error_loc = page.locator(ERROR_SELECTOR)
    if error_loc.count() > 0:
        message = error_loc.first.text_content().strip()
        if not message:
            message = "Invalid username or password"
        return LoginResult(False, None, None, message)
    
    # Check if still on login page (indicates failure)
    current_url = page.url
    if "login" in current_url.lower():
        return LoginResult(False, None, None, "Login failed - still on login page")
    
    # Success - redirected away from login page
    return LoginResult(True, current_url, username)
