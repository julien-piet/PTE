"""
Reddit API server — FastAPI wrapper around api/reddit_pw Playwright functions.

Exposes Playwright-based actions as simple HTTP endpoints so the agent can call
them without worrying about CSRF scraping, Select2 dropdowns, or AJAX form loading.

Run on port 7791:
    python3 api/servers/reddit.py

Or launched automatically by initialize.py / run_tasks_batch_new.py.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
from typing import List, Optional, Union

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from playwright.sync_api import sync_playwright

from config.init_tokens.refresh_reddit_session import refresh_session
from config.servers import SERVER_URLS
from api.reddit_pw.constants import REDDIT_DOMAIN
from api.reddit_pw import (
    vote_post,
    edit_post,
    get_forum_posts,
    get_post,
    search_posts,
    get_posts_by_username,
    subscribe_to_forum,
    reply_to_comment,
    update_biography,
    create_post,
    get_comments_on_post,
    comment_on_post_by_url,
    create_forum,
)

REDDIT_BASE_URL = SERVER_URLS["reddit"]

app = FastAPI(
    title="Reddit API",
    description="Playwright-based actions for the WebArena Reddit (Postmill) site.",
    version="1.0.0",
)


# ── Auth helper ───────────────────────────────────────────────────────────────

def _make_browser_page(playwright):
    """Create a browser page authenticated with the current Reddit session."""
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    phpsessid = refresh_session()
    # Set cookie for both localhost and 127.0.0.1 — agent-provided URLs may use either host,
    # and REDDIT_DOMAIN (playwright navigation) may differ from agent-resolved URLs.
    for domain in ("localhost", "127.0.0.1"):
        context.add_cookies([{
            "name": "PHPSESSID",
            "value": phpsessid,
            "domain": domain,
            "path": "/",
        }])
    page = context.new_page()
    return browser, page


# ── Request / Response models ─────────────────────────────────────────────────

class VotePostRequest(BaseModel):
    # Accept post_url (full URL) OR post_id + optional forum (agent may pass either)
    post_url: Optional[str] = None
    post_id: Optional[str] = None
    forum: Optional[str] = None
    # Accept direction ("up"/"down") OR vote ("1"/"-1"/1/-1) — allow int or str
    direction: Optional[Union[str, int]] = None
    vote: Optional[Union[str, int]] = None

class VotePostResponse(BaseModel):
    success: bool
    error_message: Optional[str] = None


class SubscribeForumRequest(BaseModel):
    forum_name: Optional[str] = None
    body: Optional[str] = None  # agent sometimes sends the name as "body" when resolving a reference

class SubscribeForumResponse(BaseModel):
    success: bool
    already_subscribed: bool = False
    error_message: Optional[str] = None


class UpdateBiographyRequest(BaseModel):
    username: str
    biography: str

class UpdateBiographyResponse(BaseModel):
    success: bool
    error_message: Optional[str] = None


class ReplyToCommentRequest(BaseModel):
    # post_url + comment_id (explicit) OR comment_url (full comment permalink — both derived automatically)
    post_url: Optional[str] = None
    comment_id: Optional[str] = None
    comment_url: Optional[str] = None  # e.g. http://host/f/books/59421/-/comment/1235250
    reply_text: Optional[str] = None   # also accepted as "text"
    text: Optional[str] = None         # alias for reply_text

class ReplyToCommentResponse(BaseModel):
    success: bool
    comment_url: Optional[str] = None
    error_message: Optional[str] = None


class EditPostRequest(BaseModel):
    post_url: str
    new_body: Optional[str] = None
    new_title: Optional[str] = None
    append: bool = False

class EditPostResponse(BaseModel):
    success: bool
    post_url: Optional[str] = None
    error_message: Optional[str] = None


class GetPostResponse(BaseModel):
    id: str
    title: str
    body: str
    author: str
    subreddit: str
    url: str
    score: int
    link_url: Optional[str] = None
    error_message: Optional[str] = None


class CreatePostRequest(BaseModel):
    forum: str
    title: str
    body: str = ""
    url: Optional[str] = None  # for link/image posts

class CreatePostResponse(BaseModel):
    success: bool
    post_url: Optional[str] = None
    already_existed: bool = False
    error_message: Optional[str] = None


class PostInfo(BaseModel):
    id: str
    title: str
    author: str
    subreddit: str
    url: str
    score: int
    link_url: Optional[str] = None

class GetForumPostsResponse(BaseModel):
    posts: List[PostInfo]


class CommentInfo(BaseModel):
    id: str
    body: str
    author: str
    url: str
    score: int

class GetCommentsResponse(BaseModel):
    comments: List[CommentInfo]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/vote_post", response_model=VotePostResponse)
def vote_post_endpoint(payload: VotePostRequest) -> VotePostResponse:
    """
    Upvote or downvote a submission.
    direction: "up" to upvote, "down" to downvote.
    post_url: full URL of the submission page.
    """
    # Resolve URL: accept post_url directly, or construct from post_id + forum
    url = payload.post_url
    # If post_url is a JSON-stringified dict (e.g. loop_item was a post object not a string),
    # extract the 'url' or 'post_url' field from it.
    if url and url.strip().startswith("{"):
        import json as _json
        try:
            obj = _json.loads(url)
            if isinstance(obj, dict):
                url = obj.get("url") or obj.get("post_url") or url
        except Exception:
            pass
    if not url and payload.post_id:
        forum = payload.forum or "books"
        url = f"{REDDIT_BASE_URL}/f/{forum}/{payload.post_id}"
    if not url:
        return VotePostResponse(success=False, error_message="Provide post_url or post_id")

    # Resolve direction: accept "up"/"down" or "1"/"-1"/1/-1
    raw = str(payload.direction or payload.vote or "up").strip()
    direction = "up" if raw in ("up", "1", "upvote") else "down"

    with sync_playwright() as p:
        browser, page = _make_browser_page(p)
        try:
            result = vote_post(page, url, direction)
            return VotePostResponse(success=result.success, error_message=result.error_message)
        finally:
            browser.close()


@app.post("/subscribe_forum", response_model=SubscribeForumResponse)
def subscribe_forum_endpoint(payload: SubscribeForumRequest) -> SubscribeForumResponse:
    """
    Subscribe to a forum (subreddit). Idempotent — returns already_subscribed=true if already done.
    forum_name: the forum to subscribe to (also accepted as "body" if the agent passes a bare string reference).
    """
    forum_name = payload.forum_name or payload.body
    if not forum_name:
        return SubscribeForumResponse(success=False, error_message="forum_name is required")
    with sync_playwright() as p:
        browser, page = _make_browser_page(p)
        try:
            result = subscribe_to_forum(page, forum_name)
            return SubscribeForumResponse(
                success=result.success,
                already_subscribed=result.already_subscribed,
                error_message=result.error_message,
            )
        finally:
            browser.close()


@app.post("/update_biography", response_model=UpdateBiographyResponse)
def update_biography_endpoint(payload: UpdateBiographyRequest) -> UpdateBiographyResponse:
    """
    Update the biography of the logged-in user. Markdown is supported.
    username must be the currently logged-in user's username.
    """
    with sync_playwright() as p:
        browser, page = _make_browser_page(p)
        try:
            result = update_biography(page, payload.username, payload.biography)
            return UpdateBiographyResponse(success=result.success, error_message=result.error_message)
        finally:
            browser.close()


@app.post("/reply_to_comment", response_model=ReplyToCommentResponse)
def reply_to_comment_endpoint(payload: ReplyToCommentRequest) -> ReplyToCommentResponse:
    """
    Reply to a specific comment on a post.
    Pass EITHER:
      - comment_url (full comment permalink from /comments response, e.g. http://host/f/books/59421/-/comment/1235250)
      OR
      - post_url + comment_id separately
    reply_text (or alias "text"): the reply body.
    """
    # Resolve reply text — accept "text" as alias
    reply_text = payload.reply_text or payload.text
    if not reply_text:
        return ReplyToCommentResponse(success=False, error_message="reply_text (or text) is required")

    # Derive post_url + comment_id from comment_url if provided
    post_url = payload.post_url
    comment_id = payload.comment_id
    if payload.comment_url and (not post_url or not comment_id):
        # comment_url format: http://host/f/{forum}/{post_id}/-/comment/{comment_id}
        parts = payload.comment_url.rstrip("/").split("/")
        try:
            c_idx = parts.index("comment")
            comment_id = comment_id or parts[c_idx + 1]
            # post_url = everything before /-/comment/...
            post_url = post_url or "/".join(parts[:c_idx - 1])
        except (ValueError, IndexError):
            return ReplyToCommentResponse(success=False, error_message=f"Cannot parse comment_url: {payload.comment_url}")

    # Validate we have what we need
    if not comment_id or not comment_id.strip() or comment_id.strip().lower() in ("null", "none", ""):
        return ReplyToCommentResponse(success=False, error_message="comment_id is required and must be a valid numeric ID")
    if not post_url:
        return ReplyToCommentResponse(success=False, error_message="post_url (or comment_url) is required")

    with sync_playwright() as p:
        browser, page = _make_browser_page(p)
        try:
            result = reply_to_comment(page, post_url, comment_id.strip(), reply_text)
            return ReplyToCommentResponse(
                success=result.success,
                comment_url=result.comment_url,
                error_message=result.error_message,
            )
        finally:
            browser.close()


@app.post("/edit_post", response_model=EditPostResponse)
def edit_post_endpoint(payload: EditPostRequest) -> EditPostResponse:
    """
    Edit a post's title and/or body.
    post_url: full URL of the submission.
    new_body / new_title: pass only the fields you want to change.
    """
    with sync_playwright() as p:
        browser, page = _make_browser_page(p)
        try:
            result = edit_post(page, payload.post_url, payload.new_body, payload.new_title, payload.append)
            return EditPostResponse(
                success=result.success,
                post_url=result.post_url,
                error_message=result.error_message,
            )
        finally:
            browser.close()


@app.post("/create_post", response_model=CreatePostResponse)
def create_post_endpoint(payload: CreatePostRequest) -> CreatePostResponse:
    """
    Create a new submission. Checks for duplicate titles (idempotent).
    forum: forum name (e.g. "books"). body: post body text. url: optional link URL for link posts.
    """
    # Get the username from the current session to check for duplicates
    from dotenv import dotenv_values
    from pathlib import Path
    creds = dotenv_values(Path(__file__).parent.parent.parent / "config" / ".env")
    username = creds.get("REDDIT_USERNAME", "").strip()

    with sync_playwright() as p:
        browser, page = _make_browser_page(p)
        try:
            result = create_post(page, payload.forum, payload.title, payload.body, username, payload.url)
            return CreatePostResponse(
                success=result.success,
                post_url=result.post_url,
                already_existed=result.already_existed,
                error_message=result.error_message,
            )
        finally:
            browser.close()


@app.get("/list_forums")
def list_forums_endpoint() -> dict:
    """
    Return the names of all forums (subreddits) on this site.
    Use this to discover the exact forum name before calling /create_post or /forum_posts.
    """
    import re as _re
    import requests as _http
    from config.init_tokens.refresh_reddit_session import refresh_session as _refresh
    phpsessid = _refresh()
    s = _http.Session()
    s.cookies.set("PHPSESSID", phpsessid)
    r = s.get(f"{REDDIT_BASE_URL}/forums/all")
    forums = sorted(set(_re.findall(r'/f/([A-Za-z0-9_]+)', r.text)))
    return {"forums": [{"name": f} for f in forums]}


@app.get("/forum_posts", response_model=GetForumPostsResponse)
def get_forum_posts_endpoint(
    forum: str,
    sort: str = "hot",
    limit: int = 25,
) -> GetForumPostsResponse:
    """
    List posts in a forum with their scores.
    sort: hot (default), new, top, controversial, active.
    limit: max posts to return (default 25, max 50).
    """
    limit = min(limit, 50)
    with sync_playwright() as p:
        browser, page = _make_browser_page(p)
        try:
            posts = get_forum_posts(page, forum, sort, limit)
            return GetForumPostsResponse(posts=[
                PostInfo(
                    id=p.id, title=p.title, author=p.author,
                    subreddit=p.subreddit, url=p.url, score=p.score,
                    link_url=p.link_url,
                )
                for p in posts
            ])
        finally:
            browser.close()


@app.get("/post", response_model=GetPostResponse)
def get_post_endpoint(forum: str, post_id: str) -> GetPostResponse:
    """
    Fetch a single post by forum name and post ID.
    Returns the full body text, score, author, and link URL.
    forum: forum name (e.g. "MachineLearning").
    post_id: numeric post ID from the post URL (/f/{forum}/{post_id}/...).
    """
    with sync_playwright() as p:
        browser, page = _make_browser_page(p)
        try:
            post = get_post(page, forum, post_id)
            if post is None:
                return GetPostResponse(
                    id=post_id, title="", body="", author="", subreddit=forum,
                    url="", score=0, error_message="Post not found",
                )
            return GetPostResponse(
                id=post.id,
                title=post.title,
                body=post.body,
                author=post.author,
                subreddit=post.subreddit,
                url=post.url,
                score=post.score,
                link_url=post.link_url,
            )
        finally:
            browser.close()


@app.get("/search", response_model=GetForumPostsResponse)
def search_endpoint(
    q: str,
    limit: int = 25,
) -> GetForumPostsResponse:
    """
    Full-text search across all posts by title and body content.
    Returns posts whose title or body contains the query string (fuzzy match).
    Use this instead of /forum_posts when you need to find a specific post by
    a keyword or partial title rather than listing a forum's posts.
    q: search query (e.g. "Bald Eagle").
    limit: max posts to return (default 25, max 50).
    """
    limit = min(limit, 50)
    with sync_playwright() as p:
        browser, page = _make_browser_page(p)
        try:
            posts = search_posts(page, q, limit)
            return GetForumPostsResponse(posts=[
                PostInfo(
                    id=post.id, title=post.title, author=post.author,
                    subreddit=post.subreddit, url=post.url, score=post.score,
                    link_url=post.link_url,
                )
                for post in posts
            ])
        finally:
            browser.close()


@app.get("/user_posts", response_model=GetForumPostsResponse)
def get_user_posts_endpoint(
    username: str,
    limit: int = 50,
) -> GetForumPostsResponse:
    """
    List all submissions by a user from their profile /submissions page.
    Use this when you need to find and act on all posts by a specific user,
    regardless of which forum they posted in.
    limit: max posts to return (default 50).
    """
    limit = min(limit, 50)
    with sync_playwright() as p:
        browser, page = _make_browser_page(p)
        try:
            posts = get_posts_by_username(page, username, limit)
            return GetForumPostsResponse(posts=[
                PostInfo(
                    id=p.id, title=p.title, author=p.author,
                    subreddit=p.subreddit, url=p.url, score=p.score,
                    link_url=p.link_url,
                )
                for p in posts
            ])
        finally:
            browser.close()


@app.get("/comments", response_model=GetCommentsResponse)
def get_comments_endpoint(forum: str, post_id: str) -> GetCommentsResponse:
    """
    Get all comments on a post with their net vote scores.
    score > 0 means more upvotes; score < 0 means more downvotes than upvotes.
    """
    with sync_playwright() as p:
        browser, page = _make_browser_page(p)
        try:
            comments = get_comments_on_post(page, forum, post_id)
            return GetCommentsResponse(comments=[
                CommentInfo(id=c.id, body=c.body, author=c.author, url=c.url, score=c.score)
                for c in comments
            ])
        finally:
            browser.close()


class CreateCommentRequest(BaseModel):
    post_url: str
    comment_text: str

class CreateCommentResponse(BaseModel):
    success: bool
    comment_url: Optional[str] = None
    error_message: Optional[str] = None


class CreateForumRequest(BaseModel):
    forum_name: str
    forum_title: str
    forum_description: str
    forum_sidebar: str

class CreateForumResponse(BaseModel):
    success: bool
    forum_url: Optional[str] = None
    forum_name: Optional[str] = None
    already_existed: bool = False
    error_message: Optional[str] = None


@app.post("/create_comment", response_model=CreateCommentResponse)
def create_comment_endpoint(payload: CreateCommentRequest) -> CreateCommentResponse:
    """
    Post a top-level comment on a submission.
    post_url: full URL of the submission page.
    """
    with sync_playwright() as p:
        browser, page = _make_browser_page(p)
        try:
            result = comment_on_post_by_url(page, payload.post_url, payload.comment_text)
            return CreateCommentResponse(
                success=result.success,
                comment_url=result.comment_url,
                error_message=result.error_message,
            )
        finally:
            browser.close()


@app.post("/create_forum", response_model=CreateForumResponse)
def create_forum_endpoint(payload: CreateForumRequest) -> CreateForumResponse:
    """
    Create a new forum (subreddit). Checks if the forum already exists (idempotent).
    forum_name is the URL-safe identifier; forum_title is the display name.
    Both forum_description and forum_sidebar are required.
    """
    from dotenv import dotenv_values
    from pathlib import Path
    creds = dotenv_values(Path(__file__).parent.parent.parent / "config" / ".env")
    username = creds.get("REDDIT_USERNAME", "").strip()

    with sync_playwright() as p:
        browser, page = _make_browser_page(p)
        try:
            result = create_forum(
                page, payload.forum_name, payload.forum_title,
                payload.forum_description, payload.forum_sidebar, username,
            )
            return CreateForumResponse(
                success=result.success,
                forum_url=result.forum_url,
                forum_name=result.forum_name,
                already_existed=result.already_existed,
                error_message=result.error_message,
            )
        finally:
            browser.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7791)
