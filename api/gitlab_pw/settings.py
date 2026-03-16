"""GitLab settings management helpers (deploy keys, tokens, webhooks, profile)."""

from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page, TimeoutError

from .constants import (
    GITLAB_DOMAIN,
    PROFILE_URL,
    ACCOUNT_URL,
    SSH_KEYS_URL,
    ACCESS_TOKENS_URL,
    Selectors,
    get_deploy_keys_url,
    get_deploy_tokens_url,
    get_webhooks_url,
)


@dataclass
class ProfileUpdateResult:
    """Result of attempting to update profile settings."""

    success: bool
    error_message: Optional[str] = None


@dataclass
class UsernameChangeResult:
    """Result of attempting to change username."""

    success: bool
    new_username: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class DeleteResult:
    """Generic result for deletion operations."""

    success: bool
    error_message: Optional[str] = None


def toggle_private_profile(
    page: Page,
    make_private: bool,
) -> ProfileUpdateResult:
    """
    Set the private profile checkbox to the desired state.

    Args:
        page: Playwright Page instance
        make_private: True to make profile private, False to make public

    Returns:
        ProfileUpdateResult with success status
    """
    page.goto(PROFILE_URL, wait_until="networkidle")

    checkbox = page.locator(Selectors.PRIVATE_PROFILE_CHECKBOX)
    if checkbox.count() == 0:
        return ProfileUpdateResult(
            success=False,
            error_message="Private profile checkbox not found"
        )

    current_state = checkbox.is_checked()

    if current_state == make_private:
        return ProfileUpdateResult(success=True)

    # Toggle the checkbox
    if make_private:
        checkbox.check()
    else:
        checkbox.uncheck()

    # Save settings
    page.locator(Selectors.UPDATE_PROFILE_BUTTON).click()

    # Wait for success message
    try:
        page.wait_for_selector(
            "div.gl-alert-body:has-text('Profile was successfully updated')",
            state="visible",
            timeout=5000
        )
    except TimeoutError:
        return ProfileUpdateResult(
            success=False,
            error_message="Did not receive success confirmation"
        )

    # Verify state changed
    final_state = page.locator(Selectors.PRIVATE_PROFILE_CHECKBOX).is_checked()
    if final_state != make_private:
        return ProfileUpdateResult(
            success=False,
            error_message="Checkbox state did not change"
        )

    return ProfileUpdateResult(success=True)


def change_username(
    page: Page,
    new_username: str,
) -> UsernameChangeResult:
    """
    Change the current user's username.

    Args:
        page: Playwright Page instance
        new_username: New username to set

    Returns:
        UsernameChangeResult with success status
    """
    page.goto(ACCOUNT_URL, wait_until="networkidle")

    # Get current username
    username_input = page.locator(Selectors.USERNAME_INPUT)
    if username_input.count() == 0:
        return UsernameChangeResult(
            success=False,
            error_message="Username input not found"
        )

    current_username = page.input_value(Selectors.USERNAME_INPUT)
    if current_username.strip() == new_username:
        return UsernameChangeResult(
            success=True,
            new_username=new_username
        )

    # Fill new username
    page.fill(Selectors.USERNAME_INPUT, new_username)

    # Click first confirmation trigger
    try:
        page.wait_for_selector(Selectors.USERNAME_CHANGE_TRIGGER, timeout=5000)
        page.click(Selectors.USERNAME_CHANGE_TRIGGER)
    except TimeoutError:
        return UsernameChangeResult(
            success=False,
            error_message="Username change trigger not found"
        )

    # Click second confirmation button
    try:
        page.wait_for_selector(Selectors.USERNAME_CHANGE_CONFIRM, timeout=10000)
        page.click(Selectors.USERNAME_CHANGE_CONFIRM)
    except TimeoutError:
        return UsernameChangeResult(
            success=False,
            error_message="Confirmation button not found"
        )

    # Wait for success
    try:
        page.wait_for_selector(Selectors.FLASH_CONTAINER, timeout=10000)
        success_msg = page.locator("div", has_text="Username successfully changed")
        if success_msg.count() > 0:
            return UsernameChangeResult(
                success=True,
                new_username=new_username
            )
    except TimeoutError:
        pass

    return UsernameChangeResult(
        success=False,
        error_message="Did not receive success confirmation"
    )


