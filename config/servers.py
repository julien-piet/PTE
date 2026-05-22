"""
Server definitions: base URLs and user context for all WebArena sites.

Import from here rather than hardcoding URLs or reading user_info.json:
    from config.servers import SERVERS, SERVER_URLS

Multi-docker mode ignores SERVER_URLS — the worker pool provides per-task
URLs dynamically. These values are the single-server defaults.
"""

SERVERS: dict = {
    "gitlab": {
        "url":          "http://127.0.0.1:8023",
        "label":        "GitLab",
        "username_env": "GITLAB_USERNAME",
    },
    "reddit": {
        "url":          "http://127.0.0.1:9999",
        "label":        "Reddit",
        "username_env": "REDDIT_USERNAME",
    },
    "shopping": {
        "url":          "http://127.0.0.1:7770",
        "label":        "Shopping",
        "username_env": "SHOPPING_USERNAME",
    },
    "shopping_admin": {
        "url":          "http://127.0.0.1:7780",
        "label":        "Luma Admin",
        "username_env": None,
    },
    "wikipedia": {
        "url":          "http://127.0.0.1:8889",
        "label":        "Wikipedia",
        "username_env": None,
    },
    "shopping_extra": {
        "url":          "http://127.0.0.1:7790",
        "label":        "Shopping Extra",
        "username_env": None,
    },
}

# Convenience alias used throughout the codebase
SERVER_URLS: dict = {k: v["url"] for k, v in SERVERS.items()}
