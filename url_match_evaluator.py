# url_match_evaluator.py
#
# Evaluates url_match tasks from WebArena task definitions.
#
# A url_match task passes when the agent's final_url satisfies the
# reference_url condition defined in the task eval spec.
#
# Three matching modes, determined by the url_note and reference_url fields:
#
#   Mode              | url_note       | reference_url        | Condition
#   ------------------+----------------+----------------------+------------------
#   GOLD in PRED      | "GOLD in PRED" | single URL           | expected in actual
#   exact / prefix    | ""             | single URL           | actual == expected
#                     |                |                      | OR actual starts with expected
#   OR alternatives   | any            | "URL1 |OR| URL2 ..." | any alternative matches
#
# Usage:
#   from url_match_evaluator import UrlMatchEvaluator
#
#   evaluator = UrlMatchEvaluator()
#   result = evaluator.evaluate(task, actual_url="http://...")
#
# Run tests:
#   python3 -m pytest tests/test_url_match_evaluator.py -v

from typing import Any, Dict, List, Optional
from program_html_evaluator import DEFAULT_BASE_URLS

_OR_SEPARATOR = " |OR| "


class UrlMatchEvaluator:
    """
    Evaluates the url_match component of a WebArena task.

    For each task, it:
      1. Extracts reference_url from the eval spec
      2. Splits on |OR| to get the list of acceptable URLs
      3. Substitutes __PLACEHOLDER__ tokens with real base URLs
      4. Checks actual_url against all alternatives using the match mode
         determined by url_note ("GOLD in PRED" vs exact/prefix)

    Returns a structured result dict — never raises.
    """

    def __init__(self, base_urls: Optional[Dict[str, str]] = None):
        self.base_urls = base_urls if base_urls is not None else DEFAULT_BASE_URLS

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def evaluate(
        self,
        task: Dict[str, Any],
        actual_url: Optional[str],
    ) -> Dict[str, Any]:
        """
        Evaluate the url_match section of a task.

        Args:
            task:       Full task dict (must contain task["eval"]).
            actual_url: The final URL the agent navigated to. May be None.

        Returns:
            {
                "applicable":    bool   # False when eval_type is not url_match
                "passed":        bool
                "expected_urls": list   # Resolved alternatives (after |OR| + placeholder sub)
                "actual_url":    str | None
                "match_mode":    str    # "gold_in_pred" | "exact_or_prefix"
                "matched_url":   str | None  # Which expected_url matched, if any
                "error":         str | None
            }
        """
        eval_section = task.get("eval", {})
        eval_types = eval_section.get("eval_types", [])

        if "url_match" not in eval_types:
            return self._result(
                applicable=False,
                passed=False,
                expected_urls=[],
                actual_url=actual_url,
                match_mode="",
                error="eval_types does not include url_match",
            )

        raw_reference = eval_section.get("reference_url", "") or ""
        if not raw_reference:
            return self._result(
                applicable=True,
                passed=False,
                expected_urls=[],
                actual_url=actual_url,
                match_mode="",
                error="reference_url is empty",
            )

        # Split |OR| alternatives and resolve placeholders in each
        alternatives = [
            self._resolve_placeholder(alt.strip())
            for alt in raw_reference.split(_OR_SEPARATOR)
            if alt.strip()
        ]

        url_note = eval_section.get("url_note", "") or ""
        match_mode = "gold_in_pred" if url_note == "GOLD in PRED" else "exact_or_prefix"

        if not actual_url:
            return self._result(
                applicable=True,
                passed=False,
                expected_urls=alternatives,
                actual_url=actual_url,
                match_mode=match_mode,
                error="actual_url is None or empty — agent did not return a final_url",
            )

        # Check each alternative; pass on first match
        for expected in alternatives:
            if self._matches(actual_url, expected, match_mode):
                return self._result(
                    applicable=True,
                    passed=True,
                    expected_urls=alternatives,
                    actual_url=actual_url,
                    match_mode=match_mode,
                    matched_url=expected,
                )

        return self._result(
            applicable=True,
            passed=False,
            expected_urls=alternatives,
            actual_url=actual_url,
            match_mode=match_mode,
        )

    # ------------------------------------------------------------------
    # Matching logic
    # ------------------------------------------------------------------

    def _matches(self, actual: str, expected: str, mode: str) -> bool:
        """Return True if actual satisfies expected under the given mode."""
        if mode == "gold_in_pred":
            # Expected URL must appear as a substring of actual
            return expected in actual
        else:
            # Exact equality OR actual begins with expected
            # (handles trailing query params or fragment the agent appended)
            return actual == expected or actual.startswith(expected)

    # ------------------------------------------------------------------
    # Placeholder substitution
    # ------------------------------------------------------------------

    def _resolve_placeholder(self, url: str) -> str:
        """Replace __PLACEHOLDER__ tokens with real base URLs."""
        for token, base in self.base_urls.items():
            url = url.replace(token, base)
        return url

    # ------------------------------------------------------------------
    # Result factory
    # ------------------------------------------------------------------

    @staticmethod
    def _result(
        applicable: bool,
        passed: bool,
        expected_urls: List[str],
        actual_url: Optional[str],
        match_mode: str,
        matched_url: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "applicable": applicable,
            "passed": passed,
            "expected_urls": expected_urls,
            "actual_url": actual_url,
            "match_mode": match_mode,
            "matched_url": matched_url,
            "error": error,
        }
