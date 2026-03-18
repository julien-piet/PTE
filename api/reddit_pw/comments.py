"""Reddit comment operations helpers."""

from dataclasses import dataclass
from typing import List, Optional

from playwright.sync_api import Page, TimeoutError

from .constants import (
    REDDIT_DOMAIN,
    Selectors,
    get_post_url,
)


@dataclass
class Comment:
    """Representation of a Reddit comment."""

    id: str
    body: str
    author: str
    post_id: str
    subreddit: str
    url: str


@dataclass
class CommentResult:
    """Result of attempting to post a comment."""

    success: bool
    comment_url: Optional[str]
    error_message: Optional[str] = None


@dataclass
class DeleteCommentResult:
    """Result of attempting to delete comments."""

    success: bool
    deleted_count: int = 0
    error_message: Optional[str] = None


def comment_on_post(
    page: Page,
    subreddit: str,
    post_id: str,
    comment_text: str,
) -> CommentResult:
    """
    Post a comment on a Reddit post.

    Args:
        page: Playwright Page instance
        subreddit: Name of the subreddit (e.g., "AskReddit")
        post_id: Numeric ID of the post to comment on (e.g., "2", not the slug)
        comment_text: Text content of the comment

    Returns:
        CommentResult with success status, URL, and any error message
    """
    post_url = get_post_url(subreddit, post_id)
    page.goto(post_url, wait_until="networkidle")

    # Get the dynamic comment input selector
    comment_input_selector = Selectors.get_comment_input(post_id)

    # Wait for comment form
    try:
        page.wait_for_selector(comment_input_selector, timeout=10000)
    except TimeoutError:
        return CommentResult(
            success=False,
            comment_url=None,
            error_message="Comment form not found on post"
        )

    # Fill in comment
    page.fill(comment_input_selector, comment_text)

    # Submit - using sync pattern
    page.click(Selectors.COMMENT_SUBMIT_BUTTON)
    page.wait_for_load_state("networkidle")

    # Check if we're still on the same URL (might have an anchor added)
    current_url = page.url

    # If URL changed significantly or stayed same, consider success
    # Reddit typically stays on same page after commenting
    if post_url.split("#")[0] in current_url.split("#")[0]:
        return CommentResult(
            success=True,
            comment_url=current_url,
            error_message=None
        )

    return CommentResult(
        success=False,
        comment_url=None,
        error_message=f"Comment may have failed - ended up at {current_url}"
    )


def comment_on_post_by_url(
    page: Page,
    post_url: str,
    comment_text: str,
) -> CommentResult:
    """
    Post a comment on a Reddit post using its full URL.

    Extracts the numeric post ID from the URL to build the comment selector.

    Args:
        page: Playwright Page instance
        post_url: Full URL of the post (e.g., http://localhost:9999/f/AskReddit/2/post-title)
        comment_text: Text content of the comment

    Returns:
        CommentResult with success status, URL, and any error message
    """
    page.goto(post_url, wait_until="networkidle")

    # Extract the numeric post ID from URL: /f/{subreddit}/{post_id}/...
    # URL format: http://domain/f/SubredditName/123/post-slug
    url_parts = post_url.rstrip("/").split("/")
    post_id = None

    # Find the part after /f/{subreddit}/ which is the numeric ID
    try:
        f_index = url_parts.index("f")
        if f_index + 2 < len(url_parts):
            potential_id = url_parts[f_index + 2]
            # Check if it's numeric
            if potential_id.isdigit():
                post_id = potential_id
    except (ValueError, IndexError):
        pass

    if not post_id:
        return CommentResult(
            success=False,
            comment_url=None,
            error_message=f"Could not extract post ID from URL: {post_url}"
        )

    # Get the dynamic comment input selector
    comment_input_selector = Selectors.get_comment_input(post_id)

    # Wait for comment form
    try:
        page.wait_for_selector(comment_input_selector, timeout=10000)
    except TimeoutError:
        return CommentResult(
            success=False,
            comment_url=None,
            error_message=f"Comment form not found on post (looking for {comment_input_selector})"
        )

    # Fill in comment
    page.fill(comment_input_selector, comment_text)

    # Submit - using sync pattern
    page.click(Selectors.COMMENT_SUBMIT_BUTTON)
    page.wait_for_load_state("networkidle")

    # Check if we're still on the same URL (might have an anchor added)
    current_url = page.url

    return CommentResult(
        success=True,
        comment_url=current_url,
        error_message=None
    )


def delete_all_comments_on_post(
    page: Page,
    post_url: str,
    max_attempts: int = 5,
) -> DeleteCommentResult:
    """
    Delete all comments by the current user on a specific post.

    Args:
        page: Playwright Page instance
        post_url: Full URL of the post
        max_attempts: Maximum number of comments to attempt to delete

    Returns:
        DeleteCommentResult with success status and count of deleted comments
    """
    page.goto(post_url, wait_until="networkidle")

    # Set up dialog handler to accept confirmation
    def handle_dialog(dialog):
        dialog.accept()
    page.on("dialog", handle_dialog)

    deleted_count = 0
    attempt = 0

    try:
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
                return DeleteCommentResult(
                    success=deleted_count > 0,
                    deleted_count=deleted_count,
                    error_message=f"Error after deleting {deleted_count} comments: {str(e)}"
                )

        return DeleteCommentResult(
            success=True,
            deleted_count=deleted_count,
            error_message=None if deleted_count > 0 else "No comments found to delete"
        )
    finally:
        # Remove the dialog handler to avoid conflicts with other code
        page.remove_listener("dialog", handle_dialog)


def delete_all_comments_on_post_by_user(
    page: Page,
    url: str,
    max_attempts: int = 5,
) -> DeleteCommentResult:
    """Alias for delete_all_comments_on_post for compatibility with reddit_editor.py."""
    return delete_all_comments_on_post(page, url, max_attempts)


def get_comments_on_post(
    page: Page,
    subreddit: str,
    post_id: str,
) -> List[Comment]:
    """
    Get all comments on a post.

    Args:
        page: Playwright Page instance
        subreddit: Name of the subreddit
        post_id: ID of the post

    Returns:
        List of Comment objects
    """
    post_url = get_post_url(subreddit, post_id)
    page.goto(post_url, wait_until="networkidle")

    comments: List[Comment] = []

    # Find all comment elements - selectors may vary by Reddit instance
    comment_elements = page.query_selector_all(".comment, [data-comment-id], article.comment")

    for idx, elem in enumerate(comment_elements):
        # Extract comment info
        body_elem = elem.query_selector(".comment-body, .content, p")
        body = body_elem.inner_text().strip() if body_elem else ""

        author_elem = elem.query_selector(".author, .username, a[href*='/user/']")
        author = author_elem.inner_text().strip() if author_elem else ""

        # Try to get comment ID from data attribute or generate one
        comment_id = elem.get_attribute("data-comment-id") or elem.get_attribute("id") or str(idx)

        comments.append(Comment(
            id=comment_id,
            body=body,
            author=author,
            post_id=post_id,
            subreddit=subreddit,
            url=f"{post_url}#comment-{comment_id}",
        ))

    return comments
