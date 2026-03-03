# tests/test_url_match_evaluator.py
#
# Unit tests for UrlMatchEvaluator — covering every matching mode and
# final_url scenario.
#
# Test matrix:
#   reference_url pattern    | url_note       | actual_url        | Expected
#   -------------------------+----------------+-------------------+----------
#   single __GITLAB__ URL    | "GOLD in PRED" | contains expected | PASS
#   single __GITLAB__ URL    | "GOLD in PRED" | missing expected  | FAIL
#   single __GITLAB__ URL    | ""             | exact match       | PASS
#   single __GITLAB__ URL    | ""             | starts with       | PASS
#   single __GITLAB__ URL    | ""             | wrong URL         | FAIL
#   URL1 |OR| URL2           | "GOLD in PRED" | matches URL1      | PASS
#   URL1 |OR| URL2           | "GOLD in PRED" | matches URL2      | PASS
#   URL1 |OR| URL2           | "GOLD in PRED" | matches neither   | FAIL
#   any                      | any            | None              | FAIL (error)
#   any                      | any            | ""                | FAIL (error)
#   not url_match task        | —              | any               | applicable=False
#   empty reference_url      | any            | any               | FAIL (error)
#
# Run with:
#   cd "/Users/sylvie/Desktop/API Research/PTE"
#   python3 -m pytest tests/test_url_match_evaluator.py -v

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from url_match_evaluator import UrlMatchEvaluator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(
    reference_url: str,
    url_note: str = "GOLD in PRED",
    eval_types: list = None,
) -> dict:
    return {
        "task_id": 999,
        "intent": "test task",
        "eval": {
            "eval_types": eval_types if eval_types is not None else ["url_match"],
            "reference_url": reference_url,
            "url_note": url_note,
        },
    }


GITLAB_BASE = "http://localhost:8023"
REDDIT_BASE = "http://localhost:9999"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestUrlMatchEvaluatorGoldInPred(unittest.TestCase):
    """Mode: url_note == 'GOLD in PRED' — expected is a substring of actual."""

    def setUp(self):
        self.ev = UrlMatchEvaluator()

    def test_passes_when_expected_in_actual(self):
        """Standard GOLD in PRED: expected URL appears inside the actual URL."""
        task = _make_task("__GITLAB__/dashboard/todos", url_note="GOLD in PRED")
        actual = f"{GITLAB_BASE}/dashboard/todos?sort=created_date"

        result = self.ev.evaluate(task, actual)

        self.assertTrue(result["applicable"])
        self.assertTrue(result["passed"])
        self.assertEqual(result["match_mode"], "gold_in_pred")
        self.assertIsNotNone(result["matched_url"])

    def test_fails_when_expected_not_in_actual(self):
        """GOLD in PRED fails when expected is not a substring of actual."""
        task = _make_task("__GITLAB__/dashboard/todos", url_note="GOLD in PRED")
        actual = f"{GITLAB_BASE}/dashboard/merge_requests"

        result = self.ev.evaluate(task, actual)

        self.assertFalse(result["passed"])
        self.assertIsNone(result["matched_url"])
        self.assertIsNone(result["error"])

    def test_placeholder_substituted_before_matching(self):
        """__GITLAB__ placeholder is resolved before the substring check."""
        task = _make_task("__GITLAB__/byteblaze/metaseq", url_note="GOLD in PRED")
        actual = f"{GITLAB_BASE}/byteblaze/metaseq"

        result = self.ev.evaluate(task, actual)

        self.assertTrue(result["passed"])
        self.assertIn(GITLAB_BASE, result["expected_urls"][0])

    def test_query_string_in_expected_must_appear_in_actual(self):
        """Query params in reference_url must also be present in actual."""
        task = _make_task(
            "__GITLAB__/a11yproject/a11yproject.com/-/issues/?sort=created_asc&state=opened",
            url_note="GOLD in PRED",
        )
        # actual has both required params
        actual = (
            f"{GITLAB_BASE}/a11yproject/a11yproject.com/-/issues/"
            "?sort=created_asc&state=opened&page=1"
        )
        result = self.ev.evaluate(task, actual)
        self.assertTrue(result["passed"])

    def test_query_string_missing_from_actual_fails(self):
        """If the required query string is absent, GOLD in PRED fails."""
        task = _make_task(
            "__GITLAB__/a11yproject/a11yproject.com/-/issues/?state=opened",
            url_note="GOLD in PRED",
        )
        actual = f"{GITLAB_BASE}/a11yproject/a11yproject.com/-/issues/"

        result = self.ev.evaluate(task, actual)

        self.assertFalse(result["passed"])

    def test_reddit_placeholder_substituted(self):
        """__REDDIT__ placeholder is resolved correctly."""
        task = _make_task("__REDDIT__/f/LifeProTips", url_note="GOLD in PRED")
        actual = f"{REDDIT_BASE}/f/LifeProTips?sort=new"

        result = self.ev.evaluate(task, actual)

        self.assertTrue(result["passed"])
        self.assertTrue(result["expected_urls"][0].startswith(REDDIT_BASE))


