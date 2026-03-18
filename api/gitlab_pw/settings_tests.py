"""Checks for the settings helper."""

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
playwright_stub.sync_api = types.SimpleNamespace(Page=object, TimeoutError=TimeoutError, expect=lambda x: x)
sys.modules["playwright"] = playwright_stub
sys.modules["playwright.sync_api"] = playwright_stub.sync_api

from api.gitlab_pw import settings  # noqa:E402
from api.gitlab_pw.constants import Selectors, GITLAB_DOMAIN, PROFILE_URL, ACCOUNT_URL  # noqa:E402
from api.gitlab_pw.test_utils import FakeLocator, FakePage  # noqa:E402


class SettingsDataclassTests(unittest.TestCase):
    def test_profile_update_result_dataclass(self) -> None:
        """Test ProfileUpdateResult dataclass."""
        result = settings.ProfileUpdateResult(success=True)
        self.assertTrue(result.success)

        failed = settings.ProfileUpdateResult(
            success=False,
            error_message="Update failed",
        )
        self.assertFalse(failed.success)

    def test_username_change_result_dataclass(self) -> None:
        """Test UsernameChangeResult dataclass."""
        result = settings.UsernameChangeResult(
            success=True,
            new_username="newname",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.new_username, "newname")

    def test_delete_result_dataclass(self) -> None:
        """Test DeleteResult dataclass."""
        result = settings.DeleteResult(success=True)
        self.assertTrue(result.success)

        result_with_msg = settings.DeleteResult(
            success=True,
            error_message="Deleted 3 token(s)",
        )
        self.assertTrue(result_with_msg.success)
        self.assertIn("3", result_with_msg.error_message or "")


class TogglePrivateProfileTests(unittest.TestCase):
    def test_toggle_private_profile_enable(self) -> None:
        """Test enabling private profile."""
        checkbox = FakeLocator(count_value=1, is_checked=False)
        update_btn = FakeLocator(count_value=1)
        success_alert = FakeLocator(
            text="Profile was successfully updated",
            count_value=1,
        )

        page = FakePage(
            locators={
                Selectors.PRIVATE_PROFILE_CHECKBOX: checkbox,
                Selectors.UPDATE_PROFILE_BUTTON: update_btn,
                'div.gl-alert-body:has-text("Profile was successfully updated")': success_alert,
            },
            url=PROFILE_URL,
        )

        # Simulate checkbox getting checked after check() is called
        def on_check():
            checkbox._is_checked = True
        checkbox.check = lambda: (checkbox.actions.append(("check", None)), on_check())[-1]

        result = settings.toggle_private_profile(page, make_private=True)

        self.assertTrue(result.success)

    def test_toggle_private_profile_already_correct(self) -> None:
        """Test toggling when already in desired state."""
        checkbox = FakeLocator(count_value=1, is_checked=True)

        page = FakePage(
            locators={
                Selectors.PRIVATE_PROFILE_CHECKBOX: checkbox,
            },
            url=PROFILE_URL,
        )

        result = settings.toggle_private_profile(page, make_private=True)

        self.assertTrue(result.success)
        # Should not have clicked update since already in correct state
        self.assertEqual(len(checkbox.actions), 0)


class ChangeUsernameTests(unittest.TestCase):
    def test_change_username_same_as_current(self) -> None:
        """Test changing to same username."""
        page = FakePage(
            locators={
                Selectors.USERNAME_INPUT: FakeLocator(count_value=1),
            },
            url=ACCOUNT_URL,
        )
        page._input_values[Selectors.USERNAME_INPUT] = "currentuser"

        result = settings.change_username(page, "currentuser")

        self.assertTrue(result.success)
        self.assertEqual(result.new_username, "currentuser")


class DeleteDeployKeyTests(unittest.TestCase):
    def test_delete_deploy_key_dataclass(self) -> None:
        """Test DeleteResult dataclass for deploy keys."""
        result = settings.DeleteResult(
            success=True,
            error_message="No deploy key found (may already be deleted)",
        )
        self.assertTrue(result.success)
        self.assertIn("already be deleted", result.error_message or "")


class DeleteWebhooksTests(unittest.TestCase):
    def test_delete_all_webhooks_dataclass(self) -> None:
        """Test DeleteResult dataclass for webhooks."""
        result = settings.DeleteResult(
            success=True,
            error_message="No webhooks found",
        )
        self.assertTrue(result.success)
        self.assertIn("No webhooks", result.error_message or "")


class DeleteAccessTokensTests(unittest.TestCase):
    def test_delete_all_access_tokens_dataclass(self) -> None:
        """Test DeleteResult dataclass for access tokens."""
        result = settings.DeleteResult(
            success=True,
            error_message="No tokens found",
        )
        self.assertTrue(result.success)
        self.assertIn("No tokens", result.error_message or "")


class DeleteAccountTests(unittest.TestCase):
    def test_delete_account_button_not_found(self) -> None:
        """Test account deletion when button is missing."""
        page = FakePage(
            locators={
                Selectors.DELETE_ACCOUNT_BUTTON: FakeLocator(count_value=0),
            },
            url=ACCOUNT_URL,
        )

        result = settings.delete_account(page, "password123")

        self.assertFalse(result.success)
        self.assertIn("not found", (result.error_message or "").lower())


if __name__ == "__main__":
    unittest.main()
