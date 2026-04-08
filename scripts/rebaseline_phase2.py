#!/usr/bin/env python3
"""
rebaseline_phase2.py

Restart a GitLab worker container, then query the API to find the correct
reference answers for Phase 2 tasks (173–182) and update the task file.

Phase 2 tasks ask:
  - Tasks 173–177: "latest UPDATED issue with keyword X in its title"
  - Tasks 178–182: "latest CREATED issue with keyword X in its title"

Usage:
    python3 scripts/rebaseline_phase2.py
    python3 scripts/rebaseline_phase2.py --dry-run        # print only, don't write
    python3 scripts/rebaseline_phase2.py --port 8025      # use a different worker
    python3 scripts/rebaseline_phase2.py --no-restart     # skip Docker restart
"""

import argparse
import asyncio
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TASK_FILE = PROJECT_ROOT / "eval" / "tests" / "raw_webarena_tasks_gitlab_readonly.json"

# Remote host that runs the Docker containers
REMOTE_HOST = "sylvie@red5k.cs.berkeley.edu"

# Container name template: worker_N-gitlab-1
def container_name(worker_id: int) -> str:
    return f"worker_{worker_id}-gitlab-1"

# Phase 2 task spec: task_id → (keyword, sort_field)
PHASE2_TASKS = {
    173: ("better",         "updated_at"),
    174: ("feature",        "updated_at"),
    175: ("dependency",     "updated_at"),
    176: ("theme editor",   "updated_at"),
    177: ("homepage content","updated_at"),
    178: ("better",         "created_at"),
    179: ("feature",        "created_at"),
    180: ("dependency",     "created_at"),
    181: ("theme editor",   "created_at"),
    182: ("homepage content","created_at"),
}

BYTEBLAZE_USERNAME = "byteblaze"
BYTEBLAZE_PASSWORD = "hello1234"


# ---------------------------------------------------------------------------
# Docker restart
# ---------------------------------------------------------------------------

def restart_container(worker_id: int) -> None:
    name = container_name(worker_id)
    print(f"🔄 Restarting container {name} on {REMOTE_HOST}...")
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", REMOTE_HOST, f"docker restart {name}"],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"docker restart failed: {result.stderr.strip()}"
        )
    print(f"   ✅ Container restarted.")


def wait_for_healthy(port: int, timeout: int = 360, interval: float = 5.0) -> None:
    url = f"http://127.0.0.1:{port}/api/v4/version"
    deadline = time.time() + timeout
    print(f"⏳ Waiting for GitLab at localhost:{port} to become healthy...")
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=5)
            # 200 → ready
            print(f"   ✅ GitLab is up.")
            return
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                # Auth-gated response means the server is up
                print(f"   ✅ GitLab is up (HTTP {e.code}).")
                return
        except Exception:
            pass
        time.sleep(interval)
    raise TimeoutError(f"GitLab at localhost:{port} did not become healthy within {timeout}s")


# ---------------------------------------------------------------------------
# PAT creation (Playwright)
# ---------------------------------------------------------------------------

