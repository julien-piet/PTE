"""Shared constants for the reddit_pw package."""

import os

# Reddit domain - override via environment variable
REDDIT_DOMAIN = os.getenv("REDDIT_DOMAIN", "http://localhost:9999")

# Authentication URLs
LOGIN_URL = f"{REDDIT_DOMAIN}/login"
REGISTRATION_URL = f"{REDDIT_DOMAIN}/registration"

# Content URLs
SUBMIT_URL = f"{REDDIT_DOMAIN}/submit"
CREATE_FORUM_URL = f"{REDDIT_DOMAIN}/create_forum"
MESSAGES_URL = f"{REDDIT_DOMAIN}/messages"


def get_user_profile_url(username: str) -> str:
    """Get the profile URL for a user."""
    return f"{REDDIT_DOMAIN}/user/{username}"


def get_user_account_url(username: str) -> str:
    """Get the account settings URL for a user."""
    return f"{REDDIT_DOMAIN}/user/{username}/account"


def get_user_block_list_url(username: str) -> str:
    """Get the block list URL for a user."""
    return f"{REDDIT_DOMAIN}/user/{username}/block_list"


def get_block_user_url(username_to_block: str) -> str:
    """Get the URL to block a specific user."""
    return f"{REDDIT_DOMAIN}/user/{username_to_block}/block_user"


def get_compose_message_url(recipient_username: str) -> str:
    """Get the URL to compose a message to a user."""
    return f"{REDDIT_DOMAIN}/user/{recipient_username}/compose_message"


def get_forum_url(forum_name: str) -> str:
    """Get the URL for a forum/subreddit."""
    return f"{REDDIT_DOMAIN}/f/{forum_name}"


def get_post_url(forum_name: str, post_id: str) -> str:
    """Get the URL for a specific post."""
    return f"{REDDIT_DOMAIN}/f/{forum_name}/{post_id}"


# Common selectors used across modules
class Selectors:
    """CSS selectors for Reddit UI elements."""

    # Login form
    LOGIN_USERNAME_INPUT = "input#login-username"
    LOGIN_PASSWORD_INPUT = "input#login-password"
    LOGIN_SUBMIT_BUTTON = 'button[type="submit"]'

    # Registration form
    REGISTER_USERNAME_INPUT = "input#user_username"
    REGISTER_PASSWORD_FIRST = "input#user_password_first"
    REGISTER_PASSWORD_SECOND = "input#user_password_second"
    REGISTER_SUBMIT_BUTTON = 'button:has-text("Sign up")'

    # Post creation form
    POST_TITLE_INPUT = "#submission_title"
    POST_BODY_INPUT = "#submission_body"
    POST_FORUM_SELECT = "#submission_forum"
    POST_SUBMIT_BUTTON = 'button:has-text("Create submission")'

    # Forum creation form
    FORUM_NAME_INPUT = "#forum_name"
    FORUM_TITLE_INPUT = "#forum_title"
    FORUM_DESCRIPTION_INPUT = "#forum_description"
    FORUM_SIDEBAR_INPUT = "#forum_sidebar"
    FORUM_SUBMIT_BUTTON = 'button:has-text("Create forum")'

    # Comment form (post_id is dynamic)
    @staticmethod
    def get_comment_input(post_id: str) -> str:
        """Get the selector for the comment input field."""
        return f"#reply_to_submission_{post_id}_comment"

    COMMENT_SUBMIT_BUTTON = 'button:has-text("Post")'

    # Message form
    MESSAGE_BODY_INPUT = "#message_body"
    MESSAGE_SUBMIT_BUTTON = 'button:has-text("Send")'
    MESSAGE_THREAD_LINKS = 'a[href*="messages/thread"]'

    # Account settings
    ACCOUNT_EMAIL_INPUT = "#user_email"
    ACCOUNT_SAVE_BUTTON = 'button:has-text("Save changes")'

    # Block user
    BLOCK_SUBMIT_BUTTON = 'button:has-text("Block")'

    # Delete button (used across various pages)
    DELETE_BUTTON = 'button:has-text("Delete")'

    # Error messages
    ALREADY_USED_ERROR = "This value is already used"
