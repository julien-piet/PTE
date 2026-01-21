"""Reddit/Postmill constants."""

BASE_URL = "http://ec2-18-218-205-96.us-east-2.compute.amazonaws.com:8080/"

# Page URLs
LOGIN_URL = f"{BASE_URL}login"
REGISTRATION_URL = f"{BASE_URL}registration"
FRONTPAGE_URL = BASE_URL

# Selectors
LOGIN_USERNAME_SELECTOR = 'input[name="_username"]'
LOGIN_PASSWORD_SELECTOR = 'input[name="_password"]'
LOGIN_REMEMBER_SELECTOR = 'input[name="_remember_me"]'
LOGIN_SUBMIT_SELECTOR = 'button:has-text("Log in")'

REGISTRATION_USERNAME_SELECTOR = 'input[name="user[username]"]'
REGISTRATION_EMAIL_SELECTOR = 'input[name="user[email]"]'
REGISTRATION_PASSWORD_FIRST_SELECTOR = 'input[name="user[password][first]"]'
REGISTRATION_PASSWORD_SECOND_SELECTOR = 'input[name="user[password][second]"]'
REGISTRATION_SUBMIT_SELECTOR = 'button:has-text("Sign up")'

ERROR_SELECTOR = '.alert-danger, .error, .form-error'
SUCCESS_SELECTOR = '.alert-success, .success'

# Menu selectors
USER_MENU_SELECTORS = [
    'button.site-nav__mobile-toggle',
    '.dropdown__toggle',
    '.site-nav__link.dropdown__toggle',
]

LOGOUT_SELECTORS = [
    'button:has-text("Log out")',
    'a:has-text("Log out")',
    'a[href*="logout"]',
]

# Content selectors
SUBMISSION_SELECTOR = '.submission'
SUBMISSION_TITLE_SELECTOR = '.submission__title a'
SUBMISSION_AUTHOR_SELECTOR = '.submission__author a'
SUBMISSION_FORUM_SELECTOR = '.submission__forum a'
SUBMISSION_SCORE_SELECTOR = '.vote__score'
SUBMISSION_COMMENTS_SELECTOR = 'a[href*="/comment"]'

COMMENT_SELECTOR = '.comment'
COMMENT_AUTHOR_SELECTOR = '.comment__author a'
COMMENT_BODY_SELECTOR = '.comment__body'
