"""Shared constants for the gitlab_pw package."""

import os

# GitLab domain - override via environment variable
GITLAB_DOMAIN = os.getenv("GITLAB_DOMAIN", "http://localhost:8023")

# Authentication URLs
LOGIN_URL = f"{GITLAB_DOMAIN}/users/sign_in"
SIGNUP_URL = f"{GITLAB_DOMAIN}/users/sign_up"

# Dashboard and navigation
DASHBOARD_URL = f"{GITLAB_DOMAIN}"
DASHBOARD_PROJECTS_URL = f"{GITLAB_DOMAIN}/dashboard/projects"
DASHBOARD_GROUPS_URL = f"{GITLAB_DOMAIN}/dashboard/groups"

# Profile and account
PROFILE_URL = f"{GITLAB_DOMAIN}/-/profile"
ACCOUNT_URL = f"{GITLAB_DOMAIN}/-/profile/account"
SSH_KEYS_URL = f"{GITLAB_DOMAIN}/-/profile/keys"
ACCESS_TOKENS_URL = f"{GITLAB_DOMAIN}/-/profile/personal_access_tokens"

# Project creation
NEW_PROJECT_URL = f"{GITLAB_DOMAIN}/projects/new#blank_project"
NEW_GROUP_URL = f"{GITLAB_DOMAIN}/groups/new#create-group-pane"


def get_project_url(namespace: str, project: str) -> str:
    """Get the base URL for a project."""
    return f"{GITLAB_DOMAIN}/{namespace}/{project}"


def get_project_issues_url(namespace: str, project: str) -> str:
    """Get the issues list URL for a project."""
    return f"{GITLAB_DOMAIN}/{namespace}/{project}/-/issues"


def get_new_issue_url(namespace: str, project: str) -> str:
    """Get the new issue form URL for a project."""
    return f"{GITLAB_DOMAIN}/{namespace}/{project}/-/issues/new"


def get_issue_url(namespace: str, project: str, issue_number: int) -> str:
    """Get the URL for a specific issue."""
    return f"{GITLAB_DOMAIN}/{namespace}/{project}/-/issues/{issue_number}"


def get_project_branches_url(namespace: str, project: str) -> str:
    """Get the branches list URL for a project."""
    return f"{GITLAB_DOMAIN}/{namespace}/{project}/-/branches"


def get_new_branch_url(namespace: str, project: str) -> str:
    """Get the new branch form URL."""
    return f"{GITLAB_DOMAIN}/{namespace}/{project}/-/branches/new"


def get_new_file_url(namespace: str, project: str, branch: str) -> str:
    """Get the new file form URL for a branch."""
    return f"{GITLAB_DOMAIN}/{namespace}/{project}/-/new/{branch}"


def get_file_url(namespace: str, project: str, branch: str, filename: str) -> str:
    """Get the URL for a specific file on a branch."""
    return f"{GITLAB_DOMAIN}/{namespace}/{project}/-/blob/{branch}/{filename}"


def get_project_merge_requests_url(namespace: str, project: str) -> str:
    """Get the merge requests list URL for a project."""
    return f"{GITLAB_DOMAIN}/{namespace}/{project}/-/merge_requests"


def get_new_merge_request_url(namespace: str, project: str, source_branch: str) -> str:
    """Get the new merge request form URL."""
    return f"{GITLAB_DOMAIN}/{namespace}/{project}/-/merge_requests/new?merge_request%5Bsource_branch%5D={source_branch}"


def get_merge_request_url(namespace: str, project: str, mr_number: int) -> str:
    """Get the URL for a specific merge request."""
    return f"{GITLAB_DOMAIN}/{namespace}/{project}/-/merge_requests/{mr_number}"


def get_project_settings_url(namespace: str, project: str) -> str:
    """Get the project settings/edit URL."""
    return f"{GITLAB_DOMAIN}/{namespace}/{project}/edit"


