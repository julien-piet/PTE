#!/usr/bin/env python3
"""
Wikipedia API module.

This module exposes the Wikipedia Kiwix instance API endpoints to the agent,
allowing programmatic access to Wikipedia articles, search functionality,
and random article retrieval.

The Wikipedia instance is a Kiwix-hosted snapshot from May 2022 containing
the full English Wikipedia. It provides fast, offline-capable access to
Wikipedia content without requiring internet connectivity.

Key capabilities:
- Article retrieval by exact title
- Full-text search across all articles
- Random article discovery
- Image and media file access
- Metadata retrieval

Base URL: http://ec2-18-218-205-96.us-east-2.compute.amazonaws.com:8081/wikipedia_en_all_maxi_2022-05
"""

from __future__ import annotations

from typing import List, Optional

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

# Give the server a descriptive name; this string shows up in logs/prompts.
mcp = FastMCP("Wikipedia Kiwix")

# ---------------------------------------------------------------------------
# SERVER CONFIGURATION
# ---------------------------------------------------------------------------

# Wikipedia instance base URL
WIKIPEDIA_BASE_URL = "http://ec2-18-218-205-96.us-east-2.compute.amazonaws.com:8081/wikipedia_en_all_maxi_2022-05"

# HTTP client for making requests
http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)


# ---------------------------------------------------------------------------
# DATA MODELS
# ---------------------------------------------------------------------------


class Article(BaseModel):
    """Wikipedia article data structure"""

    title: str = Field(description="Article title")
    url: str = Field(description="Full URL to the article")
    content_html: str = Field(description="Full HTML content of the article")
    content_length: int = Field(description="Length of content in characters")
    status_code: int = Field(description="HTTP status code of the response")


class SearchResult(BaseModel):
    """Individual search result from Wikipedia"""

    title: str = Field(description="Article title")
    url: str = Field(description="Full URL to the article")
    snippet: Optional[str] = Field(
        default=None, description="Text snippet or preview from the article"
    )


class SearchResponse(BaseModel):
    """Search results containing multiple matches"""

    query: str = Field(description="Original search query")
    results: List[SearchResult] = Field(
        default_factory=list, description="List of matching articles"
    )
    total_results: int = Field(description="Total number of results found")
    search_url: str = Field(description="URL used for the search")


class RandomArticle(BaseModel):
    """Random article information"""

    title: str = Field(description="Title of the random article")
    url: str = Field(description="Full URL to the article")
    content_html: str = Field(description="HTML content of the article")
    content_length: int = Field(description="Length of content in characters")


class Metadata(BaseModel):
    """Wikipedia instance metadata"""

    base_url: str = Field(description="Base URL of the Wikipedia instance")
    version: str = Field(
        default="wikipedia_en_all_maxi_2022-05",
        description="Wikipedia snapshot version",
    )
    language: str = Field(default="en", description="Wikipedia language code")
    snapshot_date: str = Field(
        default="2022-05", description="Date of the Wikipedia snapshot"
    )


# ============================================================================
# SDK - Article Retrieval
# ============================================================================


@mcp.tool()
async def get_article(article_title: str) -> Article:
    """
    Retrieve a specific Wikipedia article by its exact title.

    This function fetches the complete HTML content of a Wikipedia article.
    The article title must match the exact Wikipedia article name, including
    proper capitalization and underscores for spaces.

    Args:
        article_title (str): The exact title of the Wikipedia article.
                            Use underscores for spaces (e.g., 'Python_(programming_language)')
                            or URL encoding for special characters.

    Returns:
        article (Article): The article data including title, URL, and full HTML content.

    Examples:
        - get_article("Python_(programming_language)")
        - get_article("Machine_learning")
        - get_article("Artificial_intelligence")
    """

    # Construct article URL
    article_url = f"{WIKIPEDIA_BASE_URL}/A/{article_title}"

    # Fetch article
    response = await http_client.get(article_url)

    return Article(
        title=article_title,
        url=article_url,
        content_html=response.text,
        content_length=len(response.text),
        status_code=response.status_code,
    )


@mcp.tool()
async def get_main_page() -> Article:
    """
    Retrieve the Wikipedia main page.

    This function fetches the main landing page of Wikipedia, which typically
    contains featured articles, current events, and links to popular content.

    Returns:
        article (Article): The main page content including HTML.
    """

    main_page_url = f"{WIKIPEDIA_BASE_URL}/A/Main_Page"

    response = await http_client.get(main_page_url)

    return Article(
        title="Main_Page",
        url=main_page_url,
        content_html=response.text,
        content_length=len(response.text),
        status_code=response.status_code,
    )


# ============================================================================
# SDK - Search Functionality
# ============================================================================


