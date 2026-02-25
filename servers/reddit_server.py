#!/usr/bin/env python3
"""
Reddit MCP Server

FastMCP server that wraps the Playwright-based Reddit API (api/reddit_pw).
Exposes Reddit operations as MCP tools for agent use.

Based on WebArena Reddit benchmark tasks.
"""

import sys
from pathlib import Path

# Add project root to path so we can import from api/
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from playwright.sync_api import Page, sync_playwright
import os

# Import Reddit API modules
from api import reddit_pw

# Create MCP server
mcp = FastMCP("Reddit API Server")

# Global Playwright resources
_playwright = None
_browser = None
_context = None
_page = None


def _get_page() -> Page:
    """Get or create the Playwright page."""
    global _playwright, _browser, _context, _page

    if _page is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=True)
        _context = _browser.new_context()
        _page = _context.new_page()

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
    text: str = Field(description="Post content/text")


class CommentData(BaseModel):
    """Data for creating a comment."""
    post_url: str = Field(description="URL of the post to comment on")
    comment_text: str = Field(description="Comment content")


class MessageData(BaseModel):
    """Data for sending a message."""
    recipient: str = Field(description="Username of recipient")
    subject: str = Field(description="Message subject")
    body: str = Field(description="Message body")


class ForumData(BaseModel):
    """Data for creating a forum."""
    name: str = Field(description="Forum name (without f/ prefix)")
    description: str = Field(description="Forum description")


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
    page = _get_page()

    if credentials:
        username, password = credentials.username, credentials.password
    else:
        # Use default credentials from environment
        username = os.getenv("REDDIT_USERNAME", "MarvelsGrantMan136")
        password = os.getenv("REDDIT_PASSWORD", "test1234")

    result = reddit_pw.login_user(page, username, password)

    return {
        "success": result.success,
        "message": result.message,
        "username": username
    }


@mcp.tool()
async def create_user(user_data: UserRegistration) -> Dict[str, Any]:
    """
    Create a new Reddit user account.

    Returns:
        {"success": bool, "message": str, "username": str}
    """
    page = _get_page()

    result = reddit_pw.create_user(
        page,
        user_data.username,
        user_data.password,
        user_data.email
    )

    return {
        "success": result.success,
        "message": result.message,
        "username": user_data.username
    }


@mcp.tool()
async def check_login_status() -> Dict[str, Any]:
    """
    Check if currently logged into Reddit.

    Returns:
        {"logged_in": bool}
    """
    page = _get_page()
    logged_in = reddit_pw.is_logged_in(page)

    return {"logged_in": logged_in}


# ===== POST TOOLS =====

@mcp.tool()
async def create_post(post_data: PostData) -> Dict[str, Any]:
    """
    Create a new post in a forum.

    Returns:
        {"success": bool, "message": str, "post_url": str}
    """
    page = _get_page()

    result = reddit_pw.create_post_with_title_and_text(
        page,
        post_data.forum,
        post_data.title,
        post_data.text
    )

    return {
        "success": result.success,
        "message": result.message,
        "post_url": result.post_url if result.success else None
    }


@mcp.tool()
async def delete_post(post_url: str) -> Dict[str, Any]:
    """
    Delete a post by URL.

    Args:
        post_url: Full URL of the post to delete

    Returns:
        {"success": bool, "message": str}
    """
    page = _get_page()

    result = reddit_pw.delete_post_by_url(page, post_url)

    return {
        "success": result.success,
        "message": result.message
    }


@mcp.tool()
async def get_user_posts(username: str) -> Dict[str, Any]:
    """
    Get all posts by a specific user.

    Returns:
        {"posts": [{"title": str, "url": str, "forum": str, "score": int}]}
    """
    page = _get_page()

    posts = reddit_pw.get_posts_by_username(page, username)

    return {
        "posts": [
            {
                "title": post.title,
                "url": post.url,
                "forum": post.forum,
                "score": post.score
            }
            for post in posts
        ]
    }


@mcp.tool()
async def delete_all_user_posts(username: str) -> Dict[str, Any]:
    """
    Delete all posts by a specific user.

    Returns:
        {"success": bool, "deleted_count": int}
    """
    page = _get_page()

    result = reddit_pw.delete_all_posts_by_username(page, username)

    return {
        "success": result.success,
        "deleted_count": result.deleted_count,
        "message": result.message
    }


