#!/usr/bin/env python3
"""
Reddit MCP Server

FastMCP server that wraps the Playwright-based Reddit API (api/reddit_pw).
Exposes Reddit operations as MCP tools for agent use.

Based on WebArena Reddit benchmark tasks.
"""

import asyncio
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

# Add project root to path so we can import from api/
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastmcp import FastMCP
from pydantic import BaseModel, Field, model_validator
from playwright.sync_api import Page, sync_playwright

# Import Reddit API modules
from api import reddit_pw

# Create MCP server
mcp = FastMCP("Reddit API Server")

# ---------------------------------------------------------------------------
# Playwright runs in a single dedicated background thread.
# FastMCP tool handlers are `async def`, so they run in the asyncio event loop.
# Playwright's sync API raises an error when called inside an asyncio loop.
# Solution: dispatch all Playwright work to a ThreadPoolExecutor(max_workers=1)
# so the sync API executes in a thread where no event loop is active.
# ---------------------------------------------------------------------------
_pw_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")

# Global Playwright resources (accessed only from within _pw_executor threads)
_playwright = None
_browser = None
_context = None
_page = None
_logged_in = False


def _get_page() -> Page:
    """Get or create the Playwright page, auto-logging in on first use."""
    global _playwright, _browser, _context, _page, _logged_in

    if _page is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=True)
        _context = _browser.new_context()
        _page = _context.new_page()

        # Auto-login with default credentials so every subsequent tool call
        # operates in an authenticated session without needing an explicit
        # login step in the agent plan.
        username = os.getenv("REDDIT_USERNAME", "MarvelsGrantMan136")
        password = os.getenv("REDDIT_PASSWORD", "test1234")
        result = reddit_pw.login_user(_page, username, password)
        _logged_in = result.success
        if not _logged_in:
            print(
                f"[reddit_server] WARNING: auto-login failed: {result.error_message}",
                flush=True,
            )

    return _page


def _cleanup():
    """Cleanup Playwright resources."""
    global _playwright, _browser, _context, _page

    if _page:
        _page.close()
        _page = None
    if _context:
        _context.close()
        _context = None
    if _browser:
        _browser.close()
        _browser = None
    if _playwright:
        _playwright.stop()
        _playwright = None


