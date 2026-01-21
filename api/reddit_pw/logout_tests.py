"""Checks for the logout helper."""

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

from api.reddit_pw import logout  # noqa:E402
from api.reddit_pw.test_utils import FakeLocator, FakePage  # noqa:E402


class LogoutTests(unittest.TestCase):
    def test_logout_successful(self) -> None:
        """Test successful logout."""
        menu_button = FakeLocator(count_value=1, visible=True)
        logout_button = FakeLocator(count_value=1)
        
        page = FakePage(
            locators={
                logout.USER_MENU_SELECTORS[0]: menu_button,
                logout.LOGOUT_SELECTORS[0]: logout_button,
            },
            url="http://example.com/",
        )
        
        # Simulate successful logout
        home_url = "http://example.com/"
        logout_button.on_click = lambda: setattr(page, "url", home_url)
        
        result = logout.logout_user(page)
        
        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)
    
    def test_logout_button_not_found_returns_error(self) -> None:
        """Test logout when button cannot be found."""
        page = FakePage(
            locators={
                logout.USER_MENU_SELECTORS[0]: FakeLocator(count_value=0),
                logout.LOGOUT_SELECTORS[0]: FakeLocator(count_value=0),
            },
            url="http://example.com/"
        )
        
        result = logout.logout_user(page)
        
        self.assertFalse(result.success)
        self.assertIn("logout", (result.error_message or "").lower())
    
    def test_logout_with_hidden_menu_opens_dropdown(self) -> None:
        """Test logout opens dropdown menu first."""
        menu_opened = False
        
        def open_menu():
            nonlocal menu_opened
            menu_opened = True
        
        menu_button = FakeLocator(count_value=1, visible=True)
        menu_button.on_click = open_menu
        
        logout_button = FakeLocator(count_value=1)
        
        page = FakePage(
            locators={
                logout.USER_MENU_SELECTORS[1]: menu_button,
                logout.LOGOUT_SELECTORS[0]: logout_button,
            },
            url="http://example.com/",
        )
        
        result = logout.logout_user(page)
        
        self.assertTrue(result.success)
        self.assertTrue(menu_opened)


if __name__ == "__main__":
    unittest.main()
