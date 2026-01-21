"""Checks for the registration helper."""

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

from api.reddit_pw import registration  # noqa:E402
from api.reddit_pw.test_utils import FakeLocator, FakePage  # noqa:E402


class RegistrationTests(unittest.TestCase):
    def test_registration_successful(self) -> None:
        """Test successful user registration."""
        username_input = FakeLocator(count_value=1)
        email_input = FakeLocator(count_value=1)
        password_first = FakeLocator(count_value=1)
        password_second = FakeLocator(count_value=1)
        submit_btn = FakeLocator(count_value=1)
        
        page = FakePage(
            locators={
                registration.REGISTRATION_USERNAME_SELECTOR: username_input,
                registration.REGISTRATION_EMAIL_SELECTOR: email_input,
                registration.REGISTRATION_PASSWORD_FIRST_SELECTOR: password_first,
                registration.REGISTRATION_PASSWORD_SECOND_SELECTOR: password_second,
                registration.REGISTRATION_SUBMIT_SELECTOR: submit_btn,
                registration.ERROR_SELECTOR: FakeLocator(count_value=0),
            },
            url=registration.REGISTRATION_URL,
        )
        
        # Simulate successful redirect
        success_url = "http://example.com/"
        submit_btn.on_click = lambda: setattr(page, "url", success_url)
        
        result = registration.register_user(page, "newuser", "new@example.com", "pass123")
        
        self.assertTrue(result.success)
        self.assertEqual(result.username, "newuser")
        self.assertEqual(result.redirect_url, success_url)
        self.assertEqual(username_input.text, "newuser")
        self.assertEqual(email_input.text, "new@example.com")
        self.assertEqual(password_first.text, "pass123")
        self.assertEqual(password_second.text, "pass123")
    
    def test_registration_disabled_returns_error(self) -> None:
        """Test registration disabled message."""
        submit_btn = FakeLocator(count_value=1)
        body_locator = FakeLocator(
            text="You cannot create new accounts at this time",
            count_value=1
        )
        
        page = FakePage(
            locators={
                registration.REGISTRATION_USERNAME_SELECTOR: FakeLocator(count_value=1),
                registration.REGISTRATION_EMAIL_SELECTOR: FakeLocator(count_value=1),
                registration.REGISTRATION_PASSWORD_FIRST_SELECTOR: FakeLocator(count_value=1),
                registration.REGISTRATION_PASSWORD_SECOND_SELECTOR: FakeLocator(count_value=1),
                registration.REGISTRATION_SUBMIT_SELECTOR: submit_btn,
                registration.ERROR_SELECTOR: FakeLocator(count_value=0),
                "body": body_locator,
            },
            url=registration.REGISTRATION_URL,
        )
        
        # Stay on registration page
        submit_btn.on_click = lambda: None
        
        result = registration.register_user(page, "user", "email@test.com", "pass")
        
        self.assertFalse(result.success)
        self.assertIn("disabled", (result.error_message or "").lower())
    
    def test_registration_duplicate_user_returns_error(self) -> None:
        """Test duplicate username error."""
        error_msg = "Username already exists"
        submit_btn = FakeLocator(count_value=1)
        error_loc = FakeLocator(text=error_msg, count_value=1)
        
        page = FakePage(
            locators={
                registration.REGISTRATION_USERNAME_SELECTOR: FakeLocator(count_value=1),
                registration.REGISTRATION_EMAIL_SELECTOR: FakeLocator(count_value=1),
                registration.REGISTRATION_PASSWORD_FIRST_SELECTOR: FakeLocator(count_value=1),
                registration.REGISTRATION_PASSWORD_SECOND_SELECTOR: FakeLocator(count_value=1),
                registration.REGISTRATION_SUBMIT_SELECTOR: submit_btn,
                registration.ERROR_SELECTOR: error_loc,
            },
            url=registration.REGISTRATION_URL,
        )
        
        result = registration.register_user(page, "existing", "email@test.com", "pass")
        
        self.assertFalse(result.success)
        self.assertIn("exists", (result.error_message or "").lower())
    
    def test_missing_username_field_returns_error(self) -> None:
        """Test missing username field."""
        page = FakePage(
            locators={
                registration.REGISTRATION_EMAIL_SELECTOR: FakeLocator(count_value=1),
            },
            url=registration.REGISTRATION_URL
        )
        
        result = registration.register_user(page, "user", "email@test.com", "pass")
        
        self.assertFalse(result.success)
        self.assertIn("username", (result.error_message or "").lower())


if __name__ == "__main__":
    unittest.main()
