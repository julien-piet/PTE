import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Optional

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from playwright.sync_api import sync_playwright

from api.gitlab_pw import get_default_gitlab_credentials, login_user, get_rss_token, reset_rss_token

app = FastAPI(
    title="GitLab Extra API",
    description="Custom endpoints for GitLab that aren't covered by the REST API (e.g. RSS/feed token).",
    version="1.0.0",
)


def _make_browser_page(playwright):
    """Create a browser page authenticated as the default GitLab user."""
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    username, password = get_default_gitlab_credentials()
    login_result = login_user(page, username, password)
    if not login_result.success:
        browser.close()
        raise RuntimeError(f"Login failed: {login_result.error_message or 'Unknown error'}")
    return browser, page


class RssTokenResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    error_message: Optional[str] = None


@app.get("/rss_token", response_model=RssTokenResponse)
def rss_token() -> RssTokenResponse:
    """Read the current user's RSS/feed token from their profile page."""
    with sync_playwright() as p:
        try:
            browser, page = _make_browser_page(p)
        except RuntimeError as exc:
            return RssTokenResponse(success=False, error_message=str(exc))
        try:
            result = get_rss_token(page)
            return RssTokenResponse(success=result.success, token=result.token, error_message=result.error_message)
        finally:
            browser.close()


@app.post("/reset_rss_token", response_model=RssTokenResponse)
def reset_rss_token_endpoint() -> RssTokenResponse:
    """Reset (regenerate) the current user's RSS/feed token and return the new value."""
    with sync_playwright() as p:
        try:
            browser, page = _make_browser_page(p)
        except RuntimeError as exc:
            return RssTokenResponse(success=False, error_message=str(exc))
        try:
            result = reset_rss_token(page)
            return RssTokenResponse(success=result.success, token=result.token, error_message=result.error_message)
        finally:
            browser.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7792)
