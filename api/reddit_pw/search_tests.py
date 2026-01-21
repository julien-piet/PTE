"""Checks for the search helper."""

from __future__ import annotations

import sys
from pathlib import Path
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

api_stub = types.ModuleType("api")
api_stub.__path__ = [str(Path(__file__).resolve().parents[1])]
sys.modules["api"] = api_stub

playwright_stub = types.ModuleType("playwright")
playwright_stub.sync_api = types.SimpleNamespace(Page=object)
sys.modules["playwright"] = playwright_stub
sys.modules["playwright.sync_api"] = playwright_stub.sync_api

from api.reddit_pw import search  # noqa:E402
from api.reddit_pw.test_utils import FakeLocator, FakePage  # noqa:E402


class SearchTests(unittest.TestCase):
    def test_search_returns_results(self) -> None:
        """Test search returns results."""
        title_link = FakeLocator(
            text="Search Result Title",
            count_value=1,
            attributes={"href": "/f/test/789"}
        )
        author_link = FakeLocator(text="searchauthor", count_value=1)
        forum_link = FakeLocator(text="searchforum", count_value=1)
        score_elem = FakeLocator(text="15", count_value=1)
        
        result_elem = FakeLocator(
            count_value=1,
            nested={
                search.SUBMISSION_TITLE_SELECTOR: title_link,
                search.SUBMISSION_AUTHOR_SELECTOR: author_link,
                search.SUBMISSION_FORUM_SELECTOR: forum_link,
                search.SUBMISSION_SCORE_SELECTOR: score_elem,
            }
        )
        
        results_locator = FakeLocator(
            children=[result_elem],
            count_value=1
        )
        
        page = FakePage(
            locators={
                f"{search.SUBMISSION_SELECTOR}, .search-result": results_locator,
            },
            url=f"{search.BASE_URL}search?q=test"
        )
        
        result = search.search_submissions(page, query="test")
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].title, "Search Result Title")
        self.assertEqual(result.results[0].author, "searchauthor")
        self.assertEqual(result.results[0].forum, "searchforum")
        self.assertEqual(result.results[0].score, "15")
    
    def test_search_with_forum_filter(self) -> None:
        """Test search with forum filter."""
        title_link = FakeLocator(
            text="Filtered Result",
            count_value=1,
            attributes={"href": "/f/tech/999"}
        )
        
        result_elem = FakeLocator(
            count_value=1,
            nested={
                search.SUBMISSION_TITLE_SELECTOR: title_link,
                search.SUBMISSION_AUTHOR_SELECTOR: FakeLocator(count_value=0),
                search.SUBMISSION_FORUM_SELECTOR: FakeLocator(text="tech", count_value=1),
                search.SUBMISSION_SCORE_SELECTOR: FakeLocator(count_value=0),
            }
        )
        
        results_locator = FakeLocator(
            children=[result_elem],
            count_value=1
        )
        
        page = FakePage(
            locators={
                f"{search.SUBMISSION_SELECTOR}, .search-result": results_locator,
            },
            url=f"{search.BASE_URL}search?q=python&forum=tech"
        )
        
        result = search.search_submissions(page, query="python", forum="tech")
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.results), 1)
        self.assertIn("tech", page.url)
    
    def test_search_no_results_returns_empty_list(self) -> None:
        """Test search with no results."""
        page = FakePage(
            locators={
                f"{search.SUBMISSION_SELECTOR}, .search-result": FakeLocator(count_value=0),
            },
            url=f"{search.BASE_URL}search?q=nonexistent"
        )
        
        result = search.search_submissions(page, query="nonexistent")
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.results), 0)
    
    def test_search_with_multiple_filters(self) -> None:
        """Test search with multiple filters."""
        page = FakePage(
            locators={
                f"{search.SUBMISSION_SELECTOR}, .search-result": FakeLocator(count_value=0),
            },
            url=f"{search.BASE_URL}search"
        )
        
        result = search.search_submissions(
            page,
            query="test",
            forum="technology",
            author="testuser",
            sort="top"
        )
        
        self.assertTrue(result.success)
        self.assertIn("forum=technology", page.url)
        self.assertIn("author=testuser", page.url)
        self.assertIn("sort=top", page.url)


if __name__ == "__main__":
    unittest.main()