def delete_deploy_key(
    page: Page,
    namespace: str,
    project: str,
) -> DeleteResult:
    """
    Delete a deploy key from a project.

    Args:
        page: Playwright Page instance
        namespace: Project namespace
        project: Project name

    Returns:
        DeleteResult with success status
    """
    url = get_deploy_keys_url(namespace, project)
    page.goto(url, wait_until="networkidle")

    delete_btn_selector = "#js-deploy-keys-settings > div.settings-content > div > div.deploy-keys-panel.table-holder > div.gl-responsive-table-row.deploy-key > div.table-section.section-15.table-button-footer.deploy-key-actions > div > button"
    confirm_btn_selector = "#confirm-remove-deploy-key___BV_modal_footer_ > button.btn.js-modal-action-primary.btn-danger.btn-md.gl-button"

    try:
        page.wait_for_selector(delete_btn_selector, timeout=3000)
        page.click(delete_btn_selector)
        page.wait_for_timeout(1000)

        page.wait_for_selector(confirm_btn_selector, timeout=3000)
        page.click(confirm_btn_selector)
        page.wait_for_timeout(1000)

        return DeleteResult(success=True)
    except TimeoutError:
        return DeleteResult(
            success=True,
            error_message="No deploy key found (may already be deleted)"
        )


def delete_deploy_token(
    page: Page,
    namespace: str,
    project: str,
) -> DeleteResult:
    """
    Delete a deploy token from a project.

    Args:
        page: Playwright Page instance
        namespace: Project namespace
        project: Project name

    Returns:
        DeleteResult with success status
    """
    url = get_deploy_tokens_url(namespace, project)
    page.goto(url, wait_until="networkidle")

    expand_selector = "#js-deploy-tokens > div.settings-header > button"
    delete_btn_selector = "#js-deploy-tokens > div.settings-content > div.table-responsive.deploy-tokens > table > tbody > tr > td:nth-child(6) > div > button"
    confirm_btn_selector = "#revoke-modal-1___BV_modal_footer_ > a"

    try:
        page.wait_for_selector(expand_selector, timeout=3000)
        page.click(expand_selector)
        page.wait_for_timeout(1000)

        page.wait_for_selector(delete_btn_selector, timeout=3000)
        page.click(delete_btn_selector)
        page.wait_for_timeout(1000)

        page.wait_for_selector(confirm_btn_selector, timeout=3000)
        page.click(confirm_btn_selector)
        page.wait_for_timeout(1000)

        return DeleteResult(success=True)
    except TimeoutError:
        return DeleteResult(
            success=True,
            error_message="No deploy token found (may already be deleted)"
        )


def delete_all_webhooks(
    page: Page,
    namespace: str,
    project: str,
) -> DeleteResult:
    """
    Delete all webhooks from a project.

    Args:
        page: Playwright Page instance
        namespace: Project namespace
        project: Project name

    Returns:
        DeleteResult with success status
    """
    url = get_webhooks_url(namespace, project)
    page.goto(url, wait_until="networkidle")

    delete_btn_selector = "a >> text=Delete"
    confirm_btn_selector = "#confirmationModal___BV_modal_footer_ > button.btn.js-modal-action-primary.btn-danger.btn-md.gl-button"

    deleted_count = 0
    while True:
        try:
            page.wait_for_selector(delete_btn_selector, timeout=3000)
            page.click(delete_btn_selector)
            page.wait_for_timeout(1000)

            page.wait_for_selector(confirm_btn_selector, timeout=3000)
            page.click(confirm_btn_selector)
            page.wait_for_timeout(1000)

            deleted_count += 1
        except TimeoutError:
            break

    return DeleteResult(
        success=True,
        error_message=f"Deleted {deleted_count} webhook(s)" if deleted_count > 0 else "No webhooks found"
    )