class TestUrlMatchEvaluatorExactOrPrefix(unittest.TestCase):
    """Mode: url_note == '' — exact equality or prefix match."""

    def setUp(self):
        self.ev = UrlMatchEvaluator()

    def test_exact_match_passes(self):
        """Exact URL equality passes with empty url_note."""
        task = _make_task("__GITLAB__/dashboard/todos", url_note="")
        actual = f"{GITLAB_BASE}/dashboard/todos"

        result = self.ev.evaluate(task, actual)

        self.assertTrue(result["passed"])
        self.assertEqual(result["match_mode"], "exact_or_prefix")

    def test_prefix_match_passes(self):
        """actual starting with expected passes (agent may append query params)."""
        task = _make_task("__GITLAB__/dashboard/todos", url_note="")
        actual = f"{GITLAB_BASE}/dashboard/todos?assigned=me"

        result = self.ev.evaluate(task, actual)

        self.assertTrue(result["passed"])

    def test_wrong_url_fails(self):
        """A completely different URL fails with exact_or_prefix mode."""
        task = _make_task("__GITLAB__/dashboard/todos", url_note="")
        actual = f"{GITLAB_BASE}/dashboard/merge_requests"

        result = self.ev.evaluate(task, actual)

        self.assertFalse(result["passed"])

    def test_substring_not_enough_for_exact_or_prefix(self):
        """GOLD in PRED logic does NOT apply to exact_or_prefix mode."""
        # expected appears inside actual but actual doesn't start with expected
        task = _make_task("__GITLAB__/dashboard/todos", url_note="")
        actual = f"{GITLAB_BASE}/some/other/page?redirect={GITLAB_BASE}/dashboard/todos"

        result = self.ev.evaluate(task, actual)

        # Should FAIL — actual does not equal or start with expected
        self.assertFalse(result["passed"])


class TestUrlMatchEvaluatorOrAlternatives(unittest.TestCase):
    """reference_url contains |OR| — any alternative matching is a pass."""

    def setUp(self):
        self.ev = UrlMatchEvaluator()

    def test_first_alternative_matches(self):
        """Passes when actual matches the first |OR| alternative."""
        task = _make_task(
            "__REDDIT__/f/machinelearning |OR| __REDDIT__/f/deeplearning |OR| __REDDIT__/f/technology",
            url_note="GOLD in PRED",
        )
        actual = f"{REDDIT_BASE}/f/machinelearning/submit"

        result = self.ev.evaluate(task, actual)

        self.assertTrue(result["passed"])
        self.assertEqual(len(result["expected_urls"]), 3)
        self.assertIn("machinelearning", result["matched_url"])

    def test_last_alternative_matches(self):
        """Passes when actual matches the last |OR| alternative."""
        task = _make_task(
            "__REDDIT__/f/machinelearning |OR| __REDDIT__/f/deeplearning |OR| __REDDIT__/f/technology",
            url_note="GOLD in PRED",
        )
        actual = f"{REDDIT_BASE}/f/technology/new_post"

        result = self.ev.evaluate(task, actual)

        self.assertTrue(result["passed"])
        self.assertIn("technology", result["matched_url"])

    def test_no_alternative_matches(self):
        """Fails when actual matches none of the |OR| alternatives."""
        task = _make_task(
            "__REDDIT__/f/machinelearning |OR| __REDDIT__/f/deeplearning",
            url_note="GOLD in PRED",
        )
        actual = f"{REDDIT_BASE}/f/gaming/submit"

        result = self.ev.evaluate(task, actual)

        self.assertFalse(result["passed"])
        self.assertIsNone(result["matched_url"])
        self.assertEqual(len(result["expected_urls"]), 2)

    def test_all_alternatives_resolved(self):
        """All |OR| alternatives have their placeholders resolved."""
        task = _make_task(
            "__REDDIT__/f/machinelearning |OR| __REDDIT__/f/deeplearning",
            url_note="GOLD in PRED",
        )
        result = self.ev.evaluate(task, actual_url=f"{REDDIT_BASE}/f/machinelearning")

        for url in result["expected_urls"]:
            self.assertNotIn("__REDDIT__", url)
            self.assertIn(REDDIT_BASE, url)

    def test_or_with_exact_mode(self):
        """|OR| alternatives also work in exact_or_prefix mode."""
        task = _make_task(
            "__GITLAB__/dashboard/todos |OR| __GITLAB__/dashboard/merge_requests",
            url_note="",
        )
        actual = f"{GITLAB_BASE}/dashboard/merge_requests"

        result = self.ev.evaluate(task, actual)

        self.assertTrue(result["passed"])
        self.assertIn("merge_requests", result["matched_url"])


