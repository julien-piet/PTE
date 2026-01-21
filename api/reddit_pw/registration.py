"""User registration helpers."""

from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page

from .constants import (
    REGISTRATION_URL,
    REGISTRATION_USERNAME_SELECTOR,
    REGISTRATION_EMAIL_SELECTOR,
    REGISTRATION_PASSWORD_FIRST_SELECTOR,
    REGISTRATION_PASSWORD_SECOND_SELECTOR,
    REGISTRATION_SUBMIT_SELECTOR,
    ERROR_SELECTOR,
)


@dataclass
class RegistrationResult:
    """Outcome of attempting to register."""
    
    success: bool
    redirect_url: Optional[str]
    username: Optional[str] = None
    error_message: Optional[str] = None


def register_user(page: Page, username: str, email: str, password: str) -> RegistrationResult:
    """
    Register a new user account.
    
    Navigates to the registration page, fills all required fields, submits the form,
    and reports whether registration succeeded.
    
    Args:
        page: Playwright page object
        username: Desired username
        email: Valid email address
        password: User password
    
    Returns:
        RegistrationResult with success status and details
    """
    page.goto(REGISTRATION_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(500)
    
    # Fill username
    username_input = page.locator(REGISTRATION_USERNAME_SELECTOR)
    if username_input.count() == 0:
        return RegistrationResult(False, None, None, "Username field not found")
    
    username_input.fill(username)
    
    # Fill email
    email_input = page.locator(REGISTRATION_EMAIL_SELECTOR)
    if email_input.count() == 0:
        return RegistrationResult(False, None, None, "Email field not found")
    
    email_input.fill(email)
    
    # Fill password (both fields)
    password_first = page.locator(REGISTRATION_PASSWORD_FIRST_SELECTOR)
    password_second = page.locator(REGISTRATION_PASSWORD_SECOND_SELECTOR)
    
    if password_first.count() == 0:
        return RegistrationResult(False, None, None, "Password field not found")
    if password_second.count() == 0:
        return RegistrationResult(False, None, None, "Password confirmation field not found")
    
    password_first.fill(password)
    password_second.fill(password)
    
    # Submit form
    submit_btn = page.locator(REGISTRATION_SUBMIT_SELECTOR)
    if submit_btn.count() == 0:
        return RegistrationResult(False, None, None, "Submit button not found")
    
    submit_btn.click()
    page.wait_for_load_state("domcontentloaded", timeout=30000)
    
    # Check for errors
    error_loc = page.locator(ERROR_SELECTOR)
    if error_loc.count() > 0:
        message = error_loc.first.text_content().strip()
        if not message:
            message = "Registration failed"
        return RegistrationResult(False, None, None, message)
    
    # Check if still on registration page (indicates failure)
    current_url = page.url
    if "registration" in current_url.lower():
        # Check for specific error messages in page content
        body_text = page.locator("body").text_content()
        
        if "cannot create new accounts" in body_text.lower():
            return RegistrationResult(False, None, None, "Registration is disabled on this server")
        
        if "already" in body_text.lower() or "exists" in body_text.lower():
            return RegistrationResult(False, None, None, "Username or email already exists")
        
        return RegistrationResult(False, None, None, "Registration failed - still on registration page")
    
    # Success - redirected away from registration page
    return RegistrationResult(True, current_url, username)