def delete_ssh_key(page: Page) -> DeleteResult:
    """
    Delete an SSH key from the current user's profile.

    Args:
        page: Playwright Page instance

    Returns:
        DeleteResult with success status
    """
    page.goto(SSH_KEYS_URL, wait_until="networkidle")

    delete_btn_selector = "#content-body > div.row.gl-mt-3.js-search-settings-section > div.col-lg-8 > div.gl-mb-3 > ul > li > div > span > div > div > button"
    confirm_btn_selector = "#confirm-modal-1___BV_modal_footer_ > button.btn.btn-danger"

    try:
        page.wait_for_selector(delete_btn_selector, timeout=3000)
        page.click(delete_btn_selector)
        page.wait_for_timeout(1000)

        page.wait_for_selector(confirm_btn_selector, timeout=3000)
        page.click(confirm_btn_selector)
        page.wait_for_timeout(1000)

        return DeleteResult(success=True)
    except TimeoutError:
        return DeleteResult(
            success=True,
            error_message="No SSH key found (may already be deleted)"
        )


def delete_all_access_tokens(page: Page) -> DeleteResult:
    """
    Delete all personal access tokens from the current user's profile.

    Args:
        page: Playwright Page instance

    Returns:
        DeleteResult with success status
    """
    page.goto(ACCESS_TOKENS_URL, wait_until="networkidle")

    delete_btn_selector = "a[aria-label='Revoke']"
    confirm_btn_selector = "#confirmationModal___BV_modal_footer_ > button.btn.js-modal-action-primary.btn-danger.btn-md.gl-button"

    deleted_count = 0
    while True:
        try:
            page.wait_for_selector(delete_btn_selector, timeout=3000)
            page.click(delete_btn_selector)
            page.wait_for_timeout(1000)

            page.wait_for_selector(confirm_btn_selector, timeout=3000)
            page.click(confirm_btn_selector)
            page.wait_for_timeout(1000)

            deleted_count += 1
        except TimeoutError:
            break

    return DeleteResult(
        success=True,
        error_message=f"Deleted {deleted_count} token(s)" if deleted_count > 0 else "No tokens found"
    )


def delete_account(page: Page, password: str) -> DeleteResult:
    """
    Delete the current user's account.

    FIXED: Uses sync pattern instead of expect_navigation context manager.

    Args:
        page: Playwright Page instance
        password: Account password for confirmation

    Returns:
        DeleteResult with success status
    """
    page.goto(ACCOUNT_URL, wait_until="networkidle")

    delete_btn = page.locator(Selectors.DELETE_ACCOUNT_BUTTON)
    if delete_btn.count() == 0:
        # Check for error message
        delete_section = page.locator("text=Delete account").locator(
            "xpath=ancestor::div[contains(@class, 'row')]"
        )
        if delete_section.count() > 0:
            text_column = delete_section.locator(".col-lg-8")
            if text_column.count() > 0:
                error_text = text_column.inner_text()
                return DeleteResult(
                    success=False,
                    error_message=f"Cannot delete account: {error_text}"
                )
        return DeleteResult(
            success=False,
            error_message="Delete account button not found"
        )

    page.click(Selectors.DELETE_ACCOUNT_BUTTON)

    # Fill password confirmation
    try:
        page.wait_for_selector(Selectors.PASSWORD_CONFIRM_FIELD, timeout=5000)
        page.locator(Selectors.PASSWORD_CONFIRM_FIELD).fill(password)
    except TimeoutError:
        return DeleteResult(
            success=False,
            error_message="Password confirmation field not found"
        )

    # Confirm deletion - FIXED: sync pattern
    page.locator(Selectors.CONFIRM_DELETE_ACCOUNT).click()
    page.wait_for_load_state("networkidle")

    # Check if we're redirected to sign-in page
    expected_url = f"{GITLAB_DOMAIN}/users/sign_in"
    if page.url.rstrip("/") == expected_url.rstrip("/"):
        # Check for confirmation message
        alert = page.locator(Selectors.ALERT_BODY)
        if alert.count() > 0:
            text = alert.text_content() or ""
            if "scheduled for removal" in text.lower():
                return DeleteResult(success=True)
        return DeleteResult(success=True)

    # Check for error
    alert = page.locator(Selectors.ALERT_BODY)
    if alert.count() > 0:
        texts = alert.all_inner_texts()
        return DeleteResult(
            success=False,
            error_message="; ".join(texts)
        )

    return DeleteResult(
        success=False,
        error_message=f"Deletion may have failed; ended up at {page.url}"
    )