class TestUrlMatchEvaluatorMissingFinalUrl(unittest.TestCase):
    """final_url is None or empty — should fail cleanly with an error."""

    def setUp(self):
        self.ev = UrlMatchEvaluator()

    def test_none_final_url_fails_with_error(self):
        """None actual_url produces a structured failure — not an exception."""
        task = _make_task("__GITLAB__/dashboard/todos")

        result = self.ev.evaluate(task, actual_url=None)

        self.assertTrue(result["applicable"])
        self.assertFalse(result["passed"])
        self.assertIsNotNone(result["error"])
        self.assertIn("final_url", result["error"])

    def test_empty_string_final_url_fails_with_error(self):
        """Empty string actual_url is treated the same as None."""
        task = _make_task("__GITLAB__/dashboard/todos")

        result = self.ev.evaluate(task, actual_url="")

        self.assertFalse(result["passed"])
        self.assertIsNotNone(result["error"])

    def test_none_with_or_alternatives_still_fails(self):
        """|OR| tasks also fail cleanly when final_url is absent."""
        task = _make_task(
            "__REDDIT__/f/machinelearning |OR| __REDDIT__/f/deeplearning"
        )

        result = self.ev.evaluate(task, actual_url=None)

        self.assertFalse(result["passed"])
        self.assertIsNotNone(result["error"])
        # expected_urls still populated (so caller can show what was expected)
        self.assertEqual(len(result["expected_urls"]), 2)


class TestUrlMatchEvaluatorGuards(unittest.TestCase):
    """Guard conditions: non-url_match tasks, empty reference_url."""

    def setUp(self):
        self.ev = UrlMatchEvaluator()

    def test_non_url_match_task_returns_not_applicable(self):
        """Tasks without url_match in eval_types return applicable=False."""
        task = _make_task("__GITLAB__/foo", eval_types=["program_html"])

        result = self.ev.evaluate(task, actual_url="http://localhost:8023/foo")

        self.assertFalse(result["applicable"])
        self.assertFalse(result["passed"])

    def test_empty_reference_url_fails_with_error(self):
        """Empty reference_url is a task spec error — fails cleanly."""
        task = _make_task("", eval_types=["url_match"])

        result = self.ev.evaluate(task, actual_url="http://localhost:8023/foo")

        self.assertTrue(result["applicable"])
        self.assertFalse(result["passed"])
        self.assertIsNotNone(result["error"])
        self.assertIn("reference_url", result["error"])

    def test_mixed_eval_types_url_match_only(self):
        """url_match is applicable even when combined with other eval_types."""
        task = _make_task("__GITLAB__/dashboard/todos", eval_types=["url_match", "program_html"])
        actual = f"{GITLAB_BASE}/dashboard/todos"

        result = self.ev.evaluate(task, actual)

        self.assertTrue(result["applicable"])
        self.assertTrue(result["passed"])


class TestUrlMatchEvaluatorCustomBaseUrls(unittest.TestCase):
    """Custom base_urls= injection for test isolation."""

    def test_custom_base_urls_used_for_resolution(self):
        """Passing base_urls= lets tests use a different server address."""
        custom = {"__GITLAB__": "http://test-gitlab:9999"}
        ev = UrlMatchEvaluator(base_urls=custom)
        task = _make_task("__GITLAB__/dashboard/todos", url_note="GOLD in PRED")
        actual = "http://test-gitlab:9999/dashboard/todos"

        result = ev.evaluate(task, actual)

        self.assertTrue(result["passed"])
        self.assertIn("http://test-gitlab:9999", result["expected_urls"][0])


