"""Checks for the browse helper."""

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

from api.reddit_pw import browse  # noqa:E402
from api.reddit_pw.test_utils import FakeLocator, FakePage  # noqa:E402


class BrowseTests(unittest.TestCase):
    def test_browse_frontpage_returns_submissions(self) -> None:
        """Test browsing frontpage returns submissions."""
        title_link = FakeLocator(
            text="Test Post Title",
            count_value=1,
            attributes={"href": "/f/test/123"}
        )
        author_link = FakeLocator(text="testuser", count_value=1)
        forum_link = FakeLocator(text="testforum", count_value=1)
        score_elem = FakeLocator(text="42", count_value=1)
        
        submission_elem = FakeLocator(
            count_value=1,
            nested={
                browse.SUBMISSION_TITLE_SELECTOR: title_link,
                browse.SUBMISSION_AUTHOR_SELECTOR: author_link,
                browse.SUBMISSION_FORUM_SELECTOR: forum_link,
                browse.SUBMISSION_SCORE_SELECTOR: score_elem,
            }
        )
        
        submissions_locator = FakeLocator(
            children=[submission_elem],
            count_value=1
        )
        
        page = FakePage(
            locators={
                browse.SUBMISSION_SELECTOR: submissions_locator,
            },
            url=browse.BASE_URL
        )
        
        result = browse.browse_frontpage(page, sort="hot", scope="all")
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.submissions), 1)
        self.assertEqual(result.submissions[0].title, "Test Post Title")
        self.assertEqual(result.submissions[0].author, "testuser")
        self.assertEqual(result.submissions[0].forum, "testforum")
        self.assertEqual(result.submissions[0].score, "42")
    
    def test_browse_forum_returns_submissions(self) -> None:
        """Test browsing specific forum."""
        title_link = FakeLocator(
            text="Forum Post",
            count_value=1,
            attributes={"href": "/f/tech/456"}
        )
        
        submission_elem = FakeLocator(
            count_value=1,
            nested={
                browse.SUBMISSION_TITLE_SELECTOR: title_link,
                browse.SUBMISSION_AUTHOR_SELECTOR: FakeLocator(text="author1", count_value=1),
                browse.SUBMISSION_SCORE_SELECTOR: FakeLocator(text="10", count_value=1),
                browse.SUBMISSION_COMMENTS_SELECTOR: FakeLocator(text="5 comments", count_value=1),
            }
        )
        
        submissions_locator = FakeLocator(
            children=[submission_elem],
            count_value=1
        )
        
        page = FakePage(
            locators={
                browse.SUBMISSION_SELECTOR: submissions_locator,
                "h1:has-text('Not Found')": FakeLocator(count_value=0),
            },
            url=f"{browse.BASE_URL}f/technology/hot"
        )
        
        result = browse.browse_forum(page, "technology", sort="hot")
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.submissions), 1)
        self.assertEqual(result.submissions[0].title, "Forum Post")
        self.assertEqual(result.submissions[0].comments, "5 comments")
    
    def test_browse_forum_not_found_returns_error(self) -> None:
        """Test browsing non-existent forum."""
        not_found_header = FakeLocator(text="Not Found", count_value=1)
        
        page = FakePage(
            locators={
                browse.SUBMISSION_SELECTOR: FakeLocator(count_value=0),
                "h1:has-text('Not Found')": not_found_header,
            },
            url=f"{browse.BASE_URL}f/nonexistent/hot"
        )
        
        result = browse.browse_forum(page, "nonexistent", sort="hot")
        
        self.assertFalse(result.success)
        self.assertIn("not found", (result.error_message or "").lower())
    
    def test_browse_empty_forum_returns_empty_list(self) -> None:
        """Test browsing empty forum returns empty list."""
        page = FakePage(
            locators={
                browse.SUBMISSION_SELECTOR: FakeLocator(count_value=0),
                "h1:has-text('Not Found')": FakeLocator(count_value=0),
            },
            url=f"{browse.BASE_URL}f/empty/hot"
        )
        
        result = browse.browse_forum(page, "empty", sort="hot")
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.submissions), 0)


if __name__ == "__main__":
    unittest.main()
