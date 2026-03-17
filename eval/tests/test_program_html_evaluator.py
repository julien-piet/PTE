# tests/test_program_html_evaluator.py
#
# Unit tests for ProgramHtmlEvaluator -- specifically the URL resolution and
# evaluation pipeline under every possible value of final_url.
#
# These tests use a mock Playwright Page so they run fully offline, with no
# live GitLab / Reddit / Shopping server required.
#
# Test matrix for _resolve_url:
#   url field in eval spec           | final_url value | Expected outcome
#   ---------------------------------+-----------------+----------------------------
#   "__GITLAB__/foo/bar"             | None            | resolved to literal URL
#   "__GITLAB__/foo/bar"             | real URL        | literal URL (ignores final)
#   "last"                           | real URL        | final_url returned
#   "last"                           | None            | ValueError -> check fails
#   "last"                           | ""              | ValueError -> check fails
#   ""  (empty)                      | real URL        | final_url returned
#   ""  (empty)                      | None            | falls back to page.url
#   "func:reddit_get_post_url(...)"  | real URL        | subreddit navigated
#   "func:reddit_get_post_url(...)"  | None            | ValueError -> check fails
#   "func:shopping_get_latest..."    | any             | order history navigated
#   "func:unknown(...)"              | any             | ValueError -> check fails
#   "/relative/path"                 | any             | resolved from page origin
#
# Run with:
#   cd "/Users/sylvie/Desktop/API Research/PTE"
#   python3 -m pytest tests/test_program_html_evaluator.py -v

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Path setup so we can import from the project root without installation
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.program_html_evaluator import ProgramHtmlEvaluator, DEFAULT_BASE_URLS


# ---------------------------------------------------------------------------
# Helpers: fake Playwright Page
# ---------------------------------------------------------------------------

def _make_page(current_url: str = "http://localhost:8023/some/page") -> MagicMock:
    """Return a mock Playwright Page with sensible defaults."""
    page = MagicMock()
    page.url = current_url
    # goto() succeeds by default (returns None, doesn't raise)
    page.goto.return_value = None
    # evaluate() returns full body text by default
    page.evaluate.return_value = "page body text"
    # wait_for_selector / wait_for_function / wait_for_timeout succeed silently
    page.wait_for_selector.return_value = None
    page.wait_for_function.return_value = None
    page.wait_for_timeout.return_value = None
    return page