# ===== COMMENT TOOLS =====

@mcp.tool()
async def comment_on_post(comment_data: CommentData) -> Dict[str, Any]:
    """
    Add a comment to a post.

    Returns:
        {"success": bool, "message": str}
    """
    page = _get_page()

    result = reddit_pw.comment_on_post_by_url(
        page,
        comment_data.post_url,
        comment_data.comment_text
    )

    return {
        "success": result.success,
        "message": result.message
    }


@mcp.tool()
async def get_post_comments(post_url: str) -> Dict[str, Any]:
    """
    Get all comments on a post.

    Returns:
        {"comments": [{"author": str, "text": str, "score": int}]}
    """
    page = _get_page()

    comments = reddit_pw.get_comments_on_post(page, post_url)

    return {
        "comments": [
            {
                "author": comment.author,
                "text": comment.text,
                "score": comment.score
            }
            for comment in comments
        ]
    }


@mcp.tool()
async def delete_all_post_comments(post_url: str) -> Dict[str, Any]:
    """
    Delete all comments on a post (must be post owner).

    Returns:
        {"success": bool, "deleted_count": int}
    """
    page = _get_page()

    result = reddit_pw.delete_all_comments_on_post(page, post_url)

    return {
        "success": result.success,
        "deleted_count": result.deleted_count,
        "message": result.message
    }


@mcp.tool()
async def delete_user_comments_on_post(post_url: str, username: str) -> Dict[str, Any]:
    """
    Delete all comments by a specific user on a post.

    Returns:
        {"success": bool, "deleted_count": int}
    """
    page = _get_page()

    result = reddit_pw.delete_all_comments_on_post_by_user(
        page,
        post_url,
        username
    )

    return {
        "success": result.success,
        "deleted_count": result.deleted_count,
        "message": result.message
    }


# ===== FORUM TOOLS =====

@mcp.tool()
async def create_forum(forum_data: ForumData) -> Dict[str, Any]:
    """
    Create a new forum/subreddit.

    Returns:
        {"success": bool, "message": str, "forum_url": str}
    """
    page = _get_page()

    result = reddit_pw.create_forum(
        page,
        forum_data.name,
        forum_data.description
    )

    return {
        "success": result.success,
        "message": result.message,
        "forum_url": result.forum_url if result.success else None
    }


@mcp.tool()
async def get_forum_info(forum_name: str) -> Dict[str, Any]:
    """
    Get information about a forum.

    Args:
        forum_name: Forum name (without f/ prefix)

    Returns:
        {"exists": bool, "name": str, "description": str, "member_count": int}
    """
    page = _get_page()

    forum = reddit_pw.get_forum_info(page, forum_name)

    if forum:
        return {
            "exists": True,
            "name": forum.name,
            "description": forum.description,
            "member_count": forum.member_count
        }
    else:
        return {
            "exists": False,
            "message": f"Forum '{forum_name}' not found"
        }


@mcp.tool()
async def check_forum_exists(forum_name: str) -> Dict[str, Any]:
    """
    Check if a forum exists.

    Returns:
        {"exists": bool}
    """
    page = _get_page()

    exists = reddit_pw.forum_exists(page, forum_name)

    return {"exists": exists}


# ===== MESSAGE TOOLS =====

@mcp.tool()
async def send_message(message_data: MessageData) -> Dict[str, Any]:
    """
    Send a private message to a user.

    Returns:
        {"success": bool, "message": str}
    """
    page = _get_page()

    result = reddit_pw.send_message(
        page,
        message_data.recipient,
        message_data.subject,
        message_data.body
    )

    return {
        "success": result.success,
        "message": result.message
    }


@mcp.tool()
async def get_messages() -> Dict[str, Any]:
    """
    Get all message threads for the logged-in user.

    Returns:
        {"messages": [{"sender": str, "subject": str, "preview": str, "unread": bool}]}
    """
    page = _get_page()

    messages = reddit_pw.get_message_threads(page)

    return {
        "messages": [
            {
                "sender": msg.sender,
                "subject": msg.subject,
                "preview": msg.preview,
                "unread": msg.unread
            }
            for msg in messages
        ]
    }


