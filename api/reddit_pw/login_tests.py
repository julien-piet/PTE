"""Checks for the login helper."""

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

from api.reddit_pw import login  # noqa:E402
from api.reddit_pw.test_utils import FakeLocator, FakePage  # noqa:E402


class LoginTests(unittest.TestCase):
    def test_login_successful_redirect(self) -> None:
        """Test successful login with redirect."""
        username_input = FakeLocator(count_value=1)
        password_input = FakeLocator(count_value=1)
        remember_checkbox = FakeLocator(count_value=1)
        submit_btn = FakeLocator(count_value=1)
        
        page = FakePage(
            locators={
                login.LOGIN_USERNAME_SELECTOR: username_input,
                login.LOGIN_PASSWORD_SELECTOR: password_input,
                login.LOGIN_REMEMBER_SELECTOR: remember_checkbox,
                login.LOGIN_SUBMIT_SELECTOR: submit_btn,
                login.ERROR_SELECTOR: FakeLocator(count_value=0),
            },
            url=login.LOGIN_URL,
        )
        
        # Simulate successful login redirect
        account_url = "http://example.com/"
        submit_btn.on_click = lambda: setattr(page, "url", account_url)
        
        result = login.login_user(page, "testuser", "password123")
        
        self.assertTrue(result.success)
        self.assertEqual(result.redirect_url, account_url)
        self.assertEqual(result.username, "testuser")
        self.assertIn(login.LOGIN_URL, page.visited)
        self.assertEqual(username_input.text, "testuser")
        self.assertEqual(password_input.text, "password123")
        self.assertTrue(remember_checkbox.attributes.get("checked", False))
    
    def test_login_invalid_credentials_surface_error(self) -> None:
        """Test login with invalid credentials shows error."""
        error_msg = "Invalid username or password"
        submit_btn = FakeLocator(count_value=1)
        error_loc = FakeLocator(text=error_msg, count_value=1)
        
        page = FakePage(
            locators={
                login.LOGIN_USERNAME_SELECTOR: FakeLocator(count_value=1),
                login.LOGIN_PASSWORD_SELECTOR: FakeLocator(count_value=1),
                login.LOGIN_REMEMBER_SELECTOR: FakeLocator(count_value=1),
                login.LOGIN_SUBMIT_SELECTOR: submit_btn,
                login.ERROR_SELECTOR: error_loc,
            },
            url=login.LOGIN_URL,
        )
        
        # Simulate staying on login page (failure)
        submit_btn.on_click = lambda: None
        
        result = login.login_user(page, "baduser", "wrong")
        
        self.assertFalse(result.success)
        self.assertIn("invalid", (result.error_message or "").lower())
        self.assertIsNone(result.redirect_url)
    
    def test_missing_username_field_returns_error(self) -> None:
        """Test missing username field returns error."""
        page = FakePage(
            locators={
                login.LOGIN_PASSWORD_SELECTOR: FakeLocator(count_value=1),
                login.LOGIN_SUBMIT_SELECTOR: FakeLocator(count_value=1),
            },
            url=login.LOGIN_URL
        )
        
        result = login.login_user(page, "user", "pass")
        
        self.assertFalse(result.success)
        self.assertIn("username", (result.error_message or "").lower())
    
    def test_missing_password_field_returns_error(self) -> None:
        """Test missing password field returns error."""
        page = FakePage(
            locators={
                login.LOGIN_USERNAME_SELECTOR: FakeLocator(count_value=1),
                login.LOGIN_SUBMIT_SELECTOR: FakeLocator(count_value=1),
            },
            url=login.LOGIN_URL
        )
        
        result = login.login_user(page, "user", "pass")
        
        self.assertFalse(result.success)
        self.assertIn("password", (result.error_message or "").lower())
    
    def test_missing_submit_button_returns_error(self) -> None:
        """Test missing submit button returns error."""
        page = FakePage(
            locators={
                login.LOGIN_USERNAME_SELECTOR: FakeLocator(count_value=1),
                login.LOGIN_PASSWORD_SELECTOR: FakeLocator(count_value=1),
            },
            url=login.LOGIN_URL
        )
        
        result = login.login_user(page, "user", "pass")
        
        self.assertFalse(result.success)
        self.assertIn("button", (result.error_message or "").lower())


if __name__ == "__main__":
    unittest.main()
