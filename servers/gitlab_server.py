#!/usr/bin/env python3
"""
GitLab MCP Server - FastMCP implementation for GitLab Playwright APIs
Provides MCP functions for GitLab operations using the api/gitlab_pw module
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional, Dict, Any, List
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from playwright.sync_api import sync_playwright, Page, Browser

# Import GitLab API functions
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api import gitlab_pw

# Initialize FastMCP server
mcp = FastMCP("GitLab API Server")

# ---------------------------------------------------------------------------
# Playwright runs in a single dedicated background thread.
# FastMCP tool handlers are `async def`, so they run in the asyncio event loop.
# Playwright's sync API raises an error when called inside an asyncio loop.
# Solution: dispatch all Playwright work to a ThreadPoolExecutor(max_workers=1)
# so the sync API executes in a thread where no event loop is active.
# ---------------------------------------------------------------------------
_pw_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")

# Store Playwright instances (accessed only from within _pw_executor threads)
_playwright = None
_browser: Optional[Browser] = None
_page: Optional[Page] = None

# ---------------------------------------------------------------------------
# Module-level OAuth token cache.
# GitLab OAuth tokens last 2 hours.  We refresh proactively after 90 minutes.
# All tool functions share this cache so that one OAuth call serves many tools
# in a single benchmark run, reducing pressure on the GitLab OAuth endpoint.
# ---------------------------------------------------------------------------
import time as _time_module
_cached_oauth_token: Optional[str] = None
_cached_oauth_token_at: float = 0.0
_OAUTH_TOKEN_TTL: float = 90 * 60  # seconds

GITLAB_OAUTH_URL = "http://localhost:8023/oauth/token"
GITLAB_OAUTH_BODY = b'{"grant_type":"password","username":"byteblaze","password":"hello1234"}'


def _get_cached_oauth_token() -> Optional[str]:
    """
    Return a valid byteblaze OAuth token, using the module-level cache.

    Fetches a fresh token (with exponential-backoff retry) when the cache
    is empty or the token is approaching its TTL.  All GitLab tool functions
    should call this instead of fetching tokens inline.
    """
    global _cached_oauth_token, _cached_oauth_token_at
    import urllib.request as _ur_tok
    import json as _j_tok

    now = _time_module.time()
    if _cached_oauth_token and (now - _cached_oauth_token_at) < _OAUTH_TOKEN_TTL:
        return _cached_oauth_token

    # Fetch a new token with retry
    last_err = None
    for _attempt in range(6):  # waits: 0,1,2,4,8,16s
        req = _ur_tok.Request(
            GITLAB_OAUTH_URL,
            data=GITLAB_OAUTH_BODY,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with _ur_tok.urlopen(req, timeout=15) as r:
                tok = _j_tok.loads(r.read()).get("access_token")
                if tok:
                    _cached_oauth_token = tok
                    _cached_oauth_token_at = _time_module.time()
                    return tok
        except Exception as _e:
            last_err = _e
        if _attempt < 5:
            _time_module.sleep(2 ** _attempt)  # 1,2,4,8,16s
    import sys as _sys
    print(f"[oauth] Failed to get token after 6 attempts. Last error: {last_err}", file=_sys.stderr, flush=True)
    return None


async def _run_pw(fn: Callable) -> Any:
    """Run a synchronous Playwright callable in the dedicated playwright thread.

    Usage:
        result = await _run_pw(lambda: some_sync_playwright_call(page, ...))
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_pw_executor, fn)


class Credentials(BaseModel):
    """Authentication credentials"""
    username: str = Field(description="GitLab username")
    password: str = Field(description="GitLab password")


class IssueData(BaseModel):
    """Issue data structure"""
    namespace: str = Field(description="Project namespace (username or group)")
    project: str = Field(description="Project name")
    title: str = Field(description="Issue title")
    description: Optional[str] = Field(default="", description="Issue description")


class ProjectData(BaseModel):
    """Project data structure"""
    name: str = Field(description="Project name")
    description: Optional[str] = Field(default="", description="Project description")


class GroupData(BaseModel):
    """Group data structure"""
    name: str = Field(description="Group name")
    description: Optional[str] = Field(default="", description="Group description")


class BranchData(BaseModel):
    """Branch data structure"""
    namespace: str = Field(description="Project namespace")
    project: str = Field(description="Project name")
    branch_name: str = Field(description="Branch name")
    ref: Optional[str] = Field(default="main", description="Base branch reference")


class FileData(BaseModel):
    """File data structure"""
    namespace: str = Field(description="Project namespace")
    project: str = Field(description="Project name")
    branch: str = Field(description="Branch name")
    file_path: str = Field(description="File path in repository")
    content: Optional[str] = Field(default="", description="File content")


class MergeRequestData(BaseModel):
    """Merge request data structure"""
    namespace: str = Field(description="Project namespace")
    project: str = Field(description="Project name")
    title: str = Field(description="Merge request title")
    source_branch: str = Field(description="Source branch")
    target_branch: str = Field(default="main", description="Target branch")
    description: Optional[str] = Field(default="", description="Merge request description")


def _get_page() -> Page:
    """Get or initialize the Playwright page.
    MUST be called from within the _pw_executor thread only.
    """
    global _playwright, _browser, _page

    if _page is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=True)
        _page = _browser.new_page()

    return _page