@mcp.tool()
async def delete_all_messages() -> Dict[str, Any]:
    """
    Delete all messages for the logged-in user.

    Returns:
        {"success": bool, "deleted_count": int}
    """
    page = _get_page()

    result = reddit_pw.delete_all_messages(page)

    return {
        "success": result.success,
        "deleted_count": result.deleted_count,
        "message": result.message
    }


@mcp.tool()
async def delete_messages_from_user(username: str) -> Dict[str, Any]:
    """
    Delete all messages from a specific user.

    Returns:
        {"success": bool, "deleted_count": int}
    """
    page = _get_page()

    result = reddit_pw.delete_all_messages_by_user(page, username)

    return {
        "success": result.success,
        "deleted_count": result.deleted_count,
        "message": result.message
    }


# ===== USER TOOLS =====

@mcp.tool()
async def get_user_info(username: str) -> Dict[str, Any]:
    """
    Get information about a user.

    Returns:
        {"exists": bool, "username": str, "karma": int, "created": str}
    """
    page = _get_page()

    user_info = reddit_pw.get_user_info(page, username)

    if user_info:
        return {
            "exists": True,
            "username": user_info.username,
            "karma": user_info.karma,
            "created": user_info.created
        }
    else:
        return {
            "exists": False,
            "message": f"User '{username}' not found"
        }


@mcp.tool()
async def check_user_exists(username: str) -> Dict[str, Any]:
    """
    Check if a user exists.

    Returns:
        {"exists": bool}
    """
    page = _get_page()

    exists = reddit_pw.user_exists(page, username)

    return {"exists": exists}


@mcp.tool()
async def block_user(username: str) -> Dict[str, Any]:
    """
    Block a user.

    Returns:
        {"success": bool, "message": str}
    """
    page = _get_page()

    result = reddit_pw.block_user(page, username)

    return {
        "success": result.success,
        "message": result.message
    }


@mcp.tool()
async def unblock_user(username: str) -> Dict[str, Any]:
    """
    Unblock a user.

    Returns:
        {"success": bool, "message": str}
    """
    page = _get_page()

    result = reddit_pw.unblock_user(page, username)

    return {
        "success": result.success,
        "message": result.message
    }


@mcp.tool()
async def get_blocked_users() -> Dict[str, Any]:
    """
    Get list of blocked users.

    Returns:
        {"blocked_users": [str]}
    """
    page = _get_page()

    blocked = reddit_pw.get_blocked_users(page)

    return {"blocked_users": blocked}


@mcp.tool()
async def update_email(email_data: EmailUpdate) -> Dict[str, Any]:
    """
    Update email address for the logged-in user.

    Returns:
        {"success": bool, "message": str}
    """
    page = _get_page()

    result = reddit_pw.update_email(
        page,
        email_data.new_email,
        email_data.password
    )

    return {
        "success": result.success,
        "message": result.message
    }


@mcp.tool()
async def reset_email() -> Dict[str, Any]:
    """
    Reset/remove email address for the logged-in user.

    Returns:
        {"success": bool, "message": str}
    """
    page = _get_page()

    result = reddit_pw.reset_email(page)

    return {
        "success": result.success,
        "message": result.message
    }


# ===== NAVIGATION TOOLS =====

