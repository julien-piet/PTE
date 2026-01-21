"""Search functionality."""

from dataclasses import dataclass
from typing import List, Optional

from playwright.sync_api import Page

from .constants import (
    BASE_URL,
    SUBMISSION_SELECTOR,
    SUBMISSION_TITLE_SELECTOR,
    SUBMISSION_AUTHOR_SELECTOR,
    SUBMISSION_FORUM_SELECTOR,
    SUBMISSION_SCORE_SELECTOR,
)


@dataclass
class SearchResult:
    """A single search result."""
    
    title: str
    link: str
    author: str
    forum: str
    score: str


@dataclass
class SearchResults:
    """Search results."""
    
    success: bool
    results: List[SearchResult]
    error_message: Optional[str] = None


def search_submissions(
    page: Page,
    query: str,
    forum: Optional[str] = None,
    author: Optional[str] = None,
    sort: str = "relevance"
) -> SearchResults:
    """
    Search for submissions.
    
    Args:
        page: Playwright page object
        query: Search query
        forum: Optional forum filter
        author: Optional author filter
        sort: Sort order (relevance, new, top)
    
    Returns:
        SearchResults with list of matching submissions
    """
    # Build URL
    url = f"{BASE_URL}search?q={query}"
    
    if forum:
        url += f"&forum={forum}"
    if author:
        url += f"&author={author}"
    if sort != "relevance":
        url += f"&sort={sort}"
    
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    
    # Get all result elements
    results = []
    elements = page.locator(f"{SUBMISSION_SELECTOR}, .search-result").all()
    
    for elem in elements:
        try:
            title_elem = elem.locator(SUBMISSION_TITLE_SELECTOR)
            if title_elem.count() == 0:
                continue
            
            title = title_elem.text_content().strip()
            link = title_elem.get_attribute("href") or ""
            
            author_elem = elem.locator(SUBMISSION_AUTHOR_SELECTOR)
            author = author_elem.text_content().strip() if author_elem.count() > 0 else ""
            
            forum_elem = elem.locator(SUBMISSION_FORUM_SELECTOR)
            forum = forum_elem.text_content().strip() if forum_elem.count() > 0 else ""
            
            score_elem = elem.locator(SUBMISSION_SCORE_SELECTOR)
            score = score_elem.text_content().strip() if score_elem.count() > 0 else "0"
            
            results.append(SearchResult(
                title=title,
                link=link,
                author=author,
                forum=forum,
                score=score
            ))
        except:
            continue
    
    return SearchResults(True, results)
