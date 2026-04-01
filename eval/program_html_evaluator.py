"""
program_html_evaluator.py

Evaluates program_html tasks from WebArena task definitions.

Usage:
    from program_html_evaluator import ProgramHtmlEvaluator

    evaluator = ProgramHtmlEvaluator(base_urls={...})
    result = evaluator.evaluate(task, page, last_url="http://...")
"""

import re
from typing import Any, Dict, List, Optional

from playwright.sync_api import Page


# ---------------------------------------------------------------------------
# Default base URL mapping for placeholder substitution
# Override by passing base_urls= to ProgramHtmlEvaluator.__init__
# ---------------------------------------------------------------------------
DEFAULT_BASE_URLS: Dict[str, str] = {
    "__GITLAB__": "http://localhost:8023",
    "__REDDIT__": "http://localhost:9999",
    "__SHOPPING__": "http://ec2-18-218-205-96.us-east-2.compute.amazonaws.com:8082",
    "__SHOPPING_ADMIN__": "http://ec2-18-218-205-96.us-east-2.compute.amazonaws.com:8082/admin",
    "__MAP__": "http://localhost:3000",
}


class ProgramHtmlEvaluator:
    """
    Evaluates the program_html component of a WebArena task.

    For each entry in task["eval"]["program_html"], it:
      1. Resolves the URL using the decision tree (literal, "last", func:...)
      2. Navigates to that URL with Playwright
      3. Evaluates the locator expression (JS or func:) to extract content
      4. Checks required_contents (exact_match / must_include / must_exclude)

    All program_html entries must pass for the overall evaluation to pass.
    """

    def __init__(self, base_urls: Optional[Dict[str, str]] = None):
        """
        Args:
            base_urls: Mapping of placeholder tokens to real base URLs.
                       Defaults to DEFAULT_BASE_URLS.
        """
        self.base_urls = base_urls if base_urls is not None else DEFAULT_BASE_URLS

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def evaluate(
        self,
        task: Dict[str, Any],
        page: Page,
        last_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate the program_html section of a task.

        Args:
            task:     Full task dict (must contain task["eval"]).
            page:     An authenticated Playwright Page ready to navigate.
            last_url: The final URL the agent navigated to during execution.
                      Required when program_html url is "last" or a func that
                      references '__last_url__'.

        Returns:
            {
                "applicable":   bool   # False when eval_type is not program_html
                "passed":       bool
                "checks":       list   # Per-entry detail
                "error":        str | None
            }
        """
        eval_section = task.get("eval", {})
        eval_types = eval_section.get("eval_types", [])

        if "program_html" not in eval_types:
            return {
                "applicable": False,
                "passed": False,
                "checks": [],
                "error": "eval_type does not include program_html",
            }

        entries = eval_section.get("program_html", [])
        if not entries:
            return {
                "applicable": True,
                "passed": True,
                "checks": [],
                "error": None,
            }

        # Fall back to reference_url when last_url is unknown.
        # reference_url may carry |OR| alternatives (e.g. Reddit tasks that
        # accept several subreddits).  Resolve each alternative separately so
        # we never try to navigate to a URL containing the literal " |OR| ".
        reference_url = eval_section.get("reference_url") or ""
        if last_url:
            resolved_last_alternatives = [last_url]
        else:
            resolved_last_alternatives = [
                self._resolve_placeholder(alt.strip())
                for alt in reference_url.split(" |OR| ")
                if alt.strip()
            ] or [""]

        checks: List[Dict[str, Any]] = []
        all_passed = True

        for entry in entries:
            # For entries whose url resolves to multiple |OR| alternatives, try
            # each one and accept the first that passes (or keep the last
            # failure for diagnostics if none passes).
            best_check: Optional[Dict[str, Any]] = None
            for resolved_last in resolved_last_alternatives:
                check = self._evaluate_entry(entry, page, resolved_last)
                if check["passed"]:
                    best_check = check
                    break
                if best_check is None:
                    best_check = check
            checks.append(best_check)  # type: ignore[arg-type]
            if not best_check["passed"]:
                all_passed = False

        return {
            "applicable": True,
            "passed": all_passed,
            "checks": checks,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Per-entry evaluation
    # ------------------------------------------------------------------

    def _evaluate_entry(
        self,
        entry: Dict[str, Any],
        page: Page,
        last_url: Optional[str],
    ) -> Dict[str, Any]:
        """Evaluate a single program_html entry."""
        raw_url = entry.get("url", "")
        locator = entry.get("locator", "")
        required_contents = entry.get("required_contents", {})

        # Step 1: resolve URL
        try:
            resolved_url = self._resolve_url(raw_url, page, last_url)
        except Exception as exc:
            return self._fail_check(entry, error=f"URL resolution failed: {exc}")

        # Step 2: navigate (with retry on interrupted/crashed navigation)
        # Try networkidle first (needed for Vue.js comment components), fall back to
        # domcontentloaded if networkidle times out (GitLab project pages with activity feeds).
        import time as _time_eval
        nav_error = None
        for _nav_attempt in range(2):
            try:
                page.goto(resolved_url, wait_until="networkidle", timeout=45000)
                nav_error = None
                break
            except Exception:
                try:
                    page.goto(resolved_url, wait_until="domcontentloaded", timeout=20000)
                    # Wait briefly for Vue to mount critical components (comments, notes-list)
                    page.wait_for_timeout(3000)
                    nav_error = None
                    break
                except Exception as exc2:
                    nav_error = exc2
                    if _nav_attempt == 0:
                        _time_eval.sleep(3)  # Brief pause before retry
        if nav_error is not None:
            return self._fail_check(entry, resolved_url=resolved_url, error=f"Navigation failed: {nav_error}")

        # Step 3: if the locator references 'notes-list', wait for it to appear in the DOM.
        # Vue.js renders the comment list asynchronously after networkidle; we must poll.
        if locator and "notes-list" in locator:
            try:
                page.wait_for_selector('[id="notes-list"]', timeout=15000)
                # Also wait for at least one child element (the actual notes)
                page.wait_for_function(
                    'document.querySelector(\'[id="notes-list"]\') && '
                    'document.querySelector(\'[id="notes-list"]\').children.length > 0',
                    timeout=10000,
                )
            except Exception:
                pass  # Fall through to locator eval which will surface the error

        # Step 3: extract content via locator
        try:
            content = self._extract_content(page, locator)
        except Exception as exc:
            return self._fail_check(entry, resolved_url=resolved_url, error=f"Locator failed: {exc}")

        # Step 4: check required_contents
        passed, missing, excluded_found = self._check_contents(content, required_contents)

        return {
            "passed": passed,
            "raw_url": raw_url,
            "resolved_url": resolved_url,
            "locator": locator,
            "required_contents": required_contents,
            "extracted_content": content[:500] if content else None,
            "missing": missing,
            "excluded_found": excluded_found,
            "error": None,
        }

    # ------------------------------------------------------------------
    # URL resolution (decision tree)
    # ------------------------------------------------------------------

    def _resolve_url(
        self,
        raw_url: str,
        page: Page,
        last_url: Optional[str],
    ) -> str:
        """
        Resolve a program_html url field to a navigable URL.

        Patterns handled:
          - "last"                                  → last_url
          - "func:reddit_get_post_url('__last_url__')" → newest post on subreddit
          - "func:shopping_get_latest_order_url()"  → latest order detail page
          - "__PLACEHOLDER__/path"                  → substitute base URL
          - direct URL / relative path              → as-is or resolved
        """
        if not raw_url:
            return last_url or page.url

        # 1. "last" → use tracked last URL
        if raw_url.strip().lower() == "last":
            if not last_url:
                raise ValueError(
                    '"last" URL requested but no last_url was provided. '
                    "Pass last_url= to evaluate()."
                )
            return last_url

        # 2. func: patterns
        if raw_url.startswith("func:"):
            return self._resolve_func_url(raw_url, page, last_url)

        # 3. Literal URL with placeholder tokens
        resolved = self._resolve_placeholder(raw_url)

        # 4. Relative path (starts with / or ../): treat relative to any known base
        if resolved.startswith("/") or resolved.startswith(".."):
            # Prefix with the first matching base or fall back to current origin
            origin = page.url.split("/")[0] + "//" + page.url.split("/")[2]
            resolved = origin + "/" + resolved.lstrip("/")

        return resolved

    def _resolve_func_url(
        self,
        raw_url: str,
        page: Page,
        last_url: Optional[str],
    ) -> str:
        """Resolve func: URL patterns."""

        # func:reddit_get_post_url('__last_url__')
        if "reddit_get_post_url" in raw_url:
            subreddit_url = last_url
            if not subreddit_url:
                raise ValueError(
                    "reddit_get_post_url requires a last_url (subreddit URL) "
                    "but none was provided."
                )
            return self._reddit_get_post_url(page, subreddit_url)

        # func:shopping_get_latest_order_url()
        if "shopping_get_latest_order_url" in raw_url:
            return self._shopping_get_latest_order_url(page)

        raise ValueError(f"Unknown func: pattern in URL: {raw_url!r}")

    def _reddit_get_post_url(self, page: Page, subreddit_url: str) -> str:
        """
        Return the URL of the most recently submitted post in a subreddit.

        If subreddit_url is already a post URL (contains a numeric post ID),
        return it directly — this is the post the agent just created.
        Otherwise navigate to the subreddit's /new sort and return the first post.
        """
        import re as _re
        reddit_base = self.base_urls.get("__REDDIT__", "http://localhost:9999")

        # If last_url is already a post URL (/f/{forum}/{id}/{slug}), use it directly.
        # This handles create_post tasks where final_url is the newly created post.
        post_url_m = _re.match(
            r'(https?://[^/]+/f/[^/]+/\d+/[^/]*)',
            subreddit_url or "",
        )
        if post_url_m:
            return post_url_m.group(1)

        # Extract just the subreddit base from the URL.
        # Handles /f/{forum} forms.
        m = _re.match(r'(https?://[^/]+/f/[^/]+)', subreddit_url)
        if m:
            subreddit_url = m.group(1)

        # Postmill uses path-based sort: /f/{forum}/new  (not ?sort=new)
        sort_url = subreddit_url.rstrip("/") + "/new"
        page.goto(sort_url, wait_until="networkidle", timeout=20000)

        # Find the first local post link on the page.
        # For text posts: h1.submission__title a links to /f/{forum}/{id}/{slug}.
        # For link posts: that same element links to the external article.
        # Use article-scoped search so we prefer the local post URL.
        forum_slug = subreddit_url.rstrip("/").split("/f/")[-1]
        local_pattern = _re.compile(rf"^/f/{_re.escape(forum_slug)}/\d+/", _re.IGNORECASE)

        for article in page.query_selector_all("article"):
            # Prefer a link that matches /f/{forum}/{id}/
            for lnk in article.query_selector_all("a[href]"):
                href = lnk.get_attribute("href") or ""
                if local_pattern.match(href):
                    return reddit_base.rstrip("/") + href
            # Fallback: any /f/ link in the article
            for lnk in article.query_selector_all("a[href^='/f/']"):
                href = lnk.get_attribute("href") or ""
                if _re.search(r"/\d+/", href) and "/edit" not in href:
                    return reddit_base.rstrip("/") + href

        # Last-resort: any matching link on the page
        for lnk in page.query_selector_all(f"a[href*='/f/{forum_slug}/']"):
            href = lnk.get_attribute("href") or ""
            if _re.search(r"/\d+/", href):
                return reddit_base.rstrip("/") + href

        raise ValueError(
            f"Could not find any post link on subreddit page: {sort_url}"
        )

    def _shopping_get_latest_order_url(self, page: Page) -> str:
        """
        Navigate to the shopping order history page and return the view URL
        for the most recently placed order (first row in the table).
        """
        from api.shipping_pw.order import get_order_history

        orders = get_order_history(page)
        if not orders:
            raise ValueError("No orders found in shopping order history.")
        return orders[0].view_url

    def _resolve_placeholder(self, url: str) -> str:
        """Replace __PLACEHOLDER__ tokens with real base URLs."""
        for token, base in self.base_urls.items():
            url = url.replace(token, base)
        return url

    # ------------------------------------------------------------------
    # Content extraction
    # ------------------------------------------------------------------

    def _extract_content(self, page: Page, locator: str) -> str:
        """
        Extract content from the current page using the locator expression.

        Handles:
          - Empty locator      → full page outerText via document.body.outerText
          - JS expression      → page.evaluate(locator)
          - func: expression   → custom Python-side function (e.g. gitlab member role)
        """
        if not locator:
            return page.evaluate("document.body.outerText") or ""

        if locator.startswith("func:"):
            return self._resolve_func_locator(page, locator)

        # Standard JS expression evaluated in page context
        result = page.evaluate(locator)
        if result is None:
            return ""
        return str(result)

    def _resolve_func_locator(self, page: Page, locator: str) -> str:
        """
        Handle func: patterns in the locator field.

        Currently supported:
          func:gitlab_get_project_memeber_role(__page__, '<username>')
        """
        # func:gitlab_get_project_memeber_role(__page__, 'username')
        match = re.match(
            r"func:gitlab_get_project_memeber_role\(__page__,\s*'([^']+)'\)",
            locator,
        )
        if match:
            username = match.group(1)
            return self._gitlab_get_project_member_role(page, username)

        raise ValueError(f"Unknown func: pattern in locator: {locator!r}")

    def _gitlab_get_project_member_role(self, page: Page, username: str) -> str:
        """
        Extract the role of a project member from the GitLab members page.

        Expects the page to already be on the project members URL
        (i.e. the url field in the same entry navigated there first).
        """
        # The members page lists rows with username and role cells.
        # Try to find the row for the given username.
        role_text = page.evaluate(
            """
            (username) => {
                const rows = document.querySelectorAll('tr');
                for (const row of rows) {
                    const cells = row.querySelectorAll('td');
                    for (const cell of cells) {
                        if (cell.textContent.trim().toLowerCase() === username.toLowerCase()) {
                            // Role is typically in the last or second-to-last cell
                            const allCells = Array.from(cells);
                            const lastCell = allCells[allCells.length - 1];
                            if (lastCell) return lastCell.textContent.trim();
                        }
                    }
                }
                return null;
            }
            """,
            username,
        )
        if role_text:
            return role_text

        # Fallback: search for a select or badge element near the username
        fallback = page.evaluate(
            """
            (username) => {
                const el = Array.from(document.querySelectorAll('*')).find(
                    e => e.textContent.trim() === username && e.tagName !== 'SCRIPT'
                );
                if (!el) return null;
                const row = el.closest('tr');
                if (!row) return null;
                const badge = row.querySelector('.badge, .role, [data-role], select option[selected]');
                return badge ? badge.textContent.trim() : null;
            }
            """,
            username,
        )
        return fallback or ""

    # ------------------------------------------------------------------
    # Content checking
    # ------------------------------------------------------------------

    def _check_contents(
        self,
        content: str,
        required_contents: Dict[str, Any],
    ):
        """
        Check extracted content against required_contents spec.

        Placeholder tokens like __GITLAB__ and __REDDIT__ in required_contents
        values are expanded to their real base URLs before comparison, so ground
        truth entries such as ``"__GITLAB__/user/repo"`` correctly match the
        actual URL that appears on the page.

        Returns:
            (passed: bool, missing: list, excluded_found: list)
        """
        missing: List[str] = []
        excluded_found: List[str] = []
        content_lower = content.lower()

        # exact_match: full string equality (case-insensitive)
        exact = required_contents.get("exact_match")
        if exact is not None:
            if content.strip().lower() != str(exact).strip().lower():
                missing.append(f"exact_match: {exact!r}")

        # must_include: all items must appear somewhere in content
        for item in required_contents.get("must_include", []):
            resolved_item = self._resolve_placeholder(str(item))
            if resolved_item.lower() not in content_lower:
                missing.append(item)

        # must_exclude: none of these may appear in content
        for item in required_contents.get("must_exclude", []):
            resolved_item = self._resolve_placeholder(str(item))
            if resolved_item.lower() in content_lower:
                excluded_found.append(item)

        passed = not missing and not excluded_found
        return passed, missing, excluded_found

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fail_check(
        entry: Dict[str, Any],
        resolved_url: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "passed": False,
            "raw_url": entry.get("url"),
            "resolved_url": resolved_url,
            "locator": entry.get("locator"),
            "required_contents": entry.get("required_contents"),
            "extracted_content": None,
            "missing": [],
            "excluded_found": [],
            "error": error,
        }
