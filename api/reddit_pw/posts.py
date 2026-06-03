"""Reddit post management helpers."""

import re
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

from playwright.sync_api import Page, TimeoutError

from .constants import (
    REDDIT_DOMAIN,
    SUBMIT_URL,
    Selectors,
    get_user_profile_url,
    get_forum_url,
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
    score: int = 0
    link_url: Optional[str] = None


@dataclass
class VotePostResult:
    """Result of voting on a post."""

    success: bool
    error_message: Optional[str] = None


@dataclass
class EditPostResult:
    """Result of editing a post."""

    success: bool
    post_url: Optional[str] = None
    error_message: Optional[str] = None


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
    url: Optional[str] = None,
) -> CreatePostResult:
    """
    Create a new Reddit post with title and body text (or a link post with url).

    Checks if a post with the same title already exists for the user before creating.

    Args:
        page: Playwright Page instance
        forum: Forum/subreddit name to post in (e.g., "AskReddit")
        title: Title of the post
        body: Body text of the post
        username: Username creating the post (used to check for duplicates)
        url: Optional URL for link posts (image reposts, etc.)

    Returns:
        CreatePostResult with success status, URL, and any error message
    """
    # First check if a post with the same title already exists (idempotency).
    # Normalize dashes to handle EM DASH (–) vs HYPHEN (-) mismatches.
    def _norm(s: str) -> str:
        return s.replace("\u2013", "-").replace("\u2014", "-").lower().strip()

    profile_url = get_user_profile_url(username)
    page.goto(profile_url, wait_until="networkidle")

    title_norm = _norm(title)
    # Check all submission links on the profile for a title match
    for lnk in page.query_selector_all("a[href*='/f/']"):
        link_text = lnk.inner_text().strip()
        if link_text and _norm(link_text) == title_norm:
            href = lnk.get_attribute("href") or ""
            if href and "/" in href:
                existing_url = f"{REDDIT_DOMAIN}{href}"
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
    if url:
        try:
            page.fill(Selectors.POST_URL_INPUT, url)
        except Exception:
            pass
    page.fill(Selectors.POST_BODY_INPUT, body)

    # Select the forum using Select2-aware interaction.
    # The #submission_forum element is a Select2-enhanced widget (aria-hidden="true",
    # class="select2-hidden-accessible"), so Playwright's select_option() cannot find
    # options by label.  Instead we interact with Select2's custom UI:
    #   1. Click the visible Select2 container to open the dropdown.
    #   2. Type the forum name into the search input.
    #   3. Click the matching result in the dropdown list.
    # If that fails for any reason we fall back to the native select_option() call.
    # Strip any "r/" prefix the planner may add (e.g. "r/books" -> "books")
    forum_clean = forum.lstrip("r/").strip() if forum else forum
    try:
        # The Select2 visible widget is a sibling/cousin of the hidden <select>.
        # Clicking the container opens the dropdown search box.
        page.locator(".select2-container").first.click(timeout=3000)
        page.wait_for_timeout(300)  # give Select2 time to open
        # Type into the search field (Select2 injects this into the body)
        search_input = page.locator(".select2-search__field, .select2-search--dropdown input")
        search_input.last.fill(forum_clean, timeout=3000)
        page.wait_for_timeout(500)  # wait for results to filter
        # Click the first matching result
        page.locator(f".select2-results__option:has-text('{forum_clean}')").first.click(timeout=5000)
        # Close the Select2 dropdown so it no longer intercepts pointer events.
        # Without this, the open search overlay blocks the "Create submission" button.
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
    except Exception:
        # Always close any open Select2 dropdown before proceeding,
        # otherwise it will intercept pointer events on the submit button.
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
        except Exception:
            pass
        # Fallback: try the native select_option (works if Select2 is not active)
        try:
            page.select_option(Selectors.POST_FORUM_SELECT, label=forum_clean, timeout=5000)
        except Exception:
            pass  # best-effort — let submit proceed and detect failure via URL check

    # Ensure Select2 dropdown is closed before submitting.
    # Press Escape one more time and click somewhere neutral (the title field)
    # to guarantee any open dropdown overlay is dismissed.
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
        # Click the title field to move focus away from Select2
        page.click(Selectors.POST_TITLE_INPUT, timeout=2000)
        page.wait_for_timeout(150)
    except Exception:
        pass

    # Submit - use force=True as a last resort if the dropdown still intercepts
    try:
        page.click(Selectors.POST_SUBMIT_BUTTON, timeout=5000)
    except Exception:
        # If normal click fails (overlay still blocking), force the click
        try:
            page.locator(Selectors.POST_SUBMIT_BUTTON).dispatch_event("click")
        except Exception:
            pass
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


