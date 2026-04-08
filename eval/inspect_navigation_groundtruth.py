#!/usr/bin/env python3
"""
inspect_navigation_groundtruth.py

Logs into GitLab as byteblaze, navigates to each Phase 1 navigation task URL
(both the browser page and the equivalent API endpoint), and prints the content
so you can determine the correct `must_include` strings for string_match eval.

Run this once with the SSH tunnel active (GitLab at localhost:8023):

    python3 eval/inspect_navigation_groundtruth.py

Output goes to stdout and also to eval/tests/logs/navigation_groundtruth_inspect.txt
"""

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

PROJECT_ROOT = Path(__file__).parent.parent
for p in [str(PROJECT_ROOT), str(PROJECT_ROOT / "eval")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "config" / ".env", override=False)

GITLAB = os.getenv("GITLAB_URL", "http://localhost:8023")
USERNAME = os.getenv("GITLAB_USERNAME", "byteblaze")
PASSWORD = os.getenv("GITLAB_PASSWORD", "hello1234")

LOG_FILE = PROJECT_ROOT / "eval" / "tests" / "logs" / "navigation_groundtruth_inspect.txt"

# ---------------------------------------------------------------------------
# Navigation tasks — these are the 8 tasks that need real content inspection
# (label-filtered issue tasks already have clear must_include strings)
# ---------------------------------------------------------------------------
NAV_TASKS = {
    44: {
        "intent": "Check out my todos",
        "reference_url": f"{GITLAB}/dashboard/todos",
        "api_path": "/todos?state=pending",
        "description": "List of pending todos for byteblaze",
    },
    45: {
        "intent": "Check out the most recent open issues (a11yproject.com)",
        "reference_url": f"{GITLAB}/a11yproject/a11yproject.com/-/issues/?sort=created_asc&state=opened",
        "api_path": "/projects/a11yproject%2Fa11yproject.com/issues?state=opened&order_by=created_at&sort=asc&per_page=10",
        "description": "Open issues in a11yproject.com sorted by created asc (oldest first)",
    },
    46: {
        "intent": "Check out the most recent open issues (primer/design)",
        "reference_url": f"{GITLAB}/primer/design/-/issues/?sort=created_date&state=opened",
        "api_path": "/projects/primer%2Fdesign/issues?state=opened&order_by=created_at&sort=desc&per_page=10",
        "description": "Open issues in primer/design sorted by created_date (newest first)",
    },
    156: {
        "intent": "Checkout merge requests assigned to me",
        "reference_url": f"{GITLAB}/dashboard/merge_requests?assignee_username=byteblaze",
        "api_path": "/merge_requests?scope=all&state=opened&assignee_username=byteblaze",
        "description": "Open MRs assigned to byteblaze",
    },
    258: {
        "intent": "See all public projects",
        "reference_url": f"{GITLAB}/explore",
        "api_path": "/projects?visibility=public&order_by=name&sort=asc&per_page=20",
        "description": "All public projects",
    },
    343: {
        "intent": "List all opened issues that don't have any labels (metaseq)",
        "reference_url": f"{GITLAB}/root/metaseq/-/issues/?label_name%5B%5D=None",
        "api_path": "/projects/root%2Fmetaseq/issues?state=opened&labels=None&per_page=10",
        "description": "Open issues in metaseq with no labels",
    },
    357: {
        "intent": "Checkout merge requests requiring my review",
        "reference_url": f"{GITLAB}/dashboard/merge_requests?reviewer_username=byteblaze",
        "api_path": "/merge_requests?scope=all&state=opened&reviewer_username=byteblaze",
        "description": "Open MRs where byteblaze is reviewer",
    },
}