@mcp.tool()
async def navigate_to_url(url: str) -> Dict[str, Any]:
    """
    Navigate to a specific Reddit URL.

    Returns:
        {"success": bool, "current_url": str}
    """
    page = _get_page()

    try:
        page.goto(url, timeout=30000)
        return {
            "success": True,
            "current_url": page.url
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def get_current_url() -> Dict[str, Any]:
    """
    Get the current page URL.

    Returns:
        {"url": str}
    """
    page = _get_page()
    return {"url": page.url}


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
    page = _get_page()
    post_url = vote_data.post_url.replace("__REDDIT__", reddit_pw.REDDIT_DOMAIN)
    try:
        page.goto(post_url, timeout=15000)
        page.wait_for_load_state("networkidle", timeout=10000)
        clicked = False
        for sel in [
            '.vote button[value="1"]',
            '.vote button:first-child',
            'button[name="dir"][value="1"]',
            '.submission__vote button[name="dir"][value="1"]',
            'button[data-vote="up"]',
            'button.upvote',
            'button[title="upvote"]',
            '[aria-label*="upvote" i]',
        ]:
            try:
                page.click(sel, timeout=2000)
                clicked = True
                break
            except Exception:
                continue
        page.wait_for_timeout(500)
        return {"success": clicked, "url": page.url,
                "error": None if clicked else "Could not find upvote button"}
    except Exception as e:
        return {"success": False, "url": page.url, "error": str(e)}


@mcp.tool()
async def downvote_post(vote_data: VoteData) -> Dict[str, Any]:
    """
    Downvote (dislike) a Reddit post by its URL.

    Args:
        vote_data: VoteData containing post_url

    Returns:
        {"success": bool, "url": str}
    """
    page = _get_page()
    post_url = vote_data.post_url.replace("__REDDIT__", reddit_pw.REDDIT_DOMAIN)
    try:
        page.goto(post_url, timeout=15000)
        page.wait_for_load_state("networkidle", timeout=10000)
        clicked = False
        for sel in [
            '.vote button[value="-1"]',
            '.vote button:last-child',
            'button[name="dir"][value="-1"]',
            '.submission__vote button[name="dir"][value="-1"]',
            'button[data-vote="down"]',
            'button.downvote',
            'button[title="downvote"]',
            '[aria-label*="downvote" i]',
        ]:
            try:
                page.click(sel, timeout=2000)
                clicked = True
                break
            except Exception:
                continue
        page.wait_for_timeout(500)
        return {"success": clicked, "url": page.url,
                "error": None if clicked else "Could not find downvote button"}
    except Exception as e:
        return {"success": False, "url": page.url, "error": str(e)}


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
    page = _get_page()
    username = os.getenv("REDDIT_USERNAME", "MarvelsGrantMan136")
    account_url = f"{reddit_pw.REDDIT_DOMAIN}/user/{username}/account"
    try:
        page.goto(account_url, timeout=15000)
        page.wait_for_load_state("networkidle", timeout=10000)
        ta = page.locator(
            '#user_description, '
            'textarea[name="description"], '
            'textarea[name="bio"], '
            '.user-bio textarea, '
            '#user_bio'
        )
        ta.first.fill(bio_data.bio)
        page.click(
            'button[type="submit"], input[type="submit"], '
            'button:has-text("Save"), button:has-text("Update")',
            timeout=5000,
        )
        page.wait_for_load_state("networkidle", timeout=8000)
        return {"success": True, "url": page.url}
    except Exception as e:
        return {"success": False, "url": page.url, "error": str(e)}


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
    page = _get_page()
    try:
        forum_url = f"{reddit_pw.REDDIT_DOMAIN}/f/{forum}"
        if sort and sort != "hot":
            forum_url += f"?sort={sort}"
        page.goto(forum_url, timeout=15000)
        page.wait_for_load_state("networkidle", timeout=10000)

        posts = []
        seen_urls: set = set()
        try:
            links = page.query_selector_all(
                "article a[href*='/f/'], .listing__title a, .post-title a, "
                "h2 a[href*='/f/'], h3 a[href*='/f/'], a.listing__title"
            )
            for link in links:
                href = link.get_attribute("href") or ""
                title = link.inner_text().strip()
                if not href or "/f/" not in href:
                    continue
                post_url = href if href.startswith("http") else f"{reddit_pw.REDDIT_DOMAIN}{href}"
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


@mcp.tool()
async def subscribe_to_forum(forum_name: str) -> Dict[str, Any]:
    """
    Subscribe to a subreddit/forum.

    Args:
        forum_name: Name of the forum to subscribe to

    Returns:
        {"success": bool, "url": str}
    """
    page = _get_page()
    try:
        result = reddit_pw.subscribe_forum(page, forum_name)
        success = getattr(result, "success", False)
        return {
            "success": success,
            "url": page.url,
            "error": getattr(result, "error_message", None),
        }
    except Exception as e:
        return {"success": False, "url": page.url, "error": str(e)}


# Run the server
if __name__ == "__main__":
    import sys
    from pathlib import Path

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