def vote_post(page: Page, post_url: str, direction: str) -> VotePostResult:
    """
    Vote on a submission (upvote or downvote).

    Args:
        page: Playwright Page instance
        post_url: Full URL of the post
        direction: "up" or "1" to upvote, "down" or "-1" to downvote

    Returns:
        VotePostResult with success status
    """
    is_up = direction in ("up", "1", 1)
    selector = "button.vote__up" if is_up else "button.vote__down"

    try:
        page.goto(post_url, wait_until="networkidle")
        page.wait_for_selector(selector, timeout=5000)
        page.click(selector, timeout=5000)
        page.wait_for_load_state("networkidle")
        return VotePostResult(success=True)
    except TimeoutError:
        return VotePostResult(success=False, error_message=f"Vote button '{selector}' not found on {post_url}")
    except Exception as e:
        return VotePostResult(success=False, error_message=str(e))


def edit_post(
    page: Page,
    post_url: str,
    new_body: Optional[str] = None,
    new_title: Optional[str] = None,
    append: bool = False,
) -> EditPostResult:
    """
    Edit a post's body.

    Args:
        page: Playwright Page instance
        post_url: Full URL of the post (e.g. http://host/f/books/59421/slug)
        new_body: Body text to set. Replaces the existing body unless append=True.
        new_title: Ignored — Postmill does not allow title edits after posting.
        append: If True, new_body is appended to the existing body; if False (default), replaces it.

    Returns:
        EditPostResult with success status and post URL
    """
    m = re.search(r'/f/([^/]+)/(\d+)', post_url)
    if not m:
        return EditPostResult(success=False, error_message=f"Cannot parse forum/post_id from URL: {post_url}")

    forum, post_id = m.group(1), m.group(2)
    edit_url = f"{REDDIT_DOMAIN}/f/{forum}/{post_id}/-/edit"
    response = page.goto(edit_url, wait_until="domcontentloaded")

    if response and response.status == 403:
        return EditPostResult(success=False, error_message="Access denied: you can only edit your own posts")

    if "/edit" not in page.url:
        return EditPostResult(success=False, error_message=f"Edit page not accessible (redirected to {page.url})")

    try:
        page.wait_for_selector(Selectors.POST_BODY_INPUT, timeout=5000)
    except TimeoutError:
        return EditPostResult(success=False, error_message="Edit form not found")

    if new_body is not None:
        if append:
            existing_body = page.input_value(Selectors.POST_BODY_INPUT)
            body_to_write = (existing_body + "\n\n" + new_body) if existing_body.strip() else new_body
        else:
            body_to_write = new_body
        page.fill(Selectors.POST_BODY_INPUT, body_to_write)

    page.click(Selectors.EDIT_POST_SUBMIT_BUTTON)
    page.wait_for_load_state("domcontentloaded")

    if "/edit" in page.url:
        return EditPostResult(success=False, error_message="Still on edit page after submit — validation may have failed")

    return EditPostResult(success=True, post_url=page.url)