@mcp.tool()
async def search_articles(query: str, limit: int = 10) -> SearchResponse:
    """
    Search Wikipedia for articles matching a query string.

    This function performs a full-text search across Wikipedia articles and
    returns a list of matching results. The search is case-insensitive and
    matches article titles and content.

    Args:
        query (str): The search query string (e.g., "quantum physics", "world war")
        limit (int): Maximum number of results to return (default: 10, max: 50)

    Returns:
        results (SearchResponse): Search results containing matched articles with
                                 titles, URLs, and snippets.

    Examples:
        - search_articles("artificial intelligence")
        - search_articles("python programming", limit=5)
        - search_articles("renaissance art")
    """

    # Ensure limit is reasonable
    limit = min(limit, 50)

    # Construct search URL
    search_url = f"{WIKIPEDIA_BASE_URL}/search?q={query}"

    # Fetch search results
    response = await http_client.get(search_url)

    # Parse HTML response to extract search results
    # Note: This is a simplified implementation
    # In production, you would parse the HTML to extract actual search results
    results = _parse_search_results(response.text, query, limit)

    return SearchResponse(
        query=query,
        results=results,
        total_results=len(results),
        search_url=search_url,
    )


# ============================================================================
# SDK - Random Article
# ============================================================================


@mcp.tool()
async def get_random_article() -> RandomArticle:
    """
    Retrieve a random Wikipedia article.

    This function fetches a randomly selected article from Wikipedia, useful
    for discovery and exploration purposes.

    Returns:
        article (RandomArticle): A random article with full content.

    Examples:
        - get_random_article()  # Returns any random Wikipedia article
    """

    # Random article endpoint
    random_url = f"{WIKIPEDIA_BASE_URL}/M/Random"

    # Fetch random article (will redirect to actual article)
    response = await http_client.get(random_url)

    # Extract title from final URL after redirect
    final_url = str(response.url)
    article_title = final_url.split("/A/")[-1] if "/A/" in final_url else "Random"

    return RandomArticle(
        title=article_title,
        url=final_url,
        content_html=response.text,
        content_length=len(response.text),
    )


# ============================================================================
# SDK - Metadata and Information
# ============================================================================


@mcp.tool()
async def get_wikipedia_metadata() -> Metadata:
    """
    Get metadata about the Wikipedia instance.

    This function returns information about the Wikipedia snapshot being used,
    including version, language, and snapshot date.

    Returns:
        metadata (Metadata): Information about the Wikipedia instance.
    """

    return Metadata(
        base_url=WIKIPEDIA_BASE_URL,
        version="wikipedia_en_all_maxi_2022-05",
        language="en",
        snapshot_date="2022-05",
    )


@mcp.tool()
async def check_article_exists(article_title: str) -> bool:
    """
    Check if a Wikipedia article exists.

    This function quickly checks whether an article with the given title
    exists in the Wikipedia instance without retrieving the full content.

    Args:
        article_title (str): The exact title of the article to check.

    Returns:
        exists (bool): True if the article exists, False otherwise.

    Examples:
        - check_article_exists("Python_(programming_language)")  # Returns: True
        - check_article_exists("NonexistentArticle123")  # Returns: False
    """

    article_url = f"{WIKIPEDIA_BASE_URL}/A/{article_title}"

    try:
        response = await http_client.head(article_url)
        return response.status_code == 200
    except Exception:
        return False

# ============================================================================
# Additional Tools - Article Variants
# ============================================================================


@mcp.tool()
async def get_article_by_url(full_url: str) -> Article:
    """
    Retrieve a Wikipedia article using its full URL.

    This function allows retrieving an article when you have the complete
    URL rather than just the title.

    Args:
        full_url (str): The complete URL to the Wikipedia article.

    Returns:
        article (Article): The article content.

    Examples:
        - get_article_by_url("http://.../A/Python_(programming_language)")
    """

    response = await http_client.get(full_url)

    # Extract title from URL
    article_title = full_url.split("/A/")[-1] if "/A/" in full_url else "Unknown"

    return Article(
        title=article_title,
        url=full_url,
        content_html=response.text,
        content_length=len(response.text),
        status_code=response.status_code,
    )


@mcp.tool()
async def get_multiple_articles(article_titles: List[str]) -> List[Article]:
    """
    Retrieve multiple Wikipedia articles in a single call.

    This function efficiently fetches multiple articles at once, useful for
    comparative analysis or when you need information from several related
    articles.

    Args:
        article_titles (List[str]): List of article titles to retrieve.

    Returns:
        articles (List[Article]): List of articles with their content.

    Examples:
        - get_multiple_articles(["Python_(programming_language)", "JavaScript", "Ruby_(programming_language)"])
    """

    articles = []

    for title in article_titles:
        try:
            article = await get_article(title)
            articles.append(article)
        except Exception as e:
            # Continue with other articles if one fails
            continue

    return articles
