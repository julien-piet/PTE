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

from config.servers import SERVER_URLS as _SERVER_URLS

DEFAULT_BASE_URLS: dict = {f"__{k.upper()}__": v for k, v in _SERVER_URLS.items()}


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
                # Scroll to the bottom to trigger lazy-loading of later notes (e.g. a
                # newly posted comment that appears after the initial viewport batch).
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
                # Re-scroll in case the page extended further after first scroll
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)
                # Wait for at least one .timeline-discussion-body to be rendered —
                # this is the specific class the lastElementChild locator queries.
                try:
                    page.wait_for_selector(".timeline-discussion-body", timeout=5000)
                except Exception:
                    pass
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
        reddit_base = self.base_urls.get("__REDDIT__", DEFAULT_BASE_URLS["__REDDIT__"])

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
        from api.shopping_pw.order import get_order_history

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
          func:shopping_get_sku_latest_review_rating('<sku>')
          func:shopping_get_sku_latest_review_author('<sku>')
        """
        # func:gitlab_get_project_memeber_role(__page__, 'username')
        match = re.match(
            r"func:gitlab_get_project_memeber_role\(__page__,\s*'([^']+)'\)",
            locator,
        )
        if match:
            username = match.group(1)
            return self._gitlab_get_project_member_role(page, username)

        # func:shopping_get_sku_latest_review_rating('SKU')
        match = re.match(
            r"func:shopping_get_sku_latest_review_rating\('([^']+)'\)",
            locator,
        )
        if match:
            sku = match.group(1)
            return self._shopping_get_sku_latest_review_rating(sku)

        # func:shopping_get_sku_latest_review_author('SKU')
        match = re.match(
            r"func:shopping_get_sku_latest_review_author\('([^']+)'\)",
            locator,
        )
        if match:
            sku = match.group(1)
            return self._shopping_get_sku_latest_review_author(sku)

        # func:shopping_get_customer_cart_items('email', 'password')
        match = re.match(
            r"func:shopping_get_customer_cart_items\('([^']+)',\s*'([^']+)'\)",
            locator,
        )
        if match:
            email, password = match.group(1), match.group(2)
            return self._shopping_get_customer_cart_items(email, password)

        raise ValueError(f"Unknown func: pattern in locator: {locator!r}")

    def _gitlab_get_project_member_role(self, page: Page, username: str) -> str:
        """
        Extract the role of a project member using the GitLab REST API.

        Called after navigating to the project members page, so the browser
        session is already authenticated. Uses fetch() in page context to call
        the members API — this avoids DOM/pagination fragility entirely.

        Access level → role name mapping (GitLab standard):
          10 → Guest, 20 → Reporter, 30 → Developer,
          40 → Maintainer, 50 → Owner
        """
        ACCESS_LEVEL_NAMES = {
            10: "Guest",
            20: "Reporter",
            30: "Developer",
            40: "Maintainer",
            50: "Owner",
        }

        # Extract project path from the current URL.
        # URL pattern: /namespace/project/-/project_members
        current_url = page.url
        path = current_url.split("//", 1)[-1].split("/", 1)[-1]  # strip origin
        # Drop everything from "/-/" onward
        project_path = path.split("/-/")[0].strip("/")

        encoded_path = project_path.replace("/", "%2F")
        api_url = f"/api/v4/projects/{encoded_path}/members/all?query={username}&per_page=100"

        result = page.evaluate(
            """
            async (apiUrl) => {
                try {
                    const r = await fetch(apiUrl, {credentials: 'include'});
                    if (!r.ok) return null;
                    const members = await r.json();
                    return members;
                } catch (e) {
                    return null;
                }
            }
            """,
            api_url,
        )

        if result and isinstance(result, list):
            for member in result:
                if member.get("username", "").lower() == username.lower():
                    level = member.get("access_level")
                    return ACCESS_LEVEL_NAMES.get(level, str(level))

        return ""

    def _shopping_get_admin_token(self) -> str:
        """Return a cached or freshly-minted Magento admin token."""
        from pathlib import Path as _Path

        shopping_base = self.base_urls.get("__SHOPPING__", DEFAULT_BASE_URLS["__SHOPPING__"])
        token = ""
        server_env = _Path(__file__).parent.parent / "config" / ".server_env"
        if server_env.exists():
            for line in server_env.read_text().splitlines():
                if line.strip().startswith("ADMIN_AUTH_TOKEN="):
                    token = line.strip().split("=", 1)[1].strip()
                    break
        if not token:
            from config.init_tokens.refresh_shopping_tokens import refresh_tokens
            token = refresh_tokens(base_url=shopping_base)
        return token

    def _shopping_get_latest_review_for_sku(self, sku: str) -> dict:
        """
        Fetch the most recently created review for a product SKU via the
        Magento REST API.  Returns the review dict, or {} if none found.

        Checks approved reviews first (product reviews endpoint), then falls
        back to the admin review search endpoint to catch pending reviews too —
        agents may submit reviews that land in "Pending" status rather than
        "Approved", and both represent a successful submission.
        """
        import requests as _requests

        shopping_base = self.base_urls.get("__SHOPPING__", DEFAULT_BASE_URLS["__SHOPPING__"])
        token = self._shopping_get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}

        # First try the product reviews endpoint (approved reviews only).
        url = f"{shopping_base}/rest/V1/products/{sku}/reviews"
        resp = _requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            reviews = resp.json()
            if reviews:
                return max(reviews, key=lambda r: r.get("id", 0))

        # Fall back to admin search to also find pending/unapproved reviews.
        # Requires knowing the product's entity_id — get it from the product API.
        prod_resp = _requests.get(
            f"{shopping_base}/rest/V1/products/{sku}",
            headers=headers,
            timeout=15,
        )
        if prod_resp.status_code != 200:
            return {}
        product_id = prod_resp.json().get("id")
        if not product_id:
            return {}

        search_url = (
            f"{shopping_base}/rest/V1/reviews"
            f"?searchCriteria[filter_groups][0][filters][0][field]=entity_pk_value"
            f"&searchCriteria[filter_groups][0][filters][0][value]={product_id}"
            f"&searchCriteria[sortOrders][0][field]=id"
            f"&searchCriteria[sortOrders][0][direction]=DESC"
            f"&searchCriteria[pageSize]=1"
        )
        search_resp = _requests.get(search_url, headers=headers, timeout=15)
        if search_resp.status_code != 200:
            return {}
        data = search_resp.json()
        items = data.get("items", [])
        if not items:
            return {}
        return items[0]

    def _shopping_get_sku_latest_review_rating(self, sku: str) -> str:
        """
        Return the rating percentage (e.g. "100", "80", "60", "40", "20")
        of the most recent review for the given SKU.
        5 stars = 100, 4 = 80, 3 = 60, 2 = 40, 1 = 20.
        Returns "" if no reviews exist.

        Used by: func:shopping_get_sku_latest_review_rating('<sku>')
        """
        review = self._shopping_get_latest_review_for_sku(sku)
        ratings = review.get("ratings", [])
        if not ratings:
            return ""
        return str(ratings[0].get("percent", ""))

    def _shopping_get_sku_latest_review_author(self, sku: str) -> str:
        """
        Return the nickname (author) of the most recent review for the
        given SKU.  Returns "" if no reviews exist.

        Used by: func:shopping_get_sku_latest_review_author('<sku>')
        """
        review = self._shopping_get_latest_review_for_sku(sku)
        return review.get("nickname", "")

    def _shopping_get_customer_cart_items(self, email: str, password: str) -> str:
        """
        Return a newline-joined list of product names currently in the
        customer's cart, fetched via the Magento REST API.  Returns "" if
        the cart is empty or authentication fails.

        Avoids browser-session issues by using the REST API directly.
        Used by: func:shopping_get_customer_cart_items('<email>', '<password>')
        """
        import requests as _requests

        shopping_base = self.base_urls.get("__SHOPPING__", DEFAULT_BASE_URLS["__SHOPPING__"])

        # Get a customer token.
        token_resp = _requests.post(
            f"{shopping_base}/rest/V1/integration/customer/token",
            json={"username": email, "password": password},
            timeout=15,
        )
        if token_resp.status_code != 200:
            return ""
        token = token_resp.json()
        if not isinstance(token, str):
            return ""

        headers = {"Authorization": f"Bearer {token}"}
        items_resp = _requests.get(
            f"{shopping_base}/rest/V1/carts/mine/items",
            headers=headers,
            timeout=15,
        )
        if items_resp.status_code != 200:
            return ""
        items = items_resp.json()
        if not isinstance(items, list):
            return ""
        names = [item.get("name", "") for item in items if item.get("name")]
        return "\n".join(names)

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

        # must_include: all items must appear somewhere in content.
        # A nested list item means OR — at least one alternative must match.
        for item in required_contents.get("must_include", []):
            if isinstance(item, list):
                # OR group: at least one alternative must be present
                if not any(
                    self._resolve_placeholder(str(alt)).lower() in content_lower
                    for alt in item
                ):
                    missing.append(item)
            else:
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