def get_post(page: Page, forum: str, post_id: str) -> Optional[Post]:
    """
    Fetch a single post by forum name and post ID.

    Args:
        page: Playwright Page instance
        forum: Forum/subreddit name (e.g. "MachineLearning")
        post_id: Numeric post ID (from the post URL: /f/{forum}/{post_id}/...)

    Returns:
        Post object, or None if the post doesn't exist or is inaccessible
    """
    url = f"{REDDIT_DOMAIN}/f/{forum}/{post_id}"
    page.goto(url, wait_until="networkidle")

    article = page.query_selector("article.submission")
    if not article:
        return None

    title_el = article.query_selector("h1.submission__title a")
    title = title_el.inner_text().strip() if title_el else ""
    title_href = (title_el.get_attribute("href") or "") if title_el else ""

    # Determine full URL and link_url (link posts have external href on submission__link)
    link_el = article.query_selector("a.submission__link")
    link_href = (link_el.get_attribute("href") or "") if link_el else ""
    if link_href.startswith("http") and not link_href.startswith(REDDIT_DOMAIN):
        link_url = link_href
        post_url = f"{REDDIT_DOMAIN}{title_href}" if title_href.startswith("/") else page.url
    else:
        link_url = None
        post_url = f"{REDDIT_DOMAIN}{title_href}" if title_href.startswith("/") else page.url

    author_el = article.query_selector("a.submission__submitter strong")
    author = author_el.inner_text().strip() if author_el else ""

    forum_el = article.query_selector("a.submission__forum strong")
    subreddit = forum_el.inner_text().strip() if forum_el else forum

    body_el = article.query_selector(".submission__body")
    body = body_el.inner_text().strip() if body_el else ""

    vote_form = article.query_selector("form.vote")
    score_str = (vote_form.get_attribute("data-vote-score-value") or "0") if vote_form else "0"
    try:
        score = int(score_str)
    except ValueError:
        score = 0

    return Post(
        id=post_id,
        title=title,
        body=body,
        author=author,
        subreddit=subreddit,
        url=post_url,
        link_url=link_url,
        score=score,
    )


def search_posts(
    page: Page,
    query: str,
    limit: int = 25,
) -> List[Post]:
    """
    Full-text search across all posts (titles, bodies) using the site's search page.

    Args:
        page: Playwright Page instance
        query: Search query string
        limit: Maximum number of results to return (default: 25)

    Returns:
        List of Post objects matching the query
    """
    from urllib.parse import quote_plus
    url = f"{REDDIT_DOMAIN}/search?q={quote_plus(query)}"
    page.goto(url, wait_until="domcontentloaded")

    posts: List[Post] = []
    articles = page.query_selector_all("article.submission")

    for article in articles:
        if len(posts) >= limit:
            break

        title_link = article.query_selector("a.submission__link")
        if not title_link:
            continue

        # Replace <mark> highlight tags with spaces before stripping so adjacent
        # highlighted words (e.g. <mark>bald</mark><mark>eagle</mark>) don't merge
        raw_html = title_link.inner_html()
        raw_html = re.sub(r'<mark[^>]*>', ' ', raw_html)   # space before each highlighted word
        raw_html = re.sub(r'</mark>', '', raw_html)         # closing tag needs no space
        title = re.sub(r'<[^>]+>', '', raw_html)
        title = re.sub(r'\s+', ' ', title).strip()
        title_href = title_link.get_attribute("href") or ""
        if not title_href:
            continue

        postmill_url = None
        link_url = None
        comments_link = article.query_selector("nav.submission__nav a[href*='/f/']")
        if comments_link:
            comments_href = comments_link.get_attribute("href") or ""
            postmill_url = comments_href if comments_href.startswith("http") else f"{REDDIT_DOMAIN}{comments_href}"

        if title_href.startswith("http") and postmill_url:
            link_url = title_href
        elif title_href.startswith("/f/"):
            postmill_url = postmill_url or f"{REDDIT_DOMAIN}{title_href}"
        else:
            postmill_url = postmill_url or (title_href if title_href.startswith("http") else f"{REDDIT_DOMAIN}{title_href}")

        pm = re.search(r'/f/([^/]+)/(\d+)', postmill_url or "")
        if pm:
            post_id = pm.group(2)
            subreddit = pm.group(1)
        else:
            vote_form_action = article.query_selector("form[action^='/sv/']")
            action = vote_form_action.get_attribute("action") if vote_form_action else ""
            id_m = re.search(r'/sv/(\d+)', action or "")
            post_id = id_m.group(1) if id_m else ""
            subreddit = ""

        author_el = article.query_selector("a.submission__submitter strong")
        author = author_el.inner_text().strip() if author_el else ""

        body_el = article.query_selector(".submission__body")
        body = body_el.inner_text().strip() if body_el else ""

        vote_form = article.query_selector("form.vote[data-vote-route-value='submission_vote']")
        score_str = vote_form.get_attribute("data-vote-score-value") if vote_form else "0"
        try:
            score = int(score_str or 0)
        except ValueError:
            score = 0

        posts.append(Post(
            id=post_id,
            title=title,
            body=body,
            author=author,
            subreddit=subreddit,
            url=postmill_url or "",
            link_url=link_url,
            score=score,
        ))

    return posts


