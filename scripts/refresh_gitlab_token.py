"""
Refresh the GITLAB_TOKEN in config/.server_env.

Usage:
    python3 scripts/refresh_gitlab_token.py

Logs in as byteblaze, creates a new PAT named 'benchmark-runner',
and overwrites GITLAB_TOKEN in config/.server_env.

Run this whenever the agent gets HTTP 401 from GitLab.
"""

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).parent.parent
SERVER_ENV = PROJECT_ROOT / "config" / ".server_env"

GITLAB_URL = "http://localhost:8023"
USERNAME = "byteblaze"
PASSWORD = "hello1234"
TOKEN_NAME = "benchmark-runner"


def refresh_token() -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Login
        page.goto(f"{GITLAB_URL}/users/sign_in", wait_until="networkidle")
        page.fill("#user_login", USERNAME)
        page.fill("#user_password", PASSWORD)
        page.locator('button[type="submit"]').click()
        page.wait_for_load_state("networkidle")
        print(f"  Logged in: {page.url}")

        # Import after path is set up
        sys.path.insert(0, str(PROJECT_ROOT))
        from api.gitlab_pw.settings import create_access_token

        result = create_access_token(page, name=TOKEN_NAME, scopes=["api"])
        browser.close()

    if not result.success:
        raise RuntimeError(f"Failed to create token: {result.error_message}")

    return result.token


def update_server_env(token: str) -> None:
    content = SERVER_ENV.read_text() if SERVER_ENV.exists() else ""
    if re.search(r"^GITLAB_TOKEN=", content, re.MULTILINE):
        content = re.sub(r"^GITLAB_TOKEN=.*$", f"GITLAB_TOKEN={token}", content, flags=re.MULTILINE)
    else:
        content = content.rstrip("\n") + f"\nGITLAB_TOKEN={token}\n"
    SERVER_ENV.write_text(content)
    print(f"  Updated {SERVER_ENV}")


if __name__ == "__main__":
    print("Refreshing GitLab token...")
    token = refresh_token()
    print(f"  New token: {token}")
    update_server_env(token)
    print("Done.")
