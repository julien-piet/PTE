"""Reddit post management helpers."""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

from playwright.sync_api import Page, TimeoutError

from .constants import (
    REDDIT_DOMAIN,
    SUBMIT_URL,
    Selectors,
    get_user_profile_url,
)


@dataclass
class Post:
    """Representation of a Reddit post."""

    id: str
    title: str
    body: str
    author: str
    subreddit: str
    url: str
    created_at: Optional[datetime] = None


@dataclass
class CreatePostResult:
    """Result of attempting to create a post."""

    success: bool
    post_url: Optional[str]
    post_id: Optional[str] = None
    already_existed: bool = False
    error_message: Optional[str] = None


@dataclass
class DeletePostResult:
    """Result of attempting to delete a post."""

    success: bool
    error_message: Optional[str] = None


def create_post(
    page: Page,
    forum: str,
    title: str,
    body: str,
    username: str,
) -> CreatePostResult:
    """
    Create a new Reddit post with title and body text.

    Checks if a post with the same title already exists for the user before creating.

    Args:
        page: Playwright Page instance
        forum: Forum/subreddit name to post in (e.g., "AskReddit")
        title: Title of the post
        body: Body text of the post
        username: Username creating the post (used to check for duplicates)

    Returns:
        CreatePostResult with success status, URL, and any error message
    """
    # First check if a post with this title already exists
    profile_url = get_user_profile_url(username)
    page.goto(profile_url, wait_until="networkidle")

    if title in page.content():
        link = page.query_selector(f"a:has-text('{title}')")
        if link:
            href = link.get_attribute("href")
            existing_url = f"{REDDIT_DOMAIN}{href}" if href else None
            return CreatePostResult(
                success=True,
                post_url=existing_url,
                already_existed=True,
                error_message=f"A post with title '{title}' already exists"
            )

    # Navigate to submit page
    page.goto(SUBMIT_URL, wait_until="networkidle")

    # Wait for form
    try:
        page.wait_for_selector(Selectors.POST_TITLE_INPUT, timeout=10000)
    except TimeoutError:
        return CreatePostResult(
            success=False,
            post_url=None,
            error_message="Post creation form not found"
        )

    # Fill in post details
    page.fill(Selectors.POST_TITLE_INPUT, title)
    page.fill(Selectors.POST_BODY_INPUT, body)

    # Select forum by visible label text (options have numeric values, not forum names)
    page.select_option(Selectors.POST_FORUM_SELECT, label=forum)

    # Submit - using sync pattern
    page.click(Selectors.POST_SUBMIT_BUTTON)
    page.wait_for_load_state("networkidle")

    # Give a bit more time for navigation to complete
    page.wait_for_timeout(500)

    # Check if we're still on submit page (creation failed)
    if page.url.strip("/") == SUBMIT_URL.strip("/"):
        # Try to find any error messages on the page
        error_text = ""
        error_selectors = [
            ".alert-danger",
            ".error",
            ".form-error",
            ".invalid-feedback",
            '[class*="error"]',
        ]
        for selector in error_selectors:
            error_elements = page.query_selector_all(selector)
            for el in error_elements:
                text = el.inner_text().strip()
                if text and text not in error_text:
                    error_text += text + "; "

        if error_text:
            return CreatePostResult(
                success=False,
                post_url=None,
                error_message=f"Failed to create post: {error_text.strip('; ')}"
            )
        return CreatePostResult(
            success=False,
            post_url=None,
            error_message="Failed to create post - still on submit page"
        )

    # Extract post ID from URL if possible
    post_id = None
    url_parts = page.url.rstrip("/").split("/")
    if len(url_parts) > 0:
        post_id = url_parts[-1]

    return CreatePostResult(
        success=True,
        post_url=page.url,
        post_id=post_id,
        already_existed=False,
        error_message=None
    )


def create_post_with_title_and_text(
    page: Page,
    forum: str,
    title: str,
    body: str,
    username: str,
) -> CreatePostResult:
    """Convenience alias for create_post."""
    return create_post(page, forum, title, body, username)


def delete_post(page: Page, post_url: str) -> DeletePostResult:
    """
    Delete a post by its URL.

    Args:
        page: Playwright Page instance
        post_url: Full URL of the post to delete

    Returns:
        DeletePostResult with success status and any error message
    """
    page.goto(post_url, wait_until="networkidle")

    # Set up dialog handler to accept confirmation (use once to avoid multiple handlers)
    def handle_dialog(dialog):
        dialog.accept()
    page.once("dialog", handle_dialog)

    try:
        page.wait_for_selector(Selectors.DELETE_BUTTON, state="visible", timeout=2000)
        button = page.query_selector(Selectors.DELETE_BUTTON)
        if button:
            button.click()
            page.wait_for_timeout(1000)
            return DeletePostResult(success=True)
        else:
            return DeletePostResult(
                success=False,
                error_message="Delete button not found"
            )
    except TimeoutError:
        return DeletePostResult(
            success=False,
            error_message="Delete button not found or timeout"
        )
    except Exception as e:
        return DeletePostResult(
            success=False,
            error_message=f"Error deleting post: {str(e)}"
        )


def delete_post_by_url(page: Page, url: str) -> DeletePostResult:
    """Alias for delete_post."""
    return delete_post(page, url)


def delete_all_posts_by_username(
    page: Page,
    username: str,
    max_attempts: int = 5,
) -> int:
    """
    Delete all posts by a user.

    Args:
        page: Playwright Page instance
        username: Username whose posts should be deleted
        max_attempts: Maximum number of posts to attempt to delete

    Returns:
        Number of posts deleted
    """
    profile_url = get_user_profile_url(username)
    page.goto(profile_url, wait_until="networkidle")

    # Set up dialog handler to accept confirmation
    page.on("dialog", lambda dialog: dialog.accept())

    deleted_count = 0
    attempt = 0

    while attempt < max_attempts:
        try:
            page.wait_for_selector(Selectors.DELETE_BUTTON, state="visible", timeout=3000)
            button = page.query_selector(Selectors.DELETE_BUTTON)
            if not button:
                break

            button.click()
            page.wait_for_timeout(1000)
            deleted_count += 1
            attempt += 1
        except TimeoutError:
            break
        except Exception as e:
            print(f"Error during deletion: {e}")
            break

    return deleted_count


def get_posts_by_username(page: Page, username: str) -> List[Post]:
    """
    Get all posts by a user.

    Args:
        page: Playwright Page instance
        username: Username to get posts for

    Returns:
        List of Post objects
    """
    profile_url = get_user_profile_url(username)
    page.goto(profile_url, wait_until="networkidle")

    posts: List[Post] = []

    # Find all post links on the profile page
    # This is a simplified extraction - actual selectors may vary
    post_links = page.query_selector_all("article a, .post-title a, h2 a, h3 a")

    for link in post_links:
        href = link.get_attribute("href") or ""
        title = link.inner_text().strip()

        if href and title and "/f/" in href:
            # Extract subreddit and post_id from URL
            parts = href.split("/")
            subreddit = ""
            post_id = ""

            if len(parts) >= 3:
                try:
                    f_index = parts.index("f")
                    if f_index + 1 < len(parts):
                        subreddit = parts[f_index + 1]
                    if f_index + 2 < len(parts):
                        post_id = parts[f_index + 2]
                except ValueError:
                    pass

            posts.append(Post(
                id=post_id,
                title=title,
                body="",  # Would need to visit post to get body
                author=username,
                subreddit=subreddit,
                url=f"{REDDIT_DOMAIN}{href}" if not href.startswith("http") else href,
            ))

    return posts
