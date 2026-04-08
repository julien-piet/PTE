#!/usr/bin/env python3
"""
inspect_stale_groundtruth.py

Queries the live GitLab API to find the correct reference answers for
six tasks whose ground truth may be stale:

  Task 136 — commits by Steven Woodson to a11y-webring.club on 2/6/2023
  Task 304 — commits by Eric in a11yproject.com, Feb–May 2023
  Task 307 — commits by Nic in a11yproject.com, April 2021
  Task 784 — email of top committer to Android-IMSI-Catcher-Detector:main
  Task 785 — email of top committer to Android-IMSI-Catcher-Detector:gh-page
  Task 786 — commit count of top committer to vinta/awesome-python:main

Run with the SSH tunnel active (GitLab at localhost:8023):

    python3 eval/inspect_stale_groundtruth.py

Output goes to stdout and to eval/tests/logs/stale_groundtruth_inspect.txt
"""

import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).parent.parent
for p in [str(PROJECT_ROOT), str(PROJECT_ROOT / "eval")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "config" / ".env", override=False)

GITLAB    = os.getenv("GITLAB_URL", "http://localhost:8023")
USERNAME  = os.getenv("GITLAB_USERNAME", "byteblaze")
PASSWORD  = os.getenv("GITLAB_PASSWORD", "hello1234")

LOG_FILE  = PROJECT_ROOT / "eval" / "tests" / "logs" / "stale_groundtruth_inspect.txt"


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def get_token() -> str:
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


