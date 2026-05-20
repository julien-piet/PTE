"""
Canonical server base URLs for all WebArena sites.

Import from here rather than hardcoding URLs anywhere in the codebase:
    from config.base_urls import SERVER_URLS

Multi-docker mode ignores SERVER_URLS — the worker pool provides per-task
URLs dynamically. These values are the single-server defaults.
"""

# server name → base URL (used by agent, runners, refresh scripts, and evaluators)
SERVER_URLS: dict = {
    "gitlab":         "http://127.0.0.1:8023",  # GitLab
    "reddit":         "http://127.0.0.1:9999",  # Reddit (Postmill)
    "shopping":       "http://127.0.0.1:7770",  # OneStopShopping (Magento)
    "shopping_admin": "http://127.0.0.1:7780",  # Luma shopping
    "wikipedia":      "http://127.0.0.1:8889",  # Wikipedia
    "shopping_extra": "http://127.0.0.1:7790",  # Shopping extra FastAPI
}
