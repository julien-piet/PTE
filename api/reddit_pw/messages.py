"""Reddit private messaging helpers."""

from dataclasses import dataclass
from typing import List, Optional

from playwright.sync_api import Page, TimeoutError

from .constants import (
    REDDIT_DOMAIN,
    MESSAGES_URL,
    Selectors,
    get_compose_message_url,
)


@dataclass
class Message:
    """Representation of a Reddit private message."""

    id: str
    body: str
    sender: str
    recipient: str
    url: str
    thread_url: str


@dataclass
class MessageResult:
    """Result of attempting to send a message."""

    success: bool
    message_url: Optional[str]
    thread_url: Optional[str] = None
    already_existed: bool = False
    error_message: Optional[str] = None


@dataclass
class DeleteMessagesResult:
    """Result of attempting to delete messages."""

    success: bool
    deleted_count: int = 0
    error_message: Optional[str] = None


def send_message(
    page: Page,
    recipient_username: str,
    message_body: str,
) -> MessageResult:
    """
    Send a private message to a Reddit user.

    Checks if an identical message already exists before sending.

    Args:
        page: Playwright Page instance
        recipient_username: Username to send the message to
        message_body: Content of the message

    Returns:
        MessageResult with success status, URL, and any error message
    """
    # First check if this message already exists
    page.goto(MESSAGES_URL, wait_until="networkidle")

    if message_body in page.content() and recipient_username in page.content():
        link = page.query_selector(f"a:has-text('{message_body}')")
        if link:
            href = link.get_attribute("href")
            existing_url = f"{REDDIT_DOMAIN}{href}" if href else None
            return MessageResult(
                success=True,
                message_url=existing_url,
                already_existed=True,
                error_message=f"A message with this content to {recipient_username} already exists"
            )

    # Navigate to compose message page
    compose_url = get_compose_message_url(recipient_username)
    page.goto(compose_url, wait_until="networkidle")

    # Wait for message form
    try:
        page.wait_for_selector(Selectors.MESSAGE_BODY_INPUT, timeout=10000)
    except TimeoutError:
        return MessageResult(
            success=False,
            message_url=None,
            error_message="Message form not found"
        )

    # Fill in message
    page.fill(Selectors.MESSAGE_BODY_INPUT, message_body)

    # Submit - using sync pattern
    page.click(Selectors.MESSAGE_SUBMIT_BUTTON)
    page.wait_for_load_state("networkidle")

    # Check if we're still on compose page (sending failed)
    if page.url.strip("/") == compose_url.strip("/"):
        return MessageResult(
            success=False,
            message_url=None,
            error_message="Failed to send message - still on compose page"
        )

    return MessageResult(
        success=True,
        message_url=page.url,
        thread_url=page.url,
        already_existed=False,
        error_message=None
    )


def delete_all_messages(
    page: Page,
    username: str,
) -> DeleteMessagesResult:
    """
    Delete all messages for a user.

    Args:
        page: Playwright Page instance
        username: Username whose messages should be deleted

    Returns:
        DeleteMessagesResult with success status and count of deleted messages
    """
    page.goto(MESSAGES_URL, wait_until="networkidle")

    # Get all message thread links
    links = page.query_selector_all(Selectors.MESSAGE_THREAD_LINKS)
    thread_hrefs = [link.get_attribute("href") for link in links if link.get_attribute("href")]

    # Set up dialog handler to accept confirmation
    page.on("dialog", lambda dialog: dialog.accept())

    deleted_count = 0
    errors = []

    for href in thread_hrefs:
        try:
            full_url = f"{REDDIT_DOMAIN}{href}" if not href.startswith("http") else href
            page.goto(full_url, wait_until="networkidle")

            button = page.query_selector(Selectors.DELETE_BUTTON)
            if button:
                button.click()
                page.wait_for_timeout(1000)
                deleted_count += 1
        except Exception as e:
            errors.append(f"Error deleting message thread: {str(e)}")

    error_message = None
    if errors:
        error_message = "; ".join(errors)

    return DeleteMessagesResult(
        success=deleted_count > 0 or len(thread_hrefs) == 0,
        deleted_count=deleted_count,
        error_message=error_message
    )


def delete_all_messages_by_user(page: Page, username: str) -> DeleteMessagesResult:
    """Alias for delete_all_messages for compatibility with reddit_editor.py."""
    return delete_all_messages(page, username)


def get_message_threads(page: Page) -> List[Message]:
    """
    Get all message threads for the current user.

    Args:
        page: Playwright Page instance

    Returns:
        List of Message objects representing thread summaries
    """
    page.goto(MESSAGES_URL, wait_until="networkidle")

    messages: List[Message] = []

    # Get all message thread links
    links = page.query_selector_all(Selectors.MESSAGE_THREAD_LINKS)

    for idx, link in enumerate(links):
        href = link.get_attribute("href") or ""
        preview_text = link.inner_text().strip()

        # Try to extract sender/recipient from context
        parent = link.query_selector("xpath=..")
        sender = ""
        if parent:
            sender_elem = parent.query_selector(".username, .author, a[href*='/user/']")
            if sender_elem:
                sender = sender_elem.inner_text().strip()

        thread_url = f"{REDDIT_DOMAIN}{href}" if not href.startswith("http") else href

        messages.append(Message(
            id=str(idx),
            body=preview_text,
            sender=sender,
            recipient="",  # Would need to visit thread to determine
            url=thread_url,
            thread_url=thread_url,
        ))

    return messages