def api_get(token: str, path: str, params: dict | None = None) -> list | dict:
    import requests
    resp = requests.get(
        f"{GITLAB}/api/v4{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def api_get_all_pages(token: str, path: str, params: dict | None = None) -> list:
    """Fetch all pages of a paginated GitLab API endpoint."""
    import requests
    results = []
    p = dict(params or {})
    p.setdefault("per_page", 100)
    page = 1
    while True:
        p["page"] = page
        resp = requests.get(
            f"{GITLAB}/api/v4{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=p,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        results.extend(data)
        if len(data) < p["per_page"]:
            break
        page += 1
    return results


def find_project_path(token: str, search_name: str) -> str | None:
    """Search for a project by name and return its path_with_namespace."""
    data = api_get(token, "/projects", {
        "search": search_name,
        "per_page": 10,
        "order_by": "name",
    })
    if isinstance(data, list) and data:
        # Prefer exact name match
        for p in data:
            if p.get("name", "").lower() == search_name.lower():
                return p["path_with_namespace"]
        return data[0]["path_with_namespace"]
    return None


def encode_path(path: str) -> str:
    return quote(path, safe="")


# ---------------------------------------------------------------------------
# Per-task inspection functions
# ---------------------------------------------------------------------------

def inspect_task_136(token: str, log) -> dict:
    """Commits by Steven Woodson to a11y-webring.club on 2/6/2023 (Feb 6)."""
    log("─" * 60)
    log("Task 136: How many commits did Steven Woodson make to a11y-webring.club on 2/6/2023?")
    log("  Expected: 5")

    # Find the project
    proj_path = find_project_path(token, "a11y-webring.club")
    if not proj_path:
        log("  ❌ Project not found")
        return {}
    log(f"  Project path: {proj_path}")

    # Commits by Steven Woodson on Feb 6, 2023
    commits = api_get_all_pages(token, f"/projects/{encode_path(proj_path)}/repository/commits", {
        "since": "2023-02-06T00:00:00Z",
        "until": "2023-02-06T23:59:59Z",
        "per_page": 100,
    })

    # Filter by author name (case-insensitive contains)
    woodson_commits = [
        c for c in commits
        if "woodson" in (c.get("author_name") or "").lower()
        or "woodson" in (c.get("committer_name") or "").lower()
    ]
    all_authors = sorted({c.get("author_name", "") for c in commits})

    log(f"  Total commits on 2023-02-06: {len(commits)}")
    log(f"  All authors that day: {all_authors}")
    log(f"  Commits by Steven Woodson: {len(woodson_commits)}")
    for c in woodson_commits:
        log(f"    [{c['short_id']}] {c['author_name']} — {c['title'][:60]}")

    # Also try without date filter — all Steven Woodson commits
    all_sw = api_get_all_pages(token, f"/projects/{encode_path(proj_path)}/repository/commits", {
        "author": "Steven Woodson",
        "per_page": 100,
    })
    log(f"  All-time commits with author='Steven Woodson': {len(all_sw)}")

    return {"task_id": 136, "actual_count": len(woodson_commits), "project": proj_path}


def inspect_task_304(token: str, log) -> dict:
    """Commits by Eric in a11yproject.com, Feb–May 2023."""
    log("─" * 60)
    log("Task 304: How many commits did Eric make between Feb 2023 and May 2023?")
    log("  Project: a11yproject/a11yproject.com  |  Expected: 14")

    proj = "a11yproject/a11yproject.com"
    commits = api_get_all_pages(token, f"/projects/{encode_path(proj)}/repository/commits", {
        "since": "2023-02-01T00:00:00Z",
        "until": "2023-05-31T23:59:59Z",
        "per_page": 100,
    })

    # Filter by author name containing "eric" (case-insensitive)
    eric_commits = [
        c for c in commits
        if "eric" in (c.get("author_name") or "").lower()
        or "eric" in (c.get("committer_name") or "").lower()
    ]
    all_authors = sorted({c.get("author_name", "") for c in commits})

    log(f"  Total commits Feb–May 2023: {len(commits)}")
    log(f"  All authors in range: {all_authors}")
    log(f"  Commits by 'Eric' (name contains 'eric'): {len(eric_commits)}")
    for c in eric_commits:
        log(f"    [{c['short_id']}] {c['author_name']} — {c.get('authored_date','')[:10]} — {c['title'][:60]}")

    return {"task_id": 304, "actual_count": len(eric_commits), "project": proj}


def inspect_task_307(token: str, log) -> dict:
    """Commits by Nic in a11yproject.com, April 2021."""
    log("─" * 60)
    log("Task 307: How many commits did Nic make in April 2021?")
    log("  Project: a11yproject/a11yproject.com  |  Expected: 16")

    proj = "a11yproject/a11yproject.com"
    commits = api_get_all_pages(token, f"/projects/{encode_path(proj)}/repository/commits", {
        "since": "2021-04-01T00:00:00Z",
        "until": "2021-04-30T23:59:59Z",
        "per_page": 100,
    })

    nic_commits = [
        c for c in commits
        if "nic" in (c.get("author_name") or "").lower()
        or "nic" in (c.get("committer_name") or "").lower()
    ]
    all_authors = sorted({c.get("author_name", "") for c in commits})

    log(f"  Total commits in April 2021: {len(commits)}")
    log(f"  All authors in range: {all_authors}")
    log(f"  Commits by 'Nic' (name contains 'nic'): {len(nic_commits)}")
    for c in nic_commits:
        log(f"    [{c['short_id']}] {c['author_name']} — {c.get('authored_date','')[:10]} — {c['title'][:60]}")

    return {"task_id": 307, "actual_count": len(nic_commits), "project": proj}


def inspect_task_784_785(token: str, log) -> dict:
    """Top committer email for CellularPrivacy/Android-IMSI-Catcher-Detector on main and gh-page."""
    log("─" * 60)
    log("Tasks 784 & 785: Top committer email for Android-IMSI-Catcher-Detector")
    log("  Expected (both): secupwn@users.noreply.github.com")

    proj = "CellularPrivacy/Android-IMSI-Catcher-Detector"
    results = {}

    for branch in ("main", "gh-page"):
        task_id = 784 if branch == "main" else 785
        log(f"\n  Branch: {branch} (Task {task_id})")
        try:
            contributors = api_get_all_pages(
                token,
                f"/projects/{encode_path(proj)}/repository/contributors",
                {"ref": branch, "order_by": "commits", "sort": "desc"},
            )
            if contributors:
                # Sort by commits descending (API should already do this)
                contributors.sort(key=lambda x: x.get("commits", 0), reverse=True)
                top = contributors[0]
                log(f"  Top contributor: {top.get('name')} <{top.get('email')}> — {top.get('commits')} commits")
                log(f"  Top 5:")
                for c in contributors[:5]:
                    log(f"    {c.get('commits'):4d}  {c.get('name')}  <{c.get('email')}>")
                results[task_id] = {
                    "name": top.get("name"),
                    "email": top.get("email"),
                    "commits": top.get("commits"),
                }
            else:
                log(f"  ❌ No contributors returned for branch {branch!r}")
        except Exception as e:
            log(f"  ❌ Error for branch {branch!r}: {e}")

    return results


def inspect_task_786(token: str, log) -> dict:
    """Commit count of top committer to vinta/awesome-python:main."""
    log("─" * 60)
    log("Task 786: Number of commits of top contributor to vinta/awesome-python:main")
    log("  Expected: 412")

    proj = "vinta/awesome-python"
    try:
        contributors = api_get_all_pages(
            token,
            f"/projects/{encode_path(proj)}/repository/contributors",
            {"ref": "main", "order_by": "commits", "sort": "desc"},
        )
        if contributors:
            contributors.sort(key=lambda x: x.get("commits", 0), reverse=True)
            top = contributors[0]
            log(f"  Top contributor: {top.get('name')} <{top.get('email')}> — {top.get('commits')} commits")
            log(f"  Top 5:")
            for c in contributors[:5]:
                log(f"    {c.get('commits'):4d}  {c.get('name')}  <{c.get('email')}>")
            return {"task_id": 786, "actual_count": top.get("commits"), "name": top.get("name")}
        else:
            log("  ❌ No contributors returned")
    except Exception as e:
        log(f"  ❌ Error: {e}")

    return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    output_lines: list[str] = []

    def log(line: str = "") -> None:
        print(line)
        output_lines.append(line)

    log("=" * 60)
    log("GitLab Stale Ground-Truth Inspection")
    log(f"GitLab: {GITLAB}  User: {USERNAME}")
    log("=" * 60)

    try:
        token = get_token()
        log(f"✅ API token acquired\n")
    except Exception as e:
        log(f"❌ Could not get API token: {e}")
        log("Make sure the SSH tunnel is running (GitLab on localhost:8023)")
        return

    results = {}
    results.update({"136": inspect_task_136(token, log)})
    log()
    results.update({"304": inspect_task_304(token, log)})
    log()
    results.update({"307": inspect_task_307(token, log)})
    log()
    r = inspect_task_784_785(token, log)
    results.update({str(k): v for k, v in r.items()})
    log()
    results.update({"786": inspect_task_786(token, log)})

    log()
    log("=" * 60)
    log("SUMMARY — update reference_answers in raw_webarena_tasks_gitlab_readonly.json")
    log("=" * 60)
    log(json.dumps(results, indent=2))

    with open(LOG_FILE, "w") as f:
        f.write("\n".join(output_lines))
    print(f"\n📄 Full output saved to: {LOG_FILE}")


if __name__ == "__main__":
    run()