def get_forum_posts(
    page: Page,
    forum_name: str,
    sort: str = "hot",
    limit: int = 25,
) -> List[Post]:
    """
    Get posts from a forum, optionally sorted.

    Args:
        page: Playwright Page instance
        forum_name: Name of the forum (e.g. "books")
        sort: Sort order — "hot", "new", "top", "controversial", "active" (default: "hot")
        limit: Maximum number of posts to return (default: 25)

    Returns:
        List of Post objects (up to limit)
    """
    sort_map = {"hot": "", "new": "/new", "top": "/top", "controversial": "/controversial", "active": "/active"}
    suffix = sort_map.get(sort.lower(), f"/{sort}")
    url = f"{REDDIT_DOMAIN}/f/{forum_name}{suffix}"
    page.goto(url, wait_until="networkidle")

    posts: List[Post] = []
    articles = page.query_selector_all("article.submission")

    for article in articles:
        if len(posts) >= limit:
            break

        title_link = article.query_selector("a.submission__link")
        if not title_link:
            continue

        title = title_link.inner_text().strip()
        title_href = title_link.get_attribute("href") or ""
        if not title_href:
            continue

        # The Postmill submission URL is in the comments nav link (/f/{forum}/{id}/slug).
        # For link posts, submission__link points to the external URL — use the comments
        # link as the canonical Postmill URL and store the external URL as link_url.
        postmill_url = None
        link_url = None
        comments_link = article.query_selector("nav.submission__nav a[href*='/f/']")
        if comments_link:
            comments_href = comments_link.get_attribute("href") or ""
            postmill_url = comments_href if comments_href.startswith("http") else f"{REDDIT_DOMAIN}{comments_href}"

        if title_href.startswith("http") and postmill_url:
            # Link post: external URL is the link, comments link is the Postmill URL
            link_url = title_href
        elif title_href.startswith("/f/"):
            # Text post: submission__link IS the Postmill URL
            postmill_url = postmill_url or f"{REDDIT_DOMAIN}{title_href}"
        else:
            postmill_url = postmill_url or (title_href if title_href.startswith("http") else f"{REDDIT_DOMAIN}{title_href}")

        # Extract post_id from the Postmill URL (or vote form action /sv/{id} as fallback)
        pm = re.search(r'/f/([^/]+)/(\d+)', postmill_url or "")
        if pm:
            post_id = pm.group(2)
            subreddit = pm.group(1)
        else:
            vote_form_action = article.query_selector("form[action^='/sv/']")
            action = vote_form_action.get_attribute("action") if vote_form_action else ""
            id_m = re.search(r'/sv/(\d+)', action or "")
            post_id = id_m.group(1) if id_m else ""
            subreddit = forum_name

        # Author
        author_el = article.query_selector("a.submission__submitter strong")
        author = author_el.inner_text().strip() if author_el else ""

        # Body (text posts only — link posts have no body)
        body_el = article.query_selector(".submission__body")
        body = body_el.inner_text().strip() if body_el else ""

        # Score from vote form data attribute
        vote_form = article.query_selector("form.vote[data-vote-route-value='submission_vote']")
        score_str = vote_form.get_attribute("data-vote-score-value") if vote_form else "0"
        try:
            score = int(score_str or 0)
        except ValueError:
            score = 0

        # Timestamp
        time_el = article.query_selector("time[datetime]")
        created_at = None
        if time_el:
            dt_str = time_el.get_attribute("datetime") or ""
            try:
                from datetime import timezone
                created_at = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except Exception:
                pass

        posts.append(Post(
            id=post_id,
            title=title,
            body=body,
            author=author,
            subreddit=subreddit,
            url=postmill_url or "",
            link_url=link_url,
            created_at=created_at,
            score=score,
        ))

    return posts