def get_token() -> str:
    """Get a GitLab API token via OAuth password grant."""
    import requests
    resp = requests.post(
        f"{GITLAB}/oauth/token",
        json={
            "grant_type": "password",
            "username": USERNAME,
            "password": PASSWORD,
            "scope": "api",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def api_get(token: str, path: str) -> list | dict:
    """Make a GET request to the GitLab API."""
    import requests
    resp = requests.get(
        f"{GITLAB}/api/v4{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def inspect_page(page, url: str) -> str:
    """Navigate to a URL and return the #content-body text."""
    page.goto(url, wait_until="networkidle", timeout=20000)
    el = page.query_selector("#content-body")
    return el.inner_text() if el else page.inner_text("body")


def summarise_api_result(data: list | dict, task_id: int) -> str:
    """Format API result into readable text."""
    if isinstance(data, dict):
        return json.dumps(data, indent=2)[:2000]

    lines = []
    for i, item in enumerate(data[:15]):
        if task_id == 44:  # todos
            action = item.get("action_name", "")
            body = item.get("body", "")
            target = item.get("target", {})
            target_title = target.get("title", "") if isinstance(target, dict) else ""
            project = item.get("project", {})
            project_name = project.get("path_with_namespace", "") if isinstance(project, dict) else ""
            lines.append(f"  [{i+1}] action={action!r} body={body[:60]!r} target_title={target_title!r} project={project_name!r}")
        elif task_id in (156, 357):  # MRs
            title = item.get("title", "")
            iid = item.get("iid", "")
            proj = item.get("references", {}).get("full", item.get("web_url", ""))
            lines.append(f"  [{i+1}] !{iid} {title!r}  ({proj})")
        elif task_id == 258:  # projects
            name = item.get("path_with_namespace", item.get("name", ""))
            vis = item.get("visibility", "")
            lines.append(f"  [{i+1}] {name!r} ({vis})")
        else:  # issues
            iid = item.get("iid", "")
            title = item.get("title", "")
            labels = item.get("labels", [])
            lines.append(f"  [{i+1}] #{iid} {title!r}  labels={labels}")

    if len(data) > 15:
        lines.append(f"  ... ({len(data) - 15} more items)")
    return "\n".join(lines)


def run() -> None:
    from playwright.sync_api import sync_playwright

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    output_lines = []

    def log(line: str = "") -> None:
        print(line)
        output_lines.append(line)

    log("=" * 70)
    log("GitLab Navigation Task — Ground Truth Inspection")
    log(f"GitLab: {GITLAB}  User: {USERNAME}")
    log("=" * 70)

    # ---- Get API token ----
    try:
        token = get_token()
        log(f"✅ API token acquired\n")
    except Exception as e:
        log(f"❌ Could not get API token: {e}")
        log("Make sure the SSH tunnel is running (GitLab on localhost:8023)")
        return

    # ---- Browser login ----
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{GITLAB}/users/sign_in", wait_until="networkidle", timeout=15000)
        page.fill("#user_login", USERNAME)
        page.fill("#user_password", PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        log(f"✅ Browser logged in (current URL: {page.url})\n")

        for task_id, meta in NAV_TASKS.items():
            log("-" * 70)
            log(f"Task {task_id}: {meta['intent']}")
            log(f"  reference_url: {meta['reference_url']}")
            log(f"  description  : {meta['description']}")
            log()

            # --- API result ---
            try:
                data = api_get(token, meta["api_path"])
                count = len(data) if isinstance(data, list) else 1
                log(f"  API ({meta['api_path']}) → {count} item(s):")
                log(summarise_api_result(data, task_id))
            except Exception as e:
                log(f"  ❌ API error: {e}")

            log()

            # --- Browser page content ---
            try:
                content = inspect_page(page, meta["reference_url"])
                log(f"  Browser page (#content-body) snippet:")
                log("  " + "\n  ".join(content[:1500].splitlines()))
            except Exception as e:
                log(f"  ❌ Page navigation error: {e}")

            log()

        browser.close()

    log("=" * 70)
    log("SUGGESTED must_include VALUES")
    log("=" * 70)
    log("""
After reviewing the output above, update STRING_MATCH_REFERENCE_ANSWERS in
the JSON conversion script with specific strings that:
  1. Appear in the agent's API-based text response
  2. Are stable across docker resets (same data every time)
  3. Are specific enough to confirm the agent did the right thing

Examples of good must_include strings:
  - For todos:         a specific todo title or target issue name
  - For issue lists:   a specific issue title (#NN) that's always in the list
  - For MR lists:      a specific MR title or branch name
  - For public projects: a specific well-known project name
""")

    # Write log
    with open(LOG_FILE, "w") as f:
        f.write("\n".join(output_lines))
    print(f"\n📄 Full output saved to: {LOG_FILE}")


if __name__ == "__main__":
    run()
