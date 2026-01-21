"""Reddit/Postmill helpers split into focused modules."""

from .constants import (
    BASE_URL,
    LOGIN_URL,
    REGISTRATION_URL,
    FRONTPAGE_URL,
    # Selectors
    LOGIN_USERNAME_SELECTOR,
    LOGIN_PASSWORD_SELECTOR,
    LOGIN_REMEMBER_SELECTOR,
    LOGIN_SUBMIT_SELECTOR,
    REGISTRATION_USERNAME_SELECTOR,
    REGISTRATION_EMAIL_SELECTOR,
    REGISTRATION_PASSWORD_FIRST_SELECTOR,
    REGISTRATION_PASSWORD_SECOND_SELECTOR,
    REGISTRATION_SUBMIT_SELECTOR,
    ERROR_SELECTOR,
    SUCCESS_SELECTOR,
)
from .login import LoginResult, login_user
from .logout import LogoutResult, logout_user
from .registration import RegistrationResult, register_user
from .browse import (
    Submission,
    BrowseResult,
    browse_frontpage,
    browse_forum,
)
from .search import (
    SearchResult,
    SearchResults,
    search_submissions,
)

__all__ = [
    # Constants - URLs
    "BASE_URL",
    "LOGIN_URL",
    "REGISTRATION_URL",
    "FRONTPAGE_URL",
    # Constants - Selectors
    "LOGIN_USERNAME_SELECTOR",
    "LOGIN_PASSWORD_SELECTOR",
    "LOGIN_REMEMBER_SELECTOR",
    "LOGIN_SUBMIT_SELECTOR",
    "REGISTRATION_USERNAME_SELECTOR",
    "REGISTRATION_EMAIL_SELECTOR",
    "REGISTRATION_PASSWORD_FIRST_SELECTOR",
    "REGISTRATION_PASSWORD_SECOND_SELECTOR",
    "REGISTRATION_SUBMIT_SELECTOR",
    "ERROR_SELECTOR",
    "SUCCESS_SELECTOR",
    # Login
    "LoginResult",
    "login_user",
    # Logout
    "LogoutResult",
    "logout_user",
    # Registration
    "RegistrationResult",
    "register_user",
    # Browse
    "Submission",
    "BrowseResult",
    "browse_frontpage",
    "browse_forum",
    # Search
    "SearchResult",
    "SearchResults",
    "search_submissions",
]