def get_posts_by_username(page: Page, username: str, limit: int = 50) -> List[Post]:
    """
    Get submissions by a user from their /submissions profile page.

    Args:
        page: Playwright Page instance
        username: Username to get posts for
        limit: Max posts to return (default 50)

    Returns:
        List of Post objects
    """
    url = f"{REDDIT_DOMAIN}/user/{username}/submissions"
    page.goto(url, wait_until="networkidle")

    posts: List[Post] = []
    articles = page.query_selector_all("article.submission")

    for article in articles:
        if len(posts) >= limit:
            break

        title_link = article.query_selector("a.submission__link")
        if not title_link:
            continue

        title = title_link.inner_text().strip()
        title_href = title_link.get_attribute("href") or ""
        if not title_href:
            continue

        postmill_url = None
        link_url = None
        comments_link = article.query_selector("nav.submission__nav a[href*='/f/']")
        if comments_link:
            comments_href = comments_link.get_attribute("href") or ""
            postmill_url = comments_href if comments_href.startswith("http") else f"{REDDIT_DOMAIN}{comments_href}"

        if title_href.startswith("http") and postmill_url:
            link_url = title_href
        elif title_href.startswith("/f/"):
            postmill_url = postmill_url or f"{REDDIT_DOMAIN}{title_href}"
        else:
            postmill_url = postmill_url or (title_href if title_href.startswith("http") else f"{REDDIT_DOMAIN}{title_href}")

        pm = re.search(r'/f/([^/]+)/(\d+)', postmill_url or "")
        if pm:
            post_id = pm.group(2)
            subreddit = pm.group(1)
        else:
            vote_form_action = article.query_selector("form[action^='/sv/']")
            action = vote_form_action.get_attribute("action") if vote_form_action else ""
            id_m = re.search(r'/sv/(\d+)', action or "")
            post_id = id_m.group(1) if id_m else ""
            subreddit = ""

        body_el = article.query_selector(".submission__body")
        body = body_el.inner_text().strip() if body_el else ""

        vote_form = article.query_selector("form.vote[data-vote-route-value='submission_vote']")
        score_str = vote_form.get_attribute("data-vote-score-value") if vote_form else "0"
        try:
            score = int(score_str or 0)
        except ValueError:
            score = 0

        time_el = article.query_selector("time[datetime]")
        created_at = None
        if time_el:
            dt_str = time_el.get_attribute("datetime") or ""
            try:
                from datetime import timezone
                created_at = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except Exception:
                pass

        posts.append(Post(
            id=post_id,
            title=title,
            body=body,
            author=username,
            subreddit=subreddit,
            url=postmill_url or "",
            link_url=link_url,
            created_at=created_at,
            score=score,
        ))

    return posts
