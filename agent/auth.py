"""
Auth providers for ExecutionAgent.

All tokens are read from a .env-style file (e.g. config/.server_env).
Each server gets its own AuthProvider that knows how to format its tokens
into the correct curl headers. AuthRegistry maps server names to providers
and provides a factory that wires up all known servers from a single env file.

Adding a new server:
  1. Add its token key(s) to .server_env
  2. Register it in AuthRegistry.build_default()
"""

from abc import ABC, abstractmethod
from typing import Dict

from dotenv import dotenv_values


# ──────────────────────────────────────────────────────────────────────────────
# Base
# ──────────────────────────────────────────────────────────────────────────────

class AuthProvider(ABC):
    """Supplies HTTP headers needed for authentication."""

    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        """Return {header_name: header_value} to inject into every request."""


# ──────────────────────────────────────────────────────────────────────────────
# Concrete providers
# ──────────────────────────────────────────────────────────────────────────────

class HeaderAuth(AuthProvider):
    """
    Single token from .server_env → one request header.

    Examples:
        # GitLab PAT
        HeaderAuth(env, "GRAPHQL_TOKEN", "PRIVATE-TOKEN")

        # Shopping Bearer token
        HeaderAuth(env, "CUSTOMER_AUTH_TOKEN", "Authorization", prefix="Bearer ")
    """

    def __init__(
        self,
        env: Dict[str, str],
        env_key: str,
        header: str,
        prefix: str = "",
    ) -> None:
        token = env.get(env_key, "").strip()
        if not token:
            raise ValueError(f"Token key {env_key!r} not found or empty in env file")
        self._headers = {header: f"{prefix}{token}"}

    def get_headers(self) -> Dict[str, str]:
        return dict(self._headers)


class CookieAuth(AuthProvider):
    """
    Multiple tokens from .server_env → one "Cookie: k=v; k=v" header.

    cookie_map is an ordered dict of {cookie_name: env_key}, e.g.:
        {"token": "REDDIT_TOKEN", "phpbb3_session": "REDDIT_PHPBB_SESSION"}
    → Cookie: token=xxx; phpbb3_session=yyy

    Missing keys are skipped with a warning rather than raising, so partial
    configs still work during development.
    """

    def __init__(
        self,
        env: Dict[str, str],
        cookie_map: Dict[str, str],
    ) -> None:
        parts = []
        for cookie_name, env_key in cookie_map.items():
            value = env.get(env_key, "").strip()
            if value:
                parts.append(f"{cookie_name}={value}")
            else:
                print(f"[CookieAuth] Warning: {env_key!r} not found in env file — skipping")
        if not parts:
            raise ValueError("CookieAuth: no cookie values resolved from env file")
        self._headers = {"Cookie": "; ".join(parts)}

    def get_headers(self) -> Dict[str, str]:
        return dict(self._headers)


class MultiAuth(AuthProvider):
    """
    Combines multiple AuthProviders into one.
    Use when a server needs both cookies AND a separate auth header.

    If two providers set the same header name, the last one wins.
    """

    def __init__(self, *providers: AuthProvider) -> None:
        self._providers = providers

    def get_headers(self) -> Dict[str, str]:
        merged: Dict[str, str] = {}
        for provider in self._providers:
            merged.update(provider.get_headers())
        return merged


class StaticAuth(AuthProvider):
    """Pass headers directly — useful for tests or one-off scripts."""

    def __init__(self, headers: Dict[str, str]) -> None:
        self._headers = headers

    def get_headers(self) -> Dict[str, str]:
        return dict(self._headers)


# ──────────────────────────────────────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────────────────────────────────────

class AuthRegistry:
    """
    Maps server names to their AuthProvider.

    Usage:
        registry = AuthRegistry.build_default("config/.server_env")
        auth = registry.get("gitlab")
        agent = ExecutionAgent(base_url="...", auth=auth)
    """

    def __init__(self) -> None:
        self._registry: Dict[str, AuthProvider] = {}

    def register(self, server: str, provider: AuthProvider) -> None:
        self._registry[server] = provider

    def get(self, server: str) -> AuthProvider:
        if server not in self._registry:
            raise KeyError(
                f"No auth registered for server {server!r}. "
                f"Available: {list(self._registry.keys())}"
            )
        return self._registry[server]

    def __contains__(self, server: str) -> bool:
        return server in self._registry

    @classmethod
    def build_default(cls, env_file: str) -> "AuthRegistry":
        """
        Factory: reads env_file once and registers all known servers.

        To add a new server, add its token key(s) to .server_env and
        add a register() call below.
        """
        env = dotenv_values(env_file)
        registry = cls()

        # GitLab — PRIVATE-TOKEN header
        if env.get("GITLAB_TOKEN"):
            registry.register(
                "gitlab",
                HeaderAuth(env, "GITLAB_TOKEN", "PRIVATE-TOKEN"),
            )

        # Shopping — customer Bearer token (default) and admin Bearer token
        if env.get("CUSTOMER_AUTH_TOKEN"):
            registry.register(
                "shopping",
                HeaderAuth(env, "CUSTOMER_AUTH_TOKEN", "Authorization", prefix="Bearer "),
            )
        if env.get("ADMIN_AUTH_TOKEN"):
            registry.register(
                "shopping_admin",
                HeaderAuth(env, "ADMIN_AUTH_TOKEN", "Authorization", prefix="Bearer "),
            )

        # Reddit — cookie-based auth (token + phpbb session)
        # Add REDDIT_TOKEN and REDDIT_PHPBB_SESSION to .server_env when ready.
        if env.get("REDDIT_TOKEN"):
            registry.register(
                "reddit",
                CookieAuth(env, {
                    "token": "REDDIT_TOKEN",
                    "phpbb3_session": "REDDIT_PHPBB_SESSION",
                }),
            )

        return registry