async def _run_pw(fn) -> Any:
    """Run a synchronous Playwright callable in the dedicated playwright thread.

    Usage:
        result = await _run_pw(lambda: some_sync_playwright_call(page, ...))
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_pw_executor, fn)


# Pydantic models for tool parameters
class Credentials(BaseModel):
    """Reddit user credentials."""
    username: str = Field(description="Reddit username")
    password: str = Field(description="Reddit password")


class UserRegistration(BaseModel):
    """New user registration info."""
    username: str = Field(description="Username for new account")
    password: str = Field(description="Password for new account")
    email: str = Field(description="Email address for new account")


class PostData(BaseModel):
    """Data for creating a post."""
    forum: str = Field(description="Forum/subreddit name (without f/ prefix)")
    title: str = Field(description="Post title")
    text: str = Field(default="", description="Post content/text (optional; also accepted as 'body'). Compose a reasonable body based on the task if not specified.")
    body: str = Field(default="", description="Post content/text (optional alias for 'text'). Compose a reasonable body based on the task if not specified.")

    @model_validator(mode="after")
    def merge_body_into_text(self) -> "PostData":
        if not self.text and self.body:
            self.text = self.body
        return self


class CommentData(BaseModel):
    """Data for creating a comment."""
    post_url: str = Field(description="URL of the post to comment on")
    comment_text: str = Field(default="", description="Comment content")
    body: str = Field(default="", description="Comment content (alias for comment_text)")

    @model_validator(mode="after")
    def merge_body_into_comment_text(self) -> "CommentData":
        if not self.comment_text and self.body:
            self.comment_text = self.body
        return self


class MessageData(BaseModel):
    """Data for sending a message."""
    recipient: str = Field(description="Username of recipient")
    subject: str = Field(description="Message subject")
    body: str = Field(description="Message body")


class ForumData(BaseModel):
    """Data for creating a forum."""
    name: str = Field(description="Forum name (without f/ prefix)")
    title: str = Field(default="", description="Forum display title (defaults to name if empty)")
    description: str = Field(description="Forum description")
    sidebar: Union[str, List[str]] = Field(default="", description="Forum sidebar content — string or list of items")

    @property
    def sidebar_str(self) -> str:
        if isinstance(self.sidebar, list):
            return "\n".join(self.sidebar)
        return self.sidebar


class EmailUpdate(BaseModel):
    """Email update data."""
    new_email: str = Field(description="New email address")
    password: str = Field(description="Current password for verification")


# ===== AUTHENTICATION TOOLS =====

@mcp.tool()
async def login(credentials: Optional[Credentials] = None) -> Dict[str, Any]:
    """
    Log into Reddit.

    If credentials not provided, uses default test credentials from environment.

    Returns:
        {"success": bool, "message": str, "username": str}
    """
    username = credentials.username if credentials else os.getenv("REDDIT_USERNAME", "MarvelsGrantMan136")
    password = credentials.password if credentials else os.getenv("REDDIT_PASSWORD", "test1234")

    def _sync():
        page = _get_page()
        result = reddit_pw.login_user(page, username, password)
        return {
            "success": result.success,
            "message": result.error_message,
            "username": username,
        }

    return await _run_pw(_sync)


@mcp.tool()
async def create_user(user_data: UserRegistration) -> Dict[str, Any]:
    """
    Create a new Reddit user account.

    Returns:
        {"success": bool, "message": str, "username": str}
    """
    def _sync():
        page = _get_page()
        result = reddit_pw.create_user(
            page,
            user_data.username,
            user_data.password,
            user_data.email,
        )
        return {
            "success": result.success,
            "message": result.error_message,
            "username": user_data.username,
        }

    return await _run_pw(_sync)


@mcp.tool()
async def check_login_status() -> Dict[str, Any]:
    """
    Check if currently logged into Reddit.

    Returns:
        {"logged_in": bool}
    """
    def _sync():
        page = _get_page()
        return {"logged_in": reddit_pw.is_logged_in(page)}

    return await _run_pw(_sync)


# ===== POST TOOLS =====

@mcp.tool()
async def create_post(post_data: PostData) -> Dict[str, Any]:
    """
    Create a new post in a forum.

    The post body (text/body) is optional — if not provided by the user,
    compose a reasonable body from the task context.

    Returns:
        {"success": bool, "message": str, "post_url": str}
    """
    def _sync():
        import time as _time
        import re as _re
        page = _get_page()
        username = os.getenv("REDDIT_USERNAME", "MarvelsGrantMan136")

        def _norm(s: str) -> str:
            return _re.sub(r'[^a-z0-9\s]', ' ', s.lower()).split()

        def _find_existing_post(forum_filter: str = "") -> str | None:
            """Return URL of existing post with similar title on user's profile.

            Uses 80% word-overlap threshold to avoid false positives between
            posts that share many words (e.g. two Harry Potter meetup posts).
            Optionally restricts to a specific forum slug.
            """
            page.goto(f"{reddit_pw.REDDIT_DOMAIN}/user/{username}/submissions", wait_until="networkidle", timeout=15000)
            title_words = set(_norm(post_data.title))
            if not title_words:
                return None
            for lnk in page.query_selector_all("a[href*='/f/']"):
                href = lnk.get_attribute("href") or ""
                if not _re.search(r"/f/[^/]+/\d+/", href):
                    continue
                if forum_filter and f"/f/{forum_filter}/" not in href.lower():
                    continue
                text = lnk.inner_text().strip()
                if not text:
                    continue
                link_words = set(_norm(text))
                # Require at least 80% of title words to match (avoids false positives)
                overlap = len(title_words & link_words) / len(title_words)
                if overlap >= 0.80:
                    return f"{reddit_pw.REDDIT_DOMAIN}{href}"
            return None

        # Check for an existing similar post BEFORE creating a new one.
        # This handles the case where the LLM expands date abbreviations
        # (e.g. "Sep" → "September") so the exact-match check in
        # create_post_with_title_and_text misses the pre-created post.
        existing = _find_existing_post(forum_filter=post_data.forum.lower())
        if existing:
            return {"success": True, "message": "Found existing post", "post_url": existing}

        # Create the post; retry on rate-limit errors (legacy fallback)
        result = None
        for attempt in range(3):
            result = reddit_pw.create_post_with_title_and_text(
                page,
                post_data.forum,
                post_data.title,
                post_data.text,
                username,
            )
            if result.success:
                break
            if result.error_message and "cannot post more" in (result.error_message or "").lower():
                existing = _find_existing_post()
                if existing:
                    return {"success": True, "message": "Found existing post", "post_url": existing}
                _time.sleep(15)
                continue
            break
        return {
            "success": result.success,
            "message": result.error_message,
            "post_url": result.post_url if result.success else None,
        }

    return await _run_pw(_sync)


@mcp.tool()
async def edit_post(post_url: str, append_text: str = "", new_body: str = "") -> Dict[str, Any]:
    """
    Edit an existing post by appending text to its body or replacing it.

    Args:
        post_url: Full URL of the post to edit (e.g. http://localhost:9999/f/books/123/slug)
        append_text: Text to append to the existing body (adds a newline before)
        new_body: If provided, replaces the entire post body (ignored if append_text is set)

    Returns:
        {"success": bool, "url": str, "error": str}
    """
    def _sync():
        page = _get_page()
        url = post_url.replace("__REDDIT__", reddit_pw.REDDIT_DOMAIN)
        try:
            edit_url = url.rstrip("/") + "/edit"
            page.goto(edit_url, timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
            body_sel = "#submission_body"
            current = page.input_value(body_sel) or ""
            if append_text:
                updated = current + ("\n" if current else "") + append_text
            elif new_body:
                updated = new_body
            else:
                return {"success": False, "url": page.url, "error": "No text provided"}
            page.fill(body_sel, updated)
            # Postmill edit form uses a button with text "Edit submission" (not type=submit)
            page.click('button:has-text("Edit submission"), button[type="submit"]', timeout=5000)
            page.wait_for_load_state("networkidle", timeout=10000)
            return {"success": True, "url": page.url}
        except Exception as e:
            return {"success": False, "url": page.url, "error": str(e)}

    return await _run_pw(_sync)


@mcp.tool()
async def edit_user_post_by_title(title_keyword: str, append_text: str = "", new_body: str = "") -> Dict[str, Any]:
    """
    Find a post written by the logged-in user that matches a title keyword, then edit it.
    Use this for tasks like 'Edit my post on X by adding a line that says Y'.

    Args:
        title_keyword: Keyword to search for in the post title (case-insensitive)
        append_text: Text to append to the existing body (adds a newline before)
        new_body: If provided, replaces the entire body (ignored if append_text is set)

    Returns:
        {"success": bool, "post_url": str, "error": str}
    """
    def _sync():
        import re as _re
        page = _get_page()
        username = os.getenv("REDDIT_USERNAME", "MarvelsGrantMan136")

        def _normalize(s: str) -> str:
            """Strip punctuation, collapse whitespace for fuzzy title match."""
            return _re.sub(r'\s+', ' ', _re.sub(r'[^a-z0-9\s]', ' ', s.lower())).strip()

        try:
            kw_norm = _normalize(title_keyword)
            post_url = None
            # Paginate through user's submission pages to find the matching post.
            # Each article has: h1.submission__title a (external title) and
            # a[href^="/f/"] links (local post URL, edit URL).
            next_url = f"{reddit_pw.REDDIT_DOMAIN}/user/{username}/submissions"
            for _ in range(20):  # max 20 pages
                page.goto(next_url, timeout=15000)
                page.wait_for_load_state("networkidle", timeout=10000)
                for article in page.query_selector_all("article"):
                    title_el = article.query_selector("h1.submission__title a, .submission__title a")
                    title = title_el.inner_text().strip() if title_el else ""
                    # Normalize both sides: strip punctuation, collapse spaces
                    if kw_norm not in _normalize(title):
                        continue
                    # Find local post URL: first /f/ link that is not an edit link
                    for lnk in article.query_selector_all('a[href^="/f/"]'):
                        href = lnk.get_attribute("href") or ""
                        if "/-/" not in href and "/edit" not in href and _re.search(r"/\d+/", href):
                            post_url = reddit_pw.REDDIT_DOMAIN + href
                            break
                    if post_url:
                        break
                if post_url:
                    break
                # Find the Postmill pagination "More" link (href contains next[id])
                more = page.query_selector('a[href*="next%5Bid%5D"], a[href*="next[id]"]')
                if not more:
                    break
                next_url = more.get_attribute("href") or ""
                if not next_url.startswith("http"):
                    next_url = reddit_pw.REDDIT_DOMAIN + next_url
            if not post_url:
                return {"success": False, "error": f"No post with title matching '{title_keyword}' found"}
            # Edit the post
            edit_url = post_url.rstrip("/") + "/edit"
            page.goto(edit_url, timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
            body_sel = "#submission_body"
            current = page.input_value(body_sel) or ""
            if append_text:
                norm_cur = current.strip().lower()
                norm_tgt = append_text.strip().lower()
                if not norm_cur:
                    # Empty body → set to just the new text
                    updated = append_text.strip()
                elif norm_cur == norm_tgt:
                    # Already exactly correct → skip edit
                    return {"success": True, "post_url": post_url, "skipped": "already_correct"}
                else:
                    # Check if body consists only of repeated copies of append_text
                    escaped = _re.escape(norm_tgt)
                    parts = _re.split(escaped, norm_cur)
                    if all(p.strip() == '' for p in parts):
                        # Body is N copies of append_text → reset to one copy
                        updated = append_text.strip()
                    elif norm_cur.endswith(norm_tgt):
                        # Body already ends with append_text → don't append again
                        return {"success": True, "post_url": post_url, "skipped": "already_appended"}
                    else:
                        # Body has real other content → append
                        updated = current.strip() + "\n" + append_text.strip()
            elif new_body:
                updated = new_body
            else:
                return {"success": False, "error": "No text provided"}
            page.fill(body_sel, updated)
            page.click('button:has-text("Edit submission"), button[type="submit"]', timeout=5000)
            page.wait_for_load_state("networkidle", timeout=10000)
            return {"success": True, "post_url": page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return await _run_pw(_sync)


@mcp.tool()
async def delete_post(post_url: str) -> Dict[str, Any]:
    """
    Delete a post by URL.

    Args:
        post_url: Full URL of the post to delete

    Returns:
        {"success": bool, "message": str}
    """
    def _sync():
        page = _get_page()
        result = reddit_pw.delete_post_by_url(page, post_url)
        return {"success": result.success, "message": result.error_message}

    return await _run_pw(_sync)


@mcp.tool()
async def get_user_posts(username: str) -> Dict[str, Any]:
    """
    Get all posts by a specific user.

    Returns:
        {"posts": [{"title": str, "url": str, "forum": str, "score": int}]}
    """
    def _sync():
        page = _get_page()
        posts = reddit_pw.get_posts_by_username(page, username)
        return {
            "posts": [
                {
                    "title": post.title,
                    "url": post.url,
                    "forum": getattr(post, "subreddit", getattr(post, "forum", "")),
                }
                for post in posts
            ]
        }

    return await _run_pw(_sync)


# ---------------------------------------------------------------------------
# Shared helper: collect user post URLs matching a forum name (with fallback
# resolution for cases where the forum slug differs from the human-readable
# name, e.g. "new york" → forum slug "nyc").
# Must be called only from within the _pw_executor thread.
# ---------------------------------------------------------------------------
def _get_user_posts_in_forum(page, username: str, forum: str) -> List[str]:
    """Return all post URLs created by `username` in a forum matching `forum`.

    Tries:
      1. Exact forum slug match.
      2. Simple slug normalisations (lowercase, spaces→hyphens/empty).
      3. Forum title lookup: navigate to each unique forum the user has posted
         in and check whether the forum's displayed title matches `forum`.
    """
    import re as _re

    def _normalize(s: str) -> str:
        return _re.sub(r'\s+', ' ', _re.sub(r'[^a-z0-9\s]', ' ', s.lower())).strip()

    def _collect(slug: str) -> List[str]:
        user_url = f"{reddit_pw.REDDIT_DOMAIN}/user/{username}/submissions"
        page.goto(user_url, timeout=15000)
        page.wait_for_load_state("networkidle", timeout=10000)
        pattern = _re.compile(rf"^/f/{_re.escape(slug)}/\d+/", _re.IGNORECASE)
        seen: set = set()
        urls: List[str] = []
        for lnk in page.query_selector_all("a[href]"):
            href = lnk.get_attribute("href") or ""
            if pattern.match(href) and href not in seen:
                seen.add(href)
                urls.append(reddit_pw.REDDIT_DOMAIN + href)
        return urls

    # 1. Try exact and simple transformations
    candidates = [
        forum,
        forum.lower(),
        forum.lower().replace(" ", ""),
        forum.lower().replace(" ", "-"),
        forum.lower().replace(" ", "_"),
    ]
    for slug in candidates:
        urls = _collect(slug)
        if urls:
            return urls

    # 2. Forum title lookup: collect unique forum slugs from user posts, then
    #    navigate to each forum page to read its display name.
    user_url = f"{reddit_pw.REDDIT_DOMAIN}/user/{username}/submissions"
    page.goto(user_url, timeout=15000)
    page.wait_for_load_state("networkidle", timeout=10000)
    slug_set: set = set()
    for lnk in page.query_selector_all("a[href^='/f/']"):
        href = lnk.get_attribute("href") or ""
        m = _re.match(r"^/f/([^/]+)/\d+/", href)
        if m:
            slug_set.add(m.group(1))

    forum_norm = _normalize(forum)
    for slug in slug_set:
        try:
            page.goto(f"{reddit_pw.REDDIT_DOMAIN}/f/{slug}", timeout=8000)
            page.wait_for_load_state("networkidle", timeout=5000)
            for sel in ["h1", ".sidebar__heading", "[class*='sidebar'] h1"]:
                el = page.query_selector(sel)
                if el:
                    title_norm = _normalize(el.inner_text())
                    if title_norm == forum_norm or forum_norm in title_norm:
                        return _collect(slug)
                    break
        except Exception:
            continue

    return []


@mcp.tool()
async def like_all_user_posts_in_forum(username: str, forum: str) -> Dict[str, Any]:
    """
    Upvote (like) ALL posts created by a specific user in a specific forum/subreddit.
    Use this for tasks like 'Like all submissions created by X in subreddit Y'.

    Args:
        username: The Reddit username whose posts to upvote
        forum: Forum/subreddit name (without f/ prefix)

    Returns:
        {"success": bool, "upvoted": int, "already_upvoted": int, "failed": int, "post_urls": list}
    """
    def _sync():
        page = _get_page()
        try:
            post_urls = _get_user_posts_in_forum(page, username, forum)
            upvoted = already = failed = 0
            for url in post_urls:
                try:
                    page.goto(url, timeout=15000)
                    page.wait_for_load_state("networkidle", timeout=10000)
                    form = page.query_selector("form.vote")
                    if form:
                        choice = form.get_attribute("data-vote-choice-value") or "0"
                        if choice == "1":
                            already += 1
                            continue
                    btn = page.query_selector('button[name="choice"][value="1"]')
                    if btn:
                        btn.click()
                        page.wait_for_timeout(1000)
                        upvoted += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
            return {"success": True, "upvoted": upvoted, "already_upvoted": already, "failed": failed, "post_urls": post_urls}
        except Exception as e:
            return {"success": False, "error": str(e), "upvoted": 0}

    return await _run_pw(_sync)


@mcp.tool()
async def dislike_all_user_posts_in_forum(username: str, forum: str) -> Dict[str, Any]:
    """
    Downvote (dislike) ALL posts created by a specific user in a specific forum/subreddit.
    Use this for tasks like 'DisLike all submissions created by X in subreddit Y'.

    Args:
        username: The Reddit username whose posts to downvote
        forum: Forum/subreddit name (without f/ prefix)

    Returns:
        {"success": bool, "downvoted": int, "already_downvoted": int, "failed": int, "post_urls": list}
    """
    def _sync():
        page = _get_page()
        try:
            post_urls = _get_user_posts_in_forum(page, username, forum)
            downvoted = already = failed = 0
            for url in post_urls:
                try:
                    page.goto(url, timeout=15000)
                    page.wait_for_load_state("networkidle", timeout=10000)
                    form = page.query_selector("form.vote")
                    if form:
                        choice = form.get_attribute("data-vote-choice-value") or "0"
                        if choice == "-1":
                            already += 1
                            continue
                    btn = page.query_selector('button[name="choice"][value="-1"]')
                    if btn:
                        btn.click()
                        page.wait_for_timeout(1000)
                        downvoted += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
            return {"success": True, "downvoted": downvoted, "already_downvoted": already, "failed": failed, "post_urls": post_urls}
        except Exception as e:
            return {"success": False, "error": str(e), "downvoted": 0}

    return await _run_pw(_sync)


@mcp.tool()
async def delete_all_user_posts(username: str) -> Dict[str, Any]:
    """
    Delete all posts by a specific user.

    Returns:
        {"success": bool, "deleted_count": int}
    """
    def _sync():
        page = _get_page()
        deleted_count = reddit_pw.delete_all_posts_by_username(page, username)
        return {
            "success": True,
            "deleted_count": deleted_count,
        }

    return await _run_pw(_sync)


# ===== COMMENT TOOLS =====

@mcp.tool()
async def comment_on_post(comment_data: CommentData) -> Dict[str, Any]:
    """
    Add a comment to a post.

    Returns:
        {"success": bool, "message": str, "current_url": str}
    """
    def _sync():
        page = _get_page()
        url = comment_data.post_url.replace("__REDDIT__", reddit_pw.REDDIT_DOMAIN)
        result = reddit_pw.comment_on_post_by_url(
            page,
            url,
            comment_data.comment_text,
        )
        return {"success": result.success, "message": result.error_message, "current_url": page.url}

    return await _run_pw(_sync)


@mcp.tool()
async def get_post_comments(post_url: str) -> Dict[str, Any]:
    """
    Get all comments on a post, with their Postmill comment URLs for replies.

    Returns:
        {"comments": [{"author": str, "text": str, "comment_url": str}]}
    """
    def _sync():
        import re as _re
        page = _get_page()
        url = post_url.replace("__REDDIT__", reddit_pw.REDDIT_DOMAIN)
        page.goto(url, timeout=15000)
        page.wait_for_load_state("networkidle", timeout=10000)
        # Extract forum/post_id for building comment URLs
        m = _re.search(r"/f/([^/]+)/(\d+)", url)
        forum = m.group(1) if m else ""
        pid = m.group(2) if m else ""
        results = []
        for el in page.query_selector_all("article.comment, .comment"):
            # Author
            author_el = el.query_selector(".comment__author a, .comment__attribution a[href*='/user/']")
            author = author_el.inner_text().strip() if author_el else ""
            # Body
            body_el = el.query_selector(".comment__body")
            text = body_el.inner_text().strip() if body_el else ""
            # Comment ID from element id attr or reply link
            cid = ""
            el_id = el.get_attribute("id") or ""
            id_m = _re.search(r"\d+", el_id)
            if id_m:
                cid = id_m.group(0)
            else:
                # Try reply link
                reply_link = el.query_selector("a[href*='/-/comment/']")
                if reply_link:
                    href = reply_link.get_attribute("href") or ""
                    cm = _re.search(r"/comment/(\d+)", href)
                    if cm:
                        cid = cm.group(1)
            comment_url = (
                f"{reddit_pw.REDDIT_DOMAIN}/f/{forum}/{pid}/-/comment/{cid}"
                if cid else ""
            )
            results.append({"author": author, "text": text, "comment_url": comment_url})
        return {"comments": results, "post_url": url}

    return await _run_pw(_sync)


@mcp.tool()
async def reply_to_comment(comment_url: str, reply_text: str) -> Dict[str, Any]:
    """
    Reply to a specific comment on a post.

    Navigate to the comment's page, reveal the reply form, and post the reply.

    Args:
        comment_url: Full URL of the comment (e.g. __REDDIT__/f/books/123/-/comment/456
                     or http://localhost:9999/f/books/123/-/comment/456)
        reply_text: Text to post as the reply

    Returns:
        {"success": bool, "current_url": str, "error": str}
    """
    def _sync():
        import re as _re
        page = _get_page()
        try:
            url = comment_url.replace("__REDDIT__", reddit_pw.REDDIT_DOMAIN)

            # Extract comment ID from URL
            m = _re.search(r"/comment/(\d+)", url)
            if not m:
                return {"success": False, "current_url": page.url,
                        "error": f"Could not extract comment ID from: {url}"}
            cid = m.group(1)

            # Navigate to the comment permalink page.
            # Postmill embeds the reply form there (hidden by default).
            m2 = _re.search(r"(https?://[^/]+/f/[^/]+/\d+)", url)
            comment_page = f"{m2.group(1)}/-/comment/{cid}" if m2 else url
            page.goto(comment_page, timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)

            form_name = f"reply_to_comment_{cid}"
            form_sel  = f'form[name="{form_name}"]'

            # The reply form is display:none by default; reveal it via JS,
            # fill the textarea, then submit using the form's own button.
            filled = page.evaluate(
                """(args) => {
                    const form = document.querySelector(args.sel);
                    if (!form) return 'form not found';
                    form.style.display = '';
                    const ta = form.querySelector('textarea');
                    if (!ta) return 'textarea not found';
                    ta.value = args.text;
                    ta.dispatchEvent(new Event('input', {bubbles: true}));
                    return 'ok';
                }""",
                {"sel": form_sel, "text": reply_text},
            )
            if filled != "ok":
                return {"success": False, "current_url": page.url,
                        "error": f"Could not reveal/fill reply form: {filled}"}

            # Click the submit button scoped to this specific reply form
            form_el = page.query_selector(form_sel)
            btn = form_el.query_selector("button[type='submit'], button") if form_el else None
            if btn:
                btn.click()
            else:
                page.evaluate(f"document.querySelector(\"{form_sel}\").submit()")

            page.wait_for_load_state("networkidle", timeout=10000)
            return {"success": True, "current_url": page.url}
        except Exception as e:
            return {"success": False, "current_url": page.url, "error": str(e)}

    return await _run_pw(_sync)


@mcp.tool()
async def delete_all_post_comments(post_url: str) -> Dict[str, Any]:
    """
    Delete all comments on a post (must be post owner).

    Returns:
        {"success": bool, "deleted_count": int}
    """
    def _sync():
        page = _get_page()
        result = reddit_pw.delete_all_comments_on_post(page, post_url)
        return {
            "success": result.success,
            "deleted_count": result.deleted_count,
            "message": result.error_message,
        }

    return await _run_pw(_sync)


@mcp.tool()
async def delete_user_comments_on_post(post_url: str, username: str) -> Dict[str, Any]:
    """
    Delete all comments by a specific user on a post.

    Returns:
        {"success": bool, "deleted_count": int}
    """
    def _sync():
        page = _get_page()
        result = reddit_pw.delete_all_comments_on_post_by_user(
            page,
            post_url,
        )
        return {
            "success": result.success,
            "deleted_count": result.deleted_count,
            "message": result.error_message,
        }

    return await _run_pw(_sync)


# ===== FORUM TOOLS =====

@mcp.tool()
async def create_forum(forum_data: ForumData) -> Dict[str, Any]:
    """
    Create a new forum/subreddit.

    Returns:
        {"success": bool, "message": str, "forum_url": str}
    """
    def _sync():
        page = _get_page()
        logged_in = os.getenv("REDDIT_USERNAME", "MarvelsGrantMan136")
        result = reddit_pw.create_forum(
            page,
            forum_data.name,
            forum_data.title or forum_data.name,
            forum_data.description,
            forum_data.sidebar_str,
            logged_in,
        )
        return {
            "success": result.success,
            "message": result.error_message,
            "forum_url": result.forum_url if result.success else None,
        }

    return await _run_pw(_sync)


@mcp.tool()
async def get_forum_info(forum_name: str) -> Dict[str, Any]:
    """
    Get information about a forum.

    Args:
        forum_name: Forum name (without f/ prefix)

    Returns:
        {"exists": bool, "name": str, "description": str, "member_count": int}
    """
    def _sync():
        page = _get_page()
        forum = reddit_pw.get_forum_info(page, forum_name)
        if forum:
            return {
                "exists": True,
                "name": forum.name,
                "title": forum.title,
                "description": forum.description,
                "sidebar": forum.sidebar,
                "url": forum.url,
            }
        return {"exists": False, "message": f"Forum '{forum_name}' not found"}

    return await _run_pw(_sync)


@mcp.tool()
async def check_forum_exists(forum_name: str) -> Dict[str, Any]:
    """
    Check if a forum exists.

    Returns:
        {"exists": bool}
    """
    def _sync():
        page = _get_page()
        return {"exists": reddit_pw.forum_exists(page, forum_name)}

    return await _run_pw(_sync)


# ===== MESSAGE TOOLS =====

@mcp.tool()
async def send_message(message_data: MessageData) -> Dict[str, Any]:
    """
    Send a private message to a user.

    Returns:
        {"success": bool, "message": str}
    """
    def _sync():
        page = _get_page()
        result = reddit_pw.send_message(
            page,
            message_data.recipient,
            message_data.subject,
            message_data.body,
        )
        return {"success": result.success, "message": result.error_message}

    return await _run_pw(_sync)


@mcp.tool()
async def get_messages() -> Dict[str, Any]:
    """
    Get all message threads for the logged-in user.

    Returns:
        {"messages": [{"sender": str, "subject": str, "preview": str, "unread": bool}]}
    """
    def _sync():
        page = _get_page()
        messages = reddit_pw.get_message_threads(page)
        return {
            "messages": [
                {
                    "sender": msg.sender,
                    "subject": msg.subject,
                    "preview": msg.preview,
                    "unread": msg.unread,
                }
                for msg in messages
            ]
        }

    return await _run_pw(_sync)


@mcp.tool()
async def delete_all_messages() -> Dict[str, Any]:
    """
    Delete all messages for the logged-in user.

    Returns:
        {"success": bool, "deleted_count": int}
    """
    def _sync():
        page = _get_page()
        result = reddit_pw.delete_all_messages(page)
        return {
            "success": result.success,
            "deleted_count": result.deleted_count,
            "message": result.error_message,
        }

    return await _run_pw(_sync)


@mcp.tool()
async def delete_messages_from_user(username: str) -> Dict[str, Any]:
    """
    Delete all messages from a specific user.

    Returns:
        {"success": bool, "deleted_count": int}
    """
    def _sync():
        page = _get_page()
        result = reddit_pw.delete_all_messages_by_user(page, username)
        return {
            "success": result.success,
            "deleted_count": result.deleted_count,
            "message": result.error_message,
        }

    return await _run_pw(_sync)


# ===== USER TOOLS =====

@mcp.tool()
async def get_user_info(username: str) -> Dict[str, Any]:
    """
    Get information about a user.

    Returns:
        {"exists": bool, "username": str, "karma": int, "created": str}
    """
    def _sync():
        page = _get_page()
        user_info = reddit_pw.get_user_info(page, username)
        if user_info:
            return {
                "exists": True,
                "username": user_info.username,
                "karma": user_info.karma,
                "created": user_info.created,
            }
        return {"exists": False, "message": f"User '{username}' not found"}

    return await _run_pw(_sync)


@mcp.tool()
async def check_user_exists(username: str) -> Dict[str, Any]:
    """
    Check if a user exists.

    Returns:
        {"exists": bool}
    """
    def _sync():
        page = _get_page()
        return {"exists": reddit_pw.user_exists(page, username)}

    return await _run_pw(_sync)


@mcp.tool()
async def block_user(username: str) -> Dict[str, Any]:
    """
    Block a user.

    Returns:
        {"success": bool, "message": str}
    """
    def _sync():
        page = _get_page()
        logged_in = os.getenv("REDDIT_USERNAME", "MarvelsGrantMan136")
        result = reddit_pw.block_user(page, logged_in, username)
        return {"success": result.success, "message": result.error_message}

    return await _run_pw(_sync)


@mcp.tool()
async def unblock_user(username: str) -> Dict[str, Any]:
    """
    Unblock a user.

    Returns:
        {"success": bool, "message": str}
    """
    def _sync():
        page = _get_page()
        logged_in = os.getenv("REDDIT_USERNAME", "MarvelsGrantMan136")
        result = reddit_pw.unblock_user(page, logged_in, username)
        return {"success": result.success, "message": result.error_message}

    return await _run_pw(_sync)


@mcp.tool()
async def get_blocked_users() -> Dict[str, Any]:
    """
    Get list of blocked users.

    Returns:
        {"blocked_users": [str]}
    """
    def _sync():
        page = _get_page()
        logged_in = os.getenv("REDDIT_USERNAME", "MarvelsGrantMan136")
        return {"blocked_users": reddit_pw.get_blocked_users(page, logged_in)}

    return await _run_pw(_sync)


@mcp.tool()
async def update_email(email_data: EmailUpdate) -> Dict[str, Any]:
    """
    Update email address for the logged-in user.

    Returns:
        {"success": bool, "message": str}
    """
    def _sync():
        page = _get_page()
        logged_in = os.getenv("REDDIT_USERNAME", "MarvelsGrantMan136")
        result = reddit_pw.update_email(page, logged_in, email_data.new_email)
        return {"success": result.success, "message": result.error_message}

    return await _run_pw(_sync)


@mcp.tool()
async def reset_email() -> Dict[str, Any]:
    """
    Reset/remove email address for the logged-in user.

    Returns:
        {"success": bool, "message": str}
    """
    def _sync():
        page = _get_page()
        logged_in = os.getenv("REDDIT_USERNAME", "MarvelsGrantMan136")
        result = reddit_pw.reset_email(page, logged_in)
        return {"success": result.success, "message": result.error_message}

    return await _run_pw(_sync)


# ===== NAVIGATION TOOLS =====

@mcp.tool()
async def navigate_to_url(url: str) -> Dict[str, Any]:
    """
    Navigate to a specific Reddit URL.

    Returns:
        {"success": bool, "current_url": str}
    """
    def _sync():
        page = _get_page()
        try:
            page.goto(url, timeout=30000)
            return {"success": True, "current_url": page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return await _run_pw(_sync)


@mcp.tool()
async def get_current_url() -> Dict[str, Any]:
    """
    Get the current page URL.

    Returns:
        {"url": str}
    """
    def _sync():
        page = _get_page()
        return {"url": page.url}

    return await _run_pw(_sync)


class VoteData(BaseModel):
    post_url: str = Field(..., description="Full URL of the post to vote on")


@mcp.tool()
async def upvote_post(vote_data: VoteData) -> Dict[str, Any]:
    """
    Upvote (like) a Reddit post by its URL.

    Args:
        vote_data: VoteData containing post_url

    Returns:
        {"success": bool, "url": str}
    """
    def _sync():
        page = _get_page()
        post_url = vote_data.post_url.replace("__REDDIT__", reddit_pw.REDDIT_DOMAIN)
        try:
            page.goto(post_url, timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
            # Check if already upvoted — avoid toggling off
            form = page.query_selector("form.vote")
            if form:
                current_choice = form.get_attribute("data-vote-choice-value") or "0"
                if current_choice == "1":
                    return {"success": True, "url": page.url, "already_upvoted": True}
            # Click upvote: Postmill uses button[name="choice"][value="1"]
            btn = page.query_selector('button[name="choice"][value="1"]')
            if btn:
                btn.click()
                page.wait_for_timeout(1000)
                return {"success": True, "url": page.url}
            return {"success": False, "url": page.url, "error": "Could not find upvote button"}
        except Exception as e:
            return {"success": False, "url": page.url, "error": str(e)}

    return await _run_pw(_sync)


@mcp.tool()
async def downvote_post(vote_data: VoteData) -> Dict[str, Any]:
    """
    Downvote (dislike) a Reddit post by its URL.

    Args:
        vote_data: VoteData containing post_url

    Returns:
        {"success": bool, "url": str}
    """
    def _sync():
        page = _get_page()
        post_url = vote_data.post_url.replace("__REDDIT__", reddit_pw.REDDIT_DOMAIN)
        try:
            page.goto(post_url, timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
            # Check if already downvoted — avoid toggling off
            form = page.query_selector("form.vote")
            if form:
                current_choice = form.get_attribute("data-vote-choice-value") or "0"
                if current_choice == "-1":
                    return {"success": True, "url": page.url, "already_downvoted": True}
            # Click downvote: Postmill uses button[name="choice"][value="-1"]
            btn = page.query_selector('button[name="choice"][value="-1"]')
            if btn:
                btn.click()
                page.wait_for_timeout(1000)
                return {"success": True, "url": page.url}
            return {"success": False, "url": page.url, "error": "Could not find downvote button"}
        except Exception as e:
            return {"success": False, "url": page.url, "error": str(e)}

    return await _run_pw(_sync)


class BioData(BaseModel):
    bio: str = Field(..., description="New bio/description text for the user profile")


@mcp.tool()
async def update_bio(bio_data: BioData) -> Dict[str, Any]:
    """
    Update the logged-in user's profile bio / description.

    Args:
        bio_data: BioData containing bio text

    Returns:
        {"success": bool, "url": str}
    """
    def _sync():
        page = _get_page()
        username = os.getenv("REDDIT_USERNAME", "MarvelsGrantMan136")
        edit_url = f"{reddit_pw.REDDIT_DOMAIN}/user/{username}/edit_biography"
        try:
            page.goto(edit_url, timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
            page.fill("#user_biography_biography", bio_data.bio)
            page.click('button:has-text("Save")', timeout=5000)
            page.wait_for_load_state("networkidle", timeout=8000)
            return {"success": True, "url": page.url}
        except Exception as e:
            return {"success": False, "url": page.url, "error": str(e)}

    return await _run_pw(_sync)


@mcp.tool()
async def get_forum_posts(forum: str, sort: str = "new") -> Dict[str, Any]:
    """
    Get a list of posts from a forum/subreddit, with their URLs.

    Navigate to the forum page and return the posts found there.
    Useful when you need to upvote/downvote/comment on a specific post in a forum.

    Args:
        forum: Forum/subreddit name (e.g. "books", "DIY", "technology")
        sort: Sort order — "new", "hot", "top", "rising" (default "new")

    Returns:
        {"success": bool, "posts": [{"url": str, "title": str}, ...], "url": str}
    """
    def _sync():
        import re as _re
        page = _get_page()
        try:
            # Postmill uses path-based sort: /f/{forum}/new, /f/{forum}/top, etc.
            # Default (no sort param) is "hot".
            forum_url = f"{reddit_pw.REDDIT_DOMAIN}/f/{forum}"
            if sort and sort != "hot":
                forum_url += f"/{sort}"
            page.goto(forum_url, timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)

            posts = []
            seen_urls: set = set()
            try:
                links = page.query_selector_all("a[href]")
                post_pattern = _re.compile(r"^/f/[^/]+/\d+/")
                for link in links:
                    href = link.get_attribute("href") or ""
                    if not post_pattern.match(href):
                        continue
                    title = link.inner_text().strip()
                    post_url = f"{reddit_pw.REDDIT_DOMAIN}{href}"
                    if post_url in seen_urls:
                        continue
                    seen_urls.add(post_url)
                    posts.append({"url": post_url, "title": title})
            except Exception:
                pass

            return {
                "success": True,
                "posts": posts,
                "url": page.url,
                "final_url": page.url,
            }
        except Exception as e:
            return {"success": False, "posts": [], "url": page.url, "error": str(e)}

    return await _run_pw(_sync)


@mcp.tool()
async def subscribe_to_forum(forum_name: str) -> Dict[str, Any]:
    """
    Subscribe to a subreddit/forum.

    Args:
        forum_name: Name of the forum to subscribe to

    Returns:
        {"success": bool, "url": str}
    """
    def _sync():
        page = _get_page()
        try:
            forum_url = f"{reddit_pw.REDDIT_DOMAIN}/f/{forum_name}"
            page.goto(forum_url, timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
            # Only click if there's a subscribe button (action ends with /subscribe,
            # NOT /unsubscribe) — avoids accidentally toggling subscription off
            subscribe_btn = page.query_selector('form[action$="/subscribe"] button')
            if subscribe_btn:
                subscribe_btn.click()
                page.wait_for_load_state("networkidle", timeout=8000)
                return {"success": True, "url": page.url}
            else:
                # Already subscribed (button says "Unsubscribe") or no button found
                return {"success": True, "url": page.url, "already_subscribed": True}
        except Exception as e:
            return {"success": False, "url": page.url, "error": str(e)}

    return await _run_pw(_sync)


# Run the server
if __name__ == "__main__":
    # Add project root to path so agent module can be imported
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.common.configurator import Configurator

    print("Starting reddit-mcp server")

    config = Configurator()
    config.load_mcpserver_env()
    config.load_shared_env()

    # Read URL from config.yaml -> mcp_server.reddit
    mcp_server_url = config.get_key("mcp_server")["reddit"]
    parsed = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(mcp_server_url)
    hostname = parsed.hostname
    port = parsed.port
    path = parsed.path or "/"

    # Run FastMCP over HTTP (streamable-http transport), same as gitlab_server
    mcp.run(
        transport="streamable-http",
        host=hostname,
        port=port,
        path=path,
    )