def _make_task(url: str, locator: str = "", required_contents: dict = None,
               reference_url: str = "") -> dict:
    """Build a minimal task dict with one program_html entry."""
    return {
        "task_id": 999,
        "intent": "test task",
        "eval": {
            "eval_types": ["program_html"],
            "reference_url": reference_url,
            "program_html": [
                {
                    "url": url,
                    "locator": locator,
                    "required_contents": required_contents or {"must_include": ["page body text"]},
                }
            ],
        },
    }


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestProgramHtmlEvaluatorUrlResolution(unittest.TestCase):
    """Tests focused on _resolve_url under all final_url conditions."""

    def setUp(self):
        self.ev = ProgramHtmlEvaluator()

    # ------------------------------------------------------------------
    # 1. Literal __PLACEHOLDER__ URLs
    # ------------------------------------------------------------------

    def test_literal_gitlab_url_no_final_url(self):
        """Literal __GITLAB__ URL resolves correctly even when final_url is None."""
        task = _make_task("__GITLAB__/primer/design/-/merge_requests/450")
        page = _make_page()

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertTrue(result["applicable"])
        self.assertEqual(len(result["checks"]), 1)
        chk = result["checks"][0]
        self.assertEqual(chk["resolved_url"],
                         "http://localhost:8023/primer/design/-/merge_requests/450")
        # Navigation called with the resolved URL
        page.goto.assert_called()
        nav_url = page.goto.call_args_list[0][0][0]
        self.assertEqual(nav_url, "http://localhost:8023/primer/design/-/merge_requests/450")

    def test_literal_gitlab_url_with_final_url_ignored(self):
        """Literal URL does not use final_url at all — final_url is irrelevant."""
        task = _make_task("__GITLAB__/byteblaze/metaseq")
        page = _make_page()
        final_url = "http://localhost:8023/completely/different/page"

        result = self.ev.evaluate(task, page, last_url=final_url)

        chk = result["checks"][0]
        self.assertEqual(chk["resolved_url"], "http://localhost:8023/byteblaze/metaseq")
        # Navigation went to the literal URL, not final_url
        nav_url = page.goto.call_args_list[0][0][0]
        self.assertIn("byteblaze/metaseq", nav_url)
        self.assertNotIn("completely/different", nav_url)

    def test_literal_reddit_url(self):
        """__REDDIT__ placeholder is substituted correctly."""
        task = _make_task("__REDDIT__/f/news")
        page = _make_page()

        result = self.ev.evaluate(task, page, last_url=None)

        chk = result["checks"][0]
        self.assertEqual(chk["resolved_url"], "http://localhost:9999/f/news")

    def test_literal_shopping_url(self):
        """__SHOPPING__ placeholder is substituted correctly."""
        task = _make_task("__SHOPPING__/wishlist/")
        page = _make_page()

        result = self.ev.evaluate(task, page, last_url=None)

        chk = result["checks"][0]
        self.assertIn("wishlist", chk["resolved_url"])

    # ------------------------------------------------------------------
    # 2. "last" URL
    # ------------------------------------------------------------------

    def test_last_url_with_valid_final_url(self):
        """'last' resolves to the agent's final_url when it is a real URL."""
        final_url = "http://localhost:8023/byteblaze/dotfiles/-/milestones/3"
        task = _make_task("last")
        page = _make_page()

        result = self.ev.evaluate(task, page, last_url=final_url)

        chk = result["checks"][0]
        self.assertEqual(chk["resolved_url"], final_url)
        nav_url = page.goto.call_args_list[0][0][0]
        self.assertEqual(nav_url, final_url)

    def test_last_url_with_none_final_url_fails_gracefully(self):
        """'last' with final_url=None must fail the check — not crash the suite."""
        task = _make_task("last")
        page = _make_page()

        result = self.ev.evaluate(task, page, last_url=None)

        # Overall result: applicable=True, passed=False
        self.assertTrue(result["applicable"])
        self.assertFalse(result["passed"])
        chk = result["checks"][0]
        self.assertFalse(chk["passed"])
        # Error message must explain what happened
        self.assertIsNotNone(chk["error"])
        self.assertIn("last", chk["error"].lower())
        # Navigation must NOT have been called with a bad URL
        page.goto.assert_not_called()

    def test_last_url_with_empty_string_final_url_fails_gracefully(self):
        """'last' with final_url='' is treated the same as None — falsy check."""
        task = _make_task("last")
        page = _make_page()

        result = self.ev.evaluate(task, page, last_url="")

        self.assertFalse(result["passed"])
        chk = result["checks"][0]
        self.assertFalse(chk["passed"])
        self.assertIsNotNone(chk["error"])

    def test_last_url_case_insensitive(self):
        """'LAST' (uppercase) is still treated as the 'last' pattern."""
        final_url = "http://localhost:8023/some/milestone"
        task = _make_task("LAST")
        page = _make_page()

        result = self.ev.evaluate(task, page, last_url=final_url)

        chk = result["checks"][0]
        self.assertEqual(chk["resolved_url"], final_url)

    def test_last_url_with_whitespace(self):
        """'  last  ' (with surrounding whitespace) is still the 'last' pattern."""
        final_url = "http://localhost:8023/some/milestone"
        task = _make_task("  last  ")
        page = _make_page()

        result = self.ev.evaluate(task, page, last_url=final_url)

        chk = result["checks"][0]
        self.assertEqual(chk["resolved_url"], final_url)

    # ------------------------------------------------------------------
    # 3. Empty URL field
    # ------------------------------------------------------------------

    def test_empty_url_with_final_url(self):
        """Empty url field falls back to final_url when available."""
        final_url = "http://localhost:8023/byteblaze/empathy-prompts/-/merge_requests/19"
        task = _make_task("")
        page = _make_page()

        result = self.ev.evaluate(task, page, last_url=final_url)

        chk = result["checks"][0]
        self.assertEqual(chk["resolved_url"], final_url)

    def test_empty_url_no_final_url_falls_back_to_page_url(self):
        """Empty url field + no final_url falls back to current page.url."""
        page_current = "http://localhost:8023/dashboard"
        task = _make_task("")
        page = _make_page(current_url=page_current)

        result = self.ev.evaluate(task, page, last_url=None)

        chk = result["checks"][0]
        self.assertEqual(chk["resolved_url"], page_current)

    def test_empty_url_with_reference_url_fallback(self):
        """Empty final_url but reference_url set → reference_url used as last_url."""
        ref = "http://localhost:8023/byteblaze/2019-nCov"
        task = _make_task("last", reference_url=ref)
        page = _make_page()

        # final_url is None, but reference_url exists in the eval spec
        result = self.ev.evaluate(task, page, last_url=None)

        # The evaluator resolves reference_url as the fallback for last_url
        chk = result["checks"][0]
        self.assertEqual(chk["resolved_url"], ref)

    # ------------------------------------------------------------------
    # 4. Relative path URLs
    # ------------------------------------------------------------------

    def test_relative_path_resolved_from_page_origin(self):
        """A relative /path is prepended with the current page origin."""
        task = _make_task("/byteblaze/dotfiles/-/project_members")
        page = _make_page(current_url="http://localhost:8023/some/other/page")

        result = self.ev.evaluate(task, page, last_url=None)

        chk = result["checks"][0]
        self.assertTrue(chk["resolved_url"].startswith("http://localhost:8023"))
        self.assertIn("project_members", chk["resolved_url"])

    # ------------------------------------------------------------------
    # 5. func: URL patterns
    # ------------------------------------------------------------------

    def test_func_reddit_with_valid_last_url(self):
        """func:reddit_get_post_url uses last_url as subreddit base."""
        subreddit_url = "http://localhost:9999/f/consoles"
        task = _make_task("func:reddit_get_post_url('__last_url__')")
        page = _make_page()
        # Simulate subreddit page having a post link
        mock_link = MagicMock()
        mock_link.get_attribute.return_value = "/f/consoles/42/some-post-title"
        page.query_selector.return_value = mock_link

        result = self.ev.evaluate(task, page, last_url=subreddit_url)

        chk = result["checks"][0]
        # Should have navigated to the post URL
        self.assertIsNotNone(chk["resolved_url"])
        # No URL-resolution error (error is None when resolution succeeded)
        error = chk.get("error") or ""
        self.assertFalse(error.startswith("URL resolution failed"))

    def test_func_reddit_with_none_last_url_fails_gracefully(self):
        """func:reddit_get_post_url with final_url=None fails the check cleanly."""
        task = _make_task("func:reddit_get_post_url('__last_url__')")
        page = _make_page()

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertFalse(result["passed"])
        chk = result["checks"][0]
        self.assertFalse(chk["passed"])
        self.assertIsNotNone(chk["error"])
        self.assertIn("URL resolution failed", chk["error"])

    def test_func_shopping_get_latest_order_no_last_url_needed(self):
        """func:shopping_get_latest_order_url() does not require final_url."""
        task = _make_task("func:shopping_get_latest_order_url()")
        page = _make_page()
        fake_order_url = "http://shopping.example.com/orders/99/view"

        with patch.object(self.ev, "_shopping_get_latest_order_url",
                          return_value=fake_order_url):
            result = self.ev.evaluate(task, page, last_url=None)

        chk = result["checks"][0]
        self.assertEqual(chk["resolved_url"], fake_order_url)

    def test_func_unknown_pattern_fails_gracefully(self):
        """An unrecognised func: pattern produces a clear error, not a crash."""
        task = _make_task("func:does_not_exist()")
        page = _make_page()

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertFalse(result["passed"])
        chk = result["checks"][0]
        self.assertFalse(chk["passed"])
        self.assertIsNotNone(chk["error"])
        self.assertIn("URL resolution failed", chk["error"])

    # ------------------------------------------------------------------
    # 6. Multiple entries — partial pass
    # ------------------------------------------------------------------

    def test_multiple_entries_one_last_one_literal(self):
        """When one entry is 'last' and one is literal, both are evaluated."""
        final_url = "http://localhost:8023/byteblaze/dotfiles/-/milestones/3"
        task = {
            "task_id": 999,
            "intent": "test",
            "eval": {
                "eval_types": ["program_html"],
                "reference_url": "",
                "program_html": [
                    {
                        "url": "last",
                        "locator": "",
                        "required_contents": {"must_include": ["page body text"]},
                    },
                    {
                        "url": "__GITLAB__/byteblaze/metaseq",
                        "locator": "",
                        "required_contents": {"must_include": ["page body text"]},
                    },
                ],
            },
        }
        page = _make_page()

        result = self.ev.evaluate(task, page, last_url=final_url)

        self.assertEqual(len(result["checks"]), 2)
        # Both should resolve without URL-resolution errors
        for chk in result["checks"]:
            self.assertIsNone(chk.get("error"))
        # First check navigated to final_url, second to the literal
        nav_calls = [c[0][0] for c in page.goto.call_args_list]
        self.assertIn(final_url, nav_calls)
        self.assertIn("http://localhost:8023/byteblaze/metaseq", nav_calls)

    def test_multiple_entries_last_fails_literal_passes(self):
        """If 'last' entry fails (no final_url), other entries still run."""
        task = {
            "task_id": 999,
            "intent": "test",
            "eval": {
                "eval_types": ["program_html"],
                "reference_url": "",
                "program_html": [
                    {
                        "url": "last",
                        "locator": "",
                        "required_contents": {"must_include": ["anything"]},
                    },
                    {
                        "url": "__GITLAB__/byteblaze/metaseq",
                        "locator": "",
                        "required_contents": {"must_include": ["page body text"]},
                    },
                ],
            },
        }
        page = _make_page()

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertEqual(len(result["checks"]), 2)
        # Overall fails because 'last' entry failed
        self.assertFalse(result["passed"])
        # First check failed with URL resolution error
        self.assertFalse(result["checks"][0]["passed"])
        self.assertIsNotNone(result["checks"][0]["error"])
        # Second check still ran and passed (page body text is in mock evaluate result)
        self.assertIsNone(result["checks"][1].get("error"))

    # ------------------------------------------------------------------
    # 7. eval_types guard
    # ------------------------------------------------------------------

    def test_non_program_html_task_returns_not_applicable(self):
        """Tasks without program_html in eval_types return applicable=False."""
        task = {
            "task_id": 1,
            "intent": "test",
            "eval": {
                "eval_types": ["url_match"],
                "reference_url": "http://example.com",
                "program_html": [],
            },
        }
        page = _make_page()

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertFalse(result["applicable"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["checks"], [])

    def test_empty_program_html_list_passes(self):
        """program_html=[] with eval_type set → applicable=True, passed=True."""
        task = {
            "task_id": 1,
            "intent": "test",
            "eval": {
                "eval_types": ["program_html"],
                "reference_url": "",
                "program_html": [],
            },
        }
        page = _make_page()

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertTrue(result["applicable"])
        self.assertTrue(result["passed"])
        self.assertEqual(result["checks"], [])

    # ------------------------------------------------------------------
    # 8. Navigation failures
    # ------------------------------------------------------------------

    def test_navigation_failure_returns_failed_check_not_crash(self):
        """If page.goto raises on all attempts, the check fails with an error."""
        task = _make_task("__GITLAB__/byteblaze/metaseq")
        page = _make_page()
        page.goto.side_effect = Exception("net::ERR_CONNECTION_REFUSED")

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertFalse(result["passed"])
        chk = result["checks"][0]
        self.assertFalse(chk["passed"])
        self.assertIsNotNone(chk["error"])
        self.assertIn("Navigation failed", chk["error"])

    def test_navigation_retried_on_first_failure(self):
        """goto is retried (domcontentloaded) when networkidle times out."""
        task = _make_task("__GITLAB__/byteblaze/metaseq")
        page = _make_page()
        # First goto raises (networkidle timeout), second succeeds
        page.goto.side_effect = [Exception("Timeout"), None]

        result = self.ev.evaluate(task, page, last_url=None)

        # Should have been called at least twice
        self.assertGreaterEqual(page.goto.call_count, 2)
        # Overall check should pass (second navigation succeeded, mock evaluate returns text)
        chk = result["checks"][0]
        self.assertIsNone(chk.get("error"))

    # ------------------------------------------------------------------
    # 9. Locator failures
    # ------------------------------------------------------------------

    def test_locator_exception_returns_failed_check_not_crash(self):
        """If page.evaluate raises, the check fails with a locator error."""
        task = _make_task(
            "__GITLAB__/a11yproject/a11yproject.com/-/merge_requests/1071",
            locator='document.querySelector(\'[id="notes-list"]\').lastElementChild.outerText',
            required_contents={"exact_match": "Good idea"},
        )
        page = _make_page()
        page.evaluate.side_effect = Exception("Cannot read properties of null")

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertFalse(result["passed"])
        chk = result["checks"][0]
        self.assertFalse(chk["passed"])
        self.assertIsNotNone(chk["error"])
        self.assertIn("Locator failed", chk["error"])

    # ------------------------------------------------------------------
    # 10. Content checks
    # ------------------------------------------------------------------

    def test_exact_match_passes(self):
        """exact_match succeeds when extracted content matches (case-insensitive)."""
        task = _make_task(
            "__GITLAB__/foo",
            locator="",
            required_contents={"exact_match": "Good idea"},
        )
        page = _make_page()
        page.evaluate.return_value = "Good idea"

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertTrue(result["passed"])

    def test_exact_match_fails_with_detail(self):
        """exact_match failure records what was missing."""
        task = _make_task(
            "__GITLAB__/foo",
            locator="",
            required_contents={"exact_match": "Good idea"},
        )
        page = _make_page()
        page.evaluate.return_value = "lgtm"

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertFalse(result["passed"])
        chk = result["checks"][0]
        self.assertTrue(len(chk["missing"]) > 0)
        self.assertIn("Good idea", chk["missing"][0])

    def test_must_include_all_present(self):
        """must_include passes when all strings are in the content."""
        task = _make_task(
            "__GITLAB__/foo",
            required_contents={"must_include": ["ChatGPT", "fork"]},
        )
        page = _make_page()
        page.evaluate.return_value = "byteblaze forked ChatGPT from convexegg"

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertTrue(result["passed"])

    def test_must_include_missing_item(self):
        """must_include records exactly which items are missing."""
        task = _make_task(
            "__GITLAB__/foo",
            required_contents={"must_include": ["ChatGPT", "metaseq"]},
        )
        page = _make_page()
        page.evaluate.return_value = "byteblaze forked ChatGPT"

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertFalse(result["passed"])
        chk = result["checks"][0]
        self.assertIn("metaseq", chk["missing"])
        self.assertNotIn("ChatGPT", chk["missing"])

    def test_must_exclude_not_present(self):
        """must_exclude passes when none of the excluded strings appear."""
        task = _make_task(
            "__GITLAB__/foo",
            required_contents={"must_exclude": ["nvidia-patch", "viewgrades-scraper"]},
        )
        page = _make_page()
        page.evaluate.return_value = "byteblaze / SimCache"

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertTrue(result["passed"])

    def test_must_exclude_present_fails(self):
        """must_exclude records exactly which excluded strings were found."""
        task = _make_task(
            "__GITLAB__/foo",
            required_contents={"must_exclude": ["nvidia-patch"]},
        )
        page = _make_page()
        page.evaluate.return_value = "byteblaze forked nvidia-patch"

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertFalse(result["passed"])
        chk = result["checks"][0]
        self.assertIn("nvidia-patch", chk["excluded_found"])

    def test_content_check_case_insensitive(self):
        """must_include checks are case-insensitive."""
        task = _make_task(
            "__GITLAB__/foo",
            required_contents={"must_include": ["Page Not Found"]},
        )
        page = _make_page()
        page.evaluate.return_value = "404 page not found"

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertTrue(result["passed"])

    # ------------------------------------------------------------------
    # 11. Real task shapes from fork_comment_tasks.json
    # ------------------------------------------------------------------

    def test_fork_task_shape_passes(self):
        """Simulates a fork task eval: page contains the project name."""
        task = _make_task(
            "__GITLAB__/byteblaze/metaseq",
            locator="",
            required_contents={"must_include": ["metaseq"]},
        )
        page = _make_page()
        page.evaluate.return_value = "byteblaze / metaseq · GitLab"

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertTrue(result["passed"])

    def test_comment_task_shape_with_notes_list_locator(self):
        """Simulates a comment task: notes-list locator returns the comment."""
        locator = (
            "document.querySelector('[id=\"notes-list\"').lastElementChild"
            ".querySelector('.timeline-discussion-body').outerText"
        )
        task = _make_task(
            "__GITLAB__/a11yproject/a11yproject.com/-/merge_requests/1071",
            locator=locator,
            required_contents={"exact_match": "Good idea"},
        )
        page = _make_page()
        # wait_for_selector + wait_for_function succeed, evaluate returns comment body
        page.evaluate.return_value = "Good idea"

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertTrue(result["passed"])
        # notes-list selector was awaited
        page.wait_for_selector.assert_called_once_with('[id="notes-list"]', timeout=15000)

    def test_fork_task_not_found_fails_with_missing(self):
        """If forked project doesn't exist, page shows 'Page Not Found'."""
        task = _make_task(
            "__GITLAB__/byteblaze/ChatGPT",
            locator="",
            required_contents={"must_include": ["ChatGPT"]},
        )
        page = _make_page()
        page.evaluate.return_value = "Page Not Found"

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertFalse(result["passed"])
        chk = result["checks"][0]
        self.assertIn("ChatGPT", chk["missing"])

    def test_task398_must_exclude_pattern(self):
        """Task 398: repos that should NOT be forked must be absent."""
        task = _make_task(
            "__GITLAB__/byteblaze/nvidia-patch",
            locator="",
            required_contents={"must_include": ["Page Not Found"]},
        )
        page = _make_page()
        # GitLab 404 page text
        page.evaluate.return_value = "Page Not Found — The page you're looking for doesn't exist."

        result = self.ev.evaluate(task, page, last_url=None)

        self.assertTrue(result["passed"])


class TestProgramHtmlEvaluatorCustomBaseUrls(unittest.TestCase):
    """Tests that base_urls injection works for test isolation."""

    def test_custom_base_urls_override_defaults(self):
        """Passing base_urls= lets tests point at a different server."""
        custom = {"__GITLAB__": "http://test-server:9999"}
        ev = ProgramHtmlEvaluator(base_urls=custom)
        task = _make_task("__GITLAB__/byteblaze/metaseq")
        page = _make_page()

        result = ev.evaluate(task, page, last_url=None)

        chk = result["checks"][0]
        self.assertTrue(chk["resolved_url"].startswith("http://test-server:9999"))


class TestResolveUrlDirectly(unittest.TestCase):
    """Unit tests for _resolve_url without going through evaluate()."""

    def setUp(self):
        self.ev = ProgramHtmlEvaluator()

    def test_last_with_url(self):
        page = _make_page()
        url = "http://localhost:8023/foo"
        result = self.ev._resolve_url("last", page, url)
        self.assertEqual(result, url)

    def test_last_none_raises(self):
        page = _make_page()
        with self.assertRaises(ValueError):
            self.ev._resolve_url("last", page, None)

    def test_last_empty_string_raises(self):
        page = _make_page()
        with self.assertRaises(ValueError):
            self.ev._resolve_url("last", page, "")

    def test_empty_raw_url_prefers_last_url(self):
        page = _make_page(current_url="http://page-current.com")
        result = self.ev._resolve_url("", page, "http://last.com/foo")
        self.assertEqual(result, "http://last.com/foo")

    def test_empty_raw_url_falls_back_to_page_url(self):
        page = _make_page(current_url="http://page-current.com")
        result = self.ev._resolve_url("", page, None)
        self.assertEqual(result, "http://page-current.com")

    def test_placeholder_substitution(self):
        page = _make_page()
        result = self.ev._resolve_url("__GITLAB__/foo/bar", page, None)
        self.assertEqual(result, "http://localhost:8023/foo/bar")

    def test_relative_path_prefixed_with_origin(self):
        page = _make_page(current_url="http://localhost:8023/some/page")
        result = self.ev._resolve_url("/foo/bar", page, None)
        self.assertEqual(result, "http://localhost:8023/foo/bar")

    def test_direct_http_url_unchanged(self):
        page = _make_page()
        url = "http://example.com/some/path"
        result = self.ev._resolve_url(url, page, None)
        self.assertEqual(result, url)

    def test_unknown_func_raises(self):
        page = _make_page()
        with self.assertRaises(ValueError):
            self.ev._resolve_url("func:totally_unknown()", page, None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
