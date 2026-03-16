"""Reddit automation helpers split into focused modules."""

from .constants import (
    REDDIT_DOMAIN,
    LOGIN_URL,
    REGISTRATION_URL,
    SUBMIT_URL,
    CREATE_FORUM_URL,
    MESSAGES_URL,
    Selectors,
    get_user_profile_url,
    get_user_account_url,
    get_user_block_list_url,
    get_block_user_url,
    get_compose_message_url,
    get_forum_url,
    get_post_url,
)
from .login import (
    LoginResult,
    UserCreationResult,
    login_user,
    create_user,
    is_logged_in,
)
from .posts import (
    Post,
    CreatePostResult,
    DeletePostResult,
    create_post,
    create_post_with_title_and_text,
    delete_post,
    delete_post_by_url,
    delete_all_posts_by_username,
    get_posts_by_username,
)
from .forums import (
    Forum,
    CreateForumResult,
    create_forum,
    get_forum_info,
    forum_exists,
)
from .comments import (
    Comment,
    CommentResult,
    DeleteCommentResult,
    comment_on_post,
    comment_on_post_by_url,
    delete_all_comments_on_post,
    delete_all_comments_on_post_by_user,
    get_comments_on_post,
)
from .messages import (
    Message,
    MessageResult,
    DeleteMessagesResult,
    send_message,
    delete_all_messages,
    delete_all_messages_by_user,
    get_message_threads,
)
from .users import (
    BlockUserResult,
    UnblockUserResult,
    ResetEmailResult,
    UpdateEmailResult,
    UserInfo,
    block_user,
    unblock_user,
    reset_email,
    update_email,
    get_user_info,
    user_exists,
    get_blocked_users,
)

__all__ = [
    # Constants
    "REDDIT_DOMAIN",
    "LOGIN_URL",
    "REGISTRATION_URL",
    "SUBMIT_URL",
    "CREATE_FORUM_URL",
    "MESSAGES_URL",
    "Selectors",
    # URL helpers
    "get_user_profile_url",
    "get_user_account_url",
    "get_user_block_list_url",
    "get_block_user_url",
    "get_compose_message_url",
    "get_forum_url",
    "get_post_url",
    # Login dataclasses
    "LoginResult",
    "UserCreationResult",
    # Login functions
    "login_user",
    "create_user",
    "is_logged_in",
    # Post dataclasses
    "Post",
    "CreatePostResult",
    "DeletePostResult",
    # Post functions
    "create_post",
    "create_post_with_title_and_text",
    "delete_post",
    "delete_post_by_url",
    "delete_all_posts_by_username",
    "get_posts_by_username",
    # Forum dataclasses
    "Forum",
    "CreateForumResult",
    # Forum functions
    "create_forum",
    "get_forum_info",
    "forum_exists",
    # Comment dataclasses
    "Comment",
    "CommentResult",
    "DeleteCommentResult",
    # Comment functions
    "comment_on_post",
    "delete_all_comments_on_post",
    "delete_all_comments_on_post_by_user",
    "get_comments_on_post",
    # Message dataclasses
    "Message",
    "MessageResult",
    "DeleteMessagesResult",
    # Message functions
    "send_message",
    "delete_all_messages",
    "delete_all_messages_by_user",
    "get_message_threads",
    # User dataclasses
    "BlockUserResult",
    "UnblockUserResult",
    "ResetEmailResult",
    "UpdateEmailResult",
    "UserInfo",
    # User functions
    "block_user",
    "unblock_user",
    "reset_email",
    "update_email",
    "get_user_info",
    "user_exists",
    "get_blocked_users",
]