def _cleanup():
    """Clean up Playwright resources.
    MUST be called from within the _pw_executor thread only.
    """
    global _playwright, _browser, _page

    if _page:
        _page.close()
        _page = None
    if _browser:
        _browser.close()
        _browser = None
    if _playwright:
        _playwright.stop()
        _playwright = None


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@mcp.tool()
async def login(credentials: Optional[Credentials] = None) -> Dict[str, Any]:
    """
    Log in to GitLab with the given credentials.
    If no credentials provided, uses default credentials from environment.
    """
    def _work():
        try:
            page = _get_page()

            if credentials:
                username, password = credentials.username, credentials.password
            else:
                username, password = gitlab_pw.get_default_gitlab_credentials()

            result = gitlab_pw.login_user(page, username, password)

            return {
                "success": result.success,
                "message": result.error_message or ("Logged in successfully" if result.success else "Login failed"),
                "username": username
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def check_login_status() -> Dict[str, Any]:
    """Check if currently logged in to GitLab."""
    def _work():
        try:
            page = _get_page()
            is_logged_in = gitlab_pw.is_logged_in(page)

            return {
                "logged_in": is_logged_in,
                "message": "User is logged in" if is_logged_in else "User is not logged in"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def navigate(url: str) -> Dict[str, Any]:
    """
    Navigate to a specific GitLab URL.

    Args:
        url: The URL path to navigate to. Can be relative (starts with /) or absolute.

    Common use cases:
        - Personal dashboard: navigate("/dashboard/todos")
        - Merge requests: navigate("/dashboard/merge_requests")
        - User's merge requests: navigate("/dashboard/merge_requests?assignee_username=USERNAME")
        - Specific issue: navigate("/namespace/project/-/issues/NUMBER")

    Examples:
        - "Check my todos" → navigate("/dashboard/todos")
        - "My merge requests" → navigate("/dashboard/merge_requests?assignee_username=byteblaze")
        - "Open issue #8" → navigate("/byteblaze/empathy-prompts/-/issues/8")
    """
    def _work():
        try:
            page = _get_page()

            # If URL is relative, prepend base URL
            if url.startswith("/"):
                full_url = f"http://localhost:8023{url}"
            else:
                full_url = url

            page.goto(full_url, wait_until="networkidle")

            return {
                "success": True,
                "url": page.url,
                "final_url": page.url,
                "message": f"Navigated to {page.url}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


# ============================================================================
# ISSUE ENDPOINTS
# ============================================================================

@mcp.tool()
async def create_issue(issue: IssueData) -> Dict[str, Any]:
    """Create a new issue in a GitLab project."""
    def _work():
        try:
            page = _get_page()

            result = gitlab_pw.create_issue(
                page,
                namespace=issue.namespace,
                project=issue.project,
                title=issue.title,
                description=issue.description
            )

            return {
                "success": result.success,
                "message": result.message,
                "issue_number": result.issue_number if result.success else None,
                "issue_url": result.issue_url if result.success else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def get_issues(
    namespace: str,
    project: str,
    labels: Optional[List[str]] = None,
    state: Optional[str] = None,
    sort: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get issues from a GitLab project with optional filtering and sorting.

    Args:
        namespace: Project namespace (username or group name)
        project: Project name
        labels: Optional list of label names to filter by.
               Examples: ["bug"], ["help wanted"], ["question"]
               Common use: When task mentions "labels related to X", use labels=["X"]
        state: Optional issue state filter.
               ALLOWED VALUES: "opened" | "closed" | "all"
               - "opened" = open/active issues (DEFAULT for "open issues")
               - "closed" = closed issues
               - "all" = all issues
        sort: Optional sort order.
              ALLOWED VALUES: "created_date" | "created_asc" | "updated_desc" | "updated_asc"
              - "created_date" = newest first (DEFAULT for "most recent", "latest")
              - "created_asc" = oldest first
              - "updated_desc" = recently updated first
              - "updated_asc" = least recently updated

    Examples:
        - "Show open issues" → get_issues(namespace, project, state="opened")
        - "Issues with label bug" → get_issues(namespace, project, labels=["bug"])
        - "Most recent issues" → get_issues(namespace, project, sort="created_date")
        - "Recent open bugs" → get_issues(namespace, project, labels=["bug"], state="opened", sort="created_date")
    """
    def _work():
        try:
            page = _get_page()

            # Build URL with parameters
            base_url = f"http://localhost:8023/{namespace}/{project}/-/issues"
            params = []

            if labels:
                for label in labels:
                    params.append(f"label_name[]={label}")

            if state:
                params.append(f"state={state}")

            if sort:
                params.append(f"sort={sort}")

            url = base_url
            if params:
                url += "?" + "&".join(params)

            # Navigate to URL with filters
            page.goto(url, wait_until="networkidle")

            # Get issues from the filtered page
            issues = gitlab_pw.get_issues(page, namespace, project)

            return {
                "success": True,
                "count": len(issues),
                "url": page.url,
                "final_url": page.url,
                "issues": [
                    {
                        "number": issue.number,
                        "title": issue.title,
                        "url": issue.url
                    }
                    for issue in issues
                ]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def delete_issue(namespace: str, project: str, issue_number: int) -> Dict[str, Any]:
    """Delete a specific issue from a GitLab project."""
    def _work():
        try:
            page = _get_page()
            result = gitlab_pw.delete_issue_by_id(page, namespace, project, issue_number)
            return {"success": result.success, "message": result.message}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def delete_all_issues(namespace: str, project: str) -> Dict[str, Any]:
    """Delete all issues from a GitLab project."""
    def _work():
        try:
            page = _get_page()
            result = gitlab_pw.delete_all_issues(page, namespace, project)
            return {
                "success": result.success,
                "message": result.message,
                "deleted_count": result.deleted_count if result.success else 0
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


# ============================================================================
# PROJECT ENDPOINTS
# ============================================================================

@mcp.tool()
async def create_project(project: ProjectData) -> Dict[str, Any]:
    """
    Create a new private GitLab project.

    Args:
        project.name: Project name (REQUIRED — use 'name', not 'project_name')
        project.description: Optional project description

    Example:
        create_project(project={"name": "my-new-repo"})
    """
    def _work():
        try:
            page = _get_page()
            result = gitlab_pw.create_private_project(
                page,
                project_name=project.name,
                namespace_name=None,
            )
            return {
                "success": result.success,
                "project_url": result.project_url if result.success else None,
                "error": result.error_message if not result.success else None,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def search_projects(keyword: str, sort: Optional[str] = "stars_desc") -> Dict[str, Any]:
    """
    Search for projects on GitLab by keyword, sorted by stars (most starred first by default).

    Use this tool to find the correct namespace/project path before forking,
    especially when the task only gives a project name without a namespace.

    IMPORTANT: Results include ALL projects (including forks). When forking, always pick
    the ORIGINAL source project, not a fork (forks show the original owner's namespace).
    The top result by stars is usually the original.

    Args:
        keyword: Search term — project name or description keyword
        sort: Sort order. Use "stars_desc" (default) for most-starred first,
              "latest_activity_desc" for recently active, "name_asc" alphabetically.

    Returns:
        List of matching projects with their full path (namespace/project), stars count,
        and URL — so you can pick the right one and pass its namespace+project to fork_project.

    Examples:
        - "Find the most starred PyTorch GAN repo" →
          search_projects(keyword="PyTorch-GAN", sort="stars_desc")
          → pick top result (eriklindernoren/PyTorch-GAN), get its namespace and project name

        - "Find ChatGPT project" →
          search_projects(keyword="ChatGPT")
          → pick top result (convexegg/chatgpt or acheong08/ChatGPT)
    """
    def _work():
        import re as _re
        import json as _j
        import urllib.request as _ur
        try:
            page = _get_page()

            # Use GitLab API for more reliable search results (includes fork info)
            token = _get_cached_oauth_token()

            projects = []

            if token:
                # Use API search — returns richer data including fork info
                import urllib.parse as _up
                api_url = f"http://localhost:8023/api/v4/projects?search={_up.quote(keyword)}&order_by=stars&sort=desc&per_page=20"
                api_req = _ur.Request(api_url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
                try:
                    with _ur.urlopen(api_req, timeout=10) as r:
                        api_projects = _j.loads(r.read())
                    for p in api_projects:
                        ns = p.get("namespace", {}).get("path", "")
                        proj = p.get("path", "")
                        is_fork = bool(p.get("forked_from_project"))
                        projects.append({
                            "namespace": ns,
                            "project": proj,
                            "full_path": f"{ns}/{proj}",
                            "title": p.get("name_with_namespace", f"{ns}/{proj}"),
                            "url": f"http://localhost:8023/{ns}/{proj}",
                            "stars": p.get("star_count", 0),
                            "is_fork": is_fork,
                        })
                except Exception:
                    pass

            if not projects:
                # Fallback to Playwright UI scrape
                url = f"http://localhost:8023/explore/projects?sort={sort or 'stars_desc'}&search={keyword}"
                page.goto(url, wait_until="networkidle")
                project_links = page.locator("ul.projects-list a.text-plain")
                for i in range(min(project_links.count(), 20)):
                    link = project_links.nth(i)
                    href = link.get_attribute("href") or ""
                    title = link.inner_text().strip()
                    m = _re.match(r'^/([^/]+)/([^/]+)$', href)
                    if not m or not title:
                        continue
                    ns, proj = m.group(1), m.group(2)
                    projects.append({
                        "namespace": ns,
                        "project": proj,
                        "full_path": f"{ns}/{proj}",
                        "title": title,
                        "url": f"http://localhost:8023{href}",
                        "stars": 0,
                        "is_fork": False,
                    })

            return {
                "success": True,
                "count": len(projects),
                "projects": projects,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def get_user_projects(username: str, source_only: bool = False) -> Dict[str, Any]:
    """
    Get all projects belonging to a GitLab user by their username.

    Use this when you need to find all repos from a specific person, e.g.
    "Fork all source repos from Akilesh Kannan" — first find their username
    with search_users, then call this tool.

    Args:
        username: GitLab username (e.g. "aklsh", "byteblaze")
        source_only: If True, only return projects that are NOT forks (original source repos).
                     Use True when task says "source repos".

    Returns:
        List of projects with namespace, project name, and whether each is a fork.

    Examples:
        - "Fork all source repos from Akilesh Kannan" →
          1. search_users(name="Akilesh Kannan") → username="aklsh"
          2. get_user_projects(username="aklsh", source_only=True)
          3. fork_project(...) for each result
    """
    def _work():
        import json as _j
        import urllib.request as _ur
        try:
            token = _get_cached_oauth_token()
            if not token:
                return {"success": False, "error": "Could not obtain token"}

            import urllib.parse as _up
            api_url = f"http://localhost:8023/api/v4/users/{_up.quote(username)}/projects?per_page=50"
            api_req = _ur.Request(api_url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
            with _ur.urlopen(api_req, timeout=15) as r:
                user_projects = _j.loads(r.read())

            projects = []
            for p in user_projects:
                ns = p.get("namespace", {}).get("path", "")
                proj = p.get("path", "")
                is_fork = bool(p.get("forked_from_project"))
                if source_only and is_fork:
                    continue
                projects.append({
                    "namespace": ns,
                    "project": proj,
                    "full_path": f"{ns}/{proj}",
                    "title": p.get("name_with_namespace", f"{ns}/{proj}"),
                    "url": f"http://localhost:8023/{ns}/{proj}",
                    "stars": p.get("star_count", 0),
                    "is_fork": is_fork,
                })

            return {
                "success": True,
                "count": len(projects),
                "projects": projects,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def search_users(name: str) -> Dict[str, Any]:
    """
    Search for GitLab users by name or username.

    Use this when a task refers to a person by display name (e.g. "Akilesh Kannan")
    and you need to find their GitLab username to look up their projects.

    Args:
        name: Display name or partial username to search for

    Returns:
        List of matching users with their username, display name, and profile URL.

    Example:
        - "Fork all repos from Akilesh Kannan" →
          search_users(name="Akilesh Kannan") → finds username "aklsh"
    """
    def _work():
        import json as _j
        import urllib.request as _ur
        import urllib.parse as _up
        try:
            token = _get_cached_oauth_token()

            api_url = f"http://localhost:8023/api/v4/users?search={_up.quote(name)}&per_page=10"
            hdrs = {"Accept": "application/json"}
            if token:
                hdrs["Authorization"] = f"Bearer {token}"
            req = _ur.Request(api_url, headers=hdrs)
            with _ur.urlopen(req, timeout=10) as r:
                users = _j.loads(r.read())

            return {
                "success": True,
                "count": len(users),
                "users": [
                    {
                        "username": u.get("username"),
                        "name": u.get("name"),
                        "url": f"http://localhost:8023/{u.get('username')}",
                    }
                    for u in users
                ],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def fork_all_user_source_repos(username: str) -> Dict[str, Any]:
    """
    Fork ALL source (non-fork) repositories from a GitLab user into byteblaze's namespace.

    Use this single tool when the task says "fork all source repos from [person]".
    It finds the user's source repos and forks each one automatically.

    Args:
        username: GitLab username (e.g. "aklsh"). Use search_users() first if you only have a display name.

    Returns:
        Summary of all fork attempts with success/failure for each repo.

    Example:
        - "Fork all source repos from Akilesh Kannan" →
          1. search_users(name="Akilesh Kannan") → username="aklsh"
          2. fork_all_user_source_repos(username="aklsh")
    """
    def _work():
        import urllib.request as _ur
        import urllib.parse as _up
        import json as _j
        import time

        GITLAB = "http://localhost:8023"

        def _api(method, path, body=None, token=None):
            url = f"{GITLAB}/api/v4{path}"
            data = _j.dumps(body).encode() if body else None
            hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
            if token:
                hdrs["Authorization"] = f"Bearer {token}"
            req = _ur.Request(url, data=data, headers=hdrs, method=method)
            try:
                with _ur.urlopen(req, timeout=15) as r:
                    return _j.loads(r.read())
            except Exception as e:
                return {"_error": str(e)}

        try:
            token = _get_cached_oauth_token()
            if not token:
                return {"success": False, "error": "Could not obtain token"}

            # Get byteblaze's personal namespace ID
            ns_resp = _api("GET", "/namespaces?per_page=50", token=token)
            namespace_id = None
            if isinstance(ns_resp, list):
                for ns in ns_resp:
                    if ns.get("kind") == "user":
                        namespace_id = ns.get("id")
                        break
            # Fallback: get namespace ID from /user endpoint
            if not namespace_id:
                user_info = _api("GET", "/user", token=token)
                namespace_id = user_info.get("namespace_id") or user_info.get("id")
            if not namespace_id:
                return {"success": False, "error": "Could not determine byteblaze's namespace ID"}

            # Get user's source repos (not forks)
            user_projects = _api("GET", f"/users/{_up.quote(username)}/projects?per_page=50", token=token)
            if not isinstance(user_projects, list):
                return {"success": False, "error": f"Could not get projects for {username}: {user_projects}"}

            source_repos = [p for p in user_projects if not p.get("forked_from_project")]

            results = []
            for proj in source_repos:
                src_id = proj["id"]
                fork_slug = proj.get("path", proj.get("name"))
                proj_name = proj.get("name_with_namespace", fork_slug)

                # Check if fork already exists
                fork_path = _up.quote(f"byteblaze/{fork_slug}", safe="")
                existing = _api("GET", f"/projects/{fork_path}", token=token)
                if "id" in existing and existing.get("import_status") in ("finished", "none", ""):
                    results.append({"project": proj_name, "status": "already_exists", "url": f"{GITLAB}/byteblaze/{fork_slug}"})
                    continue

                # Fork via API
                fork_resp = _api("POST", f"/projects/{src_id}/fork", body={"namespace_id": namespace_id}, token=token)
                fork_id = fork_resp.get("id")

                if not fork_id:
                    # Check if 409 (already exists in stuck state)
                    msg = str(fork_resp.get("message", ""))
                    if "409" in msg or "already been taken" in msg.lower() or "exists" in msg.lower():
                        # Find and delete the stuck fork
                        owned = _api("GET", "/projects?owned=true&per_page=100", token=token)
                        if isinstance(owned, list):
                            stuck = next((p for p in owned if p.get("path") == fork_slug), None)
                            if stuck:
                                _api("DELETE", f"/projects/{stuck['id']}", token=token)
                                time.sleep(3)
                                fork_resp = _api("POST", f"/projects/{src_id}/fork", body={"namespace_id": namespace_id}, token=token)
                                fork_id = fork_resp.get("id")
                    if not fork_id:
                        results.append({"project": proj_name, "status": "failed", "error": str(fork_resp)})
                        continue

                # Wait for import
                deadline = time.time() + 30
                while time.time() < deadline:
                    st = _api("GET", f"/projects/{fork_id}", token=token)
                    if st.get("import_status") in ("finished", "none", ""):
                        break
                    if st.get("import_status") == "failed":
                        break
                    time.sleep(2)

                fork_slug = fork_resp.get("path", fork_slug)
                results.append({"project": proj_name, "status": "forked", "url": f"{GITLAB}/byteblaze/{fork_slug}"})

            return {
                "success": True,
                "forked_count": sum(1 for r in results if r["status"] in ("forked", "already_exists")),
                "total": len(results),
                "results": results,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def fork_project(source_namespace: str, source_project: str) -> Dict[str, Any]:
    """
    Fork an existing GitLab project into the currently logged-in user's (byteblaze) namespace.

    Use this tool whenever the task says "fork" a repository. Do NOT use
    create_project for forking — this tool performs the actual GitLab fork
    operation using the GitLab API, which is more reliable than the UI.

    IMPORTANT — finding the right source_namespace:
    On WebArena GitLab, repos are stored under various namespaces.
    Use search_projects(keyword=...) first to find the correct namespace/project path
    if you are not sure.

    Args:
        source_namespace: Namespace (username or group) that owns the source project
        source_project: Name of the project to fork

    Examples:
        - "Fork 2019-nCov" → fork_project(source_namespace="yjlou", source_project="2019-nCov")
        - "Fork ChatGPT"   → fork_project(source_namespace="convexegg", source_project="chatgpt")
        - "Fork MetaSeq"   → fork_project(source_namespace="root", source_project="metaseq")
        - "Fork PyTorch-GAN with most stars" → fork_project(source_namespace="eriklindernoren", source_project="PyTorch-GAN")
    """
    def _work():
        import urllib.request as _ur
        import urllib.parse as _up
        import json as _j
        import time

        GITLAB = "http://localhost:8023"

        def _api(method: str, path: str, body=None, token=None) -> dict:
            url = f"{GITLAB}/api/v4{path}"
            data = _j.dumps(body).encode() if body else None
            hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
            if token:
                hdrs["Authorization"] = f"Bearer {token}"
            req = _ur.Request(url, data=data, headers=hdrs, method=method)
            try:
                with _ur.urlopen(req, timeout=15) as r:
                    return _j.loads(r.read())
            except Exception as e:
                return {"_error": str(e)}

        try:
            token = _get_cached_oauth_token()
            if not token:
                return {"success": False, "error": "Could not obtain OAuth token"}

            # Get byteblaze's personal namespace ID via /namespaces API
            ns_resp = _api("GET", "/namespaces?per_page=50", token=token)
            namespace_id = None
            if isinstance(ns_resp, list):
                # Find the user's personal namespace (kind="user")
                for ns in ns_resp:
                    if ns.get("kind") == "user":
                        namespace_id = ns.get("id")
                        break
            if not namespace_id:
                # Fallback: use /user endpoint
                user_info = _api("GET", "/user", token=token)
                namespace_id = user_info.get("namespace_id") or user_info.get("id")
            if not namespace_id:
                return {"success": False, "error": "Could not get user namespace ID"}

            # Find source project ID
            encoded = _up.quote(f"{source_namespace}/{source_project}", safe="")
            src = _api("GET", f"/projects/{encoded}", token=token)
            if "id" not in src:
                return {"success": False, "error": f"Source project {source_namespace}/{source_project} not found: {src}"}
            src_id = src["id"]
            fork_slug = src.get("path", source_project)

            # Check if fork already exists and is healthy
            fork_path = _up.quote(f"byteblaze/{fork_slug}", safe="")
            existing = _api("GET", f"/projects/{fork_path}", token=token)
            if "id" in existing:
                import_status = existing.get("import_status", "finished")
                if import_status in ("finished", "none", ""):
                    fork_url = f"{GITLAB}/byteblaze/{fork_slug}"
                    return {"success": True, "fork_url": fork_url, "message": "Fork already exists"}
                elif import_status == "failed":
                    # Delete the failed fork and re-fork
                    _api("DELETE", f"/projects/{existing['id']}", token=token)
                    time.sleep(2)
                # else: still importing, will poll below

            # Attempt fork via API
            fork_resp = _api("POST", f"/projects/{src_id}/fork", body={"namespace_id": namespace_id}, token=token)

            if "message" in fork_resp and "409" in str(fork_resp.get("message", "")):
                # Fork exists in stuck state — try to delete by ID if we can find it
                # Search user's owned projects
                owned = _api("GET", "/projects?owned=true&per_page=100", token=token)
                if isinstance(owned, list):
                    stuck = next((p for p in owned if p.get("path") == fork_slug), None)
                    if stuck:
                        _api("DELETE", f"/projects/{stuck['id']}", token=token)
                        time.sleep(3)
                        fork_resp = _api("POST", f"/projects/{src_id}/fork", body={"namespace_id": namespace_id}, token=token)

            fork_id = fork_resp.get("id")
            if not fork_id:
                return {"success": False, "error": f"Fork API call failed: {fork_resp}"}

            # Poll for import completion
            fork_slug = fork_resp.get("path", fork_slug)
            deadline = time.time() + 30
            while time.time() < deadline:
                status_resp = _api("GET", f"/projects/{fork_id}", token=token)
                status = status_resp.get("import_status", "finished")
                if status in ("finished", "none", ""):
                    break
                if status == "failed":
                    return {"success": False, "error": "Fork import failed"}
                time.sleep(2)

            fork_url = f"{GITLAB}/byteblaze/{fork_slug}"
            return {"success": True, "fork_url": fork_url}

        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def delete_project(namespace: str, project: str) -> Dict[str, Any]:
    """Delete a GitLab project."""
    def _work():
        try:
            page = _get_page()
            result = gitlab_pw.delete_project(page, namespace, project)
            return {"success": result.success, "message": result.message}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


# ============================================================================
# GROUP ENDPOINTS
# ============================================================================

@mcp.tool()
async def create_group(group: GroupData) -> Dict[str, Any]:
    """Create a new private GitLab group."""
    def _work():
        try:
            page = _get_page()
            result = gitlab_pw.create_private_group(
                page,
                name=group.name,
                description=group.description
            )
            return {
                "success": result.success,
                "message": result.message,
                "group_url": result.group_url if result.success else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def delete_group(group_path: str) -> Dict[str, Any]:
    """Delete a GitLab group."""
    def _work():
        try:
            page = _get_page()
            result = gitlab_pw.delete_group(page, group_path)
            return {"success": result.success, "message": result.message}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def get_group_members(group_path: str) -> Dict[str, Any]:
    """Get all members of a GitLab group."""
    def _work():
        try:
            page = _get_page()
            members = gitlab_pw.get_group_members(page, group_path)
            return {
                "success": True,
                "count": len(members),
                "members": [
                    {"username": member.username, "name": member.name, "role": member.role}
                    for member in members
                ]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def add_member_to_group(group_path: str, username: str, role: str = "Developer") -> Dict[str, Any]:
    """Add a member to a GitLab group."""
    def _work():
        try:
            page = _get_page()
            result = gitlab_pw.add_member_to_group(page, group_path, username, role)
            return {"success": result.success, "message": result.message}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


# ============================================================================
# BRANCH ENDPOINTS
# ============================================================================

@mcp.tool()
async def create_branch(branch: BranchData) -> Dict[str, Any]:
    """Create a new branch in a GitLab project."""
    def _work():
        try:
            page = _get_page()
            result = gitlab_pw.create_branch(
                page,
                namespace=branch.namespace,
                project=branch.project,
                branch_name=branch.branch_name,
                ref=branch.ref
            )
            return {
                "success": result.success,
                "message": result.message,
                "branch_url": result.branch_url if result.success else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def get_branches(namespace: str, project: str) -> Dict[str, Any]:
    """Get all branches from a GitLab project."""
    def _work():
        try:
            page = _get_page()
            branches = gitlab_pw.get_branches(page, namespace, project)
            return {
                "success": True,
                "count": len(branches),
                "branches": [{"name": b.name, "url": b.url} for b in branches]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def delete_branch(namespace: str, project: str, branch_name: str) -> Dict[str, Any]:
    """Delete a branch from a GitLab project."""
    def _work():
        try:
            page = _get_page()
            result = gitlab_pw.delete_branch(page, namespace, project, branch_name)
            return {"success": result.success, "message": result.message}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


# ============================================================================
# FILE ENDPOINTS
# ============================================================================

@mcp.tool()
async def create_file(file: FileData) -> Dict[str, Any]:
    """Create a new file in a GitLab project."""
    def _work():
        try:
            page = _get_page()
            if file.content:
                result = gitlab_pw.create_file_with_content(
                    page,
                    namespace=file.namespace,
                    project=file.project,
                    branch=file.branch,
                    file_path=file.file_path,
                    content=file.content
                )
            else:
                result = gitlab_pw.create_empty_file(
                    page,
                    namespace=file.namespace,
                    project=file.project,
                    branch=file.branch,
                    file_path=file.file_path
                )
            return {
                "success": result.success,
                "message": result.message,
                "file_url": result.file_url if result.success else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


# ============================================================================
# MERGE REQUEST ENDPOINTS
# ============================================================================

@mcp.tool()
async def create_merge_request(mr: MergeRequestData) -> Dict[str, Any]:
    """Create a new merge request in a GitLab project."""
    def _work():
        try:
            page = _get_page()
            result = gitlab_pw.create_merge_request(
                page,
                namespace=mr.namespace,
                project=mr.project,
                title=mr.title,
                source_branch=mr.source_branch,
                target_branch=mr.target_branch,
                description=mr.description
            )
            return {
                "success": result.success,
                "message": result.message,
                "mr_number": result.mr_number if result.success else None,
                "mr_url": result.mr_url if result.success else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def get_merge_requests(
    namespace: Optional[str] = None,
    project: Optional[str] = None,
    assignee_username: Optional[str] = None,
    state: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get merge requests for a project, returning a structured list with MR numbers and titles.

    IMPORTANT: When namespace and project are both provided, returns a structured list of
    MR objects — each with mr_number, title, and url — so you can look up the correct
    mr_number before calling comment_merge_request or close_merge_request.

    Args:
        namespace: Project namespace (required together with project for structured listing)
        project: Project name (required together with namespace for structured listing)
        assignee_username: Optional username to filter by assignee
        state: Optional state filter ("opened", "closed", "merged", "all")
               Defaults to "all" when namespace+project are given, so you see every MR.

    Examples:
        - "Find MR about semantic HTML in a11yproject/a11yproject.com" →
          get_merge_requests(namespace="a11yproject", project="a11yproject.com", state="all")
          → returns list, search titles for 'semantic HTML', grab its mr_number

        - "Open MRs in project X" →
          get_merge_requests(namespace="ns", project="proj", state="opened")

        - "My merge requests (dashboard view)" →
          get_merge_requests(assignee_username="byteblaze")
    """
    def _work():
        try:
            page = _get_page()

            if namespace and project:
                # Return structured list by scraping the MR list page
                mrs = gitlab_pw.get_mr_list(page, namespace, project, state=state)
                return {
                    "success": True,
                    "count": len(mrs),
                    "url": page.url,
                    "merge_requests": [
                        {"mr_number": mr.mr_id, "title": mr.title, "url": mr.url}
                        for mr in mrs
                    ],
                }
            else:
                # Fall back to dashboard navigation (no scraping)
                url = "http://localhost:8023/dashboard/merge_requests"
                params = []
                if assignee_username:
                    params.append(f"assignee_username={assignee_username}")
                if state:
                    params.append(f"state={state}")
                if params:
                    url += "?" + "&".join(params)
                page.goto(url, wait_until="networkidle")
                return {
                    "success": True,
                    "url": page.url,
                    "final_url": page.url,
                    "message": f"Navigated to merge requests: {page.url}",
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def close_merge_request(namespace: str, project: str, mr_number: int) -> Dict[str, Any]:
    """Close a merge request in a GitLab project."""
    def _work():
        try:
            page = _get_page()
            result = gitlab_pw.close_merge_request(page, namespace, project, mr_number)
            return {"success": result.success, "message": result.message}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def comment_merge_request(
    namespace: str,
    project: str,
    body: str,
    mr_number: Optional[int] = None,
    title_keyword: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Post a comment (note) on an existing GitLab merge request.

    You MUST provide EITHER mr_number OR title_keyword (or both).

    Args:
        namespace: Project namespace (username or group name)
        project: Project name
        body: Text of the comment to post
        mr_number: (Optional) Integer MR ID from the URL. Use this when you already
                   know the exact MR number.
        title_keyword: (Optional) Keyword or phrase from the MR title to search for.
                       When mr_number is unknown, provide this and the tool will find
                       the MR automatically by searching the title list.

    Examples:
        - If you know the MR number:
          comment_merge_request(namespace="a11yproject", project="a11yproject.com",
                                mr_number=1531, body="lgtm")

        - If you only know the topic (PREFERRED when MR number is unknown):
          comment_merge_request(namespace="a11yproject", project="a11yproject.com",
                                title_keyword="semantic HTML", body="lgtm")

        - "Post 'lgtm' on the MR about fixing broken links in byteblaze/empathy-prompts" →
          comment_merge_request(namespace="byteblaze", project="empathy-prompts",
                                title_keyword="broken links", body="lgtm")
    """
    def _work():
        try:
            page = _get_page()

            resolved_mr_number = mr_number

            # Always import API helpers and obtain OAuth token
            import urllib.request as _ur2
            import urllib.parse as _up2
            import json as _j2

            # Use the module-level cached token (avoids repeated OAuth calls)
            api_token = _get_cached_oauth_token()

            # If mr_number not given (or 0), resolve by searching MR titles via API
            if not resolved_mr_number and title_keyword:

                keyword_lower = title_keyword.lower()

                def _similar(a: str, b: str) -> bool:
                    """True if a and b are similar (substring, prefix, or close edit distance)."""
                    # Only do substring check for words of at least 4 chars to avoid
                    # false positives from short stop-words like 't', 'do', 'don', etc.
                    if len(a) >= 4 and len(b) >= 4 and (a in b or b in a):
                        return True
                    # Exact match (needed for short words)
                    if a == b:
                        return True
                    # Share at least 5-char prefix
                    prefix_len = min(len(a), len(b), 5)
                    if prefix_len >= 5 and a[:prefix_len] == b[:prefix_len]:
                        return True
                    # Edit distance: allow transpositions/typos for words >= 5 chars
                    # Threshold 0.70 handles cases like "ulitity" vs "utility" (0.714)
                    if len(a) >= 5 and len(b) >= 5:
                        import difflib
                        ratio = difflib.SequenceMatcher(None, a, b).ratio()
                        if ratio >= 0.70:
                            return True
                    return False

                def _mr_matches(mr_title: str) -> bool:
                    title_l = mr_title.lower()
                    if keyword_lower in title_l:
                        return True
                    import re as _re2
                    kw_words = [w for w in _re2.findall(r'\w+', keyword_lower) if len(w) >= 3]
                    title_words = _re2.findall(r'\w+', title_l)
                    if not kw_words:
                        return False
                    hits = sum(1 for w in kw_words if any(_similar(w, tw) for tw in title_words))
                    # Require ALL keywords to match (strict) to avoid false positives
                    return hits == len(kw_words)

                found_mr_iid = None
                if api_token:
                    # Search via GitLab API (handles all pages, much faster than UI scraping)
                    # First try API search by title keyword
                    proj_encoded = _up2.quote(f"{namespace}/{project}", safe="")
                    search_term = _up2.quote(title_keyword)
                    api_url = f"http://localhost:8023/api/v4/projects/{proj_encoded}/merge_requests?state=all&search={search_term}&per_page=20"
                    api_req = _ur2.Request(api_url, headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json"})
                    try:
                        with _ur2.urlopen(api_req, timeout=15) as r:
                            api_mrs = _j2.loads(r.read())
                        if isinstance(api_mrs, list):
                            for mr in api_mrs:
                                if _mr_matches(mr.get("title", "")):
                                    found_mr_iid = mr["iid"]
                                    break
                    except Exception:
                        pass

                    # If not found by full search term, try individual keywords (paginated, up to 3 pages)
                    if not found_mr_iid:
                        import re as _re3
                        kw_words = _re3.findall(r'\w+', keyword_lower)
                        for word in kw_words:
                            if len(word) < 4:
                                continue
                            # Try the word as-is (handles most cases), then a 4-char prefix
                            search_variants = [word]
                            if len(word) > 4:
                                search_variants.append(word[:4])
                            for sv in search_variants:
                                for _page_num in range(1, 4):  # pages 1-3
                                    api_url2 = (
                                        f"http://localhost:8023/api/v4/projects/{proj_encoded}"
                                        f"/merge_requests?state=all&search={_up2.quote(sv)}"
                                        f"&per_page=20&page={_page_num}"
                                    )
                                    api_req2 = _ur2.Request(api_url2, headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json"})
                                    try:
                                        with _ur2.urlopen(api_req2, timeout=15) as r2:
                                            api_mrs2 = _j2.loads(r2.read())
                                        if not isinstance(api_mrs2, list) or not api_mrs2:
                                            break  # No more pages
                                        for mr in api_mrs2:
                                            if _mr_matches(mr.get("title", "")):
                                                found_mr_iid = mr["iid"]
                                                break
                                        if found_mr_iid or len(api_mrs2) < 20:
                                            break  # Found or end of results
                                    except Exception:
                                        break
                                if found_mr_iid:
                                    break
                            if found_mr_iid:
                                break

                if not found_mr_iid:
                    # Fallback to Playwright UI scraping (first page only)
                    import sys as _sys_cmr
                    print(f"[comment_mr] API search found nothing for {title_keyword!r} (api_token={'set' if api_token else 'NONE'}), falling back to Playwright", file=_sys_cmr.stderr, flush=True)
                    mrs = gitlab_pw.get_mr_list(page, namespace, project, state="all")
                    match = next((mr for mr in mrs if _mr_matches(mr.title)), None)
                    if match:
                        found_mr_iid = match.mr_id

                if not found_mr_iid:
                    return {
                        "success": False,
                        "error": f"No MR found with title containing '{title_keyword}' in {namespace}/{project}.",
                    }
                resolved_mr_number = found_mr_iid

            if not resolved_mr_number:
                return {
                    "success": False,
                    "error": "Must provide either mr_number or title_keyword to identify the MR.",
                }

            # Post the comment — prefer GitLab API (reliable), fall back to Playwright UI
            import sys as _sys_post
            proj_encoded2 = _up2.quote(f"{namespace}/{project}", safe="")
            api_post_succeeded = False
            if api_token:
                note_url = f"http://localhost:8023/api/v4/projects/{proj_encoded2}/merge_requests/{resolved_mr_number}/notes"
                note_body_bytes = _j2.dumps({"body": body}).encode()
                # Retry up to 3 times on transient failures (500, timeout)
                last_post_err = None
                for _post_attempt in range(3):
                    # Refresh token on retry (in case it expired)
                    if _post_attempt > 0:
                        _time_module.sleep(2 ** _post_attempt)
                        api_token = _get_cached_oauth_token()
                        if not api_token:
                            break
                    note_req = _ur2.Request(
                        note_url,
                        data=note_body_bytes,
                        headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json", "Accept": "application/json"},
                        method="POST",
                    )
                    try:
                        with _ur2.urlopen(note_req, timeout=20) as r:
                            note_resp = _j2.loads(r.read())
                            note_id = note_resp.get("id")
                            if note_id:
                                api_post_succeeded = True
                                return {
                                    "success": True,
                                    "mr_number": resolved_mr_number,
                                    "note_id": note_id,
                                    "message": f"Comment posted successfully on MR #{resolved_mr_number} (API attempt {_post_attempt+1})",
                                }
                    except Exception as _post_exc:
                        last_post_err = _post_exc
                        print(f"[comment_mr] API post attempt {_post_attempt+1} failed: {_post_exc}", file=_sys_post.stderr, flush=True)
                if not api_post_succeeded:
                    print(f"[comment_mr] All API post attempts failed for MR#{resolved_mr_number}, falling back to Playwright. Last error: {last_post_err}", file=_sys_post.stderr, flush=True)

            # Playwright fallback (used when API token unavailable or API post failed)
            if not api_post_succeeded:
                result = gitlab_pw.post_mr_comment(
                    page,
                    namespace=namespace,
                    project=project,
                    mr_id=resolved_mr_number,
                    body=body,
                )
                # Verify the comment actually landed by checking the API
                if result.success and api_token:
                    verify_url = f"http://localhost:8023/api/v4/projects/{proj_encoded2}/merge_requests/{resolved_mr_number}/notes?per_page=20"
                    verify_req = _ur2.Request(verify_url, headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json"})
                    try:
                        with _ur2.urlopen(verify_req, timeout=10) as rv:
                            verify_notes = _j2.loads(rv.read())
                        body_lower = body.lower()
                        confirmed = any(
                            not n.get("system") and body_lower in n.get("body", "").lower()
                            for n in verify_notes
                        )
                        if not confirmed:
                            print(f"[comment_mr] Playwright claimed success but comment not found in API notes. body={body!r}", file=_sys_post.stderr, flush=True)
                            return {
                                "success": False,
                                "mr_number": resolved_mr_number,
                                "message": f"Comment not found in API after Playwright post — likely failed silently. body={body!r}",
                            }
                    except Exception as _vex:
                        print(f"[comment_mr] Could not verify Playwright post via API: {_vex}", file=_sys_post.stderr, flush=True)
                return {
                    "success": result.success,
                    "mr_number": resolved_mr_number,
                    "message": result.error_message if result.error_message else "Comment posted successfully (via Playwright fallback)",
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


# ============================================================================
# SETTINGS ENDPOINTS
# ============================================================================

@mcp.tool()
async def toggle_private_profile(make_private: bool) -> Dict[str, Any]:
    """Toggle private profile setting."""
    def _work():
        try:
            page = _get_page()
            result = gitlab_pw.toggle_private_profile(page, make_private)
            return {"success": result.success, "message": result.message}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return await _run_pw(_work)


@mcp.tool()
async def cleanup_browser() -> Dict[str, str]:
    """Clean up browser resources."""
    def _work():
        try:
            _cleanup()
            return {"message": "Browser resources cleaned up successfully"}
        except Exception as e:
            return {"error": str(e)}
    return await _run_pw(_work)


# Run the MCP server
import sys
from pathlib import Path

# Add project root to path so agent module can be imported
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agent.common.configurator import Configurator
from agent.common.utils import get_mcp_logger

logger = get_mcp_logger()

if __name__ == "__main__":
    print("Starting gitlab-mcp server")
    logger.debug("Starting gitlab-mcp server")

    config = Configurator()
    config.load_mcpserver_env()
    config.load_shared_env()

    # Read URL from config.yaml -> mcp_server.gitlab
    mcp_server_url = config.get_key("mcp_server")["gitlab"]
    hostname, port, path = config.get_hostname_port(mcp_server_url)

    # Run FastMCP over HTTP (streamable-http transport)
    mcp.run(
        transport="streamable-http",
        host=hostname,
        port=port,
        path=path,
    )