def create_pat(port: int) -> str:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    gitlab_url = f"http://127.0.0.1:{port}"
    print(f"🔑 Creating PAT for localhost:{port}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(f"{gitlab_url}/users/sign_in", wait_until="networkidle")
        page.fill("#user_login", BYTEBLAZE_USERNAME)
        page.fill("#user_password", BYTEBLAZE_PASSWORD)
        page.locator('button[type="submit"]').click()
        page.wait_for_load_state("networkidle")

        page.goto(f"{gitlab_url}/-/profile/personal_access_tokens", wait_until="networkidle")
        page.locator("#personal_access_token_name").fill("rebaseline-runner")

        label = page.locator("label[for='personal_access_token_scopes_api']")
        if label.count() > 0:
            label.click()
        else:
            page.locator("#personal_access_token_scopes_api").click(force=True)

        submit = page.locator(
            "button:has-text('Create personal access token'), input[name='commit']"
        ).first
        submit.click()
        page.wait_for_load_state("networkidle")

        try:
            page.wait_for_selector("[data-clipboard-text^='glpat-']", timeout=5000, state="attached")
            clip = page.locator("[data-clipboard-text^='glpat-']").first
            token = clip.get_attribute("data-clipboard-text") or ""
        except PWTimeout:
            token_el = page.locator("#created-personal-access-token")
            token = token_el.get_attribute("value") or token_el.inner_text()

        browser.close()

    token = token.strip()
    print(f"   ✅ PAT: {token[:12]}...")
    return token


# ---------------------------------------------------------------------------
# API queries
# ---------------------------------------------------------------------------

def api_get(port: int, token: str, path: str) -> dict:
    url = f"http://127.0.0.1:{port}/api/v4{path}"
    req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": token})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def get_byteblaze_id(port: int, token: str) -> int:
    user = api_get(port, token, "/user")
    return user["id"]


def find_issue(port: int, token: str, user_id: int, keyword: str, sort_field: str) -> dict | None:
    """
    Find the most recently updated/created issue that belongs to the user
    (assigned_to OR authored_by) and whose TITLE contains keyword.

    "My issues" in GitLab UI means issues assigned to me, so we try
    assignee_id first, then author_id, and take the winner by sort_field.
    """
    import urllib.parse

    # For multi-word keywords (e.g. "homepage content"), search the first word
    # only (to avoid phrase-match failures like "homepage's content") and then
    # filter client-side so ALL words appear somewhere in the title.
    search_term = keyword.split()[0]
    words = keyword.lower().split()

    def title_matches(title: str) -> bool:
        t = title.lower()
        return all(w in t for w in words)

    def fetch(filter_key: str) -> list:
        params = urllib.parse.urlencode({
            filter_key:   user_id,
            "search":     search_term,
            "in":         "title",
            "order_by":   sort_field,
            "sort":       "desc",
            "per_page":   50,
            "scope":      "all",
        })
        results = api_get(port, token, f"/issues?{params}")
        return [i for i in results if title_matches(i.get("title", ""))]

    assignee_results = fetch("assignee_id")
    author_results   = fetch("author_id")

    # Merge and deduplicate by id
    seen = set()
    combined = []
    for issue in assignee_results + author_results:
        if issue["id"] not in seen:
            seen.add(issue["id"])
            combined.append(issue)

    if not combined:
        return None

    # Sort by the relevant timestamp field descending
    ts_key = "updated_at" if sort_field == "updated_at" else "created_at"
    combined.sort(key=lambda i: i.get(ts_key, ""), reverse=True)
    return combined[0]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Re-baseline Phase 2 reference answers.")
    parser.add_argument("--port", type=int, default=8024, help="Worker port (default: 8024)")
    parser.add_argument("--dry-run", action="store_true", help="Print proposed changes without writing")
    parser.add_argument("--no-restart", action="store_true", help="Skip Docker container restart")
    args = parser.parse_args()

    worker_id = args.port - 8023   # port 8024 → worker_id 1

    # Step 1: restart
    if not args.no_restart:
        restart_container(worker_id)
        wait_for_healthy(args.port)
    else:
        print(f"⏭️  Skipping restart (--no-restart). Assuming localhost:{args.port} is up.")

    # Step 2: create PAT
    token = create_pat(args.port)

    # Step 3: get byteblaze's user ID
    user_id = get_byteblaze_id(args.port, token)
    print(f"\n👤 byteblaze user_id = {user_id}\n")

    # Step 4: query for each Phase 2 task
    proposed: dict[int, dict] = {}   # task_id → new reference_answers

    print(f"{'─'*70}")
    print(f"{'Task':>6}  {'Sort by':<12}  {'Keyword':<18}  Result")
    print(f"{'─'*70}")

    for task_id, (keyword, sort_field) in PHASE2_TASKS.items():
        issue = find_issue(args.port, token, user_id, keyword, sort_field)

        if issue is None:
            print(f"{task_id:>6}  {sort_field:<12}  {keyword!r:<18}  ⚠️  NOT FOUND")
            proposed[task_id] = {"must_include": [f"NOT_FOUND:{keyword}"]}
        else:
            title  = issue["title"]
            state  = issue["state"]   # "opened" or "closed"
            iid    = issue["iid"]
            proj   = issue.get("references", {}).get("full", "")
            status = "open" if state == "opened" else "closed"

            print(f"{task_id:>6}  {sort_field:<12}  {keyword!r:<18}  "
                  f"[{state}] #{iid} {title!r}  ({proj})")
            proposed[task_id] = {"must_include": [title, status]}

    print(f"{'─'*70}\n")

    # Step 5: display / apply changes
    if args.dry_run:
        print("🔍 DRY RUN — proposed reference_answers updates:")
        for tid, ref in proposed.items():
            print(f"  Task {tid}: {ref}")
        print("\n(No changes written. Remove --dry-run to apply.)")
        return

    # Load task file
    with open(TASK_FILE) as f:
        tasks = json.load(f)

    updated = 0
    for task in tasks:
        tid = task["task_id"]
        if tid in proposed:
            old = task["eval"].get("reference_answers", {})
            new = proposed[tid]
            if old != new:
                task["eval"]["reference_answers"] = new
                print(f"  Task {tid}: {old}  →  {new}")
                updated += 1

    if updated == 0:
        print("Nothing changed — reference answers already match.")
        return

    with open(TASK_FILE, "w") as f:
        json.dump(tasks, f, indent=2)

    print(f"\n✅ Updated {updated} task(s) in {TASK_FILE.name}")


if __name__ == "__main__":
    sys.path.insert(0, str(PROJECT_ROOT))
    main()