class TestUrlMatchEvaluatorResultShape(unittest.TestCase):
    """Verify the result dict always has the required keys regardless of outcome."""

    REQUIRED_KEYS = {"applicable", "passed", "expected_urls", "actual_url",
                     "match_mode", "matched_url", "error"}

    def setUp(self):
        self.ev = UrlMatchEvaluator()

    def _assert_shape(self, result):
        self.assertEqual(set(result.keys()), self.REQUIRED_KEYS)

    def test_shape_on_pass(self):
        task = _make_task("__GITLAB__/dashboard/todos")
        result = self.ev.evaluate(task, f"{GITLAB_BASE}/dashboard/todos")
        self._assert_shape(result)

    def test_shape_on_fail_wrong_url(self):
        task = _make_task("__GITLAB__/dashboard/todos")
        result = self.ev.evaluate(task, f"{GITLAB_BASE}/dashboard/other")
        self._assert_shape(result)

    def test_shape_on_fail_none_url(self):
        task = _make_task("__GITLAB__/dashboard/todos")
        result = self.ev.evaluate(task, None)
        self._assert_shape(result)

    def test_shape_on_not_applicable(self):
        task = _make_task("__GITLAB__/foo", eval_types=["string_match"])
        result = self.ev.evaluate(task, "http://anything")
        self._assert_shape(result)

    def test_shape_on_empty_reference_url(self):
        task = _make_task("")
        result = self.ev.evaluate(task, "http://anything")
        self._assert_shape(result)


class TestUrlMatchEvaluatorRealTaskShapes(unittest.TestCase):
    """Smoke tests using exact task shapes from the benchmark task files."""

    def setUp(self):
        self.ev = UrlMatchEvaluator()

    def test_task_44_check_todos(self):
        """task 44: Check out my todos → __GITLAB__/dashboard/todos"""
        task = {
            "task_id": 44,
            "intent": "Check out my todos",
            "eval": {
                "eval_types": ["url_match"],
                "reference_url": "__GITLAB__/dashboard/todos",
                "url_note": "GOLD in PRED",
            },
        }
        actual = f"{GITLAB_BASE}/dashboard/todos"
        result = self.ev.evaluate(task, actual)
        self.assertTrue(result["passed"])

    def test_task_45_issues_with_query_string(self):
        """task 45: issues sorted by created_asc — must include full query string."""
        task = {
            "task_id": 45,
            "intent": "Check out the most recent open issues",
            "eval": {
                "eval_types": ["url_match"],
                "reference_url": "__GITLAB__/a11yproject/a11yproject.com/-/issues/?sort=created_asc&state=opened",
                "url_note": "GOLD in PRED",
            },
        }
        # Agent navigated to the issues page with required params
        actual = f"{GITLAB_BASE}/a11yproject/a11yproject.com/-/issues/?sort=created_asc&state=opened"
        result = self.ev.evaluate(task, actual)
        self.assertTrue(result["passed"])

    def test_task_681_reddit_or_alternatives(self):
        """task 681: reddit post — any of three subreddits is acceptable."""
        task = {
            "task_id": 681,
            "intent": "Post something to ML communities",
            "eval": {
                "eval_types": ["url_match"],
                "reference_url": "__REDDIT__/f/machinelearning |OR| __REDDIT__/f/deeplearning |OR| __REDDIT__/f/technology",
                "url_note": "GOLD in PRED",
            },
        }
        # Agent posted to deeplearning
        actual = f"{REDDIT_BASE}/f/deeplearning/submit/success"
        result = self.ev.evaluate(task, actual)
        self.assertTrue(result["passed"])
        self.assertIn("deeplearning", result["matched_url"])

    def test_task_681_wrong_subreddit_fails(self):
        """task 681: posting to a non-matching subreddit fails."""
        task = {
            "task_id": 681,
            "intent": "Post something to ML communities",
            "eval": {
                "eval_types": ["url_match"],
                "reference_url": "__REDDIT__/f/machinelearning |OR| __REDDIT__/f/deeplearning |OR| __REDDIT__/f/technology",
                "url_note": "GOLD in PRED",
            },
        }
        actual = f"{REDDIT_BASE}/f/gaming/submit"
        result = self.ev.evaluate(task, actual)
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
