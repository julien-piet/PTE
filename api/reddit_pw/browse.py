"""Browse forums and submissions."""

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
    SUBMISSION_COMMENTS_SELECTOR,
)


@dataclass
class Submission:
    """A single submission/post."""
    
    title: str
    link: str
    author: str
    forum: str
    score: str
    comments: str = "0"


@dataclass
class BrowseResult:
    """Result of browsing posts."""
    
    success: bool
    submissions: List[Submission]
    error_message: Optional[str] = None


def browse_frontpage(page: Page, sort: str = "hot", scope: str = "all") -> BrowseResult:
    """
    Browse the frontpage.
    
    Args:
        page: Playwright page object
        sort: Sort order (hot, new, top, etc.)
        scope: "featured" or "all" submissions
    
    Returns:
        BrowseResult with list of submissions
    """
    # Build URL
    if scope == "all":
        url = f"{BASE_URL}all/{sort}"
    else:
        url = f"{BASE_URL}{sort}" if sort != "hot" else BASE_URL
    
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    
    # Get all submission elements
    submissions = []
    elements = page.locator(SUBMISSION_SELECTOR).all()
    
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
            
            submissions.append(Submission(
                title=title,
                link=link,
                author=author,
                forum=forum,
                score=score
            ))
        except:
            continue
    
    return BrowseResult(True, submissions)


def browse_forum(page: Page, forum_name: str, sort: str = "hot") -> BrowseResult:
    """
    Browse a specific forum.
    
    Args:
        page: Playwright page object
        forum_name: Name of the forum (e.g., "technology")
        sort: Sort order (hot, new, top, etc.)
    
    Returns:
        BrowseResult with list of submissions
    """
    url = f"{BASE_URL}f/{forum_name}/{sort}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    
    # Check if forum not found
    if page.locator("h1:has-text('Not Found')").count() > 0:
        return BrowseResult(False, [], f"Forum '{forum_name}' not found")
    
    # Get all submission elements
    submissions = []
    elements = page.locator(SUBMISSION_SELECTOR).all()
    
    for elem in elements:
        try:
            title_elem = elem.locator(SUBMISSION_TITLE_SELECTOR)
            if title_elem.count() == 0:
                continue
            
            title = title_elem.text_content().strip()
            link = title_elem.get_attribute("href") or ""
            
            author_elem = elem.locator(SUBMISSION_AUTHOR_SELECTOR)
            author = author_elem.text_content().strip() if author_elem.count() > 0 else ""
            
            score_elem = elem.locator(SUBMISSION_SCORE_SELECTOR)
            score = score_elem.text_content().strip() if score_elem.count() > 0 else "0"
            
            comments_elem = elem.locator(SUBMISSION_COMMENTS_SELECTOR)
            comments = comments_elem.text_content().strip() if comments_elem.count() > 0 else "0"
            
            submissions.append(Submission(
                title=title,
                link=link,
                author=author,
                forum=forum_name,
                score=score,
                comments=comments
            ))
        except:
            continue
    
    return BrowseResult(True, submissions)