def get_group_url(group_name: str) -> str:
    """Get the base URL for a group."""
    return f"{GITLAB_DOMAIN}/groups/{group_name}"


def get_group_members_url(group_name: str) -> str:
    """Get the group members management URL."""
    return f"{GITLAB_DOMAIN}/groups/{group_name}/-/group_members"


def get_group_settings_url(group_name: str) -> str:
    """Get the group settings/edit URL."""
    return f"{GITLAB_DOMAIN}/groups/{group_name}/-/edit"


def get_deploy_keys_url(namespace: str, project: str) -> str:
    """Get the deploy keys URL for a project."""
    return f"{GITLAB_DOMAIN}/{namespace}/{project}/-/deploy_keys"


def get_deploy_tokens_url(namespace: str, project: str) -> str:
    """Get the deploy tokens URL for a project."""
    return f"{GITLAB_DOMAIN}/{namespace}/{project}/-/settings/repository#js-deploy-tokens"


def get_webhooks_url(namespace: str, project: str) -> str:
    """Get the webhooks URL for a project."""
    return f"{GITLAB_DOMAIN}/{namespace}/{project}/-/hooks"


# Common selectors used across modules
class Selectors:
    """CSS selectors for GitLab UI elements."""

    # Login form
    LOGIN_USERNAME_INPUT = "input#user_login"
    LOGIN_PASSWORD_INPUT = "input#user_password"
    LOGIN_SUBMIT_BUTTON = 'button[type="submit"]'

    # Survey page (appears for new accounts)
    SURVEY_ROLE_SELECT = "#user_role"
    SURVEY_SUBMIT_BUTTON = 'button:has-text("Get started!")'

    # Issue form
    ISSUE_TITLE_INPUT = "#issue_title"
    ISSUE_DESCRIPTION_TEXTAREA = "textarea#issue_description"
    ISSUE_CREATE_BUTTON = 'button:has-text("Create issue")'

    # Issue actions
    ISSUE_ACTIONS_BUTTON = 'button:has-text("Issue actions")'
    DELETE_ISSUE_BUTTON = '[data-qa-selector="delete_issue_button"]'
    DELETE_ISSUE_MODAL = "div#delete-modal-id___BV_modal_body_"
    CONFIRM_DELETE_ISSUE_BUTTON = '[data-qa-selector="confirm_delete_issue_button"]'
    ISSUE_TITLE_LINK = "a[data-qa-selector='issuable_title_link']"

    # Project form
    PROJECT_NAME_INPUT = "#project_name, input[data-qa-selector='project_name']"
    PROJECT_CREATE_BUTTON = 'button:has-text("Create project")'
    PROJECT_VISIBILITY_PRIVATE = "#blank-project-pane :text('PrivateProject access must be')"
    NAMESPACE_DROPDOWN_BUTTON = "button#__BVID__16__BV_toggle_"

    # Group form
    GROUP_NAME_INPUT = "#group_name"
    GROUP_VISIBILITY_PRIVATE = "label[for='group_visibility_level_0']"
    GROUP_ROLE_SELECT = "#user_role"
    GROUP_SETUP_COMPANY = "label[for='group_setup_for_company_true']"
    GROUP_JOBS_SELECT = "#group_jobs_to_be_done"
    GROUP_CREATE_BUTTON = 'button:has-text("Create group")'

    # Branch form
    BRANCH_NAME_INPUT = "input#branch_name"
    BRANCH_CREATE_BUTTON = "#new-branch-form > div.form-actions > button"
    BRANCH_ITEM = "li.branch-item"
    BRANCH_DELETE_BUTTON = "button.js-delete-branch-button"
    BRANCH_DELETE_CONFIRM = "#delete-branch-modal___BV_modal_footer_ > div > button.btn.btn-danger.btn-md.gl-button"

    # File form
    FILE_NAME_INPUT = "#file_name"
    FILE_COMMIT_BUTTON = "#commit-changes"
    FILE_REPLACE_BUTTON = '[data-testid="replace"]'
    FILE_UPLOAD_INPUT = 'input[name="upload_file"]'
    FILE_REPLACE_MODAL = "#modal-replace-blob___BV_modal_body_"
    FILE_REPLACE_CONFIRM = "#modal-replace-blob___BV_modal_footer_ > button.btn.js-modal-action-primary.btn-confirm.btn-md.gl-button"

    # Merge request form
    MR_TITLE_INPUT = "#merge_request_title"
    MR_CREATE_BUTTON = "#new_merge_request > div.gl-mt-5.middle-block > button"
    MR_CLOSE_BUTTON = "#notes > div.js-comment-form > ul > li > div > div > form > div.note-form-actions > button"
    MR_STATUS_SPAN = "#content-body > div.merge-request > div.merge-request-details.issuable-details > div.detail-page-description.py-2.gl-display-flex.gl-align-items-center.gl-flex-wrap > span > span"

    # Settings and deletion
    EXPAND_BUTTON = 'button:has-text("Expand")'
    DELETE_PROJECT_SECTION = "#js-project-advanced-settings"
    DELETE_PROJECT_BUTTON = 'button:has-text("Delete project")'
    DELETE_PROJECT_CONFIRM = 'button:has-text("Yes, delete project")'
    DELETE_GROUP_SECTION = "#js-advanced-settings"
    DELETE_GROUP_BUTTON = 'button:has-text("Remove group")'
    DELETE_GROUP_CONFIRM = 'button:has-text("Confirm")'
    CONFIRM_NAME_INPUT = "input#confirm_name_input"

    # Profile settings
    PRIVATE_PROFILE_CHECKBOX = "label[for='user_private_profile']"
    UPDATE_PROFILE_BUTTON = 'button:has-text("Update profile settings")'
    USERNAME_INPUT = "#username-change-input"
    USERNAME_CHANGE_TRIGGER = '[data-testid="username-change-confirmation-modal"]'
    USERNAME_CHANGE_CONFIRM = "#username-change-confirmation-modal___BV_modal_footer_ > button.btn.js-modal-action-primary.btn-confirm.btn-md.gl-button"

    # Account deletion
    DELETE_ACCOUNT_BUTTON = 'button:has-text("Delete account")'
    PASSWORD_CONFIRM_FIELD = '[data-qa-selector="password_confirmation_field"]'
    CONFIRM_DELETE_ACCOUNT = '[data-qa-selector="confirm_delete_account_button"]'

    # Group members
    INVITE_MEMBERS_BUTTON = 'button:has-text("Invite members")'
    INVITE_MODAL = "#invite-members-modal-2___BV_modal_content_"
    INVITE_SEARCH_INPUT = "input#invite-members-modal-2_search"
    INVITE_ROLE_SELECT = "#invite-members-modal-2_dropdown"
    INVITE_CONFIRM_BUTTON = '#invite-members-modal-2___BV_modal_content_ button:has-text("Invite")'
    MEMBERS_TABLE = "table[data-testid='members-table']"

    # Error and success messages
    ERROR_CONTAINER = "div#error_explanation"
    PROJECT_ERROR_CONTAINER = "div.project-edit-errors"
    FLASH_CONTAINER = '[data-qa-selector="flash_container"]'
    ALERT_BODY = "div.gl-alert-body"
    PAGE_NOT_FOUND = "div.container h3"

    # User registration
    SIGNUP_FIRST_NAME = "#new_user_first_name"
    SIGNUP_LAST_NAME = "#new_user_last_name"
    SIGNUP_USERNAME = "#new_user_username"
    SIGNUP_EMAIL = "#new_user_email"
    SIGNUP_PASSWORD = "#new_user_password"
    SIGNUP_REGISTER_BUTTON = '[data-qa-selector="new_user_register_button"]'
